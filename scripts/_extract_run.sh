#!/usr/bin/env bash
# Jalankan ekstraksi fakta dengan fallback beberapa model bila 503/overload.
set -uo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

GLOSSARY="Rempoa = nama kantor cabang; PKWT/PKWTT = jenis kontrak kerja; plan cicilan = skema cicilan pembelian barang; eligible = memenuhi syarat. Catatan: istilah 'kelasi' belum pasti (kemungkinan 'kelas'/golongan karyawan). JANGAN dianggap nama jabatan; masukkan ke open_questions sebagai needs_confirmation."

for m in gemini-3.6-flash gemini-3.8-flash gemini-3.1-flash-lite; do
  echo "=== coba model: $m ==="
  if .venv/bin/python -u scripts/extract_facts.py \
      .data/out_full/transcript_glossary.txt \
      --out .data/facts.json \
      --model "$m" \
      --date 2026-11-20 \
      --project "Sistem HR internal (absensi, kontrak, pinjaman karyawan)" \
      --glossary "$GLOSSARY"; then
    echo "=== berhasil dengan $m ==="
    exit 0
  fi
  echo "=== gagal: $m ==="
done

echo "SEMUA MODEL GAGAL"
exit 1
