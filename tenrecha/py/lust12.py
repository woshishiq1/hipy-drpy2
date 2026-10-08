import sys
sys.path.append('..')
from base.spider import Spider
import requests
import re
import html
from urllib.parse import urljoin

class Spider(Spider):
    def getName(self):
        return "lust12"

    def init(self, extend=""):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        self.domains = ["https://www.lust12.cc", "https://lust12.cc"]
        self.home_url = self.checkDomain()

    def checkDomain(self):
        for d in self.domains:
            try:
                r = self.session.get(d + "/", timeout=10, verify=False)
                if r.status_code == 200 and len(r.text) > 1000:
                    return d
            except:
                pass
        return self.domains[0]

    def fetch(self, url):
        try:
            r = self.session.get(url, headers=self.session.headers, timeout=20, verify=False)
            return r.text
        except:
            return ""

    def homeContent(self, filter):
        html_text = self.fetch(self.home_url + "/")
        videos = []
        for m in re.finditer(r'<a href="(/index\.php/vod/play/id/(\d+)\.html)">.*?<img src="(https://xjimg\.cdn-xj\.cc/[^"]+)" alt="([^"]*)"', html_text, re.S):
            href, vid, pic, title = m.groups()
            videos.append({
                "vod_id": vid,
                "vod_name": html.unescape(title),
                "vod_pic": pic,
                "vod_remarks": ""
            })
        return {"class": [{"type_id": "44", "type_name": "国产AV"}, {"type_id": "45", "type_name": "日本av"}, {"type_id": "46", "type_name": "欧美情色"}, {"type_id": "48", "type_name": "色情动漫"}], "list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        if pg == "1":
            url = self.home_url + "/index.php/vod/type/id/" + tid + ".html"
        else:
            url = self.home_url + "/index.php/vod/type/id/" + tid + "/page/" + pg + ".html"
        html_text = self.fetch(url)
        videos = []
        for m in re.finditer(r'<a href="(/index\.php/vod/play/id/(\d+)\.html)">.*?<img src="(https://xjimg\.cdn-xj\.cc/[^"]+)" alt="([^"]*)"', html_text, re.S):
            href, vid, pic, title = m.groups()
            videos.append({
                "vod_id": vid,
                "vod_name": html.unescape(title),
                "vod_pic": pic,
                "vod_remarks": ""
            })
        total_match = re.search(r'href="/index\.php/vod/type/id/\d+/page/(\d+)\.html"[^>]*>[^<]*(?:末页|尾页|last)', html_text, re.S | re.I)
        total = int(total_match.group(1)) if total_match else int(pg)
        limit = len(videos) if videos else 20
        return {"page": int(pg), "pagecount": total, "limit": limit, "total": total * limit, "list": videos}

    def detailContent(self, ids):
        vid = ids[0]
        play_url = self.home_url + "/index.php/vod/play/id/" + vid + ".html"
        html_text = self.fetch(play_url)
        title = ""
        pic = ""
        desc = ""
        m3u8 = ""
        title_match = re.search(r'<title>(.*?)</title>', html_text, re.S | re.I)
        if title_match:
            raw = html.unescape(re.sub(r'<.*?>', '', title_match.group(1)).strip())
            for sep in ['|', '-', '_', '—']:
                if sep in raw:
                    raw = raw.split(sep)[0]
                    break
            title = raw.strip()
        pic_match = re.search(r'poster\s*=\s*["\']([^"\']+)["\']', html_text, re.S | re.I)
        if pic_match:
            pic = pic_match.group(1)
        if not pic:
            pic_match2 = re.search(r'src="(https://xjimg\.cdn-xj\.cc/[^"]+)"', html_text, re.S)
            if pic_match2:
                pic = pic_match2.group(1)
        m3u8_match = re.search(r"const source\s*=\s*['\"]([^'\"]+\.m3u8)['\"]", html_text, re.S | re.I)
        if m3u8_match:
            m3u8 = m3u8_match.group(1)
        if not m3u8:
            m3u8_match2 = re.search(r'(https?://[^\s\"\']+\.m3u8)', html_text, re.S | re.I)
            if m3u8_match2:
                m3u8 = m3u8_match2.group(1)
        if not m3u8:
            m3u8_match3 = re.search(r'"url"\s*:\s*"([^"]+\.m3u8)"', html_text, re.S | re.I)
            if m3u8_match3:
                m3u8 = m3u8_match3.group(1)
        if not m3u8:
            m3u8_match4 = re.search(r'"url"\s*:\s*"([^"]+)"', html_text, re.S | re.I)
            if m3u8_match4:
                m3u8 = m3u8_match4.group(1)
        if not m3u8:
            m3u8_match5 = re.search(r'video[^>]*src="([^"]+)"', html_text, re.S | re.I)
            if m3u8_match5:
                m3u8 = m3u8_match5.group(1)
        if not m3u8:
            iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"', html_text, re.S | re.I)
            if iframe_match:
                iframe_src = iframe_match.group(1)
                if iframe_src.startswith("http"):
                    iframe_html = self.fetch(iframe_src)
                    m3u8_match_iframe = re.search(r"const source\s*=\s*['\"]([^'\"]+\.m3u8)['\"]", iframe_html, re.S | re.I)
                    if m3u8_match_iframe:
                        m3u8 = m3u8_match_iframe.group(1)
                    if not m3u8:
                        m3u8_match_iframe2 = re.search(r'(https?://[^\s\"\']+\.m3u8)', iframe_html, re.S | re.I)
                        if m3u8_match_iframe2:
                            m3u8 = m3u8_match_iframe2.group(1)
        if not title:
            title = "视频" + vid
        if m3u8.startswith("//"):
            m3u8 = "https:" + m3u8
        elif m3u8 and not m3u8.startswith("http"):
            m3u8 = urljoin(self.home_url, m3u8)
        vod_play_url = "第1集$" + m3u8 if m3u8 else ""
        return {
            "list": [{
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": desc,
                "vod_play_from": "lust12",
                "vod_play_url": vod_play_url
            }]
        }

    def searchContent(self, key, quick, pg="1"):
        url = self.home_url + "/index.php/vod/search.html?wd=" + requests.utils.quote(key)
        html_text = self.fetch(url)
        videos = []
        for m in re.finditer(r'<a href="(/index\.php/vod/play/id/(\d+)\.html)">.*?<img src="(https://xjimg\.cdn-xj\.cc/[^"]+)" alt="([^"]*)"', html_text, re.S):
            href, vid, pic, title = m.groups()
            videos.append({
                "vod_id": vid,
                "vod_name": html.unescape(title),
                "vod_pic": pic,
                "vod_remarks": ""
            })
        return {"list": videos}

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags):
        return {"parse": 0, "url": id, "header": "{\"User-Agent\":\"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36\",\"Referer\":\"" + self.home_url + "/\"}"}

    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        pass
