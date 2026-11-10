"""JalanYuk 2.5 — HTTP API standar Python, zero pip dependencies.
Jalankan: python app.py  lalu buka http://localhost:8000
"""
from __future__ import annotations
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from catalog import city_list
from planner import generate_plan, recalculate, clean_config, clean_place, optimize_budget
import providers
import storage
import route_service

ROOT=Path(__file__).resolve().parent
# No-dependency .env reader for allow-listed backend keys only.
# Existing OS environment values always override .env; no secrets in JS/API.
_env_file=ROOT/'.env'
if _env_file.is_file():
    keys={'OPENROUTESERVICE_API_KEY'}
    for line in _env_file.read_text(encoding='utf-8').splitlines():
        if '=' not in line or line.lstrip().startswith('#'):continue
        name,value=line.split('=',1)
        name=name.strip()
        if name in keys and not os.environ.get(name):
            value=value.strip().strip('"').strip("'")
            if value:os.environ[name]=value
STATIC=ROOT/'static'
MIME={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8',
      '.js':'text/javascript; charset=utf-8','.svg':'image/svg+xml',
      '.json':'application/json; charset=utf-8','.webmanifest':'application/manifest+json; charset=utf-8',
      '.png':'image/png','.ico':'image/x-icon'}

class Handler(BaseHTTPRequestHandler):
    server_version='JalanYuk/2.5'

    def respond(self,status,body,mime='application/json; charset=utf-8'):
        if mime.startswith('application/json'):
            body=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode()
        self.send_response(status)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','strict-origin-when-cross-origin')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Cache-Control','no-store' if mime.startswith('application/json') else 'public, max-age=300')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):
            pass

    def query(self):
        return {k: v[0] for k,v in parse_qs(urlsplit(self.path).query,keep_blank_values=True).items()}

    def owner(self):
        return storage.identity(self.headers.get('X-Client-Key',''))

    def read_body(self):
        try:
            length=int(self.headers.get('Content-Length','0'))
        except ValueError:
            raise ValueError('Content-Length tidak valid.') from None
        if not 2<=length<=1_000_000:
            raise ValueError('Payload harus 2 byte sampai 1 MB.')
        try:
            result=json.loads(self.rfile.read(length))
        except (ValueError,UnicodeDecodeError):
            raise ValueError('JSON tidak valid.') from None
        if not isinstance(result,dict):
            raise ValueError('Payload wajib berupa objek.')
        return result

    def plan_from_payload(self,payload):
        cfg=payload.get('config',{})
        # Sanitize old route caches (Google-derived entries are discarded by clean_config).
        if 'itinerary' in payload:
            return recalculate(cfg,payload['itinerary'],payload.get('weather'))
        return generate_plan(cfg,payload.get('places',[]),payload.get('weather'))

    def do_GET(self):
        try:
            self._get()
        except ValueError as exc:
            self.respond(400,{'error':str(exc)})
        except Exception:
            self.respond(500,{'error':'Ada gangguan server. Silakan coba lagi.'})

    def _get(self):
        path=urlsplit(self.path).path
        qs=self.query()
        if path=='/api/health':
            return self.respond(200,{'status':'ok','service':'jalanyuk','version':'2.5'})
        if path=='/api/routing/status':
            return self.respond(200,{'ors_configured':bool(os.getenv('OPENROUTESERVICE_API_KEY','').strip()),
                                     'google_routes_enabled':False,
                                     'default':'OSRM + estimasi waktu konservatif; OpenRouteService opsional',
                                     'notice':'Tanpa Google Routes API dan tanpa prediksi lalu lintas live.'})
        if path=='/api/cities':
            return self.respond(200,{'cities':city_list()})
        if path=='/api/geocode':
            return self.respond(200,providers.geocode(qs.get('q','')))
        if path=='/api/discover':
            return self.respond(200,providers.discover(qs.get('lat'),qs.get('lon'),qs.get('radius',10000)))
        if path=='/api/places/search':
            return self.respond(200,providers.search_place(qs.get('q',''),qs.get('lat') or None,qs.get('lon') or None))
        if path=='/api/hotels':
            return self.respond(200,providers.discover_hotels(qs.get('lat'),qs.get('lon'),qs.get('radius',9000)))
        if path=='/api/hotels/search':
            return self.respond(200,providers.search_hotels(qs.get('q',''),qs.get('lat') or None,qs.get('lon') or None))
        if path=='/api/curated':
            return self.respond(200,{'places':providers.curated_fallback(qs.get('city','')),
                                      'source':'Katalog ilustrasi JalanYuk (offline)'})
        if path=='/api/weather':
            return self.respond(200,providers.forecast(float(qs.get('lat')),float(qs.get('lon')),
                                                       qs.get('start_date',''),int(qs.get('days',3))))
        if path=='/api/trips':
            return self.respond(200,{'trips':storage.list_trips(self.owner())})
        match=re.fullmatch(r'/api/trips/([A-Za-z0-9_-]+)',path)
        if match:
            trip=storage.get_trip(self.owner(),match.group(1))
            return self.respond(200,trip) if trip else self.respond(404,{'error':'Rencana tidak ditemukan.'})
        match=re.fullmatch(r'/api/shares/([A-Za-z0-9_-]+)',path)
        if match:
            who=None
            try: who=self.owner()
            except ValueError: pass
            shared=storage.get_share(match.group(1),who)
            return self.respond(200,shared) if shared else self.respond(404,{'error':'Link berbagi tidak tersedia atau kedaluwarsa.'})
        if path in ('/','/index.html') or re.fullmatch('/s/[A-Za-z0-9_-]{16,80}',path):
            target=STATIC/'index.html'
        elif path.startswith('/static/'):
            target=(STATIC/path[len('/static/'):]).resolve()
            if not target.is_relative_to(STATIC.resolve()):
                return self.respond(403,{'error':'Tidak diizinkan.'})
        elif path in ('/sw.js','/manifest.webmanifest'):
            target=STATIC/path.lstrip('/')
        else:
            return self.respond(404,{'error':'Endpoint tidak ditemukan.'})
        if not target.is_file():
            return self.respond(404,{'error':'Berkas tidak ditemukan.'})
        self.respond(200,target.read_bytes(),MIME.get(target.suffix,'application/octet-stream'))

    def do_POST(self):
        try:
            self._post()
        except ValueError as exc:
            self.respond(400,{'error':str(exc)})
        except Exception:
            self.respond(500,{'error':'Ada gangguan server. Silakan coba lagi.'})

    def _post(self):
        path=urlsplit(self.path).path
        payload=self.read_body()
        if path=='/api/plan':
            return self.respond(200,generate_plan(payload.get('config',{}),payload.get('places',[]),payload.get('weather')))
        if path=='/api/recalculate':
            return self.respond(200,recalculate(payload.get('config',{}),payload.get('itinerary',[]),
                                                payload.get('weather'),payload.get('reorder') is True))
        if path=='/api/optimize':
            return self.respond(200,optimize_budget(payload.get('config',{}),payload.get('itinerary',[]),
                                                    payload.get('places',[]),payload.get('weather')))
        if path=='/api/routes/refresh':
            result=route_service.refresh(payload.get('config',{}),payload.get('itinerary',[]),
                                         payload.get('weather'),payload.get('day'))
            return self.respond(200,result)
        if path=='/api/route':
            return self.respond(200,providers.route(payload.get('coords',[])))
        if path=='/api/trips':
            plan=self.plan_from_payload(payload.get('plan',{}))
            places=payload.get('places', [])
            if not isinstance(places,list) or len(places)>500:
                raise ValueError('Katalog perjalanan maksimal 500 tempat.')
            plan['_catalog']=[clean_place(p) for p in places]
            saved=storage.save_trip(self.owner(),plan,payload.get('title') or plan['config']['city'],payload.get('id'))
            return self.respond(200,saved)
        if path=='/api/shares':
            plan=self.plan_from_payload(payload.get('plan',{}))
            return self.respond(200,storage.create_share(self.owner(),plan,payload.get('title')))
        match=re.fullmatch(r'/api/shares/([A-Za-z0-9_-]+)/sync',path)
        if match:
            plan=self.plan_from_payload(payload.get('plan',{}))
            ok=storage.sync_share(match.group(1),self.owner(),plan,payload.get('title'))
            return self.respond(200,{'ok':True}) if ok else self.respond(403,{'error':'Hanya pemilik link dapat memperbarui.'})
        match=re.fullmatch(r'/api/shares/([A-Za-z0-9_-]+)/suggest',path)
        if match:
            creator=self.owner()
            suggestion_id=storage.add_suggestion(match.group(1),creator,payload.get('kind'),payload.get('name'),
                                                 payload.get('price'),payload.get('day'),payload.get('comment',''))
            return self.respond(200,{'id':suggestion_id})
        match=re.fullmatch(r'/api/shares/([A-Za-z0-9_-]+)/vote',path)
        if match:
            sid=payload.get('id')
            if not isinstance(sid,int):
                raise ValueError('ID usulan tidak valid.')
            voted=storage.toggle_vote(match.group(1),self.owner(),sid)
            return self.respond(200,{'voted':voted})
        return self.respond(404,{'error':'Endpoint tidak ditemukan.'})

    def do_DELETE(self):
        try:
            path=urlsplit(self.path).path
            match=re.fullmatch(r'/api/trips/([A-Za-z0-9_-]+)',path)
            if not match:
                return self.respond(404,{'error':'Endpoint tidak ditemukan.'})
            return self.respond(200,{'deleted':storage.delete_trip(self.owner(),match.group(1))})
        except ValueError as exc:
            self.respond(400,{'error':str(exc)})


def main():
    storage.connect().close()
    host=os.getenv('HOST','127.0.0.1')
    port=int(os.getenv('PORT',8000))
    server=ThreadingHTTPServer((host,port),Handler)
    print(f'JalanYuk v2.4 berjalan di http://localhost:{port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: print('\nServer dihentikan.')
    finally: server.server_close()

if __name__=='__main__':
    main()
