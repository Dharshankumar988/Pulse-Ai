"""Lightweight web-search helper using DuckDuckGo Instant Answer API.

Returns a concise text snippet that the LLM can incorporate into its answer.
Zero external dependencies beyond httpx (already in requirements).
"""

from __future__ import annotations

import re
import httpx


async def web_search(query: str, max_snippets: int = 3) -> str:
    """Search the web for *query* and return a short summary string.

    Uses the DuckDuckGo Instant Answer JSON API (no API key required).
    Falls back gracefully to an empty string on any failure so callers
    never need to handle exceptions.
    """
    if not query or not query.strip():
        return ""

    try:
        cleaned = re.sub(r"[^\w\s\-]", " ", query)
        cleaned = " ".join(cleaned.split())[:200]

        params = {"q": cleaned, "format": "json", "no_html": "1", "skip_disambig": "1"}
        timeout = httpx.Timeout(8.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get("https://api.duckduckgo.com/", params=params)
            resp.raise_for_status()

        data = resp.json()

        snippets: list[str] = []

        # Abstract (main answer)
        abstract = (data.get("AbstractText") or "").strip()
        if abstract:
            snippets.append(abstract)

        # Answer box (quick factual answers)
        answer = (data.get("Answer") or "").strip()
        if answer and answer not in snippets:
            snippets.append(answer)

        # Related topics
        for topic in (data.get("RelatedTopics") or [])[:5]:
            text = (topic.get("Text") or "").strip()
            if text and text not in snippets:
                snippets.append(text)
            if len(snippets) >= max_snippets:
                break

        if not snippets:
            return ""

        combined = " | ".join(snippets[:max_snippets])
        # Trim to a reasonable length so the LLM prompt doesn't blow up
        return combined[:800]

    except Exception:
        return ""
