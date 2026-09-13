#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import re
import sys
import urllib.parse

try:
    import requests
except ImportError:
    requests = None

sys.path.append('../../')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""):
            pass


class Spider(BaseSpider):
    def __init__(self):
        self.siteUrl = 'https://m.uvod.tv'
        self.pcUrl = 'https://www.uvod.tv'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            '1': {'name': '电影', 'paths': ['/vodtype/1.html', '/index.php/vod/type/id/1.html', '/movie', '/vod/show/id/1.html']},
            '2': {'name': '电视剧', 'paths': ['/vodtype/2.html', '/index.php/vod/type/id/2.html', '/tv', '/vod/show/id/2.html']},
            '3': {'name': '综艺', 'paths': ['/vodtype/3.html', '/index.php/vod/type/id/3.html', '/variety', '/vod/show/id/3.html']},
            '4': {'name': '动漫', 'paths': ['/vodtype/4.html', '/index.php/vod/type/id/4.html', '/anime', '/vod/show/id/4.html']},
            '5': {'name': '纪录片', 'paths': ['/vodtype/5.html', '/index.php/vod/type/id/5.html', '/doc', '/vod/show/id/5.html']},
        }

    def getName(self):
        return '优视频 UVOD'

    def init(self, extend=""):
        pass

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Accept': 'text/html,application/json,application/xhtml+xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9',
            }
        try:
            if requests:
                resp = requests.get(url, headers=headers, params=params, timeout=15)
                resp.raise_for_status()
                return resp
            full = url
            if params:
                full += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
            from urllib.request import Request, urlopen
            raw = urlopen(Request(full, headers=headers), timeout=15).read()

            class R:
                def __init__(self, raw):
                    self.text = raw.decode('utf-8', 'ignore')

                def json(self):
                    return json.loads(self.text)

            return R(raw)
        except Exception as e:
            print('请求失败: %s, %s' % (url, e))
            return None

    def fetch_text(self, url, params=None):
        resp = self.fetch(url, params=params)
        return getattr(resp, 'text', '') if resp else ''

    def _abs(self, u):
        if not u:
            return ''
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('/'):
            return self.pcUrl + u
        return u

    def _clean(self, s):
        return re.sub(r'<[^>]+>', '', str(s or '')).strip()

    def _walk(self, obj, acc=None):
        if acc is None:
            acc = []
        if isinstance(obj, dict):
            if (obj.get('vod_id') or obj.get('id')) and (obj.get('vod_name') or obj.get('name') or obj.get('title')):
                acc.append(obj)
            for v in obj.values():
                self._walk(v, acc)
        elif isinstance(obj, list):
            for v in obj:
                self._walk(v, acc)
        return acc

    def _map(self, item):
        vid = str(item.get('vod_id') or item.get('id') or '')
        name = item.get('vod_name') or item.get('name') or item.get('title') or vid
        if not vid:
            return None
        return {
            'vod_id': vid,
            'vod_name': self._clean(name),
            'vod_pic': self._abs(item.get('vod_pic') or item.get('pic') or item.get('cover') or ''),
            'vod_remarks': str(item.get('vod_remarks') or item.get('remarks') or item.get('note') or ''),
        }

    def _parse_html(self, html):
        videos, seen = [], set()
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>', html or '', re.S)
        if m:
            try:
                for item in self._walk(json.loads(m.group(1))):
                    v = self._map(item)
                    if v and v['vod_id'] not in seen:
                        seen.add(v['vod_id'])
                        videos.append(v)
            except Exception:
                pass
        for pat in (
            r'href="([^"]*(?:/vod/detail/id/|/detail/|/video/)(\d+)[^"]*)"[^>]{0,160}(?:title|alt)="([^"]*)"',
            r'href="([^"]*/index\.php/vod/detail/id/(\d+)\.html)"[^>]*>([^<]{2,80})',
        ):
            for g in re.finditer(pat, html or '', re.I):
                vid, name = g.group(2), self._clean(g.group(3) or g.group(2))
                if vid in seen or name in ('详情', '播放'):
                    continue
                seen.add(vid)
                videos.append({'vod_id': vid, 'vod_name': name, 'vod_pic': '', 'vod_remarks': ''})
        for g in re.finditer(
            r'(?:/vod/detail/id/|/detail/)(\d+)[^"]*"[^>]*>[\s\S]{0,200}?(?:src|data-original|data-src)="([^"]+)"',
            html or '',
            re.I,
        ):
            for v in videos:
                if v['vod_id'] == g.group(1) and not v['vod_pic']:
                    v['vod_pic'] = self._abs(g.group(2))
        return videos

    def _load(self, paths):
        videos = []
        for path in paths:
            for host in (self.siteUrl, self.pcUrl):
                url = path if str(path).startswith('http') else host + path
                html = self.fetch_text(url)
                videos = self._parse_html(html)
                if videos:
                    return videos
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            videos = self._load(['/', '/index.php'])
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            info = self.channels.get(str(tid), self.channels['1'])
            paths = list(info.get('paths') or ['/'])
            if pg > 1:
                extra = []
                for p in paths:
                    extra.append(p.replace('.html', '/page/%s.html' % pg))
                    extra.append(p + (('&' if '?' in p else '?') + 'page=' + str(pg)))
                    extra.append(re.sub(r'\.html$', '-%s.html' % pg, p))
                paths = extra
            videos = self._load(paths)
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 12 else pg,
            'limit': 24,
            'total': 9999,
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        try:
            q = urllib.parse.quote(key)
            videos = self._load([
                '/index.php/vod/search/page/%s/wd/%s.html' % (pg, q),
                '/vodsearch/%s----------%s---.html' % (q, pg),
                '/search?q=%s&page=%s' % (q, pg),
                '/index.php/ajax/suggest?mid=1&wd=%s&limit=24' % q,
            ])
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 12 else pg,
            'limit': 24,
            'total': len(videos),
        }

    def _detail_html(self, vid):
        for path in (
            '/index.php/vod/detail/id/%s.html' % vid,
            '/vod/detail/id/%s.html' % vid,
            '/detail/%s.html' % vid,
            '/video/%s.html' % vid,
        ):
            for host in (self.siteUrl, self.pcUrl):
                html = self.fetch_text(host + path)
                if html and len(html) > 400:
                    return html, host + path
        return '', self.pcUrl + '/index.php/vod/detail/id/%s.html' % vid

    def detailContent(self, ids):
        vid = str((ids or [''])[0])
        name, pic, desc, remarks = vid, '', '', ''
        froms, urls = [], []
        try:
            html, page = self._detail_html(vid)
            tm = re.search(r'<title>([^<]+)</title>', html or '')
            if tm:
                name = re.sub(r'\s*[-_|].*$', '', tm.group(1)).strip() or name
            hm = re.search(r'<h[12][^>]*>([^<]{2,80})</h[12]>', html or '')
            if hm:
                name = self._clean(hm.group(1)) or name
            pm = re.search(r'(?:og:image["\']\s+content=["\']|data-original=")([^"\']+)', html or '')
            if pm:
                pic = self._abs(pm.group(1))
            dm = re.search(r'og:description["\']\s+content=["\']([^"\']+)', html or '')
            if dm:
                desc = dm.group(1)
            parts = []
            for href, title in re.findall(
                r'href="(/index\.php/vod/play/id/%s[^"]+\.html)"[^>]*>([^<]{1,40})' % re.escape(vid),
                html or '',
            ):
                t = self._clean(title)
                if t:
                    parts.append('%s$%s%s' % (t, self.pcUrl, href))
            if not parts:
                for href, title in re.findall(
                    r'href="([^"]*(?:/vod/play/|/play/)[^"]+)"[^>]*>([^<]{1,40})',
                    html or '',
                ):
                    t = self._clean(title)
                    if t:
                        parts.append('%s$%s' % (t, self._abs(href)))
            m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or '')
            if m3:
                parts = ['高清$%s' % m3.group(0)] + parts
            if parts:
                froms.append('UVOD')
                urls.append('#'.join(parts))
        except Exception as e:
            print('获取详情失败: %s' % e)
        if not urls:
            froms = ['UVOD']
            urls = ['播放$%s/index.php/vod/play/id/%s.html' % (self.pcUrl, vid)]
        return {'list': [{
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': remarks,
            'vod_content': (desc or '').strip(),
            'vod_play_from': '$$$'.join(froms),
            'vod_play_url': '$$$'.join(urls),
        }]}

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.pcUrl + '/',
            'Origin': self.pcUrl,
        }
        play_url = str(id or '')
        if self.isVideoFormat(play_url):
            return {'parse': 0, 'url': play_url, 'header': header}
        html = self.fetch_text(play_url if play_url.startswith('http') else self.pcUrl + play_url)
        pa = re.search(r'player_aaaa\s*=\s*(\{[\s\S]*?\})', html or '')
        if pa:
            raw = pa.group(1).replace("'", '"')
            um = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
            if um:
                u = um.group(1).replace('\\/', '/')
                p = 0 if self.isVideoFormat(u) else 1
                return {'parse': p, 'jx': '1' if p else '0', 'url': u, 'header': header}
        m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or '')
        if m3:
            return {'parse': 0, 'url': m3.group(0).replace('\\/', '/'), 'header': header}
        return {
            'parse': 1,
            'jx': '1',
            'url': play_url if play_url.startswith('http') else self.pcUrl + '/index.php/vod/play/id/' + play_url + '.html',
            'header': header,
        }

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        return any(x in u for x in ('.mp4', '.m3u8', '.flv', '.mpd'))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None


if __name__ == '__main__':
    spider = Spider()
    print(json.dumps(spider.homeContent(True), ensure_ascii=False, indent=2))
