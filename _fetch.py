import os, time
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
from faster_whisper import WhisperModel
t0 = time.time()
print("fetching faster-whisper 'small' over plain HTTP ...", flush=True)
m = WhisperModel("small", device="cpu", compute_type="int8")
print(f"OK -- model ready in {time.time()-t0:.0f}s", flush=True)
from ffilm.voice import _model_cached
print("cached now? ->", _model_cached("small"), flush=True)
