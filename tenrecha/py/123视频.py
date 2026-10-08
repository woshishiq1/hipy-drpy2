# coding: utf-8
# ============================================================
# 站点：123视频 (glm.123sp3.fit)
# 主域名：https://glm.123sp3.fit   （真实域 123spz.com，苹果CMS，fed-* 模板）
# 内容类型：成人影视（MacCMS 标准站）
# 分类：美女写真/国产精品/无码专区/中文字幕/强奸乱伦/人妻熟女/亚洲情色/制服丝袜/SM捆绑/自淫系列/三级伦理
# 详情URL：/cn/home/web/index.php/vod/detail/id/{id}.html
# 播放页：/cn/home/web/index.php/vod/play/id/{id}/sid/{sid}/nid/{nid}.html
# 播放数据：播放页 player_data JSON 内联 m3u8 直链（encrypt: 0 明文 / 1 escape 系 / 2 base64）
# m3u8：无广告目录，NEED_CLEAN=False（如需清洗置 True 并填 AD_DIRS）
# 来源：站点分析 2026-09-13
# ============================================================
import json
import re
import base64
from urllib.parse import quote, urljoin, unquote, urlparse, parse_qs
import posixpath

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        # __init__ 零网络：分类与筛选静态定义
        self.host = "https://glm.123sp3.fit"
        self.api = self.host + "/cn/home/web/index.php/vod"
        self.extend = ""
        self.classes = [
            {"type_id": "20", "type_name": "美女写真"},
            {"type_id": "21", "type_name": "国产精品"},
            {"type_id": "22", "type_name": "无码专区"},
            {"type_id": "23", "type_name": "中文字幕"},
            {"type_id": "24", "type_name": "强奸乱伦"},
            {"type_id": "25", "type_name": "人妻熟女"},
            {"type_id": "26", "type_name": "亚洲情色"},
            {"type_id": "27", "type_name": "制服丝袜"},
            {"type_id": "28", "type_name": "SM捆绑"},
            {"type_id": "29", "type_name": "自淫系列"},
            {"type_id": "30", "type_name": "三级伦理"},
        ]
        self.filters = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    # ---------------- 基础 ----------------
    def getName(self):
        return "123视频"

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
        # fed 模板卡片：li.fed-list-item > a.fed-list-pics(href=/vod/play/id/{id}/sid/{sid}/nid/{nid}.html + data-original 封面) + a.fed-list-title(标题)
        blocks = re.findall(
            r'<li[^>]*class="[^"]*fed-list-item[^"]*"[^>]*>([\s\S]*?)</li>', html, re.S)
        for b in blocks:
            pm = re.search(r'href="([^"]*vod/play/id/(\d+)/sid/(\d+)/nid/(\d+)[^"]*)"', b)
            if not pm:
                continue
            vid, sid, nid = pm.group(2), pm.group(3), pm.group(4)
            # 标题
            m_t = re.search(r'class="[^"]*fed-list-title[^"]*"[^>]*>([^<]*)<', b)
            name = self._clean(m_t.group(1)) if m_t else ""
            if not name:
                m_at = re.search(r'title="([^"]*)"', b)
                if m_at:
                    name = self._clean(m_at.group(1))
            if not name:
                name = vid
            # 封面
            m_p = re.search(r'data-original\s*=\s*["\']([^"\']*)["\']', b)
            pic = m_p.group(1) if m_p else ""
            if pic and pic.startswith("//"):
                pic = "https:" + pic
            elif pic and not pic.startswith("http"):
                pic = urljoin(self.host + "/", pic)
            # 备注（本站卡片 remarks 多为空）
            m_r = re.search(r'class="[^"]*fed-list-remarks[^"]*"[^>]*>([\s\S]*?)</span>', b)
            remark = self._clean(m_r.group(1)) if m_r else ""
            items.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return items

    # ---------------- 首页推荐 ----------------
    def homeVideoContent(self):
        html = self._fetch(self.host + "/cn/home/web/")
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
        # 该站分页格式：/cn/home/web/index.php/vod/type/id/{tid}/page/{page}.html
        url = "%s/type/id/%s/page/%s.html" % (self.api, tid, page)
        html = self._fetch(url)
        items = self._parse_list(html)
        # 读取总页数（翻页区内最大页码）
        pagecount = page
        nums = re.findall(r'type/id/%s/page/(\d+)\.html' % re.escape(str(tid)), html)
        if nums:
            pagecount = max(int(n) for n in nums)
        return {
            "list": items,
            "page": int(page),
            "pagecount": int(pagecount) if str(pagecount).isdigit() else 1,
            "limit": len(items),
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

        title, pic, content, remark = "", "", "", ""
        eps = []
        try:
            html = self._fetch("%s/detail/id/%s.html" % (self.api, vid))
            if html and len(html) > 500:
                m = re.search(r'<title>(.*?)</title>', html, re.S)
                if m:
                    title = self._clean(re.sub(r"_影片详情_.*$", "", m.group(1).strip()))
                # 封面：fed-deta-images 区块内 data-original（容器为 <dt>，兼容 dl/div）
                m = re.search(r'<(?:dt|div|dl)[^>]*class="[^"]*fed-deta-images[^"]*"[^>]*>([\s\S]*?)</(?:dt|div|dl)>', html, re.S)
                if m:
                    cm = re.search(r'data-original\s*=\s*["\']([^"\']*)["\']', m.group(1))
                    if cm:
                        pic = cm.group(1)
                        if pic.startswith("//"):
                            pic = "https:" + pic
                        elif pic and not pic.startswith("http"):
                            pic = urljoin(self.host + "/", pic)
                # 选集：详情页内 vod/play 静态链接（多集按 nid 递增）
                for mm in re.finditer(
                        r'<a[^>]+href="([^"]*vod/play/id/%s/sid/(\d+)/nid/(\d+)[^"]*)"[^>]*>(.*?)</a>' % vid,
                        html, re.S):
                    sid, nid = mm.group(2), mm.group(3)
                    if (sid, nid) not in [(e[0], e[1]) for e in eps]:
                        eps.append((sid, nid))
                m = re.search(r'<p[^>]*class="[^"]*fed-part-con[^"]*"[^>]*>([\s\S]*?)</p>', html, re.S)
                if m:
                    content = self._clean(m.group(1))
        except Exception as e:
            self.log({"detail_err": type(e).__name__})

        if not title:
            title = "视频 " + vid
        if not eps:
            eps = [("1", "1")]
        play_url = "#".join(
            "第%s集$%s/play/id/%s/sid/%s/nid/%s.html" % (n, self.api, vid, s, n)
            for s, n in eps
        )
        vod = {
            "vod_id": raw,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": remark,
            "vod_content": content or title,
            "vod_play_from": "播放",
            "vod_play_url": play_url,
        }
        return {"list": [vod]}

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        try:
            k = quote(str(key or "").strip(), safe="")
        except Exception:
            k = str(key or "")
        url = "%s/search/wd/%s.html" % (self.api, k)
        html = self._fetch(url)
        return {"list": self._parse_list(html), "page": int(pg or 1)}

    def recommendContent(self, ids, pg="1"):
        # 详情页底部同类推荐（fed 模板通常带列表卡），复用详情页解析
        try:
            vid = self._norm_ids(ids)
            vid = vid.split("|$|")[0].split("$")[0].split("@@")[0].strip()
            if not vid:
                return {"list": []}
            html = self._fetch("%s/detail/id/%s.html" % (self.api, vid))
            if not html or len(html) < 500:
                return {"list": []}
            return {"list": self._parse_list(html)}
        except Exception as e:
            self.log({"recommend_err": type(e).__name__})
            return {"list": []}

    # ---------------- 播放 ----------------
    @staticmethod
    def _unescape_js(s):
        """等价 JS unescape：解码 %uXXXX 与 %XX"""
        def _u(m):
            try:
                return chr(int(m.group(1), 16))
            except Exception:
                return m.group(0)
        s = re.sub(r'%u([0-9a-fA-F]{4})', _u, s or "")
        try:
            return unquote(s)
        except Exception:
            return s

    @staticmethod
    def _decrypt_url(data):
        """按 encrypt 值解码播放地址：0 明文 / 1 escape 系 / 2 base64"""
        url = (data or {}).get("url") or ""
        enc = data.get("encrypt")
        if enc == 1:
            url = Spider._unescape_js(url)
        elif enc == 2:
            try:
                url = base64.b64decode(url).decode("utf-8")
            except Exception:
                try:
                    url = base64.b64decode(url).decode("latin-1")
                except Exception:
                    pass
        return url

    def _extract_player_url(self, html):
        """从播放页提取 player_data 内联 JSON 的 m3u8 直链（L1-L5），含 encrypt 解码"""
        if not html:
            return ""
        # L2: player_data 变量（本站为单层 JSON，直接截取）
        m = re.search(r'player_data\s*=\s*(\{[^{}]*\})', html)
        if not m:
            m = re.search(r'player_data\s*=\s*(\{.*?\})\s*</script>', html, re.S)
        if m:
            raw = m.group(1)
            try:
                data = json.loads(raw)
                u = self._decrypt_url(data)
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
        raw = str(id or "").strip()
        if not raw:
            return {"parse": 0, "url": "", "header": {}}

        ua = self.headers.get("User-Agent", "")
        # 如果已经是 m3u8 直链
        if raw.startswith("http") and ".m3u8" in raw.lower():
            return self._play_response(raw, ua)

        # 播放页路由提取：/play/id/{id}/sid/{sid}/nid/{nid}.html（兼容 "第1集$URL"）
        m = re.search(r'play/id/(\d+)/sid/(\d+)/nid/(\d+)', raw)
        if m:
            vid, sid, nid = m.group(1), m.group(2), m.group(3)
        else:
            # 纯 ID 串：兼容 "id" / "id$sid$nid" / "名称$id-sid-nid"
            seg = raw.split("$")[-1]
            m2 = re.match(r'^(\d+)-(\d+)-(\d+)$', seg)
            if m2:
                vid, sid, nid = m2.group(1), m2.group(2), m2.group(3)
            else:
                ids2 = raw.split("$")
                vid = ids2[0]
                sid = ids2[1] if len(ids2) > 1 else "1"
                nid = ids2[2] if len(ids2) > 2 else "1"
        if not vid or not str(vid).isdigit():
            return {"parse": 0, "url": "", "header": {}}
        page_url = "%s/play/id/%s/sid/%s/nid/%s.html" % (self.api, vid, sid, nid)
        html = self._fetch(page_url)
        real = self._extract_player_url(html)
        if real:
            return self._play_response(real, ua)
        # 降级嗅探
        return {
            "parse": 1,
            "url": page_url,
            "header": {"User-Agent": ua, "Referer": self.host + "/"},
        }

    def _play_response(self, m3u8_url, ua):
        if self.NEED_CLEAN:
            return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url),
                    "header": {"User-Agent": ua}}
        return {"parse": 0, "url": m3u8_url, "header": {"User-Agent": ua}}

    # ---------------- m3u8 广告过滤（本站无广告目录，默认关闭） ----------------
    NEED_CLEAN = False
    ANCHOR = ""
    AD_DIRS = []

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