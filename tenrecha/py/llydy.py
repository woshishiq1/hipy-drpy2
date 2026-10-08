#!/usr/bin/python
# -*- coding: utf-8 -*-
import re, json, requests, urllib3
from urllib.parse import quote
urllib3.disable_warnings()
import sys; sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    HOST = 'https://yan.llydy53.cc'
    PREFIX = '/rk.php'
    UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

    CATS = [
        {'type_id': '10019', 'type_name': '国产精品'},
        {'type_id': '10020', 'type_name': '国产传媒'},
        {'type_id': '10021', 'type_name': '黑料吃瓜'},
        {'type_id': '10015', 'type_name': '亚洲有码'},
        {'type_id': '10016', 'type_name': '亚洲无码'},
        {'type_id': '10018', 'type_name': '中字字幕'},
        {'type_id': '10017', 'type_name': '激情欧美'},
        {'type_id': '10022', 'type_name': '成人动漫'},
        {'type_id': '10023', 'type_name': '三级伦理'},
        {'type_id': '10024', 'type_name': '巨乳美乳'},
        {'type_id': '10026', 'type_name': '强奸乱伦'},
        {'type_id': '10027', 'type_name': '少女萝莉'},
        {'type_id': '10028', 'type_name': '制服丝袜'},
        {'type_id': '10029', 'type_name': '人妻熟女'},
    ]

    def getName(self): return "llydy"

    def init(self, extend=""):
        self.extend = extend or ""
        self.host = self.HOST
        if self.extend:
            if self.extend.startswith('http'): self.host = self.extend.rstrip('/')
            else: self.host = self.extend
        self.base = self.host + self.PREFIX
        self.headers = {'User-Agent': self.UA, 'Referer': self.host + '/'}
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update(self.headers)
        self._cat_seen = {}

    def _fetch(self, url, retries=2):
        for i in range(retries + 1):
            try:
                r = self.session.get(url, timeout=15, allow_redirects=True)
                r.encoding = 'utf-8'
                if r.status_code == 200 and len(r.text) > 500: return r.text
            except: pass
        return ''

    def _fix(self, u):
        if not u: return ''
        if u.startswith('//'): return 'https:' + u
        if u.startswith('/'): return self.host + u
        return u

    def _parse_list(self, text):
        if not text: return []
        items, seen = [], set()
        for m in re.finditer(r'<div class="item[^"]*">\s*<a href="(/rk\.php/vod/detail/id/(\d+)\.html)"[^>]*>(.*?)</a>', text, re.S):
            vid = m.group(2)
            if vid in seen: continue
            seen.add(vid)
            block = m.group(3)
            title = ''
            tm = re.search(r'<strong class="title">(.*?)</strong>', block, re.S)
            if tm: title = re.sub(r'<[^>]+>', '', tm.group(1)).strip()
            if not title: title = f'视频{vid}'
            pic = ''
            pm = re.search(r'data-src="([^"]+)"', block)
            if pm: pic = self._fix(pm.group(1))
            if not pic or 'load5.gif' in pic:
                pm = re.search(r'<img[^>]+src="([^"]+)"', block)
                if pm and 'load5.gif' not in pm.group(1) and 'data:image' not in pm.group(1): pic = self._fix(pm.group(1))
            remarks = ''
            dm = re.search(r'<em>([^<]*)</em>', block)
            if dm: remarks = dm.group(1).strip()
            items.append({'vod_id': vid, 'vod_name': title, 'vod_pic': pic, 'vod_remarks': remarks})
        return items

    def homeContent(self, filter):
        return {'class': self.CATS, 'list': self._parse_list(self._fetch(self.base + '?shareName=daffe345')), 'filters': {}}

    def homeVideoContent(self):
        items = self._parse_list(self._fetch(self.base + '?shareName=daffe345'))
        return {'list': items[:24], 'page': 1, 'pagecount': 1, 'limit': len(items), 'total': len(items)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if page == 1: url = f'{self.base}/vod/type/id/{tid}.html'
        else: url = f'{self.base}/vod/type/id/{tid}/page/{page}.html'
        text = self._fetch(url)
        items = self._parse_list(text)
        pagecount = 1
        pages = [int(x) for x in re.findall(r'/page/(\d+)\.html', text or '') if x.isdigit()]
        if pages: pagecount = max(pages)
        if page == 1: self._cat_seen[tid] = set()
        seen = self._cat_seen.setdefault(tid, set())
        items = [it for it in items if it['vod_id'] not in seen]
        seen.update(it['vod_id'] for it in items)
        return {'list': items, 'page': page, 'pagecount': pagecount, 'limit': len(items), 'total': pagecount * 27 if items else 0}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        text = self._fetch(f'{self.base}/vod/detail/id/{vid}.html')
        if not text: return {'list': []}
        title = ''
        h1m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S)
        if h1m: title = re.sub(r'<[^>]+>', '', h1m.group(1)).strip()
        if not title:
            tm = re.search(r'<title>(.*?)</title>', text, re.S)
            if tm:
                raw = tm.group(1).strip()
                title = raw.replace('_乱伦伊甸园', '').strip()
        if not title: title = f'视频{vid}'
        pic = ''
        pm = re.search(r'"poster":\s*"([^"]+)"', text)
        if pm: pic = pm.group(1)
        if not pic:
            pm = re.search(r'data-src="(https?://[^"]+)"', text)
            if pm: pic = pm.group(1)
        m3u8 = ''
        mm = re.search(r'new\s+HlsJsPlayer\s*\(\s*\{[^}]*"url":\s*"(https?://[^"]+\.m3u8)"', text, re.S)
        if mm: m3u8 = mm.group(1)
        if not m3u8:
            mm = re.search(r'"url":\s*"(https?://[^"]+\.m3u8)"', text)
            if mm: m3u8 = mm.group(1)
        if not m3u8:
            mm = re.search(r'(https?://[^\s"\'<>]+\.m3u8)', text)
            if mm: m3u8 = mm.group(1)
        pf, pu = ['默认线路'], [f'正片${m3u8}']
        return {'list': [{'vod_id': vid, 'vod_name': title, 'vod_pic': pic, 'vod_play_from': '$$$'.join(pf), 'vod_play_url': '$$$'.join(pu)}]}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        if page == 1: url = f'{self.base}/vod/search/wd/{quote(key)}.html'
        else: url = f'{self.base}/vod/search/wd/{quote(key)}/page/{page}.html'
        text = self._fetch(url)
        items = self._parse_list(text)
        pagecount = 1
        pages = [int(x) for x in re.findall(r'/page/(\d+)\.html', text or '') if x.isdigit()]
        if pages: pagecount = max(pages)
        return {'list': items, 'page': page, 'pagecount': pagecount, 'limit': len(items), 'total': len(items)}

    def playerContent(self, flag, id, vipFlags):
        if id.startswith('http') and '.m3u8' in id:
            return {'parse': 0, 'url': id, 'header': {'Referer': self.host + '/', 'User-Agent': self.UA}}
        vid = str(id)
        text = self._fetch(f'{self.base}/vod/detail/id/{vid}.html')
        if not text: return {'parse': 1, 'url': f'{self.base}/vod/detail/id/{vid}.html', 'header': {'Referer': self.host + '/', 'User-Agent': self.UA}}
        m3u8 = ''
        mm = re.search(r'new\s+HlsJsPlayer\s*\(\s*\{[^}]*"url":\s*"(https?://[^"]+\.m3u8)"', text, re.S)
        if mm: m3u8 = mm.group(1)
        if not m3u8:
            mm = re.search(r'"url":\s*"(https?://[^"]+\.m3u8)"', text)
            if mm: m3u8 = mm.group(1)
        if not m3u8:
            mm = re.search(r'(https?://[^\s"\'<>]+\.m3u8)', text)
            if mm: m3u8 = mm.group(1)
        return {'parse': 0 if m3u8 else 1, 'url': m3u8 if m3u8 else f'{self.base}/vod/detail/id/{vid}.html', 'header': {'Referer': self.host + '/', 'User-Agent': self.UA}}
