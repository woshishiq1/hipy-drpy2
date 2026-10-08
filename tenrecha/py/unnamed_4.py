# -*- coding: utf-8 -*-
# 目标网站：https://www.libvio.cam/
# 模板类型：苹果CMS / Stui
# 解析手法：XPath + 正则 + JSON
# 技术难点：Artplayer 页面混淆常量 + 播放 API + AES-128-CBC 解密
# 炼制方式：requests + lxml + re + json + 内置 AES
# 四元方悔血炼池 · 丙午年仲秋

import base64
import hashlib
import json
import re
import time
import urllib.parse

import requests
from lxml import html

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    class _BaseSpider(object):
        pass


class _Aes128(object):
    """AES-128 解密块，仅覆盖 CBC 解密所需的最小实现。"""

    _SBOX = [
        0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
        0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
        0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
        0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
        0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
        0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
        0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
        0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
        0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
        0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
        0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
        0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
        0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
        0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
        0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
        0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
    ]

    @staticmethod
    def _xor_table():
        return [[a ^ b for b in range(256)] for a in range(256)]

    @classmethod
    def _sbox_tables(cls):
        inv_sbox = [0] * 256
        for value in range(256):
            inv_sbox[cls._SBOX[value]] = value
        return list(cls._SBOX), inv_sbox

    @staticmethod
    def _gf_mul(left, right):
        result = 0
        for _ in range(8):
            if right & 1:
                result ^= left
            high = left & 0x80
            left = (left << 1) & 0xFF
            if high:
                left ^= 0x1B
            right >>= 1
        return result

    def __init__(self, key):
        if len(key) != 16:
            raise ValueError("AES-128 key must be 16 bytes")
        self.xor_table = self._xor_table()
        self.sbox, self.inv_sbox = self._sbox_tables()
        self.round_keys = self._expand_key(key)

    def _expand_key(self, key):
        words = [int.from_bytes(key[offset:offset + 4], "big") for offset in range(0, 16, 4)]
        rcon = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36]
        for index in range(4, 44):
            temp = words[index - 1]
            if index % 4 == 0:
                temp = ((self._SBOX[(temp >> 24) & 0xFF] << 24) |
                        (self._SBOX[(temp >> 16) & 0xFF] << 16) |
                        (self._SBOX[(temp >> 8) & 0xFF] << 8) |
                        self._SBOX[temp & 0xFF])
                temp = ((temp << 8) | (temp >> 24)) & 0xFFFFFFFF
                temp ^= rcon[index // 4 - 1] << 24
            words.append(words[index - 4] ^ temp)
        return [word.to_bytes(4, "big") for word in words]

    def decrypt_block(self, block):
        inv_sbox = self.inv_sbox
        rk = self.round_keys
        gmul = self._gf_mul

        def add_round_key(state, rnd):
            for column in range(4):
                word = rk[rnd * 4 + column]
                for row in range(4):
                    state[row][column] ^= word[row]

        def inv_shift_rows(state):
            state[1] = state[1][3:] + state[1][:3]
            state[2] = state[2][2:] + state[2][:2]
            state[3] = state[3][1:] + state[3][:1]

        def inv_sub_bytes(state):
            for row in range(4):
                state[row] = [inv_sbox[v] for v in state[row]]

        def inv_mix_columns(state):
            for column in range(4):
                s0, s1, s2, s3 = (state[0][column], state[1][column], state[2][column], state[3][column])
                state[0][column] = (gmul(14, s0) ^ gmul(11, s1) ^ gmul(13, s2) ^ gmul(9, s3))
                state[1][column] = (gmul(9, s0) ^ gmul(14, s1) ^ gmul(11, s2) ^ gmul(13, s3))
                state[2][column] = (gmul(13, s0) ^ gmul(9, s1) ^ gmul(14, s2) ^ gmul(11, s3))
                state[3][column] = (gmul(11, s0) ^ gmul(13, s1) ^ gmul(9, s2) ^ gmul(14, s3))

        state = [[block[column * 4 + row] for column in range(4)] for row in range(4)]
        add_round_key(state, 10)
        for rnd in range(9, 0, -1):
            inv_shift_rows(state)
            inv_sub_bytes(state)
            add_round_key(state, rnd)
            inv_mix_columns(state)
        inv_shift_rows(state)
        inv_sub_bytes(state)
        add_round_key(state, 0)
        return bytes(state[row][column] for column in range(4) for row in range(4))

    def decrypt_cbc(self, data, iv):
        if len(iv) != 16:
            raise ValueError("IV must be 16 bytes")
        if len(data) % 16:
            raise ValueError("ciphertext length must be block aligned")
        plain = bytearray()
        previous = bytes(iv)
        for offset in range(0, len(data), 16):
            block = bytes(data[offset:offset + 16])
            plain.extend(a ^ b for a, b in zip(self.decrypt_block(block), previous))
            previous = block
        padding = plain[-1]
        if 0 < padding <= 16:
            plain = plain[:-padding]
        return bytes(plain)


class Spider(_BaseSpider):
    """Libvio 苹果 CMS / Stui 影视源。"""

    HOST = "https://www.libvio.cam"
    ARTPLAYER = "https://www.libvio.cam/static/player/artplayer/?url={url}&next={next_url}"
    API = "https://hd.ticktockwow.com/smartplay-cache/api/webvideo_ty.php"
    SALT = "RY7e48naFXPsLJC"
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36")
    # 每个主 tab：(tid, name, [(子类型tid, 子类型名)], [地区列表], [年份列表])
    MAIN_CATEGORIES = [
        ("1", "电影", [
            ("6", "动作"), ("7", "喜剧"), ("8", "爱情"), ("9", "科幻"),
            ("10", "恐怖"), ("11", "剧情"), ("12", "战争"),
        ], [
            "大陆", "香港", "台湾", "日本", "美国", "英国", "韩国",
            "西班牙", "泰国", "法国", "丹麦", "智利", "土耳其", "德国",
            "瑞典", "印度", "新西兰", "爱尔兰", "比利时", "希腊",
            "澳大利亚", "芬兰", "巴西", "俄罗斯", "加拿大", "意大利", "其它",
        ], [
            "2026", "2025", "2024", "2023", "2022", "2021", "2020",
            "2019", "2018", "2017", "2016", "2015", "2014", "2013",
            "2012", "2011",
        ]),
        ("2", "电视剧", [
            ("13", "国产剧"), ("14", "港台剧"), ("15", "日韩剧"), ("16", "海外剧"),
        ], [
            "美国", "韩国", "英国", "日本", "大陆", "台湾", "德国",
            "哥伦比亚", "意大利", "西班牙", "丹麦", "挪威", "法国",
            "香港", "泰国", "其它",
        ], [
            "2026", "2025", "2024", "2023", "2022", "2021", "2020",
            "2019", "2018", "2017", "2016", "2015", "2014", "2013",
            "2012", "2011",
        ]),
        ("3", "纪录片", [], [
            "大陆", "英国", "日本", "韩国", "美国", "其它",
        ], [
            "2026", "2025", "2024", "2023", "2022", "2021", "2020",
            "2019", "2018", "2017", "2016", "2015", "2014", "2013",
            "2012", "2011", "2010",
        ]),
        ("4", "动漫", [
            ("24", "国产动漫"), ("25", "日韩动漫"),
            ("26", "港台动漫"), ("27", "欧美动漫"),
        ], [
            "大陆", "日本", "美国", "韩国", "西班牙", "其它",
        ], [
            "2026", "2025", "2024", "2023", "2022", "2021", "2020",
            "2019", "2018", "2017", "2016", "2015", "2014", "2013",
            "2012", "2011",
        ]),
        ("5", "综艺", [
            ("17", "大陆综艺"), ("18", "港台综艺"),
            ("20", "日韩综艺"), ("21", "欧美综艺"),
        ], [], [
            "2026", "2025", "2024", "2023", "2022", "2021", "2020",
            "2019", "2018", "2017", "2016", "2015", "2014", "2013",
            "2012", "2011",
        ]),
    ]

    RE_PLAY_URL = re.compile(r'["\']?const\s+playPageUrl\s*=\s*["\']([^"\']+)["\']')
    RE_SEED = re.compile(r'const\s+secretKeySeed\s*=\s*["\']([^"\']+)["\']')
    RE_TIMESTAMP = re.compile(r'const\s+timestamp\s*=\s*["\']([^"\']+)["\']')
    RE_PLAYER_VAR = re.compile(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*;\s*</script>', re.S)
    RE_DETAIL_ID = re.compile(r'/detail/(\d+)\.html')
    RE_PLAY_ID = re.compile(r'/play/(\d+(?:-\d+)*)\.html')

    def init(self, extend=""):
        self.extend = str(extend or "").strip()
        host = self.HOST
        if self.extend:
            try:
                cfg = json.loads(self.extend)
                if isinstance(cfg, dict):
                    host = str(cfg.get("host") or host).strip()
            except Exception:
                if self.extend.startswith("http"):
                    host = self.extend.strip()
        self.host = host.rstrip("/") if host else self.HOST
        self.timeout = (5, 20)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.UA,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/",
        })

    def getName(self):
        return "Libvio"

    def isVideoFormat(self, url):
        return bool(url and (".m3u8" in url or ".mp4" in url))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    @staticmethod
    def _enc(value):
        return urllib.parse.quote(str(value), safe="~")

    @staticmethod
    def _extract_object(text, start):
        start = text.find("{", start)
        if start < 0:
            return None
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            ch = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]
        return None

    def _fetch_text(self, url):
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return self._decode_response(response)

    @staticmethod
    def _decode_response(response):
        charset = "utf-8"
        content_type = response.headers.get("Content-Type", "")
        match = re.search(r"charset\s*=\s*([\w-]+)", content_type, re.I)
        if match:
            charset = match.group(1)
        if charset.lower() in ("gbk", "gb2312"):
            return response.content.decode("gbk", "replace")
        return response.content.decode("utf-8", "replace")

    def _category_classes(self):
        return [
            {"type_id": tid, "type_pid": "0", "type_name": name}
            for tid, name, *_ in self.MAIN_CATEGORIES
        ]

    @staticmethod
    def _parse_items(text):
        doc = html.fromstring(text)
        items = []
        for box in doc.xpath("//div[contains(@class,'stui-vodlist__box')]"):
            link = box.xpath(".//a[contains(@class,'stui-vodlist__thumb') or contains(@class,'pic')][1]")
            if not link:
                continue
            element = link[0]
            href = element.get("href") or ""
            detail_match = Spider.RE_DETAIL_ID.search(href)
            if not detail_match:
                continue
            name = (element.get("title") or "").strip()
            if not name:
                title = box.xpath(".//div[contains(@class,'stui-vodlist__detail')]//h4//a/text()")
                name = (title[0].strip() if title else "")
            if not name:
                continue
            pic = (element.get("data-original") or element.get("src") or "").strip()
            if pic.startswith("//"):
                pic = "https:" + pic
            remarks = ""
            mark = box.xpath(".//span[contains(@class,'pic-text')][1]/text()")
            if mark:
                remarks = mark[0].strip()
            items.append({
                "vod_id": detail_match.group(1),
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remarks,
                "style": {"type": "rect", "ratio": 1.33},
            })
        return items

    def homeContent(self, filter):
        try:
            classes = self._category_classes()
        except Exception:
            classes = []
        try:
            videos = self._parse_items(self._fetch_text(self.host + "/"))
        except Exception:
            videos = []
        result = {"class": classes, "list": videos}
        filters = {}
        for tid, name, types, areas, years in self.MAIN_CATEGORIES:
            type_values = [{"n": "全部", "v": ""}]
            for child_tid, child_name in types:
                type_values.append({"n": child_name, "v": child_tid})
            area_values = [{"n": "全部", "v": ""}] + [{"n": area, "v": area} for area in areas]
            year_values = [{"n": "全部", "v": ""}] + [{"n": year, "v": year} for year in years]
            filters[tid] = [
                {"key": "tid", "name": "类型", "value": type_values},
                {"key": "area", "name": "地区", "value": area_values},
                {"key": "year", "name": "年份", "value": year_values},
            ]
        result["filters"] = filters
        return result

    def homeVideoContent(self):
        try:
            return {"list": self._parse_items(self._fetch_text(self.host + "/"))}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        # 兼容 TVBox 筛选：若 extend 里带了子分类 tid，直接采用
        try:
            ext = extend or {}
            if isinstance(ext, str):
                try:
                    ext = json.loads(ext)
                except Exception:
                    ext = {}
            selected_tid = str((ext.get("tid") or "")).strip()
            selected_area = str((ext.get("area") or "")).strip()
            selected_year = str((ext.get("year") or "")).strip()
            if selected_tid.isdigit():
                tid = selected_tid
        except Exception:
            selected_area = ""
            selected_year = ""
            pass
        try:
            page = max(1, int(pg or 1))
            source_page = 2 * page - 1
            # URL格式: /{tid}--------{page}---{year}.html (无地区)
            #          /{tid}-{area}-------{page}---{year}.html (有地区)
            if selected_area:
                first_url = "{}/show/{}-{}-------{}---{}.html".format(
                    self.host, tid, selected_area, source_page, selected_year
                )
            else:
                first_url = "{}/show/{}--------{}---{}.html".format(
                    self.host, tid, source_page, selected_year
                )
            first_text = self._fetch_text(first_url)
            videos = self._unique_videos(self._parse_items(first_text))
            last_page = max(1, self._last_source_page(first_text))
            for next_page in (source_page + 1, source_page + 2):
                if len(videos) >= 24 or next_page > last_page:
                    break
                if selected_area:
                    next_url = "{}/show/{}-{}-------{}---{}.html".format(
                        self.host, tid, selected_area, next_page, selected_year
                    )
                else:
                    next_url = "{}/show/{}--------{}---{}.html".format(
                        self.host, tid, next_page, selected_year
                    )
                try:
                    videos.extend(self._parse_items(self._fetch_text(next_url)))
                    videos = self._unique_videos(videos)
                except Exception:
                    pass
            return {
                "list": videos[:24],
                "page": page,
                "pagecount": max(1, (last_page + 1) // 2),
                "limit": 24,
                "total": last_page * 12,
            }
        except Exception:
            return {"list": [], "page": int(pg or 1), "pagecount": 1, "limit": 12, "total": 0}

    @staticmethod
    def _last_source_page(text):
        # 兼容: /show/1--------2---.html、/show/1-大陆-------2---.html、
        #       /show/1--------2---2026.html、/show/1-大陆-------2---2026.html
        pages = []
        for value in re.findall(r"/show/\d+--------(\d+)---(?:\d+)?\.html", text or ""):
            pages.append(int(value))
        for value in re.findall(r"/show/\d+-[^/]+-------(\d+)---(?:\d+)?\.html", text or ""):
            pages.append(int(value))
        return max(pages, default=1)

    @staticmethod
    def _unique_videos(videos):
        result = []
        seen = set()
        for item in videos or []:
            video_id = item.get("vod_id")
            if not video_id or video_id in seen:
                continue
            seen.add(video_id)
            result.append(item)
        return result

    def searchContent(self, key, quick, pg="1"):
        try:
            page = max(1, int(pg or 1))
            article = {"wd": str(key or "")}
            response = self.session.post(
                self.host + "/search/-------------.html",
                data=article,
                timeout=self.timeout,
            )
            response.raise_for_status()
            text = self._decode_response(response)
            videos = self._parse_items(text)
            return {
                "list": videos,
                "page": page,
                "pagecount": page + 1 if len(videos) >= 12 else page,
                "limit": len(videos) or 12,
                "total": len(videos),
            }
        except Exception:
            return {"list": [], "page": int(pg or 1), "pagecount": 1, "limit": 12, "total": 0}

    def detailContent(self, ids):
        try:
            if isinstance(ids, (list, tuple)):
                video_id = str(ids[0] or "")
            else:
                video_id = str(ids or "")
            video_id = video_id.split("-")[0].split("$")[-1].strip()
            text = self._fetch_text("{}/detail/{}.html".format(self.host, video_id))
            doc = html.fromstring(text)
            root = doc.xpath("//div[contains(@class,'stui-content')]")
            detail = root[0] if root else doc
            title_node = detail.xpath(".//div[contains(@class,'stui-content__detail')]//h1[contains(@class,'title')]/text()")
            title = title_node[0].strip() if title_node else video_id
            pic_node = detail.xpath(".//div[contains(@class,'stui-content__thumb')]//img[1]")
            pic = ""
            if pic_node:
                pic = (pic_node[0].get("data-original") or pic_node[0].get("src") or "").strip()
                if pic.startswith("//"):
                    pic = "https:" + pic
            vod = {
                "vod_id": video_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_play_from": "",
                "vod_play_url": "",
            }
            data_lines = detail.xpath(".//div[contains(@class,'stui-content__detail')]//p[contains(@class,'data')]//text()")
            data_text = "".join(data_lines)
            for label, field in (
                ("主演", "vod_actor"),
                ("导演", "vod_director"),
                ("地区", "vod_area"),
                ("年份", "vod_year"),
            ):
                match = re.search(label + r"\s*[:：]\s*([^/]+)", data_text)
                if match:
                    vod[field] = match.group(1).strip()
            desc_node = detail.xpath(".//div[contains(@class,'stui-content__detail')]//p[contains(@class,'desc')]")
            if desc_node:
                desc = " ".join(desc_node[0].text_content().split()).strip()
                desc = re.sub(r"详情\s*$", "", desc)
                vod["vod_content"] = desc
            heads = doc.xpath("//div[contains(@class,'stui-vodlist__head')]//h3")
            playlists = doc.xpath("//ul[contains(@class,'stui-content__playlist')]")
            play_from = []
            play_parts = []
            seen_ids = set()
            for head, playlist in zip(heads, playlists):
                source = " ".join(head.text_content().split()).strip()
                if not source or "下载" in source:
                    continue
                ids = []
                for link in playlist.xpath(".//a"):
                    href = link.get("href") or ""
                    match = self.RE_PLAY_ID.search(href)
                    if not match:
                        continue
                    play_id = match.group(1)
                    if play_id in seen_ids:
                        continue
                    seen_ids.add(play_id)
                    name = " ".join(link.text_content().split()).strip() or "播放"
                    ids.append("{}${}".format(name, play_id))
                if ids:
                    play_from.append(source)
                    play_parts.append("#".join(ids))
            if play_from:
                vod["vod_play_from"] = "$$$".join(play_from)
                vod["vod_play_url"] = "$$$".join(play_parts)
            return {"list": [vod]}
        except Exception:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        try:
            play_id = str(id or "").strip()
            try:
                result = self._resolve_play_id(play_id)
            except Exception:
                result = None
            if result and result.get("url"):
                return result
            for candidate in self._alternate_play_ids(play_id):
                try:
                    result = self._resolve_play_id(candidate)
                except Exception:
                    result = None
                if result and result.get("url"):
                    return result
            return result or {"parse": 0, "url": ""}
        except Exception:
            return {"parse": 0, "url": ""}

    def _resolve_play_id(self, play_id):
        play_id = str(play_id or "").strip()
        if play_id.startswith("http"):
            return {"parse": 0, "url": play_id, "header": {}}
        if not play_id:
            return None
        text = self._fetch_text("{}/play/{}.html".format(self.host, play_id))
        config = self._extract_player_config(text)
        if not config:
            return None
        source = str(config.get("url") or "").strip()
        if not source:
            return None
        next_url = str(config.get("link_next") or config.get("url_next") or "").strip()
        art_url = self.ARTPLAYER.format(
            url=urllib.parse.quote(source, safe=":/?&=,;%+"),
            next_url=urllib.parse.quote(next_url, safe=":/?&=,;%+"),
        )
        art_text = self._fetch_text(art_url)
        play_page = self._first_match(self.RE_PLAY_URL, art_text)
        seed = self._first_match(self.RE_SEED, art_text)
        timestamp = self._first_match(self.RE_TIMESTAMP, art_text)
        if not (play_page and seed and timestamp):
            return self._source_result(source)
        now = int(time.time())
        signature = hashlib.md5(str(now).encode("utf-8")).hexdigest()
        payload = {
            "vkey": play_page,
            "code": seed,
            "t": now,
            "signature": signature,
        }
        response = self.session.post(
            self.API,
            headers={
                "Accept": "*/*",
                "Content-Type": "application/json",
                "Origin": self.host,
                "Referer": self.host + "/",
                "User-Agent": self.UA,
            },
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=self.timeout,
        )
        response.raise_for_status()
        body = response.json()
        if body.get("code") != 200:
            return self._source_result(source)
        encrypted = str(body.get("url") or "")
        if not encrypted:
            return self._source_result(source)
        md5hex = hashlib.md5((timestamp + self.SALT).encode("utf-8")).hexdigest()
        raw = base64.b64decode(encrypted)
        aes = _Aes128(md5hex[16:32].encode("utf-8"))
        plain = aes.decrypt_cbc(raw, md5hex[:16].encode("utf-8"))
        text_url = self._decode_mixed(plain).strip()
        if text_url.startswith("http") and (".m3u8" in text_url or ".mp4" in text_url):
            return {"parse": 0, "url": text_url, "header": {"User-Agent": self.UA}}
        return self._source_result(source)

    @staticmethod
    def _source_result(source):
        source = str(source or "").strip()
        if source.startswith("http") and (".m3u8" in source or ".mp4" in source):
            return {"parse": 1, "url": source, "header": {}}
        return None

    def _alternate_play_ids(self, play_id):
        play_id = str(play_id or "").strip()
        if not play_id or "-" not in play_id:
            return []
        video_id = play_id.split("-")[0]
        episode = play_id.rsplit("-", 1)[1]
        try:
            text = self._fetch_text("{}/detail/{}.html".format(self.host, video_id))
        except Exception:
            return []
        doc = html.fromstring(text)
        heads = doc.xpath("//div[contains(@class,'stui-vodlist__head')]//h3")
        playlists = doc.xpath("//ul[contains(@class,'stui-content__playlist')]")
        same_episode = []
        seen = {play_id}
        for head, playlist in zip(heads, playlists):
            source = " ".join(head.text_content().split()).strip()
            if not source or "下载" in source:
                continue
            for link in playlist.xpath(".//a"):
                href = link.get("href") or ""
                match = self.RE_PLAY_ID.search(href)
                if not match:
                    continue
                candidate = match.group(1)
                if candidate in seen:
                    continue
                seen.add(candidate)
                if "-" in candidate and candidate.rsplit("-", 1)[1] == episode:
                    same_episode.append(candidate)
        return same_episode

    def _extract_player_config(self, text):
        start = text.find("var player_aaaa=")
        raw = ""
        if start >= 0:
            raw = self._extract_object(text, start + len("var player_aaaa=")) or ""
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    @staticmethod
    def _first_match(pattern, text):
        match = pattern.search(text or "")
        return match.group(1).strip() if match else ""

    @staticmethod
    def _decode_mixed(data):
        try:
            return bytes(data).decode("utf-8")
        except UnicodeDecodeError:
            return bytes(data).decode("gbk", "replace")
