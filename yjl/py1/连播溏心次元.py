#!/usr/bin/python
#站长邮件: txcy2users@gmail.com (新)
#TG电报: @txcyaduser
# -*- coding: utf-8 -*-
import re,json,requests
from urllib.parse import quote
try:
    from lxml import etree
except:
    etree=None
try:
    from base.spider import Spider
except:
    class Spider: pass

class Spider(Spider):
    def getName(self): return "溏心次元"
    def init(self,extend=""):
        self.host="https://lhej.txcy-emo.buzz"
        self.headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36","Referer":self.host+"/banshu/","Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
        self.classes=[{"type_id":"1","type_name":"麻豆原创"},{"type_id":"2","type_name":"代理节目"},{"type_id":"3","type_name":"节目企划"},{"type_id":"32","type_name":"国产片商"},{"type_id":"39","type_name":"国产精品"},{"type_id":"4","type_name":"MD系列"},{"type_id":"5","type_name":"导演系列"},{"type_id":"6","type_name":"MDS系列"},{"type_id":"7","type_name":"MDX系列"},{"type_id":"8","type_name":"MDXS系列"},{"type_id":"46","type_name":"MDL系列"},{"type_id":"50","type_name":"MMZ系列"},{"type_id":"53","type_name":"MAD系列"},{"type_id":"58","type_name":"MDWP系列"},{"type_id":"64","type_name":"MSD系列"},{"type_id":"74","type_name":"MDM恋爱咖啡"},{"type_id":"78","type_name":"MDUS系列"},{"type_id":"79","type_name":"MXJ系列"},{"type_id":"87","type_name":"MKY系列"},{"type_id":"89","type_name":"MAN系列"},{"type_id":"96","type_name":"MCY系列"},{"type_id":"100","type_name":"MDAG系列"},{"type_id":"101","type_name":"MDHT系列"},{"type_id":"115","type_name":"BLX系列"},{"type_id":"116","type_name":"MPG系列"},{"type_id":"10","type_name":"兔子先生"},{"type_id":"11","type_name":"果冻传媒"},{"type_id":"12","type_name":"皇家华人"},{"type_id":"13","type_name":"吴梦梦无套系列"},{"type_id":"14","type_name":"PsychoPorn色控"},{"type_id":"15","type_name":"蜜桃影像传媒"},{"type_id":"45","type_name":"天美传媒"},{"type_id":"52","type_name":"91制片厂"},{"type_id":"65","type_name":"MSM性梦者"},{"type_id":"71","type_name":"叮叮映画"},{"type_id":"72","type_name":"涩会"},{"type_id":"75","type_name":"豚豚创媒"},{"type_id":"76","type_name":"爱妃传媒"},{"type_id":"80","type_name":"辣椒原创"},{"type_id":"81","type_name":"O-STAR"},{"type_id":"91","type_name":"肉肉传媒"},{"type_id":"95","type_name":"渡边传媒"},{"type_id":"97","type_name":"葵心娱乐"},{"type_id":"103","type_name":"红斯灯影像"},{"type_id":"105","type_name":"蝌蚪传媒"},{"type_id":"106","type_name":"Pussy Hunter"},{"type_id":"108","type_name":"桃花源"},{"type_id":"17","type_name":"大鸟十八"},{"type_id":"18","type_name":"疯拍系列"},{"type_id":"19","type_name":"KISS糖果屋"},{"type_id":"20","type_name":"小鹏奇啪行"},{"type_id":"22","type_name":"30天解密麻豆"},{"type_id":"23","type_name":"突袭女优计划"},{"type_id":"24","type_name":"女神羞羞研究所"},{"type_id":"27","type_name":"小哥哥艾理"},{"type_id":"31","type_name":"情趣K歌房"},{"type_id":"40","type_name":"淫欲游戏王"},{"type_id":"41","type_name":"麻豆不回家"},{"type_id":"42","type_name":"女优淫娃培训营"},{"type_id":"54","type_name":"狼人插"},{"type_id":"55","type_name":"女优擂台摔角狂热"},{"type_id":"61","type_name":"恋爱巴士"},{"type_id":"66","type_name":"男女优生死斗"},{"type_id":"67","type_name":"情人劫密室逃脱"},{"type_id":"68","type_name":"换妻"},{"type_id":"69","type_name":"你好同学"},{"type_id":"77","type_name":"禁欲小屋"},{"type_id":"84","type_name":"鲍鱼的胜利"},{"type_id":"88","type_name":"性爱自修室"},{"type_id":"92","type_name":"春游记"},{"type_id":"93","type_name":"心动的性号"},{"type_id":"94","type_name":"情趣大富翁"},{"type_id":"99","type_name":"寻宝吧女神"},{"type_id":"102","type_name":"男优练习生"},{"type_id":"110","type_name":"女神体育祭"},{"type_id":"111","type_name":"麻豆高校"},{"type_id":"112","type_name":"野外露初"},{"type_id":"33","type_name":"乌鸦传媒"},{"type_id":"34","type_name":"精东影业"},{"type_id":"36","type_name":"SWAG"},{"type_id":"47","type_name":"星空无限传媒"},{"type_id":"48","type_name":"大象传媒"},{"type_id":"59","type_name":"大象传媒"},{"type_id":"62","type_name":"MINI传媒"},{"type_id":"73","type_name":"糖心vlog"},{"type_id":"82","type_name":"葫芦影业"},{"type_id":"83","type_name":"天马传媒"},{"type_id":"90","type_name":"CCAV成人头条"},{"type_id":"109","type_name":"性视界传媒"},{"type_id":"113","type_name":"SA国际传媒"},{"type_id":"114","type_name":"香蕉传媒"},{"type_id":"117","type_name":"91茄子"},{"type_id":"118","type_name":"EDmosaic"}]
    def _get(self,u):
        try:
            r=requests.get(self._fix(u),headers=self.headers,timeout=15,verify=False); r.encoding=r.apparent_encoding or "utf-8"; return r.text
        except Exception: return ""
    def _post(self,u,d):
        try:
            r=requests.post(self._fix(u),data=d,headers=self.headers,timeout=15,verify=False); r.encoding=r.apparent_encoding or "utf-8"; return r.text
        except Exception: return ""
    def _fix(self,u): return "https:"+u if u and u.startswith("//") else self.host+u if u and u.startswith("/") else u or ""
    def _txt(self,x): return re.sub(r"\s+"," ","".join(x.xpath(".//text()")) if hasattr(x,"xpath") else str(x)).strip()
    def _parse_list(self,h):
        if not h: return []
        res=[]; seen=set(); blocks=re.findall(r'<section[^>]+class=["\'][^"\']*item-box[^"\']*["\'][\s\S]*?</section>',h,re.I) or re.findall(r'<li[^>]+class=["\'][^"\']*col-25[^"\']*["\'][\s\S]*?</li>',h,re.I)
        for b in blocks:
            m=re.search(r'href=["\']([^"\']*/vod(?:detail|play)/(\d+)[^"\']*)["\']',b,re.I)
            if not m or m.group(2) in seen: continue
            seen.add(m.group(2)); name=""; pic=""
            n=re.search(r'title=["\']([^"\']+)["\']',b,re.I) or re.search(r'alt=["\']([^"\']+)["\']',b,re.I)
            im=re.search(r'<img[^>]+(?:data-original|data-src|src)=["\']([^"\']+)["\']',b,re.I)
            if n: name=re.sub(r'\s+',' ',n.group(1)).strip()
            if im: pic=im.group(1)
            if name: res.append({"vod_id":m.group(2),"vod_name":name,"vod_pic":self._fix(pic),"vod_remarks":""})
        if res or not etree: return res
        t=etree.HTML(h); nodes=t.xpath('//a[(contains(@href,"/voddetail/") or contains(@href,"/vodplay/")) and .//img]')
        for a in nodes:
            href=a.get("href",""); m=re.search(r'/vod(?:detail|play)/(\d+)',href)
            if not m or m.group(1) in seen: continue
            seen.add(m.group(1)); img=a.xpath('.//img')[0] if a.xpath('.//img') else None; name=a.get("title","") or (img.get("alt","") if img is not None else "") or self._txt(a); pic=(img.get("data-original") or img.get("data-src") or img.get("src") or "") if img is not None else ""
            if name: res.append({"vod_id":m.group(1),"vod_name":name,"vod_pic":self._fix(pic),"vod_remarks":""})
        return res
    def homeContent(self,filter):
        h=self._get(self.host+"/banshu/")
        return {"class":self.classes,"list":self._parse_list(h),"filters":{}}
    def categoryContent(self,tid,pg,filter,extend):
        pg=str(pg or "1"); u=f"{self.host}/vodtype/{tid}.html" if pg=="1" else f"{self.host}/vodtype/{tid}-{pg}/"
        li=self._parse_list(self._get(u))
        return {"page":int(pg),"pagecount":999 if li else int(pg),"limit":len(li) or 30,"total":999999 if li else 0,"list":li}
    def detailContent(self,ids):
        vid=str(ids[0]); h=self._get(f"{self.host}/voddetail/{vid}/"); v={"vod_id":vid,"vod_name":"","vod_pic":"","type_name":"","vod_year":"","vod_area":"","vod_actor":"","vod_director":"","vod_content":"","vod_play_from":"ckplayer","vod_play_url":f"播放${self.host}/vodplay/{vid}-1-1/"}
        if h and etree:
            t=etree.HTML(h); name="".join(t.xpath('//h1[contains(@class,"f-bold")]/text()|//h1/text()')).strip(); pic="".join(t.xpath('//div[contains(@class,"detail-image-wrapper")]//img/@src|//meta[@property="og:image"]/@content')).strip(); typ="".join(t.xpath('//span[contains(@class,"place")]//a[contains(@href,"/vodtype/")][last()]/text()')).strip(); desc="".join(t.xpath('//meta[@name="description"]/@content')).strip()
            eps=[]
            for a in t.xpath('//a[contains(@href,"/vodplay/")]'):
                href=a.get("href",""); mm=re.search(r'/vodplay/(\d+-\d+-\d+)/',href)
                if mm and mm.group(1).startswith(vid+"-"):
                    title=(a.get("title") or self._txt(a) or "播放").strip(); ep=f"{title}${self.host}/vodplay/{mm.group(1)}/"
                    if ep not in eps: eps.append(ep)
            v.update({"vod_name":name or v["vod_name"],"vod_pic":self._fix(pic),"type_name":typ,"vod_content":desc,"vod_play_url":"#".join(eps) if eps else v["vod_play_url"]})
        return {"list":[v]}
    def searchContent(self,key,quick,pg="1"):
        h=self._post(self.host+"/vodsearch/-------------/",{"wd":key}) or self._get(f"{self.host}/index.php/vodsearch/{quote(key)}-------------.html")
        return {"list":self._parse_list(h),"page":int(pg or 1)}
    def playerContent(self,flag,id,vipFlags):
        u=self._fix(id); h=self._get(u) if ".m3u8" not in u and ".mp4" not in u else ""; url=u
        if h:
            m=re.search(r'player_data\s*=\s*(\{.*?\})\s*</script>',h,re.S) or re.search(r'player_data\s*=\s*(\{.*?\})',h,re.S)
            if m:
                try: url=json.loads(m.group(1).replace('\\/','/')).get("url",u)
                except Exception: url=u
            if url==u:
                m=re.search(r'(https?://[^\s"\']+\.(?:m3u8|mp4)[^\s"\']*)',h); url=m.group(1) if m else u
        return {"parse":0,"url":self._fix(url),"header":json.dumps(self.headers,ensure_ascii=False)}

