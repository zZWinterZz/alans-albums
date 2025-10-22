"""Small Discogs API helper with caching and retry/backoff.

Usage: set DISCOGS_TOKEN in env (recommended) or pass token param.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import requests
from django.core.cache import cache

BASE_URL = "https://api.discogs.com"
DEFAULT_USER_AGENT = "alans-albums/1.0 +https://example.com"


def _get_token(token: Optional[str] = None) -> Optional[str]:
    return token or os.environ.get("DISCOGS_TOKEN")


def _cache_key_search(q: str, type_: str, page: int, per_page: int) -> str:
    return f"discogs:search:{q}:{type_}:{page}:{per_page}"


def search(
    q: str,
    type_: str = "release",
    page: int = 1,
    per_page: int = 12,
    token: Optional[str] = None,
    ttl: int = 3600,
) -> List[Dict[str, Any]]:
    """Search Discogs database and return list of result dicts.

    This function will cache successful responses for `ttl` seconds and will
    attempt a small retry/backoff on 429/5xx responses. On repeated failure it
    will return an empty list (or cached value if present).
    """
    if not q:
        return []

    key = _cache_key_search(q, type_, page, per_page)
    cached = cache.get(key)
    if cached is not None:
        return cached

    token = _get_token(token)
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    if token:
        headers["Authorization"] = f"Discogs token={token}"

    url = f"{BASE_URL}/database/search"
    params = {"q": q, "type": type_, "page": page, "per_page": per_page}

    attempts = 0
    backoff = 1.0
    max_attempts = 4
    while attempts < max_attempts:
        attempts += 1
        try:
            resp = requests.get(
                url, headers=headers, params=params, timeout=10
            )
        except requests.RequestException:
            # network-level error — backoff and retry
            if attempts >= max_attempts:
                break
            time.sleep(backoff)
            backoff *= 2
            continue

        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            # cache and return
            try:
                cache.set(key, results, ttl)
            except Exception:
                # cache failures shouldn't break the app
                pass
            return results

        if resp.status_code == 429:
            # Rate limited — respect Retry-After if provided
            retry_after = resp.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait = float(retry_after)
            else:
                wait = backoff
            time.sleep(wait)
            backoff *= 2
            continue

        if 500 <= resp.status_code < 600:
            # server error, backoff and retry
            if attempts >= max_attempts:
                break
            time.sleep(backoff)
            backoff *= 2
            continue

        # For other 4xx errors, don't retry (bad request, unauthorized, etc.)
        break

    # If we reach here, try returning whatever is in cache else empty list
    return cached or []


def get_release(
    release_id: int, token: Optional[str] = None, ttl: int = 86400
) -> Optional[Dict[str, Any]]:
    """Retrieve a release by id and cache the response."""
    if not release_id:
        return None
    key = f"discogs:release:{release_id}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    token = _get_token(token)
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    if token:
        headers["Authorization"] = f"Discogs token={token}"

    url = f"{BASE_URL}/releases/{release_id}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException:
        return cached

    if resp.status_code == 200:
        data = resp.json()
        try:
            cache.set(key, data, ttl)
        except Exception:
            pass
        return data

    return cached


def price_suggestions(
    release_id: int, token: Optional[str] = None, ttl: int = 86400
) -> Dict[str, Any]:
    """Retrieve marketplace price suggestions for a release and cache the response.

    Returns a dict mapping condition names to {currency, value} or an empty dict.
    Authentication (user token) is required by Discogs; we send the configured
    DISCOGS_TOKEN if available. We cache the response for `ttl` seconds.
    """
    try:
        release_id = int(release_id)
    except Exception:
        return {}

    key = f"discogs:price_suggestions:{release_id}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    token = _get_token(token)
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    if token:
        headers["Authorization"] = f"Discogs token={token}"

    url = f"{BASE_URL}/marketplace/price_suggestions/{release_id}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException:
        return cached or {}

    if resp.status_code == 200:
        try:
            data = resp.json() or {}
        except Exception:
            data = {}
        try:
            cache.set(key, data, ttl)
        except Exception:
            pass
        return data

    return cached or {}
