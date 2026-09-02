#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
block.frztdfnc.cc（51暗网镜像）TVBox 爬虫站源
Typecho Mirages 主题 + DPlayer（data-config JSON）
关键: 完整 Chrome UA 才返回完整页面（简短 UA 被服务器截断正文/VIP 视频不下发）
"""
import re
import json
import urllib.request
import urllib.parse
import ssl

try:
    from base.spider import Spider as BaseSpider
except Exception:
    BaseSpider = object


class Spider(BaseSpider):
    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.name = "51awBlock"
        self.host = "https://block.frztdfnc.cc"
        # 图片解密代理（站点图片 AES-CBC 加密，TVBox 无法直接显示）
        # 公网域名（CF 代理到本机 7800）——TVBox 在外网也能用
        self.img_proxy = "https://py.fzcrym.link:1314/bk51_img?u="
        # ⚠️ 必须完整 Chrome UA——简短 UA 服务器截断正文，VIP 视频直接缺失
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.header = {
            "User-Agent": self.ua,
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            # 18+ 年龄确认 cookie——缺失时分类页只有弹窗无内容
            "Cookie": "user-choose=true",
        }
        self.categories = [
            {"type_name": "今日吃瓜", "type_id": "jrrg"},
            {"type_name": "全网热搜", "type_id": "qwrs"},
            {"type_name": "暗网爆料", "type_id": "awcg"},
            {"type_name": "暗网网红", "type_id": "dywh"},
            {"type_name": "每日大赛", "type_id": "mrds"},
            {"type_name": "AI短剧", "type_id": "aidj"},
            {"type_name": "暗网反差", "type_id": "fcll"},
            {"type_name": "暗网校园", "type_id": "xycg"},
            {"type_name": "暗网乱伦", "type_id": "anwangluanlun"},
            {"type_name": "暗网视频", "type_id": "sxzq"},
            {"type_name": "海外大片", "type_id": "hwaw"},
            {"type_name": "AV解说", "type_id": "awdz"},
            {"type_name": "暗网猎奇", "type_id": "awlq"},
            {"type_name": "探花偷拍", "type_id": "tanhua"},
            {"type_name": "每日TOP", "type_id": "meiri-top"},
            {"type_name": "寸止挑战", "type_id": "cunzhi"},
            {"type_name": "动漫天堂", "type_id": "dmtt"},
            {"type_name": "暗史档案", "type_id": "dark-history"},
        ]
        try:
            self.ctx = ssl.create_default_context()
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE
        except Exception:
            self.ctx = None

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def init(self, extend=""):
        pass

    def homeContent(self, filter):
        return {"class": self.categories, "filters": {}, "list": []}

    def homeVideoContent(self):
        html = self.fetch(self.host + "/")
        return {"list": self.parse_cards(html)}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        # 站点翻页格式: /category/{tid}/ 和 /category/{tid}/{n}/（非 page/n/）
        if pg <= 1:
            url = "%s/category/%s/" % (self.host, tid)
        else:
            url = "%s/category/%s/%d/" % (self.host, tid, pg)
        html = self.fetch(url)
        videos = self.parse_cards(html)
        has_next = len(videos) > 0 and ('%s/%d/' % (tid, pg + 1)) in html
        return {
            "list": videos,
            "page": pg,
            "pagecount": pg + 1 if has_next else pg,
            "limit": max(1, len(videos)),
            "total": 999999 if has_next else pg * max(1, len(videos)),
        }

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        vid = str(vid).strip("/").split("/")[-1]
        url = "%s/archives/%s/" % (self.host, vid)
        html = self.fetch(url)
        if not html:
            return {"list": []}

        title, pic, intro = "", "", ""
        tm = re.search(r'<h1 class="post-title[^"]*"[^>]*>([\s\S]*?)</h1>', html)
        if tm:
            title = self.clean(tm.group(1))
        if not title:
            tm = re.search(r'<title>([^<]+?)\s*-\s*51暗网', html)
            if tm:
                title = self.clean(tm.group(1))

        pm = re.search(r"loadBannerDirect\('([^']+\.(?:jpe?g|png|webp)[^']*)'", html)
        if not pm:
            # 详情页封面: itemprop image（正文头图）
            pm = re.search(r'itemprop="image"\s+content="([^"]+)"', html)
        if not pm:
            pm = re.search(r"loadImage\([\"'](https?[^\")]+\.(?:jpe?g|png|webp))", html)
        if pm and "social-default" not in pm.group(1) and "logo" not in pm.group(1):
            pic = self.fix_url(pm.group(1).replace("\\/", "/"))

        # 简介: og:description / meta description
        im = re.search(r'name="description"\s+content="([^"]+)"', html)
        if not im:
            im = re.search(r'property="og:description"\s+content="([^"]+)"', html)
        if im:
            intro = self.clean(im.group(1))[:200]

        # 选集: 所有 dplayer 块（每集一个），playerContent 实时解析拿新 auth_key
        episodes = []
        seen = set()
        for m in re.finditer(r'<div class="dplayer"([^>]+)>', html):
            attrs = m.group(1)
            vm = re.search(r'data-video_id="([\w-]+)"', attrs)
            vt = re.search(r'data-video_title="([^"]*)"', attrs)
            if not vm or vm.group(1) in seen:
                continue
            seen.add(vm.group(1))
            name = vt.group(1) if vt else ("第%d集" % (len(episodes) + 1))
            # 标题去重前缀（长标题只留尾部分集号）
            name = re.sub(r'^.*?(\d{3})$', r'\1', name) if re.search(r'\d{3}$', name) else name
            episodes.append(name + "$" + vm.group(1))
        if not episodes:
            return {"list": []}
        play_url = "#".join(episodes)

        return {
            "list": [{
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": intro,
                "vod_play_from": "51aw",
                "vod_play_url": play_url,
            }]
        }

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg) if str(pg).isdigit() else 1
        wd = urllib.parse.quote(str(key))
        if pg <= 1:
            url = "%s/search/%s/" % (self.host, wd)
        else:
            url = "%s/search/%s/page/%d/" % (self.host, wd, pg)
        html = self.fetch(url)
        videos = self.parse_cards(html)
        has_next = len(videos) > 0 and ('page/%d/' % (pg + 1)) in html
        return {
            "list": videos,
            "page": pg,
            "pagecount": pg + 1 if has_next else pg,
            "limit": 20,
            "total": 999999 if has_next else pg * max(1, len(videos)),
        }

    def playerContent(self, flag, id, vipFlags):
        # id = video_id（如 109323001）→ 从详情页实时解析 m3u8（auth_key 时效 ~1h）
        video_id = str(id)
        # 由 video_id 反推文章 id（video_id = 文章id + 分集序号3位）
        arch_id = video_id[:-3] if len(video_id) > 6 and video_id[-3:].isdigit() else video_id
        html = self.fetch("%s/archives/%s/" % (self.host, arch_id))
        media = ""
        if html:
            for m in re.finditer(r'<div class="dplayer"([^>]+)>', html):
                attrs = m.group(1)
                vm = re.search(r'data-video_id="([\w-]+)"', attrs)
                if not vm or vm.group(1) != video_id:
                    continue
                cm = re.search(r"data-config='(\{.*?\})'", attrs, re.S)
                if cm:
                    try:
                        cfg = json.loads(cm.group(1))
                        v = cfg.get("video", {}) or {}
                        media = (v.get("url") or "").replace("\\/", "/")
                    except Exception:
                        media = ""
                break
        if not media:
            # 兜底: 页面里任意 m3u8
            um = re.search(r'(https?://[^"\'\s]+\.m3u8[^"\'\s]*)', html)
            if um:
                media = um.group(1)
        if not media:
            return {"parse": 1, "url": "%s/archives/%s/" % (self.host, arch_id), "header": "{}"}
        headers = {"User-Agent": self.ua, "Referer": self.host + "/"}
        return {
            "parse": 0,
            "playUrl": "",
            "url": media,
            "header": json.dumps(headers),
        }

    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]

    # ---------- 内部 ----------
    def fetch(self, url):
        try:
            import requests
            r = requests.get(url, headers=self.header, timeout=15, verify=False)
            if r.status_code == 200 and r.text:
                return r.text
        except Exception:
            pass
        try:
            req = urllib.request.Request(url, headers=self.header)
            try:
                resp = urllib.request.urlopen(req, context=self.ctx, timeout=15)
            except TypeError:
                resp = urllib.request.urlopen(req, timeout=15)
            return resp.read().decode("utf-8", errors="replace")
        except Exception:
            return ""

    def fix_url(self, u):
        if not u:
            return ""
        u = u.strip()
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = self.host + u
        if not (u.startswith("http://") or u.startswith("https://")):
            return u
        # 站点加密图片（xustgq.cn）走解密代理；其他图直连
        if "xustgq.cn" in u:
            return self.img_proxy + urllib.parse.quote(u, safe="")
        return u

    def clean(self, s):
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()

    def parse_cards(self, html):
        items = []
        seen = set()
        if not html:
            return items
        blocks = re.split(r'<div class="post-card" id="post-card-', html)
        for b in blocks[1:]:
            vid_m = re.match(r'(\d+)', b)
            if not vid_m:
                continue
            vid = vid_m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            title = ""
            tm = re.search(r'itemprop="headline"\s*>\s*([\s\S]{0,150}?)<', b)
            if tm:
                title = self.clean(tm.group(1))
            if not title:
                tm = re.search(r'title="([^"]{4,80})"', b)
                if tm:
                    title = self.clean(tm.group(1))
            if not title:
                continue
            pic = ""
            pm = re.search(r"loadBannerDirect\('([^']+)'", b)
            if pm:
                pic = self.fix_url(pm.group(1))
            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "",
            })
        return items
