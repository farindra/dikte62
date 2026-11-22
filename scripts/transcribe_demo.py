import sys
import time

from faster_whisper import WhisperModel

audio = sys.argv[1]
out = sys.argv[2]
model_name = sys.argv[3] if len(sys.argv) > 3 else "turbo"
lang = sys.argv[4] if len(sys.argv) > 4 else "id"
device = sys.argv[5] if len(sys.argv) > 5 else "mps"
compute = sys.argv[6] if len(sys.argv) > 6 else "float16"

t0 = time.time()
try:
    m = WhisperModel(model_name, device=device, compute_type=compute, cpu_threads=8)
except Exception as e:  # noqa: BLE001
    print("fallback model id:", e, flush=True)
    m = WhisperModel(
        "deepdml/faster-whisper-large-v3-turbo-ct2",
        device=device,
        compute_type=compute,
        cpu_threads=8,
    )
print(f"loaded in {time.time() - t0:.1f}s", flush=True)

t1 = time.time()
segments, info = m.transcribe(
    audio,
    language=lang,
    beam_size=1,
    vad_filter=True,
    condition_on_previous_text=False,
)
lines = []
for s in segments:
    line = f"[{s.start:07.2f} -> {s.end:07.2f}] {s.text.strip()}"
    lines.append(line)
    print(line, flush=True)
elapsed = time.time() - t1
dur = segments and 0 or 0
with open(out, "w") as f:
    f.write("\n".join(lines) + "\n")
print(f"\n=== ASR {elapsed:.1f}s | audio {float(sys.argv[7]) if len(sys.argv) > 7 else 0}s ===", flush=True)
print("\nFULL TEXT:\n" + " ".join(l.split("] ", 1)[1] for l in lines), flush=True)
