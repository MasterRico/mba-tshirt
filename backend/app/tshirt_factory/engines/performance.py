"""Performance Tracker - Tracks own MBA sales data for self-learning."""

import csv
import io
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.tshirt_factory.config import tsf_settings
from app.tshirt_factory.models import (
    DesignPrompt, DesignPerformance, DesignStatus,
)

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """Tracks real MBA sales data and classifies designs as winners/losers."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_performance(self, design_id: int, data: dict) -> dict:
        """Update performance data for a single design."""
        stmt = select(DesignPerformance).where(
            DesignPerformance.design_id == design_id
        )
        result = await self.db.execute(stmt)
        perf = result.scalar_one_or_none()

        if not perf:
            perf = DesignPerformance(design_id=design_id)
            self.db.add(perf)

        # Update fields
        if "asin" in data:
            perf.asin = data["asin"]
        if "units_sold" in data:
            perf.units_sold = data["units_sold"]
        if "royalties_earned" in data:
            perf.royalties_earned = data["royalties_earned"]
        if "current_bsr" in data:
            perf.current_bsr = data["current_bsr"]
            # Track best BSR
            if perf.best_bsr is None or data["current_bsr"] < (perf.best_bsr or float("inf")):
                perf.best_bsr = data["current_bsr"]
            # Append to BSR history
            history = perf.bsr_history or []
            history.append({
                "date": datetime.now(timezone.utc).isoformat(),
                "bsr": data["current_bsr"],
            })
            # Keep last 90 entries
            perf.bsr_history = history[-90:]

        if "page_views" in data:
            perf.page_views = data["page_views"]
            if perf.page_views > 0 and perf.units_sold > 0:
                perf.conversion_rate = perf.units_sold / perf.page_views

        # Calculate days live
        design_stmt = select(DesignPrompt).where(DesignPrompt.id == design_id)
        design_result = await self.db.execute(design_stmt)
        design = design_result.scalar_one_or_none()

        if design and design.upload_date:
            perf.days_live = (datetime.now(timezone.utc) - design.upload_date).days

        # Classify as winner or rotation candidate
        perf.is_winner = self._classify_winner(perf)
        perf.should_rotate = self._classify_underperformer(perf)

        # Update design status
        if design:
            if perf.is_winner:
                design.status = DesignStatus.LIVE.value
            elif perf.should_rotate:
                design.status = DesignStatus.UNDERPERFORMING.value

        perf.last_updated = datetime.now(timezone.utc)
        await self.db.flush()

        return {
            "design_id": design_id,
            "is_winner": perf.is_winner,
            "should_rotate": perf.should_rotate,
            "units_sold": perf.units_sold,
            "days_live": perf.days_live,
            "current_bsr": perf.current_bsr,
            "best_bsr": perf.best_bsr,
        }

    async def import_mba_csv(self, csv_content: str) -> dict:
        """Import MBA sales report CSV data.

        Expected CSV format (from MBA dashboard export):
        ASIN, Title, Units Sold, Royalties, ...
        """
        reader = csv.DictReader(io.StringIO(csv_content))
        updated = 0
        not_found = 0
        errors = 0

        for row in reader:
            try:
                asin = row.get("ASIN", row.get("asin", "")).strip()
                if not asin:
                    continue

                # Find matching design by ASIN
                stmt = select(DesignPerformance).where(
                    DesignPerformance.asin == asin
                )
                result = await self.db.execute(stmt)
                perf = result.scalar_one_or_none()

                if not perf:
                    # Try to find by listing title match
                    title = row.get("Title", row.get("title", ""))
                    if title:
                        stmt = select(DesignPrompt).where(
                            DesignPrompt.listing_title.ilike(f"%{title[:30]}%")
                        )
                        result = await self.db.execute(stmt)
                        design = result.scalar_one_or_none()
                        if design:
                            perf = DesignPerformance(
                                design_id=design.id,
                                asin=asin,
                            )
                            self.db.add(perf)
                        else:
                            not_found += 1
                            continue
                    else:
                        not_found += 1
                        continue

                # Update performance data
                units = row.get("Units Ordered", row.get("units_sold", "0"))
                perf.units_sold = int(units) if units else 0

                royalties = row.get("Royalties", row.get("royalties", "0"))
                perf.royalties_earned = float(str(royalties).replace("$", "").replace(",", "") or 0)

                perf.is_winner = self._classify_winner(perf)
                perf.should_rotate = self._classify_underperformer(perf)
                perf.last_updated = datetime.now(timezone.utc)

                updated += 1

            except Exception as e:
                logger.warning(f"Error processing CSV row: {e}")
                errors += 1

        await self.db.commit()

        return {
            "updated": updated,
            "not_found": not_found,
            "errors": errors,
            "total_rows": updated + not_found + errors,
        }

    async def get_performance_summary(self) -> dict:
        """Get overall performance summary."""
        # Total designs tracked
        stmt = select(func.count(DesignPerformance.id))
        result = await self.db.execute(stmt)
        total = result.scalar() or 0

        # Winners
        stmt = select(func.count(DesignPerformance.id)).where(
            DesignPerformance.is_winner == True
        )
        result = await self.db.execute(stmt)
        winners = result.scalar() or 0

        # Total revenue
        stmt = select(func.sum(DesignPerformance.royalties_earned))
        result = await self.db.execute(stmt)
        total_revenue = result.scalar() or 0.0

        # Total units
        stmt = select(func.sum(DesignPerformance.units_sold))
        result = await self.db.execute(stmt)
        total_units = result.scalar() or 0

        # Best performer
        stmt = select(DesignPerformance).order_by(
            DesignPerformance.units_sold.desc()
        ).limit(1)
        result = await self.db.execute(stmt)
        best = result.scalar_one_or_none()

        # Win rate
        win_rate = (winners / total * 100) if total > 0 else 0

        return {
            "total_tracked": total,
            "winners": winners,
            "win_rate": round(win_rate, 1),
            "total_revenue": round(total_revenue, 2),
            "total_units": total_units,
            "avg_revenue_per_design": round(total_revenue / total, 2) if total > 0 else 0,
            "best_performer": {
                "design_id": best.design_id,
                "asin": best.asin,
                "units_sold": best.units_sold,
                "royalties": best.royalties_earned,
            } if best else None,
        }

    async def get_niche_performance(self) -> list[dict]:
        """Get performance breakdown by niche."""
        stmt = (
            select(
                DesignPrompt.niche_id,
                func.count(DesignPerformance.id).label("designs"),
                func.sum(DesignPerformance.units_sold).label("units"),
                func.sum(DesignPerformance.royalties_earned).label("revenue"),
                func.count(DesignPerformance.id).filter(
                    DesignPerformance.is_winner == True
                ).label("winners"),
            )
            .join(DesignPerformance, DesignPerformance.design_id == DesignPrompt.id)
            .group_by(DesignPrompt.niche_id)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        niche_perf = []
        for row in rows:
            niche_perf.append({
                "niche_id": row.niche_id,
                "designs": row.designs,
                "units": row.units or 0,
                "revenue": round(float(row.revenue or 0), 2),
                "winners": row.winners,
                "win_rate": round((row.winners / row.designs * 100) if row.designs > 0 else 0, 1),
            })

        niche_perf.sort(key=lambda x: x["revenue"], reverse=True)
        return niche_perf

    def _classify_winner(self, perf: DesignPerformance) -> bool:
        """Classify if a design is a winner."""
        if perf.units_sold >= 5:
            return True
        if perf.best_bsr and perf.best_bsr < tsf_settings.BSR_WINNER_THRESHOLD:
            return True
        if perf.royalties_earned >= 25.0:
            return True
        return False

    def _classify_underperformer(self, perf: DesignPerformance) -> bool:
        """Classify if a design should be rotated out."""
        if perf.days_live < tsf_settings.MIN_DAYS_BEFORE_ROTATION:
            return False
        if perf.units_sold == 0 and perf.days_live >= tsf_settings.ROTATION_DAYS:
            return True
        if (perf.current_bsr and
            perf.current_bsr > tsf_settings.BSR_UNDERPERFORMER_THRESHOLD and
            perf.days_live >= tsf_settings.MIN_DAYS_BEFORE_ROTATION):
            return True
        return False
