# -*- coding: utf-8 -*-
"""
四壳通用Python Spider - ayk (乳香影院)
站点类型: 苹果CMS v10 (061vip2_wtpl模板, 简化URL重写)
核心特征: 分类页/vodtype/{tid}.html, 详情页/{id}.html, 播放地址藏于JS变量rawUrl
"""

import re
import json
import urllib.parse

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        def init(self, extend=""):
            pass
        def homeContent(self, filter):
            return {}
        def categoryContent(self, tid, pg, filter, extend):
            return {}
        def detailContent(self, ids):
            return {}
        def searchContent(self, key, quick, pg):
            return {}
        def playerContent(self, flag, id, vipFlags):
            return {}
        def getDependence(self):
            return ""
        def localProxy(self, param):
            return [404, "text/plain", ""]
        def destroy(self):
            pass
        def isVideoFormat(self, url):
            return False
        def getName(self):
            return ""
        def getApp(self):
            return ""
        def isManualVideo(self):
            return False

try:
    import requests
except Exception:
    requests = None


# 未成年关键词（铁律13：命中即跳过不返回）
JUVENILE_KEYWORDS = [
    "萝莉", "幼女", "少女", "童", "未成年", "teen", "loli", "schoolgirl",
    "小学生", "初中生", "高中生", "学生妹", "幼", "小女", "女童", "儿童",
    "young", "petite", "teenie", "underage", "minor",
]


def _is_juvenile(text):
    """检测文本是否含未成年相关词，命中返回True（需跳过）"""
    if not text:
        return False
    t = text.lower()
    for kw in JUVENILE_KEYWORDS:
        if kw.lower() in t:
            return True
    return False


