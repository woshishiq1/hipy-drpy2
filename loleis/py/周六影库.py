#coding=utf-8
#!/usr/bin/python
"""
影视仓 (CatVod) Python 爬虫源 - 58影视 (58hu.com)
===================================================


网站结构 (苹果CMS):
  分类页: /index.php/vod/type/id/{id}.html
  筛选:   /index.php/vod/show/class/{类型}/id/{id}/year/{年份}/page/{页码}.html
  详情页: /index.php/vod/detail/id/{id}.html
  播放页: /index.php/vod/play/id/{id}/sid/{sid}/nid/{nid}.html
  搜索:   /index.php/vod/search.html?wd={keyword}
  搜索分页: /index.php/vod/search/page/{page}/wd/{keyword}.html

播放解析:
  player_data.url -> 第三方链接 (腾讯/优酷/爱奇艺等)
  通过 jxcb.58hu.com 解析接口获取真实播放地址
  playerconfig.js 中定义了所有线路的解析地址

分类ID:
  1=电影, 2=连续剧, 3=综艺, 4=动漫, 5=短剧
  6=动作片, 7=喜剧片, 8=爱情片, 9=科幻片, 10=恐怖片, 11=剧情片, 12=战争片
  13=国产剧, 14=港台剧, 15=日韩剧, 16=欧美剧, 17=海外剧
"""

import re
import sys
import json
import time
import random
from urllib.parse import quote, urljoin

sys.path.append("..")

try:
    from pyquery import PyQuery as pq
except ImportError:
    pass

from base.spider import Spider


