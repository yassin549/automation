from pathlib import Path

from ghost.proof import pick_proof_image


def test_pick_proof_image_selects_valid_file(tmp_path: Path) -> None:
    (tmp_path / "ignore.txt").write_text("nope", encoding="utf-8")
    (tmp_path / "proof.png").write_bytes(b"fake")
    choice = pick_proof_image(tmp_path)
    assert choice is not None
    assert choice.name == "proof.png"
