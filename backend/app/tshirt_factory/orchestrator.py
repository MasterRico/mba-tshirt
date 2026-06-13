"""Main Orchestrator - Coordinates all engines for automated pipeline runs."""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tshirt_factory.config import tsf_settings
from app.tshirt_factory.engines.research import ResearchEngine
from app.tshirt_factory.engines.analysis import AnalysisEngine
from app.tshirt_factory.engines.creation import CreationEngine
from app.tshirt_factory.engines.compliance import ComplianceEngine
from app.tshirt_factory.engines.keyword import KeywordEngine
from app.tshirt_factory.engines.slot_manager import SlotManager
from app.tshirt_factory.engines.performance import PerformanceTracker
from app.tshirt_factory.engines.learning import LearningEngine
from app.tshirt_factory.models import NicheProfile

logger = logging.getLogger(__name__)

SEASON_FILE = Path(__file__).parent / "data" / "season_calendar.json"
NICHES_FILE = Path(__file__).parent / "data" / "niches.json"


class Orchestrator:
    """Coordinates all T-Shirt Factory engines in the correct sequence."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.research = ResearchEngine(db)
        self.analysis = AnalysisEngine(db)
        self.creation = CreationEngine(db)
        self.compliance = ComplianceEngine(db)
        self.keywords = KeywordEngine(db)
        self.slots = SlotManager(db)
        self.performance = PerformanceTracker(db)
        self.learning = LearningEngine(db)

    async def run_full_pipeline(self) -> dict:
        """Execute the complete automated pipeline.

        Sequence:
        1. Research - Collect market data
        2. Analysis - Find patterns in data
        3. Learning - Extract insights from past performance
        4. Slot Check - How many slots are available?
        5. Seasonal Check - Any upcoming events?
        6. Creation - Generate design prompts
        7. Summary - Report results
        """
        logger.info("=" * 60)
        logger.info("T-SHIRT DESIGN FACTORY - FULL PIPELINE RUN")
        logger.info("=" * 60)

        results = {"timestamp": datetime.now(timezone.utc).isoformat()}

        # Step 1: Research
        logger.info("Step 1/6: Running market research...")
        try:
            results["research"] = await self.research.run_full_research()
        except Exception as e:
            logger.error(f"Research failed: {e}")
            results["research"] = {"error": str(e)}

        # Step 2: Analysis
        logger.info("Step 2/6: Analyzing patterns...")
        try:
            results["analysis"] = await self.analysis.run_full_analysis()
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            results["analysis"] = {"error": str(e)}

        # Step 3: Learning
        logger.info("Step 3/6: Running self-learning cycle...")
        try:
            results["learning"] = await self.learning.run_learning_cycle()
        except Exception as e:
            logger.error(f"Learning failed: {e}")
            results["learning"] = {"error": str(e)}

        # Step 4: Check available slots
        logger.info("Step 4/6: Checking slot availability...")
        slot_summary = await self.slots.get_slot_summary()
        results["slots"] = slot_summary
        available_slots = slot_summary["available_slots"]

        # Step 5: Check seasonal opportunities
        logger.info("Step 5/6: Checking seasonal calendar...")
        upcoming = self._get_upcoming_seasonal_events()
        results["seasonal"] = upcoming

        # Step 6: Generate designs if slots available
        logger.info("Step 6/6: Generating design prompts...")
        if available_slots > 0:
            designs_to_create = min(available_slots, tsf_settings.DESIGNS_PER_BATCH)
            try:
                results["designs"] = await self._generate_smart_designs(
                    count=designs_to_create,
                    upcoming_events=upcoming,
                )
            except Exception as e:
                logger.error(f"Design generation failed: {e}")
                results["designs"] = {"error": str(e)}
        else:
            # Check for rotation candidates
            rotation = await self.slots.get_rotation_candidates()
            results["designs"] = {
                "generated": 0,
                "reason": "No slots available",
                "rotation_candidates": len(rotation),
            }

        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 60)

        return results

    async def run_research_only(self) -> dict:
        """Run only the research phase."""
        return await self.research.run_full_research()

    async def run_analysis_only(self) -> dict:
        """Run only the analysis phase."""
        return await self.analysis.run_full_analysis()

    async def run_generation_only(self, niche: str = None, count: int = 5,
                                   seasonal_event: str = None) -> list[dict]:
        """Run only design generation."""
        return await self.creation.generate_designs(
            niche_name=niche,
            count=count,
            seasonal_event=seasonal_event,
        )

    async def get_dashboard_data(self) -> dict:
        """Get all data needed for the dashboard."""
        slot_summary = await self.slots.get_slot_summary()
        perf_summary = await self.performance.get_performance_summary()
        learning_summary = await self.learning.get_insights_summary()
        upcoming = self._get_upcoming_seasonal_events()

        # Top niches
        stmt = select(NicheProfile).where(
            NicheProfile.is_active == True
        ).order_by(NicheProfile.win_rate.desc()).limit(10)
        result = await self.db.execute(stmt)
        top_niches = result.scalars().all()

        # Slot recommendations
        slot_recs = await self.slots.get_niche_allocation_recommendation()

        return {
            "slots": slot_summary,
            "performance": perf_summary,
            "learning": learning_summary,
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
            "slot_recommendations": slot_recs,
        }

    async def initialize_niches(self) -> dict:
        """Initialize niche profiles from the niches.json config.

        Should be called once on first setup.
        """
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

        # Add trending categories as niches
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

    async def _generate_smart_designs(self, count: int,
                                       upcoming_events: list) -> dict:
        """Generate designs with smart distribution between evergreen and seasonal."""
        generated = []

        # Allocate: 30% seasonal, 70% evergreen (if seasonal events upcoming)
        seasonal_count = 0
        if upcoming_events:
            seasonal_count = max(1, int(count * 0.3))
            evergreen_count = count - seasonal_count
        else:
            evergreen_count = count

        # Get niche allocation recommendation
        recs = await self.slots.get_niche_allocation_recommendation()
        recommended_niches = [
            r["niche"] for r in recs.get("recommendations", [])
            if r["action"] == "add"
        ]

        # Generate evergreen designs
        for i in range(evergreen_count):
            niche = recommended_niches[i % len(recommended_niches)] if recommended_niches else None
            try:
                designs = await self.creation.generate_designs(
                    niche_name=niche, count=1
                )
                generated.extend(designs)
            except Exception as e:
                logger.error(f"Evergreen design generation failed: {e}")

        # Generate seasonal designs
        for event in upcoming_events[:seasonal_count]:
            try:
                designs = await self.creation.generate_designs(
                    seasonal_event=event["event"], count=1
                )
                generated.extend(designs)
            except Exception as e:
                logger.error(f"Seasonal design generation failed: {e}")

        return {
            "total_generated": len(generated),
            "evergreen": evergreen_count,
            "seasonal": seasonal_count,
            "designs": generated,
        }

    def _get_upcoming_seasonal_events(self) -> list[dict]:
        """Check which seasonal events are coming up and need designs."""
        try:
            with open(SEASON_FILE) as f:
                data = json.load(f)
        except Exception:
            return []

        now = datetime.now(timezone.utc)
        upcoming = []

        for season in data.get("seasons", []):
            # Check if we're in the upload window
            upload_start = datetime(
                now.year, season["upload_start_month"], season["upload_start_day"],
                tzinfo=timezone.utc,
            )
            event_date = datetime(
                now.year, season["date_month"], season["date_day"],
                tzinfo=timezone.utc,
            )

            # Handle year wrapping (e.g., Christmas uploads start in Sept)
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

        # Sort by priority and urgency
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        upcoming.sort(key=lambda x: (priority_order.get(x["priority"], 3), x["days_until"]))

        return upcoming

    async def close(self):
        """Clean up resources."""
        await self.research.close()
        await self.creation.close()
        await self.compliance.close()
        await self.keywords.close()
