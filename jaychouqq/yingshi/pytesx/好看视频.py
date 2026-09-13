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
        self.siteUrl = 'https://haokan.baidu.com'
        self.userAgent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        self.channels = {
            'yingshi_new': {'name': '影视'},
            'yule': {'name': '娱乐'},
            'music': {'name': '音乐'},
            'game': {'name': '游戏'},
            'shougong': {'name': '生活'},
            'dongxiao': {'name': '搞笑'},
            'junshi': {'name': '军事'},
            'meishi': {'name': '美食'},
            'tiyu': {'name': '体育'},
            'keji': {'name': '科技'},
            'qiche': {'name': '汽车'},
            'shishang': {'name': '时尚'},
            'qinzi': {'name': '亲子'},
            'wenhua': {'name': '文化'},
        }

    def getName(self):
        return '好看视频'

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

    def _fmt_dur(self, sec):
        try:
            n = int(sec or 0)
        except Exception:
            return ''
        if n <= 0:
            return ''
        return '%d:%02d' % (n // 60, n % 60)

    def _map(self, item):
        if not item:
            return None
        vid = str(item.get('vid') or item.get('id') or item.get('content_id') or '')
        if not vid:
            return None
        title = item.get('title') or item.get('name') or vid
        pic = item.get('poster') or item.get('cover_src') or item.get('cover') or item.get('poster_big') or ''
        if isinstance(pic, dict):
            pic = pic.get('url') or pic.get('src') or ''
        remarks = self._fmt_dur(item.get('duration') or item.get('time_length'))
        if not remarks:
            remarks = item.get('author') or item.get('source_name') or ''
        return {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': pic,
            'vod_remarks': remarks,
        }

    def _pick_list(self, js):
        d = (js or {}).get('data') or js or {}
        for key in ('list', 'response', 'videos', 'video_list', 'feed', 'rec'):
            arr = d.get(key) if isinstance(d, dict) else None
            if isinstance(arr, list):
                return arr
            if isinstance(arr, dict) and isinstance(arr.get('list'), list):
                return arr.get('list')
        if isinstance(d, list):
            return d
        return []

    def _feed(self, tab, pg=1):
        params = {
            'tab': tab or 'yingshi_new',
            'act': 'pcFeed',
            'pd': 'pc',
            'num': '24',
        }
        if int(pg or 1) > 1:
            params['page'] = str(pg)
        js = self.fetch_json(self.siteUrl + '/web/video/feed', params)
        videos = []
        for item in self._pick_list(js):
            video = item.get('video') if isinstance(item, dict) and isinstance(item.get('video'), dict) else item
            v = self._map(video)
            if v:
                videos.append(v)
        if videos:
            return videos
        js2 = self.fetch_json(self.siteUrl + '/videoui/api/videorec', {
            'tab': tab or 'recommend',
            'pd': 'pc',
            'num': '24',
        })
        for item in self._pick_list(js2):
            v = self._map(item)
            if v:
                videos.append(v)
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            videos = self._feed('yingshi_new', 1)[:24]
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            videos = self._feed(str(tid or 'yingshi_new'), pg)
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
            js = self.fetch_json(self.siteUrl + '/web/search/api', {
                'pn': str(pg),
                'rn': '20',
                'type': 'video',
                'query': key,
            })
            for item in self._pick_list(js):
                v = self._map(item)
                if v:
                    videos.append(v)
            if not videos:
                html = self.fetch_text(self.siteUrl + '/web/search/page?query=' + urllib.parse.quote(str(key or '')))
                for m in re.finditer(r'"vid"\s*:\s*"(\d+)"[\s\S]{0,200}?"title"\s*:\s*"([^"]*)"', html or ''):
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
            'pagecount': pg + 1 if len(videos) >= 20 else pg,
            'limit': 20,
            'total': len(videos),
        }

    def detailContent(self, ids):
        vid = str((ids or [''])[0])
        title, pic, desc, author, play = vid, '', '', '', ''
        try:
            js = self.fetch_json(self.siteUrl + '/v', {'vid': vid, '_format': 'json'})
            data = js.get('data') or js
            video = data.get('videoDetail') or data.get('apiData') or data
            if isinstance(video, dict) and video.get('videoMeta'):
                video = video.get('videoMeta')
            if isinstance(video, dict):
                title = video.get('title') or title
                pic = video.get('poster') or video.get('cover_src') or pic
                desc = video.get('title') or desc
                author = video.get('author') or video.get('source_name') or ''
                play = video.get('playurl') or video.get('playUrl') or ''
            html = self.fetch_text(self.siteUrl + '/v?vid=' + urllib.parse.quote(vid))
            if not title or title == vid:
                tm = re.search(r'<title>([^<]+)</title>', html or '')
                if tm:
                    title = re.sub(r'\s*[-_].*$', '', tm.group(1)).strip() or title
            if not pic:
                pm = re.search(r'og:image["\']\s+content=["\']([^"\']+)', html or '')
                if pm:
                    pic = pm.group(1)
            if not play:
                m = re.search(r'"playurl"\s*:\s*"(https?:[^"]+)"', html or '')
                if m:
                    play = m.group(1).replace('\\/', '/')
        except Exception as e:
            print('获取详情失败: %s' % e)
        return {
            'list': [{
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_actor': author,
                'vod_content': desc,
                'vod_play_from': '好看视频',
                'vod_play_url': '正片$%s' % (play if play.startswith('http') else vid),
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
            'Origin': 'https://haokan.baidu.com',
        }
        play_id = str(id or '')
        if play_id.startswith('http') and self.isVideoFormat(play_id):
            return {'parse': 0, 'url': play_id, 'header': header}
        vid = play_id
        try:
            html = self.fetch_text(self.siteUrl + '/v?vid=' + urllib.parse.quote(vid))
            for pat in (
                r'"playurl"\s*:\s*"(https?:[^"]+)"',
                r'"playUrl"\s*:\s*"(https?:[^"]+)"',
                r'https?://[^\s"\']+\.m3u8[^\s"\']*',
                r'https?://[^\s"\']+\.mp4[^\s"\']*',
            ):
                m = re.search(pat, html or '')
                if m:
                    url = (m.group(1) if m.lastindex else m.group(0)).replace('\\/', '/')
                    if url.startswith('http'):
                        return {'parse': 0 if self.isVideoFormat(url) else 1, 'url': url, 'header': header}
            js = self.fetch_json('https://sv.baidu.com/videoui/api/videoland', {'media_id': vid, 'pd': 'pc'})
            data = js.get('data') or js
            meta = data.get('meta') or data
            url = ''
            if isinstance(meta, dict):
                url = meta.get('playurl') or meta.get('playUrl') or ''
            if url:
                return {'parse': 0 if self.isVideoFormat(url) else 1, 'url': url, 'header': header}
        except Exception as e:
            print('获取播放内容失败: %s' % e)
        return {
            'parse': 1,
            'jx': '1',
            'url': self.siteUrl + '/v?vid=' + urllib.parse.quote(vid),
            'header': header,
        }

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        return any(x in u for x in ('.mp4', '.m3u8', '.flv'))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None


if __name__ == '__main__':
    spider = Spider()
    print(json.dumps(spider.homeContent(True), ensure_ascii=False, indent=2))
