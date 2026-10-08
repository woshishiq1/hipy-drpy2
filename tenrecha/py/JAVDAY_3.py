# -*- coding: utf-8 -*-
# javday.app TVBox/FongMi base.spider (Python 3)
# 站点结构: 分类 /category/{slug}/page/{N}/ | 标签 /label/{slug}/{N}/
# 视频 /videos/{ID}/ | 搜索 /search/wd/{kw}/{N}/
# 播放: 详情页 HTML 注释中 Ep{N}${m3u8_url} 格式
# 二级: /label/groups/ -> /category/{slug}/page/{N}/

import re
import sys
import json
from urllib.parse import urljoin, quote

sys.path.append('..')
from base.spider import Spider

# ==================== 分类 ====================

_CATEGORIES = [
    {"type_name": "新作上市", "type_id": "new-release"},
    {"type_name": "有碼", "type_id": "censored"},
    {"type_name": "無碼", "type_id": "uncensored"},
    {"type_name": "國產AV", "type_id": "chinese-av"},
    {"type_name": "無碼流出", "type_id": "uncensored-leaked"},
    {"type_name": "杏吧", "type_id": "sex8"},
    {"type_name": "HongKongDoll", "type_id": "hongkongdoll"},
    {"type_name": "AI短劇", "type_id": "aiav"},
    {"type_name": "最近更新", "type_id": "label_new"},
    {"type_name": "人氣系列", "type_id": "label_hot"},
    {"type_name": "國產AV廠商", "type_id": "label_groups"},
    {"type_name": "麻豆傳媒映畫", "type_id": "tv_madou"},
    {"type_name": "天美傳媒", "type_id": "tv_timi"},
    {"type_name": "果凍傳媒", "type_id": "tv_91zhipianchang"},
    {"type_name": "星空無限傳媒", "type_id": "tv_xingkong"},
    {"type_name": "皇家華人", "type_id": "tv_royalasianstudio"},
    {"type_name": "蜜桃影像傳媒", "type_id": "tv_mtgw"},
    {"type_name": "精東影業", "type_id": "tv_jdav"},
    {"type_name": "TWAV", "type_id": "tv_twav"},
    {"type_name": "Psychoporn-TW", "type_id": "tv_psychoporn-tw"},
    {"type_name": "JVID", "type_id": "tv_jvid"},
    {"type_name": "茉莉社", "type_id": "tv_luolisheus"},
    {"type_name": "糖心VLOG", "type_id": "tv_txvlog"},
]

_TV_SLUGS = {
    "tv_madou": "madou", "tv_timi": "timi", "tv_91zhipianchang": "91zhipianchang",
    "tv_xingkong": "xingkong", "tv_royalasianstudio": "royalasianstudio",
    "tv_mtgw": "mtgw", "tv_jdav": "jdav", "tv_twav": "twav",
    "tv_psychoporn-tw": "psychoporn-tw", "tv_jvid": "jvid",
    "tv_luolisheus": "luolisheus", "tv_txvlog": "txvlog",
}

_FOLDER_TYPES = {"label_groups"}

# ==================== 正则 ====================

# 视频卡片: href + class="videoBox" + 封面 url(...) + 时长(可选) + 标题
_RE_CARD = re.compile(
    r'<a[^>]*href="(/videos/[^"]+)"[^>]*class="videoBox"[^>]*>'
    r'[\s\S]*?background-image:\s*url\(([^)]+)\)'
    r'(?:[\s\S]*?<span class="videoBox-time"[^>]*>([^<]*)</span>)?'
    r'[\s\S]*?<span class="title"[^>]*>([^<]+)</span>',
    re.I)

# 降级: 仅需 href + class="videoBox" + 封面 + 标题
_RE_CARD_SIMPLE = re.compile(
    r'<a[^>]*href="(/videos/[^"]+)"[^>]*class="videoBox"[^>]*>'
    r'[\s\S]*?background-image:\s*url\(([^)]+)\)'
    r'[\s\S]*?<span class="title"[^>]*>([^<]+)</span>',
    re.I)

# 二级厂商卡片: 提取 category/ 后的 slug + title 属性 + 封面
_RE_FOLDER_CARD = re.compile(
    r'<a\s[^>]*?href="https?://[^"]*?/category/([^"/]+)/?"[^>]*?title="([^"]+)"[^>]*?>'
    r'[\s\S]*?background-image:\s*url\(([^)]+)\)',
    re.I)

# 播放地址: <!-- Ep1-4$url1#Ep5$url2#... -->
_RE_PLAY = re.compile(
    r'<!--\s*((?:[A-Za-z0-9._-]+\$https?://[^\s"#]+\.m3u8[^\s"#]*'
    r'(?:#[A-Za-z0-9._-]+\$https?://[^\s"#]+\.m3u8[^\s"#]*)*))\s*-->',
    re.I)

