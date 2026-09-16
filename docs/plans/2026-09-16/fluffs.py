import sys, json
from pathlib import Path
sys.path.insert(0, r"C:\Users\jacek\code\ai-film-lab")
from ffilm.spec import Film
proj = Path(r"C:\Users\jacek\code\ai-film-lab\projects\I am not your fear")
film = Film.load(proj / "film.yaml")
tr = json.load(open(proj/"analysis/transcript.json", encoding="utf-8"))["sources"][0]["lines"]
tot = 0; screen = 0; rows = []
for s in film.shots:
    if s.kind != "video": continue
    tin, tout = s.tin, s.tin + s.duration*s.speed
    said = [l for l in tr if min(l["end"], tout) - max(l["start"], tin) > 0.2]
    if not said:
        rows.append((s.id, tin, tout, s.duration)); screen += s.duration
    tot += s.duration
print("shots with speech but no transcript line (re-reads / outtakes):")
for r in rows: print(f"  {r[0]}  take {r[1]:6.1f}-{r[2]:6.1f}  {r[3]:5.1f}s on screen")
print(f"  {screen:.1f}s of {film.duration:.1f}s = {100*screen/film.duration:.0f}% of the film")
