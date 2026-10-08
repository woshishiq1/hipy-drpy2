#!/usr/bin/python
# -*- coding: utf-8 -*-
import re, json, base64, requests, urllib3
from urllib.parse import quote
urllib3.disable_warnings()
import sys; sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    HOST = 'https://www.yemahl.xyz'
    UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

    CATS = [
       # {'type_id': '41', 'type_name': '有码番号'},
        {'type_id': '39', 'type_name': '番号视频'},
        {'type_id': '39&fenlei=中文字幕', 'type_name': '中文字幕'},
        {'type_id': '39&fenlei=巨乳美乳', 'type_name': '巨乳美乳'},
        {'type_id': '39&fenlei=强奸乱伦', 'type_name': '强奸乱伦'},
        {'type_id': '39&fenlei=制服丝袜', 'type_name': '制服丝袜'},
        {'type_id': '39&fenlei=萝莉少女', 'type_name': '萝莉少女'},
        {'type_id': '39&fenlei=精品素人', 'type_name': '精品素人'},
        {'type_id': '39&fenlei=亚洲有码', 'type_name': '亚洲有码'},
        {'type_id': '39&fenlei=亚洲无码', 'type_name': '亚洲无码'},
        {'type_id': '39&fenlei=女同性恋', 'type_name': '女同性恋'},
        {'type_id': '40', 'type_name': '国产视频'},
        {'type_id': '40&fenlei=国产自拍', 'type_name': '国产自拍'},
        {'type_id': '40&fenlei=国产传媒', 'type_name': '国产传媒'},
        {'type_id': '40&fenlei=AV解说', 'type_name': 'AV解说'},
        {'type_id': '40&fenlei=国产乱伦', 'type_name': '国产乱伦'},
        {'type_id': '40&fenlei=网红主播', 'type_name': '网红主播'},
        {'type_id': '40&fenlei=探花约炮', 'type_name': '探花约炮'},
        {'type_id': '40&fenlei=ai换脸', 'type_name': 'ai换脸'},
        {'type_id': '40&fenlei=伦理三级', 'type_name': '伦理三级'},
        {'type_id': '40&fenlei=欧美精品', 'type_name': '欧美精品'},
        {'type_id': '40&fenlei=成人动漫', 'type_name': '成人动漫'},
    ]

    def getName(self): return "yemahl"

    def init(self, extend=""):
        self.extend = extend or ""
        self.host = self.HOST
        if self.extend:
            if self.extend.startswith('http'): self.host = self.extend.rstrip('/')
            else: self.host = self.extend
        self.headers = {'User-Agent': self.UA, 'Referer': self.host + '/'}
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update(self.headers)

    def _fetch(self, url, retries=2):
        for i in range(retries + 1):
            try:
                r = self.session.get(url, timeout=15, allow_redirects=True)
                r.encoding = 'utf-8'
                if r.status_code == 200 and len(r.text) > 500: return r.text
            except: pass
        return ''

    def _b64(self, s):
        try:
            d1 = base64.b64decode(s.strip()).decode('utf-8')
            if re.match(r'^[A-Za-z0-9+/=]+$', d1) and len(d1) > 10:
                try: return base64.b64decode(d1).decode('utf-8')
                except: return d1
            return d1
        except: return s.strip()

    def _fix(self, u):
        if not u: return ''
        if u.startswith('//'): return 'https:' + u
        if u.startswith('/'): return self.host + u
        return u

    def _parse_list(self, text):
        if not text: return []
        items, seen = [], set()
        for m in re.finditer(r'<article[^>]*>(.*?)</article>', text, re.S):
            art = m.group(1)
            link_m = re.search(r'href="(/video\.php\?classid=(\d+)&id=(\d+))"', art)
            if not link_m:
                link_m = re.search(r'href="(/cili\.php\?classid=(\d+)&id=(\d+))"', art)
            if not link_m: continue
            vid = link_m.group(3)
            if vid in seen: continue
            seen.add(vid)
            title = ''
            title_m = re.search(r'<h2><a[^>]*>([^<]*)</a>', art)
            if title_m: title = self._b64(title_m.group(1))
            if not title: title = f'视频{vid}'
            pic = ''
            pic_m = re.search(r'data-lazy-src="([^"]+)"', art)
            if pic_m: pic = self._fix(pic_m.group(1))
            if not pic:
                pic_m = re.search(r'<img[^>]+src="([^"]+)"', art)
                if pic_m and 'gifjiazai' not in pic_m.group(1): pic = self._fix(pic_m.group(1))
            remarks = ''
            date_m = re.search(r'class="img-info">([^<]*)<', art)
            if date_m: remarks = self._b64(date_m.group(1))
            items.append({'vod_id': f'{link_m.group(2)}_{vid}', 'vod_name': title, 'vod_pic': pic, 'vod_remarks': remarks})
        return items

    def homeContent(self, filter):
        return {'class': self.CATS, 'list': self._parse_list(self._fetch(self.host + '/')), 'filters': {}}

    def homeVideoContent(self):
        items = self._parse_list(self._fetch(self.host + '/'))
        return {'list': items[:24], 'page': 1, 'pagecount': 1, 'limit': len(items), 'total': len(items)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        url = f'{self.host}/list.php?classid={tid}&page={page}'
        text = self._fetch(url)
        items = self._parse_list(text)
        pagecount = page
        m = re.search(r'page=(\d+)', text or '')
        if m:
            pages = [int(x) for x in re.findall(r'page=(\d+)', text) if x.isdigit()]
            if pages: pagecount = max(pages)
        has_next = bool(text and re.search(rf'page={page+1}[">\s]', text))
        return {'list': items, 'page': page, 'pagecount': pagecount if pagecount > page else page + 1, 'limit': len(items), 'total': pagecount * 20 if pagecount > 1 else len(items)}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        if '_' in vid: classid, vid = vid.split('_', 1)
        else: classid = '40'
        is_cili = (classid == '41')
        page_url = f'{self.host}/cili.php?classid={classid}&id={vid}' if is_cili else f'{self.host}/video.php?classid={classid}&id={vid}'
        text = self._fetch(page_url)
        if not text: return {'list': []}
        title = ''
        title_m = re.search(r'<title>(.*?)</title>', text, re.S)
        if title_m:
            raw = title_m.group(1).strip()
            parts = raw.split(' - ')
            title = self._b64(parts[0]) if parts else raw
        if not title: title = f'视频{vid}'
        cover = ''
        cover_m = re.search(r'data-lazy-src="(/img/[^"]+)"', text)
        if cover_m: cover = self._fix(cover_m.group(1))
        if not cover:
            cover_m = re.search(r'<video[^>]+poster="([^"]+)"', text)
            if cover_m: cover = self._fix(cover_m.group(1))
        pf, pu = ['默认线路'], [f'正片${classid}_{vid}']
        if not is_cili:
            m3u8 = ''
            line_m = re.search(r'data-raw="(https?://[^"]+\.m3u8)"', text)
            if line_m: m3u8 = line_m.group(1)
            if not m3u8:
                line_m = re.search(r'["\'](https?://[^"\'<>]+\.m3u8)["\']', text)
                if line_m: m3u8 = line_m.group(1)
            if m3u8: pu = [f'正片${m3u8}']
        return {'list': [{'vod_id': f'{classid}_{vid}', 'vod_name': title, 'vod_pic': cover, 'vod_play_from': '$$$'.join(pf), 'vod_play_url': '$$$'.join(pu)}]}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = f'{self.host}/fontsearch.php?query={quote(key)}' if page == 1 else f'{self.host}/fontsearch.php?query={quote(key)}&page={page}'
        text = self._fetch(url)
        items = self._parse_list(text)
        has_next = bool(text and re.search(rf'page={page+1}', text))
        return {'list': items, 'page': page, 'pagecount': page + 1 if has_next else page, 'limit': len(items), 'total': len(items)}

    def playerContent(self, flag, id, vipFlags):
        if id.startswith('http') and '.m3u8' in id:
            return {'parse': 0, 'url': id, 'header': {'Referer': self.host + '/', 'User-Agent': self.UA}}
        vid = str(id)
        if '_' in vid: classid, vid = vid.split('_', 1)
        else: classid = '40'
        hdr = {'Referer': self.host + '/', 'User-Agent': self.UA}
        if classid == '41':
            text = self._fetch(f'{self.host}/cili.php?classid={classid}&id={vid}')
            if not text: return {'parse': 1, 'url': f'{self.host}/cili.php?classid={classid}&id={vid}', 'header': hdr}
            reurl_calls = re.findall(r"reurl\('([^']+)'\)", text)
            if reurl_calls:
                binstr = reurl_calls[0]
                hex_hash = ''
                for i in range(0, len(binstr) - 7, 8):
                    chunk = binstr[i:i+8]
                    if len(chunk) < 8: break
                    val = int(chunk, 2) - 10
                    if 48 <= val <= 57 or 97 <= val <= 102: hex_hash += chr(val)
                    else: break
                if hex_hash and len(hex_hash) >= 32:
                    return {'parse': 0, 'url': f'magnet:?xt=urn:btih:{hex_hash}', 'header': hdr}
            return {'parse': 1, 'url': f'{self.host}/cili.php?classid={classid}&id={vid}', 'header': hdr}
        text = self._fetch(f'{self.host}/video.php?classid={classid}&id={vid}')
        if not text: return {'parse': 1, 'url': f'{self.host}/video.php?classid={classid}&id={vid}', 'header': hdr}
        m3u8 = ''
        m = re.search(r'data-raw="(https?://[^"]+\.m3u8)"', text)
        if m: m3u8 = m.group(1)
        if not m3u8:
            m = re.search(r'["\'](https?://[^"\'<>]+\.m3u8)["\']', text)
            if m: m3u8 = m.group(1)
        if not m3u8:
            m = re.search(r'src:\s*["\']([^"\']+\.m3u8)["\']', text)
            if m: m3u8 = m.group(1)
        if not m3u8:
            for sc in re.findall(r'<script[^>]*>(.*?)</script>', text, re.S):
                m = re.search(r'https?://[^\s"\'<>]+\.m3u8', sc)
                if m: m3u8 = m.group(0); break
        full_url = f'{self.host}/video.php?classid={classid}&id={vid}'
        return {'parse': 0 if m3u8 else 1, 'url': m3u8 if m3u8 else full_url, 'header': hdr}
