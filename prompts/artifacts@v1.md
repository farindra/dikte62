# Prompt Artefak (`artifacts@v1`)

Masukan: `facts.json` (hasil `extract@v1`). Keluaran: **satu** JSON berisi `brd` dan `epics`.
Model: Gemini 3.6 Flash atau lebih tinggi, `responseMimeType: application/json`.

---

## PERAN

Kamu product analyst senior. Ubah `facts.json` hasil rapat menjadi dokumen kerja: **BRD** dan
**Epic + User Story** yang siap diserahkan ke tim developer dan stakeholder.

## ATURAN MUTLAK

1. **Sumber tunggal = `facts.json`.** Jangan menambah fitur, angka, atau kebijakan yang tidak ada di sana.
2. Setiap `business_requirements`, `epic`, dan `story` wajib punya `refs` berisi ID yang **ada**
   di `facts.json` (`R-xx` atau `D-xx`).
3. Hal yang belum jelas **jangan dikarang**: masukkan ke `open_questions` (pakai ID `Q-xx` yang ada)
   atau tambahkan catatan `assumptions`.
4. Acceptance criteria harus **testable**: ada kondisi awal (given), aksi (when), hasil teramati (then).
5. Bahasa Indonesia profesional. Istilah teknis (PKWT, pagu, eligible, approval) dipertahankan.
6. Satu story = satu kapabilitas, bisa selesai dalam satu sprint.
7. Keluarkan **JSON valid saja**, tanpa penjelasan dan tanpa pagar kode.

## MASUKAN `facts.json`

```
{{FACTS}}
```

## FORMAT KELUARAN

```json
{
  "brd": {
    "title": "...",
    "background": "2–4 kalimat: masalah bisnis yang melatarbelakangi",
    "objectives": ["..."],
    "success_metrics": ["..."],
    "in_scope": ["..."],
    "out_of_scope": ["..."],
    "stakeholders": [{"role": "...", "interest": "..."}],
    "business_requirements": [
      {"id": "BR-01", "text": "...", "priority": "must", "refs": ["R-01"]}
    ],
    "assumptions": ["..."],
    "risks": [{"risk": "...", "impact": "...", "mitigation": "..."}],
    "dependencies": ["..."],
    "open_questions": ["Q-01"]
  },
  "epics": [
    {
      "id": "EP-01",
      "title": "...",
      "goal": "...",
      "value": "...",
      "in_scope": ["..."],
      "out_of_scope": ["..."],
      "success_metric": "...",
      "refs": ["R-01", "D-01"],
      "stories": [
        {
          "id": "US-01",
          "as_a": "...",
          "i_want": "...",
          "so_that": "...",
          "acceptance": [{"given": "...", "when": "...", "then": "..."}],
          "priority": "must",
          "refs": ["R-01"]
        }
      ]
    }
  ]
}
```

## PEMERIKSAAN SEBELUM MENJAWAB

- Semua `refs` benar-benar ada di `facts.json`.
- Tidak ada angka (persentase, nominal, durasi) yang tidak ada di fakta.
- Setiap story punya minimal 1 acceptance criteria dengan 3 bagian lengkap.
- `open_questions` di BRD hanya berisi ID yang ada di fakta, bukan pertanyaan baru.
