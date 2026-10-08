# -*- coding: utf-8 -*-
# ************************************************************
# 【色吧资源】TVBox / 影视仓 / OK影视 / HKL 通用 Python 爬虫源
# 站点：https://www.shangbanke.shop
# 更新时间：2026-08-16
# ************************************************************

import sys
import json
import re
import urllib.parse
import urllib.request

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        pass


class Spider(BaseSpider):
    """
    TVBox 标准 Python 源
    兼容：TVBox(含py版)、影视仓、OK影视、HKL、CatVod
    """

    # ==================== 站点配置 ====================
    siteUrl = "https://www.shangbanke.shop"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": siteUrl
    }

    # ==================== 生命周期方法 ====================
    def __init__(self):
        self.extend = ""

    def getName(self):
        return "色吧资源"

    def init(self, extend=""):
        self.extend = extend
        return self

    def setExtendInfo(self, extend):
        self.extend = extend
        return self

    def getDependence(self):
        return []

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        if not url:
            return False
        return bool(re.search(r'[.](m3u8|mp4|flv|avi|mkv|rm|wmv|mpg|mpeg|ts|3gp|webm)', url, re.I))

    def manualVideoCheck(self):
        return False

    # ==================== 1. 首页导航 ====================
    def homeContent(self, filter):
        """返回实际导航栏提取的9个分类"""
        result = {
            "class": [
                {"type_id": "1", "type_name": "国产传媒"},
                {"type_id": "3", "type_name": "欧美无码"},
                {"type_id": "4", "type_name": "中文字幕"},
                {"type_id": "7", "type_name": "国产主播"},
                {"type_id": "8", "type_name": "网红流出"},
                {"type_id": "9", "type_name": "明星女优"},
                {"type_id": "10", "type_name": "强奸乱伦"},
                {"type_id": "11", "type_name": "激情动漫"},
                {"type_id": "12", "type_name": "萝莉少女"}
            ],
            "filters": {}
        }
        return result

    # ==================== 2. 首页推荐 ====================
    def homeVideoContent(self):
        url = self.siteUrl + "/"
        html = self._fetch(url)
        return self._parseList(html)

    # ==================== 3. 分类页 ====================
    def categoryContent(self, tid, pg, filter, extend):
        page = self._safeInt(pg, 1)
        if page == 1:
            url = "{}/index.php/vod/type/id/{}.html".format(self.siteUrl, tid)
        else:
            url = "{}/index.php/vod/type/id/{}/page/{}.html".format(self.siteUrl, tid, page)

        html = self._fetch(url)
        result = self._parseList(html)
        result["page"] = page
        result["pagecount"] = 9999
        result["limit"] = 24
        result["total"] = 99999
        return result

    # ==================== 4. 详情页 ====================
    def detailContent(self, ids):
        if isinstance(ids, list) and len(ids) > 0:
            vid = str(ids[0])
        else:
            vid = str(ids)

        if not vid:
            return {"list": []}

        url = "{}/index.php/vod/detail/id/{}.html".format(self.siteUrl, vid)
        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 标题：从 <title> 提取（苹果CMS格式：视频名详情介绍-视频名在线观看...）
        title = ""
        m = re.search(r'<title>(.*?)</title>', html, re.I)
        if m:
            full_title = m.group(1).strip()
            if "详情介绍" in full_title:
                title = full_title.split("详情介绍")[0].strip()
            elif "在线观看" in full_title:
                title = full_title.split("在线观看")[0].strip()
            elif "迅雷下载" in full_title:
                title = full_title.split("迅雷下载")[0].strip()
            else:
                title = full_title.split("-")[0].strip() if "-" in full_title else full_title

        if not title:
            title = "未知标题"

        # 海报
        pic = ""
        m = re.search(r'<div[^>]*class="[^"]*movie[^"]*"[^>]*>.*?<img[^>]+src="([^"]+)"', html, re.S)
        if m:
            pic = m.group(1)
        if not pic:
            m = re.search(r'data-original="([^"]+)"', html)
            if m:
                pic = m.group(1)

        # 简介
        desc = ""
        m = re.search(r'<p[^>]*class="[^"]*intro[^"]*"[^>]*>(.*?)</p>', html, re.S)
        if m:
            desc = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        # 播放列表解析（忽略大小写，兼容 <A> 和 <a>）
        vod_play_from = []
        vod_play_url = []

        play_pattern = r'<a[^>]+href="(/index[.]php/vod/play/id/(\d+)/sid/(\d+)/nid/(\d+)[.]html)"[^>]*>(.*?)</a>'
        matches = re.findall(play_pattern, html, re.S | re.I)

        links = []
        seen_ids = set()
        for href, p_vid, p_sid, p_nid, name in matches:
            play_id = "{}-{}-{}".format(p_vid, p_sid, p_nid)
            if play_id in seen_ids:
                continue
            seen_ids.add(play_id)
            name = re.sub(r'<[^>]+>', '', name).strip()
            # 单集视频统一命名为"正片"
            if not name or name in ["电脑版播放", "手机版播放"]:
                name = "正片"
            links.append("{}${}".format(name, play_id))

        if links:
            vod_play_from.append("在线播放")
            vod_play_url.append("#".join(links))

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": self._absUrl(pic),
            "vod_content": desc,
            "vod_play_from": "$$$".join(vod_play_from) if vod_play_from else "",
            "vod_play_url": "$$$".join(vod_play_url) if vod_play_url else ""
        }

        return {"list": [vod]}

    # ==================== 5. 播放页 ====================
    def playerContent(self, flag, id, vipFlags):
        try:
            parts = str(id).split("-")
            if len(parts) == 3:
                vid, sid, nid = parts[0], parts[1], parts[2]
            else:
                vid = str(id)
                sid = "1"
                nid = "1"
        except Exception:
            vid, sid, nid = str(id), "1", "1"

        url = "{}/index.php/vod/play/id/{}/sid/{}/nid/{}.html".format(self.siteUrl, vid, sid, nid)
        html = self._fetch(url)
        if not html:
            return {"parse": 0, "url": "", "header": ""}

        video_url = ""

        # 策略1：提取 player_aaaa JSON（关键修复：兼容无分号、跨行匹配）
        m = re.search(r'var\s+player_aaaa\s*=\s*({.+?})(?:;|\s*</script>)', html, re.S)
        if m:
            try:
                player_data = json.loads(m.group(1))
                video_url = player_data.get("url", "")
            except Exception:
                pass

        # 策略2：直接匹配 m3u8（排除 HTML 标签字符 <>）
        if not video_url:
            m = re.search(r'(https?://[^\s\"\'<>]+[.]m3u8[^\s\"\'<>]*)', html)
            if m:
                video_url = m.group(1)

        # 策略3：直接匹配 mp4（排除 HTML 标签字符 <>）
        if not video_url:
            m = re.search(r'(https?://[^\s\"\'<>]+[.]mp4[^\s\"\'<>]*)', html)
            if m:
                video_url = m.group(1)

        # 处理 JSON 转义
        video_url = video_url.replace("\\/", "/")

        # header 使用字符串格式（TVBox 兼容性最好）
        header_str = "User-Agent={}&Referer={}".format(
            urllib.parse.quote(self.headers["User-Agent"]),
            urllib.parse.quote(self.siteUrl)
        )

        result = {
            "parse": 0,
            "url": video_url,
            "header": header_str
        }
        return result

    # ==================== 6. 搜索 ====================
    def searchContent(self, key, quick, pg=1):
        page = self._safeInt(pg, 1)
        keyword = urllib.parse.quote(str(key))

        if page == 1:
            url = "{}/index.php/vod/search.html?wd={}".format(self.siteUrl, keyword)
        else:
            url = "{}/index.php/vod/search/page/{}/wd/{}.html".format(self.siteUrl, page, keyword)

        html = self._fetch(url)
        return self._parseList(html)

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    # ==================== 7. 本地代理 ====================
    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]

    # ==================== 工具方法 ====================
    def _fetch(self, url):
        try:
            import requests
            resp = requests.get(url, headers=self.headers, timeout=15, allow_redirects=True)
            resp.encoding = "utf-8"
            return resp.text
        except Exception:
            pass

        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception:
            pass

        return ""

    def _parseList(self, html):
        if not html:
            return {"list": []}

        items = []
        seen = set()

        # 策略1：匹配 video-pic 结构
        pattern = r'<a[^>]+class="[^"]*video-pic[^"]*"[^>]+href="(/index[.]php/vod/detail/id/(\d+)[.]html)"[^>]*title="([^"]*)"[^>]*data-original="([^"]*)"'
        matches = re.findall(pattern, html)
        for href, vid, title, pic in matches:
            if vid in seen:
                continue
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": self._absUrl(pic),
                "vod_remarks": ""
            })

        # 策略2：兜底扫描所有 detail/id 链接
        if not items:
            pattern = r'<a[^>]+href="(/index[.]php/vod/detail/id/(\d+)[.]html)"[^>]*>(.*?)</a>'
            matches = re.findall(pattern, html)
            for href, vid, content in matches:
                if vid in seen:
                    continue
                seen.add(vid)
                title = re.sub(r'<[^>]+>', '', content).strip()
                if not title or len(title) < 2:
                    continue
                pic = ""
                idx = html.find(href)
                if idx > 0:
                    segment = html[max(0, idx - 500):idx + 500]
                    m = re.search(r'data-original="([^"]+)"', segment)
                    if not m:
                        m = re.search(r'src="([^"]+)"', segment)
                    if m:
                        pic = m.group(1)
                items.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": self._absUrl(pic),
                    "vod_remarks": ""
                })

        return {"list": items}

    def _absUrl(self, path):
        if not path:
            return ""
        if path.startswith("http"):
            return path
        return self.siteUrl + (path if path.startswith("/") else "/" + path)

    def _extract(self, html, pattern):
        m = re.search(pattern, html, re.S)
        if m:
            return re.sub(r'<[^>]+>', '', m.group(1)).strip()
        return ""

    def _safeInt(self, val, default=1):
        try:
            v = int(val)
            return v if v > 0 else default
        except Exception:
            return default


# ==================== 帝兵自检入口 ====================
if __name__ == "__main__":
    spider = Spider()
    spider.init()
    print("[遮天] 色吧资源 Spider 帝兵自检启动")
    print("[遮天] 站点:", spider.siteUrl)

    home = spider.homeContent(True)
    classes = home.get("class", [])
    print("[遮天] 首页分类数:", len(classes))
    for c in classes:
        print("  [遮天] 分类 ID={} 名称={}".format(c["type_id"], c["type_name"]))

    # 轮询测试每个分类
    for c in classes[:3]:
        cate = spider.categoryContent(c["type_id"], "1", "", "")
        print("[遮天] 分类[{}]视频数:".format(c["type_name"]), len(cate.get("list", [])))

    search = spider.searchContent("FC2", False, 1)
    print("[遮天] 搜索结果数:", len(search.get("list", [])))

    if home.get("class"):
        first_cate = spider.categoryContent(home["class"][0]["type_id"], "1", "", "")
        if first_cate.get("list"):
            first_id = first_cate["list"][0]["vod_id"]
            detail = spider.detailContent([first_id])
            d = detail.get("list", [{}])[0]
            print("[遮天] 详情标题:", d.get("vod_name", ""))
            print("[遮天] 播放线路:", d.get("vod_play_from", ""))

            play_url = d.get("vod_play_url", "")
            if "$" in play_url:
                pid = play_url.split("$")[1].split("#")[0]
                player = spider.playerContent("在线播放", pid, [])
                print("[遮天] 播放解析:", player.get("url", "")[:150])

    print("[遮天] 帝兵自检完成，源可用")
