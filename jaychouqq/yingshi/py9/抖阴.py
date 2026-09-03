# coding=utf-8
import json, time, ssl, re, base64, random
from base.spider import Spider
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from urllib.parse import quote, unquote


class Spider(Spider):

    def getName(self):
        return "抖阴"

    def init(self, extend=""):
        self.publish_url = "https://18dyw.net/"
        self.ua = "Mozilla/5.0 (Linux; Android 16; 2510DRK44C Build/BP2A.250605.031.A3) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/143.0.7499.192 Mobile Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.session = requests.Session()
        try:
            ssl._create_default_https_context = ssl._create_unverified_context
        except:
            pass
        self.aes_key = b"f5d965df75336270"
        self.aes_iv = b"97b60394abc2fbe1"
        self.host = ""
        self._host_cache_time = 0
        self._resolve_domain()

    def _get_host(self):
        if self.host and self._host_cache_time:
            if time.time() - self._host_cache_time < 1800:
                return self.host
        self._resolve_domain()
        return self.host

    def _resolve_domain(self):
        headers = {"User-Agent": self.ua}
        try:
            r = requests.get("https://dys18.com/", headers=headers, timeout=3, verify=False)
            if r.status_code == 200 and len(r.text) > 1000:
                self.host = "https://dys18.com"
                self._host_cache_time = time.time()
                self.headers.update({"Referer": f"{self.host}/", "Origin": self.host})
                return
        except:
            pass
        main_domain = ""
        backup_domain = ""
        try:
            r = requests.get(self.publish_url, headers=headers, timeout=10, verify=False)
            if r.status_code == 200:
                html = r.text
                m = re.search(r"var\s+mainDomain\s*=\s*'([^']+)'", html)
                if m:
                    main_domain = m.group(1)
                m = re.search(r"var\s+backupDomain\s*=\s*'([^']+)'", html)
                if m:
                    backup_domain = m.group(1)
        except:
            pass
        chars = "abcdefghjkmnpqrstuvwxy23456789"
        for _ in range(10):
            prefix = ''.join(random.choices(chars, k=4))
            for suffix in [main_domain, backup_domain]:
                if not suffix:
                    continue
                domain = f"https://{prefix}.{suffix}"
                try:
                    r = requests.get(domain, headers=headers, timeout=3, verify=False)
                    if r.status_code == 200 and len(r.text) > 1000:
                        self.host = domain.rstrip('/')
                        self._host_cache_time = time.time()
                        self.headers.update({"Referer": f"{self.host}/", "Origin": self.host})
                        return
                except:
                    continue

    def _req(self, url):
        self._get_host()
        if not self.host and not url.startswith("http"):
            return ""
        try:
            r = self.session.get(url, headers=self.headers, timeout=15, verify=False)
            if r.status_code == 200:
                return r.text
        except:
            pass
        return ""

    CATS = {
        "video": {
            "name": "精选AV",
            "base": "/video",
            "sorts": [
                {"n": "近期最佳", "v": "best-recently"},
                {"n": "最近更新", "v": "latest-updates"},
                {"n": "最多观看", "v": "most-viewed"},
                {"n": "最多收藏", "v": "most-favorites"},
            ],
            "cates": [
                {"n": "多人群P", "v": "drqp"},
                {"n": "辛尤里", "v": "xyl"},
                {"n": "按摩会所", "v": "amhs"},
                {"n": "户外搭讪", "v": "hwds"},
                {"n": "人妖伪娘", "v": "rywn"},
                {"n": "网黄主播", "v": "whzb"},
                {"n": "福利姬", "v": "flj"},
                {"n": "白虎嫩穴", "v": "bhnx"},
                {"n": "港台三级", "v": "gtsj"},
                {"n": "制服诱惑", "v": "zfyh"},
                {"n": "原创传媒", "v": "yccm"},
                {"n": "偷拍自拍", "v": "tpzp"},
                {"n": "萝莉少女", "v": "llsn"},
                {"n": "母子乱伦", "v": "mzll"},
                {"n": "成人动漫", "v": "crdm"},
                {"n": "童颜巨乳", "v": "tyjr"},
                {"n": "校园师生", "v": "xyss"},
                {"n": "色情综艺", "v": "sqzy"},
                {"n": "勾引偷情", "v": "gytq"},
                {"n": "强奸迷奸", "v": "qjmj"},
                {"n": "熟女少妇", "v": "snsf"},
                {"n": "重口猎奇", "v": "zklq"},
                {"n": "欧美性爱", "v": "omxa"},
                {"n": "内射中出", "v": "nszc"},
                {"n": "探花约啪", "v": "thyp"},
                {"n": "野战车震", "v": "yzcz"},
                {"n": "SM调教", "v": "smdj"},
                {"n": "绿帽换妻", "v": "lmhq"},
                {"n": "日韩伦理", "v": "rhll"},
                {"n": "AI换脸", "v": "aihl"},
                {"n": "黑人黑妹", "v": "hrhm"},
                {"n": "足交肛交", "v": "zjgj"},
                {"n": "玩偶姐姐", "v": "wojj"},
                {"n": "同志男同", "v": "tznt"},
                {"n": "女同拉拉", "v": "ntll"},
                {"n": "自慰高潮", "v": "zwgc"},
                {"n": "AI短剧", "v": "aidj"},
            ],
        },
        "melon": {
            "name": "黑料吃瓜",
            "base": "/melon",
            "sorts": [
                {"n": "推荐", "v": "recommend"},
                {"n": "热门", "v": "hot"},
                {"n": "最新", "v": "latest"},
            ],
            "cates": [
                {"n": "吃瓜新闻", "v": "cgxw"},
                {"n": "领导干部", "v": "ldgb"},
                {"n": "海外吃瓜", "v": "hwcg"},
                {"n": "伦理道德", "v": "lldd"},
                {"n": "每日大赛", "v": "mrds"},
                {"n": "网黄合集", "v": "whhj"},
                {"n": "明星黑料", "v": "mxhl"},
                {"n": "网红黑料", "v": "whhl"},
                {"n": "热门大瓜", "v": "rmdg"},
                {"n": "学生校园", "v": "xsxy"},
                {"n": "今日吃瓜", "v": "jrcg"},
                {"n": "反差骚女", "v": "fcsn"},
                {"n": "探花偷拍", "v": "thtp"},
                {"n": "AI短剧", "v": "aidj"},
                {"n": "寸止调教", "v": "czdj"},
                {"n": "世界杯狂欢", "v": "sjbkh"},
            ],
        },
        "av": {
            "name": "AV影片",
            "base": "/av",
            "sorts": [
                {"n": "最多搜索", "v": "trending"},
                {"n": "最新上线", "v": "new"},
                {"n": "最多观看", "v": "watching"},
                {"n": "最新发布", "v": "release"},
            ],
        },
        "av_theme": {
            "name": "影片主题",
            "base": "/av/theme",
            "sorts": [
                {"n": "近期最佳", "v": "best-recently"},
                {"n": "最近更新", "v": "latest-updates"},
                {"n": "最多观看", "v": "most-viewed"},
                {"n": "最多收藏", "v": "most-favorites"},
            ],
        },
        "av_actors": {
            "name": "AV女优",
            "base": "/av/actors-list",
            "actor_sorts": [
                {"n": "热度优先", "v": "hot-first"},
                {"n": "名称顺序", "v": "name-order"},
                {"n": "最近更新", "v": "latest-updates"},
                {"n": "最多影片", "v": "most-videos"},
            ],
        },
        "av_tag": {
            "name": "AV标签",
            "base": "/av/tag",
        },
    }

    def _parse_video_list(self, html):
        result = []
        items = re.findall(r'<li>\s*<div class="video-item">(.*?)</li>', html, re.DOTALL)
        for item in items:
            if 'rel="sponsored"' in item or 'checkNum' in item:
                continue
            href_m = re.search(r'href="(/(?:video|av)/detail/(\d+))"', item)
            if not href_m:
                continue
            href = href_m.group(1)
            vid = href_m.group(2)
            kind = "av" if "/av/detail/" in href else "video"
            du_m = re.search(r'data-url="([^"]+)"', item)
            data_url = du_m.group(1) if du_m else ""
            if not data_url:
                continue
            alt_m = re.search(r'alt="([^"]*)"', item)
            title = alt_m.group(1) if alt_m else vid
            img_m = re.search(r'data-src="([^"]+)"', item)
            img = self._img_proxy(img_m.group(1)) if img_m else ""
            duration = ""
            dur_m = re.search(r'<span class="text-sm ml-auto">([^<]+)</span>', item)
            if dur_m:
                duration = dur_m.group(1).strip()
            if not duration:
                dur_m = re.search(r'<div class="text-sm opacity-50[^"]*">\s*([^<]+)\s*</div>', item)
                if dur_m:
                    duration = dur_m.group(1).strip()
            vod_id = f"{kind}:{vid}:{self._e64(data_url)}"
            result.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": img,
                "vod_remarks": duration,
            })
        return result

    def _parse_melon_list(self, html):
        result = []
        items = re.findall(r'<li[^>]*>(.*?)</li>', html, re.DOTALL)
        for item in items:
            href_m = re.search(r'href="/melon/detail/(\d+)"', item)
            if not href_m:
                continue
            mid = href_m.group(1)
            img_m = re.search(r'data-src="([^"]+)"', item)
            img = self._img_proxy(img_m.group(1)) if img_m else ""
            a_m = re.search(r'href="/melon/detail/\d+"[^>]*>(.*?)</a>', item, re.DOTALL)
            title = ""
            if a_m:
                title = re.sub(r'<[^>]+>', ' ', a_m.group(1))
                title = re.sub(r'\s+', ' ', title).strip()
            if not title:
                title = mid
            date_m = re.search(r'<span>(\d{4}-\d{2}-\d{2})', item)
            date_str = date_m.group(1) if date_m else ""
            vod_id = f"melon:{mid}"
            result.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": img,
                "vod_remarks": date_str,
            })
        seen = set(); out = []
        for r in result:
            if r["vod_id"] not in seen:
                seen.add(r["vod_id"]); out.append(r)
        return out

    def _parse_actor_list(self, html):
        result = []
        items = re.findall(r'<li[^>]*>(.*?)</li>', html, re.DOTALL)
        for item in items:
            href_m = re.search(r'href="(/av/actors-video/(\d+)/[^"]+)"', item)
            if not href_m:
                continue
            aid = href_m.group(2)
            img_m = re.search(r'data-src="([^"]+)"', item)
            img = self._img_proxy(img_m.group(1)) if img_m else ""
            alt_m = re.search(r'alt="([^"]*)"', item)
            name = alt_m.group(1) if alt_m else aid
            num_m = re.search(r'(\d+)\s*(?:部|个|作品|视频)', item)
            remarks = f"{num_m.group(1)}部" if num_m else ""
            vod_id = f"av_actors/{aid}"
            result.append({
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": img,
                "vod_remarks": remarks,
                "vod_tag": "folder",
            })
        seen = set(); out = []
        for r in result:
            if r["vod_id"] not in seen:
                seen.add(r["vod_id"]); out.append(r)
        return out

    def _parse_av_theme_list(self, html):
        result = []
        items = re.findall(r'<li[^>]*class="[^"]*theme-item[^"]*"[^>]*>(.*?)</li>', html, re.DOTALL)
        for item in items:
            href_m = re.search(r'href="([^"]+)"', item)
            if not href_m:
                continue
            href = href_m.group(1)
            m = re.search(r'/av/theme/([^/]+)/', href)
            slug = m.group(1) if m else ''
            if not slug:
                continue
            alt_m = re.search(r'alt="([^"]*)"', item)
            title = alt_m.group(1) if alt_m else slug
            img_m = re.search(r'data-src="([^"]+)"', item)
            img = self._img_proxy(img_m.group(1)) if img_m else ""
            remark = ""
            rm = re.search(r'<div[^>]*class="[^"]*dx-opacity-bg[^"]*"[^>]*>(.*?)</div>', item, re.DOTALL)
            if rm:
                remark = re.sub(r'<[^>]+>', '', rm.group(1)).strip()
            result.append({
                "vod_id": f"av_theme/{slug}",
                "vod_name": title,
                "vod_pic": img,
                "vod_remarks": remark,
                "vod_tag": "folder",
            })
        seen = set(); out = []
        for r in result:
            if r["vod_id"] not in seen:
                seen.add(r["vod_id"]); out.append(r)
        return out

    def _parse_tag_list(self, html):
        result = []
        items = re.findall(r'<li[^>]*>(.*?)</li>', html, re.DOTALL)
        for item in items:
            href_m = re.search(r'href="(/av/tag/([^"]+))"', item)
            if not href_m:
                continue
            tag = unquote(href_m.group(2))
            h3_m = re.search(r'<h3>(.*?)</h3>', item)
            title = h3_m.group(1).strip() if h3_m else tag
            result.append({
                "vod_id": f"av_tag/{tag}",
                "vod_name": title,
                "vod_pic": "",
                "vod_remarks": "",
                "vod_tag": "folder",
            })
        seen = set(); out = []
        for r in result:
            if r["vod_id"] not in seen:
                seen.add(r["vod_id"]); out.append(r)
        return out

    def _build_url(self, cid, cat, sort, pg):
        c = self.CATS[cid]
        base = c["base"]
        if not cat:
            cat = c["cates"][0]["v"] if c.get("cates") else ""
        if not sort:
            sort = c["sorts"][0]["v"] if c.get("sorts") else ""
        url = f"{base}/{cat}/{sort}/{pg}"
        return self.host + url

    def _extract_max_page(self, html):
        total_m = re.search(r'data-rec-total="(\d+)"', html)
        per_page_m = re.search(r'data-rec-per-page="(\d+)"', html)
        if total_m and per_page_m:
            total = int(total_m.group(1))
            per_page = int(per_page_m.group(1))
            if per_page > 0:
                return (total + per_page - 1) // per_page
        if re.search(r'<link rel="next"', html):
            return 999
        return 1

    def homeContent(self, filter):
        classes = []
        filters = {}
        for cid, c in self.CATS.items():
            classes.append({"type_id": cid, "type_name": c["name"]})
            f = []
            if cid in ("video", "melon"):
                if c.get("cates"):
                    f.append({"key": "cat", "name": "分类", "value": c["cates"]})
                if c.get("sorts"):
                    f.append({"key": "sort", "name": "排序", "value": c["sorts"]})
            elif cid == "av":
                f.append({"key": "cateId", "name": "类型", "value": c["sorts"]})
            elif cid == "av_theme":
                f.append({"key": "by", "name": "影片排序", "value": c["sorts"]})
            elif cid == "av_actors":
                f.append({"key": "by", "name": "女优排序", "value": c["actor_sorts"]})
            elif cid == "av_tag":
                pass
            filters[cid] = f
        html = self._req(f"{self.host}/video/drqp/best-recently/1")
        vods = self._parse_video_list(html)
        return {"class": classes, "list": vods, "filters": filters}

    def homeVideoContent(self):
        html = self._req(f"{self.host}/video/drqp/best-recently/1")
        return {"list": self._parse_video_list(html)}

    def categoryContent(self, cid, pg, filter, ext):
        pg = int(pg) if str(pg).isdigit() else 1
        ext = self._parse_ext(ext)
        if cid == "video":
            cat = ext.get("cat", "")
            sort = ext.get("sort", "")
            url = self._build_url(cid, cat, sort, pg)
            html = self._req(url)
            vods = self._parse_video_list(html)
            pc = self._extract_max_page(html)
            return {"list": vods, "page": pg, "pagecount": pc, "limit": 24, "total": pc * 24}
        if cid == "melon":
            cat = ext.get("cat", "")
            sort = ext.get("sort", "")
            url = self._build_url(cid, cat, sort, pg)
            html = self._req(url)
            vods = self._parse_melon_list(html)
            pc = self._extract_max_page(html)
            return {"list": vods, "page": pg, "pagecount": pc, "limit": 24, "total": pc * 24}
        if cid == "av":
            cateId = ext.get("cateId", "trending")
            url = f"{self.host}/av/{cateId}/{pg}"
            html = self._req(url)
            vods = self._parse_video_list(html)
            pc = self._extract_max_page(html)
            return {"list": vods, "page": pg, "pagecount": pc, "limit": 24, "total": pc * 24}
        if cid == "av_theme":
            url = f"{self.host}/av/theme"
            if pg > 1:
                url = f"{self.host}/av/theme/{pg}"
            html = self._req(url)
            vods = self._parse_av_theme_list(html)
            pc = self._extract_max_page(html)
            if pc <= 1:
                pc = 1
            return {"list": vods, "page": pg, "pagecount": pc, "limit": 24, "total": len(vods)}
        if cid.startswith("av_theme/"):
            slug = cid[9:]
            by = ext.get("by", "best-recently")
            url = f"{self.host}/av/theme/{slug}/{by}/{pg}"
            html = self._req(url)
            vods = self._parse_video_list(html)
            pc = self._extract_max_page(html)
            return {"list": vods, "page": pg, "pagecount": pc, "limit": 24, "total": pc * 24}
        if cid == "av_actors":
            by = ext.get("by", "hot-first")
            url = f"{self.host}/av/actors-list/{by}/{pg}"
            html = self._req(url)
            vods = self._parse_actor_list(html)
            pc = self._extract_max_page(html)
            return {"list": vods, "page": pg, "pagecount": pc, "limit": 24, "total": pc * 24}
        if cid.startswith("av_actors/"):
            actor_id = cid[10:]
            url = f"{self.host}/av/actors-video/{actor_id}/latest-updates/{pg}"
            html = self._req(url)
            vods = self._parse_video_list(html)
            pc = self._extract_max_page(html)
            return {"list": vods, "page": pg, "pagecount": pc, "limit": 24, "total": pc * 24}
        if cid == "av_tag":
            url = f"{self.host}/av/tag"
            html = self._req(url)
            vods = self._parse_tag_list(html)
            return {"list": vods, "page": pg, "pagecount": 1, "limit": 24, "total": len(vods)}
        if cid.startswith("av_tag/"):
            tag = unquote(cid[7:])
            url = f"{self.host}/av/tag/{quote(tag, safe='')}/{pg}"
            html = self._req(url)
            vods = self._parse_video_list(html)
            pc = self._extract_max_page(html)
            return {"list": vods, "page": pg, "pagecount": pc, "limit": 24, "total": pc * 24}
        return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

    def detailContent(self, ids):
        raw_id = ids[0]
        parts = raw_id.split(":", 1)
        kind = parts[0] if len(parts) == 2 else "video"
        payload = parts[1] if len(parts) == 2 else raw_id
        if kind == "video":
            seg = payload.split(":", 1)
            vid = seg[0]
            data_url = self._d64(seg[1]) if len(seg) == 2 else ""
            url = f"{self.host}/video/detail/{vid}"
        elif kind == "av":
            seg = payload.split(":", 1)
            vid = seg[0]
            data_url = self._d64(seg[1]) if len(seg) == 2 else ""
            url = f"{self.host}/av/detail/{vid}"
        elif kind == "melon":
            mid = payload
            url = f"{self.host}/melon/detail/{mid}"
            data_url = ""
            vid = mid
        else:
            return {"list": []}
        html = self._req(url)
        if not html:
            return {"list": []}
        title = ""
        m = re.search(r'"title"\s*:\s*"([^"]+)"', html)
        if m:
            title = m.group(1)
        if not title:
            m = re.search(r'"name"\s*:\s*"([^"]+)"', html)
            if m:
                title = m.group(1)
        if not title:
            h1_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
            if h1_m:
                title = re.sub(r'<[^>]+>', '', h1_m.group(1)).strip()
        if not title:
            t_m = re.search(r'<title>([^<|]+)', html)
            if t_m:
                title = t_m.group(1).strip()
        img = ""
        m = re.search(r'"thumbnailUrl"\s*:\s*\[?"([^"]+)"', html)
        if m:
            img = self._img_proxy(m.group(1))
        if not img:
            m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
            if m:
                img = self._img_proxy(m.group(1))
        desc = ""
        m = re.search(r'<meta name="description" content="([^"]+)"', html)
        if m:
            desc = m.group(1)
        duration = ""
        m = re.search(r'"duration"\s*:\s*"PT(\d+)M(\d+)S"', html)
        if m:
            duration = f"{m.group(1)}:{m.group(2).zfill(2)}"
        tags = []
        for m in re.finditer(r'href="/video/([a-z]+)/best-recently"[^>]*>\s*([^<]+)', html):
            tn = m.group(2).strip()
            if tn and tn not in tags:
                tags.append(tn)
        date = ""
        m = re.search(r'"uploadDate"\s*:\s*"([^"]+)"', html)
        if m:
            date = m.group(1)[:10]
        update_time = ""
        if kind in ("video", "av"):
            um = re.search(r'icons\.svg#time"[^>]*>\s*</use>\s*</svg>\s*更新于\s*([^<]+)', html)
            if um:
                update_time = um.group(1).strip()
        play_url = ""
        if kind in ("video", "av") and data_url:
            play_url = f"正片${data_url}"
        if not play_url:
            du = re.search(r'data-url="([^"]+)"', html)
            if du:
                play_url = f"正片${du.group(1)}"
        if kind == "melon":
            body_m = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
            if body_m:
                body = re.sub(r'<[^>]+>', ' ', body_m.group(1))
                body = re.sub(r'\s+', ' ', body).strip()
                if body:
                    desc = desc or body
                    desc = desc[:500]
            if not play_url:
                melon_play = self._extract_melon_play_url(html, vid)
                if melon_play:
                    play_url = f"正片${melon_play}"
        remarks = " ".join(filter(None, [duration, date]))
        content_parts = []
        if desc:
            content_parts.append(desc)
        if update_time:
            content_parts.append(f"更新时间：{update_time}")
        vod_content = " | ".join(content_parts) if content_parts else title
        return {"list": [{
            "vod_id": f"{kind}:{vid}",
            "vod_name": title or vid,
            "vod_pic": img,
            "type_name": ", ".join(tags[:5]) if tags else "",
            "vod_remarks": remarks,
            "vod_content": vod_content,
            "vod_play_from": "m3u8" if play_url else "",
            "vod_play_url": play_url,
        }]}

    def playerContent(self, flag, id, vipFlags):
        url = id
        if url.startswith("/"):
            url = f"{self.host}{url}"
        return {
            "parse": 0,
            "url": url,
            "header": {"User-Agent": self.ua, "Referer": f"{self.host}/"},
        }

    def searchContentPage(self, key, quick, pg):
        pg = int(pg) if str(pg).isdigit() else 1
        if pg > 1:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}
        key = (key or "").strip()
        if not key:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 0}
        try:
            url = f"{self.host}/search/{quote(key, safe='')}"
            html = self._req(url)
            html = re.sub(r'<a[^>]*class="[^"]*(?:guess-item|hot-item)[^"]*"[^>]*>.*?</a>', '', html, flags=re.DOTALL)
            vods = self._parse_video_list(html)
            if vods:
                return {"list": vods, "page": 1, "pagecount": 1, "limit": 24, "total": len(vods)}
        except:
            pass
        kw = key.upper()
        for section in ("release", "watching", "new", "trending"):
            for p in range(1, 3):
                try:
                    u = f"{self.host}/av/{section}" if p == 1 else f"{self.host}/av/{section}/{p}"
                    h = self._req(u)
                    for m in re.finditer(r'href="(/av/detail/(\d+))"[^>]*>\s*<h3>(.*?)</h3>', h, re.DOTALL):
                        title = re.sub(r'<[^>]+>', ' ', m.group(3))
                        title = re.sub(r'\s+', ' ', title).strip()
                        if kw in title.upper():
                            vods = self._parse_video_list(h)
                            vods = [v for v in vods if kw in v.get("vod_name", "").upper()]
                            if vods:
                                return {"list": vods, "page": 1, "pagecount": 1, "limit": 24, "total": len(vods)}
                except:
                    continue
        return {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 0}

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def _unpack_eval(self, code):
        m = re.search(r"\('((?:[^'\\]|\\.)*)',(\d+),(\d+),'", code)
        if not m:
            return None
        template = m.group(1).replace("\\'", "'").replace('\\"', '"')
        base = int(m.group(2))
        sm = re.search(r"'([^']+)'\.split\('\|'\)", code)
        if not sm:
            return None
        parts = sm.group(1).split('|')
        result = []
        i = 0
        while i < len(template):
            ch = template[i]
            if ch.isalnum() or ch == '_':
                j = i
                while j < len(template) and (template[j].isalnum() or template[j] == '_'):
                    j += 1
                token = template[i:j]
                idx = 0
                valid = True
                for c in token:
                    if '0' <= c <= '9':
                        d = ord(c) - ord('0')
                    elif 'a' <= c <= 'z':
                        d = ord(c) - ord('a') + 10
                    elif 'A' <= c <= 'Z':
                        d = ord(c) - ord('A') + 36
                    else:
                        valid = False
                        break
                    idx = idx * base + d
                if valid and 0 <= idx < len(parts) and parts[idx]:
                    result.append(parts[idx])
                else:
                    result.append(token)
                i = j
            else:
                result.append(ch)
                i += 1
        return ''.join(result)

    def _extract_melon_play_url(self, detail_html, vid):
        evals = re.findall(r"eval\(function\(p,a,c,k,e,d\)\{.*?\}\)\)", detail_html, re.DOTALL)
        for ev in evals:
            unpacked = self._unpack_eval(ev)
            if not unpacked:
                continue
            enc_m = re.search(r'encodeURIComponent\("([^"]+)"\)', unpacked)
            c_m = re.search(r'&c=(https?://[^"]+?)&t=', unpacked)
            if not enc_m or not c_m:
                continue
            u_param = enc_m.group(1)
            c_param = c_m.group(1)
            t = int(time.time())
            play_url = f"{self.host}/melon/melon-detail-play?u={quote(u_param)}&c={quote(c_param)}&t={t}"
            play_html = self._req(play_url)
            if not play_html:
                continue
            unpacked2 = self._unpack_eval(play_html)
            if not unpacked2:
                continue
            src_m = re.search(r'src="(/media/m3u8[^"]+)"', unpacked2)
            if src_m:
                return src_m.group(1)
        return ""

    def _parse_ext(self, ext):
        if not ext:
            return {}
        if isinstance(ext, dict):
            return ext
        if isinstance(ext, str):
            ext = ext.strip()
            if not ext or ext in ("{}", "null", "undefined"):
                return {}
            try:
                return json.loads(ext)
            except:
                result = {}
                for part in ext.split("&"):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        result[k] = v
                return result
        return {}

    def _img_proxy(self, img_url):
        if not img_url:
            return ""
        return f"{self.getProxyUrl()}&url={self._e64(img_url)}&type=img"

    def localProxy(self, param):
        if param.get("type") == "img":
            try:
                url = self._d64(param.get("url", ""))
                if not url:
                    return [404, "text/plain", "", ""]
                res = requests.get(url, headers=self.headers, timeout=10, verify=False)
                if res.status_code == 200:
                    data = self.decrypt_image(res.content)
                    ext = self.detect_extension(data)
                    mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'gif': 'image/gif', 'webp': 'image/webp'}
                    return [200, mime.get(ext, 'image/jpeg'), data, ""]
            except Exception as e:
                print(f"[抖阴] localProxy img error: {e}")
            return [404, "text/plain", "", ""]
        return [404, "text/plain", "", ""]

    def decrypt_image(self, encrypted_data):
        dec = AES.new(self.aes_key, AES.MODE_CBC, self.aes_iv).decrypt(encrypted_data)
        pad = dec[-1]
        if 1 <= pad <= 16 and dec[-pad:] == bytes([pad]) * pad:
            dec = dec[:-pad]
        else:
            dec = dec.rstrip(b'\x00')
        return dec

    def detect_extension(self, data):
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            return 'png'
        if data[:3] == b'\xff\xd8\xff':
            return 'jpg'
        if data[:6] in (b'GIF87a', b'GIF89a'):
            return 'gif'
        if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            return 'webp'
        return 'bin'

    def aesimg(self, word):
        cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_iv)
        return unpad(cipher.decrypt(word), AES.block_size)

    def _e64(self, text):
        try:
            return base64.b64encode(text.encode("utf-8")).decode("utf-8")
        except:
            return ""

    def _d64(self, text):
        try:
            return base64.b64decode(text.encode("utf-8")).decode("utf-8")
        except:
            return ""
