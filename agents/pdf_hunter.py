import os
import re
import urllib.parse
import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx
from pypdf import PdfReader

from core.browser_engine import BrowserEngine
from core.dom_indexer import DOMIndexer
from core.human_emulator import HumanEmulator
from core.config import DOWNLOADS_DIR
from agents.base_agent import BaseBrowserAgent

logger = logging.getLogger("ShadowBrowser.PDFHunter")

class PDFHunter(BaseBrowserAgent):
    """
    Autonomous Internet PDF Discovery & Download Engine.
    Finds academic papers, technical documentation, whitepapers, reports,
    and books across the web, validates them, and extracts metadata.
    """

    def __init__(
        self,
        engine: BrowserEngine,
        downloads_dir: Path = DOWNLOADS_DIR,
    ):
        super().__init__(engine)
        self.downloads_dir = downloads_dir
        self.downloads_dir.mkdir(parents=True, exist_ok=True)

    async def search_and_download(
        self,
        query: str,
        max_results: int = 3,
        search_engine: str = "duckduckgo",
    ) -> List[Dict[str, Any]]:
        """
        Executes web search for query, locates high-probability PDF candidates,
        downloads, verifies, and analyzes each PDF.
        """
        logger.info(f"Initiating PDF Hunt for: '{query}' (Target limit: {max_results})")
        downloaded_files: List[Dict[str, Any]] = []

        # 1. Format search queries
        clean_query = query.strip()
        encoded = urllib.parse.quote_plus(f"{clean_query} filetype:pdf")
        
        search_urls = {
            "duckduckgo": f"https://duckduckgo.com/html/?q={encoded}",
            "google": f"https://www.google.com/search?q={encoded}",
            "bing": f"https://www.bing.com/search?q={encoded}",
        }

        target_search_url = search_urls.get(search_engine, search_urls["duckduckgo"])

        # 2. Navigate to search engine
        await self.engine.navigate(target_search_url)
        await asyncio.sleep(2.0)

        # 3. Extract candidate links
        candidate_links = await self._extract_pdf_candidate_links()
        logger.info(f"Discovered {len(candidate_links)} PDF candidate links from search engine.")

        # 4. Download and validate each candidate
        for idx, item in enumerate(candidate_links[: max_results * 2]):
            if len(downloaded_files) >= max_results:
                break

            url = item["url"]
            title = item.get("title", f"document_{idx+1}")
            logger.info(f"Evaluating candidate [{idx+1}]: {title} ({url})")

            # Check if direct PDF download or landing page
            result = await self._acquire_pdf(url, title)
            if result and result.get("valid_pdf"):
                downloaded_files.append(result)
                logger.info(f"✅ Downloaded & Verified: {result['filename']} ({result['pages']} pages)")

        return downloaded_files

    async def _extract_pdf_candidate_links(self) -> List[Dict[str, str]]:
        """Scans the search result page for PDF and document download links."""
        extract_script = """
        (() => {
            const links = Array.from(document.querySelectorAll('a[href]'));
            const results = [];
            const seen = new Set();

            for (const a of links) {
                let href = a.getAttribute('href') || '';
                // Handle duckduckgo redirect wrapper
                if (href.includes('uddg=')) {
                    const match = href.match(/uddg=([^&]+)/);
                    if (match) href = decodeURIComponent(match[1]);
                }

                if (!href.startsWith('http')) continue;
                if (seen.has(href)) continue;

                const text = (a.innerText || a.textContent || '').trim();
                const lowerHref = href.toLowerCase();
                const isPdf = lowerHref.endsWith('.pdf') || lowerHref.includes('.pdf?') || lowerHref.includes('/pdf/') || text.toLowerCase().includes('[pdf]');

                if (isPdf || text.length > 5) {
                    seen.add(href);
                    results.push({
                        url: href,
                        title: text || href.split('/').pop().replace('.pdf', ''),
                        isDirectPdf: lowerHref.endsWith('.pdf') || lowerHref.includes('/pdf/')
                    });
                }
            }

            // Prioritize direct PDF links first
            results.sort((a, b) => (b.isDirectPdf ? 1 : 0) - (a.isDirectPdf ? 1 : 0));
            return results;
        })();
        """
        try:
            links = await self.page.evaluate(extract_script)
            return links
        except Exception as e:
            logger.error(f"Error extracting search links: {e}")
            return []

    async def _acquire_pdf(self, url: str, suggested_title: str) -> Optional[Dict[str, Any]]:
        """
        Downloads a PDF via HTTP client or page navigation, and verifies PDF integrity.
        """
        clean_title = re.sub(r'[^a-zA-Z0-9_\- ]', '', suggested_title).strip()[:50]
        if not clean_title:
            clean_title = "downloaded_document"
        filename = f"{clean_title}_{int(asyncio.get_event_loop().time())}.pdf"
        target_path = self.downloads_dir / filename

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "application/pdf,application/xhtml+xml,text/html;q=0.9,*/*;q=0.8",
        }

        # Try fast direct download first
        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers=headers) as client:
                res = await client.get(url)
                content = res.content

                # Check magic bytes '%PDF-'
                if content.startswith(b"%PDF-"):
                    with open(target_path, "wb") as f:
                        f.write(content)
                    return self._inspect_pdf_file(target_path, url, suggested_title)
        except Exception as e:
            logger.debug(f"Direct HTTP fetch failed for {url}: {e}")

        # If direct fetch did not yield a PDF (e.g., Cloudflare gate or arXiv abstract page),
        # navigate via the real stealth browser!
        try:
            logger.info(f"Navigating to landing page via browser: {url}")
            await self.engine.navigate(url)
            await asyncio.sleep(2.0)

            # Look for "Download PDF" or direct PDF link on the landing page
            pdf_link_loc = self.page.locator(
                "a:has-text('Download PDF'), a:has-text('PDF'), a[href*='.pdf'], a[href*='/pdf/']"
            ).first

            if await pdf_link_loc.count() > 0:
                download_href = await pdf_link_loc.get_attribute("href")
                if download_href:
                    if not download_href.startswith("http"):
                        download_href = urllib.parse.urljoin(self.page.url, download_href)

                    # Trigger browser download or fetch
                    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers=headers) as client:
                        res = await client.get(download_href)
                        if res.content.startswith(b"%PDF-"):
                            with open(target_path, "wb") as f:
                                f.write(res.content)
                            return self._inspect_pdf_file(target_path, download_href, suggested_title)
        except Exception as e:
            logger.warning(f"Browser acquisition failed for {url}: {e}")

        return None

    def _inspect_pdf_file(self, file_path: Path, source_url: str, title: str) -> Dict[str, Any]:
        """
        Uses pypdf to inspect and validate the PDF file, extracting page count and metadata.
        """
        try:
            reader = PdfReader(str(file_path))
            num_pages = len(reader.pages)
            meta = reader.metadata or {}

            # Extract sample text from first page
            first_page_text = ""
            if num_pages > 0:
                first_page_text = (reader.pages[0].extract_text() or "")[:400].replace("\n", " ").strip()

            file_size_kb = round(os.path.getsize(file_path) / 1024, 2)

            return {
                "valid_pdf": True,
                "filename": file_path.name,
                "local_path": str(file_path.resolve()),
                "file_size_kb": file_size_kb,
                "pages": num_pages,
                "title": str(meta.get("/Title", title)),
                "author": str(meta.get("/Author", "Unknown")),
                "source_url": source_url,
                "preview_text": first_page_text,
            }
        except Exception as e:
            logger.error(f"Error parsing PDF file {file_path}: {e}")
            return {
                "valid_pdf": False,
                "filename": file_path.name,
                "error": str(e),
                "source_url": source_url,
            }
