#!/usr/bin/python3
# -*- coding: utf-8 -*-
# 兄弟影视 TVBox Python 爬虫
# 基于 www.siac-edc.com 当前结构编写

import re
import sys
import json
import time
import requests
from urllib import parse as urlparse

sys.path.append('..')

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def __init__(self):
            self._session = None

        @property
        def sess(self):
            if self._session is None:
                self._session = requests.Session()
                self._session.verify = False
                adapter = requests.adapters.HTTPAdapter(
                    pool_connections=10, pool_maxsize=10, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self.sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[兄弟影视]", *a)
            except Exception:
                pass

    BaseSpider = BaseSpider

try:
    from pyquery import PyQuery as PQ
except ImportError:
    PQ = None

# ===================== 配置 =====================
HOST = "https://www.siac-edc.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 严格只保留官方主导航的 6 个分类
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "连续剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "5",  "type_name": "短剧"},
    {"type_id": "21", "type_name": "预告片"},
]

# 简介前缀（你指定的）
INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 工具正则 =====================
_RE_CARD = re.compile(
    r'<li[^>]*>\s*<a[^>]*href="(/xddetail/\d+\.html)"[^>]*title="([^"]*)"[^>]*>'
    r'[\s\S]*?<img[^>]*?(?:data-src|data-original|src)="([^"]*)"'
    r'[\s\S]*?<p[^>]*class="[^"]*other[^"]*"><i>([^<]*)</i>',
    re.S | re.I
)

_RE_PLAY_LIST = re.compile(
    r'<div[^>]*id="stab\d+"[^>]*>[\s\S]*?<div[^>]*id="vlink_\d+"[^>]*>'
    r'[\s\S]*?<ul>([\s\S]*?)</ul>',
    re.S | re.I
)
_RE_EP = re.compile(
    r'<a[^>]*href="(/xdplay/[^"]+)"[^>]*>([^<]*)</a>',
    re.I
)

_RE_PLAYER_AA = re.compile(
    r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>',
    re.S
)

_RE_DL = re.compile(r'<dl[^>]*>(.*?)</dl>', re.S | re.I)
_RE_DT = re.compile(r'<dt><span>按(.*?)</span></dt>', re.S | re.I)
_RE_DD = re.compile(r'<dd><a[^>]*href="([^"]*)"[^>]*>(.*?)</a></dd>', re.S | re.I)

_RE_LINE_NAMES = re.compile(
    r'<li[^>]*id="tab\d+"[^>]*>.*?<i[^>]*></i>\s*([^<]+)',
    re.S | re.I
)

# 总页数解析：从"共X条数据,当前Y/Z页"或"尾页"链接获取
_RE_PAGE_INFO = re.compile(r'共\s*\d+\s*条数据\s*,\s*当前\s*(\d+)\s*/\s*(\d+)\s*页', re.S)
_RE_LAST_PAGE = re.compile(r'<a[^>]*href="[^"]*?(\d+)---?\.html"[^>]*title="尾页"', re.I)
_RE_LAST_PAGE2 = re.compile(r'title="尾页"[^>]*href="[^"]*?(\d+)---?\.html"', re.I)


