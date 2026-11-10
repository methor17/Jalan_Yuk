"""Estimasi perjalanan antartempat tanpa Google Routes API.

Rute per segmen memakai OSRM/ORS (jika tersedia) dan asumsi konservatif transparan.
Tanpa data kemacetan live; pergeseran jadwal diikuti perhitungan ulang Python.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time
from planner import clean_config, recalculate, timed_routing_key
import providers

MAX_LEGS = 28


def refresh(config, itinerary, weather=None, day_index=None, route_lookup=None):
    cfg = clean_config(config)
    if day_index is not None and (isinstance(day_index, bool) or
                                   not isinstance(day_index, int) or
                                   not 0 <= day_index < cfg['days']):
        raise ValueError('Indeks hari tidak valid.')
    route_lookup = route_lookup or providers.route_segment
    plan = recalculate(cfg, itinerary, weather)
    attempted = set()
    updated = 0
    errors = []
    sources = {}
    unresolved = 0

    def collect():
        nonlocal unresolved
        unresolved = 0
        requests = {}
        for di, day in enumerate(plan['itinerary']):
            if day_index is not None and di != day_index:
                continue
            for leg in day['travel_legs']:
                start, end = leg.get('start_coords'), leg.get('end_coords')
                if not start or not end:
                    unresolved += 1
                    continue
                minute = int(leg['depart'][:2]) * 60 + int(leg['depart'][3:5])
                key = timed_routing_key(start, end, cfg['local_travel_mode'],
                                        day['date'], minute, cfg['routing_provider'])
                if not key:
                    unresolved += 1
                    continue
                if key in cfg['route_cache'] or key in attempted:
                    continue
                requests[key] = (start, end, day['date']+'T'+leg['depart']+':00')
        return requests

    def fetch(entry):
        key, (start, end, iso) = entry
        return key, route_lookup(start, end, iso, cfg['local_travel_mode'],
                                 cfg['routing_provider'], cfg['local_utc_offset'])

    # Tahap kedua menangani keberangkatan yang bergeser setelah ETA tahap pertama.
    # Batasi permintaan untuk melindungi layanan routing publik.
    for _ in range(2):
        batch = collect()
        batch = dict(list(batch.items())[:max(0, MAX_LEGS-updated)])
        if not batch:
            break
        attempted.update(batch)
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(fetch, entry) for entry in batch.items()]
            for future in as_completed(futures):
                try:
                    key, result = future.result()
                    if (not isinstance(result,dict) or
                            not 0 <= float(result['km']) <= 2500 or
                            not 0 <= int(result['minutes']) <= 1500):
                        raise ValueError('Estimasi rute tidak valid.')
                    source = str(result.get('source') or '')
                    if source not in ('osrm_driving','multi_source_max'):
                        raise ValueError('Sumber rute tidak valid.')
                    cfg['route_cache'][key] = {
                        'km':round(float(result['km']),2),
                        'minutes':int(result['minutes']),
                        'source':source,
                        'fetched_at':int(result.get('fetched_at') or time())}
                    if source=='multi_source_max':
                        cfg['route_cache'][key].update({
                            'samples':result.get('samples',[])[:4],
                            'selected_source':str(result.get('selected_source') or ''),
                            'confidence':str(result.get('confidence') or ''),
                            })
                    sources[source] = sources.get(source,0)+1
                    updated += 1
                    if result.get('fallback_reason'):
                        errors.append('Sebagian sumber rute gagal; sistem menggunakan sumber lain atau estimasi cadangan.')
                except Exception:
                    errors.append('Sebagian rute gagal diambil dari penyedia layanan.')
        if len(cfg['route_cache']) > 380:
            cfg['route_cache'] = dict(list(cfg['route_cache'].items())[-380:])
        plan = recalculate(cfg, itinerary, weather)
    # Final state: rerun validation for missing coordinates and unrefreshed legs.
    collect()
    notices = []
    if unresolved:
        notices.append(f'{unresolved} segmen belum memiliki koordinat lengkap.')
    if errors:
        notices.extend(dict.fromkeys(errors))
    if sources.get('multi_source_max'):
        notices.append('Per segmen dipakai skenario waktu terlama + cadangan; estimasi bukan jaminan kondisi jalan.')
    if sources.get('osrm_driving'):
        notices.append('OSRM tidak menyediakan prediksi macet; ruas jalan yang sama dapat memiliki ETA yang sama.')
    if not attempted:
        notices.append('Tidak ada rute baru: cache masih berlaku atau tidak ada lokasi berkoordinat.')
    if updated >= MAX_LEGS:
        notices.append('Batas 28 rute per pembaruan tercapai. Segarkan per hari untuk melengkapi hasil.')
    return {'plan':plan,'routing':{
        'updated':updated,'unresolved':unresolved,'sources':sources,
        'notices':notices,'day':day_index,'requested':len(attempted)}}
