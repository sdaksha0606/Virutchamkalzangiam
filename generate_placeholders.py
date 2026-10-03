"""
generate_placeholders.py
Run once to create placeholder images for development.
Replace these with real photos in production.
Usage: python generate_placeholders.py
"""

import os
import struct
import zlib

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "static", "images")
GALLERY_DIR = os.path.join(IMAGES_DIR, "gallery")

os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(GALLERY_DIR, exist_ok=True)


def make_png(width: int, height: int, r: int, g: int, b: int) -> bytes:
    """Create a minimal solid-color PNG."""
    def chunk(ctype: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + ctype + data
        return c + struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)

    # Image header
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)

    # Raw pixel row (RGB, no alpha) with filter byte 0
    row = bytes([0] + [r, g, b] * width)
    raw = b"".join(row for _ in range(height))
    idat = zlib.compress(raw)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", idat)
        + chunk(b"IEND", b"")
    )


PLACEHOLDER_SPECS = {
    # filename          : (width, height,   R,   G,   B,  description)
    "hero1.jpg"        : (1920, 1080, 26, 90, 60,   "Hero 1 — community gathering"),
    "hero2.jpg"        : (1920, 1080, 31, 98, 118,  "Hero 2 — children learning"),
    "hero3.jpg"        : (1920, 1080, 20, 60, 96,   "Hero 3 — women training"),
    "about.jpg"        : (800,  1000, 34, 110, 70,  "About — community space"),
    "women.jpg"        : (800,  450,  180, 100, 140, "Women empowerment photo"),
    "transgender.jpg"  : (800,  450,  100, 130, 180, "Transgender support photo"),
    "children.jpg"     : (800,  450,  60,  140, 90,  "Children schooling photo"),
    "room.jpg"         : (1920, 1080, 15, 40, 60,   "The shared community room"),
    "donate_side.jpg"  : (800,  450,  26, 82, 60,   "Donation page sidebar"),
    "gallery/g1.jpg"   : (600,  800,  34, 100, 60,  "Gallery 1"),
    "gallery/g2.jpg"   : (600,  450,  60, 140, 100, "Gallery 2"),
    "gallery/g3.jpg"   : (600,  450,  100, 130, 80, "Gallery 3"),
    "gallery/g4.jpg"   : (900,  450,  26, 90, 120,  "Gallery 4"),
    "gallery/g5.jpg"   : (600,  450,  140, 90, 180, "Gallery 5"),
    "gallery/g6.jpg"   : (600,  450,  80, 120, 160, "Gallery 6"),
}


def main():
    for filename, (w, h, r, g, b, desc) in PLACEHOLDER_SPECS.items():
        filepath = os.path.join(IMAGES_DIR, filename)
        if os.path.exists(filepath):
            print(f"  skip  {filename}  (already exists)")
            continue
        png_bytes = make_png(w, h, r, g, b)
        with open(filepath, "wb") as f:
            f.write(png_bytes)
        print(f"  created  {filename}  ({w}×{h})  ← {desc}")

    print()
    print("✓ Placeholder images created.")
    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  HOW TO ADD REAL PHOTOS (for NGO management):")
    print("  Replace each file in static/images/ with a real photo.")
    print("  Recommended resolutions:")
    print("    hero1/2/3.jpg   → 1920×1080  (landscape, high quality)")
    print("    about.jpg       → 800×1000   (portrait)")
    print("    women/trans/children.jpg → 800×450 (landscape)")
    print("    room.jpg        → 1920×1080  (landscape)")
    print("    donate_side.jpg → 800×450   (landscape)")
    print("    gallery/g1.jpg  → 600×800   (portrait)")
    print("    gallery/g2-6.jpg→ 600×450   (landscape)")
    print("  Keep the same filenames — the website picks them up automatically.")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


if __name__ == "__main__":
    main()
