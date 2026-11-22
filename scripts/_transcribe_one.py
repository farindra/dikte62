"""Transkripsi SATU jendela dalam proses terpisah.

Dipisah karena ditemukan bug: pada MPS, kualitas decoder menurun drastis setelah
±4 panggilan `transcribe()` dalam satu proses (panggilan ke-5 menghasilkan
"!!!!!!" bahkan untuk audio yang sebelumnya benar). Proses baru per jendela
menghilangkan efek itu; biaya load model ±4–5 detik.
"""

import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import platform_support  # noqa: E402,F401  (stdout UTF-8 + cache default)

import argparse
import json
import os
import subprocess
import sys

from faster_whisper import WhisperModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from platform_support import detect_device, ffmpeg_bin  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--audio", required=True)
    p.add_argument("--start", type=float, required=True)
    p.add_argument("--dur", type=float, required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--model", default="turbo")
    p.add_argument("--device", default="auto")
    p.add_argument("--compute", default="")
    p.add_argument("--lang", default="id")
    p.add_argument("--temp", type=float, default=0.0)
    a = p.parse_args()

    a.device, a.compute = detect_device(a.device, a.compute)
    tmpdir = os.environ.get("TEMP") or os.environ.get("TMPDIR") or "/tmp"
    wav = os.path.join(tmpdir, f"dikte_one_{os.getpid()}.wav")
    subprocess.run(
        [ffmpeg_bin(), "-v", "error", "-y", "-ss", f"{a.start:.3f}", "-t", f"{a.dur:.3f}",
         "-i", a.audio, "-ar", "16000", "-ac", "1", wav],
        check=True,
    )

    model = WhisperModel(a.model, device=a.device, compute_type=a.compute, cpu_threads=4)
    segs, info = model.transcribe(
        wav,
        language=a.lang,
        beam_size=1,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,
        temperature=a.temp,
        compression_ratio_threshold=2.4,
        log_prob_threshold=-1.0,
        no_speech_threshold=0.8,
    )
    rows = [
        {
            "start": round(a.start + s.start, 2),
            "end": round(a.start + s.end, 2),
            "text": s.text.strip(),
        }
        for s in segs
    ]
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"language": info.language, "segments": rows}, f, ensure_ascii=False)
    os.remove(wav)


if __name__ == "__main__":
    main()
