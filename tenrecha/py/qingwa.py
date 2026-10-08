# -*- coding: utf-8 -*-
"""
青蛙视频 / tev969 / qw9977 爬虫
适配苹果CMS加密模板：SHA256(key) + AES-256-ECB + PKCS7 + URL-Safe Base64
修复：首页改/home.html、图片明文、artdetail兼容、小说换行、去掉二次解析
"""

import sys
import re
import json
import requests
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib3
import base64
import hashlib
from html import unescape
from urllib.parse import quote, unquote, urljoin
from Crypto.Cipher import AES

urllib3.disable_warnings()
sys.path.append('..')

_PIC_SERVER = None

class _PicHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        try:
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            u = unquote(q.get('url', [''])[0])
            if not u.startswith('http'):
                self.send_response(404)
                self.end_headers()
                return
            r = requests.get(u, headers=Spider.headers, timeout=10, verify=False)
            data = r.content
            if data.startswith(b'base:'):
                parts = data.split(b':', 3)
                if len(parts) == 4 and (not parts[2] or parts[2] in (b'jpg', b'jpeg', b'png', b'webp', b'gif')):
                    imgkey = parts[1].decode()
                    k = hashlib.sha256(imgkey.encode('utf-8')).digest()
                    b = parts[3].decode('ascii').replace('-', '+').replace('_', '/')
                    b += '=' * (4 - len(b) % 4)
                    d = AES.new(k, AES.MODE_ECB).decrypt(base64.b64decode(b))
                    p = d[-1]
                    if 1 <= p <= 16:
                        d = d[:-p]
                    data = d
            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            try:
                self.send_response(404)
                self.end_headers()
            except Exception:
                pass

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def _start_proxy():
    global _PIC_SERVER
    if _PIC_SERVER is not None:
        return _PIC_SERVER.server_address[1]
    try:
        _PIC_SERVER = ThreadingHTTPServer(('127.0.0.1', 9978), _PicHandler)
    except OSError:
        try:
            _PIC_SERVER = ThreadingHTTPServer(('127.0.0.1', 0), _PicHandler)
        except Exception:
            return 0
    threading.Thread(target=_PIC_SERVER.serve_forever, daemon=True).start()
    return _PIC_SERVER.server_address[1]

def _pic_url(u):
    if not (u.startswith('http') and 'cklou.com' in u):
        return u
    port = _start_proxy()
    if not port:
        return u
    return 'http://127.0.0.1:%d/fy/pic?url=%s' % (port, quote(u, safe=''))
from base.spider import Spider


