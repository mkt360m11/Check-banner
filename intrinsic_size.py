from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from typing import Optional

import requests
from PIL import Image  # Pillow

REQUEST_TIMEOUT = int(os.getenv("WORKER_TIMEOUT", "15"))

def _get_intrinsic_size(
    img_url: str,
    *,
    debug: bool = False,
) -> Optional[tuple[int, int]]:
    """
    Download image from URL and return its actual (width, height) in pixels.
    Returns None if download or decode fails.
    """
    if not img_url:
        if debug:
            print("SKIP — empty url")
        return None

    if debug:
        print(f"Downloading: {img_url}")

    try:
        r = requests.get(
            img_url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        r.raise_for_status()

        img = Image.open(BytesIO(r.content))
        w, h = img.size

        if debug:
            print(f"  Content-Type: {r.headers.get('Content-Type', '')}")
            print(f"  File size:    {len(r.content):,} bytes")
            print(f"  Format:       {img.format}")
            print(f"  Intrinsic:    {w}x{h} px")

        return (w, h)

    except Exception as e:
        if debug:
            print(f"  FAIL — {e}")
        return None


def get_intrinsic_sizes_bulk(
    urls: list[str],
    *,
    max_workers: int = 50,
    debug: bool = False,
) -> dict[str, Optional[tuple[int, int]]]:
    """Run get_intrinsic_size concurrently for a list of URLs."""
    results: dict[str, Optional[tuple[int, int]]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_url = {
            pool.submit(_get_intrinsic_size, url, debug=debug): url for url in urls
        }
        for future in as_completed(future_to_url):
            results[future_to_url[future]] = future.result()
    return results
