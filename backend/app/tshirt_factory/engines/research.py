"""Research Engine - Collects winning design data from multiple sources."""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.tshirt_factory.config import tsf_settings
from app.tshirt_factory.models import ResearchItem, TrendData, NicheProfile

logger = logging.getLogger(__name__)

NICHES_FILE = Path(__file__).parent.parent / "data" / "niches.json"


class ResearchEngine:
    """Collects and processes market research data for T-shirt designs."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
            follow_redirects=True,
        )

    # ─── Google Trends ────────────────────────────────────────────

    async def collect_google_trends(self, keywords: list[str] = None) -> list[dict]:
        """Collect Google Trends data for niche keywords.

        Uses pytrends library for Google Trends API access.
        """
        try:
            from pytrends.request import TrendReq
        except ImportError:
            logger.warning("pytrends not installed. Run: pip install pytrends")
            return []

        if not keywords:
            keywords = self._get_niche_keywords()

        results = []
        pytrends = TrendReq(hl=tsf_settings.GOOGLE_TRENDS_LANGUAGE)

        # Process in batches of 5 (Google Trends limit)
        for i in range(0, len(keywords), 5):
            batch = keywords[i:i + 5]
            try:
                pytrends.build_payload(
                    batch,
                    cat=0,
                    timeframe=f"today {tsf_settings.TREND_LOOKBACK_DAYS}-d",
                    geo=tsf_settings.GOOGLE_TRENDS_REGION,
                )

                # Interest over time
                interest_df = pytrends.interest_over_time()
                if interest_df is not None and not interest_df.empty:
                    for kw in batch:
                        if kw in interest_df.columns:
                            recent_interest = float(interest_df[kw].tail(7).mean())
                            older_interest = float(interest_df[kw].head(7).mean())

                            if older_interest > 0:
                                change = (recent_interest - older_interest) / older_interest
                                if change > 0.1:
                                    direction = "rising"
                                elif change < -0.1:
                                    direction = "declining"
                                else:
                                    direction = "stable"
                            else:
                                direction = "stable"

                            trend_entry = TrendData(
                                keyword=kw,
                                source="google_trends",
                                interest_score=recent_interest,
                                trend_direction=direction,
                                related_keywords=[],
                            )
                            self.db.add(trend_entry)
                            results.append({
                                "keyword": kw,
                                "interest": recent_interest,
                                "direction": direction,
                            })

                # Related queries
                try:
                    related = pytrends.related_queries()
                    for kw in batch:
                        if kw in related and related[kw].get("rising") is not None:
                            rising = related[kw]["rising"]
                            if rising is not None and not rising.empty:
                                related_kws = rising["query"].tolist()[:10]
                                # Update the trend entry with related keywords
                                for r in results:
                                    if r["keyword"] == kw:
                                        r["related"] = related_kws
                except Exception as e:
                    logger.debug(f"Could not fetch related queries: {e}")

            except Exception as e:
                logger.warning(f"Google Trends batch failed for {batch}: {e}")

        await self.db.flush()
        logger.info(f"Collected {len(results)} Google Trends data points")
        return results

    # ─── Amazon Bestseller Research ───────────────────────────────

    async def collect_amazon_bestsellers(self, category: str = "fashion") -> list[dict]:
        """Research Amazon T-shirt bestsellers from public bestseller pages.

        Parses publicly available bestseller list pages.
        """
        results = []
        marketplace = tsf_settings.AMAZON_MARKETPLACE
        base_url = f"https://www.amazon.{marketplace}"

        # Amazon T-shirt bestseller categories
        urls = [
            f"{base_url}/gp/bestsellers/fashion/9056921011",  # Novelty T-Shirts
            f"{base_url}/gp/bestsellers/fashion/15690icons011",  # Graphic Tees
        ]

        for url in urls:
            try:
                response = await self.http_client.get(url)
                if response.status_code != 200:
                    logger.warning(f"Amazon returned {response.status_code} for {url}")
                    continue

                items = self._parse_amazon_bestseller_page(response.text, url)
                for item in items[:tsf_settings.MAX_RESEARCH_ITEMS_PER_RUN]:
                    research_item = ResearchItem(
                        source="amazon_bestseller",
                        external_id=item.get("asin"),
                        title=item.get("title", ""),
                        bsr=item.get("rank"),
                        price=item.get("price"),
                        review_count=item.get("reviews"),
                        rating=item.get("rating"),
                        url=item.get("url"),
                        image_url=item.get("image"),
                        marketplace=marketplace,
                    )
                    self.db.add(research_item)
                    results.append(item)

            except Exception as e:
                logger.warning(f"Amazon bestseller scrape failed: {e}")

        await self.db.flush()
        logger.info(f"Collected {len(results)} Amazon bestseller items")
        return results

    def _parse_amazon_bestseller_page(self, html: str, source_url: str) -> list[dict]:
        """Parse Amazon bestseller page HTML."""
        soup = BeautifulSoup(html, "html.parser")
        items = []

        # Amazon bestseller list items
        product_items = soup.select("[data-asin]")

        for idx, item in enumerate(product_items):
            try:
                asin = item.get("data-asin", "")
                if not asin:
                    continue

                title_el = item.select_one("span.zg-text-center-align, .p13n-sc-truncate, ._cDEzb_p13n-sc-css-line-clamp-3_g3dy1")
                title = title_el.get_text(strip=True) if title_el else ""

                price_el = item.select_one(".p13n-sc-price, ._cDEzb_p13n-sc-price_3mJ9Z")
                price_text = price_el.get_text(strip=True) if price_el else ""
                price = self._extract_price(price_text)

                rating_el = item.select_one(".a-icon-alt")
                rating_text = rating_el.get_text(strip=True) if rating_el else ""
                rating = self._extract_rating(rating_text)

                review_el = item.select_one(".a-size-small .a-link-normal")
                review_text = review_el.get_text(strip=True) if review_el else "0"
                reviews = int(re.sub(r"[^\d]", "", review_text) or 0)

                img_el = item.select_one("img")
                image_url = img_el.get("src", "") if img_el else ""

                items.append({
                    "asin": asin,
                    "title": title,
                    "rank": idx + 1,
                    "price": price,
                    "rating": rating,
                    "reviews": reviews,
                    "image": image_url,
                    "url": f"https://www.amazon.com/dp/{asin}",
                })
            except Exception as e:
                logger.debug(f"Failed to parse product item: {e}")

        return items

    # ─── Social/Reddit Trend Detection ────────────────────────────

    async def collect_social_trends(self) -> list[dict]:
        """Collect trending topics from public social sources.

        Uses Reddit's public JSON endpoints (no auth needed).
        """
        results = []
        subreddits = [
            "funny", "memes", "shirts", "tshirtdesign",
            "merch", "AmazonMerch", "entrepeneur",
        ]

        for subreddit in subreddits:
            try:
                url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=25"
                response = await self.http_client.get(
                    url,
                    headers={"User-Agent": "TShirtFactory/1.0"},
                )

                if response.status_code != 200:
                    continue

                data = response.json()
                posts = data.get("data", {}).get("children", [])

                for post in posts:
                    post_data = post.get("data", {})
                    title = post_data.get("title", "")
                    score = post_data.get("score", 0)
                    num_comments = post_data.get("num_comments", 0)

                    if score > 100:  # Only high-engagement posts
                        trend = TrendData(
                            keyword=title[:200],
                            source=f"reddit_r_{subreddit}",
                            interest_score=min(score / 100, 100),
                            trend_direction="rising" if score > 500 else "stable",
                            related_keywords=self._extract_keywords_from_title(title),
                        )
                        self.db.add(trend)
                        results.append({
                            "title": title,
                            "source": f"r/{subreddit}",
                            "score": score,
                            "comments": num_comments,
                        })

            except Exception as e:
                logger.debug(f"Reddit scrape failed for r/{subreddit}: {e}")

        await self.db.flush()
        logger.info(f"Collected {len(results)} social trend items")
        return results

    # ─── Etsy Trending ────────────────────────────────────────────

    async def collect_etsy_trends(self) -> list[dict]:
        """Collect trending T-shirt designs from Etsy public pages."""
        results = []
        search_terms = ["funny tshirt", "graphic tee trending", "novelty shirt"]

        for term in search_terms:
            try:
                url = f"https://www.etsy.com/search?q={term.replace(' ', '+')}&ref=search_bar"
                response = await self.http_client.get(url)

                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                listings = soup.select("[data-listing-id]")

                for listing in listings[:10]:
                    try:
                        listing_id = listing.get("data-listing-id", "")
                        title_el = listing.select_one("h3, .v2-listing-card__title")
                        title = title_el.get_text(strip=True) if title_el else ""

                        price_el = listing.select_one(".currency-value, .lc-price")
                        price_text = price_el.get_text(strip=True) if price_el else ""
                        price = self._extract_price(price_text)

                        if title:
                            item = ResearchItem(
                                source="etsy",
                                external_id=listing_id,
                                title=title,
                                price=price,
                                marketplace="etsy",
                            )
                            self.db.add(item)
                            results.append({"title": title, "price": price, "source": "etsy"})

                    except Exception as e:
                        logger.debug(f"Failed to parse Etsy listing: {e}")

            except Exception as e:
                logger.debug(f"Etsy search failed for '{term}': {e}")

        await self.db.flush()
        logger.info(f"Collected {len(results)} Etsy trend items")
        return results

    # ─── Full Research Run ────────────────────────────────────────

    async def run_full_research(self) -> dict:
        """Execute a complete research cycle across all sources."""
        logger.info("Starting full research cycle...")

        trends = await self.collect_google_trends()
        bestsellers = await self.collect_amazon_bestsellers()
        social = await self.collect_social_trends()
        etsy = await self.collect_etsy_trends()

        await self.db.commit()

        summary = {
            "google_trends": len(trends),
            "amazon_bestsellers": len(bestsellers),
            "social_trends": len(social),
            "etsy_trends": len(etsy),
            "total": len(trends) + len(bestsellers) + len(social) + len(etsy),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"Research cycle complete: {summary['total']} items collected")
        return summary

    # ─── Helper Methods ───────────────────────────────────────────

    def _get_niche_keywords(self) -> list[str]:
        """Load niche keywords from config."""
        try:
            with open(NICHES_FILE) as f:
                data = json.load(f)
            keywords = []
            for niche in data.get("evergreen_niches", []):
                keywords.extend(niche.get("keywords", [])[:3])
            # Add trending categories
            keywords.extend(data.get("trending_categories", []))
            return keywords[:50]  # Limit to avoid rate limiting
        except Exception:
            return ["funny shirt", "dad joke", "nurse humor", "dog lover", "cat mom"]

    def _extract_price(self, text: str) -> float | None:
        match = re.search(r"[\d]+[.,]?\d*", text.replace(",", ""))
        return float(match.group()) if match else None

    def _extract_rating(self, text: str) -> float | None:
        match = re.search(r"([\d.]+)\s*out\s*of", text)
        return float(match.group(1)) if match else None

    def _extract_keywords_from_title(self, title: str) -> list[str]:
        """Extract potential keywords from a post/product title."""
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "shall", "can", "need",
            "this", "that", "these", "those", "i", "you", "he", "she",
            "it", "we", "they", "me", "him", "her", "us", "them",
            "my", "your", "his", "its", "our", "their", "what", "which",
            "who", "when", "where", "why", "how", "not", "no", "nor",
            "but", "and", "or", "if", "then", "else", "for", "from",
            "with", "in", "on", "at", "to", "of", "by", "about", "just",
            "so", "very", "too", "also", "only", "own", "same", "than",
        }
        words = re.findall(r'\b[a-zA-Z]{3,}\b', title.lower())
        return [w for w in words if w not in stop_words][:10]

    async def close(self):
        await self.http_client.aclose()
