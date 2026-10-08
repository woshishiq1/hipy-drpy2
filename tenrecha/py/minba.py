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
    'Referer': 'https://1h5ceqq1h0.minba-abus.buzz/',
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
    HOSTS = ['https://1h5ceqq1h0.minba-abus.buzz']
    DEFAULT_CATEGORIES = [
        {'type_id': '2', 'type_name': '国产视频'},
        {'type_id': '3', 'type_name': '国产主播'},
        {'type_id': '4', 'type_name': '91大神'},
        {'type_id': '5', 'type_name': '热门事件'},
        {'type_id': '6', 'type_name': '传媒自拍'},
        {'type_id': '7', 'type_name': '日本有码'},
        {'type_id': '8', 'type_name': '日本无码'},
        {'type_id': '9', 'type_name': '日韩主播'},
        {'type_id': '10', 'type_name': '动漫肉番'},
        {'type_id': '11', 'type_name': '女同性恋'},
        {'type_id': '12', 'type_name': '中文字幕'},
        {'type_id': '13', 'type_name': '强奸乱伦'},
        {'type_id': '14', 'type_name': '熟女人妻'},
        {'type_id': '15', 'type_name': '制服诱惑'},
        {'type_id': '16', 'type_name': 'AV解说'},
        {'type_id': '17', 'type_name': '女星换脸'},
        {'type_id': '444', 'type_name': '欧美精品'},
        {'type_id': 'label_hits', 'type_name': '热播视频'},
        {'type_id': 'label_month', 'type_name': '月播视频'},
        {'type_id': 'label_score', 'type_name': '推荐视频'},
    ]

    def __init__(self):
        super().__init__()
        self._debug = True
        self._categories_cache = list(self.DEFAULT_CATEGORIES)
        self.host = self.HOSTS[0]
        self._log(f'初始化完成，当前域名: {self.host}')

    def _log(self, msg):
        if self._debug:
            print(f'[minba] {msg}')

    def getName(self): return 'minba'
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
        """兼容两种结构：.vods>.vod（封面卡片） 和 .pic2>ul>li（纯文字列表）"""
        items = []
        seen_vids = set()

        # ========== 模式 A：带封面的 .vods > .vod 结构 ==========
        cards = re.findall(
            r'<div class="vod">\s*<div class="vod-img">(.*?)</div>\s*<div class="vod-txt">(.*?)</div>\s*</div>',
            html, re.S
        )
        if cards:
            for img_block, txt_block in cards:
                a_match = re.search(r'<a[^>]+href=["\'](/vodplay/(\d+)-\d+-\d+/)["\']', img_block)
                if not a_match:
                    a_match = re.search(r'<a[^>]+href=["\'](/voddetail/(\d+)/)["\']', img_block)
                if not a_match:
                    a_match = re.search(r'<a[^>]+href=["\'](/vodplay/(\d+)-\d+-\d+/)["\']', txt_block)
                if not a_match:
                    continue

                vid = a_match.group(2)
                if vid in seen_vids:
                    continue
                seen_vids.add(vid)

                title_match = re.search(r'<a[^>]*>(.*?)</a>', txt_block, re.S)
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else vid

                pic = ''
                pic_match = re.search(r'data-original=["\']([^"\']+)["\']', img_block)
                if not pic_match:
                    pic_match = re.search(r'src=["\']([^"\']+)["\']', img_block)
                if pic_match:
                    pic = pic_match.group(1)
                    if pic.startswith('//'):
                        pic = 'https:' + pic
                    elif pic.startswith('/'):
                        pic = self.host + pic

                remarks = ''
                remark_match = re.search(r'<span[^>]*class=["\']pic-text[^"\']*["\'][^>]*>(.*?)</span>', img_block, re.S)
                if remark_match:
                    remarks = re.sub(r'<[^>]+>', '', remark_match.group(1)).strip()

                items.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': self._proxy_url(pic),
                    'vod_remarks': remarks,
                })

        # ========== 模式 B：纯文字列表 .pic2 > ul > li（热播/月播/推荐等） ==========
        if not items:
            pic2_blocks = re.findall(r'<div class=["\']?\s*pic2\s*["\']?>\s*<ul>(.*?)</ul>', html, re.S)
            for block in pic2_blocks:
                # 先尝试带 title 属性的
                links = re.findall(
                    r'<a[^>]+href=["\'](/vodplay/(\d+)-\d+-\d+/)["\'][^>]*title=["\']([^"\']+)["\'][^>]*>.*?</a>',
                    block, re.S
                )
                # 不带 title 则取标签内文本
                if not links:
                    raw_links = re.findall(
                        r'<a[^>]+href=["\'](/vodplay/(\d+)-\d+-\d+/)["\'][^>]*>(.*?)</a>',
                        block, re.S
                    )
                    links = []
                    for href, vid, text in raw_links:
                        text = re.sub(r'<[^>]+>', '', text).strip()
                        if text:
                            links.append((href, vid, text))

                for href, vid, title in links:
                    if vid in seen_vids:
                        continue
                    seen_vids.add(vid)
                    items.append({
                        'vod_id': vid,
                        'vod_name': title,
                        'vod_pic': '',
                        'vod_remarks': '',
                    })

        self._log(f'解析出 {len(items)} 个视频')
        return items

    def _get_list(self, tid, page):
        # Label 类型（热播/月播/推荐）
        if tid.startswith('label_'):
            label_name = tid.replace('label_', '')
            urls_to_try = []
            if page == 1:
                urls_to_try.append(f'{self.host}/label/{label_name}.html')
                urls_to_try.append(f'{self.host}/label/{label_name}/')
            else:
                # 苹果CMS label 分页常见格式
                urls_to_try.append(f'{self.host}/label/{label_name}_{page}.html')
                urls_to_try.append(f'{self.host}/label/{label_name}-{page}.html')
                urls_to_try.append(f'{self.host}/label/{label_name}/{page}/')
            for url in urls_to_try:
                html = self._fetch(url, referer=self.host + '/vod/')
                if html:
                    return self._parse_list(html)
            return []

        # 普通分类类型
        urls_to_try = []
        if page == 1:
            urls_to_try.append(f'{self.host}/vodtype/{tid}.html')
            urls_to_try.append(f'{self.host}/vodtype/{tid}/')
        else:
            urls_to_try.append(f'{self.host}/vodtype/{tid}-{page}.html')
            urls_to_try.append(f'{self.host}/vodtype/{tid}-{page}/')
        for url in urls_to_try:
            html = self._fetch(url, referer=self.host + '/vod/')
            if html:
                return self._parse_list(html)
        return []

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
        for suffix in (f'/voddetail/{vid}/', f'/voddetail/{vid}.html'):
            html = self._fetch(suffix, referer=self.host + '/vod/')
            if html:
                detail = self._parse_detail(html, vid)
                if detail:
                    return detail
        return self._build_direct_detail(vid)

    def _parse_detail(self, html, vid):
        title = ''
        for pattern in (
            r'<h1[^>]*class=["\']title["\'][^>]*>(.*?)</h1>',
            r'<h3[^>]*class=["\']title["\'][^>]*>(.*?)</h3>',
            r'<div[^>]*class=["\']stui-content__detail[^"\']*["\'][^>]*>.*?<h3[^>]*>(.*?)</h3>',
        ):
            m = re.search(pattern, html, re.S)
            if m:
                title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                if title:
                    break

        cover = ''
        m = re.search(r'data-original=["\']([^"\']+)["\']', html)
        if not m:
            m = re.search(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*class=["\']lazy["\']', html)
        if m:
            cover = m.group(1)
            if cover.startswith('//'):
                cover = 'https:' + cover
            elif cover.startswith('/'):
                cover = self.host + cover

        content = title or ''
        for pattern in (
            r'<p[^>]*class=["\']desc[^"\']*["\'][^>]*>.*?简介[：:]\s*</span>\s*(.*?)\s*<a\s',
            r'<p[^>]*class=["\']desc[^"\']*["\'][^>]*>(.*?)</p>',
            r'<div[^>]*class=["\']stui-content__desc[^"\']*["\'][^>]*>(.*?)</div>',
        ):
            desc_match = re.search(pattern, html, re.S)
            if desc_match:
                desc = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()
                desc = re.sub(r'^简介[：:]\s*', '', desc)
                if desc:
                    content = desc
                    break

        play_from = []
        play_url = []

        # 1) stui-content__playlist
        playlist_match = re.search(
            r'<ul[^>]*class=["\'][^"\']*stui-content__playlist[^"\']*["\'][^>]*>(.*?)</ul>',
            html, re.S
        )
        if playlist_match:
            links = re.findall(r'<a[^>]+href=["\'](/vodplay/[^"\']+)["\'][^>]*>(.*?)</a>', playlist_match.group(1), re.S)
            if links:
                urls = []
                for href, ep_name in links:
                    ep_name = re.sub(r'<[^>]+>', '', ep_name).strip() or '第1集'
                    urls.append(f'{ep_name}${self.host}{href}')
                play_from.append('在线播放')
                play_url.append('#'.join(urls))

        # 2) 通用 playlist
        if not play_from:
            playlist_match = re.search(
                r'<div[^>]*class=["\'][^"\']*playlist[^"\']*["\'][^>]*>(.*?)</div>\s*</div>',
                html, re.S
            )
            if playlist_match:
                links = re.findall(r'<a[^>]+href=["\'](/vodplay/[^"\']+)["\'][^>]*>(.*?)</a>', playlist_match.group(1), re.S)
                if links:
                    urls = []
                    for href, ep_name in links:
                        ep_name = re.sub(r'<[^>]+>', '', ep_name).strip() or '第1集'
                        urls.append(f'{ep_name}${self.host}{href}')
                    play_from.append('在线播放')
                    play_url.append('#'.join(urls))

        # 3) 全页兜底
        if not play_from:
            all_links = re.findall(r'<a[^>]+href=["\'](/vodplay/[^"\']+)["\'][^>]*>(.*?)</a>', html, re.S)
            if all_links:
                urls = []
                for href, ep_name in all_links:
                    ep_name = re.sub(r'<[^>]+>', '', ep_name).strip() or '第1集'
                    urls.append(f'{ep_name}${self.host}{href}')
                play_from.append('在线播放')
                play_url.append('#'.join(urls))

        if not play_from:
            return None

        return {
            'vod_id': vid,
            'vod_name': title or vid,
            'vod_pic': self._proxy_url(cover) if cover else '',
            'vod_content': content,
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '$$$'.join(play_url),
        }

    def _build_direct_detail(self, vid):
        return {
            'vod_id': vid,
            'vod_name': f'视频{vid}',
            'vod_pic': '',
            'vod_content': '',
            'vod_play_from': '在线播放',
            'vod_play_url': f'第1集${self.host}/vodplay/{vid}-1-1/',
        }

    def playerContent(self, flag, id, vipFlags=None):
        if '.m3u8' in id or '.mp4' in id or '.ts' in id:
            return {'parse': 0, 'url': id, 'header': {'User-Agent': 'Mozilla/5.0', 'Referer': self.host + '/vod/'}}

        if not id.startswith('http'):
            id = self.host + id if id.startswith('/') else self.host + '/' + id

        html = self._fetch(id, referer=self.host + '/vod/')
        if not html:
            return {'parse': 1, 'url': id, 'header': {'Referer': self.host + '/vod/'}}

        player_match = re.search(r'var\s+player_\w+\s*=\s*(\{.*?\})', html, re.S)
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

        iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.S)
        if iframe_match:
            iframe_url = iframe_match.group(1)
            if iframe_url.startswith('//'):
                iframe_url = 'https:' + iframe_url
            elif iframe_url.startswith('/'):
                iframe_url = self.host + iframe_url
            if '.m3u8' in iframe_url or '.mp4' in iframe_url:
                return {'parse': 0, 'url': iframe_url, 'header': {'User-Agent': 'Mozilla/5.0', 'Referer': self.host + '/vod/'}}
            return {'parse': 1, 'url': iframe_url, 'header': {'Referer': self.host + '/vod/'}}

        m3u8 = re.search(r'https?://[^\s\'"<>]+\.m3u8', html)
        if m3u8:
            return {'parse': 0, 'url': m3u8.group(0), 'header': {'User-Agent': 'Mozilla/5.0', 'Referer': self.host + '/vod/'}}

        return {'parse': 1, 'url': id, 'header': {'Referer': self.host + '/vod/'}}

    def searchContent(self, key, quick, pg='1'):
        page = int(pg) if pg else 1
        patterns = [
            f'{self.host}/vodsearch/{quote(key)}-------------{page}---.html',
            f'{self.host}/vodsearch/{quote(key)}.html',
            f'{self.host}/vodsearch/{quote(key)}-------------{page}---/',
        ]
        html = ''
        for url in patterns:
            html = self._fetch(url, referer=self.host + '/vod/')
            if html:
                break
        items = self._parse_list(html) if html else []
        return {'list': items, 'page': page, 'pagecount': page + 1, 'limit': len(items), 'total': len(items)}
