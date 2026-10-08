# -*- coding: utf-8 -*-
import html as html_lib
import re
import urllib.parse
import urllib.request
import http.cookiejar

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    name = "Jable新版"
    BASE_URL = "https://jable.sbs"
    FALLBACK_URLS = ["https://jable.sbs", "https://jable.tv"]
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    TIMEOUT = 15

    def __init__(self):
        super().__init__()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

    def getName(self):
        return self.name

    def init(self, extend=""):
        return None

    def description(self):
        return self.name

    def isVideoFormat(self, url):
        return ".m3u8" in (url or "") or ".mp4" in (url or "")

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [404, "text/plain", "Not Found"]

    def _classes(self):
        # 与老版 jable.py 保持一致
        return [
            {"type_id": "latest-updates", "type_name": "最近更新"},
            {"type_id": "hot", "type_name": "热门影片"},
            {"type_id": "categories/chinese-subtitle", "type_name": "中文字幕"},
            {"type_id": "new-release", "type_name": "全新上市"},
            {"type_id": "categories", "type_name": "主题&标签"},
        ]

    def homeContent(self, filter):
        result = self._list_result(self._fetch(self.BASE_URL + "/latest-updates/"), 1)
        result["class"] = self._classes()
        return result

    def homeVideoContent(self):
        return {"list": self._parse_list(self._fetch(self.BASE_URL + "/latest-updates/") or "")}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg or 1)
        path = str(tid or "latest-updates").strip("/")

        # ── 主题&标签：返回文件夹列表 ──
        if path == "categories":
            return self._categories_folder()

        url = self._page_url(path, page)
        html = self._fetch(url)
        if not html or self._is_gate(html):
            return {"page": page, "pagecount": 0, "limit": 24, "total": 0, "list": []}
        return self._list_result(html, page)

    def _categories_folder(self):
        """返回主题分类和标签列表作为文件夹"""
        result = {"list": [], "page": 1, "pagecount": 1, "limit": 200, "total": 200}

        # 尝试从 /categories/ 页面抓取主题
        cat_html = self._fetch(self.BASE_URL + "/categories/")
        if cat_html and not self._is_gate(cat_html):
            for m in re.finditer(
                r'<a[^>]*href=["\'](?:https?://jable\.(?:sbs|tv))?(/categories/([^"\']+))["\'][^>]*>'
                r'([\s\S]*?)</a>',
                cat_html, re.I | re.S
            ):
                cat_path = m.group(1).strip("/")
                block = m.group(3)
                pic = ""
                img_m = re.search(r'<img[^>]*src=["\']([^"\']+)["\']', block, re.I)
                if img_m:
                    pic = img_m.group(1)
                    if pic.startswith("//"):
                        pic = "https:" + pic
                name = ""
                count = ""
                center = re.search(r'<div[^>]*class=["\'][^"\']*absolute-center[^"\']*["\'][^>]*>(.*?)</div>', block, re.I | re.S)
                if center:
                    center_text = center.group(1)
                    name = re.sub(r'<small[^>]*>.*?</small>', '', center_text, flags=re.I).strip()
                    cnt_m = re.search(r'<small[^>]*>\s*([\d,]+)\s*(?:部|个)?\s*</small>', center_text, re.I)
                    if cnt_m:
                        count = cnt_m.group(1) + "部"
                if not name:
                    name = self._clean(m.group(4) if m.lastindex >= 4 else "")
                if name:
                    result["list"].append({
                        "vod_id": cat_path,
                        "vod_name": self._clean(name),
                        "vod_pic": pic,
                        "vod_remarks": count or "主题",
                        "vod_tag": "folder",
                        "style": {"type": "rect", "ratio": 1.4}
                    })

        # 兜底：静态主题数据
        if not any(item["vod_id"].startswith("categories/") for item in result["list"]):
            static_cats = [
                ("categories/chinese-subtitle", "中文字幕",
                 "https://imgcdn18.piccdn1.cfd/assets-cdn.jable.tv/contents/categories/12/s1_chinese-subtitle.jpg", "20843部"),
                ("categories/roleplay", "角色剧情",
                 "https://imgcdn18.piccdn1.cfd/assets-cdn.jable.tv/contents/categories/9/s1_roleplay.jpg", "31733部"),
                ("categories/uniform", "制服诱惑",
                 "https://imgcdn18.piccdn1.cfd/assets-cdn.jable.tv/contents/categories/10/s1_uniform.jpg", "11883部"),
                ("categories/pantyhose", "丝袜美腿",
                 "https://imgcdn18.piccdn1.cfd/assets-cdn.jable.tv/contents/categories/3/s1_pantyhose.jpg", "7126部"),
                ("categories/bdsm", "主奴调教",
                 "https://imgcdn18.piccdn1.cfd/assets-cdn.jable.tv/contents/categories/14/s1_sm.jpg", "5312部"),
                ("categories/sex-only", "直接开啪",
                 "https://imgcdn18.piccdn1.cfd/assets-cdn.jable.tv/contents/categories/13/s1_sex-only.jpg", "6516部"),
                ("categories/insult", "凌辱快感",
                 "https://imgcdn18.piccdn1.cfd/assets-cdn.jable.tv/contents/categories/11/s1_rape.jpg", "3538部"),
                ("categories/pov", "男友视角",
                 "https://imgcdn18.piccdn1.cfd/assets-cdn.jable.tv/contents/categories/5/s1_pov.jpg", "4063部"),
                ("categories/groupsex", "多P群交",
                 "https://imgcdn18.piccdn1.cfd/assets-cdn.jable.tv/contents/categories/4/s1_groupsex.jpg", "5406部"),
                ("categories/lesbian", "女同欢愉",
                 "https://imgcdn18.piccdn1.cfd/assets-cdn.jable.tv/contents/categories/2/s1_lesbian.jpg", "425部"),
                ("categories/uncensored", "无码解放",
                 "https://imgcdn18.piccdn1.cfd/assets-cdn.jable.tv/contents/categories/6/s1_uncensored.jpg", "266部"),
                ("categories/private-cam", "盗摄偷拍",
                 "https://imgcdn18.piccdn1.cfd/assets-cdn.jable.tv/contents/categories/8/s1_s1_private-cam.jpg", "520部"),
            ]
            for cid, cname, cpic, ccount in static_cats:
                result["list"].append({
                    "vod_id": cid,
                    "vod_name": cname,
                    "vod_pic": cpic,
                    "vod_remarks": ccount,
                    "vod_tag": "folder",
                    "style": {"type": "rect", "ratio": 1.4}
                })

        # 追加标签列表
        tags_html = self._fetch(self.BASE_URL + "/latest-updates/")
        if tags_html and not self._is_gate(tags_html):
            seen = set()
            for m in re.finditer(r'href=["\'](?:https?://jable\.(?:sbs|tv))?(/tags/[^"\']+)["\'][^>]*>([^<]+)</a>', tags_html, re.I):
                tag_path = m.group(1).strip("/")
                tag_name = self._clean(m.group(2))
                if tag_path not in seen and tag_name:
                    seen.add(tag_path)
                    result["list"].append({
                        "vod_id": tag_path,
                        "vod_name": tag_name,
                        "vod_pic": "",
                        "vod_remarks": "标签",
                        "vod_tag": "folder",
                        "style": {"type": "rect", "ratio": 1}
                    })

        return result

    def searchContent(self, key, quick, pg="1"):
        page = int(pg or 1)
        q = urllib.parse.quote(str(key or ""))
        url = f"{self.BASE_URL}/search/?q={q}"
        if page > 1:
            url += f"&page={page}"
        return self._list_result(self._fetch(url), page)

    def detailContent(self, ids):
        result = {"list": []}
        value = ids[0] if isinstance(ids, list) and ids else ids
        url = self._absolute(str(value or ""))
        if not url:
            return result
        page = self._fetch(url)
        if not page or self._is_gate(page):
            return result

        title = self._first(page, r'<section[^>]+class=["\'][^"\']*video-info[^"\']*["\'][^>]*>.*?<h4[^>]*>(.*?)</h4>')
        title = self._clean(title) or self._first(page, r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)')
        title = self._clean(title) or self._first(page, r'<title[^>]*>(.*?)</title>')
        pic = self._first(page, r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)')
        pic = pic or self._first(page, r'<video[^>]+poster=["\']([^"\']+)')
        actor = re.findall(r'<a[^>]+class=["\'][^"\']*model[^"\']*["\'][^>]*>.*?<span[^>]+(?:title|data-original-title)=["\']([^"\']+)', page, re.S | re.I)
        actor = ",".join(dict.fromkeys(self._clean(x) for x in actor if self._clean(x)))
        publish = self._first(page, r'上市于\s*([^<]+)')
        quality = self._first(page, r'<div[^>]+class=["\'][^"\']*header-right[^"\']*["\'][^>]*>.*?<h6[^>]*>(.*?)</h6>')
        # 新版页面没有专门的剧情简介，用标题作为简介
        result["list"].append({
            "vod_id": url,
            "vod_name": title or url.rstrip("/").split("/")[-1],
            "vod_pic": self._absolute(pic),
            "type_name": "",
            "vod_year": self._clean(publish),
            "vod_area": "日本",
            "vod_remarks": self._clean(quality) or "",
            "vod_actor": actor,
            "vod_director": "",
            "vod_content": title or "",
            "vod_play_from": "JableTV",
            "vod_play_url": "正片$" + url,
        })
        return result

    def playerContent(self, flag, id, vipFlags):
        value = str(id or "")
        if self.isVideoFormat(value):
            return {"parse": 0, "url": value, "header": {"User-Agent": self.HEADERS["User-Agent"]}}
        url = self._absolute(value)
        page = self._fetch(url) if url else ""
        m3u8 = self._first(page, r'\bvar\s+hlsUrl\s*=\s*["\']([^"\']+\.m3u8(?:\?[^"\']*)?)["\']')
        if not m3u8:
            m3u8 = self._first(page, r'["\'](https?://[^"\']+\.m3u8(?:\?[^"\']*)?)["\']')
        if m3u8:
            return {"parse": 0, "url": m3u8, "header": {"User-Agent": self.HEADERS["User-Agent"], "Referer": url}}
        return {"parse": 1, "url": value, "header": {"User-Agent": self.HEADERS["User-Agent"]}}

    def _list_result(self, page, number):
        data = self._parse_list(page or "") if page and not self._is_gate(page) else []
        count = self._page_count(page or "")
        return {"page": number, "pagecount": count, "limit": 24, "total": count * 24, "list": data}

    def _parse_list(self, page):
        result, seen = [], set()
        cards = re.findall(
            r'<div[^>]+class=["\'][^"\']*\bcol-6\b[^"\']*\bcol-sm-4\b[^"\']*["\'][^>]*>.*?(?=<div[^>]+class=["\'][^"\']*\bcol-6\b[^"\']*\bcol-sm-4\b|</section>)',
            page or "", re.S | re.I,
        )
        for card in cards:
            links = re.findall(r'<a[^>]+href=["\']([^"\']*/videos/[^"\']+)["\'][^>]*>', card, re.I)
            href = links[-1] if links else ""
            title = self._first(card, r'<h6[^>]*class=["\'][^"\']*title[^"\']*["\'][^>]*>.*?<a[^>]*>(.*?)</a>')
            pic = self._first(card, r'<img[^>]+(?:data-src|data-original|src)=["\']([^"\']+)["\']')
            duration = self._first(card, r'class=["\'][^"\']*absolute-bottom-right[^"\']*["\'][^>]*>.*?(\d+:\d+(?::\d+)?)')
            if not href or not title:
                continue
            url = self._absolute(href)
            if url in seen:
                continue
            seen.add(url)
            if "placeholder" in pic:
                pic = self._first(card, r'data-src=["\']([^"\']+)["\']') or pic
            result.append({"vod_id": url, "vod_name": self._clean(title), "vod_pic": self._absolute(pic), "vod_remarks": duration})
        return result

    def _page_url(self, path, page):
        """新版翻页使用路径格式 /path/2/"""
        path = path.strip("/") or "latest-updates"
        if page > 1:
            return f"{self.BASE_URL}/{path}/{page}/"
        return f"{self.BASE_URL}/{path}/"

    def _page_count(self, page_html):
        """从分页链接中提取最大页码"""
        # 格式 /latest-updates/2/ 等
        nums = re.findall(r'/' + re.escape("latest-updates") + r'/(\d+)/', page_html, re.I)
        if not nums:
            nums = re.findall(r'/(?:hot|categories/.+?|tags/.+?|new-release)/(\d+)/', page_html, re.I)
        if not nums:
            nums = re.findall(r'<a[^>]+href=["\'][^"\']*/(\d+)/["\']', page_html, re.I)
        if nums:
            return max(int(x) for x in nums)
        # 兼容查询参数格式
        nums2 = re.findall(r'[?&]page=(\d+)', page_html, re.I)
        if nums2:
            return max(int(x) for x in nums2)
        return 1

    def _fetch(self, url):
        for candidate in self._candidates(url):
            try:
                req = urllib.request.Request(candidate, headers=self.HEADERS)
                with self._opener.open(req, timeout=self.TIMEOUT) as resp:
                    return resp.read().decode("utf-8", "ignore")
            except Exception as exc:
                print("[Jable] fetch failed:", candidate, exc)
        return ""

    def _candidates(self, url):
        if not url:
            return []
        parsed = urllib.parse.urlparse(url)
        result = [url]
        for host in self.FALLBACK_URLS:
            candidate = host.rstrip("/") + parsed.path + (("?" + parsed.query) if parsed.query else "")
            if candidate not in result:
                result.append(candidate)
        return result

    def _absolute(self, value):
        return urllib.parse.urljoin(self.BASE_URL + "/", value or "") if value else ""

    def _is_gate(self, page):
        return "继续访问" in page and ("/enter" in page or "continue-button" in page)

    def _first(self, text, pattern):
        match = re.search(pattern, text or "", re.S | re.I)
        return match.group(1).strip() if match else ""

    def _clean(self, value):
        value = html_lib.unescape(value or "")
        value = re.sub(r"<[^>]+>", "", value)
        return re.sub(r"\s+", " ", value).strip()
