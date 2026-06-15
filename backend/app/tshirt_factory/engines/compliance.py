"""Compliance Engine - USPTO trademark checking & copyright awareness."""

import logging
import re
from datetime import datetime, timezone, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tshirt_factory.config import tsf_settings
from app.tshirt_factory.models import TrademarkCache

logger = logging.getLogger(__name__)

# Well-known trademarked terms in the T-shirt space (hardcoded safety net).
# Word-boundary matched (see _check_known_trademarks). Curated to avoid generic
# words that legitimately appear in wholesome/humor designs (e.g. "cars", "up",
# "robin", "cowboys", "coco", "soul", "anna"). For franchises with a generic
# name, the multi-word form is listed instead (e.g. "toy story" not "toy").
KNOWN_TRADEMARKS = {
    # ── Disney / Pixar ──────────────────────────────────────────────
    "disney", "disney+", "pixar", "mickey mouse", "minnie mouse", "mickey",
    "minnie", "donald duck", "daisy duck", "goofy", "winnie the pooh",
    "tigger", "eeyore", "frozen", "elsa", "olaf", "lion king", "simba",
    "toy story", "buzz lightyear", "lightning mcqueen", "finding nemo",
    "monsters inc", "the incredibles", "ratatouille", "wall-e", "encanto",
    "moana", "tangled", "rapunzel", "little mermaid", "aladdin", "mulan",
    "pocahontas", "cinderella", "snow white", "dumbo", "bambi", "pinocchio",
    "peter pan", "tinkerbell", "mary poppins", "maleficent", "cruella",
    "lilo & stitch", "stitch", "luca",
    # ── Pokemon ─────────────────────────────────────────────────────
    "pokemon", "pikachu", "charizard", "bulbasaur", "squirtle", "eevee",
    "snorlax", "jigglypuff", "gengar", "mewtwo", "ash ketchum", "pokeball",
    "poke ball",
    # ── Marvel ──────────────────────────────────────────────────────
    "marvel", "marvel studios", "avengers", "hulk", "iron man",
    "captain america", "spider-man", "spiderman", "thor", "loki",
    "black widow", "black panther", "wakanda", "thanos", "deadpool",
    "wolverine", "x-men", "groot", "guardians of the galaxy",
    "doctor strange", "scarlet witch", "hawkeye", "ant-man",
    "captain marvel", "venom", "daredevil", "magneto",
    # ── DC ──────────────────────────────────────────────────────────
    "dc comics", "batman", "superman", "wonder woman", "the flash",
    "aquaman", "green lantern", "harley quinn", "the joker", "gotham",
    "supergirl", "batgirl", "catwoman", "justice league", "shazam",
    # ── Star Wars ───────────────────────────────────────────────────
    "star wars", "yoda", "baby yoda", "grogu", "darth vader",
    "luke skywalker", "skywalker", "jedi", "sith", "millennium falcon",
    "stormtrooper", "chewbacca", "boba fett", "mandalorian", "death star",
    "obi-wan", "han solo", "princess leia", "lightsaber",
    # ── Harry Potter ────────────────────────────────────────────────
    "harry potter", "hogwarts", "gryffindor", "slytherin", "hufflepuff",
    "ravenclaw", "dumbledore", "voldemort", "hermione", "quidditch",
    "muggle",
    # ── Kids / Cartoons / Anime ─────────────────────────────────────
    "spongebob", "patrick star", "bikini bottom", "peppa pig", "paw patrol",
    "bluey", "cocomelon", "ryan's world", "teletubbies", "thomas the tank",
    "thomas & friends", "bob the builder", "dora the explorer", "minions",
    "despicable me", "shrek", "kung fu panda", "rick and morty",
    "the simpsons", "homer simpson", "bart simpson", "family guy",
    "south park", "scooby doo", "tom and jerry", "powerpuff girls",
    "ben 10", "adventure time", "naruto", "dragon ball", "goku", "one piece",
    "demon slayer", "my hero academia", "sailor moon", "hello kitty",
    "sanrio", "sesame street", "barbie", "transformers", "looney tunes",
    # ── Video Games ─────────────────────────────────────────────────
    "nintendo", "nintendo switch", "super mario", "mario", "luigi", "zelda",
    "kirby", "donkey kong", "metroid", "animal crossing", "splatoon",
    "minecraft", "creeper", "fortnite", "roblox", "among us", "sonic",
    "pac-man", "pacman", "tetris", "call of duty", "grand theft auto", "gta",
    "fall guys", "five nights at freddy's", "fnaf",
    "league of legends", "world of warcraft", "overwatch", "playstation",
    "xbox",
    # ── Sports ──────────────────────────────────────────────────────
    "nfl", "nba", "mlb", "nhl", "fifa", "ufc", "wwe", "super bowl",
    "olympics", "olympic", "nascar", "premier league", "champions league",
    "nike", "adidas", "air jordan", "under armour", "puma", "reebok",
    "new balance",
    # ── Tech & Brands ───────────────────────────────────────────────
    "google", "microsoft", "facebook",
    "instagram", "tiktok", "snapchat", "spotify", "netflix", "lego",
    "monster energy", "red bull", "gatorade",
    # ── Auto ────────────────────────────────────────────────────────
    "ferrari", "lamborghini", "porsche", "harley-davidson",
    "harley davidson", "john deere", "caterpillar", "yeti",
    # ── Fashion ─────────────────────────────────────────────────────
    "gucci", "louis vuitton", "chanel", "versace", "prada", "hermes",
    "supreme", "off-white", "balenciaga",
    # ── Catchphrases & Slogans ──────────────────────────────────────
    "just do it", "i'm lovin' it", "think different",
    "impossible is nothing", "finger lickin' good",
    "the happiest place on earth",
    # ── Food & Bev ──────────────────────────────────────────────────
    "coca cola", "coca-cola", "pepsi", "starbucks", "mcdonalds",
}

