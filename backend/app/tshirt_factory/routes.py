"""API Routes for T-Shirt Design Factory."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.tshirt_factory.orchestrator import Orchestrator
from app.tshirt_factory.engines.compliance import ComplianceEngine
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


# ─── Curation & Planner (Winner-Maschine) ─────────────────────────────

@router.get("/curation/candidates")
async def curation_candidates(niche: str = None, limit: int = 20,
                              db: AsyncSession = Depends(get_db)):
    """Designs nach Know-how-Fit gerankt (beste Upload-Kandidaten zuerst)."""
    from app.tshirt_factory.engines.curation import CurationEngine
    return await CurationEngine(db).top_candidates(niche=niche, limit=limit)


@router.get("/planner/seasonal")
async def planner_seasonal():
    """Welche Saison-Designs JETZT erstellen (Lead-Time-aware)."""
    from app.tshirt_factory.engines.planner import seasonal_plan
    return seasonal_plan()


@router.get("/curation/gaps")
async def curation_gaps(niche: str = None, limit: int = 30,
                        db: AsyncSession = Depends(get_db)):
    """Gewinnermuster, die deine Designs noch nicht abdecken (mach davon mehr)."""
    from app.tshirt_factory.engines.curation import CurationEngine
    return await CurationEngine(db).find_gaps(niche=niche, limit=limit)


@router.post("/designs/{design_id}/generate-image")
async def generate_design_image(design_id: int, aspect_ratio: str = "1x1",
                                force: bool = False,
                                db: AsyncSession = Depends(get_db)):
    """Erzeugt via Ideogram ein Bild zum Design-Konzept (schwarzer Hintergrund).
    Pre-Flight-Trademark-Check VOR der Generierung -> verbrennt keine Credits
    bei geschuetztem Spruch/Design-Element. force=true ueberspringt das Gate."""
    from app.tshirt_factory.engines.imagegen import IdeogramGenerator, download_and_upscale
    from app.tshirt_factory.models import DesignPrompt, DesignImage
    d = (await db.execute(select(DesignPrompt).where(DesignPrompt.id == design_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Design nicht gefunden")

    if not force:
        from app.tshirt_factory.engines.compliance import ComplianceEngine
        comp = ComplianceEngine(db)
        try:
            chk = await comp.check_design_prompt(d.prompt_text or "", d.primary_text or "", d.listing_title or "")
        finally:
            await comp.close()
        if not chk.get("is_compliant"):
            flagged = sorted({(i.get("term") or "") for i in chk.get("issues", []) if i.get("term")})
            raise HTTPException(status_code=409, detail={
                "message": "Pre-Flight-Trademark-Check fehlgeschlagen",
                "flagged": flagged,
                "hint": "force=true ueberspringt das Gate",
            })

    prompt = (d.prompt_text or d.primary_text or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Kein Prompt-Text am Design")

    res = await IdeogramGenerator().generate(prompt, aspect_ratio=aspect_ratio)
    if res.get("error"):
        raise HTTPException(status_code=502, detail=f"Ideogram: {res['error']}")
    url = res.get("url")
    if not url:
        raise HTTPException(status_code=502, detail="Ideogram lieferte keine Bild-URL")

    local = await download_and_upscale(url, design_id)
    db.add(DesignImage(design_id=design_id, url=url, prompt=prompt, provider="ideogram"))
    await db.commit()
    return {
        "design_id": design_id,
        "url": url,
        "local": bool(local),
        "print_file": f"/api/v1/tsf/designs/{design_id}/image-file" if local else None,
    }


@router.post("/compliance/preflight")
async def compliance_preflight(data: dict, db: AsyncSession = Depends(get_db)):
    """Prueft Spruch (text) + Design-Elemente (elements: Tier/Objekt) VOR der
    Erstellung auf Trademark-Risiko -> spart verschwendete Generierung."""
    from app.tshirt_factory.engines.compliance import ComplianceEngine
    text = (data.get("text") or "").strip()
    elements = [str(e).strip() for e in (data.get("elements") or []) if str(e).strip()]
    comp = ComplianceEngine(db)
    flagged = []
    try:
        for el in elements:
            r = await comp.check_term(el)
            if not r["is_safe"]:
                flagged.append({"term": el, "type": "element", "issues": r["issues"]})
        if text:
            r = await comp.check_design_prompt(text, text, "")
            for iss in r.get("issues", []):
                flagged.append({"term": iss.get("term"), "type": "text", "issues": [iss]})
    finally:
        await comp.close()
    # Dedupe nach (term, type) -> n-gram-Extraktion kann denselben Treffer
    # mehrfach liefern; UI soll jede Marke nur einmal sehen.
    deduped, seen = [], set()
    for f in flagged:
        key = (f.get("term"), f.get("type"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)
    return {"compliant": len(deduped) == 0,
            "checked": {"text": bool(text), "elements": elements},
            "flagged": deduped}


@router.get("/designs/{design_id}/image-file")
async def design_image_file(design_id: int):
    """Liefert das gespeicherte 4500x5400 Print-PNG (Upload-fertig)."""
    import os
    from fastapi.responses import FileResponse
    from app.tshirt_factory.engines.imagegen import DESIGN_DIR
    path = os.path.join(DESIGN_DIR, f"{design_id}.png")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Kein Print-PNG gespeichert")
    return FileResponse(path, media_type="image/png", filename=f"design_{design_id}.png")


@router.post("/designs/{design_id}/listing-by-vision")
async def listing_by_vision(design_id: int, db: AsyncSession = Depends(get_db)):
    """AI Listing by Vision: liest das Design-Bild und schreibt das komplette
    MBA-Listing (Brand/Title/2 Bullets/Description) in EN + DE, prueft es durchs
    Trademark-Pre-Flight-Gate. Braucht ein vorhandenes Design-Bild."""
    import os
    import base64
    from app.tshirt_factory.engines.imagegen import DESIGN_DIR
    from app.tshirt_factory.engines.listing_vision import ListingVisionWriter, LIMITS
    from app.tshirt_factory.models import DesignPrompt, DesignImage

    d = (await db.execute(select(DesignPrompt).where(DesignPrompt.id == design_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Design nicht gefunden")

    writer = ListingVisionWriter()
    b64 = media = None
    # 1) bevorzugt das gespeicherte Print-PNG
    path = os.path.join(DESIGN_DIR, f"{design_id}.png")
    if os.path.exists(path):
        with open(path, "rb") as f:
            b64 = base64.standard_b64encode(f.read()).decode("ascii")
        media = "image/png"
    else:
        # 2) sonst die zuletzt gespeicherte Bild-URL
        img = (await db.execute(
            select(DesignImage).where(DesignImage.design_id == design_id)
            .order_by(DesignImage.id.desc()))).scalars().first()
        if img and img.url:
            fetched = await writer.fetch_image(img.url)
            if fetched:
                b64, media = fetched
    if not b64:
        raise HTTPException(status_code=400, detail="Kein Design-Bild vorhanden — erst Bild generieren")

    listing = writer.write_from_image(b64, media)
    if not listing:
        raise HTTPException(status_code=502, detail="Listing-Generierung fehlgeschlagen")

    # Pre-Flight-Trademark-Check auf dem EN-Listing
    en = listing.get("en", {})
    combined = " ".join([en.get("brand", ""), en.get("title", ""),
                         en.get("bullet1", ""), en.get("bullet2", ""), en.get("description", "")])
    from app.tshirt_factory.engines.compliance import ComplianceEngine
    comp = ComplianceEngine(db)
    try:
        chk = await comp.check_design_prompt(combined, en.get("title", ""), en.get("brand", ""))
    finally:
        await comp.close()
    flagged = sorted({(i.get("term") or "") for i in chk.get("issues", []) if i.get("term")})

    return {
        "design_id": design_id,
        "en": listing.get("en", {}),
        "de": listing.get("de", {}),
        "limits": LIMITS,
        "compliant": chk.get("is_compliant", True),
        "flagged": flagged,
    }
