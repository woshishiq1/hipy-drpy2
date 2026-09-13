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
        self.siteUrl = 'https://m.wuye.tv'
        self.pcUrl = 'https://www.wuye.tv'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            'new': {'name': '最新', 'paths': ['/', '/index.php', '/vod/type/id/1.html']},
            'hot': {'name': '热门', 'paths': ['/hot', '/vodtype/hot.html', '/label/hot.html']},
            '1': {'name': '国产', 'paths': ['/vodtype/1.html', '/vod/type/id/1.html', '/type/1.html']},
            '2': {'name': '日本', 'paths': ['/vodtype/2.html', '/vod/type/id/2.html', '/type/2.html']},
            '3': {'name': '欧美', 'paths': ['/vodtype/3.html', '/vod/type/id/3.html', '/type/3.html']},
            '4': {'name': '传媒', 'paths': ['/vodtype/4.html', '/vod/type/id/4.html', '/type/4.html']},
        }

    def getName(self):
        return '午夜TV'

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
        return re.sub(r'<[^>]+>', '', str(s or '')).strip()

    def _parse_list(self, html):
        videos, seen = [], set()
        pats = [
            r'href="([^"]*(?:/vod(?:detail|play)?/|/video/|/play/)([^"/\s.?]+))"[^>]{0,200}(?:title|alt)="([^"]*)"',
            r'href="([^"]*(?:/voddetail/|/vodplay/)(\d+)[^"]*)"[^>]*>\s*([^<]{2,80})',
        ]
        for pat in pats:
            for m in re.finditer(pat, html or '', re.I):
                vid = m.group(2)
                name = self._clean(m.group(3) or vid)
                if not vid or vid in seen or name in ('播放', '详情', '首页'):
                    continue
                seen.add(vid)
                videos.append({
                    'vod_id': vid,
                    'vod_name': name,
                    'vod_pic': '',
                    'vod_remarks': '',
                })
        for m in re.finditer(
            r'(?:/vod(?:detail|play)?/|/play/)([^"/\s.?]+)[^"]*"[^>]*>[\s\S]{0,240}?<img[^>]+(?:src|data-src|data-original)="([^"]+)"',
            html or '',
            re.I,
        ):
            vid, pic = m.group(1), self._abs(m.group(2))
            for v in videos:
                if v['vod_id'] == vid and not v['vod_pic']:
                    v['vod_pic'] = pic
        return videos

    def _load(self, paths):
        videos = []
        for path in paths:
            for host in (self.siteUrl, self.pcUrl):
                url = path if path.startswith('http') else host + path
                html = self.fetch_text(url)
                videos = self._parse_list(html)
                if videos:
                    return videos
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            videos = self._load(['/', '/index.php', '/vod/type/id/1.html'])
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            info = self.channels.get(str(tid), self.channels['new'])
            paths = list(info.get('paths') or ['/'])
            if pg > 1:
                extra = []
                for p in paths:
                    extra.append(p.replace('.html', '-%s.html' % pg))
                    extra.append(p + (('&' if '?' in p else '?') + 'page=' + str(pg)))
                    extra.append(re.sub(r'/page/\d+', '', p).rstrip('/') + '/page/%s.html' % pg)
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
                '/vodsearch/%s----------%s---.html' % (q, pg),
                '/search?q=%s&page=%s' % (q, pg),
                '/index.php/vod/search.html?wd=%s&page=%s' % (q, pg),
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
            '/vodplay/%s.html' % vid,
            '/voddetail/%s.html' % vid,
            '/play/%s.html' % vid,
            '/video/%s.html' % vid,
            '/index.php/vod/play/id/%s.html' % vid,
            '/index.php/vod/detail/id/%s.html' % vid,
        ):
            for host in (self.siteUrl, self.pcUrl):
                html = self.fetch_text(host + path)
                if html and len(html) > 300:
                    return html, host + path
        return '', self.siteUrl + '/vodplay/%s.html' % vid

    def detailContent(self, ids):
        vid = str((ids or [''])[0])
        name, pic, desc, remarks = vid, '', '', ''
        parts = []
        try:
            html, page = self._detail_html(vid)
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
                r'href="([^"]*(?:/vodplay/|/play/)[^"]+)"[^>]*>\s*([^<]{1,40})\s*<',
                html or '',
                re.I,
            ):
                t = self._clean(title)
                if t:
                    parts.append('%s$%s' % (t, self._abs(href)))
            m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or '')
            if m3:
                parts = ['高清$%s' % m3.group(0).replace('\\/', '/')] + parts
            player = re.search(r'player_[a-z]+\s*=\s*(\{[\s\S]*?\})', html or '')
            if player:
                try:
                    js = json.loads(player.group(1).replace("'", '"'))
                    u = js.get('url') or ''
                    if u:
                        parts = [('%s$%s' % (js.get('from') or '线路', u))] + parts
                except Exception:
                    pass
        except Exception as e:
            print('获取详情失败: %s' % e)
        if not parts:
            parts.append('播放$%s/vodplay/%s.html' % (self.siteUrl, vid))
        return {
            'list': [{
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_remarks': remarks,
                'vod_content': (desc or '').strip(),
                'vod_play_from': '午夜TV',
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
        html = self.fetch_text(play_url if play_url.startswith('http') else self.siteUrl + '/vodplay/%s.html' % play_url)
        m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or '')
        if m3:
            return {'parse': 0, 'url': m3.group(0).replace('\\/', '/'), 'header': header}
        mp4 = re.search(r'https?://[^\s"\']+\.mp4[^\s"\']*', html or '')
        if mp4:
            return {'parse': 0, 'url': mp4.group(0).replace('\\/', '/'), 'header': header}
        return {
            'parse': 1,
            'jx': '1',
            'url': play_url if play_url.startswith('http') else self.siteUrl + '/vodplay/%s.html' % play_url,
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
