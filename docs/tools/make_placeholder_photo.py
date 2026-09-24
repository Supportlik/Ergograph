"""Draw the placeholder portrait used by the example personas.

The examples must not show a real person (R21), and a stock photo would
bring a licence with it. This draws a neutral silhouette on a studio-grey
gradient instead, in the portrait format a CV photo usually has (4:5).

    uv run --with pillow python docs/tools/make_placeholder_photo.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

W, H, SS = 1000, 1250, 3          # final size, supersampling factor
OUT = Path(__file__).resolve().parents[2] / "examples" / "software-architect" / "photo.jpg"


def main() -> None:
    w, h = W * SS, H * SS
    img = Image.new("RGB", (w, h))
    px = img.load()
    cx, cy = w * 0.5, h * 0.36
    for y in range(h):
        for x in range(0, w):
            # radial studio light: lighter behind the head, darker at the edges
            d = (((x - cx) / w) ** 2 + ((y - cy) / h) ** 2) ** 0.5
            v = int(max(0, min(255, 168 - d * 150)))
            px[x, y] = (v - 6, v - 2, v + 4)
    draw = ImageDraw.Draw(img)
    body = (58, 68, 84)
    # shoulders: a wide rounded shape running off the bottom edge
    draw.rounded_rectangle((w * 0.14, h * 0.62, w * 0.86, h * 1.25),
                           radius=int(w * 0.26), fill=body)
    # neck and head
    draw.rounded_rectangle((w * 0.42, h * 0.48, w * 0.58, h * 0.66),
                           radius=int(w * 0.05), fill=body)
    draw.ellipse((w * 0.33, h * 0.18, w * 0.67, h * 0.55), fill=body)
    img = img.filter(ImageFilter.GaussianBlur(SS * 0.6))
    img = img.resize((W, H), Image.LANCZOS)
    img.save(OUT, "JPEG", quality=92, subsampling=0, optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
