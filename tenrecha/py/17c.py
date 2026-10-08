# -*- coding: utf-8 -*-
import sys
import re
import json
import time
import socket
import base64
import hashlib
import threading
import os
import zlib
import struct
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, unquote, urljoin, parse_qs
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

HOST = 'https://www.lmlgdjr.com:2087'
UA = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36'
PUB = 'MIIBVAIBADANBgkqhkiG9w0BAQEFAASCAT4wggE6AgEAAkEA0E9Nsuz6jYF+JeLqKaL1LkZyg0Wl4xPIwEzlDrO4UOMYGX1WG+nqf9ovpplgThgLcyoRM1YFshGFOrkAiHEZqwIDAQABAkABvEdncDX+K9ADPMq6ohLs2cVmdpQVOjr37ywRXUnx0o6skjM3Yg45uw3lpobrkckep0NxqrINeSsrY29hA3ZBAiEA8rnQiqs6hXw8tLIBk0i2i7tqai9xew/lD/wDGQdtvdECIQDbs6kkuEs9us9avgF/JO7F13OmlDzR0lzrIzujxvLSuwIgW+BX/tVXnoVrWR50GDMS3gt/+VeiBen7U7SZ25SDRrECIBhIx41zgX2VRI43KlsvbeUYZ4QmJoLaycKD5ne36ec5AiEA44AwFDoD1qf1wIZ152QxrkZgGMyKG6c836lRB5VdiME='
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
_PORT = 9982
_DOMAIN = 'www.lmlgdjr.com'
_DOMAINS = ['www.lmlgdjr.com', 'www.crfxdkc.com', 'www.haxeyci.com', 'www.iagjjtg.com', 'www.gcimadk.com', 'www.kbblin.com']
_N = 0
_E = 65537
_CACHE = {}
_LIST_CACHE = {}
_SEM = threading.Semaphore(6)
_CRYPTO = None
_TS = threading.local()
_PLACEHOLDER = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')


def _gray_png():
    w = h = 24
    row = b'\x00' + b'\x77\x77\x77' * w

    def ch(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)

    return (b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) +
            ch(b'IDAT', zlib.compress(row * h)) + ch(b'IEND', b''))


_PLACEHOLDER = _gray_png()
_CACHE_DIR = '/sdcard/Download/.lmlg_cache'
_REF_D = ''
_PLAY_D = ''
_VCHECK = {}
_VCHECK_TS = {}
_NY = None
_AV = 'https://ji17df5a.xn--7jw54o.net/static/images/avatar/'
_NY_TS = 0
_FALLBACK_CATES = [{'type_id': '1', 'type_name': '国产'}, {'type_id': '3', 'type_name': '日韩'},
                   {'type_id': '2', 'type_name': '传媒'}, {'type_id': '4', 'type_name': '欧美'},
                   {'type_id': '5', 'type_name': '动漫'}]


def _log(msg):
    try:
        with open('/sdcard/Download/lmlg_diag.txt', 'a') as f:
            f.write('%s %s\n' % (time.strftime('%H:%M:%S'), msg))
    except Exception:
        pass


def _pub():
    global _N, _E, _D
    try:
        der = base64.b64decode(PUB)
        m = re.search(rb'\x02\x41\x00(.{64})', der)
        e = re.search(rb'\x02\x03(.{3})', der)
        d = re.search(rb'\x02\x40(.{64})', der)
        if m and e and d:
            _N = int.from_bytes(m.group(1), 'big')
            _E = int.from_bytes(e.group(1), 'big')
            _D = int.from_bytes(d.group(1), 'big')
    except Exception:
        pass


_pub()


