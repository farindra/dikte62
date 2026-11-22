"""Transkripsi rapat panjang yang tahan terhadap mode kegagalan Whisper.

Tiga masalah nyata yang ditangani (semua terbukti pada rekaman uji):
1. Decoder kadang keluar teks sampah ("!!!!!").
2. Pada MPS, kualitas turun drastis setelah ±4 panggilan dalam satu proses.
3. Bagian sunyi/noise memicu halusinasi.

Strategi: satu jendela = satu proses baru, filter keluaran degeneratif, retry
dengan jendela digeser + temperature lebih tinggi, lalu tandai bagian yang
benar-benar tidak bisa dipulihkan sebagai "[tidak jelas]".
"""

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import time

ALLOWED_PUNCT = set(" .,?!'-:;\"()/")
HERE = os.path.dirname(os.path.abspath(__file__))


def is_degenerate(text: str) -> bool:
    t = text.strip()
    if len(t) < 2:
        return True
    non_alnum = sum(1 for c in t if not c.isalnum()) / max(len(t), 1)
    if non_alnum > 0.35:
        return True
    if re.search(r"(.)\1{7,}", t):
        return True
    return False


def quality(rows) -> tuple[int, int]:
    """(jumlah segmen baik, jumlah karakter baik)."""
    good = [r for r in rows if not is_degenerate(r["text"])]
    return len(good), sum(len(r["text"]) for r in good)


def fmt_ts(t: float, sep: str = ",") -> str:
    h, rem = divmod(max(t, 0.0), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{int(round((s - int(s)) * 1000)):03d}"


def probe_duration(path: str) -> float:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", path], capture_output=True, text=True)
    line = [l for l in out.stderr.splitlines() if "Duration" in l][0]
    hh, mm, ss = line.split("Duration:")[1].split(",")[0].strip().split(":")
    return int(hh) * 3600 + int(mm) * 60 + float(ss)


def run_window(args, start: float, dur: float, temp: float, tag: str):
    out = f"/tmp/dikte_win_{tag}.json"
    cmd = [
        sys.executable, os.path.join(HERE, "_transcribe_one.py"),
        "--audio", args.audio, "--start", f"{start:.3f}", "--dur", f"{dur:.3f}",
        "--out", out, "--model", args.model, "--device", args.device,
        "--compute", args.compute, "--lang", args.lang, "--temp", f"{temp}",
    ]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.returncode != 0 or not os.path.exists(out):
        return [], time.time() - t0, (r.stderr or "")[-300:]
    data = json.load(open(out))
    os.remove(out)
    return data.get("segments", []), time.time() - t0, ""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("audio")
    p.add_argument("--outdir", default=".data/out")
    p.add_argument("--model", default="turbo")
    p.add_argument("--device", default="mps")
    p.add_argument("--compute", default="float16")
    p.add_argument("--lang", default="id")
    p.add_argument("--window", type=float, default=90.0)
    p.add_argument("--limit-seconds", type=float, default=0.0)
    p.add_argument("--from-seconds", type=float, default=0.0)
    a = p.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(a.audio))[0]

    # Serialisasi: dua proses ASR bersamaan di MPS menghasilkan teks sampah.
    lock = open("/tmp/dikte_asr.lock", "w")
    fcntl.flock(lock, fcntl.LOCK_EX)

    total = probe_duration(a.audio)
    end_limit = min(total, a.limit_seconds) if a.limit_seconds else total
    print(f"[info] durasi proses {a.from_seconds:.0f}–{end_limit:.0f}s | model {a.model}/{a.device} | jendela {a.window:.0f}s", flush=True)

    offsets = []
    off = a.from_seconds
    while off < end_limit - 2:
        offsets.append(off)
        off += a.window

    rows, report, asr_total = [], [], 0.0
    for idx, off in enumerate(offsets, 1):
        dur = min(a.window, end_limit - off)
        segs, el, err = run_window(a, off, dur, 0.0, f"w{idx}")
        asr_total += el
        n_good, chars = quality(segs)
        status = "ok"

        if n_good == 0 or chars < dur * 1.5:
            best, best_q = segs, (n_good, chars)
            for shift, temp in ((-15.0, 0.4), (15.0, 0.4), (-30.0, 0.6)):
                soff = max(0.0, off + shift)
                sdur = min(a.window, end_limit - soff)
                if sdur < 10:
                    continue
                cand, el2, err2 = run_window(a, soff, sdur, temp, f"w{idx}s{int(shift)}")
                asr_total += el2
                cand = [r for r in cand if r["start"] >= off - 2 and r["end"] <= off + dur + 2]
                q = quality(cand)
                if q > best_q:
                    best, best_q = cand, q
                    status = f"retry(shift={shift:+.0f},temp={temp})"
            segs = best

        good = [r for r in segs if not is_degenerate(r["text"])]
        if not good and dur > 60:
            halves = []
            for h_off in (off, off + dur / 2):
                h_dur = min(dur / 2, end_limit - h_off)
                if h_dur < 20:
                    continue
                segs2, el2, _ = run_window(a, h_off, h_dur, 0.0, f"w{idx}h{int(h_off)}")
                asr_total += el2
                halves.extend([r for r in segs2 if not is_degenerate(r["text"])])
            if halves:
                good = halves
                status = "split"
        if not good:
            good = [{
                "start": round(off, 2),
                "end": round(off + dur, 2),
                "text": f"[tidak jelas {fmt_ts(off, '.')[:8]}–{fmt_ts(off + dur, '.')[:8]}]",
            }]
            status = "gagal"

        rows.extend(good)
        report.append({"window": idx, "start": round(off, 1), "end": round(off + dur, 1),
                       "status": status, "segments": len(good), "seconds": round(el, 1)})
        print(f"[win {idx}/{len(offsets)}] {off/60:5.1f}-{min(off+dur,end_limit)/60:5.1f} mnt | {len(good):3d} seg | {el:5.1f}s | {status}", flush=True)

    rows.sort(key=lambda r: r["start"])
    with open(os.path.join(a.outdir, base + ".srt"), "w") as f:
        for i, r in enumerate(rows, 1):
            f.write(f"{i}\n{fmt_ts(r['start'])} --> {fmt_ts(r['end'])}\n{r['text']}\n\n")

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

    span = end_limit - a.from_seconds
    with open(os.path.join(a.outdir, base + ".json"), "w") as f:
        json.dump({
            "file": os.path.basename(a.audio),
            "engine": f"faster-whisper/{a.model}/{a.device}/{a.compute}",
            "window_s": a.window,
            "audio_s": round(span, 1),
            "asr_s": round(asr_total, 1),
            "rtf": round(span / max(asr_total, 1e-9), 2),
            "segments": len(rows),
            "unclear": sum(1 for r in rows if r["text"].startswith("[tidak jelas")),
            "windows": report,
            "segments_data": rows,
        }, f, ensure_ascii=False, indent=1)

    unclear = [r for r in rows if r["text"].startswith("[tidak jelas")]
    print(json.dumps({
        "segments": len(rows), "unclear_ranges": len(unclear),
        "audio_min": round(span / 60, 1), "asr_min": round(asr_total / 60, 1),
        "rtf": round(span / max(asr_total, 1e-9), 2),
    }), flush=True)


if __name__ == "__main__":
    main()
