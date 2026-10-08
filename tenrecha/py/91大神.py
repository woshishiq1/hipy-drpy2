#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
91大神.com - PyramidStore/TVBox 爬虫插件 (修复版 v1.1)
目标: https://xn--iv2-91dsvodcom-s17vt13e90o4m0gi5r.xn--91shen-cy3k.com/?fulione
修复: 增强 playerContent headers、优化封面提取、完善 localProxy
"""

import requests
import re
import sys
import os
from urllib.parse import urljoin, quote

# 兼容本地调试与 PyramidStore 环境
sys.path.append('../../')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def init(self, extend=""):
            pass


# 默认基础域名
_BACKUP_BASE_URL = "https://xn--iv2-91dsvodcom-s17vt13e90o4m0gi5r.xn--91shen-cy3k.com"

# 缓存文件名
_CACHE_FILE = "91大神site.txt"

# 每页视频数
_PAGE_SIZE = 30


class Spider(Spider):
    """PyramidStore 标准爬虫插件"""

    def __init__(self):
        self.siteUrl = _BACKUP_BASE_URL
        self.userAgent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        self.timeout = 15
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.userAgent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })

    # ==================== 动态网址解析 ====================

    def _resolve_site_url(self, default_url: str = None) -> str:
        """
        动态获取站点网址，支持本地缓存。
        """
        default_url = default_url or getattr(self, 'siteUrl', _BACKUP_BASE_URL)

        # 读取缓存
        cached_url = ""
        try:
            if os.path.exists(_CACHE_FILE):
                with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                    cached_url = f.read().strip()
        except Exception as e:
            print(f"[WARN] 读取缓存文件失败: {e}")

        # 验证缓存
        if cached_url:
            try:
                resp = self.session.head(cached_url + "/?fulione", timeout=10, allow_redirects=True)
                if resp.status_code == 200:
                    self.siteUrl = cached_url
                    return cached_url
            except Exception:
                pass

        # 使用默认
        self.siteUrl = default_url
        return default_url

    # ==================== 原有接口 ====================

    def init(self, extend=""):
        """插件初始化(框架回调)"""
        global _BACKUP_BASE_URL

        if extend and isinstance(extend, str):
            custom_urls = [u.strip() for u in extend.split(",") if u.strip().startswith("http")]
            if custom_urls:
                _BACKUP_BASE_URL = custom_urls[0]
                self.siteUrl = custom_urls[0]
                print(f"[INFO] 使用自定义域名: {self.siteUrl}")

        self._resolve_site_url()

    def getName(self):
        return "91大神"

    def fetch(self, url, headers=None):
        """统一请求方法"""
        if headers is None:
            headers = {
                "User-Agent": self.userAgent,
                "Referer": self.siteUrl + "/",
            }
        try:
            resp = self.session.get(url, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            return resp
        except Exception as e:
            print(f"[ERROR] fetch {url} failed: {e}")
            return None

    def _parse_list_page(self, html_text: str) -> list:
        """解析列表页HTML，提取视频条目"""
        videos = []
        items = re.findall(r'<li class="item">(.*?)</li>', html_text, re.S)
        for item in items:
            href_match = re.search(r'href="([^"]+)"', item)
            title_match = re.search(r'title="([^"]*)"', item)
            img_match = re.search(r"background-image:url\('([^']+)'\)", item)

            if not href_match:
                continue

            href = href_match.group(1)
            # 提取ID: content-123456.html -> 123456
            vid_match = re.search(r'content-(\d+)\.html', href)
            if not vid_match:
                continue

            vid = vid_match.group(1)
            title = title_match.group(1) if title_match else ""
            pic = img_match.group(1) if img_match else ""

            videos.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "",
            })
        return videos

    def _get_page_count(self, html_text: str, cat_id: str = "") -> int:
        """从HTML中提取总页数"""
        if cat_id and cat_id != "0":
            # 分类页: index-{cat_id}-{page}.html
            pattern = rf'href="index-{re.escape(cat_id)}-(\d+)\.html"'
            pages = re.findall(pattern, html_text)
            if pages:
                return max(int(p) for p in pages)

        # 首页或其他: ?fulione&p={page}
        pages = re.findall(r'[?&]p=(\d+)[^"]*"', html_text)
        if pages:
            return max(int(p) for p in pages)

        # 尝试通用模式 index-{page}.html (排除分类ID 0-42)
        pages = re.findall(r'href="index-(\d+)\.html"', html_text)
        if pages:
            nums = [int(p) for p in pages if int(p) > 42]
            if nums:
                return max(nums)

        return 1

    def _format_vod(self, item: dict) -> dict:
        """统一格式化为TVBox标准视频条目"""
        return {
            "vod_id": str(item.get("vod_id", "")),
            "vod_name": item.get("vod_name", ""),
            "vod_pic": item.get("vod_pic", ""),
            "vod_remarks": item.get("vod_remarks", ""),
        }

    # ==================== TVBox 标准接口 ====================

    def homeContent(self, filter):
        result = {"class": [], "filters": {}}

        # 预定义分类（从首页导航提取）
        default_classes = [
            {"type_id": "0", "type_name": "全部大神"},
            {"type_id": "1", "type_name": "仓本c仔"},
            {"type_id": "2", "type_name": "夯先生"},
            {"type_id": "3", "type_name": "秦先生"},
            {"type_id": "4", "type_name": "沙漠110"},
            {"type_id": "5", "type_name": "大闸蟹"},
            {"type_id": "6", "type_name": "JL屌哥"},
            {"type_id": "7", "type_name": "KK哥"},
            {"type_id": "8", "type_name": "轻吻也飘然"},
            {"type_id": "9", "type_name": "猫先生"},
            {"type_id": "10", "type_name": "xh98hx"},
            {"type_id": "11", "type_name": "jinx"},
            {"type_id": "12", "type_name": "呆哥"},
            {"type_id": "13", "type_name": "番薯哥"},
            {"type_id": "14", "type_name": "苍先生"},
            {"type_id": "15", "type_name": "Mr.s007"},
            {"type_id": "16", "type_name": "sweattt"},
            {"type_id": "17", "type_name": "吕布"},
            {"type_id": "18", "type_name": "啪神ben"},
            {"type_id": "19", "type_name": "康先生"},
            {"type_id": "20", "type_name": "佛爷"},
            {"type_id": "21", "type_name": "王老板"},
            {"type_id": "22", "type_name": "校长"},
            {"type_id": "23", "type_name": "大黄鸭"},
            {"type_id": "24", "type_name": "波哥"},
            {"type_id": "25", "type_name": "boss"},
            {"type_id": "26", "type_name": "小青蛙"},
            {"type_id": "27", "type_name": "混血哥"},
            {"type_id": "28", "type_name": "天堂"},
            {"type_id": "29", "type_name": "汤先生"},
            {"type_id": "30", "type_name": "夜愿哥"},
            {"type_id": "31", "type_name": "逍遥龙哥"},
            {"type_id": "32", "type_name": "椰子哥"},
            {"type_id": "33", "type_name": "内裤哥"},
            {"type_id": "34", "type_name": "洋米糕"},
            {"type_id": "35", "type_name": "沈先生"},
            {"type_id": "36", "type_name": "约约哥"},
            {"type_id": "37", "type_name": "德莱文"},
            {"type_id": "38", "type_name": "98K"},
            {"type_id": "39", "type_name": "王老吉"},
            {"type_id": "40", "type_name": "四驱兄弟"},
            {"type_id": "41", "type_name": "汝工作室"},
            {"type_id": "42", "type_name": "风月海棠"},
        ]

        # 尝试从首页获取最新分类
        resp = self.fetch(self.siteUrl + "/?fulione")
        if resp:
            cat_links = re.findall(r'href="(index-?(\d*)\.html)"[^>]*>([^<]+)</a>', resp.text)
            classes = []
            seen_ids = set()
            for link, cat_id, name in cat_links:
                cat_id = cat_id if cat_id else "0"
                if cat_id not in seen_ids:
                    seen_ids.add(cat_id)
                    classes.append({"type_id": cat_id, "type_name": name.strip()})
            if classes:
                result['class'] = classes
            else:
                result['class'] = default_classes
        else:
            result['class'] = default_classes

        if filter:
            result['filters'] = {}
        return result

    def homeVideoContent(self):
        result = {"list": []}
        resp = self.fetch(self.siteUrl + "/?fulione")
        if not resp:
            return result

        videos = self._parse_list_page(resp.text)
        result["list"] = [self._format_vod(v) for v in videos]
        return result

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": pg, "pagecount": 0, "limit": _PAGE_SIZE, "total": 0}

        if tid == "0" or not tid:
            # 全部
            if pg == 1:
                url = self.siteUrl + "/?fulione"
            else:
                url = self.siteUrl + f"/?fulione&p={pg}"
        else:
            # 分类
            if pg == 1:
                url = self.siteUrl + f"/index-{tid}.html"
            else:
                url = self.siteUrl + f"/index-{tid}-{pg}.html"

        resp = self.fetch(url)
        if not resp:
            return result

        videos = self._parse_list_page(resp.text)

        # 获取总页数
        page_count = self._get_page_count(resp.text, tid if tid != "0" else "")

        # 如果当前页没有视频但页码大于1，可能是超出范围
        if not videos and pg > 1:
            page_count = pg - 1

        result.update({
            "list": [self._format_vod(v) for v in videos],
            "page": pg,
            "pagecount": page_count,
            "limit": _PAGE_SIZE,
            "total": page_count * _PAGE_SIZE,
        })
        return result

    def detailContent(self, ids):
        result = {"list": []}
        if not ids:
            return result
        video_id = ids[0] if isinstance(ids, list) else ids

        resp = self.fetch(self.siteUrl + f"/content-{video_id}.html")
        if not resp:
            return result

        html_text = resp.text

        # 提取标题
        title_match = re.search(r'<h1>(.*?)</h1>', html_text)
        title = title_match.group(1).strip() if title_match else ""

        # 提取m3u8
        m3u8_match = re.search(r"url:\s*'([^']+\.m3u8[^']*)'", html_text)
        m3u8 = m3u8_match.group(1) if m3u8_match else ""

        # 提取封面 (优先DPlayer pic字段)
        pic = ""
        pic_match = re.search(r"pic:\s*'([^']+)'", html_text)
        if pic_match:
            pic = pic_match.group(1)

        # 备用: 从meta标签提取
        if not pic:
            pic_match = re.search(r'<meta[^>]*og:image[^>]*content="([^"]+)"', html_text, re.I)
            if pic_match:
                pic = pic_match.group(1)

        # 备用: 从页面中找任何图片
        if not pic:
            img_match = re.search(r'<img[^>]*src="([^"]+)"', html_text, re.I)
            if img_match:
                pic = img_match.group(1)

        vod = {
            "vod_id": str(video_id),
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_year": "",
            "vod_area": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": title,
            "vod_play_from": "默认",
            "vod_play_url": "",
        }

        if m3u8:
            vod["vod_play_url"] = f"播放${m3u8}"

        result["list"] = [vod]
        return result

    def searchContent(self, key, quick, pg=1):
        result = {"list": []}
        url = self.siteUrl + f"/?s={quote(key)}"
        if pg > 1:
            url += f"&p={pg}"

        resp = self.fetch(url)
        if not resp:
            return result

        videos = self._parse_list_page(resp.text)
        result["list"] = [self._format_vod(v) for v in videos]
        return result

    def searchContentPage(self, key, quick, pg=1):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags):
        result = {}
        if not id:
            return result

        # 构造完整的请求头，确保m3u8和key都能正常获取
        headers = {
            "User-Agent": self.userAgent,
            "Referer": self.siteUrl + "/",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive",
        }

        if self.isVideoFormat(id):
            result["parse"] = 0
            result["url"] = id
            result["header"] = headers
        else:
            # id 是 m3u8 直链
            result["parse"] = 0
            result["url"] = id
            result["header"] = headers
        return result

    def isVideoFormat(self, url):
        if not url or not isinstance(url, str):
            return False
        if not url.startswith("http"):
            return False
        fmt = ['.mp4', '.m3u8', '.ts', '.mkv', '.avi', '.webm', '.flv']
        for f in fmt:
            if url.lower().find(f) > -1:
                return True
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        """本地代理(处理m3u8/key/封面等)"""
        action = param.get('action')
        if action == 'proxy':
            url = param.get('url')
            proxy_headers = {
                "User-Agent": self.userAgent,
                "Referer": self.siteUrl + "/",
                "Accept": "*/*",
            }
            try:
                proxy_type = param.get('type', '')

                if proxy_type == 'cover':
                    # 封面代理 - 尝试获取，失败返回空
                    r = requests.get(url, headers=proxy_headers, timeout=10, allow_redirects=True)
                    if r.status_code == 200 and r.content:
                        content_type = r.headers.get('Content-Type', 'image/jpeg')
                        return [200, content_type, r.content]
                    return [404, "text/plain", "cover not found"]

                elif proxy_type == 'm3u8':
                    # m3u8代理 - 透传内容并修复相对路径
                    r = requests.get(url, headers=proxy_headers, timeout=10)
                    content = r.text
                    # 如果m3u8内容包含相对路径的key或ts，可能需要处理
                    return [200, "application/vnd.apple.mpegurl", content]

                elif proxy_type == 'media':
                    # 媒体片段代理
                    r = requests.get(url, headers=proxy_headers, stream=True, timeout=10)
                    return [206, "application/octet-stream", r.content]

                else:
                    # 默认透传
                    r = requests.get(url, headers=proxy_headers, timeout=10)
                    content_type = r.headers.get('Content-Type', 'text/plain')
                    return [200, content_type, r.content]

            except Exception as e:
                print(f"[ERROR] localProxy failed: {e}")
                return [500, "text/plain", str(e)]
        return None
