# -*- coding: utf-8 -*-
import re
import sys
import time
import urllib.parse
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    config = {
        "player": {},
        "filter": {}
    }

    header = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Referer": "https://hsck123.com/"
    }

    def __init__(self):
        self.name = "黄色仓库"
        self.host = "https://hsck123.com/"
        self.classes = self.preprocessClasses()

        # --- 搜索 token 缓存（search2 / nmefafej）---
        self._search2_token = ""
        self._search2_token_time = 0
        self._search2_token_ttl = 30 * 60  # 30分钟，可按需调整

    def getName(self):
        return self.name

    def getDynamicHost(self):
        return "https://hsck123.com/"

    def preprocessClasses(self):
        return [
            {"type_name": "国产新片", "type_id": "ycgc"},
            {"type_name": "无码中文字幕", "type_id": "wz"},
            {"type_name": "有码中文字幕", "type_id": "yz"},
            {"type_name": "日本无码", "type_id": "rw"},
            {"type_name": "日本有码", "type_id": "ry"},
            {"type_name": "国产视频", "type_id": "gc"},
            {"type_name": "欧美高清", "type_id": "om"},
            {"type_name": "动漫剧情", "type_id": "dm"}
        ]

    def init(self, extend):
        pass

    def homeContent(self, filter):
        return {"class": self.classes}

    def homeVideoContent(self):
        result = {}
        try:
            url = f"{self.host.rstrip('/')}/"
            rsp = self.fetch(url)
            root = pq(rsp.text)
            videos = self.parseVideoList(root)
            result['list'] = videos[:30]
        except:
            result['list'] = []
        return result

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        try:
            url = f"{self.host.rstrip('/')}/?type={tid}&p={pg}"
            rsp = self.fetch(url)
            root = pq(rsp.text)
            videos = self.parseVideoList(root)

            result['list'] = videos
            result['page'] = int(pg)
            result['pagecount'] = 9999
            result['limit'] = len(videos)
            result['total'] = 999999
        except:
            result['list'] = []
        return result

    # -----------------------------
    # 搜索：核心优化点
    # -----------------------------
    def _extract_search2_from_html(self, html: str) -> str:
        if not html:
            return ""

        # 1) 优先从脚本变量里提取：var nmefafej = "xxxx";
        m = re.search(r'var\s+nmefafej\s*=\s*"([^"]+)"', html)
        if m:
            return (m.group(1) or "").strip()

        # 2) 兜底：从页面中出现的 search2=xxxx 提取
        m = re.search(r'[?&]search2=([A-Za-z0-9]+)', html)
        if m:
            return (m.group(1) or "").strip()

        return ""

    def _get_search2_token(self, force_refresh=False) -> str:
        now = int(time.time())
        if (not force_refresh) and self._search2_token and (now - self._search2_token_time < self._search2_token_ttl):
            return self._search2_token

        try:
            # 抓首页（或任意列表页）提取 token
            url = f"{self.host.rstrip('/')}/"
            rsp = self.fetch(url)
            token = self._extract_search2_from_html(rsp.text)
            if token:
                self._search2_token = token
                self._search2_token_time = now
            return token
        except:
            return self._search2_token or ""

    def _extract_search_nm(self, html: str) -> str:
        """
        尝试读取页面脚本中的：var search_nm = "xxx";
        用于判断本次页面是否真正处于“搜索模式”
        """
        if not html:
            return ""
        m = re.search(r'var\s+search_nm\s*=\s*"([^"]*)"', html)
        if m:
            return (m.group(1) or "").strip()
        return ""

    def searchContent(self, key, quick, pg):
        result = {}
        key = (key or "").strip()
        if not key:
            result["list"] = []
            return result

        def _do_search(force=False):
            token = self._get_search2_token(force_refresh=force)
            if not token:
                return None, []

            q = urllib.parse.quote(key)
            # 站点脚本显示搜索分页使用 p 参数拼接到同一个URL上
            search_url = f"{self.host.rstrip('/')}/?search2={token}&search={q}&p={pg}"
            rsp = self.fetch(search_url)
            html = rsp.text or ""
            root = pq(html)
            videos = self.parseVideoList(root)

            # 校验：如果页面脚本里 search_nm 为空，可能没进入搜索模式（比如 token 失效/参数被忽略）
            search_nm = self._extract_search_nm(html)
            return search_nm, videos

        try:
            search_nm, videos = _do_search(force=False)

            # 若疑似失败（没进入搜索模式）则强制刷新 token 再试一次
            if (not search_nm) and (not videos):
                search_nm, videos = _do_search(force=True)

            result['list'] = videos
        except:
            result['list'] = []
        return result

    # -----------------------------
    # 解析列表
    # -----------------------------
    def parseVideoList(self, root):
        videos = []
        items = root('a.stui-vodlist__thumb')
        if not items:
            items = root('a[href*="view?id="]')

        for item_node in items.items():
            href = item_node.attr('href')
            if not href:
                continue

            img = item_node.attr('data-original') or item_node.attr('src')

            name = item_node.attr('title')
            if not name:
                name = item_node.text().strip()

            if not name:
                parent = item_node.parents('.stui-vodlist__box')
                if parent:
                    name = parent.find('.stui-vodlist__detail .title a').text().strip()

            if not name or len(name) < 2:
                continue

            videos.append({
                "vod_id": href,
                "vod_name": name,
                "vod_pic": self.getFullUrl(img),
                "vod_remarks": ""
            })
        return videos

    def detailContent(self, array):
        result = {}
        try:
            vid = array[0]
            url = self.getFullUrl(vid)
            rsp = self.fetch(url)
            root = pq(rsp.text)

            title = root('h1').text().strip()
            if not title:
                title = root('.title').text().strip()
            if not title:
                title = root('title').text().replace(' - 黄色仓库', '').strip()

            # 去除标题中的“目录”
            title = title.replace('目录', '').strip()

            pic = root('.stui-content__thumb img').attr('data-original') or root('.stui-content__thumb img').attr('src')

            m3u8_urls = self.extractM3U8Url(rsp.text)
            play_urls = []
            if m3u8_urls:
                for i, m3u8_url in enumerate(m3u8_urls):
                    play_urls.append(f"线路{i+1}${m3u8_url}")
            else:
                play_urls.append(f"详情页链接${url}")

            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self.getFullUrl(pic),
                "vod_content": title,
                "vod_play_from": "HSCK线路",
                "vod_play_url": "#".join(play_urls)
            }
            result['list'] = [vod]
        except:
            result['list'] = []
        return result

    def extractM3U8Url(self, html_text):
        m3u8_urls = []
        m3u8_pattern = r'https?://[^\s"\']+\.m3u8[^\s"\']*'
        matches = re.findall(m3u8_pattern, html_text or "")
        for url in matches:
            if url not in m3u8_urls:
                m3u8_urls.append(url)
        return m3u8_urls

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "header": self.header}
        if '$' in id:
            result["url"] = id.split('$', 1)[1]
        elif id.startswith('http'):
            result["url"] = id
        else:
            detail = self.detailContent([id])
            if detail.get('list'):
                url_str = detail['list'][0].get('vod_play_url', '')
                if '$' in url_str:
                    result["url"] = url_str.split('$', 1)[1]
                else:
                    result["url"] = ""
        return result

    def getFullUrl(self, url):
        if not url:
            return ""
        if url.startswith('http'):
            return url
        if url.startswith('//'):
            return f"https:{url}"
        return f"{self.host.rstrip('/')}/{url.lstrip('/')}"

    def localProxy(self, param):
        return {}
