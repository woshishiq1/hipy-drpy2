# -*- coding: utf-8 -*-
#下载页：https://ldk520.vip
#SEO 站点：https://luolidaoapp.cc
#TG 群：https://t.me/luolidao111
import sys, re, json, urllib.parse, os, time
sys.path.append('..')
try:
    from base.spider import Spider as _B
except ImportError:
    class _B: pass
try:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
except ImportError:
    requests = None

U = "Mozilla/5.0 (Linux; Android 12; TFY-AN00 Build/HONORTFY-AN00; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/92.0.4515.105 Mobile Safari/537.36 uni-app Html5Plus/1.0 (Immersed/33.0)"
DOMAIN_API = "https://lwncnss3api.cc/api/getapi.php"
CACHE_FILE = "domain_cache.json"
CACHE_EXPIRE = 3600  # 缓存有效期1小时

# 硬编码的备用域名列表
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

class Spider(_B):
    def init(self, e=""):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": U, 
            "Accept-Encoding": "gzip",
            "Content-Type": "application/x-www-form-urlencoded"
        })
        # 忽略SSL验证
        self.s.verify = False
        self.token = ""
        self.domains = []
        self.working_domains = []  # 可工作的域名缓存
        self._load_domains()
        # 如果获取到的域名少于3个，补充备用域名
        if len(self.domains) < 3:
            self.domains.extend(BACKUP_DOMAINS)
            self.domains = list(set(self.domains))  # 去重
        self._register()

    def getName(self):
        return "萝莉岛"

    def isVideoFormat(self, u):
        return ".m3u8" in u or ".mp4" in u or "preview" in u

    def manualVideoCheck(self):
        return False

    def _get_cache_path(self):
        """获取缓存文件路径"""
        return os.path.join(os.path.dirname(__file__), CACHE_FILE)

    def _load_domains(self):
        """加载域名列表（优先从缓存读取）- 不过滤黑名单"""
        cache_path = self._get_cache_path()
        
        # 尝试从缓存读取
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    cache_time = cache_data.get('cache_time', 0)
                    # 检查缓存是否过期
                    if time.time() - cache_time < CACHE_EXPIRE:
                        domains = cache_data.get('domains', [])
                        # 不过滤黑名单，直接使用所有域名
                        self.domains = [d for d in domains if d and isinstance(d, str) and '.' in d]
                        if self.domains:
                            print(f'[DOMAIN] Loaded {len(self.domains)} domains from cache (no blacklist filter)')
                            return
            except Exception as e:
                print(f'[CACHE] Read cache failed: {e}')
        
        # 缓存失效或不存在，从API获取
        self._fetch_domains()

    def _fetch_domains(self):
        """从API获取域名列表并缓存 - 不过滤黑名单，全部轮询"""
        try:
            # 使用单独的requests，忽略SSL
            r = requests.get(DOMAIN_API, timeout=10, verify=False)
            
            # 尝试解析JSON
            try:
                data = r.json()
            except:
                # 如果JSON解析失败，尝试用正则提取域名
                domains = re.findall(r'[\w\-\.]+\.(?:com|cc|net|org|site|top|xyz)', r.text)
                if domains:
                    self.domains = list(set(domains))
                    print(f'[DOMAIN] Extracted {len(self.domains)} domains from response')
                    self._save_cache(self.domains, [])
                    return
            
            if data.get('code') == 200:
                domains = data.get('data', [])
                blacklist = data.get('blackdomain', [])
                
                # 如果data字段是字符串而不是列表，尝试解析
                if isinstance(domains, str):
                    try:
                        domains = json.loads(domains)
                    except:
                        domains = [domains]
                
                # 确保是列表
                if not isinstance(domains, list):
                    domains = [str(domains)] if domains else []
                
                # 不过滤黑名单，合并所有域名（data + blacklist）
                all_domains = list(set(domains + blacklist))  # 合并并去重
                # 过滤掉空字符串和无效格式
                self.domains = [d for d in all_domains if d and isinstance(d, str) and '.' in d]
                
                # 把 data 里的域名（通常更可靠）放在前面
                priority_domains = [d for d in domains if d and '.' in d]
                other_domains = [d for d in self.domains if d not in priority_domains]
                self.domains = priority_domains + other_domains
                
                if self.domains:
                    print(f'[DOMAIN] Fetched {len(self.domains)} domains from API (no blacklist filter)')
                    print(f'[DOMAIN] Priority domains: {priority_domains[:5]}...')
                    self._save_cache(all_domains, [])
                else:
                    print('[DOMAIN] No valid domains from API, using backup')
                    self.domains = BACKUP_DOMAINS.copy()
            else:
                print(f'[DOMAIN] API returned: {data}')
                self.domains = BACKUP_DOMAINS.copy()
                # 尝试保存备份域名到缓存
                self._save_cache(self.domains, [])
        except Exception as e:
            print(f'[DOMAIN] Fetch failed: {e}')
            self.domains = BACKUP_DOMAINS.copy()
            # 尝试保存备份域名到缓存
            self._save_cache(self.domains, [])

    def _save_cache(self, domains, blacklist):
        """保存缓存"""
        try:
            cache_data = {
                'domains': domains,
                'blacklist': blacklist,
                'cache_time': time.time()
            }
            cache_path = self._get_cache_path()
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f'[CACHE] Save failed: {e}')

    def _fallback_cache(self):
        """降级使用缓存（即使过期）- 不过滤黑名单"""
        cache_path = self._get_cache_path()
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    domains = cache_data.get('domains', [])
                    # 不过滤黑名单，直接使用
                    self.domains = [d for d in domains if d and isinstance(d, str) and '.' in d]
                    if self.domains:
                        print(f'[DOMAIN] Using fallback cache with {len(self.domains)} domains')
                        return
            except Exception as e:
                print(f'[DOMAIN] Fallback cache failed: {e}')
        
        # 如果还是没有域名，使用备用域名
        if not self.domains:
            self.domains = BACKUP_DOMAINS.copy()
            print('[DOMAIN] Using backup domains')

    def _find_working_domain(self):
        """找到一个可工作的域名"""
        # 先尝试之前找到的工作域名
        if self.working_domains:
            for domain in self.working_domains[:]:
                if self._test_domain(domain):
                    return domain
                else:
                    self.working_domains.remove(domain)
        
        # 尝试所有域名
        for domain in self.domains:
            if self._test_domain(domain):
                self.working_domains.append(domain)
                print(f'[DOMAIN] Found working domain: {domain}')
                return domain
        
        print('[DOMAIN] No working domain found')
        return None

    def _test_domain(self, domain):
        """测试域名是否可用"""
        # 优先尝试HTTPS，失败则尝试HTTP
        for protocol in ['https', 'http']:
            url = f"{protocol}://{domain}/api/setapp.php"
            try:
                r = self.s.get(url, timeout=5, verify=False)
                if r.status_code == 200:
                    return True
            except:
                continue
        return False

    def _request_api(self, path, method='post', data=None, params=None):
        """通用API请求方法，自动轮询域名"""
        # 先尝试找到工作域名
        domain = self._find_working_domain()
        if not domain:
            # 如果没有工作域名，刷新域名列表
            self._fetch_domains()
            domain = self._find_working_domain()
            if not domain:
                print(f'[REQUEST] No available domain for {path}')
                return None
        
        # 尝试HTTPS和HTTP
        for protocol in ['https', 'http']:
            url = f"{protocol}://{domain}{path}"
            try:
                if method.lower() == 'get':
                    r = self.s.get(url, params=params, timeout=10, verify=False)
                else:
                    r = self.s.post(url, data=data, params=params, timeout=10, verify=False)
                
                if r.status_code == 200:
                    return r
                else:
                    print(f'[REQUEST] {url} returned {r.status_code}')
            except Exception as e:
                print(f'[REQUEST] {url} failed: {e}')
                continue
        
        # 如果当前域名失败，从工作域名列表中移除并重试
        if domain in self.working_domains:
            self.working_domains.remove(domain)
        return self._request_api(path, method, data, params)

    def _register(self):
        """注册/获取设备的交互 Token"""
        try:
            r = self._request_api('/api/newreg.php', 'post', 
                data={"device": "android", "ntoken": "", "channel_code": "vbtQg9D8"}
            )
            if r:
                data = r.json()
                self.token = data.get("user", {}).get("token", "")
                if self.token:
                    print(f'[REGISTER] Success, token: {self.token[:20]}...')
                else:
                    print('[REGISTER] No token in response')
            else:
                print('[REGISTER] Request failed')
        except Exception as e:
            print('[REGISTER]', e)

    def homeContent(self, filter=False):
        """获取主分类及其对应的筛选条件"""
        try:
            r = self._request_api('/api/setapp.php', 'get')
            if r:
                data = r.json()
                classes = []
                filters = {}
                
                tabs = data.get("vodtab", []) + data.get("vodtaban", [])
                for tab in tabs:
                    tid = tab.get("type_id")
                    classes.append({
                        "type_id": tid,
                        "type_name": tab.get("type_name")
                    })
                    tags = tab.get("vodtags", [])
                    if tags:
                        tag_values = [{"n": "全部", "v": ""}]
                        for tag in tags:
                            tag_values.append({"n": tag.get("name"), "v": tag.get("name")})
                        filters[tid] = [{"key": "class", "name": "标签", "value": tag_values}]
                
                return {"class": classes, "filters": filters if filter else {}}
            
            return {"class": [], "filters": {}}
        except Exception as e:
            print('[HOME]', e)
            return {"class": [], "filters": {}}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        """获取分类子列表"""
        if not extend: extend = {}
        num = (int(pg) - 1) * 30
        payload = {
            "num": str(num),
            "pid": str(tid),
            "area": "全部",
            "vodclass": extend.get("class", ""),
            "vodyear": "全部",
            "sort": "1",
            "token": self.token
        }
        
        try:
            r = self._request_api('/api/vlist.php', 'post', data=payload)
            if r:
                data = r.json()
                videos = []
                for item in data.get("list", []):
                    videos.append({
                        "vod_id": str(item.get("vod_id", "")),
                        "vod_name": item.get("vod_name", ""),
                        "vod_pic": item.get("vod_pic", ""),
                        "vod_remarks": item.get("vod_class", "") or item.get("vod_remarks", "")
                    })
                return {"list": videos, "page": pg}
        except Exception as e:
            print('[CATEGORY]', e)
        
        return {"list": []}

    def detailContent(self, ids):
        """获取视频详情及播放链接"""
        payload = {
            "id": str(ids[0]),
            "token": self.token,
            "channel": ""
        }
        
        try:
            r = self._request_api('/api/Get_vod_list.php', 'post', data=payload)
            if r:
                data = r.json().get("data", {})
                
                play_url = data.get("vod_play_url", "")
                if not play_url:
                    play_url = "预览$" + data.get("preview_url", "")

                video = {
                    "vod_id": str(data.get("vod_id", ids[0])),
                    "vod_name": data.get("vod_name", ""),
                    "vod_pic": data.get("vod_pic", ""),
                    "vod_remarks": data.get("vod_remarks", ""),
                    "vod_content": data.get("vod_blurb", "暂无简介"),
                    "vod_play_from": "萝莉岛",
                    "vod_play_url": play_url
                }
                return {"list": [video]}
        except Exception as e:
            print('[DETAIL]', e)
        
        return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        """播放器直连"""
        return {
            "parse": 0,
            "url": id,
            "header": json.dumps({"User-Agent": U})
        }

    def searchContent(self, key, quick=False, pg=1):
        """搜索功能"""
        return {"list": []}

    def localProxy(self, param):
        pass