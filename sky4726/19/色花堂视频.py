# -*- coding: utf-8 -*-
import re
import json
import base64
import urllib.parse
import urllib.request
import ssl

try:
    from base.spider import Spider as _BaseSpider
except ImportError:
    class _BaseSpider:
        def init(self, extend=""):
            pass


class Spider(_BaseSpider):
    name = "色花堂视频"
    host = "https://dyz.shtsp3.lol"
    path = "/cn/home/web/index.php"
    ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"

    def init(self, extend=""):
        self.categories = [
            {"type_id": "20", "type_name": "无码视频"},
            {"type_id": "21", "type_name": "强奸乱伦"},
            {"type_id": "22", "type_name": "人妻巨乳"},
            {"type_id": "23", "type_name": "国产视频"},
            {"type_id": "24", "type_name": "制服师生"},
            {"type_id": "25", "type_name": "有码视频"},
            {"type_id": "26", "type_name": "调教变态"},
            {"type_id": "27", "type_name": "出轨偷拍"},
            {"type_id": "28", "type_name": "三级伦理"},
        ]
        self.filter_dict = {}
        for c in self.categories:
            self.filter_dict[c["type_id"]] = [
                {"key": "sort", "name": "排序", "init": "", "value": [{"n": "最新", "v": "new"}, {"n": "热门", "v": "hot"}]}
            ]
        self._ssl_ctx = ssl.create_default_context()
        try:
            self._ssl_ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        except Exception:
            pass
        try:
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        except Exception:
            pass

    def getDependence(self):
        return ""

    def homeContent(self, *args):
        result = {"class": self.categories, "filters": self.filter_dict, "list": []}
        try:
            html = self._fetch(self.host + "/shtsp/")
            result["list"] = self._parse_list(html)
        except Exception:
            pass
        return result

    def homeVideoContent(self, *args):
        return {"page": 1, "pagecount": 1, "limit": 20, "total": 0, "list": []}

    def categoryContent(self, *args):
        tid = str(args[0]) if args else "20"
        pg = int(args[1]) if len(args) > 1 and args[1] else 1
        if isinstance(tid, dict):
            tid = tid.get("tid", "20")
            pg = int(tid.get("pg", 1))
        url = f"{self.host}{self.path}/vod/type/id/{tid}/page/{pg}.html"
        try:
            html = self._fetch(url)
            vod_list = self._parse_list(html)
            total = self._parse_total(html)
            pagecount = (total + 20 - 1) // 20 if total else 1
            return {"page": pg, "pagecount": pagecount, "limit": 20, "total": total, "list": vod_list}
        except Exception:
            return {"page": pg, "pagecount": 1, "limit": 20, "total": 0, "list": []}

    def detailContent(self, *args):
        ids = args[0] if args else []
        if isinstance(ids, str):
            ids = [ids]
        result_list = []
        for vid in ids:
            try:
                url = f"{self.host}{self.path}/vod/detail/id/{vid}.html"
                html = self._fetch(url)
                vod = self._parse_detail(html, str(vid))
                if vod:
                    result_list.append(vod)
            except Exception:
                continue
        return {"list": result_list}

    def searchContent(self, *args):
        wd = args[0] if args else ""
        pg = int(args[1]) if len(args) > 1 and args[1] else 1
        if isinstance(wd, dict):
            wd = wd.get("wd", "")
            pg = int(wd.get("pg", 1))
        url = f"{self.host}{self.path}/vod/search.html?wd={urllib.parse.quote(str(wd))}"
        try:
            html = self._fetch(url)
            vod_list = self._parse_list(html)
            return {"page": 1, "pagecount": 1, "limit": 20, "total": len(vod_list), "list": vod_list}
        except Exception:
            return {"page": 1, "pagecount": 1, "limit": 20, "total": 0, "list": []}

    def playerContent(self, *args):
        flag = args[0] if args else "ckplayer"
        id_str = args[1] if len(args) > 1 else ""

        # 【核心修复】已经是完整播放页 URL，直接使用，不再重拼
        if isinstance(id_str, str) and id_str.startswith("http"):
            url = id_str
        elif isinstance(id_str, str) and id_str.startswith("/"):
            url = self.host + id_str
        else:
            vid, sid, nid = "", "1", "1"
            if isinstance(id_str, str) and "/" in id_str:
                parts = id_str.split("/")
                for i, p in enumerate(parts):
                    if p == "id" and i + 1 < len(parts):
                        vid = parts[i + 1]
                    elif p == "sid" and i + 1 < len(parts):
                        sid = parts[i + 1]
                    elif p == "nid" and i + 1 < len(parts):
                        # 去掉 ".html" 后缀，避免拼出 .html.html
                        nid = parts[i + 1].split(".")[0]
            if not vid:
                vid = str(id_str)
            url = f"{self.host}{self.path}/vod/play/id/{vid}/sid/{sid}/nid/{nid}.html"

        try:
            html = self._fetch(url)
            play_url = self._extract_play_url(html)
            if play_url:
                fmt = "application/x-mpegURL" if ".m3u8" in play_url else "video/mp4"
                return {
                    "parse": 0,
                    "jx": 0,
                    "url": play_url,
                    "header": {
                        "User-Agent": self.ua,
                        "Referer": self.host + "/",
                        "Origin": self.host,
                    },
                    "format": fmt,
                }
        except Exception:
            pass
        return {"parse": 0, "jx": 0, "url": "", "header": {}, "format": "application/x-mpegURL"}

    def localProxy(self, param):
        if not param:
            return [404, "text/plain", ""]
        try:
            if isinstance(param, dict):
                url = param.get("url", "")
            else:
                url = str(param)
            if url.startswith("local://"):
                url = url.replace("local://", "https://", 1)
            if not url.startswith("http"):
                return [404, "text/plain", ""]
            req = urllib.request.Request(url, headers={
                "User-Agent": self.ua,
                "Referer": self.host + "/",
            })
            resp = urllib.request.urlopen(req, timeout=15, context=self._ssl_ctx)
            data = resp.read()
            ct = resp.headers.get("Content-Type", "image/jpeg")
            return [200, ct, data]
        except Exception:
            pass
        return [404, "text/plain", ""]

    def isVideoFormat(self, url):
        return url.endswith(".m3u8") or url.endswith(".mp4") or ".m3u8" in url

    def manualVideoCheck(self):
        return False

    def action(self, action):
        return ""

    def destroy(self):
        pass

    def _fetch(self, url):
        req = urllib.request.Request(url, headers={
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "identity",
        })
        resp = urllib.request.urlopen(req, timeout=20, context=self._ssl_ctx)
        raw = resp.read()
        for enc in ["utf-8", "gbk", "gb2312"]:
            try:
                return raw.decode(enc)
            except Exception:
                continue
        return raw.decode("utf-8", errors="replace")

    def _parse_list(self, html):
        vod_list = []
        seen = set()

        def _add(vid, title, pic):
            if vid in seen or not title:
                return
            seen.add(vid)
            if pic and not pic.startswith("http"):
                pic = urllib.parse.urljoin(self.host, pic)
            vod_list.append({
                "vod_id": vid, "vod_name": title, "vod_pic": pic,
                "vod_remarks": "", "vod_year": "", "vod_area": "",
                "vod_actor": "", "vod_director": "", "vod_content": "",
            })

        p1 = re.compile(
            r'<a[^>]*href="[^"]*vod/play/id/(\d+)[^"]*"[^>]*title="([^"]*)"[^>]*>\s*'
            r'<img[^>]*data-original="([^"]*)"',
            re.S
        )
        for m in p1.finditer(html):
            _add(m.group(1), m.group(2).strip(), m.group(3))
        p2 = re.compile(
            r'<a[^>]*href="[^"]*vod/play/id/(\d+)[^"]*"[^>]*>\s*'
            r'<img[^>]*src="([^"]*)"[^>]*title="([^"]*)"',
            re.S
        )
        for m in p2.finditer(html):
            _add(m.group(1), m.group(3).strip(), m.group(2))
        p3 = re.compile(
            r'<a[^>]*href="[^"]*vod/play/id/(\d+)[^"]*"[^>]*title="([^"]*)"',
            re.S
        )
        for m in p3.finditer(html):
            if m.group(1) not in seen:
                _add(m.group(1), m.group(2).strip(), "")
        return vod_list[:40]

    def _parse_total(self, html):
        m = re.search(r'共(\d+)条', html)
        if m:
            return int(m.group(1))
        pages = re.findall(r'vod/type/id/\d+/page/(\d+)\.html', html)
        if pages:
            return max(int(p) for p in pages) * 20
        return 0

    def _parse_detail(self, html, vid):
        title = ""
        t = re.search(r'<title>(.*?)</title>', html, re.S)
        if t:
            title = re.sub(r"<[^>]+>", "", t.group(1)).strip()
            title = re.sub(r"\s*-\s*色花堂视频\s*$", "", title)
        pic = ""
        pm = re.search(r'<img[^>]*data-original="([^"]*)"', html)
        if not pm:
            pm = re.search(r'<img[^>]*src="([^"]*upload/vod/[^"]*)"', html)
        if pm:
            pic = pm.group(1)
            if not pic.startswith("http"):
                pic = urllib.parse.urljoin(self.host, pic)
        content = ""
        cm = re.search(r'class="[^"]*(?:desc|content|intro)[^"]*"[^>]*>(.*?)</div>', html, re.S)
        if cm:
            content = re.sub(r"<[^>]+>", "", cm.group(1)).strip()
        play_from = "ckplayer"
        play_urls = []
        play_items = re.findall(r'vod/play/id/(\d+)/sid/(\d+)/nid/(\d+)', html)
        seen_nid = set()
        for item_vid, sid, nid in play_items:
            if item_vid == vid and nid not in seen_nid:
                seen_nid.add(nid)
                play_urls.append(f"第{nid}集${self.host}{self.path}/vod/play/id/{vid}/sid/{sid}/nid/{nid}.html")
        if not play_urls:
            play_urls.append(f"正片${self.host}{self.path}/vod/play/id/{vid}/sid/1/nid/1.html")
        return {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_year": "",
            "vod_area": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": content,
            "vod_play_from": play_from,
            "vod_play_url": "#".join(play_urls),
        }

    def _extract_play_url(self, html):
        # 1. 解析 MacCMS 播放器数据（支持嵌套 JSON）
        for key in ["player_aaaa", "player_data", "mac_player_data"]:
            m = re.search(rf'(?:var\s+)?{key}\s*=\s*(\{{[\s\S]*?\}})\s*[;<]', html)
            if not m:
                continue
            raw = m.group(1)
            url = ""
            encrypt = 0
            try:
                data = json.loads(raw)
                url = str(data.get("url") or "")
                try:
                    encrypt = int(data.get("encrypt") or 0)
                except Exception:
                    encrypt = 0
            except Exception:
                um = re.search(r'"url"\s*:\s*"([^"]*)"', raw)
                if um:
                    url = um.group(1)
                em = re.search(r'"encrypt"\s*:\s*(\d+)', raw)
                if em:
                    encrypt = int(em.group(1))

            if not url:
                continue

            # 处理 JSON 转义
            url = url.replace("\\/", "/").replace("\\u0026", "&")

            # encrypt=1 时 URL 是 base64
            if encrypt == 1:
                try:
                    url = base64.b64decode(url).decode("utf-8", errors="replace")
                except Exception:
                    pass

            # 相对路径补全
            if url.startswith("//"):
                url = "https:" + url
            elif url.startswith("/"):
                url = self.host + url
            elif not url.startswith("http"):
                try:
                    decoded = base64.b64decode(url).decode("utf-8", errors="replace")
                    if decoded.startswith("http"):
                        url = decoded
                except Exception:
                    pass
                if not url.startswith("http"):
                    url = urllib.parse.urljoin(self.host + "/", url)

            return url

        # 2. 回退：直接抓 m3u8 / mp4
        m = re.search(r'(https?:(?:\\/|/){2}[^\s"\'<>\\]+\.(?:m3u8|mp4)[^\s"\'<>\\]*)', html)
        if m:
            url = m.group(1).replace("\\/", "/")
            if url.startswith("//"):
                url = "https:" + url
            return url

        # 3. 最后回退：base64 形态的 m3u8
        m = re.search(r'"url"\s*:\s*"([^"]+)"', html)
        if m:
            cand = m.group(1)
            if cand.startswith("aHR0c"):
                try:
                    decoded = base64.b64decode(cand).decode("utf-8", errors="replace")
                    if decoded.startswith("http"):
                        return decoded
                except Exception:
                    pass

        return ""