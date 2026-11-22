# Analisa Ulang (Second Pass) — Uji Asumsi & Koreksi

**Status:** draft · **Tanggal:** 22 Nov 2026
**Tujuan:** menguji ulang kesimpulan di [01](./analisa-kebutuhan.md) dan [02](./02-spek-meeting-intelligence.md),
bukan mengulangnya. Setiap klaim diperiksa: apakah masih valid, terlalu optimistis, atau salah.

---

## 0. Enam koreksi terhadap analisa sebelumnya

| # | Klaim lama | Temuan setelah diuji ulang | Dampak |
|---|---|---|---|
| K1 | "Wajib multi-pass map-reduce" | **Salah untuk cloud.** Gemini punya konteks 1M token; transkrip 1 jam cuma ±12–15k token → cukup **satu pass**. Map-reduce hanya perlu untuk model lokal (8k–32k konteks) | Pipeline lebih sederhana, biaya turun ±60%, lebih sedikit titik gagal |
| K2 | (implisit) "belum ada tool yang begini" | **Salah.** Sudah ada produk yang mengklaim notes→PRD/user story→Jira (PM Agent, BA-Assistant, Spectr, Acta) | "Build vs buy" harus dijawab eksplisit; diferensiasi harus jelas, bukan asumsi |
| K3 | "BRD/PRD adalah output utama" | **Terlalu berat.** BRD biasanya per-proyek (beberapa kali setahun); yang **harian** adalah action item, keputusan, dan user story | Prioritas build berubah: action item + story dulu, BRD/PRD belakangan |
| K4 | "Diarisasi wajib di MVP" | **Bisa ditunda.** Tanpa label speaker, 60–70% nilai (ringkasan, keputusan, story) tetap didapat; yang hilang hanya kepastian owner | P1 turun dari 5–7 hari → 2 hari; risiko OOM hilang dari jalur kritis |
| K5 | "Risiko utama = hardware/kecepatan" | **Salah sasaran.** Risiko utama = **code-switched speech ID–EN** dan akurasi token kritis (nama, angka, tanggal) | Perlu uji 30 menit audio asli **sebelum** menulis kode aplikasi |
| K6 | "MVP 3–4 minggu" | **Terlalu lama untuk memvalidasi.** Nilai inti bisa diuji dalam **3 hari** tanpa UI | Ganti urutan: validasi dulu → baru bangun produk |

---

## 1. Uji asumsi (satu per satu)

| # | Asumsi | Bukti / cara uji | Verdict |
|---|---|---|---|
| A1 | Kamu butuh 4 jenis artefak (BRD, Epic, PRD, US) | Frekuensi pemakaian nyata; BRD/PRD formal jarang, US/Epic harian | ❌ Persempit: **Epic + US + action item + decision log** dulu |
| A2 | Kamu butuh semua rapat direkam & diringkas | Standup 15 menit biasanya tidak perlu dokumen | ⚠️ Butuh **mode ringan** (notes saja) vs **mode penuh** (artefak) |
| A3 | ASR harus akurat untuk semua rapat | Rapat 1:1 & vendor call = akurasi kritis; standup = toleran | ⚠️ Kualitas boleh bervariasi per jenis rapat |
| A4 | Diarisasi speaker diperlukan | Owner action item bisa diisi manual; kamu tahu siapa yang bicara | ⚠️ **Ditunda**, tapi sediakan slot data agar tidak migrasi besar nanti |
| A5 | Generasi harus cloud | Biaya cloud sangat kecil (Rp 300–1.300/rapat); lokal 7B kalah kualitas & rebutan RAM | ✅ Cloud default, lokal sebagai opsi (bukan default) |
| A6 | Perlu UI desktop sejak awal | Nilai bisa diuji via CLI + file Markdown | ❌ UI **setelah** validasi kualitas |
| A7 | 8 GB cukup | Cukup untuk ASR (small/turbo) + LLM cloud berurutan; **tidak** cukup ASR + LLM 7B bersamaan | ✅ Cukup, dengan batasan desain |
| A8 | NotebookLM tidak bisa dipakai lagi | Tidak ada API publik; tapi bisa tetap dipakai manual di samping app | ✅ App harus menggantikan, bukan bergantung |

---

