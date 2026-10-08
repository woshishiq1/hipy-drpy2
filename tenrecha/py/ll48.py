# -*- coding: utf-8 -*-
import sys
import re
import json
import base64
import threading
import requests
import urllib3
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import unquote, quote, urljoin

urllib3.disable_warnings()
sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def __init__(self): pass

# ===== 图片代理 =====
_proxy_port = 0
_proxy_started = False
_proxy_session = requests.Session()
_proxy_session.verify = False
_proxy_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://in30.ll48host.buzz/',
}
class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
class _ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            real_url = unquote(self.path[1:])
            if not real_url or not real_url.startswith('http'):
                self.send_response(404); self.end_headers(); return
            r = _proxy_session.get(real_url, headers=_proxy_headers, timeout=20, verify=False)
            ct = r.headers.get('Content-Type', 'image/jpeg')
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', len(r.content))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(r.content)
        except:
            self.send_response(404); self.end_headers()
    def log_message(self, format, *args): pass
def _find_free_port():
    import socket
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sk.bind(('127.0.0.1', 0))
    port = sk.getsockname()[1]
    sk.close()
    return port
def _start_proxy():
    global _proxy_port, _proxy_started
    if _proxy_started: return
    _proxy_port = _find_free_port()
    server = _ThreadedHTTPServer(('127.0.0.1', _proxy_port), _ProxyHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _proxy_started = True

# ===== Spider 类 =====
class Spider(BaseSpider):
    session = requests.Session()
    HOSTS = ['https://in30.ll48host.buzz']
    DEFAULT_CATEGORIES = [
        {'type_id': '1', 'type_name': '百万资源'},
        {'type_id': '2', 'type_name': '国产视频'},
        {'type_id': '9', 'type_name': '日韩主播'},
        {'type_id': '18', 'type_name': '欧美视频'},
        {'type_id': '48', 'type_name': '日本有码'},
        {'type_id': '61', 'type_name': '日本无码'},
        {'type_id': '132', 'type_name': '中文字幕'},
        {'type_id': '347', 'type_name': '动漫剧情'},
        {'type_id': '365', 'type_name': '精品推荐'},
        {'type_id': '423', 'type_name': 'VIP专区'},
    ]

    def __init__(self):
        super().__init__()
        self._debug = True
        self._categories_cache = list(self.DEFAULT_CATEGORIES)
        self.host = self.HOSTS[0]
        self._log(f'初始化完成，当前域名: {self.host}')

    def _log(self, msg):
        if self._debug:
            print(f'[ll48] {msg}')

    def getName(self): return 'll48'
    def isVideoFormat(self, url):
        if not url: return False
        return '.m3u8' in url or '.mp4' in url or '.ts' in url or url.startswith('magnet:')
    def manualVideoCheck(self): return False
    def destroy(self): pass
    def localProxy(self, param): return [404, 'text/plain', '']

    def init(self, extend=''):
        self.session.verify = False
        self.session.headers.update(self._get_headers())
        _start_proxy()

    def _get_headers(self, referer=None):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': referer or (self.host + '/vod/'),
        }

    def _proxy_url(self, url):
        if not url: return ''
        if url.startswith('http://127.0.0.1'): return url
        if url.startswith('//'): url = 'https:' + url
        return f'http://127.0.0.1:{_proxy_port}/{quote(url, safe="")}'

    def _fetch(self, url, referer=None, retries=3):
        if not url.startswith('http'):
            url = urljoin(self.host, url)
        for attempt in range(retries):
            try:
                headers = self._get_headers(referer or self.host + '/vod/')
                r = self.session.get(url, headers=headers, timeout=15, verify=False)
                if r.status_code == 200:
                    r.encoding = 'utf-8'
                    self._log(f'请求成功: {url} (长度:{len(r.text)})')
                    return r.text
                else:
                    self._log(f'状态码异常: {r.status_code} {url}')
            except Exception as e:
                self._log(f'请求失败 [{attempt+1}]: {url} - {e}')
            time.sleep(1)
        return ''

    def _parse_list(self, html):
        """解析视频列表"""
        items = []
        seen_vids = set()
        # ========== 修复1：允许 class 中有其他内容（如 clearfix）==========
        list_match = re.search(r'<ul[^>]*class=["\'][^"\']*stui-vodlist[^"\']*["\'][^>]*>(.*?)</ul>', html, re.S)
        if not list_match:
            self._log('未找到 stui-vodlist')
            return items
        list_html = list_match.group(1)
        cards = re.findall(r'<li[^>]*>(.*?)</li>', list_html, re.S)
        self._log(f'找到 {len(cards)} 个视频卡片')
        for card in cards:
            a_match = re.search(r'<a[^>]+href=["\'](/voddetail/(\d+)/)["\'][^>]*title=["\']([^"\']+)["\'][^>]*data-original=["\']([^"\']+)["\']', card, re.S)
            if not a_match:
                href_match = re.search(r'<a[^>]+href=["\'](/voddetail/(\d+)/)["\'][^>]*title=["\']([^"\']+)["\']', card, re.S)
                if not href_match: continue
                vid = href_match.group(2)
                title = href_match.group(3)
                img_match = re.search(r'data-original=["\']([^"\']+)["\']', card)
                pic = img_match.group(1) if img_match else ''
            else:
                vid = a_match.group(2)
                title = a_match.group(3)
                pic = a_match.group(4)
            if vid in seen_vids: continue
            seen_vids.add(vid)
            if pic.startswith('//'): pic = 'https:' + pic
            elif pic.startswith('/'): pic = self.host + pic
            remarks = ''
            t_span = re.search(r'<span[^>]*class=["\']pic-text[^"\']*["\'][^>]*>(.*?)</span>', card, re.S)
            if t_span: remarks = re.sub(r'<[^>]+>', '', t_span.group(1)).strip()
            items.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': self._proxy_url(pic),
                'vod_remarks': remarks,
            })
        self._log(f'解析出 {len(items)} 个视频')
        return items

    def _get_list(self, tid, page):
        url = f'{self.host}/vodtype/{tid}-{page}.html'
        html = self._fetch(url, referer=f'{self.host}/vodtype/{tid}-1.html')
        if not html: return []
        return self._parse_list(html)

    def homeContent(self, filter):
        cats = self._categories_cache
        items = self._get_list(cats[0]['type_id'], 1) if cats else []
        return {
            'class': cats, 'filters': {}, 'type': '影视',
            'list': items, 'page': 1, 'pagecount': 1,
            'limit': len(items), 'total': len(items)
        }

    def homeVideoContent(self):
        if self._categories_cache:
            return {'list': self._get_list(self._categories_cache[0]['type_id'], 1)}
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        items = self._get_list(tid, page)
        return {
            'list': items, 'page': page, 'pagecount': page + 1,
            'limit': len(items), 'total': page + 1
        }

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        detail = self._fetch_detail(vid)
        return {'list': [detail]} if detail else {'list': []}

    def _fetch_detail(self, vid):
        url = f'{self.host}/voddetail/{vid}/'
        html = self._fetch(url, referer=self.host + '/vod/')
        if not html: return None
        return self._parse_detail(html, vid)

    def _parse_detail(self, html, vid):
        title = ''
        m = re.search(r'<h3[^>]*class=["\']title["\'][^>]*>([^<]+)</h3>', html, re.S)
        if m:
            title = m.group(1).strip()
        if not title:
            m = re.search(r'<h1[^>]*class=["\']title["\'][^>]*>([^<]+)</h1>', html, re.S)
            if m: title = m.group(1).strip()
        
        cover = ''
        m = re.search(r'data-original=["\']([^"\']+)["\']', html)
        if m: cover = m.group(1)
        if cover.startswith('//'): cover = 'https:' + cover
        elif cover.startswith('/'): cover = self.host + cover

        content = title or ''
        desc_match = re.search(r'<p[^>]*class=["\']desc[^"\']*["\'][^>]*>.*?简介[：:]\s*</span>\s*(.*?)\s*<a\s', html, re.S)
        if not desc_match:
            desc_match = re.search(r'<p[^>]*class=["\']desc[^"\']*["\'][^>]*>(.*?)</p>', html, re.S)
        if desc_match:
            desc = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()
            desc = re.sub(r'^简介[：:]\s*', '', desc)
            if desc: content = desc

        play_from = []
        play_url = []
        # ========== 修复2：允许 class 中有其他内容 ==========
        playlist_match = re.search(r'<ul[^>]*class=["\'][^"\']*stui-content__playlist[^"\']*["\'][^>]*>(.*?)</ul>', html, re.S)
        if playlist_match:
            links = re.findall(r'<a[^>]+href=["\'](/vodplay/[^"\']+)["\'][^>]*>(.*?)</a>', playlist_match.group(1), re.S)
            if links:
                urls = []
                for href, ep_name in links:
                    ep_name = re.sub(r'<[^>]+>', '', ep_name).strip() or '第1集'
                    urls.append(f'{ep_name}${self.host}{href}')
                play_from.append('在线播放')
                play_url.append('#'.join(urls))
        
        if not play_from:
            all_links = re.findall(r'<a[^>]+href=["\'](/vodplay/[^"\']+)["\'][^>]*>(.*?)</a>', html, re.S)
            if all_links:
                urls = []
                for href, ep_name in all_links:
                    ep_name = re.sub(r'<[^>]+>', '', ep_name).strip() or '第1集'
                    urls.append(f'{ep_name}${self.host}{href}')
                play_from.append('在线播放')
                play_url.append('#'.join(urls))
            else:
                play_from.append('在线播放')
                play_url.append(f'第1集${self.host}/vodplay/{vid}-1-1/')

        return {
            'vod_id': vid,
            'vod_name': title or vid,
            'vod_pic': self._proxy_url(cover) if cover else '',
            'vod_content': content,
            'vod_play_from': '$$$'.join(play_from) if play_from else '在线播放',
            'vod_play_url': '$$$'.join(play_url) if play_url else f'第1集${self.host}/vodplay/{vid}-1-1/',
        }

    def playerContent(self, flag, id, vipFlags=None):
        if '.m3u8' in id or '.mp4' in id or '.ts' in id:
            return {'parse': 0, 'url': id, 'header': {'User-Agent': 'Mozilla/5.0', 'Referer': self.host + '/vod/'}}
        
        if not id.startswith('http'):
            id = self.host + id if id.startswith('/') else self.host + '/' + id
        
        html = self._fetch(id, referer=self.host + '/vod/')
        if not html:
            return {'parse': 1, 'url': id, 'header': {'Referer': self.host + '/vod/'}}
        
        # ========== 修复3：去掉末尾强制分号，允许无空格格式 ==========
        player_match = re.search(r'var\s+player_data\s*=\s*(\{.*?\})', html, re.S)
        if player_match:
            try:
                player_json = json.loads(player_match.group(1))
                real_url = player_json.get('url', '')
                if real_url:
                    real_url = real_url.replace('\\/', '/')
                    if real_url.startswith('http'):
                        return {'parse': 0, 'url': real_url, 'header': {'User-Agent': 'Mozilla/5.0', 'Referer': self.host + '/vod/'}}
            except Exception as e:
                self._log(f'player_data解析失败: {e}')
        
        m3u8 = re.search(r'https?://[^\s\'"<>]+\.m3u8', html)
        if m3u8:
            return {'parse': 0, 'url': m3u8.group(0), 'header': {'User-Agent': 'Mozilla/5.0', 'Referer': self.host + '/vod/'}}
        
        return {'parse': 1, 'url': id, 'header': {'Referer': self.host + '/vod/'}}

    def searchContent(self, key, quick, pg='1'):
        page = int(pg) if pg else 1
        url = f'{self.host}/vodsearch/{quote(key)}-------------{page}---.html'
        html = self._fetch(url, referer=self.host + '/vod/')
        if not html:
            url = f'{self.host}/vodsearch/{quote(key)}.html'
            html = self._fetch(url, referer=self.host + '/vod/')
        items = self._parse_list(html) if html else []
        return {'list': items, 'page': page, 'pagecount': page+1, 'limit': len(items), 'total': len(items)}
