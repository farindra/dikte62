# Spek Produk v0.2 — "Dikte": Meeting → Artefak Kerja

**Status:** draft · **Tanggal:** 22 Nov 2026
**Perubahan arah:** dari *transcription tool* menjadi *meeting intelligence pipeline* untuk Team Lead IT.
**Dokumen pendahulu:** [analisa-kebutuhan.md](./analisa-kebutuhan.md) (detail ASR, model, packaging macOS)

---

## 0. Ringkasan

Kebutuhan nyata pengguna bukan "teks rapat", tapi **hasil kerja setelah rapat**: catatan keputusan,
action item, dan dokumen yang bisa langsung diserahkan ke developer/stakeholder (BRD, Epic, PRD,
user story). Saat ini alur itu dikerjakan manual: rekam → upload ke NotebookLM → baca ringkasan →
tulis ulang jadi dokumen. Dua langkah terakhir memakan waktu dan tidak menghasilkan struktur yang
bisa di-*import* ke Jira.

**Posisi produk:** menggantikan kombinasi *perekam + NotebookLM + penulisan dokumen manual*,
dengan satu perbedaan kunci — **output-nya terstruktur, tersitasi ke transkrip, dan siap diimpor
ke tool manajemen kerja**, bukan sekadar ringkasan prosa.

**Prinsip desain yang tidak boleh dilanggar:**

1. **Evidence-first.** Setiap keputusan, requirement, dan user story wajib menunjuk ke timestamp +
   pembicara di transkrip. Tanpa bukti → masuk ke daftar "Perlu konfirmasi", bukan dikarang.
2. **Human-in-the-loop.** Tidak ada dokumen yang terkirim ke stakeholder tanpa kamu review & approve.
3. **Schema sebagai sumber kebenaran.** LLM menghasilkan JSON tervalidasi; Markdown/DOCX/Jira
   hanyalah render dari JSON itu. Ini yang membuat output konsisten dan bisa di-*re-generate*.
4. **Privasi berlapis.** ASR selalu lokal. Tahap generasi bisa cloud atau lokal, dipilih per
   proyek/rapat — rapat sensitif tidak boleh dipaksa ke cloud.

---

## 1. Job-to-be-done (Lead IT, harian)

| # | Situasi | Yang diinginkan | Ukuran sukses |
|---|---|---|---|
| J1 | 3–5 meeting/hari (standup, 1:1, requirement gathering, vendor) | Rekap otomatis tanpa menulis manual | Waktu recap/meeting turun dari ±30 mnt → ≤5 mnt |
| J2 | Requirement gathering dengan user/stakeholder | Draft BRD/PRD yang bisa diedit | Draft mencakup ≥80% keputusan yang benar-benar dibahas |
| J3 | Ide fitur muncul di meeting | Epic + user story dengan acceptance criteria | Story lolos "Definition of Ready" tanpa ditulis ulang |
| J4 | Banyak action item tersebar | Satu tracker lintas meeting, tidak ada yang hilang | 0 action item hilang; carry-over terdeteksi |
| J5 | Butuh jawab "kenapa dulu kita putuskan ini?" | Decision log yang bisa dicari + bukti | Ketemu < 1 menit |
| J6 | Rapat sensitif (HR, legal, vendor pricing) | Tidak boleh keluar dari laptop | Mode lokal penuh, terverifikasi 0 request |

---

## 2. Pipeline end-to-end

```
[1] CAPTURE            [2] ASR                    [3] EXTRACT                [4] SYNTHESIZE
 mic / system audio ──► whisper (lokal)  ──────►  map-reduce per chunk  ──►  meeting note
 atau file Zoom/Meet   + VAD                      (fakta, keputusan,        (terstruktur,
      /Teams          + diarisasi speaker          angka, istilah,           tersitasi)
                      + koreksi glosarium          open question)
                                                                                    │
                                                                                    ▼
[7] EXPORT            [6] REVIEW                 [5] GENERATE ARTIFACT
 MD/DOCX/Confluence ◄── editor + sitasi +  ◄────  BRD · Epic · PRD · User Story
 /Jira CSV /Linear     approve gate               (JSON schema → render)
        │
        ▼
[8] MEMORY: library proyek, carry-over open item, decision log, digest mingguan
```

**Kenapa multi-pass, bukan satu prompt besar?** Satu prompt "buat PRD dari transkrip 1 jam"
menghasilkan dokumen dangkal dan rawan halusinasi: model kehabisan perhatian di tengah transkrip
dan mengarang bagian yang kosong. Ekstraksi fakta per chunk lalu sintesis (pola map-reduce)
memaksa setiap pernyataan punya sumber, dan bagian yang tidak dibahas menjadi *gap* yang eksplisit.

