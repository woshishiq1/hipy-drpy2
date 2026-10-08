# -*- coding: utf-8 -*-
# 猫又影视 (www.imaoyou.net) —— TVBox / 影视仓 / OK影视 通用 py 爬虫
# 站点类型: 苹果CMS (MacCMS) + mytheme 模板 (标准 vodshow 段位 + 自定义详情/播放伪静态)
#
# ============================ 逆向要点 (实爬确认) ============================
#  分类列表  /vodshow/{s0}-{s1}-...-{s11}.html          共 12 段
#            段位含义: [0]type_id [1]area 地区 [2]by 排序 [3]class 剧情 [4]lang 语言
#                      [5]letter 字母 [6]plot [7]state [8]page 页码 [9]tag
#                      [10]version [11]year 年份
#            *** 页码在段位[8], 年份在段位[11] ***
#            *** 子分类是独立 type_id(数字), 选中时替换段位[0] ***
#                电影=1 电视剧=2 综艺=3 动漫=4 短剧=5
#                动作片=6 喜剧片=7 ... 国产剧=13 韩剧=14 ... 台剧=27 泰剧=28 ...
#            *** 站点导航 /miao/{alias}.html 与 /vodshow/{数字}--------- 等价,
#                但数字 id 能区分「台剧/泰剧」这类别名冲突(站点两者 alias 都是 taiju),
#                因此本爬虫统一使用数字 type_id ***
#  详情页    /maoyou/{id}.html
#  播放页    /tv/{id}-{sid}-{nid}.html  -> var player_aaaa = {...} (encrypt/url/from)
#  搜索页    /vodsearch/{wd}-------------.html   共 14 段, 页码在段位[10]
#            搜索关键词需 >=2 字, 单字返回空列表; 搜索有频率限制, 需节流
#  封面      lazyload 占位, 真实地址在 a/@data-original 或 img/@data-original
#  线路      playerconfig.js 里 ps=0 的 flag 直出 m3u8; ps=1 (bilibili/qq/youku/
#            qiyi/mgtv/rrmj/NSHD/NSYS) 需解析 -> 交给 APP parse=1
#  坑1      letter 段位填 "0-9" 会多切出一段导致段位错乱, 站点自身也失效 -> 已剔除
#  坑2      搜索结果 ul 为 myui-vodlist__media clearfix;
#            侧栏热榜是 myui-vodlist__media active col-pd clearfix, 必须排除 active
#  坑3      详情页属性/封面必须限定在 myui-content__detail / myui-content__thumb 内,
#            否则会抓到「猜你喜欢」推荐位的其它影片
# ============================================================================

import re
import sys
import json
import time
import base64
import urllib.parse

import requests
import urllib3
from lxml import etree

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def fetch(self, url, headers=None, timeout=20, verify=False, cookies=None):
            s = requests.Session()
            s.trust_env = False
            return s.get(url, headers=headers, timeout=timeout,
                         verify=verify, cookies=cookies)

        def post(self, url, headers=None, data=None, timeout=20, verify=False, cookies=None):
            s = requests.Session()
            s.trust_env = False
            return s.post(url, headers=headers, data=data, timeout=timeout,
                          verify=verify, cookies=cookies)


SITE = 'https://www.imaoyou.net'

# ==================== 父分类 (首页导航, 数字 type_id) ====================
CATEGORIES = [
    ("1", "电影"),
    ("2", "电视剧"),
    ("3", "综艺"),
    ("4", "动漫"),
    ("5", "短剧"),
]

# ==================== 段位表 ====================
SEG_INDEX = {
    'area': 1,
    'by': 2,
    'class': 3,
    'lang': 4,
    'letter': 5,
    'plot': 6,
    'state': 7,
    'page': 8,
    'tag': 9,
    'version': 10,
    'year': 11,
}
SEG_COUNT = 12
SEARCH_SEG_COUNT = 14
SEARCH_PAGE_INDEX = 10

