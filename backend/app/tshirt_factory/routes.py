"""API Routes for T-Shirt Design Factory."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.tshirt_factory.orchestrator import Orchestrator
from app.tshirt_factory.engines.compliance import ComplianceEngine
from app.tshirt_factory.engines.learning import LearningEngine
from app.tshirt_factory.models import (
    DesignPrompt, NicheProfile, ResearchItem, TrendData, LearningInsight,
)
from app.tshirt_factory.schemas import (
    DesignPromptOut, NicheProfileOut, NicheCreateIn, DesignGenerateIn,
    PerformanceUpdateIn, PerformanceBulkImportIn, PerformanceOut,
    TrademarkCheckIn, TrademarkCheckOut, SlotSummaryOut,
    DashboardOut, LearningInsightOut, ResearchItemOut, TrendDataOut,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tsf", tags=["T-Shirt Factory"])


# ─── Dashboard ────────────────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """Get full dashboard data."""
    orchestrator = Orchestrator(db)
    try:
        return await orchestrator.get_dashboard_data()
    finally:
        await orchestrator.close()


# ─── Pipeline ─────────────────────────────────────────────────────────

@router.post("/pipeline/full")
async def run_full_pipeline(db: AsyncSession = Depends(get_db)):
    """Run the complete automated pipeline."""
    orchestrator = Orchestrator(db)
    try:
        return await orchestrator.run_full_pipeline()
    finally:
        await orchestrator.close()


@router.post("/pipeline/research")
async def run_research(db: AsyncSession = Depends(get_db)):
    """Run research phase only."""
    orchestrator = Orchestrator(db)
    try:
        return await orchestrator.run_research_only()
    finally:
        await orchestrator.close()


@router.post("/pipeline/analysis")
async def run_analysis(db: AsyncSession = Depends(get_db)):
    """Run analysis phase only."""
    orchestrator = Orchestrator(db)
    try:
        return await orchestrator.run_analysis_only()
    finally:
        await orchestrator.close()


# ─── Design Generation ───────────────────────────────────────────────

@router.post("/designs/generate", response_model=list[dict])
async def generate_designs(
    params: DesignGenerateIn,
    db: AsyncSession = Depends(get_db),
):
    """Generate new design prompts."""
    orchestrator = Orchestrator(db)
    try:
        return await orchestrator.run_generation_only(
            niche=params.niche_name,
            count=params.count,
            seasonal_event=params.seasonal_event,
        )
    finally:
        await orchestrator.close()


@router.get("/designs", response_model=list[DesignPromptOut])
async def list_designs(
    status: str = None,
    niche_id: int = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List design prompts with optional filters."""
    stmt = select(DesignPrompt).order_by(DesignPrompt.composite_score.desc())
    if status:
        stmt = stmt.where(DesignPrompt.status == status)
    if niche_id:
        stmt = stmt.where(DesignPrompt.niche_id == niche_id)
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/designs/{design_id}", response_model=DesignPromptOut)
async def get_design(design_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single design prompt with all details."""
    stmt = select(DesignPrompt).where(DesignPrompt.id == design_id)
    result = await db.execute(stmt)
    design = result.scalar_one_or_none()
    if not design:
        raise HTTPException(404, "Design not found")
    return design


@router.post("/designs/{design_id}/upload")
async def mark_design_uploaded(
    design_id: int,
    asin: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Mark a design as uploaded to MBA."""
    from app.tshirt_factory.engines.slot_manager import SlotManager
    slots = SlotManager(db)
    result = await slots.mark_uploaded(design_id, asin)
    await db.commit()
    return result


@router.post("/designs/{design_id}/rotate")
async def rotate_design(design_id: int, db: AsyncSession = Depends(get_db)):
    """Rotate out an underperforming design."""
    from app.tshirt_factory.engines.slot_manager import SlotManager
    slots = SlotManager(db)
    result = await slots.rotate_design(design_id)
    await db.commit()
    return result


# ─── Niches ───────────────────────────────────────────────────────────

@router.get("/niches", response_model=list[NicheProfileOut])
async def list_niches(db: AsyncSession = Depends(get_db)):
    """List all niche profiles."""
    stmt = select(NicheProfile).order_by(NicheProfile.win_rate.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/niches")
async def create_niche(
    data: NicheCreateIn,
    db: AsyncSession = Depends(get_db),
):
    """Create a new niche profile."""
    niche = NicheProfile(name=data.name, category=data.category)
    db.add(niche)
    await db.commit()
    return {"id": niche.id, "name": niche.name}


@router.post("/niches/initialize")
async def initialize_niches(db: AsyncSession = Depends(get_db)):
    """Initialize niches from config file."""
    orchestrator = Orchestrator(db)
    return await orchestrator.initialize_niches()


@router.get("/niches/{niche_id}/analysis")
async def analyze_niche(niche_id: int, db: AsyncSession = Depends(get_db)):
    """Run deep analysis on a niche."""
    stmt = select(NicheProfile).where(NicheProfile.id == niche_id)
    result = await db.execute(stmt)
    niche = result.scalar_one_or_none()
    if not niche:
        raise HTTPException(404, "Niche not found")

    from app.tshirt_factory.engines.analysis import AnalysisEngine
    analysis = AnalysisEngine(db)
    return await analysis.analyze_niche(niche.name)


# ─── Slots ────────────────────────────────────────────────────────────

@router.get("/slots/summary")
async def get_slot_summary(db: AsyncSession = Depends(get_db)):
    """Get current slot usage."""
    from app.tshirt_factory.engines.slot_manager import SlotManager
    slots = SlotManager(db)
    return await slots.get_slot_summary()


@router.get("/slots/recommendations")
async def get_slot_recommendations(db: AsyncSession = Depends(get_db)):
    """Get niche allocation recommendations."""
    from app.tshirt_factory.engines.slot_manager import SlotManager
    slots = SlotManager(db)
    return await slots.get_niche_allocation_recommendation()


@router.get("/slots/rotation-candidates")
async def get_rotation_candidates(db: AsyncSession = Depends(get_db)):
    """Get designs that should be rotated out."""
    from app.tshirt_factory.engines.slot_manager import SlotManager
    slots = SlotManager(db)
    return await slots.get_rotation_candidates()


# ─── Performance ──────────────────────────────────────────────────────

@router.post("/performance/update")
async def update_performance(
    data: PerformanceUpdateIn,
    db: AsyncSession = Depends(get_db),
):
    """Update performance data for a design."""
    from app.tshirt_factory.engines.performance import PerformanceTracker
    tracker = PerformanceTracker(db)
    result = await tracker.update_performance(data.design_id, data.model_dump())
    await db.commit()
    return result


@router.post("/performance/import-csv")
async def import_mba_csv(
    data: PerformanceBulkImportIn,
    db: AsyncSession = Depends(get_db),
):
    """Import MBA sales report CSV."""
    from app.tshirt_factory.engines.performance import PerformanceTracker
    tracker = PerformanceTracker(db)
    return await tracker.import_mba_csv(data.csv_data)


@router.get("/performance/summary")
async def get_performance_summary(db: AsyncSession = Depends(get_db)):
    """Get overall performance summary."""
    from app.tshirt_factory.engines.performance import PerformanceTracker
    tracker = PerformanceTracker(db)
    return await tracker.get_performance_summary()


@router.get("/performance/by-niche")
async def get_niche_performance(db: AsyncSession = Depends(get_db)):
    """Get performance breakdown by niche."""
    from app.tshirt_factory.engines.performance import PerformanceTracker
    tracker = PerformanceTracker(db)
    return await tracker.get_niche_performance()


# ─── Compliance ───────────────────────────────────────────────────────

@router.post("/compliance/check", response_model=list[TrademarkCheckOut])
async def check_trademarks(
    data: TrademarkCheckIn,
    db: AsyncSession = Depends(get_db),
):
    """Check terms against trademark database."""
    compliance = ComplianceEngine(db)
    results = []
    try:
        for term in data.terms:
            result = await compliance.check_term(term)
            results.append({
                "term": term,
                "is_trademarked": not result["is_safe"],
                "trademark_owner": result["issues"][0].get("owner") if result["issues"] else None,
                "status": result["issues"][0].get("status") if result["issues"] else None,
                "details": result,
            })
    finally:
        await compliance.close()
    return results


# ─── Research Data ────────────────────────────────────────────────────

@router.get("/research/items", response_model=list[ResearchItemOut])
async def list_research_items(
    source: str = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List collected research items."""
    stmt = select(ResearchItem).order_by(ResearchItem.scraped_at.desc())
    if source:
        stmt = stmt.where(ResearchItem.source == source)
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/research/trends", response_model=list[TrendDataOut])
async def list_trends(
    direction: str = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List trend data."""
    stmt = select(TrendData).order_by(TrendData.recorded_at.desc())
    if direction:
        stmt = stmt.where(TrendData.trend_direction == direction)
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


# ─── Learning ─────────────────────────────────────────────────────────

@router.get("/learning/insights", response_model=list[LearningInsightOut])
async def list_insights(
    category: str = None,
    min_confidence: float = 0.0,
    db: AsyncSession = Depends(get_db),
):
    """List learning insights."""
    stmt = select(LearningInsight).where(
        LearningInsight.confidence >= min_confidence
    ).order_by(LearningInsight.confidence.desc())
    if category:
        stmt = stmt.where(LearningInsight.category == category)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/learning/summary")
async def get_learning_summary(db: AsyncSession = Depends(get_db)):
    """Get learning insights summary."""
    learning = LearningEngine(db)
    return await learning.get_insights_summary()


@router.post("/learning/run")
async def run_learning_cycle(db: AsyncSession = Depends(get_db)):
    """Manually trigger a learning cycle."""
    learning = LearningEngine(db)
    return await learning.run_learning_cycle()


@router.get("/learning/guidance")
async def get_creation_guidance(
    niche: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Get actionable creation guidance from learning data."""
    learning = LearningEngine(db)
    return await learning.get_creation_guidance(niche)


# ─── Keywords ─────────────────────────────────────────────────────────

@router.get("/keywords/research/{niche_name}")
async def research_keywords(niche_name: str, db: AsyncSession = Depends(get_db)):
    """Research keywords for a niche."""
    from app.tshirt_factory.engines.keyword import KeywordEngine
    kw = KeywordEngine(db)
    try:
        return await kw.research_niche_keywords(niche_name)
    finally:
        await kw.close()


@router.get("/keywords/suggestions")
async def get_suggestions(keyword: str, db: AsyncSession = Depends(get_db)):
    """Get Amazon autocomplete suggestions."""
    from app.tshirt_factory.engines.keyword import KeywordEngine
    kw = KeywordEngine(db)
    try:
        return {"keyword": keyword, "suggestions": await kw.get_amazon_suggestions(keyword)}
    finally:
        await kw.close()


# ─── MBA Account Sales (echte Konto-Zahlen) ───────────────────────────

from app.tshirt_factory.schemas import SalesImportIn  # noqa: E402


@router.post("/sales/import")
async def import_mba_sales(
    data: SalesImportIn,
    db: AsyncSession = Depends(get_db),
):
    """Importiert den rohen Merch 'earnings'-Export (transaktionsbasiert).

    Aggregiert serverseitig je (ASIN, Marketplace, Monat) und speichert
    idempotent. Liefert die echten Konto-Zahlen unabhaengig von Designs.
    """
    from app.tshirt_factory.engines.sales import SalesTracker
    tracker = SalesTracker(db)
    return await tracker.import_raw_csv(data.csv_data)


@router.get("/sales/summary")
async def get_mba_sales_summary(db: AsyncSession = Depends(get_db)):
    """Konto-Umsatz: Totals je Waehrung, Units, Monatsverlauf, Top-Produkte."""
    from app.tshirt_factory.engines.sales import SalesTracker
    tracker = SalesTracker(db)
    return await tracker.get_summary()


# ─── Vision Know-how Ingest (Winner-Designs -> NicheProfile) ──────────

from app.tshirt_factory.schemas import VisionIngestIn  # noqa: E402


@router.post("/research/vision-ingest")
async def vision_ingest(data: VisionIngestIn, db: AsyncSession = Depends(get_db)):
    """Analysiert Winner-Design-Bilder (Claude Vision) -> ResearchItems mit
    visuellen Attributen -> aggregiert via analysis.py zu NicheProfile.
    Items koennen 'attributes' bereits mitbringen (dann kein Vision-Call)."""
    from app.tshirt_factory.engines.vision import VisionAnalyzer
    from app.tshirt_factory.engines.analysis import AnalysisEngine
    from app.tshirt_factory.models import ResearchItem

    analyzer = VisionAnalyzer()
    ingested, failed = 0, 0
    niches = set()
    for it in data.items:
        attrs = it.attributes or await analyzer.analyze_url(it.image_url)
        if not attrs:
            failed += 1
            continue
        db.add(ResearchItem(
            source=it.source,
            external_id=it.asin,
            title=it.title or (attrs.get("text_content") or "")[:500],
            niche=it.niche,
            design_type=attrs.get("design_type"),
            bsr=it.bsr, price=it.price,
            review_count=it.review_count, rating=it.rating,
            primary_colors=attrs.get("primary_colors"),
            font_style=attrs.get("font_style"),
            text_content=attrs.get("text_content"),
            design_elements=attrs.get("design_elements"),
            humor_type=attrs.get("humor_type"),
            target_audience=attrs.get("target_audience"),
            marketplace=it.marketplace,
            image_url=it.image_url,
            url=(f"https://www.amazon.com/dp/{it.asin}" if it.asin else None),
        ))
        ingested += 1
        niches.add(it.niche)
    await db.commit()

    profiles = {}
    if data.run_analysis:
        ae = AnalysisEngine(db)
        for n in niches:
            profiles[n] = await ae.analyze_niche(n)
        await db.commit()
    return {"ingested": ingested, "failed": failed, "niches": list(niches), "profiles": profiles}
