# coding=utf-8
import json, time, ssl, re, base64, random, html as html_parser, hashlib
from base.spider import Spider
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad, pad

class Spider(Spider):
    def getName(self):
        return "小男娘"

    def init(self, extend=""):
        self.publish_urls = [
            "https://nanniang10.com/",
            "https://nanniang6.com/",
        ]
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
        self.aes_key_img = b"f5d965df75336270"
        self.aes_iv_img = b"97b60394abc2fbe1"
        self._resolve_domain()
        self.classes = [
            {"type_id": "home", "type_name": "首页"},
            {"type_id": "order/hot", "type_name": "男娘热门"},
            {"type_id": "order/today", "type_name": "今日更新"},
            {"type_id": "category/wnzp", "type_name": "伪娘自拍"},
            {"type_id": "category/jqyy", "type_name": "剧情演绎"},
            {"type_id": "category/yczm", "type_name": "原创招募"},
            {"type_id": "category/jxxl", "type_name": "早泄训练"},
            {"type_id": "category/wnav", "type_name": "伪娘AV"},
            {"type_id": "category/cdxl", "type_name": "雌堕系列"},
            {"type_id": "category/omwn", "type_name": "欧美伪娘"},
            {"type_id": "category/wnhw", "type_name": "伪娘户外"},
            {"type_id": "original", "type_name": "原创主"},
            {"type_id": "creator", "type_name": "up主"},
            {"type_id": "favorite-all", "type_name": "up主收藏榜"},
            {"type_id": "tags", "type_name": "标签"},
            {"type_id": "date", "type_name": "往期"},
        ]

    def _resolve_domain(self):
        suffix = None
        key_raw = None
        for pub in self.publish_urls:
            try:
                r = self.session.get(pub, headers=self.headers, timeout=10, verify=False)
                if r.status_code != 200:
                    continue
                html = r.text
                m = re.search(r"key\s*:\s*\"([^\"]+)\"", html, re.I)
                if m:
                    key_raw = m.group(1)
                else:
                    continue
                key_sha256_hex = hashlib.sha256(key_raw.encode()).hexdigest()
                iv_str = key_sha256_hex[:16]
                m2 = re.search(r"data\s*:\s*\"([^\"]+)\"", html, re.I)
                if not m2:
                    continue
                data_b64 = m2.group(1)
                aes_key = bytes.fromhex(key_sha256_hex)
                aes_iv = iv_str.encode("utf-8")
                try:
                    cipher = AES.new(aes_key, AES.MODE_CBC, aes_iv)
                    decrypted = unpad(cipher.decrypt(base64.b64decode(data_b64)), AES.block_size)
                    decrypted_text = decrypted.decode("utf-8", errors="ignore")
                    m3 = re.search(r"\"zz_line\"\s*:\s*\"([^\"]+)\"", decrypted_text)
                    if m3:
                        suffix = m3.group(1)
                        break
                    m4 = re.search(r"\"zz_backup_line\"\s*:\s*\"([^\"]+)\"", decrypted_text)
                    if m4:
                        suffix = m4.group(1)
                        break
                except Exception as e:
                    print("[小男娘] 解密失败: " + str(e))
                    continue
            except Exception as e:
                print("[小男娘] 发布页 " + pub + " 解析失败: " + str(e))
                continue
        if not suffix:
            suffix = "mgbywlre.com"
        prefix = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=5))
        self.host = "https://" + prefix + "." + suffix + "/"
        self.domains = [self.host]
        print("[小男娘] 解析域名: " + self.host)

    def _req(self, url):
        try:
            r = self.session.get(url, headers=self.headers, timeout=15, verify=False)
            if r.status_code == 200:
                return r.text
        except Exception as e:
            print("[小男娘] req error: " + str(e))
        return ""

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.replace("\\/", "/").replace("&amp;", "&")
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host.rstrip("/") + url
        if url.startswith("http"):
            return url
        return self.host.rstrip("/") + "/" + url

    def _clean_html(self, text):
        if not text:
            return ""
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _extract_one(self, html, pattern):
        m = re.search(pattern, html, re.I | re.S)
        return m.group(1) if m else ""

    def _img_proxy(self, img_url):
        if not img_url:
            return ""
        img_url = img_url.strip("`")
        if not img_url.startswith("http"):
            return ""
        return self.getProxyUrl() + "&url=" + self.e64(img_url) + "&type=img"

    def _aes_decrypt_img(self, data):
        if not data:
            return b""
        try:
            cipher = AES.new(self.aes_key_img, AES.MODE_CBC, self.aes_iv_img)
            return unpad(cipher.decrypt(data), AES.block_size)
        except:
            return data

    def _extract_max_page(self, html):
        pagination = re.search(r"<ul[^>]*class=\"pagination\"[^>]*>(.*?)</ul>", html, re.DOTALL)
        if pagination:
            pages = re.findall(r">(\d+)<", pagination.group(1))
            if pages:
                return max(int(p) for p in pages)
        last_link = re.search(r"<link[^>]+rel=[\"\']last[\"\'][^>]+href=[\"\']([^\"\']+)[\"\']", html, re.I)
        if last_link:
            m = re.search(r"(?:page/|/)(\d+)(?:/|$)", last_link.group(1))
            if m:
                return int(m.group(1))
        next_link = re.search(r"<link[^>]+rel=[\"\']next[\"\'][^>]+href=[\"\']([^\"\']+)[\"\']", html, re.I)
        if next_link:
            m = re.search(r"(?:page/|/)(\d+)(?:/|$)", next_link.group(1))
            if m:
                return max(int(m.group(1)), 1)
        return 1

    def _parse_standard_videos(self, html):
        result = []
        cards = re.findall(
            r"<div class=\"xqbj-list-rows-image\">(.*?)<div class=\"xqbj-list-rows-bottom-tags-text is-mobile\">",
            html, re.DOTALL
        )
        for card in cards:
            link_match = re.search(r"<a href=\"([^\"]+)\"[^>]*title=\"([^\"]*)\"", card)
            if not link_match:
                link_match = re.search(r"<a href=\"([^\"]+)\"", card)
                title = ""
                link = link_match.group(1) if link_match else ""
            else:
                link = link_match.group(1)
                title = link_match.group(2)
            if not link or not title:
                title = self._extract_one(card, r"<h3[^>]*>(.*?)</h3>")
                title = self._clean_html(title)
            link = self._fix_url(link)
            if not link or not title:
                continue
            img_url = self._extract_one(card, r"z-image-loader-url=\"`([^`]+)`\"")
            if not img_url:
                img_url = self._extract_one(card, r"z-image-loader-url=\"([^\"]+)\"")
            img_url = img_url.strip("`") if img_url else ""
            pic = self._img_proxy(img_url) if img_url else ""
            remarks = ""
            tag_match = re.search(
                r"<div class=\"xqbj-list-rows-bottom-tags-text is-desktop\">(.*?)</div>",
                card, re.DOTALL
            )
            if tag_match:
                remarks = self._clean_html(tag_match.group(1))
            result.append({
                "vod_id": link,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })
        return result

    def _parse_date_list(self, html):
        result = []
        lis = re.findall(r"<li[^>]*>(.*?)</li>", html, re.DOTALL)
        for li in lis:
            if "follow" in li:
                continue
            link = self._extract_one(li, r"<a href=\"([^\"]+)\"")
            link = self._fix_url(link)
            title = self._extract_one(li, r"<h3[^>]*>(.*?)</h3>")
            title = self._clean_html(title)
            if not link or not title:
                continue
            remarks = self._extract_one(li, r"<div class=\"date\">([^<]+)</div>")
            result.append({
                "vod_id": link,
                "vod_name": title,
                "vod_pic": "https://pastebin.880223.xyz/~hjs",
                "vod_remarks": remarks,
            })
        return result

    def _parse_tags_list(self, html):
        result = []
        section = re.search(r"<div class=\"tags-group\"[^>]*>(.*?)<nav[^>]+role=\"navigation\"", html, re.DOTALL)
        if not section:
            section = re.search(r"<div class=\"tags-group\"[^>]*>(.*?)</div>", html, re.DOTALL)
        if section:
            tags = re.findall(r"<a href=\"([^\"]+)\"[^>]*>(.*?)</a>", section.group(1))
            for link, title in tags:
                title = self._clean_html(title)
                link = self._fix_url(link)
                if not link or not title:
                    continue
                result.append({
                    "vod_id": "folder$tag_" + link.rstrip("/").split("/")[-1],
                    "vod_name": title,
                    "vod_pic": "https://pastebin.880223.xyz/~hjs",
                    "vod_remarks": "标签",
                    "vod_tag": "folder",
                })
        return result

    def _parse_author_list(self, html):
        result = []
        pattern = r"<a\s+[^>]*href=\"(/author/(\d+)/new/)\"[^>]*class=\"rank-card\"[^>]*>(.*?)</a>"
        for m in re.finditer(pattern, html, re.DOTALL):
            author_id = m.group(2)
            block = m.group(3)
            title = self._extract_one(block, r"<h2>(.*?)</h2>")
            title = self._clean_html(title)
            if not title:
                continue
            img_url = self._extract_one(block, r"z-image-loader-url=\"`([^`]+)`\"")
            if not img_url:
                img_url = self._extract_one(block, r"z-image-loader-url=\"([^\"]+)\"")
            img_url = img_url.strip("`") if img_url else ""
            pic = self._img_proxy(img_url) if img_url else ""
            fans_match = re.search(r"<span>(\d+)</span>\s*粉丝", block)
            likes_match = re.search(r"<span>(\d+)</span>\s*获赞", block)
            fans = fans_match.group(1) if fans_match else "0"
            likes = likes_match.group(1) if likes_match else "0"
            remarks = "粉丝" + fans + " · 获赞" + likes
            result.append({
                "vod_id": "folder$author_" + author_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
                "vod_tag": "folder",
            })
        return result

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

    def homeContent(self, filter):
        html = self._req(self.host)
        vods = self._parse_standard_videos(html)
        return {
            "class": self.classes,
            "list": vods[:20],
            "filters": {
                "favorite-all": [
                    {
                        "key": "sort",
                        "name": "类型",
                        "value": [
                            {"n": "收藏榜", "v": "favorite-all"},
                            {"n": "日作品", "v": "post-1"},
                            {"n": "周作品", "v": "post-7"},
                            {"n": "月作品", "v": "post-30"},
                            {"n": "总作品", "v": "post-all"},
                            {"n": "日点赞", "v": "likes-1"},
                            {"n": "周点赞", "v": "likes-7"},
                            {"n": "月点赞", "v": "likes-30"},
                            {"n": "总点赞", "v": "likes-all"},
                            {"n": "日收藏", "v": "favorite-1"},
                            {"n": "周收藏", "v": "favorite-7"}
                        ]
                    }
                ]
            }
        }

    def homeVideoContent(self):
        html = self._req(self.host)
        return {"list": self._parse_standard_videos(html)[:20]}

    def categoryContent(self, cid, pg, filter, ext):
        pg = int(pg) if str(pg).isdigit() else 1
        html = ""
        vods = []
        no_pagination = False
        if isinstance(cid, str) and cid.startswith("folder$"):
            folder_type, folder_id = cid.split("$", 1)[1].split("_", 1)
            if folder_type == "tag":
                url = self.host + "tag/" + folder_id + "/" + str(pg) + "/"
                html = self._req(url)
                vods = self._parse_standard_videos(html)
                no_pagination = True
            elif folder_type == "author":
                url = self.host + "author/" + folder_id + "/new/page/" + str(pg) + "/"
                html = self._req(url)
                vods = self._parse_standard_videos(html)
                no_pagination = True
            else:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}
        elif cid == "home":
            url = self.host + "page/" + str(pg) + "/"
            html = self._req(url)
            vods = self._parse_standard_videos(html)
        elif cid == "date":
            url = self.host + "date/page/" + str(pg) + "/"
            html = self._req(url)
            vods = self._parse_date_list(html)
        elif cid == "tags":
            url = self.host + "tags/page/" + str(pg) + "/"
            html = self._req(url)
            vods = self._parse_tags_list(html)
        elif cid == "original":
            url = self.host + "authors_blogger/original/page/" + str(pg) + "/"
            html = self._req(url)
            vods = self._parse_author_list(html)
            no_pagination = True
        elif cid == "creator":
            url = self.host + "authors_blogger/creator/page/" + str(pg) + "/"
            html = self._req(url)
            vods = self._parse_author_list(html)
            no_pagination = True
        elif cid == "favorite-all":
            ext_dict = self._parse_ext(ext)
            sub_type = ext_dict.get("sort", "favorite-all")
            url = self.host + "authors_up/" + sub_type + "/" + str(pg) + "/"
            html = self._req(url)
            vods = self._parse_author_list(html)
            no_pagination = True
        elif cid.startswith("category/"):
            url = self.host + cid + "/" + str(pg) + "/"
            html = self._req(url)
            vods = self._parse_standard_videos(html)
        else:
            url = self.host + cid + "/page/" + str(pg) + "/"
            html = self._req(url)
            vods = self._parse_standard_videos(html)
        if no_pagination:
            pc = pg + 1 if vods else pg
        else:
            pc = self._extract_max_page(html) if html else 1
        limit = len(vods) if vods else 24
        total = pc * limit
        return {
            "list": vods,
            "page": pg,
            "pagecount": pc,
            "limit": limit,
            "total": total
        }

    def detailContent(self, ids):
        url = ids[0]
        if url.startswith("folder$"):
            return {"list": []}
        html = self._req(url)
        if not html:
            return {"list": []}
        title = self._clean_html(self._extract_one(html, r"<h1[^>]*>(.*?)</h1>"))
        if not title:
            title = self._extract_one(html, r"<title>(.*?)</title>")
            title = self._clean_html(title).split("|")[0].strip()
        if not title:
            title = "小男娘"
        img_url = self._extract_one(html, r"z-image-loader-url=\"`([^`]+)`\"")
        if not img_url:
            img_url = self._extract_one(html, r"z-image-loader-url=\"([^\"]+)\"" )
        if not img_url:
            img_url = self._extract_one(html, r"<meta[^>]+property=\"og:image\"[^>]+content=\"([^\"]+)\"" )
        img_url = img_url.strip("`") if img_url else ""
        pic = self._img_proxy(img_url) if img_url else ""
        desc = self._extract_one(html, r"<meta[^>]+name=\"description\"[^>]+content=\"([^\"]+)\"" )
        if not desc:
            desc = self._extract_one(html, r"<meta[^>]+property=\"og:description\"[^>]+content=\"([^\"]+)\"" )
        play_urls = []
        pattern1 = r"\"video_h265\"\s*:\s*\{\s*\"url\"\s*:\s*\"([^\"]+)\""
        for m in re.finditer(pattern1, html, re.I):
            play_urls.append(self._fix_url(m.group(1).replace("\\/", "/")))
        if not play_urls:
            pattern2 = r"\"video\"\s*:\s*\{\s*\"url\"\s*:\s*\"([^\"]+)\""
            for m in re.finditer(pattern2, html, re.I):
                play_urls.append(self._fix_url(m.group(1).replace("\\/", "/")))
        if not play_urls:
            for m in re.finditer(r"(https?://[^\s\"\']+\.(?:m3u8|mp4)[^\s\"\']*)", html, re.I):
                play_urls.append(m.group(1))
        if not play_urls:
            for pattern in [
                r"var\s+now\s*=\s*[\"\']([^\"\']+)[\"\']",
                r"var\s+playurl\s*=\s*[\"\']([^\"\']+)[\"\']",
            ]:
                m = re.search(pattern, html, re.I)
                if m:
                    play_urls.append(self._fix_url(m.group(1).replace("\\/", "/")))
        seen = set()
        unique = []
        for u in play_urls:
            if u and u not in seen:
                seen.add(u)
                unique.append(u)
        play_from = "自动档" if unique else ""
        play_url_str = "#".join(["第" + str(i+1) + "集$" + u for i, u in enumerate(unique)])
        return {
            "list": [{
                "vod_id": url,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": desc or title,
                "vod_play_from": play_from,
                "vod_play_url": play_url_str,
            }]
        }

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg) if str(pg).isdigit() else 1
        url = self.host + "search_contents/" + key + "/" + str(pg) + "/"
        html = self._req(url)
        vods = self._parse_standard_videos(html)
        pc = self._extract_max_page(html) if html else 1
        limit = len(vods) if vods else 24
        total = pc * limit
        return {
            "list": vods,
            "page": pg,
            "pagecount": pc,
            "limit": limit,
            "total": total
        }

    def playerContent(self, flag, id, vipFlags):
        if id.startswith("http") and (".m3u8" in id or ".mp4" in id):
            return {
                "parse": 0,
                "url": id,
                "header": json.dumps(self.headers, ensure_ascii=False)
            }
        html = self._req(id)
        if html:
            for pattern in [
                r"\"video_h265\"\s*:\s*\{\s*\"url\"\s*:\s*\"([^\"]+)\"",
                r"\"video\"\s*:\s*\{\s*\"url\"\s*:\s*\"([^\"]+)\"",
                r"var\s+now\s*=\s*[\"\']([^\"\']+)[\"\']",
                r"var\s+playurl\s*=\s*[\"\']([^\"\']+)[\"\']",
                r"(https?://[^\s\"\']+\.(?:m3u8|mp4)[^\s\"\']*)",
                r"<video[^>]+src=[\"\']([^\"\']+)[\"\']",
                r"<source[^>]+src=[\"\']([^\"\']+)[\"\']",
            ]:
                m = re.search(pattern, html, re.I | re.S)
                if m:
                    u = self._fix_url(m.group(1).replace("\\/", "/"))
                    return {
                        "parse": 0,
                        "url": u,
                        "header": json.dumps(self.headers, ensure_ascii=False)
                    }
        return {
            "parse": 0,
            "url": id,
            "header": json.dumps(self.headers, ensure_ascii=False)
        }

    def localProxy(self, param):
        if param.get("type") == "img":
            try:
                url = self.d64(param.get("url", ""))
                if not url:
                    return [404, "text/plain", "", ""]
                res = requests.get(url, headers=self.headers, timeout=10, verify=False)
                if res.status_code == 200:
                    content = res.content
                    try:
                        content = self._aes_decrypt_img(content)
                    except:
                        pass
                    return [200, res.headers.get("Content-Type", "image/jpeg"), content, {}]
            except Exception as e:
                print("[小男娘] localProxy img error: " + str(e))
            return [404, "text/plain", "", ""]
        return [404, "text/plain", "", ""]

    def e64(self, text):
        try:
            return base64.b64encode(text.encode("utf-8")).decode("utf-8")
        except:
            return ""

    def d64(self, encoded_text):
        try:
            return base64.b64decode(encoded_text.encode("utf-8")).decode("utf-8")
        except:
            return ""
