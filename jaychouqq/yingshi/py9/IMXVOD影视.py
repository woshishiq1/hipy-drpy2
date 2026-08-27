# -*- coding: utf-8 -*-
import os
import re
import sys
import json
import ssl
import base64
from urllib.parse import quote, unquote
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def fetch(self, url, headers=None, timeout=20, verify=False):
            raise NotImplementedError

# ---------------- 配置 ----------------
DEFAULT_HOST = 'https://imxvod.com'
UA = 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
HEADERS = {
    'User-Agent': UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': DEFAULT_HOST + '/',
}


PARENT_CATS = [
    ('dianying', '电影'),
    ('dianshiju', '电视剧'),
    ('zongyi', '综艺'),
    ('dongman', '动漫'),
    ('duanju', '短剧'),
    ('dianyingjieshuo', '电影解说'),   
    ('tiyu', '体育'),
    ('aimanju', 'AI漫剧'),
]


SUBCATS = {
    'dianying': ['动作片', '喜剧片', '爱情片', '科幻片', '恐怖片', '战争片', '剧情片',
                 '动画片', '悬疑片', '纪录片', '奇幻片', '灾难片'],
    'dianshiju': ['国产剧', '香港剧', '台湾剧', '日本剧', '韩国剧', '欧美剧', '海外剧'],
    'zongyi': ['大陆综艺', '港台综艺', '日韩综艺', '欧美综艺'],
    'dongman': ['国产动漫', '日韩动漫', '欧美动漫', '港台动漫'],
    'duanju': [],
    'dianyingjieshuo': [],
    'TVlive': [],
    'tiyu': [],
    'aimanju': [],
}

# 地区选项 (全站统一, 与 vodshow 页面一致)
AREA_OPTIONS = ['中国', '大陆', '美国', '香港', '台湾', '日本', '韩国', '英国', '法国',
                '德国', '意大利', '西班牙', '印度', '泰国', '马来西亚', '新加坡',
                '越南', '菲律宾', '俄罗斯', '加拿大', '巴西', '澳大利亚', '印度尼西亚']

# 语言选项 (全站统一)
LANG_OPTIONS = ['国语', '普通话', '粤语', '英语', '俄语', '韩语', '日语', '法语', '德语', '其它']

# 年份选项 (全站统一, 取最近15年)
YEAR_OPTIONS = ['2026', '2025', '2024', '2023', '2022', '2021', '2020', '2019',
                '2018', '2017', '2016', '2015', '2014', '2013', '2012']

# 排序选项 (全站统一)
BY_OPTIONS = [('更新排序', 'time'), ('热门排序', 'hits'), ('评分排序', 'score')]


