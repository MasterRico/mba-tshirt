"""Analysis Engine - Pattern recognition from collected research data."""

import json
import logging
from collections import Counter
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.tshirt_factory.config import tsf_settings
from app.tshirt_factory.models import (
    ResearchItem, TrendData, NicheProfile, DesignPrompt, DesignPerformance,
    LearningInsight,
)

logger = logging.getLogger(__name__)


class AnalysisEngine:
    """Analyzes collected research data to identify winning patterns."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_niche(self, niche_name: str) -> dict:
        """Deep analysis of a specific niche based on research data."""
        # Get all research items for this niche
        stmt = select(ResearchItem).where(
            ResearchItem.niche == niche_name
        ).order_by(ResearchItem.bsr.asc().nullslast())
        result = await self.db.execute(stmt)
        items = result.scalars().all()

        if not items:
            # Try to match by keywords in title
            stmt = select(ResearchItem).where(
                ResearchItem.title.ilike(f"%{niche_name}%")
            ).order_by(ResearchItem.bsr.asc().nullslast())
            result = await self.db.execute(stmt)
            items = result.scalars().all()

        if not items:
            return {"niche": niche_name, "data_available": False}

        # Aggregate analysis
        colors = Counter()
        fonts = Counter()
        design_types = Counter()
        humor_types = Counter()
        audiences = Counter()
        keywords_all = Counter()

        bsr_values = []
        prices = []
        reviews = []

        for item in items:
            if item.primary_colors:
                for c in item.primary_colors:
                    colors[c] += 1
            if item.font_style:
                fonts[item.font_style] += 1
            if item.design_type:
                design_types[item.design_type] += 1
            if item.humor_type:
                humor_types[item.humor_type] += 1
            if item.target_audience:
                audiences[item.target_audience] += 1
            if item.keywords:
                for kw in item.keywords:
                    keywords_all[kw] += 1
            if item.bsr:
                bsr_values.append(item.bsr)
            if item.price:
                prices.append(item.price)
            if item.review_count:
                reviews.append(item.review_count)

        # Calculate competition level
        avg_reviews = sum(reviews) / len(reviews) if reviews else 0
        if avg_reviews > 500:
            competition = "high"
        elif avg_reviews > 100:
            competition = "medium"
        else:
            competition = "low"

        analysis = {
            "niche": niche_name,
            "data_available": True,
            "sample_size": len(items),
            "competition_level": competition,
            "avg_bsr": int(sum(bsr_values) / len(bsr_values)) if bsr_values else None,
            "avg_price": round(sum(prices) / len(prices), 2) if prices else None,
            "avg_reviews": int(avg_reviews),
            "top_colors": dict(colors.most_common(5)),
            "top_fonts": dict(fonts.most_common(5)),
            "top_design_types": dict(design_types.most_common(5)),
            "top_humor_types": dict(humor_types.most_common(5)),
            "top_audiences": dict(audiences.most_common(5)),
            "top_keywords": dict(keywords_all.most_common(20)),
        }

        # Update or create niche profile
        await self._update_niche_profile(niche_name, analysis)

        return analysis

    async def identify_winning_patterns(self) -> dict:
        """Analyze all data to identify what makes designs sell."""
        # Get top performing items (low BSR = high sales)
        stmt = select(ResearchItem).where(
            ResearchItem.bsr.isnot(None),
            ResearchItem.bsr < tsf_settings.BSR_WINNER_THRESHOLD,
        ).order_by(ResearchItem.bsr.asc()).limit(200)
        result = await self.db.execute(stmt)
        winners = result.scalars().all()

        # Get underperformers for comparison
        stmt = select(ResearchItem).where(
            ResearchItem.bsr.isnot(None),
            ResearchItem.bsr > tsf_settings.BSR_UNDERPERFORMER_THRESHOLD,
        ).limit(200)
        result = await self.db.execute(stmt)
        losers = result.scalars().all()

        # Analyze differences
        winner_patterns = self._extract_patterns(winners)
        loser_patterns = self._extract_patterns(losers)

        # Find what winners have that losers don't
        differentiators = {}
        for key in winner_patterns:
            if key in loser_patterns:
                w_top = set(list(winner_patterns[key].keys())[:5])
                l_top = set(list(loser_patterns[key].keys())[:5])
                differentiators[key] = {
                    "winners_prefer": list(w_top - l_top),
                    "losers_have": list(l_top - w_top),
                    "shared": list(w_top & l_top),
                }

        return {
            "winners_analyzed": len(winners),
            "losers_analyzed": len(losers),
            "winner_patterns": {k: dict(v.most_common(10)) for k, v in winner_patterns.items()},
            "loser_patterns": {k: dict(v.most_common(10)) for k, v in loser_patterns.items()},
            "differentiators": differentiators,
        }

    async def identify_trending_niches(self) -> list[dict]:
        """Find niches with rising trends and low competition."""
        # Get recent trend data (last 7 days)
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        stmt = select(TrendData).where(
            TrendData.recorded_at > week_ago,
            TrendData.trend_direction == "rising",
        ).order_by(TrendData.interest_score.desc())
        result = await self.db.execute(stmt)
        rising_trends = result.scalars().all()

        opportunities = []
        for trend in rising_trends:
            # Check if we have research data for this niche
            stmt = select(func.count(ResearchItem.id)).where(
                ResearchItem.title.ilike(f"%{trend.keyword}%")
            )
            result = await self.db.execute(stmt)
            item_count = result.scalar()

            opportunities.append({
                "keyword": trend.keyword,
                "interest_score": trend.interest_score,
                "direction": trend.trend_direction,
                "related_keywords": trend.related_keywords or [],
                "existing_research": item_count,
                "opportunity_score": self._calculate_opportunity_score(
                    trend.interest_score, item_count
                ),
            })

        # Sort by opportunity score
        opportunities.sort(key=lambda x: x["opportunity_score"], reverse=True)
        return opportunities[:20]

    async def get_design_type_performance(self) -> dict:
        """Analyze which design types perform best across niches."""
        stmt = select(
            ResearchItem.design_type,
            func.count(ResearchItem.id).label("total"),
            func.avg(ResearchItem.bsr).label("avg_bsr"),
            func.avg(ResearchItem.review_count).label("avg_reviews"),
        ).where(
            ResearchItem.design_type.isnot(None),
            ResearchItem.bsr.isnot(None),
        ).group_by(ResearchItem.design_type)
        result = await self.db.execute(stmt)
        rows = result.all()

        return {
            row.design_type: {
                "count": row.total,
                "avg_bsr": int(row.avg_bsr) if row.avg_bsr else None,
                "avg_reviews": int(row.avg_reviews) if row.avg_reviews else None,
            }
            for row in rows
        }

    async def run_full_analysis(self) -> dict:
        """Run complete analysis cycle."""
        logger.info("Starting full analysis cycle...")

        # Get all active niches
        stmt = select(NicheProfile).where(NicheProfile.is_active == True)
        result = await self.db.execute(stmt)
        niches = result.scalars().all()

        niche_analyses = {}
        for niche in niches:
            analysis = await self.analyze_niche(niche.name)
            niche_analyses[niche.name] = analysis

        winning_patterns = await self.identify_winning_patterns()
        trending = await self.identify_trending_niches()
        design_type_perf = await self.get_design_type_performance()

        await self.db.commit()

        return {
            "niches_analyzed": len(niche_analyses),
            "niche_details": niche_analyses,
            "winning_patterns": winning_patterns,
            "trending_niches": trending[:10],
            "design_type_performance": design_type_perf,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ─── Helpers ──────────────────────────────────────────────────

    def _extract_patterns(self, items: list) -> dict[str, Counter]:
        patterns = {
            "colors": Counter(),
            "fonts": Counter(),
            "design_types": Counter(),
            "humor_types": Counter(),
            "audiences": Counter(),
        }
        for item in items:
            if item.primary_colors:
                for c in item.primary_colors:
                    patterns["colors"][c] += 1
            if item.font_style:
                patterns["fonts"][item.font_style] += 1
            if item.design_type:
                patterns["design_types"][item.design_type] += 1
            if item.humor_type:
                patterns["humor_types"][item.humor_type] += 1
            if item.target_audience:
                patterns["audiences"][item.target_audience] += 1
        return patterns

    def _calculate_opportunity_score(self, interest: float, competition: int) -> float:
        """Higher interest + lower competition = higher opportunity."""
        if competition == 0:
            competition_factor = 1.0
        elif competition < 10:
            competition_factor = 0.8
        elif competition < 50:
            competition_factor = 0.5
        else:
            competition_factor = 0.3
        return (interest / 100) * competition_factor

    async def _update_niche_profile(self, niche_name: str, analysis: dict):
        """Update or create a niche profile from analysis results."""
        stmt = select(NicheProfile).where(NicheProfile.name == niche_name)
        result = await self.db.execute(stmt)
        profile = result.scalar_one_or_none()

        if not profile:
            profile = NicheProfile(name=niche_name)
            self.db.add(profile)

        profile.competition_level = analysis.get("competition_level")
        profile.avg_bsr = analysis.get("avg_bsr")
        profile.avg_price = analysis.get("avg_price")
        profile.avg_reviews = analysis.get("avg_reviews")
        profile.top_keywords = list(analysis.get("top_keywords", {}).keys())[:20]
        profile.top_design_types = list(analysis.get("top_design_types", {}).keys())
        profile.top_colors = list(analysis.get("top_colors", {}).keys())
        profile.top_font_styles = list(analysis.get("top_fonts", {}).keys())
        profile.top_humor_types = list(analysis.get("top_humor_types", {}).keys())
        profile.total_designs_analyzed = analysis.get("sample_size", 0)
        profile.last_updated = datetime.now(timezone.utc)

        await self.db.flush()
