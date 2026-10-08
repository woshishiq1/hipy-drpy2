# coding: utf-8
# 站点信息沉淀（法则24）
# 主域名：https://ciw.ddwb8.best
# 备用域名：无（发布页未发现备用域名）
# 发布页：https://ciw.ddwb8.best/cn/home/web/
# 内容类型：成人影视
# 特殊说明：MacCMS标准站，AES-128加密m3u8，有广告分片（不同目录前缀）
# 最后验证时间：2026-08-31
# 来源：https://ciw.ddwb8.best/cn/home/web/
#
# m3u8 结构摘要：
# - 主m3u8为多码率主表，子m3u8含AES-128加密
# - 正片目录：/20260830/fdHqdAKg/2000kb/hls/（KEY URI目录优先）
# - 广告目录：/20260820/R7Q9mzPo/1000kb/hls/（日期不同，前缀不同）
# - 过滤方式：五层管线 - KEY URI目录锚点 + 分片过滤 + 全滤兜底

import json
import re
import urllib.parse
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.extend = ""
        self.host = "https://ciw.ddwb8.best"
        self._cached_host = self.host
        
        # 分类硬编码（法则16/17）
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
        
        # filters 与分类一一对应
        self.filters = {
            "20": [],
            "21": [],
            "22": [],
            "23": [],
            "24": [],
            "25": [],
            "26": [],
            "27": [],
            "28": [],
            "29": [],
            "30": [],
        }
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/cn/home/web/",
        }

    def getName(self):
        return "弟大勿勃"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        """首页推荐 - 从首页抓取最近更新列表"""
        url = self.host + "/cn/home/web/"
        try:
            html = self.fetch(url, headers=self.headers, timeout=10).text
        except:
            return {"list": []}
        
        items = []
        # 最近更新区域：.fed-list-info .fed-list-item
        pattern = r'<li class="fed-list-item[^"]*">.*?<a class="fed-list-pics[^"]*" href="([^"]+)"[^>]*data-original="([^"]+)"[^>]*>.*?<span class="fed-list-score[^"]*">([^<]*)</span>.*?</a>.*?<a class="fed-list-title[^"]*" href="[^"]*" target="[^"]*">([^<]*)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches[:20]:
            href, pic, score, title = match
            if not href or not title:
                continue
            vod_id = self._extract_vod_id(href)
            items.append({
                "vod_id": str(vod_id),
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": score.strip() + "分" if score else "",
            })
        
        return {"list": items}

    def _extract_vod_id(self, url):
        """从 /vod/play/id/xxx/sid/1/nid/1.html 提取 xxx"""
        m = re.search(r'/id/(\d+)/', url)
        return m.group(1) if m else "0"

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        # MacCMS 标准分页 URL
        url = f"{self.host}/cn/home/web/index.php/vod/type/id/{tid}/page/{page}.html"
        try:
            html = self.fetch(url, headers=self.headers, timeout=10).text
        except:
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
        
        items = []
        # 按 li.fed-list-item 块提取
        for li in re.findall(r'<li class="fed-list-item[^"]*">.*?</li>', html, re.DOTALL):
            href_m = re.search(r'<a class="fed-list-pics[^"]*" href="([^"]+)"', li)
            pic_m = re.search(r'data-original="([^"]+)"', li)
            score_m = re.search(r'<span class="fed-list-score[^"]*">([^<]+)</span>', li)
            title_m = re.search(r'<a class="fed-list-title[^"]*" href="[^"]*"[^>]*>([^<]+)</a>', li)
            desc_m = re.search(r'<span class="fed-list-desc[^"]*">([^<]+)</span>', li)
            
            if href_m and title_m:
                href = href_m.group(1)
                pic = pic_m.group(1) if pic_m else ""
                score = score_m.group(1) if score_m else ""
                title = title_m.group(1).strip()
                desc = desc_m.group(1).strip() if desc_m else ""
                vod_id_match = re.search(r'/id/(\d+)/', href)
                vod_id = vod_id_match.group(1) if vod_id_match else "0"
                items.append({
                    "vod_id": str(vod_id),
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": desc or (score + "分") if score else "",
                })
        
        # 提取分页信息
        total = 0
        total_match = re.search(r'共&nbsp;(\d+)&nbsp;个影片', html)
        if total_match:
            total = int(total_match.group(1))
        else:
            # 备用：从分页栏提取总页数
            page_match = re.search(r'<a[^>]*>(\d+)</a>\s*<a[^>]*>[^<]*尾页', html)
            if page_match:
                total_pages = int(page_match.group(1))
                total = total_pages * 20
            else:
                # 再备用：从分页栏最后数字提取
                nums = re.findall(r'<a[^>]*>(\d+)</a>', html)
                if nums:
                    total = int(nums[-1]) * 20
        
        pagecount = 1
        if total > 0:
            pagecount = (total + 19) // 20
        # 确保 pagecount 至少为 1
        if pagecount < 1:
            pagecount = 1
        
        return {
            "list": items,
            "page": int(page),
            "pagecount": pagecount,
            "limit": 20,
            "total": total,
        }
    def detailContent(self, ids):
        """详情页 - 从播放页提取元数据，播放地址在 playerContent 中处理"""
        vod_id = str(ids[0])
        url = f"{self.host}/cn/home/web/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
        try:
            html = self.fetch(url, headers=self.headers, timeout=10).text
        except:
            return {"list": []}
        
        # 提取标题
        title = ""
        title_m = re.search(r'<h3[^>]*>.*?<a[^>]*>([^<]+)</a>', html)
        if title_m:
            title = title_m.group(1).strip()
        
        # 提取封面
        pic = ""
        pic_m = re.search(r'<a class="fed-list-pics[^"]*" href="[^"]*" data-original="([^"]+)"', html)
        if pic_m:
            pic = pic_m.group(1)
        
        # 提取分类、年份、演员等
        category = ""
        year = ""
        actor = ""
        director = ""
        remark = ""
        
        # 分类
        cat_m = re.search(r'<span class="fed-text-muted">分类：</span><a[^>]*>([^<]+)</a>', html)
        if cat_m:
            category = cat_m.group(1).strip()
        
        # 年份
        year_m = re.search(r'<span class="fed-text-muted">年份：</span><a[^>]*>(\d+)</a>', html)
        if year_m:
            year = year_m.group(1).strip()
        
        # 评分
        score_m = re.search(r'<span class="fed-list-score[^"]*">([^<]+)</span>', html)
        if score_m:
            remark = score_m.group(1).strip() + "分"
        
        # 构造播放数据：从播放页获取 player_data.url 已在 playerContent 处理
        # 详情只返回元数据 + 播放入口
        vod_data = {
            "vod_id": vod_id,
            "vod_name": title or "未知视频",
            "vod_pic": pic,
            "vod_remarks": remark,
            "vod_actor": actor,
            "vod_director": director,
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": f"播放${vod_id}",
        }
        
        return {"list": [vod_data]}

    def searchContent(self, key, quick, pg="1"):
        """搜索 - GET 方式"""
        page = pg or "1"
        url = f"{self.host}/cn/home/web/index.php/vod/search.html"
        params = {"wd": key, "page": page}
        try:
            html = self.fetch(url, headers=self.headers, params=params, timeout=10).text
        except:
            return {"list": [], "page": int(page)}
        
        items = []
        # 搜索页结构：每个结果是一行，包含标题链接和播放链接
        # 匹配模式：<a href="/cn/home/web/index.php/vod/play/id/xxx/...">标题</a>
        # 需要提取 vod_id 和标题
        pattern = r'<a[^>]*href="(/cn/home/web/index.php/vod/play/id/(\d+)/[^"]*)"[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html)
        # 去重：用 vod_id 做 key
        seen = set()
        for href, vod_id, title in matches:
            if vod_id in seen:
                continue
            seen.add(vod_id)
            title = title.strip()
            if not title or title in ("立即播放", "报错", "刷新", "分享", "上一集", "下一集"):
                continue
            items.append({
                "vod_id": str(vod_id),
                "vod_name": title,
                "vod_pic": "",
                "vod_remarks": "",
            })
        
        return {"list": items[:30], "page": int(page)}
    def playerContent(self, flag, id, vipFlags):
        """播放器 - 从播放页提取 m3u8 直链"""
        vod_id = str(id).strip()
        # 如果已经是 URL
        if vod_id.startswith("http"):
            if ".m3u8" in vod_id:
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(vod_id),
                    "header": {"User-Agent": self.headers.get("User-Agent", "")},
                }
            return {"parse": 0, "url": vod_id, "header": self.headers}
        
        # 从播放页提取 player_data
        url = f"{self.host}/cn/home/web/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
        try:
            html = self.fetch(url, headers=self.headers, timeout=10).text
        except:
            return {"parse": 1, "url": url, "header": self.headers}
        
        # 提取 player_data
        pattern = r'var player_data=(\{.*?\})'
        m = re.search(pattern, html, re.DOTALL)
        if not m:
            return {"parse": 1, "url": url, "header": self.headers}
        
        try:
            data = json.loads(m.group(1))
        except:
            return {"parse": 1, "url": url, "header": self.headers}
        
        play_url = data.get("url", "")
        if not play_url:
            return {"parse": 1, "url": url, "header": self.headers}
        
        # 补全绝对地址
        if not play_url.startswith("http"):
            play_url = urllib.parse.urljoin(self.host, play_url)
        
        # m3u8 直链走代理过滤广告
        if ".m3u8" in play_url:
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(play_url),
                "header": {"User-Agent": self.headers.get("User-Agent", "")},
            }
        
        return {"parse": 0, "url": play_url, "header": self.headers}

    def recommendContent(self, ids, pg):
        """相关推荐 - 从播放页提取推荐列表"""
        vod_id = str(ids[0]) if ids else "0"
        url = f"{self.host}/cn/home/web/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
        try:
            html = self.fetch(url, headers=self.headers, timeout=10).text
        except:
            return {"list": []}
        
        items = []
        # 相关热播区域
        pattern = r'<li class="fed-list-item[^"]*">.*?<a class="fed-list-pics[^"]*" href="([^"]+)"[^>]*data-original="([^"]+)"[^>]*>.*?<span class="fed-list-score[^"]*">([^<]*)</span>.*?</a>.*?<a class="fed-list-title[^"]*" href="[^"]*" target="[^"]*">([^<]*)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches[:12]:
            href, pic, score, title = match
            if not href or not title:
                continue
            rid = self._extract_vod_id(href)
            items.append({
                "vod_id": str(rid),
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": score.strip() + "分" if score else "",
            })
        
        return {"list": items}

    def destroy(self):
        pass

    # ==================== m3u8 代理与广告过滤（五层管线） ====================

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url or ""), safe="")

    def _is_fake_image_stream(self, text, source_url):
        """第1层：图片流伪装检测"""
        low_url = (source_url or "").lower()
        for sig in ("doyinapi", "svip", "imgcdn", "photo"):
            if sig in low_url:
                return True
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            low = line.lower().split("?")[0]
            if low.endswith((".png", ".jpg", ".jpeg", ".webp")):
                return True
        return False

    def _resolve_main_dir(self, lines, source_url):
        """第3层：正片目录锚点 - KEY URI 目录优先"""
        import posixpath
        parsed = urllib.parse.urlparse(source_url)
        main_dir = posixpath.dirname(parsed.path)
        if not main_dir.endswith("/"):
            main_dir += "/"
        
        # 优先从 KEY URI 取目录
        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            key_uri = m.group(1)
            key_url = key_uri if key_uri.startswith("http") else urllib.parse.urljoin(source_url, key_uri)
            key_path = urllib.parse.urlparse(key_url).path
            key_dir = posixpath.dirname(key_path)
            if key_dir and key_dir != "/":
                return key_dir + "/"
        return main_dir

    def _rewrite_m3u8_tag(self, line, source_url):
        """重写 URI 为绝对地址"""
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

    def _filter_segments(self, lines, source_url, main_dir):
        """第4层：分片过滤"""
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
        """第5层：冗余标签清理"""
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

    def _clean_m3u8_multi(self, lines, source_url):
        """第2层：多码率主表透传"""
        out = []
        for line in lines:
            if line.startswith("#"):
                out.append(line)
                continue
            child = urllib.parse.urljoin(source_url, line)
            if ".m3u8" in child.lower():
                out.append(self._m3u8_proxy_url(child))
            else:
                out.append(child)
        return "\n".join(out) + "\n"

    def _clean_m3u8(self, text, source_url):
        """m3u8 清洗入口 - 五层管线"""
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 第1层：图片流伪装检测
        if self._is_fake_image_stream(text, source_url):
            restored = text
            for ext in (".png", ".jpeg", ".jpg", ".webp"):
                restored = restored.replace(ext, ".ts")
            self.log("检测到图片流伪装，已还原扩展名 -> .ts，跳过广告过滤")
            return restored

        # 第2层：多码率主表
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            return self._clean_m3u8_multi(lines, source_url)

        # 第3层：正片目录锚点
        main_dir = self._resolve_main_dir(lines, source_url)

        # 第4层：分片过滤
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)

        # 第5层：全滤兜底
        if kept == 0 and removed > 0:
            self.log("广告过滤命中全部分片，判定锚点失效，回退为不过滤模式")
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log(f"m3u8已过滤广告分片: {removed}个，保留正片: {kept}个")

        # 第5层：冗余标签清理
        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"

    def localProxy(self, param):
        """localProxy 入口 - 只代理 m3u8，分片直连"""
        try:
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

            # 只处理 m3u8，分片直连
            if b"#EXTM3U" in content[:256]:
                cleaned = self._clean_m3u8(content.decode("utf-8", errors="ignore"), target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

            # 非 m3u8 直接透传（但正常不会走到这里）
            return [200, "application/octet-stream", content]
        except Exception as e:
            return [500, "text/plain", f"localProxy error: {e}".encode("utf-8", errors="ignore")]