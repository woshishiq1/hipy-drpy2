#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
    """乐视视频 https://lefun.le.com"""

    def __init__(self):
        self.siteUrl = 'https://lefun.le.com'
        self.wwwUrl = 'https://www.le.com'
        self.mApi = 'https://d.api.m.le.com'
        self.listApi = 'https://list.le.com'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            '1': {'name': '电影', 'cid': '1'},
            '2': {'name': '电视剧', 'cid': '2'},
            '5': {'name': '动漫', 'cid': '5'},
            '11': {'name': '综艺', 'cid': '11'},
            '16': {'name': '纪录片', 'cid': '16'},
            '4': {'name': '体育', 'cid': '4'},
        }

    def getName(self):
        return '乐视视频'

    def init(self, extend=""):
        pass

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Accept': 'application/json, text/plain, */*',
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
            m = re.search(r'(\{[\s\S]+\}|\[[\s\S]+\])', text)
            if m:
                try:
                    return json.loads(m.group(1))
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
        return u.replace('http://', 'https://')

    def _clean(self, s):
        return re.sub(r'<[^>]+>', '', str(s or '')).replace('&nbsp;', ' ').strip()

    def _walk(self, obj, acc=None):
        if acc is None:
            acc = []
        if isinstance(obj, dict):
            keys = set(obj.keys())
            if keys & {'aid', 'vid', 'pid', 'albumId', 'leId', 'id'} and (
                obj.get('name') or obj.get('title') or obj.get('albumName')
            ):
                acc.append(obj)
            for v in obj.values():
                self._walk(v, acc)
        elif isinstance(obj, list):
            for v in obj:
                self._walk(v, acc)
        return acc

    def _map_item(self, it):
        if not isinstance(it, dict):
            return None
        vid = str(it.get('aid') or it.get('pid') or it.get('albumId') or it.get('leId') or it.get('vid') or it.get('id') or '')
        name = it.get('name') or it.get('title') or it.get('albumName') or it.get('subTitle') or ''
        pic = it.get('pic') or it.get('img') or it.get('poster') or it.get('images') or ''
        if isinstance(pic, dict):
            pic = pic.get('pic169') or pic.get('pic300') or next(iter(pic.values()), '')
        remarks = it.get('subTitle') or it.get('rating') or it.get('episodes') or it.get('isEnd') or ''
        if it.get('nowEpisodes'):
            remarks = '更新至%s集' % it.get('nowEpisodes')
        elif it.get('episodes'):
            remarks = '全%s集' % it.get('episodes')
        if not vid or not name:
            return None
        return {
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': self._abs(str(pic)),
            'vod_remarks': str(remarks),
        }

    def _parse_html(self, html):
        videos, seen = [], set()
        for m in re.finditer(
            r'href="((?:https?://[^"/]+)?/(?:ptv|vplay|video)/(?:[^"]*?))"[^>]{0,220}(?:title|alt)="([^"]+)"',
            html or '',
            re.I,
        ):
            href, name = m.group(1), self._clean(m.group(2))
            vid_m = re.search(r'(\d{5,})', href)
            vid = vid_m.group(1) if vid_m else href
            if not name or vid in seen:
                continue
            seen.add(vid)
            videos.append({
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': '',
                'vod_remarks': '',
            })
        for m in re.finditer(r'(\d{6,})\.html[^>]{0,80}>([^<]{2,40})', html or ''):
            vid, name = m.group(1), self._clean(m.group(2))
            if vid in seen or not name:
                continue
            seen.add(vid)
            videos.append({
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': '',
                'vod_remarks': '',
            })
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            html = self.fetch_text(self.siteUrl + '/')
            videos = self._parse_html(html)
            if not videos:
                data = self.fetch_json(
                    self.mApi + '/card/dynamic',
                    params={'cid': '2', 'platform': 'mobile', 'type': 'recommend'},
                )
                for it in self._walk(data):
                    v = self._map_item(it)
                    if v:
                        videos.append(v)
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            cid = self.channels.get(str(tid), {}).get('cid', str(tid) or '2')
            data = self.fetch_json(
                self.mApi + '/list',
                params={'cid': cid, 'page': pg, 'pagesize': 30, 'platform': 'mobile'},
            )
            if not data:
                data = self.fetch_json(
                    'https://list.le.com/apipccard/chnllist',
                    params={'cid': cid, 'page': pg, 'src': 1},
                )
            for it in self._walk(data):
                v = self._map_item(it)
                if v:
                    videos.append(v)
            if not videos:
                html = self.fetch_text(self.siteUrl + '/')
                videos = self._parse_html(html)
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 12 else pg,
            'limit': 30,
            'total': 9999,
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        try:
            q = urllib.parse.quote(key)
            data = self.fetch_json(
                'https://so.le.com/s',
                params={'wd': key, 'page': pg},
            )
            for it in self._walk(data):
                v = self._map_item(it)
                if v:
                    videos.append(v)
            if not videos:
                html = self.fetch_text('https://so.le.com/s?wd=' + q)
                videos = self._parse_html(html)
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
        name, pic, desc, remarks = vid, '', '', ''
        play_from, play_urls = ['乐视'], []
        try:
            page = vid if vid.startswith('http') else ('https://www.le.com/ptv/vplay/%s.html' % vid)
            html = self.fetch_text(page)
            data = self.fetch_json(
                self.mApi + '/apipccard/dynamic',
                params={'cid': '2', 'vid': re.sub(r'\D', '', vid) or vid, 'platform': 'pc', 'type': 'episode'},
            )
            items = self._walk(data)
            first = items[0] if items else {}
            name = first.get('name') or first.get('title') or name
            pic = self._abs(str(first.get('pic') or first.get('img') or ''))
            desc = first.get('description') or first.get('subTitle') or ''
            if items:
                for it in items:
                    epn = it.get('name') or it.get('title') or it.get('episode') or '播放'
                    epid = it.get('vid') or it.get('id') or vid
                    url = it.get('playUrl') or ('https://www.le.com/ptv/vplay/%s.html' % epid)
                    play_urls.append('%s$%s' % (epn, url))
            if not play_urls:
                tm = re.search(r'<title>([^<]+)</title>', html or '')
                if tm:
                    name = re.sub(r'\s*[-_|].*$', '', tm.group(1)).strip() or name
                m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or '')
                mp4 = re.search(r'https?://[^\s"\']+\.mp4[^\s"\']*', html or '')
                play_urls.append('播放$%s' % ((m3 or mp4).group(0) if (m3 or mp4) else page))
            remarks = '共%s集' % len(play_urls) if len(play_urls) > 1 else '乐视'
        except Exception as e:
            print('获取详情失败: %s' % e)
            play_urls = ['播放$https://www.le.com/ptv/vplay/%s.html' % vid]
        return {'list': [{
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': remarks,
            'vod_actor': '',
            'vod_director': '',
            'vod_content': (desc or '').strip(),
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '#'.join(play_urls),
        }]}

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': 'https://www.le.com/',
            'Origin': 'https://www.le.com',
        }
        play = str(id or '')
        if self.isVideoFormat(play) and play.startswith('http'):
            return {'parse': 0, 'jx': '0', 'url': play, 'header': header}
        if play.isdigit():
            play = 'https://www.le.com/ptv/vplay/%s.html' % play
        if play.startswith('/'):
            play = self.wwwUrl + play
        html = self.fetch_text(play) if play.startswith('http') else ''
        m = re.search(r'https?://[^\s"\']+\.(?:m3u8|mp4)[^\s"\']*', html or '')
        if m:
            return {'parse': 0, 'jx': '0', 'url': m.group(0).replace('\\/', '/'), 'header': header}
        vid = re.search(r'(\d{5,})', play)
        if vid:
            tkey = str(int(time.time()))
            js = self.fetch_json(
                'https://player-pc.le.com/mms/out/video/playJson.json',
                params={
                    'platid': '3',
                    'splatid': '304',
                    'tss': 'no',
                    'id': vid.group(1),
                    'detect': '1',
                    'dvtype': '1300',
                    'domain': 'www.le.com',
                    'tkey': tkey,
                },
            )
            playurl = ((js.get('msgs') or {}).get('playurl') or {})
            dispatch = playurl.get('dispatch') or {}
            domain = (playurl.get('domain') or [''])
            if isinstance(domain, list):
                domain = domain[0] if domain else ''
            path = ''
            if isinstance(dispatch, dict) and dispatch:
                path = list(dispatch.values())[0]
                if isinstance(path, list):
                    path = path[0]
            if domain and path:
                url = str(domain) + str(path)
                if not url.startswith('http'):
                    url = 'https:' + url
                return {'parse': 0, 'jx': '0', 'url': url, 'header': header}
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
