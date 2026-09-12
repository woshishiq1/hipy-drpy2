#!/usr/bin/python
# -*- coding: utf-8 -*-
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from threading import Event, RLock, Thread
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

import requests
from lxml import etree
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def getName(self):
        return "SOTVLA"

    def init(self, extend=""):
        self.host = "https://www.sotvla6.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Referer": self.host + "/index.php",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.play_headers = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": self.host + "/",
        }
        self.classes = [
            {"type_id": "teleplay", "type_name": "电视剧热搜"},
            {"type_id": "movie", "type_name": "电影热搜"},
            {"type_id": "variety", "type_name": "综艺热播"},
        ]
        source_values = [{"n": "猫眼榜", "v": "maoyan"}, {"n": "百度榜", "v": "baidu"}]
        self.filters = {
            item["type_id"]: [{"key": "source", "name": "榜单", "init": "maoyan", "value": source_values}]
            for item in self.classes
        }
        self.session = requests.Session()
        self.hot_cache = {}
        self.detail_cache = {}
        self.related_cache = {}
        self.bundle_cache = {}
        self.prefetching = set()
        self.prefetch_lock = RLock()
        self.prefetch_events = {}

    def _get(self, url, params=None, json_data=False, isolated=False):
        url = self._fix(url)
        for _ in range(1 if isolated else 2):
            try:
                getter = requests.get if isolated else self.session.get
                response = getter(url, params=params, headers=self.headers, timeout=10 if isolated else 30)
                response.raise_for_status()
                if json_data:
                    data = response.json()
                    return data if isinstance(data, dict) else {}
                response.encoding = "utf-8"
                return response.text
            except (requests.RequestException, ValueError):
                continue
        return {} if json_data else ""

    def _fix(self, url):
        return urljoin(self.host + "/", str(url or ""))

    def _clean(self, value):
        return " ".join(str(value or "").split())

    def _tree(self, source):
        try:
            return etree.HTML(source) if source else None
        except (TypeError, ValueError):
            return None

    def _hot_items(self, tab, source="maoyan"):
        source = source if source in ("maoyan", "baidu") else "maoyan"
        key = source + ":" + tab
        cached = self.hot_cache.get(key)
        if cached and time.time() - cached[0] < 300:
            return cached[1]
        data = self._get("/api/hot_movie.php", {"source": source, "tab": tab}, True)
        label = {"teleplay": "电视剧热搜", "movie": "电影热搜", "variety": "综艺热播"}.get(tab, "热播")
        items = [{
            "vod_id": "hot|" + quote(str(item.get("title", "")), safe=""),
            "vod_name": str(item.get("title", "")),
            "vod_pic": str(item.get("pic", "")),
            "vod_remarks": label,
        } for item in data.get("items", []) if item.get("title")]
        self.hot_cache[key] = (time.time(), items)
        return items

    def homeContent(self, filter):
        items = []
        for tab in ("teleplay", "movie", "variety"):
            items.extend(self._hot_items(tab))
        return {"class": self.classes, "list": items, "filters": self.filters}

    def homeVideoContent(self):
        return {"list": self.homeContent(False)["list"]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = max(1, int(pg)) if str(pg).isdigit() else 1
        extend = extend if isinstance(extend, dict) else {}
        source = str(extend.get("source") or "maoyan")
        items = self._hot_items(str(tid), source) if pg == 1 else []
        return {"page": pg, "pagecount": 1, "limit": len(items), "total": len(items), "list": items}

    def _search_rows(self, source, pg=1):
        tree = self._tree(source)
        if tree is None:
            return [], 1, 0
        rows, seen = [], set()
        for node in tree.xpath('//article[contains(@class,"search-result-item")]'):
            title_nodes = node.xpath('.//a[contains(@class,"sr-title")]')
            if not title_nodes:
                continue
            link = title_nodes[0].get("href", "")
            name = self._clean("".join(title_nodes[0].itertext()))
            if not link or not name or link in seen:
                continue
            seen.add(link)
            images = node.xpath('.//img[contains(@class,"sotv-poster-img")]/@src')
            source_name = self._clean("".join(node.xpath('.//*[contains(@class,"sr-source-line")]//*[contains(@class,"sr-value")]//text()')))
            type_name, year, area = "", "", ""
            for cell in node.xpath('.//*[contains(@class,"sr-meta-cell")]'):
                text = self._clean("".join(cell.itertext()))
                if text.startswith("类型："):
                    type_name = text.split("：", 1)[1]
                elif text.startswith("上映时间："):
                    year = text.split("：", 1)[1]
                elif text.startswith("地区："):
                    area = text.split("：", 1)[1]
            rows.append({
                "vod_id": link,
                "vod_name": name,
                "vod_pic": images[0] if images else "",
                "source_name": source_name,
                "type_name": type_name,
                "year": year,
                "area": area,
            })
        total_text = "".join(tree.xpath('//*[@id="search-result-total"]//text()'))
        total_match = re.search(r"\d+", total_text.replace(",", ""))
        total = int(total_match.group()) if total_match else len(rows)
        pages = [int(value) for value in re.findall(r"[?&]page=(\d+)", source)]
        pagecount = max([int(pg)] + pages + [max(1, (total + 15) // 16)])
        return rows, pagecount, total

    def _search_items(self, source, pg=1):
        rows, pagecount, total = self._search_rows(source, pg)
        return self._rows_to_items(rows), pagecount, total

    def _rows_to_items(self, rows):
        items = [{
            "vod_id": row["vod_id"],
            "vod_name": row["vod_name"],
            "vod_pic": row["vod_pic"],
            "vod_remarks": " · ".join(
                value for value in (row["source_name"], row["year"], row["area"])
                if value and value != "—"
            ),
        } for row in rows]
        return items

    def searchContent(self, key, quick, pg="1"):
        pg = max(1, int(pg)) if str(pg).isdigit() else 1
        source = self._get("/search.php", {"q": str(key), "page": pg})
        rows, pagecount, total = self._search_rows(source, pg)
        items = self._rows_to_items(rows)
        self._schedule_prefetch(rows)
        return {"page": pg, "pagecount": pagecount, "limit": 16, "total": total, "list": items}

    def _resolve_hot(self, vod_id):
        title = unquote(vod_id.split("|", 1)[1])
        source = self._get("/search.php", {"q": title, "page": 1})
        rows, _, _ = self._search_rows(source, 1)
        self._schedule_prefetch(rows)
        items = self._rows_to_items(rows)
        if not items:
            return "", title
        key = re.sub(r"\s+", "", title).lower()

        def score(item):
            item_key = re.sub(r"\s+", "", item["vod_name"]).lower()
            return (0 if item_key == key else 1, self._source_rank(item["vod_id"]), len(item_key))

        selected = min(items, key=score)
        return selected["vod_id"], selected["vod_name"]

    def _source_rank(self, vod_id):
        match = re.search(r"api_id=(\d+)", str(vod_id))
        api_id = int(match.group(1)) if match else 999
        priorities = {6: 0, 2: 1, 3: 2, 15: 3, 20: 4, 12: 5, 11: 6, 7: 7, 9: 8, 1: 20}
        return priorities.get(api_id, 10), api_id

    def _schedule_prefetch(self, rows):
        groups = {}
        for row in rows:
            key = (self._title_key(row["vod_name"]), self._year_key(row["year"]) or row["year"])
            groups.setdefault(key, []).append(row)
        candidates = []
        with self.prefetch_lock:
            for group in groups.values():
                if len(group) < 2:
                    continue
                for row in sorted(group, key=lambda item: self._source_rank(item["vod_id"])):
                    url = self._fix(row["vod_id"])
                    if url in self.detail_cache or url in self.prefetching or url in candidates:
                        continue
                    candidates.append(url)
            urls = candidates[:24]
            for url in urls:
                self.prefetching.add(url)
                self.prefetch_events[url] = Event()
        if not urls:
            return
        for url in urls:
            event = self.prefetch_events[url]

            def run(item=url, done=event):
                try:
                    self._detail_data_parallel(item)
                finally:
                    done.set()
                    with self.prefetch_lock:
                        self.prefetching.discard(item)
                        self.prefetch_events.pop(item, None)

            Thread(target=run, daemon=True).start()

    def _title_key(self, value):
        return re.sub(r"[\s·:：,，。.!！?？()（）\[\]【】_-]+", "", str(value or "")).lower()

    def _year_key(self, value):
        match = re.search(r"(?:19|20)\d{2}", str(value or ""))
        return match.group() if match else ""

    def _people(self, value):
        people = set()
        for item in re.split(r"[,，、/|]", str(value or "")):
            item = item.split("：", 1)[-1].split(":", 1)[-1]
            item = re.sub(r"[（(].*?[）)]", "", item)
            item = re.sub(r"\s+", "", item)
            if len(item) >= 2 and item not in ("未知", "暂无", "—"):
                people.add(item)
        return people

    def _meta(self, tree, label):
        nodes = tree.xpath('//div[contains(@class,"meta-list")]//strong[normalize-space(text())=$label]', label=label)
        return self._clean(nodes[0].tail) if nodes else ""

    def _detail_data(self, vod_id, isolated=False):
        url = self._fix(vod_id)
        cached = self.detail_cache.get(url)
        if cached and time.time() - cached[0] < 300:
            return cached[1]
        if not isolated:
            event = self.prefetch_events.get(url)
            if event:
                event.wait(timeout=12)
                cached = self.detail_cache.get(url)
                if cached and time.time() - cached[0] < 300:
                    return cached[1]
        source = self._get(url, isolated=isolated)
        tree = self._tree(source)
        if tree is None:
            return None
        name = self._clean("".join(tree.xpath('//div[contains(@class,"detail-info")]//h1//text()')))
        images = tree.xpath('//div[contains(@class,"detail-poster")]//img/@src')
        tabs = {
            str(node.get("data-src", "")): self._clean("".join(node.itertext()))
            for node in tree.xpath('//button[contains(@class,"play-source-tab")]')
        }
        lines = []
        for index, panel in enumerate(tree.xpath('//div[contains(@class,"play-ep-panel")]')):
            source_id = str(panel.get("data-src-panel", index))
            episodes, seen = [], set()
            for episode in panel.xpath('.//a[contains(@class,"play-ep-pill")]'):
                href = episode.get("href", "")
                if not href or href in seen:
                    continue
                seen.add(href)
                title = "".join(episode.itertext()).strip() or str(len(episodes) + 1)
                title = title.replace("$", "＄").replace("#", "＃")
                episodes.append(f"{title}${self._compact_play_id(self._fix(href))}")
            if episodes:
                lines.append((tabs.get(source_id) or f"线路{len(lines) + 1}", "#".join(episodes)))
        if not lines:
            play_links = tree.xpath('//*[@id="detail-btn-play"]/@href')
            if play_links:
                lines.append(("默认线路", "播放$" + self._compact_play_id(self._fix(play_links[0]))))
        data = {
            "vod_id": url,
            "vod_name": name,
            "vod_pic": images[0] if images else "",
            "type_name": self._meta(tree, "分类"),
            "vod_year": self._meta(tree, "年代"),
            "vod_area": self._meta(tree, "地区"),
            "vod_remarks": self._meta(tree, "集数"),
            "vod_actor": self._meta(tree, "演员"),
            "vod_director": self._meta(tree, "导演"),
            "vod_content": self._clean("".join(tree.xpath('//p[contains(@class,"blurb")]//text()'))),
            "lines": lines,
        }
        self.detail_cache[url] = (time.time(), data)
        return data

    def _detail_data_parallel(self, vod_id):
        return self._detail_data(vod_id, isolated=True)

    def _detail_data_candidate(self, vod_id):
        event = self.prefetch_events.get(self._fix(vod_id))
        if event:
            event.wait(timeout=12)
            cached = self.detail_cache.get(self._fix(vod_id))
            if cached and time.time() - cached[0] < 300:
                return cached[1]
        return self._detail_data_parallel(vod_id)

    def _same_work(self, base, candidate):
        if not candidate or self._title_key(base["vod_name"]) != self._title_key(candidate["vod_name"]):
            return False
        if base["vod_id"] == candidate["vod_id"]:
            return True
        base_year, candidate_year = self._year_key(base["vod_year"]), self._year_key(candidate["vod_year"])
        if base_year and candidate_year:
            return base_year == candidate_year
        base_people, candidate_people = self._people(base["vod_actor"]), self._people(candidate["vod_actor"])
        if len(base_people & candidate_people) >= 2:
            return True
        base_content, candidate_content = base["vod_content"][:600], candidate["vod_content"][:600]
        return bool(
            len(base_content) >= 20
            and len(candidate_content) >= 20
            and SequenceMatcher(None, base_content, candidate_content).ratio() >= 0.38
        )

    def _related_rows(self, name):
        cache_key = self._title_key(name)
        cached = self.related_cache.get(cache_key)
        if cached and time.time() - cached[0] < 300:
            return cached[1]
        first_source = self._get("/search.php", {"q": name, "page": 1})
        rows, pagecount, _ = self._search_rows(first_source, 1)
        target = self._title_key(name)
        exact = [row for row in rows if self._title_key(row["vod_name"]) == target]
        positions = [index for index, row in enumerate(rows) if self._title_key(row["vod_name"]) == target]
        if positions and positions[-1] >= max(0, len(rows) - 4):
            for page in range(2, min(pagecount, 4) + 1):
                page_source = self._get("/search.php", {"q": name, "page": page})
                page_rows, _, _ = self._search_rows(page_source, page)
                page_exact = [row for row in page_rows if self._title_key(row["vod_name"]) == target]
                if not page_exact:
                    break
                exact.extend(page_exact)
        unique = {}
        for row in exact:
            unique[self._fix(row["vod_id"])] = row
        rows = sorted(unique.values(), key=lambda row: self._source_rank(row["vod_id"]))[:32]
        self.related_cache[cache_key] = (time.time(), rows)
        return rows

    def detailContent(self, ids):
        result = []
        for original_id in ids:
            original_id = str(original_id)
            vod_id, fallback_name = (self._resolve_hot(original_id) if original_id.startswith("hot|") else (original_id, ""))
            base = self._detail_data(vod_id)
            if not base:
                continue
            rows = self._related_rows(base["vod_name"])
            base_year = self._year_key(base["vod_year"])
            if base_year:
                rows = [row for row in rows if not self._year_key(row["year"]) or self._year_key(row["year"]) == base_year]
            urls = [row["vod_id"] for row in rows if self._fix(row["vod_id"]) != base["vod_id"]]
            work_signature = ",".join(sorted(self._people(base["vod_actor"]))) or re.sub(r"\s+", "", base["vod_content"][:120])
            bundle_key = (self._title_key(base["vod_name"]), base_year, work_signature)
            cached_bundle = self.bundle_cache.get(bundle_key)
            if cached_bundle and time.time() - cached_bundle[0] < 300:
                line_names, playlists = cached_bundle[1], cached_bundle[2]
            else:
                with ThreadPoolExecutor(max_workers=min(24, max(1, len(urls)))) as pool:
                    candidates = [base] + list(pool.map(self._detail_data_candidate, urls))
                candidates = sorted(
                    (item for item in candidates if self._same_work(base, item)),
                    key=lambda item: self._source_rank(item["vod_id"]),
                )
                line_names, playlists, line_counts, seen_playlists = [], [], {}, set()
                for item in candidates:
                    for line_name, playlist in item["lines"]:
                        if not playlist or playlist in seen_playlists:
                            continue
                        seen_playlists.add(playlist)
                        line_name = str(line_name or "线路").replace("$", "＄").replace("#", "＃")
                        line_counts[line_name] = line_counts.get(line_name, 0) + 1
                        shown_name = line_name if line_counts[line_name] == 1 else f"{line_name}{line_counts[line_name]}"
                        line_names.append(shown_name)
                        playlists.append(playlist)
                self.bundle_cache[bundle_key] = (time.time(), line_names, playlists)
            result.append({
                "vod_id": original_id,
                "vod_name": base["vod_name"] or fallback_name,
                "vod_pic": base["vod_pic"],
                "type_name": base["type_name"],
                "vod_year": base["vod_year"],
                "vod_area": base["vod_area"],
                "vod_remarks": base["vod_remarks"],
                "vod_actor": base["vod_actor"],
                "vod_director": base["vod_director"],
                "vod_content": base["vod_content"],
                "vod_play_from": "$$$".join(line_names),
                "vod_play_url": "$$$".join(playlists),
            })
        return {"list": result}

    def _target_url(self, embed_url):
        values = parse_qs(urlparse(str(embed_url or "")).query, keep_blank_values=True).get("url", [])
        return next((value for value in reversed(values) if value), "")

    def _compact_play_id(self, url):
        parsed = urlparse(str(url or ""))
        if parsed.path != "/play.php":
            return url
        query = parse_qs(parsed.query)
        api_id = (query.get("api_id") or [""])[0]
        vod_id = (query.get("vod_id") or [""])[0]
        src = (query.get("src") or [""])[0]
        ep = (query.get("ep") or [""])[0]
        if api_id and vod_id and src and ep:
            return f"sotv://{api_id}/{vod_id}/{src}/{ep}"
        return url

    def _expand_play_id(self, value):
        match = re.fullmatch(r"sotv://([^/]+)/([^/]+)/([^/]+)/([^/]+)", str(value or ""))
        if not match:
            return value
        api_id, vod_id, src, ep = match.groups()
        return f"/play.php?api_id={api_id}&vod_id={vod_id}&src={src}&ep={ep}"

    def playerContent(self, flag, id, vipFlags):
        page = self._fix(self._expand_play_id(id))
        if re.search(r"\.(?:m3u8|mp4|flv)(?:\?|$)", page, re.I):
            return {"parse": 0, "jx": 0, "url": page, "header": self.play_headers}
        source = self._get(page)
        tree = self._tree(source)
        embeds = tree.xpath('//iframe[@id="play-player-iframe"]/@src') if tree is not None else []
        embed = embeds[0] if embeds else ""
        if not embed:
            match = re.search(r'var\s+embedAutoOn\s*=\s*("(?:\\.|[^"\\])*")', source)
            if match:
                try:
                    embed = json.loads(match.group(1))
                except ValueError:
                    embed = ""
        target = self._target_url(embed)
        if target and re.search(r"\.(?:m3u8|mp4|flv)(?:\?|$)", target, re.I):
            return {"parse": 0, "jx": 0, "url": target, "header": self.play_headers}
        if target:
            return {"parse": 1, "jx": 1, "url": target, "header": self.play_headers}
        return {"parse": 1, "jx": 0, "url": page, "header": self.headers}
