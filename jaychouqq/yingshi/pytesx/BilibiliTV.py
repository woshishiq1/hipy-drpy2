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
        self.siteUrl = 'https://www.bilibili.tv'
        self.api = 'https://api.bilibili.tv/intl/gateway'
        self.apiAlt = 'https://api.biliintl.com/intl/gateway'
        self.locale = 'en_US'
        self.userAgent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        # type: 1 anime, 2 movie, 3 documentary, 4 variety/drama-ish
        self.channels = {
            '1': {'name': 'Anime', 'type': '1'},
            '2': {'name': 'Movie', 'type': '2'},
            '5': {'name': 'Drama', 'type': '5'},
            '3': {'name': 'Documentary', 'type': '3'},
            '7': {'name': 'Variety', 'type': '7'},
        }

    def getName(self):
        return 'Bilibili TV'

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

    def fetch_text(self, url, params=None):
        resp = self.fetch(url, params=params)
        return getattr(resp, 'text', '') if resp else ''

    def _ok(self, js):
        return str((js or {}).get('code', '')) in ('0', '00', '')

    def _data(self, js):
        d = (js or {}).get('data') or js or {}
        return d if isinstance(d, dict) else {}

    def _abs(self, u):
        if not u:
            return ''
        if u.startswith('//'):
            return 'https:' + u
        return u

    def _map_season(self, item):
        sid = str(
            item.get('season_id')
            or item.get('seasonId')
            or item.get('ssid')
            or item.get('id')
            or ''
        )
        if not sid:
            return None
        title = item.get('title') or item.get('org_title') or item.get('name') or sid
        pic = item.get('cover') or item.get('horizontal_cover') or item.get('poster') or item.get('pic') or ''
        remarks = item.get('index_show') or item.get('update_info') or item.get('subtitle') or item.get('score') or ''
        if isinstance(item.get('rating'), dict):
            remarks = remarks or str(item['rating'].get('score') or '')
        return {
            'vod_id': sid,
            'vod_name': title,
            'vod_pic': self._abs(pic),
            'vod_remarks': str(remarks),
            'vod_year': str(item.get('year') or item.get('publish_date') or '')[:4],
        }

    def _walk_seasons(self, obj, acc=None):
        if acc is None:
            acc = []
        if isinstance(obj, dict):
            if obj.get('season_id') or obj.get('seasonId') or (
                obj.get('title') and (obj.get('cover') or obj.get('horizontal_cover'))
            ):
                v = self._map_season(obj)
                if v:
                    acc.append(v)
            for val in obj.values():
                self._walk_seasons(val, acc)
        elif isinstance(obj, list):
            for val in obj:
                self._walk_seasons(val, acc)
        return acc

    def _unique(self, videos):
        out, seen = [], set()
        for v in videos:
            if not v or v['vod_id'] in seen:
                continue
            seen.add(v['vod_id'])
            out.append(v)
        return out

    def _api_get(self, path, params=None):
        params = dict(params or {})
        params.setdefault('s_locale', self.locale)
        params.setdefault('platform', 'web')
        for base in (self.api, self.apiAlt):
            js = self.fetch_json(base + path, params)
            if js and (self._ok(js) or js.get('data')):
                return js
        return {}

    def _index(self, season_type, page=1, pagesize=24):
        videos = []
        attempts = [
            ('/web/v2/ogv/index', {
                'type': str(season_type),
                'page': str(page),
                'pagesize': str(pagesize),
                'order': '4',
            }),
            ('/web/v2/ogv/season/index', {
                'season_type': str(season_type),
                'type': '1',
                'page': str(page),
                'pagesize': str(pagesize),
                'order': '4',
            }),
        ]
        for path, params in attempts:
            js = self._api_get(path, params)
            rows = self._walk_seasons(js)
            if rows:
                videos = rows
                break
        if not videos:
            # homepage cards fallback
            html = self.fetch_text(self.siteUrl + '/en')
            for m in re.finditer(r'/play/(\d+)', html or ''):
                sid = m.group(1)
                videos.append({'vod_id': sid, 'vod_name': sid, 'vod_pic': '', 'vod_remarks': ''})
            videos = self._unique(videos)
        return self._unique(videos)

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            for tid in ('1', '2', '5'):
                videos.extend(self._index(self.channels[tid]['type'], 1, 8)[:8])
                if len(videos) >= 24:
                    break
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': self._unique(videos)[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            stype = self.channels.get(str(tid), {}).get('type', '1')
            videos = self._index(stype, pg, 24)
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
            for path in ('/web/v2/search', '/web/search', '/web/v2/ogv/search'):
                js = self._api_get(path, {
                    'keyword': key,
                    'page': str(pg),
                    'pagesize': '24',
                })
                videos = self._unique(self._walk_seasons(js))
                if videos:
                    break
            if not videos:
                html = self.fetch_text(self.siteUrl + '/en/search-result?q=' + urllib.parse.quote(key))
                for m in re.finditer(r'/play/(\d+)', html or ''):
                    videos.append({
                        'vod_id': m.group(1),
                        'vod_name': m.group(1),
                        'vod_pic': '',
                        'vod_remarks': '',
                    })
                videos = self._unique(videos)
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 12 else pg,
            'limit': 24,
            'total': len(videos),
        }

    def _episodes(self, season_id):
        eps = []
        for path, params in (
            ('/web/view/ogv_collection', {'season_id': season_id}),
            ('/web/v2/ogv/play/episodes', {'season_id': season_id, 'platform': 'web'}),
            ('/web/v2/ogv/view/app/season', {'season_id': season_id}),
        ):
            js = self._api_get(path, params)
            data = self._data(js)
            raw = data.get('episodes') or data.get('ep_list') or []
            if not raw:
                modules = data.get('modules') or data.get('sections') or []
                for mod in modules if isinstance(modules, list) else []:
                    raw.extend(mod.get('episodes') or mod.get('data') or [])
            if raw:
                eps = raw
                meta = data.get('season') or data.get('media') or data
                return eps, meta
        return [], {}

    def detailContent(self, ids):
        sid = str((ids or [''])[0]).split('/')[0]
        name, pic, desc, actor, director, year, remarks = sid, '', '', '', '', '', ''
        parts = []
        try:
            eps, meta = self._episodes(sid)
            name = meta.get('title') or meta.get('org_title') or name
            pic = self._abs(meta.get('cover') or meta.get('horizontal_cover') or meta.get('poster') or '')
            desc = meta.get('evaluate') or meta.get('description') or meta.get('desc') or ''
            year = str(meta.get('year') or meta.get('publish_date') or '')[:4]
            actor = meta.get('actors') or meta.get('actor') or ''
            if isinstance(actor, list):
                actor = ' '.join([a.get('name', a) if isinstance(a, dict) else str(a) for a in actor[:8]])
            director = meta.get('staff') or meta.get('director') or ''
            if isinstance(director, list):
                director = ' '.join([d.get('name', d) if isinstance(d, dict) else str(d) for d in director[:3]])
            remarks = meta.get('index_show') or meta.get('update_info') or ''

            for i, ep in enumerate(eps, 1):
                epid = str(ep.get('ep_id') or ep.get('id') or ep.get('episode_id') or '')
                if not epid:
                    continue
                ep_name = ep.get('long_title') or ep.get('title') or ep.get('index_title') or ('EP%s' % i)
                if str(ep.get('title', '')).isdigit() and ep.get('long_title'):
                    ep_name = 'E%s %s' % (ep.get('title'), ep.get('long_title'))
                play = '%s/en/play/%s/%s' % (self.siteUrl, sid, epid)
                parts.append('%s$%s' % (ep_name, play))
                if not pic:
                    pic = self._abs(ep.get('cover') or '')
        except Exception as e:
            print('获取详情失败: %s' % e)
        if not parts:
            parts.append('Play$%s/en/play/%s' % (self.siteUrl, sid))
        return {
            'list': [{
                'vod_id': sid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_year': year,
                'vod_actor': actor,
                'vod_director': director,
                'vod_remarks': remarks or ('%s EP' % len(parts) if len(parts) > 1 else 'Movie'),
                'vod_content': (desc or '').replace('\n\n', '\n').strip(),
                'vod_play_from': 'BilibiliTV',
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

        # try official intl playurl
        epid = ''
        m = re.search(r'/play/\d+/(\d+)', play_url)
        if m:
            epid = m.group(1)
        elif play_url.isdigit():
            epid = play_url
        if epid:
            js = self._api_get('/web/playurl', {
                'ep_id': epid,
                'device': 'wap',
                'qn': '64',
                'tf': '0',
            })
            data = self._data(js)
            play = (
                data.get('playurl')
                or ((data.get('video') or [{}])[0] if isinstance(data.get('video'), list) else {})
            )
            url = ''
            if isinstance(play, str):
                url = play
            elif isinstance(play, dict):
                url = play.get('url') or play.get('video_resource', [{}])
                if isinstance(url, list) and url:
                    url = url[0].get('url') or url[0].get('backup_url', [''])[0]
            if not url:
                vr = data.get('playurl', {})
                if isinstance(vr, dict):
                    res = vr.get('video_resource') or vr.get('audio_resource') or []
                    if res:
                        url = res[0].get('url') or ''
            if url and self.isVideoFormat(url):
                return {'parse': 0, 'url': url, 'header': header}

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
