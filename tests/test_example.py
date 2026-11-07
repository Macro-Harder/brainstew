"""End-to-end test: the shipped example wiki lints clean."""

import re
import shutil
import subprocess
import sys
from pathlib import Path

EXAMPLE_FILES = [
    "raw/fresnel-lens.txt",
    "wiki/index.md",
    "wiki/log.md",
    "wiki/synthesis/.gitkeep",
    "wiki/sources/fresnel-lens.md",
    "wiki/entities/augustin-fresnel.md",
    "wiki/entities/lighthouse.md",
    "wiki/concepts/fresnel-lens-optics.md",
    "wiki/concepts/lighthouse-illumination.md",
]


def test_finding_f17_search_invocation_shows_query_argument() -> None:
    skill = Path(__file__).resolve().parent.parent / ".agents" / "skills" / "wiki-query" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert re.search(r"brainstew search\s+\S+", text), text


def test_example_lints_clean(tmp_path: Path) -> None:
    for rel in EXAMPLE_FILES:
        src = Path(__file__).resolve().parent.parent / rel
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    proc = subprocess.run(
        [sys.executable, "-m", "brainstew", "--root", str(tmp_path), "lint"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout == "lint: 0 errors, 0 warnings\n"
    assert proc.stderr == ""
