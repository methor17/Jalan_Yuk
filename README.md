# JalanYuk v2.5 — Estimasi Rute Tanpa Google Routes API

Aplikasi web lokal berbasis **Python 3.10+** untuk membuat itinerary liburan dinamis, termasuk hotel → wisata → kuliner → hotel dan transfer kepulangan. **Tidak memerlukan Google Maps Routes API, Google API key, maupun billing Google.** Tautan ke Google Maps masih dapat digunakan **secara manual** untuk navigasi, tetapi tidak menjadi sumber ETA aplikasi.

## Jalankan di Windows

1. Ekstrak ZIP dan buka folder `jalanyuk-python-v2.5`.
2. Klik `Jalankan-JalanYuk.bat` atau melalui PowerShell jalankan `py app.py`.
3. Buka `http://localhost:8000`.
4. Isi kota tujuan, tanggal pergi/tiba/pulang, jumlah dewasa/anak/bayi, hotel dan budget.
5. Pilih koordinat hotel dan tempat wisata via pencarian OpenStreetMap. Tekan **Buat rencana**, lalu biarkan **Hitung rute semua hari otomatis setelah generate** aktif. Ada juga tombol **Hitung ulang rute hari ini**.

Tidak ada instalasi library Python via pip. Untuk mengaktifkan pembanding rute tambahan **OpenRouteService**, isi variabel `OPENROUTESERVICE_API_KEY` di `.env` (opsional); tidak diperlukan untuk memakai aplikasi.

## Metode estimasi (tanpa Google)

- **OSRM** untuk estimasi jaringan jalan pada moda mobil, dari koordinat setiap pasangan lokasi (tanpa data kemacetan).
- **OpenRouteService** opsional jika API key milik pengguna tersedia, dengan profil perjalanan yang didukung.
- Sistem mengambil nilai **terlama dari sumber yang berhasil**, ditambah skenario konservatif (+25% dan 5 menit untuk moda jalan raya; untuk jalan kaki/sepeda +10%), dan buffer pengguna per segmen (default 10 menit).
- Bila sumber peta tidak tersedia, dihitung asumsi dari jarak antarkoordinat, ditandai **perkiraan tanpa rute**. Jika koordinat hilang, dipakai **alokasi tanpa koordinat** (default 45 menit) dan ditandai belum terverifikasi.
- Setiap segmen dimasukkan ke jadwal berantai, sehingga keterlambatan menggeser kunjungan berikutnya. Jam kembali ke hotel dan batas keberangkatan pulang tetap diperiksa.
- Estimasi yang sama untuk pasangan lokasi sama **masih mungkin terjadi**: OSRM/ORS bukan peramal kemacetan berdasarkan tanggal/jam. Waktu yang berbeda muncul dari perbedaan lokasi, urutan, moda, durasi kunjungan atau asumsi yang diatur—bukan variasi lalu lintas buatan.
- Batas permintaan: 28 segmen per pembaruan. Untuk perjalanan panjang, jalankan per hari bila perlu. Server routing publik bersifat best-effort, untuk penggunaan ringan/pengujian; produksi sebaiknya memakai instans khusus atau vendor dengan ketentuan yang sesuai.

## Data dan kompatibilitas

Fitur dari v2.4 dipertahankan: wisata dinamis, rekomendasi pagi–malam, jadwal lintas tanggal dan tahun, kategori usia bayi dan anak usia tepat 2 tahun, rincian budget, penginapan, perjalanan pulang-pergi, jam kembali ke hotel per hari, cuaca, simpan beberapa perjalanan SQLite, ekspor/impor JSON, berbagi dan voting.

**Rencana lama**: `routing_provider=google` otomatis dialihkan ke `multi`; cache Google murni dan gabungan yang mengandung Google diabaikan, lalu rute dapat dihitung ulang dengan OSRM / ORS. Ekspor JSON versi terdahulu bisa diimpor; data wisata yang tidak memiliki koordinat tetap memerlukan pencarian/manual koordinat.

Google Maps tetap muncul hanya sebagai tautan pencarian/navigasi yang dibuka pengguna; **tidak ada panggilan Google Routes API di server**.

## Pengujian

```powershell
py -m unittest discover -s tests -v
node --check static/app.js
node tests/frontend_dom_smoke.cjs examples/contoh-hotel-rute-dan-jam-harian.json
```

**Batasan:** tidak ada pengujian live OSRM/ORS pada lingkungan tanpa internet. Pengujian unit/API memakai simulasi provider; ETA bukan harga tiket atau prediksi trafik live. Pengujian klik browser penuh perlu dilakukan di perangkat pengguna. Google Maps tautan biasa hanya untuk membuka navigasi, bukan menarik ETA tanpa izin. Data OSM/Nominatim/OSRM memiliki kebijakan dan kuota pemakaian. Untuk hosting publik, siapkan rate limit, keamanan akun, HTTPS, dan router yang layak produksi. Backend Python + SQLite tidak bisa di-host sebagai aplikasi lengkap di Cloudflare Pages statis tanpa hosting backend terpisah.
