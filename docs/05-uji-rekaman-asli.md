# Uji pada Rekaman Asli — 22 Nov 2026

**File:** `2026_11_20_16_37_25_1.mp3` · 39 menit 42 detik · mono 44,1 kHz · 128 kbps · 36 MB
**Isi:** rapat internal (bahasa Indonesia) — topik absensi antar kantor dan aturan potongan/pinjaman gaji.

---

## 1. Yang diuji

| # | Uji | Hasil |
|---|---|---|
| 1 | Deteksi bahasa | ✅ **Indonesia** (probabilitas tinggi), tanpa perlu `--language id` |
| 2 | Kualitas transkrip, model `small` (CPU) | ⚠️ Kalimat terbaca, token penting salah |
| 3 | Kualitas transkrip, model `turbo` (MPS) | ✅ Jauh lebih baik, token penting benar |
| 4 | Kecepatan `turbo` + MPS | RTF 2,6 (audio 60 s → 23 s) |
| 5 | Kecepatan `small` + CPU | RTF 1,24 (audio 60 s → 48 s) |
| 6 | Transkrip file penuh (chunk 5 menit) | ❌ **Gagal**: muncul loop `!!!!` |
| 7 | Mitigasi loop (VAD off, temperature fallback, beam 5) | ❌ Tidak berhasil |

## 2. Bukti kualitas (kutipan asli)

**`turbo` (MPS) — benar:**
> "…20% dari **gaji pokok**" · "…batas **pokok pinjaman**nya itu 25%" · "…itu udah **ketentuan baku** ya pak"
> "…anak kelasi bisa **absen dimana aja**" · "…gaji mingguannya itu dipotong 25% buat **ngebayar pinjaman**"

**`small` (CPU) — salah pada token penting:**
> "…20% dari **keji pokok**" (seharusnya *gaji pokok*)

Ini contoh persis dari risiko F3: kata umum terbaca, **istilah bernilai tinggi (gaji, persentase) yang salah**.
Untuk dokumen seperti BRD, kesalahan tipe ini jauh lebih berbahaya daripada salah ejaan biasa.

## 3. Kegagalan utama: loop repetisi `!!!!`

Pada detik 28–250, output menjadi:
```
[28.63 -> 60.04] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!...
[60.04 -> 91.80] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!...
```
Dialami dengan tiga konfigurasi berbeda:

| Konfigurasi | Hasil |
|---|---|
| VAD + beam 1 + temperature 0 | transkrip benar ±40 s, lalu loop |
| Tanpa VAD + temperature fallback 0→1 + compression ratio | **loop dari awal** |
| VAD + beam 5 | proses **crash** (kemungkinan kehabisan memori di MPS) |

Audio di area itu **bukan senyap**: level rata-rata −25,4 dB, puncak −2,7 dB, tidak ada jeda >0,8 s di bawah −35 dB.
Jadi penyebabnya bukan "audio kosong", melainkan **decoder masuk jalur degeneratif** pada potongan audio tersebut.

**Kesimpulan teknis:** `compression_ratio_threshold` dan temperature fallback bawaan **tidak cukup**.
Diperlukan komponen baru di pipeline: **deteksi keluaran degeneratif + retry dengan jendela digeser**.

## 4. Kecepatan (angka nyata, bukan estimasi)

| Skenario | RTF | Catatan |
|---|---|---|
| `turbo` MPS, 60 s, threads 4, kondisi mesin normal | **2,59** | audio 60 s → 23 s |
| `turbo` MPS, 60 s, area bermasalah | 1,33 | audio 60 s → 45 s |
| `small` CPU, 60 s | 1,24 | audio 60 s → 48 s |
| `turbo` MPS, chunk 5 menit saat mesin tertekan | **0,61** | 300 s audio → 495 s; load average 20, swap 8,7 GB |

**Catatan penting:** mesin ini memakai **8,7 GB swap** selama pengujian (8 GB RAM fisik). Kecepatan turun
4× antara kondisi ringan dan tertekan. Artinya: **jumlah aplikasi lain yang terbuka berpengaruh besar**
terhadap pengalaman pemakaian. Untuk aplikasi desktop, ini harus ditangani (chunking + progres + resume),
bukan diabaikan.

