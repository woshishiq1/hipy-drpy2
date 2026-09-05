# coding=utf-8
"""
目标站: 风尚影视 (probabyml.com)
修复:
  - 精选页增加到36个视频
  - AI漫剧分类(tid=47)不过滤，正常显示全部内容
  - 电影分类过滤后追补5页，避免空页
"""
import re
import sys
import json
import urllib.parse
import urllib.request
import gzip
import datetime
from collections import defaultdict

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    _RE_VODLIST = re.compile(
        r'<a(?=[^>]*class="ousb-item")[^>]*href="(/(?:t|video)/(\d+)\.html)"[^>]*title="([^"]+)"[^>]*>'
        r'.*?<img[^>]*(?:data-original|src)="([^"]+)"[^>]*>'
        r'.*?<span[^>]*>([^<]+)</span>',
        re.DOTALL
    )
    _RE_PAGE_LAST = re.compile(r'href="/tv/[^"]*?/page/(\d+)\.html"[^>]*>尾页')
    _RE_PAGE_NUMS = re.compile(r'/tv/[^"]*?/page/(\d+)\.html')
    _RE_DETAIL_TITLE = re.compile(r'<h1>(.*?)</h1>', re.DOTALL)
    _RE_DETAIL_PIC = re.compile(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"')
    _RE_DETAIL_DESC = re.compile(r'<p class="ousb-desc[^"]*"[^>]*>(.*?)</p>', re.DOTALL)
    _RE_DETAIL_DIRECTOR = re.compile(r'导演：<b>(.*?)</b>', re.DOTALL)
    _RE_DETAIL_ACTOR = re.compile(r'主演：<b>(.*?)</b>', re.DOTALL)
    _RE_DETAIL_TYPE = re.compile(r'类型：<b>.*?>(.*?)</a>', re.DOTALL)
    _RE_DETAIL_AREA = re.compile(r'地区：<b>.*?>(.*?)</a>', re.DOTALL)
    _RE_DETAIL_YEAR = re.compile(r'年份：<b>.*?(\d{4})</a>')
    _RE_DETAIL_LANG = re.compile(r'语言：<b>.*?>(.*?)</a>', re.DOTALL)
    _RE_DETAIL_STATUS = re.compile(r'状态：<b>(.*?)</b>', re.DOTALL)
    _RE_PLAY_LINES = re.compile(r'<button[^>]*data-sid="(\d+)"[^>]*>(.*?)</button>', re.DOTALL)
    _RE_PLAY_LINKS = re.compile(r'<a[^>]*href="(/play/(\d+)/(\d+)/(\d+)\.html)"[^>]*>(.*?)</a>', re.DOTALL)
    _RE_PLAYER_DATA = re.compile(r'var\s+player_aaaa\s*=\s*({.*?})</script>', re.DOTALL)

    # 在普通分类中需要过滤掉的标签
    _SKIP_TAGS = ['AI漫剧']

    def init(self, extend=""):
        self.site_url = "https://www.probabyml.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': self.site_url + "/",
            'Connection': 'keep-alive',
        }
        self.default_pic = "https://pic.rmb.bdstatic.com/bjh/user/default.png"
        self._filters = None

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if not url.startswith("http"):
            return urllib.parse.urljoin(self.site_url, url)
        return url

    def _fetch(self, url):
        try:
            req = urllib.request.Request(url, headers=self.headers)
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            response = urllib.request.urlopen(req, timeout=15, context=ctx)
            data = response.read()
            if 'gzip' in response.headers.get('Content-Encoding', ''):
                data = gzip.decompress(data)
            return data.decode('utf-8', errors='ignore')
        except Exception as e:
            self.log(f"请求失败: {url} - {e}")
            return ""

    def _should_skip(self, note, allow_ai=False):
        """判断是否需要跳过该视频"""
        if allow_ai:
            return False
        for tag in self._SKIP_TAGS:
            if tag in note:
                return True
        return False

    def _extract_videos(self, html, allow_ai=False):
        """提取视频列表"""
        videos = []
        seen = set()
        for match in self._RE_VODLIST.finditer(html):
            vid = match.group(2)
            title = match.group(3).strip()
            pic = match.group(4).strip()
            note = match.group(5).strip()
            if vid in seen:
                continue
            if self._should_skip(note, allow_ai):
                continue
            seen.add(vid)
            videos.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self._fix_url(pic),
                "vod_remarks": note
            })
        return videos

    def _get_pagecount(self, html):
        m = self._RE_PAGE_LAST.search(html)
        if m:
            return int(m.group(1))
        pages = self._RE_PAGE_NUMS.findall(html)
        if pages:
            return max(int(p) for p in pages)
        return 1

    def _build_cat_url(self, tid, page, paths=None):
        if not paths:
            if page == 1:
                return f"{self.site_url}/tv/{tid}.html"
            else:
                return f"{self.site_url}/tv/{tid}-{page}.html"
        else:
            base = f"/tv/{tid}/" + "/".join(paths)
            if page == 1:
                return f"{self.site_url}{base}.html"
            else:
                return f"{self.site_url}{base}/page/{page}.html"

    def _get_filters(self):
        if self._filters is not None:
            return self._filters

        movie_classes = [
            {"n": "全部", "v": ""}, {"n": "剧情", "v": "剧情"}, {"n": "喜剧", "v": "喜剧"},
            {"n": "动作", "v": "动作"}, {"n": "恐怖", "v": "恐怖"}, {"n": "爱情", "v": "爱情"},
            {"n": "科幻", "v": "科幻"}, {"n": "惊悚", "v": "惊悚"}, {"n": "战争", "v": "战争"},
            {"n": "犯罪", "v": "犯罪"}, {"n": "悬疑", "v": "悬疑"}, {"n": "奇幻", "v": "奇幻"},
        ]
        tv_classes = [
            {"n": "全部", "v": ""}, {"n": "剧情", "v": "剧情"}, {"n": "喜剧", "v": "喜剧"},
            {"n": "动作", "v": "动作"}, {"n": "爱情", "v": "爱情"}, {"n": "科幻", "v": "科幻"},
            {"n": "悬疑", "v": "悬疑"}, {"n": "古装", "v": "古装"}, {"n": "都市", "v": "都市"},
            {"n": "家庭", "v": "家庭"}, {"n": "历史", "v": "历史"}, {"n": "武侠", "v": "武侠"},
        ]
        zongyi_classes = [
            {"n": "全部", "v": ""}, {"n": "真人秀", "v": "真人秀"}, {"n": "选秀", "v": "选秀"},
            {"n": "情感", "v": "情感"}, {"n": "访谈", "v": "访谈"}, {"n": "音乐", "v": "音乐"},
            {"n": "美食", "v": "美食"}, {"n": "纪实", "v": "纪实"}, {"n": "生活", "v": "生活"},
        ]
        dongman_classes = [
            {"n": "全部", "v": ""}, {"n": "情感", "v": "情感"}, {"n": "科幻", "v": "科幻"},
            {"n": "热血", "v": "热血"}, {"n": "搞笑", "v": "搞笑"}, {"n": "冒险", "v": "冒险"},
            {"n": "校园", "v": "校园"}, {"n": "动作", "v": "动作"}, {"n": "运动", "v": "运动"},
            {"n": "战争", "v": "战争"}, {"n": "励志", "v": "励志"}, {"n": "亲子", "v": "亲子"},
        ]
        duanju_classes = [
            {"n": "全部", "v": ""}, {"n": "穿越", "v": "穿越"}, {"n": "重生", "v": "重生"},
            {"n": "古装", "v": "古装"}, {"n": "都市", "v": "都市"}, {"n": "甜宠", "v": "甜宠"},
            {"n": "虐恋", "v": "虐恋"}, {"n": "逆袭", "v": "逆袭"}, {"n": "悬疑", "v": "悬疑"},
        ]

        areas = [
            {"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
            {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"}, {"n": "韩国", "v": "韩国"},
            {"n": "日本", "v": "日本"}, {"n": "欧美", "v": "欧美"}, {"n": "英国", "v": "英国"},
            {"n": "法国", "v": "法国"}, {"n": "泰国", "v": "泰国"}, {"n": "印度", "v": "印度"},
            {"n": "加拿大", "v": "加拿大"}, {"n": "西班牙", "v": "西班牙"}, {"n": "德国", "v": "德国"},
        ]

        langs = [
            {"n": "全部", "v": ""}, {"n": "国语", "v": "国语"}, {"n": "粤语", "v": "粤语"},
            {"n": "英语", "v": "英语"}, {"n": "日语", "v": "日语"}, {"n": "韩语", "v": "韩语"},
            {"n": "法语", "v": "法语"}, {"n": "西班牙语", "v": "西班牙语"}, {"n": "泰语", "v": "泰语"},
            {"n": "德语", "v": "德语"}, {"n": "意大利语", "v": "意大利语"}, {"n": "俄语", "v": "俄语"},
            {"n": "印地语", "v": "印地语"}, {"n": "其它", "v": "其它"},
        ]

        current_year = datetime.datetime.now().year
        years = [{"n": "全部", "v": ""}]
        for y in range(current_year + 1, 1999, -1):
            years.append({"n": str(y), "v": str(y)})

        sorts = [
            {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"},
        ]

        def make(class_list):
            return [
                {"key": "class", "name": "类型", "value": class_list},
                {"key": "area", "name": "地区", "value": areas},
                {"key": "lang", "name": "语言", "value": langs},
                {"key": "year", "name": "年份", "value": years},
                {"key": "by", "name": "排序", "value": sorts},
            ]

        self._filters = {
            "1": make(movie_classes),
            "2": make(tv_classes),
            "3": make(duanju_classes),
            "4": make(dongman_classes),
            "5": make(zongyi_classes),
        }
        return self._filters

    # ========== 首页 ==========

    def homeContent(self, filter):
        categories = [
            {"type_id": "1", "type_name": "电影"},
            {"type_id": "2", "type_name": "电视剧"},
            {"type_id": "3", "type_name": "短剧"},
            {"type_id": "4", "type_name": "动漫"},
            {"type_id": "5", "type_name": "综艺"},
            {"type_id": "47", "type_name": "AI漫剧"},
            {"type_id": "48", "type_name": "网飞新剧"},
        ]
        html = self._fetch(self.site_url + "/")
        videos = self._extract_videos(html) if html else []
        # 修复: 首页返回36个视频，不再限制为10个
        return {
            "class": categories,
            "list": videos[:36],
            "filters": self._get_filters()
        }

    def homeVideoContent(self):
        return {"list": []}

    # ========== 分类 ==========

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except:
                extend = {}
        if not extend:
            extend = {}

        for k in list(extend.keys()):
            if extend[k] == "" or extend[k] is None:
                del extend[k]

        paths = []
        has_filter = False

        if extend.get("class"):
            paths.append(f"class/{urllib.parse.quote(extend['class'])}")
            has_filter = True
        if extend.get("area"):
            paths.append(f"area/{urllib.parse.quote(extend['area'])}")
            has_filter = True
        if extend.get("lang"):
            paths.append(f"lang/{urllib.parse.quote(extend['lang'])}")
            has_filter = True
        if extend.get("year"):
            paths.append(f"year/{extend['year']}")
            has_filter = True

        by = extend.get("by", "time")
        if by and by != "time":
            paths.append(f"by/{by}")
            has_filter = True

        url = self._build_cat_url(tid, page, paths if paths else None)
        self.log(f"[category] tid={tid} page={page} url={url}")
        html = self._fetch(url)

        # fallback
        if not html or not self._extract_videos(html, allow_ai=(tid == "47")):
            if has_filter:
                fb_url = self._build_cat_url(tid, page)
            else:
                fb_url = f"{self.site_url}/tv/{tid}/page/{page}.html"
            self.log(f"[category fallback] {fb_url}")
            fb_html = self._fetch(fb_url)
            if fb_html and self._extract_videos(fb_html, allow_ai=(tid == "47")):
                html = fb_html

        if not html or not self._extract_videos(html, allow_ai=(tid == "47")):
            if page > 1:
                fb2_url = f"{self.site_url}/tv/{tid}-{page}.html"
                self.log(f"[category fallback2] {fb2_url}")
                fb2_html = self._fetch(fb2_url)
                if fb2_html and self._extract_videos(fb2_html, allow_ai=(tid == "47")):
                    html = fb2_html

        # 关键修复: AI漫剧分类(tid=47)不过滤
        allow_ai = (tid == "47")
        videos = []
        pagecount = 1
        if html:
            videos = self._extract_videos(html, allow_ai=allow_ai)
            pagecount = self._get_pagecount(html)

        # 追补: 若过滤后视频太少，自动抓取后续页面，最多追5页
        if len(videos) < 5 and page < pagecount:
            for next_page in range(page + 1, min(page + 6, pagecount + 1)):
                next_url = self._build_cat_url(tid, next_page, paths if paths else None)
                self.log(f"[category追补] tid={tid} 第{page}页不足，抓取第{next_page}页")
                next_html = self._fetch(next_url)
                if next_html:
                    next_videos = self._extract_videos(next_html, allow_ai=allow_ai)
                    for v in next_videos:
                        if v["vod_id"] not in [x["vod_id"] for x in videos]:
                            videos.append(v)
                    if len(videos) >= 5:
                        break

        self.log(f"[category result] tid={tid} videos={len(videos)} pagecount={pagecount}")
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 36,
            "total": pagecount * 36
        }

    # ========== 搜索 ==========

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)

        if page == 1:
            url = f"{self.site_url}/search.html?wd={keyword}"
        else:
            url = f"{self.site_url}/search.html?wd={keyword}&page={page}"

        self.log(f"[search] key={key} page={page} url={url}")
        html = self._fetch(url)
        videos = []
        pagecount = 1
        if html:
            videos = self._extract_videos(html)
            pagecount = self._get_pagecount(html)

        self.log(f"[search result] videos={len(videos)} pagecount={pagecount}")
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 36,
            "total": pagecount * 36
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ========== 详情 ==========

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0])

        urls_to_try = [
            f"{self.site_url}/t/{vid}.html",
            f"{self.site_url}/video/{vid}.html",
        ]

        html = ""
        for url in urls_to_try:
            html = self._fetch(url)
            if html and self._RE_DETAIL_TITLE.search(html):
                break

        if not html:
            return {"list": []}

        name = vid
        year = ""
        title_match = self._RE_DETAIL_TITLE.search(html)
        if title_match:
            name = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            year_m = re.search(r'(\d{4})', name)
            if year_m:
                year = year_m.group(1)

        pic = self.default_pic
        pic_match = self._RE_DETAIL_PIC.search(html)
        if pic_match:
            pic = self._fix_url(pic_match.group(1))

        content = ""
        content_match = self._RE_DETAIL_DESC.search(html)
        if content_match:
            content = re.sub(r'<[^>]+>', '', content_match.group(1)).strip()

        director = ""
        actor = ""
        type_name = ""
        area = ""
        lang = ""
        status = ""

        d_m = self._RE_DETAIL_DIRECTOR.search(html)
        if d_m:
            director = re.sub(r'<[^>]+>', '', d_m.group(1)).strip()
        a_m = self._RE_DETAIL_ACTOR.search(html)
        if a_m:
            actor = re.sub(r'<[^>]+>', '', a_m.group(1)).strip()
        t_m = self._RE_DETAIL_TYPE.search(html)
        if t_m:
            type_name = re.sub(r'<[^>]+>', '', t_m.group(1)).strip()
        ar_m = self._RE_DETAIL_AREA.search(html)
        if ar_m:
            area = re.sub(r'<[^>]+>', '', ar_m.group(1)).strip()
        la_m = self._RE_DETAIL_LANG.search(html)
        if la_m:
            lang = re.sub(r'<[^>]+>', '', la_m.group(1)).strip()
        st_m = self._RE_DETAIL_STATUS.search(html)
        if st_m:
            status = re.sub(r'<[^>]+>', '', st_m.group(1)).strip()

        play_from = []
        play_url = []

        line_buttons = self._RE_PLAY_LINES.findall(html)
        line_map = {}
        for sid, name_html in line_buttons:
            line_name = re.sub(r'<[^>]+>', '', name_html).strip()
            if not line_name:
                line_name = f"线路{sid}"
            line_map[sid] = line_name

        all_links = self._RE_PLAY_LINKS.findall(html)
        sid_eps = defaultdict(list)
        for href, v_id, sid, nid, ep_name in all_links:
            if v_id == vid:
                ep_clean = re.sub(r'<[^>]+>', '', ep_name).strip()
                if ep_clean:
                    sid_eps[sid].append(f"{ep_clean}${href}")

        for sid in sorted(sid_eps.keys(), key=lambda x: int(x)):
            ep_list = sid_eps[sid]
            if ep_list:
                line_name = line_map.get(sid, f"线路{sid}")
                play_from.append(line_name)
                play_url.append("#".join(ep_list))

        if not play_url:
            immediate = re.search(r'href="(/play/\d+/\d+/1\.html)"[^>]*>.*立即播放', html)
            if immediate:
                play_from = ["默认线路"]
                play_url = [f"立即播放${immediate.group(1)}"]

        if not play_url:
            play_from = ["默认线路"]
            play_url = [f"播放${vid}"]

        result = [{
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_year": year,
            "vod_area": area,
            "vod_lang": lang,
            "vod_type": type_name,
            "vod_remarks": status,
            "vod_play_from": '$$$'.join(play_from),
            "vod_play_url": '$$$'.join(play_url)
        }]
        return {"list": result}

    # ========== 播放 ==========

    def playerContent(self, flag, id, vipFlags):
        play_url = id
        if "$" in id:
            play_url = id.split("$")[-1]

        if not play_url.startswith("/play/"):
            if play_url.startswith("http"):
                return {"parse": 0, "url": play_url, "header": self.headers}
            return {"parse": 1, "url": f"{self.site_url}/t/{play_url}.html", "header": self.headers}

        url = f"{self.site_url}{play_url}"
        html = self._fetch(url)
        if html:
            player_match = self._RE_PLAYER_DATA.search(html)
            if player_match:
                try:
                    player_json = json.loads(player_match.group(1))
                    m3u8 = player_json.get("url", "").strip()
                    if m3u8 and m3u8.startswith("http"):
                        return {
                            "parse": 0,
                            "url": m3u8,
                            "header": {
                                'User-Agent': self.headers['User-Agent'],
                                'Referer': self.site_url + "/",
                                'Accept': '*/*',
                            }
                        }
                except json.JSONDecodeError:
                    pass

        return {
            "parse": 1,
            "url": url,
            "header": self.headers
        }

    def isVideoFormat(self, url):
        return '.m3u8' in url or '.mp4' in url or url.startswith('http')

    def manualVideoCheck(self):
        return False
