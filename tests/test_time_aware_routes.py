"""JalanYuk v2.5 — date-specific route caching without Google Routes API."""
import json, os, sys, time, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import route_service, providers, app
from planner import generate_plan, clean_config, timed_routing_key, leg_estimate, start_point, clean_place
from test_hotel_routes import CFG, PLACES

class RouteByDateTests(unittest.TestCase):
    def base(self,**kwargs):return {**CFG,'routing_provider':'multi','local_utc_offset':7,**kwargs}
    def mocked_route(self,start,end,iso,mode,provider,utc_offset):
        delta=(int(iso[8:10])-int(self.base()['start_date'][-2:]))%3
        return {'km':9+delta*4,'minutes':15+delta*19,
                'source':'multi_source_max','fetched_at':int(time.time()),
                'samples':[{'source':'osrm_driving','km':9+delta*4,'minutes':15+delta*19}],
                'selected_source':'osrm_driving'}
    def test_location_date_hour_cache_key(self):
        a={'lat':-7.8,'lon':110.37};b={'lat':-7.9,'lon':110.44}
        keys={timed_routing_key(a,b,'mobil',d,m,p) for d,m,p in
              [('2027-01-01',540,'multi'),('2027-01-02',540,'multi'),
               ('2027-01-01',780,'multi'),('2027-01-01',540,'osrm')]}
        self.assertEqual(len(keys),4)
    def test_cached_multi_eta_applied_with_one_user_margin(self):
        place=clean_place(PLACES[0]);origin=start_point(clean_config(self.base()))
        cfg=self.base(route_safety_minutes=10)
        key=timed_routing_key(origin,place,'mobil',cfg['start_date'],600,'multi')
        cfg=clean_config(self.base(route_safety_minutes=10,route_cache={key:{'minutes':28,'km':13,'source':'multi_source_max','fetched_at':int(time.time())}}))
        leg=leg_estimate(origin,place,cfg,cfg['start_date'],600)
        self.assertEqual(leg['minutes'],38)
        self.assertEqual(leg['source'],'multi_source_max')
    def test_legacy_google_config_migrated_and_google_cache_dropped(self):
        cfg=self.base(routing_provider='google')
        cfg=clean_config(cfg)
        self.assertEqual(cfg['routing_provider'],'multi')
        place=clean_place(PLACES[0]);origin=start_point(cfg)
        key=timed_routing_key(origin,place,'mobil',cfg['start_date'],600,'multi')
        corrupt={key:{'minutes':30,'km':13,'source':'multi_source_max','fetched_at':int(time.time()),'has_google':True}}
        self.assertNotIn(key,clean_config(self.base(route_cache=corrupt))['route_cache'])
    def test_refresh_multiple_days_updates_schedule_and_cost(self):
        cfg=self.base();plan=generate_plan(cfg,PLACES)
        r=route_service.refresh(cfg,plan['itinerary'],route_lookup=self.mocked_route)
        days=r['plan']['itinerary']
        self.assertGreater(r['routing']['updated'],0)
        self.assertTrue(any(l['source']=='multi_source_max' for d in days for l in d['travel_legs']))
        self.assertNotEqual(plan['summary']['breakdown']['transport_lokal'],r['plan']['summary']['breakdown']['transport_lokal'])
        self.assertGreater(len({l['minutes'] for d in days for l in d['travel_legs']}),1)
    def test_refresh_only_selected_date(self):
        cfg=self.base();plan=generate_plan(cfg,PLACES)
        r=route_service.refresh(cfg,plan['itinerary'],day_index=1,route_lookup=self.mocked_route)
        self.assertTrue(r['plan']['config']['route_cache'])
        self.assertTrue(all(k.startswith('timed:multi:'+plan['itinerary'][1]['date']) for k in r['plan']['config']['route_cache']))
    def test_missing_coords_flagged(self):
        cfg=self.base();places=[{**p,'lat':None,'lon':None} for p in PLACES]
        plan=generate_plan(cfg,places)
        r=route_service.refresh(cfg,plan['itinerary'],route_lookup=self.mocked_route)
        self.assertEqual(r['routing']['updated'],0)
        self.assertGreater(r['routing']['unresolved'],0)
    def test_bad_day_rejected(self):
        cfg=self.base();plan=generate_plan(cfg,PLACES)
        with self.assertRaises(ValueError):route_service.refresh(cfg,plan['itinerary'],day_index=99,route_lookup=self.mocked_route)
    def test_google_environment_has_no_effect_on_provider(self):
        a={'lat':-7.81,'lon':110.35};b={'lat':-7.82,'lon':110.47}
        with patch.dict(os.environ,{'GOOGLE_MAPS_API_KEY':'should-be-ignored','OPENROUTESERVICE_API_KEY':''}),\
             patch.object(providers,'_osrm_comparison',return_value={'km':12,'minutes':35,'source':'osrm_driving'}),\
             patch('urllib.request.urlopen',side_effect=AssertionError('No Google network allowed')):
            # OSRM mock returns without any network; no Google code path remains.
            result=providers.route_segment(a,b,'2027-01-01T08:30:00','mobil','multi',7)
        self.assertEqual(result['source'],'multi_source_max')
        self.assertEqual(len(result['samples']),1)
        self.assertEqual(result['minutes'],49)
    def test_manual_google_provider_rejected(self):
        a={'lat':-7.81,'lon':110.35};b={'lat':-7.82,'lon':110.47}
        with self.assertRaises(ValueError):providers.route_segment(a,b,'2027-01-01T08:30:00','mobil','google',7)

if __name__=='__main__':unittest.main()

class HTTPRouteRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import threading
        from urllib.request import urlopen
        cls.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        cls.worker=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.worker.start()
        cls.uri='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.worker.join(3)
    def post(self,path,body):
        from urllib.request import Request,urlopen
        req=Request(self.uri+path,data=json.dumps(body).encode(),method='POST',headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=8) as r:return r.status,json.loads(r.read())
    def test_provider_status_shows_google_disabled(self):
        from urllib.request import urlopen
        with urlopen(self.uri+'/api/routing/status',timeout=5) as f:data=json.loads(f.read())
        self.assertFalse(data['google_routes_enabled'])
        self.assertNotIn('google_configured',data)
    def test_refresh_api_updates_schedule(self):
        cfg={**CFG,'routing_provider':'osrm'};plan=generate_plan(cfg,PLACES)
        with patch.object(providers,'route_segment',return_value={'km':7.2,'minutes':17,'source':'osrm_driving','fetched_at':int(time.time())}):
            status,r=self.post('/api/routes/refresh',{'config':cfg,'itinerary':plan['itinerary'],'day':0})
        self.assertEqual(status,200)
        self.assertGreater(r['routing']['updated'],0)
        self.assertTrue(any(l['source']=='osrm_driving' for l in r['plan']['itinerary'][0]['travel_legs']))
    def test_invalid_day_rejected(self):
        from urllib.error import HTTPError
        cfg={**CFG,'routing_provider':'osrm'};plan=generate_plan(cfg,PLACES)
        with self.assertRaises(HTTPError) as e:self.post('/api/routes/refresh',{'config':cfg,'itinerary':plan['itinerary'],'day':99})
        self.assertEqual(e.exception.code,400)
