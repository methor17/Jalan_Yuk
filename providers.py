"""Integrasi peta/cuaca tanpa API key. Tidak melakukan scraping Google.

Nominatim OSM publik: 1 req/detik untuk seluruh instance, TANPA autocomplete,
User-Agent khusus, cache, hanya atas aksi pencarian manual user.
Overpass: discovery terbatas area kota; gunakan sendiri/berbayar untuk traffic besar.
"""
from __future__ import annotations
import json
import math
import os
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from catalog import build_catalog, city_list

NOMINATIM = os.getenv('NOMINATIM_URL', 'https://nominatim.openstreetmap.org').rstrip('/')
OVERPASS = os.getenv('OVERPASS_URL', 'https://overpass.private.coffee/api/interpreter')
OPEN_METEO = 'https://api.open-meteo.com/v1/forecast'
OSRM = os.getenv('OSRM_URL', 'https://router.project-osrm.org').rstrip('/')
# Pengelola public deployment sebaiknya menentukan alamat kontak aplikasinya.
AGENT = os.getenv('JALANYUK_USER_AGENT', 'JalanYukTravelPlanner/2.5 (personal-use; set JALANYUK_USER_AGENT to include contact for production)')
_CACHE = {}
_LOCK = threading.RLock()
_NOMINATIM_LOCK = threading.Lock()
_last_nominatim = [0.0]

CITIES = {
    'yogyakarta': (-7.7956, 110.3695), 'jogja': (-7.7956, 110.3695),
    'bandung': (-6.9175, 107.6191), 'malang': (-7.9666, 112.6326),
    'batu': (-7.8712, 112.5267), 'semarang': (-6.9667, 110.4167),
    'solo': (-7.5755, 110.8243), 'surabaya': (-7.2575, 112.7521),
    'jakarta': (-6.2088, 106.8456), 'denpasar': (-8.6705, 115.2126),
    'bogor': (-6.5950, 106.8166), 'bali': (-8.6705, 115.2126),
}


def _json_request(url, ttl=3600, timeout=10):
    now = time.time()
    with _LOCK:
        if url in _CACHE and _CACHE[url][0] > now:
            return _CACHE[url][1]
    req = Request(url, headers={'User-Agent': AGENT, 'Accept': 'application/json'})
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read(3_000_001)
        if len(raw) > 3_000_000:
            raise ValueError('Respons layanan eksternal terlalu besar.')
        data = json.loads(raw)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        raise ValueError('Layanan peta/cuaca sedang tidak tersedia. Coba lagi atau gunakan data contoh.') from exc
    with _LOCK:
        if len(_CACHE) >= 180:
            for k in list(_CACHE)[:40]:
                _CACHE.pop(k, None)
        _CACHE[url] = (time.time() + ttl, data)
    return data


def _nominatim_request(url):
    with _NOMINATIM_LOCK:
        with _LOCK:
            if url in _CACHE and _CACHE[url][0] > time.time():
                return _CACHE[url][1]
        remaining = 1.1 - (time.monotonic() - _last_nominatim[0])
        if remaining > 0:
            time.sleep(remaining)
        _last_nominatim[0] = time.monotonic()
        return _json_request(url, ttl=7 * 86400)


def geocode(query):
    query = str(query).strip()
    if not (2 <= len(query) <= 100):
        raise ValueError('Nama kota/lokasi harus 2–100 karakter.')
    url = f'{NOMINATIM}/search?' + urlencode({'q': query, 'format': 'jsonv2', 'addressdetails': 1, 'limit': 5, 'accept-language': 'id'})
    try:
        data = _nominatim_request(url)
        results = []
        for item in data:
            lat, lon = float(item['lat']), float(item['lon'])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            results.append({'name': str(item.get('display_name', query))[:180], 'lat': lat, 'lon': lon,
                            'type': item.get('type', ''), 'osm_type': item.get('osm_type', ''),
                            'osm_id': item.get('osm_id')})
        if results:
            return {'locations': results, 'source': 'OpenStreetMap Nominatim', 'fallback': False}
        return {'locations': [], 'source': 'OpenStreetMap Nominatim', 'fallback': False}
    except ValueError:
        key = query.casefold().strip()
        coords = CITIES.get(key)
        if coords:
            return {'locations': [{'name': query.title() + ', Indonesia (koordinat cadangan)', 'lat': coords[0], 'lon': coords[1], 'type': 'city'}],
                    'source': 'Koordinat bawaan (offline)', 'fallback': True}
        raise


