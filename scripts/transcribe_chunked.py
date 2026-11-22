"""Transkripsi file panjang secara bertahap (chunk 5 menit) dengan model tetap ter-load.

Output ditulis inkremental agar progres tidak hilang bila proses dihentikan.
"""

import argparse
import json
import os
import subprocess
import time

from faster_whisper import WhisperModel


def fmt_ts(t: float, sep: str = ",") -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{int(round((s - int(s)) * 1000)):03d}"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("audio")
    p.add_argument("--outdir", default=".data/out")
    p.add_argument("--model", default="turbo")
    p.add_argument("--device", default="mps")
    p.add_argument("--compute", default="float16")
    p.add_argument("--lang", default="id")
    p.add_argument("--chunk", type=float, default=300.0)
    p.add_argument("--limit", type=int, default=0, help="batasi jumlah chunk (0 = semua)")
    a = p.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(a.audio))[0]

    probe = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", a.audio], capture_output=True, text=True
    )
    dur_line = [l for l in probe.stderr.splitlines() if "Duration" in l][0]
    hh, mm, ss = dur_line.split("Duration:")[1].split(",")[0].strip().split(":")
    total = int(hh) * 3600 + int(mm) * 60 + float(ss)
    print(f"[info] durasi {total:.0f}s | chunk {a.chunk:.0f}s", flush=True)

    t0 = time.time()
    model = WhisperModel(a.model, device=a.device, compute_type=a.compute, cpu_threads=8)
    print(f"[load] {time.time() - t0:.1f}s", flush=True)

    jsonl_path = os.path.join(a.outdir, base + ".segments.jsonl")
    open(jsonl_path, "w").close()

    offsets = [i * a.chunk for i in range(int(total // a.chunk) + 1)]
    if a.limit:
        offsets = offsets[: a.limit]

    total_asr = 0.0
    for idx, off in enumerate(offsets, 1):
        dur = min(a.chunk, total - off)
        if dur <= 1:
            continue
        wav = os.path.join("/tmp", f"dikte_chunk_{idx}.wav")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", str(off), "-t", str(dur),
             "-i", a.audio, "-ar", "16000", "-ac", "1", wav],
            check=True,
        )
        t1 = time.time()
        segments, info = model.transcribe(
            wav,
            language=a.lang,
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        n = 0
        with open(jsonl_path, "a") as f:
            for s in segments:
                n += 1
                f.write(
                    json.dumps(
                        {
                            "start": round(off + s.start, 2),
                            "end": round(off + s.end, 2),
                            "text": s.text.strip(),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        el = time.time() - t1
        total_asr += el
        print(
            f"[chunk {idx}/{len(offsets)}] {off/60:.0f}-{min(off+dur,total)/60:.0f} mnt "
            f"| {n} segmen | {el:.1f}s | RTF {dur/max(el,1e-9):.2f} | lang {info.language}",
            flush=True,
        )
        os.remove(wav)

    print(f"[selesai] total ASR {total_asr/60:.1f} mnt | RTF {total/max(total_asr,1e-9):.2f}", flush=True)


if __name__ == "__main__":
    main()
