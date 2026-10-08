# -*- coding: utf-8 -*-
"""
91情报局爬虫
站点: https://youliaoqbj8147351.xyz
"""
import sys, re, json
import requests, urllib3, time, random
from urllib.parse import quote, urljoin

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    host = 'https://youliaoqbj8147351.xyz'
    session = requests.Session()
    _cached_categories = []
    _debug = True

    def _log(self, msg):
        if self._debug: print(f'[youliao] {msg}')

    def getName(self): return '91情报局'
    def isVideoFormat(self, url):
        if not url: return False
        return '.m3u8' in url or '.mp4' in url or '.ts' in url
    def manualVideoCheck(self): return False
    def destroy(self): pass

    def localProxy(self, param):
        if not param or not param.startswith('http'):
            return [500, 'text/plain', '']
        try:
            r = self.session.get(param, headers={
                'User-Agent': 'Mozilla/5.0', 'Referer': self.host + '/'
            }, timeout=15, stream=True)
            if r.status_code != 200: return [r.status_code, 'text/plain', 'error']
            return [200, r.headers.get('Content-Type', 'image/jpeg'), r.content]
        except: return [500, 'text/plain', 'error']

    def init(self, extend=''):
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        text = self._fetch(self.host)
        if text:
            self._load_categories(text)

    def _get_headers(self, referer=None):
        h = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        h['Referer'] = referer if referer else self.host + '/'
        return h

    def _fetch(self, url, referer=None, retries=3):
        for attempt in range(retries):
            try:
                if attempt > 0: time.sleep(random.uniform(0.5, 1.5))
                r = self.session.get(url, headers=self._get_headers(referer), timeout=30, verify=False)
                r.encoding = 'utf-8'
                if r.status_code == 200: return r.text
                elif r.status_code in [403, 429, 503]:
                    self._log(f'被拦截 [{r.status_code}] 重试 {attempt+1}')
                    continue
                else: return ''
            except requests.exceptions.Timeout:
                self._log(f'超时重试 {attempt+1}')
            except Exception as e:
                self._log(f'异常 {e} 重试 {attempt+1}')
        return ''

    def _load_categories(self, text):
        cats = []
        seen = set()
        # Only extract from the sidebar navigation with the specific pattern
        # Find the "内容分类" nav section
        nav_start = text.find('内容分类')
        if nav_start < 0: nav_start = text.find('class="sidebar"')
        if nav_start < 0: nav_start = 0
        nav_text = text[nav_start:nav_start+10000]
        for m in re.finditer(r'href="/video/type/(\d+)\.html"[^>]*>\s*([^<]+?)\s*<', nav_text):
            tid, name = m.group(1), m.group(2).strip()
            if tid not in seen and name and len(name) < 15:
                seen.add(tid)
                cats.append({'type_id': tid, 'type_name': name})
        self._cached_categories = cats
        # 过滤无用分类
        skip_names = ['精品仓库']
        self._cached_categories = [c for c in cats if c['type_name'] not in skip_names]
        self._log(f'分类: {len(cats)} 个, 过滤后: {len(self._cached_categories)} 个')
        return cats

    def _parse_list(self, html):
        items = []
        seen_ids = set()
        for m in re.finditer(r'<article[^>]*>(.*?)</article>', html, re.S):
            card = m.group(1)
            link_m = re.search(r'href="(?:https?://[^/]+)?/(?:video/)?info/(\d+)\.html"', card)
            if not link_m: continue
            vid = link_m.group(1)
            if vid in seen_ids: continue
            seen_ids.add(vid)
            # Title from h2 or title attribute
            title = ''
            h_m = re.search(r'<h2[^>]*>(.*?)</h2>', card, re.S)
            if h_m: title = re.sub(r'<[^>]+>', '', h_m.group(1)).strip()
            if not title:
                title_m = re.search(r'title="([^"]+)"', card)
                if title_m: title = title_m.group(1).strip()
            img_m = re.search(r'<img[^>]+src="([^"]+)"', card)
            pic = img_m.group(1) if img_m else ''
            # Category label
            cat_m = re.search(r'class="card-cat"[^>]*>(.*?)<', card)
            remark = cat_m.group(1).strip() if cat_m else ''
            items.append({'vod_id': vid, 'vod_name': title or vid, 'vod_pic': pic, 'vod_remarks': remark})
        return items

    def _get_list(self, tid, page):
        url = f'{self.host}/video/type/{tid}.html' if page <= 1 else f'{self.host}/video/type/{tid}/{page}.html'
        html = self._fetch(url, referer=self.host)
        return self._parse_list(html) if html else []

    def homeContent(self, filter):
        try:
            text = self._fetch(self.host)
            if text: self._load_categories(text)
            cats = self._cached_categories or []
            items = self._get_list(cats[0]['type_id'], 1) if cats else []
            return {'class': cats, 'list': items}
        except Exception as e:
            self._log(f'homeContent: {e}')
            return {'class': [], 'list': []}

    def homeVideoContent(self):
        if self._cached_categories:
            return {'list': self._get_list(self._cached_categories[0]['type_id'], 1)}
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
            items = self._get_list(tid, page)
            total_page = page + 1
            if page == 1:
                html = self._fetch(f'{self.host}/video/type/{tid}.html')
                if html:
                    pages = re.findall(r'/video/type/{tid}/(\d+)\.html', html)
                    if pages: total_page = max(int(p) for p in pages)
            return {'list': items, 'page': page, 'pagecount': total_page}
        except Exception as e:
            self._log(f'categoryContent: {e}')
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1}

    def _fetch_play_url(self, vid):
        """返回 (play_url, needs_parse)"""
        # Get slug from info page
        info_html = self._fetch(f'{self.host}/info/{vid}.html', referer=self.host)
        play_path = f'/play/{vid}/'
        if info_html:
            m = re.search(r"href='(/play/{vid}/[^']+)'", info_html)
            if m: play_path = m.group(1)
        play_url = f'{self.host}{play_path}'
        html = self._fetch(play_url, referer=f'{self.host}/info/{vid}.html')
        if not html:
            play_url = f'{self.host}/play/{vid}'
            html = self._fetch(play_url, referer=f'{self.host}/info/{vid}.html')
        if not html: return ('', False)
        # Extract encrypted ID from player_a.html iframe
        m = re.search(r'src="/static/html/player_a\.html\?id=([^&\"]+)', html)
        if not m: return (play_url, True)
        enc_id = m.group(1)
        # Call /aa/{enc_id} to get the actual m3u8 URL
        try:
            r = self.session.get(f'{self.host}/aa/{enc_id}', headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': play_url, 'Accept': '*/*',
            }, timeout=20, verify=False)
            if r.status_code == 200:
                url = r.text.strip().replace('amp;', '')
                if url.startswith('http'): return (url, False)
        except: pass
        return (play_url, True)

    def detailContent(self, ids):
        try:
            vid = str(ids[0] if isinstance(ids, list) else ids)
            # Get detail page for title and cover
            url = f'{self.host}/info/{vid}.html'
            html = self._fetch(url, referer=self.host)
            title = vid
            cover = ''
            if html:
                m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
                if m: title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
                if m: cover = m.group(1)
                if not cover:
                    m = re.search(r'<img[^>]+class="info-cover-img"[^>]+src="([^"]+)"', html)
                    if m: cover = m.group(1)
                if not cover:
                    m = re.search(r'thumbnailUrl[^:]*:\s*"([^"]+)"', html)
                    if m: cover = m.group(1)
            # Get play URL
            play_url, needs_parse = self._fetch_play_url(vid)
            vod_play_from = '解析' if needs_parse else '播放'
            flag = f'{vod_play_from}${play_url}'
            return {'list': [{
                'vod_id': vid, 'vod_name': title, 'vod_pic': cover,
                'vod_play_from': vod_play_from, 'vod_play_url': flag,
            }]}
        except Exception as e:
            self._log(f'detailContent: {e}')
            return {'list': []}

    def playerContent(self, flag, id, vipFlags=None):
        needs_parse = (flag == '解析')
        return {'parse': 1 if needs_parse else 0, 'url': id,
                'header': {'Referer': self.host, 'User-Agent': 'Mozilla/5.0'}}

    def searchContent(self, key, quick, pg='1'):
        try:
            page = int(pg) if pg else 1
            url = f'{self.host}/search?keyword={quote(key)}&page={page}'
            html = self._fetch(url, referer=self.host)
            items = self._parse_list(html) if html else []
            return {'list': items, 'page': page, 'pagecount': page + 1}
        except Exception as e:
            self._log(f'searchContent: {e}')
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1}
