"""Transkripsi satu file audio → TXT (paragraf), SRT, dan JSON segmen."""

import argparse
import json
import os
import time

from faster_whisper import WhisperModel


def fmt_ts(t: float, sep: str = ",") -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("audio")
    p.add_argument("--outdir", default=".data/out")
    p.add_argument("--model", default="turbo")
    p.add_argument("--device", default="mps")
    p.add_argument("--compute", default="float16")
    p.add_argument("--lang", default="id")
    p.add_argument("--beam", type=int, default=1)
    a = p.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(a.audio))[0]

    t0 = time.time()
    model = WhisperModel(a.model, device=a.device, compute_type=a.compute, cpu_threads=8)
    print(f"[load] {time.time() - t0:.1f}s", flush=True)

    t1 = time.time()
    segments, info = model.transcribe(
        a.audio,
        language=a.lang,
        beam_size=a.beam,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,
    )

    rows = []
    for i, s in enumerate(segments, 1):
        rows.append({"id": i, "start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()})
        if i % 50 == 0:
            print(f"[progres] {i} segmen | audio {s.end / 60:.1f} mnt", flush=True)

    elapsed = time.time() - t1
    dur = rows[-1]["end"] if rows else 0.0

    # SRT
    with open(os.path.join(a.outdir, base + ".srt"), "w") as f:
        for r in rows:
            f.write(f"{r['id']}\n{fmt_ts(r['start'])} --> {fmt_ts(r['end'])}\n{r['text']}\n\n")

    # TXT berparagraf
    paras, cur = [], []
    for r in rows:
        cur.append(r["text"])
        if len(cur) >= 6:
            paras.append(" ".join(cur))
            cur = []
    if cur:
        paras.append(" ".join(cur))
    with open(os.path.join(a.outdir, base + ".txt"), "w") as f:
        f.write("\n\n".join(paras) + "\n")

    # JSON
    with open(os.path.join(a.outdir, base + ".json"), "w") as f:
        json.dump(
            {
                "file": os.path.basename(a.audio),
                "language": info.language,
                "language_prob": round(info.language_probability, 3),
                "duration_s": round(dur, 1),
                "engine": f"faster-whisper/{a.model}/{a.device}/{a.compute}",
                "asr_s": round(elapsed, 1),
                "rtf": round(dur / max(elapsed, 1e-9), 2),
                "segments": rows,
            },
            f,
            ensure_ascii=False,
            indent=1,
        )

    print(
        json.dumps(
            {
                "segments": len(rows),
                "audio_min": round(dur / 60, 1),
                "asr_min": round(elapsed / 60, 1),
                "rtf": round(dur / max(elapsed, 1e-9), 2),
                "lang": info.language,
                "lang_prob": round(info.language_probability, 3),
                "peak_rss_mb": round(__import__("resource").getrusage(__import__("resource").RUSAGE_SELF).ru_maxrss / 1e6),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