---

## 3. Kebutuhan fungsional per tahap

### 3.1 Capture
| ID | Kebutuhan | Prioritas |
|---|---|---|
| CP-01 | Impor rekaman hasil Zoom/Meet/Teams (m4a/mp4/mp3/wav) | P0 |
| CP-02 | Rekam mikrofon dalam app (16 kHz mono) dengan indikator level | P1 |
| CP-03 | Rekam system audio (ScreenCaptureKit) — menangkap semua peserta | P1 |
| CP-04 | Auto-import dari folder watch (mis. folder unduhan Zoom) | P2 |
| CP-05 | Notifikasi consent: pengingat mengumumkan perekaman + banner saat merekam | P0 |

### 3.2 ASR + diarisasi
| ID | Kebutuhan | Prioritas |
|---|---|---|
| AS-01 | Transkripsi ID/EN + deteksi bahasa per segmen (bukan hanya per file) | P0 |
| AS-02 | Segmentasi per pembicara (S1/S2/…), rename manual, simpan pemetaan suara→nama | P0 |
| AS-03 | Timestamp per segmen + word-level untuk fitur "klik untuk dengar" | P0 |
| AS-04 | Glosarium proyek (nama orang, produk, akronim) untuk koreksi otomatis pasca-ASR | P1 |
| AS-05 | Deteksi & buang sunyi/musik (VAD) untuk cegah halusinasi | P0 |
| AS-06 | Rekaman panjang (>1 jam) diproses bertahap, progres tersimpan, bisa dilanjutkan | P0 |

### 3.3 Ekstraksi & catatan rapat
| ID | Kebutuhan | Prioritas |
|---|---|---|
| EX-01 | Ekstrak **keputusan** (apa, oleh siapa, kapan) + sitasi | P0 |
| EX-02 | Ekstrak **action item** (task, owner, due date, status) — owner ditandai "terduga" bila tidak eksplisit | P0 |
| EX-03 | Ekstrak **open question / gap** yang tidak terjawab di rapat | P0 |
| EX-04 | Ekstrak **kebutuhan** (functional & non-functional) dengan prioritas & rasional | P0 |
| EX-05 | Ekstrak risiko, asumsi, ketergantungan, dan angka/anggaran yang disebut | P1 |
| EX-06 | Ringkasan naratif 5–10 baris + TL;DR 3 bullet | P0 |
| EX-07 | Tandai momen penting (keputusan, konflik, perubahan scope) untuk navigasi cepat | P2 |

### 3.4 Generasi artefak
| ID | Kebutuhan | Prioritas |
|---|---|---|
| AR-01 | **Epic** dari topik/keputusan rapat: goal, value, scope, dependencies, success metric | P0 |
| AR-02 | **User story** + acceptance criteria Gherkin (Given/When/Then), INVEST, siap masuk Jira | P0 |
| AR-03 | **BRD**: konteks bisnis, tujuan, in/out scope, stakeholder, kebutuhan bisnis, risiko | P1 |
| AR-04 | **PRD**: problem, goals/non-goals, persona, alur, FR/NFR, edge case, metrik, release criteria | P1 |
| AR-05 | Tiap item membawa sitasi `[12:34, S2]` yang bisa diklik ke transkrip | P0 |
| AR-06 | Tiap artefak punya halaman "**Perlu konfirmasi**" berisi asumsi & pertanyaan untuk stakeholder | P0 |
| AR-07 | Template artefak bisa diedit pengguna (field wajib, gaya bahasa, istilah perusahaan) | P1 |
| AR-08 | Regenerate sebagian (mis. "perbaiki acceptance criteria saja") tanpa mengulang ASR | P1 |
| AR-09 | Versi artefak (v1, v2, …), diff antar versi, catat model+prompt yang dipakai | P1 |
| AR-10 | Tampilkan tingkat keyakinan per item (tinggi/sedang/rendah) berdasarkan kekuatan bukti | P2 |

### 3.5 Review & ekspor
| ID | Kebutuhan | Prioritas |
|---|---|---|
| RV-01 | Layar review dua panel: transkrip (kiri) ↔ artefak (kanan), sinkron saat item dipilih | P0 |
| RV-02 | Edit inline semua field; tambah/hapus item; ubah prioritas | P0 |
| RV-03 | Approve per artefak → status draft/approved, tercatat siapa & kapan | P0 |
| RV-04 | Ekspor Markdown, DOCX, PDF | P0 |
| RV-05 | Ekspor **CSV siap impor Jira** (Summary, Issue Type, Epic Link, Description, Priority, Labels) | P0 |
| RV-06 | Ekspor JSON (untuk otomasi/pipeline lain) | P1 |
| RV-07 | Salin ke Confluence/Notion (Markdown clipboard yang rapi) | P1 |
| RV-08 | Integrasi API Jira/Linear (bikin issue langsung, dua arah status) | P2 |

### 3.6 Memori lintas rapat
| ID | Kebutuhan | Prioritas |
|---|---|---|
| MM-01 | Library per proyek/epic; rapat dikelompokkan, bisa dicari isinya | P1 |
| MM-02 | Deteksi topik lanjutan: "ini lanjutan keputusan tgl 12" | P2 |
| MM-03 | Action item carry-over: muncul lagi di rapat berikutnya sampai ditutup | P1 |
| MM-04 | Digest harian/mingguan: keputusan, progres, item menggantung, risiko | P2 |
| MM-05 | Q&A lintas rapat ("apa saja komitmen ke vendor X?") dengan sitasi | P2 |

---

## 4. Skema data artefak (sumber kebenaran)

```json
{
  "meeting": { "id": "mtg_2026_11_22_01", "title": "Requirement Modul Approval",
               "date": "2026-11-22", "duration_s": 3120, "lang": ["id","en"],
               "speakers": [{"id":"S1","name":"Putra","role":"Lead IT"}] },
  "summary": { "tldr": ["..."], "narrative": "..." },
  "decisions": [
    { "id":"D-01", "text":"Approval menggunakan 3 level, bukan 2",
      "by":"S2", "confidence":"high",
      "evidence":[{"seg":128,"t_start":1832.4,"quote":"jadi kita pakai tiga level ya"}] }
  ],
  "requirements": [
    { "id":"R-01", "type":"functional", "text":"Approver dapat mendelegasikan task saat cuti",
      "priority":"must", "rationale":"disebut sebagai blocker operasional",
      "evidence":[{"seg":210,"t_start":3021.0}] }
  ],
  "open_questions": [
    { "id":"Q-01", "text":"Siapa pemilik data master supplier?",
      "asked_by":"S1", "status":"unanswered", "evidence":[{"seg":301}] }
  ],
  "action_items": [
    { "id":"A-01", "task":"Kirim draft ERD ke tim", "owner":"S1",
      "owner_inferred":false, "due":"2026-11-25", "status":"open", "evidence":[{"seg":355}] }
  ],
  "artifacts": [
    { "type":"epic", "id":"EP-01", "title":"Multi-level Approval",
      "source_refs":["D-01","R-01"], "version":1,
      "model":"gemini-2.5-flash", "prompt_version":"epic@v3", "status":"draft" },
    { "type":"user_story", "id":"US-014",
      "as_a":"approver", "i_want":"mendelegasikan approval",
      "so_that":"proses tidak berhenti saat cuti",
      "acceptance":[{"given":"approver cuti","when":"delegasi diaktifkan","then":"approval diteruskan ke delegate"}],
      "estimate":null, "epic":"EP-01", "source_refs":["R-01"], "status":"draft" }
  ]
}
```

Aturan validasi (dijalankan otomatis, bukan diserahkan ke LLM):
- Setiap `decisions[]`, `requirements[]`, `action_items[]` **wajib** punya ≥1 `evidence` valid.
  Item tanpa bukti otomatis dipindah ke `open_questions` dengan label "asumsi".
- `user_story.acceptance` wajib ≥1 skenario dan harus testable (ada aksi + hasil teramati).
- Prioritas hanya boleh `must|should|could|wont` (MoSCoW) agar konsisten dengan BRD.
- Angka, tanggal, dan nama orang divalidasi ulang terhadap transkrip (string/angka harus muncul).

---

## 5. Template artefak

### 5.1 BRD (Business Requirement Document)
1. Latar belakang & masalah bisnis
2. Tujuan + metrik sukses (terukur)
3. Ruang lingkup (in scope / out of scope)
4. Stakeholder & RACI
5. Kebutuhan bisnis `BR-xx` (prioritas, rasional, sitasi)
6. Asumsi & batasan
7. Risiko & mitigasi
8. Ketergantungan antar tim/sistem
9. Milestone kasar
10. Lampiran: keputusan, open question, transkrip