def estimate_price(kind, tags):
    # BUKAN tarif resmi. Perlu diverifikasi user sebelum bepergian.
    if kind == 'kuliner':
        return 45000 if tags.get('amenity') == 'restaurant' else 30000
    tourism = tags.get('tourism', '')
    if tourism in ('museum', 'gallery', 'zoo', 'theme_park', 'aquarium'):
        return 40000
    if tourism in ('attraction', 'viewpoint'):
        return 20000
    if tags.get('charge') == 'no' or tags.get('fee') == 'no':
        return 0
    return 15000


def _theme(tags, kind):
    if kind == 'kuliner':
        return {'restaurant':'Restoran', 'cafe':'Kafe', 'fast_food':'Cepat saji', 'food_court':'Pusat kuliner'}.get(tags.get('amenity'), 'Kuliner')
    if tags.get('natural') in ('beach', 'peak', 'waterfall'):
        return 'Alam'
    if tags.get('historic'):
        return 'Sejarah'
    return {'museum': 'Museum', 'gallery': 'Seni', 'zoo': 'Keluarga', 'theme_park': 'Keluarga',
            'viewpoint':'Panorama', 'attraction':'Wisata', 'information':'Edukasi',
            'aquarium':'Keluarga'}.get(tags.get('tourism'), 'Wisata')


def _poi_from_osm(item):
    tags = item.get('tags') or {}
    name = str(tags.get('name:en') or tags.get('name') or '').strip()
    if not name or len(name) > 120:
        return None
    pos = item.get('center') or item
    try:
        lat, lon = float(pos['lat']), float(pos['lon'])
    except (KeyError, ValueError, TypeError):
        return None
    kind = 'kuliner' if tags.get('amenity') in ('restaurant', 'cafe', 'fast_food', 'food_court') else 'wisata'
    theme = _theme(tags, kind)
    osm_type = item.get('type', 'node')
    return {'id': f'osm-{osm_type}-{item["id"]}', 'name': name, 'kind': kind,
            'price': estimate_price(kind, tags), 'price_status': 'ilustrasi',
            'lat': lat, 'lon': lon, 'theme': theme,
            'area': str(tags.get('addr:suburb') or tags.get('addr:city') or '')[:80],
            'description': str(tags.get('description') or '')[:180],
            'opening_hours': str(tags.get('opening_hours') or '')[:120],
            'wheelchair': str(tags.get('wheelchair') or 'unknown')[:20],
            'website': str(tags.get('website') or '')[:250],
            'outdoor': theme in ('Alam', 'Panorama', 'Pantai', 'Taman'),
            'duration': 80 if kind == 'wisata' else 55,
            'source': 'OpenStreetMap', 'osm_url': f'https://www.openstreetmap.org/{osm_type}/{item["id"]}'}


def discover(lat, lon, radius=10000):
    lat, lon = float(lat), float(lon)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('Koordinat destinasi tidak valid.')
    radius = max(1000, min(int(radius), 15000))
    # Hanya berdasarkan aksi user, satu radius, hasil dibatasi. Hindari scan sistematis.
    around = f'(around:{radius},{lat:.5f},{lon:.5f})'
    query = ('[out:json][timeout:18];('
             f'nwr["tourism"~"^(attraction|museum|gallery|viewpoint|zoo|theme_park|aquarium)$"]["name"]{around};'
             f'nwr["historic"~"^(castle|monument|archaeological_site|memorial)$"]["name"]{around};'
             f'nwr["natural"~"^(beach|waterfall)$"]["name"]{around};'
             f'nwr["amenity"~"^(restaurant|cafe|fast_food|food_court)$"]["name"]{around};'
             ');out center 260;')
    url = OVERPASS + '?' + urlencode({'data': query})
    data = _json_request(url, ttl=12 * 3600, timeout=22)
    unique = {}
    for element in data.get('elements', []):
        place = _poi_from_osm(element)
        if place:
            unique[place['id']] = place
    results = list(unique.values())
    results.sort(key=lambda p: (p['kind'] != 'wisata', round(haversine(lat, lon, p['lat'], p['lon']), 1), p['name']))
    return {'places': results[:240], 'total': len(results), 'source': 'OpenStreetMap (Overpass)',
            'notice': 'Tiket dan kuliner = estimasi ilustratif, bukan harga live. Jam buka hanya jika terdata di OSM.'}


