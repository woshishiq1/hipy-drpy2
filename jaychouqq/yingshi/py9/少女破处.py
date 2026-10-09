# -*- coding: utf-8 -*-
# 作者：蜗牛大叔
import re
import html
import requests
from urllib.parse import quote, unquote
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def getName(self):
        return '少女破处'

    def init(self, extend=''):
        self.host = 'https://83w43wdlty.md-md22.top'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
            'Referer': self.host + '/',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'close',
        })

    def destroy(self):
        pass

    def _get(self, url):
        for _ in range(3):
            try:
                r = self.session.get(url, timeout=15)
                if r.status_code != 200:
                    return ''
                return r.content.decode('utf-8', errors='ignore')
            except Exception:
                continue
        return ''

    def _decode(self, h):
        m = re.search(r'var Words\s*=\s*"([^"]+)"', h)
        if not m:
            return h
        d = re.sub(r'%u([0-9a-fA-F]{4})', lambda x: chr(int(x.group(1), 16)), m.group(1))
        return unquote(d)

    def _abs(self, u):
        if not u:
            return ''
        if u.startswith('http'):
            return u
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('/'):
            return self.host + u
        return self.host + '/' + u

    def _cards(self, h):
        lst = []
        seen = set()
        for m in re.finditer(r'<article>(.*?)</article>', h, re.S):
            block = m.group(1)
            um = re.search(r'href="(/detail/\?\d+\.html)"', block)
            if not um:
                continue
            vid = re.search(r'\?(\d+)\.html', um.group(1))
            if not vid:
                continue
            vid = vid.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            nm = re.search(r'<cite>([^<]+)</cite>', block)
            if not nm:
                nm = re.search(r'alt="([^"]+)"', block)
            name = html.unescape(nm.group(1).strip()) if nm else ''
            if not name:
                continue
            pm = re.search(r'data-src="([^"]+)"', block)
            if not pm:
                pm = re.search(r'<img[^>]*src="([^"]+)"', block)
            pic = self._abs(pm.group(1)) if pm else ''
            lst.append({
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_remarks': '',
            })
        return lst

    def homeContent(self, filter=False):
        try:
            h = self._decode(self._get(self.host + '/'))
            cats = []
            seen = set()
            for u, cid, n in re.findall(r'href="(/list/\?(\d+)\.html)"[^>]*>([^<]{1,12})</a>', h):
                name = n.strip()
                if cid in seen or not name or '更多' in name:
                    continue
                seen.add(cid)
                cats.append({'type_id': cid, 'type_name': html.unescape(name)})
            return {'class': cats}
        except Exception:
            return {'class': []}

    def homeVideoContent(self):
        try:
            return {'list': []}
        except Exception:
            return {'list': []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            pg = int(pg) if str(pg).isdigit() else 1
            url = '{}/list/?{}.html'.format(self.host, tid)
            if pg > 1:
                url = '{}/list/?{}-{}.html'.format(self.host, tid, pg)
            h = self._decode(self._get(url))
            lst = self._cards(h)
            return {'list': lst, 'page': pg, 'pagecount': 9999, 'limit': 20, 'total': 0}
        except Exception:
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 20, 'total': 0}

    def detailContent(self, ids):
        try:
            vid = ids[0]
            url = '{}/detail/?{}.html'.format(self.host, vid)
            h = self._get(url)
            t = re.search(r'<h1[^>]*>([^<]+)</h1>', h)
            name = html.unescape(t.group(1).strip())[:60] if t else ''
            pm = re.search(r'data-src="([^"]+)"', h)
            pic = self._abs(pm.group(1)) if pm else ''
            vod = {
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_content': '',
                'vod_play_from': '少女破处',
                'vod_play_url': '正片${}'.format(url),
            }
            return {'list': [vod]}
        except Exception:
            return {'list': []}

    def searchContent(self, key, quick=None, pg='1'):
        try:
            url = '{}/search.php?searchword={}'.format(self.host, quote(key, safe=''))
            h = self._decode(self._get(url))
            return {'list': self._cards(h)}
        except Exception:
            return {'list': []}

    def _decode_obfuscated_js(self, h):
        try:
            scripts = re.findall(r'<script(?![^>]*src=)[^>]*>(.*?)</script>', h, re.S)
            for s in scripts:
                s = s.strip()
                if len(s) < 100 or 'var b=' not in s:
                    continue
                m = re.search(r'var b=(\{.*?\});', s, re.S)
                if not m:
                    continue
                pairs = re.findall(r'(?:"([^"]+)"|([A-Za-z0-9_]+))\s*:\s*"((?:[^"\\]|\\.)*)"', m.group(1))
                mp = {(qk if qk else bk): v for qk, bk, v in pairs}
                em = re.search(r'var b=a\(`([^`]+)`', s)
                if not em:
                    continue
                dec = ''.join(mp.get(c, c) for c in em.group(1))
                for pat in [r'https?://[^\s"\'<>]+?\.(m3u8|mp4)[^\s"\'<>]*']:
                    mm = re.search(pat, dec)
                    if mm:
                        return mm.group(0)
        except Exception:
            pass
        return ''

    def _parse_player_json(self, h, varname):
        idx = h.find('var {}='.format(varname))
        if idx < 0:
            return None
        seg = h[idx:idx + 12000]
        start = seg.find('{')
        if start < 0:
            return None
        depth = 0
        for i, c in enumerate(seg[start:], start):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(seg[start:i + 1])
                    except Exception:
                        return None
        return None

    def _decode_url(self, url, encrypt):
        if not url:
            return ''
        try:
            if encrypt == 1:
                from urllib.parse import unquote
                return unquote(url)
            if encrypt == 2:
                import base64
                from urllib.parse import unquote
                return unquote(base64.b64decode(unquote(url)).decode('utf-8', errors='ignore'))
        except Exception:
            pass
        return url

    def _extract_play_url(self, h):
        for varname in ['player_aaaa', 'player_data']:
            data = self._parse_player_json(h, varname)
            if data and data.get('url'):
                u = self._decode_url(data['url'], data.get('encrypt', 0))
                if u:
                    return u
        m = re.search(r'MacPlayer\.PlayUrl\s*=\s*["\']([^"\']+)["\']', h)
        if m and m.group(1).strip():
            return m.group(1).strip()
        m = re.search(r"var dp_video_url\s*=\s*['\"]([^'\"]+)['\"]", h)
        if m:
            try:
                import base64
                return base64.b64decode(m.group(1)).decode('utf-8', errors='ignore')
            except Exception:
                pass
        m = re.search(r'<iframe[^>]*src="([^"]+)"', h)
        if m:
            return m.group(1)
        for m in re.finditer(r'"url"\s*:\s*"([^"]+)"', h):
            u = m.group(1).replace('\\/', '/').replace('\\', '')
            if re.search(r'\.(m3u8|mp4)(\?|$)', u) and u.startswith('http'):
                return u
        u = self._decode_obfuscated_js(h)
        if u:
            return u
        return ''

    def playerContent(self, flag, id, vipFlags=None):
        try:
            h = self._get(id)
            url = self._extract_play_url(h)
            if url:
                if url.startswith('/'):
                    url = self._abs(url)
                return {'parse': 0, 'url': url, 'header': {'User-Agent': 'Mozilla/5.0', 'Referer': id}}
            return {'parse': 1, 'url': id}
        except Exception:
            return {'parse': 1, 'url': id}

    def isVideoFormat(self, url):
        u = url.split('?')[0].lower()
        return u.endswith('.m3u8') or u.endswith('.mp4')

    def localProxy(self, param):
        return None
