# coding: utf-8
# 站点：你的秘书 (msa.91tk.lat)
# 类型：WordPress 成人视频聚合站
# 特点：文章列表分页，详情页iframe嵌入m3u8播放器，有广告分片需过滤
# 最后验证：2026-09-09

import re
import json
from urllib.parse import quote, urljoin, urlparse, unquote
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://msa.91tk.lat"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "自拍偷拍", "type_name": "自拍偷拍"},
            {"type_id": "中文字幕", "type_name": "中文字幕"},
            {"type_id": "国产传媒", "type_name": "国产传媒"},
            {"type_id": "日本无码", "type_name": "日本无码"},
            {"type_id": "抖阴视频", "type_name": "抖阴视频"},
            {"type_id": "网红主播", "type_name": "网红主播"},
            {"type_id": "探花系列", "type_name": "探花系列"},
            {"type_id": "cosplay", "type_name": "cosplay"},
            {"type_id": "黑丝诱惑", "type_name": "黑丝诱惑"},
            {"type_id": "门事件", "type_name": "门事件"},
            {"type_id": "激情动漫", "type_name": "激情动漫"},
            {"type_id": "三级伦理", "type_name": "三级伦理"},
            {"type_id": "素人搭讪", "type_name": "素人搭讪"},
            {"type_id": "VR视角", "type_name": "VR视角"},
            {"type_id": "SWAG", "type_name": "SWAG"},
            {"type_id": "AV解说", "type_name": "AV解说"},
        ]
        self.filters = {}

    def getName(self):
        return "你的秘书"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        return self.categoryContent("", "1", False, "")

    def _fetch_html(self, url):
        r = self.fetch(url, headers=self.headers, timeout=15)
        if not r or r.status_code != 200:
            return ""
        return r.text

    def _parse_list_page(self, html):
        items = []
        article_pat = r'<article[^>]*id="post-(\d+)"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?<h2[^>]*class="entry-title"[^>]*><a[^>]*href="[^"]*"[^>]*>([^<]+)</a></h2>.*?<span[^>]*class="posted-on[^"]*"[^>]*>.*?<time[^>]*datetime="[^"]*"[^>]*>([^<]+)</time>'
        for m in re.finditer(article_pat, html, re.S):
            pid = m.group(1)
            link = m.group(2)
            pic = m.group(3)
            title = m.group(4).strip()
            remark = m.group(5).strip()
            if not link.startswith("http"):
                link = urljoin(self.host, link)
            vod_id = "|$|".join([pid, title, pic, remark, link])
            items.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark
            })
        return items

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        if tid and tid not in ["", "全部"]:
            cat_encoded = quote(tid, safe="")
            url = f"{self.host}/k/category/{cat_encoded}/page/{page}/"
        else:
            if page == "1":
                url = f"{self.host}/"
            else:
                url = f"{self.host}/page/{page}/"

        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

        items = self._parse_list_page(html)

        pagecount = 1
        page_numbers = re.findall(r'<a[^>]*class="page-numbers"[^>]*>(\d+)</a>', html)
        if page_numbers:
            pagecount = max(int(p) for p in page_numbers)
        else:
            if re.search(r'class="next page-numbers"', html):
                pagecount = 2
            elif re.search(r'class="page-numbers dots"', html):
                last_num = re.search(r'<a[^>]*class="page-numbers"[^>]*>(\d+)</a>[^<]*</div>', html)
                if last_num:
                    pagecount = int(last_num.group(1))

        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20
        }

    @staticmethod
    def _norm_ids(ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    def _skeleton(self, vid, title="", pic="", remarks="解析中"):
        pid = str(vid).split("|$|")[0].replace("$", "|")
        return {"list": [{
            "vod_id": vid,
            "vod_name": title or "未知标题",
            "vod_pic": pic or "",
            "vod_remarks": remarks,
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": "播放$" + pid,
        }]}

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}

        try:
            ps = raw.split('|$|')
            pid = ps[0]
            old_name = ps[1] if len(ps) > 1 else ''
            old_pic = ps[2] if len(ps) > 2 else ''
            old_remark = ps[3] if len(ps) > 3 else ''
            play_page = ps[4] if len(ps) > 4 else ''

            if not play_page:
                return self._skeleton(raw, old_name, old_pic)

            html = self._fetch_html(play_page)
            if not html:
                return self._skeleton(raw, old_name, old_pic)

            m3u8_url = ""
            iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"', html)
            if iframe_match:
                proxy_url = iframe_match.group(1)
                if not proxy_url.startswith("http"):
                    proxy_url = urljoin(self.host, proxy_url)
                if "tt/t.php" in proxy_url:
                    url_param = re.search(r'[?&]url=([^&]+)', proxy_url)
                    if url_param:
                        m3u8_url = unquote(url_param.group(1))
                else:
                    m3u8_url = proxy_url

            if not m3u8_url:
                m3u8_match = re.search(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', html)
                if m3u8_match:
                    m3u8_url = m3u8_match.group(0)

            if not m3u8_url:
                return self._skeleton(raw, old_name, old_pic)

            vod = {
                "vod_id": raw,
                "vod_name": old_name or "视频",
                "vod_pic": old_pic or "",
                "vod_remarks": old_remark or "",
                "vod_content": old_remark or "",
                "vod_play_from": "播放",
                "vod_play_url": "播放$" + m3u8_url
            }
            return {"list": [vod]}

        except Exception as e:
            self.log({"detail": "exception", "ids": raw, "error": str(e)})
            return self._skeleton(raw)

    def searchContent(self, key, quick, pg="1"):
        page = pg or "1"
        encoded_key = quote(key, safe="")
        if page == "1":
            url = f"{self.host}/?s={encoded_key}"
        else:
            url = f"{self.host}/page/{page}/?s={encoded_key}"

        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": int(page)}

        items = self._parse_list_page(html)
        return {"list": items, "page": int(page)}

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id or "").strip()
        if "$" in play_url:
            parts = play_url.split("$", 1)
            if len(parts) == 2:
                play_url = parts[1]

        if not play_url:
            return {"parse": 0, "url": "", "header": {}}

        if play_url.endswith(".m3u8") or ".m3u8" in play_url:
            proxy_url = self._m3u8_proxy_url(play_url)
            return {
                "parse": 0,
                "url": proxy_url,
                "header": {
                    "User-Agent": self.headers.get("User-Agent", ""),
                    "Referer": self.host + "/"
                }
            }

        return {"parse": 0, "url": play_url, "header": {"User-Agent": self.headers.get("User-Agent", "")}}

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url or ""), safe="")

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def localProxy(self, param):
        target = unquote(str((param or {}).get("url", "") or ""))
        if not target or not target.startswith("http"):
            return [400, "text/plain", b"invalid url"]

        try:
            r = self.fetch(target, headers=self.headers, timeout=15)
            if not r or r.status_code != 200:
                return [502, "text/plain", b"fetch failed"]

            text = r.text
            if not text or "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]

            lines = [l.strip() for l in text.replace("\r", "").split("\n") if l.strip()]
            if not lines:
                return [502, "text/plain", b"empty m3u8"]

            # 多码率主表
            if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
                out = []
                for line in lines:
                    if line.startswith("#"):
                        out.append(line)
                    else:
                        child = urljoin(target, line)
                        out.append(self._m3u8_proxy_url(child))
                return [200, "application/vnd.apple.mpegurl", "\n".join(out).encode("utf-8")]

            # 单码率 - 提取正片目录锚点
            parsed = urlparse(target)
            path_parts = [p for p in parsed.path.split("/") if p]
            if len(path_parts) >= 3:
                anchor_dir = "/" + "/".join(path_parts[:3]) + "/"
            else:
                anchor_dir = "/" + "/".join(path_parts[:2]) + "/" if len(path_parts) >= 2 else "/"

            out = []
            pending = []
            removed = 0
            kept = 0

            for line in lines:
                if line.startswith("#EXTINF"):
                    pending = [line]
                    continue
                if pending and line.startswith("#"):
                    pending.append(line)
                    continue
                if pending:
                    seg_url = urljoin(target, line)
                    seg_path = urlparse(seg_url).path
                    if anchor_dir in seg_path:
                        seg_url_abs = urljoin(target, line)
                        out.extend(pending)
                        out.append(seg_url_abs)
                        kept += 1
                    else:
                        removed += 1
                    pending = []
                    continue
                # 处理标签行 - 补全URI中的相对路径
                if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
                    def repl(m):
                        uri = m.group(1)
                        if not uri.startswith("http"):
                            uri = urljoin(target, uri)
                        return 'URI="' + uri + '"'
                    out.append(re.sub(r'URI="([^"]+)"', repl, line))
                else:
                    out.append(line)

            if removed > 0:
                self.log({"m3u8_clean": "ad_filter", "removed": removed, "kept": kept, "anchor": anchor_dir})

            return [200, "application/vnd.apple.mpegurl", "\n".join(out).encode("utf-8")]

        except Exception as e:
            self.log({"m3u8_proxy_error": str(e)})
            return [500, "text/plain", str(e).encode("utf-8")]

    def destroy(self):
        pass