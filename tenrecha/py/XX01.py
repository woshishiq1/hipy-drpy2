# coding: utf-8

import html as html_lib
import json
import re
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

import requests
from pyquery import PyQuery as pq

import sys
sys.path.append('..')
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def init(self, extend=""):
        cfg = {}
        if isinstance(extend, dict):
            cfg = extend
        elif isinstance(extend, str) and extend.strip():
            try:
                cfg = json.loads(extend)
            except Exception:
                cfg = {}

        self.host = (cfg.get('host') or 'https://xx01.com').rstrip('/')
        self.proxies = cfg.get('proxies') or None
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.host + '/',
        }

    def getName(self):
        return "XX01"

    def isVideoFormat(self, url):
        u = (url or '').lower()
        return any(x in u for x in ('.m3u8', '.mp4', '.ts'))

    def manualVideoCheck(self):
        return False

    def _get(self, url, **kwargs):
        headers = dict(self.headers)
        headers.update(kwargs.pop('headers', {}) or {})
        r = self.session.get(url, headers=headers, proxies=self.proxies, timeout=15, **kwargs)
        r.encoding = r.apparent_encoding
        return r

    def _normalize_url(self, tid: str) -> str:
        if not tid:
            return self.host + '/'
        u = tid if tid.startswith('http') else urljoin(self.host + '/', tid.lstrip('/'))
        sp = urlsplit(u)
        path = quote(unquote(sp.path), safe='/')
        return urlunsplit((sp.scheme, sp.netloc, path, sp.query, sp.fragment))

    @staticmethod
    def _is_detail_href(href: str) -> bool:
        if not href or not href.startswith('/'):
            return False
        if href.startswith(('/search/', '/genres', '/actresses', '/ranking', '/new', '/uncensored', '/chinese-subtitle', '/dm')):
            return False
        return href.count('/') == 1 and len(href) > 2

    def _parse_cards(self, html: str):
        d = pq(html)
        out, seen = [], set()

        for a in d('a[href]').items():
            href = (a.attr('href') or '').strip()
            if not self._is_detail_href(href):
                continue

            img = a.find('img[data-src]')
            if not img or not (img.attr('data-src') or '').strip():
                img = a.find('img.lozad')
            if not img:
                continue

            title = (img.attr('alt') or '').strip()
            pic = (img.attr('data-src') or img.attr('src') or '').strip()
            if not title or not pic:
                continue

            low = pic.lower()
            if not (low.startswith('http://') or low.startswith('https://')):
                continue
            if any(x in low for x in ('/img/flags/', 'favicon', 'logo')):
                continue

            vid = urljoin(self.host + '/', href)
            if vid in seen:
                continue
            seen.add(vid)

            remark = a.parent().find('span.absolute.bottom-1.right-1').text().strip()
            out.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': remark,
                'style': {"type": "rect", "ratio": 1.33},
            })

        return out

    def homeContent(self, filter):
        classes = [
            {'type_name': '中文字幕', 'type_id': '/chinese-subtitle'},
            {'type_name': '国产AV', 'type_id': '/madou'},
            {'type_name': '欧美大片', 'type_id': '/genres/外国女优'},
            {'type_name': '猎奇', 'type_id': '/PLANTSVSCUNTS'},
            {'type_name': 'kinostream', 'type_id': '/kinostream'},
            {'type_name': '时间工作室', 'type_id': '/TIMESTUDIO'},
            {'type_name': '日本AV', 'type_id': '/jav'},
            {'type_name': '素人', 'type_id': '/amateur'},
            {'type_name': '无码影片', 'type_id': '/uncensored'},
            {'type_name': '亚洲AV', 'type_id': '/madou-menu'},
        ]

        filters = {
            '/jav': [{'key': 'type', 'name': '子分类', 'value': [
                {'n': '最近更新', 'v': '/new'},
                {'n': '新作上市', 'v': '/release'},
                {'n': '无码流出', 'v': '/uncensored-leak'},
                {'n': '类型', 'v': '/genres'},
                {'n': 'VR', 'v': '/VR'},
                {'n': 'AV解说', 'v': '/avtalk'},
            ]}],
            '/amateur': [{'key': 'type', 'name': '子分类', 'value': [
                {'n': 'SIRO', 'v': '/siro'},
                {'n': 'LUXU', 'v': '/luxu'},
                {'n': 'GANA', 'v': '/gana'},
                {'n': 'PRESTIGE PREMIUM', 'v': '/maan'},
                {'n': 'S-CUTE', 'v': '/scute'},
                {'n': 'ARA', 'v': '/ara'},
            ]}],
            '/uncensored': [{'key': 'type', 'name': '子分类', 'value': [
                {'n': '无码流出', 'v': '/uncensored-leak'},
                {'n': 'FC2', 'v': '/fc2'},
                {'n': 'HEYZO', 'v': '/heyzo'},
                {'n': '东京热', 'v': '/tokyohot'},
                {'n': '一本道', 'v': '/1pondo'},
                {'n': 'Caribbeancom', 'v': '/caribbeancom'},
                {'n': 'Caribbeancompr', 'v': '/caribbeancompr'},
                {'n': '10musume', 'v': '/10musume'},
                {'n': 'pacopacomama', 'v': '/pacopacomama'},
                {'n': 'Gachinco', 'v': '/gachinco'},
                {'n': 'XXX-AV', 'v': '/xxxav'},
                {'n': '人妻斬', 'v': '/marriedslash'},
                {'n': '頑皮 4610', 'v': '/naughty4610'},
                {'n': '頑皮 0930', 'v': '/naughty0930'},
            ]}],
            '/madou-menu': [{'key': 'type', 'name': '子分类', 'value': [
                {'n': '麻豆传媒', 'v': '/madou'},
                {'n': 'TWAV', 'v': '/twav'},
                {'n': 'Furuke', 'v': '/furuke'},
                {'n': '韩国直播', 'v': '/klive'},
                {'n': '中国直播', 'v': '/clive'},
                {'n': '抖阴视频', 'v': '/tiktok'},
                {'n': '明星换脸', 'v': '/starface'},
                {'n': '主播直播', 'v': '/cnlive'},
                {'n': '国产传媒', 'v': '/cmedia'},
                {'n': '玩偶姐姐', 'v': '/playgirl'},
                {'n': '网曝门', 'v': '/netdoor'},
            ]}],
        }

        r = self._get(self.host + '/')
        return {'class': classes, 'filters': filters, 'list': self._parse_cards(r.text)}

    def homeVideoContent(self):
        r = self._get(self.host + '/')
        return {'list': self._parse_cards(r.text)}

    def _keyword_list(self, keyword: str, pg: int):
        keyword = (keyword or '').strip()
        if not keyword:
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 90, 'total': 0}

        base = f"{self.host}/search/{quote(keyword)}"
        url = base if pg == 1 else f"{base}/{pg}"
        r = self._get(url)
        return {'list': self._parse_cards(r.text), 'page': pg, 'pagecount': 9999, 'limit': 90, 'total': 999999}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        if isinstance(tid, str):
            if tid.startswith('actress:'):
                return self._keyword_list(tid.split(':', 1)[1], pg)
            if tid.startswith('maker:'):
                return self._keyword_list(tid.split(':', 1)[1], pg)

        if isinstance(extend, dict) and extend.get('type'):
            tid = extend['type']

        default_sub = {
            '/jav': '/new',
            '/amateur': '/siro',
            '/uncensored': '/uncensored-leak',
            '/madou-menu': '/madou',
        }
        if tid in default_sub:
            tid = default_sub[tid]

        base = self._normalize_url(str(tid).rstrip('/'))
        url = base if pg == 1 else f"{base}{'&' if '?' in base else '?'}page={pg}"
        r = self._get(url)
        return {'list': self._parse_cards(r.text), 'page': pg, 'pagecount': 9999, 'limit': 90, 'total': 999999}

    @staticmethod
    def _to_base(n: int, base: int) -> str:
        digits = "0123456789abcdefghijklmnopqrstuvwxyz"
        if n == 0:
            return "0"
        s = ""
        while n:
            s = digits[n % base] + s
            n //= base
        return s

    def _unpack_packer(self, html: str) -> str:
        m = re.search(
            r"function\(p,a,c,k,e,d\)\{.*?\}\(\s*(['\"])(?P<p>.*?)\1\s*,\s*(?P<a>\d+)\s*,\s*(?P<c>\d+)\s*,\s*(['\"])(?P<k>.*?)\5\.split\(\s*['\"]\|['\"]\s*\)",
            html,
            flags=re.S,
        )
        if not m:
            return ""

        p = m.group('p')
        a = int(m.group('a'))
        c = int(m.group('c'))
        k = m.group('k').split('|')
        token_base = 36 if 'toString(36)' in m.group(0) else a

        for i in range(c - 1, -1, -1):
            if i < len(k) and k[i]:
                key = self._to_base(i, token_base)
                p = re.sub(rf"\b{re.escape(key)}\b", k[i], p)
        return p

    @staticmethod
    def _normalize_js_text(text: str) -> str:
        if not text:
            return ""
        return (text
                .replace('\\/', '/')
                .replace('\\u0026', '&')
                .replace('\\u003d', '=')
                .replace('\\u003f', '?')
                .replace('\\u002f', '/')
                .replace('\\\\', '\\'))

    def _extract_media_list(self, html: str):
        text = self._unpack_packer(html) or html
        text = html_lib.unescape(text)
        text = self._normalize_js_text(text)

        medias = []
        for u in re.findall(r"https?://[^\s'\"<>]+?\.m3u8[^\s'\"<>]*", text, flags=re.I):
            u = u.rstrip('\\').rstrip('"\'')
            if u:
                medias.append(('m3u8', u))
        for u in re.findall(r"https?://[^\s'\"<>]+?\.mp4[^\s'\"<>]*", text, flags=re.I):
            u = u.rstrip('\\').rstrip('"\'')
            if u:
                medias.append(('mp4', u))

        seen, out = set(), []
        for t, u in medias:
            if u not in seen:
                out.append((t, u))
                seen.add(u)
        return out

    def detailContent(self, ids):
        url = ids[0]
        if not url.startswith('http'):
            url = urljoin(self.host + '/', url.lstrip('/'))

        html = self._get(url).text
        d = pq(html)

        title = (d('meta[property="og:title"]').attr('content') or '').strip() or (d('title').text() or '').strip()
        pic = (d('meta[property="og:image"]').attr('content') or '').strip()

        def cr(prefix: str, name: str) -> str:
            payload = {"id": f"{prefix}:{name}", "name": name}
            return f'[a=cr:{json.dumps(payload, ensure_ascii=False)}/]{name}[/a]'

        actors = []
        for a in d('a[href^="/actresses/"]').items():
            name = (a.text() or '').strip()
            if name:
                actors.append(cr('actress', name))
        vod_actor = ' '.join(actors)

        maker_name = (d('a[href^="/dm2/makers/"]').eq(0).text() or '').strip()
        maker_line = f"发行商: {cr('maker', maker_name)}" if maker_name else ''

        intro = (d('div.mb-1.text-secondary.break-all').eq(0).text() or '').strip()
        if not intro:
            intro = (d('meta[property="og:description"]').attr('content') or '').strip()

        medias = self._extract_media_list(html)
        is_plantsvscunts = urlsplit(url).path.upper().startswith('/PLANTSVSCUNTS-')

        best_url = ''
        if medias:
            def score(u: str) -> int:
                u = (u or '').lower()
                s = 0
                if is_plantsvscunts:
                    if '/videos/fullhd/' in u or '/videos/' in u:
                        s += 10000
                    if '/previews/' in u or 'preview.mp4' in u:
                        s -= 10000
                if '2160' in u or '4k' in u:
                    s += 4000
                if '1080' in u:
                    s += 3000
                if '720' in u:
                    s += 2000
                if '480' in u:
                    s += 1000
                if 'playlist' in u or 'master' in u:
                    s += 1500
                return s

            m3 = [u for t, u in medias if t == 'm3u8']
            mp4 = [u for t, u in medias if t == 'mp4']
            pool = m3 or mp4
            if pool:
                best_url = max(pool, key=score)

        if best_url:
            if is_plantsvscunts:
                vod_play_url = f"完整版${best_url}"
            else:
                is_sensitive = any(x in url.lower() for x in ('/timestudio', '/kinostream'))
                if is_sensitive or ('pl2.vvvvvvvv.top' in best_url or 'pl3.vvvvvvvv.top' in best_url):
                    final = best_url
                else:
                    final = 'https://pl3.vvvvvvvv.top/api/play?url=' + (quote(best_url, safe='') if '&' in best_url else best_url)
                vod_play_url = f"高清${final}"
        else:
            vod_play_url = f"网页播放${url}"

        content_parts = [x for x in (maker_line, intro) if x]
        vod_content = '\n'.join(content_parts) if content_parts else title

        return {
            'list': [{
                'vod_id': url,
                'vod_name': title,
                'vod_pic': pic,
                'vod_actor': vod_actor,
                'vod_content': vod_content,
                'vod_play_from': 'XX01',
                'vod_play_url': vod_play_url,
            }]
        }

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        base = f"{self.host}/search/{quote(str(key).strip())}"
        url = base if pg == 1 else f"{base}/{pg}"
        r = self._get(url)
        return {'list': self._parse_cards(r.text), 'page': pg, 'pagecount': 9999}

    def playerContent(self, flag, id, vipFlags):
        h = dict(self.headers)
        h.setdefault('Origin', self.host)
        h.setdefault('Accept', '*/*')
        h.setdefault('Connection', 'keep-alive')
        return {'parse': 0, 'url': id, 'header': h}
