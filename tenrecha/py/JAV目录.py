# -*- coding: utf-8 -*-
# JAV目录大全 - TVBox爬虫
# 站点: https://javmenu.com

import sys
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "JAV目录"

    def init(self, extend=""):
        self.baseUrl = "https://javmenu.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.baseUrl + "/",
        })

        # 分类映射（从导航中提取）
        self.class_map = {
            "censored/online": "有碼 在線看",
            "uncensored/online": "無碼 在線看",
            "western/online": "歐美 在線看",
            "fc2/online": "FC2 在線看",
            "hanime/online": "成人動畫 在線看",
            "chinese/online": "國產 在線看",
            "censored": "有碼 最新種子",
            "uncensored": "無碼 最新種子",
            "western": "歐美 最新種子",
            "fc2": "FC2 最新種子",
            "hanime": "成人動畫 最新種子",
            "chinese": "國產 最新種子",
        }

    def _fetch(self, url, timeout=15):
        try:
            resp = self.session.get(url, timeout=timeout)
            resp.encoding = "utf-8"
            return resp.text
        except Exception as e:
            print(f"[JAV] 请求失败: {url} -> {e}")
            return ""

    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return urljoin(self.baseUrl, url)
        if url.startswith("http"):
            return url
        return urljoin(self.baseUrl, "/" + url)

    # ========== 解析视频列表（首页/分类页） ==========
    def _parse_video_list(self, html):
        """解析视频卡片列表"""
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        videos = []

        # 查找所有卡片 .video-list-item
        items = soup.select(".video-list-item .card")
        if not items:
            # 兜底：查找任何包含 card 的列表项
            items = soup.select(".col-xl-2 .card, .col-sm-6 .card")

        for item in items:
            try:
                # 获取链接
                a_tag = item.select_one("a")
                if not a_tag:
                    continue
                href = a_tag.get("href", "")
                if not href or href == "#":
                    continue

                # 提取番号/ID
                vid = href.split("/")[-1] if href.startswith("/") else href
                if not vid:
                    vid = href

                # 标题
                title = ""
                title_tag = item.select_one(".card-title")
                if title_tag:
                    title = title_tag.get_text(strip=True)
                if not title:
                    title = a_tag.get("title", "") or a_tag.get_text(strip=True)

                # 描述（简介）
                desc = ""
                desc_tag = item.select_one(".card-text")
                if desc_tag:
                    desc = desc_tag.get_text(strip=True)

                # 封面图（懒加载 data-src）
                img = item.select_one("img.card-img-top")
                pic = ""
                if img:
                    pic = img.get("data-src") or img.get("src") or ""
                pic = self._fix_url(pic)

                # 标签（如 "在線看", "可下載", "中文字幕" 等）
                tags = []
                tag_spans = item.select(".video-list-item-tag-wrapper .badge")
                for span in tag_spans:
                    tag_text = span.get_text(strip=True)
                    if tag_text:
                        tags.append(tag_text)
                remark = " ".join(tags)

                # 日期
                date = ""
                date_tag = item.select_one(".text-muted")
                if date_tag:
                    date = date_tag.get_text(strip=True)

                # 组合备注
                if date:
                    remark = f"{date} {remark}".strip()

                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark,
                    "_desc": desc,
                    "_href": href,
                })
            except Exception as e:
                print(f"[JAV] 解析卡片失败: {e}")
                continue

        return videos

    # ========== 解析详情页 ==========
    def _parse_detail(self, html):
        soup = BeautifulSoup(html, "html.parser")

        # 标题（番号 + 标题）
        title = ""
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)
        if not title:
            og_title = soup.find("meta", property="og:title")
            if og_title:
                title = og_title.get("content", "")

        # 封面
        pic = ""
        og_image = soup.find("meta", property="og:image")
        if og_image:
            pic = og_image.get("content", "")
        if not pic:
            img = soup.select_one(".embed-responsive-item")
            if img:
                pic = img.get("data-src") or img.get("src") or ""
        pic = self._fix_url(pic)

        # 简介/描述
        desc = ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            desc = meta_desc.get("content", "")
        if not desc:
            og_desc = soup.find("meta", property="og:description")
            if og_desc:
                desc = og_desc.get("content", "")
        if not desc:
            p_desc = soup.select_one(".card-text")
            if p_desc:
                desc = p_desc.get_text(strip=True)

        # 提取播放地址（视频源）
        play_url = ""
        # 1. 查找 video 标签
        video = soup.find("video")
        if video:
            src = video.get("src") or ""
            if src:
                play_url = self._fix_url(src)
        # 2. 查找 iframe
        if not play_url:
            iframe = soup.find("iframe")
            if iframe:
                src = iframe.get("src") or ""
                if src:
                    play_url = self._fix_url(src)
        # 3. 查找 m3u8 链接
        if not play_url:
            m3u8_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
            if m3u8_match:
                play_url = m3u8_match.group(1)
        # 4. 查找 mp4 链接
        if not play_url:
            mp4_match = re.search(r'(https?://[^\s"\']+\.mp4[^\s"\']*)', html)
            if mp4_match:
                play_url = mp4_match.group(1)
        # 5. 查找 JS 中的 video_url
        if not play_url:
            js_match = re.search(r'video_url\s*[:=]\s*["\']([^"\']+)["\']', html)
            if js_match:
                play_url = self._fix_url(js_match.group(1))

        return {
            "title": title or "未知",
            "pic": pic,
            "desc": desc or "暂无简介",
            "play_url": play_url,
        }

    # ========== TVBox 接口 ==========

    def homeContent(self, filter=False):
        classes = [
            {"type_id": "censored/online", "type_name": "📺 有碼 在線看"},
            {"type_id": "uncensored/online", "type_name": "📺 無碼 在線看"},
            {"type_id": "western/online", "type_name": "📺 歐美 在線看"},
            {"type_id": "fc2/online", "type_name": "📺 FC2 在線看"},
            {"type_id": "hanime/online", "type_name": "📺 成人動畫 在線看"},
            {"type_id": "chinese/online", "type_name": "📺 國產 在線看"},
            {"type_id": "censored", "type_name": "🧲 有碼 最新種子"},
            {"type_id": "uncensored", "type_name": "🧲 無碼 最新種子"},
            {"type_id": "western", "type_name": "🧲 歐美 最新種子"},
            {"type_id": "fc2", "type_name": "🧲 FC2 最新種子"},
            {"type_id": "hanime", "type_name": "🧲 成人動畫 最新種子"},
            {"type_id": "chinese", "type_name": "🧲 國產 最新種子"},
        ]
        return {"class": classes}

    def homeVideoContent(self):
        """首页推荐：直接抓取首页轮播和推荐列表"""
        html = self._fetch(self.baseUrl)
        if not html:
            return {"list": []}
        # 首页推荐通常是轮播 + "在線看" 列表，我们合并前20个
        items = self._parse_video_list(html)
        # 去重
        seen = set()
        unique = []
        for v in items:
            if v["vod_id"] not in seen:
                seen.add(v["vod_id"])
                unique.append(v)
        return {"list": unique[:20]}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        try:
            pg = int(pg) if pg else 1

            # 构造分类 URL
            # tid 格式如 "censored/online" 或 "censored"
            # 如果以 "/" 结尾可能不需要，直接拼接
            if tid.endswith("/"):
                url_path = tid
            else:
                url_path = tid

            # 分页参数：部分分类页面支持 ?page= 或 &page=
            if pg > 1:
                # 查看原页面分页通常用 ?page= 或 &page=，我们尝试常见方式
                url = self.baseUrl + "/" + url_path
                if "?" in url:
                    url += f"&page={pg}"
                else:
                    url += f"?page={pg}"
            else:
                url = self.baseUrl + "/" + url_path

            html = self._fetch(url)
            if not html:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}

            items = self._parse_video_list(html)

            # 提取总页数（从分页控件中）
            pagecount = pg
            soup = BeautifulSoup(html, "html.parser")
            # 查找分页链接
            pagination = soup.select(".pagination a, .page-link")
            for a in pagination:
                href = a.get("href", "")
                m = re.search(r"page=(\d+)", href)
                if m:
                    num = int(m.group(1))
                    if num > pagecount:
                        pagecount = num
            # 如果没有提取到，且列表长度>=20，假定有下一页
            if pagecount == pg and len(items) >= 20:
                pagecount = pg + 1

            return {
                "list": items,
                "page": pg,
                "pagecount": pagecount,
                "limit": len(items),
                "total": pagecount * 20,
            }
        except Exception as e:
            print(f"[JAV] categoryContent error: {e}")
            return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}

    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            # 如果 vid 不是完整 URL，构造
            if not vid.startswith("http"):
                # 可能 vid 是 "CAWB-025"，链接是 /CAWB-025
                detail_url = self.baseUrl + "/" + vid
            else:
                detail_url = vid

            html = self._fetch(detail_url)
            if not html:
                return {"list": []}

            data = self._parse_detail(html)

            # 如果没有播放地址，尝试从页面中寻找iframe并提取
            if not data["play_url"]:
                # 可能页面有播放按钮，点击后加载，但我们无法执行JS，只能尝试从源码中找
                # 如果找不到，返回详情页URL，让用户用WebView打开
                data["play_url"] = detail_url

            vod = {
                "vod_id": vid,
                "vod_name": data["title"],
                "vod_pic": data["pic"],
                "vod_poster": data["pic"],
                "vod_img": data["pic"],
                "vod_content": data["desc"],
                "vod_play_from": "JAV目录",
                "vod_play_url": data["play_url"] if data["play_url"] else "",
            }
            return {"list": [vod]}
        except Exception as e:
            print(f"[JAV] detailContent error: {e}")
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        # 如果播放地址是 m3u8 或 mp4，直接返回
        if id and (".m3u8" in id or ".mp4" in id):
            return {"parse": 0, "url": id, "header": {"Referer": self.baseUrl + "/"}}
        # 否则视为详情页URL，使用WebView打开
        return {"parse": 1, "url": id, "header": {"Referer": self.baseUrl + "/"}}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg) if pg else 1
            enc_key = quote(key)
            url = self.baseUrl + f"/search?wd={enc_key}"
            if pg > 1:
                url += f"&page={pg}"
            html = self._fetch(url)
            if not html:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}

            items = self._parse_video_list(html)
            pagecount = pg
            soup = BeautifulSoup(html, "html.parser")
            pagination = soup.select(".pagination a")
            for a in pagination:
                href = a.get("href", "")
                m = re.search(r"page=(\d+)", href)
                if m:
                    num = int(m.group(1))
                    if num > pagecount:
                        pagecount = num
            if pagecount == pg and len(items) >= 20:
                pagecount = pg + 1

            return {
                "list": items,
                "page": pg,
                "pagecount": pagecount,
                "limit": len(items),
                "total": pagecount * 20,
            }
        except Exception as e:
            print(f"[JAV] searchContent error: {e}")
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 0, "total": 0}

    def isVideoFormat(self, url):
        return url and (".m3u8" in url or ".mp4" in url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self.session:
            self.session.close()

    def localProxy(self, param):
        return None