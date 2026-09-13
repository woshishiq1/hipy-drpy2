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
        self.siteUrl = 'https://www.360kan.com'
        self.api = 'https://api.web.360kan.com'
        self.searchApi = 'https://api.so.360kan.com/index'
        self.userAgent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        self.channels = {
            '1': {'name': '电影', 'catid': '1'},
            '2': {'name': '电视剧', 'catid': '2'},
            '3': {'name': '综艺', 'catid': '3'},
            '4': {'name': '动漫', 'catid': '4'},
        }
        self.site_name = {
            'qq': '腾讯',
            'qiyi': '爱奇艺',
            'youku': '优酷',
            'imgo': '芒果',
            'mgtv': '芒果',
            'sohu': '搜狐',
            'pptv': 'PP视频',
            'levp': '乐视',
            'leshi': '乐视',
            'bilibili': '哔哩哔哩',
            'xigua': '西瓜',
            'cntv': '央视',
            'wasu': '华数',
        }

    def getName(self):
        return '360影视'

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

    def _map(self, item, catid=''):
        if not item:
            return None
        vid = item.get('id') or item.get('ent_id') or item.get('en_id')
        if not vid:
            return None
        cate = str(item.get('cat_id') or item.get('catid') or catid or '2')
        title = item.get('title') or item.get('ent_name') or item.get('titleTxt') or str(vid)
        pic = item.get('cover') or item.get('cdncover') or item.get('pic') or item.get('tvcover') or ''
        remarks = item.get('upinfo') or item.get('updateinfo') or item.get('score') or item.get('pubdate') or ''
        return {
            'vod_id': '%s_%s' % (cate, vid),
            'vod_name': title,
            'vod_pic': pic,
            'vod_remarks': str(remarks),
            'vod_year': str(item.get('year') or item.get('pubdate') or '')[:4],
        }

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        filters = {}
        for tid in self.channels:
            filters[tid] = [
                {
                    'key': 'rank',
                    'name': '排序',
                    'value': [
                        {'n': '最近热映', 'v': 'rankhot'},
                        {'n': '最近更新', 'v': 'ranklatest'},
                        {'n': '最受好评', 'v': 'rankpoint'},
                    ],
                }
            ]
        return {'class': classes, 'filters': filters}

    def homeVideoContent(self):
        videos = []
        try:
            for catid in ('2', '1', '4', '3'):
                js = self.fetch_json(self.api + '/v1/filter/list', {
                    'catid': catid,
                    'rank': 'rankhot',
                    'cat': '',
                    'year': '',
                    'area': '',
                    'act': '',
                    'pageno': '1',
                })
                data = js.get('data') or {}
                movies = data.get('movies') or data.get('list') or []
                for item in movies[:6]:
                    v = self._map(item, catid)
                    if v:
                        videos.append(v)
                if len(videos) >= 24:
                    break
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        catid = str(tid or '2')
        rank = 'rankhot'
        if extend and isinstance(extend, dict):
            rank = extend.get('rank') or rank
        videos = []
        try:
            js = self.fetch_json(self.api + '/v1/filter/list', {
                'catid': catid,
                'rank': rank,
                'cat': '',
                'year': '',
                'area': '',
                'act': '',
                'pageno': str(pg),
            })
            data = js.get('data') or {}
            movies = data.get('movies') or data.get('list') or []
            for item in movies:
                v = self._map(item, catid)
                if v:
                    videos.append(v)
            total = int(data.get('total') or data.get('totalCount') or 0)
            pagecount = max(pg, (total + 19) // 20) if total else (pg + 1 if len(videos) >= 20 else pg)
        except Exception as e:
            print('获取分类内容失败: %s' % e)
            pagecount = pg
            total = len(videos)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': 20,
            'total': total if videos else len(videos),
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        try:
            js = self.fetch_json(self.searchApi, {
                'force_zonghe': '1',
                'kw': key,
                'from': '',
                'pno': str(pg),
            })
            data = js.get('data') or {}
            long = ((data.get('longData') or {}).get('rows')) or data.get('movies') or []
            for item in long:
                v = self._map(item, str(item.get('cat_id') or item.get('catid') or '2'))
                if v:
                    videos.append(v)
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 10 else pg,
            'limit': 20,
            'total': len(videos),
        }

    def _split_id(self, raw):
        s = str(raw or '')
        if '_' in s:
            a, b = s.split('_', 1)
            return a, b
        return '2', s

    def detailContent(self, ids):
        catid, vid = self._split_id((ids or [''])[0])
        try:
            js = self.fetch_json(self.api + '/v1/detail', {
                'cat': catid,
                'id': vid,
            })
            d = js.get('data') or {}
            title = d.get('title') or vid
            pic = d.get('cdncover') or d.get('cover') or ''
            desc = d.get('description') or d.get('comment') or ''
            actor = d.get('actor') or ''
            if isinstance(actor, list):
                actor = ' '.join(actor)
            director = d.get('director') or ''
            if isinstance(director, list):
                director = ' '.join(director)
            year = str(d.get('year') or d.get('pubdate') or '')
            area = d.get('area') or ''
            if isinstance(area, list):
                area = ' '.join(area)

            froms = []
            urls = []
            allep = d.get('allepidetail') or {}
            playlinks = d.get('playlinks') or {}
            if isinstance(allep, dict) and allep:
                for site, eps in allep.items():
                    if not isinstance(eps, list):
                        continue
                    parts = []
                    for i, ep in enumerate(eps, 1):
                        name = str(ep.get('playlink_num') or ep.get('name') or i)
                        link = ep.get('url') or ''
                        if link:
                            parts.append('%s$%s' % (name, link))
                    if parts:
                        froms.append(self.site_name.get(site, site))
                        urls.append('#'.join(parts))
            elif isinstance(playlinks, dict) and playlinks:
                parts = []
                for site, link in playlinks.items():
                    if link:
                        parts.append('%s$%s' % (self.site_name.get(site, site), link))
                if parts:
                    froms.append('官方源')
                    urls.append('#'.join(parts))

            if not froms:
                froms = ['360影视']
                urls = ['正片$https://www.360kan.com/%s/%s.html' % ('m' if catid == '1' else 'tv', vid)]

            remarks = d.get('upinfo') or d.get('updateinfo') or ''
            return {
                'list': [{
                    'vod_id': '%s_%s' % (catid, vid),
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_year': year[:4],
                    'vod_area': area,
                    'vod_actor': actor,
                    'vod_director': director,
                    'vod_remarks': str(remarks),
                    'vod_content': desc,
                    'vod_play_from': '$$$'.join(froms),
                    'vod_play_url': '$$$'.join(urls),
                }]
            }
        except Exception as e:
            print('获取详情失败: %s' % e)
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
        }
        play_url = str(id or '')
        if play_url.startswith('http') and self.isVideoFormat(play_url):
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
