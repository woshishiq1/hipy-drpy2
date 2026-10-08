#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import re
import json
import base64
import html as html_lib
import urllib.request
import urllib.parse
from urllib.parse import urlparse, quote, unquote
import http.cookiejar
import gzip
import zlib
import ssl

try:
    from base.spider import Spider as SpiderBase
except ImportError:
    class SpiderBase(object):
        def getCache(self, key): return None
        def setCache(self, key, value): return "fail"
        def delCache(self, key): return "fail"

def unpack_packer(p, a, c, k):
    def int2base(x, base):
        chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if x < 0:
            return "-" + int2base(-x, base)
        res = []
        while x > 0:
            res.append(chars[x % base])
            x //= base
        return "".join(reversed(res)) if res else "0"

    d = {}
    while c > 0:
        c -= 1
        key = int2base(c, a)
        val = k[c] if c < len(k) and k[c] else key
        d[key] = val

    def replace_token(match):
        w = match.group(0)
        return d.get(w, w)

    return re.sub(r'\b\w+\b', replace_token, p)

class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.defaultHost = "https://www.thisav.my"
        self.baseHost = self.defaultHost
        self.navUrls = ["https://x99dh.cc", "https://x99dh.one"]
        self.tgGroup = "https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandActor = "TG群: https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandDirector = "ZakaTV"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self.options = {}

        self.color_palette = [
            ("1e3a8a", "60a5fa"), ("14532d", "4ade80"), ("701a75", "f472b6"),
            ("7c2d12", "fb923c"), ("1f2937", "38bdf8"), ("312e81", "818cf8"),
            ("831843", "fb7185"), ("064e3b", "34d399"), ("3b0764", "c084fc")
        ]

        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx)
        )

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.options = extend
        elif extend:
            try:
                self.options = json.loads(extend)
            except Exception:
                self.options = {}

        self._get_active_host()
        return True

    def getName(self):
        return "Zaka·ThisAV完整版"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd", "index.png"))

    def manualVideoCheck(self):
        return False

    def _resolve_nav_sites(self):
        headers = {
            "User-Agent": self._ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate"
        }

        for nav in self.navUrls:
            try:
                req = urllib.request.Request(nav, headers=headers)
                with self.opener.open(req, timeout=8) as resp:
                    raw = resp.read()
                    enc = getattr(resp, "headers", {}).get("Content-Encoding", "")
                    if raw.startswith(b"\x1f\x8b") or enc == "gzip":
                        raw = gzip.decompress(raw)
                    text = raw.decode("utf-8", errors="ignore")
            except urllib.error.HTTPError as e:
                try:
                    raw = e.read()
                    if raw.startswith(b"\x1f\x8b"):
                        raw = gzip.decompress(raw)
                    text = raw.decode("utf-8", errors="ignore")
                except Exception:
                    text = ""
            except Exception:
                continue

            if not text:
                continue

            b64_blocks = re.findall(r'["\']([A-Za-z0-9+/=]{100,})["\']', text)
            for b in b64_blocks:
                try:
                    decoded = base64.b64decode(b).decode("utf-8", errors="ignore")
                    unquoted = urllib.parse.unquote(decoded)
                    if "MissAV" in unquoted and "[" in unquoted:
                        site_list = json.loads(unquoted)
                        for item in site_list:
                            if item.get("name") == "MissAV":
                                cand_urls = []
                                main_url = item.get("url", "")
                                if main_url:
                                    cand_urls.append(main_url)
                                for u_obj in item.get("urls", []):
                                    u = u_obj.get("url", "")
                                    if u and u not in cand_urls:
                                        cand_urls.append(u)

                                for c_url in cand_urls:
                                    parsed = urllib.parse.urlparse(c_url)
                                    base = "%s://%s" % (parsed.scheme, parsed.netloc)
                                    chk = self._fetch(base + "/dm247/cn", check_host=False)
                                    if chk.get("code") == 200:
                                        return base
                except Exception:
                    continue

        return self.defaultHost

    def _get_active_host(self):
        cached_host = self.getCache("thisav_live_host")
        if cached_host and cached_host.startswith("http"):
            self.baseHost = cached_host
            return self.baseHost

        new_host = self._resolve_nav_sites()
        self.baseHost = new_host if new_host else self.defaultHost
        self.setCache("thisav_live_host", self.baseHost)
        return self.baseHost

    def _fetch(self, target_url, referer="", check_host=True):
        if not target_url:
            return {"code": 0, "text": "", "err": "", "final_url": ""}
        if target_url.startswith("//"):
            target_url = "https:" + target_url
        elif target_url.startswith("/"):
            target_url = self.baseHost + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.baseHost + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

        last_err = ""
        for attempt in range(2):
            try:
                req = urllib.request.Request(target_url, headers=headers)
                with self.opener.open(req, timeout=12) as resp:
                    code = resp.getcode()
                    final_url = resp.geturl()
                    raw = resp.read()
                    enc = getattr(resp, "headers", {}).get("Content-Encoding", "")
                    if raw.startswith(b"\x1f\x8b") or enc == "gzip":
                        raw = gzip.decompress(raw)
                    elif enc == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except Exception:
                            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                    try:
                        text = raw.decode("utf-8")
                    except Exception:
                        text = raw.decode("latin1", errors="ignore")
                    return {"code": code, "text": text, "err": "", "final_url": final_url}
            except urllib.error.HTTPError as e:
                last_err = "HTTP %s" % e.code
                if e.code in (404, 502, 503) and check_host and attempt == 0:
                    self.delCache("thisav_live_host")
                    self._get_active_host()
                    target_url = re.sub(r'https?://[^/]+', self.baseHost, target_url)
                    continue
                err_raw = ""
                try:
                    err_raw = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass
                return {"code": e.code, "text": err_raw, "err": str(e), "final_url": target_url}
            except Exception as e:
                last_err = str(e)
                if attempt == 0 and check_host:
                    self.delCache("thisav_live_host")
                    self._get_active_host()
                    target_url = re.sub(r'https?://[^/]+', self.baseHost, target_url)
                    continue
                return {"code": -1, "text": "", "err": str(e), "final_url": target_url}

        return {"code": -1, "text": "", "err": last_err, "final_url": target_url}

    def homeContent(self, filter):
        classes = [
            {"type_name": "中文字幕", "type_id": "/dm278/cn/chinese-subtitle"},
            {"type_name": "最近更新", "type_id": "/dm539/cn/new"},
            {"type_name": "新作上市", "type_id": "/dm635/cn/release"},
            {"type_name": "无码流出", "type_id": "/dm817/cn/uncensored-leak"},
            {"type_name": "女优一览", "type_id": "actresses"},
            {"type_name": "女优排行", "type_id": "actresses_ranking"},
            {"type_name": "全部类型", "type_id": "genres"},
            {"type_name": "全部发行商", "type_id": "makers"},
            {"type_name": "VR专区", "type_id": "/cn/genres/VR"},
            {"type_name": "今日热门", "type_id": "/dm301/cn/today-hot"},
            {"type_name": "本週热门", "type_id": "/dm170/cn/weekly-hot"},
            {"type_name": "本月热门", "type_id": "/dm273/cn/monthly-hot"},
            {"type_name": "FC2", "type_id": "/dm597/cn/fc2"},
            {"type_name": "HEYZO", "type_id": "/dm2208642/cn/heyzo"},
            {"type_name": "东京热", "type_id": "/dm42/cn/tokyohot"},
            {"type_name": "一本道", "type_id": "/dm5199603/cn/1pondo"},
            {"type_name": "加勒比", "type_id": "/dm7704788/cn/caribbeancom"},
            {"type_name": "加勒比PR", "type_id": "/dm91887/cn/caribbeancompr"},
            {"type_name": "天然素人", "type_id": "/dm7208981/cn/10musume"},
            {"type_name": "熟女俱乐部", "type_id": "/dm3600557/cn/pacopacomama"},
            {"type_name": "Gachinco", "type_id": "/dm150/cn/gachinco"},
            {"type_name": "SIRO", "type_id": "/dm36/cn/siro"},
            {"type_name": "LUXU", "type_id": "/dm34/cn/luxu"},
            {"type_name": "GANA", "type_id": "/dm34/cn/gana"},
            {"type_name": "S-CUTE", "type_id": "/dm38/cn/scute"},
            {"type_name": "PRESTIGE", "type_id": "/dm1004/cn/maan"},
            {"type_name": "ARA", "type_id": "/dm34/cn/ara"},
            {"type_name": "顽皮4610", "type_id": "/dm33/cn/naughty4610"},
            {"type_name": "顽皮0930", "type_id": "/dm37/cn/naughty0930"},
            {"type_name": "麻豆传媒", "type_id": "/dm63/cn/madou"},
            {"type_name": "TWAV", "type_id": "/dm31/cn/twav"},
            {"type_name": "Furuke", "type_id": "/dm15/cn/furuke"},
            {"type_name": "人妻斩", "type_id": "/dm37/cn/marriedslash"},
            {"type_name": "XXX-AV", "type_id": "/dm42/cn/xxxav"}
        ]

        result = {"class": classes}

        if filter:
            filter_sort = {
                "key": "sort",
                "name": "排序",
                "init": "default",
                "value": [
                    {"n": "默认排序", "v": "default"},
                    {"n": "发行日期", "v": "released_at"},
                    {"n": "最近更新", "v": "published_at"},
                    {"n": "收藏最多", "v": "saved"},
                    {"n": "今日浏览", "v": "today_views"},
                    {"n": "本周浏览", "v": "weekly_views"},
                    {"n": "本月浏览", "v": "monthly_views"},
                    {"n": "总浏览数", "v": "views"}
                ]
            }
            filter_type = {
                "key": "filters",
                "name": "过滤",
                "init": "all",
                "value": [
                    {"n": "所有", "v": "all"},
                    {"n": "单人作品", "v": "individual"},
                    {"n": "多人作品", "v": "multiple"},
                    {"n": "中文字幕", "v": "chinese-subtitle"}
                ]
            }

            height_ranges = [
                "131-135", "136-140", "141-145", "146-150", "151-155",
                "156-160", "161-165", "166-170", "171-175", "176-180",
                "181-185", "186-190"
            ]
            filter_actress_height = {
                "key": "height",
                "name": "身高",
                "init": "all",
                "value": [{"n": "选择身高", "v": "all"}] + [{"n": "%scm" % r, "v": r} for r in height_ranges]
            }

            cups = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q"]
            filter_actress_cup = {
                "key": "cup",
                "name": "罩杯",
                "init": "all",
                "value": [{"n": "选择罩杯", "v": "all"}] + [{"n": "%s 罩杯" % c, "v": c} for c in cups]
            }

            filter_actress_age = {
                "key": "age",
                "name": "年龄",
                "init": "all",
                "value": [
                    {"n": "选择年龄", "v": "all"},
                    {"n": "< 20", "v": "<20"},
                    {"n": "20 - 30", "v": "20-30"},
                    {"n": "30 - 40", "v": "30-40"},
                    {"n": "40 - 50", "v": "40-50"},
                    {"n": "50 - 60", "v": "50-60"},
                    {"n": "> 60", "v": ">60"}
                ]
            }

            years = [str(y) for y in range(2026, 2007, -1)]
            filter_actress_debut = {
                "key": "debut",
                "name": "出道年份",
                "init": "all",
                "value": [{"n": "选择出道年份", "v": "all"}] + [{"n": "%s 以前" % y, "v": y} for y in years]
            }

            filter_actress_sort = {
                "key": "sort",
                "name": "排序",
                "init": "default",
                "value": [
                    {"n": "默认排序", "v": "default"},
                    {"n": "影片最多", "v": "videos"}
                ]
            }

            filters_dict = {}
            for item in classes:
                cid = item["type_id"]
                if cid == "actresses":
                    filters_dict[cid] = [
                        filter_actress_sort,
                        filter_actress_height,
                        filter_actress_cup,
                        filter_actress_age,
                        filter_actress_debut
                    ]
                elif cid not in ("actresses_ranking", "genres", "makers"):
                    filters_dict[cid] = [filter_sort, filter_type]

            result["filters"] = filters_dict

        return result

    def homeVideoContent(self):
        res = self.categoryContent("/dm539/cn/new", "1", False, {})
        return {"list": res.get("list", [])}

    def _parse_cards(self, html, mode="video"):
        body = html
        if "</nav>" in body:
            body = body.split("</nav>", 1)[1]
        elif "</header>" in body:
            body = body.split("</header>", 1)[1]

        vod_list = []
        seen_ids = set()

        if mode in ("actress", "actress_ranking"):
            is_ranking = (mode == "actress_ranking")
            chunks = re.findall(r'(<div[^>]*>\s*<a[^>]+href=["\'][^"\']*/actresses/[^"\']+["\'][^>]*>[\s\S]*?</div>\s*</div>)', body)
            if not chunks:
                chunks = re.findall(r'(<a[^>]+href=["\'][^"\']*/actresses/[^"\']+["\'][^>]*>[\s\S]*?</a>\s*<div[\s\S]*?</div>)', body)

            for block in chunks:
                href_m = re.search(r'href=["\']([^"\']*/actresses/[^"\']+)["\']', block)
                if not href_m:
                    continue
                href = href_m.group(1).strip()
                if href.endswith("/actresses/ranking") or "actresses/ranking" in href:
                    continue
                if href in seen_ids:
                    continue
                seen_ids.add(href)

                pic_m = re.search(r'(?:data-src|data-original|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', block, re.I)
                raw_pic = pic_m.group(1).strip() if pic_m else ""
                if raw_pic.startswith("//"):
                    raw_pic = "https:" + raw_pic
                elif raw_pic.startswith("/"):
                    raw_pic = urllib.parse.urljoin(self.baseHost, raw_pic)
                proxy_pic = ("%s@Referer=%s/@User-Agent=%s" % (raw_pic, self.baseHost, quote(self._ua))) if raw_pic else ""

                alt_m = re.search(r'alt=["\']([^"\']+)["\']', block)
                title = alt_m.group(1).strip() if alt_m else ""

                if not title:
                    txt_cands = re.findall(r'>([^<]+)<', block)
                    for tc in txt_cands:
                        t = tc.strip()
                        if t and not any(k in t for k in ("影片", "条", "條", "部", "出道", "年", "第", "名", "Ranking")):
                            if len(t) >= 2 and not t.isdigit():
                                title = t
                                break
                if not title:
                    title = "女优"

                title = html_lib.unescape(title)

                if is_ranking:
                    rank_m = re.search(r'(第\s*\d+\s*名)', block)
                    sub_desc = rank_m.group(1).replace(" ", "") if rank_m else ""
                    remarks_text = ("ZakaTV · %s" % sub_desc) if sub_desc else "ZakaTV"
                else:
                    count_m = re.search(r'(\d+)\s*(?:条影片|條影片|部影片|部)', block)
                    debut_m = re.search(r'(\d{4})\s*(?:出道|年出道)', block)
                    meta_arr = []
                    if count_m:
                        meta_arr.append("%s部" % count_m.group(1))
                    if debut_m:
                        meta_arr.append("%s出道" % debut_m.group(1))
                    sub_desc = " · ".join(meta_arr) if meta_arr else ""
                    remarks_text = ("ZakaTV · %s" % sub_desc) if sub_desc else "ZakaTV"

                display_name = ("%s\n%s" % (title, sub_desc)) if sub_desc else title

                vod_list.append({
                    "vod_id": "folder@" + (href if href.startswith("http") else urllib.parse.urljoin(self.baseHost, href)),
                    "vod_name": display_name,
                    "vod_pic": proxy_pic if proxy_pic else "https://dummyimage.com/300x300/222222/ffffff.png&text=" + quote(title[:4]),
                    "vod_remarks": remarks_text,
                    "vod_tag": "folder",
                    "style": {"type": "oval", "ratio": 1.0}
                })
            return vod_list

        if mode in ("genres", "makers"):
            target_key = "genres" if mode == "genres" else "makers"
            cell_pattern = r'(<div>\s*<a[^>]+href=["\'][^"\']*/' + target_key + r'/[^"\']+["\'][^>]*>[\s\S]*?</div>)'
            cells = re.findall(cell_pattern, body)

            for idx, cell in enumerate(cells):
                href_m = re.search(r'href=["\']([^"\']*/' + target_key + r'/[^"\']+)["\']', cell)
                if not href_m:
                    continue
                clean_href = href_m.group(1).strip()
                if clean_href in seen_ids or clean_href.endswith(("/" + target_key, "/" + target_key + "/")):
                    continue
                seen_ids.add(clean_href)

                title_m = re.search(r'<a[^>]+class=["\'][^"\']*text-nord13[^"\']*["\'][^>]*>([\s\S]*?)</a>', cell)
                if not title_m:
                    title_m = re.search(r'<a[^>]+href=["\'][^"\']*/' + target_key + r'/[^"\']+["\'][^>]*>([\s\S]*?)</a>', cell)
                raw_title = title_m.group(1).strip() if title_m else ""
                title = html_lib.unescape(re.sub(r'<[^>]+>', '', raw_title)).strip()

                if not title:
                    continue

                count_m = re.search(r'(\d+)\s*(?:条影片|條影片|部影片|部)', cell)
                remarks = ("ZakaTV · %s部" % count_m.group(1)) if count_m else "ZakaTV"

                first_char = title[0].strip().upper()
                bg_color, fg_color = self.color_palette[idx % len(self.color_palette)]
                card_pic = "https://dummyimage.com/640x360/%s/%s.png&text=%s" % (
                    bg_color, fg_color, quote(first_char)
                )

                vod_list.append({
                    "vod_id": "folder@" + (clean_href if clean_href.startswith("http") else urllib.parse.urljoin(self.baseHost, clean_href)),
                    "vod_name": title,
                    "vod_pic": card_pic,
                    "vod_remarks": remarks,
                    "vod_tag": "folder",
                    "style": {"type": "rect", "ratio": 1.78}
                })
            return vod_list

        card_chunks = []
        if 'class="relative group' in body:
            card_chunks = body.split('class="relative group')[1:]
        elif 'class="thumbnail' in body:
            card_chunks = body.split('class="thumbnail')[1:]
        else:
            card_chunks = re.findall(r'(<a[^>]+href=["\'](?:https?://[^"\']+|/[^"\']+)["\'][^>]*>[\s\S]*?</a>)', body)

        banned_slugs = {
            "chinese-subtitle", "new", "release", "uncensored-leak", "today-hot",
            "weekly-hot", "monthly-hot", "genres", "actresses", "makers", "series", "tags",
            "vip", "saved", "playlists", "history", "login", "register", "siro", "luxu", "gana"
        }

        for ch in card_chunks:
            href_m = re.search(r'href=["\']([^"\']*/(?:cn|dm\d+/cn)/([A-Za-z0-9_-]+))["\']', ch)
            if not href_m:
                continue
            full_href, dvd_id = href_m.groups()
            dvd_low = dvd_id.lower()

            if dvd_low in banned_slugs or dvd_low in seen_ids or len(dvd_id) < 3:
                continue
            seen_ids.add(dvd_low)

            title = ""
            name_div_m = re.search(r'<div[^>]*class=["\'][^"\']*(?:title|my-2|font-semibold)[^"\']*["\'][^>]*>([\s\S]*?)</div>', ch)
            if name_div_m:
                cand_title = re.sub(r'<[^>]+>', '', name_div_m.group(1)).strip()
                if cand_title and cand_title.lower() != dvd_low and len(cand_title) >= len(dvd_id):
                    title = cand_title

            if not title:
                alt_m = re.search(r'alt=["\']([^"\']+)["\']', ch)
                if alt_m:
                    cand_alt = alt_m.group(1).strip()
                    if cand_alt and cand_alt.lower() != dvd_low and len(cand_alt) >= len(dvd_id):
                        title = cand_alt

            if not title:
                a_tags = re.findall(r'<a[^>]*>([\s\S]*?)</a>', ch)
                for a_inner in a_tags:
                    t_str = re.sub(r'<[^>]+>', '', a_inner).strip()
                    if t_str and t_str.lower() != dvd_low and len(t_str) > len(dvd_id):
                        if not any(k in t_str for k in ("item.", "HD", "FHD", "4K", ":", "条影片")):
                            title = t_str
                            break

            if not title:
                txt_cands = re.findall(r'>([^<]{4,120})<', ch)
                for tc in txt_cands:
                    t_str = tc.strip()
                    if t_str and t_str.lower() != dvd_low and len(t_str) > len(dvd_id):
                        if not any(k in t_str for k in ("item.", "HD", "FHD", "4K", ":", "条影片")):
                            title = t_str
                            break

            if not title:
                title = dvd_id.upper()

            title = html_lib.unescape(title)

            pic_m = re.search(r'(?:data-src|data-original|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', ch, re.I)
            if pic_m and "item.dvd_id" not in pic_m.group(1):
                raw_pic = pic_m.group(1).strip()
            else:
                raw_pic = "https://spic2-147.71352.men/%s/cover-n.jpg" % dvd_low

            if raw_pic.startswith("//"):
                raw_pic = "https:" + raw_pic

            proxy_pic = "%s@Referer=%s/@User-Agent=%s" % (raw_pic, self.baseHost, quote(self._ua))

            dur_m = re.search(r'(\d{1,2}:\d{2}(?::\d{2})?)', ch)
            dur = ("ZakaTV · %s" % dur_m.group(1)) if dur_m else "ZakaTV"

            full_vod_id = full_href if full_href.startswith("http") else urllib.parse.urljoin(self.baseHost, full_href)

            vod_list.append({
                "vod_id": full_vod_id,
                "vod_name": title,
                "vod_pic": proxy_pic,
                "vod_remarks": dur,
                "style": {"type": "rect", "ratio": 1.78}
            })

        return vod_list

    def categoryContent(self, tid, pg, filter, extend):
        slug = str(tid).strip()
        page = int(pg) if str(pg).isdigit() else 1

        if slug.startswith("folder@"):
            target_url = slug.replace("folder@", "")
            parse_mode = "video"
        elif slug == "actresses":
            target_url = "%s/cn/actresses" % self.baseHost
            parse_mode = "actress"
        elif slug == "actresses_ranking":
            target_url = "%s/cn/actresses/ranking" % self.baseHost
            parse_mode = "actress_ranking"
        elif slug == "genres":
            target_url = "%s/cn/genres" % self.baseHost
            parse_mode = "genres"
        elif slug == "makers":
            target_url = "%s/cn/makers" % self.baseHost
            parse_mode = "makers"
        else:
            clean_route = slug.rstrip("/")
            target_url = "%s%s" % (self.baseHost, clean_route)
            parse_mode = "video"

        query_parts = []
        if page > 1:
            query_parts.append("page=%d" % page)

        if isinstance(extend, dict):
            if parse_mode == "actress":
                for param_k in ("height", "cup", "age", "debut"):
                    val = extend.get(param_k)
                    if val and val != "all":
                        query_parts.append("%s=%s" % (param_k, quote(val)))
                sort_val = extend.get("sort")
                if sort_val and sort_val != "default":
                    query_parts.append("sort=%s" % sort_val)
            elif parse_mode == "video":
                active_sort = extend.get("sort", "default")
                if active_sort and active_sort != "default":
                    query_parts.append("sort=%s" % active_sort)
                active_filters = extend.get("filters", "all")
                if active_filters and active_filters != "all":
                    query_parts.append("filters=%s" % active_filters)

        if query_parts:
            sep = "&" if "?" in target_url else "?"
            target_url = "%s%s%s" % (target_url, sep, "&".join(query_parts))

        res = self._fetch(target_url, referer=self.baseHost + "/dm247/cn")
        vod_list = self._parse_cards(res.get("text", ""), parse_mode)

        return {
            "page": page,
            "pagecount": (page + 1) if len(vod_list) >= 12 else page,
            "limit": len(vod_list),
            "total": 9999,
            "list": vod_list
        }

    def _extract_surrit_uuid(self, html):
        if not html:
            return ""

        # 1. 强特征：hls.loadSource 中绑定的正片 UUID
        hls_match = re.search(r'hls\.loadSource\(["\']https?://[^/]+/([a-f0-9-]{36})/playlist\.m3u8["\']\)', html)
        if hls_match:
            return hls_match.group(1)

        # 2. 匹配 urls 数组（排除带 sample/preview 的片段）
        urls_block = re.search(r'urls:\s*\[\s*["\']([^"\']+)["\']', html)
        if urls_block:
            target_link = urls_block.group(1)
            if "sample" not in target_link and "preview" not in target_link:
                u_m = re.search(r'([a-f0-9-]{36})', target_link)
                if u_m:
                    return u_m.group(1)

        # 3. 扫描 script 标签，提取不包含 user_uuid、preview、sample 的正片 UUID
        scripts = re.findall(r'<script[^>]*>([\s\S]*?)</script>', html)
        for sc in scripts:
            if ("surrit.com" in sc or "sixyik.com" in sc) and "sample" not in sc:
                uuids = re.findall(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', sc)
                for u in uuids:
                    u_pos = sc.find(u)
                    surround = sc[max(0, u_pos - 40):min(len(sc), u_pos + 60)]
                    if not any(bad in surround for bad in ("user_uuid", "sample", "preview", "thumbnail", "recombee")):
                        return u

        # 4. 全局提取长视频特征
        cands = re.findall(r'https?://(?:surrit\.com|sixyik\.com)/([a-f0-9-]{36})/(?:playlist\.m3u8)?', html)
        for c in cands:
            c_pos = html.find(c)
            if "sample" not in html[max(0, c_pos - 30):min(len(html), c_pos + 60)]:
                return c

        return ""

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        target_url = str(raw_id).strip()

        if not target_url.startswith("http"):
            target_url = urllib.parse.urljoin(self.baseHost, target_url)

        res = self._fetch(target_url)
        html_text = res.get("text", "")
        if not html_text:
            return {"list": []}

        title_m = re.search(r'<title>(.*?)</title>', html_text, re.I)
        raw_title = title_m.group(1).strip() if title_m else "精彩视频"
        vod_name = raw_title.split(" - ")[0].split(" | ")[0].strip()

        poster_m = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html_text, re.I)
        vod_pic = poster_m.group(1).strip() if poster_m else ""

        from_list = []
        url_list = []
        proxy_prefix = "%s/jmpres/\\1/" % self.baseHost

        # 方案 A: 增强版通用 Packer 逆向解密 (支持多种换行与混淆排版)
        packer_matches = re.findall(r"eval\(function\(p,a,c,k,e,[rd]\)[\s\S]*?\}\((['\"][\s\S]*?['\"])\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(['\"][^'\"]+['\"])\.split", html_text)
        if not packer_matches:
            packer_matches = re.findall(r"\}\s*\(\s*(['\"][\s\S]*?['\"])\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(['\"][^'\"]+['\"])\.split", html_text)

        if packer_matches:
            p_raw, a_str, c_str, k_raw = packer_matches[0]
            p = p_raw.strip("'\"")
            a = int(a_str)
            c = int(c_str)
            k = k_raw.strip("'\"").split("|")
            unpacked_code = unpack_packer(p, a, c, k)

            source_1080 = re.search(r"source1280\s*=\s*['\"]([^'\"]+)['\"]", unpacked_code)
            source_720 = re.search(r"source842\s*=\s*['\"]([^'\"]+)['\"]", unpacked_code)
            source_auto = re.search(r"source\s*=\s*['\"]([^'\"]+)['\"]", unpacked_code)

            for name, src_m in [("1080P超清", source_1080), ("720P高清", source_720), ("自适应线路", source_auto)]:
                if src_m:
                    u = src_m.group(1)
                    if "sample" not in u and "preview" not in u:
                        proxy_u = re.sub(r'https?://(([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,})/', proxy_prefix, u)
                        from_list.append(name)
                        url_list.append("正片$%s" % proxy_u)

        # 方案 B: Surrit/Sixyik 正片 UUID 提取 (直通母流，彻底跳过网页嗅探)
        if not from_list:
            uuid = self._extract_surrit_uuid(html_text)
            if uuid:
                raw_stream = "https://surrit.com/%s/playlist.m3u8" % uuid
                proxy_u = re.sub(r'https?://(([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,})/', proxy_prefix, raw_stream)
                from_list.append("超清原画正片")
                url_list.append("正片$%s" % proxy_u)

        # 方案 C: 兜底原线
        if not from_list:
            from_list.append("⚠️网页嗅探(易偶发6秒)")
            url_list.append("正片$%s" % target_url)

        play_from = "$$$".join(from_list)
        play_url = "$$$".join(url_list)

        intro_desc = (
            "【官方交流群: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "【当前接入节点】: %s\n"
            "【解析通道状态】: %s\n"
            "影片标题：%s"
        ) % (self.tgGroup, self.baseHost, from_list[0], vod_name)
        escaped_desc = intro_desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        return {
            "list": [{
                "vod_id": target_url,
                "vod_name": html_lib.unescape(vod_name),
                "vod_pic": vod_pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "ZakaTV",
                "vod_content": escaped_desc,
                "vod_play_from": play_from,
                "vod_play_url": play_url
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id).strip()
        headers = {
            "User-Agent": self._ua,
            "Referer": self.baseHost + "/",
            "Accept": "*/*"
        }
        is_page = not play_url.endswith(".m3u8") and not play_url.endswith(".mp4")
        return {
            "parse": 1 if is_page else 0,
            "jx": 0,
            "url": play_url,
            "header": headers
        }

    def searchContent(self, key, quick, pg="1"):
        page_int = int(pg) if str(pg).isdigit() else 1
        encoded_key = urllib.parse.quote(key)

        if page_int > 1:
            search_url = "%s/cn/search/%s?page=%d" % (self.baseHost, encoded_key, page_int)
        else:
            search_url = "%s/cn/search/%s" % (self.baseHost, encoded_key)

        res = self._fetch(search_url)
        vod_list = self._parse_cards(res.get("text", ""), "video")

        return {
            "page": page_int,
            "pagecount": page_int + 1 if len(vod_list) >= 12 else page_int,
            "limit": len(vod_list),
            "total": 9999,
            "list": vod_list
        }

    def action(self, action):
        return {"msg": "ThisAV自愈生产蜘蛛运行正常"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not configured"]

    def destroy(self):
        self.options = {}
