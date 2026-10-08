#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lold.py - 交互式点播（串行，每页10条）

分类 1-10 选择，0 下一页分类
进入分类后串行拉播放地址，每页展示10条，0 下一页
失败刷新 token 重试
"""

from __future__ import annotations

import json
import random
import sys
import time

import requests

# ========== 分类关键词（自行追加）==========
VOD_CLASSES = [
    '重口猎奇',
    '迷奸强奸',
    '校园霸凌',
    '真实乱伦',
    '监控偷拍',  
    '学生破处',
    '淫荡孕妇',        
    '萝莉',
    "小学",
    "初中",
    "高中",
    "小马",
    "人妖伪娘",
    '户外露出',
    '绿帽抓奸',
    '反差母犬',
    '少女媚黑',
    '暗网萝莉',
    '少女萝莉',
    '学生',
    '自慰',
    'JK',
    '母子通奸',
    '父女禁恋',
    '兄妹相爱',
    '姐弟情深',
    '舅侄畸恋',
    '全家乱P',
    '师生淫乱',
    '偷窥偷拍',
    '裸聊实录',
    '主播大秀',
    '原创自拍',
    '车震野战',
    'SM捆绑',
    '探花大神',
    '勾引搭讪',
    '最新热点',
    '独家精选',
    '学生校园',
    '网红网暴',
    '热门大瓜',
    '明星黑幕',
    '反差母狗',
    '领导干部',
    '百合',
    '足交',
    '丝袜',
    '内射',
    'Cospaly',
    '换妻Club',
    '偷窥萝莉'
]

CLASS_PER_PAGE = 10
PLAY_PER_PAGE = 10
VLIST_STEP = 40

HOST = "https://dag29jmgma1g.site"
VLIST_URL = f"{HOST}/api/vlist.php"
DETAIL_URL = f"{HOST}/api/Get_vod_list.php"
NEWREG_URL = f"{HOST}/api/newreg.php"

TIMEOUT = 15
DETAIL_RETRY = 5
REG_GAP = 1.2
REG_TRY = 8

session = requests.Session()
token = None
last_reg = 0.0

DEVICES = [
    ("ONEPLUS A5000", "OPR6.170623.013"),
    ("Pixel 4", "QQ3A.200805.001"),
    ("SM-G973F", "QP1A.190711.020"),
    ("Mi 9", "PKQ1.181121.001"),
    ("Redmi Note 8", "QKQ1.200114.002"),
]


def ua():
    m, b = random.choice(DEVICES)
    a = random.choice(["8.0.0", "9", "10", "11", "12"])
    c = random.randint(120, 138)
    return (
        f"Mozilla/5.0 (Linux; Android {a}; {m} Build/{b}; wv) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
        f"Chrome/{c}.0.{random.randint(0,7204)}.{random.randint(100,200)} "
        f"Mobile Safari/537.36 uni-app Html5Plus/1.0 (Immersed/24.0)"
    )


def headers():
    return {
        "User-Agent": ua(),
        "Content-Type": "application/x-www-form-urlencoded",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
    }


def ask(msg):
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        print("\n退出")
        sys.exit(0)


def parse_json(resp):
    if resp is None:
        return None
    t = (resp.text or "").strip()
    if not t:
        return None
    try:
        return resp.json()
    except Exception:
        try:
            return json.loads(t)
        except Exception:
            return None


def find_first(obj, key):
    if isinstance(obj, dict):
        if key in obj and obj[key] not in (None, ""):
            return str(obj[key])
        for v in obj.values():
            r = find_first(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for x in obj:
            r = find_first(x, key)
            if r is not None:
                return r
    return None


def find_all(obj, key, out=None):
    if out is None:
        out = []
    if isinstance(obj, dict):
        if key in obj and obj[key] not in (None, ""):
            out.append(str(obj[key]))
        for v in obj.values():
            find_all(v, key, out)
    elif isinstance(obj, list):
        for x in obj:
            find_all(x, key, out)
    return out


def collect_items(obj, out=None):
    if out is None:
        out = []
    if isinstance(obj, dict):
        if "vod_id" in obj and obj["vod_id"] not in (None, ""):
            out.append(
                {
                    "vod_id": str(obj["vod_id"]),
                    "vod_name": str(obj.get("vod_name") or obj.get("name") or ""),
                }
            )
        else:
            for v in obj.values():
                collect_items(v, out)
    elif isinstance(obj, list):
        for x in obj:
            collect_items(x, out)
    return out


def clean_play_url(raw: str) -> str:
    """接口常返回「正片$https://...」或「第01集$url#第02集$url」，去掉名称前缀，只留真实地址。"""
    if not raw:
        return ""
    s = str(raw).strip()
    if not s or s.lower() in ("null", "none", "undefined"):
        return ""
    # 多集: a$url#b$url -> 取第一段可解析的
    parts = [p for p in s.split("#") if p.strip()]
    candidates = parts if parts else [s]
    urls = []
    for part in candidates:
        part = part.strip()
        if "$" in part:
            # 名称$url  只取最后一个 $ 后面（防止名称里有 $）
            part = part.split("$")[-1].strip()
        if part:
            urls.append(part)
    if not urls:
        return ""
    # 多地址时用 # 拼回纯 URL 列表的第一个展示；完整列表由 extract_play_urls 处理
    return urls[0]


def extract_play_urls(raw: str) -> list[str]:
    """从 vod_play_url 字段解析出所有纯播放地址。"""
    if not raw:
        return []
    s = str(raw).strip()
    if not s or s.lower() in ("null", "none", "undefined"):
        return []
    parts = [p for p in s.split("#") if p.strip()]
    if not parts:
        parts = [s]
    out = []
    for part in parts:
        part = part.strip()
        if "$" in part:
            part = part.split("$")[-1].strip()
        if ok_url(part) and part not in out:
            out.append(part)
    return out


def ok_url(u):
    if not u:
        return False
    s = u.strip()
    if not s or s.lower() in ("null", "none", "undefined"):
        return False
    # 允许带 正片$ 前缀的原始串
    if "$" in s:
        s = s.split("$")[-1].strip()
    return s.startswith(("http://", "https://", "magnet:")) or "http://" in s or "https://" in s


def rate_limited(body):
    if not isinstance(body, dict):
        return False
    msg = str(body.get("msg", ""))
    return "频繁" in msg or "太快" in msg or "频率" in msg


# ---------- token ----------
def newreg_once():
    try:
        r = session.post(
            NEWREG_URL,
            data="device=android&ntoken=&channel_code=vbtQg9D8",
            headers=headers(),
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        print(f"[newreg] 失败: {e}")
        return None, False
    body = parse_json(r)
    if body is None:
        return None, False
    if rate_limited(body):
        print(f"[newreg] 限频: {body.get('msg')}")
        return None, True
    t = None
    if isinstance(body, dict):
        u = body.get("user")
        if isinstance(u, dict) and u.get("token"):
            t = str(u["token"])
    if not t:
        t = find_first(body, "token")
    return t, False


def refresh_token():
    global token, last_reg
    for i in range(REG_TRY):
        gap = REG_GAP - (time.time() - last_reg)
        if gap > 0:
            time.sleep(gap)
        t, limited = newreg_once()
        if t:
            token = t
            last_reg = time.time()
            print(f"[token] {t[:12]}...")
            return t
        if limited:
            wait = min(30.0, 2.0 * (2**i) + random.uniform(0.2, 1.0))
            print(f"[newreg] 退避 {wait:.1f}s")
            time.sleep(wait)
        else:
            time.sleep(REG_GAP)
    print("[newreg] 失败次数过多")
    return None


def get_token(force=False):
    global token
    if force or not token:
        return refresh_token()
    return token


# ---------- api ----------
def api_vlist(vodclass, num):
    data = {
        "num": str(num),
        "pid": "4",
        "area": "全部",
        "vodclass": vodclass,
        "vodyear": "全部",
        "sort": "1",
        "type": "undefined",
    }
    return session.post(VLIST_URL, data=data, headers=headers(), timeout=TIMEOUT)


def api_detail(vod_id, tok):
    data = f"id={vod_id}&token={tok}&channel="
    return session.post(DETAIL_URL, data=data, headers=headers(), timeout=TIMEOUT)


def get_play(vod_id, fallback_name=""):
    """串行取一条播放地址，失败刷新 token 重试。"""
    name = fallback_name
    for attempt in range(DETAIL_RETRY):
        tok = get_token(force=(attempt > 0))
        if not tok:
            continue
        try:
            r = api_detail(vod_id, tok)
        except requests.RequestException as e:
            print(f"  id={vod_id} 网络: {e}")
            time.sleep(0.3)
            continue
        body = parse_json(r)
        if body:
            n = find_first(body, "vod_name")
            if n:
                name = n
            raw_list = find_all(body, "vod_play_url") if body else []
            urls = []
            for raw in raw_list:
                for u in extract_play_urls(raw):
                    if u not in urls:
                        urls.append(u)
            if urls:
                return {
                    "vod_id": vod_id,
                    "vod_name": name,
                    "vod_play_url": urls[0],
                    "all_play_urls": urls,
                }
        print(f"  id={vod_id} 失败，刷 token ({attempt+1}/{DETAIL_RETRY})")
        time.sleep(0.2)
    return {
        "vod_id": vod_id,
        "vod_name": name,
        "vod_play_url": "",
        "all_play_urls": [],
    }


# ---------- 列表缓冲 ----------
class Cursor:
    def __init__(self, vodclass):
        self.vodclass = vodclass
        self.buf = []
        self.i = 0
        self.num = 0
        self.done = False
        self.seen = set()
        self.page = 0

    def pull(self):
        if self.done:
            return False
        print(f"[vlist] num={self.num} class={self.vodclass!r}")
        try:
            r = api_vlist(self.vodclass, self.num)
        except requests.RequestException as e:
            print(f"[vlist] 失败: {e}")
            return False
        body = parse_json(r)
        if body is None:
            print("[vlist] 无效响应")
            return False
        items = collect_items(body)
        added = 0
        for it in items:
            if it["vod_id"] not in self.seen:
                self.seen.add(it["vod_id"])
                self.buf.append(it)
                added += 1
        if added == 0:
            print("[vlist] 没有更多")
            self.done = True
            return False
        self.num += VLIST_STEP
        print(f"[vlist] +{added} 缓冲={len(self.buf)}")
        return True

    def next_meta(self, n=PLAY_PER_PAGE):
        while self.i + n > len(self.buf) and not self.done:
            if not self.pull():
                break
        batch = self.buf[self.i : self.i + n]
        self.i += len(batch)
        return batch


# ---------- UI ----------
def pick_class():
    page = 0
    total = len(VOD_CLASSES)
    while True:
        print("\n" + "=" * 40)
        start = page * CLASS_PER_PAGE
        chunk = VOD_CLASSES[start : start + CLASS_PER_PAGE]
        if not chunk:
            page = 0
            continue
        print(f"【分类】第{page+1}页 / 共{total}个")
        print("  1-10 选择  0 下一页  q 退出\n")
        for i, name in enumerate(chunk, 1):
            print(f"  {i}. {name}")
        print("  0. 下一页")
        print("  q. 退出")
        c = ask("\n选择: ")
        if c.lower() in ("q", "quit", "exit"):
            return None
        if c == "0":
            if start + CLASS_PER_PAGE < total:
                page += 1
            else:
                page = 0
            continue
        if c.isdigit():
            n = int(c)
            if 1 <= n <= len(chunk):
                return chunk[n - 1]
        print("无效输入")


def show_page(cls, page_no, items):
    print("\n" + "-" * 40)
    print(f"【{cls}】第 {page_no} 页  共{len(items)}条")
    print("  1-10 看详情  0 下一页  b 返回  q 退出\n")
    if not items:
        print("  (无数据)")
        return
    for i, it in enumerate(items, 1):
        name = it.get("vod_name") or "(无标题)"
        url = it.get("vod_play_url") or "(失败)"
        print(f"  {i}. [{it['vod_id']}] {name}")
        print(f"     {url}")
    print("\n  0. 下一页")
    print("  b. 返回分类")
    print("  q. 退出")


def show_detail(it):
    print("\n" + "-" * 40)
    print(f"标题: {it.get('vod_name') or '(无)'}")
    print(f"ID  : {it.get('vod_id')}")
    urls = list(it.get("all_play_urls") or [])
    main = it.get("vod_play_url") or ""
    if main and main not in urls:
        urls.insert(0, main)
    if not urls:
        print("播放: (无)")
    else:
        print("播放:")
        for i, u in enumerate(urls, 1):
            print(f"  [{i}] {u}")


def browse(cls):
    print(f"\n进入: {cls}")
    if not get_token(False):
        print("无 token")
        return

    cur = Cursor(cls)
    page_items = []

    def load_next():
        nonlocal page_items
        meta = cur.next_meta(PLAY_PER_PAGE)
        if not meta:
            print("没有更多视频")
            return False
        cur.page += 1
        print(f"\n串行获取第 {cur.page} 页（{len(meta)} 条）...")
        page_items = []
        for i, m in enumerate(meta, 1):
            print(f"  [{i}/{len(meta)}] id={m['vod_id']}")
            page_items.append(get_play(m["vod_id"], m.get("vod_name") or ""))
        return True

    if not load_next():
        ask("回车返回...")
        return

    while True:
        show_page(cls, cur.page, page_items)
        c = ask("\n选择: ")
        if c.lower() in ("q", "quit", "exit"):
            sys.exit(0)
        if c.lower() == "b":
            return
        if c == "0":
            if not load_next():
                ask("已到底，回车...")
            continue
        if c.isdigit():
            n = int(c)
            if 1 <= n <= len(page_items):
                show_detail(page_items[n - 1])
                ask("回车继续...")
                continue
        print("无效输入")


def main():
    print("=" * 40)
    print("  lold  交互点播  串行/每页10条")
    print("=" * 40)
    print("改分类: 编辑本文件顶部 VOD_CLASSES\n")
    while True:
        cls = pick_class()
        if cls is None:
            print("再见")
            return 0
        browse(cls)


if __name__ == "__main__":
    raise SystemExit(main())
