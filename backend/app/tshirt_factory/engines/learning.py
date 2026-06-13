"""Self-Learning Engine - Extracts insights from performance data to improve future designs."""

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.tshirt_factory.config import tsf_settings
from app.tshirt_factory.models import (
    DesignPrompt, DesignPerformance, NicheProfile, LearningInsight,
)

logger = logging.getLogger(__name__)


class LearningEngine:
    """Self-learning system that extracts insights from performance data.

    Analyzes what makes designs succeed or fail and stores insights
    that are used by the Creation Engine to generate better designs over time.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_learning_cycle(self) -> dict:
        """Execute a full learning cycle.

        Analyzes all designs with performance data and extracts insights about:
        - Which niches perform best
        - Which design types sell
        - Which humor types work
        - Which color schemes convert
        - Which font styles sell
        - Which audiences buy
        - Optimal text length
        - Seasonal patterns
        """
        # Get all designs with performance data
        stmt = (
            select(DesignPrompt, DesignPerformance)
            .join(DesignPerformance)
            .where(DesignPerformance.days_live >= 30)  # At least 30 days of data
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        if len(rows) < tsf_settings.LEARNING_MIN_DATAPOINTS:
            return {
                "status": "insufficient_data",
                "datapoints": len(rows),
                "required": tsf_settings.LEARNING_MIN_DATAPOINTS,
            }

        # Separate winners and losers
        winners = [(d, p) for d, p in rows if p.is_winner]
        losers = [(d, p) for d, p in rows if not p.is_winner and p.days_live >= 60]

        insights_generated = 0

        # Analyze each dimension
        insights_generated += await self._analyze_dimension(
            "design_type", winners, losers,
            lambda d, p: d.design_type
        )
        insights_generated += await self._analyze_dimension(
            "humor_type", winners, losers,
            lambda d, p: d.humor_type
        )
        insights_generated += await self._analyze_dimension(
            "font_style", winners, losers,
            lambda d, p: d.font_suggestion
        )
        insights_generated += await self._analyze_dimension(
            "target_audience", winners, losers,
            lambda d, p: d.target_audience
        )

        # Analyze text length
        insights_generated += await self._analyze_text_patterns(winners, losers)

        # Analyze color schemes
        insights_generated += await self._analyze_colors(winners, losers)

        # Analyze seasonal performance
        insights_generated += await self._analyze_seasonal(winners, losers)

        # Update niche profiles with win rates
        await self._update_niche_win_rates()

        # Generate meta-insights using pattern correlation
        insights_generated += await self._generate_meta_insights(winners, losers)

        await self.db.commit()

        return {
            "status": "complete",
            "datapoints_analyzed": len(rows),
            "winners": len(winners),
            "losers": len(losers),
            "insights_generated": insights_generated,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def get_insights_summary(self) -> dict:
        """Get a summary of all learning insights."""
        stmt = select(LearningInsight).order_by(
            LearningInsight.confidence.desc()
        )
        result = await self.db.execute(stmt)
        insights = result.scalars().all()

        by_category = defaultdict(list)
        for insight in insights:
            by_category[insight.category].append({
                "key": insight.insight_key,
                "value": insight.insight_value,
                "confidence": insight.confidence,
                "sample_size": insight.sample_size,
                "win_ratio": (
                    insight.positive_outcomes /
                    (insight.positive_outcomes + insight.negative_outcomes)
                    if (insight.positive_outcomes + insight.negative_outcomes) > 0
                    else 0
                ),
            })

        return {
            "total_insights": len(insights),
            "categories": dict(by_category),
            "high_confidence": [
                {
                    "category": i.category,
                    "key": i.insight_key,
                    "value": i.insight_value,
                    "confidence": i.confidence,
                }
                for i in insights if i.confidence >= 0.8
            ],
        }

    async def get_creation_guidance(self, niche: str = None) -> dict:
        """Get actionable guidance for the Creation Engine.

        Returns the best-performing attributes to use when generating new designs.
        """
        guidance = {}

        # Best design types
        stmt = select(LearningInsight).where(
            LearningInsight.category == "design_type",
            LearningInsight.confidence >= 0.5,
        ).order_by(LearningInsight.confidence.desc())
        result = await self.db.execute(stmt)
        design_insights = result.scalars().all()
        guidance["preferred_design_types"] = [
            {"type": i.insight_key, "confidence": i.confidence, "note": i.insight_value}
            for i in design_insights[:5]
        ]

        # Best humor types
        stmt = select(LearningInsight).where(
            LearningInsight.category == "humor_type",
            LearningInsight.confidence >= 0.5,
        ).order_by(LearningInsight.confidence.desc())
        result = await self.db.execute(stmt)
        humor_insights = result.scalars().all()
        guidance["preferred_humor_types"] = [
            {"type": i.insight_key, "confidence": i.confidence}
            for i in humor_insights[:5]
        ]

        # Optimal text length
        stmt = select(LearningInsight).where(
            LearningInsight.category == "text_pattern",
        ).order_by(LearningInsight.confidence.desc()).limit(3)
        result = await self.db.execute(stmt)
        text_insights = result.scalars().all()
        guidance["text_guidelines"] = [
            {"key": i.insight_key, "value": i.insight_value, "confidence": i.confidence}
            for i in text_insights
        ]

        # Best colors
        stmt = select(LearningInsight).where(
            LearningInsight.category == "color_scheme",
            LearningInsight.confidence >= 0.5,
        ).order_by(LearningInsight.confidence.desc()).limit(5)
        result = await self.db.execute(stmt)
        color_insights = result.scalars().all()
        guidance["preferred_colors"] = [
            {"color": i.insight_key, "confidence": i.confidence}
            for i in color_insights
        ]

        return guidance

    # ─── Analysis Methods ─────────────────────────────────────────

    async def _analyze_dimension(self, category: str, winners: list, losers: list,
                                  extractor) -> int:
        """Analyze a single dimension (design type, humor, etc.)."""
        winner_counts = Counter()
        loser_counts = Counter()

        for design, perf in winners:
            val = extractor(design, perf)
            if val:
                winner_counts[val] += 1

        for design, perf in losers:
            val = extractor(design, perf)
            if val:
                loser_counts[val] += 1

        total_winners = sum(winner_counts.values()) or 1
        total_losers = sum(loser_counts.values()) or 1
        insights_count = 0

        all_values = set(list(winner_counts.keys()) + list(loser_counts.keys()))
        for value in all_values:
            win_rate = winner_counts.get(value, 0) / total_winners
            lose_rate = loser_counts.get(value, 0) / total_losers
            sample = winner_counts.get(value, 0) + loser_counts.get(value, 0)

            if sample < 3:
                continue

            # Calculate confidence based on sample size and win/lose ratio
            ratio = win_rate / (lose_rate + 0.01)
            confidence = min(0.95, 0.3 + (sample / 50) * 0.3 + (min(ratio, 3) / 3) * 0.35)

            if ratio > 1.2:
                insight_text = f"Performs {ratio:.1f}x better than average"
            elif ratio < 0.8:
                insight_text = f"Underperforms at {ratio:.1f}x of average"
            else:
                insight_text = f"Average performance ({ratio:.1f}x)"

            await self._upsert_insight(
                category=category,
                key=value,
                value=insight_text,
                confidence=confidence,
                sample_size=sample,
                positive=winner_counts.get(value, 0),
                negative=loser_counts.get(value, 0),
            )
            insights_count += 1

        return insights_count

    async def _analyze_text_patterns(self, winners: list, losers: list) -> int:
        """Analyze text length and word patterns in winning vs losing designs."""
        winner_lengths = []
        loser_lengths = []

        for design, _ in winners:
            if design.primary_text:
                winner_lengths.append(len(design.primary_text.split()))
        for design, _ in losers:
            if design.primary_text:
                loser_lengths.append(len(design.primary_text.split()))

        insights = 0

        if winner_lengths:
            avg_winner_len = sum(winner_lengths) / len(winner_lengths)
            avg_loser_len = sum(loser_lengths) / len(loser_lengths) if loser_lengths else 0

            await self._upsert_insight(
                category="text_pattern",
                key="optimal_word_count",
                value=f"Winners average {avg_winner_len:.1f} words (losers: {avg_loser_len:.1f})",
                confidence=min(0.9, 0.4 + len(winner_lengths) / 100),
                sample_size=len(winner_lengths) + len(loser_lengths),
                positive=len(winner_lengths),
                negative=len(loser_lengths),
            )
            insights += 1

            # Find optimal range
            if winner_lengths:
                sorted_lens = sorted(winner_lengths)
                p25 = sorted_lens[len(sorted_lens) // 4]
                p75 = sorted_lens[3 * len(sorted_lens) // 4]
                await self._upsert_insight(
                    category="text_pattern",
                    key="optimal_range",
                    value=f"Best performing text length: {p25}-{p75} words",
                    confidence=min(0.85, 0.3 + len(winner_lengths) / 80),
                    sample_size=len(winner_lengths),
                    positive=len(winner_lengths),
                    negative=0,
                )
                insights += 1

        return insights

    async def _analyze_colors(self, winners: list, losers: list) -> int:
        """Analyze color scheme performance."""
        winner_colors = Counter()
        loser_colors = Counter()

        for design, _ in winners:
            if design.color_scheme:
                for color in design.color_scheme:
                    winner_colors[color] += 1

        for design, _ in losers:
            if design.color_scheme:
                for color in design.color_scheme:
                    loser_colors[color] += 1

        insights = 0
        for color in set(list(winner_colors.keys()) + list(loser_colors.keys())):
            wins = winner_colors.get(color, 0)
            losses = loser_colors.get(color, 0)
            total = wins + losses
            if total < 3:
                continue

            win_ratio = wins / total
            confidence = min(0.9, 0.3 + total / 40)

            await self._upsert_insight(
                category="color_scheme",
                key=color,
                value=f"Win rate: {win_ratio:.0%} ({total} designs)",
                confidence=confidence,
                sample_size=total,
                positive=wins,
                negative=losses,
            )
            insights += 1

        return insights

    async def _analyze_seasonal(self, winners: list, losers: list) -> int:
        """Analyze seasonal event performance."""
        seasonal_wins = Counter()
        seasonal_losses = Counter()

        for design, _ in winners:
            if design.seasonal_event:
                seasonal_wins[design.seasonal_event] += 1
        for design, _ in losers:
            if design.seasonal_event:
                seasonal_losses[design.seasonal_event] += 1

        insights = 0
        for event in set(list(seasonal_wins.keys()) + list(seasonal_losses.keys())):
            wins = seasonal_wins.get(event, 0)
            losses = seasonal_losses.get(event, 0)
            total = wins + losses
            if total < 2:
                continue

            win_ratio = wins / total
            await self._upsert_insight(
                category="seasonal",
                key=event,
                value=f"Win rate: {win_ratio:.0%} ({total} designs)",
                confidence=min(0.85, 0.3 + total / 30),
                sample_size=total,
                positive=wins,
                negative=losses,
            )
            insights += 1

        return insights

    async def _generate_meta_insights(self, winners: list, losers: list) -> int:
        """Generate cross-dimensional insights (e.g., 'sarcasm + text_only = best')."""
        # Find winning combinations
        win_combos = Counter()
        lose_combos = Counter()

        for design, _ in winners:
            combo = f"{design.design_type}+{design.humor_type}"
            win_combos[combo] += 1
        for design, _ in losers:
            combo = f"{design.design_type}+{design.humor_type}"
            lose_combos[combo] += 1

        insights = 0
        for combo in set(list(win_combos.keys()) + list(lose_combos.keys())):
            wins = win_combos.get(combo, 0)
            losses = lose_combos.get(combo, 0)
            total = wins + losses
            if total < 3:
                continue

            win_ratio = wins / total
            parts = combo.split("+")
            await self._upsert_insight(
                category="combination",
                key=combo,
                value=f"{parts[0]} with {parts[1]} humor: {win_ratio:.0%} win rate",
                confidence=min(0.9, 0.3 + total / 40),
                sample_size=total,
                positive=wins,
                negative=losses,
            )
            insights += 1

        return insights

    async def _update_niche_win_rates(self):
        """Update win rates in niche profiles based on actual performance."""
        stmt = (
            select(
                DesignPrompt.niche_id,
                func.count(DesignPerformance.id).label("total"),
                func.count(DesignPerformance.id).filter(
                    DesignPerformance.is_winner == True
                ).label("winners"),
            )
            .join(DesignPerformance, DesignPerformance.design_id == DesignPrompt.id)
            .where(DesignPrompt.niche_id.isnot(None))
            .group_by(DesignPrompt.niche_id)
        )
        result = await self.db.execute(stmt)

        for row in result.all():
            if row.niche_id and row.total > 0:
                niche_stmt = select(NicheProfile).where(NicheProfile.id == row.niche_id)
                niche_result = await self.db.execute(niche_stmt)
                niche = niche_result.scalar_one_or_none()
                if niche:
                    niche.win_rate = row.winners / row.total
                    niche.confidence_score = min(0.95, 0.3 + row.total / 50)

    async def _upsert_insight(self, category: str, key: str, value: str,
                               confidence: float, sample_size: int,
                               positive: int, negative: int):
        """Insert or update a learning insight."""
        stmt = select(LearningInsight).where(
            LearningInsight.category == category,
            LearningInsight.insight_key == key,
        )
        result = await self.db.execute(stmt)
        insight = result.scalar_one_or_none()

        if insight:
            insight.insight_value = value
            insight.confidence = confidence
            insight.sample_size = sample_size
            insight.positive_outcomes = positive
            insight.negative_outcomes = negative
            insight.last_updated = datetime.now(timezone.utc)
        else:
            insight = LearningInsight(
                category=category,
                insight_key=key,
                insight_value=value,
                confidence=confidence,
                sample_size=sample_size,
                positive_outcomes=positive,
                negative_outcomes=negative,
            )
            self.db.add(insight)

        await self.db.flush()
