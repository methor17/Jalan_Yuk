"""Katalog contoh tujuan wisata Indonesia.

SEMUA tarif merupakan angka simulasi untuk perencanaan, bukan harga resmi.
Ubah angka sebelum digunakan pada perjalanan nyata.
"""
from __future__ import annotations
import re

# Format: nama|estimasi_per_orang|kawasan|tema|emoji|prioritas_editorial
DATA = {
    'Yogyakarta': {
        'tagline': 'Cerita budaya, senja, dan kuliner legendaris.', 'province': 'DI Yogyakarta',
        'hotel': 310000, 'transport': 45000, 'emoji': '🏛️',
        'wisata': '''
Jalan Malioboro|0|Pusat Kota|Kota|🛍️|5
Taman Sari|15000|Kraton|Sejarah|🏛️|5
Keraton Yogyakarta|15000|Kraton|Budaya|👑|5
Benteng Vredeburg|10000|Malioboro|Museum|🏰|4
Alun-Alun Kidul|0|Kraton|Kota|🎡|4
Pasar Beringharjo|0|Malioboro|Belanja|🧺|4
Pantai Parangtritis|15000|Bantul|Pantai|🌊|5
Hutan Pinus Mangunan|10000|Bantul|Alam|🌲|4
Tebing Breksi|15000|Prambanan|Alam|⛰️|4
Candi Prambanan|50000|Prambanan|Sejarah|🛕|5
HeHa Sky View|30000|Gunungkidul|Panorama|🌅|4
Museum Ullen Sentalu|50000|Kaliurang|Museum|🎨|5
Bukit Bintang|0|Gunungkidul|Panorama|✨|4
''',
        'kuliner': '''
Gudeg Yu Djum|40000|Malioboro|Masakan Jawa|🍛|5
Angkringan sekitar Tugu|25000|Pusat Kota|Kaki Lima|🍢|5
Bakmi Jawa Mbah Mo|45000|Bantul|Mi|🍜|5
Sate Klathak Pak Pong|50000|Bantul|Sate|🍖|5
Kopi Klotok|40000|Kaliurang|Tradisional|☕|5
Oseng Mercon Bu Narti|40000|Pusat Kota|Pedas|🌶️|4
Soto Kadipiro|35000|Pusat Kota|Soto|🥣|4
Jejamuran|45000|Sleman|Vegetarian|🍄|4
Tempo Gelato|30000|Prawirotaman|Dessert|🍨|4
House of Raminten|55000|Pusat Kota|Tradisional|🍲|4
'''
    },
    'Bandung': {
        'tagline': 'Jalan-jalan kreatif, udara sejuk, dan jajan terus.', 'province': 'Jawa Barat',
        'hotel': 400000, 'transport': 65000, 'emoji': '⛰️',
        'wisata': '''
Jalan Braga|0|Pusat Kota|Kota|🏙️|5
Gedung Sate (area luar)|0|Pusat Kota|Arsitektur|🏛️|4
Alun-Alun Bandung|0|Pusat Kota|Kota|🌳|4
Museum Geologi|5000|Pusat Kota|Museum|🦕|5
Museum Konferensi Asia Afrika|10000|Braga|Museum|🏛️|4
Taman Hutan Raya Djuanda|20000|Dago|Alam|🌲|5
Tebing Keraton|20000|Dago|Panorama|⛰️|4
Kawah Putih|65000|Ciwidey|Alam|🌫️|5
Situ Patenggang|30000|Ciwidey|Danau|🛶|4
Farmhouse Lembang|35000|Lembang|Keluarga|🐑|4
Floating Market Lembang|40000|Lembang|Keluarga|🚣|4
Orchid Forest Cikole|45000|Lembang|Alam|🌸|5
''',
        'kuliner': '''
Batagor Kingsley|45000|Pusat Kota|Batagor|🥟|5
Mie Kocok Mang Dadeng|45000|Pusat Kota|Mi|🍜|5
Cuanki Serayu|35000|Dago|Bakso|🍲|5
Warung Nasi Ibu Imas|50000|Pusat Kota|Sunda|🍚|5
Surabi Setiabudi|30000|Setiabudi|Jajanan|🥞|4
Sudirman Street Food|60000|Pusat Kota|Food Court|🍢|4
Paskal Food Market|65000|Pusat Kota|Food Court|🍽️|4
Sate Hadori|55000|Pusat Kota|Sate|🍖|4
Kartika Sari|35000|Dago|Oleh-oleh|🍰|4
'''
    },
    'Malang': {
        'tagline': 'Kota apel dengan kampung warna-warni.', 'province': 'Jawa Timur',
        'hotel': 290000, 'transport': 45000, 'emoji': '🌿',
        'wisata': '''
Alun-Alun Merdeka Malang|0|Pusat Kota|Kota|🌳|5
Kampung Warna Warni Jodipan|10000|Jodipan|Foto|🎨|5
Kampung Tridi|10000|Jodipan|Foto|🖌️|4
Museum Brawijaya|10000|Ijen|Museum|🏛️|4
Jalan Ijen|0|Ijen|Kota|🌸|4
Taman Trunojoyo|0|Pusat Kota|Kota|🌲|3
Taman Rekreasi Sengkaling|40000|Dau|Keluarga|🎡|4
Candi Badut|10000|Tidar|Sejarah|🛕|4
Coban Rondo|35000|Pujon|Air Terjun|💦|5
Florawisata San Terra|35000|Pujon|Taman|🌺|4
Lembah Tumpang|60000|Tumpang|Alam|🍃|4
''',
        'kuliner': '''
Bakso President|35000|Pusat Kota|Bakso|🍲|5
Rawon Nguling|45000|Pusat Kota|Rawon|🍛|5
Pecel Kawi|30000|Kawi|Pecel|🥬|5
Toko Oen Malang|55000|Pusat Kota|Kafe|🍦|4
Pos Ketan Legenda|30000|Malang|Jajanan|🍡|4
Soto Ayam Lombok|35000|Pusat Kota|Soto|🥣|4
Bakso Bakar Pak Man|30000|Malang|Bakso|🍢|4
Depot Hok Lay|40000|Pusat Kota|Cwie Mie|🍜|4
'''
    },
    'Batu': {
        'tagline': 'Pegunungan, taman bermain, dan suasana keluarga.', 'province': 'Jawa Timur',
        'hotel': 330000, 'transport': 55000, 'emoji': '🎡',
        'wisata': '''
Alun-Alun Kota Batu|0|Pusat Kota|Kota|🎠|5
Jatim Park 1|120000|Oro-Oro Ombo|Keluarga|🎢|5
Jatim Park 2|150000|Oro-Oro Ombo|Keluarga|🐘|5
Museum Angkut|120000|Ngaglik|Museum|🚗|5
Batu Night Spectacular|45000|Oro-Oro Ombo|Keluarga|🎡|4
Selecta|50000|Tulungrejo|Taman|🌷|4
Coban Rais|20000|Oro-Oro Ombo|Air Terjun|💦|4
Coban Talun|20000|Bumiaji|Alam|🌲|4
Taman Langit Gunung Banyak|30000|Gunung Banyak|Panorama|☁️|4
Paralayang Gunung Banyak|20000|Gunung Banyak|Panorama|🪂|5
Eco Green Park|70000|Oro-Oro Ombo|Edukasi|🦜|4
''',
        'kuliner': '''
Pos Ketan Legenda 1967|30000|Pusat Kota|Jajanan|🍡|5
Warung Sate Hotplet Batu|50000|Pusat Kota|Sate|🍖|4
Bakso Arief Batu|30000|Pusat Kota|Bakso|🍲|4
Warung Wareg|55000|Batu|Tradisional|🍚|4
Kuliner Alun-Alun Batu|35000|Pusat Kota|Kaki Lima|🍢|5
Pupuk Bawang Cafe|65000|Batu|Kafe|☕|4
Susu Segar KUD Batu|22000|Pusat Kota|Minuman|🥛|4
Omah Kitir Batu|60000|Batu|Restoran|🍽️|4
'''
    },
    'Semarang': {
        'tagline': 'Kota lama yang fotogenik, lumpia dan pesisir.', 'province': 'Jawa Tengah',
        'hotel': 320000, 'transport': 50000, 'emoji': '🏙️',
        'wisata': '''
Kota Lama Semarang|0|Kota Lama|Sejarah|🏛️|5
Lawang Sewu|30000|Tugu Muda|Sejarah|🏰|5
Simpang Lima|0|Pusat Kota|Kota|🌃|5
Sam Poo Kong|35000|Gedung Batu|Budaya|🛕|5
Masjid Agung Jawa Tengah|0|Gayamsari|Religi|🕌|5
Kampung Pelangi|5000|Randusari|Foto|🌈|4
Museum Ranggawarsita|10000|Kalibanteng|Museum|🏛️|4
Taman Indonesia Kaya|0|Pusat Kota|Taman|🌿|4
Brown Canyon|0|Tembalang|Panorama|⛰️|3
Dusun Semilir|40000|Bawen|Keluarga|🎢|4
Umbul Sidomukti|25000|Ungaran|Alam|🌲|4
''',
        'kuliner': '''
Lumpia Gang Lombok|35000|Pecinan|Lumpia|🥟|5
Tahu Gimbal Pak Edy|30000|Pusat Kota|Jajanan|🍲|4
Nasi Ayam Bu Wido|35000|Pusat Kota|Masakan Jawa|🍛|5
Soto Bangkong|35000|Pusat Kota|Soto|🥣|5
Loenpia Mbak Lien|40000|Pusat Kota|Lumpia|🥟|4
Wingko Babat oleh-oleh|25000|Pusat Kota|Oleh-oleh|🍪|4
Es Puter Cong Lik|25000|Pusat Kota|Dessert|🍧|4
Pusat Kuliner Simpang Lima|50000|Simpang Lima|Kaki Lima|🍢|4
'''
    },
    'Solo': {
        'tagline': 'Budaya Jawa, pasar tradisional, dan sajian hangat.', 'province': 'Jawa Tengah',
        'hotel': 270000, 'transport': 45000, 'emoji': '👑',
        'wisata': '''
Keraton Surakarta|20000|Baluwarti|Budaya|👑|5
Pura Mangkunegaran|30000|Pusat Kota|Budaya|🏛️|5
Pasar Gede|0|Pusat Kota|Pasar|🧺|5
Pasar Klewer|0|Pusat Kota|Belanja|🛍️|4
Kampung Batik Laweyan|0|Laweyan|Budaya|🎨|5
Kampung Batik Kauman|0|Kauman|Budaya|🧵|4
Taman Balekambang|10000|Manahan|Taman|🌳|4
Museum Radya Pustaka|10000|Pusat Kota|Museum|📚|4
Benteng Vastenburg|0|Pusat Kota|Sejarah|🏰|4
The Heritage Palace|65000|Kartasura|Foto|📸|4
Solo Safari|65000|Jurug|Keluarga|🦓|4
''',
        'kuliner': '''
Selat Solo Mbak Lies|45000|Pusat Kota|Selat|🍛|5
Timlo Sastro|35000|Pusat Kota|Timlo|🥣|5
Nasi Liwet Wongso Lemu|35000|Keprabon|Nasi Liwet|🍚|5
Sate Buntel Haji Bejo|55000|Lojiwetan|Sate|🍖|5
Serabi Notosuman|25000|Notosuman|Jajanan|🥞|5
Tengkleng Klewer|50000|Klewer|Tengkleng|🍲|4
Wedangan Pendopo|35000|Pusat Kota|Angkringan|🍢|4
Dawet Telasih Pasar Gede|20000|Pasar Gede|Minuman|🥤|4
'''
    },
    'Surabaya': {
        'tagline': 'Kota Pahlawan dengan wisata urban dan kuliner kuat.', 'province': 'Jawa Timur',
        'hotel': 370000, 'transport': 60000, 'emoji': '🌉',
        'wisata': '''
Tugu Pahlawan|10000|Pusat Kota|Sejarah|🏛️|5
Jalan Tunjungan|0|Pusat Kota|Kota|🏙️|5
Kota Lama Surabaya|0|Pusat Kota|Sejarah|🏰|4
Monumen Kapal Selam|15000|Genteng|Museum|🚢|5
Kebun Binatang Surabaya|25000|Wonokromo|Keluarga|🦓|5
Taman Bungkul|0|Darmo|Taman|🌳|5
Museum Sepuluh Nopember|10000|Pusat Kota|Museum|🏛️|4
Kenjeran Park|30000|Kenjeran|Pantai|🌊|4
Ekowisata Mangrove Wonorejo|25000|Rungkut|Alam|🌿|4
Alun-Alun Surabaya|0|Pusat Kota|Kota|⛲|4
House of Sampoerna|0|Pusat Kota|Museum|🏛️|4
''',
        'kuliner': '''
Rawon Setan|50000|Pusat Kota|Rawon|🍛|5
Sate Klopo Ondomohen|55000|Pusat Kota|Sate|🍖|5
Lontong Balap Garuda|35000|Kranggan|Lontong|🍲|5
Rujak Cingur Ahmad Jais|45000|Pusat Kota|Rujak|🥗|4
Sego Sambel Mak Yeye|35000|Wonokromo|Pedas|🌶️|5
Depot Bu Rudy|45000|Pusat Kota|Masakan Jawa|🍚|4
Tahu Tek Pak Jayen|30000|Pusat Kota|Jajanan|🥟|4
Wisata Kuliner G-Walk|65000|Citraland|Food Court|🍽️|4
'''
    },
    'Jakarta': {
        'tagline': 'Ikon metropolitan, museum, dan aneka rasa Nusantara.', 'province': 'DKI Jakarta',
        'hotel': 450000, 'transport': 75000, 'emoji': '🏙️',
        'wisata': '''
Monas|20000|Jakarta Pusat|Ikon|🏛️|5
Kota Tua Jakarta|0|Jakarta Barat|Sejarah|🏰|5
Museum Fatahillah|10000|Kota Tua|Museum|🏛️|5
Museum Nasional|25000|Jakarta Pusat|Museum|🗿|5
Taman Mini Indonesia Indah|35000|Jakarta Timur|Budaya|🏡|5
Hutan Kota GBK|0|Senayan|Taman|🌳|5
Taman Literasi Blok M|0|Jakarta Selatan|Taman|📚|4
Museum MACAN|100000|Jakarta Barat|Seni|🎨|4
Ancol (akses kawasan)|35000|Jakarta Utara|Pantai|🌊|5
Setu Babakan|0|Jagakarsa|Budaya|🛶|4
Pantai Indah Kapuk waterfront|0|Jakarta Utara|Kota|🌅|4
''',
        'kuliner': '''
Gado-Gado Bonbin|50000|Cikini|Gado-gado|🥗|5
Soto Betawi H. Ma'ruf|55000|Menteng|Soto|🥣|5
Nasi Uduk Kebon Kacang|35000|Tanah Abang|Nasi Uduk|🍚|5
Kuliner Sabang|55000|Jakarta Pusat|Kaki Lima|🍢|5
Bakmi Gang Kelinci|50000|Pasar Baru|Mi|🍜|4
Kuliner Blok M|60000|Blok M|Food Court|🍽️|4
Kerak Telor Kota Tua|30000|Kota Tua|Jajanan|🥚|4
Pecenongan Food Street|65000|Jakarta Pusat|Food Court|🍲|4
'''
    },
    'Denpasar': {
        'tagline': 'Gerbang petualangan Bali dan cita rasa lokal.', 'province': 'Bali',
        'hotel': 430000, 'transport': 80000, 'emoji': '🌴',
        'wisata': '''
Pantai Sanur|0|Sanur|Pantai|🌅|5
Pantai Mertasari|0|Sanur|Pantai|🏖️|5
Monumen Bajra Sandhi|25000|Renon|Sejarah|🏛️|5
Museum Bali|20000|Pusat Kota|Museum|🎨|4
Pasar Badung|0|Pusat Kota|Pasar|🧺|4
Pasar Kumbasari|0|Pusat Kota|Belanja|🛍️|4
Taman Werdhi Budaya|15000|Art Centre|Budaya|🎭|5
Pantai Sindhu|0|Sanur|Pantai|🌊|4
Big Garden Corner|30000|Sanur|Taman|🌸|4
Pulau Serangan|0|Serangan|Pantai|🐢|4
Pura Jagatnatha (area umum)|0|Pusat Kota|Budaya|🛕|4
''',
        'kuliner': '''
Warung Mak Beng|55000|Sanur|Ikan|🐟|5
Warung Nasi Bali Men Weti|40000|Sanur|Nasi Bali|🍛|5
Ayam Betutu Gilimanuk (Denpasar)|55000|Pusat Kota|Betutu|🍗|5
Sate Plecing Arjuna|40000|Pusat Kota|Sate|🍢|4
Pasar Sindhu Night Market|50000|Sanur|Street Food|🥟|5
Warung Wardani|55000|Pusat Kota|Nasi Bali|🍚|5
Warung Babi Guling (opsi non-halal)|60000|Denpasar|Non-halal|🍖|3
Es Daluman Bali|25000|Sanur|Minuman|🥤|4
'''
    },
    'Bogor': {
        'tagline': 'Kebun hijau, suasana hujan, dan kuliner Sunda.', 'province': 'Jawa Barat',
        'hotel': 340000, 'transport': 55000, 'emoji': '🌳',
        'wisata': '''
Kebun Raya Bogor|30000|Pusat Kota|Alam|🌳|5
Alun-Alun Kota Bogor|0|Pusat Kota|Kota|🌿|5
Museum Zoologi Bogor|15000|Pusat Kota|Museum|🦋|4
Taman Sempur|0|Pusat Kota|Taman|🏃|4
Istana Bogor (area luar)|0|Pusat Kota|Arsitektur|🏛️|4
Kuntum Farmfield|65000|Tajur|Keluarga|🐐|5
The Jungle Waterpark|100000|Bogor Selatan|Keluarga|💦|4
Devoyage Bogor|50000|Bogor Selatan|Foto|🏰|4
Curug Nangka|25000|Tamansari|Air Terjun|💦|5
Situ Gede|0|Bogor Barat|Danau|🛶|4
Taman Kencana|0|Pusat Kota|Taman|🌸|4
''',
        'kuliner': '''
Soto Mie Bogor|35000|Pusat Kota|Soto|🥣|5
Asinan Bogor Gedung Dalam|30000|Pusat Kota|Asinan|🥗|5
Laksa Bogor|35000|Pusat Kota|Laksa|🍜|5
Toge Goreng Bogor|30000|Pusat Kota|Jajanan|🍲|5
Roti Unyil Venus|30000|Sukajadi|Roti|🥐|4
Kedai Kita Bogor|60000|Pusat Kota|Restoran|🍽️|4
Sop Buntut Ma Emun|65000|Pusat Kota|Sop|🍖|4
Kuliner Suryakencana|50000|Suryakencana|Street Food|🍢|5
'''
    }
}

