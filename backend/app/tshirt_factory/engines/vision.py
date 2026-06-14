"""Vision Analyzer - extrahiert visuelle Gewinnermuster aus Winner-Designs.

Schickt ein Design-Bild an Claude (Vision) und liefert strukturierte
Attribute (Font, Layout, Farben, Elemente, Humor-Typ, Text) zurueck, die
in ResearchItem geschrieben und via analysis.py zu NicheProfile aggregiert
werden. Das ist das bisher fehlende Glied: Wissensaufbau aus echten Winnern.
"""

import base64
import json
import logging

import httpx

from app.tshirt_factory.config import tsf_settings

logger = logging.getLogger(__name__)

_ALLOWED_MEDIA = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
}

_PROMPT = """You are a print-on-demand design analyst. Analyze this t-shirt design image and extract its visual attributes for a winning-pattern database.

Return ONLY valid JSON (no markdown) with exactly these keys:
{
  "design_type": "one of: text_only | text_with_icon | illustration | typography_art",
  "font_style": "short label, e.g. bold_sans | condensed_impact | script | serif | handwritten | distressed_vintage",
  "primary_colors": ["main ink colors as simple names, e.g. white, cream, gold, teal"],
  "design_elements": ["notable elements, e.g. distressed_texture, sunset_stripes, badge, icon_coffee, paw, none"],
  "humor_type": "one of: pun | sarcasm | wholesome | dark | identity_statement | none",
  "text_content": "the readable text on the design, verbatim",
  "target_audience": "short phrase, who buys/wears this",
  "layout": "short description of composition, e.g. 'stacked 3 lines, big punchline top, small icon between'"
}"""


class VisionAnalyzer:
    def __init__(self):
        self._client = None

    @property
    def claude(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=tsf_settings.ANTHROPIC_API_KEY)
        return self._client

    async def fetch_image(self, url: str) -> tuple[str, str] | None:
        """Lade Bild -> (base64, media_type). None bei Fehler."""
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as c:
                r = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                logger.warning(f"Image fetch {r.status_code} for {url}")
                return None
            media = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            if media not in _ALLOWED_MEDIA:
                media = "image/jpeg"
            return base64.standard_b64encode(r.content).decode("ascii"), media
        except Exception as e:
            logger.warning(f"Image fetch failed for {url}: {e}")
            return None

    async def analyze_url(self, image_url: str) -> dict | None:
        img = await self.fetch_image(image_url)
        if not img:
            return None
        b64, media = img
        return self._call_vision(b64, media)

    def _call_vision(self, b64: str, media_type: str) -> dict | None:
        try:
            msg = self.claude.messages.create(
                model=tsf_settings.ANTHROPIC_MODEL,
                max_tokens=600,
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
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Vision JSON parse failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Vision call failed: {e}")
            return None
