#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可乐影院 四壳通用Python Spider
CF防护站点，使用curl_cffi safari17_2_ios指纹穿透
支持：首页推荐 / 8大分类 / 搜索 / 播放（m3u8直链）
"""

import json
import re
import os

try:
    from curl_cffi import requests as cffi_req
    HAS_CFFI = True
except ImportError:
    HAS_CFFI = False

try:
    import requests as _req
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from base.spider import Spider as _Base
except ImportError:
    class _Base:
        def init(self, extend=""):
            pass


BASE_URL = "https://cil.klyy3.wiki"
BASE_PATH = "/cn/home/web"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"

# 分类（剔除未成年相关）
CATEGORIES = [
    {"type_id": "20", "type_name": "国产精品"},
    {"type_id": "21", "type_name": "主播大秀"},
    {"type_id": "22", "type_name": "唯美视频"},
    {"type_id": "23", "type_name": "口交视频"},
    {"type_id": "24", "type_name": "日本有碼"},
    {"type_id": "25", "type_name": "日本無碼"},
    {"type_id": "26", "type_name": "动漫视频"},
    {"type_id": "27", "type_name": "欧美视频"},
]

# 未成年关键词（铁律13，命中即跳过）
MINOR_KEYWORDS = ["小学生", "初中", "幼女", "萝莉", "少女", "童", "未成年", "teen", "loli", "schoolgirl", "小學生", "國中"]


class Spider(_Base):
    name = "可乐影院"
    profile = {"wd": 1, "ps": 40, "play_url": 1}

    def __init__(self):
        self._sess = None
        self.base_url = BASE_URL
        self._last_error = ""

    def init(self, extend=""):
        if extend:
            try:
                d = json.loads(extend) if isinstance(extend, str) else extend
                if d.get("siteUrl"):
                    self.base_url = d["siteUrl"].rstrip("/")
            except Exception:
                pass
        print(f"[可乐影院] 初始化: {self.base_url}")

    def _fetch(self, path, retries=3):
        """带CF穿透的请求（多级降级：curl_cffi -> requests -> urllib -> 反代）"""
        url = self.base_url + path
        self._last_error = ""
        headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        }

        # 通道1: curl_cffi
        if HAS_CFFI:
            for attempt in range(retries):
                try:
                    r = cffi_req.get(url, impersonate="safari17_2_ios", timeout=20)
                    if r.status_code == 200 and len(r.text) > 1000:
                        return r.text
                except Exception as e:
                    self._last_error = f"curl_cffi:{e}"
            try:
                r = cffi_req.get(url, impersonate="chrome131", timeout=20)
                if r.status_code == 200 and len(r.text) > 1000:
                    return r.text
            except Exception as e:
                self._last_error = f"curl_cffi_chrome:{e}"

        # 通道2: requests
        if HAS_REQUESTS:
            try:
                r = _req.get(url, headers=headers, timeout=20)
                if r.status_code == 200 and len(r.text) > 1000:
                    return r.text
                self._last_error = f"requests:HTTP{r.status_code}"
            except Exception as e:
                self._last_error = f"requests:{e}"

        # 通道3: urllib（纯标准库，处理gzip）
        try:
            import urllib.request
            import gzip
            import io
            try:
                import ssl
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            except Exception:
                ctx = None
            req = urllib.request.Request(url, headers=headers)
            if ctx:
                resp = urllib.request.urlopen(req, timeout=20, context=ctx)
            else:
                resp = urllib.request.urlopen(req, timeout=20)
            raw = resp.read()
            # 处理gzip
            if resp.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            data = raw.decode("utf-8", errors="ignore")
            if len(data) > 1000:
                return data
            self._last_error = f"urllib:内容太短({len(data)}b)"
        except Exception as e:
            self._last_error = f"urllib:{e}"

        # 通道4: 默认反代
        try:
            proxy = "https://xsz-shared-proxy.97471201.workers.dev"
            proxy_url = proxy + path
            import urllib.request as u2
            req2 = u2.Request(proxy_url, headers={"User-Agent": UA, "Referer": self.base_url + "/"})
            resp2 = u2.urlopen(req2, timeout=25)
            data2 = resp2.read().decode("utf-8", errors="ignore")
            if len(data2) > 1000:
                return data2
            self._last_error += f"|proxy:内容太短"
        except Exception as e:
            self._last_error += f"|proxy:{e}"

        return ""

    def _is_minor(self, text):
        """检查是否包含未成年关键词（铁律13）"""
        if not text:
            return False
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in MINOR_KEYWORDS)

    def _parse_list(self, html):
        """解析视频列表"""
        videos = []
        if not html:
            return videos
        # 匹配vodlist中的li项
        pattern = re.compile(
            r'<li[^>]*>\s*<a[^>]*href="([^"]*play[^"]*)"[^>]*title="([^"]*)"[^>]*>[\s\S]*?'
            r'<img[^>]*src="([^"]+)"',
            re.DOTALL
        )
        for m in pattern.finditer(html):
            href, title, pic = m.groups()
            # 未成年跳过
            if self._is_minor(title):
                continue
            # 提取vod_id
            vid_m = re.search(r'/id/(\d+)', href)
            vod_id = vid_m.group(1) if vid_m else href
            videos.append({
                "vod_id": str(vod_id),
                "vod_name": title.strip()[:80],
                "vod_pic": pic.strip(),
                "vod_remarks": "",
            })
        return videos

    def homeContent(self, *args):
        try:
            classes = [{"type_id": c["type_id"], "type_name": c["type_name"]} for c in CATEGORIES]
            filters = {c["type_id"]: [] for c in CATEGORIES}
            html = self._fetch(f"{BASE_PATH}/")
            videos = self._parse_list(html)
            # 调试：如果没有视频，把错误信息作为一个视频项显示
            if not videos:
                videos.append({
                    "vod_id": "debug",
                    "vod_name": f"调试: 无视频。错误={self._last_error[:50]}",
                    "vod_pic": "",
                    "vod_remarks": self._last_error[:100],
                })
            return {"class": classes, "filters": filters, "list": videos}
        except Exception as e:
            print(f"[可乐影院 homeContent错误] {e}")
            classes = [{"type_id": c["type_id"], "type_name": c["type_name"]} for c in CATEGORIES]
            return {"class": classes, "filters": {}, "list": [{"vod_id": "error", "vod_name": f"异常:{str(e)[:50]}", "vod_pic": "", "vod_remarks": str(e)[:100]}]}

    def homeVideoContent(self, *args):
        try:
            html = self._fetch(f"{BASE_PATH}/")
            videos = self._parse_list(html)
            return {"page": 1, "pagecount": 999, "limit": 40, "total": len(videos), "list": videos}
        except Exception as e:
            print(f"[可乐影院 homeVideoContent错误] {e}")
            return {"page": 1, "pagecount": 1, "limit": 40, "total": 0, "list": []}

    def categoryContent(self, tid, pg, *args):
        try:
            try:
                page = int(pg) if pg else 1
            except (ValueError, TypeError):
                page = 1
            path = f"{BASE_PATH}/index.php/vod/type/id/{tid}.html"
            if page > 1:
                path = f"{BASE_PATH}/index.php/vod/type/id/{tid}/page/{page}.html"
            html = self._fetch(path)
            videos = self._parse_list(html)
            pagecount = 999 if len(videos) >= 20 else page
            return {"page": page, "pagecount": pagecount, "limit": 40, "total": len(videos), "list": videos}
        except Exception as e:
            print(f"[可乐影院 categoryContent错误] {e}")
            return {"page": 1, "pagecount": 1, "limit": 40, "total": 0, "list": []}

    def detailContent(self, ids, *args):
        try:
            if not ids:
                return {"list": []}
            if isinstance(ids, str):
                ids = [ids]
            videos = []
            for vod_id in ids:
                # 播放页就是详情页
                play_url = f"{BASE_PATH}/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
                html = self._fetch(play_url)
                if not html:
                    continue
                # 标题
                title = ""
                m = re.search(r'<title>([^<]+)</title>', html)
                if m:
                    title = m.group(1).replace(" - 可乐影院", "").strip()
                # 封面
                pic = ""
                m = re.search(r'<img[^>]*class="[^"]*vod[^"]*"[^>]*src="([^"]+)"', html, re.IGNORECASE)
                if not m:
                    m = re.search(r'var player_data.*?"pic"\s*:\s*"([^"]+)"', html)
                if m:
                    pic = m.group(1)
                # 播放地址（player_data.url）
                m = re.search(r'var player_data\s*=\s*(\{[^<]+?\})\s*</script>', html, re.DOTALL)
                play_urls = []
                if m:
                    try:
                        data = json.loads(m.group(1))
                        url = data.get("url", "")
                        if url and url.startswith("http"):
                            play_urls.append(f"第1集${url}")
                    except Exception:
                        # 降级：直接正则提取url
                        url_m = re.search(r'"url"\s*:\s*"(https?://[^"]+)"', m.group(1))
                        if url_m:
                            play_urls.append(f"第1集${url_m.group(1)}")
                # 未成年跳过
                if self._is_minor(title):
                    continue
                videos.append({
                    "vod_id": str(vod_id),
                    "vod_name": title[:80] if title else str(vod_id),
                    "vod_pic": pic,
                    "vod_content": "",
                    "vod_play_from": "可乐影院",
                    "vod_play_url": "#".join(play_urls) if play_urls else "",
                    "vod_remarks": "",
                })
            return {"list": videos}
        except Exception as e:
            print(f"[可乐影院 detailContent错误] {e}")
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None, *args):
        try:
            # id就是m3u8地址（detailContent中"第1集$url"的url部分）
            url = id
            return {
                "parse": 0,
                "jx": 0,
                "url": url,
                "header": {"User-Agent": UA, "Referer": self.base_url + "/"},
            }
        except Exception as e:
            print(f"[可乐影院 playerContent错误] {e}")
            return {"parse": 0, "jx": 0, "url": "", "header": {}}

    def searchContent(self, wd, pg, *args):
        try:
            try:
                page = int(pg) if pg else 1
            except (ValueError, TypeError):
                page = 1
            # 未成年搜索词直接返回空
            if self._is_minor(wd):
                return {"page": 1, "pagecount": 1, "limit": 40, "total": 0, "list": []}
            import urllib.parse
            path = f"{BASE_PATH}/index.php/vod/search.html?wd={urllib.parse.quote(wd)}"
            if page > 1:
                path += f"&page={page}"
            html = self._fetch(path)
            videos = self._parse_list(html)
            return {"page": page, "pagecount": 999, "limit": 40, "total": len(videos), "list": videos}
        except Exception as e:
            print(f"[可乐影院 searchContent错误] {e}")
            return {"page": 1, "pagecount": 1, "limit": 40, "total": 0, "list": []}

    def localProxy(self, path, *args):
        return [404, "text/plain", ""]

    def getDependence(self, *args):
        return ""


if __name__ == "__main__":
    s = Spider()
    s.init("{}")
    print("=== 首页 ===")
    home = s.homeContent()
    print(f"分类数: {len(home['class'])}, 视频数: {len(home['list'])}")
    for v in home['list'][:3]:
        print(f"  {v['vod_id']}: {v['vod_name'][:40]}")
    print("\n=== 分类(国产精品) ===")
    cat = s.categoryContent("20", "1")
    print(f"视频数: {len(cat['list'])}")
    print("\n=== 详情+播放 ===")
    if home['list']:
        vid = home['list'][0]['vod_id']
        detail = s.detailContent([vid])
        if detail['list']:
            d = detail['list'][0]
            print(f"标题: {d['vod_name'][:40]}")
            print(f"播放地址: {d['vod_play_url'][:80]}")
            play = s.playerContent("可乐影院", d['vod_play_url'].split('$')[1] if '$' in d['vod_play_url'] else "")
            print(f"playerContent url: {play['url'][:80]}")
    print("\n✅ 测试完成")
