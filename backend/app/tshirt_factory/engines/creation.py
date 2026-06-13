"""Creation Engine - AI-powered design prompt generation using Claude API."""

import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.tshirt_factory.config import tsf_settings
from app.tshirt_factory.models import (
    DesignPrompt, NicheProfile, LearningInsight, DesignStatus,
)
from app.tshirt_factory.engines.compliance import ComplianceEngine
from app.tshirt_factory.engines.keyword import KeywordEngine

logger = logging.getLogger(__name__)

NICHES_FILE = Path(__file__).parent.parent / "data" / "niches.json"
SEASON_FILE = Path(__file__).parent.parent / "data" / "season_calendar.json"


class CreationEngine:
    """Generates T-shirt design prompts using Claude AI, informed by research data."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.compliance = ComplianceEngine(db)
        self.keywords = KeywordEngine(db)
        self._claude_client = None

    @property
    def claude(self):
        if self._claude_client is None:
            try:
                import anthropic
                self._claude_client = anthropic.Anthropic(
                    api_key=tsf_settings.ANTHROPIC_API_KEY
                )
            except ImportError:
                raise RuntimeError("anthropic package not installed. Run: pip install anthropic")
        return self._claude_client

    async def generate_designs(self, niche_name: str = None, count: int = 5,
                                design_type: str = None,
                                seasonal_event: str = None) -> list[dict]:
        """Generate design prompts using Claude AI, informed by research insights.

        This is the core creative engine that combines:
        - Niche research data (what sells)
        - Trend data (what's hot right now)
        - Learning insights (what worked before)
        - Seasonal calendar (timely designs)
        - Compliance checks (no trademark issues)
        """
        # 1. Gather context for Claude
        context = await self._build_creation_context(niche_name, seasonal_event)

        # 2. Determine design type distribution
        if design_type:
            types = [design_type] * count
        else:
            types = self._distribute_design_types(count)

        # 3. Generate designs with Claude
        designs = []
        for dtype in types:
            prompt = self._build_claude_prompt(context, dtype, seasonal_event)
            design_data = await self._call_claude(prompt)

            if design_data:
                # 4. Compliance check
                compliance_result = await self.compliance.check_design_prompt(
                    prompt_text=design_data.get("prompt_text", ""),
                    primary_text=design_data.get("primary_text", ""),
                    listing_title=design_data.get("listing_title", ""),
                )

                if compliance_result["is_compliant"]:
                    # 5. Generate optimized listing keywords
                    niche = niche_name or design_data.get("niche", "general")
                    listing = await self.keywords.generate_listing_keywords(
                        niche_name=niche,
                        primary_text=design_data.get("primary_text", ""),
                        target_audience=design_data.get("target_audience", ""),
                    )

                    # 6. Create DesignPrompt record
                    design = await self._create_design_record(
                        design_data, dtype, niche_name, seasonal_event,
                        compliance_result, listing,
                    )
                    designs.append(design)
                else:
                    logger.warning(
                        f"Design failed compliance: {compliance_result['issues']}"
                    )
                    # Try to regenerate without flagged terms
                    design_data_v2 = await self._regenerate_without_flagged(
                        context, dtype, compliance_result, seasonal_event
                    )
                    if design_data_v2:
                        listing = await self.keywords.generate_listing_keywords(
                            niche_name=niche_name or "general",
                            primary_text=design_data_v2.get("primary_text", ""),
                        )
                        design = await self._create_design_record(
                            design_data_v2, dtype, niche_name, seasonal_event,
                            {"is_compliant": True, "issues": []}, listing,
                        )
                        designs.append(design)

        await self.db.commit()
        logger.info(f"Generated {len(designs)} design prompts")
        return designs

    async def _build_creation_context(self, niche_name: str = None,
                                       seasonal_event: str = None) -> dict:
        """Build rich context for Claude from all available data."""
        context = {
            "niches": {},
            "trends": [],
            "learning_insights": [],
            "seasonal": None,
        }

        # Niche profile data
        if niche_name:
            stmt = select(NicheProfile).where(NicheProfile.name == niche_name)
            result = await self.db.execute(stmt)
            profile = result.scalar_one_or_none()
            if profile:
                context["niches"][niche_name] = {
                    "top_keywords": profile.top_keywords,
                    "top_design_types": profile.top_design_types,
                    "top_colors": profile.top_colors,
                    "top_font_styles": profile.top_font_styles,
                    "top_humor_types": profile.top_humor_types,
                    "competition_level": profile.competition_level,
                    "avg_bsr": profile.avg_bsr,
                    "win_rate": profile.win_rate,
                }
        else:
            # Get top active niches
            stmt = select(NicheProfile).where(
                NicheProfile.is_active == True
            ).order_by(NicheProfile.win_rate.desc()).limit(5)
            result = await self.db.execute(stmt)
            for profile in result.scalars():
                context["niches"][profile.name] = {
                    "top_keywords": profile.top_keywords,
                    "top_design_types": profile.top_design_types,
                    "top_humor_types": profile.top_humor_types,
                    "win_rate": profile.win_rate,
                }

        # Learning insights
        stmt = select(LearningInsight).where(
            LearningInsight.confidence > 0.6
        ).order_by(LearningInsight.confidence.desc()).limit(20)
        result = await self.db.execute(stmt)
        for insight in result.scalars():
            context["learning_insights"].append({
                "category": insight.category,
                "key": insight.insight_key,
                "value": insight.insight_value,
                "confidence": insight.confidence,
            })

        # Seasonal context
        if seasonal_event:
            try:
                with open(SEASON_FILE) as f:
                    seasons = json.load(f)
                for s in seasons.get("seasons", []):
                    if s["event"] == seasonal_event:
                        context["seasonal"] = s
                        break
            except Exception:
                pass

        return context

    def _build_claude_prompt(self, context: dict, design_type: str,
                             seasonal_event: str = None) -> str:
        """Build the prompt for Claude to generate a T-shirt design."""
        niche_info = ""
        if context["niches"]:
            niche_info = "## Niche Research Data\n"
            for name, data in context["niches"].items():
                niche_info += f"\n### {name}\n"
                niche_info += f"- Top keywords: {data.get('top_keywords', [])}\n"
                niche_info += f"- Best design types: {data.get('top_design_types', [])}\n"
                niche_info += f"- Best humor types: {data.get('top_humor_types', [])}\n"
                niche_info += f"- Competition: {data.get('competition_level', 'unknown')}\n"
                niche_info += f"- Historical win rate: {data.get('win_rate', 0):.1%}\n"

        learning_info = ""
        if context["learning_insights"]:
            learning_info = "\n## Self-Learning Insights (from past performance)\n"
            for insight in context["learning_insights"]:
                learning_info += (
                    f"- [{insight['category']}] {insight['key']}: "
                    f"{insight['value']} (confidence: {insight['confidence']:.0%})\n"
                )

        seasonal_info = ""
        if context.get("seasonal"):
            s = context["seasonal"]
            seasonal_info = f"""
## Seasonal Context
Event: {s['name']}
Date: Month {s['date_month']}, Day {s['date_day']}
Relevant niches: {s.get('niches', [])}
Keywords to consider: {s.get('keywords', [])}
"""

        return f"""You are an expert Merch by Amazon T-shirt designer with years of experience
creating bestselling designs. Your task is to create a T-shirt design concept
that has a high probability of selling.

## Design Parameters
- Design type: {design_type}
- Target marketplace: Amazon.com (Merch by Amazon)
- Must be ORIGINAL - no trademarked content, no copyrighted characters/phrases
- Must appeal to a specific target audience
- Should be printable on a T-shirt (simple, clear, readable)

{niche_info}
{learning_info}
{seasonal_info}

## Your Task
Create ONE T-shirt design concept. Return ONLY valid JSON (no markdown, no explanation):

{{
    "primary_text": "The main text on the shirt (keep it short, impactful, max 8 words)",
    "sub_text": "Optional secondary text (or empty string)",
    "niche": "The target niche",
    "target_audience": "Who would buy this",
    "humor_type": "pun|sarcasm|wholesome|relatable|dark_humor|motivational|nerd_humor|none",
    "color_scheme": ["primary_hex", "secondary_hex"],
    "font_suggestion": "bold_sans|script|serif|handwritten|block|distressed|retro",
    "prompt_text": "Detailed prompt for an AI image generator to create this design. Include style, layout, colors, typography details.",
    "prompt_negative": "What to avoid in the image generation",
    "style_instructions": "Additional style notes for the designer",
    "listing_title": "SEO-optimized MBA listing title (max 80 chars)",
    "listing_bullet1": "First bullet point (max 256 chars)",
    "listing_bullet2": "Second bullet point (max 256 chars)",
    "listing_description": "Short product description",
    "confidence_reason": "Why you think this design will sell"
}}

IMPORTANT RULES:
1. NO trademarked words, characters, brands, TV shows, movies, celebrities
2. NO copyrighted phrases or slogans
3. Be SPECIFIC - vague designs don't sell
4. The text must be FUNNY, CLEVER, or DEEPLY RELATABLE to the target audience
5. Think about what someone would actually WEAR in public
6. Consider gift-buying occasions (birthday, christmas, job-related)
7. The listing title and bullets must be keyword-rich but natural
"""

    async def _call_claude(self, prompt: str) -> dict | None:
        """Call Claude API to generate a design concept."""
        try:
            message = self.claude.messages.create(
                model=tsf_settings.ANTHROPIC_MODEL,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text.strip()

            # Clean response - remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.split("\n", 1)[1]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()

            return json.loads(response_text)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            return None

    async def _regenerate_without_flagged(self, context: dict, design_type: str,
                                           compliance_result: dict,
                                           seasonal_event: str = None) -> dict | None:
        """Regenerate a design avoiding flagged terms."""
        flagged = [i.get("term", "") for i in compliance_result.get("issues", [])]
        extra_instruction = (
            f"\n\nCRITICAL: The following terms are TRADEMARKED and must NOT "
            f"be used anywhere in the design or listing: {flagged}\n"
            f"Create a completely different design that avoids these terms."
        )

        prompt = self._build_claude_prompt(context, design_type, seasonal_event)
        prompt += extra_instruction
        return await self._call_claude(prompt)

    async def _create_design_record(self, design_data: dict, design_type: str,
                                     niche_name: str, seasonal_event: str,
                                     compliance_result: dict,
                                     listing: dict) -> dict:
        """Create a DesignPrompt database record."""
        # Get niche ID
        niche_id = None
        if niche_name:
            stmt = select(NicheProfile).where(NicheProfile.name == niche_name)
            result = await self.db.execute(stmt)
            profile = result.scalar_one_or_none()
            if profile:
                niche_id = profile.id

        # Calculate composite score
        confidence = self._calculate_confidence(design_data)

        design = DesignPrompt(
            niche_id=niche_id,
            status=DesignStatus.APPROVED.value if compliance_result["is_compliant"]
                   else DesignStatus.COMPLIANCE_CHECK.value,
            design_type=design_type,
            prompt_text=design_data.get("prompt_text", ""),
            prompt_negative=design_data.get("prompt_negative", ""),
            style_instructions=design_data.get("style_instructions", ""),
            primary_text=design_data.get("primary_text", ""),
            sub_text=design_data.get("sub_text", ""),
            color_scheme=design_data.get("color_scheme", []),
            font_suggestion=design_data.get("font_suggestion", ""),
            target_audience=design_data.get("target_audience", ""),
            humor_type=design_data.get("humor_type", ""),
            seasonal_event=seasonal_event,
            confidence_score=confidence,
            composite_score=confidence,
            trademark_cleared=compliance_result["is_compliant"],
            compliance_notes=json.dumps(compliance_result.get("issues", [])),
            listing_title=listing.get("title", design_data.get("listing_title", "")),
            listing_brand="",  # User fills in their brand
            listing_bullet1=listing.get("bullet1", design_data.get("listing_bullet1", "")),
            listing_bullet2=listing.get("bullet2", design_data.get("listing_bullet2", "")),
            listing_description=design_data.get("listing_description", ""),
            listing_keywords=listing.get("backend_keywords", []),
        )

        self.db.add(design)
        await self.db.flush()

        return {
            "id": design.id,
            "primary_text": design.primary_text,
            "design_type": design_type,
            "confidence_score": confidence,
            "trademark_cleared": design.trademark_cleared,
            "listing_title": design.listing_title,
        }

    def _distribute_design_types(self, count: int) -> list[str]:
        """Distribute design types based on configured weights."""
        try:
            with open(NICHES_FILE) as f:
                data = json.load(f)
            weights = data.get("design_type_weights", {})
        except Exception:
            weights = {"text_only": 0.4, "text_with_icon": 0.3,
                       "illustration": 0.15, "typography_art": 0.15}

        types = list(weights.keys())
        probs = list(weights.values())
        return random.choices(types, weights=probs, k=count)

    def _calculate_confidence(self, design_data: dict) -> float:
        """Calculate a confidence score for a design based on various factors."""
        score = 0.5  # Base score

        # Has specific target audience
        if design_data.get("target_audience"):
            score += 0.1

        # Has humor (humor sells)
        humor = design_data.get("humor_type", "none")
        humor_bonus = {
            "sarcasm": 0.15, "pun": 0.12, "relatable": 0.13,
            "wholesome": 0.08, "dark_humor": 0.07, "motivational": 0.05,
            "nerd_humor": 0.1, "none": 0.0,
        }
        score += humor_bonus.get(humor, 0)

        # Short, punchy text
        primary = design_data.get("primary_text", "")
        word_count = len(primary.split())
        if 2 <= word_count <= 6:
            score += 0.1
        elif word_count > 10:
            score -= 0.1

        # Has a clear niche
        if design_data.get("niche"):
            score += 0.05

        return min(max(score, 0.0), 1.0)

    async def close(self):
        await self.compliance.close()
        await self.keywords.close()
