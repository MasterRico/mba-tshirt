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
                r = await c.post(API_URL, headers={"Api-Key": self.key}, json=form)
            if r.status_code != 200:
                return {"error": f"Ideogram {r.status_code}: {r.text[:300]}"}
            j = r.json()
            arr = j.get("data") or j.get("images") or []
            url = (arr[0].get("url") if arr and isinstance(arr[0], dict) else None)
            return {"url": url, "raw": j if not url else None}
        except Exception as e:
            return {"error": str(e)}


DESIGN_DIR = "/app/data/design_images"


async def download_and_upscale(image_url: str, design_id: int) -> str | None:
    """Laedt das Ideogram-PNG, skaliert auf MBA-Format 4500x5400 (zentriert auf
    schwarzem Grund) und speichert es persistent. Gibt den lokalen Pfad zurueck."""
    import os
    import io
    try:
        from PIL import Image
    except Exception as e:
        logger.warning(f"Pillow nicht installiert: {e}")
        return None
    try:
        async with httpx.AsyncClient(timeout=120.0) as c:
            r = await c.get(image_url)
        if r.status_code != 200:
            return None
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        W, H = 4500, 5400
        scale = min(W / img.width, H / img.height)
        new = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
        img = img.resize(new, Image.LANCZOS)
        canvas = Image.new("RGB", (W, H), (0, 0, 0))
        canvas.paste(img, ((W - new[0]) // 2, (H - new[1]) // 2))
        os.makedirs(DESIGN_DIR, exist_ok=True)
        path = os.path.join(DESIGN_DIR, f"{design_id}.png")
        canvas.save(path, "PNG")
        return path
    except Exception as e:
        logger.warning(f"Upscale/Save fehlgeschlagen: {e}")
        return None
