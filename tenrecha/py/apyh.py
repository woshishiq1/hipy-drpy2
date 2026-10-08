# -*- coding: utf-8 -*-
"""
四壳通用Python Spider - apyh (A片银行)
站点类型: 苹果CMS v10 (kuhei3_pc模板)
核心特征: 分类页直连播放页, 播放页player_data JSON含m3u8地址
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
    """四壳通用Spider - apyh"""

    # 站点配置
    baseUrl = "https://azj.apyh3.mom"
    sitePath = "/cn/home/web/index.php"
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    # 分类列表（铁律7：父子层级完整，本站为一级分类）
    classList = [
        {"type_id": "20", "type_name": "国产自拍"},
        {"type_id": "21", "type_name": "制服丝袜"},
        {"type_id": "22", "type_name": "强奸乱伦"},
        {"type_id": "23", "type_name": "教师学生"},
        {"type_id": "24", "type_name": "素人系列"},
        {"type_id": "25", "type_name": "人妻熟女"},
        {"type_id": "26", "type_name": "日韩无码"},
        {"type_id": "27", "type_name": "日韩有码"},
        {"type_id": "28", "type_name": "中文字幕"},
        {"type_id": "29", "type_name": "欧美风情"},
        {"type_id": "30", "type_name": "经典伦理"},
        {"type_id": "31", "type_name": "卡通动漫"},
    ]

    # 过滤条件（苹果CMS标准筛选，本站页面无显式筛选，提供基础空结构）
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
            print(f"[apyh] GET error: {e}")
            return ""

    def _http_post(self, url, data, timeout=15):
        """HTTP POST请求"""
        try:
            sess = self._get_session()
            if sess:
                r = sess.post(url, data=data, timeout=timeout, allow_redirects=True)
                return r.text
            else:
                import urllib.request
                data_enc = urllib.parse.urlencode(data).encode("utf-8")
                req = urllib.request.Request(url, data=data_enc, headers=self.header)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"[apyh] POST error: {e}")
            return ""

    def _parse_list_page(self, html):
        """
        解析列表页（分类页/搜索页），提取视频卡片
        返回: list of {vod_id, vod_name, vod_pic, vod_remarks}
        """
        results = []
        # 匹配视频卡片: <a ... href=".../vod/play/id/{id}/sid/1/nid/1.html" title="标题" data-original="封面">
        pattern = re.compile(
            r'href="[^"]*vod/play/id/(\d+)/sid/\d+/nid/\d+\.html"[^>]*title="([^"]*)"[^>]*data-original="([^"]*)"',
            re.DOTALL
        )
        for m in pattern.finditer(html):
            vod_id = m.group(1)
            vod_name = m.group(2).strip()
            vod_pic = m.group(3).strip()
            # 铁律13：未成年相关条目跳过
            if _is_juvenile(vod_name):
                continue
            results.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": "",
            })
        return results

    def _parse_total_pages(self, html, tid=None, wd=None):
        """解析总页数"""
        # 分页链接格式: .../page/数字.html
        pages = re.findall(r'/page/(\d+)\.html', html)
        if pages:
            return max(int(p) for p in pages)
        return 1

    def _parse_play_page(self, html):
        """
        解析播放页，提取详情信息和播放地址
        返回: dict with vod_detail info + play_url
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
            "play_from": "ckplayer",
        }

        # 1. 提取player_data JSON
        m = re.search(r'var\s+player_data\s*=\s*({[\s\S]+?})\s*</script>', html)
        if m:
            try:
                player_data = json.loads(m.group(1))
                result["play_url"] = player_data.get("url", "")
                result["play_from"] = player_data.get("from", "ckplayer")
            except Exception:
                # 尝试正则提取url
                url_m = re.search(r'"url"\s*:\s*"([^"]+)"', m.group(1))
                if url_m:
                    result["play_url"] = url_m.group(1).replace("\\/", "/")

        # 2. 提取标题
        title_m = re.search(r'<h1 class="title">([^<]+)</h1>', html)
        if title_m:
            result["vod_name"] = title_m.group(1).strip()

        # 3. 提取评分/年份/分类/播放次数
        data_m = re.search(r'<div class="data">([\s\S]*?)</div>', html)
        if data_m:
            data_text = data_m.group(1)
            # 评分
            score_m = re.search(r'([\d.]+)\s*分', data_text)
            if score_m:
                result["vod_score"] = score_m.group(1)
            # 年份
            year_m = re.search(r'/\s*(\d{4})\s*/', data_text)
            if year_m:
                result["vod_year"] = year_m.group(1)

        # 4. 提取详情区域（主演/导演/类型/地区/简介）
        detail_m = re.search(r'<div class="data-more"[^>]*>([\s\S]*?)</div>\s*</div>', html)
        if detail_m:
            detail_text = detail_m.group(1)
            # 主演
            actor_m = re.search(r'主演：</span>([^<]+)', detail_text)
            if actor_m:
                result["vod_actor"] = actor_m.group(1).strip()
            # 导演
            director_m = re.search(r'导演：</span>([^<]+)', detail_text)
            if director_m:
                result["vod_director"] = director_m.group(1).strip()
            # 类型
            type_m = re.search(r'类型：</span>([^<]+)', detail_text)
            if type_m:
                result["vod_remarks"] = type_m.group(1).strip()
            # 地区
            area_m = re.search(r'地区：</span>([^<]*)', detail_text)
            if area_m:
                result["vod_area"] = area_m.group(1).strip()
            # 简介
            content_m = re.search(r'简介：</p>\s*<p>([\s\S]*?)</p>', detail_text)
            if content_m:
                result["vod_content"] = re.sub(r'<[^>]+>', '', content_m.group(1)).strip()

        # 5. 提取封面（从页面中找）
        pic_m = re.search(r'data-original="([^"]+)"', html)
        if pic_m:
            result["vod_pic"] = pic_m.group(1).strip()

        return result

    # ==================== 13标准接口 ====================

    def init(self, extend=""):
        """初始化，支持ext参数覆盖"""
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
        result = {
            "class": self.classList,
            "filters": self.filters,
        }
        return result

    def categoryContent(self, tid, pg, filter=None, extend=None):
        """
        分类内容
        tid: 分类ID
        pg: 页码
        返回五键: page/pagecount/limit/total/list
        """
        pg = int(pg) if pg else 1
        # 第一页用type路径，后续用show路径
        if pg == 1:
            url = f"{self.baseUrl}{self.sitePath}/vod/type/id/{tid}.html"
        else:
            url = f"{self.baseUrl}{self.sitePath}/vod/show/id/{tid}/page/{pg}.html"

        html = self._http_get(url)
        if not html:
            return {"page": pg, "pagecount": 1, "limit": 12, "total": 0, "list": []}

        vod_list = self._parse_list_page(html)
        pagecount = self._parse_total_pages(html, tid=tid)
        total = pagecount * 12

        return {
            "page": pg,
            "pagecount": pagecount,
            "limit": 12,
            "total": total,
            "list": vod_list,
        }

    def detailContent(self, ids):
        """
        详情内容
        ids: list/tuple of vod_id（铁律：必须遍历）
        返回: {list: [vod_detail, ...]}
        """
        if isinstance(ids, str):
            ids = [ids]

        vod_list = []
        for vod_id in ids:
            if not vod_id:
                continue
            url = f"{self.baseUrl}{self.sitePath}/vod/play/id/{vod_id}/sid/1/nid/1.html"
            html = self._http_get(url)
            if not html:
                continue

            info = self._parse_play_page(html)

            # 铁律13：未成年相关条目跳过
            if _is_juvenile(info.get("vod_name", "")) or _is_juvenile(info.get("vod_content", "")):
                continue

            # 播放地址格式化：vod_play_from用$$$分隔线路，vod_play_url用#分隔集
            # 本站单线路，播放地址即m3u8直链
            play_url = info.get("play_url", "")
            play_from = info.get("play_from", "ckplayer")

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
                "vod_play_from": play_from,
                "vod_play_url": play_url,
            }
            vod_list.append(vod_item)

        return {"list": vod_list}

    def searchContent(self, key, quick=None, pg=None):
        """
        搜索内容
        key: 搜索关键词
        pg: 页码
        返回五键: page/pagecount/limit/total/list
        """
        pg = int(pg) if pg else 1
        key_enc = urllib.parse.quote(key)

        if pg == 1:
            url = f"{self.baseUrl}{self.sitePath}/vod/search/wd/{key_enc}.html"
        else:
            url = f"{self.baseUrl}{self.sitePath}/vod/search/page/{pg}/wd/{key_enc}.html"

        html = self._http_get(url)
        if not html:
            return {"page": pg, "pagecount": 1, "limit": 12, "total": 0, "list": []}

        vod_list = self._parse_list_page(html)
        pagecount = self._parse_total_pages(html, wd=key)
        total = pagecount * 12

        return {
            "page": pg,
            "pagecount": pagecount,
            "limit": 12,
            "total": total,
            "list": vod_list,
        }

    def playerContent(self, flag, id, vipFlags=None):
        """
        播放内容
        flag: 播放源标识
        id: 播放地址（本站detail已返回m3u8直链，此处直接透传）
        返回: parse=0/jx=0/url/header
        """
        # 防盗链Header
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
        """依赖声明"""
        return ""

    def localProxy(self, param):
        """
        本地代理（m3u8广告清洗基础实现）
        铁律8：非空壳，接收m3u8代理请求→下载→清洗→返回
        """
        try:
            if not param or not isinstance(param, dict):
                return [404, "text/plain", ""]
            url = param.get("url", "")
            if not url or ".m3u8" not in url:
                return [404, "text/plain", ""]

            # 下载m3u8
            headers = dict(self.header)
            headers["Referer"] = self.baseUrl + "/"
            html = self._http_get(url)
            if not html:
                return [404, "text/plain", ""]

            # 基础广告清洗：剔除含广告关键词的ts行
            cleaned_lines = []
            ad_keywords = ["ad", "gg", "adv", "preroll", "片头", "广告", "pop", "banner"]
            for line in html.split("\n"):
                line_stripped = line.strip()
                if line_stripped.startswith("#"):
                    cleaned_lines.append(line)
                    continue
                # 检查ts路径是否含广告关键词
                is_ad = False
                for kw in ad_keywords:
                    if kw in line_stripped.lower():
                        is_ad = True
                        break
                if not is_ad:
                    cleaned_lines.append(line)

            cleaned = "\n".join(cleaned_lines)
            return [200, "application/vnd.apple.mpegurl", cleaned]
        except Exception as e:
            print(f"[apyh] localProxy error: {e}")
            return [500, "text/plain", str(e)]

    def destroy(self):
        """销毁"""
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass
            self.session = None

    def isVideoFormat(self, url):
        """判断是否为视频格式"""
        if not url:
            return False
        return any(ext in url.lower() for ext in [".m3u8", ".mp4", ".mkv", ".avi", ".flv", ".ts"])

    def getName(self):
        """获取站点名称"""
        return "apyh"

    def getApp(self):
        """获取应用标识"""
        return "apyh"

    def isManualVideo(self):
        """是否手动视频"""
        return False