# 每页条数 (实爬: 48)
PAGE_SIZE = 48


def _years(a, b):
    """生成年份筛选项 (从新到旧)"""
    v = [{"n": "全部", "v": ""}]
    v += [{"n": str(y), "v": str(y)} for y in range(a, b - 1, -1)]
    return v


_LETTERS = [{"n": "全部", "v": ""}] + \
           [{"n": c, "v": c} for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]

_AREAS = [{"n": "全部", "v": ""}] + [
    {"n": x, "v": x} for x in
    ["中国大陆", "中国香港", "中国台湾", "美国", "韩国", "日本", "泰国",
     "印度", "英国", "法国", "德国", "意大利", "西班牙", "俄罗斯",
     "加拿大", "澳大利亚", "新加坡", "马来西亚", "其他"]
]

_LANGS = [{"n": "全部", "v": ""}] + [
    {"n": x, "v": x} for x in
    ["国语", "粤语", "英语", "韩语", "日语", "泰语", "法语", "德语",
     "俄语", "印度语", "其它"]
]

_BY = [
    {"n": "最新", "v": "time"},
    {"n": "人气", "v": "hits"},
    {"n": "豆瓣评分", "v": "douban_score"},
]

# ==================== 筛选器 (实爬每个父分类采集, 子分类=独立数字 type_id) ====
FILTERS = {
    "1": [
        {"key": "tid", "name": "类型", "value": [
            {"n": "全部", "v": "1"},
            {"n": "动作片", "v": "6"}, {"n": "喜剧片", "v": "7"},
            {"n": "科幻片", "v": "8"}, {"n": "爱情片", "v": "9"},
            {"n": "恐怖片", "v": "10"}, {"n": "剧情片", "v": "11"},
            {"n": "战争片", "v": "12"}, {"n": "动画片", "v": "20"},
            {"n": "犯罪片", "v": "21"}, {"n": "奇幻片", "v": "22"},
            {"n": "悬疑片", "v": "23"}, {"n": "纪录片", "v": "24"},
            {"n": "经典片", "v": "44"}, {"n": "邵氏电影", "v": "25"},
        ]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _years(2026, 1990)},
        {"key": "lang", "name": "语言", "value": _LANGS},
        {"key": "letter", "name": "字母", "value": _LETTERS},
        {"key": "by", "name": "排序", "value": _BY},
    ],
    "2": [
        {"key": "tid", "name": "类型", "value": [
            {"n": "全部", "v": "2"},
            {"n": "国产剧", "v": "13"}, {"n": "韩剧", "v": "14"},
            {"n": "美剧", "v": "15"}, {"n": "日剧", "v": "16"},
            {"n": "港剧", "v": "26"}, {"n": "台剧", "v": "27"},
            {"n": "泰剧", "v": "28"}, {"n": "海外剧", "v": "29"},
        ]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _years(2026, 1990)},
        {"key": "lang", "name": "语言", "value": _LANGS},
        {"key": "letter", "name": "字母", "value": _LETTERS},
        {"key": "by", "name": "排序", "value": _BY},
    ],
    "3": [
        {"key": "tid", "name": "类型", "value": [
            {"n": "全部", "v": "3"},
            {"n": "大陆综艺", "v": "30"}, {"n": "日韩综艺", "v": "31"},
            {"n": "港台综艺", "v": "32"}, {"n": "欧美综艺", "v": "33"},
        ]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _years(2026, 2010)},
        {"key": "lang", "name": "语言", "value": _LANGS},
        {"key": "letter", "name": "字母", "value": _LETTERS},
        {"key": "by", "name": "排序", "value": _BY},
    ],
    "4": [
        {"key": "tid", "name": "类型", "value": [
            {"n": "全部", "v": "4"},
            {"n": "国产动漫", "v": "34"}, {"n": "日韩动漫", "v": "35"},
            {"n": "欧美动漫", "v": "36"}, {"n": "港台动漫", "v": "37"},
            {"n": "海外动漫", "v": "38"},
        ]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _years(2026, 2000)},
        {"key": "lang", "name": "语言", "value": _LANGS},
        {"key": "letter", "name": "字母", "value": _LETTERS},
        {"key": "by", "name": "排序", "value": _BY},
    ],
    "5": [
        {"key": "tid", "name": "类型", "value": [
            {"n": "全部", "v": "5"},
            {"n": "年代穿越", "v": "17"}, {"n": "现代都市", "v": "18"},
            {"n": "古装仙侠", "v": "39"}, {"n": "女频恋爱", "v": "40"},
            {"n": "反转爽剧", "v": "41"}, {"n": "脑洞悬疑", "v": "42"},
            {"n": "擦边短剧", "v": "43"},
        ]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _years(2026, 2023)},
        {"key": "lang", "name": "语言", "value": _LANGS},
        {"key": "letter", "name": "字母", "value": _LETTERS},
        {"key": "by", "name": "排序", "value": _BY},
    ],
}

