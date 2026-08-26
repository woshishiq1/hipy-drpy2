#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
河马影视 (hemyin.com) TVBox Spider 源
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
分类: 全部 153 个子分类作为一级分类 (type_id = 分类ID)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import re, json, urllib.request, urllib.parse, ssl

BASE_URL = "https://hemyin.com"
UA = "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36"

# 所有分类 (type_id = 分类数字ID)
ALL_CATS = [
    ("71","小水水"),("79","麻豆传媒"),("58","蜜桃影像传媒"),("43","乌托邦传媒"),
    ("7","饼干姐姐"),("205","菠萝啤beer"),("194","粉色情人"),("204","狐不妖"),
    ("87","人妻巨乳"),("117","口爆吞精"),("172","家庭乱伦"),("193","十八岁"),
    ("148","馒头逼"),("120","震动棒"),("177","丁字裤"),("62","中文字幕"),
    ("145","大学生"),("106","高颜值"),("108","cosplay"),("17","台北娜娜"),
    ("6","xvideos"),("114","TS人妖"),
    ("33","女神"),("11","后入"),("143","裸舞"),("23","少妇"),
    ("41","主播"),("81","苏畅"),("13","国产"),("32","骚逼"),
    ("140","深喉"),("162","高潮"),("157","露出"),("35","热门"),
    ("72","接吻"),("213","暴力"),("39","SM"),("160","多p"),
    ("152","迷药"),("55","父女"),("211","夫妻"),("67","韩国"),
    ("38","强奸"),("142","美乳"),("10","乱伦"),("175","阿朱"),
    ("201","无毛"),("132","恋足"),("181","空姐"),("141","炮机"),
    ("91","足控"),("173","捆绑"),("64","百合"),("5","性感"),
    ("75","白虎"),("135","荡妇"),("15","迷奸"),("182","小三"),
    ("110","无码"),("60","制服诱惑"),("83","淫叫"),("103","淫水"),
    ("21","吃瓜"),("192","户外露出"),("94","onlyfans"),("97","情趣装扮"),
    ("119","车震"),("122","户外野战"),("129","柚子猫"),("127","喷水"),
    ("125","VIP视频"),("19","蝴蝶逼"),("14","调教"),("1","网黄"),
    ("169","同性"),("124","鸡教练"),("68","肛交"),("209","角色扮演"),
    ("189","留学生"),("44","绿帽"),("29","少女"),("26","糖心Vlog"),
    ("170","丝袜"),("111","星空无限传媒"),("42","天美传媒"),("31","萝莉"),
    ("20","自慰"),("164","辛尤里"),("146","无毛粉嫩白"),("88","AV解说"),
    ("214","刑具"),("207","泄物"),("53","樱空桃桃"),("84","原创"),
    ("154","动漫"),("149","三级"),("18","传媒"),("49","日韩"),
    ("163","约炮"),("65","姐弟"),("134","短发"),("90","3p"),
    ("197","蜜桃女神"),("156","偷情"),("166","JVID"),("24","骚货"),
    ("151","变态"),("61","潮吹"),("183","小二先生"),("187","王梨奈"),
    ("116","滥交群交"),("174","强操"),("136","4p"),("51","女同"),
    ("66","学妹"),("144","美腿"),("40","熟女"),("76","巨乳"),
    ("128","跳蛋"),("104","流水"),("115","男同"),("8","玩偶姐姐"),
    ("27","母狗"),("118","双马尾"),("113","爆操"),("52","乱交群p"),
    ("139","出轨"),("210","公众场合"),("102","性奴"),("179","奶凶大人"),
    ("28","抠逼"),("80","Chloe"),("186","小宵虎南"),("130","重口味"),
    ("9","御姐"),("131","粉穴"),("203","泳装"),("105","日本"),
    ("167","无套"),("206","元旦"),("185","医生"),("168","SA国际传媒"),
    ("85","勾引"),("216","巨屌"),("69","足交"),("180","内射"),
    ("191","米胡桃"),("48","摸胸"),("12","口交"),("98","户外"),
    ("196","眼镜娘"),("25","舔逼"),("147","圣诞"),
]

# 网络
_has_cs = False
try:
    import cloudscraper
    _scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'android','desktop':False})
    _has_cs = True
except Exception:
    pass

def _get(url, timeout=20):
    if _has_cs:
        try:
            resp = _scraper.get(url, timeout=timeout, headers={
                "User-Agent": UA, "Accept": "text/html,*/*;q=0.8", "Referer": BASE_URL + "/",
            })
            return resp.text
        except Exception:
            pass
    try:
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*;q=0.8", "Referer": BASE_URL + "/"})
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return ""

def _fetch_page(path): return _get(BASE_URL + path)