### 5.2 Epic
Goal · Business value · Scope (in/out) · Success metric · Dependencies · Daftar story · Risiko · Sitasi

### 5.3 PRD (Product Requirement Document)
1. Problem statement & konteks
2. Goals / Non-goals
3. Persona & jobs
4. User journey / alur utama
5. Functional requirements `FR-xx` (must/should/could, edge case)
6. Non-functional (performa, keamanan, audit, aksesibilitas)
7. Dampak teknis (data model, API, integrasi)
8. Metrik & event analytics
9. Rencana rilis & kriteria terima
10. Open question & asumsi
11. Lampiran sitasi

### 5.4 User Story (Definition of Ready)
- Format: `Sebagai <persona>, saya ingin <kapabilitas>, agar <manfaat>`
- AC Gherkin minimal 1 happy path + 1 edge case
- Field: prioritas, estimasi (kosong), epic link, dependency, `source_refs`, status
- Aturan kualitas: 1 story = 1 kapabilitas, bisa selesai dalam 1 sprint, tanpa istilah ambigu

> **Realita yang harus diterima:** dari rekaman 45 menit, LLM realistis menghasilkan **70–85%**
> draft. Sisa 15–30% (konteks bisnis, prioritas antar-tim, batasan politik/anggaran) tidak ada di
> transkrip. Karena itu field `open_questions` dan halaman "Perlu konfirmasi" bukan fitur
> pelengkap — itu justru fitur utama yang membedakan draft jujur dari dokumen karangan.

---

## 6. Strategi LLM: cloud vs lokal vs hybrid

| Mode | Model | Kualitas dokumen | Biaya/meeting 1 jam | Privasi | Catatan |
|---|---|---|---|---|---|
| **Cloud (rekomendasi default)** | Gemini 2.5 Flash | Tinggi | ± $0,03–0,08 (≈ Rp 500–1.300) | Data keluar | Paling murah & cepat; 9,5 jam audio/request |
| Cloud premium | Gemini 2.5 Pro | Sangat tinggi | ± $0,15–0,30 (≈ Rp 2.500–5.000) | Data keluar | Untuk BRD/PRD final saja |
| **Lokal** | Ollama Qwen2.5-7B/14B Q4 | Sedang | Rp 0 | 100% lokal | 7B Q4 ± 4,5 GB RAM — di 8 GB harus bergantian dengan ASR |
| Hybrid | ASR lokal + generasi cloud | Tinggi | sama cloud | Transkrip keluar | Default: audionya tidak pernah keluar, hanya teks |

