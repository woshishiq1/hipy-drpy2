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
    """看度新闻 / 成都广播电视台 https://www.cditv.cn/category/4822/1.html"""

    def __init__(self):
        self.siteUrl = 'https://www.cditv.cn'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            '4822': {'name': '视频栏目'},
            '4829': {'name': '成都新闻'},
            '4831': {'name': '成都全接触'},
            '4838': {'name': '今晚800'},
            '4808': {'name': '看度资讯'},
        }

    def getName(self):
        return '看度新闻'

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
            r'href="((?:https?://www\.cditv\.cn)?/show/(\d+)-(\d+)\.html)"[^>]{0,200}(?:title|alt)="([^"]*)"',
            html or '',
            re.I,
        ):
            vid = '%s-%s' % (m.group(2), m.group(3))
            name = self._clean(m.group(4) or vid)
            if vid in seen or not name:
                continue
            seen.add(vid)
            videos.append({
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': '',
                'vod_remarks': '看度',
            })
        if not videos:
            for m in re.finditer(r'/show/(\d+)-(\d+)\.html"[^>]*>([^<]{4,80})', html or ''):
                vid = '%s-%s' % (m.group(1), m.group(2))
                name = self._clean(m.group(3))
                if vid in seen or not name:
                    continue
                seen.add(vid)
                videos.append({
                    'vod_id': vid,
                    'vod_name': name,
                    'vod_pic': '',
                    'vod_remarks': '看度',
                })
        for m in re.finditer(
            r'show/(\d+-\d+)\.html[\s\S]{0,260}?(?:src|data-src|data-original)="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
            html or '',
            re.I,
        ):
            for v in videos:
                if v['vod_id'] == m.group(1) and not v['vod_pic']:
                    v['vod_pic'] = self._abs(m.group(2))
        return videos

    def _list_url(self, tid, pg):
        tid, pg = str(tid), str(pg)
        return [
            '%s/category/%s/%s.html' % (self.siteUrl, tid, pg),
            '%s/list/%s/%s.html' % (self.siteUrl, tid, pg),
        ]

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            for tid in ('4822', '4829', '4831'):
                html = ''
                for url in self._list_url(tid, 1):
                    html = self.fetch_text(url)
                    if html and 'show/' in html:
                        break
                videos.extend(self._parse_list(html)[:8])
                if len(videos) >= 24:
                    break
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            tid = str(tid or '4822')
            html = ''
            for url in self._list_url(tid, pg):
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
                self.siteUrl + '/search/?keyword=' + q,
                self.siteUrl + '/search/index.html?keyword=' + q,
                self.siteUrl + '/list/4822/%s.html' % pg,
            ):
                html = self.fetch_text(url)
                items = self._parse_list(html)
                if 'search' in url:
                    videos = items
                    if videos:
                        break
                else:
                    videos = [v for v in items if key in v['vod_name']]
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
            page = self.siteUrl + '/show/%s.html' % vid
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
            if not desc:
                cm = re.search(r'class="[^"]*(?:content|article|intro)[^"]*"[^>]*>([\s\S]{20,400})</div>', html or '')
                if cm:
                    desc = self._clean(cm.group(1))[:400]
            m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or '')
            mp4 = re.search(r'https?://[^\s"\']+\.mp4[^\s"\']*', html or '')
            src = re.search(r'<video[^>]+src=["\']([^"\']+)["\']', html or '', re.I)
            src2 = re.search(r'(?:file|url|videoUrl|playurl)\s*[:=]\s*["\'](https?://[^"\']+)["\']', html or '', re.I)
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
            play_url = '播放$%s/show/%s.html' % (self.siteUrl, vid)
        return {'list': [{
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': '成都广播电视台',
            'vod_actor': '',
            'vod_director': '',
            'vod_content': (desc or '').strip(),
            'vod_play_from': '看度新闻',
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
        if not play.startswith('http'):
            play = self.siteUrl + (play if play.startswith('/') else '/show/%s.html' % play)
        html = self.fetch_text(play)
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