def _rsa_dec(b64key):
    c = int.from_bytes(base64.b64decode(b64key), 'big')
    m = pow(c, _D, _N)
    mb = m.to_bytes(64, 'big')
    i = mb.find(b'\x00', 2)
    return mb[i + 1:] if 10 < i < 64 else mb


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
    nr = nk + 6
    w = [int.from_bytes(key[i:i + 4], 'big') for i in range(0, len(key), 4)]
    for i in range(nk, 4 * (nr + 1)):
        t = w[i - 1]
        if i % nk == 0:
            t = ((t << 8) | (t >> 24)) & 0xffffffff
            t = ((SBOX[(t >> 24) & 0xff] << 24) | (SBOX[(t >> 16) & 0xff] << 16) |
                 (SBOX[(t >> 8) & 0xff] << 8) | SBOX[t & 0xff]) ^ (RCON[i // nk - 1] << 24)
        elif nk > 6 and i % nk == 4:
            t = ((SBOX[(t >> 24) & 0xff] << 24) | (SBOX[(t >> 16) & 0xff] << 16) |
                 (SBOX[(t >> 8) & 0xff] << 8) | SBOX[t & 0xff])
        w.append(w[i - nk] ^ t)
    return [[(x >> 24) & 0xff, (x >> 16) & 0xff, (x >> 8) & 0xff, x & 0xff] for x in w], nr


def _dec_block(key, block):
    w, nr = _key_expand(key)
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

    ark(nr)
    for rnd in range(nr - 1, 0, -1):
        isr(); isb(); ark(rnd); imc()
    isr(); isb(); ark(0)
    return bytes(s)


def _crypto_aes(key, iv, data):
    global _CRYPTO
    if _CRYPTO is None:
        try:
            from Crypto.Cipher import AES
            _CRYPTO = AES
            _log('ENV crypto')
        except Exception:
            _CRYPTO = False
    if _CRYPTO:
        return _CRYPTO.new(key, _CRYPTO.MODE_CBC, iv).decrypt(data)
    return None


def _aes_cbc_decrypt(key, iv, data):
    if len(data) % 16 == 0 and len(data) >= 16:
        r = _crypto_aes(key, iv, data)
        if r is not None:
            return r
    out = bytearray()
    prev = iv
    for i in range(0, len(data), 16):
        blk = data[i:i + 16]
        out += bytes(a ^ b for a, b in zip(_dec_block(key, blk), prev))
        prev = blk
    return bytes(out)


def _http_get(u, headers, timeout=6):
    s = getattr(_TS, 's', None)
    if s is None:
        import requests as rq
        s = rq.Session()
        _TS.s = s
    return s.get(u, headers=headers, timeout=timeout, verify=False)


def _extract_domain(html):
    m = re.search(r'en\("([^"]+)"\)', html)
    if not m:
        return ''
    dk = dict(re.findall(r'"([^"\s]+)":"([^"\s]+)"', html))
    dec = ''.join(dk.get(c, c) for c in m.group(1))
    m2 = re.search(r'https?://([^/:]+)', dec)
    return m2.group(1) if m2 else ''


def _fresh_domain():
    try:
        r = _http_get(HOST + '/', {'User-Agent': UA})
        if r.status_code == 888:
            nd = _extract_domain(r.text)
            if nd:
                _log('DOMAIN -> %s' % nd)
                return nd
    except Exception:
        pass
    return ''


def _api(path):
    global _DOMAIN, _REF_D
    for _ in range(6):
        url = 'https://%s:2087%s' % (_DOMAIN, path)
        try:
            r = _http_get(url, {'User-Agent': UA, 'Accept': 'application/json'})
            if r.status_code == 200:
                _REF_D = _DOMAIN
                try:
                    return _dec_api(r.json())
                except Exception:
                    _log('DEC_FAIL %s' % path[:60])
                    return None
            if r.status_code in (404, 410, 520):
                return None
            nd = _extract_domain(r.text) if r.status_code == 888 else _fresh_domain()
            if nd and nd != _DOMAIN:
                _DOMAIN = nd
                if nd not in _DOMAINS:
                    _DOMAINS.append(nd)
            else:
                for cand in _DOMAINS:
                    if cand == _DOMAIN:
                        continue
                    try:
                        r2 = _http_get('https://%s:2087%s' % (cand, path), {'User-Agent': UA, 'Accept': 'application/json'}, timeout=3)
                        if r2.status_code == 200:
                            _DOMAIN = cand
                            _REF_D = cand
                            try:
                                return _dec_api(r2.json())
                            except Exception:
                                return None
                    except Exception:
                        pass
        except Exception:
            time.sleep(0.3)
    return None


def _dec_api(d):
    k = _rsa_dec(d['key'])
    iv = k[::-1][:16]
    raw = _aes_cbc_decrypt(k, iv, base64.b64decode(d['data']))
    pad = raw[-1] if raw else 0
    if 1 <= pad <= 16:
        raw = raw[:-pad]
    return json.loads(raw.decode('utf-8', errors='ignore'))


def _ref():
    return 'https://%s:2087/' % (_PLAY_D or _REF_D or _DOMAIN)


def _img_dec(b):
    h = bytes(x ^ 0x88 for x in b[:16])
    if h[:2] == b'\xff\xd8' or h[:4] == b'\x89PNG' or h[:4] == b'GIF8' or h[:4] == b'RIFF':
        return bytes(x ^ 0x88 for x in b)
    return b


def _m3u8_fetch(u):
    global _PLAY_D
    try:
        r = _http_get(u, {'User-Agent': UA, 'Referer': _ref()})
        if r.status_code != 200:
            _log('M3U8_ERR %d %s' % (r.status_code, u[:80]))
            return None
        _PLAY_D = _DOMAIN
        text = r.text
        out = []
        for line in text.splitlines():
            s = line.strip()
            if s and not s.startswith('#') and not s.startswith('http'):
                out.append('http://127.0.0.1:%d/fy/ts?url=%s' % (_PORT, quote(urljoin(u, s), safe='')))
            elif s.startswith('#EXT-X-KEY') and 'URI="' in s:
                m = re.search(r'URI="([^"]+)"', s)
                if m:
                    out.append(s.replace(m.group(1), 'http://127.0.0.1:%d/fy/ts?url=%s' % (_PORT, quote(urljoin(u, m.group(1)), safe=''))))
                else:
                    out.append(s)
            else:
                out.append(s)
        _log('M3U8_OK %d' % len(out))
        return '\n'.join(out).encode('utf-8')
    except Exception as e:
        _log('M3U8_EXC %s' % repr(e)[:100])
        return None


def _ts_fetch(u):
    try:
        r = _http_get(u, {'User-Agent': UA, 'Referer': _ref()})
        _log('TS %d %d' % (r.status_code, len(r.content)))
        return r.status_code, r.content
    except Exception:
        _log('TS_EXC %s' % u[:60])
        return 500, b''


def _proxy_fetch(u):
    hit = _CACHE.get(u)
    if hit:
        return 200, hit[0], hit[1]
    try:
        f = os.path.join(_CACHE_DIR, hashlib.md5(u.encode()).hexdigest() + '.img')
        if os.path.exists(f):
            d = open(f, 'rb').read()
            ct = d[:64].decode('utf-8', errors='ignore').split('\0')[0]
            body = _img_dec(d[64:])
            _CACHE[u] = (ct, body)
            return 200, ct, body
    except Exception:
        pass
    for attempt in range(3):
        try:
            with _SEM:
                time.sleep(attempt * 0.2)
                r = _http_get(u, {'User-Agent': UA, 'Referer': _ref()}, timeout=15)
                if r.status_code != 200:
                    if attempt < 2:
                        continue
                    return 200, 'image/png', _PLACEHOLDER
                body = _img_dec(r.content)
                ct = 'image/jpeg' if body[:2] == b'\xff\xd8' else ('image/png' if body[:4] == b'\x89PNG' else ('image/webp' if body[:4] == b'RIFF' else r.headers.get('content-type', 'image/jpeg')))
                _CACHE[u] = (ct, body)
                try:
                    if not os.path.isdir(_CACHE_DIR):
                        os.makedirs(_CACHE_DIR)
                    open(os.path.join(_CACHE_DIR, hashlib.md5(u.encode()).hexdigest() + '.img'), 'wb').write(ct.encode() + b'\0' + body)
                except Exception:
                    pass
                _log('OK img %s %d' % (ct, len(body)))
                return 200, ct, body
        except Exception:
            if attempt < 2:
                continue
            return 200, 'image/png', _PLACEHOLDER
    return 200, 'image/png', _PLACEHOLDER


def _ny_name(n):
    try:
        return unquote(base64.b64decode(n).decode('utf-8', 'ignore'))
    except Exception:
        return n


def _ny_tag(tags):
    h = cup = d = ''
    for t in tags or []:
        t = t.strip().strip('"')
        if not t or len(t) > 10:
            continue
        if 'cm' in t and len(t) < 9:
            h = t.replace('T', '')
        elif t.endswith('年'):
            d = t
        elif t.startswith('B') or re.match(r'^\d{2,3}[A-Z]?$', t):
            cup = t
    return '/'.join(x for x in (h, cup, d) if x)


def _check_playable(vid):
    if vid in _VCHECK and time.time() - _VCHECK_TS.get(vid, 0) < 3600:
        return _VCHECK[vid]
    try:
        r = _http_get('https://%s:2087/v1/vod/%s?c=0' % (_DOMAIN, vid), {'User-Agent': UA, 'Accept': 'application/json'}, timeout=4)
        if r.status_code == 200:
            try:
                d = _dec_api(r.json())
                v = (d.get('data') or {}).get('video') or {}
                ok = bool(v.get('url'))
                _VCHECK[vid] = ok
                _VCHECK_TS[vid] = time.time()
                return ok
            except Exception:
                pass
    except Exception:
        pass
    return True


def _load_ny():
    global _NY, _AV, _NY_TS
    if _NY and time.time() - _NY_TS < 604800:
        return _NY
    try:
        d = _api('/v1/blist?c=0')
        if d and d.get('data'):
            s = d['data'].get('site', {})
            if s.get('nvyou_avatar_prefix'):
                _AV = s['nvyou_avatar_prefix']
    except Exception:
        pass
    f = os.path.join(_CACHE_DIR, 'ny.json')
    if _NY is None and os.path.exists(f):
        try:
            if time.time() - os.path.getmtime(f) < 604800:
                _NY = json.load(open(f, encoding='utf-8'))
                _NY_TS = time.time()
                _log('NY_DISK %d' % len(_NY))
                return _NY
        except Exception:
            pass
    try:
        h = _http_get('https://%s:2087/nvyou/0.html' % _DOMAIN, {'User-Agent': UA}).text
        mc = re.search(r'let p="(https?://[^"]+)"', h)
        mi = re.search(r'index-legacy-([a-zA-Z0-9_-]+)\.js', h)
        if not mc or not mi:
            return _NY or []
        cdn = mc.group(1)
        js = _http_get('%s/cache/t1/j/index-legacy-%s.js' % (cdn, mi.group(1)), {'User-Agent': UA}).text
        ma = re.search(r'actress-list-legacy-([a-zA-Z0-9_-]+)\.js', js)
        if not ma:
            return _NY or []
        al = _http_get('%s/cache/t1/j/actress-list-legacy-%s.js' % (cdn, ma.group(1)), {'User-Agent': UA}).text
        mn = re.search(r'ny-config-legacy-([a-zA-Z0-9_-]+)\.js', al)
        if not mn:
            return _NY or []
        ny = _http_get('%s/cache/t1/j/ny-config-legacy-%s.js' % (cdn, mn.group(1)), {'User-Agent': UA}).text
        arr = re.findall(r'\{n:"([^"]+)",tags:\[([^\]]*)\],pyKey:"([^"]+)"', ny)
        if arr:
            _NY = [{'n': a[0], 'tags': [t.strip() for t in a[1].split(',')], 'pyKey': a[2]} for a in arr]
            _NY_TS = time.time()
            try:
                if not os.path.isdir(_CACHE_DIR):
                    os.makedirs(_CACHE_DIR)
                open(f, 'w', encoding='utf-8').write(json.dumps(_NY))
            except Exception:
                pass
            _log('NY %d' % len(_NY))
    except Exception:
        pass
    return _NY or []


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        qs = self.path.split('?', 1)[1] if '?' in self.path else ''
        q = parse_qs(qs)
        u = unquote(q.get('url', [''])[0]) if q else ''
        if not u and qs and 'url=' in qs:
            u = qs.split('url=', 1)[1]
        if not u:
            self.send_response(404)
            self.end_headers()
            return
        if u.startswith('http%3A') or u.startswith('http%253A'):
            u = unquote(u)
        if '/fy/m3u8' in self.path:
            body = _m3u8_fetch(u)
            if body is None:
                self.send_response(502)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/vnd.apple.mpegurl')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if '/fy/ts' in self.path:
            st, body = _ts_fetch(u)
            self.send_response(st)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)
            return
        status, ct, body = _proxy_fetch(u)
        self.send_response(status)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'public, max-age=86400')
        self.end_headers()
        if body:
            self.wfile.write(body)


