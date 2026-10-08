#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《遮天》· 爽上天 TVBox 爬虫 · WebHomeTV 兼容版
=============================================
WebHomeTV 兼容优化：
  - 显式设置 Content-Type: application/json; charset=utf-8
  - 避免 BOM
  - 确保响应格式完全兼容
  - 增加错误处理和调试信息

TVBox 标准接口
"""

import json
import re
import time
import random
import requests
from urllib import parse
from bs4 import BeautifulSoup
import sys

# ═══════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════
SITE_URL = "https://mya.sst9.casa"
HEADERS_POOL = [
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
]

_session = requests.Session()


def _ua():
    return random.choice(HEADERS_POOL)


def fetch(url, retries=2):
    h = {"User-Agent": _ua(), "Referer": SITE_URL}
    for i in range(retries):
        try:
            r = _session.get(url, headers=h, timeout=8)
            r.encoding = "utf-8"
            return r.text
        except Exception as e:
            sys.stderr.write(f"[fetch error] {e}\n")
            time.sleep(0.5)
    return ""


def _full_url(path):
    if not path or path.startswith("http"):
        return path
    return parse.urljoin(SITE_URL, path)


# ═══════════════════════════════════════════════════
# 红尘仙
# ═══════════════════════════════════════════════════
from base.spider import Spider
class Spider(Spider):

    def homeContent(self, filter=True):
        html = fetch(f"{SITE_URL}/sst/")
        if not html:
            return {"class": [], "list": []}

        soup = BeautifulSoup(html, "html.parser")

        classes = []
        seen_tid = set()
        for a in soup.find_all("a", href=re.compile(r'/vod/type/id/\d+')):
            m = re.search(r'/vod/type/id/(\d+)', a["href"])
            if m:
                tid = m.group(1)
                if tid not in seen_tid:
                    seen_tid.add(tid)
                    classes.append({"type_id": tid, "type_name": a.get_text(strip=True)})

        videos = []
        seen_id = set()
        for a in soup.find_all("a", href=re.compile(r'/vod/play/id/\d+')):
            m = re.search(r'/vod/play/id/(\d+)', a["href"])
            if not m:
                continue
            vid = m.group(1)
            if vid in seen_id:
                continue
            seen_id.add(vid)

            img = a.find("img")
            pic = img.get("data-original", "") if img else ""

            title = ""
            if img:
                title = img.get("align", "") or img.get("title", "") or ""
            if not title:
                h3 = a.find("h3")
                if h3:
                    for em in h3.find_all("em"):
                        em.decompose()
                    title = h3.get_text(strip=True)
            if not title:
                title = a.get("title", "") or a.get_text(strip=True)
            title = re.sub(r'\s*title\s*', ' ', title).strip()

            label = a.find("label")
            remark = label.get_text(strip=True) if label else ""

            videos.append({
                "vod_id": vid,
                "vod_name": title[:100],
                "vod_pic": _full_url(pic),
                "vod_remarks": remark,
            })

        return {"class": classes, "list": videos[:50]}

    def categoryContent(self, tid, pg=1, filter=True, extend=None):
        pg = int(pg)
        url = f"{SITE_URL}/cn/home/web/index.php/vod/type/id/{tid}.html?page={pg}"
        html = fetch(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1}

        soup = BeautifulSoup(html, "html.parser")
        up_list = soup.find("ul", class_="up-list")
        items = up_list.find_all("li") if up_list else []

        videos = []
        seen_id = set()
        for item in items:
            a = item.find("a")
            if not a:
                continue
            m = re.search(r'/vod/play/id/(\d+)', a.get("href", ""))
            if not m:
                continue
            vid = m.group(1)
            if vid in seen_id:
                continue
            seen_id.add(vid)

            img = item.find("img")
            pic = img.get("data-original", "") if img else ""

            title_el = item.find("p", class_="name") or item.find("h3")
            title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)

            videos.append({
                "vod_id": vid,
                "vod_name": title[:100],
                "vod_pic": _full_url(pic),
                "vod_remarks": "",
            })

        pagecount = 1
        pg_links = soup.find_all("a", href=re.compile(r'page=(\d+)'))
        if pg_links:
            pgs = [int(re.search(r'page=(\d+)', a["href"]).group(1)) for a in pg_links]
            pagecount = max(pgs) if pgs else 1

        return {"list": videos, "page": pg, "pagecount": pagecount}

    def detailContent(self, ids):
        vod_id = ids[0]
        url = f"{SITE_URL}/cn/home/web/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
        html = fetch(url)
        if not html:
            return {"list": []}

        m3u8_url = ""
        m = re.search(r'var\s+player_data\s*=\s*({[^<]+?})\s*;?\s*</script>', html)
        if m:
            try:
                data = json.loads(m.group(1).replace('\\"', '"').replace('\\/', '/'))
                m3u8_url = data.get("url", "")
            except:
                pass
        if not m3u8_url:
            m2 = re.search(r'"url"\s*:\s*"(https?:\\?/\\?/[^"]+?\.m3u8)"', html)
            if m2:
                m3u8_url = m2.group(1).replace('\\/', '/')

        title = ""
        title_tag = BeautifulSoup(html, "html.parser").find("title")
        if title_tag:
            title = re.split(r'[-_–—]', title_tag.get_text(strip=True))[0].strip()
            title = re.sub(r'^《|》$', '', title).strip()

        pic = ""
        og = BeautifulSoup(html, "html.parser").find("meta", property="og:image")
        if og:
            pic = og.get("content", "")

        return {
            "list": [{
                "vod_id": vod_id,
                "vod_name": title or f"视频_{vod_id}",
                "vod_pic": _full_url(pic),
                "vod_play_from": "m3u8",
                "vod_play_url": f"第1集${m3u8_url}" if m3u8_url else "",
            }]
        }

    def playerContent(self, flag, id, vipFlags=None):
        return {"parse": 0, "url": id, "header": ""}

    def searchContent(self, key, quick=False, pg="1"):
        pg = int(pg)
        encoded_key = parse.quote(key)
        search_url = f"{SITE_URL}/cn/home/web/index.php/vod/search.html?wd={encoded_key}&page={pg}"
        html = fetch(search_url)
        if not html:
            return {"list": [], "page": pg}

        soup = BeautifulSoup(html, "html.parser")
        videos = []
        seen_id = set()

        for a in soup.find_all("a", href=re.compile(r'/vod/play/id/\d+')):
            m = re.search(r'/vod/play/id/(\d+)', a["href"])
            if not m:
                continue
            vid = m.group(1)
            if vid in seen_id:
                continue
            seen_id.add(vid)

            img = a.find("img")
            pic = img.get("data-original", "") if img else ""

            title = ""
            if img:
                title = img.get("align", "") or img.get("title", "") or ""
            if not title:
                h3 = a.find("h3")
                if h3:
                    for em in h3.find_all("em"):
                        em.decompose()
                    title = h3.get_text(strip=True)
            if not title:
                title = a.get("title", "") or a.get_text(strip=True)
            title = re.sub(r'\s*title\s*', ' ', title).strip()

            videos.append({
                "vod_id": vid,
                "vod_name": title[:100],
                "vod_pic": _full_url(pic),
                "vod_remarks": "搜索",
            })

        return {"list": videos, "page": pg}

    def init(self, extend=""):
        return True

    def isVideoFormat(self, url):
        return any(fmt in url.lower() for fmt in [".m3u8", ".mp4", ".flv", ".mkv", ".ts"])

    def manualVideoCheck(self):
        return False


# ═══════════════════════════════════════════════════
# WebHomeTV 兼容 HTTP 服务器
# ═══════════════════════════════════════════════════
def start_http_server(port=8080):
    """启动简单的 HTTP 服务器供 WebHomeTV 调用"""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from socketserver import ThreadingMixIn

    class Handler(BaseHTTPRequestHandler):
        spider = Spider()

        def do_GET(self):
            try:
                # 解析路径
                path = self.path
                sys.stderr.write(f"[HTTP] {path}\n")

                # 路由
                if path.startswith("/home") or path == "/":
                    data = self.spider.homeContent()
                elif path.startswith("/category"):
                    # /category/20/1
                    parts = path.strip("/").split("/")
                    tid = parts[1] if len(parts) > 1 else "20"
                    pg = parts[2] if len(parts) > 2 else "1"
                    data = self.spider.categoryContent(tid, pg)
                elif path.startswith("/detail"):
                    # /detail/1175380
                    parts = path.strip("/").split("/")
                    vid = parts[1] if len(parts) > 1 else ""
                    data = self.spider.detailContent([vid])
                elif path.startswith("/play"):
                    # /play/m3u8/url
                    parts = path.strip("/").split("/")
                    flag = parts[1] if len(parts) > 1 else "m3u8"
                    vid = parts[2] if len(parts) > 2 else ""
                    data = self.spider.playerContent(flag, vid)
                elif path.startswith("/search"):
                    # /search/关键词
                    parts = path.strip("/").split("/", 1)
                    key = parts[1] if len(parts) > 1 else ""
                    data = self.spider.searchContent(key)
                else:
                    data = {"class": [], "list": []}

                # 返回 JSON
                result = json.dumps(data, ensure_ascii=False)
                self.send_response(200)
                # WebHomeTV 需要明确的 Content-Type
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(result.encode('utf-8'))))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(result.encode('utf-8'))

            except Exception as e:
                sys.stderr.write(f"[HTTP error] {e}\n")
                self.send_response(500)
                self.end_headers()

        def log_message(self, format, *args):
            # 静默日志
            pass

    class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
        pass

    server = ThreadedHTTPServer(("0.0.0.0", port), Handler)
    sys.stderr.write(f"[HTTP] 服务器启动在 http://0.0.0.0:{port}\n")
    sys.stderr.write(f"[HTTP] WebHomeTV 配置: http://你的IP:{port}/home\n")
    server.serve_forever()


if __name__ == "__main__":
    spider = Spider()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "home":
            output_json(spider.homeContent())
        elif cmd == "category":
            tid = sys.argv[2] if len(sys.argv) > 2 else "20"
            pg = sys.argv[3] if len(sys.argv) > 3 else "1"
            output_json(spider.categoryContent(tid, pg))
        elif cmd == "detail":
            ids = sys.argv[2] if len(sys.argv) > 2 else ""
            output_json(spider.detailContent([ids]))
        elif cmd == "play":
            flag = sys.argv[2] if len(sys.argv) > 2 else "m3u8"
            vid = sys.argv[3] if len(sys.argv) > 3 else ""
            output_json(spider.playerContent(flag, vid))
        elif cmd == "search":
            key = sys.argv[2] if len(sys.argv) > 2 else ""
            output_json(spider.searchContent(key))
        elif cmd == "test":
            print("=" * 50)
            print("爽上天 TVBox 爬虫测试")
            print("=" * 50)
            home = spider.homeContent()
            print(f"class: {len(home.get('class', []))}")
            print(f"list:  {len(home.get('list', []))}")
            if home.get("list"):
                print(f"sample: {home['list'][0]['vod_name'][:30]}")
            print("OK")
        elif cmd == "serve":
            # 启动 HTTP 服务器
            port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
            start_http_server(port)
        else:
            print("Usage: python3 sst_tvbox.py [home|category|detail|search|test|serve]")
    else:
        output_json({"class": [], "list": []})
