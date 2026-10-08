# -*- coding: utf-8 -*-
import sys
import re
import json
import base64
import html as htmlmod
from urllib.parse import quote, unquote, urljoin

try:
    import requests
except ImportError:
    requests = None

try:
    from lxml import etree
except ImportError:
    etree = None

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): pass
        def homeContent(self, filter): return {}
        def homeVideoContent(self): return {}
        def categoryContent(self, tid, pg, filter, extend): return {}
        def detailContent(self, ids): return {}
        def playerContent(self, flag, id, vipFlags): return {}
        def searchContent(self, key, quick, pg="1"): return {}
        def isVideoFormat(self, url): return False
        def manualVideoCheck(self): return False
        def localProxy(self, param): return [200, "text/plain", b""]
        def destroy(self): pass
        def getName(self): return "Base"

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://4tw3gy653a.bulunhufait.buzz"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/"
        }
        self.session = None
        if requests:
            self.session = requests.Session()
            self.session.headers.update(self.headers)
        self.seen = set()

    def init(self, extend=""):
        if extend and extend.startswith("http"):
            self.host = extend.rstrip("/")
            self.headers["Referer"] = self.host + "/"
            if self.session:
                self.session.headers.update(self.headers)

    def getName(self):
        return "bulunhufait"

    def destroy(self):
        if self.session:
            self.session.close()

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or ".flv" in url or ".ts" in url

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [200, "video/MP2T", b"", {}]

    def _req(self, url):
        if not self.session:
            return ""
        try:
            r = self.session.get(url, headers=self.headers, timeout=15, verify=False)
            r.encoding = "utf-8"
            return r.text
        except Exception:
            return ""

    def _fix(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return urljoin(self.host, url)
        if url.startswith("http"):
            return url
        return urljoin(self.host, "/" + url)

    def _clean(self, text):
        if not text:
            return ""
        return htmlmod.unescape(re.sub(r"<[^>]+>", "", str(text))).strip()

    def _extract_title(self, html_text):
        title = ""
        m = re.search(r'<title>([^<]+)</title>', html_text, re.I)
        if m:
            title = m.group(1).strip()
            title = re.sub(r'详情介绍.*$', '', title)
            title = re.sub(r'在线观看.*$', '', title)
            title = re.sub(r'迅雷下载.*$', '', title)
            title = title.strip("- ")
        if title:
            return self._clean(title)
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html_text, re.S | re.I)
        if m:
            title = self._clean(m.group(1))
        if title:
            return title
        m = re.search(r'<h2[^>]*>(.*?)</h2>', html_text, re.S | re.I)
        if m:
            title = self._clean(m.group(1))
        if title:
            return title
        m = re.search(r'<div[^>]*class=["\'][^"\']*title[^"\']*["\'][^>]*>(.*?)</div>', html_text, re.S | re.I)
        if m:
            title = self._clean(m.group(1))
        if title:
            return title
        m = re.search(r'<strong[^>]*class=["\']title["\'][^>]*>(.*?)</strong>', html_text, re.S | re.I)
        if m:
            title = self._clean(m.group(1))
        if title:
            return title
        return ""

    def _extract_pic(self, html_text):
        m = re.search(r'<img[^>]+data-original=["\']([^"\']+)["\'][^>]*>', html_text, re.I)
        if m:
            return self._fix(m.group(1))
        m = re.search(r'<img[^>]+data-src=["\']([^"\']+)["\'][^>]*>', html_text, re.I)
        if m:
            return self._fix(m.group(1))
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*(?:poster|cover|thumb)[^"\']*["\']', html_text, re.I)
        if m:
            return self._fix(m.group(1))
        m = re.search(r'<img[^>]+class=["\'][^"\']*(?:poster|cover|thumb)[^"\']*["\'][^>]+src=["\']([^"\']+)["\']', html_text, re.I)
        if m:
            return self._fix(m.group(1))
        return ""

    def _extract_content(self, html_text):
        m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
        if m:
            return self._clean(m.group(1))
        m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']', html_text, re.I)
        if m:
            return self._clean(m.group(1))
        m = re.search(r'<div[^>]*class=["\'][^"\']*(?:content|desc|summary|intro|vod-content)[^"\']*["\'][^>]*>(.*?)</div>', html_text, re.S | re.I)
        if m:
            return self._clean(m.group(1))
        return ""

    def _extract_playlist(self, html_text):
        sources = []
        play_urls = []
        if etree:
            doc = etree.HTML(html_text)
            if doc is not None:
                panels = doc.xpath('//div[contains(@class,"play") or contains(@class,"playlist") or contains(@class,"source") or contains(@class,"panel")]')
                for panel in panels:
                    try:
                        sname_list = panel.xpath('.//h3/text() | .//span[contains(@class,"name") or contains(@class,"title") or contains(@class,"tab")]/text() | .//div[contains(@class,"from")]/text()')
                        sname = self._clean(sname_list[0]) if sname_list else "默认线路"
                        eps = panel.xpath('.//a[contains(@href,"/vodplay/") or contains(@href,"/play/")]')
                        if not eps:
                            eps = panel.xpath('.//a[contains(@href,"vodplay")]')
                        ep_list = []
                        for ep in eps:
                            try:
                                ep_title_list = ep.xpath('./text()')
                                ep_title = self._clean(ep_title_list[0]) if ep_title_list else "播放"
                                ep_href_list = ep.xpath('./@href')
                                ep_href = ep_href_list[0] if ep_href_list else ""
                                if ep_href:
                                    ep_list.append(ep_title + "$" + self._fix(ep_href))
                            except Exception:
                                continue
                        if ep_list:
                            sources.append(sname)
                            play_urls.append("#".join(ep_list))
                    except Exception:
                        continue
        if not sources:
            eps = re.findall(r'<a[^>]+href=["\'](/vodplay/[^"\']+)["\'][^>]*>(.*?)</a>', html_text, re.S | re.I)
            if eps:
                ep_list = []
                for href, title in eps:
                    title = self._clean(title)
                    if not title:
                        title = "播放"
                    ep_list.append(title + "$" + self._fix(href))
                if ep_list:
                    sources = ["默认线路"]
                    play_urls = ["#".join(ep_list)]
        return sources, play_urls

    def _play(self, html_text):
        m = re.search(r'var\s+player_data\s*=\s*(\{.*?\});', html_text, re.DOTALL)
        if not m:
            m = re.search(r'player_data\s*=\s*(\{.*?\});', html_text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                url = data.get("url", "")
                encrypt = data.get("encrypt", "0")
                if encrypt == "1" or encrypt == 1:
                    url = unquote(url)
                elif encrypt == "2" or encrypt == 2:
                    url = unquote(base64.b64decode(url).decode("utf-8"))
                return url
            except Exception:
                pass
        m = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html_text)
        if m:
            return m.group(1)
        m = re.search(r'(https?://[^\s"\']+\.mp4[^\s"\']*)', html_text)
        if m:
            return m.group(1)
        m = re.search(r'var\s*now\s*=\s*["\']([^"\']+)["\']', html_text)
        if m:
            return m.group(1)
        m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_text)
        if m:
            try:
                u = self._fix(m.group(1))
                h = self._req(u)
                if h:
                    return self._play(h)
            except Exception:
                pass
        return ""

    def homeContent(self, filter):
        classes = [
            {"type_name": "制服诱惑", "type_id": "27"},
            {"type_name": "网红头条", "type_id": "317"},
            {"type_name": "主播网红", "type_id": "59"},
            {"type_name": "精东影业", "type_id": "430"},
            {"type_name": "麻豆资源", "type_id": "423"},
            {"type_name": "欧美美女", "type_id": "506"},
            {"type_name": "闷骚护士", "type_id": "97"},
            {"type_name": "探花约炮", "type_id": "276"},
            {"type_name": "主播诱惑", "type_id": "275"},
            {"type_name": "AV明星", "type_id": "144"},
            {"type_name": "AV解说", "type_id": "312"},
            {"type_name": "欧美", "type_id": "52"},
            {"type_name": "国产裸聊", "type_id": "374"},
            {"type_name": "三级伦理", "type_id": "163"},
            {"type_name": "国产自拍", "type_id": "274"},
            {"type_name": "国产视频", "type_id": "297"},
            {"type_name": "杏吧原创", "type_id": "435"},
            {"type_name": "剧情介绍", "type_id": "86"},
            {"type_name": "极品媚黑", "type_id": "315"},
            {"type_name": "貧乳小奶", "type_id": "179"},
            {"type_name": "明星换脸", "type_id": "307"},
            {"type_name": "韩国主播", "type_id": "319"},
            {"type_name": "映画传媒", "type_id": "165"},
            {"type_name": "兔子先生", "type_id": "434"},
            {"type_name": "少女萝莉", "type_id": "361"},
            {"type_name": "家庭乱伦", "type_id": "397"},
            {"type_name": "女优明星", "type_id": "287"},
            {"type_name": "可爱学生", "type_id": "93"},
            {"type_name": "国产自拍", "type_id": "375"},
            {"type_name": "明星换脸", "type_id": "152"},
            {"type_name": "AV解说", "type_id": "153"},
            {"type_name": "国产精品", "type_id": "49"},
            {"type_name": "禁漫", "type_id": "53"},
            {"type_name": "素人自拍", "type_id": "80"},
            {"type_name": "SM调教", "type_id": "401"},
            {"type_name": "瑜伽裤", "type_id": "96"},
            {"type_name": "群交淫乱", "type_id": "367"},
            {"type_name": "日本无码", "type_id": "301"}
        ]
        return {"class": classes, "filters": {}}

    def homeVideoContent(self):
        return self.categoryContent("27", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
        prefix = "arttype" if tid == "506" else "vodtype"
        if int(pg) == 1:
            url = self.host + "/" + prefix + "/" + tid + "/"
        else:
            url = self.host + "/" + prefix + "/" + tid + "-" + str(pg) + "/"
        html_text = self._req(url)
        if not html_text:
            return result
        doc = etree.HTML(html_text) if etree else None
        if not doc:
            return result
        
        items = doc.xpath('//div[contains(@class,"row")]//dl')
        if not items:
            items = doc.xpath('//dl[.//a[contains(@href,"/voddetail/")]]')
        self.seen.clear()
        for item in items:
            try:
                a = item.xpath('.//dt/a | .//dd/a')[0]
                tlist = a.xpath('.//h3/text() | ./@title | .//img/@alt')
                title = self._clean(tlist[0]) if tlist else ""
                hlist = item.xpath('.//dt/a/@href | .//dd/a/@href')
                href = hlist[0] if hlist else ""
                m = re.search(r'/voddetail/([0-9]+)/', href)
                vid = m.group(1) if m else href
                if vid in self.seen:
                    continue
                self.seen.add(vid)
                plist = item.xpath('.//img/@data-original')
                if not plist:
                    plist = item.xpath('.//img/@data-src')
                if not plist:
                    plist = item.xpath('.//img/@src')
                pic = self._fix(plist[0]) if plist else ""
                result["list"].append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": ""})
            except Exception:
                continue
        
        plinks = doc.xpath('//div[@class="pagination"]//a/@href')
        maxpg = 1
        for pl in plinks:
            m = re.search(r'/(?:vod|art)type/\d+-(\d+)/', pl)
            if m:
                p = int(m.group(1))
                if p > maxpg:
                    maxpg = p
        if maxpg > 1:
            result["pagecount"] = maxpg
        else:
            result["pagecount"] = int(pg) + 1 if len(result["list"]) >= 24 else int(pg)
        return result

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        result = {"list": []}
        url = self.host + "/voddetail/" + str(vid) + "/"
        html_text = self._req(url)
        if not html_text:
            return result

        title = self._extract_title(html_text)
        if not title:
            title = str(vid)

        pic = self._extract_pic(html_text)
        content = self._extract_content(html_text)
        sources, play_urls = self._extract_playlist(html_text)

        if not play_urls:
            sources = ["默认线路"]
            direct_url = self._play(html_text)
            if direct_url:
                play_urls.append("正片$" + direct_url)
            else:
                play_urls.append("播放$" + self.host + "/vodplay/" + str(vid) + "-1-1/")

        result["list"].append({
            "vod_id": str(vid),
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": content,
            "vod_play_from": "$$$".join(sources),
            "vod_play_url": "$$$".join(play_urls)
        })
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "playUrl": "", "url": "", "header": ""}

        if self.isVideoFormat(id):
            result["url"] = id
            result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
            return result

        if "/vodplay/" in id or "/play/" in id:
            html_text = self._req(id)
            if html_text:
                purl = self._play(html_text)
                if purl:
                    result["url"] = purl
                    result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                    return result
            result["parse"] = 1
            result["url"] = id
            result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
            return result

        if id.startswith("http"):
            html_text = self._req(id)
            if html_text:
                purl = self._play(html_text)
                if purl:
                    result["url"] = purl
                    result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                    return result

        result["url"] = id
        return result

    def searchContent(self, key, quick, pg="1"):
        result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
        url = self.host + "/vodsearch/-------------/?wd=" + quote(key) + "&page=" + str(pg)
        html_text = self._req(url)
        if not html_text:
            return result
        doc = etree.HTML(html_text) if etree else None
        if not doc:
            return result
        
        items = doc.xpath('//div[contains(@class,"row")]//dl')
        if not items:
            items = doc.xpath('//dl[.//a[contains(@href,"/voddetail/")]]')
        self.seen.clear()
        for item in items:
            try:
                a = item.xpath('.//dt/a | .//dd/a')[0]
                tlist = a.xpath('.//h3/text() | ./@title | .//img/@alt')
                title = self._clean(tlist[0]) if tlist else ""
                hlist = item.xpath('.//dt/a/@href | .//dd/a/@href')
                href = hlist[0] if hlist else ""
                m = re.search(r'/voddetail/([0-9]+)/', href)
                vid = m.group(1) if m else href
                if vid in self.seen:
                    continue
                self.seen.add(vid)
                plist = item.xpath('.//img/@data-original')
                if not plist:
                    plist = item.xpath('.//img/@data-src')
                if not plist:
                    plist = item.xpath('.//img/@src')
                pic = self._fix(plist[0]) if plist else ""
                result["list"].append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": ""})
            except Exception:
                continue
        return result
