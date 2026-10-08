#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 91n 影院（91n.com）影视仓/OK影视 Spider。API 响应 RSA+AES-192 加密，内嵌纯 Python 解密。
import sys, re, json, base64, time
from urllib.parse import quote, urlencode

BASE = "https://www.vjmqvno.com:2087"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ── 纯 Python RSA-512 PKCS1 v1.5 解密 ──
_RSA_N = 11034812746936521251677573694796845190287135084811698639456218467379049151579247190638696356335870349231492335075568852461557851339228649721382342982841093
_RSA_D = 647908196136712601682336749890569606363197824226855308674909267474473673425334301798322617684275731265203384933954006416901677577458292570728152232337153

def _rsa_decrypt_key(b64key):
    c = int.from_bytes(base64.b64decode(b64key), 'big')
    m = pow(c, _RSA_D, _RSA_N)
    mb = m.to_bytes(64, 'big')
    i = mb.find(b'\x00', 2)
    if mb[0] == 0 and mb[1] == 2 and i > 0:
        return mb[i + 1:].decode('utf-8', 'replace')
    return None

# ── 纯 Python AES（128/192/256）──
_SBOX = (
0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16)
_RSBOX = (
0x52,0x09,0x6a,0xd5,0x30,0x36,0xa5,0x38,0xbf,0x40,0xa3,0x9e,0x81,0xf3,0xd7,0xfb,
0x7c,0xe3,0x39,0x82,0x9b,0x2f,0xff,0x87,0x34,0x8e,0x43,0x44,0xc4,0xde,0xe9,0xcb,
0x54,0x7b,0x94,0x32,0xa6,0xc2,0x23,0x3d,0xee,0x4c,0x95,0x0b,0x42,0xfa,0xc3,0x4e,
0x08,0x2e,0xa1,0x66,0x28,0xd9,0x24,0xb2,0x76,0x5b,0xa2,0x49,0x6d,0x8b,0xd1,0x25,
0x72,0xf8,0xf6,0x64,0x86,0x68,0x98,0x16,0xd4,0xa4,0x5c,0xcc,0x5d,0x65,0xb6,0x92,
0x6c,0x70,0x48,0x50,0xfd,0xed,0xb9,0xda,0x5e,0x15,0x46,0x57,0xa7,0x8d,0x9d,0x84,
0x90,0xd8,0xab,0x00,0x8c,0xbc,0xd3,0x0a,0xf7,0xe4,0x58,0x05,0xb8,0xb3,0x45,0x06,
0xd0,0x2c,0x1e,0x8f,0xca,0x3f,0x0f,0x02,0xc1,0xaf,0xbd,0x03,0x01,0x13,0x8a,0x6b,
0x3a,0x91,0x11,0x41,0x4f,0x67,0xdc,0xea,0x97,0xf2,0xcf,0xce,0xf0,0xb4,0xe6,0x73,
0x96,0xac,0x74,0x22,0xe7,0xad,0x35,0x85,0xe2,0xf9,0x37,0xe8,0x1c,0x75,0xdf,0x6e,
0x47,0xf1,0x1a,0x71,0x1d,0x29,0xc5,0x89,0x6f,0xb7,0x62,0x0e,0xaa,0x18,0xbe,0x1b,
0xfc,0x56,0x3e,0x4b,0xc6,0xd2,0x79,0x20,0x9a,0xdb,0xc0,0xfe,0x78,0xcd,0x5a,0xf4,
0x1f,0xdd,0xa8,0x33,0x88,0x07,0xc7,0x31,0xb1,0x12,0x10,0x59,0x27,0x80,0xec,0x5f,
0x60,0x51,0x7f,0xa9,0x19,0xb5,0x4a,0x0d,0x2d,0xe5,0x7a,0x9f,0x93,0xc9,0x9c,0xef,
0xa0,0xe0,0x3b,0x4d,0xae,0x2a,0xf5,0xb0,0xc8,0xeb,0xbb,0x3c,0x83,0x53,0x99,0x61,
0x17,0x2b,0x04,0x7e,0xba,0x77,0xd6,0x26,0xe1,0x69,0x14,0x63,0x55,0x21,0x0c,0x7d)
_RCON = (0x00,0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36,0x6c,0xd8,0xab,0x4d,0x9a)

