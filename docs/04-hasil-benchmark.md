# Hasil Benchmark ASR — M1 8 GB (22 Nov 2026)

**Tujuan:** mengukur kecepatan nyata di mesin ini, bukan mengandalkan klaim vendor.
**Kesimpulan singkat:** jalur default repo (`openai/whisper` di CPU) **tidak layak untuk pemakaian
harian**; bahkan `small` berjalan **lebih lambat dari realtime**.

---

## 1. Metode

| Item | Nilai |
|---|---|
| Audio uji | 285–286 s (26× `tests/jfk.flac` dari repo, digabung `ffmpeg -stream_loop`) |
| Isi audio | pidato Inggris jelas, banyak jeda — **kondisi ideal**, bukan kondisi rapat |
| Model | `small` (244 M) kecuali disebut lain |
| Metrik | RTF = durasi audio ÷ waktu proses (>1 = lebih cepat dari realtime) |
| RAM | peak RSS proses |
| Mesin | Apple M1, 8 GB, macOS 26.1, tanpa aplikasi lain yang dikontrol |

## 2. Hasil

| Engine | Model | Device / presisi | Beam | Threads | Waktu proses | **RTF** | Peak RAM |
|---|---|---|---|---|---|---|---|
| `openai/whisper` (fork) | small | CPU / fp32 | greedy | default | 389 s | **0,73** | 1.512 MB |
| `openai/whisper` (fork) | turbo | CPU / fp32 | greedy | default | **tidak selesai** (>20 mnt) | <0,2 | >3,2 GB |
| `faster-whisper` 1.2.1 | small | CPU / int8 | 5 | 8 | 1.148 s | **0,25** | 874 MB |
| `faster-whisper` 1.2.1 | small | CPU / int8 | 1 | 8 | 603 s | **0,47** | 901 MB |
| `faster-whisper` 1.2.1 | small | **MPS / fp16** | 1 | 8 | 261 s | **1,10** | 395 MB |

### Ekstrapolasi ke rapat 40 menit

| Konfigurasi | Waktu proses rapat 40 menit |
|---|---|
| fork, small, CPU | ±55 menit |
| faster-whisper, small, CPU int8 | ±85 menit |
| faster-whisper, small, MPS | ±36 menit |
| **target agar layak harian** | **≤10 menit (RTF ≥4)** |

## 3. Temuan teknis

1. **`beam_size` mendominasi biaya.** Beam 5 ≈ 3× lebih lambat dari greedy pada `faster-whisper`
   (0,25 vs 0,47). Perbandingan antar-engine **wajib** menyamakan setelan decoding — kalau tidak,
   kesimpulannya menyesatkan.
2. **CPU int8 (CTranslate2) bukan otomatis lebih cepat dari fp32 PyTorch di M1.** Hasilnya justru
   lebih lambat (0,47 vs 0,73). Kemungkinan karena thread 8 melampaui 4 core performa, atau build
   ARM CTranslate2 tidak seoptimal Accelerate/Metal.
3. **Turbo fp32 tidak bisa dipakai di 8 GB.** Saat dijalankan, sistem memakai **13,5 GB swap** dan
   proses tidak selesai dalam 20 menit → dihentikan. Ini bukti langsung bahwa `large-v3`
   (6,2 GB bobot) mustahil, dan `turbo`/`medium` di fp32 CPU juga bukan opsi.
4. **MPS (Metal, experimental) tercepat dan paling hemat RAM** (395 MB) — 2,3× lebih cepat dari
   jalur default repo. Tapi masih hanya 1,1× realtime.
5. **Bottleneck-nya mesin, bukan model.** Untuk mencapai target 4× realtime, satu-satunya jalan
   realistis adalah engine GPU native: **whisper.cpp (Metal, model terkuantisasi q5/q8)** atau
   **MLX (4-bit)**. Keduanya memakai bobot Whisper yang sama.

## 4. Catatan & batasan hasil

- Angka ini **pessimistis**: saat pengukuran, sistem sudah menumpuk 13,5 GB swap dan 58 juta pageins
  (sisa proses lain + percobaan turbo). Pengukuran ulang di mesin "bersih" kemungkinan 1,5–2× lebih baik.
- Audio uji adalah pidato bersih; audio rapat (mic jauh, tumpang tindih, noise) biasanya **lebih lambat**
  dan lebih banyak fallback decoding.
- Satu run per konfigurasi (belum diulang 3×), jadi ada variasi termal.
- Semua angka **belum** mencakup `word_timestamps=True`, yang menambah ±20–40% waktu.

## 5. Masalah dependensi yang ditemukan (perlu dipin)

| Paket | Versi | Masalah |
|---|---|---|
| `av` (PyAV) | 19.0.2 | `faster-whisper 1.2.1` memanggil `av.open(..., metadata_errors=...)` → `TypeError`. **Pin `av==16.0.1`** |
| `torch` | 2.15.0 | butuh Python ≥3.11 (bukan 3.9 bawaan macOS) |
| `numba` | 0.68 | butuh Python ≥3.10 |
| Python | 3.12.16 | dipasang portabel di `.runtime/` karena `brew` tidak bisa menulis ke `/opt/homebrew` dan `sudo` diblokir |

## 6. Langkah berikutnya (butuh ±45 menit)

1. Benchmark **whisper.cpp Metal** (`ggml-small-q5`, `ggml-turbo-q5`) pada audio yang sama.
2. Benchmark **MLX 4-bit** (`mlx-community/whisper-large-v3-turbo-4bit`).
3. Ulangi benchmark saat mesin bersih (tidak ada proses lain, swap rendah).
4. **Uji dengan rekaman rapat asli** (ID + campur kode EN) untuk mengukur WER nyata — ini yang
   menentukan go/no-go, bukan kecepatan saja.