**Rekomendasi:** *hybrid* — ASR 100% lokal (privasi audio terjaga), generasi via Gemini Flash
dengan opsi per-proyek "paksa lokal" untuk rapat sensitif. Harga acuan Gemini 2.5 Flash:
$0,30/1M token input, $2,50/1M output; Pro $1,25/$10 ([referensi harga](https://aicostcheck.com/blog/google-gemini-pricing-guide-2026)).
Kalkulasi: rapat 1 jam ≈ 12–15k token teks; pipeline 4 tahap ≈ 40–60k input + 10–15k output.

Catatan teknis:
- **NotebookLM tidak punya API publik** — tidak bisa dipanggil dari app; perannya digantikan
  kombinasi Gemini API + skema + sitasi di atas.
- API key disimpan di **Keychain**, tidak pernah di file config biasa.
- Semua panggilan LLM lewat satu modul `LLMProvider` (Gemini/OpenAI/Anthropic/Ollama) agar bisa
  diganti tanpa menyentuh UI.
- Prompt disimpan sebagai file berversi (`prompts/extract@v3.md`), versinya dicatat di artefak
  supaya hasil bisa direproduksi.

---

## 7. Diarisasi speaker — titik paling berisiko di 8 GB

Diarisasi dibutuhkan karena hampir semua nilai (owner action item, "siapa bilang apa") bergantung
pada label pembicara. Tapi ini juga komponen paling berat:

- pyannote (stock) dilaporkan pernah butuh **11,2 GB** untuk audio 1 jam/5 pembicara karena operasi
  `repeat_interleave`; versi yang dioptimalkan turun ke ±39 MB ([catatan optimasi](https://github.com/attevon-llc/OpenTranscribe/blob/master/docs/PYANNOTE_OPTIMIZATION_SUMMARY.md)).
  Artinya: **wajib chunking + library yang sudah dioptimalkan**, bukan pyannote default.
- Ada port MLX untuk model segmentasi pyannote yang jalan di GPU Apple Silicon
  ([mlx-community/pyannote-segmentation-3.0-mlx](https://huggingface.co/mlx-community/pyannote-segmentation-3.0-mlx)).

**Rencana:** diarisasi dijalankan sebagai *pass terpisah* setelah ASR (bukan bersamaan), pada audio
yang sudah di-chunk 5–10 menit. Fallback bila gagal/OOM: transkrip tetap jadi, label speaker
disembunyikan dan pengguna diberi tahu (degradasi anggun, bukan crash).

---

## 8. UX

| Layar | Isi |
|---|---|
| **Inbox** | Rekaman baru masuk sini, status proses, tombol "Proses sekarang" |
| **Proses** | Stepper: Audio → Transkrip → Diarisasi → Ekstraksi → Artefak, dengan progres & batal |
| **Review** | Kiri transkrip tersitasi, kanan artefak; klik sitasi → seek audio; approve per artefak |
| **Artifact** | Tab: Ringkasan · Keputusan · Action Item · BRD · Epic · PRD · User Story |
| **Library** | Per proyek: rapat-rapat, keputusan, open item, status epic |
| **Digest** | Ringkasan mingguan: apa yang diputuskan, apa yang menggantung |
| **Pengaturan** | Provider LLM & key, template, glosarium, retensi, privasi |

Alur kritis (happy path ≤ 6 menit setelah rapat selesai):
`rekaman masuk Inbox → klik Proses → tunggu (sambil kerja lain) → notifikasi → Review → Approve → Ekspor ke Jira/DOCX`.

State yang wajib ditangani: ASR gagal sebagian · diarisasi OOM · LLM rate-limit/timeout ·
API key invalid · transkrip kosong (audio senyap) · rapat tanpa keputusan (harus bilang jujur,
bukan mengarang) · dokumen belum di-approve tapi mau diekspor (peringatan) · perubahan manual
harus tidak tertimpa saat regenerate.

---

## 9. Tata kelola & kepatuhan (penting untuk Lead IT)

| Aspek | Kebutuhan |
|---|---|
| Consent | Pengingat + banner saat merekam; catatan siapa yang diberi tahu |
| UU PDP (UU 27/2022) | Data pribadi di transkrip: minimisasi, tujuan jelas, hak hapus, retensi terbatas |
| Kebijakan perusahaan | Flag "jangan keluar dari perangkat" per proyek → paksa provider lokal |
| Enkripsi | Transkrip & artefak terenkripsi at-rest (SQLCipher/FileVault), API key di Keychain |
| Retensi | Default simpan 90 hari, auto-hapus audio setelah transkrip sukses (opsional) |
| Audit | Log ekspor: siapa, kapan, artefak apa, ke mana |
| Vendor cloud | Cek DPA & region data provider sebelum dipakai untuk rapat klien |

**Rekomendasi konkret:** default = audio dihapus setelah transkrip selesai (bisa dimatikan),
karena audio mentah adalah aset paling sensitif dan paling jarang dibutuhkan lagi.

---

## 10. Cara mengukur kualitas artefak (jangan cuma "kelihatan bagus")

Buat **golden set 3 rapat** (1 requirement gathering, 1 standup, 1 vendor call) yang kamu tulis
manual sebagai pembanding. Rubrik per artefak:

| Dimensi | Cara ukur | Target |
|---|---|---|
| Recall keputusan | # keputusan tertangkap / # keputusan di ground truth | ≥ 90% |
| Presisi | # item yang benar-benar dibahas / # item yang dihasilkan | ≥ 85% |
| Groundedness | % item dengan sitasi valid & kutipan cocok | 100% |
| Hallusinasi | # item tanpa dasar di transkrip | 0 |
| Kelayakan story | % story lolos Definition of Ready | ≥ 70% |
| Usaha edit | waktu yang kamu habiskan memperbaiki draft | ≤ 5 menit/artefak |

Setiap perubahan prompt/model **wajib** diuji ulang pada golden set ini. Tanpa ini, "terasa lebih
baik" akan menyesatkan.

---

## 11. Arsitektur revisi

```
┌─────────────────────────── Tauri (macOS) ───────────────────────────┐
│  UI: React/Svelte — Inbox, Review, Artifact, Library, Settings      │
└───────────────┬─────────────────────────────────────────────────────┘
                │ IPC (JSON)
┌───────────────▼───────────────┐      ┌──────────────────────────────┐
│  Orchestrator (Rust)          │      │  SQLite (SQLCipher)          │
│  job queue, state, retry,     │◄────►│  meeting, transcript,        │
│  progress, cancel             │      │  artifact, evidence, audit   │
└───────────────┬───────────────┘      └──────────────────────────────┘
                │ spawn sidecar (stdin/stdout JSON-lines)
┌───────────────▼────────────────────────────────────────────────────┐
│  Python sidecar "dikte-engine"                                      │
│  ├─ asr: whisper.cpp(MLX/Metal) │ faster-whisper │ openai/whisper    │
│  ├─ diarize: pyannote-optimized / MLX port (chunked)                │
│  ├─ extract: map-reduce + JSON schema validation                    │
│  └─ generate: LLMProvider (gemini | openai | anthropic | ollama)    │
└────────────────────────────────────────────────────────────────────┘
```

Kunci: tiap tahap punya **kontrak JSON** dan **artefak antara** yang tersimpan
(`audio → segments.json → diarization.json → facts.json → artifact.json`). Efeknya: bisa
re-generate artefak tanpa mengulang ASR, bisa ganti model tanpa mengulang rapat lain, dan bisa
debug per tahap.

---

## 12. Roadmap & estimasi (1 developer)

| Fase | Isi | Estimasi |
|---|---|---|
| **P0 — Fondasi** | Env, engine ASR pluggable, impor file, transkrip+timestamp, chunking file panjang, DB | 4–6 hari |
| **P1 — Catatan rapat** | Diarisasi (chunked), rename speaker, ekstraksi keputusan/action/open question, ekstrak JSON tervalidasi, review sederhana, ekspor MD | 5–7 hari |
| **P2 — Artefak** ⭐ | Template BRD/Epic/PRD/US, sitasi klik, halaman "Perlu konfirmasi", review dua panel, approve, ekspor DOCX + Jira CSV | 6–8 hari |
| **P3 — Alur harian** | Inbox + auto-import folder, library proyek, carry-over action item, digest mingguan | 4–5 hari |
| **P4 — Rilis** | Rekam mic/system audio, bundling, DMG, signing/notarization, auto-update | 4–6 hari |

**MVP yang benar-benar berguna bagimu = sampai P2 (± 3–4 minggu).** P3–P4 menambah kenyamanan.
Kalau ingin cepat merasakan nilai: P0+P1+P2 dengan UI minimal dulu, baru poles.

---

## 13. Risiko baru (di luar risiko ASR di dokumen 01)

| # | Risiko | Dampak | Mitigasi |
|---|---|---|---|
| M1 | Diarisasi OOM pada rapat 1 jam+ (pyannote stock 11 GB) | Tinggi | Chunking wajib, library teroptimasi/MLX, fallback tanpa label |
| M2 | Kepemilikan action item salah karena label speaker tertukar | Tinggi (salah orang ditegur) | Owner eksplisit > terduga; kamu konfirmasi nama speaker sekali di awal |
| M3 | Requirement halusinasi masuk ke Jira | Sangat tinggi | Sitasi wajib + validator bukti + gate approve |
| M4 | Dokumen rahasia terkirim ke cloud tanpa sadar | Sangat tinggi | Flag per proyek, indikator "cloud/local" di layar review, audit log |
| M5 | Draft BRD terlalu generik, tidak bisa dipakai | Sedang | Template + contoh gaya perusahaannya + gap list jujur |
| M6 | Biaya API membengkak (regenerate berulang) | Rendah | Cache hasil per hash, batasi regenerate, tampilkan estimasi biaya sebelum jalan |
| M7 | Prompt berubah → kualitas turun diam-diam | Sedang | Prompt berversi + golden set regression |
| M8 | Scope creep ke "AI project manager" | Tinggi | Kunci P0–P2; integrasi dua arah Jira tetap P2 |

---

## 14. Keputusan yang perlu diambil

1. **Provider LLM default:** Gemini Flash (murah, cocok karena kamu sudah pakai Gemini) / lokal
   Ollama (privasi) / keduanya? → rekomendasi: **hybrid, default cloud, flag lokal per proyek**.
2. **Target ekspor utama:** Jira, Linear, Confluence, DOCX, atau cukup Markdown dulu?
3. **Diarisasi di MVP atau fase 2?** (menentukan apakah P1 jadi 5 hari atau 2 hari)
4. **Rekaman sumber:** file dari Zoom/Meet (paling mudah) atau wajib rekam langsung dari app?
5. **Bahasa dokumen artefak:** Indonesia, Inggris, atau bisa dipilih per artefak (tim developer
   kadang lebih nyaman Inggris)?
