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
        def graded(val, ranked):
            # 1.0 fuer den #1-Gewinner, abgestuft nach Rang, 0 wenn nicht in Liste
            ranked = ranked or []
            if not val or val not in ranked:
                return 0.0
            i = ranked.index(val)
            return 1.0 if i == 0 else 0.7 if i <= 2 else 0.4

        font_ok = graded(d.font_suggestion, prof.top_font_styles)
        humor_ok = graded(d.humor_type, prof.top_humor_types)
        dt_ok = graded(d.design_type, prof.top_design_types)
        prof_colors = [_norm_color(c) for c in (prof.top_colors or [])]
        des_colors = {_norm_color(c) for c in (d.color_scheme or [])}
        # Farb-Score: Anteil der Design-Farben, die zu den Top-Gewinnerfarben gehoeren
        if des_colors:
            hits = sum(1 for c in des_colors if c in prof_colors)
            color_ok = round(hits / len(des_colors), 2)
        else:
            color_ok = 0.0
        score = round(0.35 * font_ok + 0.25 * color_ok + 0.25 * humor_ok + 0.15 * dt_ok, 2)
        return score, {"font": font_ok, "color": color_ok, "humor": humor_ok, "design_type": dt_ok}

    async def find_gaps(self, niche: str = None, limit: int = 30) -> list[dict]:
        """Gewinnermuster einer Nische, die deine eigenen Designs noch NICHT
        abdecken -> gezielte 'mach davon mehr'-Empfehlungen."""
        profs = (await self.db.execute(select(NicheProfile))).scalars().all()
        if niche:
            profs = [p for p in profs if p.name == niche]

        recs = []
        for p in profs:
            designs = (await self.db.execute(
                select(DesignPrompt).where(
                    DesignPrompt.niche_id == p.id,
                    DesignPrompt.status == DesignStatus.APPROVED.value,
                )
            )).scalars().all()
            n = len(designs)
            fonts, humors, dtypes, colors, kw = set(), set(), set(), set(), set()
            for d in designs:
                if d.font_suggestion:
                    fonts.add(d.font_suggestion)
                if d.humor_type:
                    humors.add(d.humor_type)
                if d.design_type:
                    dtypes.add(d.design_type)
                for c in (d.color_scheme or []):
                    colors.add(_norm_color(c))
                for k in (d.listing_keywords or []):
                    kw.add(str(k).lower())
                for w in (d.primary_text or "").lower().split():
                    kw.add(w)

            def add(dim, missing, action):
                recs.append({"niche": p.name, "dimension": dim, "missing": missing,
                             "have_designs": n, "win_rate": round((p.win_rate or 0) * 100, 1),
                             "action": action})

            for f in (p.top_font_styles or [])[:3]:
                if f not in fonts:
                    add("font", f, f"Design im Gewinner-Font '{f}' erstellen")
            for h in (p.top_humor_types or [])[:3]:
                if h not in humors:
                    add("humor", h, f"Humor-Typ '{h}' abdecken")
            for t in (p.top_design_types or [])[:3]:
                if t not in dtypes:
                    add("design_type", t, f"Design-Typ '{t}' abdecken")
            for c in [_norm_color(x) for x in (p.top_colors or [])[:4]]:
                if c and c not in colors:
                    add("color", c, f"Gewinnerfarbe '{c}' nutzen")
            for k in (p.top_keywords or [])[:8]:
                kl = str(k).lower().strip()
                if kl and kl not in kw and not any(kl in x for x in kw):
                    add("keyword", k, f"Keyword '{k}' bespielen")

        # Nischen, in denen du schon Designs hast (validiert), zuerst
        recs.sort(key=lambda r: -r["have_designs"])
        return recs[:limit]
