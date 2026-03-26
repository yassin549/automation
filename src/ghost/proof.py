from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
import random

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
) -> Path | None:
    layout = _WIN_LAYOUT if result.upper() == "WIN" else _LOSS_LAYOUT
    template_path = proof_dir / layout.template_name
    if not template_path.exists():
        return None

    img = Image.open(template_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    time_text = _format_time(taken_at)
    time_font = _load_font(10)
    profit_font = _load_font(12)

    draw.rectangle(layout.time_box_left, fill=_BACKGROUND_COLOR)
    draw.rectangle(layout.time_box_right, fill=_BACKGROUND_COLOR)
    draw.text(layout.time_left_pos, time_text, fill=layout.time_color, font=time_font)
    draw.text(layout.time_right_pos, time_text, fill=layout.time_color, font=time_font)

    draw.rectangle(layout.profit_box, fill=_BACKGROUND_COLOR)
    label = "Profit:"
    draw.text(layout.profit_label_pos, label, fill=_LABEL_COLOR, font=profit_font)
    label_width = draw.textlength(label, font=profit_font)
    value_pos = (layout.profit_label_pos[0] + int(label_width) + 4, layout.profit_label_pos[1])
    draw.text(value_pos, profit_text, fill=layout.profit_color, font=profit_font)

    output_dir = proof_dir / "_generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{result.lower()}_{taken_at.strftime('%Y%m%d_%H%M%S_%f')}.png"
    output_path = output_dir / filename
    img.save(output_path)
    return output_path


def _format_time(timestamp: datetime) -> str:
    return f"{timestamp:%H:%M:%S}.{timestamp.microsecond // 1000:03d}"


@lru_cache(maxsize=8)
def _load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        Path(__file__).with_name("assets") / "Inter-Regular.ttf",
        Path(__file__).with_name("assets") / "Inter-SemiBold.ttf",
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


def format_profit_text(result: str, win_profit: str, loss_cost: str) -> str:
    if result.upper() == "WIN":
        return f"+${_format_currency(win_profit)}"
    return f"-${_format_currency(loss_cost)}"


def load_proof_dir(base_dir: Path) -> Path:
    return base_dir / "proof"