# Patterns that suggest potential trademark issues
TRADEMARK_PATTERNS = [
    r"\b(?:the\s+)?(?:real\s+)?housewives?\b",
    r"\bkeep\s+calm\s+and\b",  # While generic, often flagged
    r"\bgame\s+of\s+thrones\b",
    r"\bbreaking\s+bad\b",
    r"\bthe\s+office\b",
    r"\bfriends\b(?:\s+tv)?",  # Context-dependent
]


class ComplianceEngine:
    """Checks designs and listings against trademarks and copyright issues."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "TShirtFactory-Compliance/1.0"},
        )

    async def check_term(self, term: str) -> dict:
        """Check a single term against all compliance sources.

        Returns dict with:
            is_safe: bool
            issues: list of found issues
            details: dict with source-specific results
        """
        term_lower = term.lower().strip()
        issues = []

        # 1. Check hardcoded known trademarks (instant)
        known_hit = self._check_known_trademarks(term_lower)
        if known_hit:
            issues.append(known_hit)

        # 2. Check pattern matches
        pattern_hit = self._check_patterns(term_lower)
        if pattern_hit:
            issues.append(pattern_hit)

        # 3. Check USPTO database (with cache)
        uspto_result = await self._check_uspto(term_lower)
        if uspto_result and uspto_result.get("is_trademarked"):
            issues.append({
                "source": "USPTO",
                "term": term,
                "owner": uspto_result.get("owner"),
                "status": uspto_result.get("status"),
                "serial": uspto_result.get("serial_number"),
            })

        return {
            "term": term,
            "is_safe": len(issues) == 0,
            "issues": issues,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    async def check_design_prompt(self, prompt_text: str, primary_text: str = "",
                                   listing_title: str = "", listing_bullets: list[str] = None) -> dict:
        """Full compliance check for a design prompt and its listing."""
        all_text = f"{prompt_text} {primary_text} {listing_title}"
        if listing_bullets:
            all_text += " " + " ".join(listing_bullets)

        # Extract individual words and phrases to check
        terms_to_check = self._extract_checkable_terms(all_text)

        results = []
        all_issues = []

        for term in terms_to_check:
            result = await self.check_term(term)
            results.append(result)
            if not result["is_safe"]:
                all_issues.extend(result["issues"])

        return {
            "is_compliant": len(all_issues) == 0,
            "issues": all_issues,
            "terms_checked": len(terms_to_check),
            "details": results,
        }

    async def check_listing(self, title: str, brand: str, bullet1: str,
                            bullet2: str, description: str, keywords: list[str]) -> dict:
        """Check a full MBA listing for trademark issues."""
        all_text = f"{title} {brand} {bullet1} {bullet2} {description}"
        all_text += " " + " ".join(keywords or [])

        terms = self._extract_checkable_terms(all_text)
        issues = []

        for term in terms:
            result = await self.check_term(term)
            if not result["is_safe"]:
                issues.extend(result["issues"])

        return {
            "is_compliant": len(issues) == 0,
            "issues": issues,
            "flagged_terms": [i.get("term", "") for i in issues],
        }

    def _check_known_trademarks(self, text: str) -> dict | None:
        """Check against hardcoded known trademarks.

        Uses word-boundary matching to avoid false positives (e.g. 'afford'
        must NOT match 'ford', 'man' must NOT match 'iron man'). Multi-word
        marks are caught via the n-gram extraction in _extract_checkable_terms.
        """
        for tm in KNOWN_TRADEMARKS:
            if re.search(rf"\b{re.escape(tm)}\b", text, re.IGNORECASE):
                return {
                    "source": "known_trademarks",
                    "term": tm,
                    "reason": f"'{tm}' is a well-known trademark",
                }
        return None

    def _check_patterns(self, text: str) -> dict | None:
        """Check against known trademark patterns."""
        for pattern in TRADEMARK_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return {
                    "source": "pattern_match",
                    "pattern": pattern,
                    "reason": f"Text matches known trademark pattern",
                }
        return None

    async def _check_uspto(self, term: str) -> dict | None:
        """Check USPTO TSDR API for trademark registration.

        Uses cache to avoid repeated lookups.
        """
        # Check cache first
        cache_cutoff = datetime.now(timezone.utc) - timedelta(days=tsf_settings.TRADEMARK_CACHE_DAYS)
        stmt = select(TrademarkCache).where(
            TrademarkCache.term == term,
            TrademarkCache.checked_at > cache_cutoff,
        )
        result = await self.db.execute(stmt)
        cached = result.scalar_one_or_none()

        if cached:
            return {
                "is_trademarked": cached.is_trademarked,
                "owner": cached.trademark_owner,
                "status": cached.status,
                "serial_number": cached.serial_number,
                "from_cache": True,
            }

        # Query USPTO TESS (Trademark Electronic Search System)
        try:
            uspto_result = await self._query_uspto_api(term)

            # Cache the result
            cache_entry = TrademarkCache(
                term=term,
                is_trademarked=uspto_result.get("is_trademarked", False),
                trademark_owner=uspto_result.get("owner"),
                trademark_class=uspto_result.get("class"),
                serial_number=uspto_result.get("serial_number"),
                status=uspto_result.get("status"),
                details=uspto_result,
            )
            self.db.add(cache_entry)
            await self.db.flush()

            return uspto_result

        except Exception as e:
            logger.warning(f"USPTO API check failed for '{term}': {e}")
            return None

    async def _query_uspto_api(self, term: str) -> dict:
        """Query the USPTO TSDR/TESS API.

        Uses the open TSDR API for trademark status lookups.
        Falls back to keyword-based search via the TESS system.
        """
        # USPTO Open Data API - Trademark search
        # https://developer.uspto.gov/api-catalog
        search_url = "https://tsdrapi.uspto.gov/ts/cd/casestatus/sn/search"

        try:
            # Use the USPTO Trademark Status & Document Retrieval API
            response = await self.http_client.get(
                f"https://developer.uspto.gov/ibd-api/v1/trademark/search",
                params={
                    "searchText": term,
                    "status": "Active",
                    "rows": 5,
                },
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                if results:
                    # Check if any result is a live mark in relevant classes
                    # Nice Classes 25 (clothing) and 035 (advertising/retail)
                    for r in results:
                        nice_classes = str(r.get("internationalClass", ""))
                        status = r.get("status", "")

                        if "25" in nice_classes or "035" in nice_classes:
                            if "live" in status.lower() or "registered" in status.lower():
                                return {
                                    "is_trademarked": True,
                                    "owner": r.get("ownerName", "Unknown"),
                                    "class": nice_classes,
                                    "serial_number": r.get("serialNumber"),
                                    "status": status,
                                    "mark": r.get("wordMark", term),
                                }

                return {"is_trademarked": False}

            # If API returns non-200, treat as unknown (safe side)
            logger.warning(f"USPTO API returned {response.status_code} for '{term}'")
            return {"is_trademarked": False, "api_error": True}

        except httpx.RequestError as e:
            logger.error(f"USPTO API request failed: {e}")
            raise

    def _extract_checkable_terms(self, text: str) -> list[str]:
        """Extract meaningful terms and phrases from text to check."""
        terms = set()

        # Clean text
        text = re.sub(r'[^\w\s\'-]', ' ', text.lower())

        # Add individual words (3+ chars)
        words = text.split()
        for word in words:
            word = word.strip("'-")
            if len(word) >= 3:
                terms.add(word)

        # Add 2-word phrases
        for i in range(len(words) - 1):
            phrase = f"{words[i]} {words[i+1]}"
            terms.add(phrase.strip("'-"))

        # Add 3-word phrases
        for i in range(len(words) - 2):
            phrase = f"{words[i]} {words[i+1]} {words[i+2]}"
            terms.add(phrase.strip("'-"))

        # Remove common stop words as standalone terms
        stop_words = {"the", "and", "for", "are", "but", "not", "you", "all",
                      "can", "had", "her", "was", "one", "our", "out", "has",
                      "this", "that", "with", "from", "they", "been", "have"}
        terms -= stop_words

        return list(terms)

    async def close(self):
        await self.http_client.aclose()
