# -*- coding: utf-8 -*-
"""
玉女百科 - 四壳通用Python Spider
站点: https://cqglgo.ynbk6.mom
类型: 自定义CMS (HTML直出)
"""

try:
    from base.spider import Spider as _BaseSpider
except ImportError:
    class _BaseSpider:
        def init(self, extend=""):
            pass

import re
import json
import urllib.request
import urllib.parse
import ssl


class Spider(_BaseSpider):

    def init(self, extend=""):
        self.siteUrl = "https://cqglgo.ynbk6.mom"
        self.rawSite = "https://cqglgo.ynbk6.mom"
        self.HOST = self.siteUrl
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        self.timeout = 15
        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE
        # 配置覆盖
        try:
            if extend:
                if isinstance(extend, str):
                    try:
                        cfg = json.loads(extend)
                    except Exception:
                        cfg = {}
                else:
                    cfg = extend if isinstance(extend, dict) else {}
                if cfg.get("proxy"):
                    self.siteUrl = cfg["proxy"]
                    self.HOST = self.siteUrl
                if cfg.get("siteUrl"):
                    self.siteUrl = cfg["siteUrl"]
                    self.HOST = self.siteUrl
                if cfg.get("direct"):
                    self.siteUrl = self.rawSite
                    self.HOST = self.siteUrl
        except Exception:
            pass

    def getDependence(self):
        return ""

    def _fetch(self, url):
        req = urllib.request.Request(url, headers={
            "User-Agent": self.ua,
            "Referer": self.rawSite + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        resp = urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl_ctx)
        data = resp.read()
        # 尝试utf-8
        try:
            return data.decode("utf-8", errors="ignore")
        except Exception:
            return data.decode("gbk", errors="ignore")

    def _is_minor(self, text):
        """检查是否含未成年相关关键词"""
        if not text:
            return False
        t = text.lower()
        keywords = ["萝莉", "幼女", "少女", "loli", "teen", "schoolgirl",
                     "童颜", "小学生", "初中生", "高中生", "jk", "女子校生",
                     "18岁以下", "未成年"]
        # "学生"不触发(铁律13边界)
        for kw in keywords:
            if kw in t:
                return True
        return False

    def _parse_list(self, html):
        """解析视频列表"""
        results = []
        # 匹配 <a class="videoBox" href="...">...</a>，支持两种URL格式
        pattern = re.compile(
            r'<a[^>]*class="videoBox"[^>]*href="(?:/cn/home/web/index\.php/vodplay/|/)(\d+)\.html"[^>]*>(.*?)</a>\s*<div[^>]*class="videoBox-actor"[^>]*>(.*?)</div>',
            re.DOTALL
        )
        for m in pattern.finditer(html):
            vid = m.group(1)
            inner = m.group(2)
            # 封面 data-src
            pic = ""
            pm = re.search(r'data-src="([^"]+)"', inner)
            if pm:
                pic = pm.group(1)
            # 标题
            title = ""
            tm = re.search(r'<h4[^>]*class="title"[^>]*>([^<]+)</h4>', inner)
            if tm:
                title = tm.group(1).strip()
            # 日期
            remark = ""
            dm = re.search(r'<div[^>]*class="videoBox-time"[^>]*>([^<]*)</div>', inner)
            if dm:
                remark = dm.group(1).strip()
            # 未成年过滤
            if self._is_minor(title):
                continue
            results.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return results

    def _parse_page_info(self, html, base_url):
        """解析分页信息"""
        page = 1
        pagecount = 1
        # 从当前页链接提取页码
        pm = re.search(r'-(\d+)\.html', base_url)
        if pm:
            page = int(pm.group(1))
        # 尾页
        lm = re.search(r'/vodtype/\d+-(\d+)\.html[^>]*>尾页', html)
        if lm:
            pagecount = int(lm.group(1))
        else:
            # 搜索页尾页
            lm2 = re.search(r'/s/[^"\']+-(\d+)\.html[^>]*>尾页', html)
            if lm2:
                pagecount = int(lm2.group(1))
        return page, pagecount

    def homeContent(self, *args):
        classes = [
            {"type_id": "21", "type_name": "女神学生"},
            {"type_id": "22", "type_name": "美女直播"},
            {"type_id": "23", "type_name": "人妻系列"},
            {"type_id": "24", "type_name": "强奸乱伦"},
            {"type_id": "25", "type_name": "自拍偷拍"},
            {"type_id": "26", "type_name": "制服诱惑"},
            {"type_id": "27", "type_name": "巨乳系列"},
            {"type_id": "28", "type_name": "自慰系列"},
            {"type_id": "29", "type_name": "国产视频"},
            {"type_id": "30", "type_name": "无码视频"},
            {"type_id": "31", "type_name": "有码视频"},
            {"type_id": "32", "type_name": "中文字幕"},
            {"type_id": "33", "type_name": "日韩精品"},
            {"type_id": "34", "type_name": "欧美精品"},
            {"type_id": "35", "type_name": "动漫精品"},
            {"type_id": "36", "type_name": "三级伦理"},
        ]
        filters = {}
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        try:
            html = self._fetch(self.HOST + "/ynbk/")
            lst = self._parse_list(html)
            return {"list": lst, "page": 1, "pagecount": 1, "limit": 20, "total": len(lst)}
        except Exception:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

    def categoryContent(self, *args):
        tid = args[0] if len(args) > 0 else ""
        pg = args[1] if len(args) > 1 else "1"
        try:
            p = int(pg)
        except Exception:
            p = 1
        if p <= 1:
            url = self.HOST + "/vodtype/" + str(tid) + ".html"
        else:
            url = self.HOST + "/vodtype/" + str(tid) + "-" + str(p) + ".html"
        try:
            html = self._fetch(url)
            lst = self._parse_list(html)
            page, pagecount = self._parse_page_info(html, url)
            total = pagecount * 20
            return {
                "list": lst,
                "page": page,
                "pagecount": pagecount,
                "limit": 20,
                "total": total,
            }
        except Exception:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        results = []
        for vid in ids:
            try:
                url = self.HOST + "/" + str(vid) + ".html"
                html = self._fetch(url)
                # 标题
                title = ""
                tm = re.search(r'<h1[^>]*class="video-title"[^>]*>.*?<span[^>]*class="title"[^>]*>([^<]+)</span>', html, re.DOTALL)
                if tm:
                    title = tm.group(1).strip()
                # 封面
                pic = ""
                pm = re.search(r'property="og:image"\s+content="([^"]+)"', html)
                if pm:
                    pic = pm.group(1)
                # 分类
                type_name = ""
                cm = re.search(r'<span[^>]*class="cates"[^>]*>.*?<a[^>]*>([^<]+)</a>', html, re.DOTALL)
                if cm:
                    type_name = cm.group(1).strip()
                # m3u8地址
                m3u8 = ""
                mm = re.search(r"const\s+rawUrl\s*=\s*'([^']+)'", html)
                if mm:
                    m3u8 = mm.group(1)
                # 简介
                desc = ""
                dm = re.search(r'property="og:description"\s+content="([^"]+)"', html)
                if dm:
                    desc = dm.group(1)
                item = {
                    "vod_id": str(vid),
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": type_name,
                    "vod_year": "",
                    "vod_area": "",
                    "vod_content": desc,
                    "vod_play_from": "玉女百科",
                    "vod_play_url": "正片$" + m3u8,
                }
                results.append(item)
            except Exception:
                continue
        return {"list": results}

    def searchContent(self, *args):
        wd = args[0] if len(args) > 0 else ""
        pg = args[1] if len(args) > 1 else "1"
        try:
            p = int(pg)
        except Exception:
            p = 1
        # /s/{关键词}.html
        enc = urllib.parse.quote(wd)
        if p <= 1:
            url = self.HOST + "/s/" + enc + ".html"
        else:
            url = self.HOST + "/s/" + enc + "-" + str(p) + ".html"
        try:
            html = self._fetch(url)
            lst = self._parse_list(html)
            page, pagecount = self._parse_page_info(html, url)
            total = pagecount * 20
            return {
                "list": lst,
                "page": page,
                "pagecount": pagecount,
                "limit": 20,
                "total": total,
            }
        except Exception:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

    def playerContent(self, *args):
        flag = args[0] if len(args) > 0 else ""
        pid = args[1] if len(args) > 1 else ""
        # pid就是m3u8地址
        url = pid
        if not url.startswith("http"):
            url = self.HOST + "/" + url + ".html"
            try:
                html = self._fetch(url)
                mm = re.search(r"const\s+rawUrl\s*=\s*'([^']+)'", html)
                if mm:
                    url = mm.group(1)
            except Exception:
                pass
        return {
            "parse": 0,
            "jx": 0,
            "url": url,
            "header": {
                "User-Agent": self.ua,
                "Referer": self.rawSite + "/",
            },
            "format": "application/x-mpegURL",
        }

    def localProxy(self, *args):
        return [404, "text/plain", ""]

    def isVideoFormat(self, *args):
        return True

    def manualVideoCheck(self, *args):
        return False

    def action(self, *args):
        return {}

    def destroy(self, *args):
        pass
