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
    """网易公版影像典藏 https://public.163.com"""

    def __init__(self):
        self.siteUrl = 'https://public.163.com'
        self.hallUrl = 'https://wp.m.163.com/163/html/newsapp/time-hall/index.html'
        self.openUrl = 'https://open.163.com'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            'movie': {'name': '电影'},
            'doc': {'name': '纪录片'},
            'short': {'name': '短片'},
            'archive': {'name': '影像资料馆'},
            'daily': {'name': '每日精读'},
        }

    def getName(self):
        return '网易公版'

    def init(self, extend=""):
        pass

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Accept': 'text/html,application/json,application/xhtml+xml;q=0.9,*/*;q=0.8',
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
            if obj.get('title') or obj.get('name') or obj.get('movieName'):
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
        vid = str(it.get('id') or it.get('pid') or it.get('mid') or it.get('movieId') or it.get('docid') or '')
        name = it.get('title') or it.get('name') or it.get('movieName') or it.get('tname') or ''
        pic = it.get('cover') or it.get('img') or it.get('image') or it.get('poster') or it.get('pic') or ''
        remarks = it.get('year') or it.get('duration') or it.get('director') or it.get('area') or ''
        href = it.get('url') or it.get('link') or it.get('playUrl') or ''
        if not vid and href:
            vid = href
        if not vid and not name:
            return None
        return {
            'vod_id': vid or name,
            'vod_name': name or vid,
            'vod_pic': self._abs(pic),
            'vod_remarks': str(remarks),
        }

    def _parse_html(self, html):
        videos, seen = [], set()
        for m in re.finditer(
            r'href="((?:https?://(?:public|open|wp\.m)\.163\.com)?/[^"]*(?:movie|video|film|play|detail)[^"]*)"[^>]{0,200}(?:title|alt)="([^"]*)"',
            html or '',
            re.I,
        ):
            href, name = m.group(1), self._clean(m.group(2))
            if not name or href in seen:
                continue
            seen.add(href)
            videos.append({
                'vod_id': href,
                'vod_name': name,
                'vod_pic': '',
                'vod_remarks': '公版',
            })
        if not videos:
            for m in re.finditer(
                r'<h[23][^>]*>([^<]{2,40})</h[23]>[\s\S]{0,120}?(\d{4})?[\s\S]{0,80}?([^\n<]{0,40})',
                html or '',
            ):
                name = self._clean(m.group(1))
                if not name or name in seen or name in ('电影', '纪录片', '影像资料馆', '每日精读'):
                    continue
                seen.add(name)
                videos.append({
                    'vod_id': name,
                    'vod_name': name,
                    'vod_pic': '',
                    'vod_remarks': (m.group(2) or '') + ' ' + self._clean(m.group(3) or ''),
                })
        for m in re.finditer(
            r'(?:src|data-src|data-original)="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
            html or '',
            re.I,
        ):
            pic = self._abs(m.group(1))
            for v in videos:
                if not v['vod_pic']:
                    v['vod_pic'] = pic
                    break
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
                data = self.fetch_json(self.siteUrl + '/api/list')
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
            tid = str(tid or 'movie')
            html = self.fetch_text(self.siteUrl + '/')
            videos = self._parse_html(html)
            if tid == 'daily':
                videos = videos[:12]
            elif tid == 'short':
                videos = [v for v in videos if '短' in (v.get('vod_remarks') or v.get('vod_name') or '')] or videos
            elif tid == 'doc':
                videos = [v for v in videos if '纪录' in (v.get('vod_remarks') or v.get('vod_name') or '')] or videos
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
            html = self.fetch_text(self.siteUrl + '/')
            videos = [v for v in self._parse_html(html) if key in v.get('vod_name', '')]
            if not videos:
                q = urllib.parse.quote(key)
                html = self.fetch_text(self.openUrl + '/search.html?keyword=' + q)
                videos = self._parse_html(html)
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg,
            'limit': 24,
            'total': len(videos),
        }

    def detailContent(self, ids):
        vid = str((ids or [''])[0])
        name, pic, desc, remarks, director = vid, '', '', '公版影像', ''
        try:
            page = vid if vid.startswith('http') else self.siteUrl + '/'
            html = self.fetch_text(page) if vid.startswith('http') else self.fetch_text(self.siteUrl + '/')
            if not vid.startswith('http'):
                name = vid
            tm = re.search(r'<title>([^<]+)</title>', html or '')
            if tm and vid.startswith('http'):
                name = re.sub(r'\s*[-_|].*$', '', tm.group(1)).strip() or name
            hm = re.search(r'<h1[^>]*>([\s\S]{2,80})</h1>', html or '')
            if hm:
                name = self._clean(hm.group(1)) or name
            pm = re.search(r'(?:og:image["\']\s+content=["\']|poster=["\'])([^"\']+)', html or '')
            if pm:
                pic = self._abs(pm.group(1))
            dm = re.search(r'og:description["\']\s+content=["\']([^"\']+)', html or '')
            if dm:
                desc = dm.group(1)
            dm2 = re.search(r'导演[:：]\s*([^<\n]+)', html or '')
            if dm2:
                director = self._clean(dm2.group(1))
            m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or '')
            mp4 = re.search(r'https?://[^\s"\']+\.mp4[^\s"\']*', html or '')
            src = re.search(r'<video[^>]+src=["\']([^"\']+)["\']', html or '', re.I)
            src2 = re.search(r'(?:playUrl|videoUrl|mp4Url|flvUrl|src)\s*[:=]\s*["\'](https?://[^"\']+)["\']', html or '')
            play = ''
            if m3:
                play = m3.group(0).replace('\\/', '/')
            elif mp4:
                play = mp4.group(0).replace('\\/', '/')
            elif src:
                play = self._abs(src.group(1))
            elif src2:
                play = src2.group(1)
            play_url = '播放$%s' % (play or (page if page.startswith('http') else self.siteUrl + '/'))
        except Exception as e:
            print('获取详情失败: %s' % e)
            play_url = '播放$%s' % self.siteUrl
        return {'list': [{
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': remarks,
            'vod_actor': '',
            'vod_director': director,
            'vod_content': (desc or '网易公版影像典藏，站点已停更，完整片可尝试时光放映厅。').strip(),
            'vod_play_from': '网易公版',
            'vod_play_url': play_url,
        }]}

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
            'Origin': 'https://public.163.com',
        }
        play = str(id or '')
        if self.isVideoFormat(play) and play.startswith('http'):
            return {'parse': 0, 'jx': '0', 'url': play, 'header': header}
        if play.startswith('/'):
            play = self.siteUrl + play
        html = self.fetch_text(play) if play.startswith('http') else ''
        m3 = re.search(r'https?://[^\s"\']+\.(?:m3u8|mp4|flv)[^\s"\']*', html or '')
        if m3:
            return {'parse': 0, 'jx': '0', 'url': m3.group(0).replace('\\/', '/'), 'header': header}
        if not play.startswith('http'):
            play = self.hallUrl
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
