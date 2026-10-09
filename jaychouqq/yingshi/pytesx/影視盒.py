# -*- coding: utf-8 -*-
"""
影視盒 · 苹果CMS JSON API 采集
来源：影視盒_api.html（默认 https://api.1080zyku.com/inc/apijson.php）
"""
import json
import re
import ssl
import urllib.request
import urllib.parse

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass


class Spider(BaseSpider):
    def getName(self):
        return "影視盒"

    def getDependence(self):
        return []

    def __init__(self):
        super(Spider, self).__init__()
        self.api = "https://api.1080zyku.com/inc/apijson.php"
        self.proxy = ""  # 可选 CORS 代理前缀，如 https://xxx/?url=
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        # HTML 里隐藏的分类
        self.hidden_types = set(["19", "61"])

    def init(self, extend=""):
        # extend 可传 JSON: {"api":"...","proxy":"..."}
        if not extend:
            return
        try:
            ext = json.loads(extend) if isinstance(extend, str) else extend
            if isinstance(ext, dict):
                if ext.get("api"):
                    self.api = str(ext["api"]).strip()
                if ext.get("proxy") is not None:
                    self.proxy = str(ext.get("proxy") or "").strip()
        except Exception:
            if isinstance(extend, str) and extend.startswith("http"):
                self.api = extend.strip()

    def _api(self, params):
        """请求苹果CMS JSON，支持可选代理前缀。"""
        try:
            u = urllib.parse.urlparse(self.api)
            q = urllib.parse.parse_qs(u.query, keep_blank_values=True)
            # 用我们的参数覆盖
            for k, v in (params or {}).items():
                if v is None or v == "":
                    continue
                q[k] = [str(v)]
            query = urllib.parse.urlencode({k: v[0] for k, v in q.items()}, doseq=False)
            url = urllib.parse.urlunparse((u.scheme, u.netloc, u.path, u.params, query, u.fragment))
        except Exception:
            qs = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v not in (None, "")})
            url = self.api + ("&" if "?" in self.api else "?") + qs

        if self.proxy:
            url = self.proxy + urllib.parse.quote(url, safe="")

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
            raw = r.read().decode("utf-8", "ignore")
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def homeContent(self, filter):
        data = self._api({"ac": "list", "pg": "1"})
        classes = []
        for c in data.get("class") or []:
            tid = str(c.get("type_id", ""))
            if not tid or tid in self.hidden_types:
                continue
            classes.append({
                "type_id": tid,
                "type_name": c.get("type_name") or tid
            })
        # 筛选（与 HTML FILTERS 对齐）
        type_vals = [{"n": x, "v": x} for x in [
            "都市", "古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作",
            "奇幻", "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"
        ]]
        area_vals = [{"n": x, "v": x} for x in [
            "大陆", "欧美", "香港", "台湾", "韩国", "日本", "泰国", "印度", "其他"
        ]]
        lang_vals = [{"n": x, "v": x} for x in [
            "国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"
        ]]
        year_vals = [{"n": str(y), "v": str(y)} for y in range(2026, 2009, -1)]
        fitem = [
            {"key": "class", "name": "类型", "value": [{"n": "全部", "v": ""}] + type_vals},
            {"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}] + area_vals},
            {"key": "lang", "name": "语言", "value": [{"n": "全部", "v": ""}] + lang_vals},
            {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}] + year_vals},
        ]
        filters = {}
        for c in classes:
            filters[c["type_id"]] = fitem
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        data = self._api({"ac": "detail", "pg": "1"})
        return {"list": self._map_list(data.get("list") or [])}

    def _map_list(self, items):
        out = []
        for v in items or []:
            out.append({
                "vod_id": str(v.get("vod_id", "")),
                "vod_name": v.get("vod_name") or "",
                "vod_pic": v.get("vod_pic") or "",
                "vod_remarks": v.get("vod_remarks") or "",
                "vod_year": v.get("vod_year") or "",
                "vod_area": v.get("vod_area") or "",
                "type_name": v.get("type_name") or "",
                "style": {"type": "rect", "ratio": 0.75}
            })
        return out

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if str(pg).isdigit() else 1
        params = {"ac": "detail", "t": tid or "", "pg": str(page)}
        # 扩展筛选（API 不一定全支持，透传常见字段）
        if isinstance(extend, dict):
            for k in ("class", "area", "lang", "year"):
                if extend.get(k):
                    params[k] = extend[k]
        data = self._api(params)
        lst = self._map_list(data.get("list") or [])
        pagecount = int(data.get("pagecount") or 1)
        total = int(data.get("total") or 0)
        return {
            "page": page,
            "pagecount": pagecount,
            "limit": len(lst) or 20,
            "total": total or pagecount * 20,
            "list": lst
        }

    def detailContent(self, ids):
        vod_id = ids[0] if isinstance(ids, list) else ids
        data = self._api({"ac": "detail", "ids": str(vod_id)})
        items = data.get("list") or []
        if not items:
            return {"list": []}
        v = items[0]
        return {
            "list": [{
                "vod_id": str(v.get("vod_id", vod_id)),
                "vod_name": v.get("vod_name") or "",
                "vod_pic": v.get("vod_pic") or "",
                "type_name": v.get("type_name") or v.get("vod_class") or "",
                "vod_year": v.get("vod_year") or "",
                "vod_area": v.get("vod_area") or "",
                "vod_lang": v.get("vod_lang") or v.get("vod_language") or "",
                "vod_remarks": v.get("vod_remarks") or "",
                "vod_actor": v.get("vod_actor") or "",
                "vod_director": v.get("vod_director") or "",
                "vod_content": v.get("vod_content") or v.get("vod_blurb") or "",
                "vod_play_from": v.get("vod_play_from") or "線路1",
                "vod_play_url": v.get("vod_play_url") or "",
                "style": {"type": "rect", "ratio": 0.75}
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        url = str(id or "").strip()
        if "$" in url:
            url = url.split("$")[-1].strip()
        header = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": self.api
        }
        # 直链 m3u8/mp4 免解析
        if re.search(r"\.(m3u8|mp4)(\?|$)", url, re.I) and url.startswith("http"):
            return {"parse": 0, "playUrl": "", "url": url, "header": header}
        # 其它交给壳解析
        return {"parse": 1, "playUrl": "", "url": url, "header": header}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() else 1
        # 繁简：简单不处理，由用户输入；API 侧多为简体
        data = self._api({"ac": "detail", "wd": key, "pg": str(page)})
        lst = self._map_list(data.get("list") or [])
        pagecount = int(data.get("pagecount") or 1)
        return {
            "page": page,
            "pagecount": pagecount,
            "limit": len(lst) or 20,
            "total": int(data.get("total") or 100),
            "list": lst
        }

    def action(self, action):
        return {}

    def liveContent(self):
        return {}

    def localProxy(self, params):
        return [200, "text/plain;charset=utf-8", ""]

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(m3u8|mp4)(\?|$)", str(url or ""), re.I))

    def destroy(self):
        pass
