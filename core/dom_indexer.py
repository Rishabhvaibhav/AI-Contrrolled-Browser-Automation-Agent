import json
import logging
from typing import List, Dict, Any, Optional
from playwright.async_api import Page

logger = logging.getLogger("ShadowBrowser.DOMIndexer")

# JavaScript to scan DOM, label interactive elements with visual badges, and extract metadata
INDEXER_SCRIPT = """
(() => {
    // Clean up existing badges
    document.querySelectorAll('.shadow-browser-badge').forEach(el => el.remove());

    const isVisible = (elem) => {
        if (!elem) return false;
        const style = window.getComputedStyle(elem);
        if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) {
            return false;
        }
        const rect = elem.getBoundingClientRect();
        return rect.width > 2 && rect.height > 2;
    };

    const selector = [
        'a[href]',
        'button',
        'input',
        'textarea',
        'select',
        '[role="button"]',
        '[role="link"]',
        '[role="checkbox"]',
        '[role="radio"]',
        '[role="tab"]',
        '[role="combobox"]',
        '[role="menuitem"]',
        '[onclick]',
        '[tabindex]:not([tabindex="-1"])',
        'label'
    ].join(',');

    const rawElements = Array.from(document.querySelectorAll(selector));
    const items = [];
    let counter = 1;

    for (const el of rawElements) {
        if (!isVisible(el)) continue;

        const rect = el.getBoundingClientRect();
        
        // Element identifier
        const tag = el.tagName.toLowerCase();
        const type = el.getAttribute('type') || '';
        const role = el.getAttribute('role') || '';
        const placeholder = el.getAttribute('placeholder') || '';
        const ariaLabel = el.getAttribute('aria-label') || '';
        const name = el.getAttribute('name') || '';
        const id = el.id || '';
        const href = el.getAttribute('href') || '';
        const value = el.value !== undefined ? String(el.value) : '';
        
        let text = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ');
        if (text.length > 80) text = text.substring(0, 77) + '...';

        const index = counter++;
        el.setAttribute('data-shadow-index', index);

        // Add visual badge
        const badge = document.createElement('div');
        badge.className = 'shadow-browser-badge';
        badge.textContent = index;
        badge.style.position = 'fixed';
        badge.style.left = `${Math.max(0, rect.left)}px`;
        badge.style.top = `${Math.max(0, rect.top)}px`;
        badge.style.backgroundColor = '#f59e0b';
        badge.style.color = '#000000';
        badge.style.fontSize = '11px';
        badge.style.fontWeight = 'bold';
        badge.style.padding = '1px 4px';
        badge.style.borderRadius = '3px';
        badge.style.zIndex = '2147483647';
        badge.style.pointerEvents = 'none';
        badge.style.boxShadow = '0 1px 3px rgba(0,0,0,0.5)';
        badge.style.border = '1px solid #ffffff';
        document.body.appendChild(badge);

        items.push({
            index: index,
            tag: tag,
            type: type,
            role: role,
            text: text,
            placeholder: placeholder,
            ariaLabel: ariaLabel,
            name: name,
            id: id,
            href: href,
            value: value,
            bounds: {
                x: Math.round(rect.x),
                y: Math.round(rect.y),
                width: Math.round(rect.width),
                height: Math.round(rect.height)
            }
        });
    }

    return {
        url: window.location.href,
        title: document.title,
        interactiveElements: items
    };
})();
"""

CLEANUP_BADGES_SCRIPT = """
(() => {
    document.querySelectorAll('.shadow-browser-badge').forEach(el => el.remove());
})();
"""

class DOMIndexer:
    """
    Extracts structured interactive DOM elements and page text, assigning numbered
    badges for high-precision AI decision making.
    """

    @classmethod
    async def get_interactive_state(cls, page: Page) -> Dict[str, Any]:
        """
        Scans active page and returns structured elements with numerical indexes.
        """
        try:
            state = await page.evaluate(INDEXER_SCRIPT)
            return state
        except Exception as e:
            logger.error(f"Failed to scan DOM interactive elements: {e}")
            return {
                "url": page.url,
                "title": await page.title(),
                "interactiveElements": []
            }

    @classmethod
    async def remove_badges(cls, page: Page):
        """Removes the injected visual badges from the page."""
        try:
            await page.evaluate(CLEANUP_BADGES_SCRIPT)
        except Exception:
            pass

    @classmethod
    def format_elements_for_llm(cls, elements: List[Dict[str, Any]]) -> str:
        """
        Converts the list of interactive elements into a clean text representation for the LLM.
        """
        lines = []
        for el in elements:
            idx = el["index"]
            tag = el["tag"]
            parts = [f"[{idx}] <{tag}"]

            if el.get("type"):
                parts.append(f"type='{el['type']}'")
            if el.get("placeholder"):
                parts.append(f"placeholder='{el['placeholder']}'")
            if el.get("ariaLabel"):
                parts.append(f"aria-label='{el['ariaLabel']}'")
            if el.get("name"):
                parts.append(f"name='{el['name']}'")
            if el.get("value") and el["type"] not in ("password", "hidden"):
                parts.append(f"value='{el['value']}'")
            
            parts.append(">")

            if el.get("text"):
                parts.append(f"\"{el['text']}\"")
            elif el.get("href"):
                parts.append(f"href='{el['href'][:40]}'")

            lines.append(" ".join(parts))

        return "\n".join(lines) if lines else "(No interactive elements detected on page)"

    @classmethod
    async def get_page_markdown(cls, page: Page) -> str:
        """
        Extracts clean textual snapshot of the page (similar to Obscura dump).
        """
        extract_script = """
        (() => {
            const body = document.body;
            if (!body) return "";
            
            // Clone body to avoid mutating actual page
            const clone = body.cloneNode(true);
            const removeSelectors = ['script', 'style', 'noscript', 'svg', 'iframe', '.shadow-browser-badge'];
            removeSelectors.forEach(sel => {
                clone.querySelectorAll(sel).forEach(el => el.remove());
            });

            return clone.innerText.replace(/\\n{3,}/g, '\\n\\n').trim();
        })();
        """
        try:
            text = await page.evaluate(extract_script)
            return text
        except Exception as e:
            logger.warning(f"Failed to extract page text: {e}")
            return ""

    @classmethod
    async def get_element_by_index(cls, page: Page, index: int):
        """Returns the Playwright locator for an indexed element."""
        selector = f"[data-shadow-index='{index}']"
        locator = page.locator(selector).first
        if await locator.count() > 0:
            return locator
        return None
