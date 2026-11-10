"""JalanYuk v2: kalkulasi dan jadwal deterministik tanpa AI atau biaya layanan.
Semua harga tempat yang disarankan adalah angka PERKIRAAN, bukan live.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import date, datetime, timedelta
import time
from math import ceil, isfinite
import re
from providers import haversine

PACES = {'santai': ('wisata','kuliner','kuliner'),
         'normal': ('wisata','kuliner','wisata','kuliner'),
         'padat': ('wisata','kuliner','wisata','wisata','kuliner')}
DURATION = {'wisata': 85, 'kuliner': 55}
COST_CAP = 5_000_000_000


def integer(value, name, lo=0, hi=COST_CAP):
    if isinstance(value, bool):
        raise ValueError(f'{name} tidak valid.')
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f'{name} harus angka bulat.') from None
    if isinstance(value, float) and value != number:
        raise ValueError(f'{name} harus angka bulat.')
    if number < lo or number > hi:
        raise ValueError(f'{name} harus antara {lo}–{hi}.')
    return number


def number_or_none(value, name, lo, hi):
    if value is None or value == '':
        return None
    try:
        val = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{name} tidak valid.') from None
    if not isfinite(val) or not lo <= val <= hi:
        raise ValueError(f'{name} di luar rentang.')
    return round(val, 6)


def parse_date(value, name):
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        raise ValueError(f'{name} harus tanggal YYYY-MM-DD yang valid.') from None


def parse_time(value, name):
    try:
        return datetime.strptime(str(value), '%H:%M').strftime('%H:%M')
    except (ValueError, TypeError):
        raise ValueError(f'{name} harus HH:MM (00:00–23:59).') from None


def parse_bool(value, name):
    if not isinstance(value, bool):
        raise ValueError(f'{name} harus true atau false.')
    return value


def clean_config(raw):
    if not isinstance(raw, dict):
        raise ValueError('Konfigurasi harus objek JSON.')
    city = str(raw.get('city') or '').strip()[:120]
    if len(city) < 2:
        raise ValueError('Pilih kota tujuan terlebih dahulu.')
    origin = str(raw.get('origin') or '').strip()[:120]
    adults = integer(raw.get('adults', 2), 'Dewasa', 0, 30)
    children = integer(raw.get('children_2_plus', raw.get('children', 0)), 'Anak usia ≥2 tahun', 0, 20)
    age2 = integer(raw.get('children_age_2', 0), 'Anak berusia tepat 2 tahun', 0, 20)
    infants = integer(raw.get('infants_under_2', 0), 'Bayi di bawah 2 tahun', 0, 20)
    seniors = integer(raw.get('seniors', 0), 'Lansia', 0, 20)
    if age2 > children:
        raise ValueError('Jumlah anak tepat 2 tahun tidak boleh melebihi jumlah anak usia ≥2 tahun.')
    if adults + children + infants + seniors < 1:
        raise ValueError('Minimal 1 wisatawan.')
    if infants and not (adults + seniors):
        raise ValueError('Bayi di bawah 2 tahun wajib memiliki pendamping dewasa/lansia.')

    # start_date adalah hari PERTAMA BERWISATA, bukan tanggal kereta/pesawat berangkat.
    start = parse_date(raw.get('start_date') or date.today().isoformat(), 'Tanggal mulai kegiatan')
    legacy_days = integer(raw.get('days', 3), 'Durasi kegiatan', 1, 14)
    depart = parse_date(raw.get('depart_date') or start.isoformat(), 'Tanggal berangkat dari kota asal')
    arrive_dest = parse_date(raw.get('destination_arrival_date') or start.isoformat(), 'Tanggal tiba di kota tujuan')
    returning = parse_date(raw.get('return_date') or (start + timedelta(days=legacy_days - 1)).isoformat(), 'Tanggal berangkat pulang')
    arrive_home = parse_date(raw.get('home_arrival_date') or returning.isoformat(), 'Tanggal tiba kembali di kota asal')
    depart_time = parse_time(raw.get('depart_time') or '06:00', 'Jam berangkat dari kota asal')
    arrive_dest_time = parse_time(raw.get('destination_arrival_time') or '08:00', 'Jam tiba kota tujuan')
    start_time = parse_time(raw.get('arrival_time') or '09:00', 'Jam mulai kegiatan')
    return_time = parse_time(raw.get('return_time') or '20:00', 'Jam berangkat pulang')
    home_time = parse_time(raw.get('home_arrival_time') or '23:00', 'Jam tiba kota asal')
    outbound_dt = datetime.combine(depart, datetime.strptime(depart_time,'%H:%M').time())
    arrive_dest_dt = datetime.combine(arrive_dest, datetime.strptime(arrive_dest_time,'%H:%M').time())
    activity_dt = datetime.combine(start, datetime.strptime(start_time,'%H:%M').time())
    return_dt = datetime.combine(returning, datetime.strptime(return_time,'%H:%M').time())
    arrive_home_dt = datetime.combine(arrive_home, datetime.strptime(home_time,'%H:%M').time())
    if not (outbound_dt <= arrive_dest_dt <= activity_dt <= return_dt <= arrive_home_dt):
        raise ValueError('Urutan waktu harus: berangkat → tiba tujuan → mulai kegiatan → berangkat pulang → tiba kota asal.')
    if (arrive_home - depart).days > 45:
        raise ValueError('Rentang seluruh perjalanan maksimal 45 hari.')
    days = (returning - start).days + 1
    if days < 1 or days > 14:
        raise ValueError('Rentang hari kegiatan dari tanggal mulai hingga berangkat pulang harus 1–14 hari.')
    return_buffer = integer(raw.get('return_buffer_minutes', 90), 'Waktu persiapan pulang', 0, 360)

    pace = raw.get('pace', 'normal')
    if pace not in PACES:
        raise ValueError('Tempo perjalanan harus santai, normal, atau padat.')
    interests = raw.get('interests', [])
    if not isinstance(interests, list):
        interests = []
    interests = [str(i)[:35] for i in interests[:12] if isinstance(i,str)]
    transport_modes = {'kereta','pesawat','bus','mobil','lainnya'}
    out_mode = str(raw.get('outbound_mode') or raw.get('transport_mode') or 'lainnya')
    back_mode = str(raw.get('return_mode') or raw.get('transport_mode') or out_mode)
    if out_mode not in transport_modes or back_mode not in transport_modes:
        raise ValueError('Moda transportasi tidak dikenal.')
    # Kompatibilitas v2: tarif PP sebelumnya dibagi menjadi dua tarif sekali jalan.
    legacy_pp = integer(raw.get('intercity_per_person', 200000), 'Tarif PP lama', 0, 20_000_000)
    out_fare = integer(raw.get('outbound_fare', legacy_pp//2), 'Tarif pergi per dewasa atau kendaraan', 0, 20_000_000)
    back_fare = integer(raw.get('return_fare', legacy_pp-legacy_pp//2), 'Tarif pulang per dewasa atau kendaraan', 0, 20_000_000)

    local_mode = str(raw.get('local_travel_mode') or 'mobil')
    if local_mode not in ('mobil', 'motor', 'jalan', 'sepeda', 'transit'):
        raise ValueError('Moda transportasi antarwisata tidak dikenal.')
    requested_provider=str(raw.get('routing_provider') or 'multi')
    # Old saved plans may still request Google; migrate without using its API.
    if requested_provider=='google':requested_provider='multi'
    if requested_provider not in ('auto','osrm','multi'):
        raise ValueError('Penyedia rute tidak dikenal.')
    local_cost_mode = str(raw.get('local_cost_mode') or 'harian')
    if local_cost_mode not in ('harian', 'per_km'):
        raise ValueError('Metode biaya transportasi lokal tidak dikenal.')
    start_lat = number_or_none(raw.get('base_lat'), 'Latitude titik awal', -90, 90)
    start_lon = number_or_none(raw.get('base_lon'), 'Longitude titik awal', -180, 180)
    hub_lat = number_or_none(raw.get('return_hub_lat'), 'Latitude terminal kepulangan', -90, 90)
    hub_lon = number_or_none(raw.get('return_hub_lon'), 'Longitude terminal kepulangan', -180, 180)
    if (start_lat is None) != (start_lon is None) or (hub_lat is None) != (hub_lon is None):
        raise ValueError('Isi pasangan latitude dan longitude secara lengkap.')
    route_cache = raw.get('route_cache') or {}
    if not isinstance(route_cache,dict) or len(route_cache)>500:
        raise ValueError('Data rute jalan tidak valid.')
    routes={}
    for k,v in route_cache.items():
        if not isinstance(k,str) or len(k)>100 or not isinstance(v,dict):
            raise ValueError('Entri rute tidak valid.')
        if not (k.startswith('driving:') or k.startswith('timed:')) or 'google' in k.casefold():continue
        duration=integer(v.get('minutes',0),'Durasi rute',0,1500)
        km=number_or_none(v.get('km'),'Jarak rute',0,2500)
        if km is None:continue
        source=str(v.get('source') or 'osrm_driving')
        if source not in ('osrm_driving','osrm_distance_estimated_speed','multi_source_max'):
            continue
        fetched_at=integer(v.get('fetched_at',0),'Waktu pembaruan rute',0,5000000000)
        # Drop all Google-derived legacy cache records, including mixed estimates.
        if v.get('has_google') or str(v.get('selected_source','')).startswith('google_') or any(isinstance(x,dict) and str(x.get('source','')).startswith('google_')
                                      for x in (v.get('samples') if isinstance(v.get('samples'),list) else [])):
            continue
        routes[k]={'minutes':duration,'km':km,'source':source,'fetched_at':fetched_at}
        if source=='multi_source_max':
            samples=v.get('samples') if isinstance(v.get('samples'),list) else []
            clean_samples=[]
            for sample in samples[:4]:
                if not isinstance(sample,dict):continue
                if sample.get('source') not in ('osrm_driving','openrouteservice'):continue
                clean_samples.append({'source':sample['source'],
                    'minutes':integer(sample.get('minutes',0),'Durasi sumber',0,1500),
                    'km':number_or_none(sample.get('km'),'Jarak sumber',0,2500)})
            routes[k].update({'samples':clean_samples,
                'selected_source':str(v.get('selected_source') or '')[:40],
                'confidence':str(v.get('confidence') or '')[:40]})

    leg_overrides=raw.get('leg_overrides') or {}
    if not isinstance(leg_overrides,dict) or len(leg_overrides)>150:
        raise ValueError('Koreksi perjalanan tidak valid.')
    overrides={}
    for k,v in leg_overrides.items():
        if not isinstance(k,str) or len(k)>150 or not isinstance(v,dict):
            raise ValueError('Data koreksi perjalanan tidak valid.')
        overrides[k]={'minutes':integer(v.get('minutes'), 'Koreksi waktu perjalanan',0,1440),
                      'km':number_or_none(v.get('km'),'Koreksi jarak',0,2500)}
    nightly_return = parse_time(raw.get('daily_hotel_return_time') or '21:00','Jam kembali ke hotel')
    night_start = parse_time(raw.get('night_start_time') or '18:00','Jam mulai wisata malam')
    raw_daily=raw.get('hotel_return_times') or {}
    if not isinstance(raw_daily,dict) or len(raw_daily)>14:
        raise ValueError('Jadwal kembali ke hotel per hari tidak valid.')
    day_return_times={}
    for k,v in raw_daily.items():
        key=str(k)
        try: parse_date(key,'Tanggal pulang hotel')
        except ValueError: raise ValueError('Tanggal jadwal kembali hotel harus YYYY-MM-DD.') from None
        if not (start <= date.fromisoformat(key) <= returning):
            raise ValueError('Tanggal pulang hotel harus dalam rentang kegiatan wisata.')
        day_return_times[key]=parse_time(v,'Jam kembali ke hotel per hari')
    cfg = {
        'city':city, 'city_lat':number_or_none(raw.get('city_lat'),'Latitude kota',-90,90),
        'city_lon':number_or_none(raw.get('city_lon'),'Longitude kota',-180,180),
        'origin':origin, 'start_date':start.isoformat(), 'days':days, 'arrival_time':start_time,
        'depart_date':depart.isoformat(), 'depart_time':depart_time,
        'destination_arrival_date':arrive_dest.isoformat(),'destination_arrival_time':arrive_dest_time,
        'return_date':returning.isoformat(),'return_time':return_time,
        'home_arrival_date':arrive_home.isoformat(),'home_arrival_time':home_time,
        'return_buffer_minutes':return_buffer,
        'local_travel_mode':local_mode,'local_cost_mode':local_cost_mode,
        'routing_provider':requested_provider,
        'local_utc_offset':integer(raw.get('local_utc_offset',7),'Zona waktu WIB/WITA/WIT',7,9),
        'traffic_percent':integer(raw.get('traffic_percent',125),'Faktor kemacetan (%)',100,300),
        'visit_gap_minutes':integer(raw.get('visit_gap_minutes',15),'Jeda antar kegiatan',0,90),
        'route_safety_minutes':integer(raw.get('route_safety_minutes',10),'Cadangan perjalanan per segmen',0,90),
        'unknown_leg_minutes':integer(raw.get('unknown_leg_minutes',45),'Alokasi perpindahan tanpa koordinat',5,180),
        'base_name':str(raw.get('base_name') or 'Hotel / titik mulai').strip()[:100],
        'hotel_area':str(raw.get('hotel_area') or '').strip()[:140],
        'base_lat':start_lat,'base_lon':start_lon,
        'use_city_center_as_base':raw.get('use_city_center_as_base') is True,
        'include_evening':raw.get('include_evening',False) is True,
        'daily_hotel_return_time':nightly_return,'hotel_return_times':day_return_times,
        'night_start_time':night_start,
        'last_day_via_hotel':raw.get('last_day_via_hotel',False) is True,
        'return_to_base':raw.get('return_to_base',False) is True,
        'return_hub_name':str(raw.get('return_hub_name') or 'Stasiun / bandara / terminal').strip()[:100],
        'return_hub_lat':hub_lat,'return_hub_lon':hub_lon,
        'local_cost_per_km':integer(raw.get('local_cost_per_km',2500),'Tarif transport per km',0,1_000_000),
        'local_base_per_leg':integer(raw.get('local_base_per_leg',6000),'Tarif dasar per perpindahan',0,1_000_000),
        'local_vehicle_capacity':integer(raw.get('local_vehicle_capacity',5),'Kapasitas kendaraan lokal',1,12),
        'route_cache':routes,'leg_overrides':overrides,
        'daily_start_time':parse_time(raw.get('daily_start_time') or '09:00', 'Jam mulai kegiatan hari berikutnya'),
        'budget':integer(raw.get('budget',3_000_000),'Budget',0),
        'adults':adults,'children':children,'children_2_plus':children,'children_age_2':age2,
        'infants_under_2':infants,'seniors':seniors,'pace':pace,'interests':interests,
        'include_hotel':raw.get('include_hotel',True) is True,
        'hotel_rate':integer(raw.get('hotel_rate',350000),'Tarif kamar',0,20_000_000),
        'room_capacity':integer(raw.get('room_capacity',2),'Kapasitas kamar',1,10),
        'infant_uses_bed':raw.get('infant_uses_bed',False) is True,
        'outbound_mode':out_mode,'return_mode':back_mode,'outbound_fare':out_fare,'return_fare':back_fare,
        'intercity_per_person':out_fare+back_fare,
        'car_capacity':integer(raw.get('car_capacity',5),'Kapasitas kendaraan antarkota',1,12),
        'train_infant_without_seat':raw.get('train_infant_without_seat',True) is True,
        'train_age2_without_seat':raw.get('train_age2_without_seat',True) is True,
        'flight_infant_percent':integer(raw.get('flight_infant_percent',10),'Persen bayi pesawat',0,100),
        'other_infant_percent':integer(raw.get('other_infant_percent',0),'Persen bayi moda lainnya',0,100),
        'child_activity_percent':integer(raw.get('child_activity_percent',70),'Persen tiket wisata anak',0,100),
        'infant_activity_percent':integer(raw.get('infant_activity_percent',0),'Persen tiket wisata bayi',0,100),
        'age2_activity_percent':integer(raw.get('age2_activity_percent',raw.get('child_activity_percent',70)),'Persen tiket wisata anak tepat 2 tahun',0,100),
        'child_food_percent':integer(raw.get('child_food_percent',70),'Persen makan anak',0,100),
        'infant_food_percent':integer(raw.get('infant_food_percent',0),'Persen makan bayi',0,100),
        'age2_food_percent':integer(raw.get('age2_food_percent',raw.get('child_food_percent',70)),'Persen makan anak tepat 2 tahun',0,100),
        'local_child_percent':integer(raw.get('local_child_percent',100),'Persen transport lokal anak',0,100),
        'local_infant_percent':integer(raw.get('local_infant_percent',0),'Persen transport lokal bayi',0,100),
        'local_age2_percent':integer(raw.get('local_age2_percent',raw.get('local_child_percent',100)),'Persen transport lokal anak tepat 2 tahun',0,100),
        'local_per_person_day':integer(raw.get('local_per_person_day',50000),'Transport lokal harian',0,5_000_000),
        'parking_per_day':integer(raw.get('parking_per_day',15000),'Parkir harian',0,5_000_000),
        'miscellaneous':integer(raw.get('miscellaneous',100000),'Biaya lain',0,20_000_000),
        'emergency_fund':integer(raw.get('emergency_fund',150000),'Dana cadangan',0,20_000_000)}
    return cfg

def clean_place(item, expected_kind=None):
    if not isinstance(item, dict):
        raise ValueError('Tempat harus berupa objek.')
    kind = item.get('kind')
    if kind not in ('wisata','kuliner') or (expected_kind and kind != expected_kind):
        raise ValueError('Kategori tempat harus wisata/kuliner yang sesuai.')
    name = str(item.get('name') or '').strip()
    if not 1 <= len(name) <= 120:
        raise ValueError('Nama tempat 1–120 karakter.')
    lat, lon = number_or_none(item.get('lat'),'Latitude tempat',-90,90), number_or_none(item.get('lon'),'Longitude tempat',-180,180)
    if (lat is None) != (lon is None):
        lat = lon = None
    sanitized = {key: str(item.get(key) or '')[:max_len]
                 for key,max_len in [('id',100),('theme',55),('area',120),('description',180),('source',80),
                                     ('opening_hours',140),('wheelchair',20),('osm_url',250),('price_status',30)]}
    sanitized.update({'name':name,'kind':kind,'price':integer(item.get('price',0),'Tarif tempat',0,10_000_000),
                      'duration':integer(item.get('duration',DURATION[kind]),'Lama kunjungan',20,480),
                      'lat':lat,'lon':lon, 'outdoor':item.get('outdoor') is True})
    return sanitized


def party(cfg):
    return cfg['adults'] + cfg['children'] + cfg['seniors'] + cfg['infants_under_2']


def room_count(cfg):
    # Bayi yang sekamar/seranjang dengan orang tua tidak otomatis menambah kamar.
    counted = cfg['adults'] + cfg['children'] + cfg['seniors']
    if cfg['infant_uses_bed']:
        counted += cfg['infants_under_2']
    return ceil(counted / cfg['room_capacity']) if cfg['include_hotel'] else 0


def item_cost(p, cfg):
    price = p['price']
    if p['kind'] == 'kuliner':
        child_pct = cfg['child_food_percent']
        infant_pct = cfg['infant_food_percent']
        age2_pct = cfg['age2_food_percent']
    else:
        child_pct = cfg['child_activity_percent']
        infant_pct = cfg['infant_activity_percent']
        age2_pct = cfg['age2_activity_percent']
    return (price * (cfg['adults'] + cfg['seniors']) +
            round(price * child_pct / 100) * (cfg['children']-cfg['children_age_2']) +
            round(price * age2_pct / 100) * cfg['children_age_2'] +
            round(price * infant_pct / 100) * cfg['infants_under_2'])


def transport_ledger(cfg, direction):
    """Tarif total satu arah dengan kategori bayi sesuai moda; semua tarif simulasi."""
    if direction not in ('pergi', 'pulang'):
        raise ValueError('Arah perjalanan tidak valid.')
    mode = cfg['outbound_mode'] if direction == 'pergi' else cfg['return_mode']
    fare = cfg['outbound_fare'] if direction == 'pergi' else cfg['return_fare']
    if mode == 'kereta':
        # KAI: usia <3 (termasuk anak usia 2) gratis jika tidak mengambil kursi,
        # kuota 1 anak pangku per orang dewasa. Kelebihan membayar tarif penuh.
        free_slots = cfg['adults'] + cfg['seniors']
        free_babies = min(cfg['infants_under_2'], free_slots) if cfg['train_infant_without_seat'] else 0
        free_slots -= free_babies
        free_age2 = min(cfg['children_age_2'], free_slots) if cfg['train_age2_without_seat'] else 0
        paid_infants = cfg['infants_under_2'] - free_babies
        paying_children = cfg['children'] - free_age2
        amount = fare * (cfg['adults'] + cfg['seniors'] + paying_children + paid_infants)
        detail = {'gratis_bayi':free_babies, 'gratis_anak_usia_2':free_age2,
                  'bayi_tarif_penuh':paid_infants, 'persen_bayi':0}
    elif mode == 'mobil':
        # Mobil dikalkulasi PER KENDARAAN, bayi tetap butuh posisi aman/kursi.
        vehicles = ceil(party(cfg) / cfg['car_capacity'])
        amount = vehicles * fare
        detail = {'gratis_bayi':0,'gratis_anak_usia_2':0,
                  'bayi_tarif_penuh':0,'persen_bayi':0,'jumlah_kendaraan':vehicles}
    elif mode == 'pesawat':
        # Tidak menganggap gratis: tarif infant pada tiket tunai sesuai operator.
        # Tarif 10% di sini hanya ESTIMASI yang dapat diubah oleh pengguna.
        free_slots = cfg['adults'] + cfg['seniors']
        infant_lap = min(cfg['infants_under_2'], free_slots)
        infant_seated = cfg['infants_under_2'] - infant_lap
        amount = (fare * (cfg['adults'] + cfg['children'] + cfg['seniors'] + infant_seated)
                  + round(fare * cfg['flight_infant_percent'] / 100) * infant_lap)
        detail = {'gratis_bayi':0,'gratis_anak_usia_2':0,'bayi_tarif_penuh':infant_seated,
                  'bayi_dipangku':infant_lap,'persen_bayi':cfg['flight_infant_percent']}
    else:
        # Bus/mobil/lainnya tidak memiliki kebijakan nasional yang seragam.
        # Tarif bayi diasumsikan dari persentase yang bisa diubah pengguna.
        amount = (fare * (cfg['adults'] + cfg['children'] + cfg['seniors']) +
                  round(fare * cfg['other_infant_percent'] / 100) * cfg['infants_under_2'])
        detail = {'gratis_bayi':cfg['infants_under_2'] if cfg['other_infant_percent']==0 else 0,
                  'gratis_anak_usia_2':0,'bayi_tarif_penuh':0,
                  'persen_bayi':cfg['other_infant_percent']}
    return {'mode':mode,'tarif_dasar':fare,'total':amount,**detail}


def fixed_costs(cfg):
    rooms = room_count(cfg)
    nights = (date.fromisoformat(cfg['return_date']) - date.fromisoformat(cfg['destination_arrival_date'])).days
    nights = max(0,nights) if cfg['include_hotel'] else 0
    pergi = transport_ledger(cfg,'pergi')
    pulang = transport_ledger(cfg,'pulang')
    local_persons_cost = (cfg['local_per_person_day'] * (cfg['adults'] + cfg['seniors'])
        + round(cfg['local_per_person_day'] * cfg['local_child_percent'] / 100) * (cfg['children'] - cfg['children_age_2'])
        + round(cfg['local_per_person_day'] * cfg['local_age2_percent'] / 100) * cfg['children_age_2']
        + round(cfg['local_per_person_day'] * cfg['local_infant_percent'] / 100) * cfg['infants_under_2'])
    return {'hotel':rooms*nights*cfg['hotel_rate'],
            'transport_antar_kota':pergi['total']+pulang['total'],
            'transport_lokal':local_persons_cost*cfg['days'] if cfg['local_cost_mode']=='harian' else 0,
            'parkir':cfg['days']*cfg['parking_per_day'],
            'lain_lain':cfg['miscellaneous'],
            'dana_cadangan':cfg['emergency_fund']}

def distance(a, b):
    if not a or not b or a.get('lat') is None or b.get('lat') is None:
        return None
    return haversine(a['lat'], a['lon'], b['lat'], b['lon'])


def trip_cost_km(km):
    # Haversine adalah jarak lurus; faktor 1.35 perkiraan kasar jaringan jalan.
    return round(km * 1.35, 1)


def trip_minutes(km):
    return max(10, round((trip_cost_km(km) / 24)*60 + 8))


def routing_key(a, b):
    """Stable coordinate key to make cached OSRM segments location-specific."""
    if distance(a,b) is None:
        return None
    return f'driving:{a["lat"]:.5f},{a["lon"]:.5f}>{b["lat"]:.5f},{b["lon"]:.5f}'



def timed_routing_key(a,b,mode,trip_date,depart_minutes,provider='auto'):
    base=routing_key(a,b)
    if not base or not trip_date or depart_minutes is None:return None
    try:date.fromisoformat(str(trip_date))
    except ValueError:return None
    hour=max(0,min(23,int(depart_minutes)//60))
    return f'timed:{provider}:{trip_date}:{hour:02d}:{mode}:{base}'

def leg_id(a,b):
    def sig(p):
        return (str(p.get('id') or p.get('name') or 'titik').strip()[:60].replace('|','_')
                if isinstance(p,dict) else '?')
    return sig(a)+'|'+sig(b)


def start_point(cfg):
    if cfg['base_lat'] is not None:
        return {'id':'__base__','name':cfg['base_name'],'lat':cfg['base_lat'],'lon':cfg['base_lon'],'approx':False}
    if cfg['use_city_center_as_base'] and cfg['city_lat'] is not None:
        return {'id':'__city_center__','name':'Pusat '+cfg['city']+' (titik acuan perkiraan)',
                'lat':cfg['city_lat'],'lon':cfg['city_lon'],'approx':True}
    return None


def return_point(cfg):
    if cfg['return_hub_lat'] is not None:
        return {'id':'__return_hub__','name':cfg['return_hub_name'],
                'lat':cfg['return_hub_lat'],'lon':cfg['return_hub_lon'],'approx':False}
    return None


def leg_estimate(a,b,cfg,trip_date=None,depart_minutes=None):
    if not a or not b:
        return None
    key=leg_id(a,b)
    override=cfg['leg_overrides'].get(key)
    geom=distance(a,b)
    mode=cfg['local_travel_mode']
    pair=routing_key(a,b)
    time_key=timed_routing_key(a,b,mode,trip_date,depart_minutes,cfg['routing_provider'])
    live=cfg['route_cache'].get(time_key) if time_key else None
    if not live and time_key and depart_minutes is not None:
        # Jam jadwal dapat bergeser setelah ETA diperbarui; data dalam ±1 jam masih valid.
        for offset in (-1,1):
            adjacent=timed_routing_key(a,b,mode,trip_date,max(0,min(1439,depart_minutes+offset*60)),cfg['routing_provider'])
            if adjacent in cfg['route_cache']:
                live=cfg['route_cache'][adjacent]
                break
    if not live and pair and mode in ('mobil','motor','transit'):
        live=cfg['route_cache'].get(pair)

    if override:
        km=override['km'] if override['km'] is not None else (round(trip_cost_km(geom),2) if geom is not None else None)
        minutes=override['minutes']
        source='manual'
    elif live:
        km=live['km']
        samples=live.get('samples',[])
        selected_source=live.get('selected_source')
        confidence=live.get('confidence')
        # Multi-source estimate already includes a conservative margin.
        if live.get('source')=='multi_source_max':
            minutes=live['minutes']
            source=live['source']
        elif mode=='mobil':
            minutes=ceil(live['minutes'] * cfg['traffic_percent']/100 + (5 if km>0.2 else 0))
            source='osrm_driving'
        elif mode in ('jalan','sepeda') and str(live.get('source'))=='osrm_driving':
            speed=4.3 if mode=='jalan' else 13
            minutes=ceil(km/speed*60)
            source='osrm_distance_estimated_speed'
        else:
            speed=30 if mode=='motor' else 17
            minutes=ceil((km/speed*60)*cfg['traffic_percent']/100+(6 if mode=='motor' else 12))
            source='osrm_distance_estimated_speed'
    elif geom is not None:
        factor=1.24 if mode in ('jalan','sepeda') else 1.35
        km=round(geom*factor,2)
        speed={'mobil':27,'motor':30,'jalan':4.3,'sepeda':13,'transit':17}[mode]
        overhead={'mobil':5,'motor':5,'jalan':0,'sepeda':2,'transit':12}[mode]
        multiplier=cfg['traffic_percent']/100 if mode in ('mobil','motor','transit') else 1
        minutes=ceil((km/speed*60)*multiplier+overhead) if km>0.05 else 0
        source='approx_distance'
    else:
        return {'id':key,'from':a.get('name','Titik awal'),'to':b.get('name','Lokasi'),
                'minutes':None,'km':None,'source':'no_coordinates','mode':mode,
                'reserved_minutes':cfg['unknown_leg_minutes'],
                'start_coords':None,'end_coords':None, 'estimated_cost':0}
    # Safety margin is applied to provider estimates once; a manual override is authoritative.
    margin=cfg['route_safety_minutes'] if source=='multi_source_max' and km and km>.2 else 0
    minutes=min(1500,minutes+margin) if minutes is not None else None
    km=round(km,2) if km is not None else None
    return {'id':key,'from':a.get('name','Titik awal'),'to':b.get('name','Lokasi'),
            'minutes':minutes,'km':km,'source':source,'mode':mode,
            'start_coords':{'lat':a['lat'],'lon':a['lon']} if geom is not None else None,
            'end_coords':{'lat':b['lat'],'lon':b['lon']} if geom is not None else None,
            'estimated_cost':0, 'samples':locals().get('samples',[]),
            'selected_source':locals().get('selected_source'),
            'confidence':locals().get('confidence'),
            'safety_minutes':margin}


def local_leg_cost(leg,cfg):
    if cfg['local_cost_mode']!='per_km' or not leg or leg['km'] is None:
        return 0
    fare=ceil(leg['km']*cfg['local_cost_per_km'])+cfg['local_base_per_leg']
    mode=cfg['local_travel_mode']
    if mode in ('jalan','sepeda'):
        return 0  # Moda aktif tidak ditagih otomatis (sewa sepeda dapat diinput sebagai biaya lain).
    if mode=='mobil':
        return fare*ceil(party(cfg)/cfg['local_vehicle_capacity'])
    if mode=='motor':
        return fare*ceil(party(cfg)/2)
    # Public transit: cost per paying passenger using local age categories.
    return (fare*(cfg['adults']+cfg['seniors'])+
            round(fare*cfg['local_child_percent']/100)*(cfg['children']-cfg['children_age_2'])+
            round(fare*cfg['local_age2_percent']/100)*cfg['children_age_2']+
            round(fare*cfg['local_infant_percent']/100)*cfg['infants_under_2'])


def period_score(p, period, iso_date=None):
    if not period: return 0
    name=(p['name']+' '+p['theme']+' '+p['description']).casefold()
    out=p['outdoor']
    interesting={'pagi':('pagi','sunrise','pasar tradisional','taman','bukit','pantai','air terjun','trekking'),
                 'siang':('museum','galeri','mal','mall','indoor','restoran','rumah makan','kuliner','sejarah'),
                 'sore':('sunset','senja','pantai','alun-alun','taman','pemandangan','viewpoint'),
                 'malam':('malam','night','angkringan','food court','kuliner','alun-alun','bakmi','sate','restoran','kafe','cafe','malioboro')}
    score=sum(28 for term in interesting.get(period,()) if term in name)
    if period=='pagi' and out:score+=25
    if period=='siang' and not out:score+=20
    if period=='sore' and out:score+=15
    if period=='malam' and out and not any(t in name for t in ('malam','night','sunset','alun-alun','malioboro','pasar')):score-=45
    if iso_date:
        starts={'pagi':9*60,'siang':12*60,'sore':16*60,'malam':19*60}
        status=simple_opening_hours_status(p.get('opening_hours'),iso_date,starts.get(period,12*60),starts.get(period,12*60)+40)
        if status is False:score-=250
        elif status is True:score+=20
    return score


def preference_score(p, cfg, previous, used, rain=False, period=None, iso_date=None):
    score = 100 - p['price']/2000
    if p['id'] in used:
        score -= 80
    theme = p['theme'].casefold()
    for interest in cfg['interests']:
        k = interest.casefold()
        if k in theme or k in p['name'].casefold() or k in p['description'].casefold():
            score += 45
        if k == 'keluarga' and theme in ('keluarga', 'museum', 'edukasi', 'taman'):
            score += 30
        if k == 'alam' and p['outdoor']:
            score += 25
        if k == 'sejarah' and theme in ('budaya', 'sejarah', 'museum'):
            score += 25
    if cfg['children'] or cfg['seniors']:
        if theme in ('keluarga','museum','edukasi','kota','kuliner'):
            score += 15
        if p['wheelchair'] == 'yes' and cfg['seniors']:
            score += 15
    if rain and p['outdoor']:
        score -= 50
    if previous:
        km = distance(previous, p)
        if km is not None:
            score -= min(100, km*1.2)
        elif previous.get('area') and previous.get('area') == p.get('area'):
            score += 7
    return score + period_score(p,period,iso_date)


def choose_place(candidates, kind, cfg, used, previous, per_activity_budget, rainy=False, period=None, iso_date=None):
    pool = [p for p in candidates if p['kind'] == kind]
    if not pool:
        return None
    fresh = [p for p in pool if p['id'] not in used]
    if fresh:
        pool = fresh
    feasible = [p for p in pool if item_cost(p,cfg) <= max(per_activity_budget,0)]
    if feasible:
        pool = feasible
    else:
        cheapest = min(item_cost(p,cfg) for p in pool)
        pool = [p for p in pool if item_cost(p,cfg) == cheapest]
    return deepcopy(max(pool,key=lambda p:preference_score(p,cfg,previous,used,rainy,period,iso_date)))


def generate_plan(raw, raw_places, weather=None):
    cfg = clean_config(raw)
    if not isinstance(raw_places, list) or len(raw_places) > 500:
        raise ValueError('Daftar tempat harus 0–500 lokasi.')
    places = [clean_place(p) for p in raw_places]
    # Deduplication by ID. For named manual points IDs can differ by name.
    unique = list({p['id'] or f'{p["kind"]}-{p["name"]}':p for p in places}.values())
    fixed = sum(fixed_costs(cfg).values())
    budget_activities = cfg['budget'] - fixed
    planned = sum(len(PACES[cfg['pace']]) for _ in range(cfg['days']))
    used = set()
    days = []
    spent = 0
    weather_map = {day['date']:day for day in (weather or {}).get('days',[])}
    for di in range(cfg['days']):
        dt = (date.fromisoformat(cfg['start_date'])+timedelta(days=di)).isoformat()
        rainy = (weather_map.get(dt) or {}).get('rain_probability')
        rainy = rainy is not None and rainy >= 60
        slots=[]
        prev = start_point(cfg)
        # Keutamaan waktu: pagi untuk alam, siang untuk indoor/makan, sore untuk panorama, malam untuk kuliner.
        periods={'santai':['pagi','siang','malam'],
                 'normal':['pagi','siang','sore','malam'],
                 'padat':['pagi','siang','siang','sore','malam']}[cfg['pace']]
        if not cfg['include_evening']:
            periods=[('sore' if x=='malam' else x) for x in periods]
        for si,kind in enumerate(PACES[cfg['pace']]):
            period=periods[si]
            remaining = max(1,planned - (di*len(PACES[cfg['pace']])+si))
            slot_budget = max(0, (budget_activities-spent)//remaining)
            chosen=choose_place(unique,kind,cfg,used,prev,slot_budget,rainy,period,dt)
            if chosen:
                spent += item_cost(chosen,cfg)
                used.add(chosen['id'])
                prev=chosen
            slots.append({'id':f'd{di+1}-s{si+1}', 'kind':kind, 'period':period, 'item':chosen})
        days.append({'day':di+1,'date':dt,'slots':slots})
    return recalculate(cfg,days,weather=weather)


def reorder_day(slots, origin=None):
    """Nearest neighbour in each contiguous activity type group; keep food moments."""
    slots=deepcopy(slots)
    if len(slots)<2:
        return slots
    # Sort only consecutive same-kind slots; never swap lunch and morning attraction.
    start=0
    previous=origin
    while start<len(slots):
        end=start+1
        while end<len(slots) and slots[end]['kind']==slots[start]['kind'] and slots[end].get('period')==slots[start].get('period'):
            end+=1
        group=slots[start:end]
        if len(group)>1:
            ordered=[]
            while group:
                if previous and previous.get('lat') is not None:
                    best=min(range(len(group)),key=lambda i:distance(previous,group[i].get('item')) if distance(previous,group[i].get('item')) is not None else 1e9)
                else:
                    best=0
                chosen=group.pop(best)
                ordered.append(chosen)
                if chosen['item']:
                    previous=chosen['item']
            slots[start:end]=ordered
        for slot in slots[start:end]:
            if slot['item']:
                previous=slot['item']
        start=end
    return slots


def _minutes(time):
    h,m = time.split(':')
    return 60*int(h)+int(m)


def _clock(mins):
    return f'{(mins//60)%24:02d}:{mins%60:02d}'



def simple_opening_hours_status(opening_hours, iso_date, start_minute, end_minute):
    """Cek subset OSM opening_hours sederhana saja.
    Format kompleks/PH/SH/overnight => None (tidak diketahui), bukan dianggap buka.
    """
    value=(opening_hours or '').strip()
    if not value:return None
    if value=='24/7':return True
    # Mendukung "09:00-17:00", "Mo-Su 09:00-17:00", "Mo-Fr 08:00-16:00; Sa 09:00-12:00".
    tokens=['Mo','Tu','We','Th','Fr','Sa','Su']
    today=tokens[date.fromisoformat(iso_date).weekday()]
    matches=[]
    for part in value.split(';'):
        m=re.fullmatch(r'\s*(?:(Mo|Tu|We|Th|Fr|Sa|Su)(?:-(Mo|Tu|We|Th|Fr|Sa|Su))?\s+)?([0-2]\d:[0-5]\d)-([0-2]\d:[0-5]\d)\s*',part)
        if not m:return None
        first,last,start,end=m.groups()
        if first:
            a=tokens.index(first);b=tokens.index(last) if last else a
            permitted=(a<=b and a<=tokens.index(today)<=b) or (a>b and (tokens.index(today)>=a or tokens.index(today)<=b))
            if not permitted:continue
        opens=_minutes(start);closes=_minutes(end)
        if opens>=closes or closes>24*60:return None
        matches.append(opens<=start_minute and end_minute<=closes)
    return any(matches) if matches else False


def recalculate(raw, itinerary, weather=None, reorder=False):
    cfg=clean_config(raw)
    if not isinstance(itinerary,list) or len(itinerary)>14:
        raise ValueError('Itinerary tidak valid.')
    days=[]
    charges={'wisata':0,'kuliner':0}
    day_totals=[]
    weather_map={d['date']:d for d in (weather or {}).get('days',[]) if isinstance(d,dict) and 'date' in d}
    base=start_point(cfg)
    hub=return_point(cfg)
    anchor=base # Legacy mode: no first-hop travel if no base given.
    skipped_count=0
    local_variable_total=0
    missing_leg_count=0
    for di in range(cfg['days']):
        entry=itinerary[di] if di<len(itinerary) and isinstance(itinerary[di],dict) else {'slots':[]}
        raw_slots=entry.get('slots',[])
        if not isinstance(raw_slots,list) or len(raw_slots)>8:
            raise ValueError('Terlalu banyak kegiatan dalam satu hari (maks. 8).')
        slots=[]
        for si,slot in enumerate(raw_slots):
            if not isinstance(slot,dict):raise ValueError('Kegiatan tidak valid.')
            kind=slot.get('kind')
            if kind not in ('wisata','kuliner'):raise ValueError('Jenis kegiatan tidak valid.')
            item=clean_place(slot['item'],kind) if slot.get('item') is not None else None
            slots.append({'id':str(slot.get('id',f'd{di+1}-s{si+1}'))[:70], 'kind':kind, 'period':slot.get('period') if slot.get('period') in ('pagi','siang','sore','malam') else None, 'item':item})
        if reorder:
            slots=reorder_day(slots,anchor)
        dt=(date.fromisoformat(cfg['start_date'])+timedelta(days=di)).isoformat()
        forecast=weather_map.get(dt) or {}
        rain=forecast.get('rain_probability')
        moment=_minutes(cfg['arrival_time']) if di==0 else _minutes(cfg['daily_start_time'])
        first_start=moment
        last_day=dt==cfg['return_date']
        hotel_target=cfg['hotel_return_times'].get(dt,cfg['daily_hotel_return_time'])
        hotel_limit=_minutes(hotel_target)
        day_limit=23*60+59
        # Pulang ke hotel harian tidak dianggap perjalanan gratis: ETA harus masuk sebelum jam target.
        if cfg['return_to_base'] and not last_day: day_limit=min(day_limit,hotel_limit)
        if last_day:
            day_limit=min(day_limit,_minutes(cfg['return_time'])-cfg['return_buffer_minutes'])
            if cfg['last_day_via_hotel'] and cfg['return_to_base']:day_limit=min(day_limit,hotel_limit)
        cost=0
        travel_km=0.0
        travel_min_total=0
        daily_variable=0
        warnings=[]
        legs=[]
        prev=base
        completed=0
        if base is None:
            warnings.append('Titik awal/hotel belum memiliki koordinat. Perjalanan menuju wisata pertama belum dihitung; isi titik awal di pengaturan.')
        elif base.get('approx'):
            warnings.append('Titik awal memakai pusat kota sebagai acuan, BUKAN lokasi hotel yang sebenarnya. Sesuaikan koordinat hotel agar ETA lebih relevan.')
        if last_day:
            if hub is None:
                warnings.append('Lokasi stasiun/bandara/terminal pulang belum disetel. Waktu transfer terakhir TIDAK termasuk dalam buffer; isi titik keberangkatan agar dihitung.')
            warnings.append(f'Pulang {cfg["return_time"]}; batas tiba di titik keberangkatan { _clock(max(0,day_limit)) } (buffer {cfg["return_buffer_minutes"]} menit).')
        if day_limit<=moment: warnings.append('Waktu awal wisata sudah melewati batas hari ini. Tidak ada kegiatan yang bisa dijadwalkan.')
        if cfg['return_to_base'] and not last_day and base is None:
            warnings.append('Pulang ke hotel aktif, tetapi belum ada titik hotel. Jam kembali belum bisa diverifikasi dari rute.')
        if cfg['local_cost_mode']=='per_km' and cfg['local_travel_mode'] in ('jalan','sepeda'):
            warnings.append('Biaya jalan/sepeda mengikuti tarif per km yang disetel; jika tidak ada ongkos, ubah tarif menjadi Rp0.')
        for slot in slots:
            item=slot['item']
            slot.update({'start':None,'end':None,'travel_minutes':None,'travel_km':None,
                         'leg':None,'cost':0,'status':'kosong' if not item else 'scheduled',
                         'opening_warning':'','weather_warning':'','schedule_warning':''})
            if not item:continue
            incoming=leg_estimate(prev,item,cfg,dt,moment)
            travel_min=(incoming['minutes'] if incoming['minutes'] is not None else incoming.get('reserved_minutes',cfg['unknown_leg_minutes'])) if incoming else 0
            period=slot['period']
            period_start={'pagi':0,'siang':11*60,'sore':15*60,'malam':_minutes(cfg['night_start_time'])}.get(period,0)
            period_end={'pagi':12*60,'siang':16*60,'sore':19*60,'malam':23*60+59}.get(period,23*60+59)
            venue_start=max(moment+travel_min,period_start)
            venue_end=venue_start+item['duration']
            end_points=[]
            if last_day:
                if cfg['last_day_via_hotel'] and cfg['return_to_base'] and base: end_points.append(base)
                if hub:end_points.append(hub)
            elif cfg['return_to_base'] and base:
                end_points.append(base)
            # Reserve the time for the final transfer(s) before accepting an activity.
            trailing_time=0
            from_point=item
            for endpoint in end_points:
                trailing=leg_estimate(from_point,endpoint,cfg,dt,venue_end+trailing_time)
                trailing_time+=((trailing['minutes'] if trailing['minutes'] is not None else trailing.get('reserved_minutes',cfg['unknown_leg_minutes'])) if trailing else 0)
                from_point=endpoint
            # Tidak memaksa pagi setelah sore; slot di luar waktu yang cocok dikeluarkan.
            if venue_start>period_end or venue_end+trailing_time>day_limit:
                slot['status']='tidak_terjadwal'
                slot['schedule_warning']='Kegiatan tidak muat dalam periode pagi/siang/sore/malam atau melampaui waktu kembali hotel/keberangkatan pulang. Ganti tempat, durasi atau jadwal.'
                skipped_count+=1
                continue
            opening_status=simple_opening_hours_status(item.get('opening_hours'),dt,venue_start,venue_end)
            slot['opening_warning']='Waktu kunjungan diperkirakan di luar jam buka OSM; cek jam terbaru.' if opening_status is False else ''
            if rain is not None and rain>=60 and item['outdoor']:
                slot['weather_warning']='Prakiraan hujan tinggi; pertimbangkan lokasi indoor.'
            price=item_cost(item,cfg)
            charges[item['kind']]+=price
            cost+=price
            if incoming:
                incoming={**incoming,'depart':_clock(moment),'arrive':_clock(moment+travel_min),
                          'waiting_minutes':max(0,venue_start-(moment+travel_min)),
                          'estimated_cost':local_leg_cost(incoming,cfg)}
                legs.append(incoming)
                if incoming['km'] is not None: travel_km+=incoming['km']
                else:missing_leg_count+=1
                travel_min_total+=travel_min
                daily_variable+=incoming['estimated_cost']
                if incoming['km'] is not None and incoming['km']>55:
                    warnings.append(f'Rute {incoming["from"]} → {incoming["to"]} sangat jauh ({incoming["km"]} km); cek apakah layak dalam satu hari.')
            slot.update({'start':_clock(venue_start),'end':_clock(venue_end),
                         'travel_minutes':incoming['minutes'] if incoming else None,
                         'travel_km':incoming['km'] if incoming else None,'leg':incoming,
                         'cost':price,'status':'scheduled'})
            moment=venue_end+cfg['visit_gap_minutes']
            prev=item
            completed+=1
        return_leg=None
        final_arrival=None
        terminal_points=[]
        if completed:
            if last_day:
                if cfg['last_day_via_hotel'] and cfg['return_to_base'] and base:terminal_points.append(('hotel',base))
                if hub:terminal_points.append(('pulang',hub))
            elif cfg['return_to_base'] and base:
                terminal_points.append(('hotel',base))
        cursor=max(first_start,moment-cfg['visit_gap_minutes'])
        for kind,terminal in terminal_points:
            leg=leg_estimate(prev,terminal,cfg,dt,cursor)
            if leg:
                arrival=cursor+(leg['minutes'] if leg['minutes'] is not None else leg.get('reserved_minutes',cfg['unknown_leg_minutes']))
                leg={**leg,'depart':_clock(cursor),'arrive':_clock(arrival),
                     'estimated_cost':local_leg_cost(leg,cfg),'kind':kind}
                if arrival>day_limit:
                    warnings.append('PERINGATAN: Transfer akhir melampaui jam kembali hotel atau keberangkatan pulang.')
                if leg['km'] is not None:travel_km+=leg['km']
                else:missing_leg_count+=1
                travel_min_total+=(leg['minutes'] if leg['minutes'] is not None else leg.get('reserved_minutes',cfg['unknown_leg_minutes']))
                daily_variable+=leg['estimated_cost']
                legs.append(leg)
                return_leg=leg
                final_arrival=leg['arrive']
                cursor=arrival
                prev=terminal
        if cfg['return_to_base'] and not last_day and completed and not terminal_points:
            warnings.append('Perjalanan pulang ke hotel belum dihitung; koordinat hotel belum dipilih.')
        if any(l['minutes'] is None for l in legs):
            warnings.append(f'Ada perpindahan tanpa koordinat: dialokasikan {cfg["unknown_leg_minutes"]} menit per segmen sebagai waktu cadangan, BUKAN hasil perhitungan rute. Isi koordinat atau ganti tempat sebelum berangkat.')
        day_totals.append(cost)
        local_variable_total+=daily_variable
        days.append({'day':di+1,'date':dt,'slots':slots,'cost':cost,
                     'window_start':_clock(first_start),'window_end':_clock(max(0,day_limit)),
                     'is_return_day':last_day,'travel_km_estimate':round(travel_km,2),
                     'travel_minutes_total':travel_min_total,'travel_legs':legs,
                     'return_leg':return_leg,'hotel_return_target':hotel_target,'hotel_arrival':final_arrival if return_leg and return_leg['kind']=='hotel' else None,
                     'variable_transport_cost':daily_variable,
                     'route_sources':sorted({l['source'] for l in legs}),
                     'weather':forecast,'warnings':warnings})
    fixed=fixed_costs(cfg)
    if cfg['local_cost_mode']=='per_km':fixed['transport_lokal']=local_variable_total
    breakdown={**charges,**fixed}
    total=sum(breakdown.values())
    remaining=cfg['budget']-total
    suggestions=[]
    if remaining<0:
        suggestions.append(f'Anggaran kurang Rp{abs(remaining):,}. Mulai dari komponen terbesar atau ganti wisata berbiaya tinggi.'.replace(',','.'))
        pricey=sorted((s['item'] for d in days for s in d['slots'] if s['item'] and s['status']=='scheduled'),key=lambda p:item_cost(p,cfg),reverse=True)
        for item in pricey[:3]:
            if item_cost(item,cfg)>0:
                suggestions.append(f'Pertimbangkan ganti {item["name"]} (estimasi Rp{item_cost(item,cfg):,}/rombongan) dengan alternatif lebih hemat.'.replace(',','.'))
    if not any(s['item'] and s['status']=='scheduled' for d in days for s in d['slots']):
        suggestions.append('Belum ada kegiatan yang muat pada jam tersedia. Sesuaikan waktu mulai, durasi, rute atau kepulangan.')
    if any(s['item'] is None for d in days for s in d['slots']):
        suggestions.append('Beberapa slot kosong: tambahkan tempat melalui tombol Cari / Tambah.')
    if skipped_count:suggestions.append(f'{skipped_count} aktivitas tidak muat setelah waktu perpindahan dan batas kepulangan diperhitungkan; tidak dikenai biaya.')
    if missing_leg_count:suggestions.append(f'{missing_leg_count} perjalanan belum memiliki koordinat/estimasi waktu. Cari koordinat tempat pada kartu destinasi; jadwal bagian tersebut belum dapat dipastikan.')
    if cfg['children']:suggestions.append('Tarif anak 2+ untuk wisata/kuliner adalah persentase asumsi yang bisa diubah.')
    if cfg['infants_under_2']:suggestions.append('Biaya bayi tidak otomatis nol untuk semua layanan; cek kebijakan tiap operator.')
    if cfg['outbound_mode']=='kereta' or cfg['return_mode']=='kereta':
        suggestions.append('KAI: bayi/anak <3 tahun dapat gratis tanpa kursi sesuai ketentuan dan kuota pendamping; verifikasi tiket.')
    if cfg['outbound_mode']=='pesawat' or cfg['return_mode']=='pesawat':
        suggestions.append('Tarif bayi pesawat hanya estimasi persentase; cek tarif resmi maskapai.')
    rooms=room_count(cfg)
    nights=max(0,(date.fromisoformat(cfg['return_date'])-date.fromisoformat(cfg['destination_arrival_date'])).days) if cfg['include_hotel'] else 0
    outgoing=transport_ledger(cfg,'pergi')
    incoming=transport_ledger(cfg,'pulang')
    return {'config':cfg,'itinerary':days,
            'summary':{'breakdown':breakdown,'total':total,'budget':cfg['budget'],'remaining':remaining,
                       'persons':party(cfg),'rooms':rooms,'nights':nights,
                       'day_totals':day_totals,'suggestions':suggestions,
                       'local_routing':{'hotel':cfg['base_name'],'hotel_area':cfg['hotel_area'],
                                        'mode':cfg['local_travel_mode'],'cost_mode':cfg['local_cost_mode'],
                                        'total_km':round(sum(d['travel_km_estimate'] for d in days),2),
                                        'total_minutes':sum(d['travel_minutes_total'] for d in days),
                                        'unresolved_legs':missing_leg_count},
                       'transport_detail':{'pergi':outgoing,'pulang':incoming},
                       'travel_timeline':{
                           'berangkat':f'{cfg["depart_date"]} {cfg["depart_time"]}',
                           'tiba_tujuan':f'{cfg["destination_arrival_date"]} {cfg["destination_arrival_time"]}',
                           'mulai_wisata':f'{cfg["start_date"]} {cfg["arrival_time"]}',
                           'berangkat_pulang':f'{cfg["return_date"]} {cfg["return_time"]}',
                           'tiba_rumah':f'{cfg["home_arrival_date"]} {cfg["home_arrival_time"]}'},
                       'price_notice':'Harga tiket, kuliner, hotel, transportasi dan estimasi perjalanan bukan harga atau ETA live.'},
            'weather':weather or {'days':[]}}

def optimize_budget(raw, itinerary, raw_places, weather=None):
    """Replanner hemat: ganti destinasi dengan alternatif nyata di daftar tempat.

    Tidak mengubah biaya tetap (hotel/transport); tidak pernah menciptakan tiket palsu.
    """
    cfg=clean_config(raw)
    if not isinstance(raw_places,list) or len(raw_places)>500:
        raise ValueError('Daftar alternatif tempat tidak valid.')
    candidates=[clean_place(p) for p in raw_places]
    result=recalculate(cfg,itinerary,weather)
    if result['summary']['remaining']>=0:
        result['adjustments']=[]
        return result
    days=deepcopy(result['itinerary'])
    changes=[]
    for _ in range(70):
        if result['summary']['remaining']>=0:
            break
        used={s['item']['id'] for d in days for s in d['slots'] if s['item'] and s['item']['id']}
        options=[]
        for di,d in enumerate(days):
            for si,slot in enumerate(d['slots']):
                old=slot['item']
                if old is None or slot.get('status')!='scheduled':continue
                before=item_cost(old,cfg)
                if before<=0:continue
                for new in candidates:
                    if new['kind']!=old['kind'] or (new['id'] and new['id'] in used):continue
                    after=item_cost(new,cfg)
                    saved=before-after
                    if saved<=0:continue
                    km=distance(old,new)
                    penalty=(min(20_000,km*500) if km is not None else 0)
                    quality=preference_score(new,cfg,None,used)
                    options.append((saved-penalty+quality*150, saved, di, si, new))
        if not options:break
        best=max(options,key=lambda x:(x[0],x[1]))
        _,saved,di,si,new=best
        old=days[di]['slots'][si]['item']
        days[di]['slots'][si]['item']=deepcopy(new)
        changes.append({'day':di+1,'from':old['name'],'to':new['name'],'saved':saved})
        result=recalculate(cfg,days,weather)
    result['adjustments']=changes
    if changes:
        saved=sum(c['saved'] for c in changes)
        result['summary']['suggestions'].insert(0,f'{len(changes)} pilihan diganti ke alternatif lebih hemat (penghematan estimasi Rp{saved:,}).'.replace(',','.'))
    elif result['summary']['remaining']<0:
        result['summary']['suggestions'].insert(0,'Tidak ada alternatif wisata lebih murah dalam daftar. Kurangi biaya tetap atau pilih tempat manual.')
    return result
