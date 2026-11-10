"""JalanYuk v2.4: deterministic multi-source ETA / schedule, no live API needed."""
import os, sys, time, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import providers, route_service
from planner import clean_config, clean_place, start_point, leg_estimate, timed_routing_key, generate_plan, recalculate
from test_hotel_routes import CFG, PLACES

A={'lat':-7.82,'lon':110.37};B={'lat':-7.89,'lon':110.41}

class MultiSourceTests(unittest.TestCase):
    def ors(self,*args,**kwargs):
        return {'km':14,'minutes':47,'source':'openrouteservice','fetched_at':int(time.time())}
    def osrm(self,*args,**kwargs):
        return {'km':13,'minutes':38,'source':'osrm_driving','fetched_at':int(time.time())}
    def test_multi_selects_longest_and_conservative(self):
        with patch.dict(os.environ,{'OPENROUTESERVICE_API_KEY':'test'}),\
             patch.object(providers,'openrouteservice_segment',side_effect=self.ors),\
             patch.object(providers,'_osrm_comparison',side_effect=self.osrm):
            result=providers.compare_route_sources(A,B,'2027-01-01T08:00:00','mobil',7)
        self.assertEqual(result['source'],'multi_source_max')
        self.assertEqual(result['selected_source'],'openrouteservice')
        self.assertEqual(result['base_minutes'],47)
        self.assertEqual(result['minutes'],64) # ceil(47*1.25 + 5)
        self.assertEqual(len(result['samples']),2)
    def test_without_api_keys_osrm_plus_conservative(self):
        with patch.dict(os.environ,{'OPENROUTESERVICE_API_KEY':''}),\
             patch.object(providers,'_osrm_comparison',side_effect=self.osrm):
            result=providers.compare_route_sources(A,B,'2027-01-01T08:00:00','mobil',7)
        self.assertEqual(len(result['samples']),1)
        self.assertEqual(result['minutes'],53) # ceil(38*1.25 + 5)
    def test_all_services_fail_mark_estimate(self):
        with patch.dict(os.environ,{'OPENROUTESERVICE_API_KEY':''}),\
             patch.object(providers,'_osrm_comparison',side_effect=ValueError('offline')):
            result=providers.compare_route_sources(A,B,'2027-01-01T08:00:00','mobil',7)
        self.assertEqual(result['confidence'],'perkiraan_tanpa_rute')
        self.assertEqual(result['samples'],[])
        self.assertGreater(result['minutes'],0)
    def test_safety_margin_added_once_after_refresh(self):
        cfg={**CFG,'routing_provider':'multi','route_safety_minutes':10}
        origin=start_point(clean_config(cfg)); place=clean_place(PLACES[0]);date=cfg['start_date']
        k=timed_routing_key(origin,place,'mobil',date,600,'multi')
        cache={k:{'km':13,'minutes':64,'source':'multi_source_max','fetched_at':int(time.time()),
                  'samples':[{'source':'osrm_driving','minutes':38,'km':13}],
                  'selected_source':'osrm_driving'}}
        used=clean_config({**cfg,'route_cache':cache})
        leg=leg_estimate(origin,place,used,date,600)
        self.assertEqual(leg['minutes'],74)
        self.assertEqual(leg['safety_minutes'],10)
        self.assertEqual(leg['samples'][0]['minutes'],38)
        again=leg_estimate(origin,place,used,date,600)
        self.assertEqual(again['minutes'],74)
    def test_replan_after_longer_etas_shifts_visits(self):
        cfg={**CFG,'routing_provider':'multi','route_safety_minutes':10,'daily_hotel_return_time':'23:00'}
        first=generate_plan(cfg,PLACES)
        def slow(start,end,iso,mode,provider,offset):
            return {'km':7.5,'minutes':48,'source':'multi_source_max','fetched_at':int(time.time()),
                    'selected_source':'osrm_driving','samples':[{'source':'osrm_driving','minutes':35,'km':7.5}],
                    'confidence':'sumber+rencana_cadangan'}
        refreshed=route_service.refresh(cfg,first['itinerary'],route_lookup=slow)['plan']
        self.assertGreaterEqual(refreshed['summary']['local_routing']['total_minutes'],first['summary']['local_routing']['total_minutes'])
        self.assertTrue(any(l['source']=='multi_source_max' for day in refreshed['itinerary'] for l in day['travel_legs']))
        self.assertNotEqual(refreshed['summary']['breakdown']['transport_lokal'],first['summary']['breakdown']['transport_lokal'])
        self.assertTrue(any(s['start']!=b['start'] for d1,d2 in zip(first['itinerary'],refreshed['itinerary']) for s,b in zip(d1['slots'],d2['slots'])))
    def test_missing_coordinate_shows_unknown_and_does_not_call_service(self):
        places=[{**x,'lat':None,'lon':None} for x in PLACES]
        cfg={**CFG,'routing_provider':'multi'}
        first=generate_plan(cfg,places)
        with patch.object(providers,'route_segment',side_effect=AssertionError('must not call')):
            result=route_service.refresh(cfg,first['itinerary'])
        self.assertEqual(result['routing']['updated'],0)
        self.assertGreater(result['routing']['unresolved'],0)
    def test_legacy_google_comparison_removed_when_loading_saved_plan(self):
        from app import Handler
        cfg={**CFG,'routing_provider':'multi'}
        first=generate_plan(cfg,PLACES)
        cache={'timed:multi:2027-01-01:10:mobil:driving:-7.82000,110.37000>-7.89000,110.41000':
               {'km':13,'minutes':62,'source':'multi_source_max','has_google':True,'fetched_at':int(time.time()),
                'samples':[{'source':'google_routes','minutes':45,'km':12}]}}
        saved=Handler.plan_from_payload(None,{'config':{**cfg,'route_cache':cache},'itinerary':first['itinerary']})
        self.assertFalse(saved['config']['route_cache'])

if __name__=='__main__':unittest.main()
