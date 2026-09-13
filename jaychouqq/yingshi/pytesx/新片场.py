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
        self.siteUrl = 'https://www.xinpianchang.com'
        self.mHost = 'https://m.xinpianchang.com'
        self.mediaApi = 'https://mod-api.xinpianchang.com/mod/api/v2/media/'
        self.appKey = '61a2f329348b3bf77'
        self.buildId = ''
        self.userAgent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        self.channels = {
            '9999': {'name': '全球精选'},
            '1': {'name': '广告片'},
            '16': {'name': '宣传片'},
            '332': {'name': '竖屏广告'},
            '329': {'name': 'AIGC'},
            '31': {'name': '剧情短片'},
            '49': {'name': '纪录片'},
            '61': {'name': '摄影'},
            '142': {'name': '剪辑二创'},
            '347': {'name': '三维CG'},
            '69': {'name': '二维动画'},
            '27': {'name': '音乐声音'},
            '76': {'name': '视觉探索'},
            '29': {'name': '短视频'},
            '315': {'name': '校园作品'},
            '144': {'name': '学习分享'},
        }

    def getName(self):
        return '新片场'

    def init(self, extend=""):
        self._ensure_build()

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

    def _ensure_build(self):
        if self.buildId:
            return self.buildId
        html = ''
        resp = self.fetch(self.mHost + '/')
        if resp:
            html = getattr(resp, 'text', '') or ''
        m = re.search(r'"buildId"\s*:\s*"([^"]+)"', html)
        self.buildId = m.group(1) if m else 'gidgYqXpPYCSNYnalPEaP'
        return self.buildId

    def _next(self, path, params=None):
        bid = self._ensure_build()
        if not path.endswith('.json'):
            path = path + '.json'
        if not path.startswith('/'):
            path = '/' + path
        url = '%s/_next/data/%s%s' % (self.siteUrl, bid, path)
        return self.fetch_json(url, params=params) or {}

    def _fmt_dur(self, sec):
        try:
            n = int(sec or 0)
        except Exception:
            return ''
        if n <= 0:
            return ''
        return '%d:%02d' % (n // 60, n % 60)

    def _map_article(self, item):
        if not item:
            return None
        aid = str(item.get('id') or item.get('article_id') or '')
        mid = str(item.get('media_id') or item.get('video_library_id') or '')
        if not aid and not mid:
            return None
        cover = item.get('cover') or item.get('cover_url') or ''
        count = item.get('count') or {}
        remarks = self._fmt_dur(item.get('duration'))
        if not remarks and count.get('count_like'):
            remarks = '%s赞' % count.get('count_like')
        return {
            'vod_id': aid + (('|' + mid) if mid else ''),
            'vod_name': item.get('title') or aid or mid,
            'vod_pic': cover,
            'vod_remarks': remarks,
        }

    def _pick_list(self, js):
        pp = (js or {}).get('pageProps') or js or {}
        disc = (pp.get('discoverArticleData') or {}).get('list')
        if disc:
            return disc
        search = (pp.get('searchData') or {}).get('list')
        if search:
            return search
        rec = pp.get('editorRecommendData') or {}
        sections = rec.get('section') or []
        if sections:
            return sections[0].get('articles') or []
        return []

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            js = self._next('/index.json')
            for item in self._pick_list(js)[:24]:
                v = self._map_article(item)
                if v:
                    videos.append(v)
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        cate = str(tid or '1')
        try:
            js = self._next('/discover/article-%s-0.json' % cate)
            for item in self._pick_list(js):
                v = self._map_article(item)
                if v:
                    videos.append(v)
            if pg > 1 and not videos:
                raw = self.fetch_json(
                    self.siteUrl + '/v2/search',
                    {
                        'allow_download': 0,
                        'cate_id': cate,
                        'duration': 'all',
                        'page': pg,
                        'per_page': 20,
                        'resolution': 'all',
                        'result_profile': 'discover_card',
                        'screen_type': 0,
                        'sort': 'score',
                        'type': 'channel',
                    }
                )
                data = raw.get('data') or raw
                for item in data.get('list') or data.get('articles') or []:
                    v = self._map_article(item)
                    if v:
                        videos.append(v)
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 20 else pg,
            'limit': 20,
            'total': 9999,
        }

    def detailContent(self, ids):
        raw = str((ids or [''])[0])
        parts = raw.split('|')
        aid = re.sub(r'^a', '', parts[0] or '', flags=re.I)
        mid = parts[1] if len(parts) > 1 else ''
        app_key = self.appKey
        title = aid or mid
        cover = ''
        content = ''
        actor = ''
        try:
            if re.match(r'^\d+$', aid):
                js = self._next('/a%s.json' % aid)
                det = ((js.get('pageProps') or {}).get('detail') or {})
                title = det.get('title') or title
                cover = det.get('cover') or ''
                content = det.get('content') or det.get('desc') or det.get('description') or ''
                if isinstance(content, str):
                    content = re.sub(r'<[^>]+>', '', content)[:400]
                author = det.get('author') or {}
                userinfo = author.get('userinfo') if isinstance(author, dict) else {}
                actor = (userinfo or {}).get('username') or ''
                video = det.get('video') or {}
                if video.get('vid'):
                    mid = video.get('vid')
                if video.get('appKey'):
                    app_key = video.get('appKey')
                if not mid:
                    mid = det.get('video_library_id') or mid
        except Exception as e:
            print('获取详情失败: %s' % e)
        play_id = mid or aid
        if app_key and app_key != self.appKey:
            play_id = '%s|%s' % (play_id, app_key)
        return {
            'list': [{
                'vod_id': raw,
                'vod_name': title,
                'vod_pic': cover,
                'vod_actor': actor,
                'vod_content': content,
                'vod_play_from': '新片场',
                'vod_play_url': '正片$%s' % play_id,
            }]
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        try:
            m = re.search(r'a?(\d{5,})', str(key or ''), re.I)
            if m and pg == 1:
                js = self._next('/a%s.json' % m.group(1))
                det = ((js.get('pageProps') or {}).get('detail') or {})
                if det.get('id') or det.get('title'):
                    v = self._map_article({
                        'id': det.get('id') or m.group(1),
                        'title': det.get('title'),
                        'cover': det.get('cover'),
                        'duration': det.get('duration'),
                        'media_id': ((det.get('video') or {}).get('vid')) or det.get('video_library_id'),
                    })
                    if v:
                        return {'list': [v], 'page': 1, 'pagecount': 1, 'limit': 20, 'total': 1}
            js = self._next('/search.json', {'keyword': key, 'kw': key})
            for item in self._pick_list(js):
                v = self._map_article(item)
                if v:
                    videos.append(v)
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 20 else pg,
            'limit': 20,
            'total': len(videos),
        }

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
            'Origin': self.siteUrl,
            'Range': 'bytes=0-',
        }
        play_id = str(id or '')
        if play_id.startswith('http') and self.isVideoFormat(play_id):
            return {'parse': 0, 'url': play_id, 'header': header}
        parts = play_id.split('|')
        mid = parts[0]
        app_key = parts[1] if len(parts) > 1 else self.appKey
        try:
            js = self.fetch_json(
                self.mediaApi + urllib.parse.quote(mid),
                {'appKey': app_key, 'extend': 'userInfo,userStatus'}
            )
            data = js.get('data') or js
            url = self._pick_media(data)
            if url:
                return {'parse': 0 if self.isVideoFormat(url) else 1, 'url': url, 'header': header}
        except Exception as e:
            print('获取播放内容失败: %s' % e)
        return {
            'parse': 1,
            'jx': '1',
            'url': self.siteUrl + ('/a%s' % mid if str(mid).isdigit() else '/'),
            'header': header,
        }

    def _pick_media(self, data):
        res = (data or {}).get('resource') or {}
        hls = res.get('hls') or {}
        if isinstance(hls, dict) and hls.get('url'):
            return hls.get('url')
        best = None
        for it in res.get('progressive') or []:
            if not it or not it.get('url'):
                continue
            if not best or int(it.get('height') or 0) > int(best.get('height') or 0):
                best = it
        if best:
            return best.get('url') or best.get('backupUrl')
        dash = res.get('dash') or {}
        if isinstance(dash, dict):
            return dash.get('url') or ''
        return ''

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        for fmt in ('.m3u8', '.mp4', '.mpd', '.webm'):
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
