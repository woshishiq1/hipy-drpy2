# -*- coding: utf-8 -*-
import sys
import re
import json
import time
import base64
import hashlib
import threading
from urllib.parse import quote, unquote
from html import unescape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def fetch(self, url, headers=None, **kw):
            import requests as rq
            kw.pop('timeout', None)
            r = rq.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r

HOST = 'https://82729mka.jzac401.vip:8751'
PIC = 'https://wstgpic.bdpsjp.com'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
CATEGORIES = {'10': '国产', '11': '传媒', '12': '日韩', '14': '无码', '15': '欧美', '16': '动漫', '18': '主播', '19': '同性', '20': '三级', '21': '黑白'}
EP = {
    'room_list': '/room/list',
    'room_by_ids': '/room/get_info_by_ids',
    'search': '/view_model/search_model',
    'video_play': '/login/video_play',
}
_DEC = {'e': 'P', 'w': 'D', 'T': 'y', '+': 'J', 'l': '!', 't': 'L', 'E': 'E', '@': '2', 'd': 'a', 'b': '%', 'q': 'l', 'X': 'v', '~': 'R', '5': 'r', '&': 'X', 'C': 'j', ']': 'F', 'a': ')', '^': 'm', ',': '~', '}': '1', 'x': 'C', 'c': '(', 'G': '@', 'h': 'h', '.': '*', 'L': 's', '=': ',', 'p': 'g', 'I': 'Q', '1': '7', '_': 'u', 'K': '6', 'F': 't', '2': 'n', '8': '=', 'k': 'G', 'Z': ']', ')': 'b', 'P': '}', 'B': 'U', 'S': 'k', '6': 'i', 'g': ':', 'N': 'N', 'i': 'S', '%': '+', '-': 'Y', '?': '|', '4': 'z', '*': '-', '3': '^', '[': '{', '(': 'c', 'u': 'B', 'y': 'M', 'U': 'Z', 'H': '[', 'z': 'K', '9': 'H', '7': 'f', 'R': 'x', 'v': '&', '!': ';', 'M': '_', 'Q': '9', 'Y': 'e', 'o': '4', 'r': 'A', 'm': '.', 'O': 'o', 'V': 'W', 'J': 'p', 'f': 'd', ':': 'q', '{': '8', 'W': 'I', 'j': '?', 'n': '5', 's': '3', '|': 'T', 'A': 'V', 'D': 'w', ';': 'O'}
_PORT = 9979
_CACHE = {}
_PLACEHOLDER = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')


def _dec(s):
    return unescape(''.join(_DEC.get(c, c) for c in (s or '')))


def _gif():
    return _PLACEHOLDER


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        qs = self.path.split('?', 1)[1] if '?' in self.path else ''
        serial = ''
        for a in qs.split('&'):
            if a.startswith('serial='):
                serial = unquote(a[7:])
        body = None
        if serial:
            try:
                import requests as rq
                r = rq.get(PIC + '/pic/' + serial + '/thumbnail.css', headers={'User-Agent': UA, 'Referer': PIC + '/'}, timeout=8, verify=False)
                raw = r.content
                if raw:
                    body = bytes(b ^ 0x88 for b in raw)
            except Exception:
                pass
        if not body:
            body = _gif()
        self.send_response(200)
        self.send_header('Content-Type', 'image/webp' if body != _gif() else 'image/gif')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'public, max-age=86400')
        self.end_headers()
        self.wfile.write(body)


def _start_proxy():
    global _PORT
    if getattr(Spider, '_jz_proxy_ok', False):
        return _PORT
    for port in range(9979, 9989):
        try:
            srv = ThreadingHTTPServer(('127.0.0.1', port), _Handler)
            srv.daemon_threads = True
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            _PORT = port
            Spider._jz_proxy_ok = True
            return port
        except OSError:
            continue
    return 9979


