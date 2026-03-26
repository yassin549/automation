from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
import random
from collections import Counter, deque
import math

from PIL import Image, ImageDraw, ImageFont

_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_BACKGROUND_COLOR = (19, 22, 27)
_LABEL_COLOR = (231, 235, 239)


@dataclass(frozen=True)
class ProofLayout:
    template_name: str
    time_left_pos: tuple[int, int]
    time_right_pos: tuple[int, int]
    time_box_left: tuple[int, int, int, int]
    time_box_right: tuple[int, int, int, int]
    time_color: tuple[int, int, int]
    profit_box: tuple[int, int, int, int]
    profit_label_pos: tuple[int, int]
    profit_color: tuple[int, int, int]


_WIN_LAYOUT = ProofLayout(
    template_name="win.png",
    time_left_pos=(8, 100),
    time_right_pos=(196, 100),
    time_box_left=(0, 96, 120, 112),
    time_box_right=(190, 96, 300, 112),
    time_color=(39, 65, 97),
    profit_box=(95, 184, 220, 202),
    profit_label_pos=(100, 184),
    profit_color=(21, 193, 89),
)

_LOSS_LAYOUT = ProofLayout(
    template_name="loss.png",
    time_left_pos=(8, 22),
    time_right_pos=(210, 22),
    time_box_left=(0, 18, 120, 34),
    time_box_right=(190, 18, 302, 34),
    time_color=(112, 125, 143),
    profit_box=(105, 98, 230, 116),
    profit_label_pos=(110, 98),
    profit_color=(189, 34, 37),
)


@dataclass(frozen=True)
class FieldSpec:
    region: tuple[int, int, int, int]
    mode: str = "single"  # "single" or "rightmost"


_WIN_FIELDS: dict[str, FieldSpec] = {
    "time_top": FieldSpec((940, 12, 1075, 50)),
    "stake_top": FieldSpec((50, 60, 220, 110)),
    "payout_top": FieldSpec((720, 60, 920, 110)),
    "profit_top": FieldSpec((900, 60, 1075, 110)),
    "open_time": FieldSpec((30, 150, 220, 210)),
    "close_time": FieldSpec((860, 150, 1075, 210)),
    "payout_center": FieldSpec((520, 300, 700, 335), mode="rightmost"),
    "profit_center": FieldSpec((520, 340, 700, 380), mode="rightmost"),
}

_LOSS_FIELDS: dict[str, FieldSpec] = {
    "time_top": FieldSpec((450, 5, 535, 40)),
    "stake_top": FieldSpec((40, 40, 150, 85)),
    "payout_top": FieldSpec((320, 40, 420, 85)),
    "profit_top": FieldSpec((430, 40, 535, 85)),
    "open_time": FieldSpec((20, 90, 170, 135)),
    "close_time": FieldSpec((360, 90, 535, 135)),
    "payout_center": FieldSpec((200, 220, 360, 255), mode="rightmost"),
    "profit_center": FieldSpec((200, 255, 360, 295), mode="rightmost"),
}


def pick_proof_image(
    proof_dir: Path, rng: random.Random | None = None
) -> Path | None:
    if not proof_dir.exists():
        return None

    files = [
        path
        for path in proof_dir.iterdir()
        if path.is_file() and path.suffix.lower() in _ALLOWED_EXTENSIONS
    ]
    if not files:
        return None

    picker = rng or random.SystemRandom()
    return picker.choice(files)


def render_proof_image(
    proof_dir: Path,
    result: str,
    taken_at: datetime,
    profit_text: str,
    stake_text: str,
    payout_text: str,
) -> Path | None:
    is_win = result.upper() == "WIN"
    template_name = "win.jpg" if is_win else "loss.png"
    template_path = proof_dir / template_name
    if not template_path.exists():
        return None

    base_img = Image.open(template_path).convert("RGB")
    img = base_img.copy()
    draw = ImageDraw.Draw(img)

    time_short = _format_time_short(taken_at)
    time_full = _format_time_full(taken_at)

    fields = _WIN_FIELDS if is_win else _LOSS_FIELDS
    values = {
        "time_top": time_short,
        "stake_top": stake_text,
        "payout_top": payout_text,
        "profit_top": profit_text,
        "open_time": time_full,
        "close_time": time_full,
        "payout_center": payout_text,
        "profit_center": profit_text,
    }

    for name, text in values.items():
        spec = fields.get(name)
        if not spec:
            continue
        _replace_text(base_img, img, draw, spec, text)

    output_dir = proof_dir / "_generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{result.lower()}_{taken_at.strftime('%Y%m%d_%H%M%S_%f')}.png"
    output_path = output_dir / filename
    img.save(output_path)
    return output_path


def _format_time(timestamp: datetime) -> str:
    return f"{timestamp:%H:%M:%S}.{timestamp.microsecond // 1000:03d}"


def _format_time_short(timestamp: datetime) -> str:
    return f"{timestamp:%H:%M}"


def _format_time_full(timestamp: datetime) -> str:
    date_part = f"{timestamp:%d/%m}"
    time_part = _format_time(timestamp)
    return f"{date_part} {time_part}"


