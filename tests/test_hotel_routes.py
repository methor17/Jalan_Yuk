"""JalanYuk v2.2: perjalanan antar tempat, hotel, slot waktu, dan budget rute."""
import sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from planner import clean_config,generate_plan,recalculate,routing_key,leg_estimate,clean_place
import providers
from test_family_schedule import BASE,PLACES

CFG={**BASE,'adults':2,'children':0,'children_2_plus':0,'children_age_2':0,
     'base_name':'Hotel Uji Pusat','hotel_area':'Prawirotaman',
     'base_lat':-7.82,'base_lon':110.37,'return_to_base':True,
     'local_travel_mode':'mobil','local_cost_mode':'per_km',
     'local_cost_per_km':3000,'local_base_per_leg':6000,
     'local_vehicle_capacity':5,'include_evening':True,
     'night_start_time':'18:00','daily_hotel_return_time':'21:00'}

class HotelRouteTests(unittest.TestCase):
    def make(self,**kwargs):return generate_plan({**CFG,**kwargs},PLACES)

    def test_first_hop_starts_at_hotel(self):
        p=self.make();leg=p['itinerary'][0]['travel_legs'][0]
        self.assertEqual(leg['from'],'Hotel Uji Pusat')
        self.assertEqual(leg['depart'],'10:00')
        self.assertGreater(leg['minutes'],0)
    def test_last_hop_back_to_hotel(self):
        day=self.make()['itinerary'][0]
        self.assertEqual(day['return_leg']['to'],'Hotel Uji Pusat')
        self.assertEqual(day['return_leg']['kind'],'hotel')
        self.assertTrue(day['hotel_arrival'])
        self.assertLessEqual(day['hotel_arrival'],'21:00')
    def test_hotel_region_kept_for_ui(self):
        self.assertEqual(self.make()['config']['hotel_area'],'Prawirotaman')
    def test_hotel_cost_per_km_applies_to_both_ends(self):
        p=self.make();d=p['itinerary'][0]
        self.assertEqual(d['variable_transport_cost'],sum(l['estimated_cost'] for l in d['travel_legs']))
        self.assertEqual(p['summary']['breakdown']['transport_lokal'],sum(d['variable_transport_cost'] for d in p['itinerary']))
    def test_change_hotel_changes_route_and_cost(self):
        p=self.make();q=recalculate({**CFG,'base_lat':-7.95,'base_lon':110.5},p['itinerary'])
        self.assertNotEqual(p['itinerary'][0]['travel_legs'][0]['km'],q['itinerary'][0]['travel_legs'][0]['km'])
        self.assertNotEqual(p['summary']['breakdown']['transport_lokal'],q['summary']['breakdown']['transport_lokal'])
    def test_time_period_generated_per_slot(self):
        s=self.make()['itinerary'][0]['slots']
        self.assertEqual([x['period'] for x in s],['pagi','siang','sore','malam'])
        self.assertGreaterEqual(s[-1]['start'],'18:00')
    def test_day_specific_return_time_is_enforced(self):
        d=CFG['start_date'];p=self.make(hotel_return_times={d:'15:00'})
        day=p['itinerary'][0]
        self.assertEqual(day['hotel_return_target'],'15:00')
        self.assertTrue(any(s['status']=='tidak_terjadwal' for s in day['slots']))
        if day['hotel_arrival']:self.assertLessEqual(day['hotel_arrival'],'15:00')
    def test_return_time_is_independent_by_date(self):
        d=CFG['start_date'];p=self.make(hotel_return_times={d:'16:00'})
        self.assertEqual(p['itinerary'][0]['hotel_return_target'],'16:00')
        self.assertEqual(p['itinerary'][1]['hotel_return_target'],'21:00')
    def test_earlier_hotel_return_fewer_paid_activities(self):
        early=self.make(daily_hotel_return_time='14:00')
        late=self.make(daily_hotel_return_time='22:00')
        paid=lambda p:sum(s['status']=='scheduled' for d in p['itinerary'] for s in d['slots'])
        self.assertLess(paid(early),paid(late))
        self.assertLessEqual(early['summary']['breakdown']['wisata']+early['summary']['breakdown']['kuliner'],late['summary']['breakdown']['wisata']+late['summary']['breakdown']['kuliner'])
    def test_last_day_transfer_to_hub(self):
        p=self.make(return_hub_name='Stasiun Uji',return_hub_lat=-7.790,return_hub_lon=110.37)
        d=p['itinerary'][-1]
        self.assertEqual(d['return_leg']['kind'],'pulang')
        self.assertEqual(d['return_leg']['to'],'Stasiun Uji')
        self.assertLessEqual(d['return_leg']['arrive'],'16:30')
    def test_last_day_via_hotel_then_hub(self):
        p=self.make(return_hub_name='Stasiun Uji',return_hub_lat=-7.79,return_hub_lon=110.37,last_day_via_hotel=True)
        legkinds=[l.get('kind') for l in p['itinerary'][-1]['travel_legs']]
        self.assertEqual(legkinds[-2:],['hotel','pulang'])
    def test_missing_hotel_uses_city_center_as_explicit_estimate(self):
        p=self.make(base_lat=None,base_lon=None,use_city_center_as_base=True)
        self.assertTrue(any('BUKAN lokasi hotel' in w for w in p['itinerary'][0]['warnings']))
    def test_missing_coordinates_mark_unknown(self):
        missing=[{**x,'lat':None,'lon':None} for x in PLACES]
        p=generate_plan(CFG,missing)
        self.assertGreater(p['summary']['local_routing']['unresolved_legs'],0)
        self.assertTrue(any(l['minutes'] is None for l in p['itinerary'][0]['travel_legs']))
    def test_osrm_cache_is_used_and_sourced(self):
        first=clean_place(PLACES[0]);a={'id':'__base__','name':'Hotel Uji Pusat','lat':CFG['base_lat'],'lon':CFG['base_lon']}
        key=routing_key(a,first)
        c=clean_config({**CFG,'route_cache':{key:{'km':19.5,'minutes':32}}})
        leg=leg_estimate(a,first,c)
        self.assertEqual(leg['source'],'osrm_driving')
        self.assertEqual(leg['minutes'],45)
        self.assertEqual(leg['km'],19.5)
    def test_walk_mode_has_zero_transport_fare(self):
        p=self.make(local_travel_mode='jalan')
        self.assertEqual(p['summary']['breakdown']['transport_lokal'],0)
    def test_day_return_invalid_outside_trip(self):
        with self.assertRaises(ValueError):clean_config({**CFG,'hotel_return_times':{'2030-01-01':'20:00'}})
    def test_invalid_return_time_rejected(self):
        with self.assertRaises(ValueError):clean_config({**CFG,'daily_hotel_return_time':'25:00'})
    def test_invalid_period_time_rejected(self):
        with self.assertRaises(ValueError):clean_config({**CFG,'night_start_time':'nanti malam'})
    def test_invalid_coordinate_nan_rejected(self):
        with self.assertRaises(ValueError):clean_config({**CFG,'base_lat':'NaN'})
    def test_change_destination_moves_timeline(self):
        p=self.make();r=p['itinerary'];first=r[0]['slots'][0]['item']
        updated=[{**day,'slots':[{**slot} for slot in day['slots']]} for day in r]
        updated[0]['slots'][0]['item']={**first,'id':'changed-destination','lat':-7.9,'lon':110.49}
        new=recalculate(CFG,updated)
        self.assertNotEqual(new['itinerary'][0]['travel_legs'][0]['km'],p['itinerary'][0]['travel_legs'][0]['km'])
    def test_hotel_discover_mock(self):
        payload={'elements':[{'type':'node','id':7,'lat':-7.81,'lon':110.35,'tags':{'name':'Hotel Contoh','tourism':'hotel','addr:suburb':'Malioboro'}}]}
        with patch('providers._json_request',return_value=payload):r=providers.discover_hotels(-7.8,110.36)
        self.assertEqual(r['hotels'][0]['name'],'Hotel Contoh')
        self.assertIn('Malioboro',r['hotels'][0]['area'])
    def test_hotel_search_mock(self):
        mock=[{'place_id':5,'lat':'-7.79','lon':'110.37','display_name':'Hotel Y, Jogja','type':'hotel'}]
        with patch('providers._nominatim_request',return_value=mock):r=providers.search_hotels('Hotel Y',-7.8,110.35)
        self.assertEqual(r['hotels'][0]['name'],'Hotel Y')
    def test_hotel_search_bad_input(self):
        with self.assertRaises(ValueError):providers.search_hotels(' ')
    def test_morning_lunch_evening_preference_not_hardcoded_ids(self):
        places=[{'id':'morning','name':'Bukit Sunrise','kind':'wisata','price':0,'lat':-7.8,'lon':110.37,'theme':'Alam','outdoor':True,'duration':70},
                {'id':'day','name':'Museum Siang','kind':'wisata','price':0,'lat':-7.8,'lon':110.37,'theme':'Museum','outdoor':False,'duration':70},
                {'id':'food-lunch','name':'Restoran Siang','kind':'kuliner','price':0,'lat':-7.8,'lon':110.37,'theme':'Kuliner','duration':50},
                {'id':'food-night','name':'Angkringan Malam','kind':'kuliner','price':0,'lat':-7.8,'lon':110.37,'theme':'Kuliner','duration':50}]
        c={**CFG,'days':1,'start_date':'2027-01-01','return_date':'2027-01-01','return_time':'23:59','home_arrival_date':'2027-01-02','home_arrival_time':'04:00','return_buffer_minutes':0}
        p=generate_plan(c,places)
        self.assertEqual(p['itinerary'][0]['slots'][0]['item']['id'],'morning')
        self.assertEqual(p['itinerary'][0]['slots'][1]['item']['id'],'food-lunch')
        self.assertEqual(p['itinerary'][0]['slots'][-1]['item']['id'],'food-night')
    def test_recalculate_conserves_period(self):
        p=self.make();q=recalculate(CFG,p['itinerary'],reorder=True)
        self.assertEqual([x['period'] for x in p['itinerary'][0]['slots']],[x['period'] for x in q['itinerary'][0]['slots']])

if __name__=='__main__':unittest.main()
