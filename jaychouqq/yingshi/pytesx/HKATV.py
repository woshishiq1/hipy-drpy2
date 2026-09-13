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
        self.siteUrl = 'https://www.hkatv.com'
        self.userAgent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        self.channels = {
            'drama': {'name': '劇集', 'paths': ['/zh-HK/drama', '/zh-HK/series', '/drama']},
            'movie': {'name': '電影', 'paths': ['/zh-HK/movie', '/movie']},
            'variety': {'name': '綜藝', 'paths': ['/zh-HK/variety', '/variety', '/zh-HK/show']},
            'news': {'name': '新聞資訊', 'paths': ['/zh-HK/news', '/news']},
            'classic': {'name': '經典', 'paths': ['/zh-HK', '/', '/en-US']},
        }

    def getName(self):
        return '亞洲電視 ATV'

    def init(self, extend=""):
        pass

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Accept': 'text/html,application/json,application/xhtml+xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-HK,zh-TW;q=0.9,zh;q=0.8,en;q=0.7',
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

    def fetch_json(self, url, params=None):
        resp = self.fetch(url, params=params)
        if not resp:
            return {}
        try:
            return resp.json()
        except Exception:
            text = getattr(resp, 'text', '') or ''
            m = re.search(r'\{[\s\S]+\}', text)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    return {}
            return {}

    def _abs(self, u):
        if not u:
            return ''
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('/'):
            return self.siteUrl + u
        return u

    def _walk(self, obj, acc=None):
        if acc is None:
            acc = []
        if isinstance(obj, dict):
            if (obj.get('id') or obj.get('vod_id') or obj.get('videoId')) and (
                obj.get('title') or obj.get('name')
            ):
                acc.append(obj)
            for v in obj.values():
                self._walk(v, acc)
        elif isinstance(obj, list):
            for v in obj:
                self._walk(v, acc)
        return acc

    def _map(self, item):
        vid = str(item.get('id') or item.get('vod_id') or item.get('videoId') or item.get('slug') or '')
        title = item.get('title') or item.get('name') or item.get('vod_name') or vid
        if not vid:
            return None
        pic = item.get('cover') or item.get('poster') or item.get('image') or item.get('thumb') or item.get('vod_pic') or ''
        remarks = item.get('remark') or item.get('update') or item.get('category') or ''
        return {
            'vod_id': vid,
            'vod_name': re.sub(r'<[^>]+>', '', str(title)),
            'vod_pic': self._abs(pic),
            'vod_remarks': str(remarks),
        }

    def _parse_html(self, html):
        videos = []
        seen = set()
        for m in re.finditer(
            r'href="([^"]*(?:/play/|/video/|/vod/|/detail/|/watch/)([^"/\s?]+))"[^>]{0,240}(?:title|alt)="([^"]*)"',
            html or '',
            re.I,
        ):
            vid, name = m.group(2), m.group(3) or m.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            videos.append({'vod_id': vid, 'vod_name': name, 'vod_pic': '', 'vod_remarks': ''})
        for m in re.finditer(r'<script type="application/ld\+json">(\{.*?\})</script>', html or '', re.S):
            try:
                js = json.loads(m.group(1))
            except Exception:
                continue
            for item in self._walk(js):
                v = self._map(item)
                if v and v['vod_id'] not in seen:
                    seen.add(v['vod_id'])
                    videos.append(v)
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>', html or '', re.S)
        if m:
            try:
                data = json.loads(m.group(1))
                for item in self._walk(data.get('props') or data):
                    v = self._map(item)
                    if v and v['vod_id'] not in seen:
                        seen.add(v['vod_id'])
                        videos.append(v)
            except Exception:
                pass
        return videos

    def _load_list(self, paths):
        videos = []
        for path in paths:
            url = path if path.startswith('http') else self.siteUrl + path
            html = self.fetch_text(url)
            videos.extend(self._parse_html(html))
            if videos:
                break
            for api in (
                self.siteUrl + '/api/vod/list',
                self.siteUrl + '/api/video/list',
                self.siteUrl + path + '?format=json',
            ):
                js = self.fetch_json(api)
                if js:
                    for item in self._walk(js):
                        v = self._map(item)
                        if v:
                            videos.append(v)
                    if videos:
                        break
        out, seen = [], set()
        for v in videos:
            if v['vod_id'] in seen:
                continue
            seen.add(v['vod_id'])
            out.append(v)
        return out

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            videos = self._load_list(['/zh-HK', '/', '/en-US'])
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            info = self.channels.get(str(tid), self.channels['classic'])
            paths = list(info.get('paths') or ['/'])
            if pg > 1:
                paths = [p + (('&' if '?' in p else '?') + 'page=' + str(pg)) for p in paths]
            videos = self._load_list(paths)
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 8 else pg,
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
            videos = self._load_list([
                '/zh-HK/search?q=' + q,
                '/search?keyword=' + q,
                '/en-US/search?q=' + q,
            ])
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg,
            'limit': 24,
            'total': len(videos),
        }

    def detailContent(self, ids):
        vid = str((ids or [''])[0])
        name, pic, desc, remarks = vid, '', '', ''
        parts = []
        try:
            html = ''
            for path in (
                '/zh-HK/play/' + vid,
                '/play/' + vid,
                '/zh-HK/video/' + vid,
                '/video/' + vid,
                '/watch/' + vid,
            ):
                html = self.fetch_text(self.siteUrl + path)
                if html and len(html) > 400:
                    break
            tm = re.search(r'<title>([^<]+)</title>', html or '')
            if tm:
                name = re.sub(r'\s*[-_|].*$', '', tm.group(1)).strip() or name
            pm = re.search(r'og:image["\']\s+content=["\']([^"\']+)', html or '')
            if pm:
                pic = self._abs(pm.group(1))
            dm = re.search(r'og:description["\']\s+content=["\']([^"\']+)', html or '')
            if dm:
                desc = dm.group(1)
            for href, title in re.findall(
                r'href="([^"]*(?:/play/|/video/)([^"/\s?]+))"[^>]{0,160}>([^<]{1,40})',
                html or '',
                re.I,
            ):
                ep = title.strip() or href
                play = self._abs(href)
                parts.append('%s$%s' % (ep, play))
            if not parts:
                yt = re.search(r'(?:youtube\.com/embed/|youtu\.be/)([A-Za-z0-9_-]{6,})', html or '')
                if yt:
                    parts.append('YouTube$https://www.youtube.com/watch?v=%s' % yt.group(1))
            m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or '')
            if m3:
                parts = ['高清$%s' % m3.group(0)] + parts
        except Exception as e:
            print('获取详情失败: %s' % e)
        if not parts:
            parts.append('Play$%s/play/%s' % (self.siteUrl, vid))
        return {
            'list': [{
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_remarks': remarks or ('%s EP' % len(parts) if len(parts) > 1 else 'ATV'),
                'vod_content': (desc or '').strip(),
                'vod_play_from': 'ATV',
                'vod_play_url': '#'.join(parts),
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
            'Origin': self.siteUrl,
        }
        play_url = str(id or '')
        if self.isVideoFormat(play_url):
            return {'parse': 0, 'url': play_url, 'header': header}
        return {'parse': 1, 'jx': '1', 'url': play_url, 'header': header}

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
