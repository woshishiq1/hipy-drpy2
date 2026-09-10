# -*- coding: utf-8 -*-
"""
mh.yichengwlkj.com 调试版
cdn.rrmj.plus auth_key签名
适配影视仓FongMi Spider
⚠️ 站点为SPA JS渲染，首页、分类、搜索无法获取列表；仅支持已知vod_id进入详情播放
"""
import sys
import json
import re
import time
import hashlib

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
    # ========== 【重要】这里密钥需要从网页JS重新提取，站点更新就会失效 ==========
    CDN_SECRET = "rrmj2024secretkey"

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
            "Accept‑Language": "zh‑CN,zh;q=0.9"
        }

    def _get_html(self, path):
        try:
            url = self.host + path
            resp = self.fetch(url, headers=self._headers(), timeout=12)
            print(f"[DEBUG] 请求 {url} | status={resp.status_code}")
            return resp.text
        except Exception as e:
            print(f"[DEBUG] 请求异常 path={path} err={str(e)}")
            return ""

    def gen_rrmj_auth(self, video_path):
        """生成cdn.rrmj.plus auth_key鉴权地址"""
        ts = int(time.time())
        rand = "000000"
        raw_str = f"{ts}-{rand}-0-{video_path}-{self.CDN_SECRET}"
        md5_sig = hashlib.md5(raw_str.encode("utf-8")).hexdigest()
        auth_key = f"{ts}-{rand}-0-{md5_sig}"
        full_url = f"https://cdn.rrmj.plus{video_path}?auth_key={auth_key}"
        print(f"[DEBUG] 生成鉴权url：{full_url}")
        return full_url

    def extract_js_vars(self, html):
        """从页面JS源码提取 videoPath, videoName, epCount"""
        out = {"video_path": "", "video_name": "未知", "ep_count": 0}
        pat_path = re.search(r'videoPath\s*=\s*"([^"]+)"', html)
        pat_name = re.search(r'videoName\s*=\s*"([^"]+)"', html)
        pat_ep = re.search(r'epCount\s*=\s*(\d+)', html)

        if pat_path:
            out["video_path"] = pat_path.group(1)
        if pat_name:
            out["video_name"] = pat_name.group(1)
        if pat_ep:
            out["ep_count"] = int(pat_ep.group(1))
        print(f"[DEBUG] JS提取结果: {out}")
        return out

    def _parse_vod_item(self, html):
        """SPA静态HTML拿不到卡片，基本返回空"""
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
        print(f"[DEBUG] 解析卡片数量 {len(vod_list)}")
        return vod_list

    def homeContent(self, filter=False):
        ret = {
            "class": [
                {"type_id": "1", "type_name": "电影"},
                {"type_id": "2", "type_name": "剧集"},
                {"type_id": "3", "type_name": "动漫"},
                {"type_id": "4", "type_name": "综艺"}
            ],
            "filters": {},
            "list": []
        }
        html = self._get_html("/")
        ret["list"] = self._parse_vod_item(html)
        return ret

    def homeVideoContent(self):
        ret = {"list": [], "page": 1, "pagecount": 1, "limit": 30, "total": 30}
        html = self._get_html("/")
        ret["list"] = self._parse_vod_item(html)
        return ret

    def categoryContent(self, tid, pg, filter=False, extend=""):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        ret = {"list": [], "page": page, "pagecount": 1, "limit": 30, "total": 0}
        return ret

    def detailContent(self, ids):
        rid = ids[0] if isinstance(ids, (list, tuple)) and ids else str(ids or "")
        ret = {"list": []}
        try:
            html = self._get_html(f"/play/{rid}")
            js_data = self.extract_js_vars(html)
            video_path = js_data["video_path"]
            vod_name = js_data["video_name"]
            ep_total = js_data["ep_count"]

            play_items = []
            if video_path and ep_total > 0:
                for ep in range(1, ep_total + 1):
                    ep_full_path = f"{video_path}/ep{ep}/index.m3u8"
                    m3u8_url = self.gen_rrmj_auth(ep_full_path)
                    play_items.append(f"第{ep}集${m3u8_url}")
            else:
                print("[DEBUG] 未提取到videoPath或集数，无法生成分集")

            vod_play_from = "CDN‑RRMJ"
            vod_play_url = "#".join(play_items)
            print(f"[DEBUG] 分集列表总长度：{len(play_items)}")
            print(f"[DEBUG] vod_play_url(截断): {vod_play_url[:200]}")

            vod = {
                "vod_id": rid,
                "vod_name": vod_name,
                "vod_pic": "",
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
            print(f"[DEBUG] detail异常 {str(e)}")
            ret["list"].append({
                "vod_id": rid,
                "vod_name": "详情解析失败",
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
        ret = {"list": [], "page": page, "pagecount": 1, "limit": 30, "total": 0}
        return ret

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, flags=None):
        url = str(id or "").strip()
        print(f"[DEBUG] playerContent收到播放id：{url[:120]}")
        if self.isVideoFormat(url) and url.startswith("http"):
            return {
                "parse": 0,
                "playUrl": "",
                "url": url,
                "header": {
                    "User‑Agent": self.UA,
                    "Referer": self.host + "/",
                    "Accept": "*/*"
                }
            }
        print("[DEBUG] 无效播放地址")
        return {"parse": 0, "playUrl": "", "url": "", "header": {"User‑Agent": self.UA, "Referer": self.host}}


if __name__ == '__main__':
    s = Spider()
    print("===== 测试播放链路 =====\n")
    # ========== 这里替换成真实的vod_id测试 ==========
    test_vid = "12345"
    res = s.detailContent([test_vid])
    print("\n==== detail返回结果 ====")
    print(json.dumps(res, ensure_ascii=False, indent=2))