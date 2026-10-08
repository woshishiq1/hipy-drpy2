# -*- coding: utf-8 -*-
import json
import os
import time
import hmac
import hashlib
import requests
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "搜剧AI"

    def init(self, extend=""):
        self.host = "https://ai.baipiaozhe.com"
        self.secret = "f39d73aa7a6426203cdee1ef17b31d3b7ea8c23f4c59c62a3a8aa0f39ee5e79d"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Referer": self.host + "/",
            "Accept": "application/json",
            "x-ai-movie-client-name": "web",
            "x-ai-movie-client-version": "1",
            "x-ai-movie-protocol-version": "1",
        }
        self.session = requests.Session()
        self.session.verify = False
        self._anon_id = None
        self._authed = False

        self.classes = [
            {"type_id": "latest", "type_name": "最新上架"},
            {"type_id": "trending", "type_name": "大家都在看"},
            {"type_id": "tv_domestic", "type_name": "国产新剧"},
            {"type_id": "tv_korean", "type_name": "韩剧在追"},
            {"type_id": "tv_japanese", "type_name": "日剧上新"},
            {"type_id": "tv_american", "type_name": "美剧续看"},
            {"type_id": "movie_high_score", "type_name": "高分电影"},
            {"type_id": "movie_hot", "type_name": "电影热播"},
            {"type_id": "movie_nowplaying", "type_name": "院线热映"},
        ]
        self.filters = {c["type_id"]: [] for c in self.classes}

    # ---- auth & api helpers ----

    def _gen_nonce(self):
        return os.urandom(16).hex()

    def _sign(self, method, full_path):
        ts = str(int(time.time() * 1000))
        nonce = self._gen_nonce()
        msg = method + "\n" + full_path + "\n" + ts + "\n" + nonce
        sig = hmac.new(
            self.secret.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return ts, nonce, sig

    def _ensure_auth(self):
        if self._authed:
            return
        if not self._anon_id:
            self._anon_id = os.urandom(16).hex()
        path = "/v1/users/anonymous"
        ts, nonce, sig = self._sign("POST", path)
        h = dict(self.headers)
        h["Content-Type"] = "application/json"
        h["x-ai-movie-timestamp"] = ts
        h["x-ai-movie-nonce"] = nonce
        h["x-ai-movie-signature"] = sig
        try:
            r = self.session.post(
                self.host + path,
                headers=h,
                json={"anonymous_id": self._anon_id},
                timeout=15,
            )
            if r.status_code == 200 or r.status_code == 201:
                self._authed = True
        except Exception:
            pass

    def _api_get(self, path, params=None):
        self._ensure_auth()
        from urllib.parse import urlencode
        search = ""
        if params:
            search = "?" + urlencode(params)
        full = path + search
        ts, nonce, sig = self._sign("GET", full)
        h = dict(self.headers)
        h["x-ai-movie-timestamp"] = ts
        h["x-ai-movie-nonce"] = nonce
        h["x-ai-movie-signature"] = sig
        try:
            r = self.session.get(
                self.host + full,
                headers=h,
                timeout=15,
            )
            r.encoding = r.apparent_encoding or "utf-8"
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    # ---- card -> vod helper ----

    def _card_to_vod(self, card):
        vod_id = str(card.get("export_id") or card.get("id") or "")
        name = card.get("title") or card.get("normalized_title") or ""
        pic = card.get("poster_url") or card.get("backdrop_url") or ""
        remark = card.get("remarks") or ""
        if not remark and card.get("year"):
            remark = str(card.get("year"))
        return {
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remark,
        }

    # ---- six interfaces ----

    def homeContent(self, filter):
        data = self._api_get("/v1/feed/home")
        classes = list(self.classes)
        movies = []
        for sec in data.get("sections", []):
            for card in sec.get("cards", []):
                movies.append(self._card_to_vod(card))
            break
        return {
            "class": classes,
            "list": movies[:20],
            "filters": self.filters,
        }

    def homeVideoContent(self):
        data = self._api_get("/v1/feed/home")
        movies = []
        for sec in data.get("sections", []):
            for card in sec.get("cards", []):
                movies.append(self._card_to_vod(card))
            break
        return movies[:20]

    def categoryContent(self, tid, pg, filter, extend):
        page = max(1, int(pg or 1))
        limit = 20
        params = {"page": str(page), "limit": str(limit)}
        if tid == "latest":
            params["sort"] = "latest"
        elif tid == "trending":
            params["sort"] = "trending"
        else:
            params["hot_list_key"] = tid

        ext = extend if isinstance(extend, dict) else {}
        if ext.get("sort"):
            params["sort"] = ext["sort"]
            if "hot_list_key" in params:
                del params["hot_list_key"]

        data = self._api_get("/v1/browse/catalog", params)
        cards = data.get("cards", [])
        movies = [self._card_to_vod(c) for c in cards]
        pag = data.get("pagination", {})
        total = pag.get("total") or 0
        if not total:
            total = pag.get("returned_count", 0) * (page + 1) if pag.get("has_more") else pag.get("returned_count", 0) * page
        pagecount = max(total // limit if total else page, page + 1 if pag.get("has_more") else page)
        return {
            "page": page,
            "pagecount": pagecount,
            "limit": len(movies),
            "total": total or (pagecount * limit),
            "list": movies,
        }

    def _resolve_lines(self, ep_token):
        """resolve first episode token to discover multi-line providers"""
        data = self._api_get("/v1/playback/resolve/" + ep_token)
        line_options = data.get("line_options", [])
        direct_lines = []
        for lo in line_options:
            if lo.get("resolve_mode") == "direct" and lo.get("url_kind") == "m3u8":
                url = lo.get("url", "")
                if url and url.startswith("http"):
                    direct_lines.append({
                        "provider_id": lo.get("provider_id") or "",
                        "provider_name": lo.get("provider_name") or lo.get("display_label") or lo.get("label") or "",
                    })
        direct_lines.sort(key=lambda x: x.get("provider_name", ""))
        return direct_lines

    def detailContent(self, ids):
        result = []
        for vid in ids:
            export_id = str(vid)
            data = self._api_get("/v1/catalog/" + export_id)
            if not data:
                continue
            name = data.get("title") or ""
            pic = data.get("poster_url") or data.get("backdrop_url") or ""
            content = data.get("description") or ""
            remark = data.get("remarks") or ""
            year = data.get("year") or ""
            area = data.get("area") or ""
            actor = ", ".join(data.get("actors", [])) if data.get("actors") else ""
            director = ", ".join(data.get("directors", [])) if data.get("directors") else ""
            genre = ", ".join(data.get("genres", [])) if data.get("genres") else ""

            # collect all episodes via pagination
            episodes = []
            offset = 0
            ep_limit = 100
            while True:
                ep_data = self._api_get(
                    "/v1/catalog/" + export_id + "/episodes",
                    {"offset": offset, "limit": ep_limit},
                )
                eps = ep_data.get("episodes", [])
                if not eps:
                    break
                episodes.extend(eps)
                ep_pag = ep_data.get("episode_pagination", {})
                if not ep_pag.get("has_more"):
                    break
                offset += len(eps)
                if offset >= (ep_pag.get("total_count") or 9999):
                    break

            # resolve first episode to discover multi-line providers
            line_names = []
            line_pids = []
            for ep in episodes:
                tok = ep.get("token") or ""
                if tok:
                    lines = self._resolve_lines(tok)
                    if lines:
                        for ln in lines:
                            line_names.append(ln["provider_name"])
                            line_pids.append(ln["provider_id"])
                    break

            if not line_names:
                line_names = ["蜗牛专线"]
                line_pids = [""]

            # build multi-line play list
            # format: line1_eps$$$line2_eps$$$...
            # each line: 第1集$token|pid#第2集$token|pid#...
            line_urls = []
            for idx in range(len(line_names)):
                plays = []
                for ep in episodes:
                    token = ep.get("token") or ""
                    if not token:
                        continue
                    label = ep.get("title") or ep.get("key") or str(ep.get("number") or len(plays) + 1)
                    pid = line_pids[idx] if idx < len(line_pids) else ""
                    plays.append(label + "$" + token + "|" + pid)
                line_urls.append("#".join(plays) if plays else "")

            play_from = "$$$".join(line_names)
            play_url = "$$$".join(line_urls)

            txt = " ".join(x for x in [year and str(year), area, genre, director, actor] if x)

            result.append({
                "vod_id": export_id,
                "vod_name": name,
                "vod_pic": pic,
                "vod_content": content,
                "vod_year": str(year) if year else "",
                "vod_area": area,
                "vod_director": director,
                "vod_actor": actor,
                "vod_remarks": remark,
                "type_name": genre,
                "vod_play_from": play_from,
                "vod_play_url": play_url,
            })
        return {"list": result}

    def searchContent(self, key, quick, pg="1"):
        page = max(1, int(pg or 1))
        params = {"q": key, "page": str(page), "limit": "20"}
        data = self._api_get("/v1/browse/catalog", params)
        cards = data.get("cards", [])
        movies = [self._card_to_vod(c) for c in cards]
        pag = data.get("pagination", {})
        total = pag.get("total") or 0
        pagecount = max(total // 20 + (1 if total % 20 else 0), 1) if total else page
        return {
            "page": page,
            "pagecount": pagecount,
            "list": movies,
        }

    def playerContent(self, flag, id, vipFlags):
        # id format: token|provider_id  (multi-line) or token (fallback)
        raw = str(id)
        parts = raw.split("|", 1)
        token = parts[0]
        target_pid = parts[1] if len(parts) > 1 else ""

        data = self._api_get("/v1/playback/resolve/" + token)
        line_options = data.get("line_options", [])

        # try to match the specific provider line
        m3u8_url = ""
        if target_pid:
            for lo in line_options:
                if lo.get("resolve_mode") == "direct" and lo.get("url_kind") == "m3u8":
                    if lo.get("provider_id") == target_pid:
                        url = lo.get("url", "")
                        if url and url.startswith("http"):
                            m3u8_url = url
                            break

        # fallback: first available direct m3u8
        if not m3u8_url:
            for lo in line_options:
                if lo.get("resolve_mode") == "direct" and lo.get("url_kind") == "m3u8":
                    url = lo.get("url", "")
                    if url and url.startswith("http"):
                        m3u8_url = url
                        break

        # last fallback: any direct url
        if not m3u8_url:
            for lo in line_options:
                if lo.get("resolve_mode") == "direct":
                    url = lo.get("url", "")
                    if url and url.startswith("http"):
                        m3u8_url = url
                        break

        if m3u8_url:
            return {
                "parse": 0,
                "url": m3u8_url,
                "header": {"User-Agent": self.ua},
            }

        return {
            "parse": 1,
            "url": self.host + "/player/" + token,
            "header": dict(self.headers),
        }
