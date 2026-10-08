# coding: utf-8
# 站点信息沉淀（法则24）
# 站点名称: 清新萝莉
# 主域名: dcw.qxll8.boats
# 备用域名: 暂无
# 发布页: 无
# 内容类型: 成人影视 (MacCMS风格)
# 特殊说明: 无反爬，直接fetch即可
# 验证时间: 2026-09-04
# 来源: 用户提供
# m3u8结构摘要: 多码率+KEY加密，锚点采用KEY URI目录 /20260902/5K8KbF7k/2000kb/hls/，suspicious_ad_dirs为/a3/20260831/eXGj9tdu/2000kb/hls/和/20260126/VmnacVi8/2000kb/hls/，需要清洗

import json
import re
import urllib.parse
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.extend = ""
        self.host = "https://dcw.qxll8.boats"
        self.base_path = "/cn/home/web"
        
        # 分类硬编码（法则16/17）
        self.classes = [
            {"type_id": "20", "type_name": "亚洲情色"},
            {"type_id": "21", "type_name": "制服师生"},
            {"type_id": "22", "type_name": "卡通动漫"},
            {"type_id": "24", "type_name": "强奸乱伦"},
            {"type_id": "26", "type_name": "中文字幕"},
            {"type_id": "25", "type_name": "偷拍自拍"},
            {"type_id": "27", "type_name": "欧美性爱"},
            {"type_id": "28", "type_name": "人妻熟女"},
            {"type_id": "29", "type_name": "无码专区"},
            {"type_id": "23", "type_name": "三级伦理"},
        ]
        
        # filters空（站内无筛选）
        self.filters = {tid: [] for tid in ["20", "21", "22", "24", "26", "25", "27", "28", "29", "23"]}
        
        # 不加 Accept-Encoding，让沙盒返回原始文本
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        
        # m3u8清洗开关（法则30 + 取证结论）
        # m3u8清洗开关（法则30 + 取证结论）
        # 该站存在广告分片，需要清洗
        self.NEED_CLEAN = True

    def getName(self):
        return "清新萝莉"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            url = self.host + self.base_path + "/index.php/vod/search/by/time_add.html"
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text
            return {"list": self._parse_list(html)}
        except Exception as e:
            self.log({"action": "homeVideoContent", "error": str(e)})
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        try:
            # 注意：分页模板是 id/{page}.html，其中 tid 是分类ID，page 是页码
            # 但实际分类页是 id/{tid}.html，分页是 id/{page}.html
            # 所以第1页用 id/{tid}.html，第2页用 id/2.html
            if int(page) == 1:
                url = self.host + self.base_path + f"/index.php/vod/type/id/{tid}.html"
            else:
                url = self.host + self.base_path + f"/index.php/vod/type/id/{page}.html"
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
            html = resp.text
            items = self._parse_list(html)
            return {
                "list": items,
                "page": int(page),
                "pagecount": 81,
                "limit": 20,
                "total": 81 * 20
            }
        except Exception as e:
            self.log({"action": "categoryContent", "tid": tid, "pg": page, "error": str(e)})
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def _parse_list(self, html):
        """解析视频列表"""
        items = []
        card_pattern = r'<div\s+class="[^"]*video-card[^"]*">(.*?)</div>\s*</div>\s*</div>'
        cards = re.findall(card_pattern, html, re.DOTALL)
        
        for card_html in cards:
            try:
                title_match = re.search(r'<div\s+class="[^"]*video-title[^"]*">\s*<a[^>]*href="[^"]*"[^>]*>(.*?)</a>', card_html, re.DOTALL)
                if not title_match:
                    continue
                title = title_match.group(1).strip()
                if not title:
                    continue
                
                link_match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>', card_html)
                if not link_match:
                    continue
                link = link_match.group(1)
                if not link.startswith("http"):
                    link = self.host + link
                
                vod_id = re.search(r'/vod/(?:play|detail)/id/(\d+)', link)
                if not vod_id:
                    vod_id = re.search(r'/id/(\d+)', link)
                vod_id = vod_id.group(1) if vod_id else ""
                
                img_match = re.search(r'<img[^>]*data-original="([^"]+)"', card_html)
                if not img_match:
                    img_match = re.search(r'<img[^>]*src="([^"]+)"', card_html)
                pic = img_match.group(1) if img_match else ""
                if pic and not pic.startswith("http"):
                    pic = self.host + pic
                
                # 提取备注（分类）- 去掉HTML标签
                remark = ""
                remark_match = re.search(r'<div\s+class="[^"]*video-page[^"]*">\s*<a[^>]*>(.*?)</a>', card_html, re.DOTALL)
                if remark_match:
                    remark = remark_match.group(1).strip()
                    # 去掉可能残留的HTML标签
                    remark = re.sub(r'<[^>]+>', '', remark).strip()
                
                if vod_id and title:
                    items.append({
                        "vod_id": vod_id,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": remark
                    })
            except Exception as e:
                continue
        return items

    def detailContent(self, ids):
        if not ids or not ids[0]:
            return {"list": []}
        vod_id = str(ids[0])
        try:
            # 直接请求播放页（详情页会JS跳转到播放页）
            play_url = self.host + self.base_path + f"/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
            resp = self.fetch(play_url, headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return {"list": []}
            html = resp.text
            
            if not html or len(html) < 100:
                return {"list": []}
            
            # 提取标题
            title = ""
            title_match = re.search(r'<h2>\s*<a[^>]*>(.*?)</a>\s*</h2>', html, re.DOTALL)
            if title_match:
                title = title_match.group(1).strip()
            
            # 提取封面
            pic = ""
            img_match = re.search(r'<img[^>]*src="([^"]+)"[^>]*class="[^"]*float-left[^"]*"', html)
            if img_match:
                pic = img_match.group(1)
                if not pic.startswith("http"):
                    pic = self.host + pic
            
            # 提取分类
            category = ""
            cat_match = re.search(r'所属分类:<a[^>]*href="[^"]*"[^>]*>(.*?)</a>', html)
            if cat_match:
                category = cat_match.group(1).strip()
                # 去掉HTML标签
                category = re.sub(r'<[^>]+>', '', category).strip()
            
            # 提取播放地址（从 player_data）
            play_url_m3u8 = self._extract_m3u8_from_html(html)
            
            if play_url_m3u8:
                vod_play_url = f"第1集${play_url_m3u8}"
                vod_play_from = "线路1"
            else:
                vod_play_url = ""
                vod_play_from = ""
            
            vod = {
                "vod_id": vod_id,
                "vod_name": title or "视频",
                "vod_pic": pic,
                "vod_remarks": category,
                "vod_content": "",
                "vod_play_from": vod_play_from,
                "vod_play_url": vod_play_url
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"action": "detailContent", "ids": ids, "error": str(e)})
            return {"list": []}

    def _extract_m3u8_from_html(self, html):
        """从HTML中提取m3u8播放地址（参考王室日报.py）"""
        if not html:
            return None
        # 方法1: 从 player_data 中提取
        pattern = r'var\s+player_data\s*=\s*(\{[^;]+\});'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                url = data.get("url", "")
                if url and url.startswith("http") and ".m3u8" in url:
                    # 修复：将 \/ 替换为 /
                    url = url.replace("\\/", "/")
                    return url
            except:
                pass
        # 方法2: 直接提取url字段
        pattern2 = r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"'
        match2 = re.search(pattern2, html)
        if match2:
            url = match2.group(1)
            if url and url.startswith("http"):
                url = url.replace("\\/", "/")
                return url
        # 方法3: 查找任何m3u8链接
        pattern3 = r'https?://[^"\'<>]+\.m3u8[^"\'<>]*'
        match3 = re.search(pattern3, html)
        if match3:
            url = match3.group(0)
            url = url.replace("\\/", "/")
            return url
        return None

    def searchContent(self, key, quick, pg="1"):
        if not key or not key.strip():
            return {"list": [], "page": 1}
        try:
            keyword = key.strip()
            url = self.host + self.base_path + f"/index.php/vod/search.html?wd={urllib.parse.quote(keyword)}"
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if not resp or resp.status_code != 200:
                return {"list": [], "page": 1}
            html = resp.text
            items = self._parse_list(html)
            return {"list": items, "page": int(pg)}
        except Exception as e:
            self.log({"action": "searchContent", "key": key, "error": str(e)})
            return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        
        play_url = str(id).strip()
        ua = self.headers.get("User-Agent", "")
        
        if play_url.startswith("http") and ".m3u8" in play_url:
            if self.NEED_CLEAN:
                return {
                    "parse": 0,
                    "url": self._m3u8_proxy_url(play_url),
                    "header": {"User-Agent": ua}
                }
            return {"parse": 0, "url": play_url, "header": {"User-Agent": ua}}
        
        if play_url.startswith(self.host) or "/vod/play/" in play_url:
            try:
                if not play_url.startswith("http"):
                    play_url = self.host + play_url
                resp = self.fetch(play_url, headers=self.headers, timeout=15)
                if resp and resp.status_code == 200:
                    player_match = re.search(r'var player_data\s*=\s*({[^}]+})', resp.text)
                    if player_match:
                        try:
                            data = json.loads(player_match.group(1))
                            m3u8 = data.get("url", "")
                            if m3u8 and ".m3u8" in m3u8:
                                if self.NEED_CLEAN:
                                    return {
                                        "parse": 0,
                                        "url": self._m3u8_proxy_url(m3u8),
                                        "header": {"User-Agent": ua}
                                    }
                                return {"parse": 0, "url": m3u8, "header": {"User-Agent": ua}}
                        except:
                            pass
            except Exception as e:
                self.log({"action": "playerContent_parse", "error": str(e)})
        
        return {
            "parse": 1,
            "url": play_url,
            "header": {
                "User-Agent": ua,
                "Referer": self.host + self.base_path + "/"
            }
        }

    def _m3u8_proxy_url(self, url):
        if not url:
            return ""
        return self.getProxyUrl() + "?do=py&url=" + urllib.parse.quote(str(url), safe="")

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def localProxy(self, param):
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
            
            h = self.headers.copy()
            h["Accept"] = "application/vnd.apple.mpegurl, */*"
            resp = self.fetch(target, headers=h, timeout=20)
            if not resp or resp.status_code != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]
            
            content = getattr(resp, "content", b"") or b""
            if not content and getattr(resp, "text", ""):
                content = resp.text.encode("utf-8", errors="ignore")
            if not content:
                return [502, "text/plain", b"empty content"]
            
            if b"#EXTM3U" not in content[:256]:
                return [502, "text/plain", b"invalid m3u8"]
            
            text = content.decode("utf-8", errors="ignore")
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log({"action": "localProxy", "error": str(e)})
            return [500, "text/plain", f"localProxy error: {e}".encode("utf-8", errors="ignore")]

    def _clean_m3u8(self, text, source_url):
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"
        
        # ---- 第1层：图片流伪装检测 ----
        # 注意：图片流伪装的分片是正片，只是扩展名被伪装成图片格式
        # 所以只还原扩展名，不跳过后续过滤
        if self._is_fake_image_stream(text, source_url):
            # 还原扩展名：.jpg/.png/.jpeg/.webp -> .ts
            restored = text
            for ext in (".png", ".jpeg", ".jpg", ".webp"):  # .jpeg先于.jpg
                restored = restored.replace(ext, ".ts")
            # 更新text为还原后的内容，继续执行后续过滤
            text = restored
            lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
            self.log("检测到图片流伪装，已还原扩展名 -> .ts，继续执行广告过滤")
            if not lines:
                return "#EXTM3U\n"
            # 继续往下走，不return
        
        # ---- 第2层：多码率主表透传 ----
        # ---- 第2层：多码率主表透传 ----
        # 如果主表包含 #EXT-X-STREAM-INF，说明是多码率
        # 需要将子流地址代理，让播放器请求子流时再走清洗
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    # 子流地址补全为绝对地址，走代理
                    child = urllib.parse.urljoin(source_url, line)
                    if ".m3u8" in child.lower():
                        # 子流走代理，代理会再次进入 localProxy 并清洗
                        out.append(self._m3u8_proxy_url(child))
                    else:
                        out.append(child)
            return "\n".join(out) + "\n"
        
        main_dir = self._resolve_main_dir(lines, source_url)
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)
        
        if removed > 0 and (kept == 0 or removed > kept):
            self.log(f"广告过滤命中过多分片(滤{removed}/留{kept})，判定锚点失效，回退为不过滤模式")
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"
        
        if removed:
            self.log(f"m3u8已过滤广告分片: {removed}个，保留正片: {kept}个")
        
        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"

    def _is_fake_image_stream(self, text, source_url):
        """检测图片流伪装 - 只有分片扩展名为图片格式时才判定为True"""
        # 先检查分片扩展名
        has_ts = False
        has_image_ext = False
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            low = line.lower().split("?")[0]
            if low.endswith((".ts", ".m4s")):
                has_ts = True
            elif low.endswith((".png", ".jpg", ".jpeg", ".webp")):
                has_image_ext = True
        
        # 只有存在图片格式分片且不存在ts/m4s分片时，才判定为图片流
        if has_image_ext and not has_ts:
            return True
        
        # 域名特征作为辅助（但优先级低于分片扩展名）
        low_url = (source_url or "").lower()
        # 仅当域名包含图片服务商特征且分片中没有ts时
        if "imgcdn" in low_url or "doyinapi" in low_url:
            if not has_ts:
                return True
        
        return False

    def _resolve_main_dir(self, lines, source_url):
        """解析正片目录锚点（KEY URI优先）"""
        import posixpath
        parsed = urllib.parse.urlparse(source_url)
        main_dir = posixpath.dirname(parsed.path)
        if not main_dir.endswith("/"):
            main_dir += "/"
        
        # 优先以KEY URI目录为锚点
        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            key_uri = m.group(1)
            # 处理相对路径
            if not key_uri.startswith("http"):
                key_uri = urllib.parse.urljoin(source_url, key_uri)
            key_path = urllib.parse.urlparse(key_uri).path
            key_dir = posixpath.dirname(key_path)
            if key_dir and key_dir != "/":
                # KEY目录就是正片目录
                return key_dir + "/"
        # 无KEY时回退到m3u8目录
        return main_dir

    def _filter_segments(self, lines, source_url, main_dir):
        """分片过滤：保留正片目录下的分片"""
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
                # 判断分片是否在正片目录下
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
        
        if pending:
            segments.extend(pending)
        
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

    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass