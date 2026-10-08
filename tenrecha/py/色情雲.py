# coding: utf-8
import re
import json
from urllib.request import urlopen, Request
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://porncloud.tv"
        self.classes = [
            {"type_id": "jav", "type_name": "JAV视频"},
            {"type_id": "global", "type_name": "全球资源"},
            {"type_id": "domestic", "type_name": "国产资源"},
            {"type_id": "domestic-spy", "type_name": "国产偷拍"},
            {"type_id": "influencer", "type_name": "网红福利姬"},
            {"type_id": "photo-sets", "type_name": "写真套图"},
            {"type_id": "onlyfans", "type_name": "OnlyFans"},
            {"type_id": "black-stockings", "type_name": "黑丝"},
            {"type_id": "coser", "type_name": "Coser"},
            {"type_id": "private-video", "type_name": "私拍"},
            {"type_id": "one-to-one", "type_name": "1对1"},
        ]
        self.filters = {c["type_id"]: [] for c in self.classes}
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        self.type_map = {
            "photo-sets": "photo_set",
            "jav": "video",
            "global": "video",
            "domestic": "video",
            "domestic-spy": "video",
            "influencer": "video",
            "onlyfans": "video",
            "black-stockings": "video",
            "coser": "video",
            "private-video": "video",
            "one-to-one": "video",
        }

    def init(self, extend):
        pass

    def _fetch(self, url, headers=None):
        try:
            req = Request(url, headers=headers or {"User-Agent": self.ua})
            with urlopen(req, timeout=15) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except:
            return ""

    def _fix_url(self, url):
        if not url: return ""
        if url.startswith("//"): return "https:" + url
        if url.startswith("/"): return self.host + url
        if not url.startswith("http"): return self.host + "/" + url
        return url

    def _extract_images(self, html):
        images = []
        patterns = [
            r'<img[^>]+src="([^"]+\.(?:jpg|jpeg|png|gif|webp)[^"]*)"',
            r'<img[^>]+data-src="([^"]+\.(?:jpg|jpeg|png|gif|webp)[^"]*)"',
            r'<img[^>]+data-original="([^"]+\.(?:jpg|jpeg|png|gif|webp)[^"]*)"',
            r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
        ]
        seen = set()
        for pattern in patterns:
            for match in re.finditer(pattern, html, re.I):
                url = match.group(1)
                if 'logo' in url.lower() or 'icon' in url.lower():
                    continue
                if url and url not in seen and not url.startswith('data:'):
                    seen.add(url)
                    images.append(self._fix_url(url))
        return images

    def _parse_pay_status(self, html, target_id=None):
        pay_map = {}
        try:
            nuxt_match = re.search(r'<script[^>]+id="__NUXT_DATA__"[^>]*>([^<]+)</script>', html)
            if nuxt_match:
                data_str = nuxt_match.group(1)
                nuxt_data = json.loads(data_str)
                def find_items(obj):
                    if isinstance(obj, dict):
                        if "items" in obj and isinstance(obj["items"], list):
                            return obj["items"]
                        for v in obj.values():
                            result = find_items(v)
                            if result:
                                return result
                    elif isinstance(obj, list):
                        for item in obj:
                            result = find_items(item)
                            if result:
                                return result
                    return None
                
                items = find_items(nuxt_data)
                if items and isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            vid = item.get("id")
                            is_free = item.get("isFree")
                            if vid and is_free is not None:
                                pay_map["/media/" + vid] = is_free
                                pay_map["/play/" + vid] = is_free
                                if target_id and vid == target_id:
                                    return not is_free
        except:
            pass
        return pay_map

    def _parse_videos(self, html, content_type="video"):
        videos = []
        pay_map = self._parse_pay_status(html)
        
        pattern = r'<a[^>]+href="(/(?:play|media)/[^"]+)"[^>]*>'
        for match in re.finditer(pattern, html):
            href = match.group(1)
            if not href or href == "/play/" or href == "/media/":
                continue
            if "/category/" in href or "/tag/" in href:
                continue
            
            block_start = max(0, match.start() - 1000)
            block_end = min(len(html), match.end() + 1000)
            block = html[block_start:block_end]
            
            title = ""
            alt_match = re.search(r'alt="([^"]+)"', block)
            if alt_match:
                title = alt_match.group(1)
            if not title:
                text_match = re.search(r'>([^<]+)<', match.group(0))
                if text_match:
                    title = text_match.group(1).strip()
            if not title:
                title = href.split("/")[-1]
            
            pic = ""
            img_patterns = [
                r'<img[^>]+src="([^"]+)"',
                r'<img[^>]+data-src="([^"]+)"',
                r'<img[^>]+data-original="([^"]+)"',
            ]
            for p in img_patterns:
                img_match = re.search(p, block, re.I)
                if img_match:
                    pic = img_match.group(1).strip('"\'')
                    if pic and not pic.startswith("data:"):
                        break
            
            is_pay = False
            if href in pay_map:
                is_pay = not pay_map[href]
            if not is_pay:
                if '付费会员' in block or 'lock-badge' in block or '登录查看' in block:
                    is_pay = True
            
            remark = "🔒 VIP付费" if is_pay else "免费"
            
            if title:
                vod_id_with_type = f"{content_type}@@{href}"
                videos.append({
                    "vod_id": vod_id_with_type,
                    "vod_name": title.strip(),
                    "vod_pic": self._fix_url(pic),
                    "vod_remarks": remark
                })
        
        seen = set()
        result = []
        for v in videos:
            if v["vod_id"] not in seen:
                seen.add(v["vod_id"])
                result.append(v)
        return result

    def homeVideoContent(self):
        html = self._fetch(self.host)
        videos = self._parse_videos(html, "video")
        return {"list": videos[:40]}

    def homeContent(self, filter=False):
        html = self._fetch(self.host)
        videos = self._parse_videos(html, "video")
        return {"class": self.classes, "filters": self.filters, "list": videos[:40]}

    def categoryContent(self, tid, pg, filter=False, extend={}):
        pg = int(pg) if str(pg).isdigit() else 1
        url_map = {
            "jav": "/jav-list",
            "global": "/media",
            "domestic": "/media/category/domestic",
            "domestic-spy": "/media/category/domestic-spy",
            "influencer": "/media/category/influencer",
            "photo-sets": "/media/category/photo-sets",
            "onlyfans": "/media/tag/onlyfans",
            "black-stockings": "/media/tag/black-stockings",
            "coser": "/media/tag/coser",
            "private-video": "/media/tag/private-video",
            "one-to-one": "/media/tag/one-to-one",
        }
        path = url_map.get(tid, "/media")
        url = self.host + path + "?page=" + str(pg)
        html = self._fetch(url)
        content_type = self.type_map.get(tid, "video")
        videos = self._parse_videos(html, content_type)
        return {"list": videos, "page": pg, "pagecount": 100, "limit": 20, "total": len(videos)}

    def detailContent(self, ids):
        result = []
        if isinstance(ids, str):
            ids = [ids]
        for vid_with_type in ids:
            if '@@' in vid_with_type:
                content_type, vid = vid_with_type.split('@@', 1)
            else:
                content_type = "video"
                vid = vid_with_type
            
            if not vid.startswith("/"):
                vid = "/" + vid
            
            url = self._fix_url(vid)
            html = self._fetch(url)
            title = ""
            desc = ""
            pic = ""
            play_url = ""
            
            current_id = vid.split("/")[-1]
            
            is_pay = False
            try:
                nuxt_match = re.search(r'<script[^>]+id="__NUXT_DATA__"[^>]*>([^<]+)</script>', html)
                if nuxt_match:
                    data_str = nuxt_match.group(1)
                    nuxt_data = json.loads(data_str)
                    def find_video(obj, target_id):
                        if isinstance(obj, dict):
                            if "id" in obj and str(obj.get("id")) == str(target_id):
                                return obj
                            for v in obj.values():
                                result = find_video(v, target_id)
                                if result:
                                    return result
                        elif isinstance(obj, list):
                            for item in obj:
                                result = find_video(item, target_id)
                                if result:
                                    return result
                        return None
                    
                    video_data = find_video(nuxt_data, current_id)
                    if video_data and isinstance(video_data, dict):
                        is_free = video_data.get("isFree")
                        if is_free is not None:
                            is_pay = not is_free
            except:
                pass
            
            ld_pattern = r'<script type="application/ld\+json">([^<]+)</script>'
            for match in re.finditer(ld_pattern, html):
                try:
                    data = json.loads(match.group(1))
                    if isinstance(data, dict):
                        if data.get("@type") == "VideoObject":
                            play_url = data.get("contentUrl") or ""
                            if not pic:
                                thumbs = data.get("thumbnailUrl")
                                if thumbs and isinstance(thumbs, list) and thumbs:
                                    pic = thumbs[0]
                            if not title:
                                title = data.get("name") or ""
                            if not desc:
                                desc = data.get("description") or ""
                except:
                    pass
            
            if not play_url:
                og_match = re.search(r'<meta[^>]+property="og:video"[^>]+content="([^"]+)"', html)
                if og_match:
                    play_url = og_match.group(1)
            if not title:
                h1_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
                if h1_match:
                    title = h1_match.group(1).strip()
            if not title:
                title_match = re.search(r'<title>色情云 PornCloud - ([^<]+)</title>', html)
                if title_match:
                    title = title_match.group(1).strip()
            if not pic:
                og_img = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
                if og_img:
                    pic = og_img.group(1)
            if not desc:
                desc_match = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html)
                if desc_match:
                    desc = desc_match.group(1)
            
            # ====== 判断是否为写真套图 ======
            is_photo_set = False
            
            if content_type == "photo_set":
                is_photo_set = True
            elif '/photo-sets' in vid:
                is_photo_set = True
            elif not play_url:
                # 从页面内容判断
                if re.search(r'套图|写真|图集|图片|图库', html):
                    img_urls = re.findall(r'<img[^>]+src="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', html, re.I)
                    large_images = []
                    for u in img_urls:
                        if 'cover' not in u.lower() and 'logo' not in u.lower() and 'icon' not in u.lower():
                            large_images.append(u)
                    if len(large_images) >= 5:
                        is_photo_set = True
            
            if is_photo_set:
                images = self._extract_images(html)
                if not images and pic:
                    images = [pic]
                if images:
                    play_url = "全集$pics@@" + "&&".join(images)
                    remark = "🔒 VIP付费" if is_pay else "免费"
                    result.append({
                        "vod_id": vid,
                        "vod_name": title or vid.split("/")[-1],
                        "vod_pic": self._fix_url(pic),
                        "vod_content": desc or "",
                        "vod_remarks": remark,
                        "vod_play_from": "写真套图",
                        "vod_play_url": play_url
                    })
                    continue
            
            # ====== 视频处理 ======
            if not play_url:
                m3u8_match = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html)
                if m3u8_match:
                    play_url = m3u8_match.group(0)
            
            remark = "🔒 VIP付费" if is_pay else "免费"
            display_title = title or vid.split("/")[-1]
            
            if play_url:
                play_url = "播放$" + play_url
            else:
                play_url = "播放$sniff@@" + vid
            
            result.append({
                "vod_id": vid,
                "vod_name": display_title,
                "vod_pic": self._fix_url(pic),
                "vod_content": desc or "",
                "vod_remarks": remark,
                "vod_play_from": "PornCloud",
                "vod_play_url": play_url
            })
        return {"list": result}

    def searchContent(self, key, quick=False, pg="1"):
        pg = int(pg) if str(pg).isdigit() else 1
        search_url = self.host + "/search/" + key.replace(" ", "+")
        if pg > 1:
            search_url += "?page=" + str(pg)
        html = self._fetch(search_url)
        videos = self._parse_videos(html, "video")
        total = len(videos)
        pagecount = 1
        page_match = re.search(r'pagecount["\']?\s*[:=]\s*(\d+)', html)
        if page_match:
            pagecount = int(page_match.group(1))
        return {"list": videos, "page": pg, "pagecount": pagecount, "limit": 20, "total": total}

    def playerContent(self, flag, id, vipFlags=None):
        if id.startswith("pics@@"):
            return {
                "parse": 0,
                "url": "pics://" + id.replace("pics@@", "", 1),
                "header": {
                    "User-Agent": self.ua,
                    "Referer": self.host + "/"
                }
            }
        
        if id.startswith("sniff@@"):
            url = id.replace("sniff@@", "", 1)
            if not url.startswith("http"):
                url = self.host + url
            return {
                "parse": 1,
                "url": url,
                "header": {
                    "User-Agent": self.ua,
                    "Referer": self.host + "/"
                }
            }
        
        if id.startswith("http"):
            return {
                "parse": 0,
                "url": id,
                "header": {
                    "User-Agent": self.ua,
                    "Referer": self.host + "/"
                }
            }
        
        vid = id.split("/")[-1]
        play_page_url = self.host + "/play/" + vid
        html = self._fetch(play_page_url)
        play_url = ""
        
        ld_pattern = r'<script type="application/ld\+json">([^<]+)</script>'
        for match in re.finditer(ld_pattern, html):
            try:
                data = json.loads(match.group(1))
                if isinstance(data, dict) and data.get("@type") == "VideoObject":
                    play_url = data.get("contentUrl") or ""
                    break
            except:
                pass
        
        if not play_url:
            m3u8_match = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html)
            if m3u8_match:
                play_url = m3u8_match.group(0)
        
        if play_url:
            return {
                "parse": 0,
                "url": play_url,
                "header": {
                    "User-Agent": self.ua,
                    "Referer": self.host + "/"
                }
            }
        
        return {
            "parse": 1,
            "url": play_page_url,
            "header": {
                "User-Agent": self.ua,
                "Referer": self.host + "/"
            }
        }

    def localProxy(self, params):
        """
        M3U8 代理 - 将相对路径转换为绝对路径
        """
        if not params:
            return None
        
        url = params.get("url") or params.get("src") or ""
        if not url or ".m3u8" not in url:
            return None
        
        try:
            # 请求原始 m3u8
            req = Request(url, headers={
                "User-Agent": self.ua,
                "Referer": self.host + "/"
            })
            with urlopen(req, timeout=15) as resp:
                content = resp.read().decode('utf-8')
            
            # 基础 URL（用于补全相对路径）
            base_url = url.rsplit("/", 1)[0] + "/"
            
            lines = content.split("\n")
            new_lines = []
            
            for line in lines:
                line = line.strip()
                
                # 处理 #EXT-X-MAP:URI
                if line.startswith("#EXT-X-MAP:URI="):
                    match = re.search(r'URI="([^"]+)"', line)
                    if match:
                        map_url = match.group(1)
                        if not map_url.startswith("http"):
                            map_url = base_url + map_url
                        new_lines.append('#EXT-X-MAP:URI="' + map_url + '"')
                    else:
                        new_lines.append(line)
                
                # 处理 #EXT-X-DISCONTINUITY-SEQUENCE 等
                elif line.startswith("#"):
                    new_lines.append(line)
                
                # 处理分片文件（非注释行）
                elif line and not line.startswith("#"):
                    if not line.startswith("http"):
                        line = base_url + line
                    new_lines.append(line)
                
                else:
                    new_lines.append(line)
            
            # 返回处理后的 m3u8
            result_content = "\n".join(new_lines) + "\n"
            return [
                200,
                "application/vnd.apple.mpegurl",
                result_content.encode("utf-8")
            ]
            
        except Exception as e:
            print("localProxy error:", e)
            return None

    def getDependence(self):
        return []

    def destroy(self):
        pass