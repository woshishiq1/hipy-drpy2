# -*- coding: utf-8 -*-
"""
萝莉聚合AV (luojubj.xyz) Python Spider
兼容 FongMi/TV (T3) 与 WebHomeTV / PeekPro (T4)
"""
import sys
import re
import base64
import time
from urllib.parse import urljoin, quote

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    import requests as rq
    class Spider:
        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            r = rq.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r


class Spider(Spider):
    HOST = 'https://www.luojubj.xyz'

    def getName(self):
        return "萝莉聚合AV"

    def init(self, extend=''):
        if isinstance(extend, list):
            self.extend = ''
        else:
            self.extend = extend or ''
        self.host = self.HOST
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.host + '/',
            'Cookie': 'verified=true',
        }
        self._home_cache = []
        self._home_cache_time = 0
        self._classes = None
        self._filters = None

    def _url(self, path):
        if not path:
            return self.host
        if path.startswith('http'):
            return path
        return self.host + path if path.startswith('/') else self.host + '/' + path

    def _fetch_html(self, url, timeout=20):
        try:
            rsp = self.fetch(url, headers=self.header, timeout=timeout)
            try:
                rsp.encoding = 'utf-8'
            except Exception:
                pass
            text = rsp.text
            if len(text) < 100 or 'var _s' not in text:
                return ''
            m = re.search(r'var\s+_s\s*=\s*"([^"]+)"', text)
            if m:
                return base64.b64decode(m.group(1)).decode('utf-8')
            return text
        except Exception:
            return ''

    def _parse_videos(self, html):
        """解析视频卡片（兼容列表页和搜索页两种结构）"""
        videos = []
        seen = set()
        items = re.findall(
            r'<a[^>]*href=["\'](/news/(\d+)\.html)["\'][^>]*>(.*?)</a>',
            html, re.S
        )
        for href, vid, content in items:
            if vid in seen:
                continue
            if 'data-src' not in content:
                continue
            seen.add(vid)

            # 提取图片
            img = re.search(r'data-src=["\']([^"\']+)["\']', content)
            pic = img.group(1) if img else ''
            if pic and not pic.startswith('http'):
                pic = self.host + pic

            # 提取标题：优先 h3.v-title（搜索页），其次 alt（列表页）
            title = ''
            h3_match = re.search(r'<h3[^>]*class=["\'][^"\']*v-title[^"\']*["\'][^>]*>(.*?)</h3>', content, re.S)
            if h3_match:
                title = re.sub(r'<[^>]+>', '', h3_match.group(1)).strip()
            if not title:
                alt = re.search(r'alt=["\']([^"\']+)["\']', content)
                if alt and alt.group(1) != 'video':
                    title = alt.group(1)
            if not title:
                text_only = re.sub(r'<[^>]+>', '', content).strip()
                title = text_only[:50] if text_only else ''

            videos.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': '',
            })
        return videos

    def _parse_detail(self, html, vid):
        title = ''
        title_match = re.search(r'<title>([^<]+)</title>', html)
        if title_match:
            title = title_match.group(1).replace(' - 播放页', '').strip()

        pic = ''
        pic_match = re.search(r'<img[^>]*data-src=["\']([^"\']+)["\'][^>]*alt=', html)
        if not pic_match:
            pic_match = re.search(r'<img[^>]*src=["\']([^"\']+)["\'][^>]*alt=', html)
        if pic_match:
            pic = pic_match.group(1)
            if not pic.startswith('http'):
                pic = self.host + pic

        m3u8 = ''
        src_match = re.search(r'<source[^>]*src=["\']([^"\']+\.m3u8)["\']', html)
        if src_match:
            m3u8 = src_match.group(1)
        if not m3u8:
            m3u8_match = re.search(r'm3u8=["\']([^"\']+\.m3u8)["\']', html)
            if m3u8_match:
                m3u8 = m3u8_match.group(1)

        content = ''
        desc_match = re.search(r'<div[^>]*class=["\'][^"\']*desc[^"\']*["\'][^>]*>(.*?)</div>', html, re.S)
        if desc_match:
            content = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()

        play_url = f"播放${m3u8}" if m3u8 else ''

        return {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': pic,
            'type_name': '',
            'vod_year': '',
            'vod_area': '',
            'vod_remarks': '',
            'vod_actor': '',
            'vod_director': '',
            'vod_content': content[:500] if content else '',
            'vod_play_from': '默认线路',
            'vod_play_url': play_url,
        }

    def _get_pagecount(self, html):
        pages = re.findall(r'[?&]page=(\d+)', html)
        if pages:
            return max([int(p) for p in pages if p.isdigit()])
        return 1

    # ========== 分类与筛选器 ==========
    def _load_classes(self):
        if self._classes is not None:
            return self._classes

        classes = [
            {'type_id': '番号', 'type_name': '番号视频'},
            {'type_id': '国产', 'type_name': '国产视频'},
            {'type_id': '排行', 'type_name': '视频排行榜'},
            {'type_id': '专题', 'type_name': '热门专题'},
        ]

        filters = {
            '番号': [{
                'key': 'cat',
                'name': '子分类',
                'value': [
                    {'n': '中文字幕', 'v': '中文字幕'},
                    {'n': '美乳巨乳', 'v': '美乳巨乳'},
                    {'n': '童颜巨乳', 'v': '童颜巨乳'},
                    {'n': '强奸乱伦', 'v': '强奸乱伦'},
                    {'n': '邻家人妻', 'v': '邻家人妻'},
                    {'n': '萝莉少女', 'v': '萝莉少女'},
                    {'n': '制服丝袜', 'v': '制服丝袜'},
                    {'n': '亚洲情色', 'v': '亚洲情色'},
                    {'n': '日本有码', 'v': '日本有码'},
                    {'n': '日韩无码', 'v': '日韩无码'},
                    {'n': '成人动漫', 'v': '成人动漫'},
                    {'n': '重口色情', 'v': '重口色情'},
                ]
            }],
            '国产': [{
                'key': 'cat',
                'name': '子分类',
                'value': [
                    {'n': '网红主播', 'v': '网红主播'},
                    {'n': '国产自拍', 'v': '国产自拍'},
                    {'n': '国产情色', 'v': '国产情色'},
                    {'n': '吃瓜爆料', 'v': '吃瓜爆料'},
                    {'n': '麻豆传媒', 'v': '麻豆传媒'},
                    {'n': '萝莉少女', 'v': '萝莉少女'},
                    {'n': '三级伦理', 'v': '三级伦理'},
                    {'n': '国产丝袜', 'v': '国产丝袜'},
                ]
            }],
            '排行': [{
                'key': 'type',
                'name': '榜单类型',
                'value': [
                    {'n': '国产榜', 'v': 'guochan'},
                    {'n': '番号榜', 'v': 'fanhao'},
                ]
            }, {
                'key': 'time',
                'name': '时间',
                'value': [
                    {'n': '日榜', 'v': 'daily'},
                    {'n': '周榜', 'v': 'weekly'},
                    {'n': '月榜', 'v': 'monthly'},
                ]
            }],
            '专题': [{
                'key': 'region',
                'name': '视频区域',
                'value': [
                    {'n': '国产视频热门', 'v': '国产'},
                    {'n': '番号视频热门', 'v': '番号'},
                ]
            }, {
                'key': 'cat',
                'name': '专题',
                'value': [
                    {'n': '潮吹喷水', 'v': '潮吹喷水'},
                    {'n': '糖心vlog', 'v': '糖心vlog'},
                    {'n': '后入', 'v': '后入'},
                    {'n': '黑丝', 'v': '黑丝'},
                    {'n': '水果派', 'v': '水果派'},
                    {'n': '口爆吞精', 'v': '口爆吞精'},
                    {'n': '小宝寻花', 'v': '小宝寻花'},
                    {'n': '大学生', 'v': '大学生'},
                    {'n': '童颜巨乳', 'v': '童颜巨乳'},
                    {'n': '玩偶姐姐', 'v': '玩偶姐姐'},
                    {'n': '制服', 'v': '制服'},
                ]
            }],
        }

        self._classes = classes
        self._filters = filters
        return classes

    def _get_filters(self):
        if self._filters is None:
            self._load_classes()
        return self._filters or {}

    # ========== 首页 ==========
    def homeContent(self, filter):
        return {
            'class': self._load_classes(),
            'filters': self._get_filters(),
        }

    def homeVideoContent(self):
        now = int(time.time())
        if self._home_cache and now - self._home_cache_time < 300:
            return {'list': self._home_cache[:72]}

        videos = []
        seen = set()

        picks = [
            ('番号', '中文字幕'),
            ('国产', '麻豆传媒'),
            ('番号', '日韩无码'),
        ]
        for reg, cat in picks:
            if len(videos) >= 72:
                break
            try:
                url = f"{self.host}/video-list.html?reg={quote(reg, safe='')}&category={quote(cat, safe='')}&page=1"
                html = self._fetch_html(url, timeout=12)
                items = self._parse_videos(html)
                for v in items:
                    vid = v.get('vod_id')
                    if vid and vid not in seen:
                        seen.add(vid)
                        videos.append(v)
                    if len(videos) >= 72:
                        break
            except Exception:
                continue

        if len(videos) < 24:
            try:
                html = self._fetch_html(self.host + '/?site=lltdh&refer_host=obes.llt2-2.top', timeout=12)
                items = self._parse_videos(html)
                for v in items:
                    vid = v.get('vod_id')
                    if vid and vid not in seen:
                        seen.add(vid)
                        videos.append(v)
                    if len(videos) >= 72:
                        break
            except Exception:
                pass

        self._home_cache = videos[:72]
        self._home_cache_time = now
        return {'list': self._home_cache}

    # ========== 分类列表 ==========
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        ext = {}
        if extend:
            if isinstance(extend, dict):
                ext = extend
            elif isinstance(extend, str):
                try:
                    ext = json.loads(extend)
                except Exception:
                    ext = {}

        if tid == '排行':
            ttype = ext.get('type', 'guochan')
            ttime = ext.get('time', 'daily')
            url = f"{self.host}/top.html?type={quote(ttype, safe='')}&time={quote(ttime, safe='')}"
            if pg > 1:
                url += f"&page={pg}"
            html = self._fetch_html(url, timeout=20)

        elif tid == '专题':
            keyword = ext.get('cat', '潮吹喷水')
            region = ext.get('region', '国产')
            url = f"{self.host}/search.html?q={quote(keyword, safe='')}&region={quote(region, safe='')}&order=latest"
            if pg > 1:
                url += f"&page={pg}"
            html = self._fetch_html(url, timeout=20)

        else:
            reg = tid if tid in ('番号', '国产') else '番号'
            cat = ext.get('cat', '')
            if not cat:
                cat = '中文字幕' if reg == '番号' else '麻豆传媒'
            url = f"{self.host}/video-list.html?reg={quote(reg, safe='')}&category={quote(cat, safe='')}&page={pg}"
            html = self._fetch_html(url, timeout=20)

        if not html:
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 20, 'total': 0}

        videos = self._parse_videos(html)
        pagecount = self._get_pagecount(html)
        if not pagecount and videos:
            pagecount = 1

        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount or 1,
            'limit': 20,
            'total': len(videos) * (pagecount or 1),
        }

    # ========== 详情页 ==========
    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        vid = ids[0]

        url = f"{self.host}/news/{vid}.html"
        html = self._fetch_html(url, timeout=20)

        if not html:
            return {'list': []}

        vod = self._parse_detail(html, vid)
        return {'list': [vod]}

    # ========== 搜索 ==========
    def searchContent(self, key, quick, pg='1'):
        pg = int(pg or 1)
        url = f"{self.host}/search.html?q={quote(key, safe='')}"
        if pg > 1:
            url += f"&page={pg}"

        html = self._fetch_html(url, timeout=20)
        videos = self._parse_videos(html)

        pagecount = self._get_pagecount(html)
        if not pagecount and videos:
            pagecount = 1

        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount or 1,
            'limit': 20,
            'total': len(videos) * (pagecount or 1),
        }

    # ========== 播放解析 ==========
    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {'parse': 1, 'playUrl': '', 'url': ''}

        url = id if str(id).startswith('http') else self._url(id)

        if '.m3u8' in url:
            return {
                'parse': 0,
                'playUrl': '',
                'url': url,
                'header': {
                    'User-Agent': self.header['User-Agent'],
                    'Referer': self.host + '/',
                },
                'format': 'application/x-mpegURL',
            }

        if '.mp4' in url:
            return {
                'parse': 0,
                'playUrl': '',
                'url': url,
                'header': {
                    'User-Agent': self.header['User-Agent'],
                    'Referer': self.host + '/',
                },
            }

        return {'parse': 1, 'playUrl': '', 'url': url, 'header': self.header}

    def localProxy(self, param):
        return [200, 'video/MP2T', b'', '']

    def destroy(self):
        pass

    def close(self):
        self.destroy()
