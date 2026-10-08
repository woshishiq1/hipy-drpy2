# -*- coding: utf-8 -*-
# HuoPorn福利视频 (https://www.huoporn.lol) TVBox Spider
# 适配 Vue 动态渲染站 · 基于 URL 路由规律

import sys
import re
import json
import base64
import urllib.parse
from html import unescape

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider: pass

import requests

class Spider(BaseSpider):

    def init(self, extend=""):
        self.host = "https://www.huoporn.lol"
        if extend and extend.startswith("http"):
            self.host = extend.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        # 分类映射（从导航栏提取）
        self.categories = {
            "1": "国产",
            "2": "传媒",
            "3": "网红",
            "4": "大秀",
            "5": "探花",
            "6": "反差",
            "7": "颜值",
            "8": "中文",
            "9": "无码",
            "10": "日韩",
            "11": "欧美",
            "12": "动漫",
            "13": "人妻",
            "14": "制服",
            "15": "乱伦",
            "16": "明星",
            "17": "自拍",
            "18": "三级",
            "20": "师生",
        }

    def getName(self):
        return "HuoPorn"

    def isVideoFormat(self, url):
        return url and any(ext in url for ext in [".m3u8", ".mp4", ".flv", ".ts"])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self.session:
            self.session.close()

    # ---------- 工具 ----------
    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        if not url.startswith("http"):
            return self.host + "/" + url
        return url

    def _clean(self, text):
        if not text:
            return ""
        text = re.sub(r"<[^>]+>", "", text)
        text = unescape(text)
        text = text.replace("&nbsp;", " ").replace("\xa0", " ")
        return re.sub(r"\s+", " ", text).strip()

    def _fetch(self, url, data=None, timeout=15):
        try:
            if data:
                resp = self.session.post(url, data=data, timeout=timeout)
            else:
                resp = self.session.get(url, timeout=timeout)
            resp.encoding = "utf-8"
            return resp.text
        except Exception as e:
            print(f"[HuoPorn] 请求失败: {url} -> {e}")
            return ""

    def _extract_video_id(self, url):
        """从播放页 URL 提取视频 ID"""
        m = re.search(r'/play/id/(\d+)', url)
        if m:
            return m.group(1)
        m = re.search(r'/vod/play/id/(\d+)', url)
        if m:
            return m.group(1)
        return None

    # ---------- 首页 ----------
    def homeContent(self, filter=False):
        return {"class": [{"type_id": tid, "type_name": name} for tid, name in self.categories.items()]}

    def homeVideoContent(self):
        # 首页取热门推荐（分类1的第一页）
        return self.categoryContent("1", "1", False, {})

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        tid = str(tid)
        # 分类列表页 URL 格式：/index.php/vod/type/id/{tid}.html
        # 分页：/index.php/vod/type/id/{tid}/page/{pg}.html
        if pg == 1:
            url = f"{self.host}/index.php/vod/type/id/{tid}.html"
        else:
            url = f"{self.host}/index.php/vod/type/id/{tid}/page/{pg}.html"
        html = self._fetch(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}

        videos = self._parse_video_list(html)
        # 分页总数（从页面提取）
        pagecount = self._extract_page_count(html) or (pg + 1 if len(videos) >= 20 else pg)

        return {
            "list": videos,
            "page": pg,
            "pagecount": max(pagecount, pg),
            "limit": len(videos),
            "total": max(pagecount, pg) * len(videos) if videos else 0
        }

    def _parse_video_list(self, html):
        """解析视频列表（从 Vue 渲染后的 HTML 中提取）"""
        videos = []
        seen = set()
        # 匹配视频卡片：<a href="/index.php/vod/play/id/XXX/sid/1/nid/1.html">
        # 包含图片和标题
        pattern = r'<a[^>]+href="(/index\.php/vod/play/id/(\d+)/sid/\d+/nid/\d+\.html)"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]*>.*?<h3[^>]*class="[^"]*video-item__title[^"]*"[^>]*>(.*?)</h3>'
        for m in re.finditer(pattern, html, re.S):
            href = m.group(1)
            vid = m.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            pic = self._fix_url(m.group(3))
            title = self._clean(m.group(4))
            # 提取分类标签（span.video-item__duration）
            tag_match = re.search(r'<span[^>]*class="[^"]*video-item__duration[^"]*"[^>]*>([^<]*)</span>', m.group(0), re.S)
            remark = self._clean(tag_match.group(1)) if tag_match else ""
            videos.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark
            })
        # 备用：简化匹配
        if not videos:
            for a in re.finditer(r'<a[^>]+href="(/index\.php/vod/play/id/(\d+)[^"]+)"[^>]*>', html, re.S):
                vid = a.group(2)
                if vid in seen:
                    continue
                seen.add(vid)
                # 找图片
                img = re.search(r'<img[^>]+src="([^"]+)"', a.group(0), re.S)
                pic = self._fix_url(img.group(1)) if img else ""
                # 找标题
                title_match = re.search(r'<h3[^>]*>(.*?)</h3>', a.group(0), re.S)
                title = self._clean(title_match.group(1)) if title_match else f"视频{vid}"
                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        return videos

    def _extract_page_count(self, html):
        """从分页链接中提取总页数"""
        # 匹配尾页链接
        last = re.search(r'<a[^>]+href="[^"]*?/page/(\d+)\.html"[^>]*>尾页</a>', html)
        if last:
            return int(last.group(1))
        # 匹配所有页码
        nums = re.findall(r'/page/(\d+)\.html', html)
        if nums:
            return max(int(n) for n in nums)
        return None

    # ---------- 搜索 ----------
    def searchContent(self, key, quick=False, pg="1"):
        key = key.strip()
        if not key:
            return {"list": [], "page": 1}
        pg = int(pg) if pg else 1
        enc_key = urllib.parse.quote(key)
        # 搜索 URL：/index.php/vod/search.html?wd=关键词
        url = f"{self.host}/index.php/vod/search.html?wd={enc_key}"
        if pg > 1:
            url += f"&page={pg}"
        html = self._fetch(url)
        if not html:
            return {"list": [], "page": pg}
        videos = self._parse_video_list(html)
        return {"list": videos, "page": pg}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids).strip()
        # 详情页 URL（实际就是播放页）
        url = f"{self.host}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 标题
        title = ""
        h1 = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if h1:
            title = self._clean(h1.group(1))
        if not title:
            meta = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html)
            if meta:
                title = self._clean(meta.group(1))
        if not title:
            title = f"视频{vid}"

        # 封面
        pic = ""
        img = re.search(r'<img[^>]+src="([^"]+)"[^>]*class="[^"]*video-item__image[^"]*"', html)
        if img:
            pic = self._fix_url(img.group(1))
        if not pic:
            meta_pic = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
            if meta_pic:
                pic = self._fix_url(meta_pic.group(1))

        # 简介
        desc = ""
        desc_meta = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html)
        if desc_meta:
            desc = self._clean(desc_meta.group(1))

        # ========== 播放地址提取 ==========
        # 该站视频播放地址通常在 player_aaaa 中
        play_url = ""
        player_script = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*;', html, re.S)
        if player_script:
            try:
                data = json.loads(player_script.group(1))
                url = data.get("url", "")
                enc = data.get("encrypt", 0)
                if enc == 1:
                    url = urllib.parse.unquote(url)
                elif enc == 2:
                    try:
                        url = base64.b64decode(url).decode('utf-8')
                    except:
                        pass
                if url:
                    play_url = url
            except:
                pass

        # 如果没有 player_aaaa，尝试直接匹配 m3u8
        if not play_url:
            m3u8 = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
            if m3u8:
                play_url = m3u8.group(1)

        # 如果还是没有，尝试 video 标签
        if not play_url:
            video = re.search(r'<video[^>]+src="([^"]+)"', html)
            if video:
                play_url = self._fix_url(video.group(1))

        if play_url:
            play_from = "播放"
            play_urls = f"正片${play_url}"
        else:
            play_from = "详情页"
            play_urls = f"正片${url}"

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": play_from,
            "vod_play_url": play_urls,
        }
        return {"list": [vod]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {"parse": 1, "url": "", "header": {}}
        if self.isVideoFormat(id):
            return {"parse": 0, "url": id, "header": {"User-Agent": self.session.headers["User-Agent"], "Referer": self.host + "/"}}
        # 如果是播放页 URL，尝试提取
        url = id if id.startswith("http") else self._fix_url(id)
        html = self._fetch(url)
        if not html:
            return {"parse": 1, "url": url, "header": {}}

        # player_aaaa
        player_script = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*;', html, re.S)
        if player_script:
            try:
                data = json.loads(player_script.group(1))
                play_url = data.get("url", "")
                enc = data.get("encrypt", 0)
                if enc == 1:
                    play_url = urllib.parse.unquote(play_url)
                elif enc == 2:
                    try:
                        play_url = base64.b64decode(play_url).decode('utf-8')
                    except:
                        pass
                if play_url and self.isVideoFormat(play_url):
                    return {"parse": 0, "url": play_url, "header": {"User-Agent": self.session.headers["User-Agent"], "Referer": self.host + "/"}}
            except:
                pass

        # player_data
        player_data = re.search(r'var\s+player_data\s*=\s*(\{.*?\})\s*;', html, re.S)
        if player_data:
            try:
                data = json.loads(player_data.group(1))
                play_url = data.get("url", "")
                if play_url and self.isVideoFormat(play_url):
                    return {"parse": 0, "url": play_url, "header": {"User-Agent": self.session.headers["User-Agent"], "Referer": self.host + "/"}}
            except:
                pass

        # var now
        now = re.search(r'var\s+now\s*=\s*["\']([^"\']+)["\']', html)
        if now:
            play_url = self._fix_url(now.group(1))
            if self.isVideoFormat(play_url):
                return {"parse": 0, "url": play_url, "header": {"User-Agent": self.session.headers["User-Agent"], "Referer": self.host + "/"}}

        # iframe
        iframe = re.search(r'<iframe[^>]+src="([^"]+)"', html)
        if iframe:
            iframe_url = self._fix_url(iframe.group(1))
            return self.playerContent(flag, iframe_url, vipFlags)

        # 直链
        direct = re.search(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*)', html)
        if direct:
            return {"parse": 0, "url": direct.group(1), "header": {"User-Agent": self.session.headers["User-Agent"], "Referer": self.host + "/"}}

        return {"parse": 1, "url": url, "header": {}}

    def localProxy(self, param):
        return [404, "text/plain", ""]