# coding: utf-8
import re
import json
import sys
import base64
import ssl
import socket
import threading
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.append('..')
from base.spider import Spider

SITE = "https://d39cgxtrya69tg.cloudfront.net"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
IMG_KEY = b"2019ysapp7527"
CATEGORIES = [
    {'type_id': '/category/jinri/', 'type_name': '今日吃瓜'},
    {'type_id': '/category/ai-egao/', 'type_name': 'AI成人短剧'},
    {'type_id': '/category/tuite/', 'type_name': '推特网黄'},
    {'type_id': '/category/xiaoyuan/', 'type_name': '校园黑料'},
    {'type_id': '/category/wanghong/', 'type_name': '网红黑料'},
    {'type_id': '/category/hot/', 'type_name': '热门大瓜'},
    {'type_id': '/category/toboo/', 'type_name': '海角乱伦'},
    {'type_id': '/category/mingxingheiliao/', 'type_name': '明星黑料'},
    {'type_id': '/category/wuye/', 'type_name': '午夜AV'},
    {'type_id': '/category/tanhua/', 'type_name': '91探花'},
    {'type_id': '/category/lieqi/', 'type_name': '猎奇重口'},
    {'type_id': '/category/dongman/', 'type_name': '成人动漫'},
    {'type_id': '/category/meiri/', 'type_name': '每日大赛'},
]

_proxy_port = 0
_proxy_started = False
EMPTY_GIF = (b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00'
             b'\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,'
             b'\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;')


def _decode_img(data):
    key = IMG_KEY
    klen = len(key)
    raw = bytearray(data)
    for i in range(min(100, len(raw))):
        raw[i] ^= key[i % klen]
    return bytes(raw)


class _ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            real = urllib.parse.unquote(self.path[1:])
            if not real or not real.startswith('http'):
                self.send_response(404); self.end_headers(); return
            r = urllib.request.urlopen(urllib.request.Request(
                real, headers={'User-Agent': UA, 'Referer': SITE + '/'}),
                timeout=20, context=ssl._create_unverified_context())
            ct = r.headers.get('Content-Type', 'image/gif')
            data = _decode_img(r.read())
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Cache-Control', 'max-age=86400')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            self.send_response(200)
            self.send_header('Content-Type', 'image/gif')
            self.end_headers()
            self.wfile.write(EMPTY_GIF)

    def log_message(self, fmt, *args):
        pass


