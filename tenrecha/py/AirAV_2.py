#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 蜂蜜影视（FongMi TV）原生 Python 蜘蛛 - AirAV 正式版 (V5.5基底 + 圆形头像 + 单字母筛选 + idx翻页)

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

class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.siteUrl = "https://airavingg6.work"
        self.tgGroup = "https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandActor = "📺TG群: https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandDirector = "📺ZakaTV"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self.options = {}

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
        return True

    def getName(self):
        return "AirAV"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd", "index.png"))

    def manualVideoCheck(self):
        return False

    def _fetch(self, target_url, referer=""):
        if not target_url:
            return {"code": 0, "text": "", "bytes": b"", "err": "", "final_url": ""}
        if target_url.startswith("//"):
            target_url = "https:" + target_url
        elif target_url.startswith("/"):
            target_url = self.siteUrl + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }

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
                    return {"code": code, "text": text, "bytes": raw, "err": "", "final_url": final_url}
            except urllib.error.HTTPError as e:
                if e.code in (451, 403, 429) and attempt == 0:
                    continue
                err_raw = ""
                try:
                    err_raw = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass
                return {"code": e.code, "text": err_raw, "bytes": b"", "err": str(e), "final_url": target_url}
            except Exception as e:
                if attempt == 0:
                    continue
                return {"code": -1, "text": "", "bytes": b"", "err": str(e), "final_url": target_url}

        return {"code": -1, "text": "", "bytes": b"", "err": "timeout", "final_url": target_url}

    def homeContent(self, filter):
        classes = [
            {"type_name": "最新视频", "type_id": "latest"},
            {"type_name": "今日熱門", "type_id": "today_hot"},
            {"type_name": "本周熱門", "type_id": "week_hot"},
            {"type_name": "本月熱門", "type_id": "month_hot"},
            {"type_name": "VR专区", "type_id": "vr_zone"},
            {"type_name": "發行商", "type_id": "factories"},
            {"type_name": "女優一覽", "type_id": "actors"},
            {"type_name": "類型一覽", "type_id": "tags"}
        ]
        
        result = {"class": classes}
        
        if filter:
            result["filters"] = {
                "latest": [
                    {
                        "key": "sort",
                        "name": "排序",
                        "value": [
                            {"n": "最新上架", "v": ""},
                            {"n": "今日最熱", "v": "3"},
                            {"n": "本週最熱", "v": "4"},
                            {"n": "本月最熱", "v": "5"}
                        ]
                    }
                ],
                "factories": [
                    {
                        "key": "sort",
                        "name": "排序",
                        "value": [
                            {"n": "預設分類", "v": "1"},
                            {"n": "熱門搜尋", "v": "2"},
                            {"n": "最多影片", "v": "3"}
                        ]
                    }
                ],
                "tags": [
                    {
                        "key": "sort",
                        "name": "排序",
                        "value": [
                            {"n": "預設分類", "v": "1"},
                            {"n": "熱門搜尋", "v": "2"},
                            {"n": "最多影片", "v": "3"}
                        ]
                    }
                ],
                "actors": [
                    {
                        "key": "h",
                        "name": "選擇身高",
                        "value": [
                            {"n": "不選擇", "v": ""},
                            {"n": "<140cm", "v": "1"},
                            {"n": "141~150cm", "v": "2"},
                            {"n": "151~160cm", "v": "3"},
                            {"n": "161~170cm", "v": "4"},
                            {"n": "161~180cm", "v": "5"},
                            {"n": ">181cm", "v": "6"}
                        ]
                    },
                    {
                        "key": "c",
                        "name": "選擇罩杯",
                        "value": [
                            {"n": "不選擇", "v": ""},
                            {"n": "A罩杯", "v": "1"},
                            {"n": "B罩杯", "v": "2"},
                            {"n": "C罩杯", "v": "3"},
                            {"n": "D罩杯", "v": "4"},
                            {"n": "E罩杯", "v": "5"},
                            {"n": "F罩杯", "v": "6"},
                            {"n": "G罩杯", "v": "7"},
                            {"n": "H罩杯", "v": "8"},
                            {"n": "I罩杯", "v": "9"},
                            {"n": ">I罩杯", "v": "10"}
                        ]
                    },
                    {
                        "key": "a",
                        "name": "選擇年齡",
                        "value": [
                            {"n": "不選擇", "v": ""},
                            {"n": "<20", "v": "1"},
                            {"n": "20-30", "v": "2"},
                            {"n": "30-40", "v": "3"},
                            {"n": "40-50", "v": "4"},
                            {"n": ">50", "v": "5"}
                        ]
                    }
                ]
            }
        return result

    def homeVideoContent(self):
        res = self.categoryContent("latest", 1, False, {})
        return {"list": res.get("list", [])[:12]}

    def _parse_video_cards(self, html_text):
        cards = html_text.split('class="card')
        vod_list = []
        seen_ids = set()

        for card_html in cards[1:]:
            m_hid = re.search(r'href=["\'][^"\']*?/video\?hid=([^"\'&]+)["\']', card_html)
            if not m_hid:
                continue
            hid = m_hid.group(1).strip()
            if hid in seen_ids:
                continue
            seen_ids.add(hid)

            m_pic = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', card_html)
            cover = m_pic.group(1).strip() if m_pic else ("https://airav.io/storage/cover/big/%s.jpg" % hid)
            if cover.startswith("//"):
                cover = "https:" + cover
            elif cover.startswith("/"):
                cover = self.siteUrl + cover

            m_title = re.search(r'title=["\']([^"\']+)["\']', card_html)
            if m_title:
                name = m_title.group(1).strip()
            else:
                raw_texts = re.findall(r'>([^<]+)<', card_html)
                clean_lines = [t.strip() for t in raw_texts if len(t.strip()) > 3]
                name = clean_lines[0] if clean_lines else hid

            m_time = re.search(r'class=["\'][^"\']*(?:duration|time)[^"\']*["\'][^>]*>([^<]+)<', card_html)
            remarks = m_time.group(1).strip() if m_time else "ZakaTV"

            vod_list.append({
                "vod_id": hid,
                "vod_name": name,
                "vod_pic": cover,
                "vod_remarks": remarks,
                "style": {"type": "rect", "ratio": 1.78}
            })
        return vod_list

    def categoryContent(self, tid, pg, filter, extend):
        del filter
        page = int(pg) if pg else 1
        slug = str(tid).strip("/")

        # 1. 穿透模式：点击 folder 目录后钻取的视频列表翻页
        if slug.startswith("folder/"):
            slug = slug.replace("folder/", "")

        if slug.startswith("sub_"):
            parts = slug.split("_")
            sub_type = parts[1]
            sub_key = parts[2]
            sub_val = parts[3]
            
            target_url = "%s/%s?%s=%s" % (self.siteUrl, sub_type, sub_key, sub_val)
            if page > 1:
                target_url += "&idx=%d&page=%d" % (page, page)
            
            res = self._fetch(target_url)
            vod_list = self._parse_video_cards(res.get("text", ""))
            return {
                "page": page,
                "pagecount": page + 1 if len(vod_list) >= 12 else page,
                "limit": len(vod_list),
                "total": 9999,
                "list": vod_list
            }

        # 2. 發行商 (/factories) 与 類型一覽 (/tags) 翻页
        if slug in ("factories", "tags"):
            sort_val = extend.get("sort") if isinstance(extend, dict) else "1"
            if not sort_val:
                sort_val = "1"

            target_url = "%s/%s?sort=%s" % (self.siteUrl, slug, sort_val)
            if page > 1:
                target_url += "&idx=%d" % page

            res = self._fetch(target_url)
            html_text = res.get("text", "")
            items = html_text.split('class="type-item"')
            folder_list = []
            seen_subs = set()

            for item_html in items[1:]:
                m_sub = re.search(r'href=["\'](/tag\?[^"\']+)["\']', item_html)
                if not m_sub:
                    continue
                sub_href = m_sub.group(1).strip()
                if sub_href in seen_subs:
                    continue
                seen_subs.add(sub_href)

                parsed = urllib.parse.urlparse(sub_href)
                q_dict = urllib.parse.parse_qs(parsed.query)
                k = "fid" if "fid" in q_dict else "id"
                v = q_dict.get(k, ["1"])[0]
                packed_id = "folder/sub_tag_%s_%s" % (k, v)

                m_name = re.search(r'<h5[^>]*>([^<]+)</h5>', item_html)
                name = m_name.group(1).strip() if m_name else "分类"

                m_count = re.search(r'<p>([^<]+)</p>', item_html)
                count_str = m_count.group(1).strip() if m_count else "ZakaTV"

                folder_list.append({
                    "vod_id": packed_id,
                    "vod_name": name,
                    "vod_pic": "https://dummyimage.com/400x600/1e293b/ffffff.png&text=" + quote(name[:4]),
                    "vod_remarks": count_str,
                    "vod_tag": "folder",
                    "style": {"type": "rect", "ratio": 1.78}
                })

            return {
                "page": page,
                "pagecount": page + 1 if len(folder_list) >= 12 else page,
                "limit": len(folder_list),
                "total": 9999,
                "list": folder_list
            }

        # 3. 女優一覽 (/actors) - 单字母筛选与圆形卡片展示
        if slug == "actors":
            target_url = "%s/actors" % self.siteUrl
            query_parts = []
            if isinstance(extend, dict):
                h = extend.get("h", "")
                c = extend.get("c", "")
                a = extend.get("a", "")
                if h: query_parts.append("h=%s" % h)
                if c: query_parts.append("c=%s" % c)
                if a: query_parts.append("a=%s" % a)

            if page > 1:
                query_parts.append("idx=%d" % page)

            if query_parts:
                target_url += "?" + "&".join(query_parts)

            res = self._fetch(target_url)
            html_text = res.get("text", "")
            items = html_text.split('class="idol-item"')
            folder_list = []
            seen_subs = set()

            for item_html in items[1:]:
                m_sub = re.search(r'href=["\'](/actor\?id=([^"\'&]+))["\']', item_html)
                if not m_sub:
                    continue
                sub_id = m_sub.group(2).strip()
                if sub_id in seen_subs:
                    continue
                seen_subs.add(sub_id)

                packed_id = "folder/sub_actor_id_%s" % sub_id

                m_name = re.search(r'<h5[^>]*>([^<]+)</h5>', item_html)
                name = m_name.group(1).strip() if m_name else "女优"

                m_pic = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', item_html)
                pic_url = m_pic.group(1).strip() if m_pic else ""
                if pic_url.startswith("//"):
                    pic_url = "https:" + pic_url
                elif pic_url.startswith("/"):
                    pic_url = self.siteUrl + pic_url

                final_pic = pic_url if (pic_url and not pic_url.endswith(".svg")) else ("https://dummyimage.com/400x600/334155/ffffff.png&text=" + quote(name[:4]))

                # 采用 1:1 正圆形卡片
                folder_list.append({
                    "vod_id": packed_id,
                    "vod_name": name,
                    "vod_pic": final_pic,
                    "vod_remarks": "ZakaTV",
                    "vod_tag": "folder",
                    "style": {"type": "oval", "ratio": 1.0}
                })

            return {
                "page": page,
                "pagecount": page + 1 if len(folder_list) >= 12 else page,
                "limit": len(folder_list),
                "total": 9999,
                "list": folder_list
            }

        # 4. 常规视频分类 (最新、熱門、VR)
        route_map = {
            "latest": "/list",
            "today_hot": "/list?sort=3",
            "week_hot": "/list?sort=4",
            "month_hot": "/list?sort=5",
            "vr_zone": "/tag?id=81"
        }
        target_path = route_map.get(slug, "/list")
        params = []
        if page > 1:
            params.append("page=%d" % page)
            params.append("idx=%d" % page)

        sort_val = extend.get("sort") if isinstance(extend, dict) else ""
        if sort_val and "?" not in target_path:
            params.append("sort=%s" % sort_val)

        if params:
            delimiter = "&" if "?" in target_path else "?"
            target_url = self.siteUrl + target_path + delimiter + "&".join(params)
        else:
            target_url = self.siteUrl + target_path

        res = self._fetch(target_url)
        vod_list = self._parse_video_cards(res.get("text", ""))

        return {
            "page": page,
            "pagecount": page + 1 if len(vod_list) >= 12 else page,
            "limit": len(vod_list),
            "total": 9999,
            "list": vod_list
        }

    # 保持 V5.5 可播内核
    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)

        if raw_id.startswith("folder/") or raw_id.startswith("sub_"):
            clean_sub = raw_id.replace("folder/", "")
            sub_res = self.categoryContent(clean_sub, 1, False, {})
            sub_list = sub_res.get("list", [])
            
            if sub_list:
                play_episodes = []
                for v in sub_list[:30]:
                    v_name = v.get("vod_name", "").replace("$", "_").replace("#", "_")
                    v_hid = v.get("vod_id", "")
                    play_episodes.append("%s$%s" % (v_name[:25], v_hid))

                first_item = sub_list[0]
                full_desc = (
                    "【🔥 官方交流群: %s】\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "本专区已为您打包抓取了【%d】部正片，在下方选集直接点击即可起播！"
                ) % (self.tgGroup, len(sub_list))

                return {
                    "list": [{
                        "vod_id": raw_id,
                        "vod_name": "专区全集·" + first_item.get("vod_name", "合集"),
                        "vod_pic": first_item.get("vod_pic", ""),
                        "vod_actor": self.brandActor,
                        "vod_director": self.brandDirector,
                        "vod_remarks": "共 %d 部" % len(sub_list),
                        "vod_content": full_desc,
                        "vod_play_from": "AirAV专区",
                        "vod_play_url": "#".join(play_episodes)
                    }]
                }

        hid = raw_id
        target_url = "%s/video?hid=%s" % (self.siteUrl, hid)
        res = self._fetch(target_url)
        detail_html = res.get("text", "")

        m_title = re.search(r'<title>(.*?)</title>', detail_html, re.I)
        raw_title = m_title.group(1).replace("- airav.io", "").strip() if m_title else hid

        m_pic = re.search(r'"https://airav\.io/storage/cover/big/[^"]+"', detail_html)
        if m_pic:
            cover = m_pic.group(0).strip('"')
        else:
            cover = "https://airav.io/storage/cover/big/%s.jpg" % hid

        m_desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\']', detail_html, re.I)
        desc_text = m_desc.group(1).strip() if m_desc else ""

        full_desc = (
            "【🔥 官方交流群: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "%s"
        ) % (self.tgGroup, desc_text if desc_text else "暂无剧情介绍")

        m_m3u8 = re.search(r'"contentUrl":\s*["\']([^"\']+\.m3u8[^"\']*)["\']', detail_html)
        if m_m3u8:
            play_url = m_m3u8.group(1).replace("\\/", "/")
            play_route = "正片$" + play_url
        else:
            play_route = "解析线路$%s/embedded?hid=%s" % (self.siteUrl, hid)

        return {
            "list": [{
                "vod_id": hid,
                "vod_name": raw_title,
                "vod_pic": cover,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "ZakaTV",
                "vod_content": full_desc,
                "vod_play_from": "AirAV在线",
                "vod_play_url": play_route
            }]
        }

    # 保持 V5.5 原生播放解析与头部伪装
    def playerContent(self, flag, id, vipFlags):
        raw_id = str(id).strip()
        headers = {
            "User-Agent": self._ua,
            "Referer": self.siteUrl + "/",
            "Origin": self.siteUrl
        }

        if ".m3u8" in raw_id or ".mp4" in raw_id:
            return {
                "parse": 0,
                "playUrl": "",
                "url": raw_id,
                "header": headers
            }

        target_url = "%s/video?hid=%s" % (self.siteUrl, raw_id)
        res = self._fetch(target_url)
        detail_html = res.get("text", "")

        m_m3u8 = re.search(r'"contentUrl":\s*["\']([^"\']+\.m3u8[^"\']*)["\']', detail_html)
        if m_m3u8:
            real_m3u8 = m_m3u8.group(1).replace("\\/", "/")
            return {
                "parse": 0,
                "playUrl": "",
                "url": real_m3u8,
                "header": headers
            }

        return {
            "parse": 1,
            "playUrl": "",
            "url": "%s/embedded?hid=%s" % (self.siteUrl, raw_id),
            "header": headers
        }

    def searchContent(self, key, quick, pg="1"):
        del quick
        page = int(pg) if pg else 1
        search_url = "%s/search?search=%s" % (self.siteUrl, quote(key))
        if page > 1:
            search_url += "&page=%d&p=%d" % (page, page)

        res = self._fetch(search_url)
        vod_list = self._parse_video_cards(res.get("text", ""))

        return {
            "page": page,
            "pagecount": page + 1 if len(vod_list) >= 12 else page,
            "limit": len(vod_list),
            "total": 9999,
            "list": vod_list
        }

    def action(self, action):
        return {"msg": "ok"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not configured"]

    def destroy(self):
        self.options = {}