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
    """小蜜蜂影院 https://www.xmfyy.com"""

    def __init__(self):
        self.siteUrl = 'https://www.xmfyy.com'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            '1': {'name': '电影'},
            '2': {'name': '电视剧'},
            '3': {'name': '综艺'},
            '4': {'name': '动漫'},
        }

    def getName(self):
        return '小蜜蜂影院'

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
            return {}

    def _abs(self, u):
        if not u:
            return ''
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('/'):
            return self.siteUrl + u
        return u

    def _clean(self, s):
        return re.sub(r'<[^>]+>', '', str(s or '')).replace('&nbsp;', ' ').strip()

    def _parse_list(self, html):
        videos, seen = [], set()
        for m in re.finditer(
            r'href="((?:https?://[^"/]+)?(?:/index\.php)?/vod/detail/id/(\d+)\.html)"[^>]{0,200}(?:title|alt)="([^"]*)"',
            html or '',
            re.I,
        ):
            vid, name = m.group(2), self._clean(m.group(3) or m.group(2))
            if not vid or vid in seen or name in ('详情', '播放'):
                continue
            seen.add(vid)
            videos.append({'vod_id': vid, 'vod_name': name or vid, 'vod_pic': '', 'vod_remarks': ''})
        if not videos:
            for m in re.finditer(r'vod/detail/id/(\d+)\.html"[^>]*>([^<]{2,80})', html or ''):
                vid, name = m.group(1), self._clean(m.group(2))
                if vid in seen or not name:
                    continue
                seen.add(vid)
                videos.append({'vod_id': vid, 'vod_name': name, 'vod_pic': '', 'vod_remarks': ''})
        for m in re.finditer(
            r'detail/id/(\d+)[^"]*"[^>]*>[\s\S]{0,220}?(?:src|data-original|data-src)="([^"]+)"',
            html or '',
            re.I,
        ):
            for v in videos:
                if v['vod_id'] == m.group(1) and not v['vod_pic']:
                    v['vod_pic'] = self._abs(m.group(2))
        for m in re.finditer(
            r'detail/id/(\d+)[\s\S]{0,300}?class="[^"]*(?:pic-text|text-right|remarks)[^"]*"[^>]*>([^<]+)',
            html or '',
            re.I,
        ):
            for v in videos:
                if v['vod_id'] == m.group(1) and not v['vod_remarks']:
                    v['vod_remarks'] = self._clean(m.group(2))
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            html = self.fetch_text(self.siteUrl + '/')
            videos = self._parse_list(html)
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            tid = str(tid or '1')
            urls = [
                '%s/index.php/vod/type/id/%s/page/%s.html' % (self.siteUrl, tid, pg),
                '%s/vod/type/id/%s/page/%s.html' % (self.siteUrl, tid, pg),
                '%s/index.php/vod/show/id/%s/page/%s.html' % (self.siteUrl, tid, pg),
            ]
            if pg == 1:
                urls.extend([
                    '%s/index.php/vod/type/id/%s.html' % (self.siteUrl, tid),
                    '%s/vod/type/id/%s.html' % (self.siteUrl, tid),
                ])
            for url in urls:
                html = self.fetch_text(url)
                videos = self._parse_list(html)
                if videos:
                    break
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
            q = urllib.parse.quote(key)
            for url in (
                '%s/index.php/vod/search/page/%s/wd/%s.html' % (self.siteUrl, pg, q),
                '%s/index.php/ajax/suggest?mid=1&wd=%s&limit=24' % (self.siteUrl, q),
            ):
                if 'ajax/suggest' in url:
                    data = self.fetch_json(url)
                    for it in data.get('list') or []:
                        videos.append({
                            'vod_id': str(it.get('id') or ''),
                            'vod_name': it.get('name') or '',
                            'vod_pic': self._abs(it.get('pic') or ''),
                            'vod_remarks': '',
                        })
                else:
                    videos = self._parse_list(self.fetch_text(url))
                if videos:
                    break
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 12 else pg,
            'limit': 24,
            'total': len(videos),
        }

    def detailContent(self, ids):
        vid = str((ids or [''])[0])
        name, pic, desc, remarks, actor, director = vid, '', '', '', '', ''
        froms, urls = [], []
        try:
            html = ''
            for path in (
                '/index.php/vod/detail/id/%s.html' % vid,
                '/vod/detail/id/%s.html' % vid,
            ):
                html = self.fetch_text(self.siteUrl + path)
                if html and 'vod' in html.lower():
                    break
            tm = re.search(r'<title>([^<]+)</title>', html or '')
            if tm:
                name = re.sub(r'\s*[-_|].*$', '', tm.group(1)).strip() or name
            hm = re.search(r'<h1[^>]*>([\s\S]{2,80})</h1>', html or '')
            if hm:
                name = self._clean(hm.group(1)) or name
            pm = re.search(r'(?:og:image["\']\s+content=["\']|data-original=")([^"\']+)', html or '')
            if pm:
                pic = self._abs(pm.group(1))
            dm = re.search(r'og:description["\']\s+content=["\']([^"\']+)', html or '')
            if dm:
                desc = dm.group(1)
            am = re.search(r'主演[:：</span>]*([^<\n]+)', html or '')
            if am:
                actor = self._clean(am.group(1))
            dm2 = re.search(r'导演[:：</span>]*([^<\n]+)', html or '')
            if dm2:
                director = self._clean(dm2.group(1))
            flags = re.findall(
                r'class="[^"]*(?:play-title|title)[^"]*"[^>]*>([^<]{1,20})',
                html or '',
            )
            blocks = re.findall(
                r'(<ul[^>]*class="[^"]*(?:content_playlist|stui-content__playlist|playlist)[^"]*"[\s\S]*?</ul>)',
                html or '',
                re.I,
            )
            if not blocks:
                blocks = [html or '']
            for i, block in enumerate(blocks):
                parts = []
                for href, title in re.findall(
                    r'href="((?:/index\.php)?/vod/play/id/%s[^"]+\.html)"[^>]*>([^<]+)' % re.escape(vid),
                    block,
                ):
                    t = self._clean(title)
                    if t:
                        parts.append('%s$%s' % (t, self._abs(href)))
                if parts:
                    flag = flags[i] if i < len(flags) else ('线路%d' % (i + 1))
                    froms.append(self._clean(flag) or '线路%d' % (i + 1))
                    urls.append('#'.join(parts))
            if not urls:
                parts = []
                for href, title in re.findall(
                    r'href="((?:/index\.php)?/vod/play/id/%s[^"]+\.html)"[^>]*>([^<]+)' % re.escape(vid),
                    html or '',
                ):
                    t = self._clean(title)
                    if t:
                        parts.append('%s$%s' % (t, self._abs(href)))
                if parts:
                    froms.append('小蜜蜂')
                    urls.append('#'.join(parts))
        except Exception as e:
            print('获取详情失败: %s' % e)
        if not urls:
            froms = ['小蜜蜂']
            urls = ['播放$%s/index.php/vod/play/id/%s/sid/1/nid/1.html' % (self.siteUrl, vid)]
        return {'list': [{
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': remarks,
            'vod_actor': actor,
            'vod_director': director,
            'vod_content': (desc or '').strip(),
            'vod_play_from': '$$$'.join(froms),
            'vod_play_url': '$$$'.join(urls),
        }]}

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
            'Origin': self.siteUrl,
        }
        play = str(id or '')
        if self.isVideoFormat(play) and play.startswith('http'):
            return {'parse': 0, 'url': play, 'header': header}
        if not play.startswith('http'):
            play = self.siteUrl + (play if play.startswith('/') else '/' + play)
        html = self.fetch_text(play)
        pa = re.search(r'player_aaaa\s*=\s*(\{[\s\S]*?\})', html or '')
        if pa:
            raw = pa.group(1).replace("'", '"')
            um = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
            if um:
                u = um.group(1).replace('\\/', '/')
                p = 0 if self.isVideoFormat(u) else 1
                return {'parse': p, 'jx': '1' if p else '0', 'url': u, 'header': header}
        m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html or '')
        if m3:
            return {'parse': 0, 'url': m3.group(0).replace('\\/', '/'), 'header': header}
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