def _start_proxy():
    global _proxy_port, _proxy_started
    if _proxy_started:
        return _proxy_port
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sk.bind(('127.0.0.1', 0))
    _proxy_port = sk.getsockname()[1]
    sk.close()
    server = ThreadingHTTPServer(('127.0.0.1', _proxy_port), _ProxyHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _proxy_started = True
    return _proxy_port


def _img_proxy_url(url):
    if not url:
        return ''
    return 'http://127.0.0.1:%d/%s' % (_start_proxy(), urllib.parse.quote(url, safe=''))


class Spider(Spider):
    def getName(self):
        return "69吃瓜网"

    def init(self, extend):
        if extend:
            self.host = extend.get('host', SITE)
        else:
            self.host = SITE
        self.headers = {'User-Agent': UA, 'Referer': self.host + '/'}
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE
        _start_proxy()

    def _fetch(self, url, referer=None):
        hdrs = {'User-Agent': UA}
        if referer:
            hdrs['Referer'] = referer
        req = urllib.request.Request(url, headers=hdrs)
        try:
            resp = urllib.request.urlopen(req, context=self._ssl_ctx, timeout=25)
        except Exception:
            resp = urllib.request.urlopen(req, context=ssl._create_unverified_context(), timeout=25)
        return resp.read().decode('utf-8', errors='replace')

    def _fix(self, u):
        if not u:
            return ''
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('/'):
            return self.host + u
        if not u.startswith('http'):
            return self.host + '/' + u
        return u

    def _items(self, html):
        out = []
        seen = set()
        # 类型1：videoBox（分类/首页）—— h2.videoTitle 标题
        links = re.findall(r'<a href="(/archives/[^/]+/)"[^>]*class="videoCardHitArea"', html)
        cards = re.findall(
            r'videoCover[^>]*data-src="([^"]+)"[^>]*>.*?'
            r'videoTitle"[^>]*>(.*?)</h2>',
            html, re.S)
        for i, (pic, title) in enumerate(cards):
            try:
                title = re.sub(r'<[^>]+>', '', title).strip()
                if not title:
                    continue
                slug = links[i] if i < len(links) else ''
                if not slug or slug in seen:
                    continue
                seen.add(slug)
                out.append({'vod_id': 'arch_' + base64.b64encode(slug.encode()).decode(),
                            'vod_name': title, 'vod_pic': _img_proxy_url(pic), 'vod_remarks': ''})
            except Exception:
                continue
        # 类型2：searchListCard（搜索结果）—— a aria-label 是标题
        slinks = re.findall(r'<a href="(/archives/[^/]+/)"[^>]*class="searchListCard__link"'
                            r'[^>]*aria-label="([^"]*)"', html)
        simgs = re.findall(r'searchListCard__image[^>]*data-src="([^"]+)"', html)
        for i, (slug, title) in enumerate(slinks):
            try:
                title = title.strip()
                if not title or slug in seen:
                    continue
                seen.add(slug)
                pic = simgs[i] if i < len(simgs) else ''
                out.append({'vod_id': 'arch_' + base64.b64encode(slug.encode()).decode(),
                            'vod_name': title, 'vod_pic': _img_proxy_url(pic), 'vod_remarks': ''})
            except Exception:
                continue
        return out

    def homeContent(self, filter):
        h = self._fetch(self.host + "/")
        return {'class': CATEGORIES, 'list': self._items(h)}

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        if tid is None or tid == '':
            tid = '/category/jinri/'
        pg = 1 if (pg is None or pg == '') else int(pg)
        if tid.startswith('/category/'):
            base = self.host + tid.rstrip('/')
        else:
            base = self.host + tid
        url = base if pg == 1 else base + '/' + str(pg)
        h = self._fetch(url)
        out = self._items(h)
        type_name = str(tid)
        for c in CATEGORIES:
            if c['type_id'] == tid:
                type_name = c['type_name']
                break
        pagecount = 99 if out else 1
        if 'nextBtn' not in h:
            pagecount = pg
        return {'list': out, 'page': pg, 'pagecount': pagecount, 'limit': 20, 'total': pagecount * 20, 'type_name': type_name}

    def detailContent(self, array):
        if not array:
            return {'list': []}
        vid = str(array[0]) if isinstance(array, list) else str(array).strip()
        real_url = ''
        if vid.startswith('arch_'):
            try:
                real_url = base64.b64decode(vid[5:]).decode('utf-8')
            except Exception:
                return {'list': []}
        elif vid.startswith('/archives/') or vid.startswith('http'):
            real_url = vid
        if not real_url:
            return {'list': []}
        detail_url = real_url if real_url.startswith('http') else self._fix(real_url)
        try:
            h = self._fetch(detail_url)
        except Exception:
            return {'list': []}
        m = re.search(r'data-url="([^"]+?\.m3u8[^"]*)"', h)
        if not m:
            return {'list': []}
        rel = m.group(1).replace('&amp;', '&')
        if rel.startswith('http'):
            play_url = rel
        else:
            play_url = self.host + '/h5/m3u8/' + rel
        # 标题
        name = ''
        t = re.search(r'<h1[^>]*>(.*?)</h1>', h)
        if t:
            name = re.sub(r'<[^>]+>', '', t.group(1)).strip()
        return {'list': [{'vod_id': vid, 'vod_name': name, 'vod_pic': '', 'type_name': '',
                          'vod_year': '', 'vod_area': '', 'vod_actor': '', 'vod_director': '',
                          'vod_content': '', 'vod_play_from': 'm3u8',
                          'vod_play_url': '正片$' + play_url, 'vod_remarks': ''}]}

    def searchContent(self, key, quick, pg='1'):
        try:
            url = self.host + '/search/' + urllib.parse.quote(key)
            h = self._fetch(url)
            items = self._items(h)
            return {'list': items, 'page': int(pg), 'pagecount': 1}
        except Exception:
            return {'list': [], 'page': int(pg), 'pagecount': 0}

    def playerContent(self, flag, id, vipFlags):
        return {'parse': 0, 'playUrl': '', 'url': id, 'header': json.dumps({'User-Agent': UA, 'Referer': self.host + '/'})}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return {}