class Spider(Spider):
    def init(self, extend=''):
        self.live_host = ''
        self.app_id = ''
        self.app_secret = ''
        self.device_id = ''
        if extend:
            try:
                cfg = json.loads(extend)
                if isinstance(cfg, dict):
                    self.live_host = (cfg.get('live_host') or cfg.get('host') or '').rstrip('/')
                    self.app_id = cfg.get('app_id', '') or ''
                    self.app_secret = cfg.get('app_secret', '') or ''
                    self.device_id = cfg.get('device_id', '') or ''
            except Exception:
                parts = [p.strip() for p in extend.split('|')]
                if parts and parts[0].startswith('http'):
                    self.live_host = parts[0].rstrip('/')
                    if len(parts) > 1:
                        self.app_id = parts[1]
                    if len(parts) > 2:
                        self.app_secret = parts[2]
                    if len(parts) > 3:
                        self.device_id = parts[3]
        self._resolve()
        _start_proxy()

    def getName(self):
        return '橘子'

    def isVideoFormat(self, url):
        return bool(url and ('.m3u8' in url or '.mp4' in url or '.flv' in url or '127.0.0.1' in url))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return None

    def homeContent(self, filter=False):
        cls = [{'type_id': k, 'type_name': v} for k, v in CATEGORIES.items()]
        if self.live_host:
            cls.insert(0, {'type_id': 'live', 'type_name': '直播'})
        return {'class': cls, 'list': []}

    def homeVideoContent(self):
        j = self._get_json('/index.json?260211&')
        if not j:
            return {'list': []}
        out = []
        for c in (j.get('index_videos') or {}).values():
            if isinstance(c, dict):
                out.extend(c.get('videos') or [])
        return {'list': self._items(out)}

    def categoryContent(self, tid, pg=1, filter=False, extend=''):
        try:
            pn = max(int(str(pg)), 1)
        except Exception:
            pn = 1
        stid = str(tid)
        if stid == 'live' and self.live_host:
            j = self._post(self.live_host + EP['room_list'], {'page': pn, 'pageSize': 20})
            rows = self._rows(j)
            vlist = [self._live_item(r) for r in rows]
            vlist = [v for v in vlist if v.get('vod_id')]
            total = 0
            if isinstance(j, dict) and isinstance(j.get('data'), dict):
                total = j['data'].get('total') or 0
            pc = max(pn, (total // 20 + 1) if total else pn)
            return {'list': vlist, 'page': pn, 'pagecount': pc, 'limit': 20, 'total': total}
        cat = stid
        if cat not in CATEGORIES:
            cat = '10'
        j = self._get_json('/type/%s_%d.json?260211&' % (cat, pn))
        if not j:
            return {'page': pn, 'pagecount': 1, 'limit': 14, 'total': 0, 'list': []}
        d = j.get('data') or {}
        return {'page': pn, 'pagecount': int(d.get('page_count') or 1), 'limit': len(d.get('videos') or []), 'total': 0, 'list': self._items(d.get('videos') or [])}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) and ids else str(ids)
        if str(vid).startswith('L'):
            return self._live_detail(str(vid)[1:])
        m = re.search(r'(\d+)', str(vid))
        vid = m.group(1) if m else ''
        if not vid:
            return {'list': []}
        j = self._get_json('/video/%s.json?260211&' % vid)
        if not j:
            return {'list': []}
        v = j.get('video') or {}
        s = v.get('serial_number') or ''
        d = {
            'vod_id': vid,
            'vod_name': _dec(v.get('title')),
            'vod_pic': 'http://127.0.0.1:%d/jzpic?serial=%s' % (_PORT, quote(s or '')),
            'vod_year': str(v.get('date') or '')[:4],
            'vod_area': '',
            'vod_class': ', '.join(v.get('labels') or [])[:100],
            'vod_director': '',
            'vod_actor': '',
            'vod_content': '',
            'vod_remarks': '%s·%ss' % (v.get('read_number'), v.get('second')),
            'vod_play_from': '橘子',
            'vod_play_url': ('正片$' + PIC + '/m3u8/' + s + '/index_domain.m3u8?260211') if s else ''
        }
        return {'list': [d]}

    def searchContent(self, key, quick=False, pg='1'):
        try:
            pn = max(int(str(pg)), 1)
        except Exception:
            pn = 1
        j = self._get_json('/search.json?search=%s&page=%d' % (quote(key), pn))
        if not j:
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 14, 'total': 0}
        return {'list': self._items(j.get('videos') or []), 'page': pg, 'pagecount': int(j.get('page_count') or 1), 'limit': len(j.get('videos') or []), 'total': 0}

    def playerContent(self, flag, id, vipFlags=None):
        u = str(id) if id else str(flag)
        if u.startswith('http'):
            return {'url': u, 'header': {'User-Agent': UA, 'Referer': PIC + '/'}}
        if u.startswith('L'):
            d = self._live_detail(u[1:])
            v = (d.get('list') or [{}])[0]
            pu = v.get('vod_play_url') or ''
            if '$' in pu:
                pu = pu.split('$', 1)[1]
            if pu:
                return {'url': pu, 'header': {'User-Agent': UA}}
            return {'url': ''}
        return {'url': u}

    def localProxy(self, param):
        p = param.split('//', 1)[1] if param.startswith('http') else param
        qs = p.split('?', 1)[1] if '?' in p else p
        serial = ''
        for a in qs.split('&'):
            if a.startswith('serial='):
                serial = unquote(a[7:])
        if not serial:
            return None
        try:
            r = self.fetch(PIC + '/pic/' + serial + '/thumbnail.css', headers={'User-Agent': UA, 'Referer': PIC + '/'}, timeout=15000)
            raw = r.content if hasattr(r, 'content') else r.read()
            if not raw:
                return None
            dec = bytes(b ^ 0x88 for b in raw)
            if hasattr(self, 'setContentType'):
                self.setContentType('image/webp')
                return dec
            return [200, 'image/webp', dec]
        except Exception:
            return None

    def _md5_upper(self, text):
        return hashlib.md5(text.encode('utf-8')).hexdigest().upper()

    def _ts(self):
        return str(int(time.time()))

    def _headers(self):
        return {'User-Agent': UA, 'version': '5.0.2', 'package': 'com.l6b41ef196.f544c40ccd', 'Content-Type': 'application/json'}

    def _sign(self, path, data):
        if not self.app_secret:
            return ''
        ts = self._ts()
        parts = [str(data.get(k, '')) for k in sorted(data)] if isinstance(data, dict) else []
        return self._md5_upper(self.app_id + path + ts + ''.join(parts) + self.app_secret)

    def _post(self, url, data, timeout=15):
        data = dict(data or {})
        data.setdefault('app_id', self.app_id)
        data.setdefault('version', '5.0.2')
        data.setdefault('device_id', self.device_id)
        data.setdefault('timestamp', self._ts())
        path = url.split('://', 1)[-1]
        if '/' in path:
            path = '/' + path.split('/', 1)[1]
        else:
            path = ''
        sign = self._sign(path, data)
        if sign:
            data['sign'] = sign
        try:
            import requests as rq
            r = rq.post(url, json=data, headers=self._headers(), timeout=timeout, verify=False)
            if r.status_code != 200:
                return None
            try:
                return r.json()
            except Exception:
                return {'code': 0, 'data': r.text}
        except Exception:
            return None

    def _rows(self, j):
        if not isinstance(j, dict):
            return []
        d = j.get('data')
        if isinstance(d, dict):
            for k in ('list', 'rows', 'records', 'roomList', 'items', 'data'):
                if isinstance(d.get(k), list):
                    return d[k]
            return []
        if isinstance(d, list):
            return d
        return []

    def _live_item(self, it):
        if not isinstance(it, dict):
            return {}
        rid = str(it.get('id') or it.get('roomId') or it.get('viewKey') or '')
        name = str(it.get('name') or it.get('roomName') or it.get('title') or '')
        pic = str(it.get('cover') or it.get('poster') or it.get('coverImg') or '')
        if pic and not pic.startswith('http'):
            pic = self.live_host.rstrip('/') + pic
        return {'vod_id': 'L' + rid, 'vod_name': name, 'vod_pic': pic, 'vod_remarks': str(it.get('online') or it.get('viewer') or '')}

    def _live_detail(self, rid):
        if not self.live_host:
            return {'list': []}
        j = self._post(self.live_host + EP['room_by_ids'], {'ids': [rid]})
        rows = self._rows(j)
        it = rows[0] if rows else {}
        name = str(it.get('name') or it.get('roomName') or rid)
        pic = str(it.get('cover') or it.get('poster') or '')
        if pic and not pic.startswith('http'):
            pic = self.live_host.rstrip('/') + pic
        play = str(it.get('playUrl') or it.get('play_url') or it.get('url') or it.get('hlsUrl') or it.get('pullUrl') or '')
        if not play and isinstance(j, dict) and isinstance(j.get('data'), dict):
            play = str(j['data'].get('playUrl') or j['data'].get('play_url') or j['data'].get('url') or '')
        vod = {'vod_id': 'L' + rid, 'vod_name': name, 'vod_pic': pic, 'vod_remarks': '', 'vod_content': '', 'vod_play_from': '橘子', 'vod_play_url': ('正片$' + play) if play else ''}
        return {'list': [vod]}

    def _resolve(self):
        global HOST
        try:
            r = self.fetch(HOST + '/', headers={'User-Agent': UA, 'Referer': HOST + '/'}, timeout=15000)
            t = r.text if hasattr(r, 'text') else str(r)
        except Exception:
            return
        if (getattr(r, 'status_code', 0) != 881 and 'document.write' not in (t or '') and 'var url' not in (t or '')):
            return
        m = re.search(r'decodeURIComponent\("([^"]+)"\)', t)
        if m:
            t = unquote(m.group(1))
        um = re.search(r'var\s+url\s*=\s*["\'](https?://[^"\']+index\.htm[^"\']*)["\']', t)
        em = re.search(r'var\s+encoding\s*=\s*["\']([^"\']+)["\']', t)
        if not um:
            return
        u = um.group(1)
        if em:
            u += ('&' if '?' in u else '?') + 'encoding=' + em.group(1)
        try:
            self.fetch(u, headers={'User-Agent': UA}, timeout=15000)
        except Exception:
            pass
        hm = re.search(r'(https?://[^/]+)', um.group(1))
        if hm:
            HOST = hm.group(1)

    def _get_json(self, path):
        for i in range(2):
            try:
                r = self.fetch(HOST + path, headers={'User-Agent': UA, 'Referer': HOST + '/'}, timeout=30000)
                t = r.text if hasattr(r, 'text') else str(r)
                if (getattr(r, 'status_code', 0) == 881 or 'document.write' in (t or '')):
                    self._resolve()
                    continue
                if t and t.lstrip().startswith('{'):
                    return json.loads(t)
            except Exception:
                pass
        return None

    def _pagecount(self, html, current_page=1):
        return 1

    def _items(self, videos):
        items, seen = [], set()
        for v in videos:
            if not isinstance(v, dict):
                continue
            vid = str(v.get('id') or '')
            if not vid or vid in seen:
                continue
            seen.add(vid)
            items.append({
                'vod_id': vid,
                'vod_name': _dec(v.get('title'))[:50],
                'vod_pic': 'http://127.0.0.1:%d/jzpic?serial=%s' % (_PORT, quote(v.get('serial_number') or '')),
                'vod_remarks': '%s·%s' % (v.get('read_number'), v.get('second')),
            })
        return items
