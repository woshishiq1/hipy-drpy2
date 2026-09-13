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
    """AcFun https://m.acfun.cn"""

    def __init__(self):
        self.siteUrl = 'https://m.acfun.cn'
        self.wwwUrl = 'https://www.acfun.cn'
        self.api = 'https://www.acfun.cn/rest/pc-direct'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            '1': {'name': '动画', 'cid': '1'},
            '155': {'name': '番剧', 'cid': '155'},
            '60': {'name': '娱乐', 'cid': '60'},
            '123': {'name': '生活', 'cid': '123'},
            '59': {'name': '游戏', 'cid': '59'},
            '70': {'name': '科技', 'cid': '70'},
            '86': {'name': '音乐', 'cid': '86'},
            '124': {'name': '舞蹈', 'cid': '124'},
        }

    def getName(self):
        return 'AcFun'

    def init(self, extend=""):
        pass

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.wwwUrl + '/',
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
            return self.wwwUrl + u
        return u.replace('http://', 'https://')

    def _walk(self, obj, acc=None):
        if acc is None:
            acc = []
        if isinstance(obj, dict):
            if obj.get('title') or obj.get('contentTitle') or obj.get('bangumiTitle'):
                if obj.get('dougaId') or obj.get('contentId') or obj.get('bangumiId') or obj.get('ac') or obj.get('id'):
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
        bid = it.get('bangumiId') or it.get('albumId')
        vid = it.get('dougaId') or it.get('contentId') or it.get('ac') or it.get('id') or bid
        name = it.get('title') or it.get('contentTitle') or it.get('bangumiTitle') or it.get('caption') or ''
        pic = it.get('coverUrl') or it.get('cover') or it.get('image') or it.get('pic') or it.get('shareImage') or ''
        remarks = it.get('userName') or it.get('channelName') or it.get('viewCountShow') or ''
        if bid and not str(vid).startswith('aa'):
            vod_id = 'aa' + str(bid)
        else:
            s = str(vid)
            vod_id = s if s.startswith(('ac', 'aa')) else ('ac' + s)
        if not name:
            return None
        return {
            'vod_id': vod_id,
            'vod_name': name,
            'vod_pic': self._abs(str(pic)),
            'vod_remarks': str(remarks),
        }

    def _parse_html(self, html):
        videos, seen = [], set()
        for m in re.finditer(
            r'href="((?:https?://[^"/]+)?/(?:v/ac|bangumi/aa)[^"]+)"[^>]{0,200}(?:title|alt)="([^"]*)"',
            html or '',
            re.I,
        ):
            href, name = m.group(1), re.sub(r'<[^>]+>', '', m.group(2)).strip()
            mid = re.search(r'(ac\d+|aa\d+)', href)
            vid = mid.group(1) if mid else href
            if not name or vid in seen:
                continue
            seen.add(vid)
            videos.append({'vod_id': vid, 'vod_name': name, 'vod_pic': '', 'vod_remarks': ''})
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            data = self.fetch_json(self.api + '/rank/channel', params={
                'rankLimit': '30',
                'rankPeriod': 'DAY',
                'channelId': '0',
            })
            for it in self._walk(data):
                v = self._map_item(it)
                if v:
                    videos.append(v)
            if not videos:
                html = self.fetch_text(self.siteUrl + '/')
                videos = self._parse_html(html)
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            cid = self.channels.get(str(tid), {}).get('cid', str(tid) or '1')
            if str(tid) == '155':
                data = self.fetch_json(self.wwwUrl + '/rest/pc-direct/page/bangumi', params={'pageNo': pg})
                if not data:
                    data = self.fetch_json(self.api + '/rank/channel', params={
                        'rankLimit': '30', 'rankPeriod': 'WEEK', 'channelId': '155',
                    })
            else:
                data = self.fetch_json(self.api + '/rank/channel', params={
                    'rankLimit': '30',
                    'rankPeriod': 'DAY',
                    'channelId': cid,
                })
            for it in self._walk(data):
                v = self._map_item(it)
                if v:
                    videos.append(v)
            if not videos:
                html = self.fetch_text(self.wwwUrl + '/v/list' + cid + '/index.htm')
                videos = self._parse_html(html)
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 10 else pg,
            'limit': 30,
            'total': 9999,
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        try:
            data = self.fetch_json(self.api + '/search/content', params={
                'keyword': key,
                'pCursor': str(pg),
                'resourceType': '2',
                'sortType': '1',
            })
            for it in self._walk(data):
                v = self._map_item(it)
                if v:
                    videos.append(v)
            if not videos:
                q = urllib.parse.quote(key)
                html = self.fetch_text(self.wwwUrl + '/search?keyword=' + q)
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

    def _page_url(self, vid):
        s = str(vid or '')
        if s.startswith('http'):
            return s
        if s.startswith('aa'):
            return self.wwwUrl + '/bangumi/' + s
        if s.startswith('ac'):
            return self.wwwUrl + '/v/' + s
        if s.isdigit():
            return self.wwwUrl + '/v/ac' + s
        return self.wwwUrl + '/' + s.lstrip('/')

    def detailContent(self, ids):
        vid = str((ids or [''])[0])
        name, pic, desc, actor = vid, '', '', ''
        play_urls = []
        try:
            page = self._page_url(vid)
            html = self.fetch_text(page)
            jm = re.search(r'window\.(?:videoInfo|bangumiData)\s*=\s*(\{[\s\S]*?\});', html or '')
            info = {}
            if jm:
                try:
                    info = json.loads(jm.group(1))
                except Exception:
                    info = {}
            name = info.get('title') or info.get('bangumiTitle') or name
            pic = self._abs(str(info.get('coverUrl') or info.get('cover') or info.get('image') or ''))
            desc = info.get('description') or info.get('intro') or ''
            user = info.get('user') or {}
            actor = user.get('name') or info.get('userName') or ''
            vlist = info.get('videoList') or info.get('items') or info.get('episodeList') or []
            if isinstance(vlist, list) and vlist:
                for i, ep in enumerate(vlist, 1):
                    if not isinstance(ep, dict):
                        continue
                    epn = ep.get('title') or ep.get('episodeName') or ('P%s' % i)
                    eid = ep.get('id') or ep.get('videoId') or ep.get('dougaId') or vid
                    play_urls.append('%s$%s' % (epn, self._page_url(str(eid) if str(eid).startswith('ac') else vid)))
            if not play_urls:
                play_urls.append('播放$%s' % page)
            if not name:
                tm = re.search(r'<title>([^<]+)</title>', html or '')
                if tm:
                    name = re.sub(r'\s*[-_|].*$', '', tm.group(1)).strip() or vid
        except Exception as e:
            print('获取详情失败: %s' % e)
            play_urls = ['播放$%s' % self._page_url(vid)]
        return {'list': [{
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': 'AcFun',
            'vod_actor': actor,
            'vod_director': '',
            'vod_content': (desc or '').strip(),
            'vod_play_from': 'AcFun',
            'vod_play_url': '#'.join(play_urls),
        }]}

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.wwwUrl + '/',
            'Origin': self.wwwUrl,
        }
        play = str(id or '')
        if self.isVideoFormat(play) and play.startswith('http'):
            return {'parse': 0, 'jx': '0', 'url': play, 'header': header}
        page = self._page_url(play)
        html = self.fetch_text(page)
        m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or '')
        if m3:
            return {'parse': 0, 'jx': '0', 'url': m3.group(0).replace('\\/', '/'), 'header': header}
        ks = re.search(r'ksPlayJson["\']?\s*[:=]\s*["\'](\{.+?\})["\']', html or '')
        if ks:
            try:
                raw = ks.group(1).encode().decode('unicode_escape')
                jo = json.loads(raw)
                reps = (((jo.get('adaptationSet') or [{}])[0]).get('representation') or [])
                url = (reps[-1] or {}).get('url') if reps else ''
                if url:
                    return {'parse': 0, 'jx': '0', 'url': url, 'header': header}
            except Exception:
                pass
        jm = re.search(r'window\.videoInfo\s*=\s*(\{[\s\S]*?\});', html or '')
        if jm:
            try:
                info = json.loads(jm.group(1))
                cur = info.get('currentVideoInfo') or {}
                ksj = cur.get('ksPlayJson')
                if isinstance(ksj, str):
                    jo = json.loads(ksj)
                    reps = (((jo.get('adaptationSet') or [{}])[0]).get('representation') or [])
                    url = (reps[-1] or {}).get('url') if reps else ''
                    if url:
                        return {'parse': 0, 'jx': '0', 'url': url, 'header': header}
            except Exception:
                pass
        return {'parse': 1, 'jx': '1', 'url': page, 'header': header}

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
