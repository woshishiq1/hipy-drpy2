# -*- coding: utf-8 -*-
# 青鸟影视 (qndjy.com) OK影视爬虫插件 - 高速修复版
# 修复：搜索接口、播放解析、加载速度
import sys
import re
import json
import urllib.parse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "青鸟影视"

    def init(self, extend=""):
        super().init(extend)
        self.site_url = "https://qndjy.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.site_url + "/",
        }
        # 高速连接池：复用TCP连接，极大提升加载速度
        self.sess = requests.Session()
        retries = Retry(total=1, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=retries)
        self.sess.mount("https://", adapter)
        self.sess.mount("http://", adapter)

        self.page_size = 24
        self.total = 99999
        self.default_pic = "https://pic.rmb.bdstatic.com/bjh/user/default.png"

        # 分类映射（本地写死，避免每次请求首页）
        self.cate_map = {
            "1": "电影",
            "2": "连续剧", 
            "3": "动漫",
            "4": "综艺"
        }
        # 二级分类映射
        self.sub_cate_map = {
            "1": "电影", "5": "动作片", "6": "喜剧片", "7": "爱情片",
            "8": "科幻片", "9": "恐怖片", "10": "剧情片", "11": "战争片",
            "12": "悬疑片", "13": "犯罪片", "14": "惊悚片", "15": "冒险片",
            "16": "纪录片", "17": "动画片", "18": "微影视", "33": "伦理片", "19": "其他片",
            "2": "连续剧", "20": "国产剧", "21": "港台剧", "22": "日韩剧", "23": "欧美剧", "24": "海外剧",
            "3": "动漫", "25": "国产动漫", "26": "日本动漫", "27": "欧美动漫", "28": "海外动漫",
            "4": "综艺", "29": "内地综艺", "30": "港台综艺", "31": "日韩综艺", "32": "欧美综艺",
        }
        # 筛选条件
        self.area_map = ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国", "德国", "泰国", "印度", "新加坡", "其他"]
        self.year_map = [str(y) for y in range(2026, 2009, -1)]

        self.log("init done. site: " + self.site_url)

    def log(self, msg):
        try:
            sys.stdout.write("[青鸟影视] " + str(msg) + "\n")
            sys.stdout.flush()
        except Exception:
            pass

    def fetch(self, url, timeout=8):
        try:
            res = self.sess.get(url, headers=self.headers, timeout=timeout, verify=False)
            res.encoding = "utf-8"
            return res
        except Exception as e:
            self.log("fetch error: " + repr(e) + " url=" + url)
            return None

    # ================= 核心提取（速度优化：单次正则提取所有字段） =================

    def _extract_list(self, html):
        """从列表HTML提取影片，优化版：一次正则匹配所有字段"""
        videos = []
        seen = set()
        # 匹配 videoul-li 整块
        items = re.findall(
            r'<li class="videoul-li">\s*<a href="(/news/\d+\.html)"[^>]*>.*?<img[^>]+lay-src="([^"]+)"[^>]*>.*?(?:<p class="videoul-tips[^"]*">.*?<span[^>]*>([^<]+)</span>.*?</p>)?.*?<p class="pone videoul-title">([^<]+)</p>.*?</a>\s*</li>',
            html, re.S
        )
        for href, pic, remark, name in items:
            if href in seen:
                continue
            seen.add(href)
            if pic.startswith("//"):
                pic = "https:" + pic
            elif pic and not pic.startswith("http"):
                pic = self.site_url + (pic if pic.startswith("/") else "/" + pic)
            videos.append({
                "vod_id": href,
                "vod_name": name.strip(),
                "vod_pic": pic or self.default_pic,
                "vod_remarks": remark.strip() if remark else "",
                "style": {"type": "rect", "ratio": 0.75}
            })
        return videos

    def _get_filters(self, tid):
        filters = []
        type_opts = []
        if tid == "1":
            type_opts = [{"n": v, "v": k} for k, v in self.sub_cate_map.items() if k in ["1","5","6","7","8","9","10","11","12","13","14","15","16","17","18","33","19"]]
        elif tid == "2":
            type_opts = [{"n": v, "v": k} for k, v in self.sub_cate_map.items() if k in ["2","20","21","22","23","24"]]
        elif tid == "3":
            type_opts = [{"n": v, "v": k} for k, v in self.sub_cate_map.items() if k in ["3","25","26","27","28"]]
        elif tid == "4":
            type_opts = [{"n": v, "v": k} for k, v in self.sub_cate_map.items() if k in ["4","29","30","31","32"]]

        if type_opts:
            filters.append({"key": "type", "name": "类型", "value": type_opts})
        filters.append({"key": "area", "name": "地区", "value": [{"n": a, "v": a} for a in self.area_map]})
        filters.append({"key": "year", "name": "年份", "value": [{"n": y, "v": y} for y in self.year_map]})
        return filters

    # ================= 首页 =================

    def homeContent(self, filter):
        cate_list = [{"type_name": v, "type_id": k} for k, v in self.cate_map.items()]
        videos = []
        res = self.fetch(self.site_url + "/")
        if res and res.ok:
            videos = self._extract_list(res.text)

        filters = {}
        for k in self.cate_map.keys():
            filters[k] = self._get_filters(k)

        return {"class": cate_list, "list": videos[:30], "filters": filters}

    # ================= 分类（支持二级分类+地区+年份筛选） =================

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        sub_type = extend.get("type", tid)
        area = extend.get("area", "")
        year = extend.get("year", "")

        # 构建URL：该站分类格式为 /category/{id}/{page}.html
        # 地区和年份筛选格式推测为 /vod/cid/{cid}/area/{area}/year/{year}.html
        if area or year:
            path = f"/vod/cid/{tid}"
            if area:
                path += f"/area/{urllib.parse.quote(area)}"
            if year:
                path += f"/year/{year}"
            if pg > 1:
                path += f"/page/{pg}"
            path += ".html"
            url = self.site_url + path
        else:
            url = f"{self.site_url}/category/{sub_type}/{pg}.html"

        res = self.fetch(url)
        videos = []
        if res and res.ok:
            videos = self._extract_list(res.text)

        pagecount = pg + 1 if len(videos) >= self.page_size else pg
        if not videos:
            pagecount = pg

        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": self.page_size,
            "total": self.total
        }

    # ================= 详情 =================

    def detailContent(self, ids):
        vod_id = ids[0] if ids else ""
        if not vod_id:
            return {"list": []}

        detail_url = vod_id if vod_id.startswith("http") else self.site_url + vod_id
        res = self.fetch(detail_url)
        if not res or not res.ok:
            return {"list": [{"vod_id": vod_id, "vod_name": "获取详情失败"}]}

        html = res.text

        # 标题
        title = ""
        m = re.search(r'<div class="vod-info-right">.*?<h3>(.*?)</span>', html, re.S)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not title:
            m = re.search(r'<div class="pageHead-text">([^<]+)</div>', html)
            if m:
                title = m.group(1).strip()

        # 图片
        pic = ""
        m = re.search(r'<div class="vod-info-pic"><img[^>]+lay-src="([^"]+)"', html)
        if m:
            pic = m.group(1)
            if pic.startswith("//"):
                pic = "https:" + pic
            elif pic and not pic.startswith("http"):
                pic = self.site_url + pic

        # 类型
        type_name = ""
        m = re.search(r'<h3>.*?<span>(.*?)</span></h3>', html, re.S)
        if m:
            type_name = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        # 年代/地区/语言
        year = area = lang = ""
        m = re.search(r'<p>\d{4}[^<]*</p>', html)
        if m:
            info = re.sub(r'<[^>]+>', '', m.group(0))
            parts = [p.strip() for p in info.split("•")]
            if len(parts) >= 1 and re.match(r"\d{4}", parts[0]):
                year = parts[0]
            if len(parts) >= 2:
                area = parts[1]
            if len(parts) >= 3:
                lang = parts[2]

        # 导演/演员/简介
        director = ""
        m = re.search(r'<p>导演：([^<]+)</p>', html)
        if m:
            director = m.group(1).strip()

        actor = ""
        m = re.search(r'<p class="actor">主演：([^<]+)</p>', html)
        if m:
            actor = m.group(1).strip()

        content = ""
        m = re.search(r'<div class="vod-info-text">.*?<span>简介：</span>(.*?)<div class="text-more">', html, re.S)
        if m:
            content = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        # 提取多线路播放列表
        play_from = []
        play_url = []

        # 提取所有源
        sources = re.findall(r'<li data-id="(\d+)"[^>]*>(.*?)</li>', html)
        source_map = {}
        for sid, sname in sources:
            sname = re.sub(r'<[^>]+>', '', sname).strip()
            source_map[sid] = sname or "默认线路"

        # 提取每个源的剧集
        for sid, sname in source_map.items():
            pattern = r'<ul class="play-ji-ul[^"]*" id="zu-' + sid + r'">(.*?)</ul>'
            m = re.search(pattern, html, re.S)
            if not m:
                continue
            eps = []
            seen = set()
            for em in re.finditer(r'<a href="(/play/[^"]+\.html)">(.*?)</a>', m.group(1), re.S):
                ep_url, ep_text = em.group(1), em.group(2)
                ep_name = re.sub(r'<[^>]+>', '', ep_text).strip()
                if ep_url and ep_name and ep_url not in seen:
                    seen.add(ep_url)
                    eps.append(f"{ep_name}${ep_url}")
            if eps:
                play_from.append(sname)
                play_url.append("#".join(eps))

        if not play_from:
            # 兜底
            all_eps = re.findall(r'<a href="(/play/\d+/\d+\.html)">(.*?)</a>', html, re.S)
            if all_eps:
                eps = []
                seen = set()
                for ep_url, ep_text in all_eps:
                    ep_name = re.sub(r'<[^>]+>', '', ep_text).strip()
                    if ep_url and ep_name and ep_url not in seen:
                        seen.add(ep_url)
                        eps.append(f"{ep_name}${ep_url}")
                if eps:
                    play_from.append("默认线路")
                    play_url.append("#".join(eps))

        if not play_from:
            return {"list": [{"vod_id": vod_id, "vod_name": title or "未知", "vod_pic": pic}]}

        return {
            "list": [{
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "type_name": type_name,
                "vod_year": year,
                "vod_area": area,
                "vod_lang": lang,
                "vod_director": director,
                "vod_actor": actor,
                "vod_content": content,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }]
        }

    # ================= 搜索（已修复为正确接口） =================

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg) if str(pg).isdigit() else 1
        videos = []

        # 正确的搜索接口：/search.html?key=关键词&page=页码
        url = f"{self.site_url}/search.html?key={urllib.parse.quote(key)}"
        if pg > 1:
            url += f"&page={pg}"

        res = self.fetch(url)
        if res and res.ok:
            videos = self._extract_list(res.text)
            self.log(f"搜索[{key}]返回 {len(videos)} 个结果")
        else:
            self.log(f"搜索失败: {url}")

        pagecount = pg + 1 if len(videos) >= self.page_size else pg
        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": self.page_size,
            "total": len(videos) if len(videos) < self.total else self.total
        }

    # ================= 播放（速度优化：优先直链，否则WebView解析） =================

    def playerContent(self, flag, id, vipFlags):
        raw_id = id.split("$")[-1].strip() if "$" in id else id.strip()
        if not raw_id:
            return {"parse": 0, "url": "", "header": self.headers}

        play_url = raw_id if raw_id.startswith("http") else self.site_url + raw_id

        # 如果已经是直链，直接返回（极速播放）
        low = play_url.lower()
        if any(ext in low for ext in [".m3u8", ".mp4", ".flv", ".ts", ".mkv"]):
            return {
                "parse": 0,
                "url": play_url,
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.site_url + "/"
                }
            }

        # 访问播放页，尝试提取真实地址
        res = self.fetch(play_url)
        if not res or not res.ok:
            return {"parse": 0, "url": "", "header": self.headers}

        html = res.text

        # 1. 查找iframe嵌入（第三方解析常见方式）
        m = re.search(r'<iframe[^>]+src="([^"]+)"', html, re.S)
        if m:
            iframe = m.group(1)
            if iframe.startswith("//"):
                iframe = "https:" + iframe
            elif iframe and not iframe.startswith("http"):
                iframe = self.site_url + iframe
            # iframe交给APP WebView解析
            return {
                "parse": 1,
                "url": iframe,
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": play_url
                }
            }

        # 2. 查找页面中的m3u8/mp4直链
        m = re.search(r'(https?://[^\s\'"<>]+\.m3u8[^\s\'"<>]*)', html)
        if m:
            return {
                "parse": 0,
                "url": m.group(1),
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": play_url
                }
            }

        m = re.search(r'(https?://[^\s\'"<>]+\.mp4[^\s\'"<>]*)', html)
        if m:
            return {
                "parse": 0,
                "url": m.group(1),
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": play_url
                }
            }

        # 3. 查找JSON播放数据
        m = re.search(r'var\s+player_\w+\s*=\s*({.*?})</script>', html, re.S)
        if m:
            try:
                data = json.loads(m.group(1))
                real = data.get("url", "")
                if real:
                    return {
                        "parse": 0 if any(ext in real.lower() for ext in [".m3u8", ".mp4"]) else 1,
                        "url": real,
                        "header": {
                            "User-Agent": self.headers["User-Agent"],
                            "Referer": play_url
                        }
                    }
            except Exception:
                pass

        # 4. 兜底：返回播放页地址让APP解析（兼容所有加密/动态加载）
        return {
            "parse": 1,
            "url": play_url,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.site_url + "/"
            }
        }

    def liveContent(self, url):
        return {"list": []}

    def localProxy(self, param):
        return None
