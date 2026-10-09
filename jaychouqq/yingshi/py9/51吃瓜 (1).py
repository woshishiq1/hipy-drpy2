# -*- coding: utf-8 -*-
# @Author: Muse
# @Name: 51吃瓜
# TVBox Python 爬虫源 — 可直接放进 TVBox 的 py 源目录播放
# 站点: 51吃瓜网 https://chigua.com (Typecho/Mirages 主题，原创域名 51cg1.com)
# 线路失效只改下方 self.host 一处，或用 extend 传 {"host": "https://新域名"}
# 播放: 详情页 .dplayer 的 data-config JSON 里直接带 m3u8 直链 (AES-128 HLS)，免解析
# 图片: 站点 CDN (pic.ndhixj.cn) 的图是整文件 AES-128-CBC 加密的 (站内 image.*.js 里
#       decryptImage 解的，key/iv 见下方常量)，直链显示不了。源把封面走本地代理
#       (localProxy) 解密后再喂给播放器；盒子端无需任何设置。
#       如果某个盒子分支不支持 py 本地代理，图片会不出，但播放不受影响。

import sys
import re
import json
from urllib.parse import quote, unquote

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        pass

try:
    import requests
except Exception:
    requests = None

# ------------------------------------------------------------------
# 图片解密: AES-128-CBC + PKCS7，key/iv 为站点 JS 里的固定常量
# (cryjs.enc.Utf8.parse 还原，ASCII 直接作 key/iv 字节)
# ------------------------------------------------------------------
_IMG_KEY = b'f5d965df75336270'
_IMG_IV = b'97b60394abc2fbe1'

_IMG_MAGIC = (
    (b'\xff\xd8\xff', 'image/jpeg'),
    (b'\x89PNG\r\n\x1a\n', 'image/png'),
    (b'GIF8', 'image/gif'),
    (b'RIFF', 'image/webp'),  # 还要看 8..12 是不是 WEBP，误检率低，可接受
    (b'BM', 'image/bmp'),
)


def _img_type(data):
    if not data:
        return ''
    for magic, ctype in _IMG_MAGIC:
        if data[:len(magic)] == magic:
            return ctype
    return ''


def _decrypt_image_data(data):
    """先试 PyCryptodome，没有就纯 Python。失败返回 None。"""
    if not data or len(data) % 16 != 0:
        return None
    try:
        from Crypto.Cipher import AES as _AES
        out = _AES.new(_IMG_KEY, _AES.MODE_CBC, _IMG_IV).decrypt(data)
        return _pkcs7_strip(out)
    except Exception:
        pass
    try:
        return _aes128_cbc_decrypt(data, _IMG_KEY, _IMG_IV)
    except Exception:
        return None


def _pkcs7_strip(out):
    if not out:
        return None
    pad = out[-1]
    if 1 <= pad <= 16 and out[-pad:] == bytes([pad]) * pad:
        return out[:-pad]
    return out


# --- 纯 Python AES-128 (仅解密)，无 Crypto 时的兜底，已与 openssl 输出逐字节比对通过 ---
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
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
)
_INV_SBOX = [0] * 256
for _si, _sv in enumerate(_SBOX):
    _INV_SBOX[_sv] = _si
_INV_SBOX = tuple(_INV_SBOX)


def _gmul_table(n):
    tbl = []
    for a in range(256):
        p = 0
        x = a
        b = n
        for _ in range(8):
            if b & 1:
                p ^= x
            hi = x & 0x80
            x = (x << 1) & 0xFF
            if hi:
                x ^= 0x1B
            b >>= 1
        tbl.append(p)
    return tuple(tbl)


_M9 = _gmul_table(9)
_M11 = _gmul_table(11)
_M13 = _gmul_table(13)
_M14 = _gmul_table(14)
_RCON = (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36)


