# -*- coding: utf-8 -*-
# //@name:FreeOKOK全链直播放
# //@id:freeokok_direct
# //@version:1

import base64
import html as html_lib
import ipaddress
import json
import re
import time
from urllib.parse import quote, unquote, urljoin, urlsplit

import requests
from lxml import html

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    name = "FreeOKOK全链直播放"
    host = "https://freeokok.com"
    backend_parse = False
    category_mode = False
    categoryMode = False

    PLAY_PREFIX = "freeokok-play:"
    ERROR_PREFIX = "freeokok-error:"
    DEFAULT_PIC = "https://freeokok.com/static/images/logo.jpg"

    CATEGORY_SPECS = (
        ("lianxuju", "电视剧"),
        ("dianying", "电影"),
        ("zongyi", "综艺"),
        ("dongman", "动漫"),
        ("duanju", "短剧"),
    )
    CATEGORY_IDS = set(item[0] for item in CATEGORY_SPECS)
    SORTS = (("最新", "time"), ("热门", "hits"), ("评分", "score"))
    LANGUAGE_FILTERS = {
        "dianying": ("国语", "英语", "粤语", "闽南语", "韩语", "日语", "法语", "德语", "其它"),
        "lianxuju": ("国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"),
        "zongyi": ("国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"),
        "dongman": ("国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"),
        "duanju": (),
    }
    CLASS_FILTERS = {
        "dianying": (
            "喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪",
            "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚",
            "经典", "青春", "文艺", "微电影", "古装", "历史", "运动", "农村",
            "儿童", "网络电影",
        ),
        "lianxuju": (
            "古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻",
            "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他",
        ),
        "zongyi": (
            "选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实",
            "曲艺", "生活", "游戏互动", "财经", "求职",
        ),
        "dongman": (
            "情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园",
            "动作", "机战", "运动", "战争", "少年", "少女", "社会", "原创",
            "亲子", "益智", "励志", "其他",
        ),
        "duanju": (),
    }
    AREA_FILTERS = {
        "dianying": (
            "大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国",
            "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他",
        ),
        "lianxuju": ("内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国", "新加坡", "其他"),
        "zongyi": ("内地", "港台", "日韩", "欧美"),
        "dongman": ("国产", "日本", "欧美", "其他"),
        "duanju": (),
    }

    DETAIL_PATH_RE = re.compile(r"^/O/(\d+)\.html$", re.I)
    PLAY_PATH_RE = re.compile(r"^/K/(\d+)-(\d+)-(\d+)\.html$", re.I)
    DIRECT_MEDIA_RE = re.compile(
        r"\.(?:m3u8|m3u|mp4|m4v|mkv|webm|flv|mpd|ts)(?:$|[?#])", re.I
    )
    MEDIA_CONTENT_TYPES = (
        "application/vnd.apple.mpegurl",
        "application/x-mpegurl",
        "application/dash+xml",
        "video/",
        "audio/mpegurl",
    )
    DIRECT_LOADERS = set(("dplayer", "videojs", "iva", "flv"))
    PAGE_LOADERS = set(("jsyun", "iframe", "link", "parse"))
    CHALLENGE_MARKERS = (
        "just a moment",
        "/cdn-cgi/challenge-platform",
        "cf-turnstile",
        "attention required",
        "_cf_chl_opt",
    )
    PLAYER_PAGE_MARKERS = (
        "new dplayer",
        "new hls",
        "hls.loadsource",
        "player_aaaa",
        "macplayer.playurl",
        "video-js",
    )

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.timeout = 15
        self.cache_ttl = 60
        self.verify_tls = True
        self.trust_env = True
        self.resolve_depth = 3
        self.max_page_bytes = 2 * 1024 * 1024
        self.quality_weight = 0.6
        self.speed_weight = 0.4
        self.learn_resolve_latency = False
        self._line_scores = {}
        self._resolve_latency = {}
        self._last_line_ranking = []
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
        self._hosts = ["https://freeokok.com", "https://www.freeokok.com"]
        self._active_host = self._hosts[0]
        self._session = None
        self._cache = {}
        self._player_config = None
        self._reset_session()

    def getName(self):
        return self.name

    def init(self, extend=""):
        config = self._parse_dict(extend)
        hosts = self._parse_hosts(config.get("hosts"))
        single_host = self._safe_origin(config.get("host"))
        if single_host:
            hosts.insert(0, single_host)
        if hosts:
            self._hosts = self._unique_text(hosts)
        self.timeout = self._bounded_int(config.get("timeout"), self.timeout, 5, 45)
        self.cache_ttl = self._bounded_int(config.get("cache_ttl"), self.cache_ttl, 0, 600)
        self.resolve_depth = self._bounded_int(config.get("resolve_depth"), self.resolve_depth, 1, 4)
        quality_weight = config.get("quality_weight", config.get("clarity_weight", 0.6))
        speed_weight = config.get("speed_weight", 0.4)
        self.quality_weight, self.speed_weight = self._normalize_weights(
            quality_weight, speed_weight
        )
        self.learn_resolve_latency = self._bool_value(
            config.get("learn_resolve_latency"), False
        )
        self._line_scores = self._parse_line_scores(config.get("line_scores"))
        self._resolve_latency = {}
        self._last_line_ranking = []
        self.verify_tls = self._bool_value(config.get("verify_tls"), self.verify_tls)
        self.trust_env = self._bool_value(config.get("trust_env"), self.trust_env)
        user_agent = self._clean_text(config.get("user_agent"))
        if user_agent:
            self.user_agent = user_agent
        self.host = self._hosts[0]
        self._active_host = self.host
        self._cache.clear()
        self._player_config = None
        self._reset_session()

    def destroy(self):
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
        self._session = None
        self._cache.clear()

    def isVideoFormat(self, url):
        return self._is_direct_media_url(url)

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [404, "text/plain; charset=utf-8", b"not found"]

    def homeContent(self, filter):
        classes = [
            {"type_id": type_id, "type_name": type_name}
            for type_id, type_name in self.CATEGORY_SPECS
        ]
        filters = {}
        for type_id, _ in self.CATEGORY_SPECS:
            rows = [self._filter_row("sort", "排序", self.SORTS)]
            values = self.CLASS_FILTERS.get(type_id, ())
            if values:
                rows.append(
                    self._filter_row(
                        "class",
                        "类型",
                        (("全部", ""),) + tuple((value, value) for value in values),
                    )
                )
            values = self.AREA_FILTERS.get(type_id, ())
            if values:
                rows.append(
                    self._filter_row(
                        "area",
                        "地区",
                        (("全部", ""),) + tuple((value, value) for value in values),
                    )
                )
            values = self.LANGUAGE_FILTERS.get(type_id, ())
            if values:
                rows.append(
                    self._filter_row(
                        "lang",
                        "语言",
                        (("全部", ""),)
                        + tuple((value, value) for value in values),
                    )
                )
            filters[type_id] = rows
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        try:
            source, page_url = self._request_business(
                "/", markers=("video-list-container", "/O/")
            )
            result = self._parse_list_page(source, 1, page_url, "home")
            return {"list": result.get("list", []), "msg": result.get("msg", "")}
        except Exception as exc:
            return {"list": [], "msg": "首页读取失败: %s" % exc}

    def categoryContent(self, tid, pg, filter, extend):
        category = str(tid or "").strip()
        page = self._page_number(pg)
        if category not in self.CATEGORY_IDS:
            return self._empty_page(page, "未知分类")
        values = self._parse_dict(extend)
        area = self._allowed_filter(values.get("area"), self.AREA_FILTERS.get(category, ()))
        sort_value = self._allowed_filter(values.get("sort"), tuple(x[1] for x in self.SORTS))
        class_value = self._allowed_filter(values.get("class"), self.CLASS_FILTERS.get(category, ()))
        language = self._allowed_filter(
            values.get("lang"), self.LANGUAGE_FILTERS.get(category, ())
        )
        if area or sort_value or class_value or language:
            path = self._filter_path(
                category, area, sort_value, class_value, language, page
            )
        elif page == 1:
            path = "/F/%s.html" % category
        else:
            path = "/F/%s-%d.html" % (category, page)
        try:
            source, page_url = self._request_business(
                path, markers=("video-list-container", "/O/")
            )
            return self._parse_list_page(source, page, page_url, "category")
        except Exception as exc:
            return self._empty_page(page, "分类读取失败: %s" % exc)

    def searchContent(self, key, quick, pg="1"):
        page = self._page_number(pg)
        keyword = self._clean_text(key)
        if not keyword:
            return self._empty_page(page, "搜索词为空")
        if len(keyword) > 80 or any(char in keyword for char in "\r\n#$"):
            return self._empty_page(page, "搜索词不合法")
        path = "/vodsearch/%s----------%d---.html" % (
            quote(keyword, safe=""),
            page,
        )
        try:
            source, page_url = self._request_business(
                path, markers=("search_result_info", "search_result_list")
            )
            return self._parse_list_page(source, page, page_url, "search")
        except Exception as exc:
            return self._empty_page(page, "搜索读取失败: %s" % exc)

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        path = self._normalize_detail_id(raw_id)
        if not path:
            return {"list": [self._detail_error(str(raw_id or ""), "无效详情 ID")]}
        try:
            source, page_url = self._request_business(
                path, markers=("video_play_channel_list", "video-detail-main")
            )
            return {"list": [self._parse_detail_page(source, path, page_url)]}
        except Exception as exc:
            return {"list": [self._detail_error(path, "详情读取失败: %s" % exc)]}

    def playerContent(self, flag, id, vipFlags):
        started = time.time()
        value = str(id or "").strip()
        if value.startswith(self.ERROR_PREFIX):
            return self._player_error(unquote(value[len(self.ERROR_PREFIX) :]))
        if value.startswith("magnet:"):
            return self._push_result(value)
        if value.startswith(("http://", "https://")):
            try:
                result = self._resolve_web_url(value, self._active_host + "/", 0, set())
            except Exception as exc:
                result = self._player_error("播放解析失败: %s" % exc)
            return self._finish_player_result(flag, result, started)
        play_path = self._unpack_play_path(value)
        if not play_path:
            return self._player_error("无法识别播放 ID")
        try:
            source, page_url = self._request_business(
                play_path, markers=("player_aaaa", "bofang_box"), fresh=True
            )
            payload = self._extract_player_payload(source)
            result = self._resolve_player_payload(payload, page_url, 0, set())
        except Exception as exc:
            result = self._player_error("播放解析失败: %s" % exc)
        return self._finish_player_result(flag, result, started)

    def _reset_session(self):
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
        session = requests.Session()
        session.trust_env = self.trust_env
        session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
            }
        )
        self._session = session

    def _request_business(self, path, markers=(), fresh=False):
        business_path = self._business_path(path)
        errors = []
        hosts = [self._active_host] + [
            item for item in self._hosts if item != self._active_host
        ]
        for origin in hosts:
            url = urljoin(origin + "/", business_path.lstrip("/"))
            cache_key = origin + business_path
            if not fresh and self.cache_ttl > 0:
                cached = self._cache.get(cache_key)
                if cached and time.time() - cached[0] <= self.cache_ttl:
                    self._active_host = origin
                    return cached[1], cached[2]
            try:
                source, final_url = self._fetch_business(url, origin, markers)
                self._active_host = origin
                if not fresh and self.cache_ttl > 0:
                    self._cache[cache_key] = (time.time(), source, final_url)
                return source, final_url
            except Exception as exc:
                errors.append("%s: %s" % (urlsplit(origin).hostname, exc))
        raise RuntimeError("; ".join(errors) or "所有业务域名均失败")

    def _fetch_business(self, url, expected_origin, markers):
        response = self._session.get(
            url,
            timeout=(min(self.timeout, 10), self.timeout),
            allow_redirects=True,
            verify=self.verify_tls,
        )
        final_url = str(getattr(response, "url", "") or url)
        if self._safe_origin(final_url) != expected_origin:
            raise RuntimeError("已阻止外域跳转")
        source = self._response_text(response)
        status = int(getattr(response, "status_code", 0) or 0)
        if self._looks_like_challenge(status, source):
            raise RuntimeError("站点返回了浏览器验证页")
        if status == 520:
            raise RuntimeError("Cloudflare 520 源站错误")
        response.raise_for_status()
        if markers and not any(marker in source for marker in markers):
            raise RuntimeError("页面缺少业务标记")
        return source, final_url

    def _parse_list_page(self, source, page, page_url, kind):
        tree = self._tree(source)
        if kind == "search":
            anchors = tree.xpath(
                '//a[contains(concat(" ",normalize-space(@class)," ")," search_result_list_item ")]'
            )
        else:
            anchors = tree.xpath(
                '//a[contains(concat(" ",normalize-space(@class)," ")," video-item ")]'
            )
        videos = []
        seen = set()
        for anchor in anchors:
            path = self._normalize_detail_id(anchor.get("href"))
            if not path or path in seen:
                continue
            seen.add(path)
            image = str(
                anchor.xpath("string(.//img[1]/@data-src)")
                or anchor.xpath("string(.//img[1]/@src)")
                or ""
            ).strip()
            title = self._clean_text(
                anchor.xpath(
                    'string(.//*[contains(concat(" ",normalize-space(@class)," ")," search_result_list_item_content_title ")][1])'
                )
            )
            if not title:
                title = self._clean_text(anchor.xpath("string(.//img[1]/@alt)"))
            if not title:
                title = self._clean_text(anchor.text_content())
            remark = self._clean_text(
                anchor.xpath(
                    'string(.//*[contains(concat(" ",normalize-space(@class)," ")," search_result_list_item_content_tag ")][1])'
                )
            )
            videos.append(
                {
                    "vod_id": path,
                    "vod_name": title or path,
                    "vod_pic": urljoin(page_url, image) if image else self.DEFAULT_PIC,
                    "vod_remarks": remark,
                }
            )
        pagecount = self._pagecount(source, page)
        limit = len(videos) or 24
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": pagecount * limit,
        }

    def _parse_detail_page(self, source, path, page_url):
        tree = self._tree(source)
        name = self._clean_text(
            tree.xpath(
                'string(//*[contains(concat(" ",normalize-space(@class)," ")," detail-card ")]//h1[1])'
            )
        ) or self._clean_text(tree.xpath("string(//h1[1])")) or path
        pic = str(
            tree.xpath(
                'string(//*[contains(concat(" ",normalize-space(@class)," ")," detail-card ")]//img[contains(concat(" ",normalize-space(@class)," ")," el-image__inner ")][1]/@src)'
            )
            or ""
        ).strip()
        metadata = {}
        rows = tree.xpath(
            '//*[contains(concat(" ",normalize-space(@class)," ")," video_appraise_row ")]'
        )
        for row in rows:
            label = self._clean_text(
                row.xpath(
                    'string(.//*[contains(concat(" ",normalize-space(@class)," ")," video_appraise_title ")][1])'
                )
            ).rstrip(":：")
            value = self._clean_text(row.text_content())
            if label and value.startswith(label):
                value = value[len(label) :].lstrip(":： ")
            if label:
                metadata[label] = value
        classes = self._unique_text(
            tree.xpath(
                '//*[contains(concat(" ",normalize-space(@class)," ")," detail-card ")]//*[contains(concat(" ",normalize-space(@class)," ")," el-check-tag ")]/text()'
            )
        )
        source_names = {}
        tabs = tree.xpath(
            '//*[contains(concat(" ",normalize-space(@class)," ")," detail_line_ite ")][@data-source]'
        )
        for tab in tabs:
            source_id = str(tab.get("data-source") or "").strip()
            label = self._clean_text(tab.xpath("string(./div[1])"))
            if source_id:
                source_names[source_id] = label or ("线路" + source_id)
        play_from = []
        play_urls = []
        groups = tree.xpath(
            '//*[contains(concat(" ",normalize-space(@class)," ")," video_play_channel_list ")][@data-source]'
        )
        for group in groups:
            source_id = str(group.get("data-source") or "").strip()
            episodes = []
            for anchor in group.xpath(
                './/a[contains(concat(" ",normalize-space(@class)," ")," episode-item ")]'
            ):
                href = str(anchor.get("href") or "").strip()
                if not self._valid_play_path(href):
                    continue
                label = self._safe_play_label(
                    anchor.get("data-episode-name") or anchor.text_content()
                )
                if not label:
                    label = "播放"
                episodes.append(label + "$" + self._pack_play_path(href))
            if not episodes:
                continue
            play_from.append(source_names.get(source_id) or ("线路" + source_id))
            play_urls.append("#".join(episodes))
        if not play_urls:
            play_from = ["提示"]
            play_urls = [
                "暂无可用线路$"
                + self.ERROR_PREFIX
                + quote("详情页没有选集", safe="")
            ]
        else:
            play_from, play_urls = self._rank_play_groups(play_from, play_urls)
        return {
            "vod_id": path,
            "vod_name": name,
            "vod_pic": urljoin(page_url, pic) if pic else self.DEFAULT_PIC,
            "vod_remarks": metadata.get("备注", ""),
            "vod_year": metadata.get("年份", ""),
            "vod_area": metadata.get("地区", ""),
            "vod_actor": metadata.get("演员", ""),
            "vod_director": metadata.get("导演", ""),
            "vod_class": ",".join(classes),
            "vod_content": metadata.get("概述", ""),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_urls),
        }

    def _rank_play_groups(self, play_from, play_urls):
        rows = []
        for index, (label, episodes) in enumerate(zip(play_from, play_urls)):
            metrics = dict(self._line_scores.get(label, {}))
            learned = self._resolve_latency.get(label)
            if learned is not None and "latency_ms" not in metrics:
                metrics["latency_ms"] = learned
            quality = self._quality_score(metrics, label)
            speed = self._speed_score(metrics)
            combined = self._combined_score(metrics, quality, speed)
            rows.append(
                {
                    "index": index,
                    "line": label,
                    "episodes": episodes,
                    "quality_score": quality,
                    "speed_score": speed,
                    "score": combined,
                }
            )
        rows.sort(
            key=lambda item: (
                item["score"] is None,
                -(item["score"] if item["score"] is not None else 0.0),
                item["index"],
            )
        )
        self._last_line_ranking = [
            {
                "line": item["line"],
                "quality_score": item["quality_score"],
                "speed_score": item["speed_score"],
                "score": item["score"],
                "original_index": item["index"],
            }
            for item in rows
        ]
        return (
            [item["line"] for item in rows],
            [item["episodes"] for item in rows],
        )

    def _combined_score(self, metrics, quality, speed):
        explicit = self._score_value(metrics.get("score"))
        if quality is None and speed is None and explicit is not None:
            return explicit
        if quality is None and speed is None:
            return None
        if quality is None:
            return speed
        if speed is None:
            return quality
        return round(
            quality * self.quality_weight + speed * self.speed_weight, 2
        )

    def _quality_score(self, metrics, label=""):
        explicit = self._score_value(
            metrics.get("quality_score", metrics.get("clarity_score"))
        )
        if explicit is not None:
            return explicit
        height = self._positive_float(metrics.get("height"))
        bitrate = self._positive_float(
            metrics.get("bitrate_kbps", metrics.get("bandwidth_kbps"))
        )
        if not height:
            match = re.search(r"(?<!\d)(2160|1440|1080|720|576|480|360)[pP]?", label or "")
            if match:
                height = float(match.group(1))
            elif re.search(r"(?:4K|超清|蓝光)", label or "", re.I):
                height = 2160.0 if re.search(r"4K", label or "", re.I) else 1080.0
        height_score = self._height_score(height) if height else None
        bitrate_score = self._bitrate_score(bitrate) if bitrate else None
        if height_score is not None and bitrate_score is not None:
            return round(height_score * 0.75 + bitrate_score * 0.25, 2)
        return height_score if height_score is not None else bitrate_score

    def _speed_score(self, metrics):
        explicit = self._score_value(metrics.get("speed_score"))
        if explicit is not None:
            return explicit
        throughput = self._positive_float(metrics.get("throughput_mbps"))
        latency = self._positive_float(
            metrics.get("latency_ms", metrics.get("first_byte_ms"))
        )
        throughput_score = None
        if throughput:
            # 1/3/7/15/31 Mbps map to approximately 20/40/60/80/100.
            import math

            throughput_score = min(100.0, 20.0 * math.log(1.0 + throughput, 2.0))
        latency_score = self._latency_score(latency) if latency else None
        if throughput_score is not None and latency_score is not None:
            return round(throughput_score * 0.75 + latency_score * 0.25, 2)
        if throughput_score is not None:
            return round(throughput_score, 2)
        return latency_score

    def _height_score(self, height):
        points = (
            (360, 28), (480, 42), (576, 52), (720, 66),
            (1080, 82), (1440, 90), (2160, 100),
        )
        value = float(height)
        if value <= points[0][0]:
            return float(points[0][1])
        for (low_x, low_y), (high_x, high_y) in zip(points, points[1:]):
            if value <= high_x:
                ratio = (value - low_x) / float(high_x - low_x)
                return round(low_y + ratio * (high_y - low_y), 2)
        return 100.0

    def _bitrate_score(self, bitrate_kbps):
        import math

        value = max(1.0, float(bitrate_kbps))
        return round(max(0.0, min(100.0, 25.0 + 15.0 * math.log(value / 500.0, 2.0))), 2)

    def _latency_score(self, latency_ms):
        points = ((50, 100), (250, 90), (500, 75), (1000, 50), (2000, 25), (4000, 0))
        value = max(0.0, float(latency_ms))
        if value <= points[0][0]:
            return float(points[0][1])
        for (low_x, low_y), (high_x, high_y) in zip(points, points[1:]):
            if value <= high_x:
                ratio = (value - low_x) / float(high_x - low_x)
                return round(low_y + ratio * (high_y - low_y), 2)
        return 0.0

    def _finish_player_result(self, flag, result, started):
        if self.learn_resolve_latency:
            label = self._clean_text(flag)
            if label and result.get("url"):
                elapsed = max(0.0, (time.time() - started) * 1000.0)
                previous = self._resolve_latency.get(label)
                self._resolve_latency[label] = round(
                    elapsed if previous is None else previous * 0.7 + elapsed * 0.3,
                    2,
                )
        return result

    def _extract_player_payload(self, source):
        match = re.search(r"\bvar\s+player_aaaa\s*=", source or "", re.I)
        if match:
            raw = self._balanced_object(source, match.end())
            if raw:
                try:
                    payload = json.loads(raw)
                    if isinstance(payload, dict):
                        return payload
                except Exception as exc:
                    raise RuntimeError("player_aaaa JSON 无效: %s" % exc)
        iframe = re.search(
            r'<iframe\b[^>]*\bsrc=["\']([^"\']+)["\']', source or "", re.I
        )
        if iframe:
            return {"url": html_lib.unescape(iframe.group(1)), "from": "iframe", "encrypt": 0}
        raise RuntimeError("未找到 player_aaaa 或 iframe")

    def _resolve_player_payload(self, payload, page_url, depth, visited):
        value = self._decode_player_url(payload)
        if not value:
            raise RuntimeError("播放数据缺少 URL")
        if value.startswith("magnet:"):
            return self._push_result(value)
        source_key = self._clean_text(payload.get("from")).lower()
        value = self._apply_parse_config(source_key, value, page_url)
        target = urljoin(page_url, value)
        if not self._is_public_http_url(target):
            raise RuntimeError("播放地址不安全")
        if source_key == "swf" and target.lower().split("?", 1)[0].endswith(".swf"):
            return self._player_error("Flash/SWF 线路已识别，当前客户端不支持")
        if self._is_direct_media_url(target) or source_key in self.DIRECT_LOADERS:
            return self._player_result(target, page_url)
        return self._resolve_web_url(target, page_url, depth, visited)

    def _resolve_web_url(self, url, referer, depth, visited):
        target = str(url or "").strip()
        if not self._is_public_http_url(target):
            raise RuntimeError("解析地址不安全")
        if self._is_direct_media_url(target):
            return self._player_result(target, referer)
        if depth >= self.resolve_depth:
            return self._parser_fallback(target, referer, "达到最大解析深度")
        key = target.split("#", 1)[0]
        if key in visited:
            raise RuntimeError("解析页出现循环引用")
        visited = set(visited)
        visited.add(key)
        source, final_url, content_type = self._fetch_resolver_page(target, referer)
        if self._is_media_content_type(content_type) or self._is_direct_media_url(final_url):
            return self._player_result(final_url, referer)
        nested = None
        try:
            nested = self._extract_player_payload(source)
        except Exception:
            pass
        if nested:
            return self._resolve_player_payload(nested, final_url, depth + 1, visited)
        direct_candidates, page_candidates = self._extract_page_candidates(source, final_url)
        for candidate in direct_candidates:
            if self._is_public_http_url(candidate):
                return self._player_result(candidate, final_url)
        errors = []
        for candidate in page_candidates:
            if candidate.split("#", 1)[0] in visited:
                continue
            try:
                return self._resolve_web_url(candidate, final_url, depth + 1, visited)
            except Exception as exc:
                errors.append(str(exc))
        lowered = source.lower()
        if any(marker in lowered for marker in self.PLAYER_PAGE_MARKERS):
            return self._parser_fallback(final_url, referer, "静态源码未暴露直链")
        if errors:
            raise RuntimeError("; ".join(errors[:3]))
        raise RuntimeError("解析页未暴露媒体或子页")

    def _fetch_resolver_page(self, url, referer):
        headers = {
            "Accept": "text/html,application/json,text/plain,*/*;q=0.8",
        }
        if referer:
            headers["Referer"] = referer
        response = self._session.get(
            url,
            headers=headers,
            timeout=(min(self.timeout, 10), self.timeout),
            allow_redirects=True,
            verify=self.verify_tls,
        )
        final_url = str(getattr(response, "url", "") or url)
        if not self._is_public_http_url(final_url):
            raise RuntimeError("解析页跳转到不安全地址")
        content_type = str(
            getattr(response, "headers", {}).get("Content-Type", "") or ""
        ).lower()
        if self._safe_origin(final_url) != self._safe_origin(url):
            if not (
                self._is_direct_media_url(final_url)
                or self._is_media_content_type(content_type)
            ):
                raise RuntimeError("已阻止解析页跳转到其他页面域名")
        source = self._response_text(response)
        status = int(getattr(response, "status_code", 0) or 0)
        if self._looks_like_challenge(status, source):
            raise RuntimeError("解析页返回了浏览器验证")
        response.raise_for_status()
        if len(source.encode("utf-8", errors="ignore")) > self.max_page_bytes:
            raise RuntimeError("解析页超过大小限制")
        return source, final_url, content_type

    def _extract_page_candidates(self, source, page_url):
        direct = []
        pages = []
        normalized = html_lib.unescape(str(source or "")).replace("\\/", "/")
        tree = self._tree(normalized)
        for value in tree.xpath("//video/@src | //video/source/@src | //source/@src"):
            candidate = urljoin(page_url, str(value or "").strip())
            if self._is_direct_media_url(candidate):
                direct.append(candidate)
        for value in tree.xpath("//iframe/@src"):
            candidate = urljoin(page_url, str(value or "").strip())
            if self._is_direct_media_url(candidate):
                direct.append(candidate)
            elif self._is_public_http_url(candidate):
                pages.append(candidate)
        patterns = (
            r"\b(?:videoUrl|playUrl|play_url|file)\s*[:=]\s*[\"']([^\"']+)[\"']",
            r"[\"'](?:url|src)[\"']\s*:\s*[\"']([^\"']+)[\"']",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, normalized, re.I):
                value = self._decode_js_string(match.group(1))
                candidate = urljoin(page_url, value)
                if self._is_direct_media_url(candidate):
                    direct.append(candidate)
                elif self._is_public_http_url(candidate) and not self._is_static_asset(candidate):
                    pages.append(candidate)
        stripped = normalized.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                payload = json.loads(stripped)
                for value in self._json_urls(payload):
                    candidate = urljoin(page_url, value)
                    if self._is_direct_media_url(candidate):
                        direct.append(candidate)
                    elif self._is_public_http_url(candidate):
                        pages.append(candidate)
            except Exception:
                pass
        return self._unique_text(direct), self._unique_text(pages)

    def _decode_player_url(self, payload):
        value = str(payload.get("url") or "").strip()
        try:
            encrypt = int(payload.get("encrypt") or 0)
        except Exception:
            encrypt = 0
        if encrypt == 1:
            return unquote(value)
        if encrypt == 2:
            try:
                padding = "=" * ((4 - len(value) % 4) % 4)
                decoded = base64.b64decode((value + padding).encode("ascii"))
                return unquote(decoded.decode("utf-8"))
            except Exception as exc:
                raise RuntimeError("Base64 播放地址解码失败: %s" % exc)
        return value

    def _apply_parse_config(self, source_key, value, page_url):
        config, players = self._load_player_config()
        player = players.get(source_key, {}) if isinstance(players, dict) else {}
        if str(player.get("ps") or "0") != "1":
            return value
        prefix = str(player.get("parse") or config.get("parse") or "").strip()
        if not prefix:
            return value
        prefix = urljoin(page_url, prefix)
        if "{url}" in prefix:
            return prefix.replace("{url}", quote(value, safe=""))
        return prefix + value

    def _load_player_config(self):
        if self._player_config is not None:
            return self._player_config
        config = {}
        players = {}
        try:
            source, _ = self._request_business(
                "/static/js/playerconfig.js", markers=("MacPlayerConfig",)
            )
            for match in re.finditer(r"MacPlayerConfig\s*=", source):
                raw = self._balanced_object(source, match.end())
                if not raw:
                    continue
                try:
                    value = json.loads(raw)
                    if isinstance(value, dict) and value:
                        config.update(value)
                except Exception:
                    pass
            match = re.search(r"MacPlayerConfig\.player_list\s*=", source)
            if match:
                raw = self._balanced_object(source, match.end())
                value = json.loads(raw) if raw else {}
                if isinstance(value, dict):
                    players = value
        except Exception:
            pass
        self._player_config = (config, players)
        return self._player_config

    def _balanced_object(self, source, start):
        index = str(source or "").find("{", int(start or 0))
        if index < 0:
            return ""
        depth = 0
        quote_char = ""
        escaped = False
        for position in range(index, len(source)):
            char = source[position]
            if quote_char:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote_char:
                    quote_char = ""
                continue
            if char in ("\"", "'"):
                quote_char = char
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return source[index : position + 1]
        return ""

    def _pack_play_path(self, path):
        token = base64.urlsafe_b64encode(path.encode("utf-8")).decode("ascii")
        return self.PLAY_PREFIX + token.rstrip("=")

    def _unpack_play_path(self, value):
        if not value.startswith(self.PLAY_PREFIX):
            return ""
        token = value[len(self.PLAY_PREFIX) :]
        try:
            token += "=" * ((4 - len(token) % 4) % 4)
            path = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        except Exception:
            return ""
        return path if self._valid_play_path(path) else ""

    def _valid_play_path(self, value):
        parsed = urlsplit(str(value or "").strip())
        return bool(not parsed.scheme and not parsed.netloc and self.PLAY_PATH_RE.match(parsed.path))

    def _normalize_detail_id(self, value):
        text = str(value or "").strip()
        if text.startswith("atvp_detail:"):
            text = text[len("atvp_detail:") :]
        if text.isdigit():
            text = "/O/%s.html" % text
        parsed = urlsplit(text)
        if parsed.scheme or parsed.netloc:
            if self._safe_origin(text) not in self._hosts:
                return ""
            text = parsed.path
        return text if self.DETAIL_PATH_RE.match(text) else ""

    def _business_path(self, value):
        text = str(value or "").strip()
        parsed = urlsplit(text)
        if parsed.scheme or parsed.netloc:
            if self._safe_origin(text) not in self._hosts:
                raise RuntimeError("已阻止非业务域名")
            text = parsed.path + (("?" + parsed.query) if parsed.query else "")
        if not text.startswith("/"):
            text = "/" + text
        return text

    def _filter_path(self, category, area, sort_value, class_value, language, page):
        route = "%s-%s-%s-%s-%s-%s---%d---%s" % (
            category,
            quote(area, safe=""),
            quote(sort_value, safe=""),
            quote(class_value, safe=""),
            quote(language, safe=""),
            "",
            page,
            "",
        )
        return "/vodshow/%s.html" % route

    def _pagecount(self, source, page):
        counts = [int(value) for value in re.findall(r">\s*\d+\s*/\s*(\d+)\s*<", source or "")]
        counts += [int(value) for value in re.findall(r'title=["\']第(\d+)页["\']', source or "")]
        counts += [int(value) for value in re.findall(r"-{3,}(\d+)-{3}\.html", source or "")]
        counts += [int(value) for value in re.findall(r"/F/[^\"']+-(\d+)\.html", source or "")]
        return max(counts + [page])

    def _response_text(self, response):
        body = bytes(getattr(response, "content", b"") or b"")
        return body.decode("utf-8", errors="replace")

    def _tree(self, source):
        return html.fromstring(source or "<html></html>")

    def _looks_like_challenge(self, status, source):
        lowered = str(source or "").lower()
        return status in (403, 429, 503) and any(
            marker in lowered for marker in self.CHALLENGE_MARKERS
        )

    def _is_direct_media_url(self, value):
        text = str(value or "").strip()
        return bool(self._is_public_http_url(text) and self.DIRECT_MEDIA_RE.search(text))

    def _is_media_content_type(self, value):
        lowered = str(value or "").lower()
        return any(marker in lowered for marker in self.MEDIA_CONTENT_TYPES)

    def _is_public_http_url(self, value):
        parsed = urlsplit(str(value or "").strip())
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        if parsed.username or parsed.password:
            return False
        host = parsed.hostname.lower()
        if host in ("localhost", "localhost.localdomain") or host.endswith(".local"):
            return False
        try:
            address = ipaddress.ip_address(host)
            if not address.is_global:
                return False
        except ValueError:
            pass
        return True

    def _safe_origin(self, value):
        parsed = urlsplit(str(value or "").strip())
        if parsed.scheme != "https" or not parsed.hostname:
            return ""
        if parsed.username or parsed.password:
            return ""
        host = parsed.hostname.lower()
        if host == "localhost" or host.endswith(".local"):
            return ""
        try:
            address = ipaddress.ip_address(host)
            if not address.is_global:
                return ""
        except ValueError:
            pass
        port = ":%d" % parsed.port if parsed.port and parsed.port != 443 else ""
        return "https://" + host + port

    def _is_static_asset(self, value):
        path = urlsplit(str(value or "")).path.lower()
        return bool(re.search(r"\.(?:js|css|jpg|jpeg|png|gif|svg|webp|ico|woff2?)(?:$|[?#])", path))

    def _player_headers(self, referer):
        headers = {"User-Agent": self.user_agent}
        if referer:
            headers["Referer"] = referer
        return headers

    def _player_result(self, url, referer):
        return {
            "parse": 0,
            "jx": 0,
            "playUrl": "",
            "url": url,
            "header": self._player_headers(referer),
        }

    def _parser_fallback(self, url, referer, reason):
        return {
            "parse": 1,
            "jx": 1,
            "playUrl": "",
            "url": url,
            "header": self._player_headers(referer),
            "msg": "解析页兜底: %s" % reason,
        }

    def _push_result(self, value):
        return {
            "parse": 0,
            "jx": 0,
            "playUrl": "",
            "url": "push://" + value,
            "header": {},
        }

    def _player_error(self, message):
        text = self._clean_text(message) or "未知播放错误"
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

    def _detail_error(self, vod_id, message):
        text = self._clean_text(message)
        return {
            "vod_id": vod_id or "freeokok-error",
            "vod_name": "FreeOKOK解析提示",
            "vod_pic": self.DEFAULT_PIC,
            "vod_remarks": text,
            "vod_content": text,
            "vod_play_from": "提示",
            "vod_play_url": "查看提示$" + self.ERROR_PREFIX + quote(text, safe=""),
        }

    def _empty_page(self, page, message=""):
        result = {
            "list": [],
            "page": page,
            "pagecount": page,
            "limit": 24,
            "total": 0,
        }
        if message:
            result["msg"] = message
        return result

    def _filter_row(self, key, name, values):
        return {
            "key": key,
            "name": name,
            "value": [{"n": label, "v": value} for label, value in values],
        }

    def _parse_dict(self, value):
        if isinstance(value, dict):
            return dict(value)
        text = str(value or "").strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _parse_line_scores(self, value):
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return {}
            try:
                value = json.loads(text)
            except Exception:
                return {}
        if isinstance(value, dict) and isinstance(value.get("lines"), list):
            value = value.get("lines")
        result = {}
        if isinstance(value, dict):
            items = value.items()
        elif isinstance(value, list):
            items = []
            for row in value:
                if not isinstance(row, dict):
                    continue
                label = self._clean_text(row.get("line", row.get("name")))
                if label:
                    items.append((label, row))
        else:
            return {}
        for label, metrics in items:
            name = self._clean_text(label)
            if not name:
                continue
            if isinstance(metrics, dict):
                result[name] = dict(metrics)
            else:
                score = self._score_value(metrics)
                if score is not None:
                    result[name] = {"score": score}
        return result

    def _normalize_weights(self, quality, speed):
        quality_value = self._nonnegative_float(quality)
        speed_value = self._nonnegative_float(speed)
        if quality_value is None or speed_value is None:
            return 0.6, 0.4
        total = quality_value + speed_value
        if total <= 0:
            return 0.6, 0.4
        return quality_value / total, speed_value / total

    def _score_value(self, value):
        number = self._nonnegative_float(value)
        if number is None:
            return None
        return round(max(0.0, min(100.0, number)), 2)

    def _positive_float(self, value):
        number = self._nonnegative_float(value)
        return number if number is not None and number > 0 else None

    def _nonnegative_float(self, value):
        try:
            number = float(value)
            if number < 0 or number != number or number in (float("inf"), float("-inf")):
                return None
            return number
        except Exception:
            return None

    def _parse_hosts(self, value):
        if isinstance(value, (list, tuple)):
            raw = value
        else:
            raw = re.split(r"[,\s]+", str(value or ""))
        result = []
        for item in raw:
            origin = self._safe_origin(item)
            if origin:
                result.append(origin)
        return result

    def _allowed_filter(self, value, allowed):
        text = self._clean_text(value)
        return text if text in set(allowed or ()) else ""

    def _page_number(self, value):
        try:
            return max(1, int(str(value or "1")))
        except Exception:
            return 1

    def _bounded_int(self, value, default, minimum, maximum):
        try:
            return max(minimum, min(maximum, int(value)))
        except Exception:
            return default

    def _bool_value(self, value, default):
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        text = str(value).strip().lower()
        if text in ("1", "true", "yes", "on"):
            return True
        if text in ("0", "false", "no", "off"):
            return False
        return default

    def _decode_js_string(self, value):
        text = str(value or "").replace("\\/", "/")
        try:
            return json.loads('"' + text.replace('"', '\\"') + '"')
        except Exception:
            return text.replace("\\u0026", "&")

    def _json_urls(self, value):
        result = []
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).lower() in ("url", "src", "file", "playurl", "play_url"):
                    if isinstance(item, str):
                        result.append(item)
                result.extend(self._json_urls(item))
        elif isinstance(value, list):
            for item in value:
                result.extend(self._json_urls(item))
        return result

    def _safe_play_label(self, value):
        return self._clean_text(value).replace("#", " ").replace("$", " ")

    def _clean_text(self, value):
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def _unique_text(self, values):
        result = []
        seen = set()
        for value in values:
            text = str(value or "").strip()
            if text and text not in seen:
                seen.add(text)
                result.append(text)
        return result
