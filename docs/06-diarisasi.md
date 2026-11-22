# Diarisasi Speaker — Catatan Implementasi (22 Nov 2026)

**Tujuan:** memberi label pembicara (S1/S2/…) pada transkrip agar keputusan dan action item punya
pemilik yang jelas.

## Pendekatan

| Komponen | Pilihan | Alasan |
|---|---|---|
| Embedding | `speechbrain/spkrec-ecapa-voxceleb` (192-dim) | publik, tidak butuh token HF (model pyannote gated) |
| Unit | per segmen transkrip | tidak perlu diarisasi frame-level |
| Klastering | K-Means pada embedding ternormalisasi, k dipilih via silhouette | agglomerative gagal (lihat temuan 2) |
| Device | **CPU** | MPS menghasilkan embedding rusak (temuan 1) |
| Pasca-proses | smoothing jendela ±2 segmen | mengurangi label berkedip |

## Hasil pada rekaman 39:42

| Metrik | Nilai |
|---|---|
| Segmen | 618 (611 di-embed; segmen <0,5 s dilewati) |
| Waktu | **37,5 s** (embedding 35 s, klastering <2 s) |
| RAM | < 1 GB (ECAPA ~20 M parameter) |
| Speaker terpilih | 3 (silhouette 0,190; k=2 → 0,188) |
| Distribusi | S1 41,7% · S2 17,9% · S3 40,4% |
| Kohesi label | rata-rata 4,6 segmen per giliran; run terpanjang 21 segmen |

## Dua temuan teknis

### 1. Embedding di MPS rusak (cluster jadi 99,9% / 0,1%)

Percobaan pertama menghasilkan satu cluster berisi 99,9% segmen. Setelah dipaksa CPU
(`run_opts={"device": "cpu"}`), embedding punya struktur jelas: cosine similarity antar segmen
rata-rata **0,234** (p10 0,046, p90 0,456) dan K-Means menghasilkan pembagian seimbang (54/66).

Artinya: pada mesin ini, **jangan pakai MPS untuk model embedding speaker**. Pemanggilan
berulang ke MPS memang sudah dikenal bermasalah (lihat `docs/05`), dan sekarang terbukti juga
untuk ECAPA.

### 2. Agglomerative (average linkage + cosine) degenerasi

Dengan embedding yang sama, `AgglomerativeClustering(metric="cosine", linkage="average")`
tetap menghasilkan 99,9% / 0,1%, sementara K-Means menghasilkan 54/66. Penyebab: efek chaining —
satu titik outlier jauh membuat semua sisanya menyatu. K-Means dipakai sejak itu.

## Batasan yang harus diketahui

1. **Silhouette 0,19 = pemisahan lemah.** Label ini petunjuk, bukan kebenaran. Pada audio
   rapat dengan mic jauh, suara pembicara saling mirip.
2. **Segmen pendek sering salah label.** Contoh nyata: `"Bisa paralel sebenernya?"` dan
   `"Bisa, bisa."` sama-sama diberi S1 padahal jelas dua orang berbeda (tanya–jawab).
3. **Belum bisa menangani tumpang tindih** (dua orang bicara bersamaan) — perlu diarisasi
   frame-level seperti pyannote, yang butuh token HF.
4. **Jumlah speaker ditentukan otomatis**; rapat dengan suara mirip bisa digabung jadi satu.

## Alur pemakaian

1. Pipeline menjalankan diarisasi otomatis setelah transkripsi (±40 detik tambahan untuk 40 menit).
2. Di UI, label muncul sebagai badge warna di setiap segmen.
3. Panel di atas transkrip memungkinkan memberi nama (S1 → "Pak Andi"), tersimpan di
   `speakers.json` per rapat.
4. Nama dipakai pada generasi dokumen berikutnya, sehingga owner action item bisa berupa nama orang.

## Langkah lanjut (belum dikerjakan)

- Embedding ulang segmen <0,5 s memakai konteks tetangga (bukan centroid terdekat).
- Deteksi perubahan pembicara berbasis VAD + embedding bergeser (bukan per segmen).
- Opsi pyannote bila pengguna punya token HF (akurasi lebih tinggi, RAM lebih besar).
