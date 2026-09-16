"""
Build a scratch project of mixed material from files already on this
machine, so the photos-plus-clip-plus-voiceover path can be run end to
end without touching any real project.

    uv run python docs/plans/2026-09-17/mixed_project.py <folder>

Then, on that folder, in order:

    uv run film ingest -p <folder>
    uv run film init -p <folder>
    uv run film check -p <folder>
    uv run film caption -p <folder>          (preview only)
    uv run film peek -p <folder> --no-open

Made 2026-09-16 from: two shelf pictures, one project's cover picture,
12 s of a real take (20-32 s), and 14 s of that take's sound (40-54 s)
as voiceover.wav. Every source is read, never moved.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TAKE = ROOT / "projects" / "I am not your fear" / "media" / "rec_20260916-113221.mp4"

folder = Path(sys.argv[1]).resolve()
media = folder / "media"
if folder.exists():
    shutil.rmtree(folder)
media.mkdir(parents=True)
shutil.copy(ROOT / "library" / "cover" / "horizontal.png", media / "01_harbour.png")
shutil.copy(ROOT / "library" / "cover" / "vertical.png", media / "02_tall.png")
shutil.copy(ROOT / "projects" / "I love you" / "cover" / "distopia.png",
            media / "03_city.png")
subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", "20", "-t", "12",
                "-i", str(TAKE), "-c", "copy", str(media / TAKE.name)], check=True)
subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", "40", "-t", "14",
                "-i", str(TAKE), "-vn", "-ac", "1", "-ar", "48000",
                str(media / "voiceover.wav")], check=True)
print(f"made {folder}")
for p in sorted(media.iterdir()):
    print(f"  {p.name:28s} {p.stat().st_size:>10,} bytes")
