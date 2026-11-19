# -*- coding: utf-8 -*-
"""
51吃瓜 Python spider（影视壳用）

由海阔视界规则「51吃瓜 v21」（作者 Zaka）转换而来。
转换映射：海阔 find_rule -> categoryContent，detail_find_rule -> detailContent，
searchFind -> searchContent，列表 lazyRule / 详情播放按钮 -> playerContent。

注意：
1. 域名自动切换：v21 的 5 个域名按顺序试，第一个出文章的胜出，
   列表/搜索/详情/播放都走同一套切换逻辑。
2. 缩略图加密：/xiao/、/upload/upload/、/upload_01/、/uploads/ 开头的图
   是 AES-128-CBC 加密图床（key f5d965df75336270，iv 97b60394abc2fbe1，
   与海阔 v21 用的同一套），原图地址直接拿去显示是一堆乱码、所以没有缩略图。
   本 spider 把这类图改成壳的本地代理地址（127.0.0.1:9978/proxy），壳取图时
   回调 localProxy，spider 现取现解密成 JPEG 再返回；非加密图仍走原地址。
   若你那个壳的本地代理端口不是 9978，改文件头的 PROXY_BASE 即可。
3. 纯图帖：没有视频流时 playerContent 回 parse=1 打开原帖，不会硬把图片当视频播。
4. 精选（homeVideoContent）没有翻页接口：壳的精选页只拉一次、没有页码参数，
   17RIP 样例也是这样，所以精选本身做不出“下一页”。折中办法是精选一次
   合并今日吃瓜前 3 页（75 条，去重），往下刷能多看；真要翻页进分类页，
   今日吃瓜有 3151 页。壳里几列几行是壳的显示设置，spider 不管，由壳里调。
"""

import re
import json
import html as _html
from urllib.parse import quote, unquote, urlparse, parse_qs

import requests

UA = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36'

DOMAINS = [
    'https://at.aygsjxzi.cc',
    'https://chigua.com',
    'https://51cg1.com',
    'https://b79kj.avsedgssg.cc',
    'https://amazing.mmxpvspw.cc',
]

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        pass

# v21 的 28 个分类，原样照搬（type_id 用 slug，壳传回来的 tid 就是它）
CLASSES = [
    {'type_name': '今日吃瓜', 'type_id': 'wpcz'},
    {'type_name': 'AI成人短剧', 'type_id': 'cbdj'},
    {'type_name': '每日大赛', 'type_id': 'mrds'},
    {'type_name': '网黄合集', 'type_id': 'whhj'},
    {'type_name': '吃瓜榜单', 'type_id': 'mrdg'},
    {'type_name': '瓜友点播', 'type_id': 'qghj'},
    {'type_name': '热门大瓜', 'type_id': 'rdsj'},
    {'type_name': '必看大瓜', 'type_id': 'bkdg'},
    {'type_name': '成人视频', 'type_id': 'ysyl'},
    {'type_name': '伦理道德', 'type_id': 'lldd'},
    {'type_name': '国产视频', 'type_id': 'gcjq'},
    {'type_name': '探花精选', 'type_id': 'thjx'},
    {'type_name': '学生校园', 'type_id': 'xsxy'},
    {'type_name': '网红黑料', 'type_id': 'whhl'},
    {'type_name': '骚男骚女', 'type_id': 'snsn'},
    {'type_name': '明星爆料', 'type_id': 'whmx'},
    {'type_name': '海外吃瓜', 'type_id': 'hwcg'},
    {'type_name': '人人吃瓜', 'type_id': 'rrcg'},
    {'type_name': '领导干部', 'type_id': 'ldcg'},
    {'type_name': '软萌甜妹', 'type_id': 'jpll'},
    {'type_name': '竞技吃瓜', 'type_id': 'sjb'},
    {'type_name': '吃瓜看戏', 'type_id': 'qubk'},
    {'type_name': '擦边撩骚', 'type_id': 'dcbq'},
    {'type_name': '性爱技巧', 'type_id': 'zzs'},
    {'type_name': '吃瓜新闻', 'type_id': 'cgxw'},
    {'type_name': '51原创', 'type_id': 'yczq'},
    {'type_name': '51剧场', 'type_id': '51djc'},
    {'type_name': '往期活动', 'type_id': '51hd'},
]

