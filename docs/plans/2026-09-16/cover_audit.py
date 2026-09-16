import sys, os
from pathlib import Path
sys.path.insert(0, r"C:\Users\jacek\code\ai-film-lab")
from ffilm import cover, library
from ffilm.spec import headers, title_of
from PIL import Image
S = Path(sys.argv[1])
print("library root:", library.root(), "enabled:", library.enabled())
for p in library.backdrops(): 
    with Image.open(p) as im: print("  shelf:", p.name, im.size, "wide" if library.is_wide(p) else "tall")
print("shelf pick wide:", library.backdrop(True), " tall:", library.backdrop(False))
root = Path(r"C:\Users\jacek\code\ai-film-lab\projects")
cases = ["I am not your fear", "I love you", "Prayer for Her", "Night_2026-09-05_2", "Morning 2026-09-15"]
nocover = S / "No Cover Folder"; nocover.mkdir(exist_ok=True)
(nocover / "film.yaml").write_text("resolution: [1080, 1920]\nshots: []\n", encoding="utf-8")
for name in cases + [str(nocover)]:
    proj = root / name if name in cases else Path(name)
    own = cover.find_image(proj)
    hdr = headers(proj / "film.yaml")
    res = hdr.get("resolution", [1920, 1080]); wide = res[0] >= res[1]
    back = cover.choose(proj, wide=wide)
    title = cover.title_from(back, None, proj)
    dims = None
    if back.path:
        with Image.open(back.path) as im: dims = im.size
    print(f"\n{proj.name}: res {res} cover/ exists={cover.cover_dir(proj).is_dir()} own={own.name if own else None}")
    print(f"   chose {back.path.name if back.path else None} shared={back.shared} dims={dims}  title={title!r}  yaml title={hdr.get('title')!r}")
    print(f"   is_stale={cover.is_stale(proj)}  out/cover.jpg exists={cover.out_path(proj).exists()}  card exists={cover.card_path(proj).exists()}")
    if back.path:
        import cv2
        frame = cover.compose(back.path, title, res[0], res[1], "bottom", None)
        cv2.imwrite(str(S / f"cover_{proj.name.replace(' ','_')}.jpg"), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