# playerconfig.js 里 ps=1 的线路(需二次解析), 其余为 m3u8 直链
PARSE_FLAGS = {'NSHD', 'NSYS', 'bilibili', 'qq', 'youku', 'qiyi', 'mgtv', 'rrmj'}


class Spider(BaseSpider):
    # ---------------------------------------------------------------- 基础
    def getName(self):
        return "猫又影视"

    def init(self, extend=""):
        self._last = {}
        self.debug = False
        try:
            if extend:
                if isinstance(extend, str):
                    extend = json.loads(extend) if extend.strip().startswith('{') else {}
                if isinstance(extend, dict):
                    self.debug = bool(extend.get('debug'))
        except Exception:
            pass
        return {}

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|avi|mkv|ts)(\?|$)', url or '', re.I))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return {}

    def localProxy(self, param):
        """封面防盗链兜底: 由 APP 代理拉图"""
        try:
            url = (param or {}).get('url', '')
            if not url:
                return None
            r = self.fetch(url, headers={
                'User-Agent': self.header()['User-Agent'],
                'Referer': SITE + '/',
            }, timeout=20, verify=False)
            return [200, r.headers.get('Content-Type', 'image/jpeg'), r.content]
        except Exception:
            return None

    def header(self):
        return {
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                           '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': SITE + '/',
        }

    # ---------------------------------------------------------------- 工具
    def _log(self, *a):
        if getattr(self, 'debug', False):
            try:
                print('[猫又影视]', *a)
            except Exception:
                pass

    def _throttle(self, key, gap=1.0):
        """同类请求主动节流, 避免触发站点搜索限流"""
        if not hasattr(self, '_last'):
            self._last = {}
        wait = gap - (time.time() - self._last.get(key, 0))
        if wait > 0:
            time.sleep(wait)
        self._last[key] = time.time()

    @staticmethod
    def _is_limited(html):
        """限流 / 空壳页识别"""
        if not html or len(html) < 1500:
            return True
        return ('请不要频繁' in html) or ('mac_msg_jump' in html) or \
               ('系统提示' in html and '搜索' in html and len(html) < 6000)

    def _get_text(self, url, tries=3, key=None, gap=1.0):
        html = ''
        for i in range(tries):
            if key:
                self._throttle(key, gap)
            try:
                r = self.fetch(url, headers=self.header(), timeout=20, verify=False)
                if getattr(r, 'status_code', 200) == 404:
                    self._log('404', url)
                    return ''
                r.encoding = 'utf-8'
                html = r.text
            except Exception as e:
                self._log('fetch err', url, e)
                html = ''
            if html and not self._is_limited(html):
                return html
            time.sleep(1.2 + i)
        return html

    def _get(self, url, tries=3, key=None, gap=1.0):
        html = self._get_text(url, tries=tries, key=key, gap=gap)
        if not html:
            return None
        try:
            return etree.HTML(html)
        except Exception:
            return None

    @staticmethod
    def _abs(u):
        if not u:
            return ''
        u = u.strip()
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('http'):
            return u
        if u.startswith('/'):
            return SITE + u
        return SITE + '/' + u

    @staticmethod
    def _txt(node, xp):
        try:
            v = node.xpath(xp)
        except Exception:
            return ''
        if not v:
            return ''
        x = v[0]
        return (x if isinstance(x, str) else ''.join(x.itertext())).strip()

    @staticmethod
    def _bg(style):
        if not style:
            return ''
        m = re.search(r'background-image\s*:\s*url\(\s*[\'"]?([^\'")]+)', style, re.I)
        return m.group(1).strip() if m else ''

    def _pic_of(self, a, li=None):
        """封面: data-original / data-src / 内联 background-image / img src"""
        def ok(c):
            return c and 'load.gif' not in c and 'loading' not in c and 'blank' not in c

        for getter in (lambda: a.get('data-original'),
                       lambda: a.get('data-src'),
                       lambda: self._bg(a.get('style')),
                       lambda: self._txt(a, './/img/@data-original'),
                       lambda: self._txt(a, './/img/@data-src'),
                       lambda: self._txt(a, './/img/@src')):
            try:
                c = getter() or ''
            except Exception:
                c = ''
            if ok(c):
                return self._abs(c)
        if li is not None:
            for st in li.xpath('.//*[@style]/@style'):
                c = self._bg(st)
                if ok(c):
                    return self._abs(c)
            for xp in ('.//img/@data-original', './/img/@data-src', './/img/@src'):
                c = self._txt(li, xp)
                if ok(c):
                    return self._abs(c)
        return ''

    # ------------------------------------------------------- URL 构造
    def _build_list_url(self, tid, seg):
        parts = [''] * SEG_COUNT
        parts[0] = urllib.parse.quote(str(tid), safe='')
        for k, v in (seg or {}).items():
            if v not in (None, '') and k in SEG_INDEX:
                parts[SEG_INDEX[k]] = urllib.parse.quote(str(v), safe='')
        return '%s/vodshow/%s.html' % (SITE, '-'.join(parts))

    def _build_search_url(self, wd, page):
        parts = [''] * SEARCH_SEG_COUNT
        parts[0] = urllib.parse.quote(str(wd), safe='')
        if page and int(page) > 1:
            parts[SEARCH_PAGE_INDEX] = str(int(page))
        return '%s/vodsearch/%s.html' % (SITE, '-'.join(parts))

    # ------------------------------------------------------- 列表解析
    @staticmethod
    def _vid(href):
        m = re.search(r'/maoyou/(\d+)', href or '')
        return m.group(1) if m else ''

    def _parse_vodlist(self, doc):
        """网格列表 (首页推荐 / 分类页)"""
        vods = []
        if doc is None:
            return vods
        for li in doc.xpath('//ul[contains(@class,"myui-vodlist")]/li'):
            a = li.xpath('.//a[contains(@class,"myui-vodlist__thumb")]')
            if not a:
                a = li.xpath('.//a[@href and @title]')
            if not a:
                continue
            a = a[0]
            vid = self._vid(a.get('href'))
            if not vid:
                continue
            name = (a.get('title') or '').strip() or self._txt(li, './/h4//a')
            remark = self._txt(li, './/span[contains(@class,"pic-text")]') or \
                     self._txt(li, './/span[contains(@class,"pic-tag")]')
            vods.append({
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': self._pic_of(a, li),
                'vod_remarks': remark,
            })
        return vods

    def _parse_medialist(self, doc):
        """搜索结果的横向媒体列表 (必须排除侧栏 active 热榜)"""
        vods = []
        if doc is None:
            return vods
        nodes = doc.xpath('//ul[contains(@class,"myui-vodlist__media")'
                          ' and not(contains(@class,"active"))]/li')
        for li in nodes:
            a = li.xpath('.//a[contains(@href,"/maoyou/")]')
            if not a:
                continue
            a = a[0]
            vid = self._vid(a.get('href'))
            if not vid:
                continue
            name = (a.get('title') or '').strip() or self._txt(li, './/h4//a')
            remark = self._txt(li, './/span[contains(@class,"pic-text")]')
            if not remark:
                notes = [re.sub(r'\s+', ' ', ''.join(p.itertext())).strip()
                         for p in li.xpath('.//p[contains(@class,"text-muted")]')]
                notes = [x for x in notes if x]
                remark = notes[0][:40] if notes else ''
            vods.append({
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': self._pic_of(a, li),
                'vod_remarks': remark,
            })
        return vods

    @staticmethod
    def _parse_pagecount(doc):
        """分页条 '3/34' -> 34"""
        if doc is None:
            return 1
        txt = ' '.join(x.strip() for x in
                       doc.xpath('//ul[contains(@class,"myui-page")]//text()') if x.strip())
        m = re.search(r'(\d+)\s*/\s*(\d+)', txt)
        if m:
            try:
                return max(1, int(m.group(2)))
            except Exception:
                pass
        pages = []
        for h in doc.xpath('//ul[contains(@class,"myui-page")]//a/@href'):
            u = urllib.parse.unquote(h or '')
            mm = re.search(r'/vodshow/(?:[^-/]*-){8}(\d+)', u)
            if mm:
                pages.append(int(mm.group(1)))
            mm = re.search(r'/vodsearch/(?:[^-/]*-){10}(\d+)', u)
            if mm:
                pages.append(int(mm.group(1)))
            mm = re.search(r'/miao/[a-z]+-(\d+)\.html', u)
            if mm:
                pages.append(int(mm.group(1)))
        return max(pages) if pages else 1

    @staticmethod
    def _dedup(vods):
        seen, out = set(), []
        for v in vods:
            if not v.get('vod_id') or v['vod_id'] in seen:
                continue
            seen.add(v['vod_id'])
            out.append(v)
        return out

    # ---------------------------------------------------------------- 首页
    def homeContent(self, filter=False):
        classes = [{'type_id': t, 'type_name': n} for t, n in CATEGORIES]
        result = {'class': classes, 'filters': FILTERS, 'parse': 0, 'jx': 0}
        try:
            doc = self._get(SITE + '/', key='home')
            result['list'] = self._dedup(self._parse_vodlist(doc))[:60]
        except Exception as e:
            self._log('homeContent err', e)
            result['list'] = []
        return result

    def homeVideoContent(self):
        try:
            doc = self._get(SITE + '/', key='home')
            return {'list': self._dedup(self._parse_vodlist(doc))[:60], 'parse': 0, 'jx': 0}
        except Exception as e:
            self._log('homeVideoContent err', e)
            return {'list': []}

    # ---------------------------------------------------------------- 分类
    def categoryContent(self, tid, pg=1, filter=False, extend=''):
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1
        page = max(1, page)

        if isinstance(extend, str):
            try:
                extend = json.loads(extend) if extend.strip().startswith('{') else {}
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}

        real_tid = extend.get('tid') or tid       # 子分类 -> 替换段位[0]
        seg = {
            'area': extend.get('area', ''),
            'by': extend.get('by', ''),
            'class': extend.get('class', ''),
            'lang': extend.get('lang', ''),
            'letter': extend.get('letter', ''),
            'year': extend.get('year', ''),
        }
        if page > 1:
            seg['page'] = page

        url = self._build_list_url(real_tid, seg)
        self._log('category', url)
        doc = self._get(url, key='list')
        vods = self._dedup(self._parse_vodlist(doc))
        pagecount = self._parse_pagecount(doc)
        if page > pagecount:
            pagecount = page
        return {
            'list': vods,
            'page': page,
            'pagecount': pagecount,
            'limit': PAGE_SIZE,
            'total': pagecount * PAGE_SIZE if vods else 0,
        }

    # ---------------------------------------------------------------- 详情
    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        vid = str(vid).strip()
        m = re.search(r'(\d+)', vid)
        vid = m.group(1) if m else vid
        url = '%s/maoyou/%s.html' % (SITE, vid)
        html = self._get_text(url, key='detail')
        if not html:
            return {'list': []}
        try:
            doc = etree.HTML(html)
        except Exception:
            return {'list': []}
        if doc is None:
            return {'list': []}

        detail = doc.xpath('//div[contains(@class,"myui-content__detail")]')
        detail = detail[0] if detail else doc

        name = self._txt(detail, './/h1') or self._txt(doc, '//h1')

        pic = ''
        thumb = doc.xpath('//div[contains(@class,"myui-content__thumb")]//a')
        if thumb:
            pic = self._pic_of(thumb[0], thumb[0])
        if not pic:
            for xp in ('//div[contains(@class,"myui-content__thumb")]//img/@data-original',
                       '//div[contains(@class,"myui-content__thumb")]//img/@src'):
                c = self._txt(doc, xp)
                if c and 'load.gif' not in c:
                    pic = self._abs(c)
                    break
        if not pic:
            c = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html, re.I)
            if c:
                pic = self._abs(c.group(1))

        # 属性 (限定 myui-content__detail, 避免抓到推荐位)
        # 一个 <p> 里可能塞多组 "分类：x 地区：y 年份：z", 用「下一个标签」做右边界切分
        info = {}
        _keys = ('分类', '类型', '地区', '年份', '语言', '更新', '主演',
                 '导演', '编剧', '简介', '备注', '又名', '上映')
        _kk = '|'.join(_keys)
        _pat = re.compile(r'(%s)\s*[：:]\s*(.*?)(?=\s*(?:%s)\s*[：:]|$)' % (_kk, _kk), re.S)
        for p in detail.xpath('.//p'):
            raw = re.sub(r'[\s\u00a0]+', ' ', ''.join(p.itertext())).strip()
            if not raw:
                continue
            for k, v in _pat.findall(raw):
                v = v.strip(' ,、&')
                if v and (k not in info or len(v) > len(info[k])):
                    info[k] = v

        remarks = info.get('更新', '')
        if remarks:
            remarks = remarks.split('/')[0].strip()
        if not remarks:
            remarks = info.get('备注', '')

        year = re.sub(r'\D', '', info.get('年份', ''))[:4]

        # 简介: 详情页头部只有折叠摘要(带"...详情"), 完整文本在 #desc 区块;
        #       #desc 缺失时退回 meta description (格式 "{片名}剧情:xxx")
        desc = self._txt(doc, '//div[@id="desc"]//span[contains(@class,"data")]')
        if not desc:
            desc = self._txt(doc, '//div[@id="desc"]//p')
        if not desc:
            md = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html, re.I)
            if md:
                desc = md.group(1).strip()
                if name:
                    desc = re.sub(r'^\s*' + re.escape(name) + r'\s*', '', desc)
                desc = re.sub(r'^.{0,30}?剧情\s*[：:]\s*', '', desc, count=1).strip()
        if not desc:
            desc = info.get('简介', '')
        desc = re.sub(r'[\s\u00a0]+', ' ', desc).strip()
        desc = re.sub(r'\s*\.{2,}\s*详情\s*$', '', desc).strip()
        # 站点无简介时会回填片名或"暂无简介", 统一清空
        if desc in ('暂无简介', '暂无内容', name) or desc.replace(name, '').strip() in ('', '剧情'):
            desc = ''

        # 播放线路: tab 的 href(#playlistN) 与 div#playlistN 精确配对
        play_from, play_url = [], []
        tabs = doc.xpath('//ul[contains(@class,"nav-tabs")]//a[starts-with(@href,"#playlist")]')
        pairs = []
        for a in tabs:
            pid = (a.get('href') or '').lstrip('#')
            nm = re.sub(r'\s+', ' ', ''.join(a.itertext())).strip()
            nm = nm.replace('$', '').replace('#', '') or '线路'
            pairs.append((pid, nm))
        if not pairs:
            for i, d in enumerate(doc.xpath('//div[starts-with(@id,"playlist")]')):
                pairs.append((d.get('id'), '线路%d' % (i + 1)))

        for pid, nm in pairs:
            eps = []
            for a in doc.xpath('//div[@id="%s"]//ul[contains(@class,"myui-content__list")]/li/a' % pid):
                t = re.sub(r'\s+', ' ', ''.join(a.itertext())).strip()
                mm = re.search(r'/tv/(\d+)-(\d+)-(\d+)', a.get('href') or '')
                if not mm:
                    continue
                t = (t or '播放').replace('#', '').replace('$', '')
                eps.append('%s$%s-%s-%s' % (t, mm.group(1), mm.group(2), mm.group(3)))
            if eps:
                play_from.append(nm)
                play_url.append('#'.join(eps))

        vod = {
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'type_name': info.get('分类', '') or info.get('类型', ''),
            'vod_year': year,
            'vod_area': info.get('地区', ''),
            'vod_lang': info.get('语言', ''),
            'vod_remarks': remarks,
            'vod_actor': info.get('主演', ''),
            'vod_director': info.get('导演', ''),
            'vod_content': desc,
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '$$$'.join(play_url),
        }
        return {'list': [vod]}

    # ---------------------------------------------------------------- 播放
    def playerContent(self, flag, id, vipFlags=None):
        pid = str(id).strip()
        if pid.startswith('http'):
            return {'parse': 0, 'playUrl': '', 'url': pid,
                    'header': {'User-Agent': self.header()['User-Agent']}, 'jx': 0}

        m = re.search(r'(\d+)-(\d+)-(\d+)', pid)
        page_url = '%s/tv/%s.html' % (SITE, m.group(0)) if m else self._abs(pid)
        html = self._get_text(page_url, key='play')

        real, pfrom, enc = '', '', '0'
        if html:
            mm = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>', html, re.S) or \
                 re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*[;\n]', html, re.S)
            if mm:
                try:
                    j = json.loads(mm.group(1))
                except Exception:
                    j = {}
                real = j.get('url') or ''
                pfrom = j.get('from') or ''
                enc = str(j.get('encrypt', '0'))
            if not real:
                m2 = re.search(r'"url"\s*:\s*"([^"]+?\.m3u8[^"]*)"', html)
                if m2:
                    real = m2.group(1)

        if not real:
            self._log('no play url', page_url)
            return {'parse': 1, 'playUrl': '', 'url': page_url,
                    'header': self.header(), 'jx': 0}

        real = real.replace('\\/', '/')
        try:
            if enc == '1':
                real = urllib.parse.unquote(real)
            elif enc == '2':
                real = urllib.parse.unquote(base64.b64decode(real).decode('utf-8', 'ignore'))
        except Exception:
            pass

        # ps=0 的线路直出 m3u8; ps=1 (爱奇艺/腾讯/优酷等) 交给 APP 解析
        if pfrom not in PARSE_FLAGS and self.isVideoFormat(real):
            # 视频 CDN 不校验 Referer, 带站点 Referer 反而偶发 403 -> 只留 UA
            return {'parse': 0, 'playUrl': '', 'url': real,
                    'header': {'User-Agent': self.header()['User-Agent']}, 'jx': 0}
        return {'parse': 1, 'playUrl': '', 'url': real or page_url,
                'header': self.header(), 'jx': 0}

    # ---------------------------------------------------------------- 搜索
    def searchContent(self, key, quick=False, pg='1'):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick=False, pg='1'):
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1
        page = max(1, page)

        key = (key or '').strip()
        if len(key) < 2:          # 站点单字搜索恒为空
            self._log('keyword too short:', key)

        url = self._build_search_url(key, page)
        self._log('search', url)
        doc = self._get(url, key='search', gap=3.2)
        vods = self._parse_medialist(doc)
        if not vods:
            vods = self._parse_vodlist(doc)
        vods = self._dedup(vods)
        if any(v.get('vod_pic') for v in vods):
            vods = [v for v in vods if v.get('vod_pic')]
        return {'list': vods, 'page': page,
                'pagecount': self._parse_pagecount(doc),
                'limit': len(vods), 'total': len(vods)}


