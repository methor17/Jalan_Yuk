import sys
import unittest
from pathlib import Path
from datetime import date,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from planner import clean_config,clean_place,generate_plan,recalculate,integer,item_cost,fixed_costs,reorder_day,optimize_budget,simple_opening_hours_status
from providers import haversine,_poi_from_osm,estimate_price,curated_fallback,discover,geocode,search_place
from unittest.mock import patch

CONFIG={'city':'Yogyakarta','city_lat':-7.7956,'city_lon':110.3695,'origin':'Jakarta',
        'budget':3_000_000,'days':3,'start_date':date.today().isoformat(),
        'arrival_time':'09:00','adults':2,'children':1,'seniors':0,
        'pace':'normal','intercity_per_person':100000,'hotel_rate':300000,
        'local_per_person_day':30000,'parking_per_day':10000,'miscellaneous':30000,
        'emergency_fund':50000,'room_capacity':2,'include_hotel':True}
PLACES=[
    {'id':f'w{i}','name':f'Wisata {i}','kind':'wisata','price':10000+i*5000,'theme':'Alam','area':'Pusat',
     'lat':-7.75+i*.008,'lon':110.36+i*.007,'outdoor':True,'duration':80}
    for i in range(14)] + [
    {'id':f'k{i}','name':f'Kuliner {i}','kind':'kuliner','price':20000+i*5000,'theme':'Kuliner','area':'Pusat',
     'lat':-7.8+i*.008,'lon':110.38+i*.007,'duration':55} for i in range(15)]