## 2. Analisa kuantitatif (skenario: 5 rapat/hari, 40 menit)

| Metrik | Perkiraan | Catatan |
|---|---|---|
| Audio diproses | 200 menit/hari · ±67 jam/bulan | |
| Waktu komputasi ASR (3× realtime) | ±67 menit/hari | jalan di background, tidak blokir kerja |
| Penyimpanan audio | ±2 GB/bulan (m4a 64 kbps) | → **auto-hapus setelah transkrip** sebagai default |
| Penyimpanan teks | ±4 MB/bulan | tidak signifikan |
| Biaya LLM (single-pass, Flash) | ±Rp 300/rapat → **±Rp 30 rb/bulan** | multi-pass ±Rp 70 rb/bulan |
| Biaya LLM (Pro, untuk BRD final) | ±Rp 2.500/artefak | pakai selektif |
| Waktu rekap manual saat ini | ±25 menit/rapat → **125 menit/hari** | asumsi: baca ulang + tulis |
| Waktu dengan app | ±40 menit/hari (review 5 menit × 5 + edit artefak) | |
| **Hemat waktu** | **±85 menit/hari ≈ 7 jam/minggu** | |

### Break-even pembangunan

| Skenario build | Jam kerja | Payback (hemat 85 mnt/hari) |
|---|---|---|
| Walking skeleton (3 hari) | ±24 jam | ±2 minggu |
| MVP tipis (1 minggu) | ±40 jam | ±4 minggu |
| MVP penuh P0–P2 (3–4 minggu) | ±120–160 jam | ±3,5–4,5 bulan |
| Produk lengkap P0–P4 | ±200 jam | ±6 bulan |

**Kesimpulan:** semakin tipis build-nya, semakin cepat balik modal. Membangun versi penuh sebelum
membuktikan kualitas artefak adalah keputusan finansial yang buruk — bukan karena sulit, tapi karena
**risikonya salah sasaran**.

---

## 3. Analisa kualitas: dari mana error sebenarnya datang

### 3.1 Angka ASR Bahasa Indonesia (bukan opini)