class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.home_url = HOST
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.home_url + "/",
        }
        self.name = "兄弟影视"
        self._filters_cache = {}

    def getName(self):
        return self.name

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        site = self.extend.get("site")
        if site:
            self.home_url = site.rstrip("/")
            self.headers["Referer"] = self.home_url + "/"

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        filters = {}
        for cls in CLASSES:
            tid = cls["type_id"]
            if tid not in self._filters_cache:
                self._filters_cache[tid] = self._get_filters(tid)
            filters[tid] = self._filters_cache[tid]
        return {"class": CLASSES, "filters": filters}

    def _get_filters(self, tid):
        url = f"{self.home_url}/xdshow/{tid}-----------.html"
        self.log(f"获取筛选: {url}")
        html = self._fetch(url)
        if not html:
            return []
        filters = []
        for dl_match in _RE_DL.finditer(html):
            dl_html = dl_match.group(1)
            dt_match = _RE_DT.search(dl_html)
            if not dt_match:
                continue
            dim_name = dt_match.group(1).strip()
            options = []
            for dd_match in _RE_DD.finditer(dl_html):
                href = dd_match.group(1)
                text = re.sub(r'<[^>]+>', '', dd_match.group(2)).strip()
                if not href or not text:
                    continue
                href = href.replace("&amp;", "&")
                options.append({"n": text, "v": href})
            if options:
                filters.append({
                    "key": dim_name,
                    "name": dim_name,
                    "value": options
                })
        self.log(f"  筛选维度: {[f['name'] for f in filters]}")
        return filters

    def homeVideoContent(self):
        """首页推荐：抓取多个区域"""
        url = self.home_url + "/"
        html = self._fetch(url)
        if not html:
            return {"list": []}
        # 抓取首页所有 index-area 区域
        videos = self._parse_list(html)
        # 去重
        seen = set()
        unique = []
        for v in videos:
            if v["vod_id"] not in seen:
                seen.add(v["vod_id"])
                unique.append(v)
        return {"list": unique}

    def categoryContent(self, tid, page, filter, extend):
        page = int(page) if page else 1
        url = ""
        # 有筛选
        if extend:
            filter_val = ""
            for key, val in extend.items():
                if val:
                    filter_val = val
                    break
            if filter_val:
                # 构造带页码的筛选 URL
                base = filter_val  # 如 /xdshow/1---喜剧--------2026.html
                url = self.home_url + self._build_filter_page_url(base, page)
                self.log(f"category (筛选+p{page}): {url}")
        # 无筛选
        if not url:
            url = f"{self.home_url}/xdshow/{tid}--------{page}---.html"
            self.log(f"category: {url}")
        html = self._fetch(url)
        videos = self._parse_list(html)
        pagecount = self._parse_pagecount(html, page)
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
        }

    def _build_filter_page_url(self, base_url, page):
        """给筛选 URL 加页码"""
        if page <= 1:
            return base_url
        # 筛选 URL 形如 /xdshow/1---喜剧--------2026.html
        # 页码插在末尾的 8 个横线区域中间：把 -------- 替换成 ----{page}---
        if '--------' in base_url:
            return base_url.replace('--------', '----{}---'.format(page), 1)
        # 兜底：在 .html 前面加
        if base_url.endswith('.html'):
            return base_url[:-5] + f'{page}---.html'
        return base_url

    def searchContent(self, key, quick, page="1"):
        page = int(page) if page else 1
        # 用 quote_plus 处理空格
        kw = urlparse.quote_plus(key)
        url = f"{self.home_url}/xdsearch/{kw}----------{page}---.html"
        self.log(f"search: {url}")
        html = self._fetch(url)
        videos = self._parse_list(html)
        pagecount = self._parse_pagecount(html, page)
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
        }

    def searchContentPage(self, key, quick, page="1"):
        return self.searchContent(key, quick, page)

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self.home_url + vod_id
        self.log(f"detail: {url}")
        html = self._fetch(url)
        if not html:
            return {"list": []}

        name = self._extract_text(html, r'<dt[^>]*class="[^"]*name[^"]*"[^>]*>([^<]+)</dt>')
        if not name:
            name = self._extract_text(html, r'<title>(.*?)</title>')
            name = re.sub(r'《|》|_.*$', '', name).strip()

        pic = self._extract_attr(html, r'<div[^>]*class="[^"]*ct-l[^"]*"[^>]*>\s*<img[^>]*src="([^"]+)"')
        if not pic:
            pic = self._extract_attr(html, r'<img[^>]*src="([^"]+)"')

        actor = self._extract_text(html, r'<dt><span>主演：</span>([^<]*)</dt>')
        director = self._extract_text(html, r'<dd><span>导演：</span>([^<]*)</dd>')
        area = self._extract_text(html, r'<dd><span>地区：</span>([^<]*)</dd>')
        year = self._extract_text(html, r'<dd><span>年份：</span>([^<]*)</dd>')
        type_name = self._extract_text(html, r'<dt><span>类型：</span>([^<]*)</dt>')
        remarks = self._extract_text(html, r'<dd><span>备注：</span>([^<]*)</dd>')
        lang = self._extract_text(html, r'<dd><span>语言：</span>([^<]*)</dd>')

        # 简介：严格按官网文本 + 指定前缀
        content = self._extract_text(
            html, r'<div[^>]*class="[^"]*tab-jq[^"]*"[^>]*>\s*<p>([\s\S]*?)</p>',
            strip_tags=True)
        if not content:
            content = self._extract_text(
                html, r'<div[^>]*class="[^"]*ee[^"]*"[^>]*>\s*<span>简介：</span>([\s\S]*?)</div>',
                strip_tags=True)
        if not content:
            content = self._extract_text(
                html, r'<meta\s+name="description"\s+content="([^"]*)"',
                strip_tags=True)
        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # ========== 播放列表（按顺序配对） ==========
        line_names = _RE_LINE_NAMES.findall(html)
        line_names = [n.strip() for n in line_names]
        self.log(f"  线路名（按顺序）: {line_names}")

        play_lists = _RE_PLAY_LIST.findall(html)
        self.log(f"  播放列表容器数量: {len(play_lists)}")

        play_from = []
        play_url = []
        for i, ul_html in enumerate(play_lists):
            episodes = _RE_EP.findall(ul_html)
            if not episodes:
                continue
            line_name = line_names[i] if i < len(line_names) else f"线路{i+1}"
            play_from.append(line_name)
            play_url.append("#".join(f"{ep_name}${href}" for href, ep_name in episodes))

        if not play_from:
            return {"list": []}

        return {
            "list": [{
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "vod_actor": actor,
                "vod_director": director,
                "vod_area": area,
                "vod_year": year,
                "vod_type": type_name,
                "vod_lang": lang,
                "vod_remarks": remarks,
                "vod_content": content,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        url = id if id.startswith("http") else self.home_url + id
        self.log(f"player: {url}")
        html = self._fetch(url)
        if not html:
            return {"parse": 1, "url": url, "header": self.headers}

        m = _RE_PLAYER_AA.search(html)
        if m:
            try:
                aa = json.loads(m.group(1))
                play_url = aa.get("url", "")
                if play_url:
                    play_url = play_url.replace("\\/", "/").replace("&amp;", "&")
                    self.log(f"  => 直链: {play_url[:120]}")
                    return {
                        "parse": 0,
                        "playUrl": "",
                        "url": play_url,
                        "header": {
                            "User-Agent": UA,
                            "Referer": self.home_url + "/",
                        },
                    }
            except Exception as e:
                self.log(f"解析 player_aaaa 失败: {e}")

        return {
            "parse": 1,
            "playUrl": "",
            "url": url,
            "header": self.headers,
        }

    def localProxy(self, params):
        return None

    def destroy(self):
        pass

    def close(self):
        self.destroy()

    # ===================== 辅助方法 =====================
    def _fetch(self, url, headers=None, timeout=15):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            r = self.fetch(url, headers=h, timeout=timeout)
            if hasattr(r, "text"):
                return r.text or ""
            if hasattr(r, "content"):
                return r.content.decode("utf-8", "ignore")
            return str(r)
        except Exception as e:
            self.log(f"fetch fail: {url} -> {e}")
            return ""

    def _parse_pagecount(self, html, current_page):
        """解析总页数：从'共X条数据,当前Y/Z页'或'尾页'链接获取"""
        if not html:
            return current_page
        # 优先：共X条数据,当前Y/Z页
        m = _RE_PAGE_INFO.search(html)
        if m:
            try:
                return int(m.group(2))
            except Exception:
                pass
        # 次选：尾页链接
        for pat in (_RE_LAST_PAGE, _RE_LAST_PAGE2):
            m = pat.search(html)
            if m:
                try:
                    return int(m.group(1))
                except Exception:
                    pass
        # 兜底
        return 9999 if current_page == 1 else current_page

    def _parse_list(self, html):
        if not html:
            return []
        videos = []
        seen = set()

        if PQ:
            try:
                doc = PQ(html)
                items = doc('div.index-area ul li')
                for li in items.items():
                    a = li('a').eq(0)
                    href = a.attr('href')
                    title = a.attr('title')
                    if not href or not title:
                        continue
                    if href in seen:
                        continue
                    seen.add(href)
                    img = li('img').eq(0)
                    # 图片懒加载：data-src > data-original > src
                    pic = (img.attr('data-src') or img.attr('data-original')
                           or img.attr('src') or '')
                    remark = li('p.other i').text().strip()
                    videos.append({
                        "vod_id": href,
                        "vod_name": title.strip(),
                        "vod_pic": pic,
                        "vod_remarks": remark,
                    })
                if videos:
                    return videos
            except Exception as e:
                self.log(f"PyQuery 解析失败: {e}")

        for m in _RE_CARD.finditer(html):
            href, title, pic, remark = m.groups()
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": remark.strip(),
            })
        return videos

    def _extract_text(self, html, pattern, strip_tags=False):
        m = re.search(pattern, html, re.S | re.I)
        if not m:
            return ""
        text = m.group(1)
        if strip_tags:
            text = re.sub(r'<[^>]+>', '', text)
        return text.strip()

    def _extract_attr(self, html, pattern):
        m = re.search(pattern, html, re.S | re.I)
        return m.group(1).strip() if m else ""


if __name__ == '__main__':
    s = Spider()
    s.init()
    print("分类:", s.homeContent(False))
    # 测试详情
    detail = s.detailContent(["/xddetail/174041.html"])
    if detail["list"]:
        d = detail["list"][0]
        print("详情:", d["vod_name"])
        print("线路名:", d["vod_play_from"])
        print("简介:", d["vod_content"][:200])
        print("语言:", d.get("vod_lang", ""))
    # 测试首页推荐
    hv = s.homeVideoContent()
    print("首页推荐:", len(hv["list"]), "条")
