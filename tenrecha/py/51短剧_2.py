import sys
sys.path.append('..')

import json
import base64
import re
from Crypto.Cipher import AES
from base.spider import Spider


class Spider(Spider):
    def init(self, extend=""):
        self.host = "https://adjust.cbpjoocbe.com"
        self.play_aes_key = "2acf7e91e9864673"
        self.play_aes_iv = "1c29882d3ddfcfd6"
        self.img_aes_key = "f5d965df75336270"
        self.img_aes_iv = "97b60394abc2fbe1"
        self.oauth_id = ""
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Referer": self.host + "/",
        }
        self.session = self._create_session()
        self._ensure_oauth()

    def _create_session(self):
        import requests
        s = requests.Session()
        s.headers.update(self.headers)
        return s

    def _ensure_oauth(self):
        try:
            r = self.session.get(self.host + "/", timeout=15)
            self.oauth_id = r.cookies.get("OAUTH_ID", "")
        except Exception:
            self.oauth_id = ""

    def getName(self):
        return "51短剧"

    def isVideoFormat(self, url):
        return url.endswith(".m3u8") or url.endswith(".mp4") or url.endswith(".ts")

    def manualVideoCheck(self):
        return False

    def _decode_img(self, data):
        cipher = AES.new(self.img_aes_key.encode(), AES.MODE_CBC, self.img_aes_iv.encode())
        dec = cipher.decrypt(data)
        pad = dec[-1]
        if 1 <= pad <= 16:
            dec = dec[:-pad]
        return dec

    @staticmethod
    def _decode_play(data_b64):
        cipher = AES.new("2acf7e91e9864673".encode(), AES.MODE_CBC, "1c29882d3ddfcfd6".encode())
        raw = cipher.decrypt(base64.b64decode(data_b64))
        pad = raw[-1]
        if 1 <= pad <= 16:
            raw = raw[:-pad]
        return json.loads(raw.decode("utf-8", "ignore"))

    def _parse_cards(self, html):
        videos = []
        pat = r'<a[^>]*href="(?:/video/|/play\?id=)(\d+)"[^>]*>.*?<img[^>]*?data-src="([^"]+)"[^>]*?alt="([^"]*)".*?>(.*?)</a>'
        for m in re.finditer(pat, html, re.S):
            vid, pic, title, inner = m.group(1), m.group(2), m.group(3), m.group(4)
            # 跳过站点注入的广告位（alt 固定为「广告」）
            if title.strip() == "广告":
                continue
            rm = re.search(r'全(\d+)集', inner)
            remarks = ("全" + rm.group(1) + "集") if rm else ""
            from urllib.parse import quote
            pic_b64 = base64.b64encode(pic.encode("utf-8")).decode("utf-8")
            base_proxy = self.getProxyUrl()
            if not base_proxy:
                base_proxy = "http://127.0.0.1:9978/proxy?do=py"
            if "?" in base_proxy:
                pic = base_proxy + "&type=tbr_img&url=" + quote(pic_b64, safe="")
            else:
                pic = base_proxy + "?type=tbr_img&url=" + quote(pic_b64, safe="")
            videos.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })
        return videos

    _SEG_KEYS = ["cate", "tag", "bg", "channel", "status", "sort"]

    def _build_segments(self, tid, extend):
        segs = [str(tid), "0", "0", "0", "0", "0"]
        if isinstance(extend, dict):
            for i, k in enumerate(self._SEG_KEYS):
                if i == 0:
                    continue
                v = (extend.get(k, "") or "").strip()
                if v:
                    segs[i] = v
        return segs

    def _parse_filter_links(self, html):
        rows = []
        seen = set()
        pat = r'(?:https?://[^/"]*)?/new-theater-category/(\d+)-(\d+)-(\d+)-(\d+)-(\d+)-(\d+)/?[^"]*"[^>]*>([^<]*)</a>'
        for m in re.finditer(pat, html):
            s1, s2, s3, s4, s5, s6, text = m.groups()
            key = "-".join([s1, s2, s3, s4, s5, s6])
            if key in seen:
                continue
            seen.add(key)
            rows.append({"segs": [s1, s2, s3, s4, s5, s6], "text": text.strip()})
        return rows

    def homeContent(self, filter):
        nav_html = self._html(self.host + "/new-theater-category/0-0-0-0-0-0/")
        html = self._html(self.host + "/")
        classes = []
        cset = set()
        filters = {}
        for r in self._parse_filter_links(nav_html):
            s1 = r["segs"][0]
            if s1 == "0":
                continue
            if s1 not in cset:
                cset.add(s1)
                classes.append({"type_id": s1, "type_name": r["text"]})
        fkeys = ["tag", "bg", "channel", "status", "sort"]
        fnames = ["标签", "背景", "频道", "状态", "排序"]
        fvals = [
            [("大男主", "2"), ("大女主", "1"), ("甜宠", "49"), ("双向奔赴", "48"), ("赘婿逆袭", "39"), ("传承觉醒", "38"), ("家长里短", "37"), ("破镜重圆", "36"), ("虐恋", "35"), ("豪门", "34"), ("强者回归", "33"), ("先婚后爱", "32"), ("小人物", "31"), ("神豪", "30"), ("系统", "29"), ("穿越", "28"), ("重生", "27"), ("马甲", "26"), ("打脸虐渣", "25")],
            [("现代", "40"), ("都市", "41"), ("古代", "42"), ("乡村", "43"), ("年代", "44"), ("职场", "45")],
            [("男频", "1"), ("女频", "2")],
            [("7天内", "1"), ("14天内", "2"), ("30天内", "3"), ("90天内", "4")],
            [("最新", "1"), ("最热", "2")],
        ]
        flist = []
        for key, name, vals in zip(fkeys, fnames, fvals):
            opts = [{"n": "全部", "v": "0"}]
            for n, v in vals:
                opts.append({"n": n, "v": v})
            flist.append({"key": key, "name": name, "value": opts})
        for c in classes:
            filters[c["type_id"]] = [dict(x) for x in flist]
        videos = self._parse_cards(html)
        return {"class": classes, "filters": filters, "list": videos}

    def homeVideoContent(self):
        html = self._html(self.host + "/")
        return {"list": self._parse_cards(html)}

    def categoryContent(self, tid, pg, filter, extend):
        segs = self._build_segments(tid, extend)
        path = "/new-theater-category/%s/" % "-".join(segs)
        if str(pg) != "1":
            path += "page/%s" % pg
        html = self._html(self.host + path)
        videos = self._parse_cards(html)
        return {"list": videos, "page": int(pg), "pagecount": 999, "total": 99999, "limit": 24}

    def _videoepisodes(self, play_id):
        # play id 调接口，返回解密后的 data 字典
        r = self.session.post(self.host + "/video/videoepisodes",
                              data={"id": str(play_id), "oauth_id": self.oauth_id, "token": ""},
                              timeout=15)
        obj = self._decode_play(r.json().get("data", ""))
        return (obj.get("data") or {}) if isinstance(obj, dict) else {}

    def detailContent(self, ids):
        # 卡片 id 有两种体系：
        #   - 分类/搜索页：/play?id={play_id}（play id，即某一集 id，可直接调 videoepisodes）
        #   - 首页：/video/{video_id}（video id，videoepisodes 接口用它会错位，需先从详情页取真实 play id）
        # videoepisodes 只认 play id：返回的 episodeAll[0].id 即传入的 play id 时才是正确剧集。
        vid = ids[0]
        self.oauth_id = self.session.cookies.get("OAUTH_ID", self.oauth_id)
        episodes = []
        vod_name = ""
        pic = ""
        desc = ""

        play_id = vid
        d = self._videoepisodes(play_id)
        serials = d.get("episodeAll") or []
        if isinstance(serials, dict):
            serials = serials.get("list") or []
        # 校验：第一集 id 应等于传入 id，否则传入的是 video id，需转成详情页里的真实 play id
        if not serials or str(serials[0].get("id")) != str(play_id):
            # 抓 /video/{video_id} 详情页，取第一个真实 play id（如 /play?id=289358）
            html = self._html(self.host + "/video/" + str(vid))
            name = re.search(r'<title>(.*?)</title>', html)
            if name:
                vod_name = name.group(1).split(" - ")[0].strip()
            pic_m = re.search(r'property="og:image"\s+content="([^"]+)"', html)
            if pic_m:
                pic = pic_m.group(1)
            plays = re.findall(r'/play\?id=(\d+)', html)
            if plays:
                play_id = plays[0]
                d = self._videoepisodes(play_id)
                serials = d.get("episodeAll") or []
                if isinstance(serials, dict):
                    serials = serials.get("list") or []

        if not vod_name:
            vod_name = d.get("video_title") or ""
        if not desc:
            desc = d.get("description") or ""
        if not pic:
            pic = d.get("cover_img") or d.get("first_img") or ""

        for item in serials:
            eid = item.get("id")
            if eid is None:
                continue
            title = item.get("episode_title") or ("第%d集" % (item.get("sort", 0) or len(episodes) + 1))
            # 写入该集的 play id（videoepisodes 返回的 id 即某一集 id），
            # 由 playerContent 在播放时实时换取带有效 auth_key 的 m3u8，
            # 避免 detailContent 预取的 auth_key 过期导致全部跳到默认内容。
            episodes.append("%s$%s" % (title, eid))

        vod_play_url = "#".join(episodes)
        vod = {
            "vod_id": vid,
            "vod_name": vod_name,
            "vod_pic": pic,
            "vod_play_from": "51短剧",
            "vod_play_url": vod_play_url,
            "vod_content": desc,
            "vod_remarks": ("共%d集" % len(episodes)) if episodes else "",
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        # 播放串为 标题$playid（play id 即某一集 id）。
        # 若为完整 URL 直接返回；否则按 play id 实时调 videoepisodes 换取带有效 auth_key 的 m3u8。
        val = str(id).split("$")[-1]
        if val.startswith("http"):
            return {"playUrl": "", "url": val, "parse": 0, "header": self.headers, "position": "0"}
        try:
            d = self._videoepisodes(val)
            serials = d.get("episodeAll") or []
            if isinstance(serials, dict):
                serials = serials.get("list") or []
            for it in serials:
                if str(it.get("id")) == str(val):
                    url = it.get("video_url") or ""
                    if url:
                        return {"playUrl": "", "url": url, "parse": 0, "header": self.headers, "position": "0"}
        except Exception as e:
            print("[51duanju] player err:", e)
        return {"playUrl": "", "msg": "无效的播放地址: %s" % val}

    def localProxy(self, params):
        try:
            if params.get("type") != "tbr_img":
                return [404, "text/plain", "not found"]
            from urllib.parse import unquote
            img_b64 = unquote(params.get("url", ""))
            pad = 4 - len(img_b64) % 4
            if pad != 4:
                img_b64 += "=" * pad
            img_url = base64.b64decode(img_b64).decode("utf-8")
            img_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                "Referer": self.host + "/",
            }
            r = self.session.get(img_url, headers=img_headers, timeout=20)
            if r.status_code != 200:
                return [404, "text/plain", "image not found"]
            data = r.content
            # 已是明文图片则直接返回
            if data[:3] == b"\xff\xd8\xff":
                return [200, "image/jpeg", data, {"Content-Length": str(len(data))}]
            if data[:4] == b"\x89PNG":
                return [200, "image/png", data, {"Content-Length": str(len(data))}]
            if data[:4] == b"GIF8":
                return [200, "image/gif", data, {"Content-Length": str(len(data))}]
            # 否则按 AES-CBC 解密
            dec = self._decode_img(data)
            if dec[:3] == b"\xff\xd8\xff":
                return [200, "image/jpeg", dec, {"Content-Length": str(len(dec))}]
            if dec[:4] == b"\x89PNG":
                return [200, "image/png", dec, {"Content-Length": str(len(dec))}]
            if dec[:4] == b"GIF8":
                return [200, "image/gif", dec, {"Content-Length": str(len(dec))}]
            if len(dec) > 12 and dec[:4] == b"RIFF" and dec[8:12] == b"WEBP":
                return [200, "image/webp", dec, {"Content-Length": str(len(dec))}]
            return [200, "image/jpeg", dec, {"Content-Length": str(len(dec))}]
        except Exception:
            return [500, "text/plain", "decryption failed"]

    def _html(self, url):
        r = self.session.get(url, timeout=15)
        return r.text
    def searchContent(self, key, quick=False, pg=1):
        url = self.host + "/search?wd=" + key
        html = self._html(url)
        videos = self._parse_cards(html)
        return {"list": videos}
