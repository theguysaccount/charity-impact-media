#!/usr/bin/env python3
"""Open Graph share cards (1200x630 PNG): "Of every $100 spent" for each charity, so a
shared link previews the answer rather than a logo.

  python3 pipeline/og_cards.py [--limit 3000]     # needs Pillow; -> data/work/og/<ein>.png, site.png

Cards are made for the charities ranked highest by contributions (the ones most likely to
be shared), within the GitHub Pages size budget; every other page uses site.png.
Without Pillow it prints a notice and exits 0, and pages fall back to the site card.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import WORK, ensure_dir, read_json  # noqa: E402
from render import hundred_split, period, usd  # noqa: E402

W, H = 1200, 630
BG, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#6f6d68", "#e1e0d9"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
ACCENT = "#1c5cab"
FONT_DIRS = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
]


def fonts(ImageFont):
    for reg, bold in FONT_DIRS:
        if os.path.exists(reg) and os.path.exists(bold):
            return lambda size, b=False: ImageFont.truetype(bold if b else reg, size)
    return lambda size, b=False: ImageFont.load_default()


def wrap(draw, text, font, width, max_lines):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and draw.textlength(lines[-1] + "…", font=font) > width:
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1].rstrip() + "…"
    return lines


def card(Image, ImageDraw, F, c=None):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=ACCENT)
    x = 64
    if c is None:
        d.text((x, 70), "CHARITY IMPACT MEDIA", font=F(26, True), fill=ACCENT)
        y = 130
        for line in ["Where does the money go?", "Sourced breakdowns of 25,000+", "US charities' IRS Form 990s."]:
            d.text((x, y), line, font=F(64, True), fill=INK)
            y += 80
        d.text((x, 470), "Program spending · executive pay · revenue · trends. No ratings.", font=F(30), fill=INK2)
        d.text((x, 545), "Every number links to the filing it came from.", font=F(26), fill=MUTED)
        return img
    m, y0 = c["m"], c["years"][-1]
    _, lab = period(y0)
    d.text((x, 44), f"WHERE THE MONEY GOES · FORM 990, {lab}", font=F(24, True), fill=ACCENT)
    tf = F(60, True)
    lines = wrap(d, c["name"], tf, W - 2 * x, 2)
    if len(lines) == 2 and d.textlength(lines[1], font=tf) > W - 2 * x - 10:
        tf = F(50, True)
        lines = wrap(d, c["name"], tf, W - 2 * x, 2)
    y = 88
    for line in lines:
        d.text((x, y), line, font=tf, fill=INK)
        y += tf.size + 10
    y = max(y + 18, 250)
    d.text((x, y), "Of every $100 spent:", font=F(32), fill=INK2)
    y += 54
    cents = hundred_split([m["program_share"], m["mgmt_share"], m["fund_share"]])
    bw, bh, gap = W - 2 * x, 48, 4
    edges, acc = [x], 0
    for cc in cents:
        acc += cc
        edges.append(x + round(bw * acc / 10000))
    for i, cc in enumerate(cents):
        if cc <= 0:
            continue
        a, b = edges[i], edges[i + 1]
        if any(c2 > 0 for c2 in cents[i + 1:]):
            b -= gap
        b = max(b, a + 3)
        d.rounded_rectangle([a, y, b, y + bh], radius=min(8, (b - a) // 2), fill=SERIES[i])
    y += bh + 28
    labels = ["programs", "management", "fundraising"]
    col_w = (W - 2 * x) // 3
    for i, cc in enumerate(cents):
        lx = x + i * col_w
        d.rounded_rectangle([lx, y + 14, lx + 22, y + 36], radius=4, fill=SERIES[i])
        d.text((lx + 34, y), f"${cc / 100:,.2f}", font=F(46, True), fill=INK)
        d.text((lx + 34, y + 56), labels[i], font=F(28), fill=INK2)
    bits = [f"Revenue {usd(c['latest'].get('rev_total'))}"]
    if m.get("top_comp"):
        bits.append(f"top pay {usd(m['top_comp'], short=False)}")
    bits.append(f"{c['city']}, {c['state']}" if c.get("city") else c["state"])
    d.line([x, H - 76, W - x, H - 76], fill=GRID, width=2)
    d.text((x, H - 58), " · ".join(bits), font=F(26), fill=MUTED)
    brand = "Charity Impact Media"
    bf = F(26, True)
    d.text((W - x - d.textlength(brand, font=bf), H - 58), brand, font=bf, fill=ACCENT)
    return img


def save(img, path):
    img.convert("P", palette=1, colors=64).save(path, optimize=True)  # palette=1 is Image.ADAPTIVE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=int(os.environ.get("CIM_OG_LIMIT") or 3000))
    a = ap.parse_args()
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("Pillow not installed: skipping share cards (pages use the site card)", file=sys.stderr)
        return
    F = fonts(ImageFont)
    out = ensure_dir(os.path.join(WORK, "og"))
    save(card(Image, ImageDraw, F), os.path.join(out, "site.png"))
    data = read_json(os.path.join(WORK, "site_data.json.gz"))
    keep = set()
    for c in data["charities"]:
        if len(keep) >= a.limit:
            break
        if "program_share" not in c["m"]:
            continue
        save(card(Image, ImageDraw, F, c), os.path.join(out, f"{c['ein']}.png"))
        keep.add(f"{c['ein']}.png")
    n = len(keep)
    for fn in os.listdir(out):
        if fn.endswith(".png") and fn != "site.png" and fn not in keep:
            os.remove(os.path.join(out, fn))
    print(f"share cards: {n}", file=sys.stderr)


if __name__ == "__main__":
    main()