def _extract_vod_cards(html):
    items = []; seen = set()
    for m in re.finditer(r'<a[^>]*href="/video/(\d+)"[^>]*class="[^"]*nav-art-card[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL):
        vid = m.group(1)
        if vid in seen: continue
        seen.add(vid)
        inner = m.group(2)
        pic = ""
        img = re.search(r'<img[^>]*src="([^"]+)"', inner)
        if img: pic = img.group(1)
        if not pic:
            img = re.search(r'<meta[^>]+itemprop="image"[^>]+content="([^"]+)"', inner)
            if img: pic = img.group(1)
        if pic and not pic.startswith("http"): pic = BASE_URL + pic
        name = ""
        alt = re.search(r'<img[^>]*alt="([^"]+)"', inner)
        if alt: name = alt.group(1)
        if not name:
            text = re.sub(r'<[^>]+>', '', inner).strip()
            text = re.sub(r'\s+', ' ', text)
            t = re.search(r'【([^】]+)】', text)
            name = t.group(1) if t else text[:50]
        items.append({"id": vid, "name": name, "pic": pic})
    return items

def _extract_detail(html):
    info = {}
    m = re.search(r'"contentUrl"\s*:\s*"([^"]+)"', html)
    if m: info["play_url"] = m.group(1).replace("\\/", "/")
    m = re.search(r'"thumbnailUrl"\s*:\s*"([^"]+)"', html)
    if m: info["pic"] = m.group(1).replace("\\/", "/")
    m = re.search(r'"name"\s*:\s*"([^"]+)"', html)
    if m: info["name"] = m.group(1).replace("\\/", "/")
    if not info.get("name"):
        m = re.search(r'<title>([^<]+)</title>', html)
        if m: info["name"] = m.group(1).replace(" - 河马影视", "").strip()
    return info

def _norm_ids(ids):
    if ids is None: return []
    if isinstance(ids, str):
        try: p = json.loads(ids); return [str(x) for x in p] if isinstance(p, list) else [ids.strip()]
        except: pass
        return [ids.strip()]
    if isinstance(ids, (list, tuple)): return [str(i) for i in ids]
    return [str(ids)]

class Spider:
    def getDependence(self): return []
    def init(self, extend=""):
        self.extend = {}
        if extend:
            try: self.extend = json.loads(extend) if isinstance(extend, str) else dict(extend)
            except: pass
    def getName(self): return "河马影视"

    def homeContent(self, filter=None):
        return {
            "class": [{"type_id": cid, "type_name": name} for cid, name in ALL_CATS],
            "filters": {},
        }

    def homeVideoContent(self):
        html = _fetch_page("/")
        items = _extract_vod_cards(html)
        return {"list": [{"vod_id": it["id"], "vod_name": it["name"], "vod_pic": it.get("pic",""), "type_name":"", "vod_remarks":""} for it in items[:50]]}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        pg = int(pg) if pg else 1
        cid = str(tid)
        path = f"/c{cid}" if pg <= 1 else f"/c{cid}/page/{pg}"
        html = _fetch_page(path)
        items = _extract_vod_cards(html)
        # 检测是否有"下一页"链接来判断是否最后一页
        has_next = '下一页' in html
        pagecount = pg + 1 if has_next else pg
        return {
            "list": [{"vod_id": it["id"], "vod_name": it["name"], "vod_pic": it.get("pic",""), "type_name": "", "vod_remarks": ""} for it in items],
            "page": pg, "pagecount": pagecount, "limit": 24, "total": 0,
        }

    def detailContent(self, ids):
        ids = _norm_ids(ids)
        if not ids: return {"list": []}
        html = _fetch_page(f"/video/{ids[0]}")
        if not html: return {"list": []}
        info = _extract_detail(html)
        return {"list": [{
            "vod_id": ids[0], "vod_name": info.get("name", "未知"),
            "vod_pic": info.get("pic", ""),
            "type_name": "", "vod_year": "", "vod_area": "", "vod_remarks": "",
            "vod_actor": "", "vod_director": "", "vod_content": "",
            "vod_play_from": "在线播放", "vod_play_url": f"正片${ids[0]}",
        }]}

    def searchContent(self, key, quick=False, pg=1):
        try:
            kw = urllib.parse.quote(str(key))
            html = _fetch_page(f"/?q={kw}")
            items = _extract_vod_cards(html)
            return {"list": [{"vod_id": it["id"], "vod_name": it["name"], "vod_pic": it.get("pic",""), "type_name": "", "vod_remarks": ""} for it in items[:20]]}
        except Exception:
            return {"list": []}

    def playerContent(self, flag, ids, vipFlags=None):
        """通过 /api/video.php 获取真实 m3u8 地址"""
        vid = str(ids).split("@")[0]
        # 调用视频 API 获取真实播放地址
        try:
            api_url = f"{BASE_URL}/api/video.php?id={vid}"
            api_html = _get(api_url)
            if api_html:
                try:
                    j = json.loads(api_html)
                    if j.get("ok") and j.get("url"):
                        return {"parse": 0, "playUrl": j["url"], "header": {"User-Agent": UA, "Referer": BASE_URL + "/"}}
                except Exception:
                    pass
        except Exception:
            pass
        # 兜底: JSON-LD contentUrl
        html = _fetch_page(f"/video/{vid}")
        if not html: return {"parse": 0, "playUrl": "", "header": {}}
        play_url = ""
        m = re.search(r'"contentUrl"\s*:\s*"([^"]+)"', html)
        if m: play_url = m.group(1).replace("\\/", "/")
        return {"parse": 0, "playUrl": play_url, "header": {"User-Agent": UA, "Referer": BASE_URL + "/"}}

    def localProxy(self, param): return [200, "text/plain", b"", {}]
    def action(self, action): return {"code": 200, "content": "", "type": "text/plain"}
    def manualVideoCheck(self): return True
    def destroy(self): pass

# 测试
if __name__ == "__main__":
    sp = Spider(); sp.init()
    print("=" * 50)
    print(f"名称: {sp.getName()}")
    r = sp.homeContent()
    print(f"  class: {len(r['class'])} 个一级分类")
    print(f"  样本: {[c['type_name'] for c in r['class'][:10]]}...")
    r = sp.homeVideoContent()
    print(f"  home列表: {len(r['list'])} 项")
    print("✅ 测试完成")