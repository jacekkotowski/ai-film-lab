import sys, subprocess, numpy as np
from pathlib import Path
sys.path.insert(0, r"C:\Users\jacek\code\ai-film-lab"); sys.path.insert(0, sys.argv[1])
from ffilm.spec import Film
from ffilm.audio import build_soundtrack
from measure import decode, SR
S = Path(sys.argv[1]); proj = Path(r"C:\Users\jacek\code\ai-film-lab\projects\I am not your fear")
film = Film.load(proj / "film.yaml"); film.keep_clip_audio = False; film.loudness = 0
build_soundtrack(film, S / "silent.mp4", S / "music_only.mp4", fps=24, quiet=True)
x = decode(str(S / "music_only.mp4"))
n = int(SR*0.25); m = len(x)//n; L = 20*np.log10(np.sqrt((x[:m*n].reshape(m,n)**2).mean(axis=1))+1e-9)
print(f"music-only bed, {len(x)/SR:.1f}s, median {np.median(L):.1f} dBFS")
quiet = L < -50
runs=[]; i=0
while i < len(L):
    if quiet[i]:
        j=i
        while j < len(L) and quiet[j]: j+=1
        runs.append((i*0.25, j*0.25)); i=j
    else: i+=1
print("stretches of music below -50 dBFS:", [(round(a,2), round(b,2)) for a,b in runs])
print("around the seam 192..199 (0.25s RMS):")
for i in range(int(192/0.25), int(199/0.25), 4): print(f"  {i*0.25:6.2f}", np.round(L[i:i+4],1))
for f in [r"C:\Users\jacek\code\ai-film-lab\projects\I am not your fear\music\Stellardrone - Light Years - 01 Red Giant.mp3", r"C:\Users\jacek\code\ai-film-lab\library\music\tibetan_cafe.m4a"]:
    r = subprocess.run(["ffmpeg","-hide_banner","-nostats","-i",f,"-af","ebur128=framelog=quiet","-f","null","-"],capture_output=True,text=True,errors="replace")
    I = [l.strip() for l in r.stderr.splitlines() if l.strip().startswith("I:")]
    print(Path(f).name, I[-1] if I else "?")
