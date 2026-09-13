#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64
import json
import random
import re
import sys
import urllib.parse
import zlib

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
    """西瓜视频 https://m.ixigua.com"""

    def __init__(self):
        self.siteUrl = 'https://m.ixigua.com'
        self.pcUrl = 'https://www.ixigua.com'
        self.playApi = 'https://ib.365yg.com'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            'hot': {'name': '热门', 'kw': '热门'},
            'movie': {'name': '影视', 'kw': '电影'},
            'tv': {'name': '电视剧', 'kw': '电视剧'},
            'short': {'name': '短剧', 'kw': '短剧'},
            'funny': {'name': '搞笑', 'kw': '搞笑'},
            'life': {'name': '生活', 'kw': '生活'},
            'food': {'name': '美食', 'kw': '美食'},
            'game': {'name': '游戏', 'kw': '游戏'},
            'sport': {'name': '体育', 'kw': '体育'},
            'music': {'name': '音乐', 'kw': '音乐'},
            'tech': {'name': '科技', 'kw': '科技'},
            'doc': {'name': '纪录片', 'kw': '纪录片'},
        }

    def getName(self):
        return '西瓜视频'

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

    def _ssr(self, html):
        for pat in (
            r'window\._ROUTER_DATA\s*=\s*(\{.*?\})</script>',
            r'window\._RENDER_DATA\s*=\s*"([^"]+)"',
            r'<script id="RENDER_DATA"[^>]*>([^<]+)</script>',
            r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
        ):
            m = re.search(pat, html or '', re.S)
            if not m:
                continue
            raw = m.group(1)
            try:
                if raw.startswith('%') or '%7B' in raw[:8]:
                    raw = urllib.parse.unquote(raw)
                return json.loads(raw)
            except Exception:
                continue
        return {}

    def _walk(self, obj, acc=None):
        if acc is None:
            acc = []
        if isinstance(obj, dict):
            gid = obj.get('group_id') or obj.get('gid') or obj.get('item_id') or obj.get('video_id')
            title = obj.get('title') or obj.get('name') or obj.get('content')
            if gid and title:
                acc.append(obj)
            for v in obj.values():
                self._walk(v, acc)
        elif isinstance(obj, list):
            for v in obj:
                self._walk(v, acc)
        return acc

    def _map(self, item):
        vid = str(
            item.get('group_id')
            or item.get('gid')
            or item.get('item_id')
            or item.get('video_id')
            or item.get('id')
            or ''
        )
        name = item.get('title') or item.get('name') or item.get('content') or vid
        pic = ''
        for key in ('cover', 'poster_url', 'image_url', 'middle_image', 'large_image'):
            val = item.get(key)
            if isinstance(val, dict):
                pic = (val.get('url') or val.get('url_list') or [''])
                if isinstance(pic, list):
                    pic = pic[0] if pic else ''
                elif isinstance(pic, dict):
                    pic = pic.get('url') or ''
            elif isinstance(val, str):
                pic = val
            if pic:
                break
        user = item.get('user_info') or item.get('user') or item.get('author') or {}
        remarks = ''
        if isinstance(user, dict):
            remarks = user.get('name') or user.get('nickname') or ''
        dur = item.get('video_duration') or item.get('duration') or 0
        try:
            dur = int(float(dur))
            if dur:
                remarks = (remarks + ' ' if remarks else '') + '%d:%02d' % (dur // 60, dur % 60)
        except Exception:
            pass
        if not vid or not re.search(r'\d{8,}', vid):
            return None
        return {
            'vod_id': vid,
            'vod_name': re.sub(r'<[^>]+>', '', str(name)).strip(),
            'vod_pic': self._abs(pic),
            'vod_remarks': str(remarks).strip(),
        }

    def _from_html(self, html):
        videos, seen = [], set()
        data = self._ssr(html)
        for item in self._walk(data):
            v = self._map(item)
            if v and v['vod_id'] not in seen:
                seen.add(v['vod_id'])
                videos.append(v)
        for m in re.finditer(
            r'href="(?:https?://(?:www|m)\.ixigua\.com)?/(?:video/)?(\d{10,})[^"]*"[^>]{0,120}(?:title|alt)="([^"]+)"',
            html or '',
        ):
            vid, name = m.group(1), re.sub(r'<[^>]+>', '', m.group(2)).strip()
            if vid in seen or not name:
                continue
            seen.add(vid)
            videos.append({'vod_id': vid, 'vod_name': name, 'vod_pic': '', 'vod_remarks': ''})
        return videos

    def _search(self, key, offset=0):
        videos = []
        q = urllib.parse.quote(key)
        data = self.fetch_json('%s/api/searchv2/complex/%s/%s' % (self.pcUrl, q, offset))
        items = ((data.get('data') or {}).get('data')) or self._walk(data)
        for it in items:
            node = it.get('data') if isinstance(it, dict) and isinstance(it.get('data'), dict) else it
            if not isinstance(node, dict):
                continue
            v = self._map(node)
            if v:
                videos.append(v)
        if not videos:
            html = self.fetch_text('%s/search/?keyword=%s' % (self.siteUrl, q))
            videos = self._from_html(html)
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
            html = self.fetch_text(self.siteUrl + '/')
            videos = self._from_html(html)
            if not videos:
                videos = self._search('热门', 0)
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            info = self.channels.get(str(tid), {'kw': tid})
            videos = self._search(info.get('kw') or tid, (pg - 1) * 20)
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 10 else pg,
            'limit': 20,
            'total': 9999,
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        try:
            videos = self._search(key, (pg - 1) * 20)
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 10 else pg,
            'limit': 20,
            'total': len(videos),
        }

    def _detail_page(self, vid):
        for url in (
            '%s/%s' % (self.siteUrl, vid),
            '%s/video/%s' % (self.siteUrl, vid),
            '%s/%s' % (self.pcUrl, vid),
        ):
            html = self.fetch_text(url)
            if html and len(html) > 400:
                return html
        return ''

    def _play_from_vid(self, video_id):
        if not video_id:
            return ''
        r = str(random.randint(100000000, 999999999))
        path = '/video/urls/v/1/toutiao/mp4/%s?r=%s' % (video_id, r)
        s = zlib.crc32(path.encode('utf-8'))
        if s > 0x7FFFFFFF:
            s -= 0x100000000
        data = self.fetch_json(self.playApi + path + '&s=' + str(s))
        vlist = ((data.get('data') or {}).get('video_list')) or {}
        best = ''
        for key in sorted(vlist.keys(), reverse=True):
            item = vlist.get(key) or {}
            enc = item.get('main_url') or item.get('backup_url_1') or ''
            if not enc:
                continue
            try:
                best = base64.b64decode(enc).decode('utf-8', 'ignore')
                if best:
                    break
            except Exception:
                if str(enc).startswith('http'):
                    best = enc
                    break
        return best

    def _extract_play_id(self, data):
        text = json.dumps(data, ensure_ascii=False)
        m = re.search(r'"vid"\s*:\s*"(v[0-9a-zA-Z]+)"', text)
        if m:
            return m.group(1)
        m = re.search(r'"video_id"\s*:\s*"(v[0-9a-zA-Z]+)"', text)
        if m:
            return m.group(1)
        return ''

    def detailContent(self, ids):
        vid = str((ids or [''])[0])
        name, pic, desc, remarks, actor = vid, '', '', '', ''
        play_id = ''
        try:
            html = self._detail_page(vid)
            data = self._ssr(html)
            play_id = self._extract_play_id(data)
            items = self._walk(data)
            if items:
                first = items[0]
                mapped = self._map(first) or {}
                name = mapped.get('vod_name') or name
                pic = mapped.get('vod_pic') or pic
                remarks = mapped.get('vod_remarks') or remarks
                user = first.get('user_info') or first.get('user') or first.get('author') or {}
                if isinstance(user, dict):
                    actor = user.get('name') or user.get('nickname') or ''
                desc = first.get('abstract') or first.get('content') or first.get('title') or ''
            if not name or name == vid:
                tm = re.search(r'<title>([^<]+)</title>', html or '')
                if tm:
                    name = re.sub(r'\s*[-_|].*$', '', tm.group(1)).strip() or name
            if not play_id:
                m = re.search(r'"vid"\s*:\s*"(v[0-9a-zA-Z]+)"', html or '')
                if m:
                    play_id = m.group(1)
        except Exception as e:
            print('获取详情失败: %s' % e)
        play_token = play_id or vid
        return {'list': [{
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': remarks,
            'vod_actor': actor,
            'vod_content': str(desc).replace('\n\n', '\n').strip(),
            'vod_play_from': '西瓜视频',
            'vod_play_url': '播放$%s' % play_token,
        }]}

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.pcUrl + '/',
            'Origin': self.pcUrl,
        }
        play_id = str(id or '')
        if self.isVideoFormat(play_id) and play_id.startswith('http'):
            return {'parse': 0, 'url': play_id, 'header': header}
        url = ''
        try:
            if play_id.startswith('v'):
                url = self._play_from_vid(play_id)
            if not url:
                html = self._detail_page(play_id)
                data = self._ssr(html)
                vid = self._extract_play_id(data)
                if not vid:
                    m = re.search(r'"vid"\s*:\s*"(v[0-9a-zA-Z]+)"', html or '')
                    vid = m.group(1) if m else ''
                if vid:
                    url = self._play_from_vid(vid)
                if not url:
                    m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or '')
                    if m3:
                        url = m3.group(0).replace('\\/', '/')
        except Exception as e:
            print('获取播放内容失败: %s' % e)
        if url:
            return {'parse': 0, 'jx': '0', 'url': url, 'header': header}
        page = self.siteUrl + '/' + play_id
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