CAT_PATH = {c['type_id']: '/category/%s/' % c['type_id'] for c in CLASSES}

# 壳的本地代理地址（TVBox 系默认 9978；若壳不同，改这里）
PROXY_BASE = 'http://127.0.0.1:9978/proxy'
IMG_KEY = b'f5d965df75336270'
IMG_IV = b'97b60394abc2fbe1'


def _is_enc_img(url):
    u = str(url or '')
    return ('/xiao/' in u or '/upload/upload/' in u
            or '/upload_01/' in u or '/uploads/' in u)


# ---- AES-128-CBC 解密：优先用库（快），库没有时用下面这套纯 Python 兜底 ----
_AES_SBOX = [
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
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
]
_AES_INV_SBOX = [0] * 256
for _i, _v in enumerate(_AES_SBOX):
    _AES_INV_SBOX[_v] = _i


def _aes_gmul(a, b):
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= 0x1b
        b >>= 1
    return p


def _aes_cbc_decrypt_pure(data, key, iv):
    rcon = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36]
    w = list(key)
    for i in range(16, 176, 4):
        t = [w[i - 4], w[i - 3], w[i - 2], w[i - 1]]
        if i % 16 == 0:
            t = [_AES_SBOX[x] for x in (t[1], t[2], t[3], t[0])]
            t[0] ^= rcon[(i // 16) - 1]
        w.extend([w[i - 16] ^ t[0], w[i - 15] ^ t[1], w[i - 14] ^ t[2], w[i - 13] ^ t[3]])
    rk = [w[r * 16:(r + 1) * 16] for r in range(11)]

    def _dec_block(block):
        s = [block[i] ^ rk[10][i] for i in range(16)]
        for r in range(9, 0, -1):
            t = s[:]
            s = [0] * 16
            s[1], s[5], s[9], s[13] = t[13], t[1], t[5], t[9]
            s[2], s[6], s[10], s[14] = t[10], t[14], t[2], t[6]
            s[3], s[7], s[11], s[15] = t[7], t[11], t[15], t[3]
            s[0], s[4], s[8], s[12] = t[0], t[4], t[8], t[12]
            s = [_AES_INV_SBOX[x] for x in s]
            s = [s[i] ^ rk[r][i] for i in range(16)]
            out = [0] * 16
            for c in range(4):
                j = c * 4
                out[j] = _aes_gmul(s[j], 0x0e) ^ _aes_gmul(s[j + 1], 0x0b) ^ _aes_gmul(s[j + 2], 0x0d) ^ _aes_gmul(s[j + 3], 0x09)
                out[j + 1] = _aes_gmul(s[j], 0x09) ^ _aes_gmul(s[j + 1], 0x0e) ^ _aes_gmul(s[j + 2], 0x0b) ^ _aes_gmul(s[j + 3], 0x0d)
                out[j + 2] = _aes_gmul(s[j], 0x0d) ^ _aes_gmul(s[j + 1], 0x09) ^ _aes_gmul(s[j + 2], 0x0e) ^ _aes_gmul(s[j + 3], 0x0b)
                out[j + 3] = _aes_gmul(s[j], 0x0b) ^ _aes_gmul(s[j + 1], 0x0d) ^ _aes_gmul(s[j + 2], 0x09) ^ _aes_gmul(s[j + 3], 0x0e)
            s = out
        t = s[:]
        s = [0] * 16
        s[1], s[5], s[9], s[13] = t[13], t[1], t[5], t[9]
        s[2], s[6], s[10], s[14] = t[10], t[14], t[2], t[6]
        s[3], s[7], s[11], s[15] = t[7], t[11], t[15], t[3]
        s[0], s[4], s[8], s[12] = t[0], t[4], t[8], t[12]
        s = [_AES_INV_SBOX[x] for x in s]
        return [s[i] ^ rk[0][i] for i in range(16)]

    out = []
    prev = list(iv)
    for off in range(0, len(data), 16):
        block = list(data[off:off + 16])
        if len(block) < 16:
            break
        dec = _dec_block(block)
        out.extend([dec[i] ^ prev[i] for i in range(16)])
        prev = block
    if out:
        pad = out[-1]
        if 1 <= pad <= 16 and all(x == pad for x in out[-pad:]):
            out = out[:-pad]
    return bytes(out)


def _decrypt_img_bytes(data):
    if not data or len(data) % 16 != 0:
        return data
    # 1) pycryptodome（壳里常见）
    try:
        from Crypto.Cipher import AES
        plain = AES.new(IMG_KEY, AES.MODE_CBC, IMG_IV).decrypt(data)
        pad = plain[-1]
        if 1 <= pad <= 16:
            plain = plain[:-pad]
        if plain[:2] == b'\xff\xd8':
            return plain
    except Exception:
        pass
    # 2) cryptography
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        c = Cipher(algorithms.AES(IMG_KEY), modes.CBC(IMG_IV))
        d = c.decryptor()
        plain = d.update(data) + d.finalize()
        pad = plain[-1]
        if 1 <= pad <= 16:
            plain = plain[:-pad]
        if plain[:2] == b'\xff\xd8':
            return plain
    except Exception:
        pass
    # 3) 纯 Python 兜底（无依赖，慢一些但能出图）
    try:
        plain = _aes_cbc_decrypt_pure(data, IMG_KEY, IMG_IV)
        if plain[:2] == b'\xff\xd8':
            return plain
    except Exception:
        pass
    return data


class Spider(BaseSpider):
    def __init__(self):
        try:
            super(Spider, self).__init__()
        except Exception:
            pass
        self.init('')

    def init(self, extend=""):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': UA,
            'Referer': DOMAINS[0] + '/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        try:
            self.session.verify = False
        except Exception:
            pass
        return True

    def getName(self):
        return '51吃瓜'

    def _hdr(self, referer=None):
        return {'User-Agent': UA, 'Referer': referer or (DOMAINS[0] + '/')}

    def _get(self, url, referer=None):
        try:
            r = self.session.get(url, headers=self._hdr(referer), timeout=12, verify=False)
            r.encoding = 'utf-8'
            return r.text or ''
        except Exception:
            return ''

    def _get_bytes(self, url, referer=None):
        try:
            r = self.session.get(url, headers=self._hdr(referer), timeout=12, verify=False)
            return r.content or b''
        except Exception:
            return b''

    def _pic_url(self, url):
        """加密图走本地代理，非加密图走原地址。"""
        if not url:
            return ''
        if _is_enc_img(url):
            return '%s?do=img&url=%s' % (PROXY_BASE, quote(url, safe=''))
        return url

    def localProxy(self, param):
        """壳取缩略图时回调：param 里带原图 url，返回解密后的 JPEG 字节。
        兼容几种传参：dict（含 url/img/pic/src）、查询串、直接 url 字符串。"""
        try:
            url = ''
            if isinstance(param, dict):
                for k in ('url', 'img', 'pic', 'src', 'image'):
                    if param.get(k):
                        url = str(param[k])
                        break
                if not url and param.get('do'):
                    # 壳可能把整个查询串塞进某个字段，兜底再解析一次
                    url = str(param)
            elif isinstance(param, str):
                url = param
            else:
                url = str(param or '')
            if 'url=' in url and not url.startswith('http'):
                qs = parse_qs(urlparse(url).query) if '?' in url else parse_qs(url)
                if qs.get('url'):
                    url = qs['url'][0]
            url = unquote(url).strip()
            # 嵌套一层 proxy 时再剥一层
            if 'url=' in url and '/proxy' in url:
                qs = parse_qs(urlparse(url).query)
                if qs.get('url'):
                    url = qs['url'][0]
            if not url.startswith('http'):
                return [404, 'text/plain; charset=utf-8', b'no pic url']
            data = self._get_bytes(url)
            if not data:
                return [404, 'text/plain; charset=utf-8', b'pic fetch failed']
            if data[:2] != b'\xff\xd8':
                data = _decrypt_img_bytes(data)
            return [200, 'image/jpeg', data]
        except Exception as e:
            return [500, 'text/plain; charset=utf-8', ('proxy error: %s' % e).encode('utf-8')]

    def proxy(self, param):
        return self.localProxy(param)

    def _abs(self, u, base):
        u = str(u or '').strip().replace('\\/', '/')
        if not u:
            return ''
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('http'):
            return u
        base = base or DOMAINS[0]
        return base + (u if u.startswith('/') else '/' + u)

    @staticmethod
    def _clean(s):
        s = re.sub(r'<[^>]+>', '', str(s or ''))
        s = _html.unescape(s)
        return re.sub(r'\s+', ' ', s).strip()

    @staticmethod
    def _page(pg):
        try:
            n = int(pg)
        except Exception:
            n = 1
        return n if n >= 1 else 1

    @staticmethod
    def _re(s, p):
        m = re.search(p, str(s or ''))
        return m.group(1) if m else ''

    def _count_posts(self, html):
        # 与 v21 一致：按 BlogPosting 的 article 切分计数，广告 article 没有 itemtype，不计入
        parts = re.split(r'<article[^>]*itemtype="http://schema\.org/BlogPosting"[^>]*>', html or '')
        return len(parts) - 1

    def _fetch_first_ok(self, build_url, want_m3u8=False, want_detail=False):
        """按域名顺序试，返回 (html, base)。
        默认（列表/搜索）：第一个出文章的胜出；
        want_m3u8：优先含 m3u8 的那份（播放）；
        want_detail：优先含 og:title 的那份（详情页不是列表，不能用文章数判断）。"""
        first = ('', DOMAINS[0])
        for base in DOMAINS:
            html = self._get(build_url(base))
            if not html:
                continue
            if not first[0]:
                first = (html, base)
            if want_m3u8 and 'm3u8' in html:
                return html, base
            if want_detail and 'og:title' in html:
                return html, base
            if not want_m3u8 and not want_detail and self._count_posts(html) > 0:
                return html, base
        return first

    def _list_url(self, base, path, page):
        if page <= 1:
            return base + path
        return base + path + str(page) + '/'

    def _pager(self, html, page, count):
        # 当前站分页在 <ul class="page-navigator"> 里，最后一页就是最大页码
        m = re.search(r'<ul class="page-navigator">([\s\S]*?)</ul>', html or '')
        if m:
            nums = [int(x) for x in re.findall(r'/(\d+)/">', m.group(1))]
            if nums:
                return max(1, max(nums))
        m2 = re.search(r'id="pageNum"[^>]*>\s*</[^>]+>\s*<[^>]*>\s*(\d+)', html or '')
        if m2:
            return max(1, int(m2.group(1)))
        return (page + 1 if count >= 25 else page)

    def _parse_list(self, html, base):
        out, seen = [], set()
        if not html:
            return out
        parts = re.split(r'<article[^>]*itemtype="http://schema\.org/BlogPosting"[^>]*>', html)
        parts = parts[1:]
        for b in parts:
            vid = self._re(b, r'/archives/(\d+)/')
            if not vid or vid in seen:
                continue
            seen.add(vid)
            title = self._clean(self._re(b, r'class="post-card-title"[^>]*>([\s\S]*?)(?:<div class="wrap"|</h2>)'))
            title = title.replace('热搜 HOT', '').strip()
            if not title:
                title = '吃瓜 ' + vid
            dt = self._re(b, r'itemprop="datePublished" content="(\d{4}-\d{2}-\d{2})')
            author = self._re(b, r'itemprop="author"[\s\S]*?<meta itemprop="name" content="([^"]+)"')
            # 缩略图：老站 loadBannerDirect，新站 z-bg-loader-url / x-bg-loader-url，兜底 data-src
            thumb = self._re(b, r"loadBannerDirect\('([^']+)'")
            if not thumb:
                thumb = self._re(b, r'[zx]-bg-loader-url="([^"]+)"')
            if not thumb:
                thumb = self._re(b, r'data-src="([^"]+)"')
            if thumb and ('51cg.png' in thumb or 'logo' in thumb):
                thumb = ''
            out.append({
                'vod_id': base + '/archives/' + vid + '/',
                'vod_name': title,
                'vod_pic': self._pic_url(self._abs(thumb, base)),
                'vod_remarks': (dt[5:].replace('-', '/') if dt else '') + (' · ' + author if author else ''),
            })
        return out

    def _list_result(self, items, page, pagecount):
        return {
            'page': page,
            'pagecount': pagecount,
            'limit': len(items) or 25,
            'total': pagecount * (len(items) or 25),
            'list': items,
            'hasMore': page < pagecount,
        }

    def homeContent(self, filter=None):
        return {'class': CLASSES}

    def homeVideoContent(self):
        # 精选无页码参数：一次合并前 3 页，壳里往下刷能多看 75 条
        merged, seen = [], set()
        try:
            for pg in (1, 2, 3):
                html, base = self._fetch_first_ok(
                    lambda b, p=pg: self._list_url(b, CAT_PATH['wpcz'], p))
                items = self._parse_list(html, base)
                if not items:
                    break
                for it in items:
                    vid = it.get('vod_id')
                    if vid in seen:
                        continue
                    seen.add(vid)
                    merged.append(it)
            return {'list': merged}
        except Exception:
            return {'list': merged}

    def categoryContent(self, tid, pg, filter=None, extend=None):
        page = self._page(pg)
        # tid 可能是 slug、完整 /category/ 路径，也可能是分类序号，全部兼容
        path = CAT_PATH.get(str(tid or '').strip())
        if not path:
            t = str(tid or '').strip()
            if t.startswith('/category/'):
                path = t if t.endswith('/') else t + '/'
            elif t.isdigit() and int(t) < len(CLASSES):
                path = CAT_PATH[CLASSES[int(t)]['type_id']]
            else:
                path = CAT_PATH['wpcz']
        ext = {}
        if isinstance(extend, dict):
            ext = extend
        elif isinstance(filter, dict):
            ext = filter
        cate = str(ext.get('cate') or '').strip()
        if cate:
            if cate in CAT_PATH:
                path = CAT_PATH[cate]
            elif cate.startswith('/category/'):
                path = cate if cate.endswith('/') else cate + '/'
        try:
            html, base = self._fetch_first_ok(lambda b: self._list_url(b, path, page))
            items = self._parse_list(html, base)
            return self._list_result(items, page, self._pager(html, page, len(items)))
        except Exception:
            return {'page': page, 'pagecount': page, 'limit': 25, 'total': 0,
                    'list': [], 'hasMore': False}

    def detailContent(self, ids):
        raw = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        vid = self._re(raw, r'/archives/(\d+)/')
        if not vid:
            vid = self._re(raw, r'(\d{3,})')
        if not vid:
            return {'list': []}

        def build(base):
            return base + '/archives/' + vid + '/'

        html, base = self._fetch_first_ok(build, want_detail=True)
        if not html:
            html, base = self._get(build(DOMAINS[0])), DOMAINS[0]
        detail_url = build(base)

        title = self._clean(self._re(html, r'<h1[^>]*class="post-title[^"]*"[^>]*>([\s\S]*?)</h1>'))
        if not title:
            title = self._clean(self._re(html, r'property="og:title" content="([^"]*)"'))
        if not title:
            title = '吃瓜 ' + vid
        desc = _html.unescape(self._re(html, r'property="og:description" content="([^"]*)"'))
        cover = _html.unescape(self._re(html, r'itemprop="image" content="([^"]*)"'))
        if not cover:
            pics0 = self._extract_pics(html, base)
            cover = pics0[0] if pics0 else ''
        dt = self._re(html, r'itemprop="datePublished" content="(\d{4}-\d{2}-\d{2})')

        vod = {
            'vod_id': raw,
            'vod_name': title,
            'vod_pic': self._pic_url(self._abs(cover, base)),
            'vod_remarks': dt,
            'vod_content': desc or '51吃瓜',
            # 两个线路：正片 + H265 备用，playerContent 按 flag 区分
            'vod_play_from': '51吃瓜$$$H265',
            'vod_play_url': '正片$%s$$$H265$%s' % (detail_url, detail_url),
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        page = self._page(pg)
        kw = quote(str(key or '').strip(), safe='')

        def build(base):
            url = '%s/search/%s/' % (base, kw)
            if page > 1:
                url += 'page/%d/' % page
            return url

        try:
            html, base = self._fetch_first_ok(build)
            items = self._parse_list(html, base)
            return self._list_result(items, page, self._pager(html, page, len(items)))
        except Exception:
            return {'page': page, 'pagecount': page, 'limit': 25, 'total': 0,
                    'list': [], 'hasMore': False}

    def _extract_pics(self, html, base):
        pics = []
        for pu in re.findall(r'data-xkrkllgl="([^"]+)"', html or ''):
            u = self._abs(pu, base)
            if u and u not in pics and len(pics) < 60:
                pics.append(u)
        if not pics:
            for iu in re.findall(r'(?:data-src|src)="([^"]+\.(?:jpg|jpeg|png|webp)(?:\?[^"]*)?)"', html or ''):
                if '51cg.png' in iu or 'logo' in iu:
                    continue
                u = self._abs(iu, base)
                if u and u not in pics and len(pics) < 60:
                    pics.append(u)
        return pics

    def _extract_video(self, html, h265=False):
        if not html:
            return ''
        # 首选 data-config JSON（最干净，不用处理转义斜杠）
        vid = ''
        try:
            cm = re.search(r"data-config='(\{[\s\S]*?\})'", html)
            if cm:
                cfg = json.loads(cm.group(1))
                key = 'video_h265' if h265 else 'video'
                v = cfg.get(key)
                if isinstance(v, dict) and v.get('url'):
                    return str(v['url']).strip().replace('\\/', '/')
                if not h265:
                    v0 = cfg.get('video')
                    if isinstance(v0, dict) and v0.get('url'):
                        u0 = str(v0['url'])
                        im = re.search(r'videos\d*/([a-f0-9]+)/', u0)
                        if im:
                            vid = im.group(1)
        except Exception:
            pass
        # 兜底：v21 的正则，优先含当前 vid 的那条带 auth_key 的 m3u8
        field = 'video_h265' if h265 else 'video'
        best = ''
        for mm in re.finditer(r'"%s":\{"url":"(https:[^"]+?\.m3u8\?auth_key=[^"]+)"' % field, html):
            uu = mm.group(1).replace('\\/', '')
            if vid and vid in uu:
                return uu
            if not best:
                best = uu
        if best:
            return best
        if h265:
            # H265 为空时回落正片，不让备用线路直接断掉
            return self._extract_video(html, h265=False)
        m = re.search(r'(https:[^"\'\s\\]+?\.m3u8(?:\?[^"\'\s\\]*)?)', html)
        if m:
            return m.group(1).replace('\\/', '')
        m = re.search(r'(https:[^"\'\s\\]+?\.mp4(?:\?[^"\'\s\\]*)?)', html)
        if m:
            return m.group(1).replace('\\/', '')
        return ''

    def playerContent(self, flag, id, vipFlags):
        raw = str(id or '').strip()
        vid = self._re(raw, r'/archives/(\d+)/')
        if not vid:
            vid = self._re(raw, r'(\d{3,})')
        if not vid:
            return {'parse': 1, 'url': self._abs(raw, DOMAINS[0]), 'header': self._hdr()}

        def build(base):
            return base + '/archives/' + vid + '/'

        # 优先原帖域名，再按域名顺序试含 m3u8 的那份
        html, base = '', DOMAINS[0]
        if raw.startswith('http'):
            html = self._get(raw, referer=raw)
            base = re.match(r'(https?://[^/]+)', raw).group(1) if re.match(r'(https?://[^/]+)', raw) else DOMAINS[0]
            if 'm3u8' not in html:
                html2, base2 = self._fetch_first_ok(build, want_m3u8=True)
                if html2:
                    html, base = html2, base2
        else:
            html, base = self._fetch_first_ok(build, want_m3u8=True)
        detail_url = build(base)

        h265 = '265' in str(flag or '')
        stream = self._extract_video(html, h265=h265)
        if stream:
            return {'parse': 0, 'url': stream, 'header': self._hdr(detail_url)}
        # 纯图帖或取不到流：回原帖，不硬播
        return {'parse': 1, 'url': detail_url, 'header': self._hdr(detail_url)}
