"""Tes browser opsional, perlu: pip install playwright + browser Chromium.
Dapat dijalankan: python tests/browser_smoke.py
"""
import sys,threading,time,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from unittest.mock import patch
import app,providers,storage
from test_planner import PLACES,CONFIG
from playwright.sync_api import sync_playwright

with tempfile.TemporaryDirectory() as tmp:
    storage.DB=Path(tmp)/'browser-test.db'
    httpd=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
    server=threading.Thread(target=httpd.serve_forever,daemon=True)
    source_places=[{**p,'source':'OpenStreetMap','price_status':'ilustrasi','wheelchair':'unknown','opening_hours':''} for p in PLACES]
    with patch.object(providers,'geocode',return_value={'locations':[{'name':'Yogyakarta, Indonesia','lat':-7.7956,'lon':110.3695}], 'source':'mock','fallback':False}), \
         patch.object(providers,'discover',return_value={'places':source_places,'source':'OpenStreetMap (mock)','notice':''}), \
         patch.object(providers,'forecast',return_value={'days':[],'source':'Open-Meteo'}), \
         patch.object(providers,'route',return_value={'distance_km':12,'duration_minutes':30,'geometry':None,'source':'mock'}):
        server.start()
        with sync_playwright() as pl:
            browser=pl.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            for viewport,label in [({'width':1440,'height':1050},'desktop'),({'width':390,'height':844},'mobile')]:
                page=browser.new_page(viewport=viewport,accept_downloads=True)
                errors=[]
                page.on('pageerror', lambda e:errors.append(str(e)))
                page.goto('http://127.0.0.1:'+str(httpd.server_port),wait_until='domcontentloaded',timeout=20000)
                page.screenshot(path='/mnt/data/jalanyuk-python-v2-'+label+'-initial.png',full_page=True)
                page.locator('#destination').fill('Yogyakarta')
                page.locator('#generateBtn').click()
                page.locator('#planView').wait_for(state='visible',timeout=15000)
                assert 'Jelajahi Yogyakarta' in page.locator('#planTitle').inner_text()
                old=page.locator('#metricTotal').inner_text()
                assert 'Rp' in old
                page.locator('#dayContent button[data-op="price"]').first.click()
                page.locator('#newPrice').fill('100000')
                page.locator('#priceForm button[type="submit"]').click()
                page.wait_for_timeout(300)
                new=page.locator('#metricTotal').inner_text()
                assert old!=new,(old,new)
                page.locator('#dayContent button[data-op="change"]').first.click()
                page.locator('#placeDialog').wait_for(state='visible')
                page.locator('#placeResults button[data-index]').last.click()
                page.wait_for_timeout(300)
                page.locator('#addDayPlace').click()
                page.locator('#manualDetails summary').click()
                page.locator('#manualName').fill('Wisata buatan saya')
                page.locator('#manualPrice').fill('5000')
                page.locator('#manualForm button[type="submit"]').click()
                page.wait_for_timeout(300)
                assert 'Wisata buatan saya' in page.locator('#dayContent').inner_text()
                page.locator('#saveBtn').click()
                page.wait_for_timeout(350)
                page.locator('#tripsBtn').click()
                assert page.locator('#savedTripList .saved-trip').count()>=1
                page.locator('#tripsDialog [data-close]').click()
                page.locator('#shareBtn').click()
                page.locator('#shareDialog').wait_for(state='visible')
                assert '/s/' in page.locator('#shareLink').input_value()
                page.locator('#suggestName').fill('Curug Baru')
                page.locator('#suggestPrice').fill('12000')
                page.locator('#suggestForm button[type="submit"]').click()
                page.wait_for_timeout(250)
                assert 'Curug Baru' in page.locator('#sharedSuggestions').inner_text()
                page.locator('#shareDialog [data-close]').click()
                page.screenshot(path='/mnt/data/jalanyuk-python-v2-'+label+'-result.png',full_page=True)
                print(label,'OK',{'old':old,'new':new,'screenshots':True,'page_errors':errors})
                assert not errors,errors
                if label=='mobile':
                    scroll_width=page.evaluate('document.documentElement.scrollWidth')
                    assert scroll_width<=viewport['width']+3,(scroll_width,viewport['width'])
                page.close()
            browser.close()
        httpd.shutdown();httpd.server_close();server.join(timeout=3)
