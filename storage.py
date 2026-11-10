"""SQLite untuk simpan multi-rencana dan kolaborasi ringan via link.
Tanpa akun: hak akses berbasis kunci acak 32 byte tersimpan di browser.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager

ROOT=Path(__file__).resolve().parent
DB=Path(os.getenv('JALANYUK_DB', str(ROOT/'data'/'jalanyuk.db')))


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con=sqlite3.connect(DB,timeout=10)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA busy_timeout=10000')
    con.executescript('''
    CREATE TABLE IF NOT EXISTS trips(
      id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL,
      payload TEXT NOT NULL, updated TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS ix_trips_owner ON trips(owner);
    CREATE TABLE IF NOT EXISTS shares(
      id TEXT PRIMARY KEY, owner TEXT NOT NULL, payload TEXT NOT NULL,
      title TEXT NOT NULL, updated TEXT NOT NULL, expires TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS suggestions(
      id INTEGER PRIMARY KEY AUTOINCREMENT, share_id TEXT NOT NULL,
      creator TEXT NOT NULL, kind TEXT NOT NULL, name TEXT NOT NULL,
      price INTEGER NOT NULL, day INTEGER NOT NULL, comment TEXT NOT NULL,
      created TEXT NOT NULL, FOREIGN KEY(share_id) REFERENCES shares(id));
    CREATE TABLE IF NOT EXISTS votes(
      suggestion_id INTEGER NOT NULL, voter TEXT NOT NULL,
      PRIMARY KEY(suggestion_id,voter));
    ''')
    return con


@contextmanager
def db():
    conn=connect()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def now():
    return datetime.now(timezone.utc).isoformat()


def identity(key):
    if not isinstance(key,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{30,128}',key):
        raise ValueError('Identitas browser tidak valid. Muat ulang halaman.')
    return hashlib.sha256(key.encode()).hexdigest()


def id_safe(value):
    if not isinstance(value,str) or not re.fullmatch('[a-zA-Z0-9_-]{16,80}',value):
        raise ValueError('ID tidak valid.')
    return value


def _blob(plan):
    blob=json.dumps(plan,ensure_ascii=False,separators=(',',':'))
    if len(blob.encode())>850_000:
        raise ValueError('Ukuran rencana melebihi 850 KB.')
    return blob


def save_trip(owner,plan,title,id=None):
    title=str(title or 'Liburan baru')[:100]
    id=id_safe(id) if id else secrets.token_urlsafe(16)
    with db() as con:
        exists=con.execute('SELECT owner FROM trips WHERE id=?',(id,)).fetchone()
        if exists and exists['owner']!=owner:
            raise ValueError('Tidak memiliki akses mengubah rencana ini.')
        if not exists:
            count=con.execute('SELECT count(*) FROM trips WHERE owner=?',(owner,)).fetchone()[0]
            if count>=80:
                raise ValueError('Batas 80 rencana tersimpan.')
        con.execute('INSERT INTO trips(id,owner,title,payload,updated) VALUES(?,?,?,?,?) '
                    'ON CONFLICT(id) DO UPDATE SET title=excluded.title,payload=excluded.payload,updated=excluded.updated',
                    (id,owner,title,_blob(plan),now()))
    return {'id':id,'title':title}


def list_trips(owner):
    with db() as con:
        return [dict(row) for row in con.execute('SELECT id,title,updated FROM trips WHERE owner=? ORDER BY updated DESC LIMIT 80',(owner,))]


def get_trip(owner,id):
    id_safe(id)
    with db() as con:
        row=con.execute('SELECT id,title,payload,updated FROM trips WHERE owner=? AND id=?',(owner,id)).fetchone()
    return {'id':row['id'],'title':row['title'],'plan':json.loads(row['payload']),'updated':row['updated']} if row else None


def delete_trip(owner,id):
    id_safe(id)
    with db() as con:
        count=con.execute('DELETE FROM trips WHERE owner=? AND id=?',(owner,id)).rowcount
    return bool(count)


def create_share(owner,plan,title):
    token=secrets.token_urlsafe(22)
    expires=(datetime.now(timezone.utc)+timedelta(days=30)).isoformat()
    with db() as con:
        con.execute('INSERT INTO shares(id,owner,payload,title,updated,expires) VALUES(?,?,?,?,?,?)',
                    (token,owner,_blob(plan),str(title or 'Rencana liburan')[:100],now(),expires))
    return {'id':token,'expires':expires}


def get_share(token,who=None):
    id_safe(token)
    with db() as con:
        row=con.execute('SELECT * FROM shares WHERE id=? AND expires>?',(token,now())).fetchone()
        if not row:
            return None
        suggestions=[]
        for s in con.execute('''SELECT s.id,s.kind,s.name,s.price,s.day,s.comment,s.created,
             (SELECT count(*) FROM votes v WHERE v.suggestion_id=s.id) AS votes,
             (SELECT count(*) FROM votes v WHERE v.suggestion_id=s.id AND v.voter=?) AS mine
             FROM suggestions s WHERE s.share_id=? ORDER BY votes DESC,s.created''',(who or '',token)):
            suggestions.append(dict(s))
    return {'id':token,'title':row['title'],'plan':json.loads(row['payload']),
            'owner':bool(who and who==row['owner']),'suggestions':suggestions,
            'expires':row['expires']}


def sync_share(token,owner,plan,title):
    id_safe(token)
    with db() as con:
        changed=con.execute('UPDATE shares SET payload=?,title=?,updated=? WHERE id=? AND owner=? AND expires>?',
                            (_blob(plan),str(title or 'Rencana liburan')[:100],now(),token,owner,now())).rowcount
    return bool(changed)


def add_suggestion(token,creator,kind,name,price,day,comment):
    id_safe(token)
    if kind not in ('wisata','kuliner'):
        raise ValueError('Kategori usulan tidak valid.')
    name=str(name or '').strip()
    if not 2<=len(name)<=100:
        raise ValueError('Nama tempat harus 2–100 karakter.')
    if not isinstance(price,int) or not 0<=price<=10_000_000:
        raise ValueError('Perkiraan harga usulan tidak valid.')
    if not isinstance(day,int) or not 1<=day<=14:
        raise ValueError('Hari usulan tidak valid.')
    comment=str(comment or '').strip()[:300]
    with db() as con:
        share=con.execute('SELECT id FROM shares WHERE id=? AND expires>?',(token,now())).fetchone()
        if not share:
            raise ValueError('Link berbagi telah kedaluwarsa atau tidak ada.')
        count=con.execute('SELECT count(*) FROM suggestions WHERE share_id=? AND creator=?',(token,creator)).fetchone()[0]
        if count>=20:
            raise ValueError('Maksimum 20 usulan per pengguna.')
        cur=con.execute('INSERT INTO suggestions(share_id,creator,kind,name,price,day,comment,created) VALUES(?,?,?,?,?,?,?,?)',
                        (token,creator,kind,name,price,day,comment,now()))
        return cur.lastrowid


def toggle_vote(token,voter,suggestion_id):
    id_safe(token)
    with db() as con:
        exists=con.execute('''SELECT s.id FROM suggestions s JOIN shares sh ON sh.id=s.share_id
            WHERE s.id=? AND sh.id=? AND sh.expires>?''',(suggestion_id,token,now())).fetchone()
        if not exists:
            raise ValueError('Usulan tidak ditemukan.')
        prior=con.execute('SELECT 1 FROM votes WHERE suggestion_id=? AND voter=?',(suggestion_id,voter)).fetchone()
        if prior:
            con.execute('DELETE FROM votes WHERE suggestion_id=? AND voter=?',(suggestion_id,voter))
        else:
            con.execute('INSERT INTO votes(suggestion_id,voter) VALUES(?,?)',(suggestion_id,voter))
    return not bool(prior)
