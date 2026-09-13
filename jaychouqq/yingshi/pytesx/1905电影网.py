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
    """1905电影网 https://m.1905.com"""

    def __init__(self):
        self.siteUrl = 'https://m.1905.com'
        self.pcUrl = 'https://www.1905.com'
        self.vipUrl = 'https://vip.1905.com'
        self.profileApi = 'https://profile.m1905.com/mvod/getVideoinfo.php'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            '1': {'name': '全部电影', 'path': '/vod/list/n_1/o3p{pg}.html'},
            'love': {'name': '爱情', 'path': '/vod/list/n_1_t_1/o3p{pg}.html'},
            'action': {'name': '动作', 'path': '/vod/list/n_1_t_5/o3p{pg}.html'},
            'comedy': {'name': '喜剧', 'path': '/vod/list/n_1_t_25/o3p{pg}.html'},
            'plot': {'name': '剧情', 'path': '/vod/list/n_1_t_16/o3p{pg}.html'},
            'scifi': {'name': '科幻', 'path': '/vod/list/n_1_t_7/o3p{pg}.html'},
            'war': {'name': '战争', 'path': '/vod/list/n_1_t_6/o3p{pg}.html'},
            'horror': {'name': '恐怖', 'path': '/vod/list/n_1_t_8/o3p{pg}.html'},
            'crime': {'name': '犯罪', 'path': '/vod/list/n_1_t_10/o3p{pg}.html'},
            'doc': {'name': '纪录', 'path': '/vod/list/n_1_t_9/o3p{pg}.html'},
            'vip': {'name': 'VIP影院', 'path': '/list/'},
            'tv': {'name': '电视剧', 'path': '/listtv/'},
        }

    def getName(self):
        return '1905电影网'

    def init(self, extend=""):
        pass

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.pcUrl + '/',
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
            return self.pcUrl + u
        return u

    def _clean(self, s):
        return re.sub(r'<[^>]+>', '', str(s or '')).replace('&nbsp;', ' ').strip()

    def _parse_list(self, html):
        videos, seen = [], set()
        pats = [
            r'href="(https?://(?:www|vip|m)\.1905\.com/(?:vod/play|video/play|mdb/film|play)/(\d+)[^"]*)"[^>]{0,200}(?:title|alt)="([^"]+)"',
            r'href="(/(?:vod/play|video/play|mdb/film|play)/(\d+)[^"]*)"[^>]{0,160}(?:title|alt)="([^"]+)"',
            r'href="(https?://vip\.1905\.com/play/(\d+)\.shtml)"[^>]*>([^<]{2,80})',
        ]
        for pat in pats:
            for m in re.finditer(pat, html or '', re.I):
                vid, name = m.group(2), self._clean(m.group(3) or m.group(2))
                if not vid or vid in seen or name in ('详情', '播放', '更多'):
                    continue
                seen.add(vid)
                href = m.group(1)
                prefix = 'vip_' if 'vip.1905.com' in href or '/play/' in href and 'vod' not in href else ''
                if '/mdb/film/' in href:
                    prefix = 'mdb_'
                elif '/vod/play/' in href:
                    prefix = 'vod_'
                elif '/video/play/' in href:
                    prefix = 'video_'
                videos.append({
                    'vod_id': prefix + vid,
                    'vod_name': name,
                    'vod_pic': '',
                    'vod_remarks': '',
                })
        for m in re.finditer(
            r'(?:vod/play|mdb/film|video/play|play)/(\d+)[^"]*"[^>]*>[\s\S]{0,240}?(?:src|data-original|data-src)="([^"]+)"',
            html or '',
            re.I,
        ):
            for v in videos:
                if v['vod_id'].endswith(m.group(1)) and not v['vod_pic']:
                    v['vod_pic'] = self._abs(m.group(2))
        return videos

    def _split_id(self, raw):
        s = str(raw or '')
        m = re.match(r'(vip|vod|mdb|video)_(\d+)$', s)
        if m:
            return m.group(1), m.group(2)
        digits = re.search(r'(\d+)', s)
        return 'vod', digits.group(1) if digits else s

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            for url in (self.siteUrl + '/', self.pcUrl + '/vod/list/n_1/o3p1.html', self.vipUrl + '/'):
                html = self.fetch_text(url)
                videos = self._parse_list(html)
                if videos:
                    break
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            info = self.channels.get(str(tid), self.channels['1'])
            path = (info.get('path') or '/vod/list/n_1/o3p{pg}.html').replace('{pg}', str(pg))
            hosts = [self.pcUrl]
            if str(tid) in ('vip', 'tv'):
                hosts = [self.vipUrl, self.pcUrl]
            for host in hosts:
                html = self.fetch_text(host + path)
                videos = self._parse_list(html)
                if videos:
                    break
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
            for url in (
                '%s/search/?q=%s&page=%s' % (self.pcUrl, q, pg),
                '%s/search.html?q=%s' % (self.siteUrl, q),
                '%s/mdb/search.php?q=%s' % (self.pcUrl, q),
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
            'pagecount': pg + 1 if len(videos) >= 10 else pg,
            'limit': 24,
            'total': len(videos),
        }

    def _pages_for(self, kind, vid):
        pages = [
            '%s/mdb/film/%s/' % (self.pcUrl, vid),
            '%s/vod/play/%s.shtml' % (self.pcUrl, vid),
            '%s/video/play/%s.shtml' % (self.pcUrl, vid),
            '%s/play/%s.shtml' % (self.vipUrl, vid),
            '%s/vod/play/%s.shtml' % (self.siteUrl, vid),
        ]
        if kind == 'vip':
            pages.insert(0, '%s/play/%s.shtml' % (self.vipUrl, vid))
        elif kind == 'mdb':
            pages.insert(0, '%s/mdb/film/%s/' % (self.pcUrl, vid))
        return pages

    def detailContent(self, ids):
        raw = str((ids or [''])[0])
        kind, vid = self._split_id(raw)
        name, pic, desc, remarks, actor, director = vid, '', '', '', '', ''
        froms, urls = [], []
        try:
            html, page = '', ''
            for u in self._pages_for(kind, vid):
                html = self.fetch_text(u)
                if html and len(html) > 400:
                    page = u
                    break
            tm = re.search(r'<title>([^<]+)</title>', html or '')
            if tm:
                name = re.sub(r'\s*[-_|].*$', '', tm.group(1)).strip() or name
            hm = re.search(r'<h1[^>]*>([\s\S]{2,80})</h1>', html or '')
            if hm:
                name = self._clean(hm.group(1)) or name
            pm = re.search(r'(?:og:image["\']\s+content=["\']|data-original=")([^"\']+)', html or '')
            if pm:
                pic = self._abs(pm.group(1))
            dm = re.search(r'og:description["\']\s+content=["\']([^"\']+)', html or '')
            if dm:
                desc = dm.group(1)
            am = re.search(r'主演[:：]\s*([^<\n]+)', html or '')
            if am:
                actor = self._clean(am.group(1))
            dm2 = re.search(r'导演[:：]\s*([^<\n]+)', html or '')
            if dm2:
                director = self._clean(dm2.group(1))
            parts = []
            for href, title in re.findall(
                r'href="(https?://(?:www|vip)\.1905\.com/(?:vod/play|video/play|play)/\d+\.shtml)"[^>]*>([^<]{1,40})',
                html or '',
            ):
                t = self._clean(title)
                if t and t not in ('立即播放', '播放'):
                    parts.append('%s$%s' % (t, href))
            if not parts:
                play = page or '%s/vod/play/%s.shtml' % (self.pcUrl, vid)
                parts = ['正片$%s' % play]
            froms = ['1905']
            urls = ['#'.join(parts)]
        except Exception as e:
            print('获取详情失败: %s' % e)
            froms = ['1905']
            urls = ['正片$%s/vod/play/%s.shtml' % (self.pcUrl, vid)]
        return {'list': [{
            'vod_id': raw,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': remarks,
            'vod_actor': actor,
            'vod_director': director,
            'vod_content': (desc or '').strip(),
            'vod_play_from': '$$$'.join(froms),
            'vod_play_url': '$$$'.join(urls),
        }]}

    def _play_from_page(self, page):
        html = self.fetch_text(page)
        for pat in (
            r'https?://[^\s"\']+\.m3u8[^\s"\']*',
            r'"(?:uhd|hd|sd|url|playurl)"\s*:\s*"(https?://[^"]+)"',
            r'player\.src\s*=\s*["\'](https?://[^"\']+)["\']',
        ):
            m = re.search(pat, html or '', re.I)
            if m:
                u = (m.group(1) if m.lastindex else m.group(0)).replace('\\/', '/')
                if u.startswith('http'):
                    return u
        mid = re.search(r'(?:vid|mediaid|contentid)["\']?\s*[:=]\s*["\']?(\d+)', html or '', re.I)
        if mid:
            data = self.fetch_json(self.profileApi, params={'id': mid.group(1), 'type': 'movie'})
            text = json.dumps(data, ensure_ascii=False)
            m3 = re.search(r'https?://[^\s"\\]+\.m3u8[^\s"\\]*', text)
            if m3:
                return m3.group(0).replace('\\/', '/')
        return ''

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.pcUrl + '/',
            'Origin': self.pcUrl,
        }
        play = str(id or '')
        if self.isVideoFormat(play) and play.startswith('http'):
            return {'parse': 0, 'url': play, 'header': header}
        if not play.startswith('http'):
            kind, vid = self._split_id(play)
            play = '%s/play/%s.shtml' % (self.vipUrl, vid) if kind == 'vip' else '%s/vod/play/%s.shtml' % (self.pcUrl, vid)
        try:
            url = self._play_from_page(play)
            if url:
                p = 0 if self.isVideoFormat(url) else 1
                return {'parse': p, 'jx': '1' if p else '0', 'url': url, 'header': header}
        except Exception as e:
            print('获取播放内容失败: %s' % e)
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
