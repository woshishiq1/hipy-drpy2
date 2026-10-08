#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TVBox 本地包生成器（后端版）
功能：通过 api.php 后端获取和解密TVBox接口，生成可离线使用的本地包
支持自定义 User-Agent，解决 okhttp 等特殊UA需求
支持中文域名自动编码
支持自定义本地包文件夹名称
支持自定义下载文件类型
用法：python tvbox_local_package.py --url <接口地址> [选项]
"""

import os
import sys
import json
import re
import time
import hashlib
import argparse
import urllib.parse
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, Set

try:
    import requests
except ImportError:
    print("⚠️ 请先安装 requests: pip install requests")
    sys.exit(1)

# 尝试导入 idna（用于中文域名编码）
try:
    import idna
    HAS_IDNA = True
except ImportError:
    HAS_IDNA = False
    print("⚠️ 未安装 idna，中文域名可能无法正常解析")
    print("   安装: pip install idna")


# ============================================================
# 核心配置
# ============================================================

DEFAULT_CONCURRENT = 3
DEFAULT_TIMEOUT = 120
DEFAULT_OUTPUT_DIR = "files"
DEFAULT_BACKEND_URL = "http://127.0.0.1:8901/lib/php/api.php"
DEFAULT_USER_AGENT = "okhttp/4.12.0"
DEFAULT_FOLDER_NAME = "TVBox本地包"
DEFAULT_EXTS = "py,js,json,txt"


# ============================================================
# 全局变量（用于存储命令行参数）
# ============================================================

ALLOWED_EXT_FOR_EXT_FIELD = []


# ============================================================
# 中文域名编码
# ============================================================

def punycode_encode_domain(hostname: str) -> str:
    """将中文域名转换为 Punycode"""
    if not hostname:
        return hostname
    
    if 'xn--' in hostname:
        return hostname
    
    if not re.search(r'[\u4e00-\u9fa5]', hostname):
        return hostname
    
    if HAS_IDNA:
        try:
            encoded = idna.encode(hostname).decode('ascii')
            return encoded
        except Exception:
            pass
    
    try:
        encoded = hostname.encode('idna').decode('ascii')
        return encoded
    except Exception:
        pass
    
    try:
        parts = hostname.split('.')
        encoded_parts = []
        for part in parts:
            if re.search(r'[\u4e00-\u9fa5]', part):
                try:
                    encoded = part.encode('idna').decode('ascii')
                    encoded_parts.append(encoded)
                except:
                    encoded_parts.append(urllib.parse.quote(part))
            else:
                encoded_parts.append(part)
        return '.'.join(encoded_parts)
    except Exception:
        pass
    
    return urllib.parse.quote(hostname)


def encode_url_with_chinese(url: str) -> str:
    """编码包含中文的URL"""
    if not url:
        return url
    
    if 'xn--' in url:
        return url
    
    try:
        parsed = urlparse(url)
        if not parsed.hostname:
            return url
        
        if not re.search(r'[\u4e00-\u9fa5]', parsed.hostname):
            return url
        
        encoded_host = punycode_encode_domain(parsed.hostname)
        
        result = ''
        if parsed.scheme:
            result += parsed.scheme + '://'
        result += encoded_host
        if parsed.port:
            result += ':' + str(parsed.port)
        if parsed.path:
            path = parsed.path
            if re.search(r'[\u4e00-\u9fa5]', path):
                path_parts = path.split('/')
                encoded_parts = []
                for part in path_parts:
                    if part and re.search(r'[\u4e00-\u9fa5]', part):
                        encoded_parts.append(urllib.parse.quote(part))
                    else:
                        encoded_parts.append(part)
                path = '/'.join(encoded_parts)
            result += path
        if parsed.query:
            result += '?' + parsed.query
        if parsed.fragment:
            result += '#' + parsed.fragment
        
        return result
    except Exception:
        return url


# ============================================================
# URL 清洗工具
# ============================================================

def clean_url_string(url: str) -> str:
    """清洗URL，去除 ;md5;xxx 等后缀"""
    if not url:
        return url
    
    clean = url
    if ';md5;' in clean:
        clean = clean.split(';md5;')[0]
    if ';MD5;' in clean:
        clean = clean.split(';MD5;')[0]
    if ';' in clean and clean.endswith(';'):
        clean = clean.rstrip(';')
    
    return clean


# ============================================================
# 工具函数
# ============================================================

def get_file_extension(url: str) -> str:
    """获取URL的文件扩展名"""
    clean_url = url.split('?')[0].split('#')[0]
    ext = os.path.splitext(clean_url)[1].lower()
    return ext


def get_target_folder(url: str, parent_key: str = '') -> str:
    """根据URL和父级key确定目标文件夹"""
    ext = get_file_extension(url)
    url_lower = url.lower()
    
    if parent_key == 'spider':
        return 'jar/'
    
    if parent_key in ['lives', 'live']:
        return 'live/'
    
    if parent_key == 'wallpaper':
        return 'img/'
    
    if parent_key == 'logo':
        return 'img/'
    
    if parent_key == 'ext':
        if ext in ['.py']:
            return 'py/'
        if ext in ['.js']:
            return 'js/'
        if ext in ['.json', '.txt']:
            return 'json/'
        return 'other/'
    
    if ext in ['.m3u', '.m3u8']:
        return 'live/'
    if ext in ['.js']:
        return 'js/'
    if ext in ['.py']:
        return 'py/'
    if ext in ['.json']:
        return 'json/'
    if ext in ['.jar']:
        return 'jar/'
    if ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp', '.bmp']:
        return 'img/'
    if ext in ['.txt']:
        return 'json/'
    
    if 'xbpq' in url_lower:
        return 'XBPQ/'
    if 'xyq' in url_lower:
        return 'XYQ/'
    
    return 'other/'


def get_filename_from_url(url: str) -> str:
    """从URL提取文件名"""
    clean = clean_url_string(url)
    
    try:
        parsed = urlparse(clean)
        path = parsed.path
        filename = os.path.basename(path)
        if filename and filename != '/':
            filename = filename.split('?')[0].split('#')[0]
            if filename:
                return filename
    except Exception:
        pass
    
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    ext = get_file_extension(url)
    return f"file_{url_hash}{ext}"


def resolve_relative_path(base_url: str, relative_path: str) -> str:
    """解析相对路径为绝对URL"""
    if not base_url or not relative_path:
        return relative_path
    
    if relative_path.startswith(('http://', 'https://')):
        return relative_path
    
    try:
        return urljoin(base_url, relative_path)
    except Exception:
        return relative_path


def should_download_resource(url: str, parent_key: str = '') -> bool:
    """判断资源是否应该下载"""
    if not url or not isinstance(url, str):
        return False
    
    url_str = url.strip()
    if not url_str or len(url_str) < 5:
        return False
    
    # 模板地址跳过（包含 {name} 等占位符）
    if '{' in url_str and '}' in url_str:
        return False
    
    url_lower = url_str.lower()

    # 本地地址跳过（127.0.0.1/localhost/::1）- 本地服务不是可下载文件
    # 127.0.0.1:5266/iptv.m3u 是本地直播源，不下载
    if any(url_lower.startswith(p) for p in ["http://127.0.0.1", "http://localhost", "https://localhost", "http://::1"]):
        return False

    # spider 字段强制下载（不管什么后缀）
    if parent_key == 'spider':
        return True
    
    # lives/live 字段 - 只下载直播源
    if parent_key in ['lives', 'live']:
        if 'epg.112114' in url_lower or 'epg.v1.mk' in url_lower or 'epg.iill' in url_lower:
            return False
        if 'logo/' in url_lower or '/logo' in url_lower:
            return False
        if not (url_lower.startswith('http://') or url_lower.startswith('https://') or 
                url_lower.startswith('./') or url_lower.startswith('../') or url_lower.startswith('/')):
            return False
        if any(ext in url_lower for ext in ['.m3u', '.m3u8', '.txt']):
            return True
        if 'gitee.com' in url_lower:
            return False
        if url_lower.startswith('http') and ('m3u' in url_lower or 'live' in url_lower):
            return True
        return False
    
    # wallpaper 字段 - 不下载
    if parent_key == 'wallpaper':
        return False
    
    # logo 字段 - 下载图片
    if parent_key == 'logo':
        return True
    
    # ============================================================
    # ★★★ ext/api 字段 - 根据命令行参数控制下载类型 ★★★
    # ============================================================
    if parent_key == 'ext':
        ext = get_file_extension(url_str)
        # 检查是否在允许的扩展名列表中
        if ALLOWED_EXT_FOR_EXT_FIELD:
            if ext in ALLOWED_EXT_FOR_EXT_FIELD:
                return True
        else:
            # 默认：下载 py, js, json, txt
            if ext in ['.py', '.js', '.json', '.txt']:
                return True
        return False
    
    # 通用扩展名
    allowed_exts = ['.js', '.py', '.json', '.jar', '.png', '.jpg', '.jpeg', '.gif', '.svg', 
                   '.ico', '.webp', '.bmp', '.m3u', '.m3u8', '.txt', '.xml']
    ext = get_file_extension(url_str)
    if ext in allowed_exts:
        return True
    
    if any(k in url_lower for k in ['xbpq', 'xyq']):
        return True
    
    return False


# ============================================================
# 加密数据检测
# ============================================================

def is_encrypted_data(content: str) -> bool:
    """检测是否是TVBox加密数据"""
    if not content:
        return False
    
    try:
        content.encode('utf-8')
        is_utf8 = True
    except UnicodeEncodeError:
        is_utf8 = False
    
    if not is_utf8:
        return True
    
    clean = content.replace('\n', '').replace(' ', '').replace('\r', '').strip()
    if clean.startswith('2423'):
        return True
    if '2324' in clean:
        return True
    if '**' in content and len(content) > 50:
        return True
    
    return False


def extract_json_from_content(content: str) -> Optional[str]:
    """从内容中提取JSON"""
    json_match = re.search(r'\{[\s\S]*\}', content)
    if json_match:
        try:
            json_str = json_match.group()
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            json_str = re.sub(r'\/\/.*$', '', json_str, flags=re.MULTILINE)
            json_str = re.sub(r'/\*[\s\S]*?\*/', '', json_str)
            json_str = json_str.replace('，', ',').replace('：', ':')
            json.loads(json_str)
            return json_str
        except:
            pass
    return None


def parse_tvbox_config(content: str) -> Optional[Dict]:
    """解析TVBox配置文件"""
    if not content or not content.strip():
        return None
    
    if content[0] == '\ufeff':
        content = content[1:]
    
    try:
        return json.loads(content)
    except:
        pass
    
    # 检测 TXT 格式（#genre# 标记的片源列表）
    if '#genre#' in content or '#genre#' in content:
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        if len(lines) >= 2:
            sites = []
            current_site = None
            current_lives = []
            for line in lines:
                if '#genre#' in line:
                    if current_site and current_lives:
                        current_site['lives'] = current_lives
                        sites.append(current_site)
                    name = line.split(',')[0].strip()
                    current_site = {
                        'key': f'txt_{name}',
                        'name': name,
                        'type': 0,
                        'lives': []
                    }
                    current_lives = []
                elif ',' in line and current_site:
                    parts = line.split(',', 1)
                    current_lives.append({
                        'name': parts[0].strip(),
                        'url': parts[1].strip()
                    })
            if current_site and current_lives:
                current_site['lives'] = current_lives
                sites.append(current_site)
            if sites:
                # 将分类映射为 lives 格式
                lives = []
                for site in sites:
                    if site.get('lives'):
                        for live in site['lives']:
                            live['group'] = site['name']
                            lives.append(live)
                return {
                    'sites': [],
                    'lives': lives,
                    'parses': [], '_txt_source': True,
                    '_txt_source': True  # 标记为TXT源，不逐条下载
                }
    
    json_str = extract_json_from_content(content)
    if json_str:
        try:
            return json.loads(json_str)
        except:
            pass
    
    try:
        fixed = content
        lines = fixed.split('\n')
        clean_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('//') and not stripped.startswith('//http'):
                if not (stripped.startswith('//http') or stripped.startswith('//https')):
                    continue
            clean_lines.append(line)
        fixed = '\n'.join(clean_lines)
        fixed = re.sub(r'/\*[\s\S]*?\*/', '', fixed)
        fixed = re.sub(r',\s*}', '}', fixed)
        fixed = re.sub(r',\s*]', ']', fixed)
        fixed = fixed.replace('，', ',').replace('：', ':')
        return json.loads(fixed)
    except:
        pass
    
    return None


def extract_resources(config: Dict, base_url: str = '') -> List[Dict]:
    """从配置中提取所有可下载资源"""
    resources = []
    seen_urls = set()
    
    def extract_recursive(obj, parent_key: str = '', path: str = ''):
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_parent = parent_key
                if key in ['lives', 'live']:
                    new_parent = 'lives'
                elif key in ['api']:
                    new_parent = 'ext'
                elif key in ['ext']:
                    new_parent = 'ext'
                elif key in ['spider']:
                    new_parent = 'spider'
                elif key in ['wallpaper']:
                    new_parent = 'wallpaper'
                elif key in ['logo']:
                    new_parent = 'logo'
                elif key in ['site', 'rule', 'json']:
                    new_parent = 'ext'
                
                if isinstance(value, str):
                    process_url(value, new_parent)
                else:
                    extract_recursive(value, new_parent, f"{path}.{key}")
        
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, str):
                    process_url(item, parent_key)
                elif isinstance(item, dict):
                    if 'url' in item and isinstance(item['url'], str):
                        process_url(item['url'], parent_key)
                    if 'path' in item and isinstance(item['path'], str):
                        process_url(item['path'], parent_key)
                    if 'src' in item and isinstance(item['src'], str):
                        process_url(item['src'], parent_key)
                    if 'href' in item and isinstance(item['href'], str):
                        process_url(item['href'], parent_key)
                    extract_recursive(item, parent_key)
        
        elif isinstance(obj, str):
            process_url(obj, parent_key)
    
    def process_url(url_str: str, parent_key: str):
        if not url_str or not isinstance(url_str, str):
            return
        
        url_str = url_str.strip()
        if not url_str:
            return
        
        if not should_download_resource(url_str, parent_key):
            return
        
        is_relative = not (url_str.startswith('http://') or url_str.startswith('https://'))
        full_url = url_str
        
        if is_relative and base_url:
            full_url = resolve_relative_path(base_url, url_str)
        elif not is_relative:
            full_url = url_str
        
        if full_url in seen_urls:
            return
        seen_urls.add(full_url)
        
        folder = get_target_folder(full_url, parent_key)
        filename = get_filename_from_url(full_url)
        
        if parent_key == 'spider':
            folder = 'jar/'
        
        resources.append({
            'url': full_url,
            'original': url_str,
            'folder': folder,
            'filename': filename,
            'parent_key': parent_key
        })
    
    extract_recursive(config)
    return resources


# ============================================================
# 后端API调用
# ============================================================

class BackendAPI:
    """TVBox后端API客户端"""
    
    def __init__(self, backend_url: str = DEFAULT_BACKEND_URL, user_agent: str = DEFAULT_USER_AGENT, proxy: str = ""):
        self.backend_url = backend_url
        self.user_agent = user_agent
        self.proxy = proxy
        self.available = False
        self.detail = ""
    
    def test_connection(self) -> bool:
        """测试后端连接"""
        print(f"🔌 检测后端连接: {self.backend_url}")
        try:
            response = requests.get(
                f"{self.backend_url}?action=health",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'ok':
                    self.available = True
                    php_version = data.get('php_version', '未知')
                    extensions = data.get('extensions', {})
                    openssl = '✅' if extensions.get('openssl') else '❌'
                    curl = '✅' if extensions.get('curl') else '❌'
                    self.detail = f"PHP {php_version} | OpenSSL: {openssl} | cURL: {curl}"
                    return True
                else:
                    self.detail = f"后端返回异常: {data}"
                    return False
            else:
                self.detail = f"HTTP {response.status_code}"
                return False
        except requests.exceptions.ConnectionError:
            self.detail = "连接失败，请检查后端是否运行"
            return False
        except requests.exceptions.Timeout:
            self.detail = "连接超时"
            return False
        except Exception as e:
            self.detail = f"错误: {str(e)}"
            return False
    
    def fetch_url(self, url: str) -> Optional[str]:
        """通过后端获取URL内容"""
        if not self.available:
            return None
        
        encoded_url = encode_url_with_chinese(url)
        
        try:
            response = requests.post(
                self.backend_url,
                data={
                    'action': 'fetch',
                    'url': encoded_url,
                    'ua': self.user_agent
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data.get('data')
                else:
                    print(f"❌ 后端获取失败: {data.get('error', '未知错误')}")
                    return None
        except Exception as e:
            print(f"❌ 后端请求失败: {e}")
            return None
        
        return None
    
    def decrypt_data(self, data: str) -> Optional[str]:
        """通过后端解密数据"""
        if not self.available:
            return None
        
        try:
            response = requests.post(
                self.backend_url,
                data={
                    'action': 'decrypt',
                    'input': data
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    return result.get('data')
                else:
                    print(f"❌ 后端解密失败: {result.get('error', '未知错误')}")
                    return None
        except Exception as e:
            print(f"❌ 后端解密请求失败: {e}")
            return None
        
        return None
    
    def download_file(self, url: str) -> Optional[bytes]:
        """通过后端下载文件"""
        if not self.available:
            return None
        
        clean = clean_url_string(url)
        encoded_url = encode_url_with_chinese(clean)
        
        try:
            response = requests.post(
                self.backend_url,
                data={
                    'action': 'download',
                    'url': encoded_url,
                    'ua': self.user_agent
                },
                timeout=120
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    import base64
                    return base64.b64decode(data.get('data', ''))
                else:
                    print(f"⚠️ 后端下载失败: {data.get('error', '未知错误')}")
                    return None
        except Exception as e:
            print(f"⚠️ 后端下载请求失败: {e}")
            return None
        
        return None


def decode_bmp(content: bytes):
    """从BMP图片提取TVBox JSON数据（饭太硬格式）"""
    if len(content) < 100 or content[:2] != b'BM':
        return None
    pixel_offset = struct.unpack('<I', content[10:14])[0]
    pixel_data = content[pixel_offset:]
    if not pixel_data:
        return None
    for key in [0x9B, 0xAF, 0x5A, 0x66, 0x88, 0x77]:
        decoded = bytes([b ^ key for b in pixel_data])
        text = decoded.decode('utf-8', errors='replace').strip()
        start = text.find('{')
        if start < 0:
            start = text.find('[')
        if start >= 0:
            import json as _json
            candidate = text[start:]
            try:
                _json.loads(candidate)
                return candidate
            except:
                continue
    return None


def decode_image(content: bytes):
    """通用图片隐写解码（JPEG结束标记、base64等）"""
    if not content or len(content) < 50:
        return None
    
    # 方法1: 搜索 JPEG 结束标记 \xff\xd9，取标记后的数据
    jpeg_end = b'\xff\xd9'
    pos = content.rfind(jpeg_end)
    if pos >= 0 and pos + 2 < len(content):
        extra = content[pos + 2:]
        if extra.strip():
            try:
                import json as _j
                return _j.loads(extra)
            except:
                pass
            try:
                import json as _j
                import base64 as _b
                decoded = _b.b64decode(extra).decode('utf-8', errors='ignore')
                start = decoded.find('{')
                if start < 0: start = decoded.find('[')
                if start >= 0: return decoded[start:]
            except:
                pass
    
    # 方法2: 全部二进制当文本处理
    text = content.decode('utf-8', errors='ignore')
    if not text.strip():
        return None
    try:
        import json as _j
        return _j.loads(text)
    except:
        pass
    b64_pattern = __import__('re').compile(r'[A-Za-z0-9+/=]{50,}')
    for match in b64_pattern.finditer(text):
        try:
            import json as _j
            import base64 as _b
            decoded = _b.b64decode(match.group()).decode('utf-8', errors='ignore')
            start = decoded.find('{')
            if start < 0: start = decoded.find('[')
            if start >= 0:
                _j.loads(decoded[start:])
                return decoded[start:]
        except:
            continue
    return None


# ============================================================
# 下载器
# ============================================================

class Downloader:
    """文件下载器"""
    
    def __init__(self, backend: BackendAPI, concurrent: int = DEFAULT_CONCURRENT, timeout: int = DEFAULT_TIMEOUT):
        self.backend = backend
        self.concurrent = concurrent
        self.timeout = timeout
        self.proxy = backend.proxy if backend else ""
        self.downloaded = []
        self.failed = []
        self.total = 0
        self.completed = 0
    
    def download_file(self, url: str, save_path: str, retries: int = 3) -> bool:
        """下载单个文件"""
        cleaned_url = clean_url_string(url)
        
        # 优先使用后端下载
        if self.backend.available:
            for attempt in range(retries):
                try:
                    data = self.backend.download_file(cleaned_url)
                    if data:
                        os.makedirs(os.path.dirname(save_path), exist_ok=True)
                        with open(save_path, 'wb') as f:
                            f.write(data)
                        return True
                except Exception:
                    if attempt < retries - 1:
                        time.sleep(0.5 * (attempt + 1))
                    continue
        
        # 后端失败，尝试直接下载
        proxy_msg = f"，代理: {self.proxy}" if self.proxy else ""
        print(f"📥 直连降级，py脚本直接负责下载{proxy_msg}...")
        for attempt in range(retries):
            try:
                encoded_url = encode_url_with_chinese(cleaned_url)
                
                headers = {
                    'User-Agent': self.backend.user_agent if self.backend else 'okhttp/4.12.0',
                    'Accept': '*/*',
                    'Accept-Language': 'zh-CN,zh;q=0.9',
                    'Connection': 'keep-alive'
                }
                
                proxies = None
                if self.proxy:
                    proxies = {"http": self.proxy, "https": self.proxy}
                response = requests.get(encoded_url, headers=headers, timeout=self.timeout, stream=True, proxies=proxies)
                
                if response.status_code == 200:
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    with open(save_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    return True
                elif response.status_code == 404:
                    print(f"   ⚠️ 404: {os.path.basename(save_path)}")
                    return False
                elif response.status_code >= 400:
                    if attempt < retries - 1:
                        time.sleep(0.5 * (attempt + 1))
                    continue
            except Exception:
                if attempt < retries - 1:
                    time.sleep(0.5 * (attempt + 1))
                continue
        
        return False
    
    def download_all(self, resources: List[Dict], output_dir: str) -> Tuple[List, List]:
        """批量下载所有资源 - 逐行显示进度"""
        self.downloaded = []
        self.failed = []
        self.total = len(resources)
        self.completed = 0
        
        print(f"\n📥 准备下载 {self.total} 个文件...", flush=True)
        print(f"   📁 保存到: {output_dir}")
        print(f"   ⚡ 并发数: {self.concurrent}", flush=True)
        print()
        
        tasks = []
        for resource in resources:
            save_path = os.path.join(output_dir, resource['folder'], resource['filename'])
            tasks.append({
                'url': resource['url'],
                'save_path': save_path,
                'resource': resource
            })
        
        with ThreadPoolExecutor(max_workers=self.concurrent) as executor:
            futures = {}
            for task in tasks:
                future = executor.submit(self.download_file, task['url'], task['save_path'])
                futures[future] = task
            
            for future in as_completed(futures):
                task = futures[future]
                success = future.result()
                
                self.completed += 1
                if success:
                    self.downloaded.append(task['resource'])
                    status = "✅"
                else:
                    self.failed.append(task['resource'])
                    status = "❌"
                
                pct = int(self.completed / self.total * 100)
                filename = task['resource']['filename']
                folder = task['resource']['folder'].rstrip('/')
                print(f"[{pct:3d}%] {status} [{folder}] {filename}", flush=True)
        
        print(f"\n{'='*50}")
        print(f"📊 下载完成!")
        print(f"   ✅ 成功: {len(self.downloaded)} 个")
        if self.failed:
            print(f"   ❌ 失败: {len(self.failed)} 个")
        print(f"{'='*50}")
        
        return self.downloaded, self.failed


# ============================================================
# 本地包生成器
# ============================================================

class LocalPackageGenerator:
    """本地包生成器"""
    
    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR, 
                 backend_url: str = DEFAULT_BACKEND_URL,
                 user_agent: str = DEFAULT_USER_AGENT,
                 folder_name: str = DEFAULT_FOLDER_NAME,
                 proxy: str = ""):
        self.base_output_dir = output_dir
        self.folder_name = folder_name
        self.output_dir = os.path.join(output_dir, folder_name)
        self.user_agent = user_agent
        self.proxy = proxy
        self.backend = BackendAPI(backend_url, user_agent, proxy)
        self.resources = []
        self.config = None
        self.base_url = ''
        self.file_map = {}
        self._backend_fetched = False
        self.raw_content = None
    
    def _decode_bmp_raw(self, bmp_raw: bytes) -> Optional[str]:
        """BMP原始解码"""
        import struct
        pixel_offset = struct.unpack('<I', bmp_raw[10:14])[0]
        pixel_data = bmp_raw[pixel_offset:]
        for key in [0x9B, 0xAF, 0x5A, 0x66, 0x88, 0x77]:
            decoded = bytes([b ^ key for b in pixel_data])
            text = decoded.decode('utf-8', errors='replace').strip()
            start = text.find('{')
            if start < 0: start = text.find('[')
            if start >= 0:
                import json as _j
                candidate = text[start:]
                depth, end = 0, 0
                for i, ch in enumerate(candidate):
                    if ch == '{': depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0: end = i + 1; break
                if end > 0:
                    try:
                        _j.loads(candidate[:end])
                        return candidate[:end]
                    except: pass
            # 如果不是JSON，就是TXT格式
            if '#genre' in text:
                return decoded.decode('utf-8', errors='replace')
        return None
    
    def init_backend(self) -> bool:
        """初始化后端连接"""
        if self.backend.test_connection():
            print(f"✅ 后端连接成功")
            print(f"   📌 {self.backend.detail}")
            return True
        else:
            print(f"❌ 后端连接失败: {self.backend.detail}")
            print(f"   💡 提示: 请确保后端服务已启动")
            print(f"   💡 后端地址: {self.backend.backend_url}")
            print(f"   💡 启动命令: php -S 0.0.0.0:8901 api.php")
            return False
    
    def fetch_content(self, url: str) -> Optional[str]:
        """获取内容 - 后端优先，直连兜底"""

        # ========== 1. 优先通过后端获取 ==========
        if self.backend.available:
            try:
                print(f"📥 通过后端获取: {url}")
                content = self.backend.fetch_url(url)
                if content:
                    print("✅ 后端获取成功")
                    self._backend_fetched = True
                    return content
                else:
                    print("⚠️ 后端获取失败，尝试直接下载")
            except Exception as e:
                print(f"⚠️ 后端获取异常: {e}")

        # ========== 2. 直接下载 ==========
        return self._direct_download(url)
    
    def _direct_download(self, url: str) -> Optional[str]:
        """直接下载 - 先裸请求，不行再带UA兜底"""
        encoded_url = encode_url_with_chinese(url)
        if encoded_url != url:
            print(f"   🌐 中文域名编码: {url} -> {encoded_url}")

        # 尝试列表：无UA → 配置UA → Chrome UA
        attempts = [
            (None, f"📥 裸请求: {encoded_url[:60]}..."),
            (self.user_agent, f"📥 配置UA: {encoded_url[:60]}..."),
            ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36', f"📥 ChromeUA: {encoded_url[:60]}..."),
        ]

        for ua, msg in attempts:
            try:
                print(msg, flush=True)
                headers = {}
                if ua:
                    headers['User-Agent'] = ua
                
                proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
                resp = requests.get(encoded_url, headers=headers, timeout=30, proxies=proxies)

                if resp.status_code == 200:
                    raw = resp.content
                    if len(raw) >= 2 and raw[:2] == b'BM':
                        content = raw.decode('latin1')
                    else:
                        try:
                            content = resp.text
                        except:
                            try:
                                content = raw.decode('utf-8', errors='ignore')
                            except:
                                content = raw.decode('gbk', errors='ignore')
                    print("✅ 下载成功", flush=True)
                    return content
                else:
                    print(f"⚠️ HTTP {resp.status_code}", flush=True)
            except Exception as e:
                print(f"⚠️ {e}", flush=True)

        return None
    
    def load_config(self, url: str) -> bool:
        """加载TVBox配置"""
        self.base_url = url
        
        content = self.fetch_content(url)
        if not content:
            print("❌ 获取内容失败")
            return False
        
        # 保存原始获取的内容
        self.raw_content = content
        
        # ==== 1. BMP/JPEG图片解码 ====
        if len(content) > 100 and isinstance(content, str) and content[:2] == 'BM':
            decoded = decode_bmp(content.encode('latin1'))
            if decoded:
                content = decoded
                print("🔓 解析BMP隐写成功", flush=True)
        elif len(content) > 100 and isinstance(content, str):
            try:
                decoded = decode_image(content.encode('latin1'))
                if decoded:
                    content = decoded
                    print("🔓 解析图片隐写成功", flush=True)
            except:
                pass
        
        # ==== 2. 判断内容类型: JSON还是原始文件? ====
        _is_json = False
        try:
            json.loads(content)
            _is_json = True
        except:
            try:
                json.loads(content.lstrip('\ufeff').strip())
                _is_json = True
            except:
                pass
        
        if _is_json:
            pass  # 走下面的解密/解析逻辑
        else:
            # 非JSON - 直接保存为原始文件
            print("📄 检测到原始文件类型（非JSON），直接保存", flush=True)
            self._raw_file = True
            self._raw_file_content = content
            self.config = {'_raw_file': True, 'url': url}
            return True
        
        # ==== 3. JSON解密检测 ====
        if not self._backend_fetched and is_encrypted_data(content):
            print("🔓 检测到加密数据")
            if self.backend.available:
                decrypted = self.backend.decrypt_data(content)
                if decrypted:
                    content = decrypted
                    print("✅ 后端解密成功")
                else:
                    print("⚠️ 后端解密失败")
            else:
                json_str = extract_json_from_content(content)
                if json_str:
                    content = json_str
                    print("✅ 从加密数据中提取JSON成功")
                else:
                    print("❌ 无法解密")
                    return False
        
        config = parse_tvbox_config(content)
        if not config:
            print("❌ 解析配置失败")
            print(f"   内容预览: {content[:200]}...")
            return False
        
        self.config = config
        return True
    
    def extract_resources(self) -> int:
        """提取资源列表"""
        if not self.config:
            return 0
        
        # 原始文件类型（.txt/.m3u/.m3u8/.bmp）：直接保存
        if self.config.get('_raw_file'):
            self._is_raw_source = True
            self.resources = []
            return self._save_raw_file()
        
        self.resources = extract_resources(self.config, self.base_url)
        return len(self.resources)
    
    def _save_raw_file(self) -> int:
        """保存原始文件（非JSON内容）"""
        content = getattr(self, '_raw_file_content', self.raw_content)
        if not content:
            return 0
        
        txt = content if isinstance(content, str) else content.decode('utf-8', errors='replace')
        
        # 根据内容类型决定后缀
        if txt.strip().startswith('#EXTM3U'):
            ext = '.m3u'
        elif txt.strip().startswith('#genre#'):
            ext = '.txt'
        else:
            ext = os.path.splitext(self.config.get('url', ''))[1].lower()
            if ext in ('.bmp', '.m3u8', ''):
                ext = '.txt'
        
        raw_dir = os.path.join(self.output_dir, 'raw')
        os.makedirs(raw_dir, exist_ok=True)
        self._raw_ext = ext
        filepath = os.path.join(raw_dir, f'source{ext}')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(txt)
        print(f"✅ 原始文件已保存: {filepath}", flush=True)
        return 0
    
    def download_resources(self, concurrent: int = DEFAULT_CONCURRENT, timeout: int = DEFAULT_TIMEOUT) -> Tuple[List, List]:
        """下载所有资源"""
        if getattr(self, '_is_raw_source', False):
            os.makedirs(self.output_dir, exist_ok=True)
            return [], []
        
        if not self.resources:
            return [], []
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 先保存原始配置文件
        if self.raw_content:
            try:
                try:
                    parsed = json.loads(self.raw_content)
                    formatted = json.dumps(parsed, ensure_ascii=False, indent=2)
                except:
                    formatted = self.raw_content
                
                origin_path = os.path.join(self.output_dir, 'origin.json')
                with open(origin_path, 'w', encoding='utf-8') as f:
                    f.write(formatted)
                print(f"📝 原始配置文件已保存: origin.json")
            except Exception as e:
                print(f"⚠️ 保存原始配置失败: {e}")
        else:
            print("⚠️ 没有原始配置内容可保存")
        
        downloader = Downloader(self.backend, concurrent, timeout)
        
        print(f"📥 开始下载 {len(self.resources)} 个资源...")
        print(f"   User-Agent: {self.user_agent}")
        print(f"   📁 输出目录: {self.output_dir}")
        
        folder_counts = {}
        spider_count = 0
        ext_count = 0
        wallpaper_count = 0
        for r in self.resources:
            folder = r['folder'].rstrip('/')
            folder_counts[folder] = folder_counts.get(folder, 0) + 1
            if r['parent_key'] == 'spider':
                spider_count += 1
            if r['parent_key'] == 'ext':
                ext_count += 1
            if r['parent_key'] == 'wallpaper':
                wallpaper_count += 1
        
        print("📂 资源分布:")
        for folder, count in sorted(folder_counts.items()):
            print(f"  📁 {folder}/: {count} 个文件")
        if spider_count > 0:
            print(f"   📌 spider 字段: {spider_count} 个 (全部放入 jar/)")
        if ext_count > 0:
            print(f"   📌 ext/api 字段: {ext_count} 个 (py→py/, js→js/, json/txt→json/)")
        if wallpaper_count > 0:
            print(f"   📌 wallpaper 字段: {wallpaper_count} 个 (已跳过，不下载)")
        print()
        
        downloaded, failed = downloader.download_all(self.resources, self.output_dir)
        
        self.file_map = {}
        for r in downloaded:
            local_path = os.path.join(r['folder'], r['filename'])
            self.file_map[r['url']] = local_path
            self.file_map[r['original']] = local_path
        
        return downloaded, failed
    
    def generate_config(self, output_filename: str = 'index.json') -> str:
        """生成本地化配置"""
        # 原始文件：生成简单引用配置
        if getattr(self, '_is_raw_source', False):
            ext = getattr(self, '_raw_ext', '.txt')
            cfg = {"sites": [], "lives": [{"group": "原始源", "name": f"Raw Source ({ext})", "url": f"raw/source{ext}"}], "parses": []}
            cfg_path = os.path.join(self.output_dir, output_filename)
            with open(cfg_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            print(f"✅ 原始源配置已保存: {cfg_path}", flush=True)
            return cfg_path
        
        if not self.config:
            return ''
        
        import copy
        local_config = copy.deepcopy(self.config)
        
        def replace_urls(obj):
            if isinstance(obj, dict):
                for key, value in list(obj.items()):
                    if isinstance(value, str):
                        if value in self.file_map:
                            obj[key] = './' + self.file_map[value]
                        else:
                            for url, local in self.file_map.items():
                                if value == url or value == os.path.basename(url):
                                    obj[key] = './' + local
                                    break
                    elif isinstance(value, (dict, list)):
                        replace_urls(value)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    if isinstance(item, str):
                        if item in self.file_map:
                            obj[i] = './' + self.file_map[item]
                        else:
                            for url, local in self.file_map.items():
                                if item == url or item == os.path.basename(url):
                                    obj[i] = './' + local
                                    break
                    elif isinstance(item, (dict, list)):
                        replace_urls(item)
        
        replace_urls(local_config)
        
        # 移除内部标记
        local_config.pop('_txt_source', None)
        
        config_path = os.path.join(self.output_dir, output_filename)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(local_config, f, ensure_ascii=False, indent=2)
        
        return config_path
    
    def generate_report(self) -> str:
        """生成下载报告"""
        total = len(self.resources)
        downloaded = len([r for r in self.resources if r['url'] in self.file_map])
        failed = total - downloaded
        
        folder_stats = {}
        for r in self.resources:
            folder = r['folder'].rstrip('/')
            if folder not in folder_stats:
                folder_stats[folder] = {'total': 0, 'success': 0, 'failed': 0}
            folder_stats[folder]['total'] += 1
            if r['url'] in self.file_map:
                folder_stats[folder]['success'] += 1
            else:
                folder_stats[folder]['failed'] += 1
        
        report = f"""
