"""Pydantic schemas for T-Shirt Factory API."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ─── Research ─────────────────────────────────────────────────────────

class ResearchItemOut(BaseModel):
    id: int
    source: str
    title: str
    niche: Optional[str] = None
    design_type: Optional[str] = None
    bsr: Optional[int] = None
    primary_colors: Optional[list] = None
    font_style: Optional[str] = None
    text_content: Optional[str] = None
    humor_type: Optional[str] = None
    target_audience: Optional[str] = None
    keywords: Optional[list] = None
    scraped_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TrendDataOut(BaseModel):
    id: int
    keyword: str
    source: str
    interest_score: Optional[float] = None
    trend_direction: Optional[str] = None
    related_keywords: Optional[list] = None
    niche: Optional[str] = None
    recorded_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─── Niche ────────────────────────────────────────────────────────────

class NicheProfileOut(BaseModel):
    id: int
    name: str
    category: str
    competition_level: Optional[str] = None
    avg_bsr: Optional[int] = None
    top_keywords: Optional[list] = None
    top_design_types: Optional[list] = None
    win_rate: float = 0.0
    total_designs_analyzed: int = 0
    confidence_score: float = 0.0
    is_active: bool = True
    last_updated: Optional[datetime] = None

    model_config = {"from_attributes": True}


class NicheCreateIn(BaseModel):
    name: str
    category: str = "evergreen"


# ─── Design Prompts ──────────────────────────────────────────────────

class DesignPromptOut(BaseModel):
    id: int
    niche_id: Optional[int] = None
    status: str
    design_type: str
    prompt_text: str
    primary_text: Optional[str] = None
    sub_text: Optional[str] = None
    color_scheme: Optional[list] = None
    font_suggestion: Optional[str] = None
    target_audience: Optional[str] = None
    seasonal_event: Optional[str] = None
    confidence_score: float = 0.0
    composite_score: float = 0.0
    trademark_cleared: bool = False
    listing_title: Optional[str] = None
    listing_brand: Optional[str] = None
    listing_bullet1: Optional[str] = None
    listing_bullet2: Optional[str] = None
    listing_description: Optional[str] = None
    listing_keywords: Optional[list] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DesignGenerateIn(BaseModel):
    niche_name: Optional[str] = None
    count: int = Field(default=5, ge=1, le=20)
    design_type: Optional[str] = None
    seasonal_event: Optional[str] = None


# ─── Performance ──────────────────────────────────────────────────────

class PerformanceUpdateIn(BaseModel):
    design_id: int
    asin: Optional[str] = None
    units_sold: int = 0
    royalties_earned: float = 0.0
    current_bsr: Optional[int] = None
    page_views: int = 0


class PerformanceOut(BaseModel):
    id: int
    design_id: int
    asin: Optional[str] = None
    units_sold: int = 0
    royalties_earned: float = 0.0
    current_bsr: Optional[int] = None
    best_bsr: Optional[int] = None
    days_live: int = 0
    is_winner: bool = False
    should_rotate: bool = False
    last_updated: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PerformanceBulkImportIn(BaseModel):
    """For importing MBA sales CSV data."""
    csv_data: str  # Raw CSV content from MBA sales report


# ─── Trademark ────────────────────────────────────────────────────────

class TrademarkCheckIn(BaseModel):
    terms: list[str]


class TrademarkCheckOut(BaseModel):
    term: str
    is_trademarked: bool
    trademark_owner: Optional[str] = None
    status: Optional[str] = None
    details: Optional[dict] = None


# ─── Slot Management ─────────────────────────────────────────────────

class SlotSummaryOut(BaseModel):
    total_slots: int
    used_slots: int
    available_slots: int
    winners: int
    underperformers: int
    pending_rotation: list[int] = []  # design IDs to rotate
    niche_distribution: dict = {}


# ─── Dashboard ────────────────────────────────────────────────────────

class DashboardOut(BaseModel):
    slots: SlotSummaryOut
    top_niches: list[NicheProfileOut] = []
    recent_designs: list[DesignPromptOut] = []
    recent_trends: list[TrendDataOut] = []
    learning_summary: dict = {}
    season_upcoming: list[dict] = []


# ─── Learning ─────────────────────────────────────────────────────────

class LearningInsightOut(BaseModel):
    id: int
    category: str
    insight_key: str
    insight_value: str
    confidence: float
    sample_size: int
    positive_outcomes: int
    negative_outcomes: int
    last_updated: Optional[datetime] = None

    model_config = {"from_attributes": True}
