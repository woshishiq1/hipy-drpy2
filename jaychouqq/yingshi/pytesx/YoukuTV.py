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
        self.siteUrl = 'https://youku.tv'
        self.mSite = 'https://m.youku.tv'
        self.searchApi = 'https://search.youku.com/api/search'
        self.showApi = 'https://openapi.youku.com/v2/shows/videos.json'
        self.clientId = '53e6cc67237fc59a'
        self.userAgent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        self.channels = {
            'tv': {'name': 'Drama', 'keyword': '电视剧'},
            'movie': {'name': 'Movie', 'keyword': '电影'},
            'variety': {'name': 'Variety', 'keyword': '综艺'},
            'anime': {'name': 'Anime', 'keyword': '动漫'},
        }

    def getName(self):
        return 'YoukuTV'

    def init(self, extend=""):
        pass

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Accept': 'application/json, text/html, */*',
                'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8',
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
                    return json.loads(m.group(1) if m.lastindex else m.group(0))
                except Exception:
                    return {}
            return {}

    def _abs(self, u):
        if not u:
            return ''
        if u.startswith('//'):
            return 'https:' + u
        return u

    def _map_show(self, item):
        sid = str(
            item.get('showId')
            or item.get('show_id')
            or item.get('id')
            or item.get('encodevid')
            or item.get('videoid')
            or ''
        )
        if not sid:
            return None
        title = item.get('title') or item.get('showname') or item.get('name') or sid
        pic = item.get('poster') or item.get('thumbUrl') or item.get('img') or item.get('thumbnail') or item.get('pic') or ''
        remarks = item.get('notice') or item.get('subtitle') or item.get('stripeBottom') or item.get('payType') or ''
        if item.get('episodeTotal'):
            remarks = remarks or ('%s EP' % item.get('episodeTotal'))
        return {
            'vod_id': sid,
            'vod_name': re.sub(r'<[^>]+>', '', str(title)),
            'vod_pic': self._abs(pic),
            'vod_remarks': str(remarks),
            'vod_year': str(item.get('releaseYear') or item.get('year') or '')[:4],
        }

    def _parse_home_cards(self, html):
        videos = []
        seen = set()
        for m in re.finditer(
            r'href="([^"]*(?:/v/|/video/|/play/|/detail/)([^"/\s?]+))"[^>]{0,200}(?:title|alt)="([^"]+)"',
            html or '',
            re.I,
        ):
            vid, name = m.group(2), m.group(3)
            if vid in seen:
                continue
            seen.add(vid)
            videos.append({'vod_id': vid, 'vod_name': name, 'vod_pic': '', 'vod_remarks': ''})
        for m in re.finditer(r'"showId"\s*:\s*"([^"]+)".{0,400}?"title"\s*:\s*"([^"]+)"', html or '', re.S):
            vid, name = m.group(1), m.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            videos.append({'vod_id': vid, 'vod_name': name, 'vod_pic': '', 'vod_remarks': ''})
        return videos

    def _search_youku(self, key, pg=1):
        videos = []
        js = self.fetch_json(self.searchApi, {
            'keyword': key,
            'site': '1',
            'categories': '0',
            'ftype': '0',
            'ob': '0',
            'pg': str(pg),
        })
        rows = []
        data = js.get('data') or js
        if isinstance(data, dict):
            rows = data.get('nodes') or data.get('pageComponentList') or data.get('list') or []
        elif isinstance(data, list):
            rows = data
        if not rows:
            rows = js.get('results') or []

        def walk(obj):
            if isinstance(obj, dict):
                if obj.get('showId') or obj.get('title') or obj.get('showname'):
                    v = self._map_show(obj.get('data') or obj)
                    if v:
                        videos.append(v)
                for val in obj.values():
                    walk(val)
            elif isinstance(obj, list):
                for val in obj:
                    walk(val)

        walk(rows if rows else js)
        # unique
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
            html = self.fetch_text(self.siteUrl + '/')
            videos = self._parse_home_cards(html)
            if len(videos) < 8:
                videos.extend(self._search_youku('电视剧', 1)[:16])
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            key = self.channels.get(str(tid), {}).get('keyword', '电视剧')
            videos = self._search_youku(key, pg)
            if not videos and pg == 1:
                videos = self._parse_home_cards(self.fetch_text(self.siteUrl + '/'))
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
            videos = self._search_youku(key, pg)
            if not videos:
                html = self.fetch_text(self.siteUrl + '/search?q=' + urllib.parse.quote(key))
                videos = self._parse_home_cards(html)
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 12 else pg,
            'limit': 24,
            'total': len(videos),
        }

    def detailContent(self, ids):
        sid = str((ids or [''])[0])
        name, pic, desc, actor, director, year, remarks = sid, '', '', '', '', '', ''
        parts = []
        try:
            html = self.fetch_text(self.siteUrl + '/')
            # detail page candidates
            for url in (
                self.siteUrl + '/v/' + sid,
                self.siteUrl + '/detail/' + sid,
                self.mSite + '/v/' + sid,
                'https://v.youku.com/v_show/id_%s.html' % sid,
            ):
                page = self.fetch_text(url)
                if page and len(page) > 500:
                    html = page
                    break
            m = re.search(r'<title>([^<]+)</title>', html or '')
            if m:
                name = re.sub(r'\s*[-_|].*$', '', m.group(1)).strip() or name
            pm = re.search(r'og:image["\']\s+content=["\']([^"\']+)', html or '')
            if pm:
                pic = self._abs(pm.group(1))
            dm = re.search(r'og:description["\']\s+content=["\']([^"\']+)', html or '')
            if dm:
                desc = dm.group(1)

            js = self.fetch_json(self.showApi, {
                'client_id': self.clientId,
                'package': 'com.huawei.hwvplayer.youku',
                'ext': 'show',
                'show_id': sid,
                'page': '1',
                'count': '80',
            })
            videos = js.get('videos') or []
            if isinstance(js.get('data'), dict):
                videos = videos or js['data'].get('videos') or []
            for i, ep in enumerate(videos, 1):
                vid = ep.get('id') or ep.get('videoid') or ''
                ep_name = ep.get('title') or ep.get('name') or ('EP%s' % i)
                if not vid:
                    continue
                play = 'https://v.youku.com/v_show/id_%s.html' % vid
                parts.append('%s$%s' % (ep_name, play))
                if not pic:
                    pic = self._abs(ep.get('thumbnail') or ep.get('img') or '')
                if name == sid:
                    name = re.sub(r'\s+\d+$', '', ep_name) or name
        except Exception as e:
            print('获取详情失败: %s' % e)
        if not parts:
            if sid.startswith('X') or sid.startswith('x'):
                parts.append('Play$https://v.youku.com/v_show/id_%s.html' % sid)
            else:
                parts.append('Play$%s/v/%s' % (self.siteUrl, sid))
        return {
            'list': [{
                'vod_id': sid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_year': year,
                'vod_actor': actor,
                'vod_director': director,
                'vod_remarks': remarks or ('%s EP' % len(parts) if len(parts) > 1 else 'Movie'),
                'vod_content': (desc or '').replace('\n\n', '\n').strip(),
                'vod_play_from': 'Youku',
                'vod_play_url': '#'.join(parts),
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': 'https://v.youku.com/',
            'Origin': 'https://v.youku.com',
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
