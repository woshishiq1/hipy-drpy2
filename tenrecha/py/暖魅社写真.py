# coding: utf-8
# 站点信息
# 主域名: https://lisise.com
# 备用域名: 无
# 发布页: 无
# 内容类型: 写真/图集（图片+视频）
# 特殊说明: WordPress站，需要登录才能下载原图，本脚本仅提取预览图
# 最后验证时间: 2026-09-03
# 来源: 用户提供

import json
import re
from urllib.parse import quote, urljoin, unquote

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://lisise.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        # 分类列表 - 从首页导航提取的主要分类
        self.classes = [
            {"type_id": "song", "type_name": "高清写真"},
            {"type_id": "video", "type_name": "精品写真"},
            {"type_id": "fmp", "type_name": "珍藏写真"},
        ]
        # 筛选器 - 该站无筛选功能
        self.filters = {
            "song": [],
            "video": [],
            "fmp": []
        }

    def getName(self):
        return "暖魅社写真"

    def getDependence(self):
        return []

    def setExtendInfo(self, extend):
        return None

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐 - 从首页提取最新内容"""
        try:
            html = self.fetch(self.host, headers=self.headers, timeout=10).text
            items = []
            # 提取首页文章列表
            # 首页使用 .post-list-container .item 结构
            blocks = re.findall(
                r'<div class="item"[^>]*title="([^"]*)"[^>]*>.*?<a href="([^"]+)".*?<div class="post-image"[^>]*style="background-image:url\(([^)]+)\)".*?<span>([^<]*)</span>.*?<h3>([^<]*)</h3>.*?<p>([^<]*)</p>',
                html,
                re.S
            )
            if not blocks:
                # 备用：从首页轮播提取
                blocks = re.findall(
                    r'<a href="([^"]+)".*?<div class="swiper-slide-1-image"[^>]*style="background-image:url\(([^)]+)\)".*?<span class="type-text">([^<]*)</span>.*?<h3>([^<]*)</h3>.*?<p>([^<]*)</p>',
                    html,
                    re.S
                )
                for url, pic, type_text, title, remark in blocks:
                    if not url or not title:
                        continue
                    items.append({
                        "vod_id": url,
                        "vod_name": title.strip(),
                        "vod_pic": pic.strip() if pic.startswith("http") else self.host + pic.strip(),
                        "vod_remarks": remark.strip() or type_text.strip()
                    })
            else:
                for title_attr, url, pic, type_text, title, remark in blocks:
                    if not url or not title:
                        continue
                    items.append({
                        "vod_id": url,
                        "vod_name": title.strip(),
                        "vod_pic": pic.strip() if pic.startswith("http") else self.host + pic.strip(),
                        "vod_remarks": remark.strip() or type_text.strip()
                    })
            return {"list": items[:20]}
        except Exception as e:
            self.log({"action": "homeVideoContent", "error": str(e)})
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        """分类列表"""
        page = pg or "1"
        try:
            # 分类页面URL格式: https://lisise.com/archives/category/{slug}/page/{page_num}
            url = f"{self.host}/archives/category/{tid}/page/{page}"
            html = self.fetch(url, headers=self.headers, timeout=10).text
            items = []
            # 提取文章列表 - 与首页同样的结构
            blocks = re.findall(
                r'<div class="item"[^>]*title="([^"]*)"[^>]*>.*?<a href="([^"]+)".*?<div class="post-image"[^>]*style="background-image:url\(([^)]+)\)".*?<span>([^<]*)</span>.*?<h3>([^<]*)</h3>.*?<p>([^<]*)</p>',
                html,
                re.S
            )
            for title_attr, url, pic, type_text, title, remark in blocks:
                if not url or not title:
                    continue
                items.append({
                    "vod_id": url,
                    "vod_name": title.strip(),
                    "vod_pic": pic.strip() if pic.startswith("http") else self.host + pic.strip(),
                    "vod_remarks": remark.strip() or type_text.strip()
                })
            # 计算总页数
            total_match = re.search(r'<a class="page-num"[^>]*>(\d+)</a>', html)
            total = int(total_match.group(1)) if total_match else 1
            return {
                "list": items,
                "page": int(page),
                "pagecount": total,
                "limit": 20,
                "total": total * 20
            }
        except Exception as e:
            self.log({"action": "categoryContent", "tid": tid, "pg": page, "error": str(e)})
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        """详情页 - 提取图片列表"""
        try:
            url = ids[0]
            if not url.startswith("http"):
                url = self.host + url
            html = self.fetch(url, headers=self.headers, timeout=10).text

            # 提取标题
            title_match = re.search(r'<h1[^>]*>([^<]*)</h1>', html)
            title = title_match.group(1).strip() if title_match else "未知标题"

            # 提取封面/预览图
            pic = ""
            pic_match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
            if pic_match:
                pic = pic_match.group(1)
            if not pic:
                pic_match = re.search(r'<div class="post-image"[^>]*style="background-image:url\(([^)]+)\)"', html)
                if pic_match:
                    pic = pic_match.group(1)
            if pic and not pic.startswith("http"):
                pic = self.host + pic

            # 提取备注（分类/日期）
            remark = ""
            remark_match = re.search(r'<p[^>]*>([^<]*)</p>.*?<p[^>]*>([^<]*)</p>', html)
            if remark_match:
                remark = remark_match.group(1).strip() + " / " + remark_match.group(2).strip()

            # 提取正文中的所有图片（预览图）
            # 优先从正文容器中提取
            content_scope = html
            content_match = re.search(
                r'<div[^>]*class="[^"]*post-message[^"]*"[^>]*>([\s\S]*?)(?:<div[^>]*class="[^"]*related|</div>\s*<div[^>]*class="[^"]*post-footer|</article>)',
                html,
                re.S
            )
            if content_match:
                content_scope = content_match.group(1)

            imgs = re.findall(r'<img[^>]+(?:src|data-src|data-original)=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)["\']', content_scope, re.S)
            
            # 去重
            imgs = list(dict.fromkeys(imgs))
            
            # 过滤小图标/头像/广告
            bad_keywords = ['avatar', 'icon', 'logo', 'loading', 'smilies', 'qrcode', 'none.gif', 'thumb', 'static', 'favicon', 'histats']
            filtered = []
            for img in imgs:
                img_lower = img.lower()
                if any(k in img_lower for k in bad_keywords):
                    continue
                if not img.startswith("http"):
                    img = self.host + img
                # 追加Referer防盗链
                filtered.append(img + "@Referer=" + self.host + "/")
            
            # 如果没有提取到图片，尝试从页面中的图集元素提取
            if not filtered:
                # 尝试从 .post-image 提取
                pic_match = re.findall(r'<div[^>]*class="[^"]*post-image[^"]*"[^>]*style="background-image:url\(([^)]+)\)"', html)
                for p in pic_match:
                    if p and not p.startswith("http"):
                        p = self.host + p
                    filtered.append(p + "@Referer=" + self.host + "/")
                filtered = list(dict.fromkeys(filtered))

            # 构建播放地址
            if filtered:
                play_url = "pics://" + "&&".join(filtered)
            else:
                play_url = ""

            vod = {
                "vod_id": url,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark or "写真图集",
                "vod_content": f"共 {len(filtered)} 张图片，需登录下载原图",
                "vod_play_from": "图片浏览",
                "vod_play_url": f"浏览图片${play_url}" if play_url else ""
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"action": "detailContent", "url": ids[0] if ids else "", "error": str(e)})
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        """搜索"""
        try:
            page = pg or "1"
            # WordPress搜索接口
            url = f"{self.host}/?s={quote(key)}&page={page}"
            html = self.fetch(url, headers=self.headers, timeout=10).text
            items = []
            # 提取搜索结果
            blocks = re.findall(
                r'<div class="item"[^>]*title="([^"]*)"[^>]*>.*?<a href="([^"]+)".*?<div class="post-image"[^>]*style="background-image:url\(([^)]+)\)".*?<span>([^<]*)</span>.*?<h3>([^<]*)</h3>.*?<p>([^<]*)</p>',
                html,
                re.S
            )
            for title_attr, url, pic, type_text, title, remark in blocks:
                if not url or not title:
                    continue
                items.append({
                    "vod_id": url,
                    "vod_name": title.strip(),
                    "vod_pic": pic.strip() if pic.startswith("http") else self.host + pic.strip(),
                    "vod_remarks": remark.strip() or type_text.strip()
                })
            return {"list": items, "page": int(page)}
        except Exception as e:
            self.log({"action": "searchContent", "key": key, "error": str(e)})
            return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags):
        """播放 - 对于pics://协议直接返回"""
        if id.startswith("pics://"):
            return {"parse": 0, "url": id, "header": self.headers}
        # 如果传入的是详情页URL，提取图片
        if id.startswith("http") and "/archives/" in id:
            try:
                html = self.fetch(id, headers=self.headers, timeout=10).text
                content_scope = html
                content_match = re.search(
                    r'<div[^>]*class="[^"]*post-message[^"]*"[^>]*>([\s\S]*?)(?:<div[^>]*class="[^"]*related|</div>\s*<div[^>]*class="[^"]*post-footer|</article>)',
                    html,
                    re.S
                )
                if content_match:
                    content_scope = content_match.group(1)
                imgs = re.findall(r'<img[^>]+(?:src|data-src|data-original)=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)["\']', content_scope, re.S)
                imgs = list(dict.fromkeys(imgs))
                bad_keywords = ['avatar', 'icon', 'logo', 'loading', 'smilies', 'qrcode', 'none.gif', 'thumb', 'static', 'favicon']
                filtered = []
                for img in imgs:
                    img_lower = img.lower()
                    if any(k in img_lower for k in bad_keywords):
                        continue
                    if not img.startswith("http"):
                        img = self.host + img
                    filtered.append(img + "@Referer=" + self.host + "/")
                if filtered:
                    return {"parse": 0, "url": "pics://" + "&&".join(filtered), "header": self.headers}
            except Exception as e:
                self.log({"action": "playerContent", "error": str(e)})
        return {"parse": 0, "url": "", "header": {}}

    def recommendContent(self, ids, pg):
        """相关推荐"""
        try:
            url = ids[0] if ids else ""
            if not url.startswith("http"):
                url = self.host + url
            html = self.fetch(url, headers=self.headers, timeout=10).text
            items = []
            # 提取相关推荐
            blocks = re.findall(
                r'<div class="item"[^>]*title="([^"]*)"[^>]*>.*?<a href="([^"]+)".*?<div class="post-image"[^>]*style="background-image:url\(([^)]+)\)".*?<span>([^<]*)</span>.*?<h3>([^<]*)</h3>.*?<p>([^<]*)</p>',
                html,
                re.S
            )
            for title_attr, rec_url, pic, type_text, title, remark in blocks:
                if not rec_url or not title:
                    continue
                items.append({
                    "vod_id": rec_url,
                    "vod_name": title.strip(),
                    "vod_pic": pic.strip() if pic.startswith("http") else self.host + pic.strip(),
                    "vod_remarks": remark.strip() or type_text.strip()
                })
            return {"list": items[:10]}
        except Exception:
            return {"list": []}

    def destroy(self):
        pass