def search_place(query, lat=None, lon=None):
    query = str(query).strip()
    if not (2 <= len(query) <= 100):
        raise ValueError('Masukkan nama tempat minimal 2 karakter.')
    # User-triggered search (not autocomplete); Nominatim appropriate for individual named POI.
    q = query
    if lat is not None and lon is not None:
        # Prioritaskan sekitar lokasi, tapi tidak memaksakan hasil pada koordinat yang keliru.
        lat, lon = float(lat), float(lon)
        delta = 0.5
        params = {'q': q, 'format':'jsonv2', 'limit':10, 'extratags':1, 'namedetails':1, 'accept-language':'id',
                  'viewbox':f'{lon-delta:.5f},{lat+delta:.5f},{lon+delta:.5f},{lat-delta:.5f}', 'bounded':0}
    else:
        params = {'q': q, 'format':'jsonv2', 'limit':10, 'extratags':1, 'namedetails':1, 'accept-language':'id'}
    data = _nominatim_request(NOMINATIM + '/search?' + urlencode(params))
    out = []
    for p in data:
        tags = p.get('extratags') or {}
        cls = p.get('class', '')
        kind = 'kuliner' if cls == 'amenity' and p.get('type') in ('restaurant','cafe','fast_food','food_court') else 'wisata'
        name = str((p.get('namedetails') or {}).get('name') or p.get('name') or p.get('display_name', '').split(',')[0]).strip()
        if not name:
            continue
        osm_type = {'N':'node','W':'way','R':'relation'}.get(str(p.get('osm_type','')).upper()[:1], 'node')
        out.append({'id': f'osm-{osm_type}-{p.get("osm_id", len(out))}', 'name': name[:120],
                    'kind':kind, 'price': estimate_price(kind, {'amenity':p.get('type',''), 'tourism':p.get('type',''), **tags}),
                    'price_status':'ilustrasi', 'lat': float(p['lat']), 'lon': float(p['lon']),
                    'theme': _theme({'tourism':p.get('type',''), 'amenity':p.get('type','')}, kind),
                    'area': str(p.get('display_name',''))[:110], 'description':'',
                    'opening_hours':str(tags.get('opening_hours',''))[:120],
                    'wheelchair':str(tags.get('wheelchair','unknown'))[:20],
                    'outdoor': p.get('type') in ('beach', 'park', 'viewpoint'),
                    'duration':80 if kind=='wisata' else 55,
                    'source':'OpenStreetMap Nominatim',
                    'osm_url':f'https://www.openstreetmap.org/{osm_type}/{p.get("osm_id", 0)}'})
    return {'places': out, 'source': 'OpenStreetMap Nominatim', 'notice': 'Harga ilustrasi, bukan tarif resmi.'}



def discover_hotels(lat,lon,radius=9000):
    """Pencarian akomodasi berdasarkan aksi eksplisit pengguna, bukan scraping Google."""
    try:lat,lon=float(lat),float(lon)
    except (ValueError,TypeError):raise ValueError('Isi koordinat kota sebelum mencari hotel.') from None
    if not(math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180):
        raise ValueError('Koordinat pencarian hotel tidak valid.')
    radius=max(1000,min(int(radius),15000))
    around=f'(around:{radius},{lat:.5f},{lon:.5f})'
    q=('[out:json][timeout:18];('
       f'nwr["tourism"~"^(hotel|hostel|guest_house|motel|apartment|chalet)$"]["name"]{around};'
       ');out center 120;')
    data=_json_request(OVERPASS+'?'+urlencode({'data':q}),ttl=12*3600,timeout=22)
    found={}
    for el in data.get('elements',[]):
        tags=el.get('tags') or {}
        name=str(tags.get('name') or '').strip()[:120]
        coords=el.get('center') or el
        try: hlat=float(coords['lat']);hlon=float(coords['lon'])
        except (KeyError,ValueError,TypeError):continue
        if not name:continue
        identifier=f'hotel-{el.get("type","node")}-{el.get("id",0)}'
        area=', '.join(x for x in (tags.get('addr:street'),tags.get('addr:suburb'),tags.get('addr:city')) if x)[:160]
        found[identifier]={'id':identifier,'name':name,'area':area,'lat':hlat,'lon':hlon,
                           'type':str(tags.get('tourism') or 'hotel'), 'source':'OpenStreetMap'}
    hotels=sorted(found.values(),key=lambda x:haversine(lat,lon,x['lat'],x['lon']))[:90]
    return {'hotels':hotels,'source':'OpenStreetMap (Overpass)','notice':'Daftar nama dan lokasi hotel, bukan ketersediaan kamar atau tarif live.'}


