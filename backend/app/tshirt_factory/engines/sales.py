"""MBA Account Sales Tracker — echte Konto-Verkaufsdaten (design-unabhaengig).

Parst den rohen Merch-'earnings'-Export (transaktionsbasiert), aggregiert je
(ASIN, Marketplace, Monat) und speichert idempotent in tsf_mba_sales.
"""

import csv
import io
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.tshirt_factory.models import MbaSale

logger = logging.getLogger(__name__)

# USD -> EUR fuer eine zusammengefasste Schaetzung. Bei Bedarf aktuell halten
# oder spaeter aus einem FX-Feed speisen. Die Anzeige nach Waehrung bleibt exakt.
USD_TO_EUR = 0.92
EUR_TO_EUR = 1.0
_TO_EUR = {"USD": USD_TO_EUR, "EUR": EUR_TO_EUR}


def _parse_month(raw_date: str) -> str | None:
    """'Apr 30, 2026' -> '2026-04'. Robust gegen Leerzeichen/Quotes."""
    s = (raw_date or "").strip().strip('"')
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m")
        except ValueError:
            continue
    return None


def _norm_marketplace(raw: str) -> str:
    return (raw or "").strip().lstrip(".").lower() or "com"


class SalesTracker:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def import_raw_csv(self, csv_content: str) -> dict:
        # BOM entfernen
        if csv_content and csv_content[0] == "﻿":
            csv_content = csv_content[1:]
        reader = csv.DictReader(io.StringIO(csv_content))

        # (asin, marketplace, year_month) -> aggregat
        agg: dict[tuple, dict] = {}
        skipped = 0
        for row in reader:
            asin = (row.get("ASIN") or row.get("asin") or "").strip()
            ym = _parse_month(row.get("Earning Date") or row.get("earning_date") or "")
            if not asin or not ym:
                skipped += 1
                continue
            mkt = _norm_marketplace(row.get("Marketplace") or "")
            cur = (row.get("Currency") or "USD").strip() or "USD"
            try:
                qty = int(float(row.get("Quantity") or 0))
            except ValueError:
                qty = 0
            try:
                earn = float(str(row.get("Earnings") or 0).replace(",", "").strip() or 0)
            except ValueError:
                earn = 0.0
            key = (asin, mkt, ym)
            a = agg.setdefault(key, {
                "title": "", "currency": cur, "units": 0, "earnings": 0.0,
            })
            a["units"] += qty
            a["earnings"] += earn
            a["title"] = row.get("Title") or row.get("title") or a["title"]
            a["currency"] = cur

        upserted = 0
        for (asin, mkt, ym), v in agg.items():
            stmt = select(MbaSale).where(
                MbaSale.asin == asin,
                MbaSale.marketplace == mkt,
                MbaSale.year_month == ym,
            )
            existing = (await self.db.execute(stmt)).scalar_one_or_none()
            if existing:
                existing.units = v["units"]
                existing.earnings = round(v["earnings"], 2)
                existing.title = v["title"]
                existing.currency = v["currency"]
                existing.last_updated = datetime.now(timezone.utc)
            else:
                self.db.add(MbaSale(
                    asin=asin, marketplace=mkt, year_month=ym,
                    currency=v["currency"], units=v["units"],
                    earnings=round(v["earnings"], 2),
                ))
            upserted += 1

        await self.db.commit()

        # Import-Zusammenfassung
        totals: dict[str, float] = {}
        units = 0
        months = set()
        for (asin, mkt, ym), v in agg.items():
            totals[v["currency"]] = round(totals.get(v["currency"], 0.0) + v["earnings"], 2)
            units += v["units"]
            months.add(ym)
        return {
            "rows_upserted": upserted,
            "skipped": skipped,
            "months": sorted(months),
            "units": units,
            "totals_by_currency": totals,
        }

    async def get_summary(self) -> dict:
        rows = (await self.db.execute(select(MbaSale))).scalars().all()

        totals_by_currency: dict[str, float] = {}
        total_units = 0
        by_month: dict[str, dict] = {}
        combined_eur = 0.0

        for r in rows:
            totals_by_currency[r.currency] = round(
                totals_by_currency.get(r.currency, 0.0) + (r.earnings or 0.0), 2)
            total_units += r.units or 0
            combined_eur += (r.earnings or 0.0) * _TO_EUR.get(r.currency, 1.0)
            m = by_month.setdefault(r.year_month, {"year_month": r.year_month, "units": 0, "earnings_eur": 0.0})
            m["units"] += r.units or 0
            m["earnings_eur"] += (r.earnings or 0.0) * _TO_EUR.get(r.currency, 1.0)

        # Top-Produkte ueber ASIN summiert (Units), Earnings in EUR-Schaetzung vergleichbar
        prod: dict[str, dict] = {}
        for r in rows:
            p = prod.setdefault(r.asin, {"asin": r.asin, "title": r.title, "units": 0, "earnings_eur": 0.0})
            p["units"] += r.units or 0
            p["earnings_eur"] += (r.earnings or 0.0) * _TO_EUR.get(r.currency, 1.0)
            if r.title:
                p["title"] = r.title
        top_products = sorted(prod.values(), key=lambda x: x["earnings_eur"], reverse=True)[:10]
        for p in top_products:
            p["earnings_eur"] = round(p["earnings_eur"], 2)

        months_sorted = sorted(by_month.values(), key=lambda x: x["year_month"])
        for m in months_sorted:
            m["earnings_eur"] = round(m["earnings_eur"], 2)

        return {
            "total_units": total_units,
            "totals_by_currency": totals_by_currency,
            "combined_eur_estimate": round(combined_eur, 2),
            "distinct_products": len(prod),
            "by_month": months_sorted,
            "top_products": top_products,
            "fx_note": f"EUR-Schaetzung mit 1 USD = {USD_TO_EUR} EUR",
        }