def _expand_key(key):
    w = list(key)
    while len(w) < 176:
        if len(w) % 16 == 0:
            t = w[-4:]
            rc = _RCON[len(w) // 16 - 1]
            t = [_SBOX[t[1]] ^ rc, _SBOX[t[2]], _SBOX[t[3]], _SBOX[t[0]]]
            for b in t:
                w.append(w[-16] ^ b)
        else:
            for b in w[-4:]:
                w.append(w[-16] ^ b)
    return [w[i * 16:(i + 1) * 16] for i in range(11)]


def _aes_decrypt_block(block, rks):
    s = [b ^ k for b, k in zip(block, rks[10])]
    for rnd in range(9, 0, -1):
        s[1], s[5], s[9], s[13] = s[13], s[1], s[5], s[9]
        s[2], s[6], s[10], s[14] = s[10], s[14], s[2], s[6]
        s[3], s[7], s[11], s[15] = s[7], s[11], s[15], s[3]
        s = [_INV_SBOX[b] for b in s]
        rk = rks[rnd]
        s = [b ^ k for b, k in zip(s, rk)]
        for c in range(4):
            i = c * 4
            a0, a1, a2, a3 = s[i], s[i + 1], s[i + 2], s[i + 3]
            s[i] = _M14[a0] ^ _M11[a1] ^ _M13[a2] ^ _M9[a3]
            s[i + 1] = _M9[a0] ^ _M14[a1] ^ _M11[a2] ^ _M13[a3]
            s[i + 2] = _M13[a0] ^ _M9[a1] ^ _M14[a2] ^ _M11[a3]
            s[i + 3] = _M11[a0] ^ _M13[a1] ^ _M9[a2] ^ _M14[a3]
    s[1], s[5], s[9], s[13] = s[13], s[1], s[5], s[9]
    s[2], s[6], s[10], s[14] = s[10], s[14], s[2], s[6]
    s[3], s[7], s[11], s[15] = s[7], s[11], s[15], s[3]
    s = [_INV_SBOX[b] for b in s]
    return bytes([b ^ k for b, k in zip(s, rks[0])])


def _aes128_cbc_decrypt(data, key, iv):
    if not data or len(data) % 16 != 0:
        return None
    rks = _expand_key(key)
    out = bytearray()
    prev = bytes(iv)
    for off in range(0, len(data), 16):
        block = data[off:off + 16]
        dec = _aes_decrypt_block(block, rks)
        out += bytes(x ^ y for x, y in zip(dec, prev))
        prev = block
    return _pkcs7_strip(bytes(out))


class Spider(BaseSpider):
    def getName(self):
        return '51吃瓜'

    def init(self, extend=''):
        self.host = 'https://bus.yutwjhms.cc'
        # self.host = 'https://chigua.com'
        self.ua = ('Mozilla/5.0 (X11; Linux x86_64; rv:156.0) Gecko/20100101 Firefox/156.0')
        self.header = {
            'User-Agent': self.ua,
            'Referer': self.host + '/',
        }
        # extend 可传 {"host": "https://新线路"} 覆盖
        try:
            if extend:
                ext = extend if isinstance(extend, dict) else json.loads(extend)
                if isinstance(ext, dict) and ext.get('host'):
                    self.host = str(ext['host']).rstrip('/')
                    self.header['Referer'] = self.host + '/'
        except Exception:
            pass
        self.classes = [
            {'type_id': 'wpcz', 'type_name': '今日吃瓜'},
            {'type_id': 'rdsj', 'type_name': '热门大瓜'},
            {'type_id': 'bkdg', 'type_name': '必看大瓜'},
            {'type_id': 'mrdg', 'type_name': '吃瓜榜单'},
            {'type_id': '51djc', 'type_name': '51剧场'},
            {'type_id': 'cbdj', 'type_name': 'AI成人短剧'},
            {'type_id': 'ysyl', 'type_name': '成人视频'},
            {'type_id': 'gcjq', 'type_name': '国产视频'},
            {'type_id': 'thjx', 'type_name': '探花精选'},
            {'type_id': 'whhj', 'type_name': '网黄合集'},
            {'type_id': 'whhl', 'type_name': '网红黑料'},
            {'type_id': 'whmx', 'type_name': '明星爆料'},
            {'type_id': 'xsxy', 'type_name': '学生校园'},
            {'type_id': 'hwcg', 'type_name': '海外吃瓜'},
            {'type_id': 'rrcg', 'type_name': '人人吃瓜'},
            {'type_id': 'ldcg', 'type_name': '领导干部'},
            {'type_id': 'lldd', 'type_name': '伦理道德'},
            {'type_id': 'snsn', 'type_name': '骚男骚女'},
            {'type_id': 'jpll', 'type_name': '软萌甜妹'},
            {'type_id': 'sjb', 'type_name': '竞技吃瓜'},
            {'type_id': 'qubk', 'type_name': '吃瓜看戏'},
            {'type_id': 'dcbq', 'type_name': '擦边撩骚'},
            {'type_id': 'zzs', 'type_name': '性爱技巧'},
            {'type_id': 'mrds', 'type_name': '每日大赛'},
            {'type_id': 'yczq', 'type_name': '原创博主'},
            {'type_id': 'cgxw', 'type_name': '吃瓜新闻'},
        ]

    # ---------------- 工具 ----------------

    def _abs(self, u):
        if not u:
            return ''
        u = str(u).strip()
        if re.match(r'^https?://', u, re.I):
            return u
        if u.startswith('//'):
            return 'https:' + u
        return self.host + (u if u.startswith('/') else '/' + u)

    def _clean(self, s):
        if not s:
            return ''
        s = str(s)
        # 先去掉标题里的角标块 (热搜 HOT 等), 再剥其余标签
        s = re.sub(r'<div class="wrap">[\s\S]*?</div>', '', s)
        s = re.sub(r'<[^>]+>', '', s)
        s = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), s)
        s = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)), s)
        s = s.replace('&nbsp;', ' ').replace('&amp;', '&')
        s = s.replace('&quot;', '"').replace('&#39;', "'").replace('&apos;', "'")
        s = s.replace('&lt;', '<').replace('&gt;', '>')
        return re.sub(r'\s+', ' ', s).strip()

    def _fetch(self, url):
        # 优先用框架自带的 fetch（走 OkHttp），没有再用 requests
        try:
            if hasattr(super(), 'fetch'):
                res = super().fetch(url, headers=self.header)
                if isinstance(res, dict):
                    return res.get('content') or res.get('text') or ''
                if hasattr(res, 'text'):
                    return res.text or ''
                return str(res or '')
        except Exception:
            pass
        if requests is None:
            import urllib.request
            req = urllib.request.Request(url, headers=self.header)
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode('utf-8', errors='ignore')
        r = requests.get(url, headers=self.header, timeout=15)
        return r.content.decode('utf-8', errors='ignore') if r.content else ''

    def _fetch_bytes(self, url):
        try:
            if hasattr(super(), 'fetch'):
                res = super().fetch(url, headers=self.header)
                if isinstance(res, dict):
                    c = res.get('content')
                    if isinstance(c, bytes):
                        return c
                    if isinstance(c, str):
                        return c.encode('utf-8', errors='ignore')
                if hasattr(res, 'content') and isinstance(res.content, bytes):
                    return res.content
        except Exception:
            pass
        if requests is None:
            import urllib.request
            req = urllib.request.Request(url, headers=self.header)
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read()
        r = requests.get(url, headers=self.header, timeout=20)
        return r.content or b''

    def _pic(self, url):
        """封面图走本地代理解密 (站点图被 AES 加密，直链打不开)。"""
        url = self._abs(url)
        if not url:
            return ''
        if 'proxy' in url and 'url=' in url:
            return url
        base = ''
        try:
            if hasattr(super(), 'getProxyUrl'):
                base = super().getProxyUrl()
        except Exception:
            base = ''
        if not base:
            base = 'http://127.0.0.1:9978/proxy?do=py'
        return base + '&url=' + quote(url, safe='')

    def _pagecount(self, html, cur):
        """从 page-navigator 里取最大页码"""
        m = re.search(r'<ul class="page-navigator">([\s\S]*?)</ul>', html)
        if not m:
            return 9999
        nums = [int(x) for x in re.findall(r'href="[^"]*?(\d+)/"', m.group(1))]
        return max(nums) if nums else 9999

    def _parse_list(self, html):
        result = []
        seen = set()
        if not html:
            return result
        for am in re.finditer(r'<article\b[\s\S]*?</article>', html):
            block = am.group(0)
            hm = re.search(r'href="/archives/(\d+)/"', block)
            if not hm:
                continue  # 外链广告卡跳过
            vid = hm.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            tm = re.search(r'post-card-title"[^>]*>([\s\S]*?)</h2>', block)
            name = self._clean(tm.group(1)) if tm else ''
            if not name:
                continue
            pm = re.search(r"loadBannerDirect\('([^']+)'", block)
            pic = self._pic(pm.group(1)) if pm else ''
            dm = re.search(r'datePublished" content="([^"]+)"', block)
            remarks = dm.group(1)[:10] if dm else ''
            result.append({
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_remarks': remarks,
            })
        return result

    # ---------------- TVBox 接口 ----------------

    def homeContent(self, filter):
        return {'class': self.classes, 'filters': {}}

    def homeVideoContent(self):
        html = self._fetch(self.host + '/')
        lst = self._parse_list(html)[:20]
        return {'list': lst}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg)
        except Exception:
            page = 1
        tid = str(tid or 'wpcz')
        if page <= 1:
            url = f'{self.host}/category/{tid}/'
        else:
            url = f'{self.host}/category/{tid}/{page}/'
        html = self._fetch(url)
        lst = self._parse_list(html)
        return {
            'list': lst,
            'page': page,
            'pagecount': self._pagecount(html, page),
            'limit': len(lst) if lst else 25,
            'total': 999999,
        }

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ''
        m = re.search(r'(\d+)', vid)
        real_id = m.group(1) if m else vid
        url = f'{self.host}/archives/{real_id}/'
        html = self._fetch(url)
        if not html:
            return {'list': []}

        # 标题
        tm = re.search(r'<meta property="og:title" content="([^"]*)"', html)
        if not tm:
            tm = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html)
        name = self._clean(tm.group(1)) if tm else ''

        # 简介
        cm = re.search(r'<meta property="og:description" content="([^"]*)"', html)
        content = self._clean(cm.group(1)) if cm else ''

        # 封面: 正文第一张真实图 (data-xkrkllgl)
        pm = re.search(r'data-xkrkllgl="([^"]+)"', html)
        pic = self._pic(pm.group(1)) if pm else ''

        ym = re.search(r'dateModified" content="(\d{4})', html)
        year = ym.group(1) if ym else ''

        # 选集: 所有 .dplayer，data-config JSON 直出 m3u8
        eps = []
        type_name = ''
        seen = set()
        pat = re.compile(
            r'class="dplayer"[^>]*data-video_title="([^"]*)"[^>]*data-config=\'(\{[\s\S]*?\})\''
        )
        for bm in pat.finditer(html):
            ep_title = self._clean(bm.group(1))
            play_url = ''
            try:
                cfg = json.loads(bm.group(2))
                play_url = (cfg.get('video') or {}).get('url') or ''
            except Exception:
                um = re.search(r'"url"\s*:\s*"([^"]+?\.m3u8[^"]*)"', bm.group(2))
                if um:
                    play_url = um.group(1).replace('\\/', '/')
            if not play_url or play_url in seen:
                continue
            seen.add(play_url)
            if not type_name:
                tvm = re.search(r'data-video_type_name="([^"]*)"', bm.group(0))
                type_name = self._clean(tvm.group(1)) if tvm else ''
            if len(eps) == 0 and (not ep_title or ep_title == name):
                ep_name = '播放'
            else:
                ep_name = ep_title or f'第{len(eps) + 1}集'
            # 片名本身就是标题+序号时，压成序号更易读
            if name and ep_name.startswith(name) and len(ep_name) > len(name):
                ep_name = ep_name[len(name):].strip() or ep_name
            ep_name = ep_name.replace('$', '＄').replace('#', '＃')
            eps.append(f'{ep_name}${play_url}')

        vod = {
            'vod_id': vid,
            'vod_name': name,
            'type_name': type_name,
            'vod_year': year,
            'vod_area': '',
            'vod_remarks': f'{type_name} · {year}' if (type_name or year) else '',
            'vod_actor': '',
            'vod_director': '',
            'vod_pic': pic,
            'vod_content': content,
            'vod_play_from': '51吃瓜',
            'vod_play_url': '#'.join(eps),
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg='1'):
        try:
            page = int(pg)
        except Exception:
            page = 1
        kw = quote(str(key), safe='')
        if page <= 1:
            url = f'{self.host}/search/{kw}/'
        else:
            url = f'{self.host}/search/{kw}/{page}/'
        html = self._fetch(url)
        lst = self._parse_list(html)
        return {
            'list': lst,
            'page': page,
            'pagecount': self._pagecount(html, page),
        }

    def playerContent(self, flag, id, vipFlags):
        # detailContent 已经把 m3u8 直链放进 vod_play_url，直接播
        play_url = str(id or '')
        return {
            'parse': 0,
            'jx': 0,
            'playUrl': '',
            'url': play_url,
            'header': {
                'User-Agent': self.ua,
                'Referer': self.host + '/',
            },
        }

    def localProxy(self, param):
        """图片代理: 拉原图 -> AES 解密 -> 返回明文图。"""
        try:
            if not isinstance(param, dict):
                return None
            url = param.get('url') or ''
            if not url:
                return None
            # 框架可能已解码、也可能原样传编码串: 不以 http(s):// 开头就先解码一次
            if '%3' in url or not url.lower().startswith(('http://', 'https://')):
                url = unquote(url)
            data = self._fetch_bytes(url)
            if not data:
                return [404, 'text/plain', b'']
            # 未加密的图 (头就是图片魔数) 直接回
            ctype = _img_type(data)
            if ctype:
                return [200, ctype, data]
            dec = _decrypt_image_data(data)
            if dec:
                ctype = _img_type(dec) or 'image/jpeg'
                return [200, ctype, dec]
            return [200, 'application/octet-stream', data]
        except Exception:
            return None

    def isVideoFormat(self, url):
        return '.m3u8' in str(url) or '.mp4' in str(url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass
