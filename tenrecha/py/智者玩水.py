# -*- coding: utf-8 -*-
# @File    : 智者玩水.py
# @Site    : https://www.zhizhewanshui.shop

import sys
import json
import re
import urllib.parse
from lxml import etree

sys.path.append("..")
from base.spider import Spider


class Spider(Spider):
    def __init__(self):
        self.siteUrl = "https://www.zhizhewanshui.shop"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": self.siteUrl
        }
        self.categories = [
            {"type_id": "1", "type_name": "在线国产"},
            {"type_id": "6", "type_name": "传媒剧情"},
            {"type_id": "7", "type_name": "国产主播"},
            {"type_id": "8", "type_name": "国产明星"},
            {"type_id": "9", "type_name": "抖阴视频"},
            {"type_id": "10", "type_name": "网爆黑料"},
            {"type_id": "11", "type_name": "网红头条"},
            {"type_id": "12", "type_name": "萝莉少女"},
            {"type_id": "13", "type_name": "欧美无码"},
            {"type_id": "14", "type_name": "日本无码"},
            {"type_id": "15", "type_name": "制服诱惑"},
            {"type_id": "16", "type_name": "强奸乱伦"}
        ]

    def getName(self):
        return "智者玩水"

    def init(self, extend=""):
        try:
            ext = json.loads(extend) if extend else {}
            if isinstance(ext, dict):
                if ext.get("host"):
                    self.siteUrl = ext["host"]
                if ext.get("userAgent"):
                    self.headers["User-Agent"] = ext["userAgent"]
                if ext.get("cookie"):
                    self.headers["Cookie"] = ext["cookie"]
                if ext.get("referer"):
                    self.headers["Referer"] = ext["referer"]
        except Exception:
            pass
        return

    def isVideoFormat(self, url):
        if not url:
            return False
        url = url.lower()
        video_exts = [".m3u8", ".mp4", ".flv", ".avi", ".mkv", ".ts", ".mov", ".wmv"]
        return any(url.endswith(ext) or (ext + "?") in url for ext in video_exts)

    def manualVideoCheck(self):
        return False

    def _request(self, url, headers=None, method="get", data=None):
        import requests
        h = dict(self.headers)
        if headers:
            h.update(headers)
        try:
            if method.lower() == "post":
                resp = requests.post(url, headers=h, data=data, timeout=15, verify=False)
            else:
                resp = requests.get(url, headers=h, timeout=15, verify=False)
            resp.encoding = "utf-8"
            return resp
        except Exception as e:
            print(f"[遮天] 请求失败: {url} -> {e}")
            return None

    def _abs(self, path):
        if not path:
            return ""
        if path.startswith("http"):
            return path
        if path.startswith("//"):
            return "https:" + path
        return self.siteUrl + (path if path.startswith("/") else "/" + path)

    def _vid(self, url):
        if not url:
            return None
        m = re.search(r"/detail/id/(\d+)", url)
        return m.group(1) if m else None

    def _extractImage(self, element):
        if element is None:
            return ""
        for attr in ["data-original", "data-src", "original-src", "src", "data-url"]:
            val = element.get(attr, "")
            if val and val.strip() and not val.startswith("data:"):
                return self._abs(val.strip())
        style = element.get("style", "")
        bg_match = re.search(r'url\((["\']?)([^"\')]+)\1\)', style)
        if bg_match:
            return self._abs(bg_match.group(2))
        return ""

    def homeContent(self, filter):
        result = {}
        classes = []
        for c in self.categories:
            classes.append({
                "type_id": c["type_id"],
                "type_name": c["type_name"]
            })
        result["class"] = classes
        result["filters"] = {}
        resp = self._request(self.siteUrl + "/")
        if resp:
            tree = etree.HTML(resp.text)
            videos = self._parseList(tree)
            result["list"] = videos
        return result

    def homeVideoContent(self):
        resp = self._request(self.siteUrl + "/")
        if resp:
            tree = etree.HTML(resp.text)
            return {"list": self._parseList(tree)}
        return {"list": []}

    def _parseList(self, tree):
        videos = []
        seen = set()
        lis = tree.xpath('//ul[@class="img-list-data"]//li')
        if not lis:
            lis = tree.xpath('//a[contains(@href,"/detail/id/")]')
            for a in lis:
                href = a.get("href", "")
                vid = self._vid(href)
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                container = a
                parent = a.getparent()
                while parent is not None and parent.tag not in ("li", "div"):
                    parent = parent.getparent()
                if parent is not None:
                    container = parent
                img = a.xpath('.//img')
                if not img:
                    img = container.xpath('.//img')
                poster = self._extractImage(img[0]) if img else ""
                title = a.get("title", "")
                if not title:
                    title = "".join(container.xpath('.//h3//text() | .//*[@class="title"]//text() | .//*[@class="name"]//text()')).strip()
                if not title:
                    title = "".join(a.xpath('.//text()')).strip()
                if title:
                    videos.append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": poster,
                        "vod_remarks": ""
                    })
            return videos
        for li in lis:
            a = li.xpath('.//a[contains(@href,"/detail/id/")]')
            if not a:
                continue
            a = a[0]
            href = a.get("href", "")
            vid = self._vid(href)
            if not vid or vid in seen:
                continue
            seen.add(vid)
            img = li.xpath('.//img')
            poster = self._extractImage(img[0]) if img else ""
            title = a.get("title", "")
            if not title:
                title = "".join(li.xpath('.//h3[@class="text-ellipsis"]//text()')).strip()
            if not title:
                title = "".join(li.xpath('.//h3//text() | .//*[@class="title"]//text() | .//*[@class="name"]//text()')).strip()
            if title:
                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": poster,
                    "vod_remarks": ""
                })
        return videos

    def categoryContent(self, tid, pg, filter, extend):
        if not pg or str(pg) == "0":
            pg = 1
        pg = int(pg)
        if pg == 1:
            url = f"{self.siteUrl}/index.php/vod/type/id/{tid}.html"
        else:
            url = f"{self.siteUrl}/index.php/vod/type/id/{tid}/page/{pg}.html"
        resp = self._request(url)
        if not resp:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 30, "total": 0}
        tree = etree.HTML(resp.text)
        videos = self._parseList(tree)
        pagecount = 999
        total_match = re.search(r"共(\d+)条数据", resp.text)
        if total_match:
            total = int(total_match.group(1))
            pagecount = (total + 29) // 30
        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": 30,
            "total": int(total_match.group(1)) if total_match else len(videos)
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0]).split(":")[-1] if ":" in str(ids[0]) else str(ids[0])
        url = f"{self.siteUrl}/index.php/vod/detail/id/{vid}.html"
        resp = self._request(url)
        if not resp:
            return {"list": []}
        tree = etree.HTML(resp.text)
        title_el = tree.xpath('//h2[@class="c_pink text-ellipsis"]')
        title = title_el[0].text.strip() if title_el and title_el[0].text else ""
        if not title:
            title = "".join(tree.xpath('//h1//text()')).strip()
        if not title:
            title = "".join(tree.xpath('//*[@class="title"]//text()')).strip()
        poster = ""
        img_els = tree.xpath('//img[@class="lazy"]')
        for img in img_els:
            poster = self._extractImage(img)
            if poster:
                break
        if not poster:
            for sel in ['//div[contains(@class,"thumb")]//img', '//div[contains(@class,"pic")]//img', '//div[contains(@class,"poster")]//img']:
                img = tree.xpath(sel)
                if img:
                    poster = self._extractImage(img[0])
                    if poster:
                        break
        desc = ""
        for cls in ["desc", "sketch", "vod-content", "stui-content__desc", "hl-content-text", "detail-info", "content-text"]:
            els = tree.xpath(f'//*[contains(@class,"{cls}")]//text()')
            if els:
                desc = " ".join(e.strip() for e in els if e.strip())
                if desc:
                    break
        play_links = tree.xpath("//a[contains(@href,'/play/')]")
        play_from = []
        play_url = []
        for pl in play_links:
            p_name = pl.get("title", "") or pl.text or "线路一"
            p_href = pl.get("href", "")
            if p_href:
                play_from.append(p_name)
                play_url.append(f"{p_name}${self._abs(p_href)}")
        if not play_from:
            play_from = ["线路一"]
            play_url = [f"线路一${self.siteUrl}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"]
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": poster,
            "vod_content": desc,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "#".join(play_url)
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": ""}
        url = id if id.startswith("http") else self._abs(id)
        resp = self._request(url)
        if not resp:
            return {"parse": 0, "url": "", "header": ""}
        html = resp.text
        play_url = ""
        m = re.search(r'var\s+player_aaaa\s*=\s*({[\s\S]*?})\s*</script>', html)
        if m:
            try:
                obj = json.loads(m.group(1).strip())
                if obj.get("url"):
                    play_url = obj["url"]
                    enc = obj.get("encrypt", 0)
                    if enc == 1:
                        try:
                            import base64
                            play_url = base64.b64decode(play_url).decode("utf-8")
                        except Exception:
                            pass
                    elif enc == 2:
                        try:
                            play_url = urllib.parse.unquote(play_url)
                        except Exception:
                            pass
            except Exception:
                pass
        if not play_url:
            m = re.search(r'var\s+player_data\s*=\s*({[\s\S]*?})\s*</script>', html)
            if m:
                try:
                    obj = json.loads(m.group(1).strip())
                    if obj.get("url"):
                        play_url = obj["url"]
                except Exception:
                    pass
        if not play_url:
            m = re.search(r'MacPlayer\.PlayUrl\s*=\s*["\']([^"\']+)["\']', html)
            if m:
                play_url = m.group(1)
                if re.match(r'^[A-Za-z0-9+/=]+$', play_url) and len(play_url) % 4 == 0:
                    try:
                        import base64
                        play_url = base64.b64decode(play_url).decode("utf-8")
                    except Exception:
                        pass
        if not play_url:
            m = re.search(r'(https?://[^"\'\s]+\.m3u8(?:\?[^"\'\s]*)?)', html)
            if m:
                play_url = m.group(1)
        if play_url:
            play_url = play_url.replace("\\/", "/")
        sub_url = ""
        if play_url and play_url.endswith("/index.m3u8"):
            sub_url = play_url.replace("/index.m3u8", "/2000kb/hls/index.m3u8")
        final_url = sub_url or play_url
        header = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": self.siteUrl,
            "Origin": self.siteUrl
        }
        return {
            "parse": 0,
            "url": final_url,
            "header": header,
            "jx": 0
        }

    def searchContent(self, key, quick, pg="1"):
        if not pg or str(pg) == "0":
            pg = 1
        pg = int(pg)
        if pg == 1:
            url = f"{self.siteUrl}/index.php/vod/search.html?wd={urllib.parse.quote(key)}"
        else:
            url = f"{self.siteUrl}/index.php/vod/search/page/{pg}/wd/{urllib.parse.quote(key)}.html"
        resp = self._request(url)
        if not resp:
            return {"list": []}
        tree = etree.HTML(resp.text)
        videos = self._parseList(tree)
        return {"list": videos}

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]
