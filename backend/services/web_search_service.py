"""Web-search helper with multiple strategies for medical queries.

Returns a concise text snippet that the LLM can incorporate into its answer.
Uses DuckDuckGo HTML search (bypasses Instant Answer limitations) plus Wikipedia API
as a fallback, so the model gets real, grounded medical information.
"""

from __future__ import annotations

import re
import httpx


async def _ddg_instant_answer(query: str, max_snippets: int, client: httpx.AsyncClient) -> list[str]:
    """Try DuckDuckGo Instant Answer API."""
    params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
    resp = await client.get("https://api.duckduckgo.com/", params=params)
    resp.raise_for_status()
    data = resp.json()

    snippets: list[str] = []
    abstract = (data.get("AbstractText") or "").strip()
    if abstract:
        snippets.append(abstract)
    answer = (data.get("Answer") or "").strip()
    if answer and answer not in snippets:
        snippets.append(answer)
    for topic in (data.get("RelatedTopics") or [])[:8]:
        text = (topic.get("Text") or "").strip()
        if text and text not in snippets:
            snippets.append(text)
        if len(snippets) >= max_snippets:
            break
    return snippets[:max_snippets]


async def _ddg_html_search(query: str, max_snippets: int, client: httpx.AsyncClient) -> list[str]:
    """Scrape DuckDuckGo HTML-lite search for real search result snippets."""
    params = {"q": query}
    headers = {"User-Agent": "Mozilla/5.0 (compatible; PulseMedicalBot/1.0)"}
    resp = await client.get("https://html.duckduckgo.com/html/", params=params, headers=headers)
    resp.raise_for_status()
    html = resp.text

    # Extract snippets from result__snippet class
    snippets: list[str] = []
    for match in re.finditer(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL):
        text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        text = re.sub(r"\s+", " ", text)
        if text and len(text) > 30 and text not in snippets:
            snippets.append(text)
        if len(snippets) >= max_snippets:
            break
    return snippets


async def _wikipedia_search(query: str, max_snippets: int, client: httpx.AsyncClient) -> list[str]:
    """Search Wikipedia API for medical article extracts."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": str(min(max_snippets, 3)),
        "utf8": "1",
    }
    resp = await client.get("https://en.wikipedia.org/w/api.php", params=params)
    resp.raise_for_status()
    data = resp.json()

    snippets: list[str] = []
    for result in (data.get("query", {}).get("search", []))[:max_snippets]:
        snippet = re.sub(r"<[^>]+>", "", result.get("snippet", "")).strip()
        title = result.get("title", "")
        if snippet and len(snippet) > 20:
            snippets.append(f"{title}: {snippet}")
    return snippets


async def web_search(query: str, max_snippets: int = 5) -> str:
    """Search the web for *query* and return a short summary string.

    Uses multiple strategies: DuckDuckGo HTML search, DuckDuckGo Instant Answer API,
    and Wikipedia API. Falls back gracefully to an empty string on any failure so
    callers never need to handle exceptions.
    """
    if not query or not query.strip():
        return ""

    try:
        cleaned = re.sub(r"[^\w\s\-/]", " ", query)
        cleaned = " ".join(cleaned.split())[:250]

        # Add "medical treatment guidelines" to improve search relevance for medical queries
        medical_query = cleaned
        medical_keywords = {"treatment", "drug", "medication", "symptom", "diagnosis", "clinical", "triage"}
        if any(kw in cleaned.lower() for kw in medical_keywords):
            medical_query = f"{cleaned} medical treatment guidelines evidence-based"

        timeout = httpx.Timeout(10.0)
        all_snippets: list[str] = []

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            # Strategy 1: DuckDuckGo HTML search (most reliable for real results)
            try:
                html_snippets = await _ddg_html_search(medical_query, max_snippets, client)
                all_snippets.extend(html_snippets)
            except Exception:
                pass

            # Strategy 2: DuckDuckGo Instant Answer API
            try:
                ia_snippets = await _ddg_instant_answer(cleaned, max_snippets, client)
                for s in ia_snippets:
                    if s not in all_snippets:
                        all_snippets.append(s)
            except Exception:
                pass

            # Strategy 3: Wikipedia for authoritative medical information
            try:
                wiki_snippets = await _wikipedia_search(cleaned, 2, client)
                for s in wiki_snippets:
                    if s not in all_snippets:
                        all_snippets.append(s)
            except Exception:
                pass

        if not all_snippets:
            return ""

        combined = " | ".join(all_snippets[:max_snippets])
        return combined[:1200]

    except Exception:
        return ""