def search_hotels(query,lat=None,lon=None):
    query=str(query).strip()
    if not 2<=len(query)<=110:raise ValueError('Ketik nama hotel/kawasan minimal 2 karakter.')
    params={'q':query,'format':'jsonv2','limit':12,'accept-language':'id','extratags':1}
    if lat is not None and lon is not None:
        lat,lon=float(lat),float(lon)
        if not(-90<=lat<=90 and -180<=lon<=180):raise ValueError('Koordinat tidak valid.')
        params['viewbox']=f'{lon-.35:.5f},{lat+.35:.5f},{lon+.35:.5f},{lat-.35:.5f}'
        params['bounded']=0
    data=_nominatim_request(NOMINATIM+'/search?'+urlencode(params))
    hotels=[]
    for p in data:
        try:hlat=float(p['lat']);hlon=float(p['lon'])
        except (KeyError,TypeError,ValueError):continue
        named=str(p.get('name') or p.get('display_name') or query)
        hotels.append({'id':f'nominatim-{p.get("place_id",len(hotels))}',
                       'name':named.split(',')[0][:120],
                       'area':str(p.get('display_name') or '')[:160],
                       'lat':hlat,'lon':hlon,'type':str(p.get('type') or 'area'),
                       'source':'OpenStreetMap Nominatim'})
    return {'hotels':hotels,'source':'OpenStreetMap Nominatim',
            'notice':'Hasil dapat berupa kawasan, bukan hotel; pastikan koordinat sebelum memilih.'}

def haversine(lat1, lon1, lat2, lon2):
    a1, a2 = math.radians(float(lat1)), math.radians(float(lat2))
    dlat = a2-a1
    dlon = math.radians(float(lon2)-float(lon1))
    a = math.sin(dlat/2)**2 + math.cos(a1)*math.cos(a2)*math.sin(dlon/2)**2
    return 6371 * 2 * math.asin(min(1, math.sqrt(max(0, a))))


def route(coords, mode='driving'):
    if mode not in ('driving',):
        raise ValueError('Mode rute hanya driving untuk server demo.')
    if not isinstance(coords, list) or len(coords) < 2 or len(coords) > 10:
        raise ValueError('Rute membutuhkan 2–10 lokasi.')
    pairs = []
    for point in coords:
        lat, lon = float(point['lat']), float(point['lon'])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError('Koordinat tidak valid.')
        pairs.append(f'{lon:.6f},{lat:.6f}')
    url = f'{OSRM}/route/v1/driving/' + ';'.join(pairs) + '?overview=full&geometries=geojson&steps=false'
    data = _json_request(url, ttl=3600, timeout=14)
    if data.get('code') != 'Ok' or not data.get('routes'):
        raise ValueError('Jalur kendaraan belum tersedia untuk lokasi ini.')
    chosen = data['routes'][0]
    return {'distance_km':round(chosen['distance']/1000,1), 'duration_minutes':round(chosen['duration']/60),
            'geometry': chosen['geometry'], 'legs':[{'km':round(x['distance']/1000,2),'minutes':round(x['duration']/60)} for x in chosen.get('legs',[])], 'source':'OSRM demo (estimasi rute, tidak termasuk lalu lintas)'}