class Spider(Spider):
    session = requests.Session()
    host = "http://www.hff552.com"
    hosts = ["http://www.hff552.com", "http://www.dbb557.com"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "http://www.hff552.com/",
    }
    crypt_key = "nz52h7tsz68edd85"
    _aes_key = None
    _class_cache = None

    HARD_CLASSES = [
        {"type_name": "视频", "type_id": "2"},
        {"type_name": "国产视频", "type_id": "144"},
        {"type_name": "亚洲视频", "type_id": "13"},
        {"type_name": "主播直播", "type_id": "16"},
        {"type_name": "学生萝莉", "type_id": "22"},
        {"type_name": "里番动漫", "type_id": "23"},
        {"type_name": "玩具自慰", "type_id": "47"},
        {"type_name": "偷拍自拍", "type_id": "24"},
        {"type_name": "SM重口", "type_id": "25"},
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "亚洲无码", "type_id": "6"},
        {"type_name": "亚洲有码", "type_id": "7"},
        {"type_name": "无码破解", "type_id": "9"},
        {"type_name": "国产传媒", "type_id": "8"},
        {"type_name": "国产探花", "type_id": "127"},
        {"type_name": "网红博主", "type_id": "11"},
        {"type_name": "欧美无码", "type_id": "12"},
        {"type_name": "AV解说", "type_id": "116"},
    ]

    HARD_FILTERS = {
        "2": [{"key": "sub", "name": "子分类", "value": [
            {"n": "国产视频", "v": "144"}, {"n": "亚洲视频", "v": "13"},
            {"n": "主播直播", "v": "16"}, {"n": "学生萝莉", "v": "22"},
            {"n": "里番动漫", "v": "23"}, {"n": "玩具自慰", "v": "47"},
            {"n": "偷拍自拍", "v": "24"}, {"n": "SM重口", "v": "25"},
        ]}],
        "1": [{"key": "sub", "name": "子分类", "value": [
            {"n": "亚洲无码", "v": "6"}, {"n": "亚洲有码", "v": "7"},
            {"n": "无码破解", "v": "9"}, {"n": "国产传媒", "v": "8"},
            {"n": "国产探花", "v": "127"}, {"n": "网红博主", "v": "11"},
            {"n": "欧美无码", "v": "12"}, {"n": "AV解说", "v": "116"},
        ]}],
    }

    def getName(self): return "qingwa"
    def isVideoFormat(self, url): return bool(url and ('.m3u8' in url or '.mp4' in url or '.ts' in url or '.flv' in url))
    def manualVideoCheck(self): return False
    def destroy(self): pass
    def localProxy(self, param):
        try:
            u = param.split('url=')[1] if 'url=' in param else param
            u = unquote(u)
            if not u.startswith('http'):
                return [404, 'text/plain', '']
            r = self.session.get(u, headers=self.headers, timeout=10, verify=False)
            if r.status_code != 200:
                return [404, 'text/plain', '']
            data = r.content
            if data.startswith(b'base:'):
                parts = data.split(b':', 3)
                if len(parts) == 4 and (not parts[2] or parts[2] in (b'jpg', b'jpeg', b'png', b'webp', b'gif')):
                    imgkey = parts[1].decode()
                    k = hashlib.sha256(imgkey.encode('utf-8')).digest()
                    b = parts[3].decode('ascii').replace('-', '+').replace('_', '/')
                    b += '=' * (4 - len(b) % 4)
                    d = AES.new(k, AES.MODE_ECB).decrypt(base64.b64decode(b))
                    p = d[-1]
                    if 1 <= p <= 16:
                        d = d[:-p]
                    return [200, 'image/jpeg', d]
            return [200, 'image/jpeg', data]
        except Exception:
            return [404, 'text/plain', '']

    def _get_aes_key(self):
        if self._aes_key is None:
            self._aes_key = hashlib.sha256(self.crypt_key.encode('utf-8')).digest()
        return self._aes_key

    def _b64_decode(self, s):
        if not s:
            return ""
        s = s.replace('-', '+').replace('_', '/')
        while len(s) % 4 != 0:
            s += '='
        try:
            return base64.b64decode(s).decode('utf-8', errors='ignore')
        except Exception:
            return ""

    def _aes_decrypt(self, ciphertext_b64):
        if not ciphertext_b64:
            return ""
        try:
            s = ciphertext_b64.replace('-', '+').replace('_', '/')
            while len(s) % 4 != 0:
                s += '='
            data = base64.b64decode(s)
            if not data:
                return ""
            cipher = AES.new(self._get_aes_key(), AES.MODE_ECB)
            decrypted = cipher.decrypt(data)
            pad_len = decrypted[-1]
            if 1 <= pad_len <= 16:
                decrypted = decrypted[:-pad_len]
            return decrypted.decode('utf-8', errors='ignore')
        except Exception:
            return ""

    def init(self, extend=""):
        self.session.verify = False
        if extend and extend.startswith("http"):
            self.host = extend.rstrip("/")
            if self.host not in self.hosts:
                self.hosts.insert(0, self.host)
            self.headers["Referer"] = self.host + "/"
            self.session.headers.update(self.headers)

    def _fetch(self, url):
        for h in [self.host] + [x for x in self.hosts if x != self.host]:
            u = url.replace(self.host, h, 1) if h != self.host else url
            for _try in range(2):
                try:
                    r = self.session.get(u, headers=self.headers, timeout=12, verify=False)
                    r.encoding = 'utf-8'
                    if r.status_code == 200 and len(r.text) > 200:
                        self.host = h
                        self.headers['Referer'] = h + '/'
                        return r.text
                except Exception:
                    continue
        return ''

    def _pic_url(self, url):
        return _pic_url(url)

    def _fix(self, url):
        if not url:
            return ""
        url = unescape(url)
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return urljoin(self.host, url)
        if url.startswith("http"):
            return url
        return urljoin(self.host, "/" + url)

    def _clean(self, text):
        if not text:
            return ""
        return unescape(re.sub(r"<[^>]+>", "", str(text))).strip()

    def homeContent(self, filter):
        if self._class_cache is not None:
            return self._class_cache

        text = self._fetch(self.host + '/home.html')
        classes = []
        filters = {}
        seen = set()

        nav_blocks = re.findall(
            r'<div class="[^"]*type-name[^"]*"[^>]*>(.*?)<div class="[^"]*grid-link[^"]*"[^>]*>(.*?)</div>\s*</div>',
            text, re.S
        )
        for type_block, link_block in nav_blocks:
            parent_m = re.search(r'href="/(vod|art)type/(\d+)\.html".*?aesDecryptBase64\("([^"]+)"\)', type_block, re.S)
            if not parent_m:
                continue
            kind, parent_tid, parent_enc = parent_m.groups()
            if kind == "art":
                continue
            parent_name = self._aes_decrypt(parent_enc)
            if not parent_name:
                parent_name = f"分类{parent_tid}"
            if parent_tid not in seen:
                seen.add(parent_tid)
                classes.append({"type_name": parent_name, "type_id": parent_tid})
            sub_items = []
            sub_links = re.findall(
                r'href="/(vod|art)type/(\d+)\.html".*?aesDecryptBase64\("([^"]+)"\)',
                link_block, re.S
            )
            for kind, sub_tid, sub_enc in sub_links:
                if kind == "art":
                    continue
                if sub_tid in seen:
                    continue
                seen.add(sub_tid)
                sub_name = self._aes_decrypt(sub_enc)
                if not sub_name:
                    sub_name = f"子类{sub_tid}"
                classes.append({"type_name": sub_name, "type_id": sub_tid})
                sub_items.append({"n": sub_name, "v": sub_tid})
            if sub_items:
                filters[parent_tid] = [{"key": "sub", "name": "子分类", "value": sub_items}]

        if not classes:
            classes = self.HARD_CLASSES[:]
            filters = dict(self.HARD_FILTERS)
        art_links = re.findall(r'href="/arttype/(\d+)\.html"[^>]*>.*?aesDecryptBase64\("([^"]+)"\)', text, re.S)
        for atid, aenc in art_links:
            if ('art_' + atid) in seen:
                continue
            aname = self._aes_decrypt(aenc) or ('图库' + atid)
            seen.add('art_' + atid)
            classes.append({"type_name": aname, "type_id": 'art_' + atid})

        self._class_cache = {'class': classes, 'filters': filters, 'type': '影视'}
        return self._class_cache

    def homeVideoContent(self):
        text = self._fetch(self.host + '/home.html')
        items = self._parse_list(text, page=1, is_article=False).get('list', [])
        if not items:
            for tid in ['2', '1']:
                url = f'{self.host}/vodtype/{tid}.html'
                text = self._fetch(url)
                items = self._parse_list(text, page=1, is_article=False).get('list', [])
                if items:
                    break
        return {
            'list': items[:30],
            'page': 1,
            'pagecount': 2 if items else 1,
            'limit': len(items),
            'total': len(items)
        }

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        tid_str = str(tid)
        is_article = tid_str.startswith('art_')
        sub_tid = extend.get('sub', '') if extend else ''
        
        if sub_tid:
            tid_str = str(sub_tid)
            is_article = tid_str.startswith('art_')

        if is_article:
            tid_real = tid_str.replace('art_', '')
            url = f'{self.host}/arttype/{tid_real}-{page}.html' if page > 1 else f'{self.host}/arttype/{tid_real}.html'
            text = self._fetch(url)
            return self._parse_list(text, page, True)

        url = f'{self.host}/vodtype/{tid_str}-{page}.html' if page > 1 else f'{self.host}/vodtype/{tid_str}.html'
        text = self._fetch(url)
        return self._parse_list(text, page, False)

    def _extract_video_cards(self, text):
        cards = []
        for class_prefix in ['video-card', 'video-item', 'movie-item', 'film-item', 'vod-item', 'post-item']:
            pos = 0
            search_prefix = '<div class="' + class_prefix
            while True:
                start = text.find(search_prefix, pos)
                if start == -1:
                    break
                depth = 0
                i = start
                while i < len(text):
                    if text[i:i+4] == '<div':
                        depth += 1
                        i += 4
                    elif text[i:i+6] == '</div>':
                        depth -= 1
                        i += 6
                        if depth == 0:
                            cards.append(text[start:i])
                            pos = i
                            break
                    else:
                        i += 1
                else:
                    break
            if cards:
                break
        return cards

    def _parse_list(self, text, page=1, is_article=False):
        items = []
        if not text:
            return self._empty_list(page)

        cards = self._extract_video_cards(text)
        if cards:
            seen = set()
            for card in cards:
                if 'list-ad' in card or ('target="_blank"' in card and 'data-decrypt' not in card):
                    continue

                vid = ''
                is_art = False
                for vid_pat in [
                    r'href="/vodplay/(\d+)-\d+-\d+\.html"',
                    r'href="/voddetail/(\d+)\.html"',
                    r'href="/artdetail[/-](\d+)\.html"',
                    r'href="/vod/(\d+)\.html"',
                    r'href="/detail/(\d+)\.html"',
                    r'data-id="(\d+)"',
                ]:
                    vid_m = re.search(vid_pat, card)
                    if vid_m:
                        vid = vid_m.group(1)
                        is_art = 'artdetail' in vid_pat
                        break
                if not vid or vid in seen:
                    continue
                seen.add(vid)

                title = ''
                title_encs = re.findall(r'data-decrypt="([^"]+)"', card)
                for enc in title_encs:
                    dec = self._aes_decrypt(enc)
                    if dec and len(dec) > 1:
                        title = dec
                        break
                if not title:
                    alt_m = re.search(r'alt="([^"]*)"', card)
                    title = alt_m.group(1) if alt_m else ''
                if not title:
                    txt_m = re.search(r'<a[^>]+href="/(?:vodplay|voddetail|artdetail|vod|detail)[^"]+"[^>]*>([^<]+)</a>', card)
                    if txt_m:
                        title = self._clean(txt_m.group(1))
                if not title:
                    for h_pat in [r'<h2[^>]*>(.*?)</h2>', r'<h3[^>]*>(.*?)</h3>', r'<h4[^>]*>(.*?)</h4>', r'<h5[^>]*>(.*?)</h5>']:
                        h_m = re.search(h_pat, card, re.S)
                        if h_m:
                            title = self._clean(h_m.group(1))
                            if title:
                                break
                if not title:
                    title = f"未知{vid}"

                pic = ''
                img_block_m = re.search(r'<div class="video-card-image[^"]*">(.*?)</div>', card, re.S)
                if img_block_m:
                    img_block = img_block_m.group(1)
                    m = re.search(r'style=["\'][^"\']*background-image\s*:\s*url\(["\']?([^"\'()]+)["\']?\)', img_block, re.S)
                    if m:
                        pic = m.group(1).strip()
                    if not pic:
                        for pat in [r'data-original="([^"]+)"', r'data-src="([^"]+)"', r'src="([^"]+)"']:
                            m = re.search(pat, img_block)
                            if m:
                                pic = m.group(1)
                                break

                if not pic:
                    m = re.search(r'style=["\'][^"\']*background-image\s*:\s*url\(["\']?([^"\'()]+)["\']?\)', card, re.S)
                    if m:
                        pic = m.group(1).strip()
                    if not pic:
                        for pic_pat in [r'data-original="([^"]+)"', r'data-src="([^"]+)"', r'src="([^"]+)"']:
                            pic_m = re.search(pic_pat, card)
                            if pic_m:
                                pic = pic_m.group(1)
                                if pic and 'loading' not in pic and 'blank' not in pic:
                                    break
                pic = self._pic_url(self._fix(pic))

                remark = ''
                remark_m = re.search(r'<span[^>]*>(\d{2}:\d{2}:\d{2})</span>', card)
                if remark_m:
                    remark = remark_m.group(1)
                if not remark:
                    remark_m = re.search(r'<span[^>]*>([^<]{2,10})</span>', card)
                    if remark_m:
                        remark = remark_m.group(1).strip()

                items.append({
                    'vod_id': f'art_{vid}' if is_art else vid,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remark,
                })

        if not items and is_article:
            pattern = re.compile(
                r'<li[^>]*>.*?<a[^>]+href="/artdetail[/-](\d+)\.html"[^>]*>(?:<span[^>]*>.*?</span>)?\s*([^<]+)</a>.*?</li>',
                re.S
            )
            for m in pattern.finditer(text):
                vid, title = m.groups()
                title = self._clean(title)
                if title:
                    items.append({
                        'vod_id': f'art_{vid}',
                        'vod_name': title,
                        'vod_pic': '',
                        'vod_remarks': '',
                    })
            if not items:
                pattern2 = re.compile(
                    r'href="/artdetail[/-](\d+)\.html"[^>]*>(?:<[^>]+>)*\s*([^<]{2,})',
                    re.S
                )
                seen = set()
                for m in pattern2.finditer(text):
                    vid, title = m.groups()
                    title = self._clean(title)
                    if vid not in seen and len(title) > 1:
                        seen.add(vid)
                        items.append({
                            'vod_id': f'art_{vid}',
                            'vod_name': title,
                            'vod_pic': '',
                            'vod_remarks': '',
                        })

        pagecount = page + 1 if items else page
        maxpg = 1
        pg_links = re.findall(r'href="/(?:vod|art)type/\d+-(\d+)\.html"', text)
        for p in pg_links:
            try:
                if int(p) > maxpg:
                    maxpg = int(p)
            except:
                pass
        if maxpg > 1:
            pagecount = maxpg
        elif len(items) >= 24:
            pagecount = page + 1

        return {
            'list': items,
            'page': page,
            'pagecount': pagecount,
            'limit': len(items),
            'total': page * len(items) + 1
        }

    def _empty_list(self, page):
        return {'list': [], 'page': page, 'pagecount': page, 'limit': 0, 'total': 0}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        if vid.startswith('art_'):
            return self._art_detail(vid[4:])
        return self._vod_detail(vid)

    def _vod_detail(self, vid):
        url = f'{self.host}/vodplay/{vid}-1-1.html'
        text = self._fetch(url)

        if not text:
            return {'list': []}

        pj = None
        try:
            m = re.search(r'var\s+(player_aaaa|player_data|player|mac_player)\s*=\s*JSON\.parse\(aesDecryptBase64\("([^"]+)"\)\)', text)
            if m:
                raw = self._aes_decrypt(m.group(2))
                if raw:
                    pj = json.loads(raw)
        except Exception:
            pass

        title = ''
        if pj:
            title = (pj.get('vod_data') or {}).get('vod_name', '') or '' 
        title_block = re.search(r'<div class="single-video-title[^"]*">(.*?)</div>\s*</div>', text, re.S)
        if title_block:
            h2_m = re.search(r'<h2[^>]*data-decrypt="([^"]+)"', title_block.group(1), re.S)
            if h2_m:
                title = self._aes_decrypt(h2_m.group(1))
            if not title:
                dec_list = re.findall(r'data-decrypt="([^"]+)"', title_block.group(1))
                for enc in dec_list:
                    dec = self._aes_decrypt(enc)
                    if dec and len(dec) > 1:
                        title = dec
                        break

        if not title:
            dec_list = re.findall(r'data-decrypt="([^"]+)"', text)
            best = ''
            for enc in dec_list:
                dec = self._aes_decrypt(enc)
                if dec and len(dec) > len(best):
                    best = dec
            if len(best) > 1:
                title = best

        if not title:
            m = re.search(r'"vod_name":"([^"]+)"', text)
            if m:
                title = m.group(1)
        if not title:
            m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S)
            if m:
                title = self._clean(m.group(1))
        if not title:
            m = re.search(r'<h2[^>]*>(.*?)</h2>', text, re.S)
            if m:
                title = self._clean(m.group(1))
        if not title:
            m = re.search(r'<title>([^<]+)</title>', text)
            if m:
                title = m.group(1).replace('- 青蛙视频', '').replace('- qw9977', '').strip()

        cover = ''
        for pat in [
            r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
            r'data-original="(https?://[^"]+)"',
            r'<img[^>]+src="(https?://[^"]+)"[^>]*class="[^"]*img-fluid',
            r'data-src="(https?://[^"]+)"',
        ]:
            m = re.search(pat, text, re.S)
            if m:
                cover = m.group(1)
                if cover and 'loading' not in cover:
                    break
        cover = self._pic_url(self._fix(cover))

        content = ''
        m = re.search(r'"vod_content":"([^"]*)"', text)
        if m:
            content = m.group(1).replace('\\n', '\n').replace('\\r', '').replace('\\t', '')
        if not content:
            m = re.search(r'<div[^>]*class="[^"]*detail-content[^"]*"[^>]*>(.*?)</div>', text, re.S)
            if m:
                content = self._clean(m.group(1))

        play_from_list = []
        play_url_list = []

        sid_map = {}
        eps_all = re.findall(r'<a[^>]+href="(/vodplay/\d+-\d+-\d+\.html)"[^>]*>([^<]{1,12})</a>', text)
        for href, label in eps_all:
            m = re.search(r'/vodplay/\d+-(\d+)-(\d+)\.html', href)
            if not m or f'/vodplay/{vid}-' not in href:
                continue
            sid, nid = m.group(1), m.group(2)
            sid_map.setdefault(sid, {})[nid] = href

        if sid_map:
            for sid in sorted(sid_map.keys(), key=lambda x: int(x)):
                eps = sid_map[sid]
                name = '线路' + sid
                for href, idx, nm in re.findall(r'<a[^>]+href="(/vodplay/\d+-\d+-\d+\.html)"[^>]*data-index="(\d+)"[^>]*>([^<]{1,12})</a>', text):
                    if idx == sid:
                        name = nm.strip()
                        break
                items = []
                for nid in sorted(eps.keys(), key=lambda x: int(x)):
                    items.append(f'第{nid}集${eps[nid]}')
                play_from_list.append(name)
                play_url_list.append('#'.join(items))
        else:
            play_from_list.append('线路1')
            play_url_list.append(f'正片$/vodplay/{vid}-1-1.html')

        remark = ''
        m = re.search(r'class="[^"]*single-video-title[^"]*"[^>]*>.*?</h2>.*?<span[^>]*>([^<]{1,12})</span>', text, re.S)
        if m:
            remark = m.group(1).strip()
        year = ''
        m = re.search(r'<span[^>]*>(\d{4})</span>', text)
        if m:
            year = m.group(1)
        area = ''
        m = re.search(r'class="[^"]*single-video-info[^"]*"[^>]*>.*?<span[^>]*>([^<]{1,12})</span>', text, re.S)
        if m:
            area = m.group(1).strip()
        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': cover,
            'vod_content': content,
            'vod_remarks': remark,
            'vod_year': year,
            'vod_area': area,
            'vod_class': '',
            'vod_director': '',
            'vod_actor': '',
            'vod_play_from': '$$$'.join(play_from_list),
            'vod_play_url': '$$$'.join(play_url_list),
        }
        return {'list': [vod]}

    def _art_detail(self, vid):
        urls_to_try = [
            f'{self.host}/artdetail/{vid}.html',
            f'{self.host}/artdetail-{vid}.html',
        ]
        text = ''
        for url in urls_to_try:
            text = self._fetch(url)
            if text:
                break

        if not text:
            return {'list': []}

        title = ''
        title_block = re.search(r'<div class="single-video-title[^"]*">(.*?)</div>\s*</div>', text, re.S)
        if title_block:
            h2_m = re.search(r'<h2[^>]*data-decrypt="([^"]+)"', title_block.group(1), re.S)
            if h2_m:
                title = self._aes_decrypt(h2_m.group(1))
            if not title:
                dec_list = re.findall(r'data-decrypt="([^"]+)"', title_block.group(1))
                for enc in dec_list:
                    dec = self._aes_decrypt(enc)
                    if dec and len(dec) > 1:
                        title = dec
                        break

        if not title:
            for pat in [r'<h1[^>]*>(.*?)</h1>', r'<h2[^>]*>(.*?)</h2>', r'<title>([^<]+)</title>']:
                m = re.search(pat, text, re.S)
                if m:
                    title = self._clean(m.group(1))
                    if title:
                        break

        if not title:
            dec_list = re.findall(r'data-decrypt="([^"]+)"', text)
            best = ''
            for enc in dec_list:
                dec = self._aes_decrypt(enc)
                if dec and len(dec) > len(best):
                    best = dec
            if len(best) > 1:
                title = best

        if not title:
            title = f'文章{vid}'

        content_html = ''
        m = re.search(r'<div[^>]*data-decrypt="([^"]+)"[^>]*data-target="html"', text, re.S)
        if not m:
            m = re.search(r'<div[^>]*data-target="html"[^>]*data-decrypt="([^"]+)"', text, re.S)
        if m:
            content_html = self._aes_decrypt(m.group(1))

        if not content_html:
            selectors = [
                r'<div[^>]*class="content"[^>]*>(.*?)</div>',
                r'<div[^>]*class="[^"]*article-content[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*class="[^"]*post-content[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*class="[^"]*detail-content[^"]*"[^>]*>(.*?)</div>',
                r'<article[^>]*>(.*?)</article>',
                r'<div[^>]*class="[^"]*video-content[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*class="[^"]*text-content[^"]*"[^>]*>(.*?)</div>',
            ]
            for selector in selectors:
                m = re.search(selector, text, re.S)
                if m:
                    content_html = m.group(1)
                    if len(content_html) > 50:
                        break

        if not content_html:
            body = re.search(r'<body[^>]*>(.*?)</body>', text, re.S)
            if body:
                content_html = body.group(1)
                content_html = re.sub(r'<(header|nav|footer|aside)[^>]*>.*?</\1>', '', content_html, flags=re.S)

        imgs = re.findall(r'<img[^>]+(?:src|data-original|data-src)="([^"]+)"', content_html)
        img_decrypts = re.findall(r'<img[^>]+data-decrypt="([^"]+)"', content_html)
        for enc in img_decrypts:
            dec = self._aes_decrypt(enc)
            if dec and dec.startswith('http'):
                imgs.append(dec)

        big_imgs = []
        for img in imgs:
            low = img.lower()
            if any(x in low for x in ['loading', 'blank', 'logo', 'icon', 'avatar', 'smiley', 'ad.', 'gif', 'banner']):
                continue
            img = self._fix(img)
            if img.startswith('http') and img not in big_imgs:
                big_imgs.append(img)

        big_imgs = [self._pic_url(x) for x in big_imgs]
        if big_imgs:
            pics = '&&'.join(big_imgs)
            play_url = f'查看$pics://{pics}'
            vod = {
                'vod_id': f'art_{vid}',
                'vod_name': title,
                'vod_pic': big_imgs[0],
                'vod_content': f'共 {len(big_imgs)} 张',
                'vod_remarks': f'{len(big_imgs)}P',
                'vod_play_from': '图片',
                'vod_play_url': play_url,
                'vod_tag': 'image',
                'vod_player': '画',
            }
            return {'list': [vod]}

        txt = content_html
        txt = re.sub(r'<br\s*/?>', '\n', txt)
        txt = re.sub(r'<p>', '\n', txt)
        txt = re.sub(r'</p>', '\n', txt)
        txt = re.sub(r'<li>', '\n• ', txt)
        txt = re.sub(r'</li>', '\n', txt)
        txt = re.sub(r'<div>', '\n', txt)
        txt = re.sub(r'</div>', '\n', txt)
        txt = re.sub(r'<[^>]+>', '', txt)
        txt = re.sub(r'&nbsp;', ' ', txt)
        txt = re.sub(r'&[a-zA-Z]+;', '', txt)
        txt = re.sub(r'\n+', '\n').strip()

        if len(txt) > 12000:
            txt = txt[:12000] + '...'
        if not txt:
            txt = '暂无内容'

        novel_json = json.dumps({'title': title, 'content': txt}, ensure_ascii=False)
        play_url = f'阅读$novel://{novel_json}'
        vod = {
            'vod_id': f'art_{vid}',
            'vod_name': title,
            'vod_pic': '',
            'vod_content': '',
            'vod_remarks': '',
            'vod_play_from': '小说',
            'vod_play_url': play_url,
            'vod_tag': 'text',
            'vod_player': '书',
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = f'{self.host}/vodsearch/-------------.html?wd={quote(key)}&page={page}'
        text = self._fetch(url)
        items = self._parse_list(text, page, is_article=False).get('list', [])
        return {
            'list': items,
            'page': page,
            'pagecount': page + 1 if items else page,
            'limit': len(items),
            'total': page * len(items) + 1
        }

    def playerContent(self, flag, id, vipFlags=None):
        if id.startswith('novel://'):
            return {'parse': 0, 'url': id, 'header': '', 'vod_player': '书'}

        if id.startswith('pics://'):
            return {'parse': 0, 'playUrl': '', 'url': id, 'header': self.headers}

        if id.startswith('http'):
            return {
                'parse': 0,
                'url': id,
                'header': {'Referer': self.host + '/', 'User-Agent': self.headers['User-Agent']},
                'position': '0'
            }

        if id.startswith('/vodplay/'):
            url = self.host + id
        elif id.startswith('vodplay/'):
            url = f'{self.host}/{id}'
        else:
            url = f'{self.host}/vodplay/{id}'

        text = self._fetch(url)
        if not text:
            return {
                'parse': 0,
                'url': '',
                'header': {'Referer': self.host + '/', 'User-Agent': self.headers['User-Agent']},
                'position': '0'
            }

        m3u8 = ''
        try:
            m = re.search(r'var\s+(player_aaaa|player_data|player|mac_player)\s*=\s*JSON\.parse\(aesDecryptBase64\("([^"]+)"\)\)', text)
            if m:
                raw = self._aes_decrypt(m.group(2))
                if raw:
                    player = json.loads(raw)
                    u = player.get('url', '') or ''
                    if u.startswith('http'):
                        m3u8 = u
        except Exception:
            pass

        if not m3u8:
            m = re.search(r'var\s+(player_aaaa|player_data|player|mac_player)\s*=\s*JSON\.parse\("([^"]+)"\)', text)
            if m:
                try:
                    raw = self._b64_decode(m.group(2))
                    if raw:
                        player = json.loads(raw)
                        u = player.get('url', '') or ''
                        if u.startswith('http'):
                            m3u8 = u
                except Exception:
                    pass

        for var_name in ['player_aaaa', 'player_data', 'player', 'mac_player']:
            m = re.search(rf'var\s+{var_name}\s*=\s*(\{{[^<]*?\}})\s*</script>', text, re.S)
            if m:
                try:
                    player = json.loads(m.group(1))
                    raw_url = player.get('url', '')
                    if raw_url and isinstance(raw_url, str):
                        decoded = raw_url.strip()
                        if re.match(r'^[A-Za-z0-9+/=_-]{20,}$', decoded):
                            decoded = self._b64_decode(decoded)
                        if '%' in decoded:
                            try:
                                decoded = unquote(decoded)
                            except Exception:
                                pass
                        if decoded.startswith('http'):
                            m3u8 = decoded
                            break
                except Exception:
                    continue

        if not m3u8:
            m = re.search(r'<iframe[^>]+src="([^"]+)"', text, re.S)
            if m:
                iframe_src = m.group(1)
                iframe_url = iframe_src if iframe_src.startswith('http') else self._fix(iframe_src)
                iframe_text = self._fetch(iframe_url)
                if iframe_text:
                    for var_name in ['player_aaaa', 'player_data', 'player', 'mac_player']:
                        m2 = re.search(rf'var\s+{var_name}\s*=\s*(\{{[^<]*?\}})\s*</script>', iframe_text, re.S)
                        if m2:
                            try:
                                player = json.loads(m2.group(1))
                                raw_url = player.get('url', '')
                                if raw_url and isinstance(raw_url, str):
                                    decoded = raw_url.strip()
                                    if re.match(r'^[A-Za-z0-9+/=_-]{20,}$', decoded):
                                        decoded = self._b64_decode(decoded)
                                    if '%' in decoded:
                                        try:
                                            decoded = unquote(decoded)
                                        except Exception:
                                            pass
                                    if decoded.startswith('http'):
                                        m3u8 = decoded
                                        break
                            except Exception:
                                continue
                    if not m3u8:
                        m2 = re.search(r'["\'](https?://[^\s"<>]+?\.(?:m3u8|mp4|ts|flv))["\']', iframe_text)
                        if m2:
                            m3u8 = m2.group(1)

        if not m3u8:
            m = re.search(r'["\'](https?://[^\s"<>]+?\.(?:m3u8|mp4|ts|flv))["\']', text)
            if m:
                m3u8 = m.group(1)

        if not m3u8:
            m = re.search(r'unescape\(["\']([^"\']+)["\']\)', text)
            if m:
                try:
                    decoded = unquote(m.group(1))
                    if decoded.startswith('http'):
                        m3u8 = decoded
                except Exception:
                    pass

        if not m3u8:
            m = re.search(r'["\'](https?://[^\s"<>]+?)["\']', text)
            if m:
                m3u8 = m.group(1)

        if m3u8:
            return {
                'parse': 0,
                'url': m3u8,
                'header': {'Referer': self.host + '/', 'User-Agent': self.headers['User-Agent']},
                'position': '0'
            }

        return {
            'parse': 0,
            'url': url,
            'header': {'Referer': self.host + '/', 'User-Agent': self.headers['User-Agent']},
            'position': '0'
        }
