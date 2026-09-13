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
        self.siteUrl = 'https://wetv.vip'
        self.playApi = 'https://play.wetv.vip/getvinfo'
        self.userAgent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        self.channels = {
            'tv': {'name': 'TV Series', 'path': '/en'},
            'movie': {'name': 'Movie', 'path': '/en/movie'},
            'variety': {'name': 'Variety', 'path': '/en'},
            'anime': {'name': 'Anime', 'path': '/en'},
        }

    def getName(self):
        return 'WeTV'

    def init(self, extend=""):
        pass

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Accept': 'text/html,application/json,application/xhtml+xml;q=0.9,*/*;q=0.8',
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
                    self.content = raw

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

    def _next_data(self, html):
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>', html or '', re.S)
        if not m:
            m = re.search(r'__NEXT_DATA__\s*=\s*(\{.*?\})</script>', html or '', re.S)
        if not m:
            return {}
        try:
            return json.loads(m.group(1))
        except Exception:
            return {}

    def _walk(self, obj, acc=None):
        if acc is None:
            acc = []
        if isinstance(obj, dict):
            cid = obj.get('cid') or obj.get('cover_id') or obj.get('coverId')
            title = obj.get('title') or obj.get('name') or obj.get('full_title')
            if cid and title:
                acc.append(obj)
            for v in obj.values():
                self._walk(v, acc)
        elif isinstance(obj, list):
            for v in obj:
                self._walk(v, acc)
        return acc

    def _pic(self, item):
        pic = item.get('new_pic_vt') or item.get('new_pic_hz') or item.get('pic') or item.get('image') or item.get('poster') or item.get('cover_url') or ''
        if isinstance(pic, dict):
            pic = pic.get('url') or pic.get('hor') or pic.get('ver') or ''
        if pic and pic.startswith('//'):
            pic = 'https:' + pic
        return pic

    def _map_cover(self, item):
        cid = str(item.get('cid') or item.get('cover_id') or item.get('coverId') or item.get('id') or '')
        if not cid:
            return None
        title = item.get('title') or item.get('name') or item.get('full_title') or cid
        remarks = item.get('episode_updated') or item.get('update_info') or item.get('score') or item.get('sub_title') or ''
        if item.get('episode_all') and item.get('episode_updated'):
            remarks = '%s/%s' % (item.get('episode_updated'), item.get('episode_all'))
        return {
            'vod_id': cid,
            'vod_name': title,
            'vod_pic': self._pic(item),
            'vod_remarks': str(remarks),
            'vod_year': str(item.get('year') or item.get('publish_date') or '')[:4],
        }

    def _parse_cards(self, html):
        videos = []
        seen = set()
        for href, title in re.findall(r'href="([^"]*/play/([^"/?\s]+))"[^>]*>[\s\S]{0,200}?alt="([^"]+)"', html or ''):
            pass
        for m in re.finditer(r'/play/([a-z0-9]{10,})(?:-[^"/?\s]*)?', html or '', re.I):
            cid = m.group(1)
            if cid in seen:
                continue
            seen.add(cid)
        # play links with titles
        for m in re.finditer(r'href="([^"]*/play/([a-z0-9]{10,})(?:-([^"/?\s]*))?)[^"]*"', html or '', re.I):
            cid = m.group(2)
            slug = (m.group(3) or '').replace('-', ' ')
            if cid in {v['vod_id'] for v in videos}:
                continue
            videos.append({
                'vod_id': cid,
                'vod_name': urllib.parse.unquote(slug).replace('%20', ' ') or cid,
                'vod_pic': '',
                'vod_remarks': '',
            })
        data = self._next_data(html)
        for item in self._walk(data.get('props') or data):
            v = self._map_cover(item)
            if not v:
                continue
            # replace stub by richer item
            videos = [x for x in videos if x['vod_id'] != v['vod_id']]
            videos.append(v)
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            html = self.fetch_text(self.siteUrl + '/en')
            videos = self._parse_cards(html)
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:30]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            path = self.channels.get(str(tid), {}).get('path', '/en')
            url = self.siteUrl + path
            if pg > 1:
                url += ('&' if '?' in url else '?') + 'page=' + str(pg)
            html = self.fetch_text(url)
            videos = self._parse_cards(html)
            # fallback homepage if channel empty
            if not videos:
                videos = self._parse_cards(self.fetch_text(self.siteUrl + '/en'))
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 12 else pg,
            'limit': 30,
            'total': 9999,
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        try:
            q = urllib.parse.quote(key)
            for url in (
                self.siteUrl + '/en/search?q=' + q,
                self.siteUrl + '/search?keyword=' + q,
                self.siteUrl + '/en?search=' + q,
            ):
                html = self.fetch_text(url)
                videos = self._parse_cards(html)
                if videos:
                    break
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
        cid = str((ids or [''])[0]).split('/')[0]
        name, pic, desc, actor, director, year, remarks = cid, '', '', '', '', '', ''
        parts = []
        try:
            html = self.fetch_text(self.siteUrl + '/en/play/' + cid)
            data = self._next_data(html)
            page = ((data.get('props') or {}).get('pageProps') or {}).get('data') or {}
            cover = page.get('coverInfo') or page.get('cover_info') or {}
            if not cover:
                items = self._walk(page or data)
                cover = items[0] if items else {}
            name = cover.get('title') or cover.get('name') or name
            pic = self._pic(cover)
            desc = cover.get('description') or cover.get('desc') or cover.get('second_title') or ''
            year = str(cover.get('year') or cover.get('publish_date') or '')[:4]
            actor = cover.get('leading_actor') or cover.get('actors') or ''
            if isinstance(actor, list):
                actor = ' '.join([a.get('name', a) if isinstance(a, dict) else str(a) for a in actor[:8]])
            director = cover.get('director') or ''
            if isinstance(director, list):
                director = ' '.join([d.get('name', d) if isinstance(d, dict) else str(d) for d in director[:3]])
            remarks = cover.get('episode_updated') or cover.get('score') or ''

            vlist = page.get('videoList') or page.get('video_list') or page.get('episodeList') or []
            if not vlist:
                vlist = [x for x in self._walk(page) if x.get('vid')]
            seen = set()
            for i, ep in enumerate(vlist, 1):
                vid = str(ep.get('vid') or ep.get('video_id') or '')
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                ep_name = ep.get('title') or ep.get('full_title') or ep.get('name') or ('EP%s' % i)
                play = '%s/en/play/%s/%s' % (self.siteUrl, cid, vid)
                parts.append('%s$%s' % (ep_name, play))
            if not parts:
                for href in re.findall(r'/play/%s/([a-z0-9]+)' % re.escape(cid), html or '', re.I):
                    if href in seen:
                        continue
                    seen.add(href)
                    parts.append('EP%s$%s/en/play/%s/%s' % (len(parts) + 1, self.siteUrl, cid, href))
        except Exception as e:
            print('获取详情失败: %s' % e)
        if not parts:
            parts.append('Play$%s/en/play/%s' % (self.siteUrl, cid))
        return {
            'list': [{
                'vod_id': cid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_year': year,
                'vod_actor': actor,
                'vod_director': director,
                'vod_remarks': remarks or ('%s EP' % len(parts) if len(parts) > 1 else 'Movie'),
                'vod_content': (desc or '').replace('\n\n', '\n').strip(),
                'vod_play_from': 'WeTV',
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
        # 国际站播放页需网页解析；getvinfo 需要动态 ckey，这里交给解析器
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
