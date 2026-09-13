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
    """时光网 https://live.mtime.com/home  + api-m.mtime.cn"""

    def __init__(self):
        self.siteUrl = 'https://live.mtime.com'
        self.webUrl = 'https://www.mtime.com'
        self.api = 'https://api-m.mtime.cn'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            'hot': {'name': '正在热映'},
            'coming': {'name': '即将上映'},
            'ticket': {'name': '正在售票'},
            'trailer': {'name': '预告片'},
        }

    def getName(self):
        return '时光网'

    def init(self, extend=""):
        pass

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.webUrl + '/',
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

    def fetch_text(self, url):
        resp = self.fetch(url)
        return getattr(resp, 'text', '') if resp else ''

    def _abs(self, u):
        if not u:
            return ''
        if str(u).startswith('//'):
            return 'https:' + u
        return u.replace('http://', 'https://')

    def _map_movie(self, item):
        mid = str(item.get('movieId') or item.get('id') or item.get('MovieId') or '')
        name = item.get('title') or item.get('tCn') or item.get('titleCn') or item.get('name') or mid
        pic = item.get('image') or item.get('img') or item.get('poster') or item.get('movieCover') or ''
        if isinstance(pic, dict):
            pic = pic.get('url') or pic.get('src') or ''
        remarks = item.get('rYear') or item.get('ratingFinal') or item.get('type') or item.get('releaseDate') or ''
        if not mid:
            return None
        return {
            'vod_id': mid,
            'vod_name': name,
            'vod_pic': self._abs(pic),
            'vod_remarks': str(remarks),
        }

    def _walk(self, obj, acc=None):
        if acc is None:
            acc = []
        if isinstance(obj, dict):
            if obj.get('movieId') or (obj.get('id') and (obj.get('title') or obj.get('tCn') or obj.get('titleCn'))):
                acc.append(obj)
            for v in obj.values():
                self._walk(v, acc)
        elif isinstance(obj, list):
            for v in obj:
                self._walk(v, acc)
        return acc

    def _hot(self):
        videos = []
        for path in (
            '/Showtime/LocationMovies.api?locationId=292',
            '/PageSubArea/HotPlayMovies.api?locationId=292',
            '/Showtime/HotPlayMovies.api?locationId=292',
        ):
            data = self.fetch_json(self.api + path)
            for it in self._walk(data):
                v = self._map_movie(it)
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

    def _coming(self):
        videos = []
        data = self.fetch_json(self.api + '/Movie/MovieComingNew.api?locationId=292')
        for it in self._walk(data):
            v = self._map_movie(it)
            if v:
                videos.append(v)
        seen, out = set(), []
        for v in videos:
            if v['vod_id'] in seen:
                continue
            seen.add(v['vod_id'])
            out.append(v)
        return out

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            videos = self._hot()
            if not videos:
                html = self.fetch_text(self.siteUrl + '/home')
                for m in re.finditer(r'movieId["\']?\s*[:=]\s*["\']?(\d+)', html or ''):
                    videos.append({'vod_id': m.group(1), 'vod_name': m.group(1), 'vod_pic': '', 'vod_remarks': ''})
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            tid = str(tid or 'hot')
            if tid in ('hot', 'ticket'):
                videos = self._hot()
            elif tid == 'coming':
                videos = self._coming()
            else:
                videos = self._hot()
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
                self.api + '/Search/Keyword.api?keyword=' + q,
                self.webUrl + '/search/?q=' + q,
            ):
                if url.startswith(self.api):
                    data = self.fetch_json(url)
                    for it in self._walk(data):
                        v = self._map_movie(it)
                        if v:
                            videos.append(v)
                else:
                    html = self.fetch_text(url)
                    for m in re.finditer(r'/movie/(\d+)/[^"]*"[^>]*>([^<]{2,40})', html or ''):
                        videos.append({
                            'vod_id': m.group(1),
                            'vod_name': m.group(2).strip(),
                            'vod_pic': '',
                            'vod_remarks': '',
                        })
                if videos:
                    break
        except Exception as e:
            print('搜索失败: %s' % e)
        seen, out = set(), []
        for v in videos:
            if v['vod_id'] in seen:
                continue
            seen.add(v['vod_id'])
            out.append(v)
        return {
            'list': out,
            'page': pg,
            'pagecount': pg,
            'limit': 24,
            'total': len(out),
        }

    def _videos_of(self, mid, pg=1):
        data = self.fetch_json(self.api + '/Movie/Video.api', params={'pageIndex': str(pg), 'movieId': mid})
        return data.get('videoList') or []

    def detailContent(self, ids):
        mid = str((ids or [''])[0])
        name, pic, desc, remarks, actor, director = mid, '', '', '', '', ''
        froms, urls = [], []
        try:
            info = self.fetch_json(self.api + '/movie/detail.api', params={'movieId': mid})
            movie = info.get('data') or info.get('movie') or info
            if isinstance(movie, dict):
                name = movie.get('titleCn') or movie.get('title') or movie.get('tCn') or name
                pic = self._abs(movie.get('image') or movie.get('img') or '')
                desc = movie.get('story') or movie.get('content') or movie.get('intro') or ''
                director = movie.get('director') or ''
                actor = movie.get('actor') or movie.get('actors') or ''
                remarks = movie.get('releaseDate') or movie.get('rYear') or ''
            if isinstance(director, list):
                director = ' '.join([str(x.get('name') if isinstance(x, dict) else x) for x in director[:3]])
            if isinstance(actor, list):
                actor = ' '.join([str(x.get('name') if isinstance(x, dict) else x) for x in actor[:8]])
            parts = []
            for ep in self._videos_of(mid, 1):
                title = ep.get('title') or '预告片'
                play = ep.get('hightUrl') or ep.get('highUrl') or ep.get('url') or ''
                if play:
                    parts.append('%s$%s' % (title, play))
            if parts:
                froms.append('时光预告')
                urls.append('#'.join(parts))
        except Exception as e:
            print('获取详情失败: %s' % e)
        if not urls:
            froms = ['时光网']
            urls = ['详情$https://movie.mtime.com/%s/' % mid]
        return {'list': [{
            'vod_id': mid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': str(remarks),
            'vod_actor': str(actor),
            'vod_director': str(director),
            'vod_content': str(desc).replace('\n\n', '\n').strip(),
            'vod_play_from': '$$$'.join(froms),
            'vod_play_url': '$$$'.join(urls),
        }]}

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.webUrl + '/',
            'Origin': self.webUrl,
        }
        play = str(id or '')
        if self.isVideoFormat(play) and play.startswith('http'):
            return {'parse': 0, 'jx': '0', 'url': play, 'header': header}
        return {'parse': 1, 'jx': '1', 'url': play if play.startswith('http') else self.webUrl + '/', 'header': header}

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
