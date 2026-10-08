# -*- coding: utf-8 -*-
"""
浪巢福地 - 四壳通用Python Spider
站点: https://ayw.lcfd3.lat/lcfd/
架构: 苹果CMS(MacCMS)
防护: Cloudflare，safari17_2_ios指纹穿透
播放: 播放页player_data.url直接m3u8直链
"""

import re
import json

try:
    from base.spider import Spider
except Exception:
    class Spider:
        def init(self, extend=""): pass
        def homeContent(self, *args): return {"class": [], "filters": {}, "list": []}
        def homeVideoContent(self, *args): return {"list": []}
        def categoryContent(self, tid, pg, *args): return {"page": 1, "pagecount": 1, "limit": 90, "total": 0, "list": []}
        def detailContent(self, ids, *args): return {"list": []}
        def searchContent(self, key, pg, *args): return {"page": 1, "pagecount": 1, "limit": 90, "total": 0, "list": []}
        def playerContent(self, flag, id, vipFlags, *args): return {"parse": 0, "jx": 0, "url": "", "header": {}}
        def localProxy(self, flag, id, *args): return [404, "text/plain", ""]
        def isVideoFormat(self, url, *args): return False
        def manualVideoCheck(self, *args): return False
        def action(self, action, *args): return ""
        def getDependence(self, *args): return ""
        def destroy(self, *args): pass

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
BASE_URL = "https://ayw.lcfd3.lat"
BASE_PATH = "/lcfd"

# 分类（12个，古典脱敏）
CATEGORIES = [
    {"type_id": "1", "type_name": "禁脔"},
    {"type_id": "2", "type_name": "红杏出墙"},
    {"type_id": "3", "type_name": "霓裳制服"},
    {"type_id": "4", "type_name": "弄玉"},
    {"type_id": "5", "type_name": "窥帘"},
    {"type_id": "20", "type_name": "私录自拍"},
    {"type_id": "21", "type_name": "中原国产"},
    {"type_id": "22", "type_name": "断袖"},
    {"type_id": "23", "type_name": "东瀛日韩"},
    {"type_id": "24", "type_name": "西域欧美"},
    {"type_id": "25", "type_name": "风月三级"},
    {"type_id": "26", "type_name": "丹青动漫"},
]

# 古典映射表
CLASSICAL_MAP = {
    "乱伦": "禁脔", "强奸": "强占", "强奸乱伦": "强占禁脔",
    "出轨": "红杏出墙", "制服": "霓裳", "诱惑": "情思",
    "自慰": "弄玉", "偷拍": "窥帘", "偷窥": "窥帘",
    "自拍": "私录", "国产": "中原", "同性": "断袖",
    "日韩": "东瀛", "欧美": "西域", "三级": "风月", "动漫": "丹青",
    "无码": "素纱", "有码": "遮面", "人妻": "罗敷", "熟女": "徐娘",
    "口交": "含朱", "颜射": "玉露", "巨乳": "丰盈", "臀": "玉臀",
    "裸体": "玉体", "裸露": "半褪", "性交": "交欢", "做爱": "云雨",
    "高潮": "云端", "群交": "合卺", "肛交": "后庭", "迷奸": "迷魂",
    "灌醉": "醉魂", "爆操": "狂风", "约炮": "赴约", "绿帽": "绿巾",
    "成人": "风月", "色情": "春宫", "淫": "风月", "黄色": "春宫",
    "淫秽": "猥亵", "激情": "云雨", "欲": "情思", "广告": "告示",
}

# 未成年关键词（铁律13，跳过不展示）
MINOR_KEYWORDS = ["萝莉", "幼女", "少女", "童", "teen", "loli", "schoolgirl", "未成年", "小学生", "初中生"]


def desensitize(text):
    if not text:
        return text
    result = text
    for key in sorted(CLASSICAL_MAP.keys(), key=len, reverse=True):
        if key in result:
            result = result.replace(key, CLASSICAL_MAP[key])
    return result


try:
    from curl_cffi import requests as cffi_req
    HAS_CFFI = True
except Exception:
    HAS_CFFI = False

try:
    import requests as _req
    HAS_REQUESTS = True
except Exception:
    HAS_REQUESTS = False


