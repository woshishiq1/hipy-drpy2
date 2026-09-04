#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
牛牛视频 爬虫 v3 (主 API nn.123xiangshang.com, 与 APP 数据一致)
- 分类:   GET /types
- 排序:   _CLASS_ORDER 偏好(如 AI短剧紧跟短剧), 仅调序不改数据
- 配置:   GET /config  (动态获取 parser/src 解析器配置)
- 筛选:   子分类超 _FILTER_SPLIT(8) 个拆分为多个筛选组(class/class_moreN), 每组分行显示
- 列表:   GET /list  (class/order/type_id/area/year/state/wd/page, 子分类走 class)
- 首页:   GET /main
- 详情:   GET /detail?vod_id=X   (sources[].episodes[].url, 含 player_id)
- 播放:   player_id → 解析器URL → JSON {code,url,headers}
- 路线:   多播放源用 $$$ 分隔(集内 #, 集 $), 显示 APP 中文线路名(player_name)
- 短剧:   keymp4 为 CENC 加密 mp4+key, 经 _KEYMP4_PROXY 解密代理(见 keymp4_proxy.py)输出明文
响应 AES/ECB/PKCS5 加密, key = "/path?query" 截断16位(不足补"0")
"""
import base64
import json
import re
import requests
from urllib.parse import quote

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        pass

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad


class Spider(BaseSpider):
    name = "牛牛视频"

    # 主 API 域名(APP 默认 base_url, 可在 extend 中覆盖)
    _HOST = "https://nn.123xiangshang.com:35620"

    # 短剧(keymp4)解密代理服务地址, 留空则返回原始加密 mp4(标准播放器无法直接播放)
    # 部署: python3 keymp4_proxy.py --port 8765  (依赖 ffmpeg)
    _KEYMP4_PROXY = "https://8765-abb3ee7c09cf0bb4.monkeycode-ai.online"

    # 请求头(与 APP 拦截器一致: p/pkg/t/d/v/y/product/sys)
    _HEADERS = {
        "p": "android",
        "pkg": "com.sexy.goddess",
        "t": "",
        "d": "0000000000000000",
        "v": "1.6.2",
        "y": "0",
        "product": "Pixel 7",
        "sys": "13",
        "User-Agent": "okhttp/4.9.3",
    }

    # Android Uri.encode(query, "-![.:/,%?&=]") 保留字符集
    _SAFE = "-_.!~*'()[]:/?,%&="

    # src 三步源 → player_id 映射(APP 协议固定, src 配置本身不含 player_id)
    # src1/xm3u8、src2/hema、src7/xiaocao 为 xm3u8 系特殊三步(数字型 ep 需 tokenUrl), 不纳入
    _SRC_PIDS = {
        "src3": "pp", "src4": "madou", "src5": "douban", "src6": "juzi",
        "src8": "shanju", "src9": "ningmeng", "src10": "shizi",
        "src11": "paopao", "src12": "leidian",
    }

    # 实测确认不可用的源(第一步返回二级签名 API 或解析器 500), 播放时直接过滤
    # juzi/shanju: 二级 API 需应用签名; jzzy/hmjc: ht.php/dj.php 返回 500
    _BAD = {"juzi", "shanju", "jzzy", "hmjc"}

    # xm3u8 系特殊三步源(数字型 ep 需 tokenUrl 加密流程), 普通解析器不适用, 过滤
    _XM3U8 = {"xm3u8", "xiaocao", "hema"}

    # 分类排序偏好(仅顺序, 分类数据仍来自 /types):
    # 直播(11)紧跟动漫(4)后, 其后短剧(5)、AI短剧(12)依次排列; 未提及的分类保持服务端顺序
    _CLASS_ORDER = [("11", "4"), ("5", "11"), ("12", "5")]

    # 单行子分类上限: 单个"类型"筛选超过该数量即拆分为多个筛选组(每组独立一行), 避免一行过长
    _FILTER_SPLIT = 8

    def __init__(self):
        self.host = self._HOST
        self.class_cache = None
        self.config_cache = None
        self.parsers_cache = None
        self.page_size = 12
        self.session = requests.Session()
        self.session.verify = False

    def init(self, extend=""):
        if extend:
            try:
                cfg = json.loads(extend)
                if cfg.get("host"):
                    self.host = cfg["host"].rstrip("/")
            except Exception:
                pass

    def getName(self):
        return self.name

    # ========== 加解密与请求 ==========

    def _decrypt(self, pathq, text):
        """响应解密: 明文JSON直接返回, 否则 AES/ECB key=pathq截断16补0"""
        text = (text or "").strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            pass
        try:
            key = (pathq if len(pathq) >= 16 else pathq + "0" * (16 - len(pathq)))[:16]
            ct = base64.b64decode(text)
            cipher = AES.new(key.encode("utf-8"), AES.MODE_ECB)
            return json.loads(unpad(cipher.decrypt(ct), AES.block_size).decode("utf-8"))
        except Exception:
            return {}

    def _get(self, path, params=None):
        """GET 主API, 返回解密后的 dict"""
        raw_q = "&".join("%s=%s" % (k, v) for k, v in (params or {}).items())
        suffix = path + ("?" + quote(raw_q, safe=self._SAFE) if raw_q else "")
        url = self.host + "/" + suffix
        pathq = "/" + suffix
        try:
            r = self.session.get(url, headers=self._HEADERS, timeout=15)
            return self._decrypt(pathq, r.text)
        except Exception:
            return {}

    # ========== 动态配置(来自 /config) ==========

    def _config(self):
        """拉取 APP 动态配置(含 parser/src 列表), 同进程内走内存缓存"""
        if self.config_cache is not None:
            return self.config_cache
        j = self._get("config")
        data = (j or {}).get("data") or {}
        self.config_cache = data
        return data

    def _parsers(self):
        """动态构建 player_id → 第一步解析器URL模板(带缓存)

        数据源: /config 的 parser 列表(enable=1 且 url 非空) + src 三步源 yUrl
        URL 型源(bfzy/tkzy 等)的 ep 是 m3u8 直链, 无需解析器, 播放时直接返回
        """
        if self.parsers_cache is not None:
            return self.parsers_cache
        cfg = self._config()
        mapping = {}
        for p in cfg.get("parser") or []:
            pid = p.get("player_id")
            url = p.get("url") or ""
            if pid and url and p.get("enable") == 1:
                mapping[pid] = url
        for src_key, pid in self._SRC_PIDS.items():
            y_url = (cfg.get(src_key) or {}).get("yUrl") or ""
            if y_url:
                mapping[pid] = y_url
        self.parsers_cache = mapping
        return mapping

    def _player_names(self):
        """动态构建 player_id → APP 中文线路名(来自 /config parser.player_name), 空名回退 pid"""
        cfg = self._config()
        names = {}
        for p in cfg.get("parser") or []:
            pid = p.get("player_id")
            if not pid:
                continue
            name = (p.get("player_name") or "").strip()
            names[pid] = name if name else pid
        return names

    def _list_params(self, wd="", tid="", cls="", order="最新", area="", year="", pg="1"):
        """构造 /list 请求参数(列表/搜索/首页回退共用)"""
        return {
            "class": cls,
            "order": order,
            "type_id": str(tid),
            "area": area,
            "year": year,
            "state": "",
            "wd": wd,
            "page": str(pg),
        }

    # ========== 分类与筛选 ==========

    def _classes(self):
        """从 /types 动态获取分类, 同进程内走内存缓存"""
        if self.class_cache is not None:
            return self.class_cache
        arr = []
        j = self._get("types")
        for m in (j or {}).get("data") or []:
            tid = m.get("type_id")
            name = m.get("type_name")
            if tid is not None and name:
                arr.append({"type_id": str(tid), "type_name": str(name),
                            "type_extend": m.get("type_extend") or {}})
        # APP 服务端可能下掉"短剧"分类入口但内容仍在(tid=5): 补回
        # 插入动漫(4)之后, 最终位置由 _reorder 按 _CLASS_ORDER 统一调整
        if not any(c["type_id"] == "5" for c in arr):
            has_short = bool((self._get("list", self._list_params(tid="5")) or {}).get("data"))
            if has_short:
                short = {"type_id": "5", "type_name": "短剧", "type_extend": {}}
                pos = next((i for i, c in enumerate(arr) if c["type_id"] == "4"), None)
                arr.insert(pos + 1 if pos is not None else 0, short)
        self.class_cache = self._reorder(arr)
        return self.class_cache

    def _reorder(self, classes):
        """应用分类排序偏好(_CLASS_ORDER: 后一个紧跟在前一个之后), 未提及的分类保持服务端顺序"""
        classes = list(classes)
        for after, before in self._CLASS_ORDER:
            m = next((c for c in classes if c["type_id"] == after), None)
            if not m or not any(c["type_id"] == before for c in classes):
                continue
            classes = [c for c in classes if c["type_id"] != after]
            pos = next(i + 1 for i, c in enumerate(classes) if c["type_id"] == before)
            classes.insert(pos, m)
        return classes

    def _filters(self, classes):
        """基于每个分类的 type_extend 动态生成筛选条件(class/area/year + order)"""
        filters = {}
        for c in classes:
            te = c.get("type_extend") or {}
            f = []
            if te.get("class"):
                vals = [v for v in str(te["class"]).split(",") if v]
                # 超过 _FILTER_SPLIT 个子分类时拆分为多个筛选组(每组一行), 避免单行过长看不到后面的
                groups = [vals[i:i + self._FILTER_SPLIT]
                          for i in range(0, len(vals), self._FILTER_SPLIT)]
                for gi, g in enumerate(groups):
                    f.append({
                        "key": "class" if gi == 0 else "class_more%d" % gi,
                        "name": "类型" if gi == 0 else "类型·更多%d" % gi,
                        "value": [{"n": v, "v": v} for v in g],
                    })
            if te.get("area"):
                f.append({
                    "key": "area", "name": "地区",
                    "value": [{"n": v, "v": v} for v in str(te["area"]).split(",")],
                })
            if te.get("year"):
                f.append({
                    "key": "year", "name": "年份",
                    "value": [{"n": v, "v": v} for v in str(te["year"]).split(",")],
                })
            f.append({
                "key": "order", "name": "排序",
                "value": [
                    {"n": "最新", "v": "最新"},
                    {"n": "最热", "v": "最热"},
                    {"n": "评分", "v": "评分"},
                ],
            })
            filters[c["type_id"]] = f
        return filters

    # ========== TVBox 接口 ==========

    def homeContent(self, filter):
        classes = self._classes()

        # 首页推荐: /main 板块列表
        items = []
        j = self._get("main")
        for block in (j or {}).get("data") or []:
            for v in block.get("list") or []:
                items.append(self._vod_from_list(v))
        if not items:
            j = self._get("list", self._list_params(tid="5"))
            items = [self._vod_from_list(v) for v in (j or {}).get("data") or []]

        return {
            "class": [{"type_id": c["type_id"], "type_name": c["type_name"]} for c in classes],
            "filters": self._filters(classes),
            "list": items[:40],
        }

    def homeVideoContent(self):
        j = self._get("list", self._list_params(tid="5"))
        items = [self._vod_from_list(v) for v in (j or {}).get("data") or []]
        return {"list": items}

    def categoryContent(self, tid, pg, filter, extend):
        extend = extend or {}
        pg = int(pg) if str(pg).isdigit() else 1
        # 拆分的"类型·更多N"筛选组共享同一个后端 class 字段, 取第一个非空值
        cls = str(extend.get("class") or "")
        for k, v in extend.items():
            if k.startswith("class_more") and v:
                cls = str(v)
                break
        params = self._list_params(tid=tid, cls=cls,
                                   order=str(extend.get("order") or "最新"),
                                   area=str(extend.get("area") or ""),
                                   year=str(extend.get("year") or ""), pg=pg)
        j = self._get("list", params)
        items = [self._vod_from_list(v) for v in (j or {}).get("data") or []]
        return self._page_result(pg, items)

    def detailContent(self, ids):
        vid = str(ids[0])
        j = self._get("detail", {"vod_id": vid})
        d = (j or {}).get("data") or {}
        if not d.get("vod_name"):
            return {"list": []}

        vod = {
            "vod_id": str(d.get("vod_id") or vid),
            "vod_name": d.get("vod_name", ""),
            "vod_pic": d.get("vod_pic", ""),
            "vod_year": str(d.get("vod_year") or ""),
            "vod_area": d.get("vod_area", ""),
            "type_name": d.get("vod_class", ""),
            "vod_actor": d.get("vod_actor", ""),
            "vod_director": d.get("vod_director", ""),
            "vod_content": d.get("vod_content", "") or d.get("vod_blurb", ""),
            "vod_remarks": d.get("vod_remarks", ""),
        }

        sources = []
        parsers = self._parsers()
        for s_ in d.get("sources") or []:
            pid = s_.get("player_id")
            if not pid or pid in self._BAD or pid in self._XM3U8:
                continue
            eps = s_.get("episodes") or []
            if not eps:
                continue
            # URL 型 ep 直接可播; 数字型 ep 需有动态解析器映射
            first_url = eps[0].get("url") or ""
            if not first_url.startswith("http") and pid not in parsers:
                continue
            raw = s_.get("prio")
            try:
                prio = int(raw) if raw not in (None, "") else 999
            except (TypeError, ValueError):
                prio = 999
            sources.append({"player_id": pid, "prio": prio, "episodes": eps})

        if not sources:
            return {"list": []}

        # 按 prio 排序(小→大); 保留全部可用源作为路线, 自动跟随 APP 侧源增减
        sources.sort(key=lambda x: x["prio"])

        # TVBox 约定: 播放源之间用 $$$ 分隔, 源内各集用 # 分隔, 每集为 "集名$地址@@源id"
        # (若用 # 连接多个源, TVBox 会把整串当作单一源名, 并将所有源的全部集数合并到选集里)
        # 路线显示为 APP 中文线路名(player_name), 选集地址仍带 @@英文pid 供播放时取用
        names = self._player_names()
        play_from = []
        play_urls = []
        for s_ in sources:
            pid = s_["player_id"]
            play_from.append(re.sub(r"[$#]", "", names.get(pid, pid)))
            eps_str = "#".join(
                "%s$%s@@%s" % (e.get("name") or "第%02d集" % (i + 1), e.get("url"), pid)
                for i, e in enumerate(s_["episodes"])
            )
            play_urls.append(eps_str)
        vod["vod_play_from"] = "$$$".join(play_from)
        vod["vod_play_url"] = "$$$".join(play_urls)
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg) if str(pg).isdigit() else 1
        j = self._get("list", self._list_params(wd=str(key), pg=pg))
        items = [self._vod_from_list(v) for v in (j or {}).get("data") or []]
        return self._page_result(pg, items)

    def playerContent(self, flag, id, vipFlags):
        s = str(id)
        if "@@" in s:
            ep, player = s.rsplit("@@", 1)
        else:
            ep, player = s, str(flag)

        # 路线显示为中文名时, 部分播放器可能把 flag(中文名)直接当源 id 传入, 反查回 pid
        # (同名线路可能对应多个 pid, 优先取解析器映射中真实生效的那个)
        parsers = self._parsers()
        if player not in parsers:
            for pid, name in self._player_names().items():
                if name == player and pid in parsers:
                    player = pid
                    break

        # URL 型 ep(m3u8/mp4/ts)直接可播
        if ep.startswith("http") and re.search(r"\.(m3u8|mp4|ts|flv)(\?|$)", ep):
            return {"parse": 0, "playUrl": "", "url": ep, "header": "{}"}

        tpl = parsers.get(player)
        if not tpl:
            return {"parse": 1, "playUrl": "", "url": ""}

        # src 三步源的 yUrl 为完整前缀(不带 %s), parser 型带 %s 占位符
        url = tpl.replace("%s", ep) if "%s" in tpl else tpl + ep
        try:
            r = self.session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            j = r.json()
        except Exception:
            return {"parse": 1, "playUrl": "", "url": ""}

        play = (j or {}).get("url") or ""
        if not play:
            return {"parse": 1, "playUrl": "", "url": ""}

        # keymp4: CENC 加密 mp4 + 解密密钥, 标准播放器无法直播
        # 配置解密代理后改为返回代理地址(代理内部下载解密并流式输出明文 mp4)
        if (j or {}).get("type") == "keymp4" and self._KEYMP4_PROXY:
            key = (j or {}).get("key") or ""
            if key:
                play = "%s/decode?u=%s&k=%s" % (self._KEYMP4_PROXY, quote(play, safe=""), key)

        headers = self._parse_headers((j or {}).get("headers") or "")
        return {"parse": 0, "playUrl": "", "url": play, "header": json.dumps(headers)}

    def isVideoContent(self):
        return True

    # ========== 内部方法 ==========

    def _page_result(self, pg, items):
        """构造分页列表响应(接口每页固定 12 条, 有数据则 pagecount 递增表示可继续翻页)"""
        return {
            "page": pg,
            "pagecount": pg + 1 if items else pg,
            "limit": self.page_size,
            "total": 99999,
            "list": items,
        }

    @staticmethod
    def _parse_headers(s):
        """解析器响应的 headers 字符串(换行/回车分隔 key:value) → dict"""
        out = {}
        if not s:
            return out
        for line in str(s).replace("\r", "").split("\n"):
            if ":" in line:
                k, _, v = line.partition(":")
                k = k.strip()
                if k:
                    out[k] = v.strip()
        return out

    @staticmethod
    def _vod_from_list(v):
        return {
            "vod_id": str(v.get("vod_id") or ""),
            "vod_name": v.get("vod_name", ""),
            "vod_pic": v.get("vod_pic", ""),
            "vod_remarks": v.get("vod_remarks", ""),
        }
