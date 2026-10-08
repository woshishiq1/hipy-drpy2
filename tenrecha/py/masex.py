# -*- coding: utf-8 -*-
import re, json, requests, urllib.parse
from lxml import etree
from base.spider import Spider


SORT_OPTS = [
    {"n": "最近更新", "v": "latest"},
    {"n": "发布日期", "v": "release"},
    {"n": "今天最多观看", "v": "view_day"},
    {"n": "本周最多观看", "v": "view_week"},
    {"n": "本月最多观看", "v": "view_month"},
    {"n": "最多观看", "v": "view_count"},
    {"n": "最受欢迎", "v": "favorite"},
]
DURATION_OPTS = [
    {"n": "全部时长", "v": ""},
    {"n": "45分钟以内", "v": "lt-45"},
    {"n": "45-90分钟", "v": "45-90"},
    {"n": "90-120分钟", "v": "90-120"},
    {"n": "120分钟以上", "v": "gt-122"},
]
FILTER_OPTS = [
    {"n": "全部", "v": ""},
    {"n": "单体作品", "v": "single"},
    {"n": "中文字幕", "v": "chinese_sub"},
    {"n": "可下载", "v": "download"},
]

TAG_GROUPS = ["类别", "主题", "行为", "体型", "服装", "角色"]
ACTOR_HEIGHT_OPTS = [{"n": "全部身高", "v": ""}] + [
    {"n": "%s cm" % v, "v": v} for v in (
        "130-134", "135-139", "140-144", "145-149", "150-154",
        "155-159", "160-164", "165-169", "170-174", "175-179",
        "180-184", "185-189", "190-194",
    )
]
ACTOR_CUP_OPTS = [{"n": "全部胸围", "v": ""}] + [
    {"n": "%s 杯" % v, "v": v} for v in "ABCDEFGHIJKLMNOPQZ"
]
ACTOR_AGE_OPTS = [{"n": "全部年龄", "v": ""}] + [
    {"n": "< 20 岁", "v": "0-19"},
    {"n": "20-24 岁", "v": "20-24"},
    {"n": "25-29 岁", "v": "25-29"},
    {"n": "30-34 岁", "v": "30-34"},
    {"n": "35-39 岁", "v": "35-39"},
    {"n": "40-44 岁", "v": "40-44"},
    {"n": "45-49 岁", "v": "45-49"},
    {"n": "50-54 岁", "v": "50-54"},
    {"n": "> 60 岁", "v": "60-99"},
]
ACTOR_SORT_OPTS = [
    {"n": "视频数量", "v": "count"},
    {"n": "姓名", "v": "name"},
    {"n": "最多观看", "v": "view"},
    {"n": "最受欢迎", "v": "favorite"},
]


