# coding: utf-8
"""
站点名称: javxtu
主域名: https://zh.javxtu.sbs
备用域名: 无
发布页: 无
内容类型: 图片图集（成人写真）
特殊说明: WordPress站点，图片通过p.822800.xyz代理，使用pics://协议
最后验证时间: 2026-09-05
来源: 用户提供
"""
import re
import json
from urllib.parse import urljoin, quote
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://zh.javxtu.sbs"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        # 分类静态硬编码（法则16/17），从首页标签云提取
        self.classes = [
            {"type_id": "zuixin", "type_name": "最新"},
            {"type_id": "性感內衣", "type_name": "性感內衣"},
            {"type_id": "短裙子", "type_name": "短裙子"},
            {"type_id": "美腿", "type_name": "美腿"},
            {"type_id": "舔蛋", "type_name": "舔蛋"},
            {"type_id": "性感辣媽", "type_name": "性感辣媽"},
            {"type_id": "乳交", "type_name": "乳交"},
            {"type_id": "自慰", "type_name": "自慰"},
            {"type_id": "美女", "type_name": "美女"},
            {"type_id": "自娛", "type_name": "自娛"},
            {"type_id": "日本美女", "type_name": "日本美女"},
            {"type_id": "口交", "type_name": "口交"},
            {"type_id": "嫩逼", "type_name": "嫩逼"},
            {"type_id": "多毛", "type_name": "多毛"},
            {"type_id": "亞裔", "type_name": "亞裔"},
            {"type_id": "小奶子", "type_name": "小奶子"},
            {"type_id": "牛仔女郎", "type_name": "牛仔女郎"},
            {"type_id": "乳頭", "type_name": "乳頭"},
            {"type_id": "菊花", "type_name": "菊花"},
            {"type_id": "小內褲", "type_name": "小內褲"},
            {"type_id": "爆操", "type_name": "爆操"},
        ]
        self.filters = {}

    def getName(self):
        return "javxtu"

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        return None

    def init(self, extend=""):
        self.setExtendInfo(extend)
        return None

    def homeContent(self, filter):
        # 零网络依赖，直接返回硬编码分类
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def _fetch_html(self, url):
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if resp and hasattr(resp, 'text'):
                return resp.text
            return ""
        except Exception:
            return ""

    def homeVideoContent(self):
        url = self.host + "/"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}
        items = self._parse_list(html)
        return {"list": items}

    def _parse_list(self, html):
        items = []
        pattern = r'<div[^>]*class="[^"]*blog-snippet[^"]*"[^>]*>[\s\S]*?<a[^>]*href="([^"]+)"[^>]*class="[^"]*img-holder[^"]*"[^>]*>[\s\S]*?<img[^>]*src="([^"]+)"[^>]*>[\s\S]*?</a>[\s\S]*?<div[^>]*class="[^"]*blog-content[^"]*"[^>]*>[\s\S]*?<h[23][^>]*class="[^"]*title[^"]*"[^>]*><a[^>]*href="[^"]*"[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html, re.S)
        if not matches:
            pattern2 = r'<a[^>]*href="([^"]+)"[^>]*class="[^"]*img-holder[^"]*"[^>]*>[\s\S]*?<img[^>]*src="([^"]+)"[^>]*>[\s\S]*?</a>[\s\S]*?<h[23][^>]*class="[^"]*title[^"]*"[^>]*><a[^>]*href="[^"]*"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern2, html, re.S)
        for m in matches:
            url_detail, pic, name = m
            pic = urljoin(self.host, pic)
            vid = url_detail.split("/")[-1].replace(".html", "") if "/" in url_detail else url_detail
            items.append({
                "vod_id": f"{vid}||{name}||{pic}",
                "vod_name": name.strip(),
                "vod_pic": pic + "@Referer=" + self.host + "/",
                "vod_remarks": "",
            })
        seen = set()
        unique = []
        for item in items:
            if item["vod_id"] not in seen:
                seen.add(item["vod_id"])
                unique.append(item)
        return unique[:30]

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg and str(pg).isdigit() else 1
        except (ValueError, TypeError):
            page = 1

        if tid == "zuixin" or not tid:
            if page <= 1:
                url = self.host + "/"
            else:
                url = f"{self.host}/page/{page}/"
        else:
            # 标签分类：/?tag={tid}
            if page <= 1:
                url = f"{self.host}/?tag={tid}"
            else:
                url = f"{self.host}/?tag={tid}&paged={page}"

        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}

        items = self._parse_list(html)

        pagecount = 1
        pager_match = re.search(r'<a[^>]*class="page-numbers"[^>]*>(\d+)</a>', html)
        if pager_match:
            pagecount = int(pager_match.group(1))
        pager_matches = re.findall(r'<a[^>]*href="[^"]*page[/=](\d+)[^"]*"[^>]*>[\s]*(\d+)[\s]*</a>', html)
        if pager_matches:
            max_page = max([int(p) for _, p in pager_matches if p.isdigit()])
            if max_page > pagecount:
                pagecount = max_page
        if re.search(r'class="next page-numbers"', html):
            next_match = re.search(r'<a[^>]*class="next page-numbers"[^>]*href="[^"]*page[/=](\d+)"', html)
            if next_match:
                pagecount = max(pagecount, int(next_match.group(1)))

        return {
            "list": items,
            "page": page,
            "pagecount": pagecount,
            "limit": 20,
            "total": len(items) if page == pagecount else page * 20
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = ids[0]
        parts = vid.split("||")
        if len(parts) >= 3:
            post_id, name, pic = parts[0], parts[1], parts[2]
        else:
            post_id = vid
            name = ""
            pic = ""

        if post_id.isdigit():
            url = f"{self.host}/{post_id}.html"
        else:
            if "/" in post_id:
                post_id = post_id.split("/")[-1].replace(".html", "")
                if post_id.isdigit():
                    url = f"{self.host}/{post_id}.html"
                else:
                    url = post_id if post_id.startswith("http") else f"{self.host}/{post_id}"
            else:
                url = f"{self.host}/{post_id}"

        html = self._fetch_html(url)
        if not html:
            return {"list": []}

        if not name:
            title_match = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h1>', html, re.S)
            if title_match:
                name = title_match.group(1).strip()
            else:
                title_match = re.search(r'<title>([^<]+)</title>', html, re.S)
                if title_match:
                    name = title_match.group(1).replace(" - javxtu", "").strip()

        imgs = self._extract_images(html)
        if not imgs:
            return {"list": []}

        pic_urls = []
        for img in imgs:
            pic_urls.append(img + "@Referer=" + self.host + "/")
        pics_protocol = "pics://" + "&&".join(pic_urls)

        vod = {
            "vod_id": post_id,
            "vod_name": name or "图集",
            "vod_pic": pic if pic else (imgs[0] + "@Referer=" + self.host + "/"),
            "vod_remarks": f"{len(imgs)}P",
            "vod_content": f"共 {len(imgs)} 张图片",
            "vod_play_from": "图片浏览",
            "vod_play_url": f"浏览图片${pics_protocol}",
        }
        return {"list": [vod]}

    def _extract_images(self, html):
        imgs = []
        scope_match = re.search(r'<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>([\s\S]*?)(?:<div[^>]*class="[^"]*category|</main>|<div[^>]*id="comments")', html, re.S)
        if not scope_match:
            scope_match = re.search(r'<div[^>]*class="[^"]*content[^"]*"[^>]*>([\s\S]*?)(?:<div[^>]*class="[^"]*category|</main>|<div[^>]*id="comments")', html, re.S)
        if not scope_match:
            scope_match = re.search(r'<div[^>]*class="[^"]*detail-holder[^"]*"[^>]*>([\s\S]*?)(?:<div[^>]*class="[^"]*category-tag|<div[^>]*class="[^"]*clearfix")', html, re.S)
        scope = scope_match.group(1) if scope_match else html

        img_pattern = r'<img[^>]+(?:src|data-src|data-original)="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"'
        matches = re.findall(img_pattern, scope, re.S)
        for m in matches:
            low = m.lower()
            bad = ['avatar', 'icon', 'logo', 'loading', 'smilies', 'qrcode', 'none.gif', 'thumb', 'favicon', 'wp-smiley', 'spacer']
            if any(k in low for k in bad):
                continue
            img_url = urljoin(self.host, m)
            if img_url not in imgs:
                imgs.append(img_url)

        if not imgs:
            img_pattern2 = r'<img[^>]+src="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"'
            matches2 = re.findall(img_pattern2, html, re.S)
            for m in matches2:
                low = m.lower()
                bad = ['avatar', 'icon', 'logo', 'loading', 'smilies', 'qrcode', 'none.gif', 'thumb', 'favicon', 'wp-smiley', 'spacer']
                if any(k in low for k in bad):
                    continue
                img_url = urljoin(self.host, m)
                if img_url not in imgs:
                    imgs.append(img_url)

        seen = set()
        unique = []
        for img in imgs:
            if img not in seen:
                seen.add(img)
                unique.append(img)
        return unique

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg) if pg and str(pg).isdigit() else 1
        except (ValueError, TypeError):
            page = 1
        url = f"{self.host}/?s={key}&paged={page}"
        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": page}
        items = self._parse_list(html)
        return {"list": items, "page": page}

    def playerContent(self, flag, id, vipFlags):
        if id and id.startswith("pics://"):
            return {"parse": 0, "url": id, "header": {}}
        if id and "$" in id:
            parts = id.split("$", 1)
            if len(parts) == 2:
                url_part = parts[1]
                if url_part.startswith("pics://"):
                    return {"parse": 0, "url": url_part, "header": {}}
                if url_part.startswith("http"):
                    return {"parse": 0, "url": f"pics://{url_part}", "header": {}}
        if id and id.startswith("http"):
            return {"parse": 0, "url": f"pics://{id}", "header": {}}
        return {"parse": 0, "url": "", "header": {}}

    def recommendContent(self, ids, pg="1"):
        return {"list": []}

    def destroy(self):
        pass

    def siteInfo(self):
        return {
            "current": self.host,
            "publish": None,
            "nav": None,
            "backups": [],
            "email": "",
            "type": "图片图集",
            "protocol": "pics://"
        }