#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64
import hashlib
import json
import random
import re
import string
import sys
import time
import urllib.parse

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
except ImportError:
    AES = None
    pad = None
    unpad = None

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
        self.siteUrl = 'https://hanxiaoquan.com'
        self.appHost = 'https://hxqapi.hiyun.tv'
        self.appHost2 = 'https://hxqapi.zmdcq.com'
        self.tvHost = 'https://api.xiawen.tv'
        self.userAgent = 'HanjuTV/6.8.2 (Redmi Note 12; Android 14; Scale/2.00)'
        self.vn = '6.8.2'
        self.vc = 'a_8280'
        self.ch = 'xiaomi'
        self.uk_key = b'f349wghhe784tqwh'
        self.uk_iv = b'd3w8hf94fidk38lk'
        self.response_secret = '34F9Q53w/HJW8E6Q'
        self.uid = ''
        self.channels = {
            '1': {'name': '韩剧'},
            '2': {'name': '综艺'},
            '3': {'name': '电影'},
            '4': {'name': '日剧'},
            '5': {'name': '美剧'},
            '6': {'name': '泰剧'},
            '7': {'name': '国产剧'},
        }

    def getName(self):
        return '韩小圈'

    def init(self, extend=""):
        self.uid = self._uid()
        try:
            if extend:
                ext = json.loads(extend) if isinstance(extend, str) else (extend or {})
                if ext.get('host'):
                    self.appHost = str(ext.get('host')).rstrip('/')
                if ext.get('uid'):
                    self.uid = str(ext.get('uid'))
        except Exception:
            pass

    def _uid(self, n=20):
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(n))

    def _md5(self, s):
        return hashlib.md5(str(s).encode('utf-8')).hexdigest()

    def _aes_cbc(self, data, key, iv, encrypt=True):
        if not AES:
            return b'' if encrypt else ''
        cipher = AES.new(key[:16], AES.MODE_CBC, iv[:16])
        if encrypt:
            raw = pad(data if isinstance(data, bytes) else str(data).encode('utf-8'), 16)
            return cipher.encrypt(raw)
        raw = data if isinstance(data, bytes) else base64.b64decode(data)
        pt = cipher.decrypt(raw)
        try:
            return unpad(pt, 16).decode('utf-8', 'ignore')
        except Exception:
            return pt.rstrip(b'\x00').decode('utf-8', 'ignore')

    def _headers(self):
        uid = self.uid or self._uid()
        self.uid = uid
        headers = {
            'User-Agent': self.userAgent,
            'app': 'hj',
            'ch': self.ch,
            'vn': self.vn,
            'vc': self.vc,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Encoding': 'gzip',
            'Connection': 'Keep-Alive',
        }
        if AES:
            try:
                uk = base64.b64encode(self._aes_cbc(uid, self.uk_key, self.uk_iv, True)).decode('ascii')
                mix = self._md5(uid)
                payload = json.dumps({
                    'uid': uid,
                    'model': 'Redmi Note 12',
                    'maker': 'Xiaomi',
                    'osv': '14',
                    'ts': int(time.time() * 1000),
                }, separators=(',', ':'), ensure_ascii=False)
                sign = base64.b64encode(
                    self._aes_cbc(payload, mix[:16].encode('utf-8'), mix[16:32].encode('utf-8'), True)
                ).decode('ascii')
                headers['uk'] = uk
                headers['sign'] = sign
                headers['said'] = self._md5(uid)[:16]
            except Exception:
                pass
        return headers

    def _decode_body(self, obj):
        if obj is None:
            return {}
        if isinstance(obj, dict):
            data = obj.get('data')
            if isinstance(data, str) and len(data) > 20 and not data.startswith('http'):
                try:
                    key = obj.get('key') or self._md5(self.uid + str(obj.get('ts') or ''))
                    mix = self._md5(str(key) + self.response_secret)
                    text = self._aes_cbc(data, mix[:16].encode('utf-8'), mix[16:32].encode('utf-8'), False)
                    if text:
                        return json.loads(text)
                except Exception:
                    pass
            return obj
        if isinstance(obj, str):
            try:
                return self._decode_body(json.loads(obj))
            except Exception:
                return {}
        return {}

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = self._headers()
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

    def api_get(self, path, params=None, host=None):
        host = host or self.appHost
        resp = self.fetch(host + path, headers=self._headers(), params=params)
        if not resp:
            if host != self.appHost2:
                return self.api_get(path, params, self.appHost2)
            return {}
        try:
            return self._decode_body(resp.json())
        except Exception:
            return self._decode_body(getattr(resp, 'text', ''))

    def _pick_list(self, payload):
        d = payload.get('data', payload) if isinstance(payload, dict) else payload
        if isinstance(d, list):
            return d
        if not isinstance(d, dict):
            return []
        for k in ('list', 'items', 'series', 'result', 'records', 'searchList', 'data'):
            v = d.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict) and isinstance(v.get('list'), list):
                return v.get('list')
        return []

    def _pic(self, item):
        img = item.get('image') or {}
        if isinstance(img, dict):
            return img.get('thumb') or img.get('poster') or img.get('url') or ''
        return item.get('thumb') or item.get('poster') or item.get('cover') or img or ''

    def _map(self, item):
        if not item:
            return None
        sid = item.get('sid') or item.get('seriesId') or item.get('id') or item.get('series_id')
        if not sid:
            return None
        name = item.get('name') or item.get('title') or item.get('seriesName') or str(sid)
        remarks = item.get('upInfo') or item.get('updateInfo') or item.get('corner') or item.get('score') or ''
        if item.get('finish') or item.get('isFinish'):
            remarks = remarks or '完结'
        return {
            'vod_id': str(sid),
            'vod_name': name,
            'vod_pic': self._pic(item),
            'vod_remarks': str(remarks),
        }

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            js = self.api_get('/api/search/s5', {
                'k': '', 'srefer': 'home', 'type': '1', 'page': '1'
            })
            for item in self._pick_list(js)[:24]:
                v = self._map(item)
                if v:
                    videos.append(v)
            if not videos:
                js = self.api_get('/api/series/index', {'type': '1', 'page': '1', 'size': '24'})
                for item in self._pick_list(js)[:24]:
                    v = self._map(item)
                    if v:
                        videos.append(v)
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        cate = str(tid or '1')
        videos = []
        try:
            js = self.api_get('/api/search/s5', {
                'k': '', 'srefer': 'cate', 'type': cate, 'page': str(pg)
            })
            for item in self._pick_list(js):
                v = self._map(item)
                if v:
                    videos.append(v)
            if not videos:
                js = self.api_get('/api/series/index', {
                    'type': cate, 'page': str(pg), 'size': '30'
                })
                for item in self._pick_list(js):
                    v = self._map(item)
                    if v:
                        videos.append(v)
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 20 else pg,
            'limit': 30,
            'total': 9999,
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        try:
            js = self.api_get('/api/search/s5', {
                'k': key, 'srefer': 'search_input', 'type': '0', 'page': str(pg)
            })
            for item in self._pick_list(js):
                v = self._map(item)
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

    def _ep_name(self, ep, idx):
        name = str((ep or {}).get('name') or (ep or {}).get('title') or (ep or {}).get('alias') or '')
        if name and not re.match(r'^\d+$', name):
            return name
        no = (ep or {}).get('serialNo') or (ep or {}).get('episode') or (ep or {}).get('num') or idx
        return '第%s集' % no

    def _episodes(self, sid):
        episodes = []
        js = self.api_get('/api/series/detail', {'sid': sid})
        d = js.get('data') or js
        if isinstance(d, dict):
            episodes = d.get('playItems') or d.get('episodes') or d.get('programs') or []
        if not episodes:
            js = self.api_get('/api/series2/episodes', {'sid': sid})
            episodes = self._pick_list(js)
        if not episodes:
            js = self.api_get('/api/series/programs_v2', {'sid': sid})
            episodes = self._pick_list(js)
        return d if isinstance(d, dict) else {}, episodes or []

    def detailContent(self, ids):
        sid = str((ids or [''])[0])
        try:
            drama, episodes = self._episodes(sid)
            if not drama.get('name') and not drama.get('title'):
                drama = (self.api_get('/api/series/detail', {'sid': sid}).get('data') or {})
            parts = []
            for i, ep in enumerate(episodes, 1):
                pid = ep.get('pid') or ep.get('playItemId') or ep.get('id') or ep.get('eid')
                if not pid:
                    continue
                parts.append('%s$%s|%s' % (self._ep_name(ep, i), sid, pid))
            if not parts:
                parts.append('正片$%s' % sid)
            name = drama.get('name') or drama.get('title') or drama.get('seriesName') or sid
            return {
                'list': [{
                    'vod_id': sid,
                    'vod_name': name,
                    'vod_pic': self._pic(drama),
                    'vod_year': str(drama.get('year') or ''),
                    'vod_area': drama.get('area') or '韩国',
                    'vod_actor': drama.get('actor') or drama.get('actors') or '',
                    'vod_director': drama.get('director') or '',
                    'vod_remarks': drama.get('upInfo') or drama.get('updateInfo') or '',
                    'vod_content': drama.get('intro') or drama.get('description') or drama.get('brief') or '',
                    'vod_play_from': '韩小圈',
                    'vod_play_url': '#'.join(parts),
                }]
            }
        except Exception as e:
            print('获取详情失败: %s' % e)
            return {'list': [{'vod_id': sid, 'vod_name': sid, 'vod_play_from': '韩小圈', 'vod_play_url': '正片$%s' % sid}]}

    def _pick_url(self, obj):
        if not obj:
            return ''
        if isinstance(obj, str) and obj.startswith('http'):
            return obj
        if isinstance(obj, dict):
            for k in ('playUrl', 'playurl', 'url', 'm3u8', 'src', 'path'):
                v = obj.get(k)
                if isinstance(v, str) and v.startswith('http'):
                    return v
                if isinstance(v, dict):
                    u = self._pick_url(v)
                    if u:
                        return u
            for nest in ('play', 'media', 'video', 'data', 'result'):
                u = self._pick_url(obj.get(nest))
                if u:
                    return u
        if isinstance(obj, list):
            for it in obj:
                u = self._pick_url(it)
                if u:
                    return u
        return ''

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
            'Origin': self.siteUrl,
        }
        play_id = str(id or '')
        if play_id.startswith('http') and self.isVideoFormat(play_id):
            return {'parse': 0, 'url': play_id, 'header': header}
        parts = play_id.split('|')
        sid = parts[0]
        pid = parts[1] if len(parts) > 1 else ''
        try:
            for path, params in (
                ('/api/play/playurl', {'pid': pid or sid}),
                ('/api/play/get', {'pid': pid or sid, 'sid': sid}),
                ('/api/series/play', {'pid': pid or sid, 'sid': sid}),
            ):
                if not pid and 'pid' in params and params['pid'] == sid:
                    continue
                js = self.api_get(path, params)
                url = self._pick_url(js)
                if url:
                    return {'parse': 0 if self.isVideoFormat(url) else 1, 'url': url, 'header': header}
        except Exception as e:
            print('获取播放内容失败: %s' % e)
        return {
            'parse': 1,
            'jx': '1',
            'url': self.siteUrl + '/',
            'header': header,
        }

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        return any(x in u for x in ('.m3u8', '.mp4', '.mpd', '.flv'))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None


if __name__ == '__main__':
    spider = Spider()
    print(json.dumps(spider.homeContent(True), ensure_ascii=False, indent=2))
