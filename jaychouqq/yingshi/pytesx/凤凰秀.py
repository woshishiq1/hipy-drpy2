#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import re
import sys
import time
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
    """凤凰秀 https://www.fengshows.com"""

    def __init__(self):
        self.siteUrl = 'https://www.fengshows.com'
        self.mUrl = 'https://m.fengshows.com'
        self.api = 'https://api.fengshows.cn'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.appUA = 'FengWatch/5.4.2 (iPhone; iOS 16.1.2; Scale/3.00)'
        self.channels = {
            'live': {'name': '频道直播'},
            'video': {'name': '视频栏目'},
            'news': {'name': '新闻资讯'},
            'hongkongv': {'name': '香港V'},
        }

    def getName(self):
        return '凤凰秀'

    def init(self, extend=""):
        pass

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,zh-HK;q=0.8',
            }
        try:
            if requests:
                resp = requests.get(url, headers=headers, params=params, timeout=12)
                resp.raise_for_status()
                return resp
            full = url
            if params:
                full += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
            from urllib.request import Request, urlopen
            raw = urlopen(Request(full, headers=headers), timeout=12).read()

            class R:
                def __init__(self, raw):
                    self.text = raw.decode('utf-8', 'ignore')

                def json(self):
                    return json.loads(self.text)

            return R(raw)
        except Exception as e:
            print('请求失败: %s, %s' % (url, e))
            return None

    def fetch_json(self, url, params=None, headers=None):
        resp = self.fetch(url, headers=headers, params=params)
        if not resp:
            return None
        try:
            return resp.json()
        except Exception:
            text = getattr(resp, 'text', '') or ''
            m = re.search(r'(\{[\s\S]+\}|\[[\s\S]+\])', text)
            if m:
                try:
                    return json.loads(m.group(1))
                except Exception:
                    return None
            return None

    def fetch_text(self, url):
        resp = self.fetch(url)
        return getattr(resp, 'text', '') if resp else ''

    def _abs(self, u):
        if not u:
            return ''
        if str(u).startswith('//'):
            return 'https:' + u
        if str(u).startswith('/'):
            return self.siteUrl + u
        return u

    def _app_headers(self):
        return {
            'User-Agent': self.appUA,
            'Accept': 'application/json',
            'fengshows-client': 'app(ios,5040213);iPhone15,3;16.1.2',
            'Referer': self.mUrl + '/',
        }

    def _as_list(self, data):
        if data is None:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for k in ('data', 'list', 'items', 'docs', 'videos', 'lives'):
                if isinstance(data.get(k), list):
                    return data[k]
        return []

    def _map_item(self, it, prefix='vod'):
        if not isinstance(it, dict):
            return None
        vid = str(it.get('_id') or it.get('id') or it.get('vid') or '')
        name = it.get('title') or it.get('name') or it.get('live_name') or vid
        pic = it.get('cover') or it.get('image') or it.get('poster') or it.get('thumbnail') or ''
        if isinstance(pic, dict):
            pic = pic.get('url') or pic.get('src') or ''
        remarks = it.get('duration') or it.get('column') or it.get('live_type') or ''
        if not vid:
            return None
        return {
            'vod_id': prefix + ':' + vid,
            'vod_name': name,
            'vod_pic': self._abs(pic),
            'vod_remarks': str(remarks),
        }

    def _live_list(self):
        videos = []
        for url in (
            self.api + '/live/list-with-cover?live_type=tv&page=1&page_size=20',
            self.mUrl + '/api/v3/live?live_type=tv',
        ):
            data = self.fetch_json(url, headers=self._app_headers())
            items = self._as_list(data)
            if not items and isinstance(data, list):
                items = data
            for it in items:
                v = self._map_item(it, 'live')
                if v:
                    videos.append(v)
            if videos:
                break
        if not videos:
            videos = [
                {'vod_id': 'live:fhzx', 'vod_name': '凤凰中文台', 'vod_pic': '', 'vod_remarks': '直播'},
                {'vod_id': 'live:fhzw', 'vod_name': '凤凰资讯台', 'vod_pic': '', 'vod_remarks': '直播'},
                {'vod_id': 'live:fhhk', 'vod_name': '凤凰香港台', 'vod_pic': '', 'vod_remarks': '直播'},
            ]
        return videos

    def _parse_html(self, html, prefix='vod'):
        videos, seen = [], set()
        for m in re.finditer(
            r'href="((?:https?://(?:www|m)\.fengshows\.com)?/(?:video|news|hongkongv|p)/[^"]+)"[^>]{0,180}(?:title|alt)="([^"]*)"',
            html or '',
            re.I,
        ):
            href, name = m.group(1), m.group(2).strip()
            path = href.split('.com')[-1]
            if path in seen or not name:
                continue
            seen.add(path)
            videos.append({
                'vod_id': prefix + ':' + path,
                'vod_name': name,
                'vod_pic': '',
                'vod_remarks': '凤凰秀',
            })
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            videos = self._live_list()
            html = self.fetch_text(self.siteUrl + '/video')
            videos.extend(self._parse_html(html)[:16])
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            tid = str(tid or 'video')
            if tid == 'live':
                videos = self._live_list()
            else:
                path = {'news': '/news', 'hongkongv': '/hongkongv'}.get(tid, '/video')
                html = self.fetch_text(self.siteUrl + path)
                videos = self._parse_html(html, tid)
                if not videos:
                    data = self.fetch_json(
                        self.mUrl + '/api/v3/videos',
                        params={'page': pg, 'page_size': 24, 'type': tid},
                        headers=self._app_headers(),
                    )
                    for it in self._as_list(data):
                        v = self._map_item(it, tid)
                        if v:
                            videos.append(v)
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if tid != 'live' and len(videos) >= 8 else pg,
            'limit': 24,
            'total': len(videos),
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        try:
            data = self.fetch_json(
                self.mUrl + '/api/v3/search',
                params={'q': key, 'page': pg},
                headers=self._app_headers(),
            )
            for it in self._as_list(data):
                v = self._map_item(it, 'vod')
                if v:
                    videos.append(v)
            if not videos:
                html = self.fetch_text(self.siteUrl + '/video')
                videos = [v for v in self._parse_html(html) if key in v['vod_name']]
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 8 else pg,
            'limit': 24,
            'total': len(videos),
        }

    def _pick_live_url(self, it):
        for k in ('live_url_fhd', 'live_url_hd', 'live_url', 'play_url', 'url'):
            u = it.get(k) if isinstance(it, dict) else ''
            if u:
                return str(u).replace('dispatch.fengshows.cn:8383', 'qclive.fengshows.cn')
        return ''

    def detailContent(self, ids):
        raw = str((ids or [''])[0])
        kind, vid = (raw.split(':', 1) + [''])[:2] if ':' in raw else ('vod', raw)
        name, pic, desc = vid, '', ''
        froms, urls = [], []
        try:
            if kind == 'live':
                lives = []
                for url in (
                    self.api + '/live/list-with-cover?live_type=tv&page=1&page_size=20',
                    self.mUrl + '/api/v3/live?live_type=tv',
                ):
                    data = self.fetch_json(url, headers=self._app_headers())
                    lives = self._as_list(data) or (data if isinstance(data, list) else [])
                    if lives:
                        break
                hit = None
                for it in lives:
                    if str(it.get('_id') or it.get('id') or '') == vid or vid in str(it.get('title') or it.get('name') or ''):
                        hit = it
                        break
                if not hit and lives:
                    aliases = {'fhzx': 0, 'fhzw': 1, 'fhhk': 2}
                    if vid in aliases and aliases[vid] < len(lives):
                        hit = lives[aliases[vid]]
                if hit:
                    name = hit.get('title') or hit.get('name') or hit.get('live_name') or name
                    pic = self._abs(hit.get('cover') or '')
                    play = self._pick_live_url(hit)
                    froms = ['凤凰直播']
                    urls = ['直播$%s' % (play or self.siteUrl + '/live')]
                else:
                    froms = ['凤凰直播']
                    urls = ['直播$%s/live' % self.siteUrl]
            else:
                page = vid if vid.startswith('http') else self._abs(vid if vid.startswith('/') else '/' + vid)
                html = self.fetch_text(page)
                tm = re.search(r'<title>([^<]+)</title>', html or '')
                if tm:
                    name = re.sub(r'\s*[-_|].*$', '', tm.group(1)).strip() or name
                m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or '')
                mp4 = re.search(r'https?://[^\s"\']+\.mp4[^\s"\']*', html or '')
                flv = re.search(r'https?://[^\s"\']+\.flv[^\s"\']*', html or '')
                play = ''
                if m3:
                    play = m3.group(0)
                elif mp4:
                    play = mp4.group(0)
                elif flv:
                    play = flv.group(0)
                froms = ['凤凰秀']
                urls = ['播放$%s' % (play or page)]
        except Exception as e:
            print('获取详情失败: %s' % e)
        if not urls:
            froms = ['凤凰秀']
            urls = ['播放$%s' % self.siteUrl]
        return {'list': [{
            'vod_id': raw,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': '凤凰卫视',
            'vod_actor': '',
            'vod_director': '',
            'vod_content': desc,
            'vod_play_from': '$$$'.join(froms),
            'vod_play_url': '$$$'.join(urls),
        }]}

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.appUA,
            'Referer': self.mUrl + '/',
            'Origin': self.mUrl,
        }
        play = str(id or '')
        play = play.replace('dispatch.fengshows.cn:8383', 'qclive.fengshows.cn')
        if self.isVideoFormat(play) and play.startswith('http'):
            return {'parse': 0, 'jx': '0', 'url': play, 'header': header}
        if play.startswith('/'):
            play = self.siteUrl + play
        html = self.fetch_text(play) if play.startswith('http') else ''
        m3 = re.search(r'https?://[^\s"\']+\.(?:m3u8|mp4|flv)[^\s"\']*', html or '')
        if m3:
            return {'parse': 0, 'jx': '0', 'url': m3.group(0).replace('\\/', '/'), 'header': header}
        return {'parse': 1, 'jx': '1', 'url': play, 'header': header}

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
