#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AniGet · TVBox 爬虫
境界：道宫秘境 · 兵字秘觉醒
目标：https://aniget.com/
"""
import sys
import re
import json
import base64
import requests
from urllib import parse
from bs4 import BeautifulSoup

sys.path.append("..")
from base.spider import Spider


class Spider(Spider):
    def __init__(self):
        self.siteUrl = "https://aniget.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.siteUrl,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.session = requests.Session()
        self.tag_map = {
            "无码": "%E6%97%A0%E7%A0%81",
        }

    def init(self, extend=""):
        return True

    # ═════════ 临字秘 · 基础架构 ═════════
    def homeContent(self, filter):
        classes = [
            {"type_id": "2d", "type_name": "2D动画"},
            {"type_id": "3d", "type_name": "3D动画"},
            {"type_id": "anime", "type_name": "里番"},
            {"type_id": "donjin", "type_name": "同人作品"},
            {"type_id": "real", "type_name": "真人AI"},
            {"type_id": "tag_无码", "type_name": "🏷️ 无码"},
        ]
        return {"class": classes}

    # ═════════ 斗字秘 · 战斗解析 ═════════
    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg_int = int(pg) if pg else 1
        except:
            pg_int = 1

        if tid.startswith("tag_"):
            tag_name = tid.replace("tag_", "")
            tag_encoded = self.tag_map.get(tag_name, parse.quote(tag_name))
            if pg_int <= 1:
                url = f"{self.siteUrl}/tag/{tag_encoded}/"
            else:
                url = f"{self.siteUrl}/tag/{tag_encoded}/page/{pg_int}/"
        else:
            if pg_int <= 1:
                url = f"{self.siteUrl}/category/{tid}/"
            else:
                url = f"{self.siteUrl}/category/{tid}/page/{pg_int}/"

        print(f"[AniGet] 请求: {url}")

        try:
            resp = self.session.get(url, headers=self.headers, timeout=15)
            resp.encoding = "utf-8"
            html = resp.text
        except Exception:
            return {"list": [], "page": pg, "pagecount": 999}

        soup = BeautifulSoup(html, "html.parser")
        videos = []

        # 查找视频卡片
        for item in soup.select(".post-card"):
            try:
                a = item.find("a")
                if not a:
                    continue

                href = a.get("href", "")
                
                # 🔥 过滤广告（外部链接）
                if href.startswith("http") and "aniget.com" not in href:
                    continue

                # 提取ID
                id_match = re.search(r'/(\d+)/?$', href)
                vid = id_match.group(1) if id_match else href.strip('/')

                # 提取标题
                title_tag = item.select_one(".card-text")
                title = title_tag.get_text(strip=True) if title_tag else ""

                # 🔥 修复：提取封面图 - 多种方式
                pic = ""
                
                # 方式1: 从 .img-container 的 data-bg 提取
                img_div = item.select_one(".img-container")
                if img_div:
                    # data-bg 属性
                    bg = img_div.get("data-bg", "")
                    if bg:
                        pic = bg
                    else:
                        # style 属性中的 background-image
                        style = img_div.get("style", "")
                        bg_match = re.search(r"background-image:\s*url\(['\"]?([^)'\"]+)['\"]?\)", style)
                        if bg_match:
                            pic = bg_match.group(1)
                
                # 方式2: 找 img 标签
                if not pic:
                    img = item.find("img")
                    if img:
                        pic = img.get("data-src", "") or img.get("src", "")
                
                # 方式3: 找 lazyload 的 data-bg
                if not pic:
                    lazy_div = item.select_one(".lazyload")
                    if lazy_div:
                        pic = lazy_div.get("data-bg", "")
                
                # 补全URL
                if pic:
                    if pic.startswith("//"):
                        pic = "https:" + pic
                    elif pic.startswith("/"):
                        pic = self.siteUrl + pic
                    elif not pic.startswith("http"):
                        pic = self.siteUrl + "/" + pic.lstrip('/')

                # 提取日期作为备注
                remark = ""
                footer = item.select_one(".card-footer")
                if footer:
                    time_span = footer.select_one("span:first-child")
                    if time_span:
                        remark = time_span.get_text(strip=True)

                # 🔥 过滤广告卡片（标题含广告关键词）
                ad_keywords = ["梯子", "VPN", "加速器", "翻墙", "代理", "月付", "免费"]
                is_ad = any(kw in title for kw in ad_keywords)
                if is_ad:
                    continue

                if vid and title:
                    videos.append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": remark
                    })
            except Exception as e:
                print(f"[AniGet] 解析卡片失败: {e}")
                continue

        # 获取总页数
        pagecount = 999
        try:
            max_page = 0
            for a in soup.find_all("a"):
                href = a.get("href", "")
                m = re.search(r'/page/(\d+)/', href)
                if m:
                    page_num = int(m.group(1))
                    if page_num > max_page:
                        max_page = page_num
            if max_page > 0:
                pagecount = max_page
        except Exception:
            pass

        return {"list": videos, "page": pg, "pagecount": pagecount}

    # ═════════ 者字秘+兵字秘+前字秘 ═════════
    def detailContent(self, ids):
        vid = ids[0]
        url = f"{self.siteUrl}/{vid}/"

        try:
            resp = self.session.get(url, headers=self.headers, timeout=15)
            resp.encoding = "utf-8"
            html = resp.text
        except Exception:
            return {"list": []}

        # 提取标题
        title = "AniGet"
        try:
            soup = BeautifulSoup(html, "html.parser")
            h5 = soup.find("h5", class_="fw-bold")
            if h5:
                title = h5.get_text(strip=True)
            else:
                m = re.search(r'<title>([^<]+)</title>', html)
                if m:
                    title = m.group(1).split(" - ")[0].strip()
        except Exception:
            pass

        # 兵字秘：6层视频地址提取
        play_url = ""

        # 第1层：data-encoded-src 属性（Base64编码）
        if not play_url:
            try:
                m = re.search(r'data-encoded-src="([^"]+)"', html)
                if m:
                    encoded = m.group(1)
                    play_url = base64.b64decode(encoded).decode("utf-8")
                    print(f"[AniGet] Base64解码成功")
            except Exception:
                pass

        # 第2层：video标签src
        if not play_url:
            try:
                m = re.search(r'<video[^>]+src=["\']([^"\']+)["\']', html)
                if m:
                    play_url = m.group(1)
            except Exception:
                pass

        # 第3层：source标签src
        if not play_url:
            try:
                m = re.search(r'<source[^>]+src=["\']([^"\']+)["\']', html)
                if m:
                    play_url = m.group(1)
            except Exception:
                pass

        # 第4层：m3u8/mp4直链
        if not play_url:
            try:
                m = re.search(r'(https?://[^\s"\']+\.(?:m3u8|mp4|mkv|webm)[^\s"\']*)', html)
                if m:
                    play_url = m.group(1)
            except Exception:
                pass

        # 第5层：iframe中的src
        if not play_url:
            try:
                m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html)
                if m:
                    src = m.group(1)
                    if src.startswith("//"):
                        src = "https:" + src
                    elif not src.startswith("http"):
                        src = parse.urljoin(self.siteUrl, src)
                    play_url = src
            except Exception:
                pass

        # 第6层：JSON中的url字段
        if not play_url:
            try:
                m = re.search(r'"url"\s*:\s*"([^"]+\.(?:m3u8|mp4)[^"]*)"', html)
                if m:
                    play_url = m.group(1).replace("\\/", "/")
            except Exception:
                pass

        if play_url and play_url.startswith('/'):
            play_url = parse.urljoin(self.siteUrl, play_url)

        play_url_str = f"第1集${play_url}" if play_url else ""

        return {
            "list": [{
                "vod_id": vid,
                "vod_name": title,
                "vod_play_from": "AniGet",
                "vod_play_url": play_url_str
            }]
        }

    # ═════════ 兵字秘+阵字秘 ═════════
    def playerContent(self, flag, id, vipFlags):
        if id.startswith("http"):
            if not self.isVideoFormat(id):
                return {
                    "parse": 1,
                    "url": id,
                    "header": json.dumps({
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": self.siteUrl
                    })
                }
            return {
                "parse": 0,
                "url": id,
                "header": json.dumps({
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.siteUrl
                })
            }
        return {"parse": 0, "url": id, "header": ""}

    # ═════════ 临字秘+斗字秘 ═════════
    def searchContent(self, key, quick, pg="1"):
        search_url = f"{self.siteUrl}/?s={parse.quote(key)}"
        if pg != "1":
            search_url += f"&paged={pg}"

        try:
            resp = self.session.get(search_url, headers=self.headers, timeout=15)
            resp.encoding = "utf-8"
            html = resp.text
        except Exception:
            return {"list": [], "page": pg, "pagecount": 999}

        soup = BeautifulSoup(html, "html.parser")
        videos = []

        for item in soup.select(".post-card"):
            try:
                a = item.find("a")
                if not a:
                    continue
                href = a.get("href", "")
                
                if href.startswith("http") and "aniget.com" not in href:
                    continue
                    
                id_match = re.search(r'/(\d+)/?$', href)
                vid = id_match.group(1) if id_match else href.strip('/')

                title_tag = item.select_one(".card-text")
                title = title_tag.get_text(strip=True) if title_tag else ""

                pic = ""
                img_div = item.select_one(".img-container")
                if img_div:
                    bg = img_div.get("data-bg", "")
                    if bg:
                        pic = bg
                    else:
                        style = img_div.get("style", "")
                        bg_match = re.search(r"background-image:\s*url\(['\"]?([^)'\"]+)['\"]?\)", style)
                        if bg_match:
                            pic = bg_match.group(1)
                
                if pic and pic.startswith("//"):
                    pic = "https:" + pic
                elif pic and pic.startswith("/"):
                    pic = self.siteUrl + pic

                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": "搜索"
                })
            except Exception:
                continue

        return {"list": videos, "page": pg, "pagecount": 999}

    # ═════════ 阵字秘 · 代理入口 ═════════
    def localProxy(self, param):
        return [404, "application/json", json.dumps({"error": "proxy not implemented"})]

    def isVideoFormat(self, url):
        return any(url.lower().endswith(ext) for ext in [".m3u8", ".mp4", ".flv", ".mkv", ".ts", ".webm"])

    def manualVideoCheck(self):
        return False