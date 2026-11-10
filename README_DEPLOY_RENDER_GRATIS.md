# Deploy JalanYuk Python di Render Free (tanpa langganan)

Paket ini mempertahankan **backend Python** + semua file frontend (`static/`) + API wisata/kuliner/hotel/rute/cuaca + perhitungan keluarga + itinerary + penyimpanan SQLite untuk demo. Tidak memerlukan Google Routes API, npm, maupun pip requirements.

## Langkah mudah: GitHub -> Render

1. Ekstrak berkas `JalanYuk_Render_Free_v2.5.zip` ke folder lokal. **Jangan unggah ZIP mentah ke halaman Web Service Render**; Render mengambil kode dari repository Git.
2. Buka https://github.com/new dan buat repository, misalnya `jalanyuk-python`. Pilih Private bila tidak ingin source code publik.
3. Buka repository -> **Add file** -> **Upload files**. Seret **isi folder** `JalanYuk_Render_Free_v2.5` (bukan ZIP dan bukan folder induknya) agar `app.py`, `render.yaml`, `static/`, `planner.py`, `storage.py`, `providers.py`, `route_service.py` berada di root repository. Commit.
4. Masuk ke https://dashboard.render.com/ -> **New** -> **Web Service**. Hubungkan GitHub, pilih repository yang baru diunggah.
5. Pilih **Language / Runtime: Python**, **Instance Type / Plan: Free**.
6. Isi jika Render meminta manual:

   - Build Command: `python -m compileall -q app.py planner.py providers.py route_service.py storage.py catalog.py`
   - Start Command: `python app.py`
   - Environment Variable: `HOST` = `0.0.0.0`
   - Health Check Path: `/api/health`
   - Region: Singapore (jika tersedia di paket Free).

7. Klik **Deploy Web Service**. `render.yaml` disertakan untuk jalur **New -> Blueprint** jika ingin konfigurasi otomatis (pilih service plan Free sebelum Apply). **Jangan pilih paket berbayar.**
8. Setelah status Live, buka URL yang diberikan Render (contoh `https://jalanyuk-python.onrender.com`), lalu `/api/health` untuk melihat status JSON.

## Periksa lengkapnya

- Halaman utama: `/`
- API kesehatan: `/api/health`
- Katalog kota: `/api/cities`
- Status rute: `/api/routing/status`
- Coba `Buat rencana` dan `Hitung rute semua hari`, lalu buka DevTools Network jika koneksi gagal.

## Batasan penting paket gratis

- Layanan Render Free tidur setelah sekitar 15 menit idle. Permintaan berikutnya perlu waktu untuk bangun.
- Filesystem **tidak persisten**. Database SQLite `data/jalanyuk.db` dibuat pada startup, tetapi hilang jika layanan tidur, restart, atau redeploy. Karena itu **Simpan rencana di server / link berbagi / usulan / voting** hanya bersifat demo dan dapat hilang. Gunakan **Export JSON** secara berkala; cadangan browser hanya untuk browser/perangkat yang sama.
- Agar penyimpanan server benar-benar permanen, perlu migrasi `storage.py` dari SQLite ke database eksternal seperti Postgres gratis (Neon/Supabase, sesuai persyaratan dan kuota). Paket ini BELUM mengimplementasikan migrasi Postgres sehingga **jangan memasukkan DATABASE_URL tanpa mengubah kode**.
- Pencarian lokasi, hotel, dan ETA membutuhkan akses internet ke layanan peta publik. Kuota/policy layanan tersebut tetap berlaku dan host gratis bisa membatasi lalu lintas keluar.
- Karena ini aplikasi demo publik, keamanan login, rate limiting, proteksi penyalahgunaan endpoint dan ketentuan penggunaan data peta harus diaudit sebelum dipakai banyak pengguna.
- Proses ini bukan drag-and-drop ZIP seperti Cloudflare Pages; GitHub menjadi tempat seluruh source code untuk Render.

## Uji lokal tanpa membayar

```
python -m unittest discover -s tests -v
```

Di PowerShell (Windows):

```
$env:HOST="0.0.0.0"
$env:PORT="8000"
py app.py
```

Lalu buka http://localhost:8000/api/health. Tidak ada paket pip yang harus dipasang.

## Troubleshooting

- **No open ports / port scan timeout**: periksa `HOST=0.0.0.0` dan Start Command `python app.py`; Render memberikan variabel `PORT` secara otomatis.
- **ModuleNotFoundError**: pastikan semua `.py` berada di root repo, bukan di dalam folder ZIP yang terbungkus lagi.
- **404 /static/**: pastikan folder `static` lengkap ikut diunggah ke GitHub.
- **Data rencana hilang**: karakteristik filesystem gratis Render; gunakan Export JSON atau migrasikan database.
- **Pencarian peta gagal**: cek batas API pihak ketiga dan log Render; gunakan katalog cadangan/koordinat manual jika diperlukan.
- **Render meminta pembayaran**: jangan lanjutkan opsi berbayar. Pastikan memilih Web Service Free; ketersediaan plan/verifikasi akun dapat berubah sesuai kebijakan penyedia.
