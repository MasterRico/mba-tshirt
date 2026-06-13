"""Slot Manager - Optimizes the 100 MBA slots for maximum revenue."""

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.tshirt_factory.config import tsf_settings
from app.tshirt_factory.models import (
    DesignPrompt, DesignPerformance, DesignStatus, NicheProfile,
)

logger = logging.getLogger(__name__)


class SlotManager:
    """Manages Tier 100 MBA slots - tracks usage, identifies rotation candidates."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_slot_summary(self) -> dict:
        """Get current slot usage overview."""
        # Count designs by status
        stmt = select(
            DesignPrompt.status,
            func.count(DesignPrompt.id),
        ).group_by(DesignPrompt.status)
        result = await self.db.execute(stmt)
        status_counts = {row[0]: row[1] for row in result.all()}

        live_count = status_counts.get(DesignStatus.LIVE.value, 0)
        uploaded_count = status_counts.get(DesignStatus.UPLOADED.value, 0)
        used = live_count + uploaded_count

        # Count winners
        stmt = select(func.count(DesignPerformance.id)).where(
            DesignPerformance.is_winner == True
        )
        result = await self.db.execute(stmt)
        winners = result.scalar() or 0

        # Count underperformers
        stmt = select(func.count(DesignPerformance.id)).where(
            DesignPerformance.should_rotate == True
        )
        result = await self.db.execute(stmt)
        underperformers = result.scalar() or 0

        # Designs pending rotation
        rotation_candidates = await self.get_rotation_candidates()

        # Niche distribution
        niche_dist = await self._get_niche_distribution()

        return {
            "total_slots": tsf_settings.MAX_SLOTS,
            "used_slots": used,
            "available_slots": tsf_settings.MAX_SLOTS - used,
            "winners": winners,
            "underperformers": underperformers,
            "pending_rotation": [c["design_id"] for c in rotation_candidates],
            "niche_distribution": niche_dist,
            "status_breakdown": status_counts,
        }

    async def get_rotation_candidates(self) -> list[dict]:
        """Identify designs that should be rotated out.

        Criteria:
        - Live for more than MIN_DAYS_BEFORE_ROTATION days
        - BSR consistently above UNDERPERFORMER threshold
        - No sales in the last 30 days
        """
        min_days = tsf_settings.MIN_DAYS_BEFORE_ROTATION
        cutoff = datetime.now(timezone.utc) - timedelta(days=min_days)

        stmt = (
            select(DesignPrompt, DesignPerformance)
            .outerjoin(DesignPerformance)
            .where(
                DesignPrompt.status.in_([
                    DesignStatus.LIVE.value,
                    DesignStatus.UPLOADED.value,
                ]),
                DesignPrompt.upload_date.isnot(None),
                DesignPrompt.upload_date < cutoff,
            )
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        candidates = []
        for design, perf in rows:
            should_rotate = False
            reason = ""

            if perf is None:
                # No performance data after min_days = likely no sales
                should_rotate = True
                reason = f"No performance data after {min_days} days"
            elif perf.units_sold == 0 and perf.days_live >= min_days:
                should_rotate = True
                reason = f"Zero sales after {perf.days_live} days"
            elif (perf.current_bsr and
                  perf.current_bsr > tsf_settings.BSR_UNDERPERFORMER_THRESHOLD and
                  perf.days_live >= min_days):
                should_rotate = True
                reason = f"BSR {perf.current_bsr} above threshold after {perf.days_live} days"

            if should_rotate:
                candidates.append({
                    "design_id": design.id,
                    "primary_text": design.primary_text,
                    "niche_id": design.niche_id,
                    "days_live": perf.days_live if perf else min_days,
                    "units_sold": perf.units_sold if perf else 0,
                    "current_bsr": perf.current_bsr if perf else None,
                    "reason": reason,
                })

        # Sort: worst performers first
        candidates.sort(key=lambda x: x["units_sold"])
        return candidates

    async def rotate_design(self, design_id: int) -> dict:
        """Mark a design as rotated out, freeing the slot."""
        stmt = select(DesignPrompt).where(DesignPrompt.id == design_id)
        result = await self.db.execute(stmt)
        design = result.scalar_one_or_none()

        if not design:
            return {"error": f"Design {design_id} not found"}

        design.status = DesignStatus.ROTATED_OUT.value
        design.rotation_date = datetime.now(timezone.utc)

        # Update performance record
        if design.performance:
            design.performance.should_rotate = False

        await self.db.flush()

        return {
            "design_id": design_id,
            "previous_status": design.status,
            "new_status": DesignStatus.ROTATED_OUT.value,
            "slot_freed": True,
        }

    async def get_niche_allocation_recommendation(self) -> dict:
        """Recommend how to distribute remaining slots across niches.

        Based on:
        - Niche win rates
        - Current slot distribution
        - Config limits (min/max per niche)
        """
        # Get current distribution
        current_dist = await self._get_niche_distribution()

        # Get niche performance data
        stmt = select(NicheProfile).where(
            NicheProfile.is_active == True
        ).order_by(NicheProfile.win_rate.desc())
        result = await self.db.execute(stmt)
        niches = result.scalars().all()

        # Get available slots
        summary = await self.get_slot_summary()
        available = summary["available_slots"]

        recommendations = []
        for niche in niches:
            current = current_dist.get(niche.name, 0)
            min_designs = tsf_settings.MIN_DESIGNS_PER_NICHE
            max_designs = tsf_settings.MAX_DESIGNS_PER_NICHE

            # Higher win rate = more slots
            ideal = min(max_designs, max(min_designs,
                       int(tsf_settings.MAX_SLOTS * (niche.win_rate or 0.1))))
            gap = ideal - current

            recommendations.append({
                "niche": niche.name,
                "current_slots": current,
                "ideal_slots": ideal,
                "gap": gap,
                "win_rate": niche.win_rate or 0.0,
                "action": "add" if gap > 0 else ("remove" if gap < -2 else "hold"),
                "designs_to_add": max(0, gap),
            })

        # Sort by gap (most underserved first)
        recommendations.sort(key=lambda x: x["gap"], reverse=True)

        return {
            "available_slots": available,
            "recommendations": recommendations,
        }

    async def mark_uploaded(self, design_id: int, asin: str = None) -> dict:
        """Mark a design as uploaded to MBA."""
        stmt = select(DesignPrompt).where(DesignPrompt.id == design_id)
        result = await self.db.execute(stmt)
        design = result.scalar_one_or_none()

        if not design:
            return {"error": f"Design {design_id} not found"}

        design.status = DesignStatus.UPLOADED.value
        design.was_uploaded = True
        design.upload_date = datetime.now(timezone.utc)

        # Create performance tracking record
        perf = DesignPerformance(
            design_id=design_id,
            asin=asin,
        )
        self.db.add(perf)
        await self.db.flush()

        return {
            "design_id": design_id,
            "status": DesignStatus.UPLOADED.value,
            "asin": asin,
            "performance_tracking": "active",
        }

    async def _get_niche_distribution(self) -> dict:
        """Get how many live/uploaded designs per niche."""
        stmt = (
            select(
                NicheProfile.name,
                func.count(DesignPrompt.id),
            )
            .join(DesignPrompt, DesignPrompt.niche_id == NicheProfile.id)
            .where(
                DesignPrompt.status.in_([
                    DesignStatus.LIVE.value,
                    DesignStatus.UPLOADED.value,
                ])
            )
            .group_by(NicheProfile.name)
        )
        result = await self.db.execute(stmt)
        return {row[0]: row[1] for row in result.all()}
