# -*- coding: utf-8 -*-
# //@name:Hanime1
# //@id:hanime1
# //@version:2
# //wab201 学习研究用

import base64
import json
import re
import time
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from lxml import html

from base.spider import Spider


class Spider(Spider):
    HOST = "https://hanime1.me"
    PLAY_PREFIX = "hanime1://play/"
    CATEGORIES = (
        ("all", "全部", ""),
        ("hentai", "裏番", "裏番"),
        ("short", "泡麵番", "泡麵番"),
        ("motion", "Motion Anime", "Motion Anime"),
        ("cg3d", "3DCG", "3DCG"),
        ("d25", "2.5D", "2.5D"),
        ("d2", "2D動畫", "2D動畫"),
        ("ai", "AI生成", "AI生成"),
        ("mmd", "MMD", "MMD"),
        ("cosplay", "Cosplay", "Cosplay"),
    )
    SORTS = (
        "最新上市",
        "最新上傳",
        "本日排行",
        "本週排行",
        "本月排行",
        "觀看次數",
        "讚好比例",
        "時長最長",
        "他們在看",
    )
    DURATIONS = (
        "",
        "1 分鐘 +",
        "5 分鐘 +",
        "10 分鐘 +",
        "20 分鐘 +",
        "30 分鐘 +",
        "60 分鐘 +",
        "0 - 10 分鐘",
        "0 - 20 分鐘",
    )
    VIDEO_RE = re.compile(r"\.(?:mp4|m3u8|mkv|webm)(?:$|[?#])", re.I)

    def __init__(self):
        self.name = "Hanime1"
        self.host = self.HOST
        self.timeout = 20
        self.retries = 2
        self.preferred_quality = 0
        self.trust_env = True
        self.cookie = ""
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/138.0.0.0 Safari/537.36"
        )
        self.backend_parse = False
        self.category_mode = False
        self.categoryMode = False
        self.session = None

    def getName(self):
        return self.name

    def init(self, extend=""):
        config = self._config(extend)
        self.host = self._host(config.get("host") or self.HOST)
        self.timeout = self._bounded_int(config.get("timeout"), 20, 8, 45)
        self.retries = self._bounded_int(config.get("retries"), 2, 0, 4)
        self.preferred_quality = self._bounded_int(
            config.get("preferred_quality"), 0, 0, 4320
        )
        self.trust_env = self._bool(config.get("trust_env"), True)
        self.cookie = str(
            config.get("cookie") or config.get("cf_cookie") or ""
        ).strip()
        self.user_agent = str(config.get("user_agent") or self.user_agent).strip()
        self._reset_session()

    def destroy(self):
        if self.session is not None:
            try:
                self.session.close()
            except Exception:
                pass
        self.session = None

    def isVideoFormat(self, url):
        return bool(self.VIDEO_RE.search(str(url or "")))

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        classes = [
            {"type_id": type_id, "type_name": type_name}
            for type_id, type_name, _ in self.CATEGORIES
        ]
        filters = {}
        sort_values = [{"n": value, "v": value} for value in self.SORTS]
        duration_values = [
            {"n": value or "全部", "v": value} for value in self.DURATIONS
        ]
        for type_id, _, _ in self.CATEGORIES:
            filters[type_id] = [
                {"key": "sort", "name": "排序", "value": sort_values},
                {"key": "duration", "name": "時長", "value": duration_values},
            ]
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        result = self.categoryContent("all", "1", False, {"sort": "最新上傳"})
        return {"list": result.get("list", [])}

    def categoryContent(self, tid, pg, filter, extend):
        page = self._page(pg)
        genre = self._category_genre(tid)
        options = self._config(extend)
        params = {
            "sort": str(options.get("sort") or "最新上傳"),
            "page": page,
        }
        duration = str(options.get("duration") or "").strip()
        if genre:
            params["genre"] = genre
        if duration:
            params["duration"] = duration
        try:
            source, _ = self._request_text("/search", params=params)
            return self._parse_listing(source, page)
        except Exception as exc:
            return self._empty_page(page, "分類讀取失敗: %s" % exc)

    def searchContent(self, key, quick, pg="1"):
        page = self._page(pg)
        keyword = self._clean(key)
        if not keyword:
            return self._empty_page(page)
        try:
            source, _ = self._request_text(
                "/search", params={"query": keyword, "page": page}
            )
            return self._parse_listing(source, page)
        except Exception as exc:
            return self._empty_page(page, "搜尋失敗: %s" % exc)

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        video_id = self._video_id(raw_id)
        if not video_id:
            return {"list": []}
        try:
            source, page_url = self._request_text(
                "/watch", params={"v": video_id}
            )
            return {"list": [self._parse_detail(source, video_id, page_url)]}
        except Exception as exc:
            message = "詳情讀取失敗: %s" % exc
            return {
                "list": [
                    {
                        "vod_id": video_id,
                        "vod_name": "Hanime1 %s" % video_id,
                        "vod_remarks": message,
                        "vod_content": message,
                        "vod_play_from": "Hanime1直鏈",
                        "vod_play_url": "重試$%s%s/0" % (self.PLAY_PREFIX, video_id),
                    }
                ]
            }

    def playerContent(self, flag, id, vipFlags):
        video_id, requested_quality = self._play_id(id)
        if not video_id:
            return self._player_error("無法識別播放 ID")
        try:
            source, page_url = self._request_text(
                "/watch", params={"v": video_id}
            )
            sources = self._parse_sources(self._document(source))
            selected = self._select_source(sources, requested_quality)
            if not selected:
                return self._player_error("播放頁沒有可用的直鏈")
            return {
                "parse": 0,
                "jx": 0,
                "playUrl": "",
                "url": selected[1],
                "header": {
                    "User-Agent": self.user_agent,
                    "Referer": page_url,
                    "Origin": self.host,
                },
            }
        except Exception as exc:
            return self._player_error("播放解析失敗: %s" % exc)

    def _reset_session(self):
        self.destroy()
        self.session = requests.Session()
        self.session.trust_env = self.trust_env
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
                "Cache-Control": "no-cache",
            }
        )
        if self.cookie:
            self.session.headers["Cookie"] = self.cookie.removeprefix("Cookie:").strip()

    def _request_text(self, path, params=None):
        if self.session is None:
            self._reset_session()
        url = urljoin(self.host + "/", str(path or "").lstrip("/"))
        last_error = None
        for attempt in range(self.retries + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers={"Referer": self.host + "/"},
                    timeout=self.timeout,
                    allow_redirects=True,
                )
                source = self._decode_response(response)
                if self._is_challenge(source) or response.status_code in (403, 429, 503):
                    raise RuntimeError(
                        "Cloudflare 驗證未通過；請在同一出口的瀏覽器完成驗證，"
                        "再於 Extend 填入 Cookie 和相同 User-Agent"
                    )
                response.raise_for_status()
                return source, response.url
            except (requests.RequestException, RuntimeError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.35 * (attempt + 1))
        raise RuntimeError(str(last_error or "請求失敗"))

    def _parse_listing(self, source, page):
        doc = self._document(source)
        cards = []
        seen = set()
        nodes = doc.xpath(
            "//a[contains(@href,'/watch') and "
            ".//div[contains(concat(' ',normalize-space(@class),' '),' search-videos ')]]"
        )
        if not nodes:
            nodes = doc.xpath("//a[contains(@class,'video-link') and contains(@href,'/watch')]")
        for node in nodes:
            video_id = self._video_id(node.get("href"))
            if not video_id or video_id in seen:
                continue
            seen.add(video_id)
            title = self._clean(
                node.xpath("string(.//div[contains(@class,'home-rows-videos-title')][1])")
                or node.xpath("string(.//div[contains(@class,'title')][1])")
                or node.get("title")
            )
            image = node.xpath("string(.//img[1]/@src)")
            duration = self._clean(
                node.xpath("string(.//div[contains(@class,'duration')][1])")
            )
            cards.append(
                {
                    "vod_id": video_id,
                    "vod_name": title or "Hanime1 %s" % video_id,
                    "vod_pic": urljoin(self.host + "/", image),
                    "vod_remarks": duration,
                }
            )
        page_numbers = []
        for text_value in doc.xpath("//ul[contains(@class,'pagination')]//li//text()"):
            value = self._clean(text_value)
            if value.isdigit():
                page_numbers.append(int(value))
        pagecount = max([page] + page_numbers)
        limit = len(cards)
        return {
            "list": cards,
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": pagecount * limit if limit else 0,
        }

    def _parse_detail(self, source, video_id, page_url):
        doc = self._document(source)
        title = self._clean(
            doc.xpath("string(//meta[@property='og:title']/@content)")
            or doc.xpath("string(//h3[@id='shareBtn-title'])")
            or doc.xpath("string(//title)")
        )
        title = re.sub(r"\s*-\s*Hanime1\.me\s*$", "", title, flags=re.I)
        cover = doc.xpath("string(//meta[@property='og:image']/@content)")
        if not cover:
            cover = doc.xpath("string(//video[@id='player']/@poster)")
        content = self._clean(doc.xpath("string(//meta[@name='description']/@content)"))
        actor = self._clean(doc.xpath("string(//a[@id='video-artist-name'])"))
        genre = self._clean(
            doc.xpath("string((//a[contains(@href,'genre=')])[last()])")
        )
        tag_values = []
        for node in doc.xpath("//div[contains(@class,'single-video-tag')]/a"):
            value = re.sub(r"\s*\(\d+\)\s*$", "", self._clean(node.text_content()))
            if value and value not in tag_values:
                tag_values.append(value)
        date_match = re.search(
            r"\b(20\d{2})-\d{2}-\d{2}\b", self._clean(doc.text_content())
        )
        sources = self._parse_sources(doc)
        play_items = []
        for quality, _ in sources:
            label = "%sP" % quality if quality else "自動"
            play_items.append(
                "%s$%s%s/%s" % (label, self.PLAY_PREFIX, video_id, quality or 0)
            )
        if not play_items:
            play_items.append("自動$%s%s/0" % (self.PLAY_PREFIX, video_id))
        return {
            "vod_id": video_id,
            "vod_name": title or "Hanime1 %s" % video_id,
            "vod_pic": urljoin(page_url, cover),
            "type_name": genre,
            "vod_year": date_match.group(1) if date_match else "",
            "vod_actor": actor,
            "vod_content": content,
            "vod_tag": ",".join(tag_values[:24]),
            "vod_play_from": "Hanime1直鏈",
            "vod_play_url": "#".join(play_items),
        }

    def _parse_sources(self, doc):
        values = {}
        for node in doc.xpath("//video//source[@src]"):
            url = urljoin(self.host + "/", node.get("src"))
            quality = self._quality(node.get("size"), url)
            if url.startswith(("http://", "https://")):
                values[quality] = url
        if not values:
            for node in doc.xpath("//link[@rel='preload' and @as='video']/@href"):
                url = urljoin(self.host + "/", node)
                values[self._quality("", url)] = url
        return sorted(values.items(), key=lambda item: item[0], reverse=True)

    def _document(self, source):
        if isinstance(source, (bytes, bytearray)):
            text = self._decode_bytes(bytes(source))
        else:
            text = str(source or "")
            if "\x00" in text[:256]:
                try:
                    text = self._decode_bytes(text.encode("latin-1"))
                except (UnicodeEncodeError, UnicodeDecodeError):
                    text = text.replace("\x00", "")
        parser = html.HTMLParser(encoding="utf-8", recover=True)
        return html.fromstring(text.encode("utf-8"), parser=parser)

    def _decode_response(self, response):
        return self._decode_bytes(response.content, response.encoding)

    @staticmethod
    def _decode_bytes(raw, declared_encoding=""):
        if not raw:
            return ""
        signatures = (
            (b"\xff\xfe\x00\x00", "utf-32-le"),
            (b"\x00\x00\xfe\xff", "utf-32-be"),
            (b"\xff\xfe", "utf-16-le"),
            (b"\xfe\xff", "utf-16-be"),
        )
        for signature, encoding in signatures:
            if raw.startswith(signature):
                return raw.decode(encoding).lstrip("\ufeff")
        sample = raw[:512]
        if len(sample) >= 16:
            groups = len(sample) // 4
            le32_zeros = sum(
                sample[index] == 0
                for index in range(1, groups * 4)
                if index % 4 in (1, 2, 3)
            )
            be32_zeros = sum(
                sample[index] == 0
                for index in range(0, groups * 4)
                if index % 4 in (0, 1, 2)
            )
            if le32_zeros >= groups * 2:
                return raw.decode("utf-32-le")
            if be32_zeros >= groups * 2:
                return raw.decode("utf-32-be")
        if raw[:4] == b"<\x00\x00\x00":
            return raw.decode("utf-32-le")
        if raw[:4] == b"\x00\x00\x00<":
            return raw.decode("utf-32-be")
        if raw[:2] == b"<\x00":
            return raw.decode("utf-16-le")
        if raw[:2] == b"\x00<":
            return raw.decode("utf-16-be")
        candidates = [str(declared_encoding or "").strip(), "utf-8-sig", "utf-8"]
        for encoding in candidates:
            if not encoding:
                continue
            try:
                return raw.decode(encoding)
            except (LookupError, UnicodeDecodeError):
                continue
        return raw.decode("utf-8", errors="replace")

    def _select_source(self, sources, requested_quality):
        if not sources:
            return None
        target = requested_quality or self.preferred_quality
        if target:
            for item in sources:
                if item[0] == target:
                    return item
            return min(sources, key=lambda item: abs(item[0] - target))
        return sources[0]

    def _play_id(self, value):
        text = str(value or "").strip()
        match = re.match(r"^hanime1://play/(\d+)/(\d+)$", text)
        if match:
            return match.group(1), int(match.group(2))
        video_id = self._video_id(text)
        return (video_id, 0) if video_id else ("", 0)

    def _video_id(self, value):
        text = str(value or "").strip()
        if text.startswith("atvp_detail:"):
            text = text[len("atvp_detail:") :].strip()
        if text.isdigit():
            return text
        match = re.search(r"hanime1://(?:video|play)/(\d+)", text)
        if match:
            return match.group(1)
        try:
            values = parse_qs(urlsplit(text).query).get("v") or []
            if values and str(values[0]).isdigit():
                return str(values[0])
        except Exception:
            pass
        match = re.search(r"(?:[?&]v=|/watch/)(\d+)", text)
        return match.group(1) if match else ""

    def _category_genre(self, tid):
        value = str(tid or "all")
        for type_id, _, genre in self.CATEGORIES:
            if value == type_id or value == genre:
                return genre
        return ""

    def _quality(self, value, url):
        match = re.search(r"(\d{3,4})", str(value or ""))
        if not match:
            match = re.search(r"[-_](\d{3,4})p(?:\.|[/?])", str(url or ""), re.I)
        return int(match.group(1)) if match else 0

    def _is_challenge(self, source):
        text = str(source or "")[:80000].lower()
        signals = (
            "<title>just a moment...</title>",
            "id=\"challenge-form\"",
            "cf-browser-verification",
            "cf-chl-captcha",
            "attention required! | cloudflare",
        )
        return any(signal in text for signal in signals)

    def _player_error(self, message):
        text = self._clean(message) or "播放失敗"
        return {
            "parse": 0,
            "jx": 0,
            "playUrl": "",
            "url": "",
            "header": {},
            "msg": text,
            "error": text,
            "content": text,
        }

    def _empty_page(self, page, message=""):
        result = {
            "list": [],
            "page": page,
            "pagecount": page,
            "limit": 0,
            "total": 0,
        }
        if message:
            result["msg"] = message
        return result

    def _config(self, extend):
        if isinstance(extend, dict):
            return extend
        text = str(extend or "").strip()
        if not text:
            return {}
        candidates = [text]
        try:
            candidates.append(
                base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)).decode("utf-8")
            )
        except Exception:
            pass
        for candidate in candidates:
            try:
                value = json.loads(candidate)
                if isinstance(value, dict):
                    return value
            except Exception:
                continue
        return {"cookie": text} if "=" in text else {}

    @staticmethod
    def _host(value):
        text = str(value or "").strip().rstrip("/")
        return text if text.startswith(("http://", "https://")) else Spider.HOST

    @staticmethod
    def _clean(value):
        return " ".join(str(value or "").replace("\xa0", " ").split())

    @staticmethod
    def _page(value):
        try:
            return max(1, int(value))
        except Exception:
            return 1

    @staticmethod
    def _bounded_int(value, default, low, high):
        try:
            return min(high, max(low, int(value)))
        except Exception:
            return default

    @staticmethod
    def _bool(value, default):
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in ("1", "true", "yes", "on")
