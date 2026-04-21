from __future__ import annotations

import os
import sys
from io import BytesIO
from typing import Optional

import requests
from PIL import Image # Pillow

REQUEST_TIMEOUT = int(os.getenv("WORKER_TIMEOUT", "15"))

def get_intrinsic_size(
    img_url: str,
    *,
    debug: bool = False,
) -> Optional[tuple[int, int]]:
    """
    Download image from URL and return its actual (width, height) in pixels.
    Returns None if download or decode fails.
    No proxy needed — images are served from public CDN.
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


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    img_url = sys.argv[1].strip()
    result = get_intrinsic_size(img_url, debug=True)

    print()
    if result:
        print(f"{'─'*50}")
        print(f"  intrinsic size: {result[0]}x{result[1]} px")
        print(f"{'─'*50}")
    else:
        print("Failed to get intrinsic size.")


if __name__ == "__main__":
    main()
