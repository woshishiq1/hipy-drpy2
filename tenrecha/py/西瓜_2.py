# -*- coding: utf-8 -*-
import sys
import re
import json
import time
import socket
import base64
import hashlib
import threading
from urllib.parse import quote, unquote, urljoin, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import time
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

HOST = 'https://71us.tov7yi5pxg.cc'
UA = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36'
KEY = b'NHboMHZerxFQ401E'
IV = b'i7JeCEIMVrj2W9xN'
CATEGORIES = [
    {'type_id': '51', 'type_name': '国产'}, {'type_id': '156', 'type_name': '国产-乱伦'},
    {'type_id': '152', 'type_name': '国产-偷情'}, {'type_id': '191', 'type_name': '国产-剧情'},
    {'type_id': '144', 'type_name': '国产-偷拍'}, {'type_id': '145', 'type_name': '国产-自拍'},
    {'type_id': '151', 'type_name': '国产-直播'}, {'type_id': '153', 'type_name': '国产-探花'},
    {'type_id': '154', 'type_name': '国产-强奸'}, {'type_id': '155', 'type_name': '国产-迷奸'},
    {'type_id': '76', 'type_name': '日韩'}, {'type_id': '169', 'type_name': '日韩-中字'},
    {'type_id': '171', 'type_name': '日韩-无码'}, {'type_id': '194', 'type_name': '日韩-乱伦'},
    {'type_id': '193', 'type_name': '日韩-人妻'}, {'type_id': '183', 'type_name': '日韩-群交'},
    {'type_id': '170', 'type_name': '日韩-OL'}, {'type_id': '196', 'type_name': '日韩-偷情'},
    {'type_id': '127', 'type_name': '欧美'}, {'type_id': '176', 'type_name': '欧美-黑白配'},
    {'type_id': '185', 'type_name': '欧美-剧情'}, {'type_id': '178', 'type_name': '欧美-中字'},
    {'type_id': '182', 'type_name': '欧美-SM'}, {'type_id': '186', 'type_name': '欧美-自拍'},
    {'type_id': '177', 'type_name': '欧美-男同'}, {'type_id': '181', 'type_name': '欧美-女同'},
    {'type_id': '93', 'type_name': '吃瓜'},
    {'type_id': '60', 'type_name': '传媒'}, {'type_id': '146', 'type_name': '传媒-麻豆'},
    {'type_id': '147', 'type_name': '传媒-天美'}, {'type_id': '148', 'type_name': '传媒-91'},
    {'type_id': '157', 'type_name': '传媒-星空'}, {'type_id': '158', 'type_name': '传媒-精东'},
    {'type_id': '159', 'type_name': '传媒-蜜桃'}, {'type_id': '160', 'type_name': '传媒-SWAG'},
    {'type_id': '187', 'type_name': '传媒-果冻'}, {'type_id': '188', 'type_name': '传媒-糖心'},
    {'type_id': '190', 'type_name': '传媒-萝莉社'}, {'type_id': '192', 'type_name': '传媒-扣扣'},
    {'type_id': '195', 'type_name': '传媒-皇家'},
    {'type_id': '137', 'type_name': 'AI视频'},
    {'type_id': '83', 'type_name': '动漫'}, {'type_id': '172', 'type_name': '动漫-中字'},
    {'type_id': '173', 'type_name': '动漫-有码'}, {'type_id': '174', 'type_name': '动漫-无码'},
    {'type_id': '189', 'type_name': '动漫-3D'},
    {'type_id': '71', 'type_name': '综艺'}, {'type_id': '198', 'type_name': '解说'},
    {'type_id': '197', 'type_name': 'VR'}, {'type_id': '199', 'type_name': '伦理'},
    {'type_id': '200', 'type_name': '猎奇'}, {'type_id': '201', 'type_name': '福利姬'},
]
SBOX = bytes([
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16])
INV_SBOX = bytes([SBOX.index(i) for i in range(256)])
RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36]
_PORT = 9978
_CACHE = {}
_LIST_CACHE = {}
_SEM = threading.Semaphore(6)
_CRYPTO = None
_PLACEHOLDER = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')
_SESS = None
_CFFI = None