_RE_M3U8 = re.compile(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', re.I)


class Spider(Spider):

    def init(self, extend=""):
        self.HOST = "https://javday.app"
        if extend and str(extend).startswith("http"):
            self.HOST = str(extend).rstrip("/")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/126.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.HOST + "/",
        }

    def getName(self):
        return "JAVDAY"

    def isAdult(self):
        return 1

    # ==================== 工具 ====================

    def _resp_text(self, r):
        return r.text if hasattr(r, "text") else r.content.decode("utf-8", errors="ignore")

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip().strip('"\'').replace("&amp;", "&")
        url = re.sub(r'[);]+$', '', url).strip('"\'')
        if url.startswith("//"):
            return "https:" + url
        if not url.startswith("http"):
            return urljoin(self.HOST, url)
        return url

    def _get(self, path, timeout=10):
        url = path if str(path).startswith("http") else self.HOST + "/" + str(path).lstrip("/")
        try:
            r = self.fetch(url, headers=self.headers, timeout=timeout, allow_redirects=True)
            return self._resp_text(r)
        except Exception:
            return ""

    def _result(self, lst, pg, pagecount, total=99999):
        return {"list": lst, "page": pg, "pagecount": pagecount, "limit": 30, "total": total}

    @staticmethod
    def _clean(s):
        return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', (s or '').replace('&nbsp;', ' '))).strip()

    def _clickable(self, text):
        if not text or text == "N/A":
            return text or ""
        cr = json.dumps({"type_id": f"search@{text}", "type_name": text}, ensure_ascii=False, separators=(",", ":"))
        return f"[a=cr:{cr}/]{text}[/a]"

    def _clickable_tag(self, text):
        """标签跳转: 走 /search/class/{kw}/page/{N}/"""
        if not text or text == "N/A":
            return text or ""
        cr = json.dumps({"type_id": f"class@{text}", "type_name": text}, ensure_ascii=False, separators=(",", ":"))
        return f"[a=cr:{cr}/]{text}[/a]"

    def _clickable_actor(self, text):
        """女优跳转: 走 /search/actor/{kw}/page/{N}/"""
        if not text or text == "N/A":
            return text or ""
        cr = json.dumps({"type_id": f"actor@{text}", "type_name": text}, ensure_ascii=False, separators=(",", ":"))
        return f"[a=cr:{cr}/]{text}[/a]"

    def _field(self, html, cls):
        m = re.search(rf'<span class="{cls}"[^>]*>([\s\S]*?)</span>', html, re.I)
        return self._clean(m.group(1)) if m else ""

    def _field_actors(self, html):
        m = re.search(r'<span class="vod_actor"[^>]*>([\s\S]*?)</span>', html, re.I)
        if not m:
            return []
        return [v for v in (self._clean(a).strip() for a in
                re.findall(r'<a[^>]*>([^<]+)</a>', m.group(1), re.I)) if v]

    def _field_tags(self, html):
        """从 tag span 提取所有标签名 (標籤: 中出、護士、口交...)"""
        m = re.search(r'<span class="tag"[^>]*>([\s\S]*?)</span>', html, re.I)
        if not m:
            return []
        return [v for v in (self._clean(a).strip() for a in
                re.findall(r'<a[^>]*>([^<]+)</a>', m.group(1), re.I)) if v and v != "N/A"]

    def _re(self, pattern, text, flags=re.I, exclude=None):
        for m in re.finditer(pattern, text, flags | re.S):
            val = m.group(1).strip()
            if exclude and exclude in val:
                continue
            return val
        return ""

    # ==================== 首页 ====================

    def homeContent(self, filter):
        return {"class": _CATEGORIES, "filters": {}}

    def homeVideoContent(self):
        try:
            html = self._get("/label/new/")
            if len(html) < 500:
                return {"list": []}
            return {"list": self._parse_list(html)}
        except:
            return {"list": []}

    # ==================== 分类 ====================

    def categoryContent(self, tid, pg, filter, extend):
        pg_str, pg_num = str(pg), int(pg) if str(pg).isdigit() else 1
        DEFAULT = self._result([], pg_str, pg_num)
        try:
            # 女优路由: actor@{text} -> /search/actor/{kw}/page/{N}/
            if isinstance(tid, str) and tid.startswith("actor@"):
                kw = tid[6:]
                ekw = quote(kw, safe='')
                path = f"/search/actor/{ekw}/" if pg_num <= 1 else f"/search/actor/{ekw}/page/{pg_num}/"
                html = self._get(path)
                if len(html) < 500:
                    return DEFAULT
                videos = self._parse_list(html)
                return self._result(videos, pg_str, self._pagecount(html, pg_num) if videos else pg_num)

            # 标签路由: class@{text} -> /search/class/{kw}/page/{N}/
            if isinstance(tid, str) and tid.startswith("class@"):
                kw = tid[6:]
                path = f"/search/class/{quote(kw, safe='')}/" if pg_num <= 1 else f"/search/class/{quote(kw, safe='')}/page/{pg_num}/"
                html = self._get(path)
                if len(html) < 500:
                    return DEFAULT
                videos = self._parse_list(html)
                return self._result(videos, pg_str, self._pagecount(html, pg_num) if videos else pg_num)

            # 二级路由: 点击厂商 folder 后进入视频列表
            if isinstance(tid, str) and tid.startswith("\u4e8c\u7ea7@"):
                base_url = tid[3:]
                if pg_num <= 1:
                    path = base_url
                else:
                    path = base_url.rstrip("/") + f"/page/{pg_num}/"
                html = self._get(path)
                if len(html) < 500:
                    return DEFAULT
                videos = self._parse_list(html)
                return self._result(videos, pg_str, self._pagecount(html, pg_num) if videos else pg_num)

            # 二级入口 (label_groups): 厂商大全 folder 列表
            if tid in _FOLDER_TYPES:
                slug = tid[6:]
                path = f"/label/{slug}/" if pg_num <= 1 else f"/label/{slug}/{pg_num}/"
                html = self._get(path)
                if len(html) < 500:
                    return DEFAULT
                folders = self._parse_folder_list(html)
                if folders:
                    return self._result(folders, pg_str, self._pagecount(html, pg_num), len(folders))
                videos = self._parse_list(html)
                return self._result(videos, pg_str, self._pagecount(html, pg_num) if videos else pg_num)

            # 厂商直通 -> /category/{slug}/page/{N}/
            if tid in _TV_SLUGS:
                slug = _TV_SLUGS[tid]
                path = f"/category/{slug}/" if pg_num <= 1 else f"/category/{slug}/page/{pg_num}/"
                html = self._get(path)
                if len(html) < 500:
                    return DEFAULT
                videos = self._parse_list(html)
                return self._result(videos, pg_str, self._pagecount(html, pg_num) if videos else pg_num)

            # 普通分类/标签
            if tid.startswith("label_"):
                slug = tid[6:]
                path = f"/label/{slug}/" if pg_num <= 1 else f"/label/{slug}/{pg_num}/"
            else:
                path = f"/category/{tid}/" if pg_num <= 1 else f"/category/{tid}/page/{pg_num}/"

            html = self._get(path)
            if len(html) < 500:
                return DEFAULT
            videos = self._parse_list(html)
            return self._result(videos, pg_str, self._pagecount(html, pg_num) if videos else pg_num)
        except:
            return DEFAULT

    # ==================== 列表解析 ====================

    def _parse_list(self, html):
        videos, seen = [], set()
        for m in _RE_CARD.finditer(html):
            href, pic, remark, title = m.groups()
            vod_id = href.strip()
            if vod_id in seen:
                continue
            seen.add(vod_id)
            videos.append({
                "vod_id": vod_id,
                "vod_name": self._clean(title),
                "vod_pic": self._fix_url(pic),
                "vod_remarks": self._clean(remark) or "",
            })
        # 降级: 主正则未匹配时用简化正则
        if not videos:
            for m in _RE_CARD_SIMPLE.finditer(html):
                href, pic, title = m.groups()
                vod_id = href.strip()
                if vod_id in seen:
                    continue
                seen.add(vod_id)
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": self._clean(title),
                    "vod_pic": self._fix_url(pic),
                    "vod_remarks": "",
                })
        return videos

    def _parse_folder_list(self, html):
        folders, seen = [], set()
        for m in _RE_FOLDER_CARD.finditer(html):
            slug, name, pic = m.groups()
            name = self._clean(name)
            if not name or slug in seen:
                continue
            seen.add(slug)
            folders.append({
                "vod_id": "\u4e8c\u7ea7@/category/" + slug + "/",
                "vod_name": name,
                "vod_pic": self._fix_url(pic),
                "vod_remarks": "",
                "vod_tag": "folder",
            })
        return folders

    def _pagecount(self, html, current_pg):
        if html:
            # /category/slug/page/N/ 或 /label/slug/page/N/ 或 /search/*/page/N/
            nums = re.findall(r'/(?:category|label|search)/(?:[^/]+/)*page/(\d+)/?', html, re.I)
            page_nums = [int(x) for x in nums if x.isdigit() and 0 < int(x) < 10000]
            if page_nums:
                return max(page_nums)
            # /category/slug/N/ 或 /label/slug/N/ 或 /search/wd/kw/N/
            nums = re.findall(r'/(?:category|label)/[^/]+/(\d+)/?', html, re.I)
            page_nums = [int(x) for x in nums if x.isdigit() and 0 < int(x) < 10000]
            if page_nums:
                return max(page_nums)
            # /search/wd/kw/N/ 或 /search/actor/kw/N/ 或 /search/class/kw/N/
            nums = re.findall(r'/search/(?:wd|actor|class)/[^/]+/(\d+)/?', html, re.I)
            page_nums = [int(x) for x in nums if x.isdigit() and 0 < int(x) < 10000]
            if page_nums:
                return max(page_nums)
            # data-page 属性 (layui-laypage)
            dp = re.findall(r'data-page="(\d+)"', html, re.I)
            page_nums = [int(x) for x in dp if x.isdigit() and 0 < int(x) < 10000]
            if page_nums:
                return max(page_nums)
        return current_pg + 1 if current_pg < 999 else current_pg

    # ==================== 搜索 ====================

    def searchContent(self, key, quick, pg="1"):
        try:
            pg_num = int(pg) if str(pg).isdigit() else 1
            kw = quote(key, safe='')
            path = f"/search/wd/{kw}/" if pg_num <= 1 else f"/search/wd/{kw}/{pg_num}/"
            html = self._get(path)
            if len(html) < 500:
                return {"list": []}
            videos = self._parse_list(html)
            return {"list": videos, "page": pg,
                    "pagecount": self._pagecount(html, pg_num) if videos else pg_num, "limit": 30}
        except:
            return {"list": []}

    # ==================== 详情页 ====================

    def detailContent(self, ids):
        try:
            vid = str(ids[0] if isinstance(ids, list) else ids)
            detail_url = vid if vid.startswith("http") else self.HOST + "/" + vid.lstrip("/")
            html = self._get(detail_url)
            if len(html) < 500:
                return {"list": []}

            title = self._clean(self._re(r'<h1[^>]*class="video-title"[^>]*>([^<]+)</h1>', html))

            pic = (self._re(r'<div class="art-poster"[^>]*background-image:\s*url\(["\']?([^"\'\);]+)', html)
                   or self._re(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html, exclude="javday.png"))

            actress = self._field(html, "vod_actor")
            jpnum = self._field(html, "jpnum")
            producer = self._field(html, "producer")
            actors = self._field_actors(html)
            tags = self._field_tags(html)

            parts = []
            if jpnum:
                parts.append("\u756a\u865f: " + jpnum)
            if tags:
                parts.append("\u6a19\u7c64: " + "\u3001".join(self._clickable_tag(t) for t in tags))
            elif producer:
                parts.append("\u5ee0\u5546: " + self._clickable(producer))
            if actors:
                parts.append("\u5973\u512a: " + "\u3001".join(self._clickable_actor(a) for a in actors))
            vod_content = " | ".join(parts)

            play_url = self._extract_play(html)

            vod = {
                "vod_id": vid,
                "vod_name": title or jpnum or "\u672a\u77e5",
                "vod_pic": self._fix_url(pic),
                "vod_year": "",
                "vod_area": "",
                "vod_type": producer,
                "vod_director": "",
                "vod_actor": actress,
                "vod_remarks": jpnum,
                "vod_play_from": "JAVDAY",
                "vod_play_url": play_url,
                "vod_content": vod_content,
            }
            return {"list": [vod]}
        except:
            return {"list": []}

    def _extract_play(self, html):
        for m in _RE_PLAY.finditer(html):
            parts = []
            for part in m.group(1).split('#'):
                part = part.strip()
                if '$' in part:
                    label, url = part.split('$', 1)
                    url = url.replace('&amp;', '&').strip()
                    if url:
                        parts.append(f"{label}${url}")
            if parts:
                return '#'.join(parts)
        urls = list(dict.fromkeys(u.replace('&amp;', '&') for u in _RE_M3U8.findall(html)))
        if urls:
            return '#'.join(f"\u64ad\u653e{i+1}${u}" for i, u in enumerate(urls))
        return "\u6b63\u7247$" + self.HOST

    # ==================== 播放 ====================

    def playerContent(self, flag, id, vipFlags=0):
        url = id.strip()
        if url.startswith("//"):
            url = "https:" + url
        return {
            "parse": 0,
            "url": url,
            "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.HOST + "/"},
        }

    def isVideoFormat(self, url):
        return any(ext in (url or "").lower() for ext in [".m3u8", ".mp4", ".flv", ".mkv"])

    def manualVideoCheck(self):
        return False

    def isSearchable(self):
        return 1