def _start_proxy():
    global _PORT
    if getattr(Spider, '_proxy_started', False):
        return _PORT
    for port in range(9982, 9992):
        try:
            srv = ThreadingHTTPServer(('127.0.0.1', port), _Handler)
            srv.daemon_threads = True
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            _PORT = port
            Spider._proxy_started = True
            _log('PROXY_START %d' % port)
            return port
        except OSError:
            continue
    return 9982


class Spider(Spider):
    _settings = None

    def getName(self):
        return '17c'

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
        _log('INIT %s' % HOST)

    def _pic(self, poster):
        if not poster:
            return ''
        _start_proxy()
        return 'http://127.0.0.1:%d/fy/pic?url=%s' % (_PORT, quote(poster, safe=''))

    def _warm_imgs(self, vlist):
        def _f(it):
            try:
                u = it.get('vod_pic', '')
                if u and '/fy/pic' in u:
                    _proxy_fetch(unquote(u.split('url=', 1)[1]))
            except Exception:
                pass
        try:
            with ThreadPoolExecutor(max_workers=6) as ex:
                ex.map(_f, vlist)
        except Exception:
            pass

    def _play_url(self, u):
        _start_proxy()
        return 'http://127.0.0.1:%d/fy/m3u8?url=%s' % (_PORT, quote(u, safe=''))

    def _vlist(self, videos):
        out = []
        for v in videos:
            out.append({'vod_id': str(v.get('id', '')), 'vod_name': v.get('name', ''),
                        'vod_pic': self._pic(v.get('enc_img', '')), 'vod_remarks': v.get('time', '')})
        return out

    def homeContent(self, filter=False):
        _start_proxy()
        d = _api('/v1/vod/category?c=0')
        cls = list(_FALLBACK_CATES)
        if d and d.get('data'):
            cates = d['data'].get('cates', [])
            if cates:
                cls = []
                for c in cates:
                    cls.append({'type_id': str(c['id']), 'type_name': c['name']})
                    for s in c.get('sub_cates', []):
                        cls.append({'type_id': str(s['id']), 'type_name': '%s-%s' % (c['name'], s['name'])})
        cls.insert(0, {'type_id': 'actress', 'type_name': '女优'})
        _log('HOME cls=%d' % len(cls))
        return {'class': cls, 'list': []}

    def homeVideoContent(self):
        d = _api('/v1/relist?c=0')
        if not d or not d.get('data'):
            return {'list': []}
        vids = []
        rv = d['data'].get('recommend_videos') or {}
        vids += rv.get('videos', [])
        rk = d['data'].get('rank_videos') or {}
        vids += rk.get('videos', [])
        out = {'list': self._vlist(vids[:24]), 'page': 1, 'pagecount': 1, 'limit': 24, 'total': len(vids[:24])}
        threading.Thread(target=lambda: self._warm_imgs(out['list']), daemon=True).start()
        return out

    def categoryContent(self, tid, pg=1, filter=False, extend=''):
        if str(tid) == 'actress':
            ny = _load_ny()
            empty = {'list': [], 'page': pg, 'pagecount': 1, 'limit': 24, 'total': 0}
            if not ny:
                return empty
            start = (int(pg) - 1) * 24
            items = ny[start:start + 24]
            vlist = [{'vod_id': 'act:' + a['pyKey'], 'vod_name': _ny_name(a['n']),
                      'vod_pic': self._pic(_AV + a['pyKey'] + '.jpg'),
                      'vod_remarks': _ny_tag(a['tags'])} for a in items]
            _log('ACTL pg=%s n=%d' % (pg, len(vlist)))
            threading.Thread(target=lambda: self._warm_imgs(vlist), daemon=True).start()
            return {'list': vlist, 'page': int(pg), 'pagecount': (len(ny) + 23) // 24, 'limit': 24, 'total': len(ny)}
        sub = ''
        if filter and isinstance(filter, dict) and filter.get('sub'):
            sub = filter['sub'][0]
        cid = sub or str(tid)
        _log('CAT tid=%s pg=%s sub=%s' % (tid, pg, sub))
        d = _api('/v1/vod?c=0&cate_id=%s&page=%s&limit=24&sort=time' % (cid, pg))
        empty = {'list': [], 'page': pg, 'pagecount': pg, 'limit': 24, 'total': 0}
        if not d or not d.get('data'):
            return empty
        data = d['data']
        vlist = self._vlist(data.get('videos', []))
        pc = int(data.get('last_page', pg) or pg)
        out = {'list': vlist, 'page': int(data.get('current_page', pg) or pg), 'pagecount': pc, 'limit': 24, 'total': pc * 24}
        threading.Thread(target=lambda: self._warm_imgs(vlist), daemon=True).start()
        return out

    def _actress_detail(self, key):
        ny = _load_ny()
        nm, tags, pic = key, [], _AV + key + '.jpg'
        for a in ny:
            if a['pyKey'] == key:
                nm = _ny_name(a['n'])
                tags = a['tags']
                break
        d = _api('/v1/vod?c=0&name=%s&page=1&limit=24' % quote(nm))
        if not d or not d.get('data'):
            return {'list': []}
        data = d['data']
        videos = data.get('videos', [])
        cand = [v for v in videos if not v.get('href')][:24]
        kept = []
        with ThreadPoolExecutor(max_workers=4) as ex:
            for v, ok in ex.map(lambda v: (v, _check_playable(str(v.get('id', '')))), cand):
                if ok:
                    kept.append(v)
        if not kept and cand:
            kept = cand
        urls = []
        for i, v in enumerate(kept[:20]):
            nm2 = re.sub(r'[$#]', ' ', str(v.get('name', '') or ''))[:32]
            urls.append('%s$actp:%s' % (nm2, v.get('id', '')))
        tag = _ny_tag(tags)
        vod = {'vod_id': 'act:' + key, 'vod_name': nm, 'vod_pic': self._pic(pic),
               'vod_remarks': '共%s部' % len(kept),
               'vod_content': ('%s\n%s' % (nm, tag)) if tag else nm,
               'vod_play_from': '作品', 'vod_play_url': '#'.join(urls)}
        _log('ACTD %s total=%s kept=%s' % (nm, data.get('total', 0), len(kept)))
        return {'list': [vod]}

    def detailContent(self, ids):
        if not ids:
            return {'list': []}
        if str(ids[0]).startswith('act:'):
            return self._actress_detail(str(ids[0])[4:])
        vid = str(ids[0]).split('-')[0]
        d = _api('/v1/vod/%s?c=0' % vid)
        if not d or not d.get('data'):
            d = _api('/v1/vod/%s?c=0' % vid)
        if not d or not d.get('data'):
            return {'list': []}
        v = d['data'].get('video') or {}
        if not v:
            return {'list': []}
        url = v.get('url', '')
        for _ in range(2):
            if url:
                break
            time.sleep(0.5)
            d = _api('/v1/vod/%s?c=0' % vid)
            if d and d.get('data'):
                v = d['data'].get('video') or {}
                url = v.get('url', '')
        cate = (v.get('cate') or {}).get('name', '')
        vod = {'vod_id': vid, 'vod_name': v.get('name', vid),
               'vod_pic': self._pic(v.get('enc_img', '')),
               'vod_class': cate, 'vod_remarks': v.get('time', ''),
               'vod_content': cate, 'vod_play_from': '17c',
               'vod_play_url': ('正片$' + self._play_url(url)) if url else ''}
        _log('DETAIL %s url_ok=%s' % (vid, 'yes' if url else 'no'))
        return {'list': [vod]}

    def searchContent(self, key, quick=False, pg='1'):
        d = _api('/v1/vod?c=0&name=%s&page=%s&limit=24' % (quote(key), pg))
        empty = {'list': [], 'page': pg, 'pagecount': 1, 'limit': 24, 'total': 0}
        if not d or not d.get('data'):
            return empty
        data = d['data']
        vlist = self._vlist(data.get('videos', []))
        pc = int(data.get('last_page', 1) or 1)
        return {'list': vlist, 'page': pg, 'pagecount': pc, 'limit': 24, 'total': pc * 24}

    def playerContent(self, flag, id, vipFlags=None):
        _log('PLAY id=%s' % str(id)[:100])
        if str(id).startswith('http://127.0.0.1'):
            return {'parse': 0, 'url': id}
        vid = str(id).replace('actp:', '').split('-')[0]
        for attempt in range(3):
            d = _api('/v1/vod/%s?c=0' % vid)
            if d and d.get('data'):
                v = d['data'].get('video') or {}
                url = v.get('url', '')
                if url:
                    return {'parse': 0, 'url': self._play_url(url)}
            if attempt < 2:
                time.sleep(0.8)
        return {}

    def _pagecount(self, page, html):
        return page + 1

    def _items(self):
        return []
