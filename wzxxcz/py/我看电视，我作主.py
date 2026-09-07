# -*- coding: utf-8 -*-
# @tvbox-role manager
# @version v5.1-lite-pc
# 电脑端 PeekPro 精简版：
#   - 只扫描 SCAN_DIR 下的 .py 源文件（递归子目录）
#   - 点击 py 源直接使用（代理模式：浏览/搜索/播放全部透传给该源的 Spider）
#   - 导航模型与宿主一致：顶部标签 = 「源·分类」，点标签出视频列表，点视频进详情/播放
#   - 不生成、不写入 智能点播.json，无任何注册表操作


import importlib.util
import json
import os
import socket
import threading
import time

from base.spider import Spider as BaseSpider

# 自定义扫描目录：
#   留空 ""  -> 使用当前脚本所在目录为根目录
#   填路径  -> 使用自定义目录，例如 r"/storage/emulated/0/lz/"
CUSTOM_SCAN_DIR = "/storage/emulated/0/"

# 扫描目录：以当前脚本所在目录为根目录（递归子目录）
SCAN_DIR = (
    os.path.abspath(os.path.expanduser(CUSTOM_SCAN_DIR))
    if str(CUSTOM_SCAN_DIR or "").strip()
    else os.path.dirname(os.path.abspath(__file__))
)


# 扫描上限，防止目录异常时列表爆炸
MAX_FILES = 500

# 单个源拉取分类的时限（秒）：超时放弃，保证任何界面不卡死
HOME_DEADLINE = 6.0

# 全局 socket 超时（秒）：防止底层源 urllib 请求无限挂起
try:
    socket.setdefaulttimeout(10)
except Exception:
    pass

# 分类缓存文件：首次加载后落盘，之后启动秒开
CACHE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".pc_lite_home_cache.json"
)

# 诊断日志：卡顿时查看此文件最后几行定位阶段
LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".pc_lite_log.txt"
)


def _log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fp:
            fp.write("[{}] {}\n".format(time.strftime("%H:%M:%S"), msg))
    except Exception:
        pass


_log("模块导入完成")