@lru_cache(maxsize=8)
def _load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        Path(__file__).with_name("assets") / "Inter-Regular.ttf",
        Path(__file__).with_name("assets") / "Inter-SemiBold.ttf",
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                pass

    for name in ("DejaVuSans.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue

    return ImageFont.load_default()


def _format_currency(value: str) -> str:
    try:
        return f"{float(value):.2f}"
    except ValueError:
        return value


def _replace_text(
    base_img: Image.Image,
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    spec: FieldSpec,
    text: str,
    threshold: float = 35.0,
) -> None:
    group = _detect_text_group(base_img, spec.region, spec.mode, threshold=threshold)
    if not group:
        return
    bbox, bg_color, text_color = group

    x1, y1, x2, y2 = bbox
    fill_color = _sample_background_color(base_img, bbox, spec.region, bg_color)
    pad = 1
    ix1 = max(0, x1 - pad)
    iy1 = max(0, y1 - pad)
    ix2 = min(img.width - 1, x2 + pad)
    iy2 = min(img.height - 1, y2 + pad)
    draw.rectangle((ix1, iy1, ix2, iy2), fill=fill_color)

    max_w = x2 - x1 + 1
    max_h = y2 - y1 + 1
    font = _fit_font(draw, text, max_w, max_h)
    text_box = draw.textbbox((0, 0), text, font=font)
    text_w = text_box[2] - text_box[0]
    text_h = text_box[3] - text_box[1]

    align = _infer_align(spec.region, bbox)
    if align == "right":
        x = x2 - text_w
    else:
        x = x1
    y = y1 + max(0, (max_h - text_h) // 2)
    draw.text((x, y), text, fill=text_color, font=font)


def _fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    max_height: int,
) -> ImageFont.ImageFont:
    size = max(6, max_height)
    while size >= 6:
        font = _load_font(size)
        box = draw.textbbox((0, 0), text, font=font)
        width = box[2] - box[0]
        height = box[3] - box[1]
        if width <= max_width and height <= max_height:
            return font
        size -= 1
    return _load_font(6)


def _infer_align(region: tuple[int, int, int, int], bbox: tuple[int, int, int, int]) -> str:
    rx1, _, rx2, _ = region
    bx1, _, bx2, _ = bbox
    left_gap = bx1 - rx1
    right_gap = rx2 - bx2
    if right_gap < left_gap:
        return "right"
    return "left"


def _detect_text_group(
    img: Image.Image,
    region: tuple[int, int, int, int],
    mode: str,
    threshold: float,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int], tuple[int, int, int]] | None:
    x1, y1, x2, y2 = region
    crop = img.crop((x1, y1, x2, y2))
    pixels = list(crop.getdata())
    if not pixels:
        return None

    bg = Counter(pixels).most_common(1)[0][0]

    def dist(c: tuple[int, int, int]) -> float:
        return math.sqrt((c[0] - bg[0]) ** 2 + (c[1] - bg[1]) ** 2 + (c[2] - bg[2]) ** 2)

    w, h = crop.size
    mask = [[False] * w for _ in range(h)]
    for i, px in enumerate(pixels):
        if dist(px) > threshold:
            cx = i % w
            cy = i // w
            mask[cy][cx] = True

    visited = [[False] * w for _ in range(h)]
    comps: list[tuple[int, int, int, int, list[tuple[int, int, int]]]] = []
    for cy in range(h):
        for cx in range(w):
            if visited[cy][cx] or not mask[cy][cx]:
                continue
            q = deque([(cx, cy)])
            visited[cy][cx] = True
            minx = maxx = cx
            miny = maxy = cy
            text_pixels: list[tuple[int, int, int]] = []
            while q:
                x, y = q.popleft()
                text_pixels.append(crop.getpixel((x, y)))
                minx = min(minx, x)
                miny = min(miny, y)
                maxx = max(maxx, x)
                maxy = max(maxy, y)
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx] and mask[ny][nx]:
                        visited[ny][nx] = True
                        q.append((nx, ny))
            if (maxx - minx) * (maxy - miny) >= 10:
                comps.append((minx, miny, maxx, maxy, text_pixels))

    if not comps:
        return None

    # Merge close components into groups by x-gap.
    comps.sort(key=lambda c: c[0])
    groups: list[list[tuple[int, int, int, int, list[tuple[int, int, int]]]]] = []
    current: list[tuple[int, int, int, int, list[tuple[int, int, int]]]] = [comps[0]]
    for comp in comps[1:]:
        gap = comp[0] - current[-1][2]
        if gap > 6:
            groups.append(current)
            current = [comp]
        else:
            current.append(comp)
    groups.append(current)

    group = groups[-1] if mode == "rightmost" else groups[0]
    gx1 = min(c[0] for c in group)
    gy1 = min(c[1] for c in group)
    gx2 = max(c[2] for c in group)
    gy2 = max(c[3] for c in group)
    text_pixels = [px for c in group for px in c[4]]
    avg_text = tuple(int(sum(p[i] for p in text_pixels) / len(text_pixels)) for i in range(3))

    # Convert to global coords
    bbox = (x1 + gx1, y1 + gy1, x1 + gx2, y1 + gy2)
    return bbox, bg, avg_text


def _sample_background_color(
    img: Image.Image,
    bbox: tuple[int, int, int, int],
    region: tuple[int, int, int, int],
    fallback: tuple[int, int, int],
) -> tuple[int, int, int]:
    x1, y1, x2, y2 = bbox
    rx1, ry1, rx2, ry2 = region
    pad = 2
    sx1 = max(rx1, x1 - pad)
    sy1 = max(ry1, y1 - pad)
    sx2 = min(rx2, x2 + pad)
    sy2 = min(ry2, y2 + pad)

    samples: list[tuple[int, int, int]] = []
    for cy in range(sy1, sy2 + 1):
        for cx in range(sx1, sx2 + 1):
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                continue
            samples.append(img.getpixel((cx, cy)))

    if not samples:
        return fallback
    return Counter(samples).most_common(1)[0][0]


def format_profit_text(result: str, win_profit: str, loss_cost: str) -> str:
    if result.upper() == "WIN":
        return f"+${_format_currency(win_profit)}"
    return f"-${_format_currency(loss_cost)}"


def load_proof_dir(base_dir: Path) -> Path:
    return base_dir / "proof"
