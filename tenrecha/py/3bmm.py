#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3bmm.com / dtijfoc.info — PeekPro / TVBox 兼容爬虫
站点: https://3bmm.com (301 → dtijfoc.info)
CMS: 自建站点，无签名/无反爬/无倒计时
"""

import re
import html
import logging
import requests
from urllib.parse import urljoin, urlparse

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("3bmm")

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
CANDIDATE_BASE_URLS = [
    "https://3bmm.com",
    "https://dtijfoc.info",
]

CATEGORY_MAP = {
    "guochan": "国产",
    "zhibo":   "直播",
    "rihan":   "日韩",
    "oumei":   "欧美",
    "sanji":   "三级",
    "dongman": "动漫",
}

# 分类列表页模板
CAT_LIST_URL = "/suoyoushipin/{cat}/"
CAT_PAGE_URL = "/suoyoushipin/{cat}/index_{pg}.html"
DETAIL_URL   = "/suoyoushipin/{cat}/{vid}.html"

# 播放 & 封面 CDN
CDN_HLS  = "https://kngyyvu.info/new/hls"
CDN_PIC  = "https://aghivwz.info/pic"

# 搜索接口
SEARCH_URL = "/e/search/index.php"

# 通用请求头
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def resolve_base_url(session):
    """探测可用的 base_url，3bmm.com 会自动 301，取最终跳转后域名。"""
    for url in CANDIDATE_BASE_URLS:
        try:
            r = session.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
            if r.status_code == 200:
                final = urlparse(r.url)
                base = f"{final.scheme}://{final.netloc}"
                log.info("选定 base_url: %s (尝试 %s)", base, url)
                return base
        except Exception as e:
            log.warning("探测 %s 失败: %s", url, e)
    raise RuntimeError("所有候选域名均不可达")


def unescape_entities(text):
    """解码 HTML 实体（&#xxxx;/&lt;/&gt;/&amp; 等）。"""
    if not text:
        return ""
    return html.unescape(text)


# ---------------------------------------------------------------------------
# 正则抽取
# ---------------------------------------------------------------------------
RE_CARD = re.compile(
    r'<li>\s*<a\s+href="([^"]+)"[^>]*title="([^"]*)"[^>]*>'
    r'\s*<img\s+src="([^"]+)"[^>]*alt="([^"]*)">'
    r'\s*(?:<p>[^<]*</p>\s*)?'
    r'(?:<span>([^<]*)</span>\s*)?',
    re.S | re.I,
)

RE_M3U8_HASH = re.compile(
    r'var\s+vHLSurl\s*=\s*"/([a-f0-9]+)/index\.m3u8"',
    re.I,
)

RE_TITLE = re.compile(r"<title>([^<]*)</title>", re.S | re.I)

# 详情页 meta
RE_CONTENT = re.compile(
    r'<div\s+class="vod-content"[^>]*>([\s\S]*?)</div>', re.S | re.I
)

