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
        self.siteUrl = 'https://zh.xhamster.com'
        self.userAgent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        self.channels = {
            'newest': {'name': '最新', 'path': '/newest'},
            'best': {'name': '最佳', 'path': '/best'},
            '4k': {'name': '4K', 'path': '/4k'},
            'hd': {'name': '高清', 'path': '/hd'},
            'vr': {'name': 'VR', 'path': '/vr'},
            'categories-amateur': {'name': '业余', 'path': '/categories/amateur'},
            'categories-asian': {'name': '亚洲', 'path': '/categories/asian'},
            'categories-japanese': {'name': '日本', 'path': '/categories/japanese'},
            'categories-chinese': {'name': '中国', 'path': '/categories/chinese'},
            'categories-korean': {'name': '韩国', 'path': '/categories/korean'},
            'categories-milf': {'name': '熟女', 'path': '/categories/milf'},
            'categories-lesbian': {'name': '女同', 'path': '/categories/lesbian'},
        }

    def getName(self):
        return 'xHamster'

    def init(self, extend=""):
        try:
            if extend:
                ext = json.loads(extend) if isinstance(extend, str) else (extend or {})
                if ext.get('host'):
                    self.siteUrl = str(ext.get('host')).rstrip('/')
        except Exception:
            pass

    def fetch(self, url, headers=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
        try:
            if requests:
                resp = requests.get(url, headers=headers, timeout=20)
                resp.raise_for_status()
                return resp.text
            from urllib.request import Request, urlopen
            raw = urlopen(Request(url, headers=headers), timeout=20).read()
            return raw.decode('utf-8', 'ignore')
        except Exception as e:
            print('请求失败: %s, %s' % (url, e))
            return ''

    def _abs(self, u):
        if not u:
            return ''
        if u.startswith('http'):
            return u
        if u.startswith('//'):
            return 'https:' + u
        return self.siteUrl + (u if u.startswith('/') else '/' + u)

    def _page_url(self, path, pg=1):
        path = path or '/newest'
        if not path.startswith('/'):
            path = '/' + path
        url = self.siteUrl + path
        if int(pg or 1) > 1:
            url += ('&' if '?' in url else '?') + 'page=' + str(pg)
        return url

    def _parse_list(self, html):
        videos = []
        seen = set()
        html = html or ''
        for m in re.finditer(
            r'href="(https?://[^"]+/videos/[^"?]+)"[^>]*>[\s\S]{0,600}?(?:src|data-src)="(https?://[^"]+)"[\s\S]{0,400}?alt="([^"]*)"',
            html, re.I
        ):
            href, pic, title = m.group(1), m.group(2), m.group(3)
            slug = href.rstrip('/').split('/videos/')[-1]
            if not slug or slug in seen:
                continue
            seen.add(slug)
            videos.append({
                'vod_id': slug,
                'vod_name': title or slug,
                'vod_pic': self._abs(pic),
                'vod_remarks': '',
            })
        if videos:
            return videos
        for m in re.finditer(r'/videos/([a-z0-9][a-z0-9\-_]{4,})', html, re.I):
            slug = m.group(1)
            if slug in seen:
                continue
            seen.add(slug)
            videos.append({
                'vod_id': slug,
                'vod_name': slug.replace('-', ' '),
                'vod_pic': '',
                'vod_remarks': '',
            })
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        html = self.fetch(self._page_url('/newest', 1))
        return {'list': self._parse_list(html)[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        info = self.channels.get(str(tid), {'path': '/' + str(tid or 'newest')})
        html = self.fetch(self._page_url(info.get('path') or '/newest', pg))
        videos = self._parse_list(html)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 20 else pg,
            'limit': 24,
            'total': 9999,
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        url = '%s/search/%s' % (self.siteUrl, urllib.parse.quote(str(key or '')))
        if pg > 1:
            url += '?page=' + str(pg)
        html = self.fetch(url)
        videos = self._parse_list(html)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 20 else pg,
            'limit': 24,
            'total': len(videos),
        }

    def detailContent(self, ids):
        slug = str((ids or [''])[0]).lstrip('/')
        if slug.startswith('videos/'):
            slug = slug[7:]
        page = self.siteUrl + '/videos/' + slug
        html = self.fetch(page)
        title = slug.replace('-', ' ')
        pic = ''
        tm = re.search(r'og:title["\']\s+content=["\']([^"\']+)', html or '', re.I)
        if not tm:
            tm = re.search(r'<title>([^<]+)</title>', html or '', re.I)
        if tm:
            title = re.sub(r'\s*[-|].*$', '', tm.group(1)).strip() or title
        pm = re.search(r'og:image["\']\s+content=["\']([^"\']+)', html or '', re.I)
        if pm:
            pic = self._abs(pm.group(1))
        return {
            'list': [{
                'vod_id': slug,
                'vod_name': title,
                'vod_pic': pic,
                'vod_content': title,
                'vod_play_from': 'xHamster',
                'vod_play_url': '正片$%s' % slug,
            }]
        }

    def _pick_play(self, html):
        html = html or ''
        m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html)
        if m3:
            return m3.group(0).replace('\\/', '/')
        for key in ('h264', 'av1', 'videoUrl', 'fallback'):
            m = re.search(r'"%s"\s*:\s*"(https?:[^"]+)"' % key, html)
            if m:
                return m.group(1).replace('\\/', '/')
        m = re.search(r'"url"\s*:\s*"(https?:[^"]+\.(?:mp4|m3u8)[^"]*)"', html)
        if m:
            return m.group(1).replace('\\/', '/')
        return ''

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
            'Origin': self.siteUrl,
        }
        play_id = str(id or '')
        if play_id.startswith('http') and self.isVideoFormat(play_id):
            return {'parse': 0, 'url': play_id, 'header': header}
        slug = play_id.split('|')[0]
        if slug.startswith('videos/'):
            slug = slug[7:]
        page = self.siteUrl + '/videos/' + slug
        html = self.fetch(page)
        url = self._pick_play(html)
        if url:
            return {'parse': 0 if self.isVideoFormat(url) else 1, 'url': url, 'header': header}
        return {'parse': 1, 'jx': '1', 'url': page, 'header': header}

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        return any(x in u for x in ('.m3u8', '.mp4', '.webm'))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None


if __name__ == '__main__':
    spider = Spider()
    print(json.dumps(spider.homeContent(True), ensure_ascii=False, indent=2))