class PlannerTests(unittest.TestCase):
    def test_config(self):
        cfg=clean_config(CONFIG)
        self.assertEqual(cfg['days'],3)
        self.assertEqual(cfg['adults'],2)
        self.assertEqual(cfg['city_lat'],-7.7956)
    def test_no_people(self):
        with self.assertRaises(ValueError):clean_config({**CONFIG,'adults':0,'children':0})
    def test_invalid_date(self):
        with self.assertRaises(ValueError):clean_config({**CONFIG,'start_date':'foo'})
    def test_invalid_time(self):
        with self.assertRaises(ValueError):clean_config({**CONFIG,'arrival_time':'25:77'})
    def test_budget_negative(self):
        with self.assertRaises(ValueError):clean_config({**CONFIG,'budget':-1})
    def test_bad_pace(self):
        with self.assertRaises(ValueError):clean_config({**CONFIG,'pace':'random'})
    def test_bad_price(self):
        with self.assertRaises(ValueError):clean_place({**PLACES[0],'price':-1})
    def test_boolean_rejected(self):
        with self.assertRaises(ValueError):integer(True,'harga')
    def test_party_cost(self):
        self.assertEqual(item_cost(clean_place(PLACES[0]),clean_config(CONFIG)),27000)
    def test_fixed_cost(self):
        cfg=clean_config(CONFIG)
        costs=fixed_costs(cfg)
        self.assertEqual(costs['hotel'],2*2*300000)
        self.assertEqual(costs['transport_antar_kota'],300000)
        self.assertEqual(costs['transport_lokal'],270000)
    def test_generate_all_slots(self):
        p=generate_plan(CONFIG,PLACES)
        self.assertEqual(len(p['itinerary']),3)
        self.assertEqual(len(p['itinerary'][0]['slots']),4)
        self.assertTrue(p['itinerary'][0]['slots'][0]['item'])
        self.assertEqual(p['summary']['total'],sum(p['summary']['breakdown'].values()))
        self.assertEqual(p['summary']['remaining'],CONFIG['budget']-p['summary']['total'])
    def test_price_update(self):
        p=generate_plan(CONFIG,PLACES)
        old=p['summary']['total']
        old_price=p['itinerary'][0]['slots'][0]['item']['price']
        p['itinerary'][0]['slots'][0]['item']['price']=old_price+10000
        new=recalculate(CONFIG,p['itinerary'])
        self.assertEqual(new['summary']['total'],old+27000)
    def test_remove_location(self):
        p=generate_plan(CONFIG,PLACES)
        cost=p['itinerary'][0]['slots'][0]['cost']
        p['itinerary'][0]['slots'][0]['item']=None
        q=recalculate(CONFIG,p['itinerary'])
        self.assertEqual(q['summary']['total'],p['summary']['total']-cost)
    def test_low_budget(self):
        p=generate_plan({**CONFIG,'budget':10000},PLACES)
        self.assertLess(p['summary']['remaining'],0)
        self.assertTrue(p['summary']['suggestions'])
    def test_no_candidates(self):
        p=generate_plan(CONFIG,[])
        self.assertEqual(p['summary']['wisata'] if 'wisata' in p['summary'] else p['summary']['breakdown']['wisata'],0)
        self.assertTrue(p['summary']['suggestions'])
    def test_unknown_city_manual(self):
        p=generate_plan({**CONFIG,'city':'Selayar'},PLACES)
        self.assertEqual(p['config']['city'],'Selayar')
    def test_pace_santai(self):
        p=generate_plan({**CONFIG,'pace':'santai'},PLACES)
        self.assertEqual(len(p['itinerary'][0]['slots']),3)
    def test_pace_padat(self):
        p=generate_plan({**CONFIG,'pace':'padat'},PLACES)
        self.assertEqual(len(p['itinerary'][0]['slots']),5)
    def test_weather_rain(self):
        p=generate_plan(CONFIG,PLACES,weather={'days':[{'date':CONFIG['start_date'],'rain_probability':91}]})
        self.assertTrue(any(s.get('weather_warning') for s in p['itinerary'][0]['slots'] if s['item']))
    def test_distance(self):
        self.assertEqual(round(haversine(0,0,0,0)),0)
        self.assertGreater(haversine(-7.8,110.3,-7.7,110.3),10)
    def test_reorder_preserves_food(self):
        p=generate_plan(CONFIG,PLACES)
        q=recalculate(CONFIG,p['itinerary'],reorder=True)
        self.assertEqual([s['kind'] for s in q['itinerary'][0]['slots']],[s['kind'] for s in p['itinerary'][0]['slots']])
    def test_missing_coords_no_made_up_route(self):
        single=[{k:v for k,v in p.items() if k not in ('lat','lon')} for p in PLACES]
        p=generate_plan(CONFIG,single)
        self.assertTrue(all(s['travel_km'] is None for d in p['itinerary'] for s in d['slots']))
    def test_osm_parse(self):
        point={'type':'node','id':234,'lat':-7.7,'lon':110.4,'tags':{'name':'Candi Uji','tourism':'museum','opening_hours':'Mo-Su 10:00-17:00'}}
        p=_poi_from_osm(point)
        self.assertEqual(p['kind'],'wisata')
        self.assertEqual(p['source'],'OpenStreetMap')
        self.assertEqual(p['price_status'],'ilustrasi')
        self.assertEqual(p['opening_hours'],'Mo-Su 10:00-17:00')
    def test_osm_no_name(self):
        self.assertIsNone(_poi_from_osm({'type':'node','id':1,'lat':0,'lon':0,'tags':{}}))
    def test_curated_fallback(self):
        data=curated_fallback('Yogyakarta')
        self.assertGreater(len(data),10)
        self.assertTrue(all(p['lat'] is None for p in data))
    def test_optimizer_reduces_trip(self):
        expensive=[{**p,'price':150000} for p in PLACES]
        cheap=[{**p,'id':'cheap-'+p['id'],'name':'Hemat '+p['name'],'price':0} for p in PLACES]
        base=generate_plan({**CONFIG,'budget':1_600_000},expensive)
        optimized=optimize_budget({**CONFIG,'budget':1_600_000},base['itinerary'],cheap)
        self.assertLess(optimized['summary']['total'],base['summary']['total'])
        self.assertGreater(len(optimized['adjustments']),0)
    def test_optimizer_no_change_when_under_budget(self):
        plan=generate_plan({**CONFIG,'budget':5_000_000},PLACES)
        optimized=optimize_budget({**CONFIG,'budget':5_000_000},plan['itinerary'],PLACES)
        self.assertEqual(optimized['adjustments'],[])
    def test_opening_hours_simple(self):
        self.assertTrue(simple_opening_hours_status('Mo-Su 08:00-17:00','2026-11-10',540,610))
        self.assertFalse(simple_opening_hours_status('Mo-Su 08:00-17:00','2026-11-10',1080,1140))
        self.assertIsNone(simple_opening_hours_status('PH off','2026-11-10',540,610))
    def test_outside_opening_hours_flagged(self):
        places=[{**PLACES[0],'opening_hours':'Mo-Su 07:00-07:30'}]
        r=generate_plan({**CONFIG,'days':1},places)
        self.assertTrue(r['itinerary'][0]['slots'][0].get('opening_warning'))
    def test_mock_overpass(self):
        data={'elements':[{'type':'node','id':100,'lat':-7.7,'lon':110.4,
             'tags':{'name':'Museum Uji','tourism':'museum'}},
            {'type':'node','id':101,'lat':-7.7,'lon':110.42,
             'tags':{'name':'Warung Uji','amenity':'restaurant'}}]}
        with patch('providers._json_request',return_value=data):
            result=discover(-7.79,110.37)
            self.assertEqual(len(result['places']),2)
            self.assertEqual({p['kind'] for p in result['places']},{'wisata','kuliner'})
    def test_mock_nominatim_geocode(self):
        with patch('providers._nominatim_request',return_value=[{'lat':'-7.7','lon':'110.4','display_name':'Banyuwangi, Indonesia'}]):
            result=geocode('Banyuwangi')
            self.assertEqual(result['locations'][0]['name'],'Banyuwangi, Indonesia')
    def test_mock_nominatim_place(self):
        with patch('providers._nominatim_request',return_value=[{'lat':'-7.7','lon':'110.4','display_name':'Pantai Baru, Indonesia',
               'osm_type':'node','osm_id':123,'type':'beach','class':'natural','namedetails':{'name':'Pantai Baru'}}]):
            result=search_place('Pantai Baru',-7.8,110.4)
            self.assertEqual(result['places'][0]['name'],'Pantai Baru')

    def test_room_disabled(self):
        c=clean_config({**CONFIG,'include_hotel':False})
        self.assertEqual(fixed_costs(c)['hotel'],0)
    def test_more_than_8_slots_rejected(self):
        with self.assertRaises(ValueError):recalculate(CONFIG,[{'slots':[{'kind':'wisata','item':PLACES[0]}]*9}])

if __name__=='__main__':unittest.main()
