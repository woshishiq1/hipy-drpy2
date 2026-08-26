#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""玩蛋吧 (lysh.wandanba.biz) TVBox Spider """

import re
import json
import urllib.request
import urllib.parse
import ssl

BASE_URL = "https://lysh.wandanba.biz"
UA = "Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

# 分类映射
TYPE_MAP = {
    "5228": "国产精品",
    "5229": "主播秀色",
    "5230": "网曝系列",
    "5231": "麻豆传媒",
    "5232": "日本有码",
    "5233": "日本无码",
    "5234": "中文字幕",
    "5235": "童颜巨乳",
    "5236": "性感人妻",
    "5237": "强奸乱伦",
    "5238": "丝袜OL",
    "5239": "欧美情色",
    "5240": "三级伦理",
    "5241": "卡通动漫",
}

# ────────────────────────────── 网络工具 ──────────────────────────────

def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _get(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Referer": BASE_URL + "/",
        })
        resp = urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx())
        return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def _fetch_page(path, timeout=15):
    return _get(BASE_URL + path, timeout)


# ────────────────────────────── 数据提取 ──────────────────────────────

def _extract_vod_cards(html):
    """从分类页/搜索页提取视频卡片"""
    items = []
    seen = set()
    # 卡片: <li> → <a href="/vod/detail/id/{id}"> → <img data-src="图"> → <span class="text">标题</span>
    for m in re.finditer(r'vod/detail/id/(\d+)\.html[^>]*>.*?<img[^>]*(?:data-src|src)="([^"]*)"[^>]*>.*?<span class="text">(.*?)</span>', html, re.DOTALL):
        vid = m.group(1)
        pic = m.group(2)
        # 清理标题中 HTML 标签（搜索高亮 <b> 等）
        name = re.sub(r'<[^>]+>', '', m.group(3)).strip()
        if vid not in seen:
            seen.add(vid)
            items.append({"id": vid, "name": name, "pic": pic})
    return items


def _extract_detail_info(html):
    """提取详情字段"""
    info = {}
    # 标题
    m = re.search(r'<title>([^<]+)</title>', html)
    if m:
        t = m.group(1).strip()
        t = re.sub(r'\s*玩蛋吧\s*$', '', t)
        info["name"] = t
    # 图片
    m = re.search(r'<img[^>]*data-src="([^"]*)"', html)
    if m:
        info["pic"] = m.group(1)
    # 播放地址
    m = re.search(r'url":\s*"([^"]+)"', html)
    if m:
        info["play_url"] = m.group(1)
    return info


# ────────────────────────────── ID 规范化 ──────────────────────────────

def _norm_ids(ids):
    if ids is None:
        return []
    if isinstance(ids, str):
        try:
            p = json.loads(ids)
            if isinstance(p, list):
                return [str(x) for x in p]
        except (json.JSONDecodeError, TypeError):
            pass
        return [ids.strip()]
    if isinstance(ids, (list, tuple)):
        return [str(i) for i in ids]
    return [str(ids)]


# ────────────────────────────── Spider 类 ──────────────────────────────