class Spider(BaseSpider):
    def __init__(self):
        self.name = 'IMXVOD影视'
        self.host = DEFAULT_HOST
        self._headers = dict(HEADERS)
        self._ssl_ctx = None
        try:
            # OK影视(FongMi/Chaquopy) 环境常缺 CA 证书, 构造器内 ssl 失败不能整体崩溃
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            self._ssl_ctx = ctx
        except Exception:
            self._ssl_ctx = None

    # ======================== 基础接口 ========================

    def getName(self):
        return self.name

    def init(self, extend="", *args):
        """TVBox / OK影视 引擎初始化入口(必须实现, 缺失则源加载失败)"""
        return self

    @staticmethod
    def isVideoFormat(url):
        if not url:
            return False
        u = url.lower()
        return any(x in u for x in ('.m3u8', '.mp4', '.flv', '.mkv', '.ts', 'm3u8?', '.mpd'))

    def manualVideoCheck(self):
        return False

    def liveContent(self, url):
        """直播源: 本源为点播站, 返回空。OK影视 桥接层会调用此方法。"""
        return ''

    def action(self, action):
        """自定义动作: 未使用。OK影视 桥接层会调用此方法。"""
        return '{}'

    def destroy(self):
        pass

    def localProxy(self, param):
        return None

    # ======================== 工具方法 ========================

    @staticmethod
    def _decode(raw):
        if isinstance(raw, str):
            return raw
        for enc in ('utf-8', 'gbk', 'gb18030'):
            try:
                return raw.decode(enc)
            except Exception:
                continue
        return raw.decode('utf-8', 'ignore')

    def _fetch(self, url, referer=None, timeout=25):
        headers = dict(self._headers)
        headers['Accept'] = '*/*'
        if referer:
            headers['Referer'] = referer
        req = Request(url, headers=headers)
        try:
            with urlopen(req, timeout=timeout, context=self._ssl_ctx) as r:
                return self._decode(r.read())
        except Exception as e:
            self._log('fetch 失败 %s -> %s' % (url[:90], e))
            return ''

    def _log(self, msg):
        try:
            print('[%s] %s' % (self.name, msg))
        except Exception:
            pass

    def _abs(self, path):
        if not path:
            return ''
        if path.startswith('http://') or path.startswith('https://'):
            return path
        if path.startswith('//'):
            return 'https:' + path
        if path.startswith('/'):
            return self.host + path
        return self.host + '/' + path

    @staticmethod
    def _clean(text):
        if not text:
            return ''
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'[\u200b-\u200f\ufe00-\ufe0f]', '', text)
        return re.sub(r'\s+', ' ', text).strip()

    @staticmethod
    def _img_src(html_fragment):
        """从 HTML 片段中提取图片地址, 优先 data-src/data-original(懒加载)"""
        if not html_fragment:
            return ''
        for attr in ('data-src', 'data-original', 'src'):
            m = re.search(attr + r'="([^"]+)"', html_fragment, re.I)
            if m:
                val = m.group(1)
                if 'load.gif' not in val and 'placeholder' not in val:
                    return val
        return ''

    # ======================== URL 构建 ========================

    def _build_vodshow_url(self, slug, page=1, area='', by='', cls='', lang='', year=''):
        """构建 vodshow 分类列表 URL (12 段)
        /vodshow/{slug}-{area}-{by}-{class}-{lang}-------{page}---{year}.html
        索引: 0=slug 1=area 2=by 3=class 4=lang 5-7=空 8=page 9-10=空 11=year
        """
        parts = [
            slug,
            area,
            by,
            cls,
            lang,
            '', '', '',
            str(page) if page else '1',
            '', '',
            year,
        ]
        encoded = '-'.join(quote(p, safe='') if p else '' for p in parts)
        return '%s/vodshow/%s.html' % (self.host, encoded)

    def _build_search_url(self, wd, page=1):
        """构建搜索 URL (14 段): /vodsearch/{wd}----------{page}---.html"""
        parts = [quote(wd, safe='')] + [''] * 9 + [str(page) if page else '1'] + [''] * 3
        return '%s/vodsearch/%s.html' % (self.host, '-'.join(parts))

    # ======================== 列表解析 ========================

    def _parse_list(self, html):
        """解析 vodshow / vodsearch 页面的视频列表
        支持两种容器结构:
        - 分类页: <div class="module-item"> ... <img data-src="{pic}">
        - 搜索页: <div class="module-search-item"> ... <img data-src="{pic}">
        标题优先级: module-item-titlebox / h3 a / img alt(均为干净标题),
        规避 vodplay 链接 title 的"立刻播放/立即播放"前缀。
        """
        items = []
        seen = set()
        # 以 module-item / module-search-item 为容器逐块解析
        for m in re.finditer(
                r'<div[^>]*class="[^"]*module-(?:item|search-item)[^"]*"[^>]*>([\s\S]*?)</div>\s*(?:</div>)?',
                html, re.S):
            block = m.group(1)
            # 定位视频 id (优先 voddetail 链接, 其次 vodplay 链接)
            vid = ''
            m_detail = re.search(r'href="/voddetail/(\d+)\.html"', block)
            m_play = re.search(r'href="/vodplay/(\d+)-', block)
            if m_detail:
                vid = m_detail.group(1)
            elif m_play:
                vid = m_play.group(1)
            if not vid or vid in seen:
                continue
            # 标题: 干净标题优先
            title = ''
            t_m = re.search(r'class="[^"]*module-item-title[^"]*"[^>]*>(.*?)</a>', block, re.S)
            if t_m:
                title = self._clean(t_m.group(1))
            if not title:
                h_m = re.search(r'<h3[^>]*>\s*<a[^>]*title="([^"]*)"', block, re.S)
                if h_m:
                    title = h_m.group(1).strip()
            if not title:
                a_m = re.search(r'<a[^>]*href="/voddetail/\d+\.html"[^>]*title="([^"]*)"', block)
                if a_m:
                    title = a_m.group(1).strip()
            if not title:
                alt_m = re.search(r'<img[^>]*alt="([^"]*)"', block)
                title = alt_m.group(1).strip() if alt_m else ''
            if not title:
                continue
            # 清理"立即播放/立刻播放"等前缀
            title = re.sub(r'^(?:立刻播放|立即播放)\s*', '', title).strip()
            pic = self._img_src(block)
            # 备注(更新状态/清晰度)
            remarks = ''
            r_m = re.search(r'class="[^"]*video-serial[^"]*"[^>]*>(.*?)</a>', block, re.S)
            if r_m:
                remarks = self._clean(r_m.group(1))
            if not remarks:
                r_m = re.search(r'class="[^"]*module-item-text[^"]*"[^>]*>(.*?)</', block, re.S)
                if r_m:
                    remarks = self._clean(r_m.group(1))
            seen.add(vid)
            items.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': self._abs(pic) if pic else '',
                'vod_remarks': remarks or '',
            })

        # 兜底: 容器正则没匹配到时, 直接抓所有 vodplay 链接
        if len(items) < 5:
            items = []
            seen = set()
            for link_m in re.finditer(r'<a[^>]*href="(/vodplay/(\d+)[^"]*\.html)"[^>]*title="([^"]*)"', html):
                vid = link_m.group(2)
                title = link_m.group(3).strip()
                if vid in seen or not title:
                    continue
                seen.add(vid)
                title = re.sub(r'^(?:立刻播放|立即播放)\s*', '', title).strip()
                ctx = html[max(0, link_m.start() - 300):link_m.end() + 100]
                pic = self._img_src(ctx)
                items.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': self._abs(pic) if pic else '',
                    'vod_remarks': '',
                })
        return items

    # ======================== 首页 ========================

    def homeContent(self, filter=False):
        """首页推荐 + 全部分类 + 筛选器"""
        classes = [{'type_id': slug, 'type_name': name} for slug, name in PARENT_CATS]
        filters = {}
        for slug, _ in PARENT_CATS:
            filters[slug] = self._build_filters(slug)

        html = self._fetch(self.host + '/', referer=self.host + '/')
        items = self._parse_list(html) if html else []
        return {
            'class': classes,
            'list': items,
            'filters': filters,
            'parse': 0,
            'jx': 0,
        }

    def homeVideoContent(self):
        """首页推荐(部分外壳独立调用)"""
        html = self._fetch(self.host + '/', referer=self.host + '/')
        return {'list': self._parse_list(html) if html else [], 'parse': 0, 'jx': 0}

    def _build_filters(self, slug):
        """为指定父分类构建完整筛选器列表"""
        filters = []

        # 1. 子分类(类型)维度
        subs = SUBCATS.get(slug, [])
        if subs:
            sub_values = [{'n': '全部', 'v': ''}]
            for sub_name in subs:
                sub_values.append({'n': sub_name, 'v': sub_name})
            filters.append({'key': 'class', 'name': '类型', 'value': sub_values})

        # 2. 地区
        area_values = [{'n': '全部', 'v': ''}]
        for area in AREA_OPTIONS:
            area_values.append({'n': area, 'v': area})
        filters.append({'key': 'area', 'name': '地区', 'value': area_values})

        # 3. 排序
        by_values = [{'n': '全部', 'v': ''}]
        for n, v in BY_OPTIONS:
            by_values.append({'n': n, 'v': v})
        filters.append({'key': 'by', 'name': '排序', 'value': by_values})

        # 4. 语言
        lang_values = [{'n': '全部', 'v': ''}]
        for lang in LANG_OPTIONS:
            lang_values.append({'n': lang, 'v': lang})
        filters.append({'key': 'lang', 'name': '语言', 'value': lang_values})

        # 5. 年份
        year_values = [{'n': '全部', 'v': ''}]
        for year in YEAR_OPTIONS:
            year_values.append({'n': year, 'v': year})
        filters.append({'key': 'year', 'name': '年份', 'value': year_values})

        return filters

    # ======================== 分类列表 ========================

    def categoryContent(self, tid, pg, filter=False, extend=""):
        """分类列表 + 分页 + 筛选器联动
        extend 可能是 dict(TVBox/影视仓) 或 JSON 字符串(个别外壳), 需兼容。
        """
        if isinstance(extend, str):
            try:
                extend = json.loads(extend) if extend.strip().startswith('{') else {}
            except Exception:
                extend = {}
        ext = extend or {}
        page = int(pg) if str(pg).isdigit() else 1
        url = self._build_vodshow_url(
            slug=tid,
            page=page,
            area=ext.get('area', ''),
            by=ext.get('by', ''),
            cls=ext.get('class', ''),
            lang=ext.get('lang', ''),
            year=ext.get('year', ''),
        )
        html = self._fetch(url, referer=self.host + '/')
        items = self._parse_list(html) if html else []

        # 从页面提取总页数
        pagecount = 1
        if html:
            nums = re.findall(r'/vodshow/%s--------(\d+)---\.html' % re.escape(tid), html)
            if nums:
                try:
                    pagecount = max(int(n) for n in nums)
                except Exception:
                    pagecount = 1
            else:
                m = re.search(r'pagecount[=:]\s*["\']?(\d+)', html)
                if m:
                    pagecount = int(m.group(1))

        return {
            'page': page,
            'pagecount': pagecount,
            'limit': 36,
            'total': pagecount * 36,
            'list': items,
            'parse': 0,
            'jx': 0,
        }

    # ======================== 详情 ========================

    def detailContent(self, ids):
        """影片详情: 标题/封面/简介/导演/主演/年份 + 多节点线路选集
        ids 可能是 list(标准) 或字符串(个别外壳), 需兼容。
        """
        result = {'list': []}
        if isinstance(ids, str):
            ids = [ids]
        for vid in ids:
            try:
                html = self._fetch('%s/voddetail/%s.html' % (self.host, vid),
                                   referer=self.host + '/')
                if not html:
                    continue
                vod = self._parse_detail(html, vid)
                result['list'].append(vod)
            except Exception as e:
                self._log('detail 失败 %s -> %s' % (vid, e))
                continue
        return result

    def _parse_detail(self, html, vid):
        """解析详情页 (MXOne 模板)"""
        # 标题
        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if m:
            title = self._clean(m.group(1))
        if not title:
            m = re.search(r'<meta property="og:title" content="([^"]*)"', html)
            title = m.group(1).split('_')[0].strip() if m else ''

        # 封面 (懒加载 data-src)
        pic = ''
        m = re.search(r'<div[^>]*class="[^"]*video-cover[^"]*"[^>]*>([\s\S]*?)</div>', html)
        if m:
            pic = self._img_src(m.group(1))
        if not pic:
            m = re.search(r'<meta property="og:image" content="([^"]*)"', html)
            if m:
                pic = m.group(1)

        # 元数据: video-info-items 块
        # <div class="video-info-items"><span class="video-info-itemtitle">导演：</span>
        #   <div class="video-info-item video-info-actor">...<a>名字</a>...</div></div>
        director = ''
        actor = ''
        area = ''
        lang = ''
        year = ''
        remarks = ''
        type_name = ''
        for block in re.finditer(
                r'<div[^>]*class="[^"]*video-info-items[^"]*"[^>]*>([\s\S]*?)</div>\s*</div>',
                html, re.S):
            seg = block.group(1)
            t_m = re.search(r'class="[^"]*video-info-itemtitle[^"]*"[^>]*>([^<]*)<', seg)
            if not t_m:
                continue
            label = t_m.group(1).strip()
            val = self._clean(re.sub(r'<span[^>]*>.*?</span>', '', seg))
            val = re.sub(r'^[^：:]*[：:]\s*', '', val)
            val = val.strip('/ ')
            if not val:
                continue
            if '导演' in label:
                director = val
            elif '主演' in label or '演员' in label:
                actor = val
            elif '地区' in label:
                area = val
            elif '语言' in label:
                lang = val
            elif '年份' in label:
                year = val
            elif '状态' in label or '更新' in label:
                remarks = val
            elif '类型' in label or '分类' in label:
                type_name = val

        # 简介
        desc = ''
        m = re.search(r'<div[^>]*class="[^"]*video-info-content[^"]*"[^>]*>([\s\S]*?)</div>', html)
        if m:
            desc = self._clean(m.group(1))
        if not desc:
            m = re.search(r'<meta name="description" content="([^"]*)"', html)
            if m:
                desc = m.group(1).strip()
        desc = re.sub(r'(收起|展开)$', '', desc).strip()
        if len(desc) > 500:
            desc = desc[:500] + '...'

        # 多线路选集
        froms, urls = self._parse_playlists(html)

        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': self._abs(pic) if pic else '',
            'type_name': type_name,
            'vod_year': year,
            'vod_area': area,
            'vod_lang': lang,
            'vod_director': director,
            'vod_actor': actor,
            'vod_remarks': remarks,
            'vod_content': desc or '暂无简介',
            'vod_play_from': '$$$'.join(froms) if froms else '',
            'vod_play_url': '$$$'.join(urls) if urls else '',
        }
        return vod

    def _parse_playlists(self, html):
        """解析多节点线路和集数
        线路名: <div class="module-tab-item tab-item" data-dropdown-value="推荐全网 〇">...
        集数面板: <div class="module-list module-player-list tab-list sort-list">
                    <a href="/vodplay/{id}-{sid}-{nid}.html">第1集</a>...
                  </div>
        面板顺序与线路 tab 顺序一一对应。
        """
        # 1. 线路名
        tabs = re.findall(
            r'<div[^>]*class="[^"]*module-tab-item[^"]*"[^>]*data-dropdown-value="([^"]*)"',
            html)
        tabs = [t.strip() for t in tabs if t.strip()]

        # 2. 集数面板 (每个面板对应一个线路)
        panels = re.findall(
            r'<div[^>]*class="[^"]*module-player-list[^"]*"[^>]*>([\s\S]*?)</div>\s*</div>',
            html, re.S)

        lines = []  # [(line_name, [(ep_name, ep_url), ...]), ...]
        for idx, panel in enumerate(panels):
            eps = []
            seen_ep = set()
            for em in re.finditer(
                    r'href="(/vodplay/\d+-\d+-\d+\.html)"[^>]*>(.*?)</a>', panel, re.S):
                ep_url = em.group(1)
                if ep_url in seen_ep:
                    continue
                seen_ep.add(ep_url)
                ep_name = self._clean(em.group(2))
                if not ep_name or ep_name == '排序':
                    ep_name = '第%02d集' % (len(eps) + 1)
                eps.append((ep_name, ep_url))
            if eps:
                line_name = tabs[idx] if idx < len(tabs) and tabs[idx] else '线路%d' % (len(lines) + 1)
                lines.append((line_name, eps))

        # 3. 兜底: 无面板结构时抓所有 vodplay 链接
        if not lines:
            eps = []
            seen_ep = set()
            for em in re.finditer(
                    r'href="(/vodplay/\d+-\d+-\d+\.html)"[^>]*>(.*?)</a>', html, re.S):
                ep_url = em.group(1)
                if ep_url in seen_ep:
                    continue
                seen_ep.add(ep_url)
                ep_name = self._clean(em.group(2))
                if not ep_name:
                    ep_name = '第%02d集' % (len(eps) + 1)
                eps.append((ep_name, ep_url))
            if eps:
                lines.append(('高清云播', eps))

        froms = [name for name, _ in lines]
        urls = ['#'.join('%s$%s' % (n, u) for n, u in eps) for _, eps in lines]
        return froms, urls

    # ======================== 搜索 ========================

    def searchContent(self, key, quick, pg='1'):
        """关键词搜索"""
        page = int(pg) if str(pg).isdigit() else 1
        url = self._build_search_url(key, page)
        html = self._fetch(url, referer=self.host + '/')
        items = self._parse_list(html) if html else []

        pagecount = 1
        if html:
            nums = re.findall(r'/vodsearch/[^-]+----------(\d+)---\.html', html)
            if nums:
                try:
                    pagecount = max(int(n) for n in nums)
                except Exception:
                    pagecount = 1
        return {
            'list': items,
            'page': page,
            'pagecount': pagecount,
            'limit': 36,
            'total': pagecount * 36,
            'parse': 0,
            'jx': 0,
        }

    def searchContentPage(self, key, quick, page):
        """搜索分页(OK影视 等外壳调用)"""
        return self.searchContent(key, quick, str(page))

    # ======================== 播放 ========================

    def playerContent(self, flag, id, vipFlags=None):
        """解析播放页, 提取真实视频地址
        播放页包含 player_aaaa JSON 变量:
        {"flag":"play","encrypt":0,"url":"https://xxx.m3u8","from":"bfzym3u8",...}
        encrypt=0 表示 URL 为明文直链。
        """
        play_url = id
        if not play_url.startswith('http'):
            play_url = self._abs(play_url)

        # 直链直接返回
        if self.isVideoFormat(play_url):
            return {'parse': 0, 'url': play_url, 'header': {}}

        html = self._fetch(play_url, referer=self.host + '/')
        if not html:
            return {'parse': 1, 'url': play_url, 'header': {}}

        # 提取 player_aaaa
        m = re.search(r'player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', html)
        if not m:
            m = re.search(r'player_aaaa\s*=\s*(\{[\s\S]*?\})\s*;', html)
        if not m:
            # 兜底: 页面里直接找 m3u8/mp4
            m = re.search(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4)(?:[^\s"\'<>]*))', html)
            if m:
                return {'parse': 0, 'url': m.group(1), 'header': {}}
            return {'parse': 1, 'url': play_url, 'header': {}}

        try:
            p = json.loads(m.group(1))
        except Exception:
            try:
                p = json.loads(m.group(1).replace(r'\/', '/'))
            except Exception:
                return {'parse': 1, 'url': play_url, 'header': {}}

        url = p.get('url', '')
        enc = str(p.get('encrypt', '0'))

        if not url:
            return {'parse': 1, 'url': play_url, 'header': {}}

        # encrypt=0: 明文直链
        if enc == '0':
            url = url.replace('\\/', '/')
            if self.isVideoFormat(url):
                return {'parse': 0, 'url': url, 'header': {}}
            return {'parse': 1, 'url': url, 'header': {}}

        # encrypt=1: escape 编码
        if enc == '1':
            url = self._js_unescape(url)
            if self.isVideoFormat(url):
                return {'parse': 0, 'url': url, 'header': {}}
            return {'parse': 1, 'url': url, 'header': {}}

        # encrypt=2: base64 编码
        if enc == '2':
            try:
                raw = re.sub(r'[^A-Za-z0-9+/=]', '', unquote(url))
                url = self._js_unescape(base64.b64decode(raw).decode('utf-8', 'ignore'))
                if self.isVideoFormat(url):
                    return {'parse': 0, 'url': url, 'header': {}}
            except Exception:
                pass
            return {'parse': 1, 'url': url, 'header': {}}

        return {'parse': 1, 'url': url, 'header': {}}

    @staticmethod
    def _js_unescape(s):
        """还原 JS escape 编码的 URL"""
        if not s:
            return ''
        try:
            return unquote(s.replace('%u', '\\u'), errors='replace').encode('utf-8').decode('unicode_escape', 'ignore')
        except Exception:
            return s
