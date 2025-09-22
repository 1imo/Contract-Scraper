from typing import List, Tuple, Dict, Set
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from ...domain.models import Listing
import os

BASE_URL = os.getenv("BASE_URL", "https://www.emarketplace.state.pa.us/Procurement.aspx")
HEADERS = {"User-Agent": os.getenv("USER_AGENT", "contract-scraper/1.0")}
GRID_ID = "ctl00$MainBody$gdvSearchData"
GRID_ID_HTML = "ctl00_MainBody_gdvSearchData"


class EMarketplaceScraper:
    def _parse_listings_from_html(self, html: str) -> List[Listing]:
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", id=GRID_ID_HTML)
        if not table:
            print("[scraper] listings table not found")
            return []
        listings: List[Listing] = []
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 6:
                continue
            id_text = cells[0].get_text(strip=True)
            title_cell = cells[1]
            link = title_cell.find("a")
            if not link:
                continue
            title = link.get_text(strip=True)
            detail_href = link.get("href")
            # Skip pager or invalid javascript links
            if not detail_href or detail_href.startswith("javascript:"):
                continue
            if "Procurement_Details.aspx?id=" not in detail_href:
                continue
            detail_url = urljoin(BASE_URL, detail_href)
            agency = cells[2].get_text(strip=True)
            category = cells[3].get_text(strip=True)
            status = cells[5].get_text(strip=True)
            listings.append(Listing(id=id_text, title=title, agency=agency, category=category, status=status, detail_url=detail_url))
        return listings

    def _extract_form_fields(self, html: str) -> Dict[str, str]:
        soup = BeautifulSoup(html, "lxml")
        fields: Dict[str, str] = {}
        for name in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION", "__VIEWSTATEENCRYPTED"]:
            el = soup.find("input", attrs={"name": name})
            if el and el.has_attr("value"):
                fields[name] = el.get("value", "")
        # include all hidden inputs to be safe
        for inp in soup.find_all("input", attrs={"type": "hidden"}):
            name = inp.get("name")
            if name and name not in fields:
                fields[name] = inp.get("value", "")
        return fields

    def _find_pager_pages(self, html: str) -> Tuple[int, Set[int]]:
        soup = BeautifulSoup(html, "lxml")
        pages: Set[int] = set()
        current = 1
        pager_row = soup.find("tr", class_="GridPager")
        if not pager_row:
            return current, pages
        for td in pager_row.find_all("td"):
            # current page as <span>
            span = td.find("span")
            if span and span.get_text(strip=True).isdigit():
                current = int(span.get_text(strip=True))
            # linked pages
            for a in td.find_all("a"):
                text = a.get_text(strip=True)
                if text.isdigit():
                    pages.add(int(text))
        return current, pages

    def _postback_page(self, session: requests.Session, html: str, page: int) -> str:
        form_fields = self._extract_form_fields(html)
        data = {
            "__EVENTTARGET": GRID_ID,
            "__EVENTARGUMENT": f"Page${page}",
        }
        data.update(form_fields)
        print(f"[scraper] POST page {page}")
        resp = session.post(BASE_URL, data=data, headers=HEADERS, timeout=30)
        print(f"[scraper] Page {page} status: {resp.status_code}")
        resp.raise_for_status()
        return resp.text

    def fetch_it_listings(self) -> List[Listing]:
        session = requests.Session()
        print(f"[scraper] GET {BASE_URL}")
        resp = session.get(BASE_URL, headers=HEADERS, timeout=30)
        print(f"[scraper] Status: {resp.status_code}")
        resp.raise_for_status()
        first_html = resp.text

        all_listings: List[Listing] = []
        page_current, page_links = self._find_pager_pages(first_html)
        print(f"[scraper] Current page: {page_current}, links found: {sorted(page_links) if page_links else 'none'}")

        # parse current page
        current_list = self._parse_listings_from_html(first_html)
        print(f"[scraper] Parsed {len(current_list)} IT listings on page {page_current}")
        all_listings.extend(current_list)

        # iterate all other linked pages
        visited_pages: Set[int] = {page_current}
        for p in sorted(page_links):
            if p in visited_pages:
                continue
            html = self._postback_page(session, first_html, p)
            page_current2, page_links2 = self._find_pager_pages(html)
            listings_p = self._parse_listings_from_html(html)
            print(f"[scraper] Parsed {len(listings_p)} IT listings on page {p}")
            all_listings.extend(listings_p)
            visited_pages.add(p)
            # try to discover further pages if pager shifts (e.g., when there are many pages)
            for np in page_links2:
                if np not in visited_pages:
                    html2 = self._postback_page(session, html, np)
                    listings_np = self._parse_listings_from_html(html2)
                    print(f"[scraper] Parsed {len(listings_np)} IT listings on page {np}")
                    all_listings.extend(listings_np)
                    visited_pages.add(np)
                    html = html2

        # de-duplicate by id
        by_id: Dict[str, Listing] = {l.id: l for l in all_listings}
        print(f"[scraper] Total unique IT listings: {len(by_id)}")
        return list(by_id.values())

    def enrich_description(self, listing: Listing) -> Listing:
        try:
            print(f"[scraper] Enrich {listing.id} -> {listing.detail_url}")
            resp = requests.get(listing.detail_url, headers=HEADERS, timeout=30)
            print(f"[scraper] Detail status: {resp.status_code}")
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            main = soup.find(id="MainBody") or soup
            paragraphs = main.find_all(["p", "div", "td"])[:80]
            text_parts = []
            seen = set()
            for p in paragraphs:
                txt = p.get_text(" ", strip=True)
                if not txt or len(txt) <= 40:
                    continue
                # de-duplicate exact repeats and already included substrings
                if txt in seen:
                    continue
                if any(txt in prev or prev in txt for prev in text_parts):
                    continue
                seen.add(txt)
                text_parts.append(txt)
            description = "\n".join(text_parts) if text_parts else None
            return Listing(
                id=listing.id,
                title=listing.title,
                agency=listing.agency,
                category=listing.category,
                status=listing.status,
                detail_url=listing.detail_url,
                description=description,
            )
        except Exception as e:
            print(f"[scraper] Enrich error for {listing.id}: {e}")
            return listing
