"""Ideogram 3.0 Bildgenerierung fuer Top-Design-Konzepte.

Erzeugt aus einem Design-Prompt ein print-taugliches Motiv auf SOLIDEM
SCHWARZEM Hintergrund -> direkt auf schwarze Shirts nutzbar (kein Transparenz-
Schritt noetig). Upscale/Transparenz fuer andere Shirtfarben = Folgeschritt.
"""

import logging
import httpx

from app.tshirt_factory.config import tsf_settings

logger = logging.getLogger(__name__)
API_URL = "https://api.ideogram.ai/v1/ideogram-v3/generate"


class IdeogramGenerator:
    def __init__(self):
        self.key = getattr(tsf_settings, "IDEOGRAM_API_KEY", None)

    async def generate(self, prompt: str, aspect_ratio: str = "1x1") -> dict:
        if not self.key:
            return {"error": "IDEOGRAM_API_KEY nicht gesetzt (TSF_IDEOGRAM_API_KEY in Coolify)"}
        form = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "rendering_speed": "DEFAULT",
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as c:
                r = await c.post(API_URL, headers={"Api-Key": self.key}, data=form)
            if r.status_code != 200:
                return {"error": f"Ideogram {r.status_code}: {r.text[:300]}"}
            j = r.json()
            arr = j.get("data") or j.get("images") or []
            url = (arr[0].get("url") if arr and isinstance(arr[0], dict) else None)
            return {"url": url, "raw": j if not url else None}
        except Exception as e:
            return {"error": str(e)}
