"""Whole-take sound measurement: per-15s blocks and band-split spectrum of pauses vs speech."""
import subprocess, sys, numpy as np
SR = 44100
def decode(path, ss=None, t=None):
    cmd = ["ffmpeg", "-v", "error"]
    if ss is not None: cmd += ["-ss", str(ss)]
    cmd += ["-i", path]
    if t is not None: cmd += ["-t", str(t)]
    cmd += ["-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)
def db(x): return 20*np.log10(max(float(x), 1e-9))
def rms_windows(x, win=0.05):
    n = int(SR*win); m = len(x)//n
    w = x[:m*n].reshape(m, n)
    return np.sqrt((w**2).mean(axis=1)), n
def bands(x):
    # mean power spectrum over 4096-sample frames, then band sums in dB
    n = 4096; m = len(x)//n
    if m == 0: return {}
    fr = x[:m*n].reshape(m, n) * np.hanning(n)
    P = (np.abs(np.fft.rfft(fr, axis=1))**2).mean(axis=0)
    f = np.fft.rfftfreq(n, 1/SR)
    edges = [(0,120),(120,300),(300,1000),(1000,3000),(3000,6000),(6000,12000),(12000,22050)]
    tot = P.sum()
    return {f"{a}-{b}": 10*np.log10(P[(f>=a)&(f<b)].sum()/tot + 1e-12) for a,b in edges}
def report(path, label, block=15.0):
    x = decode(path)
    if len(x) == 0: print(label, "NO AUDIO"); return
    lv, n = rms_windows(x)
    lvdb = 20*np.log10(lv+1e-9)
    p10, p90 = np.percentile(lvdb, 10), np.percentile(lvdb, 90)
    line = p10 + (p90-p10)*0.35
    print(f"\n== {label}  ({len(x)/SR:.1f}s)  whole: p10 {p10:.1f}  p50 {np.percentile(lvdb,50):.1f}  p90 {p90:.1f}  split {line:.1f}")
    per = int(block/0.05)
    rows = []
    for b in range(0, len(lvdb), per):
        seg = lvdb[b:b+per]
        rows.append((b*0.05, np.percentile(seg,10), np.percentile(seg,50), np.percentile(seg,90), (seg<line).mean()*100))
    print("  block  p10    p50    p90   %pause")
    for t,a,c,d,pp in rows: print(f"  {t:5.0f} {a:6.1f} {c:6.1f} {d:6.1f} {pp:5.0f}")
    p10s = [r[1] for r in rows]
    print(f"  worst block p10 {max(p10s):.1f}  best {min(p10s):.1f}  spread {max(p10s)-min(p10s):.1f}")
    # spectrum of pause windows vs speech windows
    idx_p = np.flatnonzero(lvdb < line); idx_s = np.flatnonzero(lvdb > p90-6)
    def gather(idx):
        return np.concatenate([x[i*n:(i+1)*n] for i in idx]) if len(idx) else np.zeros(0, np.float32)
    bp, bs = bands(gather(idx_p)), bands(gather(idx_s))
    print("  band       pause   speech  (dB rel. to own total)")
    for k in bp: print(f"  {k:12s} {bp[k]:6.1f}  {bs.get(k,0):6.1f}")
    print(f"  pause abs level {db(np.sqrt((gather(idx_p)**2).mean())):.1f} dBFS over {len(idx_p)*0.05:.0f}s; speech abs {db(np.sqrt((gather(idx_s)**2).mean())):.1f} over {len(idx_s)*0.05:.0f}s")
if __name__ == "__main__":
    for i in range(1, len(sys.argv), 2): report(sys.argv[i], sys.argv[i+1])