## 5. Implikasi untuk produk

1. **Filter keluaran degeneratif wajib ada.** Aturan deteksi: rasio karakter non-alfabet > 30%,
   ada karakter berulang > 10×, atau rasio kompresi gzip > 2,4.
2. **Retry berlapis:** geser jendela ±10 s → naikkan temperature → ganti model (`small` ↔ `turbo`).
   Bila tetap gagal, tandai `[tidak jelas 00:28–04:10]` alih-alih menulis sampah.
3. **Chunk wajib, dengan overlap 30 s**, karena loop bersifat sensitif terhadap batas jendela.
4. **Jangan pakai `beam_size=5` di MPS 8 GB** — crash.
5. **Model default `turbo`, fallback `small`.** `small` cukup cepat tetapi salah pada istilah kritikal.
6. Transkrip mentah **tidak boleh** langsung masuk ke tahap BRD; harus lewat pembersihan & penandaan
   bagian tidak jelas, agar LLM tidak "mengarang" isi bagian yang gagal.

## 6. Status artefak

| File | Isi |
|---|---|
| `.data/out/sample_10-11m.srt` | 22 segmen SRT dari sampel menit 10:00–11:00 (kualitas baik) |
| `.data/out/sample_10-11m.txt` | teks polos sampel yang sama |
| `.data/out/2026_11_20_16_37_25_1.segments.jsonl` | transkrip parsial chunk 1 (berisi contoh loop — dipakai sebagai bukti) |

Transkrip penuh 39 menit **belum selesai**: pada kondisi mesin saat ini butuh ±65 menit, dan sebagian
bagian akan tetap perlu mekanisme retry di atas.

---

## 7. Resolusi (22 Nov 2026, 20:00)

### Akar masalah loop `!!!!` — bukan audio

Eksperimen: satu proses, transkrip jendela 10:00–11:00 (berhasil), lalu tiga jendela lain,
lalu **ulang** jendela 10:00–11:00 yang sama:

| Panggilan | Jendela | Hasil |
|---|---|---|
| 1 | 10:00–11:00 | ✅ benar |
| 2 | 11:00–12:00 | ✅ benar |
| 3 | 12:00–13:00 | ✅ benar |
| 4 | 13:00–14:00 | ❌ `!!!!!!!!` |
| **5** | **10:00–11:00 (audio yang sama dengan #1)** | ❌ `!!!!!!!!` |

**Kesimpulan: state decoder memburuk setelah ±4 panggilan dalam satu proses (MPS / CTranslate2).**
Bukan konten audio, bukan VAD, bukan threshold. Karena itu semua jendela setelah ke-4 gagal pada
percobaan pertama pipeline.

### Perbaikan

`scripts/transcribe_robust.py` sekarang menjalankan **satu proses baru per jendela**
(`_transcribe_one.py`), sehingga state selalu bersih. Biaya: ±4–5 detik load model per jendela.

### Hasil transkrip penuh

| Metrik | Hasil |
|---|---|
| Audio | 39,7 menit |
| Waktu proses | 15,4 menit (RTF **2,57**, termasuk overhead startup) |
| Segmen | 618 |
| `[tidak jelas]` | **0** |
| Sampah `!!!!` | 0 |
| Jendela perlu retry | 0 (setelah perbaikan) |

Artefak: `.data/out_full/2026_11_20_16_37_25_1.{txt,srt,json}` dan
`.data/out_full/transcript_for_prompt.txt` (618 baris ber-timestamp, ±6 ribu token).

### Sisa masalah (bukan blocker)

ASR masih salah pada **nama diri dan istilah domain**: `rempoha`/`rompohak` (kemungkinan "Rempoa"),
`anak kelasi` (kemungkinan "anak kelas"), `rubus` ("rumus"), `PKWT/PKWTT` kadang terpotong.
Solusinya glosarium per proyek + koreksi pasca-ASR — belum diimplementasikan.
