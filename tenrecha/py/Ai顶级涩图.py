# coding: utf-8
"""
站点: Ai顶级涩图
主域名: https://aidjst.cc/888/
内容类型: AI绘画图片站 (pics://协议)
特殊说明: WordPress站，分类页面404，所有内容在首页，分类仅作标签显示
最后验证时间: 2026-09-04
来源: 用户提供
m3u8结构: 无，纯图片站
"""
import re
import urllib.request
import urllib.parse
import ssl
from urllib.parse import urljoin, quote

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://aidjst.cc/888"
        # 分类硬编码 - 由于分类页面404，所有分类均返回首页内容
        self.classes = [
            {"type_id": "all", "type_name": "全部"},
            {"type_id": "doupo", "type_name": "斗破苍穹"},
            {"type_id": "douluo", "type_name": "斗罗大陆"},
            {"type_id": "uncategorized", "type_name": "未分类"},
        ]
        self.filters = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36",
            "Referer": self.host + "/"
        }
        self.page_size = 10
        # 分类slug映射 - 仅用于显示，实际不用于URL
        self.category_slugs = {
            "doupo": "斗破苍穹",
            "douluo": "斗罗大陆",
            "uncategorized": "uncategorized"
        }

    def getName(self):
        return "Ai顶级涩图"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def _fetch_text(self, url):
        """获取页面文本 - 兼容沙盒环境"""
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            return resp.text
        except Exception as e:
            pass
        try:
            context = ssl._create_unverified_context()
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=15, context=context) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
            raise e

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐 - 抓取首页文章列表"""
        return self._fetch_list(self.host)

    def categoryContent(self, tid, pg, filter, extend):
        """
        分类列表 - 由于分类页面404，所有分类均返回首页内容
        分页使用正确的URL格式: /index.php/page/{page}/
        """
        page = int(pg or 1)
        # 所有分类都返回首页列表，分页URL使用 index.php/page/{page}/
        if page <= 1:
            url = self.host + "/"
        else:
            url = f"{self.host}/index.php/page/{page}/"

        result = self._fetch_list(url)
        items = result.get("list", [])
        total = page * self.page_size + 10
        return {
            "list": items,
            "page": page,
            "pagecount": page + 5 if items else page,
            "limit": self.page_size,
            "total": total if items else 0
        }

    def _fetch_list(self, url):
        """通用列表抓取方法"""
        try:
            html = self._fetch_text(url)
        except Exception as e:
            self.log(f"fetch_list error: {e}")
            return {"list": []}

        items = []
        # 匹配文章块
        pattern = r'<article[^>]*id="post-(\d+)"[^>]*>([\s\S]*?)</article>'
        for post_id, block in re.findall(pattern, html, re.S):
            # 提取标题和链接
            title_match = re.search(r'<h[23][^>]*class="[^"]*entry-title[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', block, re.S)
            if not title_match:
                continue
            link = title_match.group(1)
            title = title_match.group(2).strip()
            # 提取封面图
            pic_match = re.search(r'<img[^>]+src="([^"]+)"[^>]*>', block, re.S)
            pic = pic_match.group(1) if pic_match else ""
            # 提取分类标签
            cat_match = re.search(r'<a[^>]*rel="category tag"[^>]*>([^<]+)</a>', block, re.S)
            remark = cat_match.group(1) if cat_match else ""
            items.append({
                "vod_id": link,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark[:20] if remark else "",
            })
        return {"list": items}

    def detailContent(self, ids):
        """详情页 - 提取所有图片"""
        url = ids[0] if ids else ""
        if not url or not url.startswith("http"):
            return {"list": []}

        try:
            html = self._fetch_text(url)
        except Exception as e:
            self.log(f"detail error: {e}")
            return {"list": []}

        title_match = re.search(r'<h1[^>]*class="[^"]*entry-title[^"]*"[^>]*>([^<]+)</h1>', html, re.S)
        title = title_match.group(1).strip() if title_match else "图片"

        content_match = re.search(r'<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>([\s\S]*?)(?:</div>|</article>)', html, re.S)
        scope = content_match.group(1) if content_match else html

        imgs = re.findall(r'<img[^>]+src="([^"]+\.(?:jpg|jpeg|png|webp|gif))"', scope, re.S)
        imgs += re.findall(r'<img[^>]+data-src="([^"]+\.(?:jpg|jpeg|png|webp|gif))"', scope, re.S)

        filtered = []
        seen = set()
        bad_keywords = ['avatar', 'icon', 'logo', 'loading', 'smilies', 'qrcode', 'thumb', 'index', 'favicon', 'static']
        for img in imgs:
            img = img.strip()
            if not img or img in seen:
                continue
            img_lower = img.lower()
            if any(k in img_lower for k in bad_keywords):
                continue
            if img.startswith("//"):
                img = "https:" + img
            elif img.startswith("/"):
                img = urljoin(self.host, img)
            filtered.append(img)
            seen.add(img)

        if not filtered:
            all_imgs = re.findall(r'<img[^>]+src="([^"]+)"', html, re.S)
            for img in all_imgs:
                img = img.strip()
                if not img or img in seen:
                    continue
                if any(k in img.lower() for k in bad_keywords):
                    continue
                if img.startswith("//"):
                    img = "https:" + img
                elif img.startswith("/"):
                    img = urljoin(self.host, img)
                filtered.append(img)
                seen.add(img)

        pics_play = "&&".join([f"{img}@Referer={self.host}/" for img in filtered])

        vod = {
            "vod_id": url,
            "vod_name": title,
            "vod_pic": filtered[0] if filtered else "",
            "vod_remarks": f"共{len(filtered)}张",
            "vod_content": f"共{len(filtered)}张图片",
            "vod_play_from": "图片浏览",
            "vod_play_url": f"浏览图片$pics://{pics_play}" if filtered else ""
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg or 1)
        url = f"{self.host}/?s={quote(key)}"
        if page > 1:
            url = f"{self.host}/page/{page}/?s={quote(key)}"

        try:
            html = self._fetch_text(url)
        except Exception as e:
            self.log(f"search error: {e}")
            return {"list": []}

        items = []
        pattern = r'<article[^>]*id="post-(\d+)"[^>]*>([\s\S]*?)</article>'
        for post_id, block in re.findall(pattern, html, re.S):
            title_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', block, re.S)
            if not title_match:
                continue
            link = title_match.group(1)
            title = title_match.group(2).strip()
            pic_match = re.search(r'<img[^>]+src="([^"]+)"[^>]*>', block, re.S)
            pic = pic_match.group(1) if pic_match else ""
            items.append({
                "vod_id": link,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "搜索结果"
            })
        return {"list": items}

    def playerContent(self, flag, id, vipFlags):
        if id.startswith("pics://"):
            return {"parse": 0, "url": id, "header": {"Referer": self.host + "/"}}
        if id.startswith("http"):
            detail = self.detailContent([id])
            if detail and detail.get("list"):
                vod = detail["list"][0]
                play_url = vod.get("vod_play_url", "")
                if play_url.startswith("浏览图片$pics://"):
                    pics_url = play_url.replace("浏览图片$", "")
                    return {"parse": 0, "url": pics_url, "header": {"Referer": self.host + "/"}}
        return {"parse": 0, "url": "", "header": {}}

    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass