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
        self.siteUrl = 'https://m.yifan.tv'
        self.pcUrl = 'https://www.yifan.tv'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            'anime': {'name': '动漫', 'path': '/list/anime'},
            'tv': {'name': '电视剧', 'path': '/list/tv'},
            'movie': {'name': '电影', 'path': '/list/movie'},
            'variety': {'name': '综艺', 'path': '/list/variety'},
            'documentary': {'name': '纪录片', 'path': '/list/documentary'},
        }

    def getName(self):
        return '爱壹帆'

    def init(self, extend=""):
        pass

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Accept': 'text/html,application/json,application/xhtml+xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
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

    def _clean(self, s):
        return re.sub(r'<[^>]+>', '', str(s or '')).strip()

    def _parse_cards(self, html):
        videos, seen = [], set()
        for m in re.finditer(
            r'href="([^"]*/play/([A-Za-z0-9_-]+))"[^>]*>[\s\S]{0,400}?(?:alt|title)="([^"]+)"',
            html or '',
            re.I,
        ):
            vid, name = m.group(2), self._clean(m.group(3))
            if vid in seen:
                continue
            seen.add(vid)
            videos.append({'vod_id': vid, 'vod_name': name or vid, 'vod_pic': '', 'vod_remarks': ''})
        for m in re.finditer(r'href="[^"]*/play/([A-Za-z0-9_-]+)"[^>]*>([^<]{2,80})</a>', html or '', re.I):
            vid, name = m.group(1), self._clean(m.group(2))
            if vid in seen or name in ('详情', '播放', '选集'):
                continue
            seen.add(vid)
            videos.append({'vod_id': vid, 'vod_name': name or vid, 'vod_pic': '', 'vod_remarks': ''})
        for m in re.finditer(
            r'/play/([A-Za-z0-9_-]+)[^"]*"[^>]*>[\s\S]{0,200}?<img[^>]+(?:src|data-src)="([^"]+)"',
            html or '',
            re.I,
        ):
            vid, pic = m.group(1), self._abs(m.group(2))
            for v in videos:
                if v['vod_id'] == vid and not v['vod_pic']:
                    v['vod_pic'] = pic
        return videos

    def _list_page(self, path, pg=1):
        videos = []
        urls = []
        if path.startswith('http'):
            urls.append(path)
        else:
            urls.append(self.siteUrl + path)
            urls.append(self.pcUrl + path)
        if pg and int(pg) > 1:
            extra = []
            for u in urls:
                extra.append(u + (('&' if '?' in u else '?') + 'page=' + str(pg)))
                extra.append(u.rstrip('/') + '/page/' + str(pg))
            urls = extra + urls
        for url in urls:
            html = self.fetch_text(url)
            videos = self._parse_cards(html)
            if videos:
                break
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            videos = self._list_page('/list/anime', 1)
            if len(videos) < 8:
                videos.extend(self._list_page('/', 1))
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        out, seen = [], set()
        for v in videos:
            if v['vod_id'] in seen:
                continue
            seen.add(v['vod_id'])
            out.append(v)
        return {'list': out[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            path = self.channels.get(str(tid), {}).get('path', '/list/anime')
            videos = self._list_page(path, pg)
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
            for path in (
                '/search?q=' + q,
                '/search?wd=' + q,
                '/list/search?keyword=' + q,
            ):
                videos = self._list_page(path, pg)
                if videos:
                    break
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
        vid = str((ids or [''])[0])
        name, pic, desc, remarks, year = vid, '', '', '', ''
        parts = []
        try:
            html = self.fetch_text(self.siteUrl + '/play/' + vid)
            if not html or len(html) < 200:
                html = self.fetch_text(self.pcUrl + '/play/' + vid)
            tm = re.search(r'<title>([^<]+)</title>', html or '')
            if tm:
                name = re.sub(r'[-_|].*(爱壹帆|在线|免费).*$', '', tm.group(1)).strip() or name
                name = re.sub(r'-免费在线观看.*$', '', name).strip()
            hm = re.search(r'<h[12][^>]*>([^<]{2,80})</h[12]>', html or '')
            if hm:
                name = self._clean(hm.group(1)) or name
            pm = re.search(r'og:image["\']\s+content=["\']([^"\']+)', html or '')
            if pm:
                pic = self._abs(pm.group(1))
            dm = re.search(r'og:description["\']\s+content=["\']([^"\']+)', html or '')
            if dm:
                desc = dm.group(1)
            rm = re.search(r'(\d+集全|更新到?\s*\S+|更新\s*\d+)', html or '')
            if rm:
                remarks = rm.group(1)
            # episode buttons like 01 02 03
            eps = re.findall(r'(?:href="[^"]*/play/([A-Za-z0-9_-]+)(?:\?ep=(\d+))?"[^>]*>\s*(0?\d+|SP|全集)\s*<)', html or '', re.I)
            if not eps:
                # same page episode index
                for label in re.findall(r'>\s*(0?\d+|SP)\s*<', html or ''):
                    parts.append('%s$%s/play/%s?ep=%s' % (label, self.siteUrl, vid, label))
            else:
                for epid, epn, label in [(a, b, c) if len(a) else ('', '', '') for a, b, c in []]:
                    pass
                seen = set()
                for m in re.finditer(
                    r'href="([^"]*/play/([A-Za-z0-9_-]+)[^"]*)"[^>]*>\s*(0?\d+|SP|第\d+集)\s*<',
                    html or '',
                    re.I,
                ):
                    label = m.group(3)
                    href = self._abs(m.group(1))
                    key = label + href
                    if key in seen:
                        continue
                    seen.add(key)
                    parts.append('%s$%s' % (label, href))
            if not parts:
                m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or '')
                if m3:
                    parts.append('高清$%s' % m3.group(0))
                else:
                    parts.append('播放$%s/play/%s' % (self.siteUrl, vid))
        except Exception as e:
            print('获取详情失败: %s' % e)
            parts = ['播放$%s/play/%s' % (self.siteUrl, vid)]
        return {
            'list': [{
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_year': year,
                'vod_remarks': remarks or ('%s集' % len(parts) if len(parts) > 1 else ''),
                'vod_content': (desc or '').replace('\n\n', '\n').strip(),
                'vod_play_from': '爱壹帆',
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
        html = self.fetch_text(play_url if play_url.startswith('http') else self.siteUrl + '/play/' + play_url)
        m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or '')
        if m3:
            return {'parse': 0, 'url': m3.group(0).replace('\\/', '/'), 'header': header}
        mp4 = re.search(r'https?://[^\s"\']+\.mp4[^\s"\']*', html or '')
        if mp4:
            return {'parse': 0, 'url': mp4.group(0).replace('\\/', '/'), 'header': header}
        return {
            'parse': 1,
            'jx': '1',
            'url': play_url if play_url.startswith('http') else self.siteUrl + '/play/' + play_url,
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
