# make_spritesheet.py
import math, json, argparse, os
from PIL import Image

def pack(images, cols=None, pad=0, scale=1.0):
    # Load frames, find max w/h (after scale)
    frames = [Image.open(p).convert("RGBA") for p in images]
    if scale != 1.0:
        frames = [im.resize((int(im.width*scale), int(im.height*scale)), Image.BICUBIC) for im in frames]
    fw = max(im.width for im in frames)
    fh = max(im.height for im in frames)

    n = len(frames)
    cols = cols or math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)

    sheet_w = cols*fw + (cols-1)*pad
    sheet_h = rows*fh + (rows-1)*pad
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (0,0,0,0))

    rects = []
    for i, im in enumerate(frames):
        c = i % cols
        r = i // cols
        x = c*(fw+pad)
        y = r*(fh+pad)
        sheet.paste(im, (x, y))
        rects.append({"x": x, "y": y, "w": fw, "h": fh, "index": i})

    return sheet, rects, (fw, fh), (cols, rows)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="output PNG path")
    ap.add_argument("--json", required=True, help="output JSON path")
    ap.add_argument("--cols", type=int, default=0, help="columns (0 = auto)")
    ap.add_argument("--pad", type=int, default=0, help="padding between frames")
    ap.add_argument("--scale", type=float, default=1.0, help="scale frames before packing (e.g., 0.66)")
    ap.add_argument("frames", nargs="+", help="input frame images in order")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    os.makedirs(os.path.dirname(args.json), exist_ok=True)

    sheet, rects, cell, grid = pack(args.frames, cols=(args.cols or None), pad=args.pad, scale=args.scale)
    sheet.save(args.out)
    meta = {"frames": rects, "cell": {"w": cell[0], "h": cell[1]}, "grid": {"cols": grid[0], "rows": grid[1]}}
    with open(args.json, "w") as f:
        json.dump(meta, f)
    print(f"Wrote {args.out} and {args.json}")

    print("Wrote:", os.path.abspath(args.out))
    print("Wrote:", os.path.abspath(args.json))