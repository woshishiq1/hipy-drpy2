#coding=utf-8
#!/usr/bin/python
"""
==================================================
  杏吧视频 媒体解析插件 (优先默认域名/故障容灾版)
  作者: 飞鱼
==================================================
"""
import sys
import re
import requests
from pyquery import PyQuery as pq

sys.path.append('..')
try:
    from base.spider import Spider
except Exception:
    try:
        from spider import Spider
    except Exception:
        class Spider(object):
            pass

class Spider(Spider):
    def getName(self):
        return "杏吧视频"

    def init(self, extend=""):
        # 1. 设定默认域名
        self.site_url = "https://jlj.xbsp6.boats"
        self.publish_page_url = "https://ruv.xxkk7.com/323/"
        
        # 2. 检查默认域名连通性，失败时才获取最新域名
        if not self.check_site_available(self.site_url):
            self.get_latest_site_url()

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def getHeader(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": getattr(self, 'site_url', "https://jlj.xbsp6.boats/")
        }

    # ===== 新增：检查域名连通性 =====
    def check_site_available(self, url):
        try:
            # 仅检测连通性，设置较短超时（3秒）以提升加载效率
            resp = requests.head(url, headers=self.getHeader(), timeout=3, allow_redirects=True)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        return False

    def get_latest_site_url(self):
        try:
            resp = requests.get(self.publish_page_url, headers=self.getHeader(), timeout=10)
            resp.encoding = 'UTF-8'
            html = resp.text
            sub_domain_match = re.search(r"sub_domain\s*=\s*['\"]([^'\"]+)['\"]", html)
            prefix_match = re.search(r"prefix\s*=\s*['\"]([^'\"]+)['\"]", html)
            suffix_match = re.search(r"suffix\s*=\s*['\"]([^'\"]+)['\"]", html)

            if sub_domain_match and prefix_match and suffix_match:
                sub_domain = sub_domain_match.group(1)
                prefix = prefix_match.group(1)
                suffix = suffix_match.group(1)
                self.site_url = f"https://{sub_domain}.{prefix}.{suffix}".rstrip("/")
        except Exception as e:
            print(e)

    def _get_items_from_html(self, html_str, base_url=""):
        videos = []
        try:
            doc = pq(html_str)
            for item in doc("#posts article").items():
                title = item("h2").text().strip()
                href = item("a").attr("href") or ""
                img = item("img").attr("data-src") or item("img").attr("src") or ""
                remark = item(".meta-content").text().strip()

                if not title and not href:
                    continue

                if href and not href.startswith("http"):
                    href = base_url + ("" if href.startswith("/") else "/") + href

                videos.append({
                    "vod_id": href,
                    "vod_name": title,
                    "vod_pic": img,
                    "vod_remarks": remark
                })
        except Exception as e:
            print(f"Parse error: {e}")
        return videos

    def homeContent(self, filter):
        result = {}
        classes = [
            {"type_id": "20", "type_name": "熟母少妇"},
            {"type_id": "21", "type_name": "网红直播"},
            {"type_id": "22", "type_name": "自拍偷拍"},
            {"type_id": "23", "type_name": "强奸乱伦"},
            {"type_id": "24", "type_name": "高清国产"},
            {"type_id": "25", "type_name": "韩国专区"},
            {"type_id": "26", "type_name": "日本有码"},
            {"type_id": "27", "type_name": "日本无码"},
            {"type_id": "28", "type_name": "欧美情色"},
            {"type_id": "29", "type_name": "动漫卡通"},
            {"type_id": "30", "type_name": "三级伦理"}
        ]
        result['class'] = classes
        try:
            home_url = f"{self.site_url}/xbsp/"
            resp = requests.get(home_url, headers=self.getHeader(), timeout=10)
            resp.encoding = 'UTF-8'
            result['list'] = self._get_items_from_html(resp.text, base_url=self.site_url)
        except Exception as e:
            print(e)
        return result

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg="1", filter=False, extend={}):
        result = {}
        videos = []
        try:
            page = str(pg) if pg else "1"
            url = f"{self.site_url}/vodtype/{tid}-{page}.html"
            resp = requests.get(url, headers=self.getHeader(), timeout=10)
            resp.encoding = 'UTF-8'
            videos = self._get_items_from_html(resp.text, base_url=self.site_url)
        except Exception as e:
            print(e)
            
        result['list'] = videos
        result['page'] = pg
        result['pagecount'] = 9999
        result['limit'] = 20
        result['total'] = 9999
        return result

    def detailContent(self, ids):
        vod = {}
        try:
            url = ids[0] if isinstance(ids, list) else ids
            vod['vod_id'] = url
            vod['vod_name'] = "在线播放"
            vod['type_name'] = "福利"
            vod['vod_play_from'] = "杏吧播放"
            vod['vod_play_url'] = f"正片${url}"
        except Exception as e:
            print(e)
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        videos = []
        try:
            url = f"{self.site_url}/s/{key}/page/{pg}.html"
            resp = requests.get(url, headers=self.getHeader(), timeout=10)
            resp.encoding = 'UTF-8'
            videos = self._get_items_from_html(resp.text, base_url=self.site_url)
        except Exception as e:
            print(e)
        return {"list": videos}

    def playerContent(self, flag, id, vipFlags):
        play_url = id
        try:
            resp = requests.get(id, headers=self.getHeader(), timeout=10)
            resp.encoding = 'UTF-8'
            html = resp.text

            raw_match = re.search(r"const\s+rawUrl\s*=\s*['\"]([^'\"]+\.m3u8[^'\"]*)['\"]", html)
            if raw_match:
                play_url = raw_match.group(1)
            else:
                m3u8_match = re.search(r"https?://[^\s$#\'\"]+\.m3u8(?:\?[^\s#\'\"]*)?", html, re.IGNORECASE)
                if m3u8_match:
                    play_url = m3u8_match.group(0)
        except Exception as e:
            print(f"Player parsing error: {e}")

        return {
            "parse": 0,
            "url": play_url,
            "header": self.getHeader()
        }

    def localProxy(self, param):
        pass