class Spider(Spider):
    def getName(self):
        return "masex"

    def init(self, extend=""):
        self.host = "https://masex.tv"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": "https://masex.tv/zh-CN",
        }
        self._home_list = []

    @staticmethod
    def _norm_pic(pic):
        if pic and pic.startswith("http://"):
            return "https://" + pic[7:]
        return pic or ""

    def _build_url(self, path, pg, extend):
        q = []
        for k in ("sort", "duration", "filter", "height", "cup", "age"):
            v = (extend or {}).get(k)
            if v:
                q.append("%s=%s" % (k, urllib.parse.quote(str(v))))
        if pg and pg > 1:
            q.append("page=%d" % pg)
        return self.host + path + ("?" + "&".join(q) if q else "")

    @staticmethod
    def _empty(pg):
        pg = pg or 1
        return {"list": [], "page": pg, "pagecount": pg, "limit": 30, "total": 0}

    def homeContent(self, filter):
        classes = [
            {"type_id": "latest", "type_name": "最近更新"},
            {"type_id": "tag/531", "type_name": "中文"},
            {"type_id": "tag/268", "type_name": "VR"},
            {"type_id": "tags", "type_name": "类型"},
            {"type_id": "maker", "type_name": "系列"},
            {"type_id": "maker/all", "type_name": "片商"},
            {"type_id": "actor/all", "type_name": "女优"},
        ]
        return {
            "class": classes,
            "filters": self._filters(),
        }

    def homeVideoContent(self, *args):
        videos = []
        try:
            res = requests.get(self.host + "/zh-CN", headers=self.headers, timeout=10)
            tree = etree.HTML(res.text)
            areas = ["最近更新", "热门推荐", "VR", "片商"]
            seen = set()
            for sec in tree.xpath('//div[contains(@class,"sec")]'):
                title = sec.xpath('string(.//span[contains(@class,"sec-title")])').strip()
                if title not in areas:
                    continue
                for a in sec.xpath('.//a[contains(@class,"card")]'):
                    name = a.xpath('string(.//div[contains(@class,"card-title")])').strip()
                    if not name:
                        name = a.xpath('string(.//img/@alt)').strip()
                    pic = a.xpath('string(.//img/@src)')
                    href = a.get('href', '')
                    if not name or not href or href in seen:
                        continue
                    seen.add(href)
                    videos.append({
                        "vod_id": href,
                        "vod_name": name,
                        "vod_pic": self._norm_pic(pic),
                        "vod_remarks": title,
                    })
        except Exception:
            pass
        return {"list": videos, "page": 1, "pagecount": 1}
        
    def _filters(self):
        f = [
            {"key": "sort", "name": "排序", "value": SORT_OPTS},
            {"key": "duration", "name": "时长", "value": DURATION_OPTS},
            {"key": "filter", "name": "筛选", "value": FILTER_OPTS},
        ]
        tag_cls = [{"n": "全部", "v": ""}] + [{"n": g, "v": g} for g in TAG_GROUPS]
        actor_f = [
            {"key": "height", "name": "身高", "value": ACTOR_HEIGHT_OPTS},
            {"key": "cup", "name": "胸围", "value": ACTOR_CUP_OPTS},
            {"key": "age", "name": "年龄", "value": ACTOR_AGE_OPTS},
            {"key": "sort", "name": "排序", "value": ACTOR_SORT_OPTS},
        ]
        return {
            "latest": f,
            "tag/531": f,
            "tag/268": f,
            "tags": [{"key": "cls", "name": "分类", "value": tag_cls}],
            "actor/all": actor_f,
        }

    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid)
        if isinstance(extend, str):
            try:
                extend = json.loads(extend) if extend.strip() else {}
            except Exception:
                extend = {}
        extend = extend if isinstance(extend, dict) else {}
        try:
            pg = int(pg)
        except Exception:
            pg = 1

        if tid == "tags":
            return self._tag_list(extend)
        if tid == "maker":
            return self._series_list(pg)
        if tid == "maker/all":
            return self._maker_list(pg, extend)
        if tid == "actor/all":
            return self._actor_list(pg, extend)

        path = tid if tid.startswith("/") else ("/zh-CN/" + tid)
        return self._video_list(path, pg, extend)

    def _tag_list(self, extend):
        group = (extend or {}).get("cls", "")
        try:
            res = requests.get(self.host + "/zh-CN/tags", headers=self.headers, timeout=10)
            tree = etree.HTML(res.text)
        except Exception:
            return self._empty(1)
        out = []
        for sec in tree.xpath('//div[contains(@class,"sec")]'):
            title = sec.xpath('string(.//span[contains(@class,"tag-sec-title")])').strip()
            if title not in TAG_GROUPS:
                continue
            if group and title != group:
                continue
            for a in sec.xpath('.//a[contains(@class,"tag-grid-item")]'):
                name = a.xpath('string(.//span[contains(@class,"tag-grid-name")])').strip()
                href = a.get('href', '')
                m = re.search(r'/tag/(\d+)', href or '')
                if not name or not m:
                    continue
                out.append({
                    "vod_id": "tag/" + m.group(1),
                    "vod_name": name,
                    "vod_pic": "",
                    "vod_tag": "folder",
                    "vod_remarks": title,
                })
        return {"list": out, "page": 1, "pagecount": 1, "limit": len(out), "total": len(out)}

    def _series_list(self, pg):
        url = self.host + "/zh-CN/maker" + ("?page=%d" % pg if pg > 1 else "")
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            tree = etree.HTML(res.text)
        except Exception:
            return self._empty(pg)
        out, seen = [], set()
        for a in tree.xpath('//a[contains(@class,"series-card")]'):
            href = a.get('href', '')
            name = a.xpath('string(.//div[contains(@class,"series-card-name")])').strip()
            style = a.xpath('string(.//div[contains(@class,"series-card-img")]/@style)')
            m = re.search(r"url\('([^']+)'\)", style)
            pic = m.group(1) if m else ""
            sid = re.search(r'/series/(\d+)', href or '')
            if not name or not sid or href in seen:
                continue
            seen.add(href)
            out.append({
                "vod_id": "series/" + sid.group(1),
                "vod_name": name,
                "vod_pic": self._norm_pic(pic),
                "vod_tag": "folder",
                "vod_remarks": "系列",
            })
        return {"list": out, "page": pg, "pagecount": 999, "limit": 30, "total": 999}

    def _maker_list(self, pg, extend):
        url = self._build_url("/zh-CN/maker/all", pg, extend)
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            tree = etree.HTML(res.text)
        except Exception:
            return self._empty(pg)
        out, seen = [], set()
        for a in tree.xpath('//a[contains(@class,"maker-grid-link")]'):
            href = a.get('href', '')
            if "/maker/" not in (href or ""):
                continue
            name = a.xpath('string(.//div[contains(@class,"maker-grid-name")])').strip()
            pic = a.xpath('string(.//img[contains(@class,"maker-circle-img")]/@src)')
            mid = re.search(r'/maker/(\d+)', href)
            if not name or not mid or href in seen:
                continue
            seen.add(href)
            out.append({
                "vod_id": "maker/" + mid.group(1),
                "vod_name": name,
                "vod_pic": self._norm_pic(pic),
                "vod_tag": "folder",
                "vod_remarks": "片商",
            })
        return {"list": out, "page": pg, "pagecount": 999, "limit": 30, "total": 999}

    def _actor_list(self, pg, extend):
        url = self._build_url("/zh-CN/actor/all", pg, extend)
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            tree = etree.HTML(res.text)
        except Exception:
            return self._empty(pg)
        out, seen = [], set()
        for a in tree.xpath('//a[contains(@class,"maker-grid-link")]'):
            href = a.get('href', '')
            if "/actor/" not in (href or ""):
                continue
            name = a.xpath('string(.//div[contains(@class,"maker-grid-name")])').strip()
            pic = a.xpath('string(.//img[contains(@class,"maker-circle-img")]/@src)')
            count = a.xpath('string(.//div[contains(@class,"maker-grid-count")])').strip()
            aid = re.search(r'/actor/(\d+)', href)
            if not name or not aid or href in seen:
                continue
            seen.add(href)
            out.append({
                "vod_id": "actor/" + aid.group(1),
                "vod_name": name,
                "vod_pic": self._norm_pic(pic),
                "vod_tag": "folder",
                "vod_remarks": count if count else "女优",
            })
        return {"list": out, "page": pg, "pagecount": 999, "limit": 30, "total": 999}

    def _video_list(self, path, pg, extend):
        url = self._build_url(path, pg, extend)
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            tree = etree.HTML(res.text)
        except Exception:
            return self._empty(pg)
        videos, seen = [], set()
        for a in tree.xpath('//a[contains(@class,"card")]'):
            name = a.xpath('string(.//div[contains(@class,"card-title")])').strip()
            if not name:
                name = a.xpath('string(.//img/@alt)').strip()
            pic = a.xpath('string(.//img/@src)')
            href = a.get('href', '')
            if not name or not href or href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": name,
                "vod_pic": self._norm_pic(pic),
                "vod_remarks": "",
            })
        return {"list": videos, "page": pg, "pagecount": 999, "limit": 30, "total": 999}

    def detailContent(self, ids):
        url = ids[0] if str(ids[0]).startswith("http") else self.host + ids[0]
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            tree = etree.HTML(res.text)
        except Exception:
            return {"list": []}

        title = tree.xpath('string(//h1[contains(@class,"vd-title")])').strip()
        if not title:
            title = tree.xpath('string(//h1)').strip()
        pic = tree.xpath('string(//video[contains(@class,"vd-player")]/@poster)')

        meta = {}
        for row in tree.xpath('//div[contains(@class,"vd-meta-row")]'):
            label = row.xpath('string(.//span[contains(@class,"vd-meta-label")])').strip()
            val = row.xpath('string(.//*[contains(@class,"vd-meta-val")])').strip()
            if label and val:
                meta[label] = re.sub(r'\s+', ' ', val)
        content = "  ".join([f"{k}: {v}" for k, v in meta.items()])

        vid = tree.xpath('string(//video[contains(@class,"vd-player")]/@data-video-id)')
        trailer = tree.xpath('string(//video[contains(@class,"vd-player")]/@data-trailer-url)').strip()
        if not trailer and vid:
            trailer = f"{self.host}/trailer/{vid}"

        vod = {
            "vod_id": ids[0],
            "vod_name": title,
            "vod_pic": self._norm_pic(pic),
            "vod_content": content,
            "vod_play_from": "官方试看",
            "vod_play_url": ("第1集$" + trailer) if trailer else "",
        }
        return {"list": [vod]}

    def searchContent(self, key, quick):
        url = f"{self.host}/zh-CN/search?q={urllib.parse.quote(key)}"
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            tree = etree.HTML(res.text)
        except Exception:
            return {"list": [], "page": 1, "pagecount": 0, "limit": 0, "total": 0}
        videos, seen = [], set()
        for a in tree.xpath('//a[contains(@class,"card")]')[:30]:
            name = a.xpath('string(.//div[contains(@class,"card-title")])').strip()
            if not name:
                name = a.xpath('string(.//img/@alt)').strip()
            pic = a.xpath('string(.//img/@src)')
            href = a.get('href', '')
            if not name or not href or href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": name,
                "vod_pic": self._norm_pic(pic),
                "vod_remarks": "",
            })
        return {"list": videos, "page": 1, "pagecount": 1, "limit": 30, "total": len(videos)}

    def playerContent(self, flag, id, vipFlags):
        header = dict(self.headers)
        if "/trailer/" in id or id.endswith(".m3u8") or id.endswith(".mp4"):
            return {"parse": 0, "play": id, "url": id, "header": header}
        target = id if id.startswith("http") else self.host + id
        try:
            res = requests.get(target, headers=header, timeout=10)
            text = res.text
        except Exception:
            return {"parse": 0, "play": id, "url": id, "header": header}
        play_url = ""
        for pat in [r'(https?://[^"\']+\.m3u8[^"\']*)', r'(https?://[^"\']+\.mp4[^"\']*)', r'src\s*=\s*["\']([^"\']+)["\']']:
            m = re.search(pat, text)
            if m:
                play_url = m.group(1)
                break
        if not play_url:
            play_url = id
        if play_url and not play_url.startswith("http"):
            play_url = ("https://" + self.host + play_url) if play_url.startswith("/") else ("https:" + play_url)
        return {"parse": 0, "play": play_url, "url": play_url, "header": header}