# ==================== 本地测试入口 ====================
if __name__ == "__main__":
    sp = Spider()
    sp.init()
    print("=== homeContent ===")
    home = sp.homeContent()
    print(f"分类数: {len(home.get('class', []))}")
    print(f"filters类型: {type(home.get('filters'))}")

    print("\n=== categoryContent (tid=20, pg=1) ===")
    cat = sp.categoryContent("20", "1")
    print(f"page={cat['page']}, pagecount={cat['pagecount']}, limit={cat['limit']}, total={cat['total']}")
    print(f"列表数: {len(cat['list'])}")
    if cat["list"]:
        print(f"首个: {cat['list'][0]['vod_name'][:30]}...")

    print("\n=== detailContent ===")
    if cat["list"]:
        first_id = cat["list"][0]["vod_id"]
        detail = sp.detailContent([first_id])
        print(f"详情数: {len(detail['list'])}")
        if detail["list"]:
            d = detail["list"][0]
            print(f"标题: {d['vod_name'][:40]}")
            print(f"播放源: {d['vod_play_from']}")
            print(f"播放地址: {d['vod_play_url'][:80]}...")

    print("\n=== searchContent ===")
    search = sp.searchContent("国产")
    print(f"page={search['page']}, pagecount={search['pagecount']}, 列表数: {len(search['list'])}")

    print("\n=== playerContent ===")
    if detail["list"]:
        pc = sp.playerContent("ckplayer", detail["list"][0]["vod_play_url"])
        print(f"parse={pc['parse']}, jx={pc['jx']}")
        print(f"header类型: {type(pc['header'])}")
        print(f"url: {pc['url'][:60]}...")

    sp.destroy()
    print("\n=== 测试完成 ===")
