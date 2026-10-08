# coding: utf-8
# 霸王鸟视频 - TVBox爬虫
# 站点: https://xn--cl0a.bawangniao.click/
# 类型: 成人影视站 (HTML解析, 单集直链)
# 特征: 分类页 /videos/categories/{tid}/, 详情页 /video/{id}/
# m3u8: 需去广告 (广告目录 /20260731/UTxI1Mxv/9567kb/hls/)
# 创建时间: 2026-09-09

import json
import re
import base64
import urllib.parse
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://xn--cl0a.bawangniao.click"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        self.NEED_CLEAN = True  # m3u8_analyzer确认有广告
        self.classes = [
            {"type_id": "avmingxing", "type_name": "AV明星"},
            {"type_id": "juru", "type_name": "巨乳尤物"},
            {"type_id": "linrenrenqi", "type_name": "邻家人妻"},
            {"type_id": "zhiyouyouhuo", "type_name": "制服诱惑"},
            {"type_id": "teshuzhiye", "type_name": "特殊职业"},
            {"type_id": "sm", "type_name": "SM重味"},
            {"type_id": "zipaipaitou", "type_name": "自拍偷拍"},
            {"type_id": "ziweixilie", "type_name": "自慰系列"},
            {"type_id": "koujiaokoubao", "type_name": "口交口爆"},
            {"type_id": "rihanwuma", "type_name": "日韩无码"},
            {"type_id": "qiangjianluanlun", "type_name": "强奸乱伦"},
            {"type_id": "oumeijingpin", "type_name": "欧美精品"},
            {"type_id": "zhongwenzimu", "type_name": "中文字幕"},
            {"type_id": "duoren", "type_name": "多人运动"},
        ]
        self.filters = {
            "avmingxing": [],
            "juru": [],
            "linrenrenqi": [],
            "zhiyouyouhuo": [],
            "teshuzhiye": [],
            "sm": [],
            "zipaipaitou": [],
            "ziweixilie": [],
            "koujiaokoubao": [],
            "rihanwuma": [],
            "qiangjianluanlun": [],
            "oumeijingpin": [],
            "zhongwenzimu": [],
            "duoren": [],
        }

    def getName(self):
        return "霸王鸟视频"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

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

    def _fetch_text(self, url, referer=None):
        headers = self.headers.copy()
        if referer:
            headers["Referer"] = referer
        try:
            r = self.fetch(url, headers=headers, timeout=15)
            if r and r.status_code == 200:
                return r.text
        except Exception:
            pass
        return ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 首页推荐：取AV明星分类第1页作为推荐
        return self.categoryContent("avmingxing", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        url = f"{self.host}/videos/categories/{tid}/{page}/"
        html = self._fetch_text(url)
        if not html:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

        items = self._parse_list(html)
        # 从页面提取总页数
        total_pages = self._extract_total_pages(html)
        if total_pages < 1:
            total_pages = 648  # 从pagination_parser得到的实际值

        return {
            "list": items,
            "page": int(page),
            "pagecount": total_pages,
            "limit": 20,
            "total": len(items) * total_pages
        }

    def _parse_list(self, html):
        """解析分类列表页 - 匹配 <div class="item"> 视频卡片"""
        items = []
        # 匹配 <div class="item"> 中的视频卡片
        pattern = r'<div[^>]*class="[^"]*item[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*title="([^"]*)"[^>]*>.*?<img[^>]*data-original="([^"]+)"[^>]*>.*?<div[^>]*class="duration"[^>]*>([^<]*)</div>.*?<div[^>]*class="added"[^>]*><em>([^<]*)</em></div>.*?</div>'
        for m in re.finditer(pattern, html, re.S):
            link = m.group(1).strip()
            title = m.group(2).strip()
            pic = m.group(3).strip()
            duration = m.group(4).strip()
            date = m.group(5).strip()
            if not link or not title:
                continue
            vod_id = link.split("/")[-2] if "/" in link else link
            remark = f"{date} {duration}" if date and duration else (date or duration or "")
            items.append({
                "vod_id": f"{vod_id}|$|{title}|$|{pic}|$|{remark}|$|/embed/{vod_id}",
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark
            })
        return items

    def _extract_pic(self, html, link):
        """提取图片URL，优先data-original/data-src"""
        # 找到对应卡片区域
        parts = html.split(f'href="{link}"')
        if len(parts) < 2:
            return ""
        card = parts[1][:500]  # 取href后的500字符
        # 优先级: data-original > data-src > src
        pic_patterns = [
            r'data-original="([^"]+)"',
            r'data-src="([^"]+)"',
            r'src="([^"]+)"',
        ]
        for pat in pic_patterns:
            m = re.search(pat, card)
            if m:
                pic = m.group(1)
                if pic.startswith("//"):
                    pic = "https:" + pic
                elif not pic.startswith("http"):
                    pic = urllib.parse.urljoin(self.host, pic)
                return pic
        return ""

    def _extract_total_pages(self, html):
        """提取总页数"""
        # 从分页器提取
        for pat in [
            r'<a[^>]*href="[^"]*/page/(\d+)/"[^>]*>最后</a>',
            r'<a[^>]*href="[^"]*/(\d+)/"[^>]*>最后</a>',
            r'共(\d+)页',
            r'pagecount["\s:]+(\d+)',
        ]:
            m = re.search(pat, html)
            if m:
                return int(m.group(1))
        return 0

    def detailContent(self, ids):
        vid = self._norm_ids(ids)
        if not vid:
            return {"list": []}

        # L1: 从列表阶段封装的字段直出
        if "|$|" in vid:
            parts = vid.split("|$|")
            if len(parts) >= 5 and parts[4]:
                return {"list": [{
                    "vod_id": vid,
                    "vod_name": parts[1] or "视频",
                    "vod_pic": parts[2] or "",
                    "vod_remarks": parts[3] or "",
                    "vod_content": "",
                    "vod_play_from": "播放",
                    "vod_play_url": f"播放${parts[4]}"
                }]}

        # L2: 请求详情页
        detail_url = f"{self.host}/video/{vid}/"
        html = self._fetch_text(detail_url)
        if not html:
            return self._skeleton(vid)

        # L3: 提取标题、封面、简介
        title = self._extract_title(html)
        pic = self._extract_pic_from_detail(html)
        desc = self._extract_desc(html)

        # L4: 提取播放地址 (详情页可能已含m3u8或embed链接)
        play_url = self._extract_play_from_detail(html)
        if not play_url:
            # 尝试从embed获取
            embed_url = self._extract_embed_url(html)
            if embed_url:
                embed_html = self._fetch_text(embed_url, referer=detail_url)
                play_url = self._extract_m3u8_from_embed(embed_html)

        if play_url:
            from_str = "播放"
            url_str = f"播放${play_url}"
        else:
            # 兜底：用embed地址作为播放ID
            embed_url = self._extract_embed_url(html) or f"/embed/{vid}"
            from_str = "播放"
            url_str = f"播放${embed_url}"

        return {"list": [{
            "vod_id": vid,
            "vod_name": title or "视频",
            "vod_pic": pic or "",
            "vod_remarks": "",
            "vod_content": desc or "",
            "vod_play_from": from_str,
            "vod_play_url": url_str
        }]}

    def _skeleton(self, vid):
        return {"list": [{
            "vod_id": vid,
            "vod_name": "未知标题",
            "vod_pic": "",
            "vod_remarks": "",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": f"播放$embed/{vid}"
        }]}

    def _extract_title(self, html):
        patterns = [
            r'<h1[^>]*>(.*?)</h1>',
            r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"',
            r'<title>([^<]+)</title>',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.S)
            if m:
                title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
                if title:
                    # 清洗站名后缀
                    title = re.sub(r"\s*[-|_–]\s*[^-|_–]{2,20}$", "", title)
                    return title
        return ""

    def _extract_pic_from_detail(self, html):
        patterns = [
            r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
            r'data-original="([^"]+)"',
            r'data-src="([^"]+)"',
            r'<img[^>]+class="[^"]*cover[^"]*"[^>]+src="([^"]+)"',
        ]
        for pat in patterns:
            m = re.search(pat, html)
            if m:
                pic = m.group(1)
                if pic.startswith("//"):
                    pic = "https:" + pic
                elif not pic.startswith("http"):
                    pic = urllib.parse.urljoin(self.host, pic)
                return pic
        return ""

    def _extract_desc(self, html):
        patterns = [
            r'<meta[^>]+name="description"[^>]+content="([^"]*)"',
            r'<meta[^>]+property="og:description"[^>]+content="([^"]*)"',
            r'<div[^>]*class="[^"]*(?:desc|plot|intro|content)[^"]*"[^>]*>(.*?)</div>',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.S)
            if m:
                desc = re.sub(r"<[^>]+>", "", m.group(1)).strip()
                if desc:
                    return desc
        return ""

    def _extract_embed_url(self, html):
        m = re.search(r'<iframe[^>]+src="([^"]+)"', html)
        if m:
            embed_url = m.group(1)
            if not embed_url.startswith("http"):
                embed_url = urllib.parse.urljoin(self.host, embed_url)
            return embed_url
        # 也可能直接用 /embed/{id}
        m = re.search(r'video_id["\s:]+"(\d+)"', html)
        if m:
            return f"{self.host}/embed/{m.group(1)}"
        return ""

    def _extract_play_from_detail(self, html):
        """从详情页直接提取m3u8"""
        patterns = [
            r'video_url["\s:]+"([^"]+\.m3u8[^"]*)"',
            r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"',
            r'<source[^>]+src="([^"]+\.m3u8[^"]*)"',
        ]
        for pat in patterns:
            m = re.search(pat, html)
            if m:
                url = m.group(1)
                if url.startswith("//"):
                    url = "https:" + url
                return url
        return ""

    def _extract_m3u8_from_embed(self, html):
        """从embed播放页提取m3u8"""
        m = re.search(r'video_url["\s:]+"([^"]+\.m3u8[^"]*)"', html)
        if m:
            url = m.group(1)
            if url.startswith("//"):
                url = "https:" + url
            return url
        return ""

    def searchContent(self, key, quick, pg="1"):
        # 搜索接口: /search/{key}/
        encoded_key = urllib.parse.quote(key, safe="")
        url = f"{self.host}/search/{encoded_key}/"
        html = self._fetch_text(url)
        if not html:
            return {"list": [], "page": 1}

        items = self._parse_list(html)
        return {"list": items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        ua = self.headers.get("User-Agent", "")
        play_url = str(id or "").strip()

        # 规范化embed路径
        if "/embed/" in play_url:
            # 提取embed ID
            m = re.search(r'/embed/(\d+)', play_url)
            if m:
                embed_id = m.group(1)
                play_url = f"{self.host}/embed/{embed_id}"
            # 如果play_url以/embed/开头，补全host
            elif play_url.startswith("/embed/"):
                play_url = self.host + play_url

        # L1: 直链识别
        if play_url.startswith("http") and self._is_media_url(play_url):
            if ".m3u8" in play_url.lower() and self.NEED_CLEAN:
                return {"parse": 0, "url": self._m3u8_proxy_url(play_url), "header": {"User-Agent": ua}}
            return {"parse": 0, "url": play_url, "header": {"User-Agent": ua}}

        # 如果是embed地址，请求embed页面提取m3u8
        if "/embed/" in play_url:
            try:
                r = self.fetch(play_url, headers={"User-Agent": ua, "Referer": self.host + "/"}, timeout=15)
                if r and r.status_code == 200:
                    embed_html = r.text
                    # 提取video_url，支持单引号和双引号
                    m = re.search(r'video_url["\s:]+(["\'])([^"\']+\.m3u8[^"\']*)\1', embed_html)
                    if m:
                        m3u8_url = m.group(2)
                        if m3u8_url.startswith("//"):
                            m3u8_url = "https:" + m3u8_url
                        if self.NEED_CLEAN:
                            return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url), "header": {"User-Agent": ua}}
                        return {"parse": 0, "url": m3u8_url, "header": {"User-Agent": ua}}
                    # 尝试从flashvars中提取
                    flash_match = re.search(r'var flashvars\s*=\s*\{([^}]*)\}', embed_html, re.S)
                    if flash_match:
                        flash_content = flash_match.group(1)
                        m2 = re.search(r'video_url["\s:]+(["\'])([^"\']+\.m3u8[^"\']*)\1', flash_content)
                        if m2:
                            m3u8_url = m2.group(2)
                            if m3u8_url.startswith("//"):
                                m3u8_url = "https:" + m3u8_url
                            if self.NEED_CLEAN:
                                return {"parse": 0, "url": self._m3u8_proxy_url(m3u8_url), "header": {"User-Agent": ua}}
                            return {"parse": 0, "url": m3u8_url, "header": {"User-Agent": ua}}
            except Exception as e:
                self.log({"player": "embed_fetch_error", "error": str(e)})

        # 降级
        if play_url.startswith("http"):
            return {"parse": 1, "url": play_url, "header": {"User-Agent": ua, "Referer": self.host + "/"}}

        return {"parse": 1, "url": self.host + "/embed/" + str(play_url), "header": {"User-Agent": ua, "Referer": self.host + "/"}}

    def _is_media_url(self, url):
        ext = (".m3u8", ".mp4", ".mkv", ".flv", ".avi")
        path = url.split("?")[0].split("#")[0].lower()
        return path.endswith(ext) or "index.m3u8" in path

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def localProxy(self, param):
        """m3u8五层去广告代理"""
        try:
            # 解析target
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")
            if target.startswith("url="):
                target = target[4:]
            elif "url=" in target:
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(target).query)
                if "url" in qs:
                    target = qs["url"][0]
            target = urllib.parse.unquote(str(target or ""))
            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            resp = self.fetch(target, headers=self.headers, timeout=20)
            if not resp:
                return [502, "text/plain", b"fetch failed"]
            content = getattr(resp, "content", b"") or b""
            if not content and getattr(resp, "text", ""):
                content = resp.text.encode("utf-8", errors="ignore")
            if not content:
                return [502, "text/plain", b"empty content"]

            if b"#EXTM3U" in content[:256]:
                cleaned = self._clean_m3u8(content.decode("utf-8", errors="ignore"), target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

            return [200, "application/octet-stream", content]
        except Exception as e:
            return [500, "text/plain", f"localProxy error: {e}".encode("utf-8", errors="ignore")]

    def _clean_m3u8(self, text, source_url):
        """五层去广告管线"""
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        # L1: 图片流检测（只打标记）
        is_img = self._is_fake_image_stream(text, source_url)
        if is_img:
            self.log({"stage": "clean", "fake_image_stream": True, "action": "keep_suffix_as_is"})

        # L2: 多码率主表
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            return self._clean_m3u8_multi(lines, source_url)

        # L3: 正片目录锚点（普通流用KEY/URL目录）
        main_dir = self._resolve_main_dir(lines, source_url, is_image_stream=is_img)

        # L4: 分片过滤
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)

        # L5: 全滤兜底（误杀过半即回退）
        if removed > 0 and (kept == 0 or removed > kept):
            self.log({"stage": "clean", "fallback": "no_filter", "removed": removed, "kept": kept, "anchor": main_dir})
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log({"stage": "clean", "removed": removed, "kept": kept, "anchor": main_dir})

        # 冗余标签清理
        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"

    def _is_fake_image_stream(self, text, source_url):
        IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
        VIDEO_EXT = (".ts", ".m4s", ".mp4", ".aac")
        has_video = False
        has_image = False
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            path = line.split("?")[0].split("#")[0].lower()
            if path.endswith(VIDEO_EXT):
                has_video = True
            elif path.endswith(IMAGE_EXT):
                has_image = True
        return has_image and not has_video

    def _resolve_main_dir(self, lines, source_url, is_image_stream=False):
        import posixpath
        base_dir = posixpath.dirname(urllib.parse.urlparse(source_url).path)
        if not base_dir.endswith("/"):
            base_dir += "/"

        # 图片流：用分片目录众数
        if is_image_stream:
            counter = {}
            for line in lines:
                if not line or line.startswith("#"):
                    continue
                p = urllib.parse.urlparse(urllib.parse.urljoin(source_url, line)).path
                d = posixpath.dirname(p)
                if d and d != "/":
                    counter[d + "/"] = counter.get(d + "/", 0) + 1
            if counter:
                return max(counter.items(), key=lambda kv: kv[1])[0]
            return base_dir

        # 普通流：KEY URI目录优先
        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            key_uri = m.group(1)
            key_path = urllib.parse.urlparse(
                key_uri if key_uri.startswith("http")
                else urllib.parse.urljoin(source_url, key_uri)
            ).path
            key_dir = posixpath.dirname(key_path)
            if key_dir and key_dir != "/":
                return key_dir + "/"
        return base_dir

    def _filter_segments(self, lines, source_url, main_dir):
        segments = []
        pending = []
        removed = 0
        kept = 0
        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urllib.parse.urljoin(source_url, line)
                media_path = urllib.parse.urlparse(media_url).path
                if media_path.startswith(main_dir):
                    segments.extend(pending)
                    segments.append(media_url)
                    kept += 1
                else:
                    removed += 1
                pending = []
                continue
            if line.startswith("#"):
                segments.append(line)
            else:
                segments.append(urllib.parse.urljoin(source_url, line))
        return segments, removed, kept

    def _dedup_tags(self, segments, source_url):
        NOISE = ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE")
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in NOISE:
                if not out or out[-1] in NOISE:
                    continue
            out.append(line)
        while len(out) > 1 and out[-1] in NOISE:
            out.pop()
        return out

    def _rewrite_m3u8_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                uri = match.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urllib.parse.urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urllib.parse.urljoin(source_url, line)
        return line

    def _clean_m3u8_multi(self, lines, source_url):
        out = []
        for line in lines:
            if line.startswith("#"):
                out.append(line)
            else:
                child = urllib.parse.urljoin(source_url, line)
                if ".m3u8" in child.lower():
                    out.append(self._m3u8_proxy_url(child))
                else:
                    out.append(child)
        return "\n".join(out) + "\n"