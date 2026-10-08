#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lold.py - 全自动点播（抓取全部）"""

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
# 移除 MAX_PAGES_PER_CLASS，改为抓取全部

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
        self.total_pages = 0  # 记录总页数

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
            print("[vlist] 没有更多数据")
            self.done = True
            return False
        self.num += VLIST_STEP
        self.total_pages += 1
        print(f"[vlist] +{added} 缓冲={len(self.buf)} 页={self.total_pages}")
        return True

    def next_meta(self, n=PLAY_PER_PAGE):
        while self.i + n > len(self.buf) and not self.done:
            if not self.pull():
                break
        batch = self.buf[self.i : self.i + n]
        self.i += len(batch)
        return batch

    def has_more(self):
        """检查是否还有更多数据"""
        return not self.done or self.i < len(self.buf)


# ---------- 全自动抓取（全部） ----------
def fetch_class_all(cls):
    """抓取单个分类的所有视频，返回结果列表"""
    print(f"\n{'='*40}")
    print(f"开始抓取分类: {cls}")
    print(f"{'='*40}")
    
    if not get_token(False):
        print(f"无 token，跳过 {cls}")
        return []

    cur = Cursor(cls)
    all_results = []
    page_num = 0

    while True:
        # 获取一批数据
        meta = cur.next_meta(PLAY_PER_PAGE)
        if not meta:
            if cur.done:
                print(f"分类 {cls} 已全部抓取完成（共 {cur.total_pages} 页）")
            else:
                print(f"分类 {cls} 没有更多视频")
            break
        
        page_num += 1
        print(f"\n抓取第 {page_num} 页（{len(meta)} 条）...")
        
        page_results = []
        for i, m in enumerate(meta, 1):
            print(f"  [{i}/{len(meta)}] id={m['vod_id']}")
            result = get_play(m["vod_id"], m.get("vod_name") or "")
            page_results.append(result)
            # 抓取间隔，避免请求过快
            time.sleep(0.5)
        
        all_results.extend(page_results)
        valid_count = len([r for r in page_results if r.get('vod_play_url')])
        print(f"本页获取 {valid_count}/{len(meta)} 个有效地址")
        
        # 如果没数据了，退出
        if len(meta) < PLAY_PER_PAGE and cur.done:
            print(f"分类 {cls} 已到最后一页")
            break
        
        # 页面间隔
        time.sleep(1)
    
    print(f"分类 {cls} 共抓取 {len(all_results)} 条，{cur.total_pages} 页")
    return all_results


def save_results(all_data, filename="results.json"):
    """保存结果到JSON文件"""
    # 按分类统计
    class_stats = {}
    for item in all_data:
        # 这里无法直接获取分类，因为结果中没有保存分类信息
        pass
    
    output = {
        "total": len(all_data),
        "valid": len([r for r in all_data if r.get('vod_play_url')]),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "data": all_data
    }
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到: {filename}")
        return True
    except Exception as e:
        print(f"保存失败: {e}")
        return False


def print_summary(all_data):
    """打印汇总信息"""
    total = len(all_data)
    valid = len([r for r in all_data if r.get('vod_play_url')])
    invalid = total - valid
    
    print(f"\n{'='*40}")
    print(f"抓取完成！")
    print(f"总计: {total} 条")
    print(f"有效: {valid} 条")
    print(f"无效: {invalid} 条")
    print(f"有效率: {valid/total*100:.1f}%" if total > 0 else "有效率: 0%")
    print(f"{'='*40}")
    
    # 打印前10条示例
    print("\n示例数据（前10条）:")
    for i, item in enumerate(all_data[:10], 1):
        print(f"  {i}. [{item['vod_id']}] {item.get('vod_name', '')}")
        url = item.get('vod_play_url', '')
        if url:
            print(f"     {url[:80]}..." if len(url) > 80 else f"     {url}")
        else:
            print(f"     (无地址)")


# ---------- 主函数 ----------
def main():
    print("=" * 40)
    print("  lold  全自动点播抓取（全部数据）")
    print("=" * 40)
    print(f"分类数: {len(VOD_CLASSES)}")
    print(f"抓取模式: 全部（直到没有更多数据为止）")
    print("=" * 40)
    
    all_results = []
    start_time = time.time()
    total_valid = 0
    
    for idx, cls in enumerate(VOD_CLASSES, 1):
        print(f"\n{'#'*40}")
        print(f"[{idx}/{len(VOD_CLASSES)}] 处理分类: {cls}")
        print(f"{'#'*40}")
        
        results = fetch_class_all(cls)
        all_results.extend(results)
        
        valid_in_class = len([r for r in results if r.get('vod_play_url')])
        total_valid += valid_in_class
        print(f"分类完成: {len(results)} 条，有效 {valid_in_class} 条")
        
        # 定期保存中间结果
        if idx % 3 == 0:
            save_results(all_results, f"results_partial_{idx}.json")
        
        # 分类间隔
        time.sleep(2)
    
    # 最终保存
    save_results(all_results, "results_final.json")
    
    elapsed = time.time() - start_time
    print(f"\n{'='*40}")
    print(f"全部完成！")
    print(f"总耗时: {elapsed:.1f} 秒 ({elapsed/60:.1f} 分钟)")
    print_summary(all_results)
    print(f"{'='*40}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())