ALIASES = {'jogja': 'Yogyakarta', 'jogjakarta': 'Yogyakarta', 'yogya': 'Yogyakarta',
           'kota batu': 'Batu', 'surakarta': 'Solo', 'bali': 'Denpasar', 'dki jakarta': 'Jakarta'}


def normalize_city(value: str) -> str:
    text = str(value or '').strip()
    if not text:
        raise ValueError('Nama kota wajib diisi.')
    if len(text) > 70 or not re.fullmatch(r"[\w\s.,'()-]+", text, re.UNICODE):
        raise ValueError('Nama kota mengandung karakter tidak valid.')
    return ALIASES.get(text.casefold(), next((name for name in DATA if name.casefold() == text.casefold()), text.title()))


def build_catalog(city: str) -> dict:
    name = normalize_city(city)
    raw = DATA.get(name)
    if raw is None:
        return {'city': name, 'supported': False, 'province': 'Indonesia', 'tagline': 'Bangun rencanamu secara manual.',
                'emoji': '🧭', 'hotel': 350000, 'transport': 60000, 'places': []}
    items = []
    for kind in ('wisata', 'kuliner'):
        for index, line in enumerate(raw[kind].strip().splitlines()):
            name_part, price, area, theme, icon, rank = line.split('|')
            items.append({'id': f'{name.lower()}-{kind}-{index}', 'name': name_part,
                          'price': int(price), 'area': area, 'theme': theme,
                          'icon': icon, 'rank': int(rank), 'kind': kind, 'custom': False,
                          'description': f'{theme} · {area}'})
    return {'city': name, 'supported': True, 'province': raw['province'], 'tagline': raw['tagline'],
            'emoji': raw['emoji'], 'hotel': raw['hotel'], 'transport': raw['transport'], 'places': items}


def city_list() -> list:
    return [{'name': city, 'province': raw['province'], 'emoji': raw['emoji'], 'tagline': raw['tagline']}
            for city, raw in DATA.items()]
