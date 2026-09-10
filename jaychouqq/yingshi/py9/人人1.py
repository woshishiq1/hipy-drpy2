# -*- coding: utf-8 -*-
"""
站点：https://mh.yichengwlkj.com
问题说明：网站内容JS动态渲染，普通requests拿不到完整dom；本版本增加调试打印，修复spider字段规范
适配影视仓FongMi spider，对齐儿歌乐园模板
"""
import sys
import json
import re
sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    import requests
    class BaseSpider(object):
        def fetch(self, url, headers=None, timeout=20, verify=False, cookies=None):
            s = requests.Session()
            s.trust_env = False
            return s.get(url, headers=headers, timeout=timeout, verify=verify, cookies=cookies)

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

class Spider(BaseSpider):
    name = "yicheng影视"
    host = "https://mh.yichengwlkj.com"
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"

    def init(self, extend=""):
        return {}

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".m4v", ".ts", ".flv", ".mkv"))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def localProxy(self, param):
        return [200, "text/plain", ""]

    def liveContent(self, url):
        return ""

    def action(self, action):
        return "{}"

    def _headers(self):
        return {
            "User‑Agent": self.UA,
            "Referer": self.host + "/",
            "Accept‑Language": "zh‑CN,zh;q=0.9",
            "X‑Requested‑With": "XMLHttpRequest"
        }

    def _get_html(self, path):
        """GET获取网页HTML文本，增加调试打印"""
        try:
            url = self.host + path
            resp = self.fetch(url, headers=self._headers(), timeout=10)
            print(f"[debug] url={url} status={resp.status_code}")
            return resp.text
        except Exception as e:
            print(f"[debug] fetch error {path}, err={str(e)}")
            return ""

    def _parse_vod_item(self, html):
        """解析卡片，返回vod字典列表"""
        vod_list = []
        pattern = re.compile(r'<a href="(/play/\d+)">.*?<img.*?src="(.*?)".*?alt="(.*?)".*?</a>', re.S)
        matches = pattern.findall(html)
        for href, pic, title in matches:
            vid = href.strip("/play/")
            pic = pic.strip()
            if pic.startswith("//"):
                pic = "https:" + pic
            vod_list.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": ""
            })
        print(f"[debug] parse card count: {len(vod_list)}")
        return vod_list

    def homeContent(self, filter=False):
        """
        【故障点】网站导航JS渲染，静态html拿不到导航菜单class数组；
        临时降级写死分类，保证APP菜单栏可以显示；
        如果想要真实分类，必须无头浏览器渲染页面
        """
        ret = {"class": [
            {"type_id":"1","type_name":"电影"},
            {"type_id":"2","type_name":"剧集"},
            {"type_id":"3","type_name":"动漫"},
            {"type_id":"4","type_name":"综艺"}
        ], "filters": {}, "list": []}
        html = self._get_html("/")
        ret["list"] = self._parse_vod_item(html)
        return ret

    def homeVideoContent(self):
        ret = {"list": [], "page":1, "pagecount":1, "limit":30, "total":30}
        html = self._get_html("/")
        ret["list"] = self._parse_vod_item(html)
        return ret

    def categoryContent(self, tid, pg, filter=False, extend=""):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        ret = {"list":[], "page":page, "pagecount":999, "limit":30, "total":9999}
        path = f"/category/{tid}"
        if page > 1:
            path += f"?page={page}"
        html = self._get_html(path)
        ret["list"] = self._parse_vod_item(html)
        has_next = "下一页" in html
        ret["pagecount"] = page + 1 if has_next else page
        return ret

    def detailContent(self, ids):
        """
        【故障点】播放地址JS渲染，静态html正则抓不到m3u8，vod_play_url为空，分集列表空白
        """
        rid = ids[0] if isinstance(ids, (list, tuple)) and ids else str(ids or "")
        ret = {"list":[]}
        try:
            html = self._get_html(f"/play/{rid}")
            title_match = re.search(r'<h1.*?>(.*?)</h1>', html, re.S)
            vod_name = title_match.group(1).strip() if title_match else "未知"
            pic_match = re.search(r'<img.*?src="(.*?)".*?alt="{}"'.format(re.escape(vod_name)), re.S)
            vod_pic = pic_match.group(1).strip() if pic_match else ""
            if vod_pic.startswith("//"):
                vod_pic = "https:" + vod_pic

            play_items = []
            # 原正则只抓页面明文$http，JS渲染的链接抓不到
            ep_pat = re.compile(r'<li.*?><a.*?>([^$]+)\$(http.*?\.m3u8[^<]*)', re.S)
            ep_matches = ep_pat.findall(html)
            for ep_name, ep_url in ep_matches:
                ep_name = ep_name.strip()
                ep_url = ep_url.strip()
                play_items.append(f"{ep_name}${ep_url}")

            vod_play_from = "默认线路"
            vod_play_url = "#".join(play_items)
            print(f"[debug] detail ep count={len(play_items)} play_url={vod_play_url[:120]}")

            vod = {
                "vod_id": rid,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": "",
                "vod_year": "",
                "vod_area": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": vod_play_from,
                "vod_play_url": vod_play_url
            }
            ret["list"].append(vod)
        except Exception as e:
            print(f"[debug] detail error {str(e)}")
            ret["list"].append({
                "vod_id": rid,
                "vod_name": "详情加载失败",
                "vod_content": str(e),
                "vod_play_from": "",
                "vod_play_url": ""
            })
        return ret

    def searchContent(self, key, quick=False, pg="1"):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        ret = {"list":[], "page":page, "pagecount":999, "limit":30, "total":9999}
        if not key.strip():
            return ret
        params = {"wd": key, "page": page}
        try:
            from urllib.parse import urlencode
            qs = urlencode(params)
            html = self._get_html("/search?" + qs)
            ret["list"] = self._parse_vod_item(html)
            ret["pagecount"] = page + 1 if "下一页" in html else page
        except Exception as e:
            print(f"[debug] search error {str(e)}")
        return ret

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, flags=None):
        """播放：增加完整防盗链头"""
        url = str(id or "").strip()
        if self.isVideoFormat(url) and url.startswith("http"):
            return {
                "parse": 0,
                "playUrl": "",
                "url": url,
                "header": {
                    "User‑Agent": self.UA,
                    "Referer": self.host + "/play/",
                    "Accept": "*/*"
                }
            }
        return {"parse":0, "playUrl":"", "url":"", "header":{"User‑Agent":self.UA,"Referer":self.host}}

if __name__ == '__main__':
    s = Spider()
    print("=== homeContent ===")
    h = s.homeContent(False)
    print("分类：", len(h["class"]), "首页条目：", len(h["list"]))