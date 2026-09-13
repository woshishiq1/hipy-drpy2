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
    """5lxtv https://18.5lxtv.com  18+"""

    def __init__(self):
        self.siteUrl = 'https://18.5lxtv.com'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            'latest': {'name': '最新影片', 'path': '/latest'},
            'movies': {'name': '影视', 'path': '/movies'},
            'hot': {'name': '热门', 'path': '/hot'},
            'jav': {'name': '日本', 'path': '/movies?type=jav'},
            'cn': {'name': '国产', 'path': '/movies?type=cn'},
        }

    def getName(self):
        return '5lxtv'

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
            return self.siteUrl + u
        return u

    def _clean(self, s):
        return re.sub(r'<[^>]+>', '', str(s or '')).replace('&nbsp;', ' ').strip()

    def _parse_list(self, html):
        videos, seen = [], set()
        for m in re.finditer(
            r'href="((?:https?://[^"/]+)?/(?:video|videos|movie|watch|v|play)/[^"]+)"[^>]{0,240}(?:title|alt)="([^"]*)"',
            html or '',
            re.I,
        ):
            href, name = m.group(1), self._clean(m.group(2))
            path = href if href.startswith('/') else urllib.parse.urlparse(href).path
            if not path or path in seen:
                continue
            seen.add(path)
            videos.append({
                'vod_id': path,
                'vod_name': name or path.split('/')[-1],
                'vod_pic': '',
                'vod_remarks': '',
            })
        for m in re.finditer(
            r'href="(/[^"]+)"[^>]*>\s*([^<]{6,80})\s*<',
            html or '',
        ):
            path, name = m.group(1), self._clean(m.group(2))
            if path in seen or path in ('/', '/latest', '/movies', '/hot', '/search'):
                continue
            if any(x in path for x in ('/login', '/tag', '/page', '/user', '#')):
                continue
            if not re.search(r'/\d+', path) and 'video' not in path and 'movie' not in path:
                continue
            seen.add(path)
            videos.append({
                'vod_id': path,
                'vod_name': name,
                'vod_pic': '',
                'vod_remarks': '',
            })
        for m in re.finditer(
            r'(?:src|data-src|data-original)="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
            html or '',
            re.I,
        ):
            pic = self._abs(m.group(1))
            if any(x in pic.lower() for x in ('logo', 'icon', 'avatar')):
                continue
            for v in videos:
                if not v['vod_pic']:
                    v['vod_pic'] = pic
                    break
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            html = self.fetch_text(self.siteUrl + '/latest')
            videos = self._parse_list(html)
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            info = self.channels.get(str(tid), {'path': '/latest'})
            url = self.siteUrl + info.get('path', '/latest')
            if pg > 1:
                url += ('&' if '?' in url else '?') + 'page=' + str(pg)
            html = self.fetch_text(url)
            videos = self._parse_list(html)
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
            url = '%s/search?q=%s&page=%s' % (self.siteUrl, q, pg)
            html = self.fetch_text(url)
            videos = self._parse_list(html)
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 8 else pg,
            'limit': 24,
            'total': len(videos),
        }

    def _page_url(self, vid):
        s = str(vid or '')
        if s.startswith('http'):
            return s
        if s.startswith('/'):
            return self.siteUrl + s
        return self.siteUrl + '/' + s

    def detailContent(self, ids):
        vid = str((ids or [''])[0])
        name, pic, desc = vid, '', ''
        try:
            page = self._page_url(vid)
            html = self.fetch_text(page)
            tm = re.search(r'<title>([^<]+)</title>', html or '')
            if tm:
                name = re.sub(r'\s*[-_|].*$', '', tm.group(1)).strip() or name
            hm = re.search(r'<h1[^>]*>([\s\S]{2,200})</h1>', html or '')
            if hm:
                name = self._clean(hm.group(1)) or name
            pm = re.search(r'(?:og:image["\']\s+content=["\']|poster=["\'])([^"\']+)', html or '')
            if pm:
                pic = self._abs(pm.group(1))
            dm = re.search(r'og:description["\']\s+content=["\']([^"\']+)', html or '')
            if dm:
                desc = dm.group(1)
            m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or '')
            mp4 = re.search(r'https?://[^\s"\']+\.mp4[^\s"\']*', html or '')
            src = re.search(r'<video[^>]+src=["\']([^"\']+)["\']', html or '', re.I)
            play = ''
            if m3:
                play = m3.group(0).replace('\\/', '/')
            elif mp4:
                play = mp4.group(0).replace('\\/', '/')
            elif src:
                play = self._abs(src.group(1))
            play_url = '播放$%s' % (play or page)
        except Exception as e:
            print('获取详情失败: %s' % e)
            play_url = '播放$%s' % self._page_url(vid)
        return {'list': [{
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': '18+',
            'vod_actor': '',
            'vod_director': '',
            'vod_content': (desc or '').strip(),
            'vod_play_from': '5lxtv',
            'vod_play_url': play_url,
        }]}

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
        }
        play = str(id or '')
        if self.isVideoFormat(play) and play.startswith('http'):
            return {'parse': 0, 'jx': '0', 'url': play, 'header': header}
        page = self._page_url(play)
        html = self.fetch_text(page) if '5lxtv' in page or play.startswith('/') else ''
        m = re.search(r'https?://[^\s"\']+\.(?:m3u8|mp4)[^\s"\']*', html or '')
        if m:
            return {'parse': 0, 'jx': '0', 'url': m.group(0).replace('\\/', '/'), 'header': header}
        return {'parse': 1, 'jx': '1', 'url': page, 'header': header}

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
