from pathlib import Path
import random

_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


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
