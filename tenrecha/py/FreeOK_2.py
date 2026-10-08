# -*- coding: utf-8 -*-
# FreeOK (https://www.freeok88.com) · catvod/py-drpy Spider · 遮天法·四极境
from base.spider import Spider as BaseSpider
import re
import json
import base64
import urllib.request
from urllib.parse import quote, unquote, urljoin

try:
    import requests
    requests.packages.urllib3.disable_warnings()
except ImportError:
    requests = None


class Spider(BaseSpider):
    host = "https://www.freeok88.com"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': host + '/',
    }
    REALM = 3

    def __init__(self):
        super().__init__()
        self.session = requests.Session() if requests else None
        if self.session:
            self.session.verify = False
            self.session.headers.update(self.headers)
        self._debug = True
        self._cats = None

    def _log(self, msg):
        if self._debug:
            print('[freeok88] ' + str(msg))

    def getName(self):
        return 'FreeOK'

    def isVideoFormat(self, url):
        if not url:
            return False
        return any(x in url for x in ['.m3u8', '.mp4', '.flv', '.ts']) or url.startswith('magnet:')

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if getattr(self, 'session', None):
            try:
                self.session.close()
            except Exception:
                pass

    def localProxy(self, param):
        EMPTY_GIF = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
        if not param or not param.startswith('http'):
            return [200, 'image/gif', EMPTY_GIF]
        try:
            r = self.session.get(param, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15) if self.session else urllib.request.urlopen(urllib.request.Request(param, headers=self.headers), timeout=15)
            data = r.read() if not self.session else r.content
            ctype = r.headers.get('Content-Type', 'application/octet-stream') if not self.session else r.headers.get('Content-Type', 'application/octet-stream')
            return [200, ctype, data]
        except Exception:
            return [200, 'image/gif', EMPTY_GIF]

    def _fetch(self, url, referer=None, timeout=15):
        headers = dict(self.headers)
        if referer:
            headers['Referer'] = referer
        if self.session:
            try:
                r = self.session.get(url, headers=headers, timeout=timeout, verify=False)
                r.encoding = 'utf-8'
                if r.status_code == 200:
                    return r.text
                self._log('status %s %s' % (r.status_code, url))
                return ''
            except Exception as e:
                self._log(e)
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                enc = resp.headers.get('Content-Encoding', '')
                if enc == 'gzip':
                    import gzip
                    data = gzip.decompress(data)
                elif enc == 'deflate':
                    import zlib
                    data = zlib.decompress(data)
                return data.decode('utf-8', errors='ignore')
        except Exception as e:
            self._log(e)
        return ''

    @staticmethod
    def _clean(text):
        if not text:
            return ''
        text = re.sub(r'<[^>]+>', '', str(text))
        for old, new in {'&nbsp;': ' ', '&amp;': '&', '&quot;': '"', '&lt;': '<', '&gt;': '>'}.items():
            text = text.replace(old, new)
        return re.sub(r'\s+', ' ', text).strip()

    @staticmethod
    def _fix(u, base):
        if not u:
            return ''
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('/'):
            return urljoin(base, u)
        if u.startswith('http'):
            return u
        return urljoin(base, '/' + u)

    @staticmethod
    def _b64decode(s):
        try:
            pad = 4 - len(s) % 4
            if pad != 4:
                s += '=' * pad
            return base64.b64decode(s).decode('utf-8', errors='ignore')
        except Exception:
            return s

    def _parse_list(self, html):
        if not html:
            return []
        out, seen = [], set()
        for box in re.findall(r'<li[^>]*>\s*<div class="stui-vodlist__box">(.*?)</div>\s*</li>', html, re.S):
            try:
                a = re.search(r'<a[^>]*href="(/video/[^"]+)"[^>]*title="([^"]*)"', box) or re.search(r'<a class="db"[^>]*href="([^"]+)"[^>]*title="([^"]*)"', box)
                if not a:
                    continue
                link, title = a.group(1), a.group(2)
                pic = re.search(r'data-original="([^"]+)"', box)
                pic = self._fix(pic.group(1), self.host) if pic else ''
                rem = re.search(r'class="pic-text[^"]*"[^>]*>([^<]*)<', box)
                vid = self._fix(link, self.host)
                if vid and vid not in seen:
                    seen.add(vid)
                    out.append({
                        'vod_id': vid,
                        'vod_name': self._clean(title),
                        'vod_pic': pic,
                        'vod_remarks': self._clean(rem.group(1)) if rem else '',
                    })
            except Exception:
                continue
        return out

    def homeContent(self, filter):
        html = self._fetch(self.host + '/')
        if not html:
            return {'class': [], 'list': []}
        classes, seen = [], set()
        for href, slug, body in re.findall(r'href="(/vodshow/([a-z]+)-----------\.html)"[^>]*>(.*?)</a>', html, re.S):
            name = self._clean(body)
            if slug in seen or not name:
                continue
            seen.add(slug)
            classes.append({'type_name': name, 'type_id': slug})
        self._cats = classes
        return {'class': classes, 'list': self._parse_list(html)}

    def homeVideoContent(self):
        return {'list': self._parse_list(self._fetch(self.host + '/'))}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if str(pg).isdigit() else 1
        url = '%s/vodshow/%s-----------%s.html' % (self.host, tid, page) if page > 1 else '%s/vodshow/%s-----------.html' % (self.host, tid)
        html = self._fetch(url, referer=self.host + '/')
        videos = self._parse_list(html) if html else []
        return {'list': videos, 'page': page, 'pagecount': page + 1, 'limit': len(videos), 'total': 999999}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) else ids
        url = vid if vid.startswith('http') else self._fix(vid, self.host)
        html = self._fetch(url, referer=self.host + '/')
        if not html:
            return {'list': []}
        m = re.search(r'<h1[^>]*class="title"[^>]*>([^<]+)</h1>', html)
        name = self._clean(m.group(1)) if m else ''
        pic = ''
        mp = re.search(r'<img[^>]*data-original="([^"]+)"', html)
        if mp:
            pic = self._fix(mp.group(1), self.host)
        content = ''
        md = re.search(r'<meta name="description" content="([^"]*)"', html, re.I)
        if md:
            content = md.group(1).split('FreeOK提供')[0].strip()

        def meta(label):
            pat = r'<span class="text-muted[^"]*">%s[：:]</span>(.*?)(?=<span class="text-muted[^"]*">|</div>)' % re.escape(label)
            mm = re.search(pat, html, re.S)
            if not mm:
                return ''
            return ','.join(x.strip() for x in re.findall(r'<a[^>]*>([^<]+)</a>', mm.group(1)) if x.strip())

        actor = meta('主演') or meta('演员')
        director = meta('导演')
        area = meta('地区') or meta('国家')
        year = meta('年份') or meta('年代')
        vtype = meta('类型')
        froms, urls = [], []
        for ul in re.findall(r'<ul class="stui-content__playlist[^"]*"[^>]*>(.*?)</ul>', html, re.S):
            eps = re.findall(r'<li[^>]*>\s*<a[^>]*href="(/play/[^"]+)"[^>]*>([^<]*)</a>', ul)
            if not eps:
                continue
            parts = []
            for i, (h, t) in enumerate(eps, 1):
                parts.append('%s$%s' % (t.strip() or str(i), self._fix(h, self.host)))
            if parts:
                froms.append('FreeOK')
                urls.append('#'.join(parts))
        return {'list': [{
            'vod_id': url,
            'vod_name': name,
            'vod_pic': pic,
            'vod_year': year,
            'vod_area': area,
            'vod_actor': actor,
            'vod_director': director,
            'vod_class': vtype,
            'vod_content': content,
            'vod_play_from': '$$$'.join(froms),
            'vod_play_url': '$$$'.join(urls),
        }]}

    def searchContent(self, key, quick=False, pg="1"):
        page = int(pg) if str(pg).isdigit() else 1
        url = '%s/so/-------------.html?wd=%s' % (self.host, quote(key))
        html = self._fetch(url, referer=self.host + '/')
        videos = self._parse_list(html) if html else []
        return {'list': videos, 'page': page, 'pagecount': page + 1, 'limit': len(videos), 'total': 999999}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {'parse': 0, 'url': '', 'header': {}, 'playUrl': ''}
        if any(x in id for x in ['.m3u8', '.mp4', '.flv', '.ts']):
            return {'parse': 0, 'url': id, 'header': {'User-Agent': self.headers['User-Agent'], 'Referer': self.host + '/'}, 'playUrl': ''}
        html = self._fetch(id, referer=self.host + '/')
        if not html:
            return {'parse': 1, 'url': id, 'header': {}, 'playUrl': ''}
        url = ''
        pm = re.search(r'var\s+player_[a-z]+\s*=\s*(\{.*?\})\s*;?', html, re.S)
        if pm:
            try:
                pdata = json.loads(pm.group(1))
                u = pdata.get('url', '')
                if u:
                    url = u.replace('\\/', '/')
            except Exception:
                pass
        if not url:
            dm = re.search(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4|flv)(?:[^\s"\'<>]*)?)', html)
            if dm:
                url = dm.group(1)
        if not url:
            im = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I)
            if im:
                src = self._fix(im.group(1), id)
                if any(k in src for k in ['play', 'm3u8', 'embed', 'player']):
                    return {'parse': 1, 'url': src, 'header': {'Referer': id}, 'playUrl': ''}
        if not url:
            for b in re.findall(r'["\']([A-Za-z0-9+/]{20,}={0,2})["\']', html):
                try:
                    dec = self._b64decode(b)
                    if dec.startswith('http') and any(e in dec for e in ['.m3u8', '.mp4']):
                        url = dec
                        break
                except Exception:
                    pass
        if not url:
            return {'parse': 1, 'url': id, 'header': {}, 'playUrl': ''}
        return {'parse': 0, 'url': url, 'header': {'User-Agent': self.headers['User-Agent'], 'Referer': self.host + '/'}, 'playUrl': ''}