class Spider(Spider):
    def __init__(self):
        self.base_url = BASE_URL
        self._last_error = ""

    def init(self, extend=""):
        if extend:
            try:
                d = json.loads(extend) if isinstance(extend, str) else extend
                if d.get("siteUrl"):
                    self.base_url = d["siteUrl"].rstrip("/")
            except Exception:
                pass
        print(f"[浪巢福地] 初始化: {self.base_url}")

    def _fetch(self, path, retries=3):
        url = self.base_url + path
        self._last_error = ""
        headers = {"User-Agent": UA, "Accept": "text/html", "Accept-Language": "zh-CN,zh;q=0.9"}

        if HAS_CFFI:
            for attempt in range(retries):
                try:
                    r = cffi_req.get(url, impersonate="safari17_2_ios", timeout=20)
                    if r.status_code == 200 and len(r.text) > 500:
                        return r.text
                except Exception as e:
                    self._last_error = f"cffi:{e}"
            try:
                r = cffi_req.get(url, impersonate="chrome131", timeout=20)
                if r.status_code == 200 and len(r.text) > 500:
                    return r.text
            except Exception as e:
                self._last_error = f"cffi_chrome:{e}"

        if HAS_REQUESTS:
            try:
                r = _req.get(url, headers=headers, timeout=20)
                if r.status_code == 200 and len(r.text) > 500:
                    return r.text
                self._last_error = f"requests:HTTP{r.status_code}"
            except Exception as e:
                self._last_error = f"requests:{e}"

        try:
            import urllib.request
            import ssl
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            except Exception:
                ctx = None
            proxy_handler = urllib.request.ProxyHandler({})
            if ctx:
                opener = urllib.request.build_opener(proxy_handler, urllib.request.HTTPSHandler(context=ctx))
            else:
                opener = urllib.request.build_opener(proxy_handler)
            req = urllib.request.Request(url, headers=headers)
            resp = opener.open(req, timeout=20)
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            data = raw.decode("utf-8", errors="ignore")
            if len(data) > 500:
                return data
            self._last_error = f"urllib:太短({len(data)})"
        except Exception as e:
            self._last_error = f"urllib:{e}"

        return ""

    def _is_minor(self, text):
        if not text:
            return False
        return any(kw.lower() in text.lower() for kw in MINOR_KEYWORDS)

    def _parse_list(self, html):
        videos = []
        if not html:
            return videos
        pattern = re.compile(
            r'<li[^>]*>\s*<a[^>]*href="([^"]*play[^"]*)"[^>]*title="([^"]*)"[^>]*>[\s\S]*?'
            r'<img[^>]*src="([^"]+)"',
            re.DOTALL
        )
        for m in pattern.finditer(html):
            href, title, pic = m.groups()
            if self._is_minor(title):
                continue
            vid_m = re.search(r'/id/(\d+)', href)
            vod_id = vid_m.group(1) if vid_m else href
            videos.append({
                "vod_id": str(vod_id),
                "vod_name": desensitize(title.strip())[:80],
                "vod_pic": pic.strip(),
                "vod_remarks": "",
            })
        return videos

    def homeContent(self, *args):
        try:
            classes = [{"type_id": c["type_id"], "type_name": c["type_name"]} for c in CATEGORIES]
            filters = {c["type_id"]: [] for c in CATEGORIES}
            html = self._fetch(f"{BASE_PATH}/")
            videos = self._parse_list(html)
            return {"class": classes, "filters": filters, "list": videos}
        except Exception as e:
            print(f"[浪巢福地 homeContent错误] {e}")
            return {"class": [{"type_id": c["type_id"], "type_name": c["type_name"]} for c in CATEGORIES], "filters": {}, "list": []}

    def homeVideoContent(self, *args):
        return self.homeContent(*args)

    def categoryContent(self, tid, pg, *args):
        try:
            pg = int(pg) if pg else 1
            if pg == 1:
                path = f"/cn/home/web/index.php/vod/type/id/{tid}.html"
            else:
                path = f"/cn/home/web/index.php/vod/type/id/{tid}/page/{pg}.html"
            html = self._fetch(path)
            videos = self._parse_list(html)
            pagecount = max(pg, 10)
            total = len(videos) * pagecount
            return {"page": pg, "pagecount": pagecount, "limit": 90, "total": total, "list": videos}
        except Exception as e:
            print(f"[浪巢福地 categoryContent错误] {e}")
            return {"page": 1, "pagecount": 1, "limit": 90, "total": 0, "list": []}

    def detailContent(self, ids, *args):
        results = []
        if not ids:
            return {"list": results}
        id_list = ids if isinstance(ids, (list, tuple)) else [ids]
        for vid in id_list:
            try:
                vid_str = str(vid).strip()
                # 播放页即详情页
                path = f"/cn/home/web/index.php/vod/play/id/{vid_str}/sid/1/nid/1.html"
                html = self._fetch(path)
                if not html:
                    continue
                # 标题
                title_m = re.search(r'<title>([^<]+)</title>', html)
                title = title_m.group(1).strip() if title_m else "未知"
                title = re.sub(r'\s*-\s*浪巢福地\s*$', '', title).strip()
                if self._is_minor(title):
                    continue
                # 封面
                pic_m = re.search(r'<img[^>]*src="([^"]+)"', html)
                pic = pic_m.group(1) if pic_m else ""
                # m3u8直链（player_data.url）
                play_url = ""
                m = re.search(r'var player_data\s*=\s*(\{[^<]+?\})\s*</script>', html, re.DOTALL)
                if m:
                    try:
                        data = json.loads(m.group(1))
                        play_url = data.get("url", "")
                    except Exception:
                        url_m = re.search(r'"url"\s*:\s*"(https?://[^"]+)"', m.group(1))
                        if url_m:
                            play_url = url_m.group(1)

                results.append({
                    "vod_id": str(vid),
                    "vod_name": desensitize(title)[:80],
                    "vod_pic": pic,
                    "vod_content": "",
                    "vod_play_from": "浪巢福地",
                    "vod_play_url": f"第1集${play_url}" if play_url else "",
                })
            except Exception as e:
                print(f"[浪巢福地 detailContent错误] {e}")
                continue
        return {"list": results}

    def searchContent(self, key, pg, *args):
        try:
            pg = int(pg) if pg else 1
            import urllib.parse
            encoded_key = urllib.parse.quote(key)
            path = f"/index.php/vod/search/wd/{encoded_key}.html"
            html = self._fetch(path)
            videos = self._parse_list(html)
            return {"page": pg, "pagecount": max(pg, 3), "limit": 90, "total": len(videos) * 3, "list": videos}
        except Exception as e:
            print(f"[浪巢福地 searchContent错误] {e}")
            return {"page": 1, "pagecount": 1, "limit": 90, "total": 0, "list": []}

    def playerContent(self, flag, id, vipFlags, *args):
        return {
            "parse": 0,
            "jx": 0,
            "url": id,
            "header": {"User-Agent": UA, "Referer": f"{BASE_URL}/"},
        }

    def localProxy(self, flag, id, *args):
        return [404, "text/plain", ""]

    def isVideoFormat(self, url, *args):
        if not url:
            return False
        return any(ext in url.lower() for ext in [".m3u8", ".mp4", ".ts", ".flv", ".avi", ".mkv", ".mov"])

    def manualVideoCheck(self, *args):
        return False

    def action(self, action, *args):
        return ""

    def getDependence(self, *args):
        return ""

    def destroy(self, *args):
        pass


# ============ 自测 ============
if __name__ == "__main__":
    s = Spider()
    s.init("{}")

    print("=== 首页 ===")
    home = s.homeContent()
    print(f"分类: {len(home['class'])}, 视频: {len(home['list'])}")
    for v in home['list'][:3]:
        print(f"  {v['vod_id']}: {v['vod_name'][:30]}")

    print("\n=== 分类(禁脔) ===")
    cat = s.categoryContent("1", "1")
    print(f"视频: {len(cat['list'])}")

    print("\n=== 详情+播放 ===")
    if home['list']:
        vid = home['list'][0]['vod_id']
        detail = s.detailContent([vid])
        if detail['list']:
            d = detail['list'][0]
            print(f"标题: {d['vod_name'][:40]}")
            print(f"播放: {d['vod_play_url'][:80]}")
            if '$' in d['vod_play_url']:
                play = s.playerContent("浪巢福地", d['vod_play_url'].split('$')[1], [])
                print(f"playerContent: {play['url'][:80]}")

    print("\n=== 搜索 ===")
    sch = s.searchContent("人妻", "1")
    print(f"搜索结果: {len(sch['list'])}")

    print("\n✅ 测试完成")
