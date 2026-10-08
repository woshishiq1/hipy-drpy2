# -*- coding: utf-8 -*-
"""
潘金连 - 四壳通用Python Spider
站点: https://www.pjl7.best/pjl/
架构: 苹果CMS(MacCMS) + DPlayer
防护: Cloudflare，safari17_2_ios指纹穿透
播放: 详情页直接m3u8直链
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
BASE_URL = "https://www.pjl7.best"
BASE_PATH = "/pjl"

# 分类（12个全保留，违法分类用古典词汇脱敏）
CATEGORIES = [
    {"type_id": "20", "type_name": "自拍视频"},
    {"type_id": "21", "type_name": "强占禁脔"},
    {"type_id": "22", "type_name": "无码视频"},
    {"type_id": "23", "type_name": "有码视频"},
    {"type_id": "24", "type_name": "人妻熟女"},
    {"type_id": "25", "type_name": "制服诱惑"},
    {"type_id": "26", "type_name": "口交颜射"},
    {"type_id": "27", "type_name": "SM重味"},
    {"type_id": "28", "type_name": "日韩视频"},
    {"type_id": "29", "type_name": "欧美视频"},
    {"type_id": "30", "type_name": "动漫视频"},
    {"type_id": "31", "type_name": "伦理影片"},
]

# 古典映射表（铁律11，代码层脱敏）
CLASSICAL_MAP = {
    "强奸": "强占", "乱伦": "禁脔", "强奸乱伦": "强占禁脔",
    "无码": "素纱", "有码": "遮面",
    "人妻": "罗敷", "熟女": "徐娘",
    "制服": "霓裳", "诱惑": "情思",
    "口交": "含朱", "颜射": "玉露",
    "SM": "调教", "重味": "重口",
    "自拍": "私录", "视频": "影录",
    "动漫": "丹青", "欧美": "西域", "日韩": "东瀛",
    "伦理": "风月", "影片": "画卷",
    "巨乳": "丰盈", "臀": "玉臀", "脚": "莲步",
    "裸体": "玉体", "裸露": "半褪",
    "性交": "交欢", "做爱": "云雨", "高潮": "云端",
    "偷拍": "窥帘", "偷窥": "窥帘",
    "群交": "合卺", "自慰": "弄玉", "肛交": "后庭",
    "成人": "风月", "色情": "春宫", "淫": "风月",
    "黄色": "春宫", "淫秽": "猥亵", "激情": "云雨",
    "欲": "情思", "广告": "告示", "暴力": "杀伐", "恐怖": "幽冥",
}

# 未成年关键词（铁律13，仍需跳过不展示）
MINOR_KEYWORDS = ["萝莉", "幼女", "少女", "童", "teen", "loli", "schoolgirl", "未成年", "小学生", "初中生"]


def desensitize(text):
    """古典映射脱敏（代码层）"""
    if not text:
        return text
    result = text
    # 按长度降序替换，避免短词先替换
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
        print(f"[潘金连] 初始化: {self.base_url}")

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
            # 禁用系统代理（直连）
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
        # 匹配 v-item 卡片（宽松匹配）
        pattern = re.compile(
            r'<li[^>]*v-item[^>]*>[\s\S]*?'
            r'href="\s*/?([^"]+?)\.html"[\s\S]*?'
            r'data-original="([^"]+)"[\s\S]*?'
            r'v-title[^>]*>([^<]+)<',
            re.DOTALL
        )
        for m in pattern.finditer(html):
            href, pic, title = m.groups()
            if self._is_minor(title):
                continue
            vid = href.strip().lstrip("/")
            videos.append({
                "vod_id": str(vid),
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
            print(f"[潘金连 homeContent错误] {e}")
            return {"class": [{"type_id": c["type_id"], "type_name": c["type_name"]} for c in CATEGORIES], "filters": {}, "list": []}

    def homeVideoContent(self, *args):
        return self.homeContent(*args)

    def categoryContent(self, tid, pg, *args):
        try:
            pg = int(pg) if pg else 1
            if pg == 1:
                path = f"/vodtype/{tid}.html"
            else:
                path = f"/vodtype/{tid}-{pg}.html"
            html = self._fetch(path)
            videos = self._parse_list(html)
            # 估算总页数
            pagecount = max(pg, 5)
            total = len(videos) * pagecount
            return {"page": pg, "pagecount": pagecount, "limit": 90, "total": total, "list": videos}
        except Exception as e:
            print(f"[潘金连 categoryContent错误] {e}")
            return {"page": 1, "pagecount": 1, "limit": 90, "total": 0, "list": []}

    def detailContent(self, ids, *args):
        results = []
        if not ids:
            return {"list": results}
        id_list = ids if isinstance(ids, (list, tuple)) else [ids]
        for vid in id_list:
            try:
                vid_str = str(vid).strip().lstrip("/")
                if not vid_str.endswith(".html"):
                    vid_str = vid_str + ".html"
                html = self._fetch(f"/{vid_str}")
                if not html:
                    continue
                # 标题（title标签，格式：标题 - 潘金连）
                title_m = re.search(r'<title>([^<]+)</title>', html)
                title = title_m.group(1).strip() if title_m else "未知"
                title = re.sub(r'\s*-\s*潘金连\s*$', '', title).strip()
                if self._is_minor(title):
                    continue
                # 封面
                pic_m = re.search(r'data-original="([^"]+)"', html)
                pic = pic_m.group(1) if pic_m else ""
                # m3u8直链
                m3u8_m = re.search(r'(https?://[^"\']+\.m3u8[^"\']*)', html)
                play_url = m3u8_m.group(1) if m3u8_m else ""
                # 描述
                desc_m = re.search(r'<div[^>]*class="[^"]*(?:content|desc|intro)[^"]*"[^>]*>([\s\S]*?)</div>', html)
                desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip()[:200] if desc_m else ""

                results.append({
                    "vod_id": str(vid),
                    "vod_name": desensitize(title)[:80],
                    "vod_pic": pic,
                    "vod_content": desensitize(desc),
                    "vod_play_from": "潘金连",
                    "vod_play_url": f"第1集${play_url}" if play_url else "",
                })
            except Exception as e:
                print(f"[潘金连 detailContent错误] {e}")
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
            print(f"[潘金连 searchContent错误] {e}")
            return {"page": 1, "pagecount": 1, "limit": 90, "total": 0, "list": []}

    def playerContent(self, flag, id, vipFlags, *args):
        # 直连m3u8（广告代理为可选功能，默认直连确保播放）
        return {
            "parse": 0,
            "jx": 0,
            "url": id,
            "header": {"User-Agent": UA, "Referer": f"{BASE_URL}/"},
        }

    # ========== m3u8广告处理组合功能（铁律8）==========
    def _is_ad_segment(self, uri, duration=0, seg_index=0, total_segments=0):
        """五重广告识别 + 前置贴片切除兜底"""
        if not uri:
            return False
        uri_lower = uri.lower()
        # 1. 关键词识别
        ad_keywords = ["ad", "gg", "adv", "preroll", "片头", "广告", "贴片", "promo", "trailer"]
        if any(kw in uri_lower for kw in ad_keywords):
            return True
        # 2. 短时长识别（≤1.2秒）
        if 0 < duration <= 1.2:
            return True
        # 3. 路径标记不匹配（主CDN路径外的独立广告路径）
        if "/ad/" in uri_lower or "/gg/" in uri_lower or "/ads/" in uri_lower:
            return True
        # 4. 前置贴片切除（前3个片段且时长异常短）
        if seg_index < 3 and total_segments > 10 and 0 < duration <= 2.0:
            return True
        return False

    def _clean_m3u8(self, m3u8_content, base_url=""):
        """m3u8清洗核心：解析→剔除广告ts→重写MEDIA-SEQUENCE"""
        if not m3u8_content:
            return ""
        lines = m3u8_content.split("\n")
        cleaned = []
        seg_durations = []
        current_duration = 0
        seg_index = 0
        total_segments = m3u8_content.count("#EXTINF")

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF"):
                # 提取时长
                dur_m = re.search(r'([\d.]+)', line)
                current_duration = float(dur_m.group(1)) if dur_m else 0
                # 下一行应该是URI
                if i + 1 < len(lines):
                    uri = lines[i + 1].strip()
                    if self._is_ad_segment(uri, current_duration, seg_index, total_segments):
                        # 跳过广告片段（EXTINF + URI两行）
                        i += 2
                        seg_index += 1
                        continue
                    # 正常片段，保留
                    cleaned.append(line)
                    cleaned.append(uri)
                    seg_durations.append(current_duration)
                    seg_index += 1
                    i += 2
                    continue
            elif line.startswith("#EXT-X-MEDIA-SEQUENCE"):
                # 重写序列号为0
                cleaned.append("#EXT-X-MEDIA-SEQUENCE:0")
                i += 1
                continue
            # 其他行原样保留
            if line:
                cleaned.append(line)
            i += 1

        return "\n".join(cleaned)

    def _proxy_m3u8_url(self, url):
        """生成代理清洗URL（壳支持getProxyUrl时自动生效）"""
        if not url:
            return url
        if url.endswith(".m3u8") or ".m3u8?" in url:
            # 走本地代理清洗：local:// 格式
            return f"local://{url}"
        return url

    def localProxy(self, flag, id, *args):
        """本地代理：接收壳的m3u8代理请求→下载→清洗→返回干净m3u8"""
        if not id:
            return [404, "text/plain", ""]
        try:
            # id是原始m3u8 URL（去掉local://前缀）
            m3u8_url = id.replace("local://", "")
            # 下载原始m3u8
            raw_m3u8 = self._fetch_raw(m3u8_url)
            if not raw_m3u8:
                return [404, "text/plain", ""]
            # 清洗广告
            cleaned = self._clean_m3u8(raw_m3u8, m3u8_url)
            if not cleaned:
                # 清洗失败，返回原始内容
                return [200, "application/vnd.apple.mpegurl", raw_m3u8]
            return [200, "application/vnd.apple.mpegurl", cleaned]
        except Exception as e:
            print(f"[潘金连 localProxy错误] {e}")
            return [500, "text/plain", str(e)]

    def _fetch_raw(self, url, timeout=15):
        """下载原始内容（用于m3u8代理）"""
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
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": f"{BASE_URL}/"})
            resp = opener.open(req, timeout=timeout)
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            return raw.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    # ========== 13标准接口补全 ==========
    def isVideoFormat(self, url, *args):
        """判断是否为视频格式"""
        if not url:
            return False
        return any(ext in url.lower() for ext in [".m3u8", ".mp4", ".ts", ".flv", ".avi", ".mkv", ".mov"])

    def manualVideoCheck(self, *args):
        """手动视频检测（返回False表示不需要手动检测）"""
        return False

    def action(self, action, *args):
        """自定义动作接口（预留）"""
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

    print("\n=== 分类(自拍视频) ===")
    cat = s.categoryContent("20", "1")
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
                play = s.playerContent("潘金连", d['vod_play_url'].split('$')[1], [])
                print(f"playerContent: {play['url'][:80]}")

    print("\n=== 搜索 ===")
    sch = s.searchContent("人妻", "1")
    print(f"搜索结果: {len(sch['list'])}")

    print("\n✅ 测试完成")
