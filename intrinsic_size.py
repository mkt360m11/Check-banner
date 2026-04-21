from __future__ import annotations
import os
import sys
from io import BytesIO
from typing import Optional
import requests
from PIL import Image

REQUEST_TIMEOUT = int(os.getenv("WORKER_TIMEOUT", "15"))

def get_intrinsic_size(
    img_url: str,
    *,
    debug: bool = False,
) -> Optional[tuple[int, int]]:
    """
    Download image and return its actual (width, height) in pixels.
    Returns None if download or decode fails.
    No proxy needed — images are served from public CDN.
    """
    if not img_url:
        if debug:
            print(f"SKIP — empty url")
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

        content_type = r.headers.get("Content-Type", "")
        size_bytes = len(r.content)

        img = Image.open(BytesIO(r.content))
        w, h = img.size

        if debug:
            print(f"  Content-Type: {content_type}")
            print(f"  File size:    {size_bytes:,} bytes")
            print(f"  Format:       {img.format}")
            print(f"  Intrinsic:    {w}x{h} px")

        return (w, h)

    except Exception as e:
        if debug:
            print(f"  FAIL — {e}")
        return None


def compare_size(
    intrinsic: Optional[tuple[int, int]],
    declared_w: Optional[int],
    declared_h: Optional[int],
    *,
    debug: bool = False,
) -> dict:
    """
    Compare intrinsic vs declared size.
    Returns {match, reason, scale_factor}.
    """
    if intrinsic is None:
        result = {"match": False, "reason": "image_fetch_failed", "scale_factor": None}
    elif not declared_w or not declared_h:
        result = {"match": False, "reason": "missing_declared_size", "scale_factor": None}
    else:
        iw, ih = intrinsic
        scale_w = iw / declared_w
        scale_h = ih / declared_h
        is_exact = (iw == declared_w and ih == declared_h)
        is_retina = (scale_w == scale_h and scale_w in {1.5, 2.0, 3.0})

        if is_exact:
            reason = "exact_match"          # intrinsic == declared, perfect match
        elif is_retina:
            reason = f"retina_{int(scale_w)}x"  # image is {scale}x larger for high-DPI screens, acceptable
        else:
            reason = "size_mismatch"        # intrinsic differs from declared, not a known retina ratio

        result = {
            "match": is_exact or is_retina,
            "reason": reason,
            "scale_factor": round(scale_w, 2),
        }

    _reason_desc = {
        "exact_match":          "intrinsic == declared, perfect match",
        "size_mismatch":        "intrinsic differs from declared, not a known retina ratio",
        "image_fetch_failed":   "could not download or decode the image",
        "missing_declared_size":"no width/height attribute found in <img> tag",
    }

    if debug:
        declared = f"{declared_w}x{declared_h}" if declared_w and declared_h else "unknown"
        status = "PASS" if result["match"] else "FAIL"
        reason = result["reason"]
        if reason.startswith("retina_"):
            desc = f"image is {result['scale_factor']}x larger for high-DPI screens, acceptable"
        else:
            desc = _reason_desc.get(reason, "")
        print(f"  Declared:     {declared}")
        print(f"  Result:       {status} — {reason}" + (f" (scale={result['scale_factor']}x)" if result['scale_factor'] else ""))
        print(f"  Explanation:  {desc}")

    return result


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    img_url = args[0]
    declared_w: Optional[int] = None
    declared_h: Optional[int] = None

    if len(args) >= 2:
        try:
            dw, dh = args[1].lower().split("x")
            declared_w, declared_h = int(dw), int(dh)
        except ValueError:
            print(f"[WARN] Could not parse declared size '{args[1]}', expected format: 728x90")

    intrinsic = get_intrinsic_size(img_url, debug=True)
    print()
    result = compare_size(intrinsic, declared_w, declared_h, debug=True)
    print()

    # Final verdict
    status = "PASS" if result["match"] else "FAIL"
    print(f"{'─'*50}")
    print(f"  verdict: {status}")
    print(f"  reason:          {result['reason']}")
    if result["scale_factor"]:
        print(f"  scale_factor:    {result['scale_factor']}x")
    print(f"{'─'*50}")


if __name__ == "__main__":
    main()
