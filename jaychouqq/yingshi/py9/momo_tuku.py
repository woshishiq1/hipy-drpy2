# coding: utf-8
"""
站点: MOMO图库
主域名: https://www.momo777.cc/888/
备用域名: 无
发布页: 无
内容类型: 图片/写真图集
特殊说明: WordPress站，使用pics://协议，图片站
最后验证时间: 2026-09-04
来源: 用户提供 https://www.momo777.cc/888/
"""
import json
import re
from urllib.parse import urljoin, quote, unquote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://www.momo777.cc/888"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        # 分类硬编码 - 只保留全部、白丝、黑丝
        self.classes = [
            {"type_id": "all", "type_name": "全部"},
            {"type_id": "2", "type_name": "白丝"},
            {"type_id": "3", "type_name": "黑丝"},
        ]
        self.filters = {c["type_id"]: [] for c in self.classes}

    def getName(self):
        return "MOMO图库"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐 - 获取最新图集"""
        try:
            html = self.fetch(self.host + "/", headers=self.headers, timeout=15).text
            if not html:
                return {"list": []}
            items = []
            card_pattern = r'<article[^>]*class="[^"]*satin-card[^"]*"[^>]*>([\s\S]*?)</article>'
            cards = re.findall(card_pattern, html, re.S)
            for card in cards[:20]:
                title_match = re.search(r'<h2[^>]*class="[^"]*satin-card__title[^"]*"[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', card, re.S)
                if not title_match:
                    continue
                url, title = title_match.group(1), title_match.group(2).strip()
                if not title or "搜索" in title:
                    continue
                pic = ""
                img_match = re.search(r'<img[^>]+src="([^"]+)"[^>]*>', card, re.S)
                if img_match:
                    raw_pic = img_match.group(1)
                    if "wp.com" in raw_pic or "jrtk.cc" in raw_pic or "mxhxs.cc" in raw_pic:
                        clean_match = re.search(r'[?&]url=([^&]+)', raw_pic)
                        if clean_match:
                            raw_pic = clean_match.group(1)
                        pic = raw_pic
                    else:
                        pic = urljoin(self.host, raw_pic)
                category = ""
                cat_match = re.search(r'<a[^>]*class="[^"]*satin-category[^"]*"[^>]*>([^<]+)</a>', card, re.S)
                if cat_match:
                    category = cat_match.group(1).strip()
                items.append({
                    "vod_id": url,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": category or "图集"
                })
            return {"list": items}
        except Exception as e:
            self.log({"action": "homeVideoContent_error", "error": str(e)})
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        """分类列表 - 按分类获取图集"""
        page = int(pg) if pg else 1
        try:
            # 构建URL
            if tid == "all":
                url = self.host + "/"
            else:
                url = self.host + "/?cat=" + str(tid)
            if page > 1:
                if "?" in url:
                    url += "&paged=" + str(page)
                else:
                    url += "?paged=" + str(page)
            
            html = self.fetch(url, headers=self.headers, timeout=15).text
            if not html:
                return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}

            items = []
            card_pattern = r'<article[^>]*class="[^"]*satin-card[^"]*"[^>]*>([\s\S]*?)</article>'
            cards = re.findall(card_pattern, html, re.S)
            
            for card in cards:
                title_match = re.search(r'<h2[^>]*class="[^"]*satin-card__title[^"]*"[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', card, re.S)
                if not title_match:
                    continue
                url, title = title_match.group(1), title_match.group(2).strip()
                if not title or "搜索" in title:
                    continue
                pic = ""
                img_match = re.search(r'<img[^>]+src="([^"]+)"[^>]*>', card, re.S)
                if img_match:
                    raw_pic = img_match.group(1)
                    if "wp.com" in raw_pic or "jrtk.cc" in raw_pic or "mxhxs.cc" in raw_pic:
                        clean_match = re.search(r'[?&]url=([^&]+)', raw_pic)
                        if clean_match:
                            raw_pic = clean_match.group(1)
                        pic = raw_pic
                    else:
                        pic = urljoin(self.host, raw_pic)
                category = ""
                cat_match = re.search(r'<a[^>]*class="[^"]*satin-category[^"]*"[^>]*>([^<]+)</a>', card, re.S)
                if cat_match:
                    category = cat_match.group(1).strip()
                items.append({
                    "vod_id": url,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": category or "图集"
                })
            
            # 获取总页数
            pagecount = 1
            page_links = re.findall(r'<a[^>]*class="[^"]*page-numbers[^"]*"[^>]*>(\d+)</a>', html, re.S)
            if page_links:
                pagecount = max([int(p) for p in page_links if p.isdigit()])
            # 检查下一页
            if re.search(r'class="[^"]*next[^"]*page-numbers[^"]*"', html, re.S) or re.search(r'下一页', html, re.S):
                if pagecount <= page:
                    pagecount = page + 1
            
            return {
                "list": items,
                "page": page,
                "pagecount": pagecount,
                "limit": 20,
                "total": len(items)
            }
        except Exception as e:
            self.log({"action": "categoryContent_error", "error": str(e)})
            return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        """详情页 - 提取图集信息"""
        if not ids:
            return {"list": []}
        url = ids[0]
        if not url.startswith("http"):
            url = urljoin(self.host, url)
        try:
            html = self.fetch(url, headers=self.headers, timeout=15).text
            if not html:
                return {"list": []}
            title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html, re.S)
            title = title_match.group(1).strip() if title_match else "图集"
            
            # 提取正文内容
            content_scope = ""
            scope_match = re.search(r'<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>([\s\S]*?)(?:</div>|$)', html, re.S)
            if scope_match:
                content_scope = scope_match.group(1)
            else:
                content_scope = html
            
            # 提取所有图片
            img_pattern = r'<img[^>]+src="([^"]+)"[^>]*>'
            imgs = re.findall(img_pattern, content_scope, re.S)
            
            # 过滤杂图和emoji
            bad_keywords = ["avatar", "logo", "icon", "loading", "qrcode", "none", "thumb", "favicon", "static", "gif", "emoji", "svg"]
            filtered = []
            for img in imgs:
                img_lower = img.lower()
                if any(k in img_lower for k in bad_keywords):
                    continue
                # 放宽条件，不仅限于wp-content/uploads
                if "emoji" in img_lower or "svg" in img_lower:
                    continue
                img_url = urljoin(self.host, img)
                if img_url not in filtered:
                    filtered.append(img_url)
            
            # 如果提取不到图片，返回空
            if not filtered:
                return {"list": []}
            
            # 封面图：优先使用正文第一张图片
            pic = filtered[0]
            
            # 图片数量备注
            remark = str(len(filtered)) + "P"
            
            pics_url = "pics://" + "&&".join([f + "@Referer=" + self.host + "/" for f in filtered])
            vod = {
                "vod_id": url,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
                "vod_content": "共" + remark,
                "vod_play_from": "图片浏览",
                "vod_play_url": "浏览$" + pics_url
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"action": "detailContent_error", "error": str(e)})
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        """搜索"""
        if not key:
            return {"list": [], "page": 1}
        page = int(pg) if pg else 1
        try:
            url = self.host + "/?s=" + quote(str(key))
            if page > 1:
                url += "&paged=" + str(page)
            html = self.fetch(url, headers=self.headers, timeout=15).text
            if not html:
                return {"list": [], "page": page}
            items = []
            card_pattern = r'<article[^>]*class="[^"]*satin-card[^"]*"[^>]*>([\s\S]*?)</article>'
            cards = re.findall(card_pattern, html, re.S)
            for card in cards:
                title_match = re.search(r'<h2[^>]*class="[^"]*satin-card__title[^"]*"[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', card, re.S)
                if not title_match:
                    continue
                url, title = title_match.group(1), title_match.group(2).strip()
                if not title or "搜索" in title:
                    continue
                pic = ""
                img_match = re.search(r'<img[^>]+src="([^"]+)"[^>]*>', card, re.S)
                if img_match:
                    raw_pic = img_match.group(1)
                    if "wp.com" in raw_pic or "jrtk.cc" in raw_pic or "mxhxs.cc" in raw_pic:
                        clean_match = re.search(r'[?&]url=([^&]+)', raw_pic)
                        if clean_match:
                            raw_pic = clean_match.group(1)
                        pic = raw_pic
                    else:
                        pic = urljoin(self.host, raw_pic)
                category = ""
                cat_match = re.search(r'<a[^>]*class="[^"]*satin-category[^"]*"[^>]*>([^<]+)</a>', card, re.S)
                if cat_match:
                    category = cat_match.group(1).strip()
                items.append({
                    "vod_id": url,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": category or "图集"
                })
            return {"list": items, "page": page}
        except Exception as e:
            self.log({"action": "searchContent_error", "error": str(e)})
            return {"list": [], "page": page}

    def playerContent(self, flag, id, vipFlags):
        """播放 - 图片走 pics:// 协议"""
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        if id.startswith("pics://"):
            return {"parse": 0, "url": id, "header": {"Referer": self.host + "/"}}
        if "&&" in id and "http" in id:
            id = "pics://" + id
            return {"parse": 0, "url": id, "header": {"Referer": self.host + "/"}}
        return {"parse": 0, "url": "", "header": {}}

    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass