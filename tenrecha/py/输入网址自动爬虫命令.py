#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 AI智能爬虫终极版 v5.1 - 可直接输入网址运行
功能：网络智能诊断 | VPN自动切换 | 夸克式磁力嗅探 | 微型DeepSeek AI | 全格式保存
修改：支持直接输入网址、重构夸克为磁力嗅探器、修复语法错误
"""
import re
import html
import sys
import base64
import json
import urllib.parse
import sqlite3
import hashlib
import random
import time
import threading
import socket
import subprocess
import os
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty, PriorityQueue
from datetime import datetime
import requests
import warnings
warnings.filterwarnings('ignore')

# ============ 可选依赖 ============
try:
    import execjs
    JS_AVAILABLE = True
except ImportError:
    JS_AVAILABLE = False
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
try:
    from pyquery import PyQuery as pq
    PYQUERY_AVAILABLE = True
except ImportError:
    PYQUERY_AVAILABLE = False

# ============ 微型DeepSeek AI引擎 ============
class MicroDeepSeek:
    """微型DeepSeek AI - 本地决策引擎"""
    def __init__(self):
        self.memory = []  # 记忆库
        self.rules = self._load_rules()
        self.confidence_threshold = 0.7

    def _load_rules(self) -> Dict:
        """加载决策规则库"""
        return {
            'network': {
                'timeout_patterns': ['Connection timed out', 'No route to host', 'Network is unreachable'],
                'block_patterns': ['403 Forbidden', '429 Too Many Requests', 'Access Denied', 'Cloudflare'],
                'success_patterns': ['200 OK', 'Content-Type: text/html'],
            },
            'content': {
                'video_indicators': ['.m3u8', 'magnet:', 'torrent', 'mp4', 'video'],
                'ad_indicators': ['ad.js', 'popup', 'redirect', 'click'],
                'protection_indicators': ['captcha', 'verify', 'challenge', 'bot']
            },
            'strategy': {
                'proxy_triggers': ['block', 'timeout', '403', '429'],
                'vpn_triggers': ['Great Firewall', 'DNS poisoning', 'TCP reset'],
                'headless_triggers': ['heavy_js', 'dynamic_load', 'react', 'vue']
            }
        }

    def decide(self, context: Dict) -> Dict:
        """AI决策核心"""
        decision = {
            'action': 'continue',
            'confidence': 0.0,
            'reasoning': [],
            'suggestions': []
        }
        if context.get('last_error'):
            error = context['last_error']
            confidence = 0.0
            if any(p in error for p in self.rules['network']['block_patterns']):
                decision['action'] = 'switch_proxy'
                confidence = 0.85
                decision['reasoning'].append(f"检测到拦截: {error[:50]}")
            elif any(p in error for p in self.rules['strategy']['vpn_triggers']):
                decision['action'] = 'enable_vpn'
                confidence = 0.90
                decision['reasoning'].append("检测到网络封锁，建议启用VPN")
            elif 'captcha' in error.lower():
                decision['action'] = 'solve_captcha'
                confidence = 0.80
                decision['reasoning'].append("检测到验证码挑战")
            decision['confidence'] = confidence
        if context.get('content_type') == 'video_page':
            indicators = sum(1 for ind in self.rules['content']['video_indicators']
                           if ind in context.get('html', ''))
            if indicators >= 3:
                decision['suggestions'].append('high_value_target')
                decision['confidence'] = max(decision['confidence'], 0.75)
        self.memory.append({
            'timestamp': time.time(),
            'context': context,
            'decision': decision
        })
        return decision

    def learn(self, result: bool, context: Dict):
        """强化学习"""
        if self.memory:
            last = self.memory[-1]
            if result:
                last['reward'] = 1.0
            else:
                last['reward'] = -0.5
                self.confidence_threshold = min(0.95, self.confidence_threshold + 0.05)

    def predict_url_value(self, url: str, features: Dict) -> float:
        """预测URL价值分数 (0-1)"""
        score = 0.5
        if re.search(r'/(video|watch|play|movie|episode)/\d+', url):
            score += 0.3
        if '.m3u8' in url or 'magnet' in url:
            score += 0.4
        if features.get('has_video_tag', False):
            score += 0.2
        similar = [m for m in self.memory if m['context'].get('url', '').rsplit('/', 1)[0] in url]
        if similar:
            avg_reward = sum(s.get('reward', 0) for s in similar) / len(similar)
            score += avg_reward * 0.2
        return min(1.0, max(0.0, score))

# ============ 网络智能诊断器 ============
class NetworkDiagnoser:
    """网络智能诊断 - 自动检测连接状态"""
    def __init__(self):
        self.test_urls = [
            'http://www.baidu.com',
            'http://www.google.com',
            'https://www.cloudflare.com',
            'https://www.github.com'
        ]
        self.vpn_interfaces = ['tun0', 'tun1', 'ppp0', 'wg0', 'utun']  # 常见VPN接口
        self.last_diagnosis = None

    def diagnose(self) -> Dict:
        """全面网络诊断"""
        result = {
            'timestamp': time.time(),
            'internet_access': False,
            'dns_working': False,
            'vpn_active': False,
            'vpn_type': None,
            'latency': {},
            'recommendation': 'normal'
        }
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            result['internet_access'] = True
        except:
            pass
        try:
            socket.gethostbyname('www.google.com')
            result['dns_working'] = True
        except:
            pass
        result['vpn_active'], result['vpn_type'] = self._detect_vpn()
        for url in self.test_urls:
            result['latency'][url] = self._test_latency(url)
        if not result['internet_access']:
            result['recommendation'] = 'check_network'
        elif not result['dns_working'] and not result['vpn_active']:
            result['recommendation'] = 'enable_vpn'
        elif result['latency'].get('http://www.google.com', 999) > 500:
            result['recommendation'] = 'use_proxy'
        self.last_diagnosis = result
        return result

    def _detect_vpn(self) -> Tuple[bool, Optional[str]]:
        """检测VPN状态"""
        try:
            if os.path.exists('/proc/net/dev'):
                with open('/proc/net/dev', 'r') as f:
                    interfaces = f.read()
                    for iface in self.vpn_interfaces:
                        if iface in interfaces:
                            return True, iface
            result = subprocess.run(['ip', 'route'], capture_output=True, text=True)
            if 'tun' in result.stdout or 'ppp' in result.stdout:
                return True, 'unknown'
            if os.path.exists('/data/data/com.termux/files/usr/bin/proxy'):
                return True, 'termux_proxy'
        except:
            pass
        return False, None

    def _test_latency(self, url: str) -> float:
        """测试延迟"""
        try:
            start = time.time()
            requests.get(url, timeout=5, verify=False)
            return (time.time() - start) * 1000
        except:
            return 9999

    def auto_fix(self, target_url: str) -> bool:
        """自动修复网络问题"""
        diagnosis = self.diagnose()
        if diagnosis['recommendation'] == 'enable_vpn':
            print("🔍 AI诊断: 检测到网络限制，尝试启用VPN...")
            return self._enable_vpn()
        elif diagnosis['recommendation'] == 'use_proxy':
            print("🔍 AI诊断: 连接缓慢，建议使用代理...")
            return self._find_working_proxy(target_url)
        return diagnosis['internet_access']

    def _enable_vpn(self) -> bool:
        """尝试启用VPN"""
        try:
            vpn_apps = [
                'com.github.shadowsocks',
                'com.v2ray.ang',
                'io.nekohasekai.sagernet',
                'com.wireguard.android'
            ]
            for app in vpn_apps:
                result = subprocess.run(
                    ['am', 'start', '-n', f'{app}/.MainActivity'],
                    capture_output=True
                )
                if result.returncode == 0:
                    print(f"✅ 已启动VPN应用: {app}")
                    time.sleep(3)
                    return True
        except:
            pass
        print("⚠️ 请手动启用VPN后按回车继续...")
        input()
        return True

    def _find_working_proxy(self, target_url: str) -> bool:
        """寻找可用代理"""
        proxy_pool = [
            'http://127.0.0.1:7890',  # Clash默认
            'http://127.0.0.1:10809', # V2RayN默认
            'http://127.0.0.1:1080',  # SS默认
            'socks5://127.0.0.1:7890',
            'socks5://127.0.0.1:10808',
        ]
        for proxy in proxy_pool:
            try:
                test_session = requests.Session()
                test_session.proxies = {'http': proxy, 'https': proxy}
                test_session.get(target_url, timeout=5, verify=False)
                print(f"✅ 找到可用代理: {proxy}")
                return True
            except:
                continue
        return False

# ============ 夸克式磁力嗅探器（核心修改） ============
class QuarkMagnetSniffer:
    """夸克浏览器式磁力嗅探器 - 实时检测/提取/解析页面磁力链接"""
    def __init__(self):
        self.session = requests.Session()
        # 模拟夸克浏览器UA
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36 Quark/6.9.0.243',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Cache-Control': 'no-cache'
        })

    def sniff_magnet(self, page_html: str, page_url: str) -> List[Dict]:
        """
        夸克式嗅探核心：从页面HTML/JS中提取磁力链接
        :param page_html: 页面源码
        :param page_url: 页面URL（用于补全相对链接）
        :return: 解析后的磁力链接列表（含hash/文件名/大小）
        """
        magnets = []
        # 夸克级正则：匹配所有磁力链接格式（兼容btih/xt=urn等）
        magnet_pattern = r'magnet:\?xt=urn:(btih|ed2k):[a-fA-F0-9]{32,40}([&?][^"\'<>\s]*)?'
        for match in re.finditer(magnet_pattern, page_html, re.I):
            magnet_url = match.group(0).strip()
            magnet_hash = self._extract_magnet_hash(magnet_url)
            # 解析磁力链接参数（dn=文件名、xl=大小等）
            magnet_params = self._parse_magnet_params(magnet_url)
            magnets.append({
                'url': magnet_url,
                'hash': magnet_hash.upper(),
                'filename': magnet_params.get('dn', f'未知文件_{magnet_hash[:8].upper()}'),
                'size': self._format_size(magnet_params.get('xl', 0)),
                'source_page': page_url,
                'sniff_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        # 去重：根据hash去重
        magnets = self._deduplicate_magnets(magnets)
        return magnets

    def _extract_magnet_hash(self, magnet_url: str) -> str:
        """提取磁力链接核心HASH"""
        btih_match = re.search(r'btih:([a-fA-F0-9]{32,40})', magnet_url, re.I)
        if btih_match:
            return btih_match.group(1)
        ed2k_match = re.search(r'ed2k:([a-fA-F0-9]{32})', magnet_url, re.I)
        return ed2k_match.group(1) if ed2k_match else ""

    def _parse_magnet_params(self, magnet_url: str) -> Dict:
        """解析磁力链接的参数（dn=文件名，xl=文件大小）"""
        params = {}
        try:
            query_part = magnet_url.split('?', 1)[1]
            for param in query_part.split('&'):
                if '=' in param:
                    k, v = param.split('=', 1)
                    params[k] = urllib.parse.unquote(v)
        except:
            pass
        return params

    def _format_size(self, size: str or int) -> str:
        """格式化文件大小（B/KB/MB/GB）"""
        try:
            size = int(size)
            units = ['B', 'KB', 'MB', 'GB', 'TB']
            idx = 0
            while size >= 1024 and idx < len(units)-1:
                size /= 1024
                idx += 1
            return f"{size:.2f} {units[idx]}"
        except:
            return "未知大小"

    def _deduplicate_magnets(self, magnets: List[Dict]) -> List[Dict]:
        """根据HASH去重磁力链接"""
        hash_set = set()
        unique_magnets = []
        for mag in magnets:
            if mag['hash'] and mag['hash'] not in hash_set:
                hash_set.add(mag['hash'])
                unique_magnets.append(mag)
        return unique_magnets

# ============ 智能请求管理器 ============
class SmartRequester:
    """智能请求管理器 - 集成AI决策"""
    def __init__(self, ai: MicroDeepSeek, network: NetworkDiagnoser):
        self.session = requests.Session()
        self.ai = ai
        self.network = network
        self.proxy_pool = []
        self.current_proxy = None
        self.vpn_enabled = False
        self.failed_count = 0
        self.success_patterns = []
        self._init_identity()

    def _init_identity(self):
        """初始化身份"""
        self.rotate_identity()

    def rotate_identity(self):
        """轮换身份"""
        uas = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Quark/6.8.0 Mobile",
            "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36 Quark/6.9.0.243"
        ]
        self.session.headers.update({
            'User-Agent': random.choice(uas),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': random.choice(['zh-CN,zh;q=0.9', 'en-US,en;q=0.9', 'ja-JP,ja;q=0.9']),
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

    def smart_get(self, url: str, **kwargs) -> Optional[requests.Response]:
        """智能GET - AI决策驱动"""
        context = {
            'url': url,
            'last_error': None,
            'retry_count': 0,
            'use_proxy': self.current_proxy is not None,
            'vpn_active': self.vpn_enabled
        }
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if context['last_error']:
                    decision = self.ai.decide(context)
                    if decision['action'] == 'switch_proxy':
                        self._switch_proxy()
                    elif decision['action'] == 'enable_vpn':
                        self.vpn_enabled = self.network.auto_fix(url)
                    elif decision['action'] == 'rotate_identity':
                        self.rotate_identity()
                proxies = {'http': self.current_proxy, 'https': self.current_proxy} if self.current_proxy else None
                delay = random.uniform(1, 3) + (self.failed_count * 0.5)
                time.sleep(delay)
                resp = self.session.get(
                    url,
                    timeout=kwargs.get('timeout', 20),
                    proxies=proxies,
                    allow_redirects=True,
                    verify=False,
                    **kwargs
                )
                if self._is_blocked(resp):
                    raise requests.exceptions.RequestException("Blocked by protection")
                self.failed_count = 0
                self.ai.learn(True, context)
                return resp
            except Exception as e:
                context['last_error'] = str(e)
                context['retry_count'] += 1
                self.failed_count += 1
                if attempt == max_retries - 1:
                    self.ai.learn(False, context)
                    return None
                time.sleep(2 ** attempt)
        return None

    def _is_blocked(self, resp: requests.Response) -> bool:
        """检测是否被拦截"""
        indicators = [b'cloudflare', b'captcha', b'blocked', b'access denied', b'403', b'429']
        content = resp.content.lower()
        return any(ind in content for ind in indicators) or resp.status_code in [403, 429, 503]

    def _switch_proxy(self):
        """切换代理"""
        if self.proxy_pool:
            self.current_proxy = random.choice(self.proxy_pool)
            print(f"🔄 切换到代理: {self.current_proxy}")

# ============ 终极JS解包器 ============
class UltimateJSPacker:
    """终极JS解包器"""
    def __init__(self):
        self.stats = {
            'hex': 0, 'unicode': 0, 'base64': 0, 'eval': 0,
            'reverse': 0, 'concat': 0, 'aa': 0, 'jsfuck': 0
        }
        self.cache = {}

    def unpack(self, code: str, depth: int = 0) -> str:
        if depth >= 20:
            return code
        code_hash = hashlib.md5(code[:1000].encode()).hexdigest()
        if code_hash in self.cache:
            return self.cache[code_hash]
        original = code
        code = self._decode_hex(code)
        code = self._decode_unicode(code)
        code = self._decode_base64(code)
        code = self._resolve_concat(code)
        code = self._resolve_reverse(code)
        code = self._execute_eval(code)
        if code != original:
            self.cache[code_hash] = code
            return self.unpack(code, depth + 1)
        self.cache[code_hash] = code
        return code

    def _decode_hex(self, code: str) -> str:
        def replace(m):
            try:
                return bytes.fromhex(m.group(0).replace('\\x', '')).decode('utf-8')
            except:
                return m.group(0)
        return re.sub(r'\\x[0-9a-fA-F]{2}', replace, code)

    def _decode_unicode(self, code: str) -> str:
        def replace(m):
            try:
                return chr(int(m.group(0)[2:], 16))
            except:
                return m.group(0)
        return re.sub(r'\\u[0-9a-fA-F]{4}', replace, code)

    def _decode_base64(self, code: str) -> str:
        pattern = r'atob\s*\(\s*["\']([A-Za-z0-9+/=]{20,})["\']'
        def replace(m):
            try:
                return base64.b64decode(m.group(1)).decode('utf-8')
            except:
                return m.group(0)
        return re.sub(pattern, replace, code, flags=re.I)

    def _resolve_concat(self, code: str) -> str:
        pattern = r'(["\'][^"\']*["\'])\s*\+\s*(["\'][^"\']*["\'])'
        def replace(m):
            return f'"{m.group(1).strip("\"\'") + m.group(2).strip("\"\'")}"'
        prev = None
        while prev != code:
            prev = code
            code = re.sub(pattern, replace, code)
        return code

    def _resolve_reverse(self, code: str) -> str:
        pattern = r'["\']([^"\']+)["\']\.split\([^)]*\)\.reverse\(\)\.join\([^)]*\)'
        return re.sub(pattern, lambda m: f'"{m.group(1)[::-1]}"', code)

    def _execute_eval(self, code: str) -> str:
        if not JS_AVAILABLE:
            return code
        pattern = r'eval\s*\(\s*["\'](.+?)["\']\s*\)'
        def replace(m):
            try:
                return execjs.eval(m.group(1))
            except:
                return m.group(0)
        return re.sub(pattern, replace, code, flags=re.DOTALL)

# ============ 资源提取器 ============
class ResourceExtractor:
    """资源提取器 - M3U8/磁力/视频"""
    @staticmethod
    def extract_m3u8(code: str, base_url: str) -> Set[str]:
        urls = set()
        patterns = [
            r'https?://[^\s"\'<>|\\]+[^\\s"\'<>|\\]*\.m3u8[^\s"\'<>|]*',
            r'["\'](/[^"\']*\.m3u8[^"\']*)["\']',
            r'url\s*[:=]\s*["\']([^"\']*\.m3u8[^"\']*)["\']'
        ]
        for p in patterns:
            for m in re.findall(p, code, re.I):
                url = m.strip('"\'')
                if url.startswith('/'):
                    url = urljoin(base_url, url)
                if url.startswith('http'):
                    urls.add(url)
        return urls

# ============ AI智能爬虫核心 ============
class AICrawler:
    """AI智能爬虫核心"""
    def __init__(self, start_url: str):
        self.start_url = start_url
        self.domain = urlparse(start_url).netloc
        self.ai = MicroDeepSeek()
        self.network = NetworkDiagnoser()
        self.requester = SmartRequester(self.ai, self.network)
        self.packer = UltimateJSPacker()
        self.magnet_sniffer = QuarkMagnetSniffer()  # 替换为夸克磁力嗅探器

        # 数据存储
        self.data = {
            'm3u8': set(),
            'magnets': [],  # 存储夸克嗅探的磁力链接
            'videos': [],
            'pages': set()
        }

        # 队列
        self.url_queue = PriorityQueue()
        self.url_queue.put((1.0, start_url, 'page'))

        # 线程控制
        self.lock = threading.Lock()
        self.running = True
        self.stats = {'fetched': 0, 'failed': 0}

    def crawl(self, max_items: int = 50):
        """主爬取循环"""
        print(f"🚀 AI爬虫启动: {self.start_url}")
        print(f"🧠 AI决策引擎就绪 | 🌐 网络诊断就绪 | 🧲 夸克磁力嗅探就绪")
        print(f"📌 爬取上限: {max_items} 个视频资源\n")

        workers = []
        for _ in range(3):
            t = threading.Thread(target=self._worker)
            t.start()
            workers.append(t)

        try:
            while self.running and len(self.data['videos']) < max_items:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⛔ 用户手动中断爬取")
            self.running = False

        for w in workers:
            w.join()

        # 最终保存所有数据
        self._auto_save()
        print(f"\n✅ 爬取完成！统计：成功{self.stats['fetched']} | 失败{self.stats['failed']}")
        print(f"📁 结果已保存至 /data/data/com.termux/files/home/py_lib/output 目录")
        return self.data

    def _worker(self):
        """工作线程"""
        while self.running:
            try:
                priority, url, url_type = self.url_queue.get(timeout=5)
            except Empty:
                continue
            try:
                if url_type == 'page':
                    self._process_page(url)
                else:
                    self._process_video(url)
            except Exception as e:
                with self.lock:
                    self.stats['failed'] += 1
            finally:
                self.url_queue.task_done()

    def _process_page(self, url: str):
        """处理列表页"""
        if url in self.data['pages']:
            return
        with self.lock:
            self.data['pages'].add(url)
        resp = self.requester.smart_get(url)
        if not resp:
            return
        html = resp.text
        self.stats['fetched'] += 1

        # AI分析页面价值
        features = {
            'has_video_tag': '<video' in html or '.m3u8' in html,
            'has_magnet': 'magnet:' in html,
            'link_count': html.count('<a ')
        }
        self.ai.predict_url_value(url, features)

        # 提取视频链接
        if PYQUERY_AVAILABLE:
            doc = pq(html)
            for a in doc('a[href*=".html"]').items():
                href = a.attr('href')
                if href and re.search(r'/\d+\.html$', href):
                    video_url = urljoin(url, href)
                    score = self.ai.predict_url_value(video_url, {})
                    self.url_queue.put((1 - score, video_url, 'video'))
        else:
            for m in re.finditer(r'href=["\']([^"\']+\.html)["\']', html):
                video_url = urljoin(url, m.group(1))
                self.url_queue.put((0.5, video_url, 'video'))

        # 提取JS并解包，提取M3U8
        js_urls = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html)
        for js_url in js_urls:
            full_js = urljoin(url, js_url)
            try:
                js_resp = self.requester.smart_get(full_js)
                if js_resp:
                    unpacked = self.packer.unpack(js_resp.text)
                    m3u8s = ResourceExtractor.extract_m3u8(unpacked, url)
                    with self.lock:
                        self.data['m3u8'].update(m3u8s)
            except:
                pass

    def _process_video(self, url: str):
        """处理视频页 - 集成夸克磁力嗅探"""
        resp = self.requester.smart_get(url)
        if not resp:
            return
        html = resp.text
        # 1. JS解包+提取M3U8
        unpacked_html = self.packer.unpack(html)
        m3u8s = ResourceExtractor.extract_m3u8(unpacked_html, url)
        # 2. 夸克式磁力嗅探（核心）
        sniffed_magnets = self.magnet_sniffer.sniff_magnet(unpacked_html, url)
        # 3. 提取标题
        title = self._extract_title(html)

        # 加锁更新数据
        with self.lock:
            self.data['m3u8'].update(m3u8s)
            self.data['magnets'].extend(sniffed_magnets)
            self.data['videos'].append({
                'url': url,
                'title': title,
                'magnets': len(sniffed_magnets),
                'm3u8': len(m3u8s),
                'crawl_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        # 打印爬取结果
        print(f"🎬 {title[:40]:<40} | 磁力:{len(sniffed_magnets):<2} | M3U8:{len(m3u8s):<2}")

    def _extract_title(self, html: str) -> str:
        """提取标题"""
        if PYQUERY_AVAILABLE:
            title = pq(html)('h1').text() or pq(html)('title').text()
            if title:
                return title.split('-')[0].strip()
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html, re.I)
        if m:
            return m.group(1).strip()
        m = re.search(r'<title>([^<]+)</title>', html, re.I)
        if m:
            return m.group(1).split('-')[0].strip()
        return "Unknown Title"

    def _auto_save(self):
        """自动保存"""
        saver = MultiSaver('/data/data/com.termux/files/home/py_lib/output')
        saver.save(self.data, self.start_url)

# ============ 多格式保存器（修复截断代码） ============
class MultiSaver:
    """多格式保存器 - 修复原代码截断问题"""
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    def save(self, data: Dict, source: str):
        """保存所有格式：TXT/JSON/SQLite/M3U"""
        self._save_txt(data, source)
        self._save_json(data, source)
        self._save_db(data, source)
        self._save_m3u(data, source)

    def _save_txt(self, data, source):
        """保存为TXT（易读）"""
        path = f"{self.output_dir}/crawl_magnet_{self.ts}.txt"
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"========== AI爬虫结果 ==========\n")
            f.write(f"爬取源地址: {source}\n")
            f.write(f"爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"视频页面数: {len(data['videos'])}\n")
            f.write(f"M3U8链接数: {len(data['m3u8'])}\n")
            f.write(f"磁力链接数: {len(data['magnets'])}\n\n")

            f.write(f"========== M3U8链接 ==========\n")
            for idx, url in enumerate(sorted(data['m3u8']), 1):
                f.write(f"{idx}. {url}\n")

            f.write(f"\n========== 磁力链接（夸克嗅探） ==========\n")
            for idx, mag in enumerate(data['magnets'], 1):
                f.write(f"{idx}. 文件名: {mag['filename']}\n")
                f.write(f"   HASH: {mag['hash']}\n")
                f.write(f"   大小: {mag['size']}\n")
                f.write(f"   链接: {mag['url']}\n")
                f.write(f"   来源: {mag['source_page']}\n\n")

    def _save_json(self, data, source):
        """保存为JSON（易解析）"""
        path = f"{self.output_dir}/crawl_magnet_{self.ts}.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                'meta': {
                    'source': source,
                    'crawl_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'video_count': len(data['videos']),
                    'm3u8_count': len(data['m3u8']),
                    'magnet_count': len(data['magnets'])
                },
                'data': {
                    'm3u8': list(data['m3u8']),
                    'magnets': data['magnets'],
                    'videos': data['videos']
                }
            }, f, ensure_ascii=False, indent=2)

    def _save_db(self, data, source):
        """保存为SQLite（持久化）"""
        path = f"{self.output_dir}/crawl_magnet_{self.ts}.db"
        conn = sqlite3.connect(path)
        c = conn.cursor()
        # 创建表
        c.execute('''CREATE TABLE IF NOT EXISTS magnets
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      url TEXT UNIQUE,
                      hash TEXT,
                      filename TEXT,
                      size TEXT,
                      source_page TEXT,
                      sniff_time TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS m3u8
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT UNIQUE)''')
        # 插入数据
        for mag in data['magnets']:
            try:
                c.execute('INSERT OR IGNORE INTO magnets (url, hash, filename, size, source_page, sniff_time) VALUES (?, ?, ?, ?, ?, ?)',
                          (mag['url'], mag['hash'], mag['filename'], mag['size'], mag['source_page'], mag['sniff_time']))
            except:
                pass
        for m3u8 in data['m3u8']:
            try:
                c.execute('INSERT OR IGNORE INTO m3u8 (url) VALUES (?)', (m3u8,))
            except:
                pass
        conn.commit()
        conn.close()

    def _save_m3u(self, data, source):
        """保存为M3U（播放器直接播放）"""
        path = f"{self.output_dir}/crawl_m3u8_{self.ts}.m3u"
        with open(path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for url in sorted(data['m3u8']):
                f.write(f"#EXTINF:-1,{url.split('/')[-1]}\n{url}\n")

# ============ 主入口（核心：直接输入网址运行） ============
def main():
    print("=====================================")
    print("     AI智能爬虫v5.1 - 夸克磁力嗅探版")
    print("=====================================\n")
    # 1. 获取用户输入的网址
    while True:
        start_url = input("📌 请输入要爬取的网址：").strip()
        if start_url.startswith(('http://', 'https://')):
            break
        print("❌ 网址格式错误，请以http://或https://开头！\n")
    # 2. 获取用户自定义爬取数量
    try:
        max_items = int(input("\n📌 请输入爬取上限（默认50）：").strip() or 50)
        max_items = max(10, min(max_items, 200))  # 限制10-200
    except:
        max_items = 50
    # 3. 启动爬虫
    try:
        crawler = AICrawler(start_url)
        crawler.crawl(max_items=max_items)
    except Exception as e:
        print(f"\n❌ 爬虫运行出错: {str(e)[:100]}")
        print("💡 建议检查网络/VPN，或确认目标网址可访问")

if __name__ == '__main__':
    main()
