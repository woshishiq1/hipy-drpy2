import re
import json
from urllib.parse import quote, urljoin, unquote

import requests

try:
    from base.spider import Spider
except Exception:
    class Spider:  # 兼容本地查看
        pass


class Spider(Spider):
    def getName(self):
        return "夜色"

    def init(self, extend=""):
        self.host = "https://yese.co"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        }
        self.timeout = 10
        self.classes = [
            {"type_name": "亚洲情色", "type_id": "亚洲情色"},
            {"type_name": "中文字幕", "type_id": "中文字幕"},
            {"type_name": "国产主播", "type_id": "国产主播"},
            {"type_name": "国产自拍", "type_id": "国产自拍"},
            {"type_name": "无码专区", "type_id": "无码专区"},
            {"type_name": "欧美性爱", "type_id": "欧美性爱"},
            {"type_name": "熟女人妻", "type_id": "熟女人妻"},
            {"type_name": "强奸乱伦", "type_id": "强奸乱伦"},
            {"type_name": "巨乳美乳", "type_id": "巨乳美乳"},
            {"type_name": "制服诱惑", "type_id": "制服诱惑"},
            {"type_name": "女同性恋", "type_id": "女同性恋"},
            {"type_name": "卡通动画", "type_id": "卡通动画"},
            {"type_name": "丝袜长腿", "type_id": "丝袜长腿"},
            {"type_name": "少女萝莉", "type_id": "少女萝莉"},
            {"type_name": "重口色情", "type_id": "重口色情"},
        ]

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return True

    def fetch(self, url, **kwargs):
        return requests.get(
            url,
            headers=self.headers,
            timeout=self.timeout,
            verify=False,
            **kwargs
        )

    def cleanText(self, text):
        if not text:
            return ""
        text = re.sub(r"<.*?>", "", text, flags=re.S)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def homeContent(self, filter):
        result = {}
        result["class"] = self.classes
        result["filters"] = {}
        return result

    def homeVideoContent(self):
        return self.categoryContent("", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if str(pg).isdigit() else 1
        if tid:
            url = f"{self.host}/vod/show/class/{quote(tid)}/id/1/page/{page}/"
        else:
            url = f"{self.host}/vod/show/id/1/page/{page}/"

        html = self.fetch(url).text

        pattern = re.compile(
            r'<a href="(/vod/play/id/(\d+)/sid/\d+/nid/\d+/)">\s*'
            r'<img[^>]+src="([^"]+)"[^>]+title="([^"]+)"',
            re.S
        )
        matches = pattern.findall(html)

        videos = []
        seen = set()
        for play_path, vod_id, pic, name in matches:
            if vod_id in seen:
                continue
            seen.add(vod_id)
            videos.append({
                "vod_id": vod_id,
                "vod_name": self.cleanText(name),
                "vod_pic": pic,
                "vod_remarks": ""
            })

        pagecount = page + 1 if '下一页' in html else page
        result = {
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
            "list": videos
        }
        return result

    def detailContent(self, ids):
        vod_id = ids[0]
        url = f"{self.host}/vod/detail/id/{vod_id}/"
        html = self.fetch(url).text

        name = ""
        pic = ""
        remarks = ""
        content = ""
        type_name = ""

        m = re.search(r'<h1[^>]*class="title"[^>]*>(.*?)</h1>', html, re.S)
        if m:
            name = self.cleanText(m.group(1))

        m = re.search(r'data-original="([^"]+)"', html, re.S)
        if not m:
            m = re.search(r'<img[^>]+src="([^"]+)"[^>]+data-original=', html, re.S)
        if m:
            pic = m.group(1)

        m = re.search(r'更新：\s*</span>\s*([^<]+)', html, re.S)
        if m:
            remarks = self.cleanText(m.group(1))

        m = re.search(r'●分類\s*:\s*<a[^>]*>(.*?)</a>', html, re.S)
        if m:
            type_name = self.cleanText(m.group(1))

        m = re.search(
            r'<span class="data"[^>]*>(.*?)</span>',
            html,
            re.S
        )
        if m:
            content = self.cleanText(m.group(1))
        if not content:
            content = name

        play_list = re.findall(
            r'<li[^>]*class="[^"]*col-lg-10[^"]*"[^>]*>\s*<a[^>]+href="(/vod/play/id/\d+/sid/\d+/nid/\d+/)"[^>]*>(.*?)</a>',
            html,
            re.S
        )
        if not play_list:
            play_list = re.findall(
                r'<a[^>]+class="btn btn-default"[^>]+href="(/vod/play/id/\d+/sid/\d+/nid/\d+/)"[^>]*>(.*?)</a>',
                html,
                re.S
            )

        play_urls = []
        for href, title in play_list:
            ep_name = self.cleanText(title) or "播放"
            play_urls.append(f"{ep_name}${urljoin(self.host, href)}")

        if not play_urls:
            play_urls = [f"播放${self.host}/vod/play/id/{vod_id}/sid/1/nid/1/"]

        vod = {
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "type_name": type_name,
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": remarks,
            "vod_actor": "",
            "vod_director": "",
            "vod_content": content,
            "vod_play_from": "夜色",
            "vod_play_url": "#".join(play_urls)
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() else 1
        api = f"{self.host}/index.php/ajax/suggest?mid=1&wd={quote(key)}&page={page}"
        data = self.fetch(api).json()
        videos = []
        for item in data.get("list", []):
            videos.append({
                "vod_id": str(item.get("id", "")),
                "vod_name": item.get("name", ""),
                "vod_pic": item.get("pic", ""),
                "vod_remarks": ""
            })
        return {"list": videos}

    def playerContent(self, flag, id, vipFlags):
        play_url = id
        try:
            # 请求播放页面获取网页源码
            res = self.fetch(id)
            html = res.text

            # 方案 1：匹配苹果 CMS 标准的 player_aac / player_aaaa 播放配置对象
            m = re.search(r'var\s+player_aa\w*\s*=\s*(\{.*?\});', html, re.S)
            if m:
                player_info = json.loads(m.group(1))
                raw_url = player_info.get("url", "")
                if raw_url:
                    play_url = unquote(raw_url)

            # 方案 2：如果提取到的不是 .m3u8/HTTP 格式，或是动态 URL，正则全页匹配直连地址
            if not play_url.startswith("http") or ".m3u8" not in play_url:
                m_m3u8 = re.search(r'(https?://[^\'\"]+\.m3u8[^\'\"]*)', html)
                if m_m3u8:
                    play_url = m_m3u8.group(1)

            # 修正 URL 中的转义斜杠
            play_url = play_url.replace("\\/", "/")

            return {
                "parse": 0,  # 设为 0 直接交由内置播放器播放 m3u8
                "playUrl": "",
                "url": play_url,
                "header": json.dumps(self.headers)
            }
        except Exception:
            return {
                "parse": 0,
                "playUrl": "",
                "url": id,
                "header": json.dumps(self.headers)
            }

    def localProxy(self, params):
        return [200, "video/MP2T", ""]
