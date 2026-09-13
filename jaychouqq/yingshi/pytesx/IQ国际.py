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
        self.siteUrl = 'https://www.iq.com'
        self.pcwApi = 'https://pcw-api.iq.com'
        self.iqiyiPcw = 'https://pcw-api.iqiyi.com'
        self.searchApi = 'https://intl.iqiyi.com/w/search'
        self.userAgent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        self.channels = {
            '2': {'name': 'Drama', 'channel_id': '2'},
            '1': {'name': 'Movie', 'channel_id': '1'},
            '4': {'name': 'Variety', 'channel_id': '6'},
            '3': {'name': 'Anime', 'channel_id': '4'},
            '15': {'name': 'Kids', 'channel_id': '15'},
        }

    def getName(self):
        return 'iQIYI International'

    def init(self, extend=""):
        pass

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Origin': self.siteUrl,
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8',
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

    def _ok(self, js):
        code = str((js or {}).get('code') or '')
        return code in ('A00000', '0', '00', '')

    def _list_from(self, js):
        d = (js or {}).get('data') or js or {}
        if isinstance(d, list):
            return d
        for k in ('list', 'albumList', 'epg', 'docs', 'videoList', 'album'):
            v = d.get(k) if isinstance(d, dict) else None
            if isinstance(v, list):
                return v
            if isinstance(v, dict) and isinstance(v.get('list'), list):
                return v.get('list')
        return []

    def _id(self, item):
        return str(
            item.get('albumQipuId')
            or item.get('qipuId')
            or item.get('albumId')
            or item.get('tvId')
            or item.get('id')
            or ''
        )

    def _map(self, item):
        vid = self._id(item)
        if not vid:
            return None
        title = item.get('name') or item.get('title') or item.get('albumName') or item.get('shortDisplayName') or vid
        pic = item.get('imageUrl') or item.get('image') or item.get('poster') or item.get('albumPic') or ''
        if isinstance(pic, dict):
            pic = pic.get('url') or ''
        remarks = item.get('latestOrder') or item.get('updateInfo') or item.get('focus') or item.get('score') or ''
        if remarks and str(remarks).isdigit():
            remarks = 'EP%s' % remarks
        return {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': pic,
            'vod_remarks': str(remarks),
            'vod_year': str(item.get('period') or item.get('year') or '')[:4],
        }

    def _album_list(self, channel_id, page=1, size=30):
        videos = []
        attempts = [
            (self.pcwApi + '/api/v2/albumListSource/%s' % channel_id, {
                'pageNum': str(page),
                'pageSize': str(size),
                'dataType': '1',
            }),
            (self.pcwApi + '/api/albumList/chnl/%s' % channel_id, {
                'pageNo': str(page),
                'pageSize': str(size),
                'dataType': '1',
            }),
            (self.iqiyiPcw + '/search/recommend/list', {
                'channel_id': str(channel_id),
                'data_type': '1',
                'mode': '11',
                'page_id': str(page),
                'ret_num': str(size),
                'session': '',
            }),
        ]
        for url, params in attempts:
            js = self.fetch_json(url, params)
            if not js:
                continue
            for item in self._list_from(js):
                v = self._map(item)
                if v:
                    videos.append(v)
            if videos:
                break
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            for cid in ('2', '1', '3', '4'):
                videos.extend(self._album_list(self.channels[cid]['channel_id'], 1, 8)[:6])
                if len(videos) >= 24:
                    break
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        channel_id = self.channels.get(str(tid), {}).get('channel_id', '2')
        videos = []
        try:
            videos = self._album_list(channel_id, pg, 36)
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 20 else pg,
            'limit': 36,
            'total': 9999,
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        try:
            for url, params in (
                (self.pcwApi + '/api/search/recommend/list', {
                    'key': key, 'pageNum': str(pg), 'pageSize': '24', 'dataType': '1'
                }),
                ('https://search.video.iqiyi.com/o', {
                    'if': 'html5', 'key': key, 'pageNum': str(pg), 'pageSize': '24'
                }),
            ):
                js = self.fetch_json(url, params)
                rows = self._list_from(js)
                if not rows and isinstance(js.get('data'), dict):
                    rows = js['data'].get('docinfos') or []
                for item in rows:
                    album = item.get('albumDocInfo') or item
                    v = self._map(album)
                    if v:
                        videos.append(v)
                if videos:
                    break
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 20 else pg,
            'limit': 24,
            'total': len(videos),
        }

    def detailContent(self, ids):
        album_id = str((ids or [''])[0])
        name, pic, desc, actor, director, year, remarks = album_id, '', '', '', '', '', ''
        episodes = []
        try:
            js = self.fetch_json(self.pcwApi + '/api/v2/episodeListSource/' + album_id, {
                'pageNo': '1',
                'pageSize': '80',
            })
            data = js.get('data') or {}
            episodes = data.get('epg') or data.get('list') or self._list_from(js)
            if not episodes:
                js = self.fetch_json(self.iqiyiPcw + '/albums/album/avlistinfo', {
                    'aid': album_id, 'page': '1', 'size': '50'
                })
                episodes = ((js.get('data') or {}).get('epsodelist')) or []

            base = self.fetch_json(self.pcwApi + '/api/v1/album/' + album_id)
            info = base.get('data') or {}
            if not info:
                base = self.fetch_json(self.iqiyiPcw + '/video/video/baseinfo/' + album_id)
                info = base.get('data') or {}
            name = info.get('name') or info.get('albumName') or info.get('title') or name
            pic = info.get('imageUrl') or info.get('albumImageUrl') or pic
            desc = info.get('description') or info.get('desc') or ''
            year = str(info.get('period') or info.get('year') or '')[:4]
            people = info.get('people') or {}
            if isinstance(people, dict):
                director = ' '.join([d.get('name', '') for d in (people.get('director') or []) if d.get('name')])
                actor = ' '.join([a.get('name', '') for a in (people.get('main_charactor') or people.get('actor') or []) if a.get('name')])
            if not episodes and info.get('playUrl'):
                episodes = [{'name': name, 'playUrl': info.get('playUrl'), 'qipuId': album_id}]
        except Exception as e:
            print('获取详情失败: %s' % e)

        parts = []
        for i, ep in enumerate(episodes, 1):
            ep_name = ep.get('shortTitle') or ep.get('name') or ep.get('subtitle') or ('EP%s' % i)
            play = ep.get('playUrl') or ''
            qid = ep.get('qipuId') or ep.get('tvId') or ep.get('albumQipuId') or ''
            if play:
                play = play.replace('www.iqiyi.com', 'www.iq.com').replace('m.iqiyi.com', 'www.iq.com')
                if 'iq.com' not in play and play.startswith('http'):
                    play = play
            elif qid:
                play = self.siteUrl + '/play/' + str(qid)
            else:
                continue
            parts.append('%s$%s' % (ep_name, play))
        if not parts:
            parts.append('Play$%s/play/%s' % (self.siteUrl, album_id))
        remarks = remarks or ('%s EP' % len(parts) if len(parts) > 1 else 'Movie')
        return {
            'list': [{
                'vod_id': album_id,
                'vod_name': name,
                'vod_pic': pic,
                'vod_year': year,
                'vod_actor': actor,
                'vod_director': director,
                'vod_remarks': remarks,
                'vod_content': (desc or '').replace('\n\n', '\n').strip(),
                'vod_play_from': 'iQIYI',
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
        if play_url.startswith('http'):
            play_url = play_url.replace('www.iqiyi.com', 'www.iq.com').replace('m.iqiyi.com', 'www.iq.com')
        if self.isVideoFormat(play_url):
            return {'parse': 0, 'url': play_url, 'header': header}
        return {'parse': 1, 'jx': '1', 'url': play_url, 'header': header}

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
