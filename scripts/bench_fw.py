import argparse
import json
import resource
import time

from faster_whisper import WhisperModel

p = argparse.ArgumentParser()
p.add_argument("--model", default="small")
p.add_argument("--audio", required=True)
p.add_argument("--lang", default=None)
p.add_argument("--threads", type=int, default=8)
p.add_argument("--compute", default="int8")
p.add_argument("--vad", action="store_true")
p.add_argument("--beam", type=int, default=5)
p.add_argument("--device", default="cpu")
p.add_argument("--cpu_threads", type=int, default=8)
a = p.parse_args()

t0 = time.time()
m = WhisperModel(a.model, device=a.device, compute_type=a.compute, cpu_threads=a.cpu_threads)
t1 = time.time()
segments, info = m.transcribe(
    a.audio, language=a.lang, beam_size=a.beam, vad_filter=a.vad, condition_on_previous_text=False
)
segs = list(segments)
t2 = time.time()
dur = segs[-1].end if segs else 0.0
print(
    json.dumps(
        {
            "engine": "faster-whisper",
            "model": a.model,
            "compute": a.compute,
            "threads": a.cpu_threads,
            "beam": a.beam,
            "vad": a.vad,
            "lang_detected": info.language,
            "audio_s": round(dur, 1),
            "load_s": round(t1 - t0, 2),
            "asr_s": round(t2 - t1, 2),
            "rtf": round(dur / max(t2 - t1, 1e-9), 2),
            "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6),
            "segments": len(segs),
            "text_head": " ".join(s.text.strip() for s in segs)[:100],
        }
    )
)
