"""End-to-end HTTP validation of family and travel calendar fields."""
import json
import sys
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
from test_family_schedule import BASE
from test_planner import PLACES

class FamilyAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=3)
    def post(self,path,body):
        req=Request(self.url+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urlopen(req,timeout=5) as res:
            return json.load(res)
    def test_plan_api_cross_year_and_train_fare(self):
        cfg={**BASE,'adults':1,'infants_under_2':1,'children_2_plus':1,'children_age_2':1}
        result=self.post('/api/plan',{'config':cfg,'places':PLACES})
        self.assertEqual(result['summary']['persons'],3)
        self.assertEqual(result['summary']['transport_detail']['pergi']['total'],350000)
        self.assertEqual(result['summary']['transport_detail']['pergi']['gratis_bayi'],1)
        self.assertEqual(result['itinerary'][0]['date'],'2027-01-01')
        self.assertEqual(result['summary']['travel_timeline']['tiba_rumah'],'2027-01-04 00:30')
        self.assertEqual(result['summary']['total'],sum(result['summary']['breakdown'].values()))
    def test_invalid_date_api_http_400(self):
        with self.assertRaises(HTTPError) as e:
            self.post('/api/plan',{'config':{**BASE,'home_arrival_date':'2027-01-02'},'places':[]})
        self.assertEqual(e.exception.code,400)
        self.assertIn('Urutan waktu',e.exception.read().decode())
    def test_recalculate_api_cuts_last_day(self):
        plan=self.post('/api/plan',{'config':BASE,'places':PLACES})
        newcfg={**BASE,'return_time':'08:00','home_arrival_date':'2027-01-03','home_arrival_time':'17:00'}
        revised=self.post('/api/recalculate',{'config':newcfg,'itinerary':plan['itinerary']})
        self.assertEqual(revised['itinerary'][-1]['cost'],0)
        self.assertTrue(all(s['cost']==0 for s in revised['itinerary'][-1]['slots']))
        self.assertLess(revised['summary']['total'],plan['summary']['total'])

if __name__=='__main__':unittest.main()
