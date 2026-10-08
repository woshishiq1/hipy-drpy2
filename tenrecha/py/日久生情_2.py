# -*- coding: utf-8 -*-
# QQ:807916734@猪猪
"""
日久生情 (https://btm.rjsq2.skin/rjsq/) 蜘蛛  ——  OK影视壳 / dr_py (TVBox) 适用

站点特征（苹果CMS + ThinkPHP 路由）：
  * 站点根路径：/cn/home/web/（注意：/rjsq/ 是门户入口，实际页面链接用 /cn/home/web/ 绝对路径）
  * 分类页：/index.php/vod/type/id/{tid}.html
  * 分页页：/index.php/vod/show/id/{tid}/page/{pg}.html  ← 注意是 show 不是 type
  * 详情/播放页：/index.php/vod/play/id/{vid}/sid/1/nid/1.html
  * 搜索页：/index.php/vod/search.html?wd={keyword}
  * 卡片结构（分类页）：<li><a href="...vod/play/id/{vid}..."><img class="loading" src="占位图" data-original="真实封面" alt="片名" title="片名">
  * 卡片结构（搜索页）：<a href="...vod/play/id/{vid}..."><img src="真实封面" title="片名" align="片名">
  * m3u8 直链在详情页 player_data JSON 的 url 字段中，含 \/ 转义需解码
  * m3u8 需带 Referer 头才能访问
  * 片名取 meta keywords 第一个 - 前部分
"""

import re
import json
import requests
import urllib3
from urllib.parse import quote, urljoin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from base.spider import Spider


