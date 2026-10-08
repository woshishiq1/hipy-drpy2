# -*- coding: utf-8 -*-
import html
import re
import urllib.parse
import requests
from base.spider import Spider


class Spider(Spider):
    name = '777hub'
    base_url = 'https://leaves-fall-gracefully.777hub129.xyz/label/sort999'
    ua = 'Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36'
    classes = [
        {'type_id': str(i), 'type_name': n} for i, n in [
            (20, '国产自拍'), (21, '网红主播'), (22, '国产传媒'), (23, '人妻熟女'),
            (24, '探花系列'), (25, '日本无码'), (26, '美乳巨乳'), (27, '强制侵犯'),
            (28, '制服诱惑'), (29, '绝色佳人'), (30, '风俗泡泡浴'), (31, '家庭乱伦'),
            (32, 'AV解说'), (33, 'A V 解说'), (34, '三级电影'), (35, '少女萝莉'),
            (36, 'SM调教'), (37, '绝顶潮吹'), (38, '魔镜系列'), (39, '时间停止'),
            (40, '催眠洗脑'), (41, '漫改系列'), (42, '电车痴汉'), (43, '淫欲痴女'),
            (44, 'AI换脸'), (45, '网曝门'), (46, 'TS专区'), (47, '女性向系列'),
            (48, '女同性恋'), (49, '男同性恋'), (50, '欧美精品'), (51, '日本动漫'),
            (52, '3D动漫'), (53, '韩国主播'), (54, '泰国风情'), (55, 'OnlyFans')]]

    def init(self, extend=''):
        return None

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        return any(x in str(url or '').lower() for x in ('.m3u8', '.mp4', '.ts'))

    def manualVideoCheck(self):
        return False

    def _headers(self, referer=None):
        return {'User-Agent': self.ua, 'Referer': referer or self.base_url + '/'}

    def _fetch_html(self, url, params=None):
        if params:
            url += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
        try:
            response = self.fetch(url, headers=self._headers(), timeout=20)
            text = getattr(response, 'text', '') if response else ''
            if text:
                return text
        except Exception as e:
            print('[777hub] fetch error:', e)
        return ''

    def _absolute(self, value):
        value = html.unescape(str(value or '').strip())
        if value.startswith('http://') or value.startswith('https://'):
            return value
        if value.startswith('/label/sort999/'):
            return 'https://leaves-fall-gracefully.777hub129.xyz' + value
        return self.base_url.rstrip('/') + '/' + value.lstrip('/')

    def _clean(self, value):
        value = html.unescape(str(value or ''))
        value = re.sub(r'777午夜精品在线影院|777成人网', '', value, flags=re.I)
        return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', value)).strip(' -_|，,')

    def _cards(self, page):
        result, seen = [], set()
        for match in re.finditer(r'<a\b[^>]*href=["\']([^"\']*/vod/detail/id/(\d+)\.html)["\'][^>]*>', page or '', re.I):
            href, vid = match.groups()
            url = self._absolute(href)
            if url in seen:
                continue
            start = max(0, match.start() - 300)
            end = min(len(page), match.end() + 1800)
            block = page[start:end]
            title = self._first(block, r'(?:alt|title)=["\']([^"\']+)')
            if not title:
                title = self._clean(block)
            pic = self._first(block, r'(?:data-src|data-original|src)=["\']([^"\']+)')
            remark = self._first(block, r'<span[^>]+class=["\'][^"\']*type[^"\']*["\'][^>]*>(.*?)</span>')
            seen.add(url)
            result.append({'vod_id': url, 'vod_name': title or vid, 'vod_pic': self._absolute(pic), 'vod_remarks': remark})
        return result

    def homeContent(self, filter=False):
        return {'class': self.classes, 'filters': {}}

    def homeVideoContent(self):
        return {'list': self._cards(self._fetch_html(self.base_url + '/'))}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = max(1, self._int(pg, 1))
        path = '/index.php/vod/type/id/%s.html' % str(tid or '20')
        if page > 1:
            path = '/index.php/vod/type/id/%s/page/%d.html' % (str(tid or '20'), page)
        data = self._fetch_html(self._absolute(path))
        items = self._cards(data)
        return {'list': items, 'page': page, 'pagecount': self._page_count(data), 'limit': len(items) or 24, 'total': 0}

    def detailContent(self, ids):
        value = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        url = self._absolute(value)
        page = self._fetch_html(url)
        if not page:
            return {'list': []}
        title = self._first(page, r'<h1[^>]*>(.*?)</h1>') or self._first(page, r'<title[^>]*>(.*?)</title>')
        pic = self._first(page, r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)')
        desc = self._first(page, r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)')
        plays = []
        seen_urls = set()
        for href, text in re.findall(r'<a\b[^>]*href=["\']([^"\']*vod/play[^"\']+)["\'][^>]*>(.*?)</a>', page, re.I | re.S):
            label = self._clean(text) or '播放'
            play_url = self._absolute(href)
            if play_url not in seen_urls:
                seen_urls.add(play_url)
                plays.append((label, play_url))
        if not plays:
            plays = [('播放地址', self._absolute('/index.php/vod/play/id/%s/sid/1/nid/1.html' % self._id(value)))]
        return {'list': [{'vod_id': url, 'vod_name': self._clean(title), 'vod_pic': self._absolute(pic), 'vod_content': self._clean(desc), 'vod_play_from': '$$$'.join(x[0] for x in plays), 'vod_play_url': '$$$'.join(x[0] + '$' + x[1] for x in plays)}]}

    def searchContent(self, key, quick=False, pg='1'):
        page = max(1, self._int(pg, 1))
        data = self._fetch_html(self._absolute('/index.php/vod/search.html'), {'wd': str(key or ''), 'page': page})
        items = self._cards(data)
        return {'list': items, 'page': page, 'pagecount': self._page_count(data), 'limit': len(items) or 24, 'total': 0}

    def playerContent(self, flag, id, vipFlags=None):
        value = str(id or '')
        if self.isVideoFormat(value):
            return {'parse': 0, 'url': value, 'header': self._headers()}
        # 尝试从播放页提取真实 m3u8
        page = self._fetch_html(value)
        if page:
            # DPlayer 格式
            m = re.search(r'url:\s*["\']\s*([^"\']+\.m3u8[^"\']*)', page, re.I | re.S)
            if not m:
                m = re.search(r'(?:hlsUrl|playurl|src|file)\s*[:=]\s*["\']\s*([^"\']+\.m3u8[^"\']*)', page, re.I | re.S)
            if m:
                m3u8 = m.group(1).strip()
                if m3u8.startswith('//'):
                    m3u8 = 'https:' + m3u8
                if m3u8.startswith('http'):
                    return {'parse': 0, 'url': m3u8, 'header': self._headers(value)}
        return {'parse': 1, 'url': value, 'header': self._headers(value)}

    def _first(self, text, pattern):
        match = re.search(pattern, text or '', re.I | re.S)
        return self._clean(match.group(1)) if match else ''

    def _id(self, value):
        match = re.search(r'/id/(\d+)', str(value or ''))
        return match.group(1) if match else str(value or '')

    def _page_count(self, page):
        nums = [int(x) for x in re.findall(r'(?:page|页)[=/"\'](\d+)', page or '', re.I)]
        return max(nums or [1])

    def _int(self, value, default=1):
        try:
            return int(value)
        except Exception:
            return default
