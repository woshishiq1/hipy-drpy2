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
import http.cookiejar
import gzip
import zlib
import ssl

try:
    from base.spider import Spider as SpiderBase
except ImportError:
    class SpiderBase(object):
        pass


class PureAES(object):
    """纯 Python 3 标准库实现的 AES-128-CBC 解密器，无需任何第三方依赖"""
    SBOX = [
        0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
        0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
        0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
        0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
        0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
        0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
        0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
        0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
        0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
        0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
        0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
        0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
        0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
        0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
        0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
        0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16
    ]

    INV_SBOX = [
        0x52,0x09,0x6a,0xd5,0x30,0x36,0xa5,0x38,0xbf,0x40,0xa3,0x9e,0x81,0xf3,0xd7,0xfb,
        0x7c,0xe3,0x39,0x82,0x9b,0x2f,0xff,0x87,0x34,0x8e,0x43,0x44,0xc4,0xde,0xe9,0xcb,
        0x54,0x7b,0x94,0x32,0xa6,0xc2,0x23,0x3d,0xee,0x4c,0x95,0x0b,0x42,0xfa,0xc3,0x4e,
        0x08,0x2e,0xa1,0x66,0x28,0xd9,0x24,0xb2,0x76,0x5b,0xa2,0x49,0x6d,0x8b,0xd1,0x25,
        0x72,0xf8,0xf6,0x64,0x86,0x68,0x98,0x16,0xd4,0xa4,0x5c,0xcc,0x5d,0x65,0xb6,0x92,
        0x6c,0x70,0x48,0x50,0xfd,0xed,0xb9,0xda,0x5e,0x15,0x46,0x57,0xa7,0x8d,0x9d,0x84,
        0x90,0xd8,0xab,0x00,0x8c,0xbc,0xd3,0x0a,0xf7,0xe4,0x58,0x05,0xb8,0xb3,0x45,0x06,
        0xd0,0x2c,0x1e,0x8f,0xca,0x3f,0x0f,0x02,0xc1,0xaf,0xbd,0x03,0x01,0x13,0x8a,0x6b,
        0x3a,0x91,0x11,0x41,0x4f,0x67,0xdc,0xea,0x97,0xf2,0xcf,0xce,0xf0,0xb4,0xe6,0x73,
        0x96,0xac,0x74,0x22,0xe7,0xad,0x35,0x85,0xe2,0xf9,0x37,0xe8,0x1c,0x75,0xdf,0x6e,
        0x47,0xf1,0x1a,0x71,0x1d,0x29,0xc5,0x89,0x6f,0xb7,0x62,0x0e,0xaa,0x18,0xbe,0x1b,
        0xfc,0x56,0x3e,0x4b,0xc6,0xd2,0x79,0x20,0x9a,0xdb,0xc0,0xfe,0x78,0xcd,0x5a,0xf4,
        0x1f,0xdd,0xa8,0x33,0x88,0x07,0xc7,0x31,0xb1,0x12,0x10,0x59,0x27,0x80,0xec,0x5f,
        0x60,0x51,0x7f,0xa9,0x19,0xb5,0x4a,0x0d,0x2d,0xe5,0x7a,0x9f,0x93,0xc9,0x9c,0xef,
        0xa0,0xe0,0x3b,0x4d,0xae,0x2a,0xf5,0xb0,0xc8,0xeb,0xbb,0x3c,0x83,0x53,0x99,0x61,
        0x17,0x2b,0x04,0x7e,0xba,0x77,0xd6,0x26,0xe1,0x69,0x14,0x63,0x55,0x21,0x0c,0x7d
    ]

    RCON = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36]

    @staticmethod
    def _gmul(a, b):
        p = 0
        for _ in range(8):
            if b & 1:
                p ^= a
            hi = a & 0x80
            a = (a << 1) & 0xFF
            if hi:
                a ^= 0x1b
            b >>= 1
        return p

    @classmethod
    def _key_expansion(cls, key_bytes):
        w = [0] * 176
        for i in range(16):
            w[i] = key_bytes[i]
        for col in range(16, 176, 4):
            t = [w[col-4], w[col-3], w[col-2], w[col-1]]
            if col % 16 == 0:
                tmp = t[0]
                t[0] = cls.SBOX[t[1]]
                t[1] = cls.SBOX[t[2]]
                t[2] = cls.SBOX[t[3]]
                t[3] = cls.SBOX[tmp]
                t[0] ^= cls.RCON[col // 16 - 1]
            w[col]   = w[col-16] ^ t[0]
            w[col+1] = w[col-15] ^ t[1]
            w[col+2] = w[col-14] ^ t[2]
            w[col+3] = w[col-13] ^ t[3]
        return w

    @staticmethod
    def _inv_shift_rows(s):
        t = s[13]; s[13] = s[9]; s[9] = s[5]; s[5] = s[1]; s[1] = t
        t = s[2]; s[2] = s[10]; s[10] = t; t = s[6]; s[6] = s[14]; s[14] = t
        t = s[3]; s[3] = s[7]; s[7] = s[11]; s[11] = s[15]; s[15] = t

    @classmethod
    def _inv_mix_columns(cls, s):
        for c in range(4):
            i = c * 4
            a = s[i]; b = s[i+1]; c2 = s[i+2]; d = s[i+3]
            s[i]   = cls._gmul(a, 0x0e) ^ cls._gmul(b, 0x0b) ^ cls._gmul(c2, 0x0d) ^ cls._gmul(d, 0x09)
            s[i+1] = cls._gmul(a, 0x09) ^ cls._gmul(b, 0x0e) ^ cls._gmul(c2, 0x0b) ^ cls._gmul(d, 0x0d)
            s[i+2] = cls._gmul(a, 0x0d) ^ cls._gmul(b, 0x09) ^ cls._gmul(c2, 0x0e) ^ cls._gmul(d, 0x0b)
            s[i+3] = cls._gmul(a, 0x0b) ^ cls._gmul(b, 0x0d) ^ cls._gmul(c2, 0x09) ^ cls._gmul(d, 0x0e)

    @classmethod
    def _decrypt_block(cls, block, ek):
        s = list(block)
        for i in range(16):
            s[i] ^= ek[160 + i]
        for r in range(9, 0, -1):
            cls._inv_shift_rows(s)
            for i in range(16):
                s[i] = cls.INV_SBOX[s[i]]
            for i in range(16):
                s[i] ^= ek[r * 16 + i]
            cls._inv_mix_columns(s)
        cls._inv_shift_rows(s)
        for i in range(16):
            s[i] = cls.INV_SBOX[s[i]]
        for i in range(16):
            s[i] ^= ek[i]
        return s

    @classmethod
    def decrypt_cbc(cls, cipher_bytes, key_bytes, iv_bytes):
        ek = cls._key_expansion(key_bytes)
        pt = []
        prev = list(iv_bytes)
        for i in range(0, len(cipher_bytes), 16):
            block = cipher_bytes[i:i+16]
            dec = cls._decrypt_block(block, ek)
            for j in range(16):
                pt.append(dec[j] ^ prev[j])
            prev = list(block)
        pad_len = pt[-1]
        if pad_len < 1 or pad_len > 16:
            return bytes(pt)
        return bytes(pt[:-pad_len])


class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.siteUrl = "https://ommjs4.xxsxlz.top"
        self.apiKey = b"a9yX32LpQvUt7wBc"
        self.apiIv  = b"N7cPk2Bv38hWqFzM"

        # 品牌规范
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        try:
            self.ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        except Exception:
            pass

        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx)
        )

        # 固化 16 个分类
        self.classList = [
            {"type_id": "2383", "type_name": "乱伦毁三观"},
            {"type_id": "2411", "type_name": "中文字幕"},
            {"type_id": "2412", "type_name": "SM调教"},
            {"type_id": "2421", "type_name": "丝袜制服"},
            {"type_id": "2432", "type_name": "国内换脸"},
            {"type_id": "2433", "type_name": "自拍偷拍"},
            {"type_id": "2434", "type_name": "传媒剧情"},
            {"type_id": "2435", "type_name": "抖阴短片"},
            {"type_id": "2436", "type_name": "网曝吃瓜"},
            {"type_id": "2437", "type_name": "偷拍偷窥"},
            {"type_id": "2438", "type_name": "探花约炮"},
            {"type_id": "2439", "type_name": "主播诱惑"},
            {"type_id": "2440", "type_name": "国产自拍"},
            {"type_id": "2441", "type_name": "女优明星"},
            {"type_id": "2443", "type_name": "日韩无码"},
            {"type_id": "2444", "type_name": "日韩精品"}
        ]
        self.filters = {}

    def init(self, extend=""):
        return True

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts"))

    def manualVideoCheck(self):
        return False

    def _fetch(self, target_url, referer=""):
        if not target_url:
            return {"code": 0, "text": "", "err": "URL 为空"}
        if target_url.startswith("/"):
            target_url = self.siteUrl + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + "/"),
            "Accept": "application/json,text/html,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "close"
        }

        try:
            req = urllib.request.Request(target_url, headers=headers)
            with self.opener.open(req, timeout=15) as resp:
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
            return {"code": -1, "text": "", "err": "Exception: %s" % str(e)}

    def _unesc(self, s):
        try:
            return html_lib.unescape(s or "").strip()
        except Exception:
            return (s or "").strip()

    def _encode_id(self, raw_id):
        safe_str = base64.urlsafe_b64encode(str(raw_id).encode("utf-8")).decode("utf-8").rstrip("=")
        return "v_" + safe_str

    def _decode_id(self, safe_id):
        if not str(safe_id).startswith("v_"):
            return str(safe_id)
        b64_str = str(safe_id)[2:]
        pad = len(b64_str) % 4
        if pad:
            b64_str += "=" * (4 - pad)
        try:
            return base64.urlsafe_b64decode(b64_str.encode("utf-8")).decode("utf-8")
        except Exception:
            return str(safe_id)

    # API 请求与 AES-128-CBC 自动解密
    def _api_get(self, path):
        req_url = "%s/api%s" % (self.siteUrl, path)
        res = self._fetch(req_url, referer=self.siteUrl + "/")
        text = res.get("text", "")
        if not text:
            return None
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "cipher" in data:
                cipher_bytes = base64.b64decode(data["cipher"])
                dec_bytes = PureAES.decrypt_cbc(cipher_bytes, self.apiKey, self.apiIv)
                return json.loads(dec_bytes.decode("utf-8"))
            return data
        except Exception:
            return None

    def _parse_video_list(self, data):
        if not data or not isinstance(data, dict):
            return []
        inner = data.get("data", {})
        if not isinstance(inner, dict):
            return []
        items = inner.get("list", [])
        if not isinstance(items, list):
            return []

        vod_list = []
        for v in items:
            vid = str(v.get("id", ""))
            if not vid:
                continue
            vod_list.append({
                "vod_id": self._encode_id(vid),
                "vod_name": self._unesc(v.get("title", "")),
                "vod_pic": str(v.get("cover_url", "")).strip(),
                "vod_remarks": self._unesc(v.get("category", ""))
            })
        return vod_list

    # 1. 首页：纯内存毫秒级返回
    def homeContent(self, *args, **kwargs):
        return {
            "class": self.classList,
            "filters": self.filters
        }

    # 2. 分类列表页
    def categoryContent(self, tid, pg, *args, **kwargs):
        pg_int = 1
        try:
            pg_int = int(pg)
        except Exception:
            pass

        tid_str = str(tid).strip("/")
        path = "/videos?category_id=%s&page=%d&ps=20" % (tid_str, pg_int)
        data = self._api_get(path)

        vod_list = self._parse_video_list(data)

        page_count = 1
        total = 0
        if data and isinstance(data, dict) and "data" in data:
            d = data["data"]
            try:
                page_count = int(d.get("pages", 1))
                total = int(d.get("total", 0))
            except Exception:
                pass

        return {
            "list": vod_list,
            "page": pg_int,
            "pagecount": page_count,
            "limit": 20,
            "total": total
        }

    # 3. 详情页：直接调用 /api/movie 逆向直链
    def detailContent(self, ids):
        raw_id_param = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        real_id = self._decode_id(raw_id_param)

        path = "/movie?id=%s" % real_id
        data = self._api_get(path)

        title = "未知片名"
        pic = ""
        category_name = ""
        clean_desc = ""
        play_url = ""

        if data and isinstance(data, dict) and "data" in data:
            info = data["data"].get("info", {})
            title = info.get("title", "未知片名")
            pic = info.get("cover_url", "")
            category_name = info.get("category", "")
            clean_desc = "%s | 播放: %s | 收藏: %s" % (
                category_name,
                str(info.get("hits", 0)),
                str(info.get("favorites", 0))
            )
            play_url = info.get("play_url", "")

        custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】"
        group_info = "【🔥 官方交流群: %s】" % self.tgGroup
        if clean_desc:
            vod_content = "%s\n\n%s\n\n%s" % (group_info, custom_notice, clean_desc)
        else:
            vod_content = "%s\n\n%s\n\n暂无详细简介，欢迎加入TG群获取最新资源！" % (group_info, custom_notice)

        # 逆向直解直链组装
        target_play = play_url if (play_url and play_url.startswith("http")) else real_id
        vod_play_url = "在线播放$%s" % target_play

        return {
            "list": [{
                "vod_id": raw_id_param,
                "vod_name": self._unesc(title),
                "vod_pic": pic.strip(),
                "vod_type_name": category_name,
                "vod_year": "",
                "vod_area": category_name,
                "vod_remarks": category_name,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_content": vod_content,
                "vod_play_from": "欧美精选",
                "vod_play_url": vod_play_url
            }]
        }

    # 4. 播放器：parse 严格为 0，直链交付
    def playerContent(self, flag, id, vipFlags):
        play_target = str(id).strip()

        # 若未直接命中直链，调 /api/movie 获取
        if not play_target.startswith("http"):
            path = "/movie?id=%s" % play_target
            data = self._api_get(path)
            if data and isinstance(data, dict) and "data" in data:
                info = data["data"].get("info", {})
                if info.get("play_url"):
                    play_target = info["play_url"].strip()

        return {
            "parse": 0,
            "playUrl": "",
            "url": play_target,
            "header": json.dumps({
                "User-Agent": self._ua,
                "Referer": self.siteUrl + "/"
            })
        }

    # 5. 搜索模块
    def searchContent(self, key, quick, pg="1"):
        wd = (key or "").strip()
        if not wd:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 0, "total": 0}

        pg_int = 1
        try:
            pg_int = int(pg)
        except Exception:
            pass

        path = "/videos?kw=%s&page=%d" % (urllib.parse.quote(wd), pg_int)
        data = self._api_get(path)

        vod_list = self._parse_video_list(data)

        page_count = 1
        if data and isinstance(data, dict) and "data" in data:
            d = data["data"]
            try:
                page_count = int(d.get("pages", 1))
            except Exception:
                pass

        return {
            "list": vod_list,
            "page": pg_int,
            "pagecount": page_count,
            "limit": len(vod_list),
            "total": len(vod_list)
        }