"""Keyword Engine - Amazon SEO keyword research for listings."""

import logging
import re
from collections import Counter
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.tshirt_factory.config import tsf_settings
from app.tshirt_factory.models import ResearchItem, TrendData, NicheProfile

logger = logging.getLogger(__name__)


class KeywordEngine:
    """Amazon-focused keyword research for MBA listings."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.http_client = httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": "Mozilla/5.0"},
            follow_redirects=True,
        )

    async def get_amazon_suggestions(self, seed_keyword: str) -> list[str]:
        """Get Amazon autocomplete suggestions for a keyword.

        Uses Amazon's public autocomplete API - the same data source
        that tools like Merch Informer and Flying Research use.
        """
        suggestions = []
        marketplace = tsf_settings.AMAZON_MARKETPLACE

        # Amazon Autocomplete API (public, no auth needed)
        url = f"https://completion.amazon.{marketplace}/api/2017/suggestions"
        params = {
            "mid": "ATVPDKIKX0DER",  # US marketplace
            "alias": "fashion",
            "prefix": seed_keyword,
            "event": "onKeyPress",
            "limit": 10,
            "fb": 1,
            "suggestion-type": "KEYWORD",
        }

        try:
            response = await self.http_client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                for suggestion in data.get("suggestions", []):
                    value = suggestion.get("value", "")
                    if value and value != seed_keyword:
                        suggestions.append(value)
        except Exception as e:
            logger.debug(f"Amazon autocomplete failed for '{seed_keyword}': {e}")

        # Alphabet soup technique - append each letter to get more suggestions
        if not suggestions:
            for letter in "abcdefghijklmnopqrstuvwxyz":
                try:
                    params["prefix"] = f"{seed_keyword} {letter}"
                    response = await self.http_client.get(url, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        for s in data.get("suggestions", []):
                            val = s.get("value", "")
                            if val and val not in suggestions:
                                suggestions.append(val)
                except Exception:
                    continue

        return suggestions

    async def research_niche_keywords(self, niche_name: str) -> dict:
        """Full keyword research for a niche.

        Combines:
        1. Amazon autocomplete suggestions
        2. Keywords from top-selling research items
        3. Google Trends related keywords
        4. Long-tail keyword generation
        """
        all_keywords = Counter()

        # 1. Amazon autocomplete
        seed_keywords = await self._get_seed_keywords(niche_name)
        for seed in seed_keywords[:5]:
            suggestions = await self.get_amazon_suggestions(seed)
            for s in suggestions:
                all_keywords[s] += 2  # Higher weight for Amazon suggestions

        # 2. Keywords from research items
        stmt = select(ResearchItem).where(
            ResearchItem.title.ilike(f"%{niche_name}%"),
            ResearchItem.bsr.isnot(None),
            ResearchItem.bsr < tsf_settings.BSR_GOOD_THRESHOLD,
        ).order_by(ResearchItem.bsr.asc()).limit(50)
        result = await self.db.execute(stmt)
        items = result.scalars().all()

        for item in items:
            if item.keywords:
                for kw in item.keywords:
                    all_keywords[kw] += 3  # Highest weight for winner keywords
            # Also extract from titles
            title_kws = self._extract_keywords(item.title)
            for kw in title_kws:
                all_keywords[kw] += 1

        # 3. Google Trends related
        stmt = select(TrendData).where(
            TrendData.keyword.ilike(f"%{niche_name}%"),
        ).order_by(TrendData.recorded_at.desc()).limit(10)
        result = await self.db.execute(stmt)
        trends = result.scalars().all()

        for trend in trends:
            if trend.related_keywords:
                for kw in trend.related_keywords:
                    all_keywords[kw] += 1

        # 4. Generate long-tail combinations
        long_tails = self._generate_long_tails(niche_name, list(all_keywords.keys())[:10])
        for lt in long_tails:
            all_keywords[lt] += 1

        # Sort by relevance score
        sorted_keywords = all_keywords.most_common(100)

        return {
            "niche": niche_name,
            "primary_keywords": [kw for kw, _ in sorted_keywords[:10]],
            "secondary_keywords": [kw for kw, _ in sorted_keywords[10:30]],
            "long_tail_keywords": [kw for kw, _ in sorted_keywords[30:60]],
            "all_keywords": dict(sorted_keywords),
            "total_unique": len(sorted_keywords),
        }

    async def generate_listing_keywords(self, niche_name: str,
                                         primary_text: str,
                                         target_audience: str = "") -> dict:
        """Generate optimized listing keywords for a specific design."""
        # Get niche keywords
        niche_research = await self.research_niche_keywords(niche_name)
        primary_kws = niche_research.get("primary_keywords", [])
        secondary_kws = niche_research.get("secondary_keywords", [])

        # Extract keywords from the design text itself
        design_keywords = self._extract_keywords(primary_text)

        # Build optimized title (max 80 chars for MBA)
        title_keywords = primary_kws[:3] + design_keywords[:2]
        title = self._build_listing_title(primary_text, title_keywords, max_len=60)

        # Build bullet points (max 256 chars each)
        bullet1 = self._build_bullet(
            primary_kws[:5],
            f"Perfect {niche_name} design",
            target_audience,
            max_len=256,
        )
        bullet2 = self._build_bullet(
            secondary_kws[:5],
            "Great gift idea",
            "",
            max_len=256,
        )

        # Build search keywords (max 7 for MBA backend)
        backend_keywords = (primary_kws + secondary_kws + design_keywords)[:7]

        return {
            "title": title,
            "bullet1": bullet1,
            "bullet2": bullet2,
            "backend_keywords": backend_keywords,
            "all_researched_keywords": primary_kws + secondary_kws,
        }

    # ─── Helpers ──────────────────────────────────────────────────

    async def _get_seed_keywords(self, niche_name: str) -> list[str]:
        """Get seed keywords for a niche from the profile or defaults."""
        stmt = select(NicheProfile).where(NicheProfile.name == niche_name)
        result = await self.db.execute(stmt)
        profile = result.scalar_one_or_none()

        if profile and profile.top_keywords:
            return profile.top_keywords[:5]

        # Fallback: use niche name variations
        return [
            f"{niche_name} shirt",
            f"{niche_name} tshirt",
            f"funny {niche_name}",
            f"{niche_name} gift",
        ]

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract meaningful keywords from text."""
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "can", "this", "that",
            "these", "those", "i", "you", "he", "she", "it", "we", "they",
            "my", "your", "his", "its", "our", "their", "and", "or", "but",
            "for", "from", "with", "in", "on", "at", "to", "of", "by",
            "shirt", "tshirt", "t-shirt", "tee",
        }
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        return [w for w in words if w not in stop_words]

    def _generate_long_tails(self, niche: str, keywords: list[str]) -> list[str]:
        """Generate long-tail keyword combinations."""
        modifiers = [
            "funny", "cool", "best", "vintage", "retro", "cute",
            "gift", "birthday", "christmas", "men", "women",
        ]
        long_tails = []
        for kw in keywords[:5]:
            for mod in modifiers[:5]:
                long_tails.append(f"{mod} {kw}")
                long_tails.append(f"{kw} {mod}")
        long_tails.append(f"funny {niche} shirt")
        long_tails.append(f"{niche} gift idea")
        long_tails.append(f"best {niche} tshirt")
        return long_tails

    def _build_listing_title(self, design_text: str, keywords: list[str],
                             max_len: int = 60) -> str:
        """Build a natural, human-readable MBA listing title (no pipe-stuffing)."""
        base = (design_text or "").strip().strip(".")
        # ein kurzes, beschreibendes Keyword waehlen, das noch nicht im Text steht
        extra = ""
        for kw in keywords:
            k = (kw or "").strip()
            if k and k.lower() not in base.lower() and len(k) <= 18:
                extra = k.title()
                break
        # Kandidaten in absteigender Reichhaltigkeit, erster der in max_len passt
        candidates = []
        if extra:
            candidates.append(f"{base} {extra} Gift Tee")
            candidates.append(f"{base} {extra} Tee")
        candidates += [f"{base} Funny Gift Tee", f"{base} Tee", base]
        for cand in candidates:
            if len(cand) <= max_len:
                return cand
        return base[:max_len]

    def _build_bullet(self, keywords: list[str], prefix: str,
                      audience: str, max_len: int = 256) -> str:
        """Build an SEO-optimized bullet point."""
        parts = [prefix]
        if audience:
            parts.append(f"for {audience}")

        # Add keywords naturally
        kw_text = ", ".join(keywords[:5])
        if kw_text:
            parts.append(f"featuring {kw_text}")

        bullet = " ".join(parts)
        if len(bullet) > max_len:
            bullet = bullet[:max_len - 3] + "..."
        return bullet

    async def close(self):
        await self.http_client.aclose()