# ---------------------------------------------------------------------------
# Spider
# ---------------------------------------------------------------------------
class Spider:
    """
    PeekPro / TVBox 标准爬虫类。
    必须包含:
      init, getName, destroy, localProxy,
      homeContent, homeVideoContent, categoryContent,
      detailContent, searchContent, playerContent
    参数签名必须与 PeekPro 调用约定一致。
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update(HEADERS)
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.base_url = ""
        self._hash_cache = {}   # vid → m3u8_hash，detailContent 写入，playerContent 读取

    def getName(self):
        return "3bmm"

    def init(self, extend=""):
        self.base_url = resolve_base_url(self.session)
        log.info("init 完成，base_url=%s", self.base_url)

    def destroy(self):
        if self.session:
            self.session.close()

    def localProxy(self, param):
        return [404, "text/plain", ""]

    # ------------------------------------------------------------------
    def _get(self, path, **kwargs):
        url = urljoin(self.base_url, path)
        log.info("GET %s", url)
        r = self.session.get(url, timeout=20, **kwargs)
        r.raise_for_status()
        if r.encoding and r.encoding.lower() == "iso-8859-1":
            r.encoding = "utf-8"
        return r

    def _post(self, path, data, **kwargs):
        url = urljoin(self.base_url, path)
        log.info("POST %s", url)
        r = self.session.post(url, data=data, timeout=20, **kwargs)
        r.raise_for_status()
        if r.encoding and r.encoding.lower() == "iso-8859-1":
            r.encoding = "utf-8"
        return r

    def _extract_list_from_html(self, html_text):
        items = []
        for m in RE_CARD.finditer(html_text):
            href  = m.group(1)
            title = unescape_entities(m.group(2))
            img   = m.group(3)
            date  = m.group(5) if m.lastindex >= 5 else ""

            parts = href.strip("/").split("/")
            if parts:
                last = parts[-1]
                if last.endswith(".html") and last.replace(".html", "").isdigit():
                    vid = last.replace(".html", "")
                else:
                    continue

            items.append({
                "vod_id":      vid,
                "vod_name":    title,
                "vod_pic":     img,
                "vod_remarks": date.strip(),
            })
        return items

    # ------------------------------------------------------------------
    def homeContent(self, filter):
        log.info("homeContent filter=%s", filter)
        try:
            r = self._get(CAT_LIST_URL.format(cat="guochan"))
            items = self._extract_list_from_html(r.text)
            return {
                "class": [
                    {"type_id": c, "type_name": n}
                    for c, n in CATEGORY_MAP.items()
                ],
                "filters": {},
                "list": items[:30],
            }
        except Exception as e:
            log.error("homeContent 失败: %s", e)
            return {"class": [], "filters": {}, "list": []}

    def homeVideoContent(self):
        try:
            r = self._get(CAT_LIST_URL.format(cat="guochan"))
            items = self._extract_list_from_html(r.text)
            return {"list": items[:30]}
        except:
            return {"list": []}

    # ------------------------------------------------------------------
    def categoryContent(self, tid, pg, filter, extend):
        log.info("categoryContent tid=%s pg=%s", tid, pg)
        cat = str(tid)
        page = int(pg) if pg else 1
        try:
            if page <= 1:
                path = CAT_LIST_URL.format(cat=cat)
            else:
                path = CAT_PAGE_URL.format(cat=cat, pg=page)

            r = self._get(path)
            items = self._extract_list_from_html(r.text)

            last_match = re.search(
                r'/suoyoushipin/' + re.escape(cat) + r'/index_(\d+)\.html[^>]*>尾页',
                r.text, re.I,
            )
            total_pg = int(last_match.group(1)) if last_match else page

            return {
                "page": page,
                "pagecount": total_pg,
                "limit": len(items),
                "total": total_pg * 30,
                "list": items,
            }
        except Exception as e:
            log.error("categoryContent 失败: %s", e)
            return {"page": page, "pagecount": 1, "limit": 0, "total": 0, "list": []}

    # ------------------------------------------------------------------
    def detailContent(self, ids):
        """
        ids: PeekPro 传入的是列表，取 ids[0]（数字 vid）。
        需要根据 vid 构造详情页 URL 来抓取标题和 m3u8 hash。
        """
        log.info("detailContent ids=%s type=%s", ids, type(ids))
        try:
            vid = str(ids[0]) if isinstance(ids, list) else str(ids)
            # 需要找到该视频的详情页 URL —— 从列表页预加载的缓存或通过搜索。
            # 策略：尝试所有分类目录找到这个 vid。
            detail_html = self._find_detail_html(vid)
            if not detail_html:
                log.warning("detailContent 未能定位 vid=%s 的详情页", vid)
                return {"list": []}

            # 标题
            title = ""
            m_title = RE_TITLE.search(detail_html)
            if m_title:
                raw = unescape_entities(m_title.group(1))
                for suffix in [" - 迷妹网", "| 迷妹网", "- 迷妹网"]:
                    if suffix in raw:
                        raw = raw[: raw.index(suffix)].strip()
                title = raw

            # m3u8 hash
            hash_val = ""
            m_m3u8 = RE_M3U8_HASH.search(detail_html)
            if m_m3u8:
                hash_val = m_m3u8.group(1)
                self._hash_cache[vid] = hash_val   # 缓存，playerContent 复用

            vod_pic = f"{CDN_PIC}/{hash_val}.jpg" if hash_val else ""
            play_url = f"{CDN_HLS}/{hash_val}/index.m3u8" if hash_val else ""

            return {
                "list": [{
                    "vod_id":          vid,
                    "vod_name":        title or f"视频_{vid}",
                    "vod_pic":         vod_pic,
                    "type_name":       "",
                    "vod_year":        "",
                    "vod_area":        "",
                    "vod_remarks":     "",
                    "vod_actor":       "",
                    "vod_director":    "",
                    "vod_content":     "",
                    "vod_play_from":   "迷妹网",
                    "vod_play_url":    f"{title or f'视频_{vid}'}${play_url}" if play_url else "",
                }],
            }
        except Exception as e:
            log.error("detailContent 失败: %s", e)
            return {"list": []}

    def _find_detail_html(self, vid):
        """直连 6 个分类的详情 URL（最多 6 次请求），不再扫描分页列表。"""
        for cat in CATEGORY_MAP:
            try:
                path = f"/suoyoushipin/{cat}/{vid}.html"
                r = self._get(path)
                if RE_M3U8_HASH.search(r.text):
                    log.info("  直连命中: %s", path)
                    return r.text
            except:
                pass
        log.warning("  6分类直连全miss: vid=%s", vid)
        return None

    def _req_headers_for_playback(self):
        """构造播放所需的请求头（含 Referer 反盗链）。"""
        return {
            "User-Agent": HEADERS.get("User-Agent", ""),
            "Referer": self.base_url + "/",
        }

    # ------------------------------------------------------------------
    def searchContent(self, key, quick, pg="1"):
        log.info("searchContent key=%s quick=%s", key, quick)
        try:
            r = self._post(SEARCH_URL, data={
                "keyboard": key,
                "show":     "title",
                "tempid":   "1",
            })
            items = self._extract_list_from_html(r.text)
            if not items:
                r2 = self._get(f"/search/?q={key}")
                items = self._extract_list_from_html(r2.text)
            return {"list": items}
        except Exception as e:
            log.error("searchContent 失败: %s", e)
            return {"list": []}

    # ------------------------------------------------------------------
    def playerContent(self, flag, id, vipFlags=None):
        """
        flag=线路标识（如"迷妹网"），id=detailContent 返回的 vod_play_url
        中该线路对应的播放地址（直接就是 m3u8 URL）。
        无需再发 HTTP 请求，直接返回即可。
        """
        log.info("playerContent flag=%s id=%s", flag, str(id)[:80])
        try:
            vid_or_url = str(id)
            # id 就是 m3u8 URL，直接返回
            if vid_or_url.startswith("http"):
                return {
                    "url": vid_or_url,
                    "parse": 0,
                    "header": self._req_headers_for_playback(),
                }
            # 兜底：id 是纯数字 vid，走缓存/直连查找
            hash_val = self._hash_cache.get(vid_or_url)
            if not hash_val:
                detail_html = self._find_detail_html(vid_or_url)
                if detail_html:
                    m = RE_M3U8_HASH.search(detail_html)
                    if m:
                        hash_val = m.group(1)
                        self._hash_cache[vid_or_url] = hash_val
            if hash_val:
                return {
                    "url": f"{CDN_HLS}/{hash_val}/index.m3u8",
                    "parse": 0,
                    "header": self._req_headers_for_playback(),
                }
            return {"url": "", "parse": 0, "header": {}}
        except Exception as e:
            log.error("playerContent 失败: %s", e)
            return {"url": "", "parse": 0, "header": {}}


# ---------------------------------------------------------------------------
# 独立运行测试
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    spider = Spider()
    spider.init()

    print("\n=== homeContent ===")
    result = spider.homeContent(None)
    print(f"分类数: {len(result.get('class', []))}")
    print(f"首页视频数: {len(result.get('list', []))}")
    if result.get("list"):
        item = result["list"][0]
        print(f"  首条: {item['vod_name']} | {item['vod_id']}")

    print("\n=== categoryContent (国产, pg=1) ===")
    result = spider.categoryContent("guochan", 1, None, None)
    print(f"当前页: {result.get('page')}/{result.get('pagecount')}, 视频数: {len(result.get('list', []))}")

    print("\n=== categoryContent (日韩, pg=1) ===")
    result = spider.categoryContent("rihan", 1, None, None)
    print(f"当前页: {result.get('page')}/{result.get('pagecount')}, 视频数: {len(result.get('list', []))}")

    print("\n=== detailContent ===")
    home = spider.homeContent(None)
    if home.get("list"):
        first = home["list"][0]
        result = spider.detailContent([first["vod_id"]])
        if result.get("list"):
            d = result["list"][0]
            print(f"  标题: {d['vod_name']}")
            print(f"  播放: {d['vod_play_url']}")

    print("\n=== searchContent (美女) ===")
    result = spider.searchContent("美女", False)
    print(f"搜索结果数: {len(result.get('list', []))}")

    print("\n=== playerContent ===")
    if home.get("list"):
        first = home["list"][0]
        result = spider.playerContent("迷妹网", first["vod_id"])
        print(f"  播放地址: {result.get('url', '')}")

    spider.destroy()
    print("\nDone.")
