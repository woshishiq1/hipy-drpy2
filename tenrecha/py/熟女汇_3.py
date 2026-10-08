# -*- coding: utf-8 -*-
"""熟女汇 - dr_py/CatVod Spider

站点： https://shunvhzuna.lol/
说明：基于站点公开 HTML 页面解析；详情/播放结构可能随站点改版变化。
"""
import json
import re
import sys
from html import unescape
from urllib.parse import quote, urljoin, urlparse

import requests

sys.path.append('..')
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    name = '熟女汇'
    HOST = 'https://shunvhzuna.lol'
    PAGE_SIZE = 30
    CATEGORIES = (
        ('亚洲情色', '374'), ('主播自拍', '375'), ('国产偷拍', '376'),
        ('无码系列', '377'), ('欧美性爱', '378'), ('熟女专区', '379'),
        ('强奸系列', '380'), ('巨乳系列', '381'), ('中文大全', '382'),
        ('制服学生', '383'), ('女同蕾丝', '384'), ('卡通动画', '385'),
        ('视频伦理', '386'), ('少女裸体', '387'), ('重口色情', '388'),
        ('人兽性交', '389'), ('福利姬', '473'), ('精品推荐', '224'),
        ('国产色情', '225'), ('主播直播', '227'), ('亚洲无码', '229'),
        ('亚洲有码', '231'), ('中文有码', '233'), ('巨乳美乳', '235'),
        ('人妻系列', '237'), ('强奸精品', '239'), ('欧美精品', '241'),
        ('萝莉少女', '243'), ('伦理三级', '245'), ('自拍偷拍', '249'),
        ('制服丝袜', '251'), ('口交颜射', '253'), ('日本精品', '255'),
        ('Cosplay', '257'), ('素人自拍', '259'), ('台湾辣妹', '261'),
        ('韩国御姐', '263'), ('唯美港姐', '265'), ('东南亚AV', '267'),
        ('欺辱凌辱', '269'), ('剧情介绍', '271'), ('多人多P', '273'),
        ('91探花', '275'), ('网红流出', '276'), ('野外露出', '277'),
        ('古装扮演', '278'), ('女优系列', '279'), ('可爱学生', '280'),
        ('风情旗袍', '281'), ('兽耳系列', '282'), ('瑜伽裤', '283'),
        ('闷骚护士', '284'), ('过膝袜', '285'), ('网曝门', '286'),
        ('传媒出品', '287'), ('女同性恋', '288'), ('男同性恋', '289'),
        ('恋腿狂魔', '290'), ('最新视频', 'newest'),
    )

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.host = self.HOST
        self.timeout = 20
        self.session = requests.Session()
        self.headers = {
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/120.0 Safari/537.36'),
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

    def getName(self):
        return self.name

    def init(self, extend=''):
        if isinstance(extend, dict):
            config = extend
        else:
            try:
                config = json.loads(extend or '{}')
            except Exception:
                config = {}
        host = str(config.get('host') or '').strip().rstrip('/')
        if host.startswith(('http://', 'https://')):
            self.host = host
        ua = str(config.get('userAgent') or config.get('ua') or '').strip()
        if ua:
            self.headers['User-Agent'] = ua
        cookie = str(config.get('cookie') or '').strip()
        if cookie:
            self.headers['Cookie'] = cookie
        return None

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    def isVideoFormat(self, url):
        value = str(url or '').lower()
        return any(x in value for x in ('.m3u8', '.mp4', '.m3u', '.mpd', '.flv', '.webm'))

    def manualVideoCheck(self):
        return False

    def _request(self, path, params=None, referer=None):
        url = path if str(path).startswith(('http://', 'https://')) else urljoin(self.host + '/', str(path).lstrip('/'))
        headers = dict(self.headers)
        headers['Referer'] = referer or self.host + '/'
        try:
            response = self.session.get(url, params=params, headers=headers,
                                        timeout=self.timeout, allow_redirects=True)
            response.encoding = response.apparent_encoding or 'utf-8'
            if response.status_code != 200:
                return None
            return response
        except Exception as error:
            self._log('request failed: %s' % error)
            return None

    def _log(self, message):
        try:
            self.log('[%s] %s' % (self.name, message))
        except Exception:
            print('[%s] %s' % (self.name, message))

    @staticmethod
    def _clean(value):
        value = unescape(str(value or ''))
        value = re.sub(r'<[^>]+>', ' ', value)
        return re.sub(r'\s+', ' ', value).strip()

    def _cards(self, html, base_url):
        result = []
        pattern = re.compile(
            r'<div[^>]+class=["\'][^"\']*video-item[^"\']*["\'][^>]*>(.*?)(?=<div[^>]+class=["\'][^"\']*video-item|</div>\s*</div>\s*</div>)',
            re.I | re.S)
        for block in pattern.findall(html or ''):
            link = re.search(r'<a[^>]+href=["\']([^"\']*/info/id/[^"\']+)["\'][^>]*', block, re.I)
            if not link:
                continue
            href = urljoin(base_url, link.group(1))
            title = re.search(r'<(?:h[1-6]|a)[^>]+title=["\']([^"\']+)', block, re.I)
            if not title:
                title = re.search(r'<h[1-6][^>]*>(.*?)</h[1-6]>', block, re.I | re.S)
            image = re.search(r'<img[^>]+(?:src|data-original|data-src)=["\']([^"\']+)', block, re.I)
            remark = re.search(r'<(?:time|span)[^>]*>(.*?)</(?:time|span)>', block, re.I | re.S)
            result.append({
                'vod_id': href,
                'vod_name': self._clean(title.group(1) if title else ''),
                'vod_pic': urljoin(base_url, image.group(1)) if image else '',
                'vod_remarks': self._clean(remark.group(1) if remark else ''),
            })
        # 兼容卡片嵌套层级差异
        if not result:
            for m in re.finditer(r'<a[^>]+href=["\']([^"\']*/info/id/[^"\']+)["\'][^>]*title=["\']([^"\']+)', html or '', re.I):
                href = urljoin(base_url, m.group(1))
                if not any(x['vod_id'] == href for x in result):
                    result.append({'vod_id': href, 'vod_name': self._clean(m.group(2)), 'vod_pic': '', 'vod_remarks': ''})
        return result

    def _section_cards(self, html, base_url, section_name):
        """首页包含多个分区；当分类路由失效时从首页分区兜底。"""
        if not html or not section_name:
            return []
        starts = list(re.finditer(r'<div[^>]+class=["\\\'][^"\\\']*video-section[^"\\\']*["\\\']', html, re.I))
        for pos, match in enumerate(starts):
            end = starts[pos + 1].start() if pos + 1 < len(starts) else len(html)
            section = html[match.start():end]
            heading = re.search(r'<(?:h[1-6]|div)[^>]+class=["\\\'][^"\\\']*section-title[^"\\\']*["\\\'][^>]*>(.*?)</', section, re.I | re.S)
            if heading and section_name in self._clean(heading.group(1)):
                return self._cards(section, base_url)
        return []

    def getDependence(self):
        return []

    def homeLayout(self):
        return 0

    def action(self, action):
        return {}

    def homeContent(self, filter=False):
        # CatVod 会把首页导航和首页视频分开请求；这里必须只返回导航字典。
        classes = [{'type_name': str(n), 'type_id': str(i)}
                   for n, i in self.CATEGORIES]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        response = self._request('/')
        videos = self._cards(response.text, response.url or self.host + '/') if response else []
        return {'list': videos}

    def _pagecount(self, html, current=1):
        """从分页链接提取总页数，站点格式为 /类别/页码.html。"""
        nums = re.findall(r'/(?:type/id/[^/]+|show/newest|lookup/[^/]+)(?:/L)?/([0-9]+)\.html', html or '', re.I)
        return max([int(x) for x in nums] + [int(current or 1)])

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = max(1, int(str(pg or 1)))
        # 当前站点首页展示的是有效内容分区，/type/id 路由在部分节点会返回 404。
        # 第 1 页优先走分类地址，失败后从首页对应分区提取。
        path = '/show/newest/1.html' if str(tid) == 'newest' else '/type/id/%s/1.html' % tid
        if page > 1:
            path = '/show/newest/%s.html' % page if str(tid) == 'newest' else '/type/id/%s/%s.html' % (tid, page)
        response = self._request(path)
        videos = self._cards(response.text, response.url) if response else []
        pagecount = self._pagecount(response.text, page) if response else page
        if not videos and page == 1:
            home = self._request('/')
            if home:
                names = dict(self.CATEGORIES)
                videos = self._section_cards(home.text, home.url, names.get(str(tid), ''))
        return {'list': videos, 'page': page, 'pagecount': pagecount,
                'limit': len(videos) or self.PAGE_SIZE, 'total': 0}

    def searchContent(self, key, quick=False, pg='1'):
        keyword = str(key or '').strip()
        page = max(1, int(str(pg or 1)))
        if not keyword:
            return {'list': [], 'page': page, 'pagecount': 0, 'limit': self.PAGE_SIZE, 'total': 0}
        path = '/lookup/%s/L/1.html' % quote(keyword, safe='')
        if page > 1:
            path = '/lookup/%s/L/%s.html' % (quote(keyword, safe=''), page)
        response = self._request(path)
        videos = self._cards(response.text, response.url) if response else []
        pagecount = self._pagecount(response.text, page) if response else page
        return {'list': videos, 'page': page, 'pagecount': pagecount,
                'limit': len(videos) or self.PAGE_SIZE, 'total': 0}

    def detailContent(self, ids):
        vod_id = str(ids[0] if isinstance(ids, (list, tuple)) and ids else ids or '').strip()
        detail_url = vod_id
        if re.search(r'/info/id/[^/]+\.html', detail_url, re.I):
            play_url = re.sub(r'/info/id/([^/]+)\.html', r'/play/id/\1.html', detail_url, flags=re.I)
        else:
            play_url = detail_url
        response = self._request(detail_url)
        if not response:
            return {'list': []}
        html = response.text
        # 详情页只提供“播放高清/4K”按钮，真正的 m3u8 位于 /play/id 页面。
        play_page = self._request(play_url, referer=response.url or detail_url)
        play_html = play_page.text if play_page else ''
        title_m = re.search(r'<title[^>]*>(.*?)</title>|<h1[^>]*>(.*?)</h1>', html, re.I | re.S)
        title = self._clean(next((x for x in (title_m.groups() if title_m else ()) if x), ''))
        pic_m = re.search(r'<img[^>]+(?:src|data-original|data-src)=["\']([^"\']+)', html, re.I)
        content_m = re.search(r'(?:剧情简介|影片简介|简介)[：:\s]*(.{0,1000})', html, re.I | re.S)
        episodes = []
        # 播放页使用 Aliplayer，地址写在 var playUrl = '...'; 中。
        play_urls = re.findall(r'\bplayUrl\s*=\s*[\'\"]([^\'\"]+)', play_html, re.I)
        if not play_urls:
            play_urls = re.findall(r'\bplayUrl\s*[:=]\s*[\'\"]([^\'\"]+)', play_html, re.I)
        if not play_urls:
            play_urls = re.findall(r'(?<![\w.-])https?://[^"\'\s<>]+(?:m3u8|mp4|m3u|mpd)(?:\?[^"\'\s<>]*)?', play_html, re.I)
        for index, url in enumerate(dict.fromkeys(play_urls)):
            episodes.append('正片%s$%s' % (index + 1, url))
        if not episodes:
            for index, href in enumerate(re.findall(r'<iframe[^>]+src=["\']([^"\']+)', play_html or html, re.I)):
                episodes.append('播放%s$%s' % (index + 1, urljoin(response.url, href)))
        vod = {'vod_id': vod_id, 'vod_name': title or vod_id,
               'vod_pic': urljoin(response.url, pic_m.group(1)) if pic_m else '',
               'vod_content': self._clean(content_m.group(1)) if content_m else '',
               'vod_play_from': '默认线路' if episodes else '',
               'vod_play_url': '#'.join(episodes)}
        return {'list': [vod]}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id or '').strip()
        # 详情中保存的是实际 m3u8；播放器需要 Referer 才能正常取分片。
        if self.isVideoFormat(url):
            return {'parse': 0, 'url': url,
                    'header': {'User-Agent': self.headers.get('User-Agent', ''),
                               'Referer': self.host + '/'}}
        # 兼容误传 /info/ 或 /play/ 地址：重新读取播放页提取 playUrl。
        if '/info/id/' in url:
            url = re.sub(r'/info/id/([^/]+)\.html', r'/play/id/\1.html', url)
        if '/play/id/' in url:
            page = self._request(url, referer=self.host + '/')
            if page:
                found = re.search(r'\bplayUrl\s*[:=]\s*[\'\"]([^\'\"]+)', page.text, re.I)
                if not found:
                    found = re.search(r'(?<![\w.-])(https?://[^"\'\s<>]+(?:m3u8|mp4|m3u|mpd)(?:\?[^"\'\s<>]*)?)', page.text, re.I)
                if found:
                    return {'parse': 0, 'url': found.group(1),
                            'header': {'User-Agent': self.headers.get('User-Agent', ''),
                                       'Referer': url}}
        return {'parse': 1, 'url': url, 'header': dict(self.headers)}
