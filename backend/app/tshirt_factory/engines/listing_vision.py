"""AI Listing by Vision - schreibt ein komplettes MBA-Listing aus dem Design-Bild.

Schickt das fertige Design-Bild an Claude (Vision) und laesst daraus ein
verkaufsfertiges Merch-by-Amazon-Listing schreiben: Brand, Title, 2 Bullets,
Description - in EN und DE, unter Einhaltung der MBA-Zeichenlimits und der
Brand-Constraints (keine geschuetzten Begriffe). Pendant zu FRs
"AI - Listing By Vision". Eigenes Design + eigene KI = compliant.
"""

import base64
import json
import logging

import httpx

from app.tshirt_factory.config import tsf_settings

logger = logging.getLogger(__name__)

# MBA-Feld-Limits (aus der MBA/FR-Oberflaeche)
LIMITS = {"brand": 50, "title": 60, "bullet1": 256, "bullet2": 256, "description": 2000}

_ALLOWED_MEDIA = {"image/jpeg", "image/png", "image/webp", "image/gif"}

_PROMPT = f"""You are a Merch by Amazon listing copywriter. Look at this t-shirt design image and write a complete, conversion- and search-optimized listing for it.

Write the listing in BOTH English (en) and natural German for amazon.de (de) — the German must read naturally for German buyers, NOT a literal translation.

HARD CHARACTER LIMITS (stay safely under, never exceed):
- brand: max {LIMITS['brand']} chars
- title: max {LIMITS['title']} chars
- bullet1: max {LIMITS['bullet1']} chars
- bullet2: max {LIMITS['bullet2']} chars
- description: max {LIMITS['description']} chars

RULES:
- Read the actual text and motif ON the design and build the listing around it.
- Title: natural and keyword-rich, NO pipe stuffing, NO quotation marks, readable.
- Brand: a plausible invented brand name — NEVER a real/registered trademark, character, band, team or company.
- Bullets: who it's for + occasion/gift angle + a benefit; concrete, not generic.
- Description: 2-4 sentences, mention it's a great gift idea.
- STRICTLY AVOID trademarked names, characters, slogans, brands, sports teams, Disney/Marvel/Pokemon etc.
- No medical claims, no profanity.

Return ONLY valid JSON (no markdown), exactly:
{{
  "en": {{"brand": "", "title": "", "bullet1": "", "bullet2": "", "description": ""}},
  "de": {{"brand": "", "title": "", "bullet1": "", "bullet2": "", "description": ""}}
}}"""


class ListingVisionWriter:
    def __init__(self):
        self._client = None

    @property
    def claude(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=tsf_settings.ANTHROPIC_API_KEY)
        return self._client

    async def fetch_image(self, url: str) -> tuple[str, str] | None:
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as c:
                r = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                return None
            media = r.headers.get("content-type", "image/png").split(";")[0].strip()
            if media not in _ALLOWED_MEDIA:
                media = "image/png"
            return base64.standard_b64encode(r.content).decode("ascii"), media
        except Exception as e:
            logger.warning(f"Image fetch failed for {url}: {e}")
            return None

    def write_from_image(self, b64: str, media_type: str) -> dict | None:
        try:
            msg = self.claude.messages.create(
                model=tsf_settings.ANTHROPIC_MODEL,
                max_tokens=1500,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {
                            "type": "base64", "media_type": media_type, "data": b64}},
                        {"type": "text", "text": _PROMPT},
                    ],
                }],
            )
            text = msg.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
            data = json.loads(text)
            return self._enforce_limits(data)
        except json.JSONDecodeError as e:
            logger.error(f"Listing JSON parse failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Listing vision call failed: {e}")
            return None

    @staticmethod
    def _enforce_limits(data: dict) -> dict:
        """Harte Sicherung der Zeichenlimits (falls Claude leicht ueberzieht)."""
        for lang in ("en", "de"):
            block = data.get(lang) or {}
            for field, limit in LIMITS.items():
                val = (block.get(field) or "").strip()
                if len(val) > limit:
                    val = val[:limit].rstrip()
                block[field] = val
            data[lang] = block
        return data
