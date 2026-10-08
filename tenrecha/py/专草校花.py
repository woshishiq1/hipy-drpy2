# -*- coding: utf-8 -*-
#!/usr/bin/python
# 遮天法·极道帝兵·专草校花修复版
# 修复: 列表标题提取 + 详情页简介补充
import sys, re, json, base64, html
from urllib.parse import quote, unquote, urljoin, urlparse
try:
    from lxml import etree
except ImportError:
    etree = None
try:
    import requests
except ImportError:
    requests = None
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): pass
        def homeContent(self, filter): pass
        def homeVideoContent(self): pass
        def categoryContent(self, tid, pg, filter, extend): pass
        def detailContent(self, ids): pass
        def playerContent(self, flag, id, vipFlags=None): pass
        def searchContent(self, key, quick, pg="1"): pass
        def isVideoFormat(self, url): pass
        def manualVideoCheck(self): pass
        def localProxy(self, param): pass

def fix_url(url, host):
    if not url: return ""
    if url.startswith("//"): return "https:" + url
    if url.startswith("/"): return urljoin(host, url)
    if url.startswith("http"): return url
    return urljoin(host, "/" + url)

def clean_text(text):
    if not text: return ""
    return html.unescape(re.sub(r"<[^>]+>", "", str(text))).strip()

def extract_play(html_text, host):
    # 13层深度提取
    m = re.search(r"(https?://[^\s\"'<>]+\.m3u8[^\s\"'<>]*)", html_text)
    if m: return m.group(1)
    m = re.search(r"(https?://[^\s\"'<>]+\.mp4[^\s\"'<>]*)", html_text)
    if m: return m.group(1)
    m = re.search(r"var\s+now\s*=\s*['\"]([^'\"]+)['\"]", html_text)
    if m: return m.group(1)
    m = re.search(r"player_data\s*=\s*(\{.*?\})", html_text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1)).get("url", "")
        except: pass
    m = re.search(r"var\s+player_aaaa\s*=\s*(\{.*?\})", html_text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1)).get("url", "")
        except: pass
    m = re.search(r"<iframe[^>]+src\s*=\s*['\"]([^'\"]+)['\"]", html_text)
    if m:
        iframe = fix_url(m.group(1), host)
        try:
            r = requests.get(iframe, headers={"User-Agent":"Mozilla/5.0","Referer":host}, timeout=10, verify=False)
            if r: return extract_play(r.text, host)
        except: pass
    m = re.search(r"videoSources\s*:\s*(\[.*?\])", html_text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1))[0].get("file", "")
        except: pass
    m = re.search(r"wvPlayer\.play\s*\(\s*['\"]([^'\"]+)['\"]", html_text)
    if m: return m.group(1)
    m = re.search(r"url\s*:\s*['\"]([^'\"]+\.m3u8)['\"]", html_text)
    if m: return m.group(1)
    m = re.search(r"var\s+playurl\s*=\s*['\"]([^'\"]+)['\"]", html_text)
    if m: return m.group(1)
    m = re.search(r"eval\((.*?)\)", html_text, re.DOTALL)
    if m: return "eval_encrypted"
    return ""

def extract_content(html_text):
    # 简介提取
    for pat in [
        r"<div[^>]+class=['\"][^'\"]*(?:content|description|intro|summary|plot)[^'\"]*['\"][^>]*>([\s\S]*?)</div>",
        r"<p[^>]+class=['\"][^'\"]*(?:content|description|intro|summary)[^'\"]*['\"][^>]*>([\s\S]*?)</p>",
        r"<section[^>]*>([\s\S]*?)</section>",
    ]:
        m = re.search(pat, html_text, re.I)
        if m:
            txt = clean_text(m.group(1))
            if len(txt) > 10: return txt
    m = re.search(r"<meta[^>]+name=['\"]description['\"][^>]+content=['\"]([^'\"]+)['\"]", html_text, re.I)
    if m: return clean_text(m.group(1))
    m = re.search(r"<meta[^>]+content=['\"]([^'\"]+)['\"][^>]+name=['\"]description['\"]", html_text, re.I)
    if m: return clean_text(m.group(1))
    texts = re.findall(r"<p[^>]*>([^<]{30,})</p>", html_text)
    if texts: return clean_text(texts[0])
    return ""

