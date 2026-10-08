# coding: utf-8
# ============================================================
# 站点：抠爆B处 (kbbshape.buzz)
# 主域名：https://t3g15u7s.kbbshape.buzz
# 内容类型：成人影视（MacCMS 标准站）
# 分类：番号资源/大地资源/黄色仓库/麻豆资源/百万资源/奥斯卡资源/杏吧资源/森林资源
# 详情URL：/voddetail/{id}/    播放页：/vodplay/{id}-1-1/
# 播放数据：播放页 player_data JSON 内联 m3u8 直链
# m3u8：多码率 + AES KEY，含广告目录，NEED_CLEAN=True
# 来源：站点分析 2026-09-13
# ============================================================
import json
import re
from urllib.parse import quote, urljoin, unquote, urlparse, parse_qs
import posixpath

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        # __init__ 零网络：分类与筛选静态定义
        self.host = "https://t3g15u7s.kbbshape.buzz"
        self.extend = ""
        self.classes = [
            {"type_id": "1", "type_name": "百万资源"},
            {"type_id": "18", "type_name": "大地资源"},
            {"type_id": "61", "type_name": "森林资源"},
            {"type_id": "132", "type_name": "杏吧资源"},
            {"type_id": "268", "type_name": "奶香香资源"},
            {"type_id": "296", "type_name": "奥斯卡资源"},
            {"type_id": "382", "type_name": "黄色仓库"},
            {"type_id": "423", "type_name": "麻豆资源"},
        ]
        self.filters = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    # ---------------- 基础 ----------------
    def getName(self):
        return "抠爆B处"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # 零网络
        self.extend = extend or ""

    def destroy(self):
        pass

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def _fetch(self, url, timeout=15):
        try:
            r = self.fetch(url, headers=self.headers, timeout=timeout)
            if not r or getattr(r, "status_code", 0) != 200:
                return ""
            return getattr(r, "text", "") or ""
        except Exception as e:
            self.log({"fetch_fail": type(e).__name__, "url": url.split("?")[0]})
            return ""

    # ---------------- 列表解析 ----------------
    @staticmethod
    def _clean(s):
        if not s:
            return ""
        s = re.sub(r"<[^>]+>", "", s)
        for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " ")):
            s = s.replace(a, b)
        return s.strip()

    def _parse_list(self, html):
        items = []
        if not html:
            return items
        # 卡片：div.item > a[href=/voddetail/{id}/] ... </a> </div>
        blocks = re.findall(
            r'<div class="item">\s*<a[^>]+href="/voddetail/(\d+)/"[^>]*>(.*?)</a>',
            html, re.S)
        if not blocks:
            blocks = re.findall(
                r'<a[^>]+href="/voddetail/(\d+)/"[^>]*>(.*?)</a>', html, re.S)
        for vid, b in blocks:
            # 标题：优先 strong.title，其次 a[title]
            m_t = re.search(r'<strong class="title"[^>]*>(.*?)</strong>', b, re.S)
            name = self._clean(m_t.group(1)) if m_t else ""
            if not name:
                m_at = re.search(r'title="([^"]*)"', b)
                if m_at:
                    name = self._clean(m_at.group(1))
            if not name:
                m_img = re.search(r'<img[^>]+alt="([^"]*)"', b)
                if m_img:
                    name = self._clean(m_img.group(1))
            if not name:
                name = vid
            # 封面
            m_p = re.search(r'<img[^>]+class="thumb[^"]*"[^>]+src="([^"]+)"', b)
            if not m_p:
                m_p = re.search(r'<img[^>]+src="([^"]+)"', b)
            pic = m_p.group(1) if m_p else ""
            if pic and pic.startswith("//"):
                pic = "https:" + pic
            elif pic and not pic.startswith("http"):
                pic = urljoin(self.host + "/", pic)
            # 备注：duration 或 is-hd 分类
            m_r = re.search(r'<div class="duration">([^<]+)</div>', b)
            remark = m_r.group(1).strip() if m_r else ""
            if not remark:
                m_hd = re.search(r'<span class="is-hd">([^<]+)</span>', b)
                if m_hd:
                    remark = m_hd.group(1).strip()
            items.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return items

    # ---------------- 首页推荐 ----------------
    def homeVideoContent(self):
        # 根路径 / 只是跳转页，真实首页为 /gao/
        html = self._fetch(self.host + "/gao/")
        if not html or len(html) < 500:
            html = self._fetch(self.host + "/")
        return {"list": self._parse_list(html)}

    # ---------------- 分类 ----------------
    def _parse_extend(self, extend):
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            try:
                return json.loads(extend)
            except Exception:
                pass
            out = {}
            for part in extend.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    out[k.strip()] = v.strip()
            return out
        return {}

    def categoryContent(self, tid, pg, filter, extend):
        page = str(pg or "1")
        # 该站分页格式：第1页 /vodtype/{tid}/，第2页起 /vodtype/{tid}-{page}/
        if page == "1":
            url = f"{self.host}/vodtype/{tid}/"
        else:
            url = f"{self.host}/vodtype/{tid}-{page}/"
        html = self._fetch(url)
        items = self._parse_list(html)
        # 读取总页数（翻页区内最大页码）
        pagecount = page
        nums = re.findall(r'/vodtype/%s-(\d+)/' % re.escape(str(tid)), html)
        if not nums:
            nums = re.findall(r'/vodtype/%s/(\d+)/' % re.escape(str(tid)), html)
        if nums:
            pagecount = max(int(n) for n in nums)
        else:
            m_pg = re.search(r'共\s*(\d+)\s*页', html)
            if m_pg:
                pagecount = int(m_pg.group(1))
        return {
            "list": items,
            "page": int(page),
            "pagecount": int(pagecount) if str(pagecount).isdigit() else 1,
            "limit": 20,
            "total": 9999,
        }

    # ---------------- 详情 ----------------
    @staticmethod
    def _norm_ids(ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    def _skeleton(self, vid, title="", pic="", remarks="解析中"):
        pid = str(vid).split("|$|")[0].replace("$", "|")
        return {"list": [{
            "vod_id": vid, "vod_name": title or "未知标题", "vod_pic": pic or "",
            "vod_remarks": remarks, "vod_content": "",
            "vod_play_from": "播放", "vod_play_url": "播放$" + pid,
        }]}

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        vid = raw.split("|$|")[0].split("$")[0].split("@@")[0].strip()
        play_id = f"{vid}-1-1"

        title, pic, content, remark = "", "", "", ""
        try:
            html = self._fetch(f"{self.host}/voddetail/{vid}/")
            if html and len(html) > 500:
                m = re.search(r'<div class="headline">\s*<h1[^>]*>(.*?)</h1>', html, re.S)
                if not m:
                    m = re.search(r'<h1(?![^>]*class="htitle")[^>]*>(.*?)</h1>', html, re.S)
                if m:
                    title = self._clean(m.group(1))
                else:
                    m = re.search(r'<title>(.*?)</title>', html, re.S)
                    if m:
                        title = self._clean(m.group(1)).split("-")[0].split("详情")[0].strip()
                m = re.search(r'<div class="img-wrap">\s*<img[^>]+src="([^"]+)"', html, re.S)
                if not m:
                    m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
                if m:
                    pic = m.group(1)
                    if pic.startswith("//"):
                        pic = "https:" + pic
                    elif pic and not pic.startswith("http"):
                        pic = urljoin(self.host + "/", pic)
                m = re.search(r'描述:\s*<em>(.*?)</em>', html, re.S)
                if m:
                    content = self._clean(m.group(1))
                m = re.search(r'<div class="duration">([^<]+)</div>', html)
                if m:
                    remark = m.group(1).strip()
                if not remark:
                    m = re.search(r'类别:\s*<a[^>]*>([^<]+)</a>', html)
                    if m:
                        remark = m.group(1).strip()
        except Exception as e:
            self.log({"detail_err": type(e).__name__})

        if not title:
            title = "视频 " + vid

        vod = {
            "vod_id": raw,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": remark,
            "vod_content": content or title,
            "vod_play_from": "播放",
            "vod_play_url": "正片$" + play_id,
        }
        return {"list": [vod]}

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        try:
            k = quote(str(key or "").strip())
        except Exception:
            k = str(key or "")
        url = f"{self.host}/vodsearch/{k}-------------.html"
        html = self._fetch(url)
        return {"list": self._parse_list(html), "page": int(pg or 1)}
    def recommendContent(self, ids, pg="1"):
        # 详情页含「相关视频」，直接复用详情页抓取并解析
        try:
            vid = self._norm_ids(ids)
            vid = vid.split("|$|")[0].split("$")[0].split("@@")[0].strip()
            if not vid:
                return {"list": []}
            html = self._fetch(f"{self.host}/voddetail/{vid}/")
            if not html or len(html) < 500:
                return {"list": []}
            m = re.search(r'相关视频(.*)$', html, re.S)
            seg = m.group(1) if m else html
            return {"list": self._parse_list(seg)}
        except Exception as e:
            self.log({"recommend_err": type(e).__name__})
            return {"list": []}

    # ---------------- 播放 ----------------
    def _extract_player_url(self, html):
        """从播放页提取 player_data 内联 JSON 的 m3u8 直链（L1-L5）"""
        if not html:
            return ""
        # L2: player_data 变量
        m = re.search(r'player_data\s*=\s*(\{.*?\})\s*</script>', html, re.S)
        if not m:
            m = re.search(r'player_data\s*=\s*(\{.*\})', html, re.S)
        if m:
            raw = m.group(1)
            try:
                data = json.loads(raw)
                u = data.get("url", "")
                if u:
                    return self._norm_url(u)
            except Exception:
                # loose 重试
                try:
                    loose = raw.replace("\\/", "/")
                    data = json.loads(loose)
                    u = data.get("url", "")
                    if u:
                        return self._norm_url(u)
                except Exception:
                    pass
            # 正则兜底
            mu = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
            if mu:
                return self._norm_url(mu.group(1))
        # L5: 全文正则找 m3u8
        mu = re.search(r'(https?:\\?/\\?/[^"\'\s]+\.m3u8[^"\'\s]*)', html)
        if mu:
            return self._norm_url(mu.group(1))
        return ""

    @staticmethod
    def _norm_url(u):
        if not u:
            return ""
        u = u.replace("\\/", "/").replace("\\u002f", "/").replace("&amp;", "&")
        if u.startswith("//"):
            u = "https:" + u
        return u.strip()

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id or "").strip()
        if "$" in play_url:
            parts = play_url.split("$", 1)
            if len(parts) == 2:
                play_url = parts[1]
        play_url = play_url.strip()
        if not play_url:
            return {"parse": 0, "url": "", "header": {}}

        ua = self.headers.get("User-Agent", "")
        # 如果已经是 m3u8 直链
        if play_url.startswith("http") and ".m3u8" in play_url.lower():
            return self._play_response(play_url, ua)

        # 否则是播放ID，如 1904270-1-1 或 1904270
        pid = play_url
        if not re.match(r"^\d+-\d+-\d+$", pid):
            pid = f"{play_url}-1-1"
        html = self._fetch(f"{self.host}/vodplay/{pid}/")
        real = self._extract_player_url(html)
        if real:
            return self._play_response(real, ua)
        # 降级嗅探
        return {
            "parse": 1,
            "url": f"{self.host}/vodplay/{pid}/",
            "header": {"User-Agent": ua, "Referer": self.host + "/"},
        }

    def _play_response(self, m3u8_url, ua):
        if self.NEED_CLEAN:
            return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url),
                    "header": {"User-Agent": ua}}
        return {"parse": 0, "url": m3u8_url, "header": {"User-Agent": ua}}

    # ---------------- m3u8 广告过滤 ----------------
    NEED_CLEAN = True
    ANCHOR = "/20260427/soqUwUxi/2000kb/hls/"
    AD_DIRS = ["/a3/20260912/5viWELDU/2000kb/hls/", "/20260913/LA0EIgjb/2000kb/hls/"]

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + quote(str(url or ""), safe="")

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")
            if target.startswith("url="):
                target = target[4:]
            elif "url=" in target:
                qs = parse_qs(urlparse(target).query)
                if "url" in qs:
                    target = qs["url"][0]
            target = unquote(str(target or ""))
            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            r = self.fetch(target, headers=self.headers, timeout=20)
            if not r or getattr(r, "status_code", 0) != 200:
                return [502, "text/plain", b"fetch failed"]
            content = getattr(r, "content", b"") or b""
            if not content and getattr(r, "text", ""):
                content = r.text.encode("utf-8", errors="ignore")
            if not content:
                return [502, "text/plain", b"empty"]
            if b"#EXTM3U" in content[:512]:
                cleaned = self._clean_m3u8(content.decode("utf-8", errors="ignore"), target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
            return [200, "application/octet-stream", content]
        except Exception as e:
            return [500, "text/plain", ("localProxy error: " + type(e).__name__).encode("utf-8")]

    def _clean_m3u8(self, text, source_url):
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 第1层：图片流检测（只打标记）
        is_img = self._is_fake_image_stream(text)

        # 第2层：多码率主表透传，子流改代理
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        # 第3层：锚点（KEY URI 目录优先；图片流用分片目录众数）
        main_dir = self._resolve_main_dir(lines, source_url, is_img)

        # 第4层：分片过滤
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)

        # 第5层：全滤兜底（误杀过半即回退）
        if removed > 0 and (kept == 0 or removed > kept):
            self.log({"clean": "fallback_no_filter", "removed": removed, "kept": kept, "anchor": main_dir})
            out = [self._rewrite_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log({"clean": "filtered", "removed": removed, "kept": kept, "anchor": main_dir})

        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"

    @staticmethod
    def _is_fake_image_stream(text):
        IMG = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
        VID = (".ts", ".m4s", ".mp4", ".aac", ".m4a")
        has_img = has_vid = False
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            p = line.split("?")[0].split("#")[0].lower()
            if p.endswith(VID):
                has_vid = True
            elif p.endswith(IMG):
                has_img = True
        return has_img and not has_vid

    def _resolve_main_dir(self, lines, source_url, is_img):
        base_dir = posixpath.dirname(urlparse(source_url).path)
        if not base_dir.endswith("/"):
            base_dir += "/"
        # 通用：优先分片目录众数（对图片流与普通流都最鲁棒）
        counter = {}
        for line in lines:
            if not line or line.startswith("#"):
                continue
            p = urlparse(urljoin(source_url, line)).path
            d = posixpath.dirname(p)
            if d and d != "/":
                counter[d + "/"] = counter.get(d + "/", 0) + 1
        if counter:
            top_dir, top_n = max(counter.items(), key=lambda kv: kv[1])
            total = sum(counter.values())
            # 众数覆盖率 >= 50% 才用它作锚点，否则回退 KEY/m3u8 目录
            if total > 0 and top_n / total >= 0.5:
                return top_dir
        # 普通流：KEY URI 目录优先
        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            ku = m.group(1)
            kp = urlparse(ku if ku.startswith("http") else urljoin(source_url, ku)).path
            kd = posixpath.dirname(kp)
            if kd and kd != "/":
                return kd + "/"
        return base_dir

    def _filter_segments(self, lines, source_url, main_dir):
        segments = []
        pending = []
        removed = kept = 0
        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media = urljoin(source_url, line)
                mp = urlparse(media).path
                if mp.startswith(main_dir):
                    segments.extend(pending)
                    segments.append(media)
                    kept += 1
                else:
                    removed += 1
                pending = []
                continue
            if line.startswith("#"):
                segments.append(line)
            else:
                segments.append(urljoin(source_url, line))
        return segments, removed, kept

    def _rewrite_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                uri = match.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urljoin(source_url, line)
        return line

    def _dedup_tags(self, segments, source_url):
        NOISE = ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE")
        out = []
        for line in segments:
            line = self._rewrite_tag(line, source_url)
            if line in NOISE:
                if not out or out[-1] in NOISE:
                    continue
            out.append(line)
        while len(out) > 1 and out[-1] in NOISE:
            out.pop()
        return out
