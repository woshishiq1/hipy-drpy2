#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import re
import json
import time
import base64
import html as html_lib
import urllib.request
import urllib.parse
import http.cookiejar
import gzip
import zlib
import ssl

try:
    from base.spider import Spider as SpiderBase
except ImportError:
    class SpiderBase(object):
        pass


class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.siteHost = "https://ubi.lsavw6.pics"
        self.entryPrefix = "/cn/home/web/index.php"
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

    def init(self, extend=""):
        return True

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts"))

    def manualVideoCheck(self):
        return False

    def _build_opener(self):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        except Exception:
            pass
        cj = http.cookiejar.CookieJar()
        return urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cj),
            urllib.request.HTTPSHandler(context=ctx)
        )

    def _fetch(self, target_url, referer=""):
        if not target_url:
            return {"code": 0, "text": "", "err": ""}
        if target_url.startswith("/"):
            target_url = self.siteHost + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteHost + self.entryPrefix + "/vod/type/id/20.html"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }

        last_err = ""
        for attempt in range(2):
            try:
                opener = self._build_opener()
                req = urllib.request.Request(target_url, headers=headers)
                with opener.open(req, timeout=12) as resp:
                    code = resp.getcode()
                    raw = resp.read()
                    if raw.startswith(b"\x1f\x8b"):
                        raw = gzip.decompress(raw)
                    elif getattr(resp, "headers", {}).get("Content-Encoding") == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except Exception:
                            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                    try:
                        text = raw.decode("utf-8")
                    except Exception:
                        text = raw.decode("latin1", errors="ignore")
                    return {"code": code, "text": text, "err": ""}
            except urllib.error.HTTPError as e:
                err_body = ""
                try:
                    raw_err = e.read()
                    if raw_err.startswith(b"\x1f\x8b"):
                        raw_err = gzip.decompress(raw_err)
                    err_body = raw_err.decode("utf-8", errors="ignore")
                except Exception:
                    pass
                return {"code": e.code, "text": err_body, "err": "HTTPError: %s" % str(e)}
            except Exception as e:
                last_err = "请求异常: %s" % str(e)
                time.sleep(1)

        return {"code": -1, "text": "", "err": last_err}

    def _unesc(self, s):
        try:
            return html_lib.unescape(s or "").strip()
        except Exception:
            return (s or "").strip()

    # 1. 首页：纯内存零网络请求，秒级加载，固化真实分类矩阵
    def homeContent(self, *args, **kwargs):
        return {
            "class": [
                {"type_name": "国产精品", "type_id": "20"},
                {"type_name": "主播大秀", "type_id": "21"},
                {"type_name": "抖阴视频", "type_id": "22"},
                {"type_name": "女神学生", "type_id": "23"},
                {"type_name": "美熟少妇", "type_id": "24"},
                {"type_name": "娇妻素人", "type_id": "25"},
                {"type_name": "空姐模特", "type_id": "26"},
                {"type_name": "国产乱伦", "type_id": "27"},
                {"type_name": "自慰群交", "type_id": "28"},
                {"type_name": "野合车震", "type_id": "29"},
                {"type_name": "职场同事", "type_id": "30"},
                {"type_name": "国产名人", "type_id": "31"},
                {"type_name": "日本无码", "type_id": "32"},
                {"type_name": "精品三级", "type_id": "33"}
            ]
        }

    # 2. 列表页：纯净解析真实卡片，过滤分页噪音，安全ID编码
    def categoryContent(self, tid, pg, *args, **kwargs):
        page_num = str(pg or "1").strip()
        tid = str(tid).strip()

        if page_num == "1":
            target_path = "%s/vod/type/id/%s.html" % (self.entryPrefix, tid)
        else:
            target_path = "%s/vod/type/id/%s/page/%s.html" % (self.entryPrefix, tid, page_num)

        res = self._fetch(target_path)
        html_text = res.get("text", "")

        vod_list = []
        card_matches = re.findall(r'(<a[^>]+href=["\']([^"\']*vod/play/id/[^"\']+)["\'][^>]*>([\s\S]*?)</a>)', html_text, re.I)
        seen_urls = set()

        for full_a, play_href, inner in card_matches:
            clean_href = play_href.strip()
            if clean_href in seen_urls:
                continue
            seen_urls.add(clean_href)

            # 提取标题
            title_m = re.search(r'title=["\']([^"\']+)["\']', full_a, re.I)
            if title_m:
                title = title_m.group(1).strip()
            else:
                title = re.sub(r'<[^>]+>', '', inner).strip()

            # 过滤噪音节点
            if not title or any(k in title for k in ("上一页", "下一页", "尾页", "首页")):
                continue

            # 提取高清海报
            pic = ""
            img_m = re.search(r'<img[^>]+(?:data-original|data-src|src)=["\']([^"\']+)["\']', inner, re.I)
            if not img_m:
                img_m = re.search(r'<img[^>]+(?:data-original|data-src|src)=["\']([^"\']+)["\']', full_a, re.I)
            if img_m:
                pic = img_m.group(1).strip()
                if pic.startswith("//"):
                    pic = "https:" + pic
                elif pic.startswith("/"):
                    pic = self.siteHost + pic

            safe_id = "v_" + base64.urlsafe_b64encode(clean_href.encode("utf-8")).decode("utf-8").rstrip("=")

            vod_list.append({
                "vod_id": safe_id,
                "vod_name": self._unesc(title),
                "vod_pic": pic,
                "vod_remarks": "高清"
            })

        return {
            "page": int(page_num),
            "pagecount": 99,
            "limit": len(vod_list),
            "total": 99,
            "list": vod_list
        }

    # 3. 详情页：解密直链与标准品牌简介封装
    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)

        play_path = ""
        if str(raw_id).startswith("v_"):
            try:
                b64_str = raw_id[2:]
                pad = len(b64_str) % 4
                if pad:
                    b64_str += "=" * (4 - pad)
                play_path = base64.urlsafe_b64decode(b64_str.encode("utf-8")).decode("utf-8")
            except Exception:
                play_path = ""

        if not play_path:
            return {"list": []}

        res = self._fetch(play_path)
        html_text = res.get("text", "")

        # 提取 player 对象并解析
        player_obj = {}
        p_match = re.search(r'var\s+(?:player_aaaa|player_data)\s*=\s*(\{[\s\S]*?\});', html_text, re.I)
        if p_match:
            player_json_raw = p_match.group(1).strip()
            try:
                player_obj = json.loads(player_json_raw)
            except Exception:
                url_m = re.search(r'["\']?url["\']?\s*:\s*["\']([^"\']+)["\']', player_json_raw)
                if url_m:
                    player_obj["url"] = url_m.group(1).strip()
                enc_m = re.search(r'["\']?encrypt["\']?\s*:\s*(\d+)', player_json_raw)
                if enc_m:
                    player_obj["encrypt"] = enc_m.group(1).strip()

        raw_url = player_obj.get("url", "")
        encrypt_flag = str(player_obj.get("encrypt", "0"))
        decrypted_url = ""

        if raw_url:
            if encrypt_flag == "0":
                decrypted_url = raw_url
            elif encrypt_flag == "1":
                decrypted_url = urllib.parse.unquote(raw_url)
            elif encrypt_flag == "2":
                try:
                    decrypted_url = urllib.parse.unquote(base64.b64decode(raw_url.encode("utf-8")).decode("utf-8"))
                except Exception:
                    decrypted_url = raw_url
        else:
            stream_m = re.search(r'["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', html_text, re.I)
            if stream_m:
                decrypted_url = stream_m.group(1).strip()

        # 提取视频标题
        title_m = re.search(r'<title>(.*?)</title>', html_text, re.I)
        page_title = title_m.group(1).strip() if title_m else "精彩视频"
        page_title = re.sub(r'(-|\||_).*$', '', page_title).strip()

        # 品牌与版权规范结构
        custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】"
        group_info = "【🔥 官方交流群: %s】" % self.tgGroup

        # 简介提取与清洗
        clean_content = ""
        desc_m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
        if desc_m:
            clean_content = desc_m.group(1).strip()

        if clean_content:
            vod_content = "%s\n\n%s\n\n%s" % (group_info, custom_notice, clean_content)
        else:
            vod_content = "%s\n\n%s\n\n暂无详细简介，欢迎加入TG群获取最新资源！" % (group_info, custom_notice)

        final_play_url = decrypted_url if (decrypted_url and decrypted_url.startswith("http")) else "http://127.0.0.1"

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": self._unesc(page_title),
                "vod_pic": "",
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "高清直链",
                "vod_content": vod_content,
                "vod_play_from": "蝴蝶专线",
                "vod_play_url": "正片$%s" % final_play_url
            }]
        }

    # 4. 播放器：parse: 0 安全直连交付
    def playerContent(self, flag, id, vipFlags):
        real_url = str(id).strip()
        return {
            "parse": 0,
            "playUrl": "",
            "url": real_url,
            "header": json.dumps({
                "User-Agent": self._ua,
                "Referer": self.siteHost + "/"
            })
        }

    # 5. 搜索保底实现
    def searchContent(self, key, quick, pg="1"):
        return {"list": []}