# ===== PAGE_PLAYLIST_START =====
def _pl_install(_C):
    if getattr(_C, "_pl_patched", False):
        return _C
    _C._pl_patched = True
    _orig_init = getattr(_C, "init", None)
    _orig_home = getattr(_C, "homeContent", None)
    _orig_homev = getattr(_C, "homeVideoContent", None)
    _orig_cate = getattr(_C, "categoryContent", None)
    _orig_detail = getattr(_C, "detailContent", None)
    _orig_search = getattr(_C, "searchContent", None)
    _orig_searchp = getattr(_C, "searchContentPage", None)
    _orig_player = getattr(_C, "playerContent", None)

    def _ensure(self):
        if not hasattr(self, "page_cache"):
            self.page_cache = {}
            self.page_index = {}
            self.page_keys = []
            self._src_cache = {}

    def _clean(s):
        return str(s or "").replace("$", " ").replace("#", " ").strip()

    def _enc(s):
        try:
            from urllib.parse import quote
            return quote(str(s or ""), safe="")
        except Exception:
            return str(s or "")

    def _dec(s):
        try:
            from urllib.parse import unquote
            return unquote(str(s or ""))
        except Exception:
            return str(s or "")

    def _cache_page(self, key, items):
        _ensure(self)
        out = []
        for x in items or []:
            if isinstance(x, dict) and x.get("vod_id"):
                out.append(x)
        if not out:
            return
        self.page_cache[key] = out
        if key in self.page_keys:
            self.page_keys.remove(key)
        self.page_keys.append(key)
        for it in out:
            self.page_index[str(it["vod_id"])] = key
        while len(self.page_keys) > 30:
            old = self.page_keys.pop(0)
            self.page_cache.pop(old, None)

    def _page_of(self, vid):
        _ensure(self)
        key = self.page_index.get(str(vid))
        if key in self.page_cache:
            return list(self.page_cache[key])
        return []

    def _as_result(r):
        if r is None:
            return {}
        if isinstance(r, dict):
            return r
        if isinstance(r, (bytes, bytearray)):
            r = r.decode("utf-8", "ignore")
        if isinstance(r, str):
            s = r.strip()
            if s.startswith("{") or s.startswith("["):
                try:
                    import json as _j
                    return _j.loads(s)
                except Exception:
                    return {}
        return {}

    def _split_sources(vod):
        fr = str((vod or {}).get("vod_play_from") or "").split("$$$")
        ur = str((vod or {}).get("vod_play_url") or "").split("$$$")
        while len(ur) < len(fr):
            ur.append("")
        sources = []
        for i, name in enumerate(fr):
            parts = []
            for p in (ur[i] or "").split("#"):
                if not p:
                    continue
                if "$" in p:
                    n, u = p.split("$", 1)
                else:
                    n, u = str(i + 1), p
                parts.append((_clean(n), u))
            sources.append((_clean(name) or ("线路%d" % (i + 1)), parts))
        return [x for x in sources if x[1]]

    def _call_detail(self, vid):
        if not _orig_detail:
            return {}
        try:
            return _as_result(_orig_detail(self, [vid]))
        except TypeError:
            try:
                return _as_result(_orig_detail(self, vid))
            except Exception:
                return {}
        except Exception:
            return {}

    def _load_src(self, vid):
        _ensure(self)
        vid = str(vid)
        if vid in self._src_cache:
            return self._src_cache[vid]
        r = self._pl_call_detail(vid)
        vod = ((r.get("list") or [None])[0]) or {}
        sources = _split_sources(vod)
        self._src_cache[vid] = sources
        return sources

    def _item_parts(self, it, src_idx, current_sources, current_vid):
        iid = str(it.get("vod_id") or "")
        if not iid:
            return []
        name = _clean(it.get("vod_name") or iid) or iid
        if iid == str(current_vid):
            eps = []
            if current_sources:
                if src_idx < len(current_sources) and current_sources[src_idx][1]:
                    eps = current_sources[src_idx][1]
                else:
                    eps = current_sources[0][1]
            if len(eps) > 1:
                out = []
                for i, (en, u) in enumerate(eps):
                    label = _clean("%s %s" % (name, en or ("%02d" % (i + 1))))
                    out.append("%s$%s" % (label, u))
                return out
            if eps:
                return ["%s$%s" % (name, eps[0][1])]
            return ["%s$nid:%s" % (name, _enc(iid))]
        return ["%s$nid:%s" % (name, _enc(iid))]

    def _apply_playlist(self, vid, vod, items):
        sources = _split_sources(vod)
        _ensure(self)
        self._src_cache[str(vid)] = sources
        if not items:
            return vod
        ordered = [x for x in items if str(x.get("vod_id")) == str(vid)]
        ordered += [x for x in items if str(x.get("vod_id")) != str(vid)]
        plist, seen = [], set()
        for it in ordered:
            iid = str(it.get("vod_id") or "")
            if not iid or iid in seen:
                continue
            seen.add(iid)
            plist.append(it)
        if not plist:
            return vod
        if not sources:
            sources = [("线路1", [("播放", "nid:%s" % _enc(vid))])]
        play_from, play_urls = [], []
        for i, (sname, _eps) in enumerate(sources):
            parts = []
            for it in plist:
                parts.extend(self._pl_item_parts(it, i, sources, vid))
            if not parts:
                continue
            play_from.append(sname or ("线路%d" % (i + 1)))
            play_urls.append("#".join(parts))
        if not play_from:
            return vod
        vod = dict(vod)
        vod["vod_play_from"] = "$$$".join(play_from)
        vod["vod_play_url"] = "$$$".join(play_urls)
        return vod

    def init(self, *args, **kwargs):
        _ensure(self)
        if _orig_init:
            return _orig_init(self, *args, **kwargs)

    def homeContent(self, *args, **kwargs):
        _ensure(self)
        r = _orig_home(self, *args, **kwargs) if _orig_home else {}
        try:
            _cache_page(self, ("home",), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def homeVideoContent(self, *args, **kwargs):
        _ensure(self)
        r = _orig_homev(self, *args, **kwargs) if _orig_homev else {"list": []}
        try:
            _cache_page(self, ("homev",), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def categoryContent(self, *args, **kwargs):
        _ensure(self)
        r = _orig_cate(self, *args, **kwargs) if _orig_cate else {"list": []}
        try:
            tid = args[0] if args else kwargs.get("tid", "")
            pg = args[1] if len(args) > 1 else kwargs.get("pg", "1")
            ext = args[3] if len(args) > 3 else kwargs.get("extend", "")
            _cache_page(self, ("cate", str(tid), str(pg), str(ext)), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def searchContent(self, *args, **kwargs):
        _ensure(self)
        if not _orig_search:
            return {"list": []}
        r = _orig_search(self, *args, **kwargs)
        try:
            key = args[0] if args else kwargs.get("key", "")
            pg = args[2] if len(args) > 2 else kwargs.get("pg", "1")
            _cache_page(self, ("search", str(key), str(pg)), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def searchContentPage(self, *args, **kwargs):
        _ensure(self)
        if not _orig_searchp:
            return {"list": []}
        r = _orig_searchp(self, *args, **kwargs)
        try:
            key = args[0] if args else kwargs.get("key", "")
            pg = args[2] if len(args) > 2 else kwargs.get("page", kwargs.get("pg", "1"))
            _cache_page(self, ("searchp", str(key), str(pg)), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def detailContent(self, ids, *args, **kwargs):
        _ensure(self)
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0]) if ids else ""
            call_ids = list(ids)
        else:
            vid = str(ids)
            call_ids = [vid]
        if vid.startswith("nid:"):
            vid = _dec(vid[4:])
            call_ids[0] = vid
        cached = _page_of(self, vid)
        if _orig_detail:
            try:
                r = _orig_detail(self, call_ids, *args, **kwargs)
            except TypeError:
                r = _orig_detail(self, call_ids)
        else:
            r = {"list": []}
        try:
            rr = _as_result(r)
            lst = rr.get("list") or []
            if not lst or not isinstance(lst[0], dict):
                return r
            vod = dict(lst[0])
            vod["vod_id"] = str(vod.get("vod_id") or vid)
            if not vod.get("vod_name"):
                hit = next((x for x in cached if str(x.get("vod_id")) == vid), None)
                if hit:
                    vod["vod_name"] = hit.get("vod_name") or vid
            if cached:
                vod = self._pl_apply_playlist(vid, vod, cached)
            rr = dict(rr)
            rr["list"] = [vod]
            if isinstance(r, dict) or r is None:
                return rr
            try:
                import json as _j
                return _j.dumps(rr, ensure_ascii=False)
            except Exception:
                return rr
        except Exception:
            return r

    def playerContent(self, flag, id, vipFlags=None, *args, **kwargs):
        _ensure(self)
        s = str(id)
        if s.startswith("nid:"):
            vid = _dec(s[4:])
            sources = self._pl_load_src(vid)
            real = ""
            if sources:
                picked = None
                for name, eps in sources:
                    if str(name) == str(flag) and eps:
                        picked = eps
                        break
                if not picked:
                    picked = sources[0][1]
                if picked:
                    real = picked[0][1]
            if real and not str(real).startswith("nid:"):
                id = real
            else:
                id = vid
        if not _orig_player:
            return {"parse": 0, "url": id}
        try:
            return _orig_player(self, flag, id, vipFlags, *args, **kwargs)
        except TypeError:
            try:
                return _orig_player(self, flag, id, vipFlags)
            except TypeError:
                return _orig_player(self, flag, id)

    _C._pl_call_detail = _call_detail
    _C._pl_load_src = _load_src
    _C._pl_item_parts = _item_parts
    _C._pl_apply_playlist = _apply_playlist
    if _orig_init:
        _C.init = init
    if _orig_home:
        _C.homeContent = homeContent
    if _orig_homev:
        _C.homeVideoContent = homeVideoContent
    if _orig_cate:
        _C.categoryContent = categoryContent
    if _orig_search:
        _C.searchContent = searchContent
    if _orig_searchp:
        _C.searchContentPage = searchContentPage
    if _orig_detail:
        _C.detailContent = detailContent
    if _orig_player:
        _C.playerContent = playerContent
    return _C

try:
    _pl_install(Spider)
except Exception:
    pass
# ===== PAGE_PLAYLIST_END =====