def _http_get(u, headers):
    global _SESS, _CFFI
    if _CFFI is None:
        try:
            from curl_cffi import requests as cffi
            _CFFI = cffi.Session()
        except Exception:
            _CFFI = False
    if _CFFI:
        try:
            return _CFFI.get(u, headers=headers, impersonate='chrome124', timeout=5)
        except Exception:
            pass
    if _SESS is None:
        import requests as rq
        _SESS = rq.Session()
    return _SESS.get(u, headers=headers, timeout=5, verify=False)


def _xtime(a):
    return ((a << 1) ^ 0x1b) & 0xff if a & 0x80 else (a << 1) & 0xff


def _gmul(a, b):
    r = 0
    while b:
        if b & 1:
            r ^= a
        b >>= 1
        a = _xtime(a)
    return r


def _key_expand(key):
    nk = len(key) // 4
    w = [int.from_bytes(key[i:i + 4], 'big') for i in range(0, len(key), 4)]
    for i in range(nk, 44):
        t = w[i - 1]
        if i % nk == 0:
            t = ((t << 8) | (t >> 24)) & 0xffffffff
            t = ((SBOX[(t >> 24) & 0xff] << 24) | (SBOX[(t >> 16) & 0xff] << 16) |
                 (SBOX[(t >> 8) & 0xff] << 8) | SBOX[t & 0xff]) ^ (RCON[i // nk - 1] << 24)
        w.append(w[i - nk] ^ t)
    return [[(x >> 24) & 0xff, (x >> 16) & 0xff, (x >> 8) & 0xff, x & 0xff] for x in w]


def _dec_block(key, block):
    w = _key_expand(key)
    s = list(block)

    def ark(rnd):
        for c in range(4):
            for r in range(4):
                s[4 * c + r] ^= w[rnd * 4 + c][r]

    def isb():
        for i in range(16):
            s[i] = INV_SBOX[s[i]]

    def isr():
        t = s[:]
        for r in range(1, 4):
            for c in range(4):
                s[4 * c + r] = t[4 * ((c - r) % 4) + r]

    def imc():
        for c in range(4):
            a0, a1, a2, a3 = s[4 * c], s[4 * c + 1], s[4 * c + 2], s[4 * c + 3]
            s[4 * c] = _gmul(a0, 0x0e) ^ _gmul(a1, 0x0b) ^ _gmul(a2, 0x0d) ^ _gmul(a3, 0x09)
            s[4 * c + 1] = _gmul(a0, 0x09) ^ _gmul(a1, 0x0e) ^ _gmul(a2, 0x0b) ^ _gmul(a3, 0x0d)
            s[4 * c + 2] = _gmul(a0, 0x0d) ^ _gmul(a1, 0x09) ^ _gmul(a2, 0x0e) ^ _gmul(a3, 0x0b)
            s[4 * c + 3] = _gmul(a0, 0x0b) ^ _gmul(a1, 0x0d) ^ _gmul(a2, 0x09) ^ _gmul(a3, 0x0e)

    ark(10)
    for rnd in range(9, 0, -1):
        isr(); isb(); ark(rnd); imc()
    isr(); isb(); ark(0)
    return bytes(s)


def _aes_cbc_decrypt(key, iv, data):
    if len(data) % 16 == 0 and len(data) >= 16:
        r = _crypto_aes(data)
        if r is not None:
            return r
    out = bytearray()
    prev = iv
    for i in range(0, len(data), 16):
        blk = data[i:i + 16]
        out += bytes(a ^ b for a, b in zip(_dec_block(key, blk), prev))
        prev = blk
    return bytes(out)


def _decode(data):
    raw = _aes_cbc_decrypt(KEY, IV, base64.b64decode(data))
    pad = raw[-1] if raw else 0
    if 1 <= pad <= 16:
        raw = raw[:-pad]
    return raw.decode('utf-8', errors='ignore')


def _proxy_ref(u):
    m = re.search(r'/([0-9a-f]{32})/', u)
    return HOST + '/poster.html?viewkey=' + m.group(1) if m else HOST + '/'


_IMG_ENGINE = None
_CACHE_DIR = '/sdcard/Download/.71us_cache'


def _crypto_aes(data):
    global _CRYPTO
    if _CRYPTO is None:
        try:
            from Crypto.Cipher import AES
            _CRYPTO = AES
            _log('ENV crypto')
        except Exception:
            _CRYPTO = False
    if _CRYPTO:
        c = _CRYPTO.new(KEY, _CRYPTO.MODE_CBC, IV)
        return c.decrypt(data)
    return None


def _img_result(b):
    global _IMG_ENGINE
    if b[:4] == b'RIFF' and b[8:12] == b'WEBP':
        if _IMG_ENGINE is None:
            _IMG_ENGINE = 0
            for mod in ('PIL', 'cv2', 'imageio'):
                try:
                    __import__(mod)
                    _IMG_ENGINE = {'PIL': 1, 'cv2': 2, 'imageio': 3}[mod]
                    _log('ENV img %s' % mod)
                    break
                except Exception:
                    pass
            if _IMG_ENGINE == 0:
                _log('ENV no img lib webp')
        try:
            if _IMG_ENGINE == 1:
                from PIL import Image
                import io
                im = Image.open(io.BytesIO(b)).convert('RGB')
                out = io.BytesIO()
                im.save(out, 'JPEG', quality=88)
                return 'image/jpeg', out.getvalue()
            if _IMG_ENGINE == 2:
                import cv2
                import numpy as np
                img = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)
                ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 88])
                if ok:
                    return 'image/jpeg', buf.tobytes()
            if _IMG_ENGINE == 3:
                import imageio
                out = imageio.v2.imwrite('<bytes>', imageio.v2.imread(b), format='JPEG')
                return 'image/jpeg', out
        except Exception:
            pass
        return 'image/webp', b
    if b[:2] == b'\xff\xd8':
        return 'image/jpeg', b
    if b[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png', b
    return 'application/octet-stream', b


def _strict_unpad(b, block_size=16):
    if not b or len(b) % block_size:
        return None
    pad = b[-1]
    if not 1 <= pad <= block_size or b[-pad:] != bytes([pad]) * pad:
        return None
    return b[:-pad]


def _cache_proxy_body(u, ct, body):
    if len(_CACHE) > 300:
        _CACHE.clear()
    _CACHE[u] = (ct, body)
    try:
        import os
        if not os.path.isdir(_CACHE_DIR):
            os.makedirs(_CACHE_DIR)
        f = os.path.join(_CACHE_DIR, hashlib.md5(u.encode()).hexdigest() + '.img')
        with open(f, 'wb') as fp:
            fp.write(ct.encode('utf-8') + b'\0' + body)
    except Exception:
        pass


def _decrypt_image_body(body):
    ct, visible = _img_result(body)
    if ct != 'application/octet-stream':
        return ct, visible, False
    if len(body) < 16 or len(body) % 16:
        return ct, body, False
    try:
        raw = _aes_cbc_decrypt(KEY, IV, body)
        unpadded = _strict_unpad(raw)
        if unpadded is None:
            return ct, body, False
        decrypted_ct, decrypted_body = _img_result(unpadded)
        if decrypted_ct != 'application/octet-stream':
            return decrypted_ct, decrypted_body, True
    except Exception:
        pass
    return ct, body, False


def _log(msg):
    try:
        with open('/sdcard/Download/71us_diag.txt', 'a') as f:
            f.write('%s %s\n' % (time.strftime('%H:%M:%S'), msg))
    except Exception:
        pass


def _proxy_fetch(u):
    hit = _CACHE.get(u)
    if hit:
        return 200, hit[0], hit[1]
    if '.m3u8' not in u:
        try:
            import os
            f = os.path.join(_CACHE_DIR, hashlib.md5(u.encode()).hexdigest() + '.img')
            if os.path.exists(f):
                with open(f, 'rb') as fp:
                    d = fp.read()
                sep = d.find(b'\0', 0, 64)
                if 0 < sep < 64:
                    ct = d[:sep].decode('utf-8', errors='ignore')
                    body = d[sep + 1:]
                    _CACHE[u] = (ct, body)
                    return 200, ct, body
        except Exception:
            pass
    for attempt in range(2):
        try:
            with _SEM:
                time.sleep(attempt * 0.3)
                r = _http_get(u, {'User-Agent': UA, 'Referer': _proxy_ref(u)})
                if r.status_code != 200:
                    _log('ERR status %d %s' % (r.status_code, u[:80]))
                    if attempt == 0:
                        continue
                    return 200, 'image/gif', _PLACEHOLDER
                body = r.content
                if '.m3u8' in u:
                    lines = []
                    for line in body.decode('utf-8', errors='ignore').splitlines():
                        s = line.strip()
                        if s and not s.startswith('#') and not s.startswith('http'):
                            lines.append('http://127.0.0.1:%d/71us?url=%s' % (_PORT, quote(urljoin(u, s), safe='')))
                        elif s.startswith('#EXT-X-KEY') and 'URI="' in s:
                            m = re.search(r'URI="([^"]+)"', s)
                            if m:
                                lines.append(s.replace(m.group(1), 'http://127.0.0.1:%d/71us?url=%s' % (_PORT, quote(urljoin(u, m.group(1)), safe=''))))
                            else:
                                lines.append(s)
                        else:
                            lines.append(s)
                    return 200, 'application/vnd.apple.mpegurl', '\n'.join(lines).encode('utf-8')
                if 'post.js' in u or '.js' in u.split('?')[0]:
                    ct, image_body, decrypted = _decrypt_image_body(body)
                    if ct != 'application/octet-stream':
                        _cache_proxy_body(u, ct, image_body)
                        _log('OK img%s %s %d' % ('-dec' if decrypted else '', ct, len(image_body)))
                        return 200, ct, image_body
                    return 200, r.headers.get('content-type', 'application/octet-stream'), body
                ct, image_body, decrypted = _decrypt_image_body(body)
                if ct != 'application/octet-stream':
                    _cache_proxy_body(u, ct, image_body)
                    _log('OK img%s %s %d' % ('-dec' if decrypted else '', ct, len(image_body)))
                    return 200, ct, image_body
                return 200, r.headers.get('content-type', 'application/octet-stream'), body
        except Exception as e:
            _log('ERR exc %s' % repr(e)[:120])
            if attempt == 0:
                continue
            return 200, 'image/gif', _PLACEHOLDER
    return 200, 'image/gif', _PLACEHOLDER


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        qs = self.path.split('?', 1)[1] if '?' in self.path else ''
        q = parse_qs(qs)
        u = unquote(q.get('url', [''])[0]) if q else ''
        if not u and qs and 'url=' in qs:
            u = qs.split('url=', 1)[1]
        _log('REQ %d %s' % (len(u), u[:100]))
        if not u:
            self.send_response(404)
            self.end_headers()
            return
        if u.startswith('http%3A') or u.startswith('http%253A'):
            u = unquote(u)
        status, ct, body = _proxy_fetch(u)
        self.send_response(status)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'public, max-age=86400')
        self.end_headers()
        if body:
            self.wfile.write(body)
        _log('SENT %d %s' % (status, ct))


