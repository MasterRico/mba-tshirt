"""Main Orchestrator - coordinates the active engines.

Schlank gehalten: Research-/Performance-/Learning-/Slots-Pipeline wurde entfernt
(Automatisierung laeuft extern via n8n + Harvester bzw. compliant via Keepa).
Hier bleiben Design-Generierung, Nischen-Init und die Dashboard-Daten.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tshirt_factory.engines.analysis import AnalysisEngine
from app.tshirt_factory.engines.creation import CreationEngine
from app.tshirt_factory.engines.compliance import ComplianceEngine
from app.tshirt_factory.engines.keyword import KeywordEngine
from app.tshirt_factory.models import NicheProfile

logger = logging.getLogger(__name__)

SEASON_FILE = Path(__file__).parent / "data" / "season_calendar.json"
NICHES_FILE = Path(__file__).parent / "data" / "niches.json"


class Orchestrator:
    """Coordinates the active T-Shirt Factory engines."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.analysis = AnalysisEngine(db)
        self.creation = CreationEngine(db)
        self.compliance = ComplianceEngine(db)
        self.keywords = KeywordEngine(db)

    async def run_generation_only(self, niche: str = None, count: int = 5,
                                   seasonal_event: str = None) -> list[dict]:
        """Run only design generation."""
        return await self.creation.generate_designs(
            niche_name=niche,
            count=count,
            seasonal_event=seasonal_event,
        )

    async def get_dashboard_data(self) -> dict:
        """Daten fuer das Winner-Cockpit-Dashboard."""
        upcoming = self._get_upcoming_seasonal_events()

        stmt = select(NicheProfile).where(
            NicheProfile.is_active == True
        ).order_by(NicheProfile.win_rate.desc()).limit(10)
        result = await self.db.execute(stmt)
        top_niches = result.scalars().all()

        return {
            "seasonal_upcoming": upcoming,
            "top_niches": [
                {
                    "name": n.name,
                    "category": n.category,
                    "win_rate": n.win_rate,
                    "competition": n.competition_level,
                    "designs": n.total_designs_analyzed,
                }
                for n in top_niches
            ],
        }

    async def initialize_niches(self) -> dict:
        """Initialize niche profiles from the niches.json config (einmalig)."""
        try:
            with open(NICHES_FILE) as f:
                data = json.load(f)
        except Exception as e:
            return {"error": f"Failed to load niches config: {e}"}

        created = 0
        for niche in data.get("evergreen_niches", []):
            stmt = select(NicheProfile).where(NicheProfile.name == niche["name"])
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            if not existing:
                profile = NicheProfile(
                    name=niche["name"],
                    category="evergreen",
                    top_keywords=niche.get("keywords", []),
                    top_design_types=niche.get("design_types", []),
                    top_humor_types=niche.get("humor_types", []),
                    target_audiences=niche.get("audiences", []),
                    is_active=True,
                )
                self.db.add(profile)
                created += 1

        for trend_name in data.get("trending_categories", []):
            stmt = select(NicheProfile).where(NicheProfile.name == trend_name)
            result = await self.db.execute(stmt)
            if not result.scalar_one_or_none():
                profile = NicheProfile(
                    name=trend_name,
                    category="trending",
                    is_active=True,
                )
                self.db.add(profile)
                created += 1

        await self.db.commit()
        return {"niches_created": created}

    # ─── Private Methods ──────────────────────────────────────────

    def _get_upcoming_seasonal_events(self) -> list[dict]:
        """Welche Saison-Events stehen an und brauchen Designs."""
        try:
            with open(SEASON_FILE) as f:
                data = json.load(f)
        except Exception:
            return []

        now = datetime.now(timezone.utc)
        upcoming = []

        for season in data.get("seasons", []):
            upload_start = datetime(
                now.year, season["upload_start_month"], season["upload_start_day"],
                tzinfo=timezone.utc,
            )
            event_date = datetime(
                now.year, season["date_month"], season["date_day"],
                tzinfo=timezone.utc,
            )

            if upload_start > event_date:
                if now.month >= season["upload_start_month"]:
                    event_date = event_date.replace(year=now.year + 1)
                else:
                    upload_start = upload_start.replace(year=now.year - 1)

            if upload_start <= now <= event_date:
                days_until = (event_date - now).days
                upcoming.append({
                    "event": season["event"],
                    "name": season["name"],
                    "days_until": days_until,
                    "priority": season.get("priority", "medium"),
                    "niches": season.get("niches", []),
                    "keywords": season.get("keywords", []),
                })

        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        upcoming.sort(key=lambda x: (priority_order.get(x["priority"], 3), x["days_until"]))

        return upcoming

    async def close(self):
        """Clean up resources."""
        await self.creation.close()
        await self.compliance.close()
        await self.keywords.close()