class Spider(BaseSpider):
    """四壳通用Spider - ayk"""

    # 站点配置
    baseUrl = "https://ayk.rxyy8.buzz"
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    # 分类列表
    classList = [
        {"type_id": "20", "type_name": "国产视频"},
        {"type_id": "21", "type_name": "日韩有码"},
        {"type_id": "22", "type_name": "日韩无码"},
        {"type_id": "23", "type_name": "制服学生"},
        {"type_id": "24", "type_name": "动漫卡通"},
        {"type_id": "25", "type_name": "欧美变态"},
        {"type_id": "26", "type_name": "三级伦理"},
    ]

    filters = {}

    def __init__(self):
        self.rawSite = self.baseUrl
        self.siteUrl = self.baseUrl
        self.HOST = self.baseUrl
        self.extend = ""
        self.session = None

    # ==================== 工具方法 ====================

    def _get_session(self):
        if self.session is None:
            if requests:
                self.session = requests.Session()
                self.session.headers.update(self.header)
        return self.session

    def _http_get(self, url, timeout=15):
        """HTTP GET请求"""
        try:
            sess = self._get_session()
            if sess:
                r = sess.get(url, timeout=timeout, allow_redirects=True)
                return r.text
            else:
                import urllib.request
                req = urllib.request.Request(url, headers=self.header)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"[ayk] GET error: {e}")
            return ""

    def _parse_list_page(self, html):
        """
        解析列表页（分类页/搜索页），提取视频卡片
        本站视频卡片：封面和标题在不同a标签中，均指向/{id}.html
        返回: list of {vod_id, vod_name, vod_pic, vod_remarks}
        """
        # 按vod_id收集信息
        vod_info = {}

        # 1. 提取所有 /数字.html 链接及其周围内容
        # 匹配含封面图的a标签
        pic_pattern = re.compile(
            r'<a[^>]*href="/(\d+)\.html"[^>]*>\s*<img[^>]*(?:data-original|src)="([^"]+)"',
            re.DOTALL
        )
        for m in pic_pattern.finditer(html):
            vid = m.group(1)
            pic = m.group(2).strip()
            if vid not in vod_info:
                vod_info[vid] = {"vod_id": vid, "vod_name": "", "vod_pic": pic, "vod_remarks": ""}
            else:
                vod_info[vid]["vod_pic"] = pic

        # 2. 提取标题（不含img的纯文本a标签）
        title_pattern = re.compile(
            r'<a[^>]*href="/(\d+)\.html"[^>]*>([^<]+)</a>',
            re.DOTALL
        )
        for m in title_pattern.finditer(html):
            vid = m.group(1)
            title = m.group(2).strip()
            # 跳过纯数字/日期/短文本
            if title and len(title) > 2 and not re.match(r'^\d{2}-\d{2}$', title):
                if vid not in vod_info:
                    vod_info[vid] = {"vod_id": vid, "vod_name": title, "vod_pic": "", "vod_remarks": ""}
                else:
                    if not vod_info[vid]["vod_name"]:
                        vod_info[vid]["vod_name"] = title

        # 3. 过滤未成年条目，构建结果列表
        results = []
        for vid, info in vod_info.items():
            if _is_juvenile(info["vod_name"]):
                continue
            if info["vod_name"] or info["vod_pic"]:
                results.append(info)

        return results

    def _parse_total_pages(self, html, tid=None):
        """解析总页数 - 本站分页格式 /vodtype/{tid}-{page}.html"""
        if tid:
            pages = re.findall(rf'/vodtype/{tid}-(\d+)\.html', html)
        else:
            pages = re.findall(r'/vodtype/\d+-(\d+)\.html', html)
        if pages:
            return max(int(p) for p in pages)
        return 1

    def _parse_detail_page(self, html):
        """
        解析详情页，提取标题、播放地址等
        本站播放地址藏于 JS: const rawUrl = '...m3u8';
        """
        result = {
            "vod_name": "",
            "vod_pic": "",
            "vod_content": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "",
            "vod_score": "",
            "play_url": "",
            "play_from": "dplayer",
        }

        # 1. 提取播放地址 rawUrl
        raw_m = re.search(r"const\s+rawUrl\s*=\s*['\"]([^'\"]+)['\"]", html)
        if raw_m:
            result["play_url"] = raw_m.group(1).strip()
        else:
            # 兜底：直接找m3u8链接
            m3u8_m = re.search(r"['\"](https?://[^'\"]+\.m3u8[^'\"]*)['\"]", html)
            if m3u8_m:
                result["play_url"] = m3u8_m.group(1).strip()

        # 2. 提取标题 <title>标题 -乳香影院</title>
        title_m = re.search(r"<title>([^<]+?)\s*[-–—]\s*乳香影院</title>", html)
        if title_m:
            result["vod_name"] = title_m.group(1).strip()
        else:
            title_m2 = re.search(r"<title>([^<]+)</title>", html)
            if title_m2:
                t = title_m2.group(1).strip()
                # 去掉站点名后缀
                t = re.sub(r"\s*[-–—]\s*乳香影院\s*$", "", t)
                result["vod_name"] = t

        # 3. 提取封面
        pic_m = re.search(r'(?:data-original|src)="([^"]+\.(?:jpg|jpeg|png|webp))"', html)
        if pic_m:
            result["vod_pic"] = pic_m.group(1).strip()

        # 4. 提取详情信息（主演/导演/类型/年份/地区）
        for label, key in [("主演", "vod_actor"), ("导演", "vod_director"), ("类型", "vod_remarks"), ("年份", "vod_year"), ("地区", "vod_area")]:
            m = re.search(rf'{label}[:：]\s*</?[^>]*>?\s*([^<\n]+)', html)
            if m:
                result[key] = m.group(1).strip()

        # 5. 提取简介
        desc_m = re.search(r'简介[:：]\s*</?[^>]*>?\s*([\s\S]{10,500}?)(?:</div>|<br|</p>)', html)
        if desc_m:
            content = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip()
            if content and len(content) > 5:
                result["vod_content"] = content

        return result

    # ==================== 13标准接口 ====================

    def init(self, extend=""):
        """初始化"""
        self.extend = extend if extend else ""
        if self.extend:
            try:
                ext = json.loads(self.extend) if isinstance(self.extend, str) else self.extend
                if ext.get("siteUrl"):
                    self.siteUrl = ext["siteUrl"]
                    self.HOST = self.siteUrl
                if ext.get("proxy"):
                    self.siteUrl = ext["proxy"]
                    self.HOST = self.siteUrl
                if ext.get("direct") is True:
                    self.siteUrl = self.baseUrl
                    self.HOST = self.baseUrl
            except Exception:
                pass

    def homeContent(self, filter=None):
        """首页：返回分类列表+filters"""
        return {
            "class": self.classList,
            "filters": self.filters,
        }

    def categoryContent(self, tid, pg, filter=None, extend=None):
        """
        分类内容
        本站URL: /vodtype/{tid}.html (page=1), /vodtype/{tid}-{page}.html (page>1)
        """
        pg = int(pg) if pg else 1
        if pg == 1:
            url = f"{self.baseUrl}/vodtype/{tid}.html"
        else:
            url = f"{self.baseUrl}/vodtype/{tid}-{pg}.html"

        html = self._http_get(url)
        if not html:
            return {"page": pg, "pagecount": 1, "limit": 60, "total": 0, "list": []}

        vod_list = self._parse_list_page(html)
        pagecount = self._parse_total_pages(html, tid=tid)
        total = pagecount * 60

        return {
            "page": pg,
            "pagecount": pagecount,
            "limit": 60,
            "total": total,
            "list": vod_list,
        }

    def detailContent(self, ids):
        """
        详情内容
        本站详情页: /{vod_id}.html
        """
        if isinstance(ids, str):
            ids = [ids]

        vod_list = []
        for vod_id in ids:
            if not vod_id:
                continue
            url = f"{self.baseUrl}/{vod_id}.html"
            html = self._http_get(url)
            if not html:
                continue

            info = self._parse_detail_page(html)

            # 铁律13：未成年相关条目跳过
            if _is_juvenile(info.get("vod_name", "")) or _is_juvenile(info.get("vod_content", "")):
                continue

            vod_item = {
                "vod_id": str(vod_id),
                "vod_name": info.get("vod_name", ""),
                "vod_pic": info.get("vod_pic", ""),
                "vod_content": info.get("vod_content", ""),
                "vod_actor": info.get("vod_actor", ""),
                "vod_director": info.get("vod_director", ""),
                "vod_year": info.get("vod_year", ""),
                "vod_area": info.get("vod_area", ""),
                "vod_remarks": info.get("vod_remarks", ""),
                "vod_score": info.get("vod_score", ""),
                "vod_play_from": info.get("play_from", "dplayer"),
                "vod_play_url": info.get("play_url", ""),
            }
            vod_list.append(vod_item)

        return {"list": vod_list}

    def searchContent(self, key, quick=None, pg=None):
        """
        搜索内容
        本站搜索: /s/index.html?wd=关键词
        """
        pg = int(pg) if pg else 1
        params = {"wd": key}
        if pg > 1:
            params["page"] = pg
        url = f"{self.baseUrl}/s/index.html?{urllib.parse.urlencode(params)}"

        html = self._http_get(url)
        if not html:
            return {"page": pg, "pagecount": 1, "limit": 60, "total": 0, "list": []}

        vod_list = self._parse_list_page(html)
        # 搜索页分页可能不同，保守估计
        pagecount = max(1, self._parse_total_pages(html))
        total = pagecount * 60

        return {
            "page": pg,
            "pagecount": pagecount,
            "limit": 60,
            "total": total,
            "list": vod_list,
        }

    def playerContent(self, flag, id, vipFlags=None):
        """播放内容"""
        header = {
            "User-Agent": self.header["User-Agent"],
            "Referer": self.baseUrl + "/",
            "Origin": self.baseUrl,
        }
        return {
            "parse": 0,
            "jx": 0,
            "url": id,
            "header": header,
        }

    def getDependence(self):
        return ""

    def localProxy(self, param):
        """本地代理（m3u8广告清洗）"""
        try:
            if not param or not isinstance(param, dict):
                return [404, "text/plain", ""]
            url = param.get("url", "")
            if not url or ".m3u8" not in url:
                return [404, "text/plain", ""]

            html = self._http_get(url)
            if not html:
                return [404, "text/plain", ""]

            cleaned_lines = []
            ad_keywords = ["ad", "gg", "adv", "preroll", "片头", "广告", "pop", "banner"]
            for line in html.split("\n"):
                line_stripped = line.strip()
                if line_stripped.startswith("#"):
                    cleaned_lines.append(line)
                    continue
                is_ad = any(kw in line_stripped.lower() for kw in ad_keywords)
                if not is_ad:
                    cleaned_lines.append(line)

            return [200, "application/vnd.apple.mpegurl", "\n".join(cleaned_lines)]
        except Exception as e:
            print(f"[ayk] localProxy error: {e}")
            return [500, "text/plain", str(e)]

    def destroy(self):
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass
            self.session = None

    def isVideoFormat(self, url):
        if not url:
            return False
        return any(ext in url.lower() for ext in [".m3u8", ".mp4", ".mkv", ".avi", ".flv", ".ts"])

    def getName(self):
        return "ayk"

    def getApp(self):
        return "ayk"

    def isManualVideo(self):
        return False


if __name__ == "__main__":
    sp = Spider()
    sp.init()
    print("=== homeContent ===")
    home = sp.homeContent()
    print(f"分类数: {len(home.get('class', []))}")

    print("\n=== categoryContent (tid=20, pg=1) ===")
    cat = sp.categoryContent("20", "1")
    print(f"page={cat['page']}, pagecount={cat['pagecount']}, 列表={len(cat['list'])}")
    if cat["list"]:
        print(f"首个: {cat['list'][0]['vod_name'][:40]}")
        print(f"封面: {cat['list'][0]['vod_pic'][:60]}")

    print("\n=== detailContent ===")
    if cat["list"]:
        first_id = cat["list"][0]["vod_id"]
        detail = sp.detailContent([first_id])
        print(f"详情数: {len(detail['list'])}")
        if detail["list"]:
            d = detail["list"][0]
            print(f"标题: {d['vod_name'][:40]}")
            print(f"播放: {d['vod_play_url'][:80]}")

    print("\n=== searchContent ===")
    search = sp.searchContent("国产")
    print(f"列表={len(search['list'])}")

    sp.destroy()
    print("\n=== 测试完成 ===")
