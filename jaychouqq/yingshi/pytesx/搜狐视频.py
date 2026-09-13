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
        self.siteUrl = 'https://tv.sohu.com'
        self.api = 'https://api.tv.sohu.com'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            '1': {'name': '电影', 'cid': '1'},
            '2': {'name': '电视剧', 'cid': '2'},
            '7': {'name': '综艺', 'cid': '7'},
            '16': {'name': '动漫', 'cid': '16'},
            '8': {'name': '纪录片', 'cid': '8'},
            '21': {'name': '教育', 'cid': '21'},
        }
        self.filters = {
            '1': [
                {'key': 'o', 'name': '排序', 'value': [
                    {'n': '相关', 'v': '1'},
                    {'n': '最新', 'v': '3'},
                    {'n': '最热', 'v': '2'},
                ]}
            ],
            '2': [
                {'key': 'o', 'name': '排序', 'value': [
                    {'n': '相关', 'v': '1'},
                    {'n': '最新', 'v': '3'},
                    {'n': '最热', 'v': '2'},
                ]}
            ],
        }

    def getName(self):
        return '搜狐视频'

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

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        result = {'class': classes}
        if filter:
            result['filters'] = self.filters
        return result

    def homeVideoContent(self):
        videos = []
        try:
            for cid in ('1', '2', '7'):
                data = self.fetch_json(
                    self.api + '/v4/search/channel.json',
                    {'cid': cid, 'page': 1, 'page_size': 8}
                )
                for item in ((data.get('data') or {}).get('videos') or [])[:8]:
                    videos.append(self._parseAlbum(item))
                if len(videos) >= 24:
                    break
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        pagecount = pg
        total = 0
        try:
            cid = self.channels.get(str(tid), {}).get('cid', str(tid))
            o = '1'
            if extend and isinstance(extend, dict):
                o = str(extend.get('o') or '1')
            data = self.fetch_json(
                self.api + '/v4/search/channel.json',
                {'cid': cid, 'page': pg, 'page_size': 24, 'o': o}
            )
            body = data.get('data') or {}
            for item in body.get('videos') or []:
                videos.append(self._parseAlbum(item))
            total = int(body.get('count') or len(videos))
            pagecount = max(1, (total + 23) // 24) if total else (pg + 1 if videos else pg)
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': min(pagecount, 400),
            'limit': 24,
            'total': total or len(videos),
        }

    def detailContent(self, ids):
        try:
            aid = str(ids[0]).split('_')[0]
            info = (self.fetch_json(self.api + '/v4/album/info/%s.json' % aid).get('data') or {})
            videos = []
            page = 1
            while page <= 20:
                body = (self.fetch_json(
                    self.api + '/v4/album/videos/%s.json' % aid,
                    {'page': page, 'page_size': 50}
                ).get('data') or {})
                part = body.get('videos') or []
                videos.extend(part)
                if len(part) < 50:
                    break
                page += 1
            play_urls = []
            for ep in videos:
                name = ep.get('albumVideoShowName') or ep.get('video_name') or ('第%s集' % (len(play_urls) + 1))
                play_id = self._pickPlay(ep)
                if play_id:
                    play_urls.append('%s$%s' % (name, play_id))
            if not play_urls:
                play_urls.append('正片$%s' % aid)
            vod = {
                'vod_id': aid,
                'vod_name': info.get('album_name') or info.get('video_name') or aid,
                'vod_pic': info.get('ver_high_pic') or info.get('hor_high_pic') or '',
                'vod_remarks': info.get('tip') or info.get('update_notification') or '',
                'vod_year': str(info.get('year') or '')[:4],
                'vod_area': info.get('area') or '',
                'vod_actor': info.get('actor') or '',
                'vod_director': info.get('director') or '',
                'vod_content': (info.get('album_desc') or '').replace('\n\n', '\n').strip(),
                'vod_play_from': '搜狐视频',
                'vod_play_url': '#'.join(play_urls),
            }
            return {'list': [vod]}
        except Exception as e:
            print('获取详情失败: %s' % e)
            return {'list': []}

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        try:
            if re.match(r'^\d{5,}$', str(key).strip()):
                info = (self.fetch_json(self.api + '/v4/album/info/%s.json' % key.strip()).get('data') or {})
                if info.get('aid') or info.get('album_name'):
                    videos.append(self._parseAlbum(info))
                    return {'list': videos, 'page': 1, 'pagecount': 1, 'limit': 20, 'total': 1}
            for path in (
                '/v4/search/video.json',
                '/v4/search/album.json',
                '/v4/search/channel.json',
            ):
                data = self.fetch_json(
                    self.api + path,
                    {'key': key, 'keyword': key, 'page': pg, 'page_size': 20}
                )
                body = data.get('data') or {}
                items = body.get('videos') or body.get('albums') or []
                if items and path != '/v4/search/channel.json':
                    for item in items:
                        videos.append(self._parseAlbum(item))
                    break
                if items and path == '/v4/search/channel.json' and not videos:
                    # channel.json 在部分地区忽略关键词，仅作兜底
                    for item in items[:20]:
                        name = item.get('album_name') or item.get('video_name') or ''
                        if key and key not in name:
                            continue
                        videos.append(self._parseAlbum(item))
            if not videos:
                html = self._get_text('https://so.tv.sohu.com/mts?wd=%s&c=0' % urllib.parse.quote(key))
                for aid, title in re.findall(r'/album/(\d+)\.html[^>]*title="([^"]+)"', html or ''):
                    videos.append({
                        'vod_id': aid,
                        'vod_name': title,
                        'vod_pic': '',
                        'vod_remarks': '',
                    })
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if videos else pg,
            'limit': 20,
            'total': len(videos),
        }

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': 'https://tv.sohu.com/',
            'Origin': 'https://tv.sohu.com',
        }
        play_url = str(id or '')
        try:
            if play_url.startswith('http') and self.isVideoFormat(play_url):
                return {'parse': 0, 'url': play_url.replace('http://', 'https://'), 'header': header}
            if play_url.startswith('http'):
                return {'parse': 1, 'jx': '1', 'url': play_url, 'header': header}
            if play_url.isdigit():
                body = (self.fetch_json(
                    self.api + '/v4/album/videos/%s.json' % play_url,
                    {'page': 1, 'page_size': 1}
                ).get('data') or {})
                vs = body.get('videos') or []
                if vs:
                    picked = self._pickPlay(vs[0])
                    if picked and picked.startswith('http') and self.isVideoFormat(picked):
                        return {'parse': 0, 'url': picked.replace('http://', 'https://'), 'header': header}
            return {
                'parse': 1,
                'jx': '1',
                'url': 'https://tv.sohu.com/album/%s.html' % play_url,
                'header': header,
            }
        except Exception as e:
            print('获取播放内容失败: %s' % e)
            return {'parse': 1, 'url': play_url, 'header': header}

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        for fmt in ('.m3u8', '.mp4', '.flv', '.ts'):
            if fmt in u:
                return True
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def _get_text(self, url):
        resp = self.fetch(url)
        if not resp:
            return ''
        if hasattr(resp, 'content'):
            raw = resp.content
            for enc in ('utf-8', 'gbk', 'gb2312'):
                try:
                    return raw.decode(enc)
                except Exception:
                    continue
            return raw.decode('utf-8', 'ignore')
        return getattr(resp, 'text', '') or ''

    def _parseAlbum(self, item):
        aid = str(item.get('aid') or item.get('album_id') or '')
        pic = (
            item.get('ver_high_pic')
            or item.get('hor_high_pic')
            or item.get('ver_big_pic')
            or item.get('hor_w16_pic')
            or ''
        )
        remarks = item.get('tip') or item.get('update_notification') or item.get('album_sub_name') or ''
        return {
            'vod_id': aid,
            'vod_name': item.get('album_name') or item.get('video_name') or aid,
            'vod_pic': pic,
            'vod_remarks': remarks,
            'vod_year': str(item.get('year') or '')[:4],
            'vod_area': item.get('area') or '',
        }

    def _pickPlay(self, ep):
        for key in (
            'url_super', 'url_super_265', 'url_high', 'url_high_265',
            'url_original', 'url_nor', 'url_blue', 'url_4K', 'url_html5'
        ):
            u = ep.get(key) or ''
            if u and u.startswith('http'):
                return u
        vid = ep.get('vid')
        if vid:
            return 'https://hot.vrs.sohu.com/ipad%s.m3u8' % vid
        return ''


if __name__ == '__main__':
    spider = Spider()
    print(json.dumps(spider.homeContent(True), ensure_ascii=False, indent=2))
