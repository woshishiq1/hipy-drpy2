# coding: utf-8
# TVBox / FongMi / OK影视 / WebHomeTV / PeekPro  Python Spider
"""
西瓜短剧 bikamanhuaapp.com | TVBox Python 爬虫 
关键:
  - 分类走 /api/tags/{slug}/articles，修复旧版 ?tag= 被静默忽略的问题
  - 排行榜走 /api/rankings/latest-bundle?period_type=week|month（daily 会 400）
  - 播放取流跟完 302，Location 为相对路径 /m3c/xxx.m3u8?sign=...&time=...&rand=...&uid=...
  - 三条可切换线路: 直连v4 / 代理v4 / 原链v4
  - 兼容 leanback-python 注入的 BaseSpider（三态回退导入）
"""
import re
import sys
import requests
from requests.compat import urljoin

sys.path.append('..')
try:
    requests.packages.urllib3.disable_warnings()
except Exception:
    pass

# 简介前缀：与原豆花爬虫保持一致
INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ------------------------------------------------------------------
# 三态回退导入（避免客户端注入基类名不匹配导致整站空白）：
#   1) TVBox 标准注入 Spider
#   2) OK影视 / 绿豆等 leanback-python 注入 BaseSpider
#   3) 均失败时用空占位类兜底
# ------------------------------------------------------------------
try:
    from base.spider import Spider as _BaseSpider
except Exception:
    try:
        from base.spider import BaseSpider as _BaseSpider
    except Exception:
        class _BaseSpider(object):
            pass


class Spider(_BaseSpider):

    LINE_DIRECT = "西瓜短剧·直连v4"   # spider 先解析 302，返回绝对直链
    LINE_PROXY = "西瓜短剧·代理v4"    # 客户端本地代理取 m3u8 内容
    LINE_RAW = "西瓜短剧·原链v4"      # 原始地址，仅作对照

    # 内置特殊分类（非 tag slug）
    TID_NEW = "new"
    TID_RANK_WEEK = "rank_week"

    def getName(self):
        return "西瓜短剧"

    def init(self, extend=""):
        self.host = "https://bikamanhuaapp.com"
        self.img = self.host + "/cdn/image"

        # 抓取数据用的普通 UA
        self.api_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        }

        # 播放专用的 WebView UA
        self.play_headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 15; 2407FRK8EC Build/AP3A.240617.008; wv) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
                          "Chrome/128.0.6613.127 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "*/*",
        }
        self.cache_cats = []

    def destroy(self):
        self.cache_cats = []

    def isVideoFormat(self, url):
        try:
            u = str(url or "").lower().split("?")[0]
            return u.endswith(".m3u8") or u.endswith(".mp4")
        except Exception:
            return False

    def manualVideoCheck(self):
        return False

    # ------------------------------------------------------------
    # 分类标签（对应 /api/tags）
    # ------------------------------------------------------------
    def loadCategories(self):
        try:
            r = requests.get(self.host + "/api/tags?page=1&limit=300",
                             headers=self.api_headers, timeout=10, verify=False)
            data = r.json().get("data") or []
            self.cache_cats = [
                {"type_id": t.get("slug", ""), "type_name": t.get("name", "")}
                for t in data if t.get("slug")
            ]
        except Exception:
            pass

    # ------------------------------------------------------------
    # 首页
    # ------------------------------------------------------------
    def homeContent(self, filter=False):
        result = {"class": [], "filters": {}, "list": []}
        try:
            if not self.cache_cats:
                self.loadCategories()
            classes = [
                {"type_id": self.TID_NEW, "type_name": "最新更新"},
                {"type_id": self.TID_RANK_WEEK, "type_name": "本周热播榜"},
            ]
            classes.extend(self.cache_cats)
            result["class"] = classes
            vids, _ = self._parse_list(
                self.host + "/api/articles?page=1&limit=24&sort=new")
            result["list"] = vids
        except Exception:
            pass
        return result

    def homeVideoContent(self):
        try:
            vids, _ = self._parse_list(
                self.host + "/api/articles?page=1&limit=24&sort=new")
            return {"list": vids}
        except Exception:
            return {"list": []}

    # ------------------------------------------------------------
    # 列表公共解析（首页 / 分类 / 搜索 复用）
    # 期望返回结构：{"data": [...], "pagination": {"totalPages": N, ...}}
    # 返回 (videos, pagecount)；分页信息缺失时兜底 9999。
    # ------------------------------------------------------------
    def _parse_list(self, url):
        videos = []
        pagecount = 9999
        data = []
        try:
            r = requests.get(url, headers=self.api_headers, timeout=10, verify=False)
            j = r.json() or {}
            data = j.get("data") or []
            pg = j.get("pagination") or {}
            tp = pg.get("totalPages")
            if tp:
                try:
                    pagecount = int(tp)
                except Exception:
                    pass
        except Exception:
            data = []

        for x in data:
            ed = x.get("extra_data") or {}
            try:
                tags = "/".join([t.get("name", "") for t in (x.get("tags") or [])])
            except Exception:
                tags = ""
            remark = "{}·{}集·{}".format(
                ed.get("cat_name", "短剧"),
                ed.get("episode_count") or "?",
                ed.get("update_status") or ""
            )
            if tags:
                remark = remark + "·" + tags

            cover = x.get("cover_image") or ""
            pic = (self.img + cover) if cover else ""

            videos.append({
                "vod_id":     x.get("slug", ""),
                "vod_name":   x.get("title", ""),
                "vod_pic":    pic,
                "vod_remarks": remark,
            })
        return videos, pagecount

    # ------------------------------------------------------------
    # 排行榜解析：/api/rankings/latest-bundle 返回结构与普通列表不同，
    # 取 tabs[0].items（kind=overall 那条），字段为 article_* 前缀。
    # ------------------------------------------------------------
    def _parse_rankings(self, period_type="week"):
        videos = []
        try:
            url = "{}/api/rankings/latest-bundle?period_type={}".format(
                self.host, period_type)
            r = requests.get(url, headers=self.api_headers, timeout=10, verify=False)
            j = r.json() or {}
        except Exception:
            return videos

        tabs = j.get("tabs") or []
        items = []
        if tabs:
            # 优先取 overall，否则取第一个 tab
            overall = [t for t in tabs if t.get("kind") == "overall"]
            tab = overall[0] if overall else tabs[0]
            items = tab.get("items") or []

        for it in items:
            cover = it.get("article_cover") or ""
            pic = (self.img + cover) if cover else ""
            views = it.get("period_views") or 0
            videos.append({
                "vod_id":     it.get("article_slug", ""),
                "vod_name":   it.get("article_title", ""),
                "vod_pic":    pic,
                "vod_remarks": "周榜第{}名·{}次播放".format(
                    it.get("rank", "?"), views),
            })
        return videos

    # ------------------------------------------------------------
    # 分类
    # ------------------------------------------------------------
    def categoryContent(self, tid, pg="1", filter="", extend=""):
        result = {"list": [], "page": 1, "pagecount": 9999, "limit": 24, "total": 999999}
        try:
            pg = int(pg)
            result["page"] = pg
            tid = str(tid)

            if tid == self.TID_NEW:
                url = "{}/api/articles?page={}&limit=24&sort=new".format(self.host, pg)
                vids, pc = self._parse_list(url)
                result["list"] = vids
                result["pagecount"] = pc
            elif tid == self.TID_RANK_WEEK:
                # 排行榜一次性返回全部，不分页
                result["list"] = self._parse_rankings("week")
                result["pagecount"] = 1
            else:
                # 题材分类：正确接口是 /api/tags/{slug}/articles，
                # 而不是旧版错误的 /api/articles?tag=xxx
                url = "{}/api/tags/{}/articles?page={}&limit=24".format(
                    self.host, requests.utils.quote(tid, safe=""), pg)
                vids, pc = self._parse_list(url)
                result["list"] = vids
                result["pagecount"] = pc
        except Exception:
            pass
        return result

    # ------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------
    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg)
            url = "{}/api/articles?search={}&page={}&limit=24".format(
                self.host, requests.utils.quote(str(key)), pg
            )
            vids, pc = self._parse_list(url)
            return {
                "list": vids,
                "page": pg,
                "pagecount": pc,
            }
        except Exception:
            return {"list": [], "page": 1, "pagecount": 1}

    # ------------------------------------------------------------
    # 详情
    # ------------------------------------------------------------
    def detailContent(self, ids=""):
        if isinstance(ids, (list, tuple)):
            slug = str(ids[0]) if ids else ""
        else:
            slug = str(ids or "")
        if not slug:
            return {"list": []}

        videos = []
        try:
            r = requests.get("{}/api/articles/{}".format(self.host, slug),
                             headers=self.api_headers, timeout=10, verify=False)
            d = r.json()
        except Exception:
            return {"list": videos}

        ed = d.get("extra_data") or {}
        links = ed.get("links") or []

        # 按集数数字升序排序，避免 API 乱序
        def ep_num(ep):
            m = re.search(r"\d+", (ep.get("name") or ""))
            return int(m.group()) if m else 999999

        try:
            links = sorted(links, key=ep_num)
        except Exception:
            pass

        names, urls = [], []
        for i, ep in enumerate(links):
            name = ep.get("name") or "第{}集".format(i + 1)
            purl = ep.get("m3u8_url") or ""
            if not purl:
                continue
            u = purl if purl.startswith("http") else (self.host + purl)
            names.append(name)
            urls.append(u)

        cover = d.get("cover_image") or ""
        pic = (self.img + cover) if cover else ""

        # ===== 简介：统一加 INTRO_PREFIX =====
        raw_content = d.get("content") or d.get("excerpt") or ""
        raw_content = str(raw_content).strip()
        if raw_content:
            content = INTRO_PREFIX + "\n" + raw_content
        else:
            content = INTRO_PREFIX

        # 三条线路共用同一批选集地址，区别只在 playerContent 里如何处理
        play = "#".join(["{}${}".format(n, u) for n, u in zip(names, urls)]) if names else ""

        vod = {
            "vod_id":        slug,
            "vod_name":      d.get("title", ""),
            "vod_pic":       pic,
            "type_name":     ed.get("cat_name", "短剧"),
            "vod_year":      str(ed.get("year", "") or ed.get("issue_date", "") or ""),
            "vod_area":      ed.get("area", "") or "",
            "vod_remarks":   ed.get("update_status", "") or "",
            "vod_actor":     ed.get("actor", "") or "",
            "vod_director":  ed.get("director", "") or "",
            "vod_content":   content,
            "vod_play_from": "$$$".join([self.LINE_DIRECT, self.LINE_PROXY, self.LINE_RAW]),
            "vod_play_url":  "$$$".join([play, play, play]) if play else "",
        }
        videos.append(vod)
        return {"list": videos}

    def metaContent(self, ids=""):
        return self.detailContent(ids)

    # ------------------------------------------------------------
    # 播放
    # ------------------------------------------------------------
    def _resolve(self, url):
        """跟随 302，返回带签名的绝对 m3u8 地址；失败时原样返回。"""
        try:
            r = requests.get(url, headers=self.play_headers, timeout=10,
                             allow_redirects=False, verify=False)
            if r.status_code in (301, 302, 303, 307, 308):
                loc = r.headers.get("location") or ""
                if loc:
                    return urljoin(url, loc)
            if r.status_code == 200:
                return url
        except Exception:
            pass
        # 兜底：直接跟随跳转，用最终地址
        try:
            r = requests.get(url, headers=self.play_headers, timeout=10, verify=False)
            if r.status_code == 200:
                return r.url
        except Exception:
            pass
        return url

    def _fetch_playlist(self, url):
        """取 m3u8 内容：优先客户端注入的 Java HTTP 栈，其次 requests。返回 (bytes, mime)。"""
        # 1) self.fetch（Java 栈，TLS 指纹接近浏览器，通常会自动跟随跳转）
        fetch = getattr(self, "fetch", None)
        if callable(fetch):
            res = None
            for call in (lambda: fetch(url, self.play_headers), lambda: fetch(url)):
                try:
                    res = call()
                    break
                except TypeError:
                    continue
                except Exception:
                    res = None
                    break
            data = None
            if res is not None:
                for attr in ("content", "text", "body", "data"):
                    data = getattr(res, attr, None)
                    if data:
                        break
                if not data and isinstance(res, (bytes, str)):
                    data = res
            if data:
                if isinstance(data, str):
                    data = data.encode("utf-8", "ignore")
                if bytes(data[:7]) == b"#EXTM3U":
                    return bytes(data), "application/vnd.apple.mpegurl"

        # 2) requests 兜底
        try:
            r = requests.get(url, headers=self.play_headers, timeout=15, verify=False)
            if r.status_code == 200 and bytes(r.content[:7]) == b"#EXTM3U":
                return r.content, (r.headers.get("content-type")
                                   or "application/vnd.apple.mpegurl")
        except Exception:
            pass
        return None, None

    def _proxy_url(self, url):
        """构造客户端本地代理地址；客户端不支持时返回 None。"""
        get_url = getattr(self, "getProxyUrl", None)
        if not callable(get_url):
            return None
        try:
            base = get_url(True)          # 期望得到 proxy://?do=py
        except Exception:
            return None
        if not base:
            return None
        sep = "&" if "?" in base else "?"
        return "{}{}url={}".format(base, sep, requests.utils.quote(str(url), safe=""))

    def proxy(self, params):
        """客户端本地代理回调：由客户端 HTTP 栈拉取上游 m3u8，再把内容交回播放器。"""
        try:
            url = (params or {}).get("url") or ""
            if not url:
                return [400, "text/plain", b""]
            body, mime = self._fetch_playlist(url)
            if not body:
                return [502, "text/plain", b""]
            return [200, mime or "application/vnd.apple.mpegurl", body]
        except Exception:
            return [500, "text/plain", b""]

    def playerContent(self, flag, id, vipFlags=""):
        # 播放地址是 m3u8 直链，必须 parse=0（直接播放）
        try:
            url = str(id or "")
            if url and not url.startswith("http"):
                url = self.host + url

            line = str(flag).strip()
            if line == self.LINE_RAW:
                pass                                   # 对照线路：原样返回
            elif line == self.LINE_PROXY:
                purl = self._proxy_url(url)
                url = purl if purl else self._resolve(url)
            else:
                url = self._resolve(url)               # 默认（含直连线路）

            return {
                "parse":  0,
                "url":    url,
                "header": self.play_headers,
                "format": "application/x-mpegURL",
            }
        except Exception:
            return {"parse": 0, "url": str(id or ""), "header": {}}
