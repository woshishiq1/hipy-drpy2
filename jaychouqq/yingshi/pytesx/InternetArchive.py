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
        self.siteUrl = 'https://archive.org'
        self.searchApi = 'https://archive.org/advancedsearch.php'
        self.metaApi = 'https://archive.org/metadata/'
        self.userAgent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        self.channels = {
            'feature_films': {'name': '故事片', 'media': 'movies'},
            'moviesandfilms': {'name': '电影合集', 'media': 'movies'},
            'Film_Noir': {'name': '黑色电影', 'media': 'movies'},
            'SciFi_Horror': {'name': '科幻恐怖', 'media': 'movies'},
            'silent_films': {'name': '默片', 'media': 'movies'},
            'animationandcartoons': {'name': '动画', 'media': 'movies'},
            'classic_tv': {'name': '经典电视', 'media': 'movies'},
            'prelinger': {'name': 'Prelinger', 'media': 'movies'},
            'opensource_movies': {'name': '开源电影', 'media': 'movies'},
            'movie_trailers': {'name': '预告片', 'media': 'movies'},
            'TVNews': {'name': '电视新闻', 'media': 'movies'},
            'etree': {'name': '现场音乐', 'media': 'audio'},
            'audio_music': {'name': '音乐音频', 'media': 'audio'},
        }

    def getName(self):
        return 'Internet Archive'

    def init(self, extend=""):
        pass

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Accept': 'application/json, text/plain, */*',
            }
        try:
            if requests:
                resp = requests.get(url, headers=headers, params=params, timeout=20)
                resp.raise_for_status()
                return resp
            full = url
            if params:
                q = params if isinstance(params, str) else urllib.parse.urlencode(params, doseq=True)
                full += ('&' if '?' in url else '?') + q
            from urllib.request import Request, urlopen
            raw = urlopen(Request(full, headers=headers), timeout=20).read()

            class R:
                def __init__(self, raw):
                    self.content = raw
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
            return {}

    def _as_text(self, v):
        if v is None:
            return ''
        if isinstance(v, list):
            return ', '.join(str(x) for x in v if x)
        return str(v)

    def _thumb(self, ident):
        return '%s/services/img/%s' % (self.siteUrl, urllib.parse.quote(ident))

    def _map_doc(self, doc):
        ident = str(doc.get('identifier') or '')
        if not ident:
            return None
        return {
            'vod_id': ident,
            'vod_name': self._as_text(doc.get('title')) or ident,
            'vod_pic': self._thumb(ident),
            'vod_remarks': self._as_text(doc.get('year')) or self._as_text(doc.get('mediatype')),
        }

    def _ia_search(self, q, pg=1, rows=20):
        pg = int(pg or 1)
        params = [
            ('q', q),
            ('output', 'json'),
            ('rows', str(rows)),
            ('page', str(pg)),
            ('sort[]', 'downloads desc'),
        ]
        for f in ('identifier', 'title', 'year', 'creator', 'mediatype', 'downloads'):
            params.append(('fl[]', f))
        js = self.fetch_json(self.searchApi, params=params)
        resp = js.get('response') or {}
        return resp.get('docs') or [], int(resp.get('numFound') or 0)

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            docs, _ = self._ia_search('collection:(feature_films) AND mediatype:movies', 1, 20)
            for doc in docs:
                v = self._map_doc(doc)
                if v:
                    videos.append(v)
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        col = str(tid or 'feature_films')
        media = self.channels.get(col, {}).get('media', 'movies')
        videos = []
        total = 0
        try:
            q = 'collection:(%s) AND mediatype:%s' % (col, media)
            docs, total = self._ia_search(q, pg, 20)
            for doc in docs:
                v = self._map_doc(doc)
                if v:
                    videos.append(v)
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        pagecount = (total + 19) // 20 if total else (pg + 1 if videos else pg)
        return {
            'list': videos,
            'page': pg,
            'pagecount': min(pagecount, 500),
            'limit': 20,
            'total': total or len(videos),
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        total = 0
        try:
            q = '(%s) AND (mediatype:movies OR mediatype:audio)' % key
            docs, total = self._ia_search(q, pg, 20)
            for doc in docs:
                v = self._map_doc(doc)
                if v:
                    videos.append(v)
        except Exception as e:
            print('搜索失败: %s' % e)
        pagecount = (total + 19) // 20 if total else pg
        return {
            'list': videos,
            'page': pg,
            'pagecount': min(pagecount, 500),
            'limit': 20,
            'total': total or len(videos),
        }

    def _rank_file(self, f):
        name = str(f.get('name') or '').lower()
        fmt = str(f.get('format') or '').lower()
        if '.ia.' in name or name.endswith('_files.xml'):
            return -1
        if name.endswith(('.gif', '.jpg', '.jpeg', '.png')):
            return -1
        if name.endswith('.m3u8') or 'hls' in fmt:
            return 100
        if fmt in ('h.264', 'mpeg4', '512kb mpeg4'):
            return 90
        if name.endswith('.mp4'):
            return 80
        if name.endswith('.webm'):
            return 70
        if name.endswith('.ogv') or 'ogg video' in fmt:
            return 50
        if name.endswith('.mp3') or 'mp3' in fmt:
            return 40
        if name.endswith('.ogg') and 'vorbis' in fmt:
            return 30
        return -1

    def detailContent(self, ids):
        ident = str((ids or [''])[0]).strip('/')
        try:
            js = self.fetch_json(self.metaApi + urllib.parse.quote(ident))
            meta = js.get('metadata') or {}
            files = js.get('files') or []
            cands = []
            for f in files:
                sc = self._rank_file(f)
                if sc > 0:
                    cands.append((sc, f))
            cands.sort(key=lambda x: x[0], reverse=True)
            urls = []
            seen = set()
            for _, f in cands:
                name = f.get('name')
                if not name or name in seen:
                    continue
                seen.add(name)
                label = f.get('format') or name
                if f.get('height'):
                    label = '%s %sp' % (label, f.get('height'))
                urls.append('%s$%s|%s' % (label, ident, urllib.parse.quote(name, safe='')))
                if len(urls) >= 12:
                    break
            if not urls:
                urls.append('页面$%s' % ident)
            return {
                'list': [{
                    'vod_id': ident,
                    'vod_name': self._as_text(meta.get('title')) or ident,
                    'vod_pic': self._thumb(ident),
                    'vod_year': self._as_text(meta.get('year') or meta.get('date')),
                    'vod_actor': self._as_text(meta.get('creator')),
                    'vod_director': self._as_text(meta.get('producer')),
                    'vod_content': self._as_text(meta.get('description'))[:600],
                    'vod_remarks': self._as_text(meta.get('mediatype')),
                    'vod_play_from': 'Internet Archive',
                    'vod_play_url': '#'.join(urls),
                }]
            }
        except Exception as e:
            print('获取详情失败: %s' % e)
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        header = {'User-Agent': self.userAgent, 'Referer': self.siteUrl + '/'}
        play_id = str(id or '')
        if play_id.startswith('http'):
            return {'parse': 0 if self.isVideoFormat(play_id) else 1, 'url': play_id, 'header': header}
        parts = play_id.split('|', 1)
        ident = parts[0]
        fname = urllib.parse.unquote(parts[1]) if len(parts) > 1 else ''
        try:
            if fname:
                url = '%s/download/%s/%s' % (
                    self.siteUrl,
                    urllib.parse.quote(ident),
                    '/'.join(urllib.parse.quote(p) for p in fname.split('/')),
                )
                return {'parse': 0, 'url': url, 'header': header}
            js = self.fetch_json(self.metaApi + urllib.parse.quote(ident))
            best, best_sc = None, -1
            for f in js.get('files') or []:
                sc = self._rank_file(f)
                if sc > best_sc:
                    best_sc, best = sc, f
            if best and best.get('name'):
                url = '%s/download/%s/%s' % (
                    self.siteUrl,
                    urllib.parse.quote(ident),
                    '/'.join(urllib.parse.quote(p) for p in str(best['name']).split('/')),
                )
                return {'parse': 0, 'url': url, 'header': header}
        except Exception as e:
            print('获取播放内容失败: %s' % e)
        return {
            'parse': 1,
            'jx': '1',
            'url': '%s/details/%s' % (self.siteUrl, urllib.parse.quote(ident)),
            'header': header,
        }

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        for fmt in ('.m3u8', '.mp4', '.mp3', '.ogv', '.webm', '.ogg'):
            if fmt in u:
                return True
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None


if __name__ == '__main__':
    spider = Spider()
    print(json.dumps(spider.homeContent(True), ensure_ascii=False, indent=2))
