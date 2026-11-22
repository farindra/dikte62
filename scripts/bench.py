import argparse
import json
import resource
import time

import whisper

p = argparse.ArgumentParser()
p.add_argument("--model", required=True)
p.add_argument("--audio", required=True)
p.add_argument("--lang", default=None)
p.add_argument("--device", default=None)
a = p.parse_args()

t0 = time.time()
m = whisper.load_model(a.model, device=a.device)
t1 = time.time()
r = m.transcribe(
    a.audio, language=a.lang, fp16=False, verbose=False, condition_on_previous_text=False
)
t2 = time.time()
dur = max((s["end"] for s in r["segments"]), default=0.0)
print(
    json.dumps(
        {
            "model": a.model,
            "device": str(m.device),
            "audio_s": round(dur, 1),
            "load_s": round(t1 - t0, 2),
            "asr_s": round(t2 - t1, 2),
            "rtf": round(dur / max(t2 - t1, 1e-9), 2),
            "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6),
            "segments": len(r["segments"]),
            "text_head": r["text"].strip()[:100],
        }
    )
)