def forecast(lat, lon, start_date, days):
    from datetime import date, timedelta
    day = date.fromisoformat(start_date)
    today = date.today()
    if day < today or day > today + timedelta(days=15):
        return {'days':[], 'notice':'Prakiraan hanya tersedia untuk perjalanan hingga 16 hari ke depan.'}
    end = min(day + timedelta(days=int(days)-1), today + timedelta(days=15))
    params = {'latitude':float(lat), 'longitude':float(lon),
              'daily':'precipitation_probability_max,weather_code,temperature_2m_max,temperature_2m_min',
              'timezone':'auto', 'start_date':day.isoformat(), 'end_date':end.isoformat()}
    data = _json_request(OPEN_METEO + '?' + urlencode(params), ttl=3600, timeout=10)
    d = data.get('daily') or {}
    dates = d.get('time') or []
    result = []
    for idx, iso in enumerate(dates):
        rain = (d.get('precipitation_probability_max') or [])
        code = (d.get('weather_code') or [])
        temps = (d.get('temperature_2m_max') or [])
        result.append({'date':iso, 'rain_probability':rain[idx] if idx < len(rain) else None,
                       'code':code[idx] if idx < len(code) else None,
                       'temperature_max':temps[idx] if idx < len(temps) else None})
    return {'days':result, 'source':'Open-Meteo', 'notice':'Prakiraan dapat berubah, bukan jaminan kondisi cuaca.'}


def curated_fallback(city):
    try:
        meta = build_catalog(city)
    except ValueError:
        return []
    out = []
    for p in meta['places']:
        out.append({**p, 'lat':None, 'lon':None, 'opening_hours':'', 'wheelchair':'unknown',
                    'outdoor':p['theme'] in ('Alam','Panorama','Pantai','Taman'),
                    'duration':85 if p['kind']=='wisata' else 55,
                    'source':'Katalog contoh JalanYuk', 'price_status':'ilustrasi'})
    return out


def route_segment(start, end, departure_iso, mode='mobil', provider='multi', utc_offset=7):
    """Estimate each travel segment without Google Routes API.

    'multi'/'auto' compare available non-Google routing sources plus a
    conservative margin. 'osrm' requests road geometry for driving only.
    """
    from datetime import datetime
    if provider not in ('auto','osrm','multi'):
        raise ValueError('Penyedia rute tidak valid.')
    if mode not in ('mobil','motor','jalan','sepeda','transit'):
        raise ValueError('Moda transportasi lokal tidak valid.')
    try:
        for point in (start,end):
            lat,lon=float(point['lat']),float(point['lon'])
            if not (math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180):
                raise ValueError()
        datetime.fromisoformat(departure_iso)
    except (TypeError,ValueError,KeyError):
        raise ValueError('Koordinat atau waktu perjalanan tidak valid.') from None
    if provider in ('multi','auto') or mode!='mobil':
        return compare_route_sources(start,end,departure_iso,mode,utc_offset)
    # OSRM demo gives road graph ETA, without traffic prediction.
    r=_osrm_comparison(start,end)
    return {**r,'traffic_aware':False}


# Provider comparison is server-side; API keys never reach the browser.
# OSM's public OSRM demo is used as a light development fallback; production
# traffic must use a contracted/self-hosted routing service.
_OSRM_LOCK = threading.Lock()
_OSRM_LAST = [0.0]

def openrouteservice_segment(start,end,mode):
    """Optional independent road router (set OPENROUTESERVICE_API_KEY)."""
    key=os.getenv('OPENROUTESERVICE_API_KEY','').strip()
    if not key:
        raise ValueError('OpenRouteService belum dikonfigurasi.')
    profiles={'mobil':'driving-car','motor':'driving-car',
              'jalan':'foot-walking','sepeda':'cycling-regular'}
    if mode not in profiles:
        raise ValueError('OpenRouteService tidak mendukung mode transit.')
    url='https://api.openrouteservice.org/v2/directions/'+profiles[mode]
    coords=[[float(start['lon']),float(start['lat'])],[float(end['lon']),float(end['lat'])]]
    req=Request(url,data=json.dumps({'coordinates':coords}).encode('utf-8'),method='POST',
                headers={'Authorization':key,'Content-Type':'application/json',
                         'Accept':'application/json','User-Agent':AGENT})
    try:
        with urlopen(req,timeout=9) as response:raw=response.read(400001)
        payload=json.loads(raw)
        summary=payload['routes'][0]['summary']
        km=float(summary['distance'])/1000
        minute=max(1,math.ceil(float(summary['duration'])/60)) if km>0 else 0
        if not (math.isfinite(km) and math.isfinite(minute) and 0<=km<=2500 and 0<=minute<=1500):
            raise ValueError('Estimasi ORS tidak valid.')
        return {'km':round(km,2),'minutes':minute,'source':'openrouteservice',
                'fetched_at':int(time.time()),'attribution':'© OpenStreetMap contributors / openrouteservice'}
    except (HTTPError,URLError,TimeoutError,ValueError,KeyError,IndexError,OSError) as exc:
        raise ValueError('OpenRouteService tidak tersedia.') from exc


