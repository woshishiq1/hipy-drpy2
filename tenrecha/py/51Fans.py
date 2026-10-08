# -*- coding: utf-8 -*-
"""
51Fans (m.fansg.cc) TV Box 爬虫
支持分类、列表、详情、m3u8播放提取
修复：分类分页（第2页起 URL 为 /category/{tid}/{page}/）
"""
import re
import json
import urllib.request
import urllib.error
import urllib.parse

HOST = "https://m.fansg.cc"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": HOST + "/",
}


class Spider:
    def __init__(self):
        self.host = HOST
        self.name = "51Fans"

    # ── 工具方法 ──
    def _fetch(self, url):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            print("[51Fans] fetch error: %s" % e)
            return ""

    def _parse_cards(self, html):
        """解析列表页卡片（分类页、搜索页）"""
        cards = []
        pattern = re.compile(
            r'<article[^>]*class="[^"]*seo-media-card[^"]*"[^>]*>'
            r'.*?<a[^>]*href="(/video/(\d+)/?)"[^>]*>'
            r'.*?<img[^>]*data-cover="([^"]+)"[^>]*>'
            r'.*?<h3><a[^>]*>([^<]+)</a></h3>'
            r'.*?<p><span>([^<]*)</span>.*?<span>([^<]*)次播放</span>',
            re.DOTALL
        )
        for m in pattern.finditer(html):
            href, vid, cover, title, category, views = m.groups()
            cards.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": cover if cover.startswith("http") else (HOST + cover),
                "vod_remarks": "%s %s" % (category.strip(), views.strip()),
            })
        if not cards:
            pattern2 = re.compile(
                r'<a[^>]*href="(/video/(\d+)/?)"[^>]*>.*?<img[^>]*data-cover="([^"]+)"[^>]*>.*?<h3>.*?<a[^>]*>([^<]+)</a>',
                re.DOTALL
            )
            for m in pattern2.finditer(html):
                href, vid, cover, title = m.groups()
                cards.append({
                    "vod_id": vid,
                    "vod_name": title.strip(),
                    "vod_pic": cover if cover.startswith("http") else (HOST + cover),
                    "vod_remarks": "",
                })
        return cards

    # ═══════════════════════════════════════════════════════════════
    # 🔧 修复：提取总页数（增强版）
    # ═══════════════════════════════════════════════════════════════
    def _extract_page_count(self, html):
        """从分页导航中提取总页数（支持 /category/cate4/2/ 格式）"""
        # 定位分页区域
        pagination = re.search(
            r'<nav[^>]*class="[^"]*seo-pagination[^"]*"[^>]*>(.*?)</nav>',
            html, re.DOTALL
        )
        if not pagination:
            return 1

        nav_html = pagination.group(1)
        # 提取所有数字页码（包括尾页）
        nums = re.findall(r'>(\d+)</a>', nav_html)
        # 也提取“…”后面的数字（可能有尾页）
        nums += re.findall(r'…\s*<a[^>]*>(\d+)</a>', nav_html)
        if nums:
            return max(int(n) for n in nums)
        # 如果没有数字，检查是否有“下一页”链接，有则至少2页
        if re.search(r'下一页</a>', nav_html):
            return 2
        return 1

    # ── 首页分类 ──
    def homeContent(self, filter=None):
        cats = [
            {"type_id": "cate4", "type_name": "颜值少女"},
            {"type_id": "cate5", "type_name": "极品嫩穴"},
            {"type_id": "cate6", "type_name": "网曝黑料"},
            {"type_id": "cate7", "type_name": "激情大秀"},
            {"type_id": "cate8", "type_name": "偷欢黑人"},
            {"type_id": "cate9", "type_name": "迷药罪恶"},
            {"type_id": "cate10", "type_name": "反差女神"},
            {"type_id": "cate11", "type_name": "精选动漫"},
            {"type_id": "cate12", "type_name": "探花精选"},
            {"type_id": "cate13", "type_name": "蜜桃科技"},
            {"type_id": "cate14", "type_name": "明星换脸"},
            {"type_id": "cate15", "type_name": "异域风情"},
            {"type_id": "cate16", "type_name": "重口猎奇"},
            {"type_id": "cate17", "type_name": "蜜桃福利"},
            {"type_id": "cate18", "type_name": "精选AV"},
            {"type_id": "cate19", "type_name": "蜜桃剧场"},
        ]
        return {"class": cats}

    # ── 首页推荐 ──
    def homeVideoContent(self):
        html = self._fetch(self.host + "/")
        cards = self._parse_cards(html)
        return {"list": cards[:20]}

    # ═══════════════════════════════════════════════════════════════
    # 🔧 分类列表（修复分页 URL 和总页数）
    # ═══════════════════════════════════════════════════════════════
    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        pg = int(pg or 1)
        # 构造分类 URL：第1页为 /category/{tid}/，后续为 /category/{tid}/{page}/
        if pg == 1:
            url = self.host + "/category/%s/" % tid
        else:
            url = self.host + "/category/%s/%s/" % (tid, pg)

        html = self._fetch(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "total": 0}

        cards = self._parse_cards(html)
        pagecount = self._extract_page_count(html)
        # 估算总条目数（假设每页24条，取 pagecount * 24）
        limit = 24
        total = pagecount * limit
        return {
            "list": cards,
            "page": pg,
            "pagecount": pagecount,
            "limit": limit,
            "total": total,
        }

    # ── 详情页 ──
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = ids[0]
        url = self.host + "/video/%s/" % vid
        html = self._fetch(url)
        if not html:
            return {"list": []}

        title = ""
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if m:
            title = m.group(1).strip()
        if not title:
            m = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', html)
            if m:
                title = m.group(1).strip()

        cover = ""
        m = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
        if m:
            cover = m.group(1)
        if not cover:
            m = re.search(r'<img[^>]*data-cover="([^"]+)"[^>]*>', html)
            if m:
                cover = m.group(1)

        tags = []
        for m in re.finditer(r'<a[^>]*href="/tag/[^"]*"[^>]*>([^<]+)</a>', html):
            tags.append(m.group(1).strip())

        play_url = ""
        m = re.search(r'<div[^>]*id="article-videos"[^>]*data-url="([^"]+)"[^>]*data-cdnline="([^"]+)"', html)
        if m:
            raw, cdn = m.groups()
            play_url = cdn + raw
        if not play_url:
            m = re.search(r'<video[^>]*src="([^"]+)"', html)
            if m:
                play_url = m.group(1)

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": cover,
            "vod_remarks": " ".join(tags[:3]),
            "vod_content": " ".join(tags),
            "vod_play_from": "播放源",
            "vod_play_url": "正片$%s" % play_url if play_url else "",
        }
        return {"list": [vod]}

    # ── 搜索 ──
    def searchContent(self, key, quick=False, pg=1):
        pg = int(pg or 1)
        encoded = urllib.parse.quote(key)
        url = self.host + "/search/%s/" % encoded
        if pg > 1:
            url += "page/%s/" % pg
        html = self._fetch(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "total": 0}
        cards = self._parse_cards(html)
        pagecount = self._extract_page_count(html)
        limit = 24
        total = pagecount * limit
        return {
            "list": cards,
            "page": pg,
            "pagecount": pagecount,
            "limit": limit,
            "total": total,
        }

    # ── 播放 ──
    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {"parse": 0, "url": "", "header": {}}

        if id.startswith("http"):
            return {
                "parse": 0,
                "url": id,
                "header": {
                    "Referer": self.host + "/",
                    "User-Agent": HEADERS["User-Agent"],
                }
            }

        url = self.host + "/video/%s/" % id
        html = self._fetch(url)
        if not html:
            return {"parse": 0, "url": "", "header": {}}

        play_url = ""
        m = re.search(r'<div[^>]*id="article-videos"[^>]*data-url="([^"]+)"[^>]*data-cdnline="([^"]+)"', html)
        if m:
            raw, cdn = m.groups()
            play_url = cdn + raw
        if not play_url:
            m = re.search(r'<video[^>]*src="([^"]+)"', html)
            if m:
                play_url = m.group(1)

        if play_url:
            return {
                "parse": 0,
                "url": play_url,
                "header": {
                    "Referer": self.host + "/",
                    "User-Agent": HEADERS["User-Agent"],
                }
            }
        else:
            return {"parse": 1, "url": url, "header": {"Referer": self.host + "/"}}

    # ── 其他必须方法 ──
    def getName(self):
        return self.name

    def init(self, extend=""):
        pass

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|webm|flv)(\?|$)', str(url), re.I))

    def manualVideoCheck(self):
        return False

    def getHomeContent(self, filter=True):
        return self.homeContent(filter)

    def getDependence(self):
        return []


# ── 实例化 ──
spider = Spider()


# ── 测试 ──
if __name__ == "__main__":
    s = Spider()
    print("Spider name:", s.getName())

    print("\n--- 首页分类 ---")
    for c in s.homeContent()["class"][:3]:
        print("  %s: %s" % (c["type_id"], c["type_name"]))

    print("\n--- 分类第1页 ---")
    cat1 = s.categoryContent("cate4", 1)
    print("获取 %s 条，总页数 %s" % (len(cat1["list"]), cat1["pagecount"]))

    print("\n--- 分类第2页 ---")
    cat2 = s.categoryContent("cate4", 2)
    print("获取 %s 条，总页数 %s" % (len(cat2["list"]), cat2["pagecount"]))