# -*- coding: utf-8 -*-
# 作者：蜗牛大叔
import re
import json
import html
import requests
from urllib.parse import quote
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def getName(self):
        return '66在线'

    def init(self, extend=''):
        self.host = 'https://442855.66sp025.top'
        self.base = self.host + '/liuliu'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
            'Referer': self.base + '/',
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

    def _abs(self, u):
        if not u:
            return ''
        if u.startswith('http'):
            return u
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('/'):
            return self.host + u
        return self.base + '/' + u

    def _pick_pic(self, block):
        for attr in ['data-original', 'data-src', 'src']:
            m = re.search(r'<img[^>]*?\b' + attr + r'="([^"]+)"', block)
            if m:
                u = m.group(1).strip()
                if not u or 'data:image' in u:
                    continue
                low = u.lower()
                if any(k in low for k in ['loading', 'load.svg', 'placeholder', 'blank']):
                    continue
                return self._abs(u)
        return ''

    def _cards(self, h):
        lst = []
        seen = set()
        for m in re.finditer(r'<li>(.*?)</li>', h, re.S):
            block = m.group(1)
            um = re.search(r'href="(/liuliu/index\.php/vod/play/id/(\d+)/sid/\d+/nid/\d+\.html)"', block)
            if not um:
                continue
            vid = um.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            nm = re.search(r'<h5><a[^>]*>([^<]+)</a></h5>', block)
            name = html.unescape(nm.group(1).strip()) if nm else ''
            if not name:
                continue
            lst.append({
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': self._pick_pic(block),
                'vod_remarks': '',
            })
        return lst

    def homeContent(self, filter=False):
        try:
            h = self._get(self.base + '/')
            cats = []
            seen = set()
            for cid, n in re.findall(r'href="/liuliu/index\.php/vod/type/id/(\d+)\.html"[^>]*>\s*<span>([^<]{1,15})</span>', h):
                name = n.strip()
                if cid in seen or not name:
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
            url = '{}/index.php/vod/type/id/{}.html'.format(self.base, tid)
            if pg > 1:
                url = '{}/index.php/vod/type/id/{}/page/{}.html'.format(self.base, tid, pg)
            h = self._get(url)
            lst = self._cards(h)
            return {'list': lst, 'page': pg, 'pagecount': 9999, 'limit': 20, 'total': 0}
        except Exception:
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 20, 'total': 0}

    def detailContent(self, ids):
        try:
            vid = ids[0]
            play_url = '{}/index.php/vod/play/id/{}/sid/1/nid/1.html'.format(self.base, vid)
            h = self._get(play_url)
            t = re.search(r'<title>([^<]+)</title>', h)
            name = ''
            if t:
                name = html.unescape(t.group(1).split('-')[0].split('_')[0].split('在线播放')[0].strip())
            vod = {
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': self._pick_pic(h),
                'vod_content': '',
                'vod_play_from': '66在线',
                'vod_play_url': '正片${}'.format(play_url),
            }
            return {'list': [vod]}
        except Exception:
            return {'list': []}

    def searchContent(self, key, quick=None, pg='1'):
        try:
            url = '{}/index.php/vod/search/wd/{}.html'.format(self.base, quote(key, safe=''))
            h = self._get(url)
            return {'list': self._cards(h)}
        except Exception:
            return {'list': []}

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
        m = re.search(r'<iframe[^>]*src="([^"]+)"', h)
        if m:
            return m.group(1)
        for m in re.finditer(r'"url"\s*:\s*"([^"]+)"', h):
            u = m.group(1).replace('\\/', '/').replace('\\', '')
            if re.search(r'\.(m3u8|mp4)(\?|$)', u) and u.startswith('http'):
                return u
        return ''

    def playerContent(self, flag, id, vipFlags=None):
        try:
            h = self._get(id)
            url = self._extract_play_url(h)
            if not url:
                return {'parse': 1, 'url': id}
            if url.startswith('/'):
                url = self._abs(url)
            return {'parse': 0, 'url': url, 'header': {'User-Agent': 'Mozilla/5.0', 'Referer': id}}
        except Exception:
            return {'parse': 1, 'url': id}

    def isVideoFormat(self, url):
        u = url.split('?')[0].lower()
        return u.endswith('.m3u8') or u.endswith('.mp4')

    def localProxy(self, param):
        return None
