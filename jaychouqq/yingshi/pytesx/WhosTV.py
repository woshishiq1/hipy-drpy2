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
    """Whos.tv https://whos.tv  18+ JAV 以图搜片"""

    def __init__(self):
        self.siteUrl = 'https://whos.tv'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            'movies': {'name': '影片库', 'path': '/movies'},
            'frames': {'name': '帧探索', 'path': '/frames'},
            'actresses': {'name': '女优', 'path': '/actresses'},
            'tags': {'name': '原创', 'path': '/tags/原创'},
            'new': {'name': '最新', 'path': '/movies?sort=new'},
        }

    def getName(self):
        return 'WhosTV'

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
            r'href="((?:https?://whos\.tv)?/(?:movies?|video|film|v)/[^"]+)"[^>]{0,240}(?:title|alt)="([^"]*)"',
            html or '',
            re.I,
        ):
            href, name = m.group(1), self._clean(m.group(2))
            path = href if href.startswith('/') or href.startswith('http') else '/' + href
            if path in seen or not name:
                continue
            seen.add(path)
            videos.append({
                'vod_id': path if path.startswith('/') else urllib.parse.urlparse(path).path,
                'vod_name': name,
                'vod_pic': '',
                'vod_remarks': '',
            })
        for m in re.finditer(
            r'href="(/[^"]+)"[^>]*>\s*([a-z]{2,8}-\d{2,5}(?:-[a-z0-9-]+)?)\s*<',
            html or '',
            re.I,
        ):
            path, code = m.group(1), m.group(2).upper()
            if path in seen or path.startswith('/frames') or path.startswith('/tags/'):
                if '/movies' not in path and '/video' not in path and not re.search(r'[a-z]{2,8}-\d', path, re.I):
                    continue
            if code in seen:
                continue
            seen.add(code)
            videos.append({
                'vod_id': path if path.startswith('/') else '/' + path,
                'vod_name': code,
                'vod_pic': '',
                'vod_remarks': '',
            })
        for m in re.finditer(
            r'([a-z]{2,10}-\d{2,5}(?:-[a-z0-9-]+)?)\s*</h[1-4]>',
            html or '',
            re.I,
        ):
            code = m.group(1)
            if code.upper() in seen:
                continue
            seen.add(code.upper())
            videos.append({
                'vod_id': '/movies/' + code.lower(),
                'vod_name': code.upper(),
                'vod_pic': '',
                'vod_remarks': '',
            })
        for m in re.finditer(
            r'(?:src|data-src|data-original)="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
            html or '',
            re.I,
        ):
            pic = self._abs(m.group(1))
            if 'logo' in pic or 'icon' in pic:
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
            html = self.fetch_text(self.siteUrl + '/movies')
            videos = self._parse_list(html)
            if not videos:
                html = self.fetch_text(self.siteUrl + '/tags/%E5%8E%9F%E5%88%9B')
                videos = self._parse_list(html)
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            info = self.channels.get(str(tid), {'path': '/movies'})
            path = info.get('path', '/movies')
            url = self.siteUrl + path
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
            for url in (
                '%s/search?q=%s&page=%s' % (self.siteUrl, q, pg),
                '%s/movies?keyword=%s' % (self.siteUrl, q),
            ):
                html = self.fetch_text(url)
                videos = self._parse_list(html)
                if videos:
                    break
            if not videos and re.match(r'^[a-z]{2,10}-\d+', key, re.I):
                videos.append({
                    'vod_id': '/movies/' + key.lower(),
                    'vod_name': key.upper(),
                    'vod_pic': '',
                    'vod_remarks': '番号',
                })
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
        name, pic, desc, actor = vid, '', '', ''
        try:
            page = vid if vid.startswith('http') else self.siteUrl + (vid if vid.startswith('/') else '/' + vid)
            html = self.fetch_text(page)
            tm = re.search(r'<title>([^<]+)</title>', html or '')
            if tm:
                name = re.sub(r'\s*[-_|].*$', '', tm.group(1)).strip() or name
            hm = re.search(r'<h1[^>]*>([\s\S]{2,160})</h1>', html or '')
            if hm:
                name = self._clean(hm.group(1)) or name
            pm = re.search(r'(?:og:image["\']\s+content=["\']|poster=["\'])([^"\']+)', html or '')
            if pm:
                pic = self._abs(pm.group(1))
            dm = re.search(r'og:description["\']\s+content=["\']([^"\']+)', html or '')
            if dm:
                desc = dm.group(1)
            am = re.search(r'(?:女优|女優|actress)[:：]?\s*([^<\n]{2,40})', html or '', re.I)
            if am:
                actor = self._clean(am.group(1))
            links = []
            for m in re.finditer(r'href="(https?://[^"]+)"[^>]{0,80}>([^<]{0,30})', html or ''):
                href, text = m.group(1), self._clean(m.group(2))
                if 'whos.tv' in href:
                    continue
                if any(x in href for x in ('missav', 'javbus', 'javdb', 'avgle', 'jable', 'netflav', 'njav')):
                    links.append('%s$%s' % (text or '外部源', href))
            m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or '')
            mp4 = re.search(r'https?://[^\s"\']+\.mp4[^\s"\']*', html or '')
            if m3:
                links.insert(0, '直链$%s' % m3.group(0))
            elif mp4:
                links.insert(0, '直链$%s' % mp4.group(0))
            if not links:
                links.append('详情$%s' % page)
            play_url = '#'.join(links[:8])
        except Exception as e:
            print('获取详情失败: %s' % e)
            play_url = '详情$%s' % (self.siteUrl + '/')
        return {'list': [{
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': '18+',
            'vod_actor': actor,
            'vod_director': '',
            'vod_content': (desc or 'Whos.tv 以图搜片，本站多为番号检索，完整播放走外部源。').strip(),
            'vod_play_from': 'WhosTV',
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
        if play.startswith('/'):
            play = self.siteUrl + play
        html = self.fetch_text(play) if play.startswith('http') and 'whos.tv' in play else ''
        m = re.search(r'https?://[^\s"\']+\.(?:m3u8|mp4)[^\s"\']*', html or '')
        if m:
            return {'parse': 0, 'jx': '0', 'url': m.group(0).replace('\\/', '/'), 'header': header}
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
