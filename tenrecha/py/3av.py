# -*- coding: utf-8 -*-
"""
3av.app 在线观看脚本
基于 maccms 模板架构
支持自动获取分类 / 使用内置分类
新增：排行榜、女优大全（按标签/字母分组）
"""
import sys, re, json, base64, threading, time, random
import requests, urllib3
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import unquote, quote, urljoin, urlparse

urllib3.disable_warnings()
sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider: pass

# ===== 图片代理 =====
_proxy_port = 0
_proxy_started = False
_proxy_session = requests.Session()
_proxy_session.verify = False

class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class _ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            real_url = unquote(self.path[1:])
            if not real_url or not real_url.startswith('http'):
                self.send_response(404)
                self.end_headers()
                return
            r = _proxy_session.get(
                real_url,
                headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.3av.app/'},
                timeout=20,
                verify=False
            )
            ct = r.headers.get('Content-Type', 'image/jpeg')
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', len(r.content))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(r.content)
        except Exception:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

def _start_proxy():
    global _proxy_port, _proxy_started
    if _proxy_started:
        return
    import socket
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sk.bind(('127.0.0.1', 0))
    _proxy_port = sk.getsockname()[1]
    sk.close()
    server = _ThreadedHTTPServer(('127.0.0.1', _proxy_port), _ProxyHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _proxy_started = True


# ===== Spider =====
class Spider(BaseSpider):
    session = requests.Session()

    # 主域名
    HOST = 'https://www.3av.app'

    # 内置默认分类（与源码一致）
    DEFAULT_CATEGORIES = [
        {'type_id': 'rank', 'type_name': '排行榜'},
        {'type_id': 'nvyou', 'type_name': '女优大全'},
        {'type_id': '1', 'type_name': '国产福利'},
        {'type_id': '2', 'type_name': '国产自拍'},
        {'type_id': '3', 'type_name': '国产偷拍'},
        {'type_id': '4', 'type_name': '国产探花'},
        {'type_id': '5', 'type_name': '国产主播'},
        {'type_id': '6', 'type_name': '丝袜美腿'},
        {'type_id': '7', 'type_name': '人妻少妇'},
        {'type_id': '8', 'type_name': '港台美女'},
        {'type_id': '9', 'type_name': '明星换脸'},
        {'type_id': '10', 'type_name': '网红黑料'},
        {'type_id': '11', 'type_name': '国产口交'},
        {'type_id': '12', 'type_name': '国产群交'},
        {'type_id': '13', 'type_name': '麻豆传媒'},
        {'type_id': '14', 'type_name': '角色扮演'},
        {'type_id': '15', 'type_name': '国产乱伦'},
        {'type_id': '16', 'type_name': '绿帽换妻'},
        {'type_id': '17', 'type_name': '野战激情'},
        {'type_id': '18', 'type_name': '国产TS'},
        {'type_id': '20', 'type_name': '亚洲福利'},
        {'type_id': '21', 'type_name': '日韩福利'},
        {'type_id': '22', 'type_name': '欧美福利'},
        {'type_id': '23', 'type_name': '中文字幕'},
        {'type_id': '24', 'type_name': '三级伦理'},
        {'type_id': '25', 'type_name': '动漫福利'},
        {'type_id': '26', 'type_name': '制服丝袜'},
        {'type_id': '27', 'type_name': '童颜巨乳'},
        {'type_id': '28', 'type_name': '强奸乱伦'},
        {'type_id': '29', 'type_name': '人妻熟女'},
        {'type_id': '30', 'type_name': '少女萝莉'},
        {'type_id': '31', 'type_name': '口交群交'},
        {'type_id': '32', 'type_name': '另类调教'},
        {'type_id': '33', 'type_name': '男同女同'},
        {'type_id': '34', 'type_name': '名人素人'},
    ]

    def __init__(self):
        super().__init__()
        self._debug = True
        self._categories_cache = list(self.DEFAULT_CATEGORIES)
        self.host = self.HOST
        self._nvyou_cache = []
        self._log(f'当前域名: {self.host}')

    def _log(self, msg):
        if self._debug:
            print(f'[3av] {msg}')

    def getName(self):
        return '3av'

    def isVideoFormat(self, url):
        return '.m3u8' in url or '.mp4' in url or '.ts' in url or url.startswith('magnet:')

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def localProxy(self, param):
        return [404, 'text/plain', '']

    def init(self, extend=''):
        self.session.verify = False
        self.session.headers.update(self._get_headers())
        _start_proxy()
        text = self._fetch(self.host + '/')
        if text and len(text) > 2000:
            self._update_categories(text)
        else:
            self._log('首页加载失败，使用默认分类')

    def _get_headers(self, referer=None):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': referer or (self.host + '/')
        }

    def _proxy_url(self, url):
        if not url:
            return ''
        if url.startswith('http://127.0.0.1'):
            return url
        return f'http://127.0.0.1:{_proxy_port}/{quote(url, safe="")}'

    def _fetch(self, url, referer=None, retries=3):
        if not url.startswith('http'):
            url = urljoin(self.host, url)
        for attempt in range(retries):
            try:
                headers = self._get_headers(referer or self.host + '/')
                r = self.session.get(url, headers=headers, timeout=15, verify=False)
                if r.status_code == 200 and len(r.text) > 500:
                    r.encoding = 'utf-8'
                    self._log(f'请求成功: {url} (长度:{len(r.text)})')
                    return r.text
                else:
                    self._log(f'请求内容过短: {url} 长度:{len(r.text) if r.text else 0}')
            except Exception as e:
                self._log(f'请求失败 [{attempt+1}]: {url} - {e}')
            time.sleep(1)
        return ''

    def _update_categories(self, text):
        seen_ids = {c['type_id'] for c in self._categories_cache}
        seen_names = {c['type_name'] for c in self._categories_cache}

        links = re.findall(
            r'<a[^>]+class="text-333"[^>]+href="/vodtype/(\d+)\.html"[^>]*>([^<]+)</a>',
            text
        )
        links += re.findall(
            r'<a[^>]+href="/vodtype/(\d+)\.html"[^>]*>([^<]+)</a>',
            text
        )

        new_cats = []
        for tid, raw_name in links:
            name = re.sub(r'<[^>]+>', '', raw_name).strip()
            if not name or name in ['首页', '留言', '求片', 'APP', '专题', '排行榜', '最新', '永久网址']:
                continue
            if tid not in seen_ids and name not in seen_names:
                new_cats.append({'type_id': tid, 'type_name': name})
                seen_ids.add(tid)
                seen_names.add(name)

        if new_cats:
            self._categories_cache.extend(new_cats)
            self._log(f'自动获取到 {len(new_cats)} 个新分类')

    def _get_category_name(self, tid):
        for cat in self._categories_cache:
            if cat['type_id'] == str(tid):
                return cat['type_name']
        return f'分类_{tid}'

    def _parse_list(self, html):
        items, seen_vids = [], set()
        cards = re.findall(r'<li[^>]*class="[^"]*col-[^"]*"[^>]*>(.*?)</li>', html, re.S)
        if not cards:
            cards = re.findall(r'<li[^>]*>(.*?)</li>', html, re.S)

        for card in cards:
            a_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*title="([^"]*)"', card)
            if not a_match:
                a_match = re.search(r'<a[^>]+href="([^"]+)"', card)
                if not a_match:
                    continue
                href = a_match.group(1).strip()
                title = ''
            else:
                href = a_match.group(1).strip()
                title = a_match.group(2).strip()

            if not href.startswith('/vodplay/'):
                continue

            vid_match = re.search(r'/vodplay/(\d+)', href)
            if not vid_match:
                continue
            vid = vid_match.group(1)
            if vid in seen_vids:
                continue
            seen_vids.add(vid)

            if not title:
                h4 = re.search(r'<h4[^>]*>.*?<a[^>]*>(.*?)</a>', card, re.S)
                if h4:
                    title = re.sub(r'<[^>]+>', '', h4.group(1)).strip()
            if not title:
                title = f'视频_{vid}'

            pic = ''
            img = re.search(r'data-original="([^"]+)"', card)
            if img:
                pic = img.group(1)
                if pic.startswith('//'):
                    pic = 'https:' + pic
                elif pic.startswith('/'):
                    pic = self.host + pic

            remarks = ''
            date_match = re.search(r'<span>(\d{2}-\d{2})</span>', card)
            if date_match:
                remarks = date_match.group(1)
            else:
                remark_match = re.search(r'class="pic-text[^"]*">(.*?)</span>', card, re.S)
                if remark_match:
                    remarks = re.sub(r'<[^>]+>', '', remark_match.group(1)).strip()

            items.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': self._proxy_url(pic),
                'vod_remarks': remarks
            })

        self._log(f'解析到 {len(items)} 个视频')
        return items

    def _get_list(self, tid, page):
        url = f'{self.host}/vodtype/{tid}-{page}.html'
        html = self._fetch(url, referer=f'{self.host}/vodtype/{tid}-1.html')
        return self._parse_list(html) if html else []

    # ===== 排行榜解析 =====
    def _parse_rank(self, html):
        items, seen_vids = [], set()

        # 匹配排行榜中的视频链接（带序号的h3/h4结构）
        entries = re.findall(
            r'<h[34][^>]*>\s*<a[^>]+href="(/vodplay/(\d+)-\d+-\d+\.html)"[^>]*>(.*?)</a>\s*</h[34]>',
            html, re.S
        )

        for href, vid, title in entries:
            if vid in seen_vids:
                continue
            seen_vids.add(vid)

            title = re.sub(r'<[^>]+>', '', title).strip()
            if not title:
                title = f'视频_{vid}'

            items.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': '',
                'vod_remarks': '排行榜'
            })

        # 兜底：匹配所有vodplay链接
        if not items:
            all_links = re.findall(r'href="(/vodplay/(\d+)-\d+-\d+\.html)"[^>]*>(.*?)</a>', html, re.S)
            for href, vid, title in all_links:
                if vid in seen_vids:
                    continue
                seen_vids.add(vid)
                title = re.sub(r'<[^>]+>', '', title).strip()
                if not title:
                    continue
                items.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': '',
                    'vod_remarks': '排行榜'
                })

        self._log(f'排行榜解析到 {len(items)} 个视频')
        return items

    def _get_rank_list(self, page=1):
        url = f'{self.host}/index.php/label/rank.html'
        html = self._fetch(url, referer=self.host)
        return self._parse_rank(html) if html else []

    # ===== 女优大全解析 =====
    def _parse_nvyou(self, html):
        items = []

        # 匹配字母分组结构
        groups = re.findall(
            r'<li class="nvyouzimu">([^<]+)</li>\s*<li class="nvyouliebiao">(.*?)</li>',
            html, re.S
        )

        for group_name, group_html in groups:
            group_name = group_name.strip()
            actresses = re.findall(
                r'<a href="/vodsearch/([^"]+)-\.html"[^>]*>([^<]+)</a>',
                group_html
            )

            for url_name, display_name in actresses:
                display_name = display_name.strip()
                if not display_name:
                    continue
                vid = f'nvyou_{url_name}'
                items.append({
                    'vod_id': vid,
                    'vod_name': display_name,
                    'vod_pic': '',
                    'vod_remarks': group_name
                })

        # 兜底：直接匹配所有女优链接
        if not items:
            actresses = re.findall(
                r'<a href="/vodsearch/([^"]+)-\.html"[^>]*>([^<]+)</a>',
                html
            )
            for url_name, display_name in actresses:
                display_name = display_name.strip()
                if not display_name:
                    continue
                vid = f'nvyou_{url_name}'
                items.append({
                    'vod_id': vid,
                    'vod_name': display_name,
                    'vod_pic': '',
                    'vod_remarks': '女优'
                })

        self._log(f'女优大全解析到 {len(items)} 个女优')
        return items

    def _get_nvyou_list(self, page=1):
        url = f'{self.host}/vodtype/35-{page}.html'
        html = self._fetch(url, referer=self.host)
        if html:
            items = self._parse_nvyou(html)
            self._nvyou_cache = items
            return items
        return []

    # ===== 首页 / 分类 =====
    def homeContent(self, filter):
        text = self._fetch(self.host + '/')
        if text and len(text) > 2000:
            self._update_categories(text)

        cats = self._categories_cache
        items = self._get_rank_list(1) if cats else []
        if not items and cats:
            items = self._get_list(cats[2]['type_id'], 1) if len(cats) > 2 else []

        return {
            'class': cats,
            'filters': {},
            'type': '影视',
            'list': items,
            'page': 1,
            'pagecount': 1,
            'limit': len(items),
            'total': len(items)
        }

    def homeVideoContent(self):
        items = self._get_rank_list(1)
        if not items and self._categories_cache:
            items = self._get_list(self._categories_cache[2]['type_id'], 1) if len(self._categories_cache) > 2 else []
        return {'list': items}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1

        if str(tid) == 'rank':
            items = self._get_rank_list(page)
            return {
                'list': items,
                'page': page,
                'pagecount': 1,
                'limit': len(items),
                'total': len(items)
            }

        if str(tid) == 'nvyou':
            items = self._get_nvyou_list(page)
            return {
                'list': items,
                'page': page,
                'pagecount': 10,
                'limit': len(items),
                'total': 1000
            }

        items = self._get_list(tid, page)
        return {
            'list': items,
            'page': page,
            'pagecount': page + 1,
            'limit': len(items),
            'total': page + 1
        }

    # ===== 详情页 =====
    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)

        if vid.startswith('nvyou_'):
            actress_name = vid.replace('nvyou_', '')
            search_items = self._do_search(actress_name, 1)
            if search_items:
                first = search_items[0]
                return {
                    'list': [{
                        'vod_id': vid,
                        'vod_name': f'女优: {actress_name}',
                        'vod_pic': first.get('vod_pic', ''),
                        'vod_play_from': '在线播放',
                        'vod_play_url': f'线路1${self.host}/vodsearch/{actress_name}-1.html',
                        'vod_content': f'{actress_name} 的作品集，共 {len(search_items)} 部',
                        'vod_remarks': f'{len(search_items)}部作品'
                    }]
                }
            else:
                return {
                    'list': [{
                        'vod_id': vid,
                        'vod_name': f'女优: {actress_name}',
                        'vod_pic': '',
                        'vod_play_from': '在线播放',
                        'vod_play_url': f'线路1${self.host}/vodsearch/{actress_name}-1.html',
                        'vod_content': f'{actress_name} 的作品集',
                        'vod_remarks': ''
                    }]
                }

        detail = self._fetch_detail(vid)
        if not detail:
            detail = {
                'vod_id': vid,
                'vod_name': f'视频_{vid}',
                'vod_pic': '',
                'vod_play_from': '在线播放',
                'vod_play_url': f'线路1${self.host}/vodplay/{vid}-1-1.html',
                'vod_content': ''
            }
        else:
            if not detail.get('vod_name'):
                detail['vod_name'] = f'视频_{vid}'
        return {'list': [detail]}

    def _fetch_detail(self, vid):
        url = f'{self.host}/vodplay/{vid}-1-1.html'
        html = self._fetch(url, referer=self.host)
        return self._parse_detail(html, vid) if html else None

    def _parse_detail(self, html, vid):
        title = ''
        m = re.search(r'<title>(.*?)</title>', html, re.S)
        if m:
            full_title = m.group(1).strip()
            parts = full_title.split('_')
            if len(parts) >= 2:
                title = parts[0].strip()
            else:
                title = full_title

        if not title:
            m = re.search(r'<h1[^>]*class="title"[^>]*>(.*?)</h1>', html, re.S)
            if m:
                title = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        if not title:
            m = re.search(r'<h4[^>]*class="title"[^>]*>(.*?)</h4>', html, re.S)
            if m:
                title = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        if not title:
            title = f'视频_{vid}'

        cover = ''
        m = re.search(r'data-original="([^"]+)"', html)
        if m:
            cover = m.group(1)
            if cover.startswith('//'):
                cover = 'https:' + cover
            elif cover.startswith('/'):
                cover = self.host + cover

        content = ''
        desc_match = re.search(r'class="[^"]*desc[^"]*"[^>]*>(.*?)</', html, re.S)
        if desc_match:
            content = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()
        if not content:
            content = title

        play_url = f'{self.host}/vodplay/{vid}-1-1.html'
        m3u8_url = self._extract_m3u8(html)
        if m3u8_url:
            play_url = m3u8_url

        return {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': self._proxy_url(cover) if cover else '',
            'vod_play_from': '在线播放',
            'vod_play_url': f'线路1${play_url}',
            'vod_content': content,
        }

    def _extract_m3u8(self, html):
        m = re.search(r'var\s+player_aaaa\s*=\s*({.*?});', html, re.S)
        if not m:
            m = re.search(r'player_aaaa\s*=\s*({.*?});', html, re.S)
        if m:
            try:
                cfg = json.loads(m.group(1).replace('\\/', '/'))
                url = cfg.get('url', '')
                if url and ('.m3u8' in url or '.mp4' in url):
                    if not url.startswith('http'):
                        url = urljoin(self.host, url)
                    return url
            except Exception:
                pass

        m = re.search(r'["\'](https?://[^"\'<>]+\.(?:m3u8|mp4)[^"\'<>]*)["\']', html)
        if m:
            return m.group(1)

        return None

    # ===== 播放器 =====
    def playerContent(self, flag, id, vipFlags=None):
        self._log(f'playerContent: id={id[:120] if len(id) > 120 else id}')

        if '.m3u8' in id or '.mp4' in id or id.startswith('magnet:'):
            return {
                'parse': 0,
                'url': id,
                'header': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': self.host
                }
            }

        if 'vodsearch/' in id:
            html = self._fetch(id, referer=self.host)
            if html:
                items = self._parse_list(html)
                if items:
                    first_vid = items[0]['vod_id']
                    detail_url = f'{self.host}/vodplay/{first_vid}-1-1.html'
                    detail_html = self._fetch(detail_url, referer=self.host)
                    if detail_html:
                        m3u8 = self._extract_m3u8(detail_html)
                        if m3u8:
                            return {
                                'parse': 0,
                                'url': m3u8,
                                'header': {
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                                    'Referer': self.host
                                }
                            }
            return {
                'parse': 1,
                'url': id,
                'header': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': self.host
                }
            }

        html = ''
        if id.startswith(self.host):
            html = self._fetch(id, referer=self.host)

        if html:
            m3u8 = self._extract_m3u8(html)
            if m3u8:
                return {
                    'parse': 0,
                    'url': m3u8,
                    'header': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Referer': self.host
                    }
                }

            all_urls = re.findall(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4|ts)[^\s"\'<>]*)', html)
            if all_urls:
                return {
                    'parse': 0,
                    'url': all_urls[0],
                    'header': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Referer': self.host
                    }
                }

        return {
            'parse': 1,
            'url': id,
            'header': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': self.host
            }
        }

    # ===== 搜索 =====
    def searchContent(self, key, quick, pg='1'):
        page = int(pg) if pg else 1
        items = self._do_search(key, page)
        return {
            'list': items,
            'page': page,
            'pagecount': page + 1,
            'limit': len(items),
            'total': len(items)
        }

    def _do_search(self, key, page=1):
        url = f'{self.host}/vodsearch/{quote(key)}-------------{page}---.html'
        html = self._fetch(url, referer=self.host)
        return self._parse_list(html) if html else []
