#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#51暗网最新入口：51awn4.com
#51暗网官方邮箱：anwangchigua@gmail.com
#永久域名：https://51aw.com
"""
51暗网 TVBox 爬虫站源（自动获取可用域名）
Typecho Mirages 主题 + DPlayer（data-config JSON）
关键: 完整 Chrome UA 才返回完整页面（简短 UA 被服务器截断正文/VIP 视频不下发）
站点会换域名（DNS 污染/封禁），加载源时自动从地址发布页抓取当前可用域名：
51awn4.com -> JS 跳转壳 -> ehiynkuc.com(Base64编码) -> 站点列表 -> 探测可用 -> 缓存
"""
import re
import json
import base64
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
        self.host = "https://51aw.com"
        # 地址发布页入口（会 301/JS 跳转到最新发布页），可追加新入口
        self.entries = [
            "https://51awn4.com/",
            "https://awcg48.com/",
            "https://51aw.com/",
        ]
        self._host_done = False
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
        self.resolve_host()

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
    def resolve_host(self):
        # 自动获取当前可用播放站，结果缓存，只探测一次
        # 顺序: 已知播放站(快) -> 地址发布页收集的候选(慢) -> 默认
        if getattr(self, "_host_done", False):
            return
        self._host_done = True
        for u in ["https://51aw.com/", "https://block.jfnarrqbo.cc/"]:
            if self._check_host(u):
                self.host = u.rstrip("/")
                return
        cands = []
        for e in self.entries:
            for u in self._harvest_candidates(e):
                if u not in cands:
                    cands.append(u)
        for u in cands:
            if self._check_host(u):
                self.host = u.rstrip("/")
                return

    def _harvest_candidates(self, entry, depth=0):
        # 从发布页提取候选站点域名，支持 JS 跳转壳和 Base64 编码页
        out = []
        if depth > 2:
            return out
        html = self.fetch(entry)
        if not html:
            return out
        source = html
        for b in re.findall(r"Base64\.decode\('([^']+)'\)", html):
            try:
                source += "\n" + base64.b64decode(b).decode("utf-8", "replace")
            except Exception:
                pass
        for m in re.finditer(r'https?://([a-zA-Z0-9._-]+)', source):
            dom = m.group(1).rstrip("/").split("/")[0].split("?")[0]
            if self._is_playable_domain(dom):
                u = "https://" + dom
                if u not in out:
                    out.append(u)
        for m in re.finditer(r'([a-zA-Z0-9-]+\.cloudfront\.net)', source):
            u = "https://" + m.group(1)
            if u not in out:
                out.append(u)
        # JS 跳转壳: <a href="...">加载中</a>
        jm = re.search(r'<a[^>]+href=["\'](https?://[^"\']+)["\'][^>]*>', html)
        if jm and jm.group(1) not in entry:
            for u in self._harvest_candidates(jm.group(1), depth + 1):
                if u not in out:
                    out.append(u)
        return out

    def _is_playable_domain(self, dom):
        dom = dom.lower().rstrip("/").split("/")[0]
        if not re.match(r'^[a-z0-9.-]+\.(com|cc|net|top|xyz|vip|cloudfront\.net)$', dom):
            return False
        skip = ("googletagmanager", "google-analytics", "googlesyndication",
                "googleapis", "gstatic", "google", "cloudflare", "jsdelivr",
                "bootcdn", "unpkg", "picsum", "51awn4", "ehiynkuc")
        return not any(s in dom for s in skip)

    def _check_host(self, u):
        u = u.rstrip("/")
        try:
            h = self.fetch(u + "/category/jrrg/", hdr={"Referer": u + "/"}, timeout=8)
        except Exception:
            return False
        return "post-card" in h

    def fetch(self, url, hdr=None, timeout=15):
        headers = self.header
        if hdr:
            headers = dict(self.header)
            headers.update(hdr)
        try:
            import requests
            r = requests.get(url, headers=headers, timeout=timeout, verify=False)
            if r.status_code == 200 and r.text:
                return r.text
        except Exception:
            pass
        try:
            req = urllib.request.Request(url, headers=headers)
            try:
                resp = urllib.request.urlopen(req, context=self.ctx, timeout=timeout)
            except TypeError:
                resp = urllib.request.urlopen(req, timeout=timeout)
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
