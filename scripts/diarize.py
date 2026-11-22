"""Diarisasi speaker sederhana: embedding ECAPA per segmen + clustering.

Pendekatan ini dipilih karena tidak butuh token HF (model pyannote gated) dan
ringan di CPU: ECAPA-TDNN 192 dimensi, ±30 ms per segmen 3 detik.

Keterbatasan yang disadari: tanpa diarisasi frame-level, tumpang tindih pembicara
dan segmen sangat pendek masih sulit. Hasilnya dipakai sebagai *petunjuk* label
(S1/S2/...), bukan kebenaran mutlak.
"""

import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import platform_support  # noqa: E402,F401  (stdout UTF-8 + cache default)

import argparse
import json
import os
import sys
import subprocess
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from platform_support import ffmpeg_bin  # noqa: E402

import numpy as np
import soundfile as sf
import torch
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from speechbrain.inference.speaker import EncoderClassifier

SR = 16000
MIN_DUR = 0.5


def load_audio(path: str) -> np.ndarray:
    tmpdir = os.environ.get("TEMP") or os.environ.get("TMPDIR") or "/tmp"
    wav = os.path.join(tmpdir, f"dikte_diarize_{os.getpid()}.wav")
    subprocess.run(
        [ffmpeg_bin(), "-v", "error", "-y", "-i", path, "-ar", str(SR), "-ac", "1", wav],
        check=True,
    )
    data, sr = sf.read(wav, dtype="float32")
    os.remove(wav)
    assert sr == SR
    return data


def embed(enc, audio: np.ndarray, start: float, end: float) -> np.ndarray:
    a = max(0, int(start * SR))
    b = min(len(audio), int(end * SR))
    seg = audio[a:b]
    if len(seg) < int(0.3 * SR):
        return None
    with torch.no_grad():
        e = enc.encode_batch(torch.from_numpy(seg).unsqueeze(0)).squeeze().cpu().numpy()
    n = np.linalg.norm(e)
    return e / n if n > 0 else None


def smooth(labels: list[int], window: int = 2) -> list[int]:
    out = labels[:]
    for i, cur in enumerate(labels):
        neigh = labels[max(0, i - window): i + window + 1]
        counts = {}
        for n in neigh:
            counts[n] = counts.get(n, 0) + 1
        best = max(counts, key=counts.get)
        if best != cur and counts[best] >= 3:
            out[i] = best
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("audio")
    p.add_argument("transcript")
    p.add_argument("-o", "--out", default="")
    p.add_argument("--min-speakers", type=int, default=2)
    p.add_argument("--max-speakers", type=int, default=6)
    a = p.parse_args()

    t0 = time.time()
    data = json.load(open(a.transcript, encoding="utf-8"))
    segs = data.get("segments_data") or data.get("segments") or []
    print(f"[info] {len(segs)} segmen | memuat audio…", flush=True)
    audio = load_audio(a.audio)
    print(f"[info] audio {len(audio)/SR/60:.1f} menit dimuat", flush=True)

    enc = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=".cache/speechbrain",
        run_opts={"device": "cpu"},  # MPS menghasilkan embedding rusak (cluster degenerate)
    )

    embs, idx = [], []
    t1 = time.time()
    for i, s in enumerate(segs):
        if (s["end"] - s["start"]) < MIN_DUR:
            continue
        e = embed(enc, audio, s["start"], s["end"])
        if e is not None:
            embs.append(e)
            idx.append(i)
        if (i + 1) % 100 == 0:
            print(f"  embedding {i+1}/{len(segs)}…", flush=True)
    X = np.vstack(embs)
    print(f"[info] {len(X)} embedding | {time.time()-t1:.1f}s", flush=True)

    best_k, best_labels, best_score = 2, None, -1.0
    for k in range(a.min_speakers, min(a.max_speakers, max(2, len(X) // 8)) + 1):
        lab = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(X)
        if len(set(lab)) < 2:
            continue
        score = silhouette_score(X, lab, metric="cosine")
        print(f"  k={k} silhouette={score:.3f}", flush=True)
        if score > best_score:
            best_k, best_labels, best_score = k, lab, score
    print(f"[info] speaker terpilih: {best_k} (silhouette {best_score:.3f})", flush=True)

    # pusat cluster → label untuk semua segmen (termasuk yang pendek)
    centroids = np.vstack([X[best_labels == c].mean(axis=0) for c in range(best_k)])
    centroids /= np.linalg.norm(centroids, axis=1, keepdims=True)
    labels_all = [None] * len(segs)
    for pos, i in enumerate(idx):
        labels_all[i] = int(best_labels[pos])
    for i, s in enumerate(segs):
        if labels_all[i] is not None:
            continue
        e = embed(enc, audio, s["start"], s["end"])
        if e is None:
            labels_all[i] = labels_all[i - 1] if i else 0
        else:
            labels_all[i] = int(np.argmax(centroids @ e))

    raw = [(-1 if x is None else x) for x in labels_all]
    raw = [x if x >= 0 else 0 for x in raw]
    sm = smooth(raw)

    # nomori ulang berdasarkan kemunculan pertama
    order, mapping = [], {}
    for x in sm:
        if x not in mapping:
            mapping[x] = f"S{len(order)+1}"
            order.append(x)
    names = [mapping[x] for x in sm]

    dur = {}
    for s, n in zip(segs, names):
        dur[n] = dur.get(n, 0) + (s["end"] - s["start"])

    for s, n in zip(segs, names):
        s["speaker"] = n
    data["segments_data"] = segs
    data["speakers"] = {n: round(d, 1) for n, d in dur.items()}
    data["diarization"] = {
        "method": "ecapa-embeddings+agglomerative",
        "k": best_k,
        "silhouette": round(best_score, 3),
        "segments_embedded": len(X),
    }

    out = a.out or a.transcript.replace(".json", "_speakers.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    total = sum(dur.values()) or 1
    print(f"[ok] {out}")
    for n, d in sorted(dur.items()):
        print(f"  {n}: {d/60:5.1f} mnt ({100*d/total:4.1f}%)")
    print(f"[waktu] total {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
