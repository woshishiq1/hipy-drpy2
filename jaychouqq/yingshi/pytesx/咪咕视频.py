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
    """咪咕视频 https://m.miguvideo.com"""

    LIVE_ROOT = '1ff892f2b5ab4a79be6e25b69d2f5d05'
    CHANNEL_ID = '0132_10010001005'

    def __init__(self):
        self.siteUrl = 'https://m.miguvideo.com'
        self.pcUrl = 'https://www.miguvideo.com'
        self.webApi = 'https://webapi.miguvideo.com'
        self.programApi = 'https://program-sc.miguvideo.com'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            'movie': {'name': '电影', 'kind': 'vod', 'kw': '电影'},
            'tv': {'name': '电视剧', 'kind': 'vod', 'kw': '电视剧'},
            'variety': {'name': '综艺', 'kind': 'vod', 'kw': '综艺'},
            'anime': {'name': '动漫', 'kind': 'vod', 'kw': '动漫'},
            'sport': {'name': '体育', 'kind': 'vod', 'kw': '体育'},
            'live': {'name': '直播频道', 'kind': 'live', 'kw': ''},
        }
        self._live_cache = None

    def getName(self):
        return '咪咕视频'

    def init(self, extend=""):
        pass

    def _headers(self, extra=None):
        h = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
            'Origin': self.pcUrl,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Appcode': 'miguvideo_default_www',
            'Appid': 'miguvideo',
            'Channel': 'H5',
            'x-up-client-channel-id': self.CHANNEL_ID,
        }
        if extra:
            h.update(extra)
        return h

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = self._headers()
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

    def fetch_json(self, url, params=None, headers=None):
        resp = self.fetch(url, headers=headers, params=params)
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
        if str(u).startswith('//'):
            return 'https:' + u
        return u

    def _item(self, obj, live=False):
        vid = str(obj.get('contId') or obj.get('pID') or obj.get('pid') or obj.get('id') or obj.get('contentId') or '')
        name = obj.get('name') or obj.get('title') or obj.get('contName') or obj.get('programName') or vid
        pic = ''
        pics = obj.get('pics') or obj.get('pic') or {}
        if isinstance(pics, dict):
            pic = pics.get('highResolutionH') or pics.get('lowResolutionH') or pics.get('highResolutionV') or ''
        elif isinstance(pics, str):
            pic = pics
        pic = pic or obj.get('h5pics') or obj.get('img') or obj.get('image') or ''
        remarks = obj.get('updateEP') or obj.get('mediaForm') or obj.get('score') or ('直播' if live else '')
        if not vid:
            return None
        return {
            'vod_id': ('live_' if live else '') + vid,
            'vod_name': name,
            'vod_pic': self._abs(pic),
            'vod_remarks': str(remarks),
        }

    def _walk(self, obj, acc=None):
        if acc is None:
            acc = []
        if isinstance(obj, dict):
            if obj.get('contId') or obj.get('pID') or obj.get('contentId'):
                acc.append(obj)
            for v in obj.values():
                self._walk(v, acc)
        elif isinstance(obj, list):
            for v in obj:
                self._walk(v, acc)
        return acc

    def _search_vod(self, keyword, pg=1, size=24):
        videos = []
        params = {
            'searchWord': keyword,
            'pageNum': str(pg),
            'pageSize': str(size),
            'searchType': '0',
        }
        for url in (
            self.webApi + '/gateway/search/v3/search',
            self.webApi + '/gateway/search/v2/search',
        ):
            data = self.fetch_json(url, params=params)
            items = self._walk(data)
            for it in items:
                v = self._item(it, live=False)
                if v:
                    videos.append(v)
            if videos:
                break
        seen, out = set(), []
        for v in videos:
            if v['vod_id'] in seen:
                continue
            seen.add(v['vod_id'])
            out.append(v)
        return out

    def _live_cats(self):
        if self._live_cache:
            return self._live_cache
        data = self.fetch_json(self.programApi + '/live/v2/tv-data/' + self.LIVE_ROOT)
        live_list = ((data.get('body') or {}).get('liveList')) or []
        cats = []
        for c in live_list:
            name = c.get('name') or ''
            vid = c.get('vomsID') or ''
            if not vid or name == '热门':
                continue
            cats.append({'name': name, 'vomsID': vid})
        self._live_cache = cats
        return cats

    def _live_list(self, voms_id):
        data = self.fetch_json(self.programApi + '/live/v2/tv-data/' + voms_id)
        items = ((data.get('body') or {}).get('dataList')) or []
        videos = []
        for it in items:
            v = self._item(it, live=True)
            if v:
                videos.append(v)
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        try:
            for c in self._live_cats():
                classes.append({'type_id': 'livecat_' + c['vomsID'], 'type_name': '直播-' + c['name']})
        except Exception:
            pass
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            videos = self._search_vod('热播', 1, 24)
            if not videos:
                cats = self._live_cats()
                if cats:
                    videos = self._live_list(cats[0]['vomsID'])[:24]
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            tid = str(tid or '')
            if tid.startswith('livecat_'):
                videos = self._live_list(tid.replace('livecat_', '', 1))
            elif tid == 'live':
                for c in self._live_cats():
                    videos.extend(self._live_list(c['vomsID']))
            else:
                info = self.channels.get(tid, {'kind': 'vod', 'kw': tid})
                videos = self._search_vod(info.get('kw') or tid, pg, 24)
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        more = len(videos) >= 12 and not str(tid).startswith('live')
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if more else pg,
            'limit': 24,
            'total': 9999 if more else len(videos),
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        try:
            videos = self._search_vod(key, pg, 24)
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 12 else pg,
            'limit': 24,
            'total': len(videos),
        }

    def _content_info(self, cid):
        for path in (
            '/gateway/program/v3/cont/content-info/%s' % cid,
            '/gateway/program/v2/cont/content-info/%s' % cid,
        ):
            data = self.fetch_json(self.webApi + path)
            body = data.get('body') or data.get('data') or {}
            if body:
                return body
        return {}

    def detailContent(self, ids):
        raw = str((ids or [''])[0])
        is_live = raw.startswith('live_')
        cid = raw.replace('live_', '', 1) if is_live else raw
        name, pic, desc, remarks = cid, '', '', '直播' if is_live else ''
        actor, director = '', ''
        froms, urls = [], []
        try:
            if is_live:
                froms = ['咪咕直播']
                urls = ['直播$live_%s' % cid]
            else:
                info = self._content_info(cid)
                name = info.get('name') or info.get('contName') or info.get('title') or name
                pics = info.get('pics') or {}
                if isinstance(pics, dict):
                    pic = pics.get('highResolutionH') or pics.get('lowResolutionH') or ''
                pic = self._abs(pic or info.get('img') or '')
                desc = info.get('detail') or info.get('shortDesc') or info.get('intro') or ''
                actor = info.get('actor') or info.get('stars') or ''
                director = info.get('director') or ''
                remarks = info.get('updateEP') or info.get('mediaForm') or remarks
                episodes = info.get('episodes') or info.get('programList') or info.get('datas') or []
                parts = []
                if isinstance(episodes, list) and episodes:
                    for ep in episodes:
                        if not isinstance(ep, dict):
                            continue
                        eid = str(ep.get('contId') or ep.get('pID') or ep.get('id') or '')
                        en = ep.get('name') or ep.get('title') or eid
                        if eid:
                            parts.append('%s$%s' % (en, eid))
                if not parts:
                    parts = ['正片$%s' % cid]
                froms = ['咪咕']
                urls = ['#'.join(parts)]
        except Exception as e:
            print('获取详情失败: %s' % e)
            froms = ['咪咕']
            urls = ['播放$%s' % cid]
        if isinstance(actor, list):
            actor = ' '.join([str(x) for x in actor[:8]])
        if isinstance(director, list):
            director = ' '.join([str(x) for x in director[:3]])
        return {'list': [{
            'vod_id': raw,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': str(remarks),
            'vod_actor': str(actor),
            'vod_director': str(director),
            'vod_content': str(desc).replace('\n\n', '\n').strip(),
            'vod_play_from': '$$$'.join(froms),
            'vod_play_url': '$$$'.join(urls),
        }]}

    def _ddcalcu(self, raw_url):
        try:
            qs = raw_url.split('?', 1)[1] if '?' in raw_url else ''
            params = {}
            for part in qs.split('&'):
                if '=' in part:
                    k, v = part.split('=', 1)
                    params[k] = v
            pu = params.get('puData') or ''
            if not pu:
                return raw_url
            chars = list(pu)
            result = []
            p = 0
            while 2 * p < len(chars):
                result.append(chars[len(chars) - p - 1])
                if p < len(chars) - p - 1:
                    result.append(pu[p])
                if p == 1:
                    result.append('e')
                if p == 2:
                    ts = params.get('timestamp') or ''
                    result.append(ts[6] if len(ts) > 6 else '0')
                if p == 3:
                    pid = params.get('ProgramID') or params.get('programId') or ''
                    result.append(pid[2] if len(pid) > 2 else '0')
                if p == 4:
                    ch = params.get('Channel_ID') or params.get('Channel_Id') or self.CHANNEL_ID
                    result.append(ch[-4] if len(ch) >= 4 else '0')
                p += 1
            return raw_url + '&ddCalcu=' + ''.join(result)
        except Exception:
            return raw_url

    def _playurl(self, cid, rate='3'):
        url = self.webApi + '/gateway/playurl/v3/play/playurl'
        params = {
            'contId': cid,
            'rateType': str(rate),
            'xh265': 'true',
            'chip': 'mgwww',
            'channelId': self.CHANNEL_ID,
        }
        data = self.fetch_json(url, params=params)
        body = data.get('body') or {}
        info = body.get('urlInfo') or {}
        raw = info.get('url') or ''
        if not raw:
            return ''
        return self._ddcalcu(raw)

    def playerContent(self, flag, id, vipFlags):
        header = self._headers()
        play_id = str(id or '').replace('live_', '', 1)
        if self.isVideoFormat(play_id) and play_id.startswith('http'):
            return {'parse': 0, 'url': play_id, 'header': header}
        try:
            url = self._playurl(play_id, '3')
            if url:
                return {'parse': 0, 'jx': '0', 'url': url, 'header': header}
        except Exception as e:
            print('获取播放内容失败: %s' % e)
        page = self.pcUrl + '/p/detail/' + play_id
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
