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
    """肉视频 https://rouvb1.xyz  永久域名 https://rou.video"""

    def __init__(self):
        self.siteUrl = 'https://rouvb1.xyz'
        self.permUrl = 'https://rou.video'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            '国产AV': {'name': '国产AV'},
            '探花': {'name': '探花'},
            '自拍流出': {'name': '自拍流出'},
            'OnlyFans': {'name': 'OnlyFans'},
            '日本': {'name': '日本'},
            'AI短剧': {'name': 'AI短剧'},
        }

    def getName(self):
        return '肉视频'

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

    def fetch_json(self, url, params=None):
        resp = self.fetch(url, params=params)
        if not resp:
            return {}
        try:
            return resp.json()
        except Exception:
            return {}

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
            r'href="((?:https?://[^"/]+)?/(?:v|video|watch|t)/[^"]+)"[^>]{0,220}(?:title|alt)="([^"]*)"',
            html or '',
            re.I,
        ):
            href, name = m.group(1), self._clean(m.group(2))
            path = href.split('://')[-1]
            path = '/' + path.split('/', 1)[-1] if '/' in path else href
            if '/t/' in path and path.count('/') <= 2:
                continue
            if path in seen or not name or name in ('更多', '全部劇集'):
                continue
            seen.add(path)
            videos.append({
                'vod_id': path,
                'vod_name': name,
                'vod_pic': '',
                'vod_remarks': '',
            })
        if not videos:
            for m in re.finditer(r'href="(/v/[^"]+)"[^>]*>([^<]{2,80})', html or ''):
                path, name = m.group(1), self._clean(m.group(2))
                if path in seen or not name:
                    continue
                seen.add(path)
                videos.append({
                    'vod_id': path,
                    'vod_name': name,
                    'vod_pic': '',
                    'vod_remarks': '',
                })
        for m in re.finditer(
            r'((?:/v/|/video/)[^"]+)[\s\S]{0,240}?(?:src|data-src)="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
            html or '',
            re.I,
        ):
            for v in videos:
                if m.group(1) in v['vod_id'] and not v['vod_pic']:
                    v['vod_pic'] = self._abs(m.group(2))
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            html = self.fetch_text(self.siteUrl + '/home')
            if not html:
                html = self.fetch_text(self.permUrl + '/home')
            videos = self._parse_list(html)
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            tid = str(tid or '国产AV')
            q = urllib.parse.quote(tid)
            urls = [
                '%s/t/%s?page=%s' % (self.siteUrl, q, pg),
                '%s/t/%s' % (self.siteUrl, q),
                '%s/series?tag=%s' % (self.siteUrl, q),
            ]
            for url in urls:
                html = self.fetch_text(url)
                videos = self._parse_list(html)
                if videos:
                    break
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
            for url in (
                '%s/search?q=%s&page=%s' % (self.siteUrl, q, pg),
                '%s/search/%s' % (self.siteUrl, q),
            ):
                html = self.fetch_text(url)
                videos = self._parse_list(html)
                if videos:
                    break
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 8 else pg,
            'limit': 24,
            'total': len(videos),
        }

    def detailContent(self, ids):
        vid = str((ids or [''])[0])
        name, pic, desc = vid, '', ''
        try:
            page = self._abs(vid if vid.startswith('/') else '/' + vid)
            html = self.fetch_text(page)
            tm = re.search(r'<title>([^<]+)</title>', html or '')
            if tm:
                name = re.sub(r'\s*[-_|].*$', '', tm.group(1)).strip() or name
            hm = re.search(r'<h1[^>]*>([\s\S]{2,120})</h1>', html or '')
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
            src2 = re.search(r'(?:playUrl|videoUrl|file|src)\s*[:=]\s*["\'](https?://[^"\']+)["\']', html or '')
            play = ''
            if m3:
                play = m3.group(0).replace('\\/', '/')
            elif mp4:
                play = mp4.group(0).replace('\\/', '/')
            elif src:
                play = self._abs(src.group(1))
            elif src2:
                play = src2.group(1)
            play_url = '播放$%s' % (play or page)
        except Exception as e:
            print('获取详情失败: %s' % e)
            play_url = '播放$%s' % self._abs(vid)
        return {'list': [{
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': '肉视频',
            'vod_actor': '',
            'vod_director': '',
            'vod_content': (desc or '').strip(),
            'vod_play_from': '肉视频',
            'vod_play_url': play_url,
        }]}

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
            'Origin': self.siteUrl,
        }
        play = str(id or '')
        if self.isVideoFormat(play) and play.startswith('http'):
            return {'parse': 0, 'jx': '0', 'url': play, 'header': header}
        if play.startswith('/'):
            play = self.siteUrl + play
        html = self.fetch_text(play) if play.startswith('http') else ''
        m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or '')
        if m3:
            return {'parse': 0, 'jx': '0', 'url': m3.group(0).replace('\\/', '/'), 'header': header}
        mp4 = re.search(r'https?://[^\s"\']+\.mp4[^\s"\']*', html or '')
        if mp4:
            return {'parse': 0, 'jx': '0', 'url': mp4.group(0).replace('\\/', '/'), 'header': header}
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