def _xtime(b):
    return ((b << 1) ^ (0x1b if b & 0x80 else 0)) & 0xff

def _aes_key_expand(key):
    nk = len(key) // 4
    nr = nk + 6
    w = [list(key[i * 4:(i + 1) * 4]) for i in range(nk)]
    for i in range(nk, 4 * (nr + 1)):
        t = list(w[i - 1])
        if i % nk == 0:
            t = t[1:] + t[:1]
            t = [_SBOX[b] for b in t]
            t[0] ^= _RCON[i // nk]
        w.append([w[i - nk][j] ^ t[j] for j in range(4)])
    return w

def _gmul(a, b):
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xff
        if hi:
            a ^= 0x1b
        b >>= 1
    return p

def _inv_mix_cols(s):
    return [
        _gmul(14, s[0]) ^ _gmul(11, s[1]) ^ _gmul(13, s[2]) ^ _gmul(9, s[3]),
        _gmul(9, s[0]) ^ _gmul(14, s[1]) ^ _gmul(11, s[2]) ^ _gmul(13, s[3]),
        _gmul(13, s[0]) ^ _gmul(9, s[1]) ^ _gmul(14, s[2]) ^ _gmul(11, s[3]),
        _gmul(11, s[0]) ^ _gmul(13, s[1]) ^ _gmul(9, s[2]) ^ _gmul(14, s[3]),
    ]

def _aes_decrypt_block(block, w, nr):
    state = [[block[4 * c + r] for c in range(4)] for r in range(4)]
    for r in range(4):
        for c in range(4):
            state[r][c] ^= w[nr * 4 + c][r]
    for rnd in range(nr - 1, 0, -1):
        for r in range(1, 4):
            state[r] = state[r][-r:] + state[r][:-r]
        for r in range(4):
            for c in range(4):
                state[r][c] = _RSBOX[state[r][c]]
        for r in range(4):
            for c in range(4):
                state[r][c] ^= w[rnd * 4 + c][r]
        for c in range(4):
            col = _inv_mix_cols([state[r][c] for r in range(4)])
            for r in range(4):
                state[r][c] = col[r]
    for r in range(1, 4):
        state[r] = state[r][-r:] + state[r][:-r]
    for r in range(4):
        for c in range(4):
            state[r][c] = _RSBOX[state[r][c]]
    for r in range(4):
        for c in range(4):
            state[r][c] ^= w[c][r]
    out = bytearray(16)
    for c in range(4):
        for r in range(4):
            out[4 * c + r] = state[r][c]
    return bytes(out)

def _aes_cbc_decrypt(ciphertext, key, iv):
    w = _aes_key_expand(key)
    nr = len(key) // 4 + 6
    prev = iv
    out = bytearray()
    for i in range(0, len(ciphertext), 16):
        blk = ciphertext[i:i + 16]
        dec = _aes_decrypt_block(blk, w, nr)
        out += bytes(dec[j] ^ prev[j] for j in range(16))
        prev = blk
    return bytes(out)

def _unpad(pt):
    if pt:
        pad = pt[-1]
        if 1 <= pad <= 16 and pt[-pad:] == bytes([pad]) * pad:
            pt = pt[:-pad]
    return pt

def _decrypt_resp(obj):
    key_str = _rsa_decrypt_key(obj['key'])
    if not key_str:
        return None
    iv = key_str[::-1][:16].encode()
    ct = base64.b64decode(obj['data'])
    pt = _unpad(_aes_cbc_decrypt(ct, key_str.encode(), iv))
    return pt.decode('utf-8', 'replace')

# ── HTTP（requests 优先，urllib 兜底）──
try:
    import requests
    _HAS_REQ = True
except ImportError:
    _HAS_REQ = False

class _Http:
    def __init__(self):
        self._s = requests.Session() if _HAS_REQ else None

    def get_json(self, url, params=None, timeout=12):
        hdrs = {"User-Agent": UA, "X-Requested-With": "XMLHttpRequest",
                "Referer": BASE + "/"}
        if _HAS_REQ:
            r = self._s.get(url, params=params, headers=hdrs, timeout=timeout, verify=False)
            return r.json()
        import urllib.request
        if params:
            url += ('&' if '?' in url else '?') + urlencode(params)
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8', 'replace'))

    def get_raw(self, url, timeout=10):
        """取原始字节（localProxy 图片代理用，带 Referer 防盗链）"""
        hdrs = {"User-Agent": UA, "Referer": BASE + "/"}
        if _HAS_REQ:
            r = self._s.get(url, headers=hdrs, timeout=timeout, verify=False)
            return r.status_code, r.headers.get('Content-Type', 'image/jpeg'), r.content
        import urllib.request
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.headers.get('Content-Type', 'image/jpeg'), resp.read()

# 91n Spider（类名必须为 Spider，OK影视/影视仓约定）
class Spider:
    name = "91n"
    version = "1.1.0"

    def __init__(self):
        # 兜底：部分播放器（OK影视/影视仓旧版）不调 init 直接调其他方法
        self.http = _Http()
        self._cates = None
        self._last_vod_id = None   # 最近一次详情 id（供播放过期续期）

    def init(self, extend=""):
        if not isinstance(extend, str):
            extend = ""
        self.http = _Http()
        self._cates = None   # 分类缓存

    # 内部：请求 + 解密
    def _api(self, path, params=None):
        obj = self.http.get_json(BASE + "/v1/" + path, params)
        if not isinstance(obj, dict) or 'key' not in obj:
            return None
        plain = _decrypt_resp(obj)
        if not plain:
            return None
        try:
            return json.loads(plain)
        except Exception:
            return None

    def _get_cates(self):
        if self._cates:
            return self._cates
        try:
            d = self._api("blist", {"c": "t1"})
            if d and d.get('data'):
                self._cates = d['data'].get('shipin_cates') or []
        except Exception:
            self._cates = []
        return self._cates

    # ── 首页 ──
    def homeContent(self, filter=None):
        cates = self._get_cates()
        classes = [{"type_id": str(c['id']), "type_name": c['name']}
                   for c in cates if isinstance(c, dict)]
        vlist = []
        try:
            d = self._api("vod/category", {"c": "t1"})
            if d and d.get('data'):
                seen = set()
                for c in (d['data'].get('cates') or []):
                    for v in (c.get('videos') or []):
                        if not isinstance(v, dict) or 'href' in v:
                            continue
                        vid = str(v.get('id'))
                        if vid in seen:
                            continue
                        seen.add(vid)
                        vlist.append(self._fmt_vod(v))
        except Exception:
            pass
        return {"class": classes, "list": vlist}

    # ── 分类列表 ──
    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        d = self._api("vod", {"c": "t1", "cate_id": str(tid), "page": pg, "limit": 24})
        if not d or not d.get('data'):
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}
        data = d['data']
        vlist = [self._fmt_vod(v) for v in (data.get('videos') or [])
                 if isinstance(v, dict) and 'href' not in v]
        total = int(data.get('total') or 0)
        last = int(data.get('last_page') or 1)
        return {"list": vlist, "page": pg, "pagecount": last, "limit": 24, "total": total}

    # ── 详情 ──
    def detailContent(self, ids):
        if isinstance(ids, list):
            vid = str(ids[0])
        else:
            vid = str(ids)
        vid = re.sub(r'\D', '', vid)
        d = self._api("vod/" + vid, {"c": "t1"})
        if not d or not d.get('data'):
            return {"list": []}
        v = d['data'].get('video') or {}
        vod_id = str(v.get('id', vid))
        self._last_vod_id = vod_id
        name = v.get('name') or ''
        pic = v.get('enc_img') or ''
        m3u8 = v.get('url') or ''
        cates = v.get('cates') or []
        type_name = cates[0]['name'] if cates and isinstance(cates[0], dict) else ''
        actor = ','.join(v.get('actress') or [])
        tags = ','.join(v.get('tags') or [])
        content = v.get('description') or ''
        year = ''
        m = re.search(r'(\d{4})', str(v.get('create_time') or ''))
        if m:
            year = m.group(1)
        remark = ''
        if m3u8:
            remark = '正片'
        vod = {
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": self._pic_proxy(pic or ''),
            "type_name": type_name,
            "vod_year": year,
            "vod_area": '',
            "vod_actor": actor,
            "vod_director": '',
            "vod_content": content,
            "vod_remarks": remark,
            "vod_tag": tags,
            "vod_play_from": "91n",
            "vod_play_url": ("第1集$" + self._with_vid(m3u8, vod_id)) if m3u8 else '',
        }
        return {"list": [vod]}

    # ── 搜索 ──
    def searchContent(self, key, quick=False, pg="1"):
        d = self._api("vod", {"c": "t1", "name": str(key), "page": 1, "limit": 24})
        if not d or not d.get('data'):
            return {"list": []}
        data = d['data']
        vlist = [self._fmt_vod(v) for v in (data.get('videos') or [])
                 if isinstance(v, dict) and 'href' not in v]
        return {"list": vlist}

    # ── 播放 ──
    def playerContent(self, flag, ids, vipFlags=None):
        url = str(ids)
        # 从 URL 反查视频 id（detailContent 已在 m3u8 URL 附加 &vid=）
        m = re.search(r'[?&]vid=(\d+)', url)
        vid = m.group(1) if m else self._last_vod_id
        # auth_key 过期自动续期：签名约1小时有效，播放器缓存详情/历史记录
        # 直接播放时可能已过期，反查 id 重新请求拿新 URL
        m = re.search(r'auth_key=(\d+)', url)
        if m and int(m.group(1)) < time.time() + 300 and vid:
            try:
                d = self._api("vod/" + str(vid), {"c": "t1"})
                if d and d.get('data'):
                    u = (d['data'].get('video') or {}).get('url')
                    if u:
                        url = self._with_vid(u, str(vid))
            except Exception:
                pass
        # header 必须为 dict（JSON 对象）：OK影视/羊壳的 Json.toMap 只认对象，
        # 字符串格式会解析成空 Map 导致无 Referer → m3u8 403
        return {"parse": 0, "url": url,
                "header": {"User-Agent": UA, "Referer": BASE + "/"}}

    @staticmethod
    def _with_vid(url, vid):
        """m3u8 URL 附加 &vid= 供播放时反查（不影响 CDN 签名校验）"""
        if 'vid=' in url:
            return url
        return url + ('&' if '?' in url else '?') + 'vid=' + str(vid)

    # ── 工具 ──
    @staticmethod
    def _pic_proxy(pic):
        """封面走本地代理：proxy://do=py&url=ENC —— OK影视/羊壳 请求本地服务器，
        Python 侧 localProxy 带 Referer 取图，解决防盗链封面 403（不依赖 @Referer= 语法）"""
        return "proxy://do=py&url=" + quote(pic, safe='')

    def _fmt_vod(self, v):
        return {
            "vod_id": str(v.get('id', '')),
            "vod_name": v.get('name', ''),
            "vod_pic": self._pic_proxy(v.get('enc_img', '') or ''),
            "vod_remarks": v.get('time', ''),
        }

    # ── 图片本地代理（OK影视/羊壳 proxy:// 协议）──
    def localProxy(self, param):
        try:
            if isinstance(param, str):
                param = json.loads(param)
            url = (param or {}).get('url', '')
            if url and url.startswith('http'):
                code, mime, data = self.http.get_raw(url)
                if code == 200 and data:
                    # 91n 封面 CDN 返回 XOR 0x88 加密的 JPEG（前端 JS 解密显示），
                    # 这里解密还原成有效图片；非加密内容 XOR 后不是 JPEG 则原样返回
                    dec = bytes(b ^ 0x88 for b in data)
                    if dec[:3] == b'\xff\xd8\xff':
                        data = dec
                    return [200, 'image/jpeg', data, {}]
        except Exception:
            pass
        return [404, 'text/plain', b'', {}]

    def isVideoFormat(self, url):
        return True
