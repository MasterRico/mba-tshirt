"""T-Shirt Factory configuration."""

from pydantic_settings import BaseSettings
from typing import Optional


class TShirtFactorySettings(BaseSettings):
    # General
    MBA_TIER: int = 100
    MAX_SLOTS: int = 100
    ROTATION_DAYS: int = 90  # Days before underperformer gets rotated out

    # Claude API for AI-powered analysis & prompt generation
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    # Research
    RESEARCH_INTERVAL_HOURS: int = 24
    MAX_RESEARCH_ITEMS_PER_RUN: int = 50
    TREND_LOOKBACK_DAYS: int = 90

    # Google Trends
    GOOGLE_TRENDS_REGION: str = "US"
    GOOGLE_TRENDS_LANGUAGE: str = "en-US"

    # Amazon Research
    AMAZON_MARKETPLACE: str = "com"  # com, de, co.uk
    AMAZON_BSR_THRESHOLD: int = 500_000  # Below this = potential winner

    # USPTO Compliance
    USPTO_API_BASE: str = "https://tsdrapi.uspto.gov"
    TRADEMARK_CACHE_DAYS: int = 30  # Re-check trademarks after this

    # Design Generation
    DESIGNS_PER_BATCH: int = 10
    MIN_CONFIDENCE_SCORE: float = 0.7  # Minimum score to approve a design prompt
    DESIGN_TYPES: list = [
        "text_only",
        "text_with_icon",
        "illustration",
        "typography_art",
    ]

    # Niche Strategy
    MAX_NICHES: int = 10  # Focus on max 10 niches for Tier 100
    MIN_DESIGNS_PER_NICHE: int = 5
    MAX_DESIGNS_PER_NICHE: int = 20

    # Performance Thresholds
    BSR_WINNER_THRESHOLD: int = 100_000
    BSR_GOOD_THRESHOLD: int = 300_000
    BSR_UNDERPERFORMER_THRESHOLD: int = 1_000_000
    MIN_DAYS_BEFORE_ROTATION: int = 60

    # Seasonal Planning
    SEASONAL_UPLOAD_LEAD_DAYS: int = 45  # Upload seasonal designs X days before event

    # Self-Learning
    LEARNING_MIN_DATAPOINTS: int = 20  # Min designs before model starts adjusting
    LEARNING_UPDATE_INTERVAL_HOURS: int = 48

    model_config = {"env_file": ".env", "env_prefix": "TSF_", "case_sensitive": True}


tsf_settings = TShirtFactorySettings()
