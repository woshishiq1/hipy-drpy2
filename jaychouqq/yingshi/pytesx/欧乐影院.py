#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
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
    """欧乐影院 https://www.olevod.com  + api.olelive.com"""

    def __init__(self):
        self.siteUrl = 'https://www.olevod.com'
        self.api = 'https://api.olelive.com'
        self.static = 'https://static.olelive.com/'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            '1': {'name': '电影', 'type_id': '1'},
            '2': {'name': '电视剧', 'type_id': '2'},
            '14': {'name': '短剧', 'type_id': '14'},
            '3': {'name': '综艺', 'type_id': '3'},
            '4': {'name': '动漫', 'type_id': '4'},
        }

    def getName(self):
        return '欧乐影院'

    def init(self, extend=""):
        pass

    def _vv(self):
        ts = str(int(time.time()))
        rows = ['', '', '', '']
        for ch in ts:
            bits = bin(ord(ch))[2:]
            rows[0] += bits[2:3] if len(bits) > 2 else ''
            rows[1] += bits[3:4] if len(bits) > 3 else ''
            rows[2] += bits[4:5] if len(bits) > 4 else ''
            rows[3] += bits[5:] if len(bits) > 5 else ''
        parts = []
        for row in rows:
            if not row:
                parts.append('000')
                continue
            hx = format(int(row, 2), 'x')
            if len(hx) == 2:
                hx = '0' + hx
            elif len(hx) == 1:
                hx = '00' + hx
            elif len(hx) == 0:
                hx = '000'
            parts.append(hx)
        n = hashlib.md5(ts.encode('utf-8')).hexdigest()
        return (
            n[0:3] + parts[0] +
            n[6:11] + parts[1] +
            n[14:19] + parts[2] +
            n[22:27] + parts[3] +
            n[30:]
        )

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Origin': self.siteUrl,
                'Accept': 'application/json, text/plain, */*',
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

    def fetch_json(self, url):
        if '?' in url:
            url = url + '&_vv=' + self._vv()
        else:
            url = url + '?_vv=' + self._vv()
        resp = self.fetch(url)
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

    def fetch_text(self, url):
        resp = self.fetch(url)
        return getattr(resp, 'text', '') if resp else ''

    def _pic(self, p):
        if not p:
            return ''
        if str(p).startswith('http'):
            return p
        return self.static + str(p).lstrip('/')

    def _parseVideoItem(self, item):
        return {
            'vod_id': str(item.get('id') or item.get('vod_id') or ''),
            'vod_name': item.get('name') or item.get('vod_name') or '',
            'vod_pic': self._pic(item.get('pic') or item.get('vod_pic') or ''),
            'vod_remarks': item.get('remarks') or item.get('vod_remarks') or '',
        }

    def _list_api(self, type_id, pg, limit=48):
        pg = int(pg or 1)
        url = '%s/v1/pub/vod/list/true/3/0/0/%s/0/0/update/%s/%s' % (
            self.api, type_id, pg, limit
        )
        data = self.fetch_json(url)
        items = ((data.get('data') or {}).get('list')) or []
        videos = [self._parseVideoItem(x) for x in items if x]
        total = int((data.get('data') or {}).get('total') or 0)
        pagecount = pg + 1 if len(videos) >= limit else pg
        if total:
            pagecount = max(1, (total + limit - 1) // limit)
        return videos, pagecount, total or len(videos)

    def _html_list(self, tid, pg):
        url = '%s/index.php/vod/show/id/%s/page/%s.html' % (self.siteUrl, tid, pg)
        html = self.fetch_text(url)
        videos = []
        for m in re.finditer(
            r'href="(/index\.php/vod/detail/id/(\d+)\.html)"[^>]*title="([^"]+)"[^>]*',
            html or '',
        ):
            videos.append({
                'vod_id': m.group(2),
                'vod_name': m.group(3),
                'vod_pic': '',
                'vod_remarks': '',
            })
        if not videos:
            for m in re.finditer(
                r'vod/detail/id/(\d+)\.html"[^>]{0,80}title="([^"]+)"',
                html or '',
            ):
                videos.append({
                    'vod_id': m.group(1),
                    'vod_name': m.group(2),
                    'vod_pic': '',
                    'vod_remarks': '',
                })
        for m in re.finditer(
            r'detail/id/(\d+)[^>]{0,200}data-original="([^"]+)"',
            html or '',
        ):
            for v in videos:
                if v['vod_id'] == m.group(1) and not v['vod_pic']:
                    v['vod_pic'] = self._pic(m.group(2))
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            data = self.fetch_json(self.api + '/v1/pub/vod/newest/1/24')
            items = ((data.get('data') or {}).get('list')) or []
            videos = [self._parseVideoItem(x) for x in items]
            if not videos:
                videos, _, _ = self._list_api('2', 1, 24)
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos, pagecount, total = [], pg, 0
        try:
            info = self.channels.get(str(tid), {'type_id': str(tid)})
            type_id = info.get('type_id', str(tid))
            videos, pagecount, total = self._list_api(type_id, pg, 48)
            if not videos:
                videos = self._html_list(type_id, pg)
                pagecount = pg + 1 if len(videos) >= 20 else pg
                total = len(videos)
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': 48,
            'total': total,
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        try:
            q = urllib.parse.quote(key)
            data = self.fetch_json('%s/v1/pub/index/search/%s/vod/0/%s/24' % (self.api, q, pg))
            block = ((data.get('data') or {}).get('data') or [{}])
            if isinstance(block, list) and block:
                items = (block[0] or {}).get('list') or []
            else:
                items = (data.get('data') or {}).get('list') or []
            if items:
                videos = [self._parseVideoItem(x) for x in items]
            if not videos:
                html = self.fetch_text(
                    self.siteUrl + '/index.php/vod/search/page/%s/wd/%s.html' % (pg, q)
                )
                for m in re.finditer(r'vod/detail/id/(\d+)\.html"[^>]*title="([^"]+)"', html or ''):
                    videos.append({
                        'vod_id': m.group(1),
                        'vod_name': m.group(2),
                        'vod_pic': '',
                        'vod_remarks': '',
                    })
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
        try:
            data = self.fetch_json('%s/v1/pub/vod/detail/%s/true' % (self.api, vid))
            info = data.get('data') or {}
            name = info.get('name') or info.get('vod_name') or vid
            pic = self._pic(info.get('pic') or info.get('vod_pic') or '')
            remarks = info.get('remarks') or info.get('vod_remarks') or ''
            content = info.get('content') or info.get('vod_content') or info.get('blurb') or ''
            actor = info.get('actor') or info.get('vod_actor') or ''
            director = info.get('director') or info.get('vod_director') or ''
            urls = info.get('urls') or []
            groups = info.get('play_list') or info.get('vod_play_list') or []
            play_from = []
            play_urls = []
            if urls:
                parts = []
                for ep in urls:
                    if ep.get('vip') is True:
                        continue
                    title = ep.get('title') or ep.get('name') or '播放'
                    u = ep.get('url') or ''
                    if u:
                        parts.append('%s$%s' % (title, u))
                if parts:
                    play_from.append('欧乐')
                    play_urls.append('#'.join(parts))
            if groups and not play_urls:
                for g in groups:
                    flag = g.get('from') or g.get('name') or '线路'
                    eps = g.get('urls') or g.get('list') or []
                    parts = []
                    for ep in eps:
                        if isinstance(ep, dict):
                            if ep.get('vip') is True:
                                continue
                            parts.append('%s$%s' % (ep.get('title') or ep.get('name') or '播放', ep.get('url') or ''))
                        elif isinstance(ep, str) and '$' in ep:
                            parts.append(ep)
                    if parts:
                        play_from.append(flag)
                        play_urls.append('#'.join(parts))
            if not play_urls:
                html = self.fetch_text('%s/index.php/vod/detail/id/%s.html' % (self.siteUrl, vid))
                tm = re.search(r'<h[12][^>]*>([^<]+)</h[12]>', html or '')
                if tm:
                    name = tm.group(1).strip() or name
                parts = []
                for href, title in re.findall(
                    r'href="(/index\.php/vod/play/id/%s/sid/\d+/nid/\d+\.html)"[^>]*>([^<]+)' % re.escape(vid),
                    html or '',
                ):
                    parts.append('%s$%s%s' % (title.strip(), self.siteUrl, href))
                if parts:
                    play_from.append('欧乐')
                    play_urls.append('#'.join(parts))
                pm = re.search(r'data-original="([^"]+)"', html or '')
                if pm and not pic:
                    pic = self._pic(pm.group(1))
            if not play_urls:
                play_from = ['欧乐']
                play_urls = ['播放$%s/index.php/vod/play/id/%s.html' % (self.siteUrl, vid)]
            return {'list': [{
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_remarks': remarks,
                'vod_actor': actor if isinstance(actor, str) else ' '.join(actor or []),
                'vod_director': director if isinstance(director, str) else ' '.join(director or []),
                'vod_content': str(content).replace('\n\n', '\n').strip(),
                'vod_play_from': '$$$'.join(play_from),
                'vod_play_url': '$$$'.join(play_urls),
            }]}
        except Exception as e:
            print('获取详情失败: %s' % e)
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
            'Origin': self.siteUrl,
        }
        play_url = str(id or '')
        if self.isVideoFormat(play_url):
            return {'parse': 0, 'url': play_url, 'header': header}
        html = self.fetch_text(play_url if play_url.startswith('http') else self.siteUrl + '/' + play_url)
        m = re.search(r'player_aaaa\s*=\s*(\{[\s\S]*?\})', html or '')
        if m:
            raw = m.group(1).replace("'", '"')
            try:
                js = json.loads(raw)
                u = (js.get('url') or '').replace('\\/', '/')
                if u:
                    if self.isVideoFormat(u):
                        return {'parse': 0, 'url': u, 'header': header}
                    return {'parse': 1, 'jx': '1', 'url': u, 'header': header}
            except Exception:
                um = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                if um:
                    u = um.group(1).replace('\\/', '/')
                    p = 0 if self.isVideoFormat(u) else 1
                    return {'parse': p, 'jx': '1' if p else '0', 'url': u, 'header': header}
        m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or '')
        if m3:
            return {'parse': 0, 'url': m3.group(0).replace('\\/', '/'), 'header': header}
        return {
            'parse': 1,
            'jx': '1',
            'url': play_url if play_url.startswith('http') else self.siteUrl + '/index.php/vod/play/id/' + play_url + '.html',
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
