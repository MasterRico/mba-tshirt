"""SQLAlchemy models for T-Shirt Design Factory."""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Text, Boolean, DateTime, JSON,
    ForeignKey, Index, Enum as SAEnum,
)
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class DesignStatus(str, enum.Enum):
    DRAFT = "draft"
    COMPLIANCE_CHECK = "compliance_check"
    APPROVED = "approved"
    UPLOADED = "uploaded"
    LIVE = "live"
    UNDERPERFORMING = "underperforming"
    ROTATED_OUT = "rotated_out"


class DesignType(str, enum.Enum):
    TEXT_ONLY = "text_only"
    TEXT_WITH_ICON = "text_with_icon"
    ILLUSTRATION = "illustration"
    TYPOGRAPHY_ART = "typography_art"


class NicheCategory(str, enum.Enum):
    EVERGREEN = "evergreen"
    TRENDING = "trending"
    SEASONAL = "seasonal"
    MICRO_NICHE = "micro_niche"


# ─── Research & Knowledge ────────────────────────────────────────────

class ResearchItem(Base):
    """Scraped/researched winning designs from the market."""
    __tablename__ = "tsf_research_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False)  # amazon, etsy, redbubble, google_trends
    external_id = Column(String(200), nullable=True)  # ASIN or external identifier
    title = Column(String(500), nullable=False)
    niche = Column(String(200), nullable=True)
    design_type = Column(String(50), nullable=True)
    bsr = Column(Integer, nullable=True)
    price = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    rating = Column(Float, nullable=True)

    # Analyzed design attributes
    primary_colors = Column(JSON, nullable=True)  # ["#fff", "#000"]
    font_style = Column(String(100), nullable=True)  # bold, script, serif, etc.
    text_content = Column(Text, nullable=True)
    design_elements = Column(JSON, nullable=True)  # ["icon", "border", "distressed"]
    humor_type = Column(String(50), nullable=True)  # pun, sarcasm, wholesome, none
    target_audience = Column(String(200), nullable=True)
    keywords = Column(JSON, nullable=True)

    # Metadata
    scraped_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    marketplace = Column(String(20), default="com")
    url = Column(String(1000), nullable=True)
    image_url = Column(String(1000), nullable=True)

    __table_args__ = (
        Index("idx_research_niche", "niche"),
        Index("idx_research_bsr", "bsr"),
        Index("idx_research_source", "source"),
    )


class TrendData(Base):
    """Tracked trend data over time."""
    __tablename__ = "tsf_trend_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(200), nullable=False)
    source = Column(String(50), nullable=False)  # google_trends, social, amazon
    interest_score = Column(Float, nullable=True)  # 0-100
    volume_estimate = Column(Integer, nullable=True)
    trend_direction = Column(String(20), nullable=True)  # rising, stable, declining
    related_keywords = Column(JSON, nullable=True)
    niche = Column(String(200), nullable=True)
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_trend_keyword", "keyword"),
        Index("idx_trend_recorded", "recorded_at"),
    )


class NicheProfile(Base):
    """Analyzed niche profiles with performance data."""
    __tablename__ = "tsf_niche_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, unique=True)
    category = Column(String(50), default=NicheCategory.EVERGREEN.value)
    competition_level = Column(String(20), nullable=True)  # low, medium, high
    avg_bsr = Column(Integer, nullable=True)
    avg_price = Column(Float, nullable=True)
    avg_reviews = Column(Integer, nullable=True)
    top_keywords = Column(JSON, nullable=True)
    top_design_types = Column(JSON, nullable=True)
    top_colors = Column(JSON, nullable=True)
    top_font_styles = Column(JSON, nullable=True)
    top_humor_types = Column(JSON, nullable=True)
    target_audiences = Column(JSON, nullable=True)
    win_rate = Column(Float, default=0.0)  # % of designs that become winners
    total_designs_analyzed = Column(Integer, default=0)
    confidence_score = Column(Float, default=0.0)  # 0-1, how confident we are
    is_active = Column(Boolean, default=True)
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── Design Pipeline ─────────────────────────────────────────────────