def _osrm_comparison(start,end):
    # Protect the volunteer-hosted public demo from bursts across threads.
    with _OSRM_LOCK:
        remaining=1.05-(time.monotonic()-_OSRM_LAST[0])
        if remaining>0:time.sleep(remaining)
        _OSRM_LAST[0]=time.monotonic()
        result=route([start,end])
    row=result['legs'][0]
    return {'km':float(row['km']),'minutes':int(row['minutes']),
            'source':'osrm_driving','fetched_at':int(time.time()),
            'attribution':'© OpenStreetMap contributors / OSRM'}


def compare_route_sources(start,end,departure_iso,mode='mobil',utc_offset=7):
    """Use the longest supported non-Google ETA, plus a safety allowance.

    OSRM driving and optional OpenRouteService use street networks. A single
    response is *not* falsely presented as multiple independent sources.
    With no route result, estimate from geometry and label uncertainty.
    """
    from datetime import datetime
    if mode not in ('mobil','motor','jalan','sepeda','transit'):
        raise ValueError('Mode perjalanan tidak dikenal.')
    try:
        for point in (start,end):
            lat,lon=float(point['lat']),float(point['lon'])
            if not (math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180):
                raise ValueError()
        datetime.fromisoformat(departure_iso)
    except (ValueError,TypeError,KeyError):
        raise ValueError('Koordinat atau waktu keberangkatan tidak valid.') from None
    samples=[];errors=[]
    if os.getenv('OPENROUTESERVICE_API_KEY','').strip() and mode!='transit':
        try:samples.append(openrouteservice_segment(start,end,mode))
        except ValueError:errors.append('OpenRouteService tidak tersedia.')
    if mode=='mobil':
        try:samples.append(_osrm_comparison(start,end))
        except (ValueError,KeyError,IndexError,TypeError):errors.append('OSRM tidak tersedia.')
    physical=haversine(start['lat'],start['lon'],end['lat'],end['lon'])
    road_km=max((r['km'] for r in samples),default=round(physical*1.35,2))
    if samples:
        top=max(r['minutes'] for r in samples)
        # Safety factor models delays; this is NOT a live traffic prediction.
        conservative=math.ceil(top*(1.25 if mode in ('mobil','motor','transit') else 1.1)+(5 if road_km>.2 else 0))
        winner=max(samples,key=lambda r:r['minutes'])
        selected=max(top,conservative)
        confidence='sumber+rencana_cadangan'
    else:
        speed={'mobil':22,'motor':24,'jalan':3.8,'sepeda':11,'transit':14}[mode]
        selected=math.ceil(road_km*60/speed+(10 if mode in ('mobil','motor','transit') else 3)) if road_km>.05 else 0
        winner={'source':'approx_distance','km':road_km,'minutes':selected}
        confidence='perkiraan_tanpa_rute'
    selected=max(0,min(1500,selected))
    return {'km':round(float(road_km),2),'minutes':selected,
            'base_minutes':int(winner['minutes']),'source':'multi_source_max',
            'selected_source':winner['source'],'confidence':confidence,
            'samples':[{'source':r['source'],'minutes':int(r['minutes']),
                        'km':round(float(r['km']),2)} for r in samples],
            'fetched_at':int(time.time()),'fallback_reason':' '.join(errors)[:240],
            'attribution':'© OpenStreetMap contributors'}
