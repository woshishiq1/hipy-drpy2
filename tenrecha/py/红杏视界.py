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
    """纯 Python 3 标准库实现的 AES-128-CBC 加解密引擎（PKCS7 Padding），不引入任何第三方依赖"""
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
    def _shift_rows(s):
        t = s[1]; s[1] = s[5]; s[5] = s[9]; s[9] = s[13]; s[13] = t
        t = s[2]; s[2] = s[10]; s[10] = t; t = s[6]; s[6] = s[14]; s[14] = t
        t = s[15]; s[15] = s[11]; s[11] = s[7]; s[7] = s[3]; s[3] = t

    @staticmethod
    def _inv_shift_rows(s):
        t = s[13]; s[13] = s[9]; s[9] = s[5]; s[5] = s[1]; s[1] = t
        t = s[2]; s[2] = s[10]; s[10] = t; t = s[6]; s[6] = s[14]; s[14] = t
        t = s[3]; s[3] = s[7]; s[7] = s[11]; s[11] = s[15]; s[15] = t

    @classmethod
    def _mix_columns(cls, s):
        for c in range(4):
            i = c * 4
            a = s[i]; b = s[i+1]; c2 = s[i+2]; d = s[i+3]
            s[i]   = cls._gmul(a, 2) ^ cls._gmul(b, 3) ^ c2 ^ d
            s[i+1] = a ^ cls._gmul(b, 2) ^ cls._gmul(c2, 3) ^ d
            s[i+2] = a ^ b ^ cls._gmul(c2, 2) ^ cls._gmul(d, 3)
            s[i+3] = cls._gmul(a, 3) ^ b ^ c2 ^ cls._gmul(d, 2)

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
    def _encrypt_block(cls, block, ek):
        s = list(block)
        for i in range(16):
            s[i] ^= ek[i]
        for r in range(1, 10):
            for i in range(16):
                s[i] = cls.SBOX[s[i]]
            cls._shift_rows(s)
            cls._mix_columns(s)
            for i in range(16):
                s[i] ^= ek[r * 16 + i]
        for i in range(16):
            s[i] = cls.SBOX[s[i]]
        cls._shift_rows(s)
        for i in range(16):
            s[i] ^= ek[160 + i]
        return s

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
    def encrypt_cbc(cls, plain_bytes, key_bytes, iv_bytes):
        pad_len = 16 - (len(plain_bytes) % 16)
        padded = list(plain_bytes) + [pad_len] * pad_len
        ek = cls._key_expansion(key_bytes)
        ct = []
        prev = list(iv_bytes)
        for i in range(0, len(padded), 16):
            block = [padded[i+j] ^ prev[j] for j in range(16)]
            enc = cls._encrypt_block(block, ek)
            ct.extend(enc)
            prev = list(enc)
        return bytes(ct)

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
        self.siteUrl = "https://fmhd.tf5xn2q2hx.cc"
        self.playDomain = "https://mhxvmjsr01.dajfalb.com"
        self.imgDomain = "https://mhxvmjsr01.dajfalb.com"
        self.aesKey = b"NHboMHZerxFQ401E"
        self.aesIv  = b"i7JeCEIMVrj2W9xN"

        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self._ua = "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36"

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

        # 固化分类列表
        self.classList = [
            {"type_id": "s2",  "type_name": "推荐"},
            {"type_id": "s1",  "type_name": "今日更新"},
            {"type_id": "s3",  "type_name": "日榜"},
            {"type_id": "s4",  "type_name": "周榜"},
            {"type_id": "s5",  "type_name": "月榜"},
            {"type_id": "51",  "type_name": "国产"},
            {"type_id": "76",  "type_name": "日韩"},
            {"type_id": "127", "type_name": "欧美"},
            {"type_id": "93",  "type_name": "吃瓜"},
            {"type_id": "60",  "type_name": "传媒"},
            {"type_id": "137", "type_name": "AI视频"},
            {"type_id": "83",  "type_name": "动漫"},
            {"type_id": "71",  "type_name": "综艺"},
            {"type_id": "198", "type_name": "解说"},
            {"type_id": "197", "type_name": "VR"},
            {"type_id": "199", "type_name": "伦理"},
            {"type_id": "200", "type_name": "猎奇"},
            {"type_id": "201", "type_name": "福利姬"}
        ]

        sub_categories = {
            "51":  [["乱伦","156"],["偷情","152"],["剧情","191"],["偷拍","144"],["自拍","145"],["直播","151"],["探花","153"],["强奸","154"],["迷奸","155"]],
            "76":  [["中字","169"],["无码","171"],["乱伦","194"],["人妻","193"],["群交","183"],["OL","170"],["偷情","196"]],
            "127": [["黑白配","176"],["剧情","185"],["中字","178"],["SM","182"],["自拍","186"],["男同","177"],["女同","181"]],
            "60":  [["麻豆","146"],["天美","147"],["91","148"],["星空","157"],["精东","158"],["蜜桃","159"],["SWAG","160"],["果冻","187"],["糖心","188"],["萝莉社","190"],["扣扣","192"],["皇家","195"]],
            "83":  [["中字","172"],["有码","173"],["无码","174"],["3D","189"]]
        }

        sort_values = [
            {"n": "默认", "v": ""},
            {"n": "推荐", "v": "2"},
            {"n": "今日更新", "v": "1"},
            {"n": "日榜", "v": "3"},
            {"n": "周榜", "v": "4"},
            {"n": "月榜", "v": "5"}
        ]

        self.filters = {}
        for c in self.classList:
            tid = c["type_id"]
            f_list = []
            if tid in sub_categories:
                c_vals = [{"n": "全部", "v": ""}]
                for sub in sub_categories[tid]:
                    c_vals.append({"n": sub[0], "v": sub[1]})
                f_list.append({"key": "children", "name": "子分类", "value": c_vals})
            f_list.append({"key": "sort", "name": "排序", "value": sort_values})
            self.filters[tid] = f_list

    def init(self, extend=""):
        return True

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts"))

    def manualVideoCheck(self):
        return False

    def _fetch(self, target_url, referer="", raw_bytes=False):
        if not target_url:
            return {"code": 0, "text": "", "bytes": b"", "err": "URL 为空"}
        if target_url.startswith("/"):
            target_url = self.siteUrl + target_url

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "platform": "7",
            "Channel-Code": "fmhd",
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + "/"),
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
                if raw_bytes:
                    return {"code": code, "bytes": raw, "err": ""}
                try:
                    text = raw.decode("utf-8")
                except Exception:
                    text = raw.decode("latin1", errors="ignore")
                return {"code": code, "text": text, "bytes": raw, "err": ""}
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                raw_err = e.read()
                if raw_err.startswith(b"\x1f\x8b"):
                    raw_err = gzip.decompress(raw_err)
                err_body = raw_err.decode("utf-8", errors="ignore")
            except Exception:
                pass
            return {"code": e.code, "text": err_body, "bytes": b"", "err": "HTTPError: %s" % str(e)}
        except Exception as e:
            return {"code": -1, "text": "", "bytes": b"", "err": "Exception: %s" % str(e)}

    def _unesc(self, s):
        try:
            return html_lib.unescape(s or "").strip()
        except Exception:
            return (s or "").strip()

    def _clean_title(self, t):
        return (t or "").replace("\ufeff", "").strip()

    def _fmt_dur(self, sec):
        try:
            s_val = int(sec)
            m = s_val // 60
            s = s_val % 60
            return "%d:%02d" % (m, s)
        except Exception:
            return ""

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

    # 封面代理 URL 构造（交付 TVBox 原生代理接口）
    def _build_vod_pic(self, poster):
        if not poster:
            return ""
        full_url = self.imgDomain + poster if poster.startswith("/") else (self.imgDomain + "/" + poster)
        encoded_url = base64.urlsafe_b64encode(full_url.encode("utf-8")).decode("utf-8").rstrip("=")
        return "http://127.0.0.1:9978/proxy?do=js&url=%s" % encoded_url

    # AES 文本与数据交互封装
    def _aes_decode(self, text):
        clean_text = text.strip()
        cipher_bytes = base64.b64decode(clean_text)
        dec_bytes = PureAES.decrypt_cbc(cipher_bytes, self.aesKey, self.aesIv)
        return dec_bytes.decode("utf-8", errors="ignore").strip("\ufeff \r\n\t")

    def _aes_encode(self, text):
        plain_bytes = text.encode("utf-8")
        enc_bytes = PureAES.encrypt_cbc(plain_bytes, self.aesKey, self.aesIv)
        return base64.b64encode(enc_bytes).decode("utf-8")

    def _api_get(self, url):
        res = self._fetch(url, referer=self.siteUrl + "/")
        text = res.get("text", "").strip()
        if not text:
            return None
        if text.startswith("{"):
            try:
                return json.loads(text)
            except Exception:
                pass
        try:
            dec_text = self._aes_decode(text)
            return json.loads(dec_text)
        except Exception:
            return None

    def _build_vod_list(self, data):
        list_data = []
        if not data or not isinstance(data, dict):
            return list_data
        records = data.get("records", [])
        if not isinstance(records, list):
            return list_data
        for item in records:
            view_key = item.get("viewKey", "")
            if not view_key:
                continue
            list_data.append({
                "vod_id": self._encode_id(view_key),
                "vod_name": self._unesc(self._clean_title(item.get("title", ""))),
                "vod_pic": self._build_vod_pic(item.get("poster", "")),
                "vod_remarks": self._fmt_dur(item.get("duration", 0))
            })
        return list_data

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

        sort_val = ""
        child_val = ""
        if kwargs.get("extend"):
            ext = kwargs["extend"]
            sort_val = str(ext.get("sort", ""))
            child_val = str(ext.get("children", ""))
        elif len(args) > 1 and isinstance(args[1], dict):
            ext = args[1]
            sort_val = str(ext.get("sort", ""))
            child_val = str(ext.get("children", ""))

        params = "page=%d&pageSize=18" % pg_int
        if tid_str.startswith("s"):
            params += "&sort=%s" % tid_str[1:]
        else:
            params += "&cid=%s" % tid_str
            if sort_val:
                params += "&sort=%s" % sort_val
            if child_val:
                params += "&children=%s" % child_val

        api_url = "%s/app/movie/getList?%s" % (self.siteUrl, params)
        data = self._api_get(api_url)

        vod_list = self._build_vod_list(data)
        page_count = 1
        if data and isinstance(data, dict):
            try:
                page_count = int(data.get("pageCount", 1))
            except Exception:
                pass

        return {
            "list": vod_list,
            "page": pg_int,
            "pagecount": page_count,
            "limit": 18,
            "total": page_count * 18
        }

    # 3. 详情页
    def detailContent(self, ids):
        raw_id_param = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        real_viewkey = self._decode_id(raw_id_param)

        api_url = "%s/app/movie/getDetail?viewKey=%s" % (self.siteUrl, real_viewkey)
        data = self._api_get(api_url)

        title = "未知片名"
        pic = ""
        desc = ""
        year = ""
        duration_str = ""
        tags = []
        play_from_list = []
        play_url_list = []

        if data and isinstance(data, dict) and "data" in data:
            d = data["data"]
            title = self._clean_title(d.get("title", ""))
            pic = self._build_vod_pic(d.get("poster", ""))
            desc = d.get("description", "")
            year = str(d.get("releaseDate", ""))[:4]
            duration_str = self._fmt_dur(d.get("duration", 0))

            raw_tags = str(d.get("tags", "")).split(",")
            tags = [t.strip() for t in raw_tags if t.strip()]

            sources = d.get("sourceInfoListVO", [])
            if sources and isinstance(sources, list):
                for i, src in enumerate(sources):
                    name = src.get("name") if (isinstance(src, dict) and src.get("name")) else ("线路%d" % (i + 1))
                    play_from_list.append(name)
                    play_url_list.append("正片$%s_%d" % (real_viewkey, i))
            else:
                play_from_list.append("红杏线路")
                play_url_list.append("正片$%s_0" % real_viewkey)

        custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】"
        group_info = "【🔥 官方交流群: %s】" % self.tgGroup
        if desc:
            vod_content = "%s\n\n%s\n\n%s" % (group_info, custom_notice, desc)
        else:
            vod_content = "%s\n\n%s\n\n暂无详细简介，欢迎加入TG群获取最新资源！" % (group_info, custom_notice)

        return {
            "list": [{
                "vod_id": raw_id_param,
                "vod_name": self._unesc(title),
                "vod_pic": pic,
                "vod_type_name": ",".join(tags),
                "vod_year": year,
                "vod_area": "",
                "vod_remarks": duration_str,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_content": vod_content,
                "vod_play_from": "$$$".join(play_from_list) if play_from_list else "红杏线路",
                "vod_play_url": "$$$".join(play_url_list) if play_url_list else "正片$%s_0" % real_viewkey
            }]
        }

    # 4. 播放器：保持 parse: 0，纯净直连
    def playerContent(self, flag, id, vipFlags):
        parts = str(id).strip().split("_")
        view_key = parts[0]
        src_idx = 0
        if len(parts) > 1:
            try:
                src_idx = int(parts[1])
            except Exception:
                pass

        api_url = "%s/app/movie/getPlayUrl?viewKey=%s" % (self.siteUrl, view_key)
        data = self._api_get(api_url)

        play_url = ""
        domain = self.playDomain
        if data and isinstance(data, dict) and "data" in data:
            d = data["data"]
            play_url = d.get("playUrl", "")
            sources = d.get("sourceInfoListVO", [])
            if sources and isinstance(sources, list) and len(sources) > src_idx:
                domain = sources[src_idx].get("playDomain") or domain

        real_stream_url = domain + play_url if play_url.startswith("/") else (domain + "/" + play_url)

        return {
            "parse": 0,
            "playUrl": "",
            "url": real_stream_url,
            "header": json.dumps({
                "User-Agent": self._ua,
                "Referer": self.siteUrl + "/",
                "origin": self.siteUrl,
                "priority": "u=1, i"
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

        enc_wd = self._aes_encode(wd)
        api_url = "%s/app/movie/getList?keyword=%s&page=%d&pageSize=18" % (
            self.siteUrl,
            urllib.parse.quote(enc_wd),
            pg_int
        )
        data = self._api_get(api_url)

        vod_list = self._build_vod_list(data)
        page_count = 1
        if data and isinstance(data, dict):
            try:
                page_count = int(data.get("pageCount", 1))
            except Exception:
                pass

        return {
            "list": vod_list,
            "page": pg_int,
            "pagecount": page_count,
            "limit": len(vod_list),
            "total": page_count * 18
        }

    # 6. TVBox 原生封面代理回调
    def localProxy(self, param):
        url = ""
        if isinstance(param, dict):
            url = param.get("url", "")
        elif isinstance(param, str):
            url = param

        if not url:
            return [500, "text/plain", b""]

        # 解码 base64 参数
        decoded_url = ""
        try:
            pad = len(url) % 4
            padded = url + ("=" * (4 - pad) if pad else "")
            decoded_url = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        except Exception:
            try:
                decoded_url = urllib.parse.unquote(url)
            except Exception:
                decoded_url = url

        if not decoded_url.startswith("http"):
            decoded_url = url

        # 拉取加密图片流（二进制）
        res = self._fetch(decoded_url, referer=self.siteUrl + "/", raw_bytes=True)
        raw_cipher = res.get("bytes", b"")
        if not raw_cipher:
            return [500, "text/plain", b""]

        # AES-128-CBC 解密出明文图片流
        dec_bytes = b""
        try:
            # 尝试直接二进制解密
            dec_bytes = PureAES.decrypt_cbc(raw_cipher, self.aesKey, self.aesIv)
        except Exception:
            try:
                # 兜底：Base64 文本解密
                b64_cipher = base64.b64decode(raw_cipher.strip())
                dec_bytes = PureAES.decrypt_cbc(b64_cipher, self.aesKey, self.aesIv)
            except Exception:
                pass

        if not dec_bytes:
            return [500, "text/plain", b""]

        # 检测图片真实 MIME
        mime = "image/webp"
        if dec_bytes.startswith(b"RIFF") and b"WEBP" in dec_bytes[:16]:
            mime = "image/webp"
        elif dec_bytes.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        elif dec_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        elif dec_bytes.startswith(b"GIF8"):
            mime = "image/gif"

        return [200, mime, dec_bytes]