| Model | Dataset | WER |
|---|---|---|
| Whisper large-v2 | FLEURS (bersih) | ±7,1% |
| Whisper small | FLEURS | **±16,3%** |
| Whisper large-v3 | FLEURS | ±7,6% ([model card](https://huggingface.co/Dafisns/whisper-turbo-multilingual-fleurs)) |
| Whisper large-v3 | Common Voice 22 (spontan, aksen beragam) | **±11,4%** |
| Whisper large-v3 | uji independen | ±5,5% ([inferenceapis](https://inferenceapis.com/speech-to-text/#method)) |

Baca: di audio bersih, ID **bagus**. Di audio rapat spontan (banyak "eee", tumpang tindih, mic jauh,
aksen), angka nyata akan lebih dekat ke Common Voice atau lebih buruk.

### 3.2 Risiko yang jauh lebih besar: campur kode ID–EN

Satu studi code-switching ID–EN 2024 melaporkan CER **4,10%** pada monolingual Indonesia vs
**91,76%** pada percakapan campur kode alami ([rangkuman](https://www.matthewswong.com/id/blog/speech-to-text-bahasa-indonesia-production/)).
Angka 91,76% itu ekstrem dan kemungkinan spesifik model/dataset tertentu — **jangan dipakai sebagai
prediksi**, tapi arah risikonya jelas dan sangat relevan:

> Rapat tim IT di Indonesia hampir selalu campur kode: *"nanti kita deploy ke staging, terus QA
> regression dulu, kalau clear baru kita rilis"*. Kalau ASR gagal di pola ini, seluruh pipeline
> di atasnya runtuh — dan ini **bukan** masalah hardware yang bisa diselesaikan dengan GPU.

**Konsekuensi desain:** ini bukan risiko yang boleh diasumsikan. Harus diukur pada 30 menit
rekaman asli sebelum satu baris kode aplikasi ditulis.

### 3.3 Error compounding

| Lapisan | Error khas | Dampak ke artefak |
|---|---|---|
| ASR | 11–25% WER (rapat nyata) | kata hilang/berubah |
| Token kritis (nama, angka, tanggal) | jauh lebih buruk dari rata-rata | **requirement salah angka = bahaya** |
| Ekstraksi LLM | 5–15% item salah/generik | item perlu diedit |
| Generasi artefak | halusinasi bagian kosong | dokumen tidak bisa dipercaya |

Jika peluang tiap item benar ±0,85 di tiga lapisan, hasil akhir ±0,61 → **hampir 4 dari 10 item perlu
disentuh**. Inilah justifikasi kenapa **review gate** dan **sitasi** bukan fitur tambahan, dan kenapa
klaim "otomatis 100%" harus ditolak sejak awal.

---

## 4. FMEA pipeline (Severity/Occurrence/Detection, skala 1–5; RPN = S×O×D)

| # | Mode kegagalan | Efek | S | O | D | RPN | Mitigasi |
|---|---|---|---|---|---|---|---|
| F1 | Campur kode ID–EN salah transkrip | Arti berubah | 5 | 4 | 2 | **40** | Uji awal; prompt+glosarium; `language=id`; opsi koreksi manual cepat |
| F2 | Nama orang/produk/akronim salah | Salah orang, salah sistem | 4 | 4 | 3 | **48** | Glosarium per proyek; sorot token tak dikenal untuk dicek |
| F3 | Angka/tanggal/harga salah | Keputusan bisnis keliru | 5 | 3 | 3 | **45** | Validasi angka terhadap transkrip; tandai semua angka |
| F4 | Label speaker tertukar | Owner action item salah | 4 | 3 | 3 | 36 | Owner manual/konfirmasi; tandai "terduga" |
| F5 | Rapat tanpa keputusan → LLM mengarang | Dokumen palsu | 5 | 3 | 2 | 30 | Instruksi "boleh kosong"; blokir item tanpa bukti |
| F6 | Data rahasia terkirim ke cloud | Insiden kepatuhan | 5 | 2 | 3 | 30 | Flag per proyek; indikator mode; audit log |
| F7 | Dokumen generik tak dipakai | Waktu terbuang | 4 | 3 | 2 | 24 | Template + contoh gaya sendiri + gap list |
| F8 | Diarisasi OOM (1 jam+) | Proses gagal | 3 | 4 | 1 | 12 | Chunking; fallback tanpa label |
| F9 | Prompt/model berubah → kualitas turun | Regresi senyap | 3 | 3 | 4 | 36 | Golden set + versi prompt |
| F10 | Audio jelek (echo, mic jauh) | Transkrip buruk | 4 | 4 | 2 | 32 | Deteksi kualitas audio di awal; saran rekam ulang |

**Prioritas mitigasi:** F1, F2, F3, F9 — semuanya bisa ditangani **sebelum** UI dibangun
(glosarium, validator angka, golden set). Ini memperkuat urutan: validasi dulu.

---

## 5. Build vs buy (yang sebelumnya saya lewatkan)

| Opsi | Yang didapat | Kekurangan | Biaya |
|---|---|---|---|
| Otter / Fireflies / Granola | Transkrip, ringkasan, action item | Cloud; tidak menghasilkan BRD/PRD tersitasi; kualitas ID campur kode tidak dijamin | ±$10–20/user/bulan |
| BA-Assistant | BRD (IEEE 830), user story, Jira | Cloud; template kaku; data keluar | SaaS |
| PM Agent / Spectr / Acta | Notes → PRD/story → Jira/Linear | Cloud, Chrome ext, fokus tim produk global | SaaS |
| MacWhisper | Transkripsi lokal cepat di Mac | Hanya transkrip, tanpa artefak | sekali bayar |
| NotebookLM | Ringkasan tersitasi, tanya-jawab | Tidak ada API, tidak ada artefak/Jira | gratis/Plus |
| **Bangun sendiri** | Lokal, ID, artefak tersitasi, kontrol penuh | Waktu build + maintenance | ±24–160 jam |

**Kesimpulan jujur:** untuk *catatan rapat + action item*, membeli lebih rasional. Untuk
**artefak tersitasi + data tidak keluar + kualitas ID**, belum ada yang cocok — tapi ini klaim yang
harus diverifikasi dengan uji 1 jam coba SaaS gratis sebelum dibangun.

---

## 6. Di mana nilainya sebenarnya (value vs effort)

| Fitur | Nilai untukmu | Effort | Urutan |
|---|---|---|---|
| Transkrip + timestamp + pencarian | Sedang (sudah bisa pakai NotebookLM) | Rendah | 2 |
| **Action item + keputusan + open question** | **Tinggi** (ini yang bikin kamu kelihatan rapi) | Rendah | **1** |
| **Epic + user story + AC, ekspor Jira CSV** | **Tinggi** (menghemat kerja paling menyebalkan) | Sedang | **3** |
| Glosarium & koreksi nama | Tinggi (mencegah salah nama di depan stakeholder) | Rendah | 2 |
| Review dua panel + sitasi klik | Tinggi (membangun kepercayaan) | Sedang | 4 |
| BRD/PRD lengkap | Sedang–rendah (jarang dipakai) | Sedang | 6 |
| Diarisasi | Sedang | Tinggi (RAM) | 7 |
| Rekam system audio | Sedang | Sedang-tinggi | 5 |
| Library, digest, Q&A lintas rapat | Sedang (jangka panjang) | Tinggi | 8 |

---

## 7. Rekomendasi yang direvisi

### Langkah 0 — Validasi 3 hari (sebelum membangun apa pun)
1. Siapkan env: `brew install ffmpeg python@3.12`, venv, `faster-whisper` (atau whisper.cpp).
2. Ambil **3 rekaman asli**: satu rapat requirement (campur kode), satu standup, satu vendor call.
3. Transkrip dengan `small` dan `turbo`; ukur WER kasar pada 5 menit pertama + cek manual token
   kritis (nama, angka, tanggal).
4. Ambil 1 transkrip → prompt satu pass ke Gemini Flash → hasilkan: keputusan, action item,
   Epic, 3–5 user story + AC, dengan sitasi.
5. **Ukur:** berapa menit kamu mengedit sampai layak dikirim?

**Kriteria go:** waktu edit ≤ 10 menit untuk 1 rapat 40 menit, dan ≥80% item bisa dipakai
tanpa ditulis ulang. **Kriteria no-go:** CER campur kode > 30% dan tidak membaik dengan glosarium,
atau editing > 60% waktu menulis manual.

### Langkah 1 — MVP tipis (1 minggu), tanpa UI
CLI + folder watch: file masuk → transkrip → `facts.json` → `notes.md` + `jira.csv`.
Glosarium, validator angka, sitasi. Dipakai untuk rapat asli setiap hari.

### Langkah 2 — UI (setelah 2 minggu dipakai)
Baru bangun Tauri + review dua panel. Pada titik ini kamu sudah tahu field mana yang benar-benar
dipakai dan mana yang tidak — menghindari membangun UI untuk fitur yang ternyata tidak dibuka.

### Langkah 3 — Perluas
Diarisasi, BRD/PRD template, library proyek, digest.

---

## 8. Kriteria berhenti (kill criteria) — jujur sejak awal

Hentikan atau ubah arah jika salah satu terjadi:
1. Waktu review+edit > 60% dari waktu menulis manual, selama 3 rapat berturut-turut.
2. Campur kode tetap tidak terbaca setelah glosarium + prompt khusus → ASR tidak layak untuk rapatmu.
3. Setelah 2 bulan, waktu perawatan (update model/dependency) > waktu yang dihemat.
4. Kamu tetap membuka NotebookLM karena tidak percaya hasilnya → masalahnya kepercayaan, bukan fitur.
5. Tool ini jadi proyek sampingan yang dikerjakan hanya saat senggang dan tidak pernah dipakai harian.

---

## 9. Kesimpulan

Analisa sebelumnya benar di **lapisan teknis** (ASR, model, RAM, packaging) tapi **terlalu cepat
melompat ke solusi**: mengasumsikan semua artefak dibutuhkan, mengasumsikan multi-pass wajib,
melewatkan bahwa produk sejenis sudah ada, dan menempatkan risiko pada hardware padahal risiko
sesungguhnya ada di kualitas bahasa campur kode + kepercayaan pada output.

Arah yang benar: **uji 3 hari → MVP tipis 1 minggu → baru UI.** Investasi terbesar bukan di kode,
tapi di **glosarium, validator, dan golden set** — tiga hal yang membuat output bisa dipercaya.