class Spider(BaseSpider):
    # ==========================================================================
    # 内部状态
    # ==========================================================================
    def __init__(self):
        super().__init__()
        self.lock = threading.RLock()
        self.sites = []      # [{"name","path","spider","error","home"}]
        self.scanned = False

    def init(self, extend=""):
        _log("init 开始")
        self._scan()
        _log("init 完成，扫描到 {} 个py源".format(len(self.sites)))

    def getName(self):
        return "本地py源直载"

    # ==========================================================================
    # 扫描与加载
    # ==========================================================================
    def _scan(self):
        with self.lock:
            if self.scanned:
                return
            sites = []
            self_path = ""
            try:
                self_path = os.path.realpath(__file__)
            except Exception:
                pass
            if os.path.isdir(SCAN_DIR):
                for root, dirs, files in os.walk(SCAN_DIR):
                    dirs[:] = [d for d in dirs if not d.startswith(".")]
                    for name in sorted(files):
                        if not name.lower().endswith(".py"):
                            continue
                        path = os.path.join(root, name)
                        try:
                            if self_path and os.path.realpath(path) == self_path:
                                continue
                        except Exception:
                            pass
                        sites.append({
                            "name": os.path.splitext(name)[0],
                            "path": path,
                            "spider": None,
                            "error": "",
                            "home": None,
                        })
                        if len(sites) >= MAX_FILES:
                            break
                    if len(sites) >= MAX_FILES:
                        break
            self.sites = sites
            self.scanned = True

    def _rescan(self):
        with self.lock:
            self.scanned = False
            self.sites = []
        self._scan()

    def _load_spider(self, site):
        """懒加载 py 源：导入文件 -> 找到 Spider 类 -> 实例化并 init，结果缓存。"""
        with self.lock:
            if site["spider"] is not None or site["error"]:
                return site["spider"]
            try:
                spec = importlib.util.spec_from_file_location(
                    "local_py_site_{}".format(abs(hash(site["path"]))),
                    site["path"],
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                spider_cls = getattr(module, "Spider", None)
                if spider_cls is None:
                    for value in vars(module).values():
                        if (
                            isinstance(value, type)
                            and issubclass(value, BaseSpider)
                            and value is not BaseSpider
                        ):
                            spider_cls = value
                            break
                if spider_cls is None:
                    raise RuntimeError("文件中未找到 Spider 类")
                spider = spider_cls()
                try:
                    spider.init("")
                except TypeError:
                    spider.init()
                site["spider"] = spider
            except Exception as exc:
                site["error"] = str(exc)[:200]
            return site["spider"]

    def _fetch_home(self, site):
        """加载源并拉取其分类（homeContent），缓存到 site["home"]。"""
        spider = self._load_spider(site)
        if spider is None:
            return
        try:
            result = spider.homeContent(True)
            if isinstance(result, dict):
                site["home"] = result
        except Exception as exc:
            if not site["error"]:
                site["error"] = str(exc)[:200]

    # ---------------- 分类缓存：避免每次启动都联网拉取 ----------------
    def _file_mtime(self, path):
        try:
            return int(os.path.getmtime(path))
        except Exception:
            return 0

    def _cache_key(self, site):
        try:
            return os.path.realpath(site["path"])
        except Exception:
            return site["path"]

    def _load_home_cache(self):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_home_cache(self, cache):
        try:
            with open(CACHE_PATH, "w", encoding="utf-8") as fp:
                json.dump(cache, fp, ensure_ascii=False)
        except Exception:
            pass

    def _fetch_home_bounded(self, site, timeout):
        """在独立守护线程里拉取分类，主线程最多等 timeout 秒，绝不挂死。"""
        done = threading.Event()

        def runner():
            try:
                self._fetch_home(site)
            except Exception:
                pass
            finally:
                done.set()

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        done.wait(timeout)
        return done.is_set()

    def _site_by_id(self, idx):
        try:
            return self.sites[int(idx)]
        except Exception:
            return None

    # ==========================================================================
    # TVBox 标准接口
    # 两级导航：
    #   一级标签 tid = s:{i}            -> 第 i 个 py 脚本
    #   二级分类 通过该标签的筛选栏选择   -> extend["cat"] = 源内分类 type_id
    # vod_id 编码：
    #   v:{i}:{vod_id}       -> 第 i 个源内的影片（详情/播放用）
    # 播放 flag 编码为 "{i}|{原flag}"，playerContent 据此路由回对应源
    # ==========================================================================
    def homeContent(self, filter):
        _log("homeContent 开始")
        self._scan()
        # 首页只做纯本地操作（扫文件+读缓存），立即返回，绝不联网/不等待线程
        cache = self._load_home_cache()
        pending = []
        for site in self.sites:
            entry = cache.get(self._cache_key(site))
            if entry and entry.get("mtime") == self._file_mtime(site["path"]):
                site["home"] = {
                    "class": entry.get("class") or [],
                    "filters": entry.get("filters") or {},
                }
            else:
                pending.append(site)
        # 未缓存的源：后台守护线程慢慢拉取并落盘，下次启动/重扫即展开
        if pending:
            thread = threading.Thread(
                target=self._background_fetch, args=(pending,), daemon=True
            )
            thread.start()

        classes = [
            {"type_id": "rescan", "type_name": "🔄 重新扫描 ({})".format(len(self.sites))},
        ]
        filters = {}
        for i, site in enumerate(self.sites):
            tid = "s:{}".format(i)
            classes.append({
                "type_id": tid,
                "type_name": site["name"] + ("[加载失败]" if site["error"] else ""),
            })
            # 二级分类：源内分类映射为该标签的筛选栏
            home = site.get("home") or {}
            cats = home.get("class") or []
            if cats:
                values = [
                    {"n": str(c.get("type_name", "")), "v": str(c.get("type_id", ""))}
                    for c in cats
                ]
                filters[tid] = [{"key": "cat", "name": "分类", "value": values}]
        _log("homeContent 返回 {} 个标签".format(len(classes)))
        return {"class": classes, "list": [], "filters": filters}

    def _background_fetch(self, sites):
        """后台逐个拉取未缓存源的分类并落盘；每个源最多等 HOME_DEADLINE 秒。"""
        cache = self._load_home_cache()
        for site in sites:
            _log("后台拉取: {}".format(site["name"]))
            self._fetch_home_bounded(site, HOME_DEADLINE)
            home = site.get("home")
            if home:
                cache[self._cache_key(site)] = {
                    "mtime": self._file_mtime(site["path"]),
                    "class": home.get("class") or [],
                    "filters": home.get("filters") or {},
                }
                self._save_home_cache(cache)
                _log("后台拉取成功: {}".format(site["name"]))
            else:
                _log("后台拉取失败: {} - {}".format(site["name"], site["error"]))

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        self._scan()
        if tid == "rescan":
            self._rescan()
            return self._page_result(self._site_items(), 1)

        if tid.startswith("s:"):
            site = self._site_by_id(tid[2:])
            if site is None:
                return self._page_result(self._msg_items("源不存在，请重新扫描"), 1)
            idx = int(tid[2:])
            if site.get("home") is None:
                # 未缓存的源：点进来时同步补拉，最多等 HOME_DEADLINE 秒
                _log("同步补拉: {}".format(site["name"]))
                self._fetch_home_bounded(site, HOME_DEADLINE)
                if site.get("home"):
                    cache = self._load_home_cache()
                    cache[self._cache_key(site)] = {
                        "mtime": self._file_mtime(site["path"]),
                        "class": site["home"].get("class") or [],
                        "filters": site["home"].get("filters") or {},
                    }
                    self._save_home_cache(cache)
            home = site.get("home") or {}
            cats = home.get("class") or []
            ext = self._parse_extend(extend)
            cat = str(ext.get("cat", "") or "").strip()
            if not cat and cats:
                # 未选二级分类时默认进第一个分类
                cat = str(cats[0].get("type_id", ""))
            spider = self._load_spider(site)
            if spider is None:
                return self._page_result(
                    self._msg_items("加载失败：{}".format(site["error"])), 1
                )
            if cat:
                result = self._safe_call(
                    spider.categoryContent, cat, pg, filter, ext
                )
                videos = result.get("list") or []
                if videos:
                    return self._wrap_videos(idx, videos, pg, result)
            # 无分类或分类无数据：回退到源首页推荐
            videos = home.get("list") or []
            if videos:
                return self._wrap_videos(idx, videos, pg)
            return self._page_result(
                self._msg_items("加载失败：{}".format(site["error"] or "源无首页数据")), 1
            )

        return self._page_result([], 1)

    def detailContent(self, array):
        vid = str(array[0]) if isinstance(array, (list, tuple)) and array else str(array or "")
        if vid.startswith("s:"):
            # 信息项（重新扫描列表里的条目）：展示源信息，不可播放
            site = self._site_by_id(vid[2:])
            if site is None:
                return {"list": []}
            return {
                "list": [
                    {
                        "vod_id": vid,
                        "vod_name": site["name"],
                        "vod_pic": "",
                        "vod_remarks": "本地py源",
                        "vod_content": "文件：{}\n状态：{}".format(
                            site["path"], site["error"] or "正常"
                        ),
                        "vod_play_from": "",
                        "vod_play_url": "",
                    }
                ]
            }
        if not vid.startswith("v:"):
            return {"list": []}
        parts = vid.split(":", 2)
        if len(parts) != 3:
            return {"list": []}
        idx, vod_id = parts[1], parts[2]
        site = self._site_by_id(idx)
        if site is None:
            return {"list": []}
        spider = self._load_spider(site)
        if spider is None:
            return {"list": self._msg_items("加载失败：{}".format(site["error"]))}
        result = self._safe_call(spider.detailContent, [vod_id])
        # 播放线路 flag 前缀化，playerContent 才能路由回对应源
        for vod in result.get("list") or []:
            flags = str(vod.get("vod_play_from", "") or "")
            if flags:
                vod["vod_play_from"] = "$$$".join(
                    "{}|{}".format(idx, f) for f in flags.split("$$$") if f
                )
        return result

    def playerContent(self, flag, id, vipFlags):
        idx = None
        real_flag = flag
        head, sep, tail = str(flag or "").partition("|")
        if sep and head.isdigit():
            idx = int(head)
            real_flag = tail
        if idx is None:
            return {"parse": 0, "url": "", "header": {}, "msg": "未知播放来源"}
        site = self._site_by_id(idx)
        if site is None:
            return {"parse": 0, "url": "", "header": {}, "msg": "源不存在，请重新扫描"}
        spider = self._load_spider(site)
        if spider is None:
            return {
                "parse": 0, "url": "", "header": {},
                "msg": "源加载失败：{}".format(site["error"]),
            }
        try:
            return spider.playerContent(real_flag, id, vipFlags)
        except Exception as exc:
            return {
                "parse": 0, "url": "", "header": {},
                "msg": "播放失败：{}".format(str(exc)[:120]),
            }

    def searchContent(self, key, quick, pg="1"):
        self._scan()
        videos = []
        for i, site in enumerate(self.sites):
            spider = self._load_spider(site)
            if spider is None:
                continue
            try:
                result = spider.searchContent(key, quick, pg)
            except Exception:
                continue
            for vod in (result or {}).get("list") or []:
                vod = dict(vod)
                vod["vod_id"] = "v:{}:{}".format(i, vod.get("vod_id", ""))
                vod["vod_remarks"] = "{} {}".format(
                    site["name"], str(vod.get("vod_remarks", "") or "")
                ).strip()
                videos.append(vod)
        return {"list": videos}

    # ==========================================================================
    # 工具方法
    # ==========================================================================
    def _parse_extend(self, extend):
        """宿主传来的筛选参数可能是 dict / JSON 字符串 / key=value 串，统一成 dict。"""
        if isinstance(extend, dict):
            return extend
        text = str(extend or "").strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            pass
        result = {}
        for part in text.split("&"):
            if "=" in part:
                key, _, value = part.partition("=")
                result[key] = value
        return result
    def _safe_call(self, func, *args):
        try:
            result = func(*args)
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}

    def _wrap_videos(self, idx, videos, pg, raw=None):
        """把底层源返回的影片列表 vod_id 前缀化后透传分页信息。"""
        wrapped = []
        for vod in videos:
            vod = dict(vod)
            vod["vod_id"] = "v:{}:{}".format(idx, vod.get("vod_id", ""))
            wrapped.append(vod)
        result = dict(raw) if isinstance(raw, dict) else {}
        result["list"] = wrapped
        result.setdefault("page", pg)
        result.setdefault("pagecount", 1)
        result.setdefault("limit", len(wrapped))
        result.setdefault("total", len(wrapped))
        return result

    def _site_items(self):
        return [
            {
                "vod_id": "s:{}".format(i),
                "vod_name": ("[失败] " if site["error"] else "") + site["name"],
                "vod_pic": "",
                "vod_remarks": site["error"] or os.path.dirname(site["path"]),
            }
            for i, site in enumerate(self.sites)
        ]

    def _msg_items(self, text):
        return [{
            "vod_id": "",
            "vod_name": text,
            "vod_pic": "",
            "vod_remarks": "",
        }]

    def _page_result(self, videos, pg):
        return {
            "page": pg,
            "pagecount": 1,
            "limit": len(videos),
            "total": len(videos),
            "list": videos,
        }
