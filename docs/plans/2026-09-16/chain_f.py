import sys, subprocess, numpy as np
from pathlib import Path
sys.path.insert(0, r"C:\Users\jacek\code\ai-film-lab"); sys.path.insert(0, sys.argv[1])
from ffilm import audio, ingest
from measure import decode, SR
S = Path(sys.argv[1]); proj = Path(r"C:\Users\jacek\code\ai-film-lab\projects\I am not your fear")
src = proj/"media/rec_20260916-113221.mp4"
snd = ingest.sound_of(proj, "media/rec_20260916-113221.mp4"); tun = audio.tuning_for(snd["room_db"], snd["voice_db"])
base = audio.voiced_chain(1.0, True, tun)
def stats(name, chain):
    out = S / f"ab_{name}.wav"
    r = subprocess.run(["ffmpeg","-y","-v","error","-ss","20","-t","34","-i",str(src),"-vn","-filter:a",",".join(chain),"-ac","1","-c:a","pcm_s16le",str(out)],capture_output=True,text=True)
    if r.returncode: print(name, "ffmpeg error:", r.stderr[-300:]); return
    x = decode(str(out)); n=int(SR*0.05); m=len(x)//n; w=x[:m*n].reshape(m,n)
    L = 20*np.log10(np.sqrt((w**2).mean(axis=1))+1e-9); p90 = np.percentile(L,90)
    live = L[L > -75]; sp = np.flatnonzero(L > p90-8)
    seg = np.concatenate([x[i*n:(i+1)*n] for i in sp]); N=4096; k=len(seg)//N
    P=(np.abs(np.fft.rfft(seg[:k*N].reshape(k,N)*np.hanning(N),axis=1))**2).mean(axis=0); f=np.fft.rfftfreq(N,1/SR)
    def band(a,b): return 10*np.log10(P[(f>=a)&(f<b)].sum()/P.sum())
    crest = 20*np.log10(np.abs(x).max()/ (np.sqrt((seg**2).mean())+1e-9))
    print(f"  {name:18s} floor {np.percentile(live,5):6.1f}  p50 {np.percentile(L,50):6.1f} p90 {p90:6.1f}  crest {crest:4.1f}  bands: 100-300 {band(100,300):5.1f}  300-1k {band(300,1000):5.1f}  1-3k {band(1000,3000):5.1f}  3-6k {band(3000,6000):5.1f}  6-10k {band(6000,10000):5.1f}")
    subprocess.run(["ffmpeg","-y","-v","error","-ss","6","-t","12","-i",str(out),"-c:a","pcm_s16le",str(S/f"listen_{name}.wav")])
print("34s excerpt, take 20-54s; bands are dB relative to the speech's own total")
stats("A_current", base)
stats("G_warmer_only", base + ["lowshelf=f=180:g=2", "equalizer=f=3200:width_type=q:w=1.0:g=2.0", "highshelf=f=9000:g=-2.5"])
stats("Gplus", base + ["lowshelf=f=180:g=2", "equalizer=f=3500:width_type=q:w=1:g=4", "highshelf=f=9000:g=-2.5"])
stats("Gplus_deess", base + ["lowshelf=f=180:g=2", "equalizer=f=3500:width_type=q:w=1:g=4", "highshelf=f=9000:g=-2.5", "deesser=i=0.3"])