class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = "https://172608.zzxiaohua1.top"
        self.name = "专草校花"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
            "sec-ch-ua": "Not_A Brand;v=8, Chromium;v=120",
            "Upgrade-Insecure-Requests": "1"
        }
        self.s = requests.Session() if requests else None
        if self.s: self.s.headers.update(self.headers)

    def init(self, extend=""): pass
    def getName(self): return self.name
    def isVideoFormat(self, url): return any(x in url for x in [".m3u8", ".mp4", ".flv", ".ts"])
    def manualVideoCheck(self): return False
    def localProxy(self, param): return [200, "video/MP2T", b"", {}]

    def _fetch(self, url):
        if not self.s: return ""
        try:
            r = self.s.get(url, timeout=15, headers=self.headers, verify=False)
            r.raise_for_status()
            r.encoding = "utf-8"
            return r.text
        except Exception as e:
            print(f"[{self.name}] 请求失败: {url} - {e}")
            return ""

    def _parse_list(self, doc):
        videos = []
        if not doc: return videos
        items = doc.xpath('//div[@id="list_videos_videos_watched_right_now_items"]/div[contains(@class,"item")]')
        if not items:
            items = doc.xpath('//div[contains(@class,"item")]')
        seen = set()
        for item in items:
            try:
                hrefs = item.xpath('.//a[contains(@href,"/player/")]/@href')
                if not hrefs: continue
                href = hrefs[0]
                if href in seen: continue
                seen.add(href)
                title = ""
                tnodes = item.xpath('.//a[contains(@class,"font-bold")]/text()')
                if tnodes:
                    title = clean_text(tnodes[0])
                else:
                    for a_text in item.xpath('.//a[contains(@href,"/player/")]//text()'):
                        txt = clean_text(a_text)
                        if txt and not txt.startswith("http") and len(txt) > 3:
                            title = txt
                            break
                pic = ""
                pnodes = item.xpath('.//img/@data-original')
                if not pnodes:
                    pnodes = item.xpath('.//img/@src')
                if pnodes:
                    pic = fix_url(pnodes[0], self.host)
                remark = ""
                rnodes = item.xpath('.//div[contains(@class,"text-xs")]//text()')
                if rnodes: remark = clean_text(rnodes[0])
                videos.append({
                    "vod_id": href,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark
                })
            except Exception as e:
                print(f"[{self.name}] 单条解析失败: {e}")
                continue
        return videos

    def homeContent(self, filter):
        classes = [
            {"type_name": "日韩", "type_id": "1"},
            {"type_name": "国产", "type_id": "2"},
            {"type_name": "欧美", "type_id": "3"},
            {"type_name": "动漫", "type_id": "4"}
        ]
        return {"class": classes, "filters": {}}

    def homeVideoContent(self):
        return self.categoryContent("1", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
        try:
            url = f"{self.host}/list.php?cid={tid}&page={pg}"
            html_text = self._fetch(url)
            if not html_text: return result
            doc = etree.HTML(html_text) if etree else None
            result["list"] = self._parse_list(doc)
            result["pagecount"] = int(pg) + 1 if len(result["list"]) >= 24 else int(pg)
            pm = re.search(r"(?:page|pg)[/=]\s*(\d+)", html_text, re.I) or re.search(r"共\s*(\d+)\s*页", html_text)
            if pm: result["pagecount"] = int(pm.group(1))
            return result
        except Exception as e:
            print(f"[{self.name}] 分类失败: {e}")
            return result

    def detailContent(self, ids):
        result = {"list": []}
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            url = fix_url(vid, self.host)
            html_text = self._fetch(url)
            if not html_text: return result
            doc = etree.HTML(html_text) if etree else None
            title = ""
            if doc:
                title = doc.xpath("//h1/text()")
                if title: title = clean_text(title[0])
            if not title:
                m = re.search(r"<title>([^<]+)</title>", html_text)
                if m: title = clean_text(m.group(1).split("-")[0])
            if not title: title = vid
            pic = ""
            if doc:
                pic = doc.xpath('//img[contains(@class,"thumb") or contains(@class,"poster") or contains(@class,"cover")]/@src') or doc.xpath('//img[contains(@class,"thumb")]/@data-original')
                if pic: pic = fix_url(pic[0], self.host)
            if not pic:
                m = re.search(r"<img[^>]+src=['\"](https?://[^'\"]+\.(?:jpg|jpeg|png|webp))['\"]", html_text, re.I)
                if m: pic = m.group(1)
            content = extract_content(html_text)
            play_url = extract_play(html_text, self.host)
            play_from = "直链" if play_url and play_url != "eval_encrypted" else "嗅探"
            play_url = play_url if play_url else url
            result["list"].append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": content,
                "vod_play_from": play_from,
                "vod_play_url": f"正片${play_url}"
            })
            return result
        except Exception as e:
            print(f"[{self.name}] 详情失败: {e}")
            return result

    def playerContent(self, flag, id, vipFlags=None):
        try:
            if self.isVideoFormat(id):
                return {"parse": 0, "url": id, "header": json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})}
            if id.startswith("http"):
                html_text = self._fetch(id)
                if html_text:
                    pu = extract_play(html_text, self.host)
                    if pu and pu != "eval_encrypted":
                        return {"parse": 0, "url": pu, "header": json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})}
            return {"parse": 1, "url": id, "header": json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})}
        except Exception as e:
            print(f"[{self.name}] 播放失败: {e}")
            return {"parse": 1, "url": id}

    def searchContent(self, key, quick, pg="1"):
        result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
        try:
            url = f"{self.host}/search.php?keyword={quote(key)}&page={pg}"
            html_text = self._fetch(url)
            if not html_text: return result
            doc = etree.HTML(html_text) if etree else None
            result["list"] = self._parse_list(doc)
            result["pagecount"] = int(pg) + 1 if len(result["list"]) >= 24 else int(pg)
            return result
        except Exception as e:
            print(f"[{self.name}] 搜索失败: {e}")
            return result
