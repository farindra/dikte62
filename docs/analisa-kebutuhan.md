# Analisa Kebutuhan — Aplikasi Desktop Transkripsi ID/EN berbasis Whisper

**Status:** draft v0.1 · **Tanggal:** 22 Nov 2026
**Target awal:** macOS (Apple Silicon M1, 8 GB RAM, macOS 26.1) — mesin pengembangan saat ini
**Referensi model:** [openai/whisper](https://github.com/openai/whisper) (MIT, PyPI `openai-whisper` 20250625)

> ⚠️ **Dokumen ini adalah lapisan dasar (ASR + paket desktop).** Arah produk sudah diperluas menjadi
> pipeline *meeting → artefak kerja* (keputusan, action item, BRD/Epic/PRD/user story).
> Lihat **[02-spek-meeting-intelligence.md](./02-spek-meeting-intelligence.md)** untuk ruang lingkup terkini.

---

## 0. Ringkasan

Aplikasi desktop yang mengubah audio/video menjadi teks **Bahasa Indonesia & Inggris**, berjalan
**offline di mesin pengguna**, dengan output teks + timestamp (SRT/VTT) yang bisa diedit dan diekspor.

Kesimpulan utama dari analisa:

1. **Repo `openai/whisper` sanggup memenuhi kebutuhan fungsional** (99 bahasa, ID & EN didukung,
   lisensi MIT termasuk bobot model), tetapi **bukan pilihan tercepat di Mac**: `load_model()`
   default-nya `cpu` di macOS, dan jalur MPS (`device="mps"`) masih bolong (operator
   `repeat_interleave`/sparse belum didukung) sehingga rawan error atau fallback ke CPU.
2. **CPU-only + fp32 = mahal.** Di CPU, bobot berjalan fp32 (± 4 byte/parameter) sehingga
   `large-v3` butuh ± 6,2 GB RAM — **tidak realistis di 8 GB**. Batas praktis mesin ini:
   `small`, `medium`, `turbo`.
3. **Kebutuhan sistem berubah:** Python 3.9 bawaan macOS sudah tidak kompatibel dengan PyTorch
   modern (torch 2.15 minta ≥ 3.11) dan numba terbaru (≥ 3.10). Butuh Python 3.11/3.12 + ffmpeg.
4. **Ada jalur alternatif yang jauh lebih cepat di Apple Silicon** (whisper.cpp/Metal, MLX,
   faster-whisper int8) memakai bobot model yang sama. Disarankan arsitektur *engine pluggable*
   agar repo openai/whisper tetap jadi acuan/referensi, tapi performa tidak jadi korban.
5. **Yang paling sering bikin produk gagal bukan modelnya**, tapi: halusinasi pada audio sunyi,
   campur kode ID–EN, file panjang (OOM/kehilangan progres), dan distribusi (signing + notarization).

---

## 1. Tujuan, ruang lingkup, asumsi

### 1.1 Tujuan
- Transkripsi akurat audio ID/EN tanpa mengirim data ke cloud (privasi total, offline).
- Alur kerja cepat: impor → transkripsi → edit → ekspor.
- Terasa seperti aplikasi native macOS (drag & drop, shortcut, menu bar), bukan script Python.

### 1.2 Dalam ruang lingkup (MVP)
Transkripsi **file** audio/video, pilih bahasa (auto/ID/EN), pilih model, progres + batal,
editor transkrip dengan timestamp, ekspor TXT/SRT/VTT/JSON, riwayat lokal.

### 1.3 Di luar ruang lingkup MVP (fase berikutnya)
Transkripsi real-time dari mikrofon, perekaman system audio, diarisasi pembicara,
terjemahan, ringkasan AI, kolaborasi/cloud sync, Windows/Linux.

### 1.4 Asumsi
- Pengguna bersedia mengunduh model sekali di awal (139 MB – 1,5 GB).
- Audio yang ditranskrip legal untuk diproses (bukan konten yang melanggar).
- Mesin target setara/serupa M1 8 GB; jika target lebih luas, perlu uji ulang batas model.

---

## 2. Pengguna & use case

| Persona | Kebutuhan utama | Prioritas |
|---|---|---|
| Jurnalis/riset | Wawancara panjang (30–120 menit), butuh SRT + teks rapi | P0 |
| Kreator konten | Subtitle video, timing presisi, ekspor SRT/VTT | P0 |
| Mahasiswa | Rekaman kuliah ID/EN campur, ringkasan teks | P1 |
| Podcaster | 2 pembicara, butuh pemisahan speaker | P2 |
| Profesional rapat | Transkrip cepat, catatan, privasi | P1 |

**Use case inti (UC-01):** pengguna men-drop `wawancara.m4a` → pilih "Deteksi otomatis" →
aplikasi estimasi durasi & progres → transkrip muncul per segmen dengan timestamp → klik segmen
untuk memutar audio → ekspor `.srt`.

---

## 3. Kebutuhan fungsional

Prioritas: **P0** wajib untuk rilis pertama · **P1** penting · **P2** nice-to-have.

### 3.1 Input

| ID | Kebutuhan | Prioritas |
|---|---|---|
| FR-01 | Impor file audio/video: wav, mp3, m4a, aac, flac, ogg, opus, mp4, mov, mkv, webm | P0 |
| FR-02 | Drag & drop ke jendela + tombol "Pilih File" + buka via Finder/`Open With` | P0 |
| FR-03 | Antrean multi-file dengan status per file (menunggu/proses/selesai/gagal) | P1 |
| FR-04 | Rekam dari mikrofon langsung (16 kHz mono) | P2 |
| FR-05 | Rekam system audio (ScreenCaptureKit), mis. rapat/zoom | P2 |

### 3.2 Pemrosesan

| ID | Kebutuhan | Prioritas |
|---|---|---|
| FR-06 | Pemilihan bahasa: **Otomatis**, **Indonesia**, **Inggris**; deteksi ditampilkan ke pengguna | P0 |
| FR-07 | Pemilihan model (tiny/base/small/medium/turbo/large-v3) + label ukuran & perkiraan kecepatan | P0 |
| FR-08 | Unduh model on-demand dengan progres, resumable, verifikasi checksum (SHA-256) | P0 |
| FR-09 | Progres transkripsi per segmen + estimasi sisa waktu + tombol **Batal** | P0 |
| FR-10 | Deteksi & buang bagian sunyi (VAD) agar tidak muncul halusinasi | P0 |
| FR-11 | File panjang diproses bertahap (chunk) + checkpoint, bisa dilanjutkan bila app tertutup | P1 |
| FR-12 | Opsi lanjutan: word-level timestamp, prompt awal/kosakata khusus, suhu decoding, beam size | P1 |
| FR-13 | Caching hasil per file (hash audio) agar tidak memproses ulang | P2 |

### 3.3 Hasil & output

| ID | Kebutuhan | Prioritas |
|---|---|---|
| FR-14 | Tampilan transkrip per segmen: timestamp + teks, bisa diklik untuk seek & putar | P0 |
| FR-15 | Edit teks segmen langsung di UI (dan edit timing bila memungkinkan) | P0 |
| FR-16 | Ekspor **TXT, SRT, VTT, JSON**; nama file default = nama audio | P0 |
| FR-17 | Ekspor sekaligus (pilih beberapa format) + "Salin ke Clipboard" | P1 |
| FR-18 | Gabung/pecah segmen, tombol "gabung baris" agar SRT tidak terlalu pendek | P1 |
| FR-19 | Riwayat transkripsi (daftar, pencarian teks, buka ulang, hapus) | P1 |
| FR-20 | Pemutar audio mini yang tersinkron dengan sorotan segmen | P1 |
| FR-21 | Ekspor `.docx`/`.md` dengan paragraf rapi | P2 |

### 3.4 Pengaturan & sistem

| ID | Kebutuhan | Prioritas |
|---|---|---|
| FR-22 | Pengaturan: folder model, folder output, jumlah thread, bahasa default, tema | P0 |
| FR-23 | Indikator mode offline & ukuran pemakaian disk model (dengan tombol hapus model) | P1 |
| FR-24 | Shortcut keyboard: ⌘O impor, ⌘E ekspor, Space play/pause, ⌘Enter mulai | P1 |
| FR-25 | Menu bar status + notifikasi saat transkripsi selesai (app di background) | P2 |
| FR-26 | Log/diagnostik yang bisa diunduh untuk troubleshooting | P2 |

---

## 4. Kebutuhan non-fungsional

| ID | Kebutuhan | Target terukur |
|---|---|---|
| NFR-01 | Akurasi transkripsi | WER ≤ 15% untuk ID bersih (audio podcast), ≤ 10% untuk EN bersih; diukur pada golden set sendiri |
| NFR-02 | Kecepatan | ≥ 3× realtime pada model default mesin target (10 menit audio ≤ ±3,5 menit) |
| NFR-03 | Memori | Puncak ≤ 4 GB RSS; tidak boleh menyebabkan swap berat di 8 GB |
| NFR-04 | Startup | Cold start ≤ 3 s; model di-load lazy (saat pertama transkripsi) |
| NFR-05 | Responsivitas | UI 60 fps; proses inferensi tidak boleh memblokir main thread |
| NFR-06 | Offline | 100% fungsi setelah model terunduh; nol request jaringan saat transkripsi |
| NFR-07 | Privasi | Audio & transkrip tidak pernah keluar dari mesin; tanpa telemetri pihak ketiga |
| NFR-08 | Ketahanan | File 3 jam tidak crash; progres tersimpan tiap segmen |
| NFR-09 | Ukuran aplikasi | Installer ≤ 150 MB (tanpa model); total dengan 1 model ≤ 1 GB |
| NFR-10 | Aksesibilitas | VoiceOver label, kontras 4.5:1, dukungan keyboard penuh, dark mode |
| NFR-11 | Lokalisasi UI | UI Bahasa Indonesia & Inggris |
| NFR-12 | Batas resource | Hemat baterai saat idle (0% CPU/GPU), hentikan proses inferensi orphan |
| NFR-13 | Distribusi | DMG universal/arm64, ter-sign & ter-notarize, lolos Gatekeeper tanpa warning |
| NFR-14 | Observabilitas | Log berotasi, crash report lokal (opt-in), versi & hash model tercatat |

---

## 5. Kebutuhan data & format

### 5.1 Audio
- Whisper mensyaratkan **16 kHz, mono, PCM float32** — semua input harus di-resample (ffmpeg/PyAV/AVAudioConverter).
- Dukungan wadah (container) bergantung pada ffmpeg: mp3, m4a/aac, flac, ogg/opus, wav, mp4, mov, mkv, webm.
- Batas praktis: file > 2 jam sebaiknya di-chunk ±10 menit dengan overlap 0,5–1 s untuk menjaga konteks.

### 5.2 Output
- **TXT**: teks polos per paragraf.
- **SRT**: `00:00:01,240 --> 00:00:04,880`, segmen ≤ 42 karakter/baris, maks 2 baris.
- **VTT**: header `WEBVTT`, timing `00:00:01.240`.
- **JSON**: `{language, duration, segments:[{id,start,end,text,words?}], model, created_at}`.

### 5.3 Model
| Model | Unduh | Param | RAM fp32 (CPU) | VRAM resmi | Catatan |
|---|---|---|---|---|---|
| tiny | 72 MB | 39 M | 0,15 GB | ~1 GB | cepat, akurasi rendah |
| base | 139 MB | 74 M | 0,3 GB | ~1 GB | baseline |
| small | 461 MB | 244 M | 1,0 GB | ~2 GB | **kandidat default** |
| medium | 1.457 MB | 769 M | 3,1 GB | ~5 GB | akurasi ID lebih baik, berat |
| turbo | 1.543 MB | 809 M | 3,2 GB | ~6 GB | cepat + akurasi tinggi; **tidak dilatih untuk translate** |
| large-v3 | 2.944 MB | 1.550 M | 6,2 GB | ~10 GB | **tidak disarankan** di 8 GB |

> Angka RAM dihitung dari 4 byte/parameter karena PyTorch di CPU menjalankan fp32.
> `.half()` di CPU justru lebih lambat. Ukuran unduh diukur langsung dari server OpenAI.

---

## 6. Kebutuhan teknis & dependensi

### 6.1 Dependensi wajib (repo openai/whisper)
| Komponen | Versi/ukuran | Status di mesin ini |
|---|---|---|
| Python | 3.11 atau 3.12 (repo: ≥3.8; torch modern: ≥3.11) | ❌ hanya 3.9.6 sistem |
| ffmpeg | 6/7/8 | ❌ belum terpasang |
| torch | 2.x, wheel arm64 ± 139 MB | ❌ |
| numba, numpy, tiktoken, tqdm, more-itertools | kecil (total < 15 MB) | ❌ |
| Disk untuk env + 1 model | ± 1,2 GB | ✅ 44 GB bebas |

### 6.2 Setup minimum (diverifikasi terhadap mesin ini)
```bash
brew install python@3.12 ffmpeg
python3.12 -m venv .venv && source .venv/bin/activate
pip install -U openai-whisper
whisper --help
# uji cepat
whisper contoh.m4a --model small --language id --output_format srt
```

### 6.3 Dependensi build/distribusi
- Toolchain C/C++ (Command Line Tools ✅), Rust (jika Tauri) / Swift 6.2 (✅ tersedia),
  Node 20+ (✅ v26), Xcode/CLT untuk `codesign` + `xcrun notarytool` (✅ tersedia).
- Akun Apple Developer (US$99/tahun) untuk signing & notarization distribusi ke pengguna lain.
  **Untuk pemakaian sendiri, signing tidak wajib.**

---

## 7. Batasan hardware → keputusan model

Mesin target: **Apple M1, 8 GB unified memory, GPU 7-core, 44 GB disk bebas.**

Implikasi langsung:
- `large-v3` (6,2 GB fp32) → **drop**. Risiko memory pressure + swap, sistem bisa tersendat.
- `medium`/`turbo` (3,1–3,2 GB) → bisa, tapi menyisakan sedikit ruang untuk OS + audio buffer;
  aman hanya jika satu file diproses sekali jalan (tanpa antrean paralel).
- `small` (1,0 GB) → **paling aman sebagai default**, ~2–3× realtime di CPU.
- Untuk kualitas ID yang lebih baik, opsi terbaik = `turbo` **lewat engine GPU**
  (whisper.cpp Metal / MLX), bukan PyTorch-CPU: fp16 + GPU memangkas memori & waktu drastis.

**Perlu diukur, bukan diasumsikan:** RTF (real-time factor) tiap model × engine pada audio ID nyata.
Rencana: spike 1 hari, ukur 3 file × 3 model, catat waktu, RAM puncak, dan kualitas transkrip.

---

## 8. Kebutuhan akurasi & validasi kualitas

Ini bagian yang membedakan "demo" dan "produk".

| Aspek | Masalah khas Whisper | Mitigasi |
|---|---|---|
| Halusinasi | Audio sunyi/musik menghasilkan teks karangan ("Terima kasih telah menonton") | VAD (Silero) + `no_speech_threshold`, buang segmen < durasi minimum, retry dengan prompt |
| Campur kode ID–EN | Kalimat "kita meeting jam 3 nanti" terpotong/berubah bahasa | `language=id` dipaksa, prompt berisi istilah campuran, opsi "biarkan code-switching" |
| Nama diri/istilah teknis | Salah tulis nama orang, merek, jargon | `initial_prompt` + daftar kosakata pengguna, find-replace di editor |
| Angka & format | "dua ribu dua puluh lima" vs "2025", tanda baca | Normalisasi opsional di post-processing (P2) |
| Timestamp | Segment-level kasar (± 0,5–2 s) | `word_timestamps=True` atau pasca-align (P1) |
| Repetisi/loop | Output berulang pada audio buruk | `condition_on_previous_text=False`, `temperature` fallback |

**Golden set:** 10–15 menit audio ID (2 pembicara, 1 rekaman telepon, 1 podcast ber-noise) + 5 menit EN,
ditranskrip manual sebagai ground truth. Hitung WER dengan `jiwer`. Jalankan setiap kali ganti model/versi.
Kriteria lulus: WER ID ≤ 15%, EN ≤ 10%, dan **0** segmen halusinasi pada 30 s sunyi.

---

## 9. Opsi arsitektur

| Opsi | Stack | Kelebihan | Kekurangan | Cocok bila |
|---|---|---|---|---|
| **A. Shell + Python sidecar (openai/whisper apa adanya)** | Electron/Tauri + Python venv + `whisper` CLI/API via JSON-lines | Paling cepat dibangun; persis repo yang diminta; lintas platform | Bundel 500 MB–1 GB; rapuh (venv, macOS update); **lambat di Mac (CPU)** | Butuh MVP < 1 minggu, toleran performa |
| **B. Shell + Python sidecar multi-engine** | Sama + engine `whisper` / `faster-whisper` / `mlx-whisper` | Fleksibel; repo tetap dipakai; Mac dapat kecepatan GPU | Kompleksitas dependensi lebih tinggi | **Rekomendasi**: seimbang |
| **C. Native Rust/Swift + whisper.cpp (Metal)** | Tauri + `whisper-rs`, atau SwiftUI + libwhisper | Ringan (~15 MB), cepat (Metal), offline, tak butuh Python | Effort lebih besar; fitur harus ditulis manual | Produk jangka panjang, Mac-first |
| **D. Web app lokal** | Browser + server lokal | Mudah | Bukan desktop sejati; file access & mic terbatas | Prototipe internal |

**Rekomendasi (B → C):**
1. MVP: **Tauri 2 + React/Svelte** (UI) + **Python sidecar** dengan antarmuka engine seragam
   (`transcribe(path, {model, language, vad, ...}) -> segments`). Implementasi engine pertama:
   `faster-whisper` (CPU int8, jauh lebih cepat dari fp32, tanpa ffmpeg sistem) dan
   `openai/whisper` sebagai referensi/benchmark.
2. Fase 2: tambah engine **MLX/whisper.cpp** untuk GPU Apple; pertahankan `openai/whisper`
   sebagai pembanding akurasi (bobot & arsitektur sama, jadi hasil harus mendekati).
3. Jika ingin tanpa Python sama sekali: ganti sidecar dengan `whisper-rs` — UI tidak perlu diubah.

> Catatan penting: repo openai/whisper tetap memenuhi permintaan "pakai repo ini" sebagai
> *reference engine*, dan bobot modelnya (MIT) dipakai oleh semua alternatif di atas.

---

## 10. UX tingkat tinggi

**Layar/jendela:**
1. **Beranda** — drop zone besar, tombol impor, daftar riwayat terbaru, status model terpasang.
2. **Antrean** — kartu per file: durasi, bahasa terdeteksi, progres, ETA, batal/hapus.
3. **Hasil** — panel kiri: daftar segmen (timestamp + teks); kanan: player + waveform;
   toolbar: ekspor, salin, cari, ganti kata.
4. **Unduh model** — modal dengan tabel ukuran, progres, dan peringatan disk.
5. **Pengaturan** — folder, model, performa (thread/GPU), bahasa default, tema, privasi.

**State yang wajib ditangani:** file rusak/tidak didukung · codec tak dikenal · disk penuh saat
unduh model · model gagal verifikasi · audio tanpa suara · dibatalkan di tengah · app keluar saat proses ·
izin mikrofon ditolak · tidak ada jaringan saat unduh · file > 2 jam.

**Pola UX:** progres harus jujur (estimasi berbasis RTF terukur, bukan palsu), operasi berat
selalu bisa dibatalkan, dan hasil tidak boleh hilang saat app ditutup.

---

## 11. Packaging & distribusi (macOS)

| Kebutuhan | Detail |
|---|---|
| Format | `.dmg` (drag-to-Applications), arsitektur `arm64` (opsional universal2) |
| Signing | Developer ID Application + Hardened Runtime; `codesign --options runtime` |
| Notarization | `xcrun notarytool submit` + staple, agar Gatekeeper tidak memblokir |
| Entitlement | `com.apple.security.device.audio-input` + `NSMicrophoneUsageDescription` |
| Sandbox | App Sandbox opsional; tanpa sandbox lebih mudah untuk akses file & model |
| Auto-update | Tauri Updater / Sparkle; sertakan signature update |
| Model | **Jangan dibundel** ke DMG (× ukuran); unduh saat pertama pakai ke `~/Library/Application Support/…` |
| Sidecar | Python wajib dibundel relatif (relocatable venv/PyInstaller) atau dihindari (opsi C) |
| Uninstall | Tombol hapus model + data di Pengaturan; dokumentasikan lokasi data |

Tanpa akun Apple Developer, build tetap jalan untuk mesin sendiri (jalankan dari `target/release`
atau `open` setelah `xattr -d`), tapi pengguna lain akan kena peringatan Gatekeeper.

---

## 12. Lisensi & kepatuhan

| Komponen | Lisensi | Implikasi |
|---|---|---|
| Kode Whisper | MIT | Bebas dipakai komersial, wajib sertakan copyright notice |
| Bobot model | MIT | Bebas, termasuk penggunaan komersial |
| whisper.cpp / ggml | MIT | aman |
| CTranslate2 / faster-whisper | MIT | aman |
| ffmpeg | LGPL/GPL tergantung build | Jika distribusi biner, pakai build **LGPL** atau hindari dengan PyAV (bundled, tetap perhatikan lisensi) |
| MLX | MIT | aman |
| Tauri/Electron | MIT | aman |

Kewajiban praktis: file `THIRD_PARTY_NOTICES` berisi semua lisensi + atribusi "Whisper oleh OpenAI".

---

## 13. Risiko & mitigasi

| # | Risiko | Dampak | Kemungkinan | Mitigasi |
|---|---|---|---|---|
| R1 | Terlalu lambat di M1 CPU (openai/whisper fp32) | Tinggi | Tinggi | Engine alternatif (faster-whisper int8 / whisper.cpp Metal / MLX); ukur lebih dulu |
| R2 | OOM pada file panjang / model besar | Tinggi | Sedang | Batasi model ≤ turbo; chunking; proses serial; pantau RSS |
| R3 | Halusinasi pada sunyi/musik | Tinggi (kredibilitas) | Tinggi | VAD + threshold + filter segmen pendek |
| R4 | Akurasi ID di bawah harapan | Sedang | Sedang | Golden set + pilih model terbaik; prompt & kosakata; ekspektasi realistis |
| R5 | Paket Python rapuh (venv, macOS update, Gatekeeper) | Sedang | Tinggi | PyInstaller/relocatable; atau pindah ke whisper.cpp (opsi C) |
| R6 | Notarization/signing memblokir rilis | Sedang | Sedang | Uji `codesign`+`notarytool` sejak awal (tersedia di mesin ini) |
| R7 | Disk pengguna penuh setelah unduh model | Rendah | Sedang | Cek ruang sebelum unduh, tampilkan ukuran, izin hapus |
| R8 | Scope creep (real-time, diarisasi, ringkasan AI) | Tinggi (jadwal) | Tinggi | Kunci MVP; fitur P2 ditunda |
| R9 | Perubahan API/versi dependensi (torch, numba) | Sedang | Sedang | Pin versi di `requirements.txt`/lockfile |
| R10 | Audio ber-DRM / format aneh | Rendah | Sedang | Pesan error jelas + saran konversi |

---

## 14. Estimasi effort & milestone

Asumsi: 1 developer, familiar TypeScript + sedikit Python.

| Milestone | Isi | Estimasi |
|---|---|---|
| M0 — Spike | Setup env, ukur RTF & RAM 3 model × 2 engine, uji 10 menit audio ID | 1–2 hari |
| M1 — MVP | Tauri shell + sidecar, impor file, transkripsi, progres, tampilan segmen, ekspor TXT/SRT/VTT | 4–6 hari |
| M2 — Produk | Editor segmen, riwayat, pengaturan, unduh model, VAD, error states | 3–4 hari |
| M3 — Distribusi | Bundling sidecar, ikon, DMG, signing/notarization, auto-update | 3–4 hari |
| M4 — Lanjutan | Mic real-time / system audio, diarisasi, word timestamps, normalisasi | 5–10 hari |

**Total MVP layak pakai: ± 2–3 minggu.** Tanpa bundling Python (opsi C), M3 bisa lebih cepat
tapi M1–M2 lebih lambat.

---

## 15. Definition of Done (MVP)

- [ ] Bisa men-drop `.m4a`/`.mp3`/`.mp4` dan mendapat transkrip ID yang benar (WER ≤ 15% pada golden set).
- [ ] Deteksi bahasa otomatis untuk ID dan EN benar pada ≥ 90% sampel uji.
- [ ] Progres akurat ± 20%, bisa dibatalkan, dan tidak crash pada file 60 menit.
- [ ] Ekspor SRT terbuka benar di VLC/YouTube (timing tidak melenceng > 0,5 s).
- [ ] Puncak memori ≤ 4 GB pada model default.
- [ ] Bekerja penuh offline setelah model terunduh (diverifikasi dengan jaringan dimatikan).
- [ ] App ter-build jadi `.app`, jalan dari `/Applications`, tanpa error di Console.
- [ ] Tidak ada audio/transkrip yang keluar dari mesin (diverifikasi via proxy/log jaringan).

---

## 16. Keputusan yang perlu diambil sebelum coding

1. **Target platform:** macOS saja, atau macOS + Windows dari awal? (menentukan pilihan stack)
2. **Bentuk pemakaian:** hanya untuk diri sendiri, atau dibagikan/dijual? (menentukan signing/notarization)
3. **Fitur inti:** file-based saja, atau wajib ada real-time dictation di v1?
4. **Prioritas akurasi vs kecepatan:** boleh pakai engine GPU (whisper.cpp/MLX) walau tidak
   "Python murni", atau harus benar-benar `openai/whisper` saja?
5. **UI bahasa:** Indonesia, Inggris, atau keduanya?
