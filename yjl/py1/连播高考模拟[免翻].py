# -*- coding: utf-8 -*-
"""
TVBox影视壳插件 - 三年高考五年模拟
适配自 lold.py 全自动点播抓取
"""
import sys
import json
import random
import time
import re
import requests
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

sys.path.append('..')
from base.spider import Spider

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Spider(Spider):
    
    # ========== 配置 ==========
    DOMAIN_API = "https://lwncnss3api.cc/api/getapi.php"
    CACHE_FILE = "domain_cache_3n.json"
    CACHE_EXPIRE = 3600  # 缓存有效期1小时
    
    # 硬编码备用域名
    BACKUP_DOMAINS = [
        "dag29jmgma1g.site",
        "ldngksapi.cc",
        "lagh23ksapi.cc",
        "ldagwhdgpi.cc",
        "lwetasdf3api.cc",
        "lwasga289api.cc",
        "lw2wthchhaapi.cc",
        "lwncnss3api.cc",
        "lw23412gaapi.cc"
    ]
    
    TIMEOUT = 15
    DETAIL_RETRY = 3
    REG_GAP = 1.2
    REG_TRY = 5
    
    # 分类列表（从原代码迁移）
    VOD_CLASSES = [
    '重口猎奇',
    '迷奸强奸',
    '校园霸凌',
    '真实乱伦',
    '监控偷拍',  
    '学生破处',
    '淫荡孕妇',        
    '萝莉',
    "小学",
    "初中",
    "高中",
    "小马",
    "人妖伪娘",
    '户外露出',
    '绿帽抓奸',
    '反差母犬',
    '少女媚黑',
    '暗网萝莉',
    '少女萝莉',
    '学生',
    '自慰',
    'JK',
    '母子通奸',
    '父女禁恋',
    '兄妹相爱',
    '姐弟情深',
    '舅侄畸恋',
    '全家乱P',
    '师生淫乱',
    '偷窥偷拍',
    '裸聊实录',
    '主播大秀',
    '原创自拍',
    '车震野战',
    'SM捆绑',
    '探花大神',
    '勾引搭讪',
    '最新热点',
    '独家精选',
    '学生校园',
    '网红网暴',
    '热门大瓜',
    '明星黑幕',
    '反差母狗',
    '领导干部',
    '百合',
    '足交',
    '丝袜',
    '内射',
    'Cospaly',
    '换妻Club',
    '偷窥萝莉'
    ]
    
    # 设备伪装列表
    DEVICES = [
        ("ONEPLUS A5000", "OPR6.170623.013"),
        ("Pixel 4", "QQ3A.200805.001"),
        ("SM-G973F", "QP1A.190711.020"),
        ("Mi 9", "PKQ1.181121.001"),
        ("Redmi Note 8", "QKQ1.200114.002"),
    ]
    
    # 图片提取正则
    RE_IMG = re.compile(r'(?:data-src|src|poster|cover|pic|image)=["\']([^"\']+\.(?:jpg|png|jpeg|webp|gif))[^"\']*["\']', re.I)
    RE_IMG_URL = re.compile(r'(https?://[^\s"\']+\.(?:jpg|png|jpeg|webp|gif))', re.I)
    
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.token = None
        self.last_reg = 0.0
        self.cache = {}
        self.domains = []
        self.working_domains = []
        self.current_domain_index = 0
        self._load_domains()
        if len(self.domains) < 3:
            self.domains.extend(self.BACKUP_DOMAINS)
            self.domains = list(set(self.domains))

    def getName(self):
        return "三年高考五年模拟"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    # ========== 域名管理 ==========
    def _get_cache_path(self):
        """获取缓存文件路径"""
        return os.path.join(os.path.dirname(__file__), self.CACHE_FILE)

    def _load_domains(self):
        """加载域名列表（优先从缓存读取）- 不过滤黑名单"""
        cache_path = self._get_cache_path()
        
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    cache_time = cache_data.get('cache_time', 0)
                    if time.time() - cache_time < self.CACHE_EXPIRE:
                        domains = cache_data.get('domains', [])
                        self.domains = [d for d in domains if d and isinstance(d, str) and '.' in d]
                        if self.domains:
                            print(f'[DOMAIN] Loaded {len(self.domains)} domains from cache')
                            return
            except Exception as e:
                print(f'[CACHE] Read cache failed: {e}')
        
        self._fetch_domains()

    def _fetch_domains(self):
        """从API获取域名列表并缓存 - 不过滤黑名单，全部轮询"""
        try:
            r = requests.get(self.DOMAIN_API, timeout=10, verify=False)
            
            try:
                data = r.json()
            except:
                domains = re.findall(r'[\w\-\.]+\.(?:com|cc|net|org|site|top|xyz)', r.text)
                if domains:
                    self.domains = list(set(domains))
                    self._save_cache(self.domains)
                    return
            
            if data.get('code') == 200:
                domains = data.get('data', [])
                blacklist = data.get('blackdomain', [])
                
                if isinstance(domains, str):
                    try:
                        domains = json.loads(domains)
                    except:
                        domains = [domains]
                
                if not isinstance(domains, list):
                    domains = [str(domains)] if domains else []
                
                # 不过滤黑名单，合并所有域名
                all_domains = list(set(domains + blacklist))
                self.domains = [d for d in all_domains if d and isinstance(d, str) and '.' in d]
                
                # 把 data 里的域名放在前面
                priority_domains = [d for d in domains if d and '.' in d]
                other_domains = [d for d in self.domains if d not in priority_domains]
                self.domains = priority_domains + other_domains
                
                if self.domains:
                    print(f'[DOMAIN] Fetched {len(self.domains)} domains from API')
                    self._save_cache(all_domains)
                else:
                    print('[DOMAIN] No valid domains, using backup')
                    self.domains = self.BACKUP_DOMAINS.copy()
            else:
                print(f'[DOMAIN] API returned error, using backup')
                self.domains = self.BACKUP_DOMAINS.copy()
        except Exception as e:
            print(f'[DOMAIN] Fetch failed: {e}')
            self.domains = self.BACKUP_DOMAINS.copy()

    def _save_cache(self, domains):
        """保存缓存"""
        try:
            cache_data = {
                'domains': domains,
                'cache_time': time.time()
            }
            cache_path = self._get_cache_path()
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f'[CACHE] Save failed: {e}')

    def _get_base_url(self):
        """获取当前可用的基础URL"""
        if not self.domains:
            self._load_domains()
            if not self.domains:
                return "https://dag29jmgma1g.site"
        
        # 尝试之前找到的工作域名
        if self.working_domains:
            for domain in self.working_domains[:]:
                for protocol in ['https', 'http']:
                    try:
                        url = f"{protocol}://{domain}/api/setapp.php"
                        r = self.session.get(url, timeout=5, verify=False)
                        if r.status_code == 200:
                            return f"{protocol}://{domain}"
                    except:
                        continue
                self.working_domains.remove(domain)
        
        # 尝试所有域名
        for domain in self.domains:
            for protocol in ['https', 'http']:
                try:
                    url = f"{protocol}://{domain}/api/setapp.php"
                    r = self.session.get(url, timeout=5, verify=False)
                    if r.status_code == 200:
                        self.working_domains.append(domain)
                        base = f"{protocol}://{domain}"
                        print(f'[DOMAIN] Using: {base}')
                        return base
                except:
                    continue
        
        print('[DOMAIN] No working domain found')
        return "https://dag29jmgma1g.site"

    def _request_api(self, path, method='post', data=None):
        """通用API请求方法，自动轮询域名"""
        base_url = self._get_base_url()
        url = base_url + path
        
        try:
            headers = self._headers()
            if method.lower() == 'get':
                r = self.session.get(url, timeout=self.TIMEOUT, verify=False)
            else:
                r = self.session.post(url, data=data, headers=headers, timeout=self.TIMEOUT, verify=False)
            return r
        except Exception as e:
            print(f'[REQUEST] {url} failed: {e}')
            # 当前域名失败，从工作列表中移除
            domain = base_url.replace('https://', '').replace('http://', '')
            if domain in self.working_domains:
                self.working_domains.remove(domain)
            # 递归重试
            return self._request_api(path, method, data)

    # ========== 工具方法 ==========
    def _ua(self):
        """生成随机UA"""
        m, b = random.choice(self.DEVICES)
        a = random.choice(["8.0.0", "9", "10", "11", "12"])
        c = random.randint(120, 138)
        return (
            f"Mozilla/5.0 (Linux; Android {a}; {m} Build/{b}; wv) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
            f"Chrome/{c}.0.{random.randint(0,7204)}.{random.randint(100,200)} "
            f"Mobile Safari/537.36 uni-app Html5Plus/1.0 (Immersed/24.0)"
        )

    def _headers(self):
        return {
            "User-Agent": self._ua(),
            "Content-Type": "application/x-www-form-urlencoded",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
        }

    def _parse_json(self, resp):
        if resp is None:
            return None
        t = (resp.text or "").strip()
        if not t:
            return None
        try:
            return resp.json()
        except Exception:
            try:
                return json.loads(t)
            except Exception:
                return None

    def _find_first(self, obj, key):
        """递归查找第一个匹配的值"""
        if isinstance(obj, dict):
            if key in obj and obj[key] not in (None, ""):
                return str(obj[key])
            for v in obj.values():
                r = self._find_first(v, key)
                if r is not None:
                    return r
        elif isinstance(obj, list):
            for x in obj:
                r = self._find_first(x, key)
                if r is not None:
                    return r
        return None

    def _find_all(self, obj, key, out=None):
        """递归查找所有匹配的值"""
        if out is None:
            out = []
        if isinstance(obj, dict):
            if key in obj and obj[key] not in (None, ""):
                out.append(str(obj[key]))
            for v in obj.values():
                self._find_all(v, key, out)
        elif isinstance(obj, list):
            for x in obj:
                self._find_all(x, key, out)
        return out

    def _collect_items(self, obj, out=None):
        """从响应中收集 vod_id 和 vod_name"""
        if out is None:
            out = []
        if isinstance(obj, dict):
            if "vod_id" in obj and obj["vod_id"] not in (None, ""):
                pic = ""
                pic = self._find_first(obj, "vod_pic") or ""
                if not pic:
                    pic = self._find_first(obj, "vod_img") or ""
                if not pic:
                    pic = self._find_first(obj, "pic") or ""
                if not pic:
                    pic = self._find_first(obj, "cover") or ""
                if not pic:
                    pic = self._find_first(obj, "image") or ""
                
                if pic and pic.startswith("//"):
                    pic = "https:" + pic
                elif pic and pic.startswith("/") and not pic.startswith("//"):
                    base = self._get_base_url()
                    pic = base + pic
                
                out.append({
                    "vod_id": str(obj["vod_id"]),
                    "vod_name": str(obj.get("vod_name") or obj.get("name") or ""),
                    "vod_pic": pic,
                    "vod_remarks": str(obj.get("vod_remarks") or obj.get("remarks") or obj.get("status") or "")
                })
            else:
                for v in obj.values():
                    self._collect_items(v, out)
        elif isinstance(obj, list):
            for x in obj:
                self._collect_items(x, out)
        return out

    def _collect_detail(self, obj):
        """从详情响应中提取完整信息"""
        result = {
            "vod_id": "",
            "vod_name": "",
            "vod_pic": "",
            "vod_content": "",
            "vod_play_url": "",
            "vod_actor": "",
            "vod_director": "",
            "type_name": "",
        }
        
        result["vod_id"] = self._find_first(obj, "vod_id") or ""
        result["vod_name"] = self._find_first(obj, "vod_name") or self._find_first(obj, "name") or ""
        
        pic = self._find_first(obj, "vod_pic") or ""
        if not pic:
            pic = self._find_first(obj, "vod_img") or ""
        if not pic:
            pic = self._find_first(obj, "pic") or ""
        if not pic:
            pic = self._find_first(obj, "cover") or ""
        if not pic:
            pic = self._find_first(obj, "image") or ""
        if not pic:
            pic = self._find_first(obj, "poster") or ""
        
        if pic and pic.startswith("//"):
            pic = "https:" + pic
        elif pic and pic.startswith("/") and not pic.startswith("//"):
            base = self._get_base_url()
            pic = base + pic
        result["vod_pic"] = pic
        
        result["vod_content"] = self._find_first(obj, "vod_content") or self._find_first(obj, "description") or self._find_first(obj, "desc") or ""
        result["vod_actor"] = self._find_first(obj, "vod_actor") or self._find_first(obj, "actor") or ""
        result["vod_director"] = self._find_first(obj, "vod_director") or self._find_first(obj, "director") or ""
        result["type_name"] = self._find_first(obj, "type_name") or self._find_first(obj, "type") or self._find_first(obj, "vod_class") or ""
        
        raw_urls = self._find_all(obj, "vod_play_url")
        play_urls = []
        for raw in raw_urls:
            play_urls.extend(self._extract_play_urls(raw))
        play_urls = list(dict.fromkeys(play_urls))
        result["vod_play_url"] = "#".join([f"第{i+1}集${url}" for i, url in enumerate(play_urls)])
        
        return result

    def _rate_limited(self, body):
        """检查是否被限频"""
        if not isinstance(body, dict):
            return False
        msg = str(body.get("msg", ""))
        return "频繁" in msg or "太快" in msg or "频率" in msg

    def _extract_play_urls(self, raw):
        """从 vod_play_url 字段解析播放地址"""
        if not raw:
            return []
        s = str(raw).strip()
        if not s or s.lower() in ("null", "none", "undefined"):
            return []
        parts = [p for p in s.split("#") if p.strip()]
        if not parts:
            parts = [s]
        out = []
        for part in parts:
            part = part.strip()
            if "$" in part:
                part = part.split("$")[-1].strip()
            if self._ok_url(part) and part not in out:
                out.append(part)
        return out

    def _ok_url(self, u):
        if not u:
            return False
        s = u.strip()
        if not s or s.lower() in ("null", "none", "undefined"):
            return False
        if "$" in s:
            s = s.split("$")[-1].strip()
        return s.startswith(("http://", "https://", "magnet:")) or "http://" in s or "https://" in s

    # ========== Token 管理 ==========
    def _newreg_once(self):
        """注册获取token"""
        try:
            r = self._request_api('/api/newreg.php', 'post', 
                data="device=android&ntoken=&channel_code=vbtQg9D8")
        except requests.RequestException as e:
            print(f"[newreg] 失败: {e}")
            return None, False
        
        body = self._parse_json(r)
        if body is None:
            return None, False
        
        if self._rate_limited(body):
            print(f"[newreg] 限频: {body.get('msg')}")
            return None, True
        
        t = None
        if isinstance(body, dict):
            u = body.get("user")
            if isinstance(u, dict) and u.get("token"):
                t = str(u["token"])
        if not t:
            t = self._find_first(body, "token")
        return t, False

    def _refresh_token(self):
        """刷新token"""
        for i in range(self.REG_TRY):
            gap = self.REG_GAP - (time.time() - self.last_reg)
            if gap > 0:
                time.sleep(gap)
            t, limited = self._newreg_once()
            if t:
                self.token = t
                self.last_reg = time.time()
                print(f"[token] {t[:12]}...")
                return t
            if limited:
                wait = min(30.0, 2.0 * (2**i) + random.uniform(0.2, 1.0))
                print(f"[newreg] 退避 {wait:.1f}s")
                time.sleep(wait)
            else:
                time.sleep(self.REG_GAP)
        print("[newreg] 失败次数过多")
        return None

    def _get_token(self, force=False):
        if force or not self.token:
            return self._refresh_token()
        return self.token

    # ========== API 调用 ==========
    def _api_vlist(self, vodclass, num):
        """获取视频列表"""
        data = {
            "num": str(num),
            "pid": "4",
            "area": "全部",
            "vodclass": vodclass,
            "vodyear": "全部",
            "sort": "1",
            "type": "undefined",
        }
        return self._request_api('/api/vlist.php', 'post', data=data)

    def _api_detail(self, vod_id, tok):
        """获取视频详情"""
        data = f"id={vod_id}&token={tok}&channel="
        return self._request_api('/api/Get_vod_list.php', 'post', data=data)

    # ========== 核心方法 ==========
    def homeContent(self, filter):
        """首页分类"""
        cats = []
        for cls in self.VOD_CLASSES:
            cats.append({"type_name": cls, "type_id": cls})
        
        return {"class": cats, "filters": {}}

    def homeVideoContent(self):
        """首页视频（默认第一个分类）"""
        if self.VOD_CLASSES:
            return self.categoryContent(self.VOD_CLASSES[0], "1", None, {})
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        """分类内容"""
        try:
            tok = self._get_token()
            if not tok:
                return {"list": []}
            
            page_num = int(pg) if pg else 1
            offset = (page_num - 1) * 30
            
            r = self._api_vlist(tid, offset)
            body = self._parse_json(r)
            if body is None:
                return {"list": []}
            
            items = self._collect_items(body)
            
            vlist = []
            for item in items:
                vlist.append({
                    "vod_id": item["vod_id"],
                    "vod_name": item["vod_name"],
                    "vod_pic": item.get("vod_pic", ""),
                    "vod_remarks": item.get("vod_remarks", "")
                })
            
            return {
                "list": vlist,
                "page": pg,
                "pagecount": 999,
                "limit": 30,
                "total": 99999
            }
        except Exception as e:
            print(f"categoryContent error: {e}")
            return {"list": []}

    def detailContent(self, ids):
        """详情内容"""
        vid = ids[0]
        
        cache_key = f"detail_{vid}"
        if cache_key in self.cache:
            return {"list": [self.cache[cache_key]]}
        
        try:
            tok = self._get_token()
            if not tok:
                return {"list": []}
            
            r = self._api_detail(vid, tok)
            body = self._parse_json(r)
            if body is None:
                return {"list": []}
            
            detail = self._collect_detail(body)
            
            result = {
                "vod_id": vid,
                "vod_name": detail["vod_name"] or "未知",
                "vod_pic": detail["vod_pic"],
                "type_name": detail["type_name"] or "课程",
                "vod_content": detail["vod_content"],
                "vod_actor": detail["vod_actor"],
                "vod_director": detail["vod_director"],
                "vod_play_from": "三年高考",
                "vod_play_url": detail["vod_play_url"]
            }
            
            self.cache[cache_key] = result
            
            return {"list": [result]}
        except Exception as e:
            print(f"detailContent error: {e}")
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        """搜索内容"""
        results = []
        for cls in self.VOD_CLASSES:
            try:
                tok = self._get_token()
                if not tok:
                    continue
                
                r = self._api_vlist(cls, 0)
                body = self._parse_json(r)
                if body is None:
                    continue
                
                items = self._collect_items(body)
                for item in items:
                    if key.lower() in item["vod_name"].lower():
                        results.append({
                            "vod_id": item["vod_id"],
                            "vod_name": item["vod_name"],
                            "vod_pic": item.get("vod_pic", ""),
                            "vod_remarks": item.get("vod_remarks", "")
                        })
            except:
                continue
            
            if len(results) >= 30:
                break
        
        return {"list": results[:30]}

    def playerContent(self, flag, id, vipFlags):
        """播放器内容"""
        if id.startswith(("http://", "https://")):
            return {
                "parse": 0,
                "playUrl": "",
                "url": id,
                "header": {
                    "User-Agent": self._ua(),
                    "Referer": self._get_base_url()
                }
            }
        
        try:
            detail = self.detailContent([id])
            if detail.get("list"):
                play_url = detail["list"][0].get("vod_play_url", "")
                if play_url:
                    parts = play_url.split("#")
                    if parts:
                        first = parts[0]
                        if "$" in first:
                            url = first.split("$")[-1]
                        else:
                            url = first
                        if url.startswith(("http://", "https://")):
                            return {
                                "parse": 0,
                                "playUrl": "",
                                "url": url,
                                "header": {
                                    "User-Agent": self._ua(),
                                    "Referer": self._get_base_url()
                                }
                            }
        except:
            pass
        
        return {
            "parse": 0,
            "playUrl": "",
            "url": "",
            "header": {}
        }

    def localProxy(self, param):
        pass

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
