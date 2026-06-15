"""Curation Engine - rankt Designs nach Know-how-Fit (Winner-Wahrscheinlichkeit).

Vergleicht jedes Design mit dem NicheProfile seiner Nische (Gewinner-Font/
-Farben/-Humor/-Design-Typ) und liefert einen Fit-Score 0-1 + Begruendung.
So sieht man sofort, welche generierten Designs am ehesten verkaufen ->
Kuratierungs-/Upload-Cockpit.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tshirt_factory.models import DesignPrompt, NicheProfile, DesignStatus

# grobe Hex->Name-Normalisierung, damit Profil-Namen und Design-Hex matchen
_HEX = {
    "#ffffff": "white", "#fff": "white", "#000000": "black", "#000": "black",
    "#ffd700": "gold", "#f5f5dc": "cream", "#ff4500": "orange", "#ff6b35": "orange",
    "#ffa500": "orange", "#dc2626": "red", "#e74c3c": "red", "#ff0000": "red",
    "#2c3e50": "navy", "#1f2937": "navy", "#000080": "navy", "#ff6b9d": "pink",
    "#ff69b4": "pink", "#f1c40f": "yellow", "#ffff00": "yellow", "#008000": "green",
}


def _norm_color(c) -> str:
    if not c:
        return ""
    c = str(c).strip().lower()
    if c in _HEX:
        return _HEX[c]
    return c.lstrip("#")


class CurationEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def top_candidates(self, niche: str = None, limit: int = 20) -> list[dict]:
        profiles = {
            p.id: p for p in
            (await self.db.execute(select(NicheProfile))).scalars().all()
        }
        stmt = (
            select(DesignPrompt)
            .where(DesignPrompt.status == DesignStatus.APPROVED.value)
            .order_by(DesignPrompt.created_at.desc())
            .limit(300)
        )
        designs = (await self.db.execute(stmt)).scalars().all()

        out = []
        for d in designs:
            prof = profiles.get(d.niche_id)
            if niche and (not prof or prof.name != niche):
                continue
            score, breakdown = self._fit(d, prof)
            out.append({
                "id": d.id,
                "primary_text": d.primary_text,
                "sub_text": d.sub_text,
                "niche": prof.name if prof else None,
                "font": d.font_suggestion,
                "colors": d.color_scheme,
                "humor": d.humor_type,
                "design_type": d.design_type,
                "listing_title": d.listing_title,
                "trademark_cleared": d.trademark_cleared,
                "fit_score": score,
                "fit": breakdown,
            })
        out.sort(key=lambda x: x["fit_score"], reverse=True)
        return out[:limit]

    def _fit(self, d: DesignPrompt, prof: NicheProfile):
        if not prof:
            return round(float(d.composite_score or 0), 2), {"note": "kein Nischen-Profil"}
        font_ok = 1.0 if d.font_suggestion and d.font_suggestion in (prof.top_font_styles or []) else 0.0
        humor_ok = 1.0 if d.humor_type and d.humor_type in (prof.top_humor_types or []) else 0.0
        dt_ok = 1.0 if d.design_type and d.design_type in (prof.top_design_types or []) else 0.0
        prof_colors = {_norm_color(c) for c in (prof.top_colors or [])}
        des_colors = {_norm_color(c) for c in (d.color_scheme or [])}
        color_ok = 1.0 if (prof_colors & des_colors) else 0.0
        score = round(0.35 * font_ok + 0.25 * color_ok + 0.25 * humor_ok + 0.15 * dt_ok, 2)
        return score, {"font": font_ok, "color": color_ok, "humor": humor_ok, "design_type": dt_ok}