📊 TVBox 本地包生成报告
{'=' * 50}
📁 输出目录: {self.output_dir}
📄 配置文件: index.json
📄 原始配置: origin.json
📦 资源总数: {total}
✅ 下载成功: {downloaded}
❌ 下载失败: {failed}
🔗 User-Agent: {self.user_agent}
🔌 后端状态: {'✅ 已连接' if self.backend.available else '❌ 未连接'}
📋 ext/api 下载类型: {', '.join(ALLOWED_EXT_FOR_EXT_FIELD) if ALLOWED_EXT_FOR_EXT_FIELD else 'py, js, json, txt'}

📂 文件分布:
"""
        
        for folder, stats in sorted(folder_stats.items()):
            status = "✅" if stats['failed'] == 0 else "⚠️"
            report += f"  {status} 📁 {folder}/: {stats['success']}/{stats['total']} 成功"
            if stats['failed'] > 0:
                report += f" ({stats['failed']} 失败)"
            report += "\n"
        
        key_stats = {}
        for r in self.resources:
            key = r['parent_key']
            if key not in key_stats:
                key_stats[key] = 0
            key_stats[key] += 1
        
        report += f"\n📋 来源分布:\n"
        for key, count in sorted(key_stats.items()):
            report += f"  • {key}: {count} 个\n"
        
        return report


# ============================================================
# 命令行接口
# ============================================================

def main():
    global ALLOWED_EXT_FOR_EXT_FIELD
    
    parser = argparse.ArgumentParser(description='TVBox本地包生成器（后端版）')
    parser.add_argument('-u', '--url', required=True, help='TVBox接口URL（支持中文域名）')
    parser.add_argument('-o', '--output', default='TVBox_Local', help='输出父目录')
    parser.add_argument('-n', '--name', default=DEFAULT_FOLDER_NAME, help='本地包文件夹名称 (默认: TVBox本地包)')
    parser.add_argument('-b', '--backend', default=DEFAULT_BACKEND_URL, help='后端API地址')
    parser.add_argument('-a', '--ua', default=DEFAULT_USER_AGENT, help='User-Agent (默认: okhttp/4.12.0)')
    parser.add_argument('-c', '--concurrent', type=int, default=3, help='并发下载数 (1-10)')
    parser.add_argument('-t', '--timeout', type=int, default=120, help='下载超时秒数')
    parser.add_argument('--exts', default=DEFAULT_EXTS, 
                        help='ext/api字段下载的文件扩展名，逗号分隔 (默认: py,js,json,txt)')
    parser.add_argument('--no-backend', action='store_true', help='不使用后端（直接下载，更快）')
    parser.add_argument('--proxy', help='SOCKS5代理地址 (如 socks5://127.0.0.1:7890)，后端下载失败时作为直连降级')
    parser.add_argument('--no-download', action='store_true', help='只解析不下载')
    
    args = parser.parse_args()
    
    # ★★★ 解析允许的扩展名 ★★★
    ALLOWED_EXT_FOR_EXT_FIELD = ['.' + ext.strip() for ext in args.exts.split(',') if ext.strip()]
    if not ALLOWED_EXT_FOR_EXT_FIELD:
        ALLOWED_EXT_FOR_EXT_FIELD = ['.py', '.js', '.json', '.txt']
    
    # 清理文件夹名称
    folder_name = re.sub(r'[<>:"/\\|?*]', '_', args.name).strip()
    if not folder_name:
        folder_name = DEFAULT_FOLDER_NAME
    
    print(f"🚀 TVBox 本地包生成器（后端版）", flush=True)
    print(f"📡 接口地址: {args.url}", flush=True)
    print(f"📁 输出父目录: {args.output}", flush=True)
    print(f"📂 本地包文件夹: {folder_name}", flush=True)
    print(f"📁 完整输出路径: {os.path.join(args.output, folder_name)}", flush=True)
    print(f"🔗 后端地址: {args.backend}", flush=True)
    print(f"🔑 User-Agent: {args.ua}", flush=True)
    if args.proxy:
        print(f"🔌 代理: {args.proxy}", flush=True)
    print(f"⚡ 并发数: {args.concurrent}", flush=True)
    print(f"📋 ext/api 下载类型: {', '.join(ALLOWED_EXT_FOR_EXT_FIELD)}", flush=True)
    print(flush=True)
    
    generator = LocalPackageGenerator(args.output, args.backend, args.ua, folder_name, args.proxy or "")
    
    if not args.no_backend:
        generator.init_backend()
    else:
        print("⚠️ 已禁用后端（直接下载模式）", flush=True)
    
    print("📥 加载配置...", flush=True)
    if not generator.load_config(args.url):
        print("❌ 加载配置失败", flush=True)
        sys.exit(1)
    print("✅ 配置加载成功", flush=True)
    
    print("🔍 提取资源...", flush=True)
    count = generator.extract_resources()
    print(f"✅ 找到 {count} 个可下载资源", flush=True)
    
    spider_count = len([r for r in generator.resources if r['parent_key'] == 'spider'])
    ext_count = len([r for r in generator.resources if r['parent_key'] == 'ext'])
    wallpaper_count = len([r for r in generator.resources if r['parent_key'] == 'wallpaper'])
    if spider_count > 0:
        print(f"   📌 spider 字段: {spider_count} 个 (全部放入 jar/)", flush=True)
    if ext_count > 0:
        print(f"   📌 ext/api 字段: {ext_count} 个 (下载类型: {', '.join(ALLOWED_EXT_FOR_EXT_FIELD)})", flush=True)
    if wallpaper_count > 0:
        print(f"   📌 wallpaper 字段: {wallpaper_count} 个 (已跳过，不下载)", flush=True)
    
    if count == 0 and not getattr(generator, '_is_raw_source', False):
        print("⚠️ 没有找到可下载的资源", flush=True)
        sys.exit(0)
    
    print("\n📋 资源预览 (前10个):", flush=True)
    for i, r in enumerate(generator.resources[:10]):
        parent_info = f"[spider]" if r['parent_key'] == 'spider' else f"[{r['parent_key']}]"
        print(f"  {i+1}. {parent_info} {r['folder']}{r['filename']}", flush=True)
    if count > 10:
        print(f"  ... 还有 {count - 10} 个资源", flush=True)
    
    if args.no_download:
        print("\n⚠️ 只解析模式，不执行下载", flush=True)
        sys.exit(0)
    
    print(flush=True)
    
    # 原始文件（M3U/TXT）：直接保存完成，不需要生成JSON配置和报告
    if hasattr(generator, '_is_raw_source') and generator._is_raw_source:
        print("\n✨ 完成!", flush=True)
        return
    
    downloaded, failed = generator.download_resources(args.concurrent, args.timeout)
    
    if downloaded:
        print("\n📝 生成本地配置...", flush=True)
        config_path = generator.generate_config()
        print(f"✅ 配置已保存: {config_path}", flush=True)
    
    print("\n" + generator.generate_report(), flush=True)
    
    if failed:
        print("\n❌ 下载失败的文件 (最多显示10个):", flush=True)
        for r in failed[:10]:
            print(f"  - {r['url']}", flush=True)
        if len(failed) > 10:
            print(f"  ... 还有 {len(failed) - 10} 个失败", flush=True)
    
    print("\n✨ 完成!", flush=True)


if __name__ == '__main__':
    main()