class Spider(Spider):

    host = "https://www.58hu.com"

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Referer": host,
    }

    # 播放器配置 (来自 playerconfig.js)
    # 所有线路的解析接口
    parse_url = "https://jxcb.58hu.com/?url="
    parse_url2 = "https://qcbl.xundog.com/?url="

    # 电影子分类
    movie_sub = [
        {"n": "全部", "v": ""},
        {"n": "动作片", "v": "6"},
        {"n": "喜剧片", "v": "7"},
        {"n": "爱情片", "v": "8"},
        {"n": "科幻片", "v": "9"},
        {"n": "恐怖片", "v": "10"},
        {"n": "剧情片", "v": "11"},
        {"n": "战争片", "v": "12"},
        {"n": "纪录片", "v": "22"},
    ]

    # 连续剧子分类
    tv_sub = [
        {"n": "全部", "v": ""},
        {"n": "国产剧", "v": "13"},
        {"n": "港台剧", "v": "14"},
        {"n": "日韩剧", "v": "15"},
        {"n": "欧美剧", "v": "16"},
        {"n": "海外剧", "v": "17"},
    ]

    # 年份选项
    years = [{"n": "全部", "v": ""}]
    for _y in range(2026, 2014, -1):
        years.append({"n": str(_y), "v": str(_y)})

    # 类型标签 (用于 class 筛选)
    tags = [
        {"n": "全部", "v": ""},
        {"n": "喜剧", "v": "喜剧"},
        {"n": "爱情", "v": "爱情"},
        {"n": "恐怖", "v": "恐怖"},
        {"n": "动作", "v": "动作"},
        {"n": "科幻", "v": "科幻"},
        {"n": "剧情", "v": "剧情"},
        {"n": "战争", "v": "战争"},
        {"n": "犯罪", "v": "犯罪"},
        {"n": "奇幻", "v": "奇幻"},
        {"n": "悬疑", "v": "悬疑"},
        {"n": "动画", "v": "动画"},
    ]

    def init(self, extend=""):
        pass

    def getName(self):
        return "58影视"

    def destroy(self):
        pass

    def action(self, action):
        return None

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(m3u8|mp4|flv|avi)(\?|$)", url))

    def manualVideoCheck(self):
        return False

    # --------------------------------------------------------
    # 首页分类 + 筛选配置
    # --------------------------------------------------------
    def homeContent(self, filter):
        html = self.fetch(self.host, headers=self.headers).text
        data = self.getpq(html)

        classes = []
        # 从导航栏提取分类
        for a in data("a[href*='/vod/type/']").items():
            href = a.attr("href")
            if href:
                m = re.search(r"id/(\d+)", href)
                if m:
                    classes.append({
                        "type_name": a.text().strip(),
                        "type_id": m.group(1)
                    })

        # 去重
        seen = set()
        unique_classes = []
        for c in classes:
            if c["type_id"] not in seen and c["type_name"]:
                seen.add(c["type_id"])
                unique_classes.append(c)

        result = {"class": unique_classes[:8]}

        # 筛选配置
        if filter:
            result["filters"] = {}
            # 电影: 子分类 + 类型标签 + 年份
            result["filters"]["1"] = [
                {"key": "cateId", "name": "分类", "value": self.movie_sub},
                {"key": "class", "name": "类型", "value": self.tags},
                {"key": "year", "name": "年份", "value": self.years},
            ]
            # 连续剧: 子分类 + 年份
            result["filters"]["2"] = [
                {"key": "cateId", "name": "分类", "value": self.tv_sub},
                {"key": "year", "name": "年份", "value": self.years},
            ]
            # 综艺: 年份
            result["filters"]["3"] = [
                {"key": "year", "name": "年份", "value": self.years},
            ]
            # 动漫: 年份
            result["filters"]["4"] = [
                {"key": "year", "name": "年份", "value": self.years},
            ]
            # 短剧: 年份
            result["filters"]["5"] = [
                {"key": "year", "name": "年份", "value": self.years},
            ]

        return result

    # --------------------------------------------------------
    # 首页推荐
    # --------------------------------------------------------
    def homeVideoContent(self):
        html = self.fetch(self.host, headers=self.headers).text
        data = self.getpq(html)
        videos = []
        # 首页结构: div.box-title (标题) + 兄弟 div.layout-box (影片列表)
        for bt in data(".box-title").items():
            h2 = bt.find("h2")
            title = h2.text().strip() if h2 else ""
            if "热播榜" in title:
                continue
            # 找紧跟的兄弟 div.layout-box
            for sib in bt.next_all().items():
                if sib.is_("div") and sib.hasClass("layout-box"):
                    for item in sib.find("li.pic-list-hover").items():
                        v = self.parse_card(item)
                        if v:
                            videos.append(v)
                    break
        return {"list": videos}

    # --------------------------------------------------------
    # 分类列表 (支持筛选)
    # --------------------------------------------------------
    def categoryContent(self, tid, pg, filter, extend):
        # 构建筛选URL
        # 格式: /index.php/vod/show/class/{类型}/id/{id}/year/{年份}/page/{页码}.html
        cate_id = tid
        cls = ""
        year = ""

        if extend:
            if extend.get("cateId"):
                cate_id = extend["cateId"]
            if extend.get("class"):
                cls = extend["class"]
            if extend.get("year"):
                year = extend["year"]

        url_parts = [f"{self.host}/index.php/vod/show"]
        if cls:
            url_parts.append(f"class/{quote(cls)}")
        url_parts.append(f"id/{cate_id}")
        if year:
            url_parts.append(f"year/{year}")
        url_parts.append(f"page/{pg}.html")
        url = "/".join(url_parts)

        html = self.fetch(url, headers=self.headers).text
        data = self.getpq(html)

        videos = self.getlist(data(".border-box, .public-r, .box"))

        # 解析分页
        pagecount = 9999
        page_text = data(".page").text()
        m = re.search(r"(\d+)/(\d+)", page_text)
        if m:
            pagecount = int(m.group(2))

        return {
            "list": videos,
            "page": int(pg),
            "pagecount": pagecount,
            "limit": 90,
            "total": 999999
        }

    # --------------------------------------------------------
    # 详情
    # --------------------------------------------------------
    def detailContent(self, ids):
        url = f"{self.host}/index.php/vod/detail/id/{ids[0]}.html"
        html = self.fetch(url, headers=self.headers).text
        data = self.getpq(html)

        vod = {
            "vod_id": ids[0],
            "vod_name": data("h1").text().strip() or data("title").text().split("-")[0].strip(),
            "vod_pic": data("img[data-original]").attr("data-original") or data("img.lazyload").attr("data-original") or "",
            "type_name": "",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": ""
        }

        # 解析详情信息
        info_div = data(".video-info")
        if info_div:
            for div in info_div("div").items():
                text = div.text().strip()
                if text.startswith("类型："):
                    vod["type_name"] = text.replace("类型：", "").strip()
                elif text.startswith("年代："):
                    vod["vod_year"] = text.replace("年代：", "").strip()
                elif text.startswith("国家地区："):
                    vod["vod_area"] = text.replace("国家地区：", "").strip()
                elif text.startswith("状态："):
                    vod["vod_remarks"] = text.replace("状态：", "").strip()
                elif text.startswith("主演："):
                    vod["vod_actor"] = text.replace("主演：", "").strip()
                elif text.startswith("导演："):
                    vod["vod_director"] = text.replace("导演：", "").strip()
                elif text.startswith("简介："):
                    vod["vod_content"] = text.replace("简介：", "").strip()

        # 解析播放源
        tab_links = data("a.gico")
        tab_names = [a.text().strip() for a in tab_links.items() if a.text().strip()]

        playlists = data("ul.fade-in")
        if not playlists:
            playlists = data("ul.playlist")

        play_from = []
        play_url = []

        for i in range(len(playlists)):
            name = f"线路{i + 1}"
            if i < len(tab_names):
                name = tab_names[i]
            play_from.append(name)

            episodes = []
            ul = playlists.eq(i)
            for li in ul("li a").items():
                title = li.text().strip()
                href = li.attr("href")
                if title and href:
                    m = re.search(r"sid/(\d+)/nid/(\d+)", href)
                    if m:
                        sid, nid = m.group(1), m.group(2)
                        episodes.append(f"{title}${ids[0]}/{sid}/{nid}")

            play_url.append("#".join(episodes))

        vod["vod_play_from"] = "$$$".join(play_from)
        vod["vod_play_url"] = "$$$".join(play_url)

        return {"list": [vod]}

    # --------------------------------------------------------
    # 搜索
    # --------------------------------------------------------
    def searchContent(self, key, quick, pg="1"):
        if str(pg) == "1":
            url = f"{self.host}/index.php/vod/search.html?wd={quote(key)}"
        else:
            url = f"{self.host}/index.php/vod/search/page/{pg}/wd/{quote(key)}.html"

        html = self.fetch(url, headers=self.headers).text
        data = self.getpq(html)
        videos = []

        # 搜索结果在 h2.font16 a 中 (ul.pic-list.box-news-list > li > h2 > a)
        for h2 in data("h2.font16").items():
            a = h2.find("a[href*='/vod/detail/']")
            if not a:
                continue
            href = a.attr("href")
            if not href:
                continue

            m = re.search(r"id/(\d+)", href)
            if not m:
                continue

            vid = m.group(1)
            title = a.text().strip()
            if not title:
                continue

            # 图片在 li 层级 (h2 的祖父元素)
            pic = ""
            li = h2.closest("li")
            if li:
                img = li.find("img")
                if img:
                    pic = img.attr("data-original") or img.attr("src") or ""

            # 提取状态信息 (li > div > p 第一个)
            remarks = ""
            if li:
                p = li.find("p.text-muted")
                if p:
                    remarks = p.text().strip()

            videos.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks
            })

        return {"list": videos, "page": pg}

    # --------------------------------------------------------
    # 播放解析
    # --------------------------------------------------------
    def playerContent(self, flag, id, vipFlags):
        """
        flag: 播放源名称
        id: videoId/sid/nid
        """
        parts = str(id).split("/")
        if len(parts) != 3:
            return {"parse": 1, "url": "", "header": self.headers}

        video_id, sid, nid = parts
        url = f"{self.host}/index.php/vod/play/id/{video_id}/sid/{sid}/nid/{nid}.html"

        html = self.fetch(url, headers=self.headers).text

        play_url = ""
        source_from = ""

        # 从 player_data JSON 提取
        m = re.search(r'var\s+player_data\s*=\s*(\{[^<]+\})', html)
        if m:
            try:
                pd = json.loads(m.group(1))
                play_url = pd.get("url", "").replace("\\/", "/")
                source_from = pd.get("from", "")
            except (json.JSONDecodeError, KeyError):
                pass

        # 备用: 从 iframe 提取
        if not play_url:
            m = re.search(r'<iframe[^>]+src="([^"]+)"', html)
            if m:
                play_url = m.group(1).replace("\\/", "/")

        if not play_url:
            return {"parse": 1, "url": f"{self.host}{url}", "header": self.headers}

        # 如果已经是直链格式
        if self.isVideoFormat(play_url):
            return {
                "parse": 0,
                "playUrl": "",
                "url": play_url,
                "header": self.headers
            }

        # 第三方平台链接 -> 通过解析接口获取真实地址
        # 解析接口: jxcb.58hu.com/?url= (来自 playerconfig.js)
        # 该接口返回 MizhiPlayerART 播放器页面，内含 AES 解密逻辑
        # 影视仓无法直接执行 JS，所以返回 parse=1 让影视仓处理
        jx_url = self.parse_url + play_url

        return {
            "parse": 1,
            "playUrl": "",
            "url": jx_url,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host,
            }
        }

    # --------------------------------------------------------
    # 本地代理
    # --------------------------------------------------------
    def localProxy(self, param):
        return None

    # --------------------------------------------------------
    # 工具方法
    # --------------------------------------------------------
    def getlist(self, data):
        """从容器中提取视频列表"""
        videos = []

        # 方式1: box-title + layout-box (首页结构)
        for bt in data(".box-title").items():
            h2 = bt.find("h2")
            title = h2.text().strip() if h2 else ""
            if "热播榜" in title:
                continue
            for sib in bt.next_all().items():
                if sib.is_("div") and sib.hasClass("layout-box"):
                    for item in sib.find("li.pic-list-hover").items():
                        v = self.parse_card(item)
                        if v:
                            videos.append(v)
                    break

        # 方式2: 直接在容器中查找 (分类列表页)
        if not videos:
            for item in data.find("li.pic-list-hover").items():
                v = self.parse_card(item)
                if v:
                    videos.append(v)

        return videos

    def parse_card(self, item):
        """解析单个影片卡片"""
        try:
            a = item.find("a[href*='/vod/detail/']")
            if not a:
                return None

            href = a.attr("href")
            title = a.attr("title") or a.text().strip()

            if not href or not title:
                return None

            m = re.search(r"id/(\d+)", href)
            if not m:
                return None

            vid = m.group(1)

            img = item.find("img")
            pic = img.attr("data-original") or img.attr("src") or ""

            score = item.find("span.score").text().strip()
            status = item.find("span.titles").text().strip()

            remarks = score
            if status:
                remarks = f"{score} {status}".strip() if score else status

            return {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks
            }
        except Exception:
            return None

    def getpq(self, data):
        """创建 PyQuery 对象"""
        try:
            return pq(data)
        except Exception:
            return pq(data.encode("utf-8"))