class Spider(Spider):

    BASE_URL = "https://btm.rjsq2.skin"
    SITE_PATH = "/cn/home/web"

    FALLBACK_CATES = [
        {"type_id": "20", "type_name": "自拍视频"},
        {"type_id": "21", "type_name": "强奸乱伦"},
        {"type_id": "22", "type_name": "无码视频"},
        {"type_id": "23", "type_name": "有码视频"},
        {"type_id": "24", "type_name": "人妻熟女"},
        {"type_id": "25", "type_name": "制服诱惑"},
        {"type_id": "26", "type_name": "口交颜射"},
        {"type_id": "27", "type_name": "SM重味"},
        {"type_id": "28", "type_name": "日韩视频"},
        {"type_id": "29", "type_name": "欧美视频"},
        {"type_id": "30", "type_name": "动漫视频"},
        {"type_id": "31", "type_name": "伦理影片"},
    ]

    def init(self, extend=""):
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.BASE_URL + "/",
        }
        self.host = self.BASE_URL
        self.site_path = self.SITE_PATH
        self.classes = []
        self._fetch_categories()

    @staticmethod
    def name():
        return "日久生情"

    def getName(self):
        return "日久生情"

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def localProxy(self, param):
        return None

    # ============================== 分类提取 ==============================

    def _fetch_categories(self):
        """从首页导航提取分类"""
        url = self.host + self.site_path + "/"
        html = self._get(url)
        if html:
            matches = re.findall(
                r'href="[^"]*/index\.php/vod/type/id/(\d+)\.html"[^>]*>([^<]+)',
                html)
            seen = set()
            for tid, tname in matches:
                tname = tname.strip()
                if tid not in seen and tname and len(tname) < 10:
                    seen.add(tid)
                    self.classes.append(
                        {"type_id": tid, "type_name": tname})
        if not self.classes:
            self.classes = list(self.FALLBACK_CATES)

    # ============================== 工具 ==============================

    def _get(self, url, timeout=15):
        try:
            r = requests.get(url, headers=self.headers, timeout=timeout, verify=False)
            r.encoding = "utf-8"
            return r.text
        except Exception:
            return ""

    def _parse_video_list(self, html):
        """
        解析视频卡片：按 vid 合并标题和封面
        分类页：<a href="...vod/play/id/{vid}..."><img data-original="封面" title="片名" alt="片名">
        搜索页：<a href="...vod/play/id/{vid}..."><img src="封面" title="片名" align="片名">
        """
        vid_map = {}
        for m in re.finditer(
            r'<a[^>]*href="[^"]*vod/play/id/(\d+)[^"]*"[^>]*>([\s\S]*?)</a>',
                html):
            vid = m.group(1)
            block = m.group(0)
            if vid not in vid_map:
                vid_map[vid] = {"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_remarks": ""}

            # 取标题：title 属性优先，降级 alt，再降级 align
            if not vid_map[vid]["vod_name"]:
                tm = re.search(r'title="([^"]*)"', block)
                if tm and tm.group(1).strip():
                    vid_map[vid]["vod_name"] = tm.group(1).strip()
            if not vid_map[vid]["vod_name"]:
                am = re.search(r'alt="([^"]*)"', block)
                if am and am.group(1).strip():
                    vid_map[vid]["vod_name"] = am.group(1).strip()
            if not vid_map[vid]["vod_name"]:
                am2 = re.search(r'align="([^"]*)"', block)
                if am2 and am2.group(1).strip():
                    vid_map[vid]["vod_name"] = am2.group(1).strip()

            # 取封面：data-original 优先（分类页），降级 data-background（移动版），降级 src（搜索页），排除占位图
            if not vid_map[vid]["vod_pic"]:
                im = re.search(r'data-original="([^"]*)"', block)
                if im:
                    vid_map[vid]["vod_pic"] = im.group(1)
            if not vid_map[vid]["vod_pic"]:
                im = re.search(r'data-background="([^"]*)"', block)
                if im:
                    vid_map[vid]["vod_pic"] = im.group(1)
            if not vid_map[vid]["vod_pic"]:
                im = re.search(r'<img[^>]*src="([^"]*)"', block)
                if im and "template" not in im.group(1) and "pic.png" not in im.group(1):
                    vid_map[vid]["vod_pic"] = im.group(1)

            # 取备注（播放次数等）
            if not vid_map[vid]["vod_remarks"]:
                rm = re.search(r'<label[^>]*>([^<]*)</label>', block)
                if rm:
                    vid_map[vid]["vod_remarks"] = rm.group(1).strip()

        return [v for v in vid_map.values() if v["vod_name"]]

    def _parse_page_count(self, html, tid):
        """分页：/vod/show/id/{tid}/page/{pg}.html"""
        pages = re.findall(
            r'/vod/show/id/%s/page/(\d+)\.html' % re.escape(str(tid)), html)
        return max(int(p) for p in pages) if pages else 1

    # ============================== TVBox 接口 ==============================

    def homeContent(self, filter):
        classes = [{"type_name": c["type_name"], "type_id": c["type_id"]}
                   for c in self.classes]
        result = {"class": classes, "list": [], "filters": {}}

        url = self.host + self.site_path + "/"
        html = self._get(url)
        if html:
            videos = self._parse_video_list(html)
            result["list"] = videos[:30]
        return result

    def homeVideoContent(self):
        return self.homeContent(False)

    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid)
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1

        # 第1页用 type/id，第2页起用 show/id
        if page <= 1:
            url = "%s%s/index.php/vod/type/id/%s.html" % (
                self.host, self.site_path, tid)
        else:
            url = "%s%s/index.php/vod/show/id/%s/page/%d.html" % (
                self.host, self.site_path, tid, page)

        html = self._get(url)
        if not html:
            return {"list": [], "page": page, "pagecount": 1,
                    "limit": 30, "total": 0}

        videos = self._parse_video_list(html)
        pagecount = self._parse_page_count(html, tid)

        return {
            "list": videos,
            "page": page,
            "pagecount": max(pagecount, 1),
            "limit": 30,
            "total": max(pagecount * 30, len(videos)),
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0]).strip()
        url = "%s%s/index.php/vod/play/id/%s/sid/1/nid/1.html" % (
            self.host, self.site_path, vid)
        html = self._get(url)
        if not html:
            return {"list": []}

        # 标题：取 meta keywords 第一个 - 前部分
        name = ""
        kw_m = re.search(
            r'<meta\s+name="keywords"\s+content="([^"]*)"', html)
        if kw_m:
            name = kw_m.group(1).split("-")[0].strip()
        if not name:
            title_m = re.search(r'<title>(.*?)</title>', html, re.S)
            if title_m:
                name = title_m.group(1).split("-")[0].strip()

        # 封面图
        pic = ""
        # 方式1：bdPic 分享配置
        bp = re.search(r'bdPic\s*:\s*[\'"]([^\'"]+)[\'"]', html)
        if bp:
            pic = bp.group(1)
        # 方式2：详情页 img（data-original 优先，降级 src，排除占位图）
        if not pic:
            for im_m in re.finditer(
                r'<img[^>]*(?:data-original|src)="([^"]*)"[^>]*',
                html):
                candidate = im_m.group(1)
                if "template" not in candidate and "pic.png" not in candidate:
                    pic = candidate
                    break
        if pic and not pic.startswith("http"):
            pic = urljoin(self.host, pic)

        # 简介
        desc = ""
        dm = re.search(
            r'<div[^>]*class="[^"]*(?:vod-content|content-desc|detail)[^"]*"[^>]*>([\s\S]*?)</div>',
            html)
        if dm:
            desc = re.sub(r'<[^>]+>', '', dm.group(1)).strip()

        # m3u8 提取
        play_url = ""
        # 方式1：player_data JSON（首选）
        pd = re.search(r'player_data\s*=\s*(\{.*?\})\s*;?\s*</script>', html, re.S)
        if pd:
            try:
                pdata = json.loads(pd.group(1))
                raw = pdata.get("url", "")
                play_url = raw.replace("\\/", "/")
            except Exception:
                pass
        # 方式2："url":"https:\/\/..."
        if not play_url:
            m1 = re.search(r'"url"\s*:\s*"([^"]*)"', html)
            if m1:
                play_url = m1.group(1).replace("\\/", "/")
        # 方式3：裸 m3u8
        if not play_url:
            m3 = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
            if m3:
                play_url = m3.group(1)

        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": "日久生情",
            "vod_play_url": "播放$%s" % play_url if play_url else "",
            "type_name": "",
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        url = "%s%s/index.php/vod/search.html?wd=%s" % (
            self.host, self.site_path, quote(key))
        if page > 1:
            url += "&page=%d" % page

        html = self._get(url)
        if not html:
            return {"list": [], "page": page, "pagecount": 1}

        videos = self._parse_video_list(html)
        # 搜索分页数
        pagecount = 1
        pc = re.findall(r'/page/(\d+)\.html', html)
        if pc:
            pagecount = max(int(p) for p in pc)

        return {
            "list": videos,
            "page": page,
            "pagecount": max(pagecount, 1),
            "limit": 30,
            "total": max(pagecount * 30, len(videos)),
        }

    def playerContent(self, flag, id, vipFlags):
        url = str(id).strip()
        return {
            "parse": 0,
            "url": url,
            "header": {
                "User-Agent": self.ua,
                "Referer": self.host + "/",
            },
        }
