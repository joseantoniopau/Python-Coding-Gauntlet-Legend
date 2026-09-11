#!/usr/bin/env python3
"""Generate the app icon as original pixel art, with no external dependencies.

A 32x32 design is authored here, scaled with nearest-neighbour into every size
macOS wants, written as PNGs with stdlib zlib, and assembled by iconutil.
"""
from __future__ import annotations

import struct
import subprocess
import sys
import zlib
from pathlib import Path

# A sword crossed over a bracket pair, on a deep violet field: the two halves of
# what this app actually is.
PALETTE = {
    ".": None,
    "b": (18, 15, 32, 255),      # background deep
    "B": (32, 26, 58, 255),      # background mid
    "e": (58, 48, 98, 255),      # edge
    "g": (232, 195, 125, 255),   # gold
    "G": (255, 232, 160, 255),   # gold highlight
    "s": (200, 205, 220, 255),   # steel
    "S": (245, 248, 255, 255),   # steel highlight
    "d": (90, 95, 115, 255),     # steel shadow
    "v": (168, 154, 255, 255),   # violet
    "n": (143, 208, 122, 255),   # green
}

ART = [
    "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    "eBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBe",
    "eBbbbbbbbbbbbbbbbbbbbbbbbbbbbbBe",
    "eBbbbbbbbbbbbbSSbbbbbbbbbbbbbbBe",
    "eBbbbbbbbbbbbbSSbbbbbbbbbbbbbbBe",
    "eBbbvvbbbbbbbdSSdbbbbbbbbnnbbbBe",
    "eBbvvvbbbbbbbdSSdbbbbbbbbnnnbbBe",
    "eBbvvbbbbbbbbdSSdbbbbbbbbbnnbbBe",
    "eBbvvbbbbbbbbdSSdbbbbbbbbbnnbbBe",
    "eBbvvbbbbbbbbdSSdbbbbbbbbbnnbbBe",
    "eBbvvbbbbbbbbdSSdbbbbbbbbbnnbbBe",
    "eBbvvbbbbbbbbdSSdbbbbbbbbbnnbbBe",
    "eBbvvbbbbbbbbdSSdbbbbbbbbbnnbbBe",
    "eBbvvbbbbbbbbdSSdbbbbbbbbbnnbbBe",
    "eBbvvbbbbbbgggSSgggbbbbbbbnnbbBe",
    "eBbvvbbbbbgGGGSSGGGgbbbbbbnnbbBe",
    "eBbvvbbbbbgGgggggggGbbbbbbnnbbBe",
    "eBbvvbbbbbbggdSSdggbbbbbbbnnbbBe",
    "eBbvvbbbbbbbbdSSdbbbbbbbbbnnbbBe",
    "eBbvvbbbbbbbbdSSdbbbbbbbbbnnbbBe",
    "eBbvvbbbbbbbbdSSdbbbbbbbbbnnbbBe",
    "eBbvvbbbbbbbbdSSdbbbbbbbbbnnbbBe",
    "eBbvvbbbbbbbbbSSbbbbbbbbbbnnbbBe",
    "eBbvvbbbbbbbbbgGbbbbbbbbbbnnbbBe",
    "eBbvvvbbbbbbbbgGbbbbbbbbbnnnbbBe",
    "eBbbvvbbbbbbbbbgbbbbbbbbbnnbbbBe",
    "eBbbbbbbbbbbbbbbbbbbbbbbbbbbbbBe",
    "eBbbbbbbbbbbbbbbbbbbbbbbbbbbbbBe",
    "eBbbbbbbbbbbbbbbbbbbbbbbbbbbbbBe",
    "eBbbbbbbbbbbbbbbbbbbbbbbbbbbbbBe",
    "eBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBe",
    "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
]


def render(scale: int) -> tuple:
    size = 32 * scale
    rows = []
    for y in range(size):
        row = bytearray([0])          # PNG filter byte: none
        src_y = y // scale
        for x in range(size):
            colour = PALETTE.get(ART[src_y][x // scale]) or (0, 0, 0, 0)
            row += bytes(colour)
        rows.append(bytes(row))
    return size, b"".join(rows)


def write_png(path: Path, size: int, raw: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return (struct.pack(">I", len(data)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", header)
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    path.write_bytes(png)


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/AppIcon.icns")
    iconset = out.with_suffix(".iconset")
    iconset.mkdir(parents=True, exist_ok=True)

    wanted = [(16, "16x16"), (32, "16x16@2x"), (32, "32x32"), (64, "32x32@2x"),
              (128, "128x128"), (256, "128x128@2x"), (256, "256x256"),
              (512, "256x256@2x"), (512, "512x512"), (1024, "512x512@2x")]
    for pixels, name in wanted:
        scale = max(1, pixels // 32)
        size, raw = render(scale)
        write_png(iconset / f"icon_{name}.png", size, raw)

    try:
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out)],
                       check=True, capture_output=True)
        print(f"wrote {out}")
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"iconutil unavailable ({exc}); PNG iconset left at {iconset}")
        return 0
    for f in iconset.iterdir():
        f.unlink()
    iconset.rmdir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
