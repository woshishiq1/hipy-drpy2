from base.spider import Spider
import re, json, requests, random, string, time
from urllib.parse import quote, urlsplit, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://netfapx.net"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.siteUrl,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        }
        self.session = requests.Session()

    def getName(self):
        return "NetFapX"

    def init(self, extend=""):
        pass

    def fix_url(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.siteUrl + url
        return url

    def _clean_url(self, u):
        """HTML 反转义 + JSON \/ 反转义"""
        return unescape(u).replace('\\/', '/').strip()

    def _is_video_url(self, u):
        """判断 URL 是否为视频直链 (排除图片等)"""
        if not u or not u.startswith('http'):
            return False
        ul = u.lower()
        if re.search(r'\.(?:jpg|jpeg|png|gif|webp|bmp|svg|ico)(?:\?|$)', ul):
            return False
        if 'cloudatacdn' in ul or 'doodcdn' in ul:
            return True
        if re.search(r'\.(?:mp4|m3u8|flv|ts|mkv|avi)(?:\?|$)', ul):
            return True
        return False

    def _extract_video_url(self, html):
        """从视频页面 HTML 中提取真实播放地址 (支持 JS 动态加载 + DoodStream)"""
        # 1. <video> / <source> 标签 src (DoodStream 直连 CDN URL 无扩展名, 需直接返回)
        for pat in [
            r'<video[^>]*\ssrc=["\']([^"\']+)["\']',
            r'<source[^>]*\ssrc=["\']([^"\']+)["\']',
            r'<video[^>]*\sdata-src=["\']([^"\']+)["\']',
            r'<source[^>]*\sdata-src=["\']([^"\']+)["\']',
        ]:
            m = re.search(pat, html, re.I)
            if m:
                u = self._clean_url(m.group(1))
                if u.startswith('http') and ('cloudatacdn' in u.lower() or 'doodcdn' in u.lower()):
                    return u
                if re.search(r'\.(?:mp4|m3u8|flv|ts|mkv|avi)(?:\?|$)', u, re.I):
                    return u

        # 2. data-* 属性中的视频地址
        for attr in ['data-video-url', 'data-video-src', 'data-video', 'data-src', 'data-url', 'data-file', 'data-hls', 'data-stream', 'data-mp4', 'data-source']:
            m = re.search(rf'{attr}=["\']([^"\']+)["\']', html, re.I)
            if m:
                u = self._clean_url(m.group(1))
                if u.startswith('http') and ('cloudatacdn' in u.lower() or 'doodcdn' in u.lower()):
                    return u
                if re.search(r'\.(?:mp4|m3u8|flv|ts)(?:\?|$)', u, re.I):
                    return u

        # 3. meta 标签
        for prop in ['og:video', 'og:video:url', 'og:video:secure_url', 'twitter:player:stream']:
            m = re.search(rf'<meta[^>]*property=["\']({re.escape(prop)})["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
            if m:
                u = self._clean_url(m.group(2))
                if self._is_video_url(u):
                    return u

        # 4. JSON-LD 结构化数据
        m = re.search(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.S | re.I)
        if m:
            for url_pat in [r'"contentUrl"\s*:\s*"([^"]+)"', r'"embedUrl"\s*:\s*"([^"]+)"', r'"url"\s*:\s*"(https?://[^"]+\.(?:mp4|m3u8)[^"]*)"']:
                um = re.search(url_pat, m.group(1), re.I)
                if um:
                    u = self._clean_url(um.group(1))
                    if self._is_video_url(u):
                        return u

        # 5. JavaScript 变量 (最常见的动态加载方式)
        for var_name in ['videoUrl', 'video_url', 'videourl', 'file', 'mp4', 'url', 'src', 'source', 'video', 'hls', 'stream', 'videoSrc', 'videoLink', 'playUrl', 'play_url', 'videoFile', 'videoSource', 'sourceUrl']:
            patterns = [
                rf'(?:var|let|const)\s+{var_name}\s*=\s*["\']([^"\']+)["\']',
                rf'{var_name}\s*[:=]\s*["\']([^"\']+)["\']',
            ]
            for pat in patterns:
                m = re.search(pat, html, re.I)
                if m:
                    u = self._clean_url(m.group(1))
                    if re.search(r'\.(?:mp4|m3u8|flv|ts)(?:\?|$)', u, re.I):
                        return u

        # 6. JS 对象中的 file/src/sources
        for obj_pat in [
            r'"file"\s*:\s*"(https?://[^"]+)"',
            r'"src"\s*:\s*"(https?://[^"]+\.(?:mp4|m3u8)[^"]*)"',
            r'"source"\s*:\s*"(https?://[^"]+)"',
            r'"url"\s*:\s*"(https?://[^"]+\.(?:mp4|m3u8)[^"]*)"',
            r'"video"\s*:\s*"(https?://[^"]+)"',
        ]:
            m = re.search(obj_pat, html, re.I)
            if m:
                u = self._clean_url(m.group(1))
                if self._is_video_url(u):
                    return u

        # 7. 兜底: 在整个 HTML 中搜索 CDN/视频 URL
        for ext_pat in [
            r'(https?://[^\s"\'<>+]*cloudatacdn[^\s"\'<>+]*)',
            r'(https?://[^\s"\'<>+]*doodcdn[^\s"\'<>]+\.mp4[^\s"\'<>+]*)',
            r'(https?://[^\s"\'<>+]+\.mp4[^\s"\'<>+]*)',
            r'(https?://[^\s"\'<>+]+\.m3u8[^\s"\'<>+]*)',
            r'(https?://[^\s"\'<>+]+\.flv[^\s"\'<>+]*)',
        ]:
            urls = re.findall(ext_pat, html, re.I)
            for u in urls:
                u = self._clean_url(u)
                if 'netfapx' not in u.lower() and len(u) > 30:
                    return u

        # 8. 解码 eval-packed JavaScript (LuluStream JW Player 等)
        decoded = self._unpack_eval_js(html)
        if decoded:
            for dm in re.finditer(r'(https?://[^\s"\']+\.(?:m3u8|mp4)[^\s"\']*)', decoded, re.I):
                u = self._clean_url(dm.group(1))
                if self._is_video_url(u):
                    return u
            for dm in re.finditer(r'file\s*:\s*["\']([^"\']+)["\']', decoded, re.I):
                u = self._clean_url(dm.group(1))
                if self._is_video_url(u):
                    return u

        return ""

    def _unpack_eval_js(self, html):
        """解码 eval(function(p,a,c,k,e,d){...}) 格式的混淆 JavaScript"""
        m = re.search(
            r"eval\(function\(p,a,c,k,e,d\)\{.*?\}\('(.*?)',(\d+),(\d+),'(.*?)'\.split",
            html, re.S
        )
        if not m:
            return ""
        packed = m.group(1)
        base = int(m.group(2))
        keys = m.group(4).split('|')

        def replace_token(match):
            token = match.group(0)
            try:
                idx = int(token, base)
                if 0 <= idx < len(keys) and keys[idx]:
                    return keys[idx]
            except ValueError:
                pass
            return token

        return re.sub(r'\b[0-9a-zA-Z]+\b', replace_token, packed)

    def _doodstream_resolve(self, page_html, final_url):
        """DoodStream pass_md5 解析: 获取 base CDN URL → 生成 makePlay() 后缀 → 组合最终直链"""
        # 1. 提取 token (从 pass_md5 路径或 makePlay 函数)
        token = ""
        pm = re.search(r'/pass_md5/[a-zA-Z0-9\-]+/([a-zA-Z0-9]+)', page_html)
        if pm:
            token = pm.group(1)
        if not token:
            pm = re.search(r'\?token=([a-zA-Z0-9]+)&expiry=', page_html)
            if pm:
                token = pm.group(1)
        if not token:
            return ""

        # 2. 提取 pass_md5 完整路径
        pm = re.search(r'/pass_md5/([a-zA-Z0-9\-]+/[a-zA-Z0-9]+)', page_html)
        if not pm:
            return ""
        pass_path = '/pass_md5/' + pm.group(1)

        # 3. 请求 pass_md5 获取 base CDN URL
        base = urlsplit(final_url)
        pass_url = f"{base.scheme}://{base.netloc}{pass_path}"
        r = self.session.get(pass_url, headers={
            **self.headers,
            "Referer": final_url,
            "X-Requested-With": "XMLHttpRequest",
        }, timeout=10, verify=False)
        data = r.text.strip()
        if not data or data == "RELOAD" or not data.startswith('http'):
            return ""

        # 4. 生成 makePlay() 后缀: 10位随机字母数字 + ?token=xxx&expiry=时间戳
        random_chars = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        expiry = str(int(time.time() * 1000))
        make_play_suffix = random_chars + f"?token={token}&expiry={expiry}"

        # 5. 组合最终 URL
        return data + make_play_suffix

    def _extract_videos(self, html):
        items = []
        seen = set()
        for m in re.finditer(r'<article\b[^>]*>(.*?)</article>', html, re.S | re.I):
            full = m.group(0)
            block = m.group(1)
            vid = ""
            vm = re.search(r'data-post-id=["\'](\d+)["\']', full, re.I)
            if vm:
                vid = vm.group(1)
            if not vid:
                vm = re.search(r'data-video-id=["\']video_(\d+)["\']', full, re.I)
                if vm:
                    vid = vm.group(1)
            if not vid:
                vm = re.search(r'post-(\d+)(?:\s|"|>)', full, re.I)
                if vm:
                    vid = vm.group(1)
            if not vid:
                vm = re.search(r'href=["\'][^"\']*/watch/(\d+)/["\']', block, re.I)
                if vm:
                    vid = vm.group(1)
            if not vid or vid in seen:
                continue
            seen.add(vid)
            href = ""
            hm = re.search(r'<a\b[^>]*href=["\']([^"\']+)["\']', block, re.I)
            if hm:
                href = hm.group(1)
            title = ""
            tm = re.search(r'<a\b[^>]*title=["\']([^"\']+)["\']', block, re.I)
            if tm:
                title = tm.group(1).strip()
            else:
                tm = re.search(r'<span[^>]*>([^<]+)</span>', block, re.I)
                if tm:
                    title = tm.group(1).strip()
            pic = ""
            pm = re.search(r'data-main-thumb=["\']([^"\']+)["\']', full, re.I)
            if not pm:
                pm = re.search(r'<img\b[^>]*src=["\']([^"\']+)["\']', block, re.I)
            if not pm:
                pm = re.search(r'<img\b[^>]*data-src=["\']([^"\']+)["\']', block, re.I)
            if pm:
                pic = pm.group(1)
            remarks = ""
            rm = re.search(r'<span\b[^>]*class=["\'][^"\']*duration[^"\']*["\'][^>]*>(.*?)</span>', block, re.I)
            if rm:
                remarks = re.sub(r'<[^>]+>', '', rm.group(1)).strip()
            if not remarks:
                rm = re.search(r'<i\b[^>]*fa-clock-o[^>]*></i>\s*([^<]+)', block, re.I)
                if rm:
                    remarks = rm.group(1).strip()
            items.append({"vod_id": vid, "vod_name": title, "vod_pic": self.fix_url(pic), "vod_remarks": remarks})
        if not items:
            for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+/watch/(\d+)/)["\'][^>]*title=["\']([^"\']+)["\'][^>]*>.*?<img\b[^>]*src=["\']([^"\']+)["\']', html, re.S | re.I):
                vid = m.group(2)
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                title = m.group(3).strip()
                pic = m.group(4)
                items.append({"vod_id": vid, "vod_name": title, "vod_pic": self.fix_url(pic), "vod_remarks": ""})
        return items

    def _parse_pagination(self, html):
        pagecount = 1
        pm = re.search(r'href=["\'][^"\']*/page/(\d+)/["\'][^>]*>Last</a>', html, re.I)
        if pm:
            pagecount = int(pm.group(1))
        else:
            for m in re.finditer(r'href=["\'][^"\']*/page/(\d+)/["\']', html, re.I):
                p = int(m.group(1))
                if p > pagecount:
                    pagecount = p
        return pagecount

    # playmogo.com 及其所有代理域名 (有 Cloudflare Turnstile 验证码)
    CAPTCHA_DOMAINS = ('dsvplay.com', 'myvidplay.com', 'luluvid.com',
                       'vide0.net', 'vidply.com', 'do7go.com', 'playmogo.com')

    def _is_captcha_embed(self, iframe_url):
        """检查 iframe URL 是否指向 CAPTCHA 保护的平台"""
        low = iframe_url.lower()
        return any(d in low for d in self.CAPTCHA_DOMAINS)

    def _check_category_platform(self, tid):
        """检查分类的第一个视频是否使用 CAPTCHA 平台, 返回 (tid, True=可用)"""
        try:
            cat = self.categoryContent(tid, "1", {}, {})
            vids = cat.get("list", [])
            if not vids:
                return (tid, False)
            detail = self.detailContent([vids[0].get("vod_id")])
            dlist = detail.get("list", [])
            if not dlist:
                return (tid, False)
            play_url = dlist[0].get("vod_play_url", "")
            iframe = play_url.split("$", 1)[1] if "$" in play_url else ""
            if not iframe:
                return (tid, False)
            iframe = unquote(unescape(iframe))
            return (tid, not self._is_captcha_embed(iframe))
        except Exception:
            return (tid, False)

    def _extract_tags(self, html):
        """从首页 article 中提取标签子分类"""
        tags = []
        seen = set()
        for m in re.finditer(r'<article\b[^>]*>(.*?)</article>', html, re.S | re.I):
            block = m.group(1)
            sm = re.search(r'\?s=([^&"]+)', block)
            if sm:
                tag_raw = unquote(sm.group(1)).replace('+', ' ').strip()
                if tag_raw and tag_raw.lower() not in seen:
                    seen.add(tag_raw.lower())
                    tag_id = quote(tag_raw)
                    tag_name = tag_raw.title()
                    tags.append({"type_id": f"tag:{tag_id}", "type_name": tag_name})
        return tags

    def _extract_channels(self, html):
        """从 /categories/ 页面提取频道子分类"""
        channels = []
        seen = set()
        for m in re.finditer(r'<a[^>]*href=["\']([^"\']*/latest-videos/([^/]+)/)["\']', html, re.I):
            href, slug = m.group(1), m.group(2)
            if slug and slug.lower() not in seen and not slug.isdigit():
                seen.add(slug.lower())
                name = slug.replace('-', ' ').title()
                channels.append({"type_id": f"channel:{slug}", "type_name": name})
        return channels

    def homeContent(self, filter):
        result = {"class": [], "list": []}
        # 主分类: 只保留无 CAPTCHA 的 latest 和 random
        result["class"] = [
            {"type_id": "latest", "type_name": "Latest Videos"},
            {"type_id": "random", "type_name": "Random Videos"}
        ]
        all_subcats = []
        try:
            r = self.session.get(self.siteUrl, headers=self.headers, timeout=10, verify=False)
            r.raise_for_status()
            all_subcats.extend(self._extract_tags(r.text))
        except Exception:
            pass
        try:
            r2 = self.session.get(f"{self.siteUrl}/categories/", headers=self.headers, timeout=10, verify=False)
            r2.raise_for_status()
            all_subcats.extend(self._extract_channels(r2.text))
        except Exception:
            pass
        # 并行检查子分类: 过滤掉视频跳转到 playmogo.com (CAPTCHA) 的
        if all_subcats:
            valid_tids = set()
            with ThreadPoolExecutor(max_workers=10) as pool:
                futures = {pool.submit(self._check_category_platform, c["type_id"]): c["type_id"] for c in all_subcats}
                for f in as_completed(futures, timeout=60):
                    try:
                        tid, ok = f.result(timeout=30)
                        if ok:
                            valid_tids.add(tid)
                    except Exception:
                        pass
            result["class"].extend(c for c in all_subcats if c["type_id"] in valid_tids)
        try:
            r3 = self.session.get(f"{self.siteUrl}/latest-videos/", headers=self.headers, timeout=10, verify=False)
            r3.raise_for_status()
            result["list"] = self._extract_videos(r3.text)[:12]
        except Exception:
            pass
        return result

    def homeVideoContent(self):
        try:
            r = self.session.get(f"{self.siteUrl}/latest-videos/", headers=self.headers, timeout=10, verify=False)
            return {"list": self._extract_videos(r.text)[:12]}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(str(pg)), "pagecount": 1, "limit": 24, "total": 0}
        try:
            pg = int(str(pg))
            if tid == "latest":
                url = f"{self.siteUrl}/latest-videos/" if pg == 1 else f"{self.siteUrl}/latest-videos/page/{pg}/"
            elif tid in ("popular", "longest", "random"):
                url = f"{self.siteUrl}/?filter={tid}" if pg == 1 else f"{self.siteUrl}/page/{pg}/?filter={tid}"
            elif tid.startswith("tag:"):
                tag = unquote(tid[4:])
                url = f"{self.siteUrl}/?s={quote(tag)}&filter=latest" if pg == 1 else f"{self.siteUrl}/page/{pg}/?s={quote(tag)}&filter=latest"
            elif tid.startswith("channel:"):
                slug = tid[8:]
                url = f"{self.siteUrl}/latest-videos/{slug}/" if pg == 1 else f"{self.siteUrl}/latest-videos/{slug}/page/{pg}/"
            else:
                url = f"{self.siteUrl}/?filter={tid}" if pg == 1 else f"{self.siteUrl}/page/{pg}/?filter={tid}"
            r = self.session.get(url, headers=self.headers, timeout=10, verify=False)
            r.raise_for_status()
            result["list"] = self._extract_videos(r.text)
            result["pagecount"] = self._parse_pagination(r.text)
            result["total"] = result["pagecount"] * 24
        except Exception:
            pass
        return result

    def detailContent(self, ids):
        result = {"list": []}
        if not ids:
            return result
        vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        url = f"{self.siteUrl}/watch/{vid}/"
        try:
            r = self.session.get(url, headers=self.headers, timeout=10, verify=False)
            r.raise_for_status()
            html = r.text
            title = ""
            pic = ""
            sources = []
            tm = re.search(r'<title>([^<]+)</title>', html, re.I)
            if tm:
                title = tm.group(1).split(" - ")[0].strip()
            pm = re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
            if pm:
                pic = self.fix_url(pm.group(1))
            if not pic:
                pm = re.search(r'<img[^>]*src=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*video-main-thumb', html, re.I)
                if pm:
                    pic = self.fix_url(pm.group(1))

            # 使用统一的视频 URL 提取逻辑 (页面本身可能没有直链)
            video_url = self._extract_video_url(html)
            if video_url:
                sources.append(f"HD${self.fix_url(video_url)}")

            # 如果没找到直链, 提取视频 iframe (排除广告 iframe)
            if not sources:
                # 优先找 responsive-player 容器内的 iframe
                pm = re.search(r'class="[^"\']*responsive-player[^"\']*"[^>]*>\s*<iframe[^>]*src=["\']([^"\']+)["\']', html, re.I)
                if not pm:
                    pm = re.search(r'<div[^>]*class="[^"\']*player[^"\']*"[^>]*>\s*<iframe[^>]*src=["\']([^"\']+)["\']', html, re.I)
                if pm:
                    iframe_src = unquote(unescape(pm.group(1)))
                    sources.append(f"播放${self.fix_url(iframe_src)}")
                else:
                    # 逐个检查 iframe, 跳过广告域名
                    ad_domains = ['tsyndicate', 'adsco.re', 'blockadsnot', 'google', 'doubleclick', 'adsterra', 'exoclick', 'juicyads']
                    for m in re.finditer(r'<iframe[^>]*src=["\']([^"\']+)["\']', html, re.I):
                        src = unquote(unescape(m.group(1).strip()))
                        if not any(ad in src.lower() for ad in ad_domains) and src.startswith('http'):
                            sources.append(f"播放${self.fix_url(src)}")
                            break

            # 最终回退: meta embedURL
            if not sources:
                pm = re.search(r'<meta[^>]*itemprop=["\']embedURL["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
                if pm:
                    src = unquote(unescape(pm.group(1)))
                    sources.append(f"播放${self.fix_url(src)}")

            result["list"].append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": "",
                "vod_play_from": "线路1" if sources else "",
                "vod_play_url": "#".join(sources) if sources else ""
            })
        except Exception:
            pass
        return result

    def searchContent(self, key, quick, pg="1"):
        result = {"list": [], "page": int(str(pg)), "pagecount": 1, "limit": 24, "total": 0}
        try:
            pg = int(str(pg))
            encoded = quote(key)
            if pg == 1:
                url = f"{self.siteUrl}/?s={encoded}"
            else:
                url = f"{self.siteUrl}/page/{pg}/?s={encoded}"
            r = self.session.get(url, headers=self.headers, timeout=10, verify=False)
            if r.status_code != 200 or not self._extract_videos(r.text):
                url = f"{self.siteUrl}/?s={encoded}&paged={pg}"
                r = self.session.get(url, headers=self.headers, timeout=10, verify=False)
            r.raise_for_status()
            result["list"] = self._extract_videos(r.text)
            result["pagecount"] = self._parse_pagination(r.text)
            result["total"] = result["pagecount"] * 24
        except Exception:
            pass
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "playUrl": "", "url": "", "header": json.dumps(self.headers)}
        if not id:
            return result
        url = unquote(unescape(id)) if id.startswith("http") else self.fix_url(unquote(unescape(id)))

        # 直接视频格式 (含 CDN URL 带 token), 直链播放
        if re.search(r'\.(?:m3u8|mp4|ts|mkv|flv|avi)(?:\?|$)', url, re.I) or 'cloudatacdn' in url.lower() or 'doodcdn' in url.lower():
            result["url"] = url
            result["header"] = json.dumps({
                "User-Agent": self.headers["User-Agent"],
                "Referer": url,
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            })
            return result

        # 非直链 (embed/iframe 页面): 主动抓取提取真实视频地址
        try:
            r = self.session.get(url, headers={
                **self.headers,
                "Referer": self.siteUrl + "/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }, timeout=15, verify=False, allow_redirects=True)
            r.raise_for_status()
            page_html = r.text
            final_url = r.url  # 重定向后的最终 URL

            # 0. 检测 CAPTCHA 页面 (Cloudflare Turnstile / reCAPTCHA)
            if 'turnstile' in page_html.lower() or ('captcha' in page_html.lower() and 'video_player' in page_html.lower()):
                result["parse"] = 1
                result["url"] = final_url
                result["header"] = json.dumps({
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.siteUrl + "/",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                })
                return result

            # 1. 用统一提取逻辑
            real_url = self._extract_video_url(page_html)
            if real_url:
                result["url"] = self.fix_url(real_url)
                result["header"] = json.dumps({
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": final_url,
                    "Accept": "*/*",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                })
                return result

            # 2. DoodStream pass_md5 解析 (完整 makePlay() 流程)
            real_url = self._doodstream_resolve(page_html, final_url)
            if real_url:
                result["url"] = real_url
                result["header"] = json.dumps({
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": final_url,
                    "Accept": "*/*",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                })
                return result
        except Exception:
            pass

        # 最终回退: 交由 WebView 嗅探解析
        result["parse"] = 1
        result["url"] = url
        result["header"] = json.dumps({
            "User-Agent": self.headers["User-Agent"],
            "Referer": self.siteUrl + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        return result

    def localProxy(self, param):
        return [200, "video/MP2T", b"", {}]

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(?:mp4|m3u8|flv|ts|mkv|avi)(?:\?|$)', str(url), re.I))
