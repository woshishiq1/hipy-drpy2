# -*- coding: utf-8 -*-
"""
青空次元 (sorani.net) TVBox Python爬虫
站点: https://www.sorani.net
API:  https://api.sorani.cc/sorani-cms
图片: https://img.sorani.net
类型: SvelteKit SSR + RESTful JSON API, 无CF/无加密
播放: API /api/video/episode/{episodeId}/play?lineCode=anime_jp_m3u8 → m3u8直链
"""

import re
import json
import requests

# 尝试导入基类
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): pass
        def getName(self): return "sorani"
        def isVideoFormat(self, url): return False
        def manualVideoContent(self): return {}
        def homeContent(self, filter=0): return {}
        def homeVideoContent(self): return {}
        def categoryContent(self, tid, pg, filter, extend): return {}
        def detailContent(self, ids): return {}
        def searchContent(self, key, quick, pg): return {}
        def playerContent(self, flag, id, vipFlags): return {}
        def localProxy(self, params): return []
        def destroy(self): pass


class Spider(BaseSpider):

    HOST = "https://www.sorani.net"
    API = "https://api.sorani.cc/sorani-cms"
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def getName(self):
        return "青空次元"

    def init(self, extend=""):
        self.headers = {
            "User-Agent": self.UA,
            "Referer": self.HOST + "/",
            "Origin": self.HOST,
            "Accept": "application/json, text/plain, */*",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        return None

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    def isVideoFormat(self, url):
        u = str(url).lower()
        return ".m3u8" in u or ".mp4" in u or ".flv" in u

    def manualVideoContent(self):
        return {}

    # ==================== 内部方法 ====================

    def _api(self, path, params=None):
        """请求 JSON API，带重试"""
        url = self.API + path
        if params:
            from urllib.parse import urlencode
            url = url + "?" + urlencode(params)
        for _ in range(3):
            try:
                r = self.session.get(url, headers=self.headers, timeout=18)
                r.encoding = "utf-8"
                obj = r.json()
                if isinstance(obj, dict) and (obj.get("success") or obj.get("code") == 200):
                    return obj
            except Exception:
                pass
        return {}

    def _cover(self, item):
        """取最佳封面"""
        for k in ("coverLarge", "cover", "coverThumb", "coverSmall", "coverOg"):
            v = item.get(k)
            if v:
                return str(v)
        for k in ("backgroundImage", "backgroundThumb", "backgroundLarge"):
            v = item.get(k)
            if v:
                return str(v)
        return ""

    def _remark(self, item):
        """生成备注"""
        parts = []
        if item.get("year"):
            parts.append(str(item["year"]))
        st = item.get("statusText")
        if st:
            parts.append(st)
        ec = item.get("episodeCount")
        if ec:
            parts.append("共{0}集".format(ec))
        elif item.get("latestEpisodeLabel"):
            parts.append(item["latestEpisodeLabel"])
        return " / ".join(parts) if parts else ""

    def _card(self, item):
        """格式化视频卡片"""
        return {
            "vod_id": str(item.get("id", "")),
            "vod_name": item.get("title") or item.get("alias") or "",
            "vod_pic": self._cover(item),
            "vod_remarks": self._remark(item),
        }

    def _filter_block(self):
        """生成筛选器"""
        tags = [
            "奇幻", "搞笑", "战斗", "校园", "冒险", "恋爱", "科幻", "治愈",
            "热血", "百合", "后宫", "悬疑", "励志", "青春", "轻小说", "剧情",
            "机战", "竞技", "萝莉", "异世界", "泡面番", "神魔", "魔法", "运动",
            "战争", "女性向", "日常", "肉番", "推理", "歌舞", "犯罪", "社会",
            "恐怖", "职场", "美少女", "游戏", "历史", "耽美", "欢乐向", "血腥",
            "吸血鬼", "伪娘", "惊悚",
        ]
        years = [
            "2026", "2025", "2024", "2023", "2022", "2021", "2020",
            "2019", "2018", "2017", "2016", "2015", "2014", "2013",
            "2012", "2011", "2010", "2009", "2008", "2007", "2006",
            "2005", "2004", "2003", "2002", "2001", "2000",
            "90年代", "80年代", "70年代", "更早",
        ]
        initials = ["0-9"] + [chr(c) for c in range(ord("A"), ord("Z") + 1)]
        def vals(items):
            return [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in items]
        return [
            {
                "key": "sort",
                "name": "排序",
                "value": [
                    {"n": "最新", "v": "latest"},
                    {"n": "热门", "v": "trending"},
                    {"n": "好评", "v": "rating"},
                ],
            },
            {
                "key": "tag",
                "name": "类型",
                "value": vals(tags),
            },
            {
                "key": "year",
                "name": "年份",
                "value": vals(years),
            },
            {
                "key": "initial",
                "name": "字母",
                "value": vals(initials),
            },
            {
                "key": "status",
                "name": "状态",
                "value": [
                    {"n": "全部", "v": ""},
                    {"n": "连载中", "v": "0"},
                    {"n": "已完结", "v": "1"},
                    {"n": "即将播出", "v": "2"},
                ],
            },
        ]

    # ==================== 首页 ====================

    def homeContent(self, filter=0):
        """
        首页: 分类 + 筛选器
        推荐列表放 homeVideoContent (兼容性更好)
        """
        classes = [
            {"type_id": "0", "type_name": "精选"},
            {"type_id": "1", "type_name": "TV番剧"},
            {"type_id": "2", "type_name": "剧场动画"},
            {"type_id": "5", "type_name": "特摄剧场"},
        ]
        filters = {}
        fb = self._filter_block()
        for c in classes:
            filters[c["type_id"]] = fb

        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        """首页推荐: 热门列表 (扁平结构, 兼容影视仓)"""
        try:
            data = self._api("/api/video", {
                "page": 1, "size": 20, "enabled": "true",
                "sortMode": "trending", "sortDesc": "true",
            })
            rows = (data.get("data") or {}).get("records") or []
            return {"list": [self._card(r) for r in rows]}
        except Exception:
            return {"list": []}

    # ==================== 分类列表 ====================

    def categoryContent(self, tid, pg=1, filter=0, extend=None):
        """
        分类列表
        tid=0 精选 (不限分类)
        tid=1 TV番剧, tid=2 剧场动画, tid=5 特摄剧场
        """
        page = int(pg) if str(pg).isdigit() else 1
        if page < 1:
            page = 1

        params = {
            "page": page,
            "size": 24,
            "enabled": "true",
            "sortMode": "latest",
            "sortDesc": "true",
        }

        # 分类ID映射 (tid → API categoryId)
        cid_map = {"1": 1, "2": 2, "5": 5}
        cid = cid_map.get(str(tid), 0)
        if cid:
            params["categoryId"] = cid

        # 筛选参数 (兼容 filter/extend 两种传参)
        f = {}
        if extend and isinstance(extend, dict):
            f = extend
        if isinstance(filter, dict):
            f.update(filter)
        if isinstance(filter, str):
            try:
                f.update(json.loads(filter))
            except Exception:
                pass

        if f.get("sort"):
            params["sortMode"] = f["sort"]
        if f.get("tag") or f.get("tags"):
            params["tags"] = f.get("tag") or f.get("tags")
        if f.get("year"):
            params["year"] = f["year"]
        if f.get("initial"):
            params["initial"] = f["initial"]
        if f.get("status") is not None and str(f.get("status", "")) != "":
            params["status"] = str(f["status"])

        try:
            data = self._api("/api/video", params)
        except Exception:
            return {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}

        body = data.get("data") or {}
        rows = body.get("records") or []
        items = [self._card(r) for r in rows]

        total = int(body.get("total") or 0)
        limit = int(body.get("size") or 24)
        pages = int(body.get("pages") or ((total + limit - 1) // limit if total else 1))
        current = int(body.get("current") or page)

        return {
            "list": items,
            "page": current,
            "pagecount": pages,
            "limit": limit,
            "total": total,
        }

    # ==================== 搜索 ====================

    def searchContent(self, key, quick=False, pg=1):
        """搜索: 用 API keyword 参数"""
        page = int(pg) if str(pg).isdigit() else 1
        if page < 1:
            page = 1
        if not key or not str(key).strip():
            return {"list": [], "page": 1, "pagecount": 0}

        params = {
            "page": page,
            "size": 24,
            "keyword": str(key).strip(),
            "enabled": "true",
            "sortMode": "latest",
            "sortDesc": "true",
        }

        try:
            data = self._api("/api/video", params)
        except Exception:
            return {"list": [], "page": page, "pagecount": 0}

        body = data.get("data") or {}
        rows = body.get("records") or []
        items = [self._card(r) for r in rows]

        total = int(body.get("total") or 0)
        limit = int(body.get("size") or 24)
        pages = int(body.get("pages") or ((total + limit - 1) // limit if total else 1))

        return {
            "list": items,
            "page": page,
            "pagecount": pages,
            "limit": limit,
            "total": total,
        }

    # ==================== 详情 ====================

    def detailContent(self, ids):
        """视频详情: API获取集数列表(含episodeId)"""
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0]) if ids else ""
        else:
            vid = str(ids or "")
        m = re.search(r"\d+", vid)
        if m:
            vid = m.group(0)

        try:
            data = self._api("/api/video/{0}".format(vid))
        except Exception:
            return {"list": []}

        v = data.get("data")
        if not v:
            return {"list": []}

        # 演员
        actor_names = []
        for a in (v.get("actors") or []):
            name = a.get("actorName", "")
            role = a.get("roleName", "")
            if role:
                actor_names.append("{0}({1})".format(name, role))
            else:
                actor_names.append(name)

        # 简介 (去掉日文原文)
        summary = v.get("summary", "")
        if "[简介原文]" in summary:
            summary = summary.split("[简介原文]")[0].strip()

        # 集数列表 — 用 episodeId 作为播放ID
        episodes = v.get("episodes") or []
        if not episodes:
            ec = v.get("episodeCount", 0)
            if ec:
                episodes = [{"episodeOrder": i + 1, "title": "第{0:02d}集".format(i + 1)} for i in range(ec)]

        ep_list = []
        for ep in sorted(episodes, key=lambda e: e.get("episodeOrder", 0)):
            eid = ep.get("episodeId")
            title = ep.get("title") or ep.get("episodeLabel") or "第{0:02d}集".format(int(ep.get("episodeOrder", 0)))
            if eid:
                ep_list.append("{0}${1}".format(title, eid))

        play_url = "#".join(ep_list) if ep_list else ""

        # 标签
        tags = v.get("tags") or ""
        if v.get("tagList"):
            tags = ",".join(v["tagList"])

        item = {
            "vod_id": str(v.get("id", vid)),
            "vod_name": v.get("title", ""),
            "vod_pic": self._cover(v),
            "vod_content": summary,
            "vod_year": str(v.get("year", "")),
            "vod_area": v.get("area", ""),
            "vod_director": v.get("director", ""),
            "vod_actor": " / ".join(actor_names) if actor_names else "",
            "vod_remarks": self._remark(v),
            "vod_play_from": "青空次元",
            "vod_play_url": play_url,
            "type_name": v.get("categoryName", ""),
            "vod_tag": tags,
        }
        return {"list": [item]}

    # ==================== 播放 ====================

    def playerContent(self, flag, id, vipFlags=None):
        """
        播放: 调用API获取m3u8直链
        id = episodeId (从 detailContent 的 play_url 中传来)
        """
        eid = str(id or "")
        if isinstance(id, (list, tuple)):
            eid = str(id[0]) if id else ""
        m = re.search(r"\d+", eid)
        if not m:
            return {"parse": 1, "url": "", "header": {}}
        eid = m.group(0)

        url = self.API + "/api/video/episode/{0}/play?lineCode=anime_jp_m3u8".format(eid)
        play = ""
        try:
            r = self.session.get(url, headers=self.headers, timeout=18)
            r.encoding = "utf-8"
            obj = r.json()
            play = (obj.get("data") or {}).get("playUrl") or ""
        except Exception:
            pass

        return {
            "parse": 0,
            "jx": 0,
            "url": play,
            "header": {
                "User-Agent": self.UA,
                "Referer": self.HOST + "/",
                "Origin": self.HOST,
            },
        }

    def localProxy(self, params):
        return [404, "text/plain", b"", {}]


# ==================== 测试 ====================
if __name__ == "__main__":
    s = Spider()
    s.init()

    print("=" * 60)
    print("  青空次元 (sorani.net) TVBox 爬虫测试")
    print("=" * 60)

    print("\n[1] 首页 homeContent")
    home = s.homeContent()
    print("  分类:", [c["type_name"] for c in home.get("class", [])])
    print("  筛选器:", list(home.get("filters", {}).keys()))
    print("  推荐板块:", [l.get("name") for l in home.get("list", [])])
    if home.get("list"):
        first = home["list"][0]
        print("  {0}: {1} 条".format(first["name"], len(first.get("list", []))))
        if first.get("list"):
            print("  第一条:", first["list"][0])

    print("\n[2] 精选 categoryContent (tid=0, 第1页)")
    cat = s.categoryContent("0", "1")
    print("  总数:", cat["total"], "页数:", cat["pagecount"], "当前页:", len(cat["list"]), "条")
    if cat["list"]:
        print("  第一条:", cat["list"][0])

    print("\n[3] TV番剧 categoryContent (tid=1, 第1页)")
    cat2 = s.categoryContent("1", "1")
    print("  总数:", cat2["total"], "页数:", cat2["pagecount"])

    print("\n[4] 筛选 categoryContent (tid=1, tag=战斗)")
    cat3 = s.categoryContent("1", "1", {"tag": "战斗"})
    print("  总数:", cat3["total"], "页数:", cat3["pagecount"])

    print("\n[5] 搜索 searchContent ('攻壳')")
    search = s.searchContent("攻壳")
    print("  结果数:", len(search.get("list", [])))
    if search.get("list"):
        print("  第一条:", search["list"][0])

    print("\n[6] 详情 detailContent (4695)")
    detail = s.detailContent(["4695"])
    if detail.get("list"):
        d = detail["list"][0]
        print("  标题:", d["vod_name"])
        print("  年份:", d["vod_year"])
        print("  地区:", d["vod_area"])
        print("  导演:", d["vod_director"])
        print("  演员:", (d["vod_actor"] or "")[:80], "...")
        print("  简介:", (d["vod_content"] or "")[:80], "...")
        print("  播放源:", d["vod_play_from"])
        eps = (d.get("vod_play_url") or "").split("#")
        print("  集数:", len(eps))
        if eps:
            print("  第一集:", eps[0][:80])

    print("\n[7] 播放 playerContent (episodeId=64427)")
    if detail.get("list"):
        first_ep = eps[0].split("$")[1] if "$" in eps[0] else "64427"
        play = s.playerContent("青空次元", first_ep)
        print("  parse:", play["parse"])
        print("  url:", (play.get("url") or "")[:100])
    else:
        play = s.playerContent("青空次元", "64427")
        print("  parse:", play["parse"])
        print("  url:", (play.get("url") or "")[:100])

    print("\n" + "=" * 60)
    print("  测试完成!")
    print("=" * 60)