def _start_proxy():
    global _PORT
    if getattr(Spider, '_proxy_started', False):
        return _PORT
    for port in range(9978, 9988):
        try:
            srv = ThreadingHTTPServer(('127.0.0.1', port), _Handler)
            srv.daemon_threads = True
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            _PORT = port
            Spider._proxy_started = True
            _log('PROXY_START V7 %d' % port)
            return port
        except OSError:
            continue
    _log('PROXY_FAIL all ports busy')
    return 9978


class Spider(Spider):
    _settings = None

    def getName(self):
        return '西瓜'

    def isVideoFormat(self, url):
        return bool(url and ('.m3u8' in url or '.mp4' in url or '127.0.0.1' in url))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return None

    def localProxy(self, param):
        p = param.split('//', 1)[1] if param.startswith('http') else param
        qs = p.split('?', 1)[1] if '?' in p else ''
        u = unquote(parse_qs(qs).get('url', [''])[0]) if qs else ''
        if not u:
            return [404, 'text/plain', '']
        status, ct, body = _proxy_fetch(u)
        return [status, ct, body]

    def init(self, extend=''):
        global HOST
        if extend and extend.startswith('http'):
            HOST = extend.rstrip('/')
        socket.setdefaulttimeout(8)

    def _headers(self):
        ch = HOST.split('//')[1].split('.')[0]
        return {'User-Agent': UA, 'platform': '5', 'Channel-Code': ch, 'uuid': '__UUID'}

    def _get(self, url):
        t0 = time.time()
        try:
            r = _http_get(url, self._headers())
        except Exception:
            return ''
        dt = int((time.time() - t0) * 1000)
        if dt > 1500:
            _log('SLOW %dms %s' % (dt, url[:60]))
        if r.status_code == 200 and r.content:
            try:
                return _decode(r.content)
            except Exception:
                return ''
        return ''

    def _setting(self):
        if self._settings is None:
            html = self._get(HOST + '/app/common/getSetting?platform=5')
            self._settings = {}
            if html:
                try:
                    self._settings = json.loads(html).get('data', {}) or {}
                except Exception:
                    self._settings = {}
        return self._settings

    def _pic(self, poster):
        if not poster:
            return ''
        u = poster if poster.startswith('http') else (self._setting().get('imgdomain', '') or '') + poster
        _start_proxy()
        return 'http://127.0.0.1:%d/fy/pic.webp?url=%s' % (_PORT, quote(u, safe=''))

    def _list(self, page, cid=''):
        ck = '%s_%s' % (page, cid or 'home')
        now = time.time()
        hit = _LIST_CACHE.get(ck)
        if hit and now - hit[0] < 60:
            return hit[1]
        params = {'page': page, 'pageSize': 18, 'sort': 1}
        if cid:
            params['cid'] = cid
        url = HOST + '/app/movie/getList?' + '&'.join('%s=%s' % (k, v) for k, v in params.items())
        html = self._get(url)
        empty = {'list': [], 'page': page, 'pagecount': page, 'limit': 18, 'total': 0}
        if not html:
            return empty
        try:
            j = json.loads(html)
        except Exception:
            return empty
        vlist = []
        for r in j.get('records', []):
            vlist.append({'vod_id': r.get('viewKey', ''), 'vod_name': r.get('title', ''),
                          'vod_pic': self._pic(r.get('poster', '')), 'vod_remarks': '',
                          'vod_year': ''})
        pc = j.get('pageCount', page) or page
        out = {'list': vlist, 'page': page, 'pagecount': pc, 'limit': 18, 'total': pc * 18}
        _LIST_CACHE[ck] = (now, out)
        if len(_LIST_CACHE) > 200:
            _LIST_CACHE.clear()
        _start_proxy()

        def _warm():
            for it in vlist:
                try:
                    u = it['vod_pic']
                    if u and '/fy/pic' in u:
                        _proxy_fetch(unquote(u.split('url=', 1)[1]))
                except Exception:
                    pass

        threading.Thread(target=_warm, daemon=True).start()
        return out

    def homeContent(self, filter=False):
        return {'class': CATEGORIES, 'list': []}

    def homeVideoContent(self):
        return self._list(1)

    def categoryContent(self, tid, pg=1, filter=False, extend=''):
        return self._list(pg, str(tid))

    def detailContent(self, ids):
        if not ids:
            return {'list': []}
        vid = ids[0]
        url = HOST + '/app/movie/getDetail?viewKey=' + quote(vid)
        html = self._get(url)
        if not html:
            return {'list': []}
        try:
            d = json.loads(html).get('data', {}) or {}
        except Exception:
            return {'list': []}
        st = self._setting()
        pd = st.get('playdomain', '') or ''
        pu = d.get('playUrl', '') or ''
        tags = d.get('tags', '') or ''
        vod = {'vod_id': vid, 'vod_name': d.get('title', '') or vid,
               'vod_pic': self._pic(d.get('poster', '')),
               'vod_year': str(d.get('releaseDate', '') or ''), 'vod_area': '',
               'vod_class': tags, 'vod_director': '', 'vod_actor': '',
               'vod_content': tags, 'vod_remarks': '', 'vod_play_from': '西瓜',
               'vod_play_url': '正片$' + pd + pu}
        return {'list': [vod]}

    def searchContent(self, key, quick=False, pg='1'):
        url = HOST + '/app/movie/getList?page=1&pageSize=18&sort=1&keyword=' + quote(key)
        html = self._get(url)
        empty = {'list': [], 'page': pg, 'pagecount': 1, 'limit': 18, 'total': 0}
        if not html:
            return empty
        try:
            j = json.loads(html)
        except Exception:
            return empty
        vlist = []
        for r in j.get('records', []):
            vlist.append({'vod_id': r.get('viewKey', ''), 'vod_name': r.get('title', ''),
                          'vod_pic': self._pic(r.get('poster', '')), 'vod_remarks': '',
                          'vod_year': ''})
        return {'list': vlist, 'page': pg, 'pagecount': 1, 'limit': 18, 'total': len(vlist)}

    def playerContent(self, flag, id, vipFlags=None):
        m = re.search(r'/([0-9a-f]{32})/', id or '')
        ref = HOST + '/poster.html?viewkey=' + (m.group(1) if m else '')
        return {'parse': 0, 'url': id, 'header': {'User-Agent': UA, 'Referer': ref}}

    def _pagecount(self, page, html):
        return page + 1

    def _items(self):
        return []
