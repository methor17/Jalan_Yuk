# Changelog

## v2.5 — Tanpa Google Routes API

- Menghapus Google Routes API dari backend, konfigurasi .env, pilihan sumber rute, dan status integrasi frontend.
- Google Maps hanya tersisa sebagai tautan navigasi manual; tidak pernah digunakan untuk menghasilkan ETA aplikasi.
- Tetap mendukung estimasi konservatif OSRM, opsional OpenRouteService, serta fallback jarak.
- Membersihkan cache Google dan cache multi-source lama yang mengandung sampel Google saat import/memuat rencana.
- Mempertahankan pembaruan jadwal antarlokasi semua hari, buffer pengguna, koordinat, hotel, anggaran, kategori usia, dan alur kepulangan.
- Memperbarui uji regresi sehingga Google provider tidak bisa dipakai kembali.
