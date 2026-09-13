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
    """四川广播电视台 https://www.sctv.com/video/"""

    def __init__(self):
        self.siteUrl = 'https://www.sctv.com'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            'live': {'name': '频道直播'},
            'replay': {'name': '电视回放'},
            'video': {'name': '热门视频'},
            'news': {'name': '新闻联播'},
            'column': {'name': '热门栏目'},
        }
        self.lives = [
            {'id': 'sctv1', 'name': '四川卫视', 'remarks': 'SCTV-1'},
            {'id': 'sctv2', 'name': '四川文旅', 'remarks': 'SCTV-2'},
            {'id': 'sctv3', 'name': '四川经济', 'remarks': 'SCTV-3'},
            {'id': 'sctv4', 'name': '四川新闻', 'remarks': 'SCTV-4'},
            {'id': 'sctv5', 'name': '四川影视文艺', 'remarks': 'SCTV-5'},
            {'id': 'sctv6', 'name': '四川妇女儿童', 'remarks': 'SCTV-6'},
            {'id': 'sctv7', 'name': '四川乡村', 'remarks': 'SCTV-7'},
            {'id': 'kangba', 'name': '康巴卫视', 'remarks': 'SCTV-11'},
            {'id': 'sctv4k', 'name': '四川卫视4K', 'remarks': '超高清'},
        ]

    def getName(self):
        return '四川卫视'

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
        return re.sub(r'<[^>]+>', '', str(s or '')).replace('&nbsp;', ' ').strip()

    def _parse_cards(self, html):
        videos, seen = [], set()
        for m in re.finditer(
            r'href="((?:https?://www\.sctv\.com)?/(?:news|video|column|live|replay)/[^"]+)"[^>]{0,160}(?:title|alt)="([^"]*)"',
            html or '',
            re.I,
        ):
            href, name = m.group(1), self._clean(m.group(2))
            vid = href.split('sctv.com')[-1]
            if not name or vid in seen:
                continue
            seen.add(vid)
            videos.append({
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': '',
                'vod_remarks': '四川台',
            })
        if not videos:
            for m in re.finditer(r'href="(/news/\d+)"[^>]*>([^<]{4,80})', html or ''):
                vid, name = m.group(1), self._clean(m.group(2))
                if vid in seen or not name:
                    continue
                seen.add(vid)
                videos.append({
                    'vod_id': vid,
                    'vod_name': name,
                    'vod_pic': '',
                    'vod_remarks': '新闻',
                })
        for m in re.finditer(
            r'(/(?:news|video)/[^"]+)[\s\S]{0,240}?(?:src|data-src|data-original)="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
            html or '',
            re.I,
        ):
            path = m.group(1)
            for v in videos:
                if path in v['vod_id'] and not v['vod_pic']:
                    v['vod_pic'] = self._abs(m.group(2))
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            html = self.fetch_text(self.siteUrl + '/video/')
            if not html:
                html = self.fetch_text(self.siteUrl + '/')
            videos = self._parse_cards(html)
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            tid = str(tid or 'video')
            if tid == 'live':
                for ch in self.lives:
                    videos.append({
                        'vod_id': 'live/' + ch['id'],
                        'vod_name': ch['name'],
                        'vod_pic': '',
                        'vod_remarks': ch['remarks'],
                    })
            else:
                paths = {
                    'replay': ['/video/', '/'],
                    'video': ['/video/'],
                    'news': ['/', '/news/'],
                    'column': ['/'],
                }.get(tid, ['/video/'])
                for path in paths:
                    html = self.fetch_text(self.siteUrl + path)
                    videos = self._parse_cards(html)
                    if videos:
                        break
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg,
            'limit': 24,
            'total': len(videos),
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        try:
            q = urllib.parse.quote(key)
            for url in (
                self.siteUrl + '/search?keyword=' + q,
                self.siteUrl + '/search/?q=' + q,
                self.siteUrl + '/',
            ):
                html = self.fetch_text(url)
                videos = self._parse_cards(html)
                if videos and url != self.siteUrl + '/':
                    break
            if url == self.siteUrl + '/' and videos:
                videos = [v for v in videos if key in v['vod_name']]
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg,
            'limit': 24,
            'total': len(videos),
        }

    def detailContent(self, ids):
        vid = str((ids or [''])[0])
        name, pic, desc = vid, '', ''
        froms, urls = [], []
        try:
            if vid.startswith('live/'):
                cid = vid.split('/', 1)[-1]
                ch = next((c for c in self.lives if c['id'] == cid), {'name': cid, 'remarks': '直播'})
                name = ch['name']
                froms = ['四川台直播']
                play = self.siteUrl + '/live/' + cid
                urls = ['直播$%s' % play]
            else:
                page = self._abs(vid if vid.startswith('/') else '/' + vid)
                html = self.fetch_text(page)
                tm = re.search(r'<title>([^<]+)</title>', html or '')
                if tm:
                    name = re.sub(r'\s*[-_|].*$', '', tm.group(1)).strip() or name
                hm = re.search(r'<h1[^>]*>([\s\S]{2,80})</h1>', html or '')
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
                froms = ['四川卫视']
                urls = ['播放$%s' % (play or page)]
        except Exception as e:
            print('获取详情失败: %s' % e)
        if not urls:
            froms = ['四川卫视']
            urls = ['播放$%s' % self._abs(vid)]
        return {'list': [{
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': '四川广播电视台',
            'vod_actor': '',
            'vod_director': '',
            'vod_content': (desc or '').strip(),
            'vod_play_from': '$$$'.join(froms),
            'vod_play_url': '$$$'.join(urls),
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
