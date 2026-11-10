import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request,urlopen
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,storage,providers
from test_planner import CONFIG,PLACES

class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        storage.DB=Path(cls.tmp.name)/'test.db'
        cls.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.url='http://127.0.0.1:'+str(cls.server.server_port)
        cls.key='1'*64

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=4);cls.tmp.cleanup()

    def call(self,endpoint,payload=None,method=None,key=None):
        body=json.dumps(payload).encode() if payload is not None else None
        req=Request(self.url+endpoint,data=body,method=method or ('POST' if body else 'GET'),
                    headers={'Content-Type':'application/json','X-Client-Key':key or self.key})
        try:
            with urlopen(req,timeout=5) as r:return r.status,json.loads(r.read())
        except __import__('urllib').error.HTTPError as e:
            return e.code,json.loads(e.read())

    def test_health(self):self.assertEqual(self.call('/api/health')[0],200)
    def test_static(self):
        with urlopen(self.url+'/static/app.js') as r:self.assertIn(b'JalanYuk 2.5',r.read())
    def test_traversal_blocked(self):
        self.assertNotEqual(self.call('/static/..%2fapp.py')[0],200)
    def test_curated(self):self.assertGreater(len(self.call('/api/curated?city=Bandung')[1]['places']),5)
    def test_plan(self):
        code,p=self.call('/api/plan',{'config':CONFIG,'places':PLACES})
        self.assertEqual(code,200)
        self.assertEqual(p['config']['city'],'Yogyakarta')
    def test_recalc(self):
        _,p=self.call('/api/plan',{'config':CONFIG,'places':PLACES})
        code,q=self.call('/api/recalculate',{'config':CONFIG,'itinerary':p['itinerary']})
        self.assertEqual(code,200)
        self.assertEqual(q['summary']['total'],p['summary']['total'])
    def test_invalid_budget(self):
        code,res=self.call('/api/plan',{'config':{**CONFIG,'budget':-1},'places':PLACES})
        self.assertEqual(code,400)
    def test_save_and_list(self):
        _,plan=self.call('/api/plan',{'config':CONFIG,'places':PLACES})
        code,saved=self.call('/api/trips',{'plan':plan,'title':'Liburan uji'})
        self.assertEqual(code,200)
        _,listed=self.call('/api/trips')
        self.assertTrue(any(t['id']==saved['id'] for t in listed['trips']))
        _,fetched=self.call('/api/trips/'+saved['id'])
        self.assertEqual(fetched['plan']['summary']['total'],plan['summary']['total'])
    def test_cannot_read_other_owner(self):
        _,plan=self.call('/api/plan',{'config':CONFIG,'places':PLACES})
        _,t=self.call('/api/trips',{'plan':plan})
        code,_=self.call('/api/trips/'+t['id'],key='2'*64)
        self.assertEqual(code,404)
    def test_share_suggest_vote_sync(self):
        _,p=self.call('/api/plan',{'config':CONFIG,'places':PLACES})
        code,s=self.call('/api/shares',{'plan':p,'title':'Uji bersama'})
        self.assertEqual(code,200)
        token=s['id']
        _,public=self.call('/api/shares/'+token,key='2'*64)
        self.assertFalse(public['owner'])
        _,proposal=self.call('/api/shares/'+token+'/suggest',{'name':'Museum Baru','kind':'wisata','price':9000,'day':1,'comment':'Seru'},key='2'*64)
        _,v=self.call('/api/shares/'+token+'/vote',{'id':proposal['id']},key='3'*64)
        self.assertTrue(v['voted'])
        _,public=self.call('/api/shares/'+token,key='2'*64)
        self.assertEqual(public['suggestions'][0]['votes'],1)
        code,_=self.call('/api/shares/'+token+'/sync',{'plan':p,'title':'Uji bersama'},key='2'*64)
        self.assertEqual(code,403)
        code,_=self.call('/api/shares/'+token+'/sync',{'plan':p,'title':'Uji bersama'},key=self.key)
        self.assertEqual(code,200)
    def test_optimize_endpoint(self):
        pricey=[{**p,'price':150000} for p in PLACES]
        cheap=[{**p,'id':'save-'+p['id'],'price':0} for p in PLACES]
        _,plan=self.call('/api/plan',{'config':{**CONFIG,'budget':1_600_000},'places':pricey})
        code,result=self.call('/api/optimize',{'config':{**CONFIG,'budget':1_600_000},
                          'itinerary':plan['itinerary'],'places':cheap})
        self.assertEqual(code,200)
        self.assertLess(result['summary']['total'],plan['summary']['total'])
    def test_saved_catalog(self):
        _,plan=self.call('/api/plan',{'config':CONFIG,'places':PLACES})
        _,saved=self.call('/api/trips',{'plan':plan,'places':PLACES,'title':'Katalog tersimpan'})
        _,full=self.call('/api/trips/'+saved['id'])
        self.assertEqual(len(full['plan']['_catalog']),len(PLACES))

    def test_mock_geocode(self):
        with patch.object(providers,'geocode',return_value={'locations':[{'name':'Solo','lat':-7.57,'lon':110.8}], 'source':'mock'}):
            code,r=self.call('/api/geocode?q=Solo')
            self.assertEqual(code,200)
            self.assertEqual(r['locations'][0]['name'],'Solo')
    def test_mock_discover(self):
        with patch.object(providers,'discover',return_value={'places':PLACES,'source':'mock'}):
            code,r=self.call('/api/discover?lat=-7.7&lon=110.3')
            self.assertEqual(code,200)
            self.assertEqual(len(r['places']),len(PLACES))

if __name__=='__main__':unittest.main()