class DesignPrompt(Base):
    """Generated design prompts ready for image generation."""
    __tablename__ = "tsf_design_prompts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    niche_id = Column(Integer, ForeignKey("tsf_niche_profiles.id"), nullable=True)
    status = Column(String(30), default=DesignStatus.DRAFT.value)
    design_type = Column(String(50), nullable=False)

    # The actual prompt
    prompt_text = Column(Text, nullable=False)
    prompt_negative = Column(Text, nullable=True)  # What to avoid
    style_instructions = Column(Text, nullable=True)

    # Design metadata
    primary_text = Column(String(500), nullable=True)  # Main text on shirt
    sub_text = Column(String(500), nullable=True)
    color_scheme = Column(JSON, nullable=True)
    font_suggestion = Column(String(100), nullable=True)
    target_audience = Column(String(200), nullable=True)
    humor_type = Column(String(50), nullable=True)
    seasonal_event = Column(String(100), nullable=True)  # christmas, halloween, etc.

    # Scores
    confidence_score = Column(Float, default=0.0)
    trend_score = Column(Float, default=0.0)
    competition_score = Column(Float, default=0.0)
    composite_score = Column(Float, default=0.0)

    # Compliance
    trademark_cleared = Column(Boolean, default=False)
    compliance_notes = Column(Text, nullable=True)

    # Listing
    listing_title = Column(String(200), nullable=True)
    listing_brand = Column(String(50), nullable=True)
    listing_bullet1 = Column(String(256), nullable=True)
    listing_bullet2 = Column(String(256), nullable=True)
    listing_description = Column(Text, nullable=True)
    listing_keywords = Column(JSON, nullable=True)

    # Learning feedback
    was_uploaded = Column(Boolean, default=False)
    upload_date = Column(DateTime, nullable=True)
    rotation_date = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship
    niche = relationship("NicheProfile", backref="design_prompts")
    performance = relationship("DesignPerformance", back_populates="design", uselist=False)

    __table_args__ = (
        Index("idx_prompt_status", "status"),
        Index("idx_prompt_niche", "niche_id"),
        Index("idx_prompt_score", "composite_score"),
    )


# ─── Performance Tracking ────────────────────────────────────────────

class DesignPerformance(Base):
    """Track real MBA performance data for self-learning."""
    __tablename__ = "tsf_design_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    design_id = Column(Integer, ForeignKey("tsf_design_prompts.id"), nullable=False)
    asin = Column(String(20), nullable=True)

    # Sales metrics (manually entered or imported via CSV)
    units_sold = Column(Integer, default=0)
    royalties_earned = Column(Float, default=0.0)
    current_bsr = Column(Integer, nullable=True)
    best_bsr = Column(Integer, nullable=True)
    page_views = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)

    # BSR history (JSON array of {date, bsr} entries)
    bsr_history = Column(JSON, default=list)

    # Status
    days_live = Column(Integer, default=0)
    is_winner = Column(Boolean, default=False)
    should_rotate = Column(Boolean, default=False)

    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    design = relationship("DesignPrompt", back_populates="performance")

    __table_args__ = (
        Index("idx_perf_design", "design_id"),
        Index("idx_perf_winner", "is_winner"),
    )


# ─── Trademark Cache ─────────────────────────────────────────────────

class TrademarkCache(Base):
    """Cache USPTO trademark search results."""
    __tablename__ = "tsf_trademark_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    term = Column(String(300), nullable=False, index=True)
    is_trademarked = Column(Boolean, default=False)
    trademark_owner = Column(String(500), nullable=True)
    trademark_class = Column(String(100), nullable=True)  # Nice class
    serial_number = Column(String(50), nullable=True)
    status = Column(String(50), nullable=True)  # live, dead, pending
    details = Column(JSON, nullable=True)
    checked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── Learning Memory ─────────────────────────────────────────────────

class LearningInsight(Base):
    """Persistent self-learning insights extracted from performance data."""
    __tablename__ = "tsf_learning_insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(50), nullable=False)  # niche, design_type, color, font, etc.
    insight_key = Column(String(200), nullable=False)  # specific attribute
    insight_value = Column(Text, nullable=False)  # the learning
    confidence = Column(Float, default=0.5)
    sample_size = Column(Integer, default=0)
    positive_outcomes = Column(Integer, default=0)
    negative_outcomes = Column(Integer, default=0)
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_insight_cat_key", "category", "insight_key"),
    )