class Spider:
    """玩蛋吧 — HTML 抓取版"""

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = {}
        if extend:
            try:
                self.extend = json.loads(extend) if isinstance(extend, str) else dict(extend)
            except Exception:
                pass

    def getName(self):
        return "玩蛋吧"

    def homeContent(self, filter=None):
        return {
            "class": [{"type_id": tid, "type_name": name} for tid, name in TYPE_MAP.items()],
            "filters": {},
        }

    def homeVideoContent(self):
        html = _fetch_page("/index.php")
        items = _extract_vod_cards(html)
        return {"list": [{
            "vod_id": it["id"],
            "vod_name": it["name"],
            "vod_pic": it.get("pic", ""),
            "type_name": "",
            "vod_remarks": "",
        } for it in items[:50]]}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        pg = int(pg) if pg else 1
        if pg <= 1:
            path = f"/index.php/vod/type/id/{tid}.html"
        else:
            path = f"/index.php/vod/type/id/{tid}/page/{pg}.html"
        html = _fetch_page(path)
        items = _extract_vod_cards(html)
        return {
            "list": [{
                "vod_id": it["id"],
                "vod_name": it["name"],
                "vod_pic": it.get("pic", ""),
                "type_name": TYPE_MAP.get(str(tid), ""),
                "vod_remarks": "",
            } for it in items],
            "page": pg,
            "pagecount": 9999,
            "limit": 40,
            "total": 0,
        }

    def detailContent(self, ids):
        ids = _norm_ids(ids)
        if not ids:
            return {"list": []}
        vid = ids[0]
        html = _fetch_page(f"/index.php/vod/detail/id/{vid}.html")
        if not html:
            return {"list": []}
        info = _extract_detail_info(html)
        return {
            "list": [{
                "vod_id": vid,
                "vod_name": info.get("name", "未知"),
                "vod_pic": info.get("pic", ""),
                "type_name": "",
                "vod_year": "",
                "vod_area": "",
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "在线播放",
                "vod_play_url": f"正片${vid}",
            }]
        }

    def searchContent(self, key, quick=False, pg=1):
        try:
            kw = urllib.parse.quote(str(key))
            html = _fetch_page(f"/index.php/vod/search/wd/{kw}")
            items = _extract_vod_cards(html)
            return {"list": [{
                "vod_id": it["id"],
                "vod_name": it["name"],
                "vod_pic": it.get("pic", ""),
                "type_name": "",
                "vod_remarks": "",
            } for it in items[:20]]}
        except Exception:
            return {"list": []}

    def playerContent(self, flag, ids, vipFlags=None):
        """ids = {vid} → 去详情页提取 xgplayer 的 url"""
        vid = str(ids).split("@")[0].split("-")[0]
        html = _fetch_page(f"/index.php/vod/detail/id/{vid}.html")
        if not html:
            return {"parse": 0, "playUrl": "", "header": {}}
        m = re.search(r'url":\s*"([^"]+)"', html)
        play_url = m.group(1) if m else ""
        return {
            "parse": 0,
            "playUrl": play_url,
            "header": {
                "User-Agent": UA,
                "Referer": BASE_URL + "/",
            },
        }

    def localProxy(self, param):
        return [200, "text/plain", b"", {}]

    def action(self, action):
        return {"code": 200, "content": "", "type": "text/plain"}

    def manualVideoCheck(self):
        return True

    def destroy(self):
        pass


# ────────────────────────────── 测试 ──────────────────────────────

if __name__ == "__main__":
    sp = Spider()
    sp.init()

    print("=" * 50)
    print(f"名称: {sp.getName()}")

    print("\n▶ homeContent")
    r = sp.homeContent()
    print(f"  class: {len(r['class'])}")

    print("\n▶ homeVideoContent")
    r = sp.homeVideoContent()
    print(f"  list: {len(r['list'])}")
    if r["list"]:
        print(f"  首项: {r['list'][0]['vod_name'][:30]} id={r['list'][0]['vod_id']}")

    print("\n▶ categoryContent (5228)")
    r = sp.categoryContent("5228")
    print(f"  list: {len(r['list'])}")
    if r["list"]:
        print(f"  首项: {r['list'][0]['vod_name'][:30]} id={r['list'][0]['vod_id']}")

    print("\n▶ detailContent (408675)")
    r = sp.detailContent(["408675"])
    if r["list"]:
        v = r["list"][0]
        print(f"  name: {v['vod_name'][:30]}")
        print(f"  play_from: {v['vod_play_from']}")

    print("\n▶ playerContent (408675)")
    r = sp.playerContent("玩蛋吧", "408675")
    print(f"  playUrl: {r['playUrl'][:80]}")

    print("\n▶ searchContent (自慰)")
    r = sp.searchContent("自慰")
    print(f"  list: {len(r['list'])}")
    if r["list"]:
        print(f"  首项: {r['list'][0]['vod_name'][:30]}")

    print("\n▶ 测试完成")