# ==================================================================== 自测
if __name__ == '__main__':
    import io
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

    sp = Spider()
    sp.init('{"debug":true}')
    print('=== getName ===', sp.getName())

    home = sp.homeContent(True)
    print('=== homeContent ===', len(home['class']), '个父分类, 首页推荐',
          len(home.get('list', [])), '条')
    for v in home.get('list', [])[:3]:
        print('   ', v['vod_id'], v['vod_name'], v['vod_remarks'], v['vod_pic'][:60])

    for tid, tname in CATEGORIES:
        r = sp.categoryContent(tid, 1)
        print('=== 分类 %s(%s) p1 ===' % (tname, tid), len(r['list']), '条, 共', r['pagecount'], '页')
        sub = FILTERS[tid][0]['value'][1]
        r2 = sp.categoryContent(tid, 2, True, {'tid': sub['v']})
        print('    子分类 %s(%s) p2 ->' % (sub['n'], sub['v']), len(r2['list']),
              '条, 共', r2['pagecount'], '页, 首条:',
              r2['list'][0]['vod_name'] if r2['list'] else '-')

    r3 = sp.categoryContent('1', 1, True,
                            {'tid': '6', 'area': '美国', 'year': '2024', 'by': 'hits'})
    print('=== 组合筛选 动作片/美国/2024/人气 ===', len(r3['list']), '条, 共', r3['pagecount'], '页')
    for v in r3['list'][:3]:
        print('   ', v['vod_name'], v['vod_remarks'])

    r4 = sp.categoryContent('1', 1, True, {'tid': '1', 'letter': 'A'})
    print('=== 字母筛选 A ===', len(r4['list']), '条, 共', r4['pagecount'], '页')

    vid = (r['list'][0]['vod_id'] if r.get('list') else '126703')
    d = sp.detailContent([vid])
    v = d['list'][0]
    print('=== detailContent', vid, '===')
    for k in ('vod_name', 'vod_pic', 'type_name', 'vod_year', 'vod_area',
              'vod_remarks', 'vod_actor', 'vod_director'):
        print('   %-14s %s' % (k, str(v.get(k))[:80]))
    print('    vod_content   ', (v.get('vod_content') or '')[:100])
    print('    线路          ', v['vod_play_from'])
    print('    集数          ', [len(x.split('#')) for x in v['vod_play_url'].split('$$$')])
    print('    首集          ', v['vod_play_url'].split('$$$')[0].split('#')[0])

    first = v['vod_play_url'].split('$$$')[0].split('#')[0].split('$')[-1]
    p = sp.playerContent(v['vod_play_from'].split('$$$')[0], first)
    print('=== playerContent ===', 'parse=', p['parse'], 'url=', p['url'][:110])

    s1 = sp.searchContent('庆余年', False, '1')
    print('=== searchContent 庆余年 ===', len(s1['list']), '条, 共', s1['pagecount'], '页')
    for x in s1['list'][:5]:
        print('   ', x['vod_id'], x['vod_name'], '|', x['vod_remarks'][:24], '|', x['vod_pic'][:50])
    s2 = sp.searchContentPage('爱情', False, '2')
    print('=== 搜索翻页 爱情 p2 ===', len(s2['list']), '条, 共', s2['pagecount'], '页,',
          [x['vod_name'] for x in s2['list'][:3]])
