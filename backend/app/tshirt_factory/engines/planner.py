"""Seasonal Planner - welche Saison-Designs JETZT erstellen (Lead-Time-aware).

Nutzt season_calendar.json (peak-Datum + upload_start) und sagt, fuer welche
Events das Upload-Fenster gerade offen ist (peak noch in der Zukunft, aber nah
genug, dass ein Upload jetzt noch rankt). Loest die MBA-Vorlaufzeit-Falle.
"""

import datetime
import json
from pathlib import Path

SEASON_FILE = Path(__file__).parent.parent / "data" / "season_calendar.json"


def seasonal_plan() -> dict:
    today = datetime.date.today()
    try:
        seasons = json.loads(SEASON_FILE.read_text(encoding="utf-8")).get("seasons", [])
    except Exception as e:
        return {"today": today.isoformat(), "error": str(e), "recommend_now": [], "all": []}

    plan = []
    for s in seasons:
        try:
            peak = datetime.date(today.year, s["date_month"], s["date_day"])
            if peak < today:
                peak = datetime.date(today.year + 1, s["date_month"], s["date_day"])
            ustart = None
            if s.get("upload_start_month"):
                ustart = datetime.date(peak.year, s["upload_start_month"], s["upload_start_day"])
                if ustart > peak:  # upload-start liegt im Vorjahr (z.B. Valentinstag)
                    ustart = ustart.replace(year=peak.year - 1)
            days_until_peak = (peak - today).days
            window_open = ustart is not None and ustart <= today <= peak
            plan.append({
                "event": s["event"],
                "name": s["name"],
                "priority": s.get("priority"),
                "peak": peak.isoformat(),
                "days_until_peak": days_until_peak,
                "upload_window_open": window_open,
                "upload_start": ustart.isoformat() if ustart else None,
                "niches": s.get("niches", []),
                "keywords": s.get("keywords", []),
            })
        except Exception:
            continue

    plan.sort(key=lambda x: (not x["upload_window_open"], x["days_until_peak"]))

    MIN_LEAD = 35  # genug Vorlauf, damit ein Upload noch rankt
    EXCLUDE = {"patriotic", "american", "election", "political", "religious", "christian"}

    def recommendable(p):
        if not p["upload_window_open"]:
            return False
        if p["days_until_peak"] < MIN_LEAD:
            return False  # zu spaet zum Ranken
        if any(n in EXCLUDE for n in p.get("niches", [])):
            return False  # Politik/Patriotik -> Amazon lehnt ab
        return True

    return {
        "today": today.isoformat(),
        "recommend_now": [p for p in plan if recommendable(p)],
        "all": plan,
    }
