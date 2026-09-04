# -*- coding: utf-8 -*-
# @version v4.0 -  自适应（手机·平板·电视）
# @author 陆小凤

import base64
import copy
import hashlib
import json
import os
import queue
import re
import shutil
import threading
import time
import traceback
import urllib.parse
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from base.spider import Spider as BaseSpider

try:
    from java import jclass, dynamic_proxy
except ImportError:
    jclass = None
    dynamic_proxy = None

DEFAULT_USER_AGENT = 'okhttp/4.12.0'
DEFAULT_EXTERNAL_API_URL = "https://xn--v4q818bf34b.cc/helper/api.php"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.getcwd()
CACHE_DIR = os.path.join(SCRIPT_DIR, 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)

PERSISTENT_CONFIG_PATH = None

def _get_app_cache_dir():
    try:
        from java import jclass
        ActivityThread = jclass("android.app.ActivityThread")
        at = ActivityThread.currentActivityThread()
        context = at.getApplication()
        cache_dir = context.getCacheDir().getAbsolutePath()
        return cache_dir
    except Exception:
        return "/storage/emulated/0/.local_source_manager"

_cache_root = _get_app_cache_dir()
os.makedirs(_cache_root, exist_ok=True)
PERSISTENT_CONFIG_PATH = os.path.join(_cache_root, "persistent_config.json")

def _decode_bytes(raw):
    if not raw:
        return ''
    if raw[:3] == b'\xef\xbb\xbf':
        return raw.decode('utf-8-sig', errors='replace')
    for enc in ('utf-8', 'gb18030', 'big5'):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode('utf-8', errors='replace')

def _read_text_file(path):
    with open(path, 'rb') as f:
        return _decode_bytes(f.read())

_COMMON_USER_DIRS = [
    '/storage/emulated/0', '/sdcard', '/storage/sdcard0',
    '/storage/emulated/0/TVBox', '/storage/emulated/0/影视仓',
    '/storage/emulated/0/影视TV', '/storage/emulated/0/Download',
    '/storage/emulated/0/Documents', '/data/data', '/storage',
]

_FS_SEARCH_ROOTS = ['/storage/emulated/0', '/sdcard', '/storage/sdcard0', '/storage']
_FS_SKIP_DIRS = {
    'Android', 'DCIM', 'Pictures', 'Music', 'Movies', 'WhatsApp',
    'tencent', 'Telegram', '.cache', 'cache', 'Download', 'Documents',
    'Ringtones', 'Alarms', 'Notifications', 'Podcasts', 'Audiobooks',
}

GITHUB_PROXY = "https://gh-proxy.com/"

DOWNLOAD_EXTS = {
    '.js', '.py', '.jar', '.json', '.txt', '.m3u', '.m3u8',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
    '.css', '.html', '.htm', '.xml', '.zip', '.mp4', '.ts',
    '.woff', '.woff2', '.ttf', '.eot', '.svg',
}
SKIP_EXTS = {'.php', '.asp', '.aspx', '.jsp'}
SKIP_PATTERNS = [
    r'/api\.php/provide/vod', r'/api\.php/app/', r'provide/vod',
    r'\?url=', r'\{name\}', r'\{date\}', r'\{episode\}', r'proxy://',
]

PLACEHOLDER_RE = r'\{[A-Za-z_][A-Za-z0-9_]*\}'
SKIP_PATTERNS_WITH_PLACEHOLDER = SKIP_PATTERNS + [PLACEHOLDER_RE]

BOOL_MAP = {'是': True, '否': False, '下载': True, '不下载': False,
            'true': True, 'false': False, '1': True, '0': False, True: True, False: False}

LOG_LEVELS = {'debug': 10, 'info': 20, 'warn': 30, 'error': 40}
LOG_LEVEL_DEFAULT = 'debug'

LOG_FILE_QUEUE_MAXSIZE = 20000
LOG_FILE_FLUSH_LINES = 30
LOG_FILE_FLUSH_SECONDS = 1.0
LOG_FILE_IDLE_TIMEOUT = 0.4

LOG_FILE_MAX_BYTES = 10 * 1024 * 1024
LOG_FILE_BACKUPS = 3

MULTIPART_MIN_BYTES = 20 * 1024 * 1024
MULTIPART_MIN_BYTES_MIN = 64 * 1024

DOWNLOAD_MAX_SECONDS = 120
DOWNLOAD_MAX_SECONDS_MIN = 30

LOG_VIEW_MAX_CHARS = 10000
LOG_VIEW_TRIM_TO = 6000

LOG_LEVEL_TAG = {'debug': '·', 'info': 'ℹ', 'warn': '⚠', 'error': '✖'}
LOG_LEVEL_LABEL = {'debug': 'DEBUG', 'info': 'INFO',
                   'warn': 'WARN', 'error': 'ERROR'}
LOG_VIEW_BUFFER_MAX = 400

LOOPER_INTERVAL_MS = 300
LOOPER_BATCH_MAX = 60
LOOPER_MISS_LIMIT = 10

HEAD_FAIL_THRESHOLD = 3
HEAD_TIMEOUT_MAX = 6
HEAD_CACHE_TTL = 600
HEAD_CACHE_MAX = 2000
HASH_CHUNK_SIZE = 1 << 20

SITE_BATCH_MAX_WORKERS = 3

URL_DSLASH_GUARD = "@@DSLASH@@"

def safe_urljoin(base, rel):
    if not rel:
        return base
    if not base:
        return rel
    low = str(rel).strip().lower()
    if low.startswith(('http://', 'https://')):
        return rel
    try:
        p = urllib.parse.urlsplit(base)
        guarded = urllib.parse.urlunsplit(
            (p.scheme, p.netloc, p.path.replace("//", URL_DSLASH_GUARD),
             p.query, p.fragment))
        joined = urllib.parse.urljoin(guarded, rel)
        jp = urllib.parse.urlsplit(joined)
        return urllib.parse.urlunsplit(
            (jp.scheme, jp.netloc, jp.path.replace(URL_DSLASH_GUARD, "//"),
             jp.query, jp.fragment))
    except Exception:
        return urllib.parse.urljoin(base, rel)

import re as _re
SCHEME_RE = _re.compile(r'^[a-zA-Z][a-zA-Z0-9+.\-]*://')

DEFAULT_FILE_SERVICE_PORT = 9978
DEFAULT_PROXY_PORT = 7890

EDIT_MIN_LINES = 24
EDIT_MIN_HEIGHT_RATIO = 0.46

WARNING_TEXT = "禁止任何商业用途，仅限个人学习爬虫原理使用@陆小凤。"

LOG_LINE_SOFT_LIMIT = 46
LOG_URL_KEEP_HOST = True
LOG_CONTINENT_INDENT = "    "

def _short_url(u, max_len=52):
    s = str(u or "").strip()
    if not s:
        return ""
    if len(s) <= max_len:
        return s
    try:
        p = urllib.parse.urlsplit(s)
        scheme = p.scheme + "://" if p.scheme else ""
        host = p.netloc or ""
        tail = (p.path or "").rstrip("/")
        fname = tail.rsplit("/", 1)[-1] if tail else ""
        if fname:
            short = "{}{}/.../{}".format(scheme, host, fname)
        elif host:
            short = "{}{}/...".format(scheme, host)
        else:
            short = s
        if len(short) > max_len:
            short = short[:max_len - 3] + "..."
        return short
    except Exception:
        return s[:max_len - 3] + "..." if len(s) > max_len else s

_EXC_START_RE = re.compile(
    r'(?:HTTPS?ConnectionPool|HTTPConnectionPool|URLError|urlopen|Invalid URL)\b.*$',
    re.S)

def _exc_reason(tail):
    low = str(tail or "").lower()
    if "nodename nor servname" in low or "name or service not known" in low \
            or "failed to resolve" in low or "getaddrinfo" in low:
        return "DNS 解析失败"
    if "no scheme supplied" in low:
        return "URL 缺少协议头"
    if "invalid url" in low:
        return "URL 格式无效"
    if "certificate" in low or "ssl" in low:
        return "SSL 证书错误"
    if "connection refused" in low:
        return "连接被拒绝"
    if "connection reset" in low or "connection aborted" in low:
        return "连接被重置"
    if "connect timeou" in low or "connection to" in low and "timed out" in low:
        return "连接超时"
    if "read timeou" in low or "read timed out" in low:
        return "读取超时"
    if "max retries exceeded" in low:
        return "重试次数用尽"
    return "网络请求失败"

def _simplify_exception(msg):
    s = str(msg or "")
    if not s:
        return s
    m = _EXC_START_RE.search(s)
    if not m:
        return s
    head = s[:m.start()].rstrip()
    head = head.rstrip(":： ").rstrip()
    reason = _exc_reason(m.group(0))
    return ("%s: %s" % (head, reason)) if head else reason

def _disp_width(s):
    w = 0
    for ch in str(s or ""):
        w += 2 if ord(ch) > 0x2E80 else 1
    return w

class _LogRing(object):

    def __init__(self, maxlen):
        self._max = max(1, int(maxlen or 1))
        self._buf = []

    def append(self, item):
        self._buf.append(item)
        if len(self._buf) > self._max:
            cut = max(1, self._max // 5)
            del self._buf[:cut]

    def __iter__(self):
        return iter(self._buf)

    def __len__(self):
        return len(self._buf)

    def clear(self):
        self._buf = []

_URL_RE = re.compile(r'https?://[^\s，。；）)\]】"\'，,]+')

def _format_log_block(msg, level='info'):
    s = _simplify_exception(str(msg or "")).strip()
    if not s:
        return ""

    long_urls = []
    def _take(m):
        u = m.group(0)
        short = _short_url(u)
        if short != u:
            long_urls.append(u)
        return short
    s = _URL_RE.sub(_take, s)

    detail = ""
    for sep in ("：", ": ", "，尝试", " -> ", " => "):
        if sep in s:
            head, tail = s.split(sep, 1)
            head, tail = head.strip(), tail.strip()
            if not head or not tail:
                continue
            if _disp_width(head) <= LOG_LINE_SOFT_LIMIT and \
                    _disp_width(tail) <= LOG_LINE_SOFT_LIMIT:
                break
            if _disp_width(head) <= LOG_LINE_SOFT_LIMIT:
                s, detail = head, tail
                break

    out = [s]
    if detail:
        out.append(LOG_CONTINENT_INDENT + detail)

    for u in long_urls:
        out.append(LOG_CONTINENT_INDENT + "地址: " + u)

    result = []
    for line in out:
        if _disp_width(line) <= LOG_LINE_SOFT_LIMIT * 2:
            result.append(line)
            continue
        cur = ""
        for ch in line:
            cur += ch
            if _disp_width(cur) >= LOG_LINE_SOFT_LIMIT * 2:
                result.append(cur)
                cur = LOG_CONTINENT_INDENT
        if cur.strip():
            result.append(cur)
    return "\n".join(result).rstrip()

PROCESS_INFO_KEY = "处理信息"

GITHUB_HOSTS = ('raw.githubusercontent.com', 'github.com', 'gist.github.com',
                'gist.githubusercontent.com', 'githubusercontent.com')

PROXY_FAIL_THRESHOLD = 2

FAIL_SKIP_THRESHOLD = 2
FAIL_ENTRY_TTL = 3 * 24 * 3600

DEFAULT_DOWNLOAD_DIR = "/storage/emulated/0/download/本地包"

CONFIG_BACKUP_NAME = "persistent_config.json"

CONFIG_BACKUP_PREFIX = "down_config["
CONFIG_BACKUP_STAMP_FMT = "%y%m%d%H"
CONFIG_BACKUP_STAMP_RE = None
CONFIG_BACKUP_SUBDIR = "temp"

UI_CLICK_DEBOUNCE = 0.35

MANIFEST_NAME = ".localize_manifest.json"
MANIFEST_VERSION = 1
VERIFY_JSON_MAX_BYTES = 2 << 20
NOT_MODIFIED_CACHE_TTL = 600

SETTING_SPECS = [
    {
        "key": "log_dir", "id": "log_dir",
        "title": "设置日志目录", "kind": "dir",
        "path": "log.dir", "raw": True, "attr": "log_dir",
        "normalize": "dir_slash", "makedirs": True,
        "icon": "☷", "label": "日志目录", "fmt": "dir",
    },
    {
        "key": "download_dir", "id": "download_dir",
        "title": "设置本地包输出目录", "kind": "dir",
        "store": "attr", "attr": "download_output_dir",
        "default": DEFAULT_DOWNLOAD_DIR, "makedirs": True,
        "icon": "☷", "label": "本地包下载目录", "fmt": "or_unset",
    },
    {
        "key": "overwrite", "id": "overwrite",
        "title": "覆盖开关", "kind": "bool",
        "path": "download.overwrite", "dl_key": "overwrite",
        "icon": "✍️", "label": "覆盖已有文件", "fmt": "onoff",
        "on_text": "是", "off_text": "否",
        "sw_label": "覆盖已有文件",
        "sw_sub": lambda s: "当前：{}".format(
            "开启" if s.download_config.get('overwrite', False) else "关闭"),
        "pre_hint": "开启后，下载时同名文件会被重新覆盖；关闭则跳过已存在的文件。",
        "toast_tpl": "覆盖已{}",
    },
    {
        "key": "inject_manager", "id": "inject_manager",
        "title": "自动注入管理中心", "kind": "bool",
        "store": "attr", "attr": "inject_manager_site",
        "icon": "⚙️", "label": "自动注入管理接口", "fmt": "onoff",
        "on_text": "开启", "off_text": "关闭",
        "sw_label": "注入管理中心",
        "sw_sub": lambda s: "在本地化生成的配置里自动追加一个管理中心入口",
        "toast_tpl": "注入已{}",
    },
    {
        "key": "decrypt_filename", "id": "decrypt_filename",
        "title": "设置解密文件命名规则", "kind": "text",
        "store": "attr", "attr": "decrypt_filename_template",
        "hint": "支持 {name} 占位符，如 {name}_m.json",
        "icon": "✒️", "label": "解密文件命名规则", "fmt": "str",
    },
    {
        "key": "localized_filename", "id": "localized_filename",
        "title": "设置本地化主文件命名规则", "kind": "text",
        "store": "attr", "attr": "localized_filename_template",
        "hint": "支持 {name} 占位符，如 {name}.json",
        "icon": "✒️", "label": "本地化文件命名规则", "fmt": "str",
    },
    {
        "key": "max_file_size", "id": "max_file_size",
        "title": "设置最大文件大小 (MB)", "kind": "int",
        "path": "download.max_file_size_mb", "dl_key": "max_file_size_mb",
        "min": 1, "hint": "输入单文件大小限制 (MB)",
        "icon": "✂️", "label": "最大文件大小 (MB)", "fmt": "str",
    },
    {
        "key": "multipart_min_bytes", "id": "multipart_min_bytes",
        "title": "设置分块下载阈值 (KB)", "kind": "int",
        "path": "download.multipart_min_bytes_kb",
        "dl_key": "multipart_min_bytes_kb",
        "min": int(MULTIPART_MIN_BYTES_MIN / 1024),
        "hint": "超过此大小且服务端支持断点续传时启用多线程分块 (KB)",
        "icon": "⚡", "label": "分块下载阈值 (KB)", "fmt": "str",
    },
    {
        "key": "chunk_size", "id": "chunk_size",
        "title": "设置块大小 (字节)", "kind": "int",
        "path": "download.chunk_size", "dl_key": "chunk_size",
        "min": 1024, "hint": "输入下载块大小 (字节)",
        "icon": "✒️", "label": "分块文件大小 (KB)", "fmt": "str",
    },
    {
        "key": "recursive_depth", "id": "recursive_depth",
        "title": "设置递归深度", "kind": "int",
        "path": "download.recursive_depth", "dl_key": "recursive_depth",
        "min": 0, "max": 5, "hint": "输入 JSON 递归解析深度 (0-5)",
        "icon": "❓️", "label": "递归解析深度", "fmt": "str",
    },
    {
        "key": "max_workers", "id": "max_workers",
        "title": "设置下载并发数", "kind": "int",
        "path": "download.max_workers", "attr": "max_workers", "dl_key": "max_workers", "src": "attr",
        "min": 1, "max": 16, "hint": "输入最大并发数 (1-16)",
        "icon": "➕️", "label": "下载并发数", "fmt": "str",
    },
    {
        "key": "retry_total", "id": "retry_total",
        "title": "设置 HTTP 重试次数", "kind": "int",
        "path": "download.retry_total", "attr": "retry_total", "dl_key": "retry_total", "src": "attr",
        "min": 0, "max": 5, "hint": "输入重试次数 (0-5)",
        "icon": "➰️", "label": "HTTP 重试次数", "fmt": "str",
    },
    {
        "key": "timeout_connect", "id": "timeout_connect",
        "title": "设置连接超时 (秒)", "kind": "int",
        "path": "download.timeout_connect", "dl_key": "timeout_connect",
        "min": 1, "hint": "输入连接超时秒数",
        "icon": "⏱️", "label": "连接超时 (秒)", "fmt": "str",
    },
    {
        "key": "timeout_read", "id": "timeout_read",
        "title": "设置读取超时 (秒)", "kind": "int",
        "path": "download.timeout_read", "dl_key": "timeout_read",
        "min": 1, "hint": "输入读取超时秒数",
        "icon": "⏱️", "label": "读取超时 (秒)", "fmt": "str",
    },
    {
        "key": "oktv_timeout", "id": "oktv_timeout",
        "title": "设置 OKTV 切换超时 (秒)", "kind": "int",
        "store": "attr", "attr": "oktv_switch_timeout",
        "min": 1, "hint": "输入超时秒数，建议1-10",
        "icon": "⏱️", "label": "接口切换超时(秒)", "fmt": "str",
        "name": "⏱️接口切换超时(秒)",
    },
    {
        "key": "user_agent", "id": "user_agent",
        "title": "设置 User-Agent", "kind": "text",
        "path": "user_agent", "attr": "user_agent",
        "hint": "输入 User-Agent 字符串",
        "icon": "✈️", "label": "User‑Agent", "fmt": "trunc30",
    },
    {
        "key": "github_proxy", "id": "github_proxy",
        "title": "设置 GitHub 代理", "kind": "text",
        "path": "github_proxy", "dl_key": "github_proxy",
        "src": "config", "default": GITHUB_PROXY,
        "hint": "输入 GitHub 代理前缀 URL",
        "icon": "✨️", "label": "GitHub 加速代理", "fmt": "trunc30",
    },
    {
        "key": "proxy", "id": "proxy",
        "title": "设置全局代理", "kind": "text",
        "path": "proxy", "dl_key": "proxy",
        "src": "config", "default": "",
        "hint": "输入代理地址 (如 http://127.0.0.1:7890)，留空取消",
        "icon": "✈️", "label": "全局代理", "fmt": "or_unset",
    },
    {
        "key": "external_api", "id": "external_api",
        "title": "设置备用解密接口", "kind": "text",
        "path": "external_api_url", "attr": "external_api_url",
        "mirror": ["download.decrypt.external_api_url"],
        "hint": "输入外部解密API URL",
        "icon": "✴️", "label": "备用解密接口", "fmt": "trunc30",
    },
    {
        "key": "config_backup", "id": "config_backup",
        "title": "设置配置备份目录", "kind": "dir",
        "path": "config_backup_dir", "attr": "config_backup_dir",
        "normalize": "dir_slash", "makedirs": True,
        "hint": "留空则跟随本地包目录的 temp 子目录",
        "icon": "💾", "label": "配置备份目录", "fmt": "or_unset",
        "default": "",
    },
    {
        "key": "file_service", "id": "file_service",
        "title": "设置本地文件服务地址", "kind": "text",
        "path": "file_service_base", "attr": "file_service_base",
        "hint": "文件/文件夹浏览器用；留空则自动探测（推荐）",
        "icon": "📂", "label": "本地文件服务", "fmt": "or_unset",
        "default": "",
    },
    {
        "key": "proxy_port", "id": "proxy_port",
        "title": "设置内置服务端口", "kind": "int",
        "path": "proxy_port", "attr": "proxy_port",
        "min": 1, "max": 65535,
        "hint": "仅当无法自动获取端口时才用到，留空用默认 %d" % DEFAULT_PROXY_PORT,
        "icon": "🔌", "label": "内置服务端口", "fmt": "str",
        "default": DEFAULT_PROXY_PORT,
    },
    {
        "key": "incremental", "id": "incremental",
        "title": "增量更新", "kind": "bool",
        "path": "incremental_update", "attr": "incremental_update",
        "icon": "♻️", "label": "增量更新", "fmt": "onoff",
        "on_text": "已开启", "off_text": "已关闭",
        "sw_label": "增量更新",
        "sw_sub": lambda s: "再次本地化时只下载远端有变更的文件（首次本地化不受影响）",
        "toast_tpl": "增量更新已{}",
    },
    {
        "key": "localize_prefer_decrypted", "id": "localize_prefer_decrypted",
        "title": "本地化优先使用解密产物", "kind": "bool",
        "path": "localize_prefer_decrypted",
        "attr": "localize_prefer_decrypted",
        "icon": "🔗", "label": "本地化用解密数据", "fmt": "onoff",
        "on_text": "优先", "off_text": "重新拉取",
        "sw_label": "本地化优先使用解密产物",
        "sw_sub": lambda s: "本地化时直接采用解密结果（可先手工修正），"
                            "关闭则每次都从远端重新解析",
        "toast_tpl": "本地化输入源已设为：{}",
    },
    {
        "key": "log_mode", "id": "log_mode",
        "title": "日志开关与级别", "kind": "choice",
        "virtual": True,
        "opts": [("off", "关闭（不写日志）"),
                 ("error", "ERROR（仅错误）"),
                 ("warn", "WARN（错误+警告）"),
                 ("info", "INFO（常规，推荐）"),
                 ("debug", "DEBUG（全部细节）")],
        "icon": "⚡", "label": "日志开关与级别", "fmt": "log_mode",
        "pre_hint": "选「关闭」即停用文件日志；选任一级别会自动开启日志。\n"
                    "级别越高，输出越少：DEBUG 会打印逐文件的下载细节。",
    },
]

SETTING_GROUPS = {
    "log": {
        "title": "日志设置", "icon": "⚡",
        "remark": "开关与级别、日志目录",
        "keys": ["log_mode", "log_dir"],
    },
    "dirs": {
        "title": "目录管理", "icon": "☷",
        "remark": "本地包 / 日志 / 备份 三类目录，可一键统一",
        "keys": ["download_dir", "log_dir", "config_backup"],
        "extra": "unify_dirs",
    },
    "behavior": {
        "title": "下载行为", "icon": "⚙️",
        "remark": "覆盖、注入、增量、输入源",
        "keys": ["overwrite", "inject_manager",
                 "incremental", "localize_prefer_decrypted"],
    },
    "transfer": {
        "title": "下载设置", "icon": "🚀",
        "remark": "并发 / 重试 / 分块 / 深度 / 大小 / 三类超时",
        "keys": ["max_workers", "retry_total", "chunk_size",
                 "recursive_depth", "max_file_size", "multipart_min_bytes",
                 "timeout_connect", "timeout_read", "oktv_timeout"],
        "subsections": [("传输参数", ["max_workers", "retry_total",
                                      "chunk_size", "recursive_depth",
                                      "max_file_size",
                                      "multipart_min_bytes"]),
                        ("超时设置", ["timeout_connect", "timeout_read",
                                      "oktv_timeout"])],
    },
    "network": {
        "title": "网络设置", "icon": "🌐",
        "remark": "UA / 各类代理 / 备用解密 / 本地服务地址",
        "keys": ["user_agent", "github_proxy", "proxy", "external_api",
                 "file_service", "proxy_port"],
    },
    "naming": {
        "title": "文件命名", "icon": "📝",
        "remark": "解密 / 本地化产物的命名规则",
        "keys": ["decrypt_filename", "localized_filename"],
    },
}

SETTING_SPECS_BY_KEY = {s["key"]: s for s in SETTING_SPECS}
SETTING_SPECS_BY_ACTION = {"local_source_edit_" + s["key"]: s for s in SETTING_SPECS}

class _LogSentinel(object):
    __slots__ = ()
    def __repr__(self):
        return "<LOG_SENTINEL>"

_LOG_SENTINEL = _LogSentinel()

class UITheme(object):

    BRAND = "#6C63FF"
    BRAND_DEEP = "#5449E0"
    BRAND_SOFT = "#EFEDFF"
    BRAND_LINE = "#CDC7FF"

    SUCCESS = "#12B76A"
    SUCCESS_DEEP = "#0E9F62"
    SUCCESS_SOFT = "#E6F7EF"
    SUCCESS_LINE = "#B4E7D2"

    WARNING = "#F59E0B"
    WARNING_DEEP = "#D08708"
    WARNING_SOFT = "#FEF4E3"
    WARNING_LINE = "#F7DCA8"

    DANGER = "#F04438"
    DANGER_DEEP = "#D92D20"
    DANGER_SOFT = "#FEE4E2"
    DANGER_LINE = "#FACFCB"

    INFO = "#3B82F6"
    INFO_DEEP = "#2563EB"
    INFO_SOFT = "#E8F1FE"
    INFO_LINE = "#C3D9FD"

    ROW_FOCUS = "#E7E9FF"
    ROW_ICON = "#6C63FF"

    BG = "#F2F4F9"
    SURFACE = "#FFFFFF"
    SURFACE_ALT = "#F8FAFC"
    SURFACE_SUNKEN = "#F1F5F9"
    BORDER = "#E4E8F0"
    BORDER_STRONG = "#CBD5E1"

    TEXT = "#1E293B"
    TEXT_2 = "#475569"
    TEXT_3 = "#94A3B8"
    WHITE = "#FFFFFF"

    R_XS = 4.0
    R_SM = 6.0
    R_MD = 10.0
    R_LG = 14.0
    R_XL = 18.0
    R_PILL = 999.0

    S_XXS = 2.0
    S_XS = 4.0
    S_SM = 8.0
    S_MD = 12.0
    S_LG = 16.0
    S_XL = 24.0

    FS_MICRO = 9.5
    FS_CAPTION = 11.0
    FS_BODY = 12.5
    FS_BODY_LG = 13.5
    FS_SUBTITLE = 15.0
    FS_TITLE = 17.0

    H_BTN_SM = 34.0
    H_BTN = 42.0
    H_BTN_LG = 48.0
    H_INPUT = 44.0

    STYLES = {
        "primary": (BRAND, WHITE, BRAND, BRAND_DEEP),
        "success": (SUCCESS, WHITE, SUCCESS, SUCCESS_DEEP),
        "danger": (DANGER, WHITE, DANGER, DANGER_DEEP),
        "warning": (WARNING, WHITE, WARNING, WARNING_DEEP),
        "info": (INFO, WHITE, INFO, INFO_DEEP),
        "secondary": (SURFACE_SUNKEN, TEXT_2, BORDER, "#E2E8F0"),
        "outline": (SURFACE, BRAND, BRAND_LINE, BRAND_SOFT),
        "ghost": (SURFACE, TEXT_2, BORDER, SURFACE_SUNKEN),
        "soft_brand": (BRAND_SOFT, BRAND, BRAND_LINE, "#E3E0FF"),
        "soft_danger": (DANGER_SOFT, DANGER, DANGER_LINE, "#FCD9D6"),
        "soft_success": (SUCCESS_SOFT, SUCCESS, SUCCESS_LINE, "#CFEEDF"),
    }

    LEGACY_COLOR_MAP = {
        "#6C63FF": "primary",
        "#10B981": "success",
        "#EF4444": "danger",
        "#F59E0B": "warning",
        "#3B82F6": "info",
        "#F1F5F9": "secondary",
        "#F8FAFC": "ghost",
        "#FFFFFF": "ghost",
        "#2C3E50": "secondary",
        "#7F8C8D": "secondary",
    }

class UIKit(object):

    def __init__(self, act, sink=None, logger=None):
        self.act = act
        self.sink = sink if sink is not None else []
        self.logger = logger
        self._java_ok = True
        try:
            from java import jclass
            self._jclass = jclass
        except Exception:
            self._java_ok = False
            self._jclass = None

        self.density = 1.0
        self.w_px = 1080
        self.h_px = 1920
        try:
            m = act.getResources().getDisplayMetrics()
            self.density = float(m.density) or 1.0
            self.w_px = int(m.widthPixels)
            self.h_px = int(m.heightPixels)
        except Exception:
            self.density = 3.0
            self.w_px = 1080
            self.h_px = 1920
        self.w_dp = self.w_px / self.density
        self.h_dp = self.h_px / self.density
        self.landscape = self.w_px > self.h_px
        self.kind = self._detect_kind(act)
        self.scale = self._compute_scale()
        if self.kind == "tv":
            self.max_cols = 4
        elif self.kind == "tablet":
            self.max_cols = 4
        elif self.landscape:
            self.max_cols = 4
        else:
            self.max_cols = 3
        if self.kind == "tv":
            self.max_w_dp, self.max_h_dp = 880.0, 660.0
        elif self.kind == "tablet":
            self.max_w_dp, self.max_h_dp = 660.0, 700.0
        else:
            self.max_w_dp, self.max_h_dp = 470.0, 720.0
        self.tv_focus = (self.kind == "tv")

    def _detect_kind(self, act):
        try:
            svc = act.getSystemService("uimode")
            if svc is not None and int(svc.getCurrentModeType()) == 4:
                return "tv"
        except Exception:
            pass
        try:
            cfg = act.getResources().getConfiguration()
            if int(getattr(cfg, "uiMode", 0) & 15) == 4:
                return "tv"
        except Exception:
            pass
        if self.w_dp >= 900 and self.landscape:
            return "tv"
        if self.w_dp >= 600:
            return "tablet"
        return "phone"

    def _compute_scale(self):
        short_dp = min(self.w_dp, self.h_dp)
        s = short_dp / 360.0
        s = min(max(s, 0.90), 1.20)
        if self.kind == "tv":
            s = min(max(s * 1.30, 1.22), 1.60)
        elif self.kind == "tablet":
            s = min(max(s * 1.08, 1.00), 1.28)
        return s

    def j(self, name):
        if not self._java_ok:
            return None
        return self._jclass(name)

    def dp(self, value):
        try:
            TV = self.j("android.util.TypedValue")
            return int(TV.applyDimension(
                TV.COMPLEX_UNIT_DIP, float(value),
                self.act.getResources().getDisplayMetrics()))
        except Exception:
            return int(float(value) * self.density)

    def color(self, hex_str):
        try:
            return self.j("android.graphics.Color").parseColor(str(hex_str))
        except Exception:
            return 0

    def fs(self, size):
        return float(size) * self.scale

    def gravity(self):
        return self.j("android.view.Gravity")

    def typeface(self):
        return self.j("android.graphics.Typeface")

    def _ellipsize(self, view):
        try:
            TA = self.j("android.text.TextUtils$TruncateAt")
            if TA is not None:
                view.setEllipsize(TA.END)
        except Exception:
            pass

    def lp(self, w=-1, h=-2, weight=0.0, margins=None):
        LP = self.j("android.widget.LinearLayout$LayoutParams")
        p = LP(w, h, float(weight))
        if margins:
            l, t, r, b = margins
            p.setMargins(self.dp(l), self.dp(t), self.dp(r), self.dp(b))
        return p

    def shape(self, solid, radius_dp=UITheme.R_MD, stroke_dp=0.0, stroke=None):
        try:
            GD = self.j("android.graphics.drawable.GradientDrawable")
            d = GD()
            d.setShape(GD.RECTANGLE)
            d.setCornerRadius(float(self.dp(radius_dp)))
            d.setColor(self.color(solid))
            d.setStroke(int(self.dp(stroke_dp)), self.color(stroke if stroke else solid))
            return d
        except Exception:
            return None

    def pressable(self, normal, pressed, radius_dp=UITheme.R_MD,
                  stroke_dp=0.0, stroke=None):
        try:
            SLD = self.j("android.graphics.drawable.StateListDrawable")
            RA = self.j("android.R$attr")
            st_pressed = int(RA.state_pressed)
            st_focused = int(RA.state_focused)
            sld = SLD()
            sld.addState([st_pressed], self.shape(pressed, radius_dp, stroke_dp, stroke))
            sld.addState([st_focused], self.shape(pressed, radius_dp, stroke_dp, stroke))
            sld.addState([-st_pressed], self.shape(normal, radius_dp, stroke_dp, stroke))
            return sld
        except Exception:
            return self.shape(normal, radius_dp, stroke_dp, stroke)

    def _set_bg(self, view, drawable):
        if drawable is None:
            return
        try:
            view.setBackgroundDrawable(drawable)
        except Exception:
            try:
                view.setBackground(drawable)
            except Exception:
                pass

    def _box(self, vertical, pad=None, bg=None, radius=0.0, stroke_dp=0.0, stroke=None):
        LinearLayout = self.j("android.widget.LinearLayout")
        v = LinearLayout(self.act)
        v.setOrientation(LinearLayout.VERTICAL if vertical else LinearLayout.HORIZONTAL)
        if bg:
            self._set_bg(v, self.shape(bg, radius, stroke_dp, stroke))
        if pad:
            if isinstance(pad, (list, tuple)):
                l, t, r, b = pad
            else:
                l = t = r = b = pad
            v.setPadding(self.dp(l), self.dp(t), self.dp(r), self.dp(b))
        return v

    def vbox(self, pad=None, bg=None, radius=0.0, stroke_dp=0.0, stroke=None):
        return self._box(True, pad, bg, radius, stroke_dp, stroke)

    def hbox(self, pad=None, bg=None, radius=0.0, stroke_dp=0.0, stroke=None):
        return self._box(False, pad, bg, radius, stroke_dp, stroke)

    def card(self, pad=UITheme.S_MD, bg=UITheme.SURFACE, radius=UITheme.R_LG,
             stroke=UITheme.BORDER, margin=(0.0, 0.0, 0.0, UITheme.S_SM)):
        c = self.vbox(pad=pad, bg=bg, radius=radius, stroke_dp=1.0, stroke=stroke)
        c.setLayoutParams(self.lp(-1, -2, 0.0, margin))
        return c

    def scroll(self, view, fill=True):
        ScrollView = self.j("android.widget.ScrollView")
        sv = ScrollView(self.act)
        try:
            sv.setFillViewport(bool(fill))
        except Exception:
            pass
        sv.addView(view, self.lp(-1, -2))
        return sv

    def divider(self, top=0.0, bottom=0.0, color=UITheme.BORDER, height_dp=1.0):
        TextView = self.j("android.widget.TextView")
        v = TextView(self.act)
        v.setBackgroundColor(self.color(color))
        v.setLayoutParams(self.lp(-1, self.dp(height_dp), 0.0, (0.0, top, 0.0, bottom)))
        return v

    def text(self, txt, size=UITheme.FS_BODY, color=UITheme.TEXT, bold=False,
             gravity=None, single_line=False, max_lines=0, mono=False,
             line_spacing=1.25, selectable=False, pad=None):
        TextView = self.j("android.widget.TextView")
        tv = TextView(self.act)
        tv.setText("" if txt is None else str(txt))
        tv.setTextSize(self.fs(size))
        tv.setTextColor(self.color(color))
        TF = self.typeface()
        if TF is not None:
            try:
                if mono:
                    tv.setTypeface(TF.MONOSPACE)
                elif bold:
                    tv.setTypeface(TF.DEFAULT_BOLD)
                else:
                    tv.setTypeface(TF.DEFAULT)
            except Exception:
                pass
        try:
            tv.setIncludeFontPadding(False)
        except Exception:
            pass
        try:
            tv.setLineSpacing(0.0, float(line_spacing))
        except Exception:
            pass
        if gravity is not None:
            tv.setGravity(gravity)
        if single_line:
            tv.setSingleLine(True)
            self._ellipsize(tv)
        elif max_lines:
            tv.setSingleLine(False)
            tv.setMaxLines(int(max_lines))
            self._ellipsize(tv)
        else:
            tv.setSingleLine(False)
        if selectable:
            try:
                tv.setTextIsSelectable(True)
            except Exception:
                pass
        if pad:
            l, t, r, b = pad
            tv.setPadding(self.dp(l), self.dp(t), self.dp(r), self.dp(b))
        return tv

    def title(self, txt):
        G = self.gravity()
        return self.text(txt, size=UITheme.FS_TITLE, color=UITheme.TEXT, bold=True,
                         gravity=G.CENTER_VERTICAL if G else None, single_line=True)

    def section_title(self, txt, hint=None):
        G = self.gravity()
        box = self.vbox(pad=(0.0, UITheme.S_SM, 0.0, 0.0))
        box.setLayoutParams(self.lp(-1, -2))

        row = self.hbox()
        row.setLayoutParams(self.lp(-1, -2))
        if G:
            row.setGravity(G.CENTER_VERTICAL)

        pill = self.j("android.widget.TextView")(self.act)
        pill.setBackgroundColor(self.color(UITheme.BRAND))
        pill.setLayoutParams(self.lp(self.dp(3), self.dp(15), 0.0, (0.0, 0.0, UITheme.S_SM, 0.0)))
        self._set_bg(pill, self.shape(UITheme.BRAND, UITheme.R_XS))
        row.addView(pill)

        tv = self.text(txt, size=UITheme.FS_SUBTITLE, color=UITheme.TEXT, bold=True,
                       gravity=G.CENTER_VERTICAL if G else None, max_lines=2)
        tv.setLayoutParams(self.lp(0, -2, 1.0))
        row.addView(tv)
        box.addView(row, self.lp(-1, -2))

        if hint:
            hv = self.text(hint, size=UITheme.FS_CAPTION, color=UITheme.TEXT_3,
                           line_spacing=1.35,
                           pad=(self.dp(3) + self.dp(UITheme.S_SM), UITheme.S_XS, 0.0, 0.0))
            box.addView(hv, self.lp(-1, -2, 0.0, (0.0, UITheme.S_XXS, 0.0, 0.0)))
        return box

    def field_label(self, txt):
        return self.text(txt, size=UITheme.FS_CAPTION, color=UITheme.TEXT_2, bold=True,
                         max_lines=2,
                         pad=(0.0, UITheme.S_XS, 0.0, UITheme.S_XS))

    def hint(self, txt, max_lines=6):
        return self.text(txt, size=UITheme.FS_CAPTION, color=UITheme.TEXT_3,
                         line_spacing=1.4, max_lines=max_lines,
                         pad=(0.0, 0.0, 0.0, UITheme.S_XS))

    def empty(self, msg="暂无数据", icon="📭"):
        box = self.vbox(pad=(UITheme.S_LG, UITheme.S_XL, UITheme.S_LG, UITheme.S_XL),
                        bg=UITheme.SURFACE_ALT, radius=UITheme.R_LG,
                        stroke_dp=1.0, stroke=UITheme.BORDER)
        box.setLayoutParams(self.lp(-1, -2, 0.0, (0.0, UITheme.S_XS, 0.0, UITheme.S_XS)))
        G = self.gravity()
        box.addView(self.text(icon, size=UITheme.FS_TITLE + 4, color=UITheme.TEXT_3,
                              gravity=G.CENTER if G else None),
                    self.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_XS)))
        box.addView(self.text(msg, size=UITheme.FS_BODY, color=UITheme.TEXT_3,
                              gravity=G.CENTER if G else None, line_spacing=1.4),
                    self.lp(-1, -2))
        return box

    def set_tv_focus(self, enabled):
        self.tv_focus = bool(enabled)
        return self.tv_focus

    def apply_focus(self, view, clickable=True):
        if view is None:
            return view
        try:
            if self.tv_focus:
                view.setFocusable(True)
                view.setFocusableInTouchMode(True)
            else:
                view.setFocusable(False)
                view.setFocusableInTouchMode(False)
            view.setClickable(bool(clickable))
        except Exception:
            pass
        return view

    def row_metrics(self):
        h = min(max(46.0 * self.scale, 42.0), 84.0)
        icon = min(max(26.0 * self.scale, 24.0), 48.0)
        return h, icon

    def list_min_rows(self, height_ratio=0.85, reserve_dp=170.0):
        h_dp, _icon = self.row_metrics()
        if self.kind == "tv":
            reserve_dp += 60.0
        avail = min(self.h_dp * float(height_ratio or 0.85), self.max_h_dp) - reserve_dp
        n = int(avail / max(h_dp, 1.0))
        return max(5, min(n, 14))

    def filler_row(self, idx=0, zebra=True, radius=UITheme.R_MD):
        h_dp, _icon = self.row_metrics()
        v = self.hbox()
        v.setLayoutParams(self.lp(-1, -2))
        try:
            v.setMinimumHeight(self.dp(h_dp))
        except Exception:
            pass
        if zebra:
            self._set_bg(v, self.shape(
                UITheme.SURFACE_ALT if (idx % 2 == 0) else UITheme.SURFACE,
                radius))
        try:
            v.setFocusable(False)
            v.setFocusableInTouchMode(False)
            v.setClickable(False)
        except Exception:
            pass
        return v

    def fill_rows(self, list_box, used_rows, min_rows=None, height_ratio=0.85):
        if list_box is None:
            return 0
        if min_rows is None:
            min_rows = self.list_min_rows(height_ratio)
        n = 0
        for k in range(int(used_rows), int(min_rows)):
            list_box.addView(self.filler_row(k),
                             self.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_XS)))
            n += 1
        return n

    def fill_spring(self, list_box, idx):
        if list_box is None:
            return None
        v = self.filler_row(idx)
        try:
            v.setFocusable(False)
            v.setFocusableInTouchMode(False)
            v.setClickable(False)
        except Exception:
            pass
        list_box.addView(v, self.lp(-1, 0, 1.0, (0.0, 0.0, 0.0, UITheme.S_XS)))
        return v

    def measure_fill_rows(self, scroller, list_box, gap_dp=UITheme.S_XS,
                          probe=None, fallback_row_px=None):
        try:
            vh = scroller.getHeight()
            if not vh or vh <= 0:
                return None
            rh = 0
            if probe is not None:
                try:
                    rh = probe.getHeight() or 0
                except Exception:
                    rh = 0
            if not rh and fallback_row_px:
                rh = fallback_row_px
            if not rh or rh <= 0:
                rh = self.dp(self.row_metrics()[0])
            if rh <= 0:
                return None
            gap = max(int(self.dp(gap_dp)), 0)
            n = int((vh + gap) // (rh + gap))
            return max(1, n)
        except Exception:
            return None

    def _row_bg(self, idx, zebra=True, radius=UITheme.R_MD):
        normal = (UITheme.SURFACE_ALT if (idx % 2 == 0) else UITheme.SURFACE) if zebra \
            else UITheme.SURFACE
        return self.pressable(normal, UITheme.ROW_FOCUS, radius, 1.0, UITheme.BORDER)

    def row(self, icon=None, title="", subtitle=None, trailing=None,
            on_click=None, on_long_click=None, idx=0, zebra=True,
            title_color=None, title_bold=False, radius=UITheme.R_MD,
            icon_color=UITheme.ROW_ICON, min_height=None, disabled=False):
        G = self.gravity()
        h_dp, icon_dp = self.row_metrics()
        h_px = self.dp(min_height if min_height else h_dp)

        row = self.hbox(pad=(UITheme.S_MD, UITheme.S_XS, UITheme.S_MD, UITheme.S_XS))
        row.setLayoutParams(self.lp(-1, -2))
        if G:
            row.setGravity(G.CENTER_VERTICAL)
        try:
            row.setMinimumHeight(h_px)
        except Exception:
            pass

        if icon:
            iv = self.text(icon, size=UITheme.FS_BODY_LG + 1.0, color=icon_color,
                           gravity=G.CENTER if G else None, single_line=True)
            iv.setLayoutParams(self.lp(self.dp(icon_dp), -2))
            row.addView(iv)

        mid = self.vbox()
        mid.setLayoutParams(self.lp(
            0, -2, 1.0,
            (UITheme.S_SM if icon else 0.0, 0.0, UITheme.S_SM, 0.0)))
        if G:
            mid.setGravity(G.CENTER_VERTICAL)
        mid.addView(
            self.text(title, size=UITheme.FS_BODY if subtitle else UITheme.FS_BODY_LG,
                      color=title_color or (UITheme.TEXT_3 if disabled else UITheme.TEXT),
                      bold=title_bold, max_lines=2),
            self.lp(-1, -2))
        if subtitle:
            mid.addView(self.text(subtitle, size=UITheme.FS_CAPTION, color=UITheme.TEXT_3,
                                  max_lines=2,
                                  pad=(0.0, UITheme.S_XXS, 0.0, 0.0)), self.lp(-1, -2))
        row.addView(mid)

        if trailing:
            tv = self.text(trailing, size=UITheme.FS_CAPTION, color=UITheme.TEXT_3,
                           single_line=True)
            try:
                tv.setGravity((G.CENTER_VERTICAL | G.END) if G else 0)
            except Exception:
                pass
            row.addView(tv, self.lp(-2, -2, 0.0, (UITheme.S_SM, 0.0, 0.0, 0.0)))

        self._set_bg(row, self._row_bg(idx, zebra, radius))

        if on_click is not None:
            self.bind_click(row, on_click)
        if on_long_click is not None:
            try:
                row.setOnLongClickListener(self._on_long_click(on_long_click))
            except Exception:
                pass

        self.apply_focus(row, on_click is not None)
        return row

    def input(self, hint="", value="", multiline=False, mono=False,
              min_lines=0, max_lines=0, min_height=None):
        EditText = self.j("android.widget.EditText")
        et = EditText(self.act)
        et.setHint("" if hint is None else str(hint))
        et.setHintTextColor(self.color(UITheme.TEXT_3))
        et.setText("" if value is None else str(value))
        et.setTextSize(self.fs(UITheme.FS_BODY))
        et.setTextColor(self.color(UITheme.TEXT))
        TF = self.typeface()
        if TF is not None:
            try:
                et.setTypeface(TF.MONOSPACE if mono else TF.DEFAULT)
            except Exception:
                pass
        et.setPadding(self.dp(UITheme.S_MD), self.dp(UITheme.S_SM + 2),
                      self.dp(UITheme.S_MD), self.dp(UITheme.S_SM + 2))
        G = self.gravity()
        if multiline:
            et.setSingleLine(False)
            if min_lines:
                et.setMinLines(int(min_lines))
            if max_lines:
                et.setMaxLines(int(max_lines))
            if G:
                et.setGravity(G.TOP | G.START)
            try:
                et.setOverScrollMode(2)
            except Exception:
                pass
            self._ellipsize(et)
        else:
            et.setSingleLine(True)
            self._ellipsize(et)
            if G:
                et.setGravity(G.CENTER_VERTICAL | G.START)
        try:
            if min_height:
                et.setMinHeight(self.dp(min_height))
            elif not multiline:
                et.setMinHeight(self.dp(UITheme.H_INPUT))
        except Exception:
            pass
        self._set_bg(et, self.shape(UITheme.SURFACE_ALT, UITheme.R_MD, 1.0, UITheme.BORDER))
        try:
            if value:
                et.setSelection(len(str(value)))
        except Exception:
            pass
        return et

    def toggle(self, label, checked=False, on_change=None, on_long_click=None, weight=1.0):
        Switch = self.j("android.widget.Switch")
        sw = Switch(self.act)
        sw.setText("" if label is None else str(label))
        sw.setTextSize(self.fs(UITheme.FS_BODY))
        sw.setTextColor(self.color(UITheme.TEXT))
        TF = self.typeface()
        if TF is not None:
            try:
                sw.setTypeface(TF.DEFAULT)
            except Exception:
                pass
        sw.setChecked(bool(checked))
        sw.setSingleLine(True)
        self._ellipsize(sw)
        p = self.dp(UITheme.S_XS)
        sw.setPadding(p, p, p, p)
        if on_change is not None:
            sw.setOnCheckedChangeListener(self._on_checked(on_change))
        if on_long_click is not None:
            sw.setOnLongClickListener(self._on_long_click(on_long_click))
        self.apply_focus(sw, True)
        if weight:
            sw.setLayoutParams(self.lp(0, -2, float(weight)))
        self.apply_focus(sw, True)
        return sw

    def switch_card(self, label, sub=None, checked=False, on_change=None,
                    on_long_click=None, state_out=None):
        G = self.gravity()
        card = self.card(pad=(UITheme.S_MD, UITheme.S_SM, UITheme.S_MD, UITheme.S_SM))
        row = self.hbox()
        row.setLayoutParams(self.lp(-1, -2))
        if G:
            row.setGravity(G.CENTER_VERTICAL)

        text_box = self.vbox()
        text_box.setLayoutParams(self.lp(0, -2, 1.0, (0.0, 0.0, UITheme.S_SM, 0.0)))
        text_box.addView(self.text(label, size=UITheme.FS_BODY_LG, color=UITheme.TEXT,
                                   max_lines=2), self.lp(-1, -2))
        if sub:
            text_box.addView(self.text(sub, size=UITheme.FS_CAPTION, color=UITheme.TEXT_3,
                                       max_lines=3,
                                       pad=(0.0, UITheme.S_XXS, 0.0, 0.0)), self.lp(-1, -2))
        row.addView(text_box)

        sw = self.toggle("", checked, on_change, on_long_click, weight=0.0)
        row.addView(sw)
        card.addView(row, self.lp(-1, -2))
        if isinstance(state_out, dict):
            state_out["switch"] = sw
        return card

    def button(self, label, style="secondary", on_click=None, dialog_ref=None, size="md"):
        Button = self.j("android.widget.Button")
        btn = Button(self.act)
        bg_c, tx_c, line_c, press_c = UITheme.STYLES.get(style, UITheme.STYLES["secondary"])
        if size == "sm":
            h = UITheme.H_BTN_SM
            radius = UITheme.R_SM
            font = UITheme.FS_CAPTION + 0.5
            min_w = 60.0
        elif size == "lg":
            h = UITheme.H_BTN_LG
            radius = UITheme.R_MD
            font = UITheme.FS_BODY_LG
            min_w = 96.0
        else:
            h = UITheme.H_BTN
            radius = UITheme.R_MD
            font = UITheme.FS_BODY
            min_w = 88.0

        btn.setText("" if label is None else str(label))
        try:
            btn.setAllCaps(False)
        except Exception:
            pass
        btn.setTextSize(self.fs(font))
        TF = self.typeface()
        if TF is not None:
            try:
                solid = style in ("primary", "success", "danger", "warning", "info")
                btn.setTypeface(TF.DEFAULT_BOLD if solid else TF.DEFAULT)
            except Exception:
                pass
        btn.setTextColor(self.color(tx_c))
        try:
            btn.setMinHeight(self.dp(h))
            btn.setMinimumHeight(self.dp(h))
            btn.setMinWidth(self.dp(min_w))
            btn.setMinimumWidth(self.dp(min_w))
        except Exception:
            pass
        pad_h = self.dp(UITheme.S_MD if size != "sm" else UITheme.S_SM)
        btn.setPadding(pad_h, 0, pad_h, 0)
        btn.setSingleLine(True)
        self._ellipsize(btn)
        G = self.gravity()
        if G:
            btn.setGravity(G.CENTER)
        self._set_bg(btn, self.pressable(bg_c, press_c, radius, 1.0, line_c))
        if on_click is not None or dialog_ref is not None:
            btn.setOnClickListener(self._on_click(on_click, dialog_ref))
        self.apply_focus(btn, on_click is not None or dialog_ref is not None)
        return btn

    def button_bar(self, specs, size="md", per_row=None, gap=UITheme.S_XS):
        if not specs:
            return None
        n = len(specs)
        cols = per_row or self._best_cols(n, self.max_cols)
        rows = max(1, (n + cols - 1) // cols)
        base, rem = divmod(n, rows)
        h_px = self.dp({"sm": UITheme.H_BTN_SM, "lg": UITheme.H_BTN_LG}.get(size, UITheme.H_BTN))
        outer = self.vbox()
        outer.setLayoutParams(self.lp(-1, -2))
        i = 0
        for r in range(rows):
            chunk = specs[i:i + base + (1 if r < rem else 0)]
            row = self.hbox()
            row.setLayoutParams(self.lp(-1, -2, 0.0,
                                         (0.0, 0.0 if i == 0 else gap, 0.0, 0.0)))
            G = self.gravity()
            if G:
                row.setGravity(G.CENTER)
            for k, spec in enumerate(chunk):
                style = self.spec_style(spec)
                btn = self.button(spec.get("text", ""), style,
                                  spec.get("callback"), spec.get("dialog_ref"), size)
                blp = self.lp(0, h_px, 1.0)
                if k > 0:
                    blp.setMargins(self.dp(gap), 0, 0, 0)
                row.addView(btn, blp)
            outer.addView(row, self.lp(-1, -2))
            i += len(chunk)
        return outer

    def _best_cols(self, n, max_cols):
        if n <= 0:
            return 1
        return min(max_cols, n)

    @staticmethod
    def spec_style(spec):
        if not isinstance(spec, dict):
            return "secondary"
        if spec.get("style"):
            return spec["style"]
        c = str(spec.get("color") or "").strip().upper()
        if c in UITheme.LEGACY_COLOR_MAP:
            return UITheme.LEGACY_COLOR_MAP[c]
        return "primary" if spec.get("is_primary") else "secondary"

    def _on_click(self, cb, dialog_ref=None):
        from java import jclass, dynamic_proxy
        OCL = jclass("android.view.View$OnClickListener")

        class _Click(dynamic_proxy(OCL)):
            def __init__(self):
                super().__init__()

            def onClick(self, v):
                if dialog_ref is not None and isinstance(dialog_ref, dict):
                    d = dialog_ref.get("dialog")
                    if d is not None:
                        try:
                            d.dismiss()
                        except Exception:
                            pass
                if not cb:
                    return
                try:
                    cb()
                    return
                except TypeError as e:
                    if "positional argument" not in str(e):
                        self._report_cb_error(e)
                        return
                except Exception as e:
                    self._report_cb_error(e)
                    return
                try:
                    cb(v)
                except Exception as e2:
                    self._report_cb_error(e2)

        listener = _Click()
        self.sink.append(listener)
        return listener

    def _click(self, cb, dialog_ref=None):
        return self._on_click(cb, dialog_ref)

    def _report_cb_error(self, e):
        try:
            log = getattr(self, "logger", None)
            if log is not None:
                log("UI 回调异常: {}".format(e), level='error')
        except Exception:
            pass
        try:
            traceback.print_exc()
        except Exception:
            pass

    def _on_long_click(self, cb):
        from java import jclass, dynamic_proxy
        OLCL = jclass("android.view.View$OnLongClickListener")

        class _Long(dynamic_proxy(OLCL)):
            def __init__(self):
                super().__init__()

            def onLongClick(self, v):
                try:
                    return bool(cb())
                except Exception:
                    return False

        listener = _Long()
        self.sink.append(listener)
        return listener

    def _on_checked(self, cb):
        from java import jclass, dynamic_proxy
        CCL = jclass("android.widget.CompoundButton$OnCheckedChangeListener")

        class _Checked(dynamic_proxy(CCL)):
            def __init__(self):
                super().__init__()

            def onCheckedChanged(self, buttonView, isChecked):
                try:
                    cb(bool(isChecked))
                except Exception:
                    traceback.print_exc()

        listener = _Checked()
        self.sink.append(listener)
        return listener

    def post(self, view, fn):
        if view is None:
            return None
        try:
            from java import jclass, dynamic_proxy
            from java.lang import Runnable

            class _Run(dynamic_proxy(Runnable)):
                def __init__(self):
                    super().__init__()

                def run(self):
                    try:
                        fn()
                    except Exception:
                        traceback.print_exc()

            r = _Run()
            self.sink.append(r)
            view.post(r)
            return r
        except Exception:
            return None

    def on_layout_ready(self, view, cb, max_times=12):
        if view is None or cb is None:
            return None
        try:
            from java import jclass, dynamic_proxy
            L = jclass("android.view.ViewTreeObserver$OnGlobalLayoutListener")

            class _L(dynamic_proxy(L)):
                def __init__(self):
                    super().__init__()
                    self.n = 0

                def onGlobalLayout(self):
                    try:
                        self.n += 1
                        cb()
                    except Exception:
                        traceback.print_exc()
                    if self.n >= int(max_times):
                        try:
                            vto = view.getViewTreeObserver()
                            try:
                                vto.removeOnGlobalLayoutListener(self)
                            except Exception:
                                vto.removeGlobalOnLayoutListener(self)
                        except Exception:
                            pass

            listener = _L()
            self.sink.append(listener)
            view.getViewTreeObserver().addOnGlobalLayoutListener(listener)
            return listener
        except Exception:
            return None

    def bind_click(self, view, cb, dialog_ref=None):
        if view is None:
            return None
        listener = self._on_click(cb, dialog_ref)
        view.setOnClickListener(listener)
        self.apply_focus(view, True)
        return listener

    def toast(self, msg, long=False):
        try:
            Toast = self.j("android.widget.Toast")
            Toast.makeText(self.act, str(msg),
                           Toast.LENGTH_LONG if long else Toast.LENGTH_SHORT).show()
        except Exception:
            pass

    def copy(self, text, label="文本"):
        try:
            ClipData = self.j("android.content.ClipData")
            cm = None
            try:
                cm = self.act.getSystemService(self.act.CLIPBOARD_SERVICE)
            except Exception:
                cm = None
            if cm is None:
                cm = self.act.getSystemService("clipboard")
            if cm is None:
                return False
            cm.setPrimaryClip(ClipData.newPlainText(str(label), str(text)))
            return True
        except Exception:
            return False

    def dialog(self, title=None, content=None, buttons=None, width_ratio=0.92,
               height_ratio=0.85, back_callback=None, scroll=True, on_dismiss=None,
               closable=True):
        Builder = self.j("android.app.AlertDialog$Builder")
        holder = {"dialog": None}

        normalized = []
        for spec in (buttons or []):
            if isinstance(spec, dict):
                spec = dict(spec)
                if spec.get("dismiss", True):
                    spec["dialog_ref"] = holder
            normalized.append(spec)
        buttons = normalized or None

        root = self.vbox(bg=UITheme.SURFACE, radius=UITheme.R_XL,
                         stroke_dp=1.0, stroke=UITheme.BORDER)
        root.setLayoutParams(self.lp(-1, -1 if (height_ratio and height_ratio > 0) else -2))

        if title:
            G = self.gravity()
            header = self.hbox(pad=(UITheme.S_LG, UITheme.S_MD, UITheme.S_LG, UITheme.S_LG))
            header.setLayoutParams(self.lp(-1, -2))
            if G:
                header.setGravity(G.CENTER_VERTICAL)

            pill = self.j("android.widget.TextView")(self.act)
            self._set_bg(pill, self.shape(UITheme.BRAND, UITheme.R_XS))
            pill.setLayoutParams(self.lp(self.dp(4), self.dp(18), 0.0,
                                         (0.0, 0.0, UITheme.S_SM, 0.0)))
            header.addView(pill)

            tv = self.text(title, size=UITheme.FS_TITLE, color=UITheme.TEXT, bold=True,
                           gravity=G.CENTER_VERTICAL if G else None, max_lines=2)
            tv.setLayoutParams(self.lp(0, -2, 1.0))
            header.addView(tv)

            if back_callback:
                back = self.button("返回", "ghost", back_callback, holder, size="sm")
                back.setLayoutParams(self.lp(-2, -2, 0.0, (0.0, 0.0, UITheme.S_XS, 0.0)))
                header.addView(back)
            if closable:
                close = self.button("✕", "ghost", None, holder, size="sm")
                close.setLayoutParams(self.lp(self.dp(UITheme.H_BTN_SM),
                                              self.dp(UITheme.H_BTN_SM)))
                header.addView(close)
            root.addView(header, self.lp(-1, -2))
            root.addView(self.divider(color=UITheme.BORDER))

        if content is not None:
            body = content
            if scroll:
                body = self.scroll(content)
            body.setPadding(self.dp(UITheme.S_LG), self.dp(UITheme.S_MD),
                            self.dp(UITheme.S_LG), self.dp(UITheme.S_MD))
            root.addView(body, self.lp(-1, 0, 1.0))

        if buttons:
            root.addView(self.divider(color=UITheme.BORDER))
            footer = self.vbox(pad=(UITheme.S_LG, UITheme.S_MD, UITheme.S_LG, UITheme.S_LG))
            footer.setLayoutParams(self.lp(-1, -2))
            bar = self.button_bar(buttons, size="md")
            if bar is not None:
                footer.addView(bar, self.lp(-1, -2))
            root.addView(footer, self.lp(-1, -2))

        builder = Builder(self.act)
        builder.setView(root)
        dialog = builder.create()
        try:
            dialog.setCancelable(True)
        except Exception:
            pass
        holder["dialog"] = dialog

        if on_dismiss is not None:
            from android.content import DialogInterface
            from java import dynamic_proxy

            class _Dismiss(dynamic_proxy(DialogInterface.OnDismissListener)):
                def __init__(self, cb):
                    super().__init__()
                    self.cb = cb

                def onDismiss(self, d):
                    try:
                        self.cb()
                    except Exception:
                        traceback.print_exc()

            dl = _Dismiss(on_dismiss)
            self.sink.append(dl)
            dialog.setOnDismissListener(dl)

        self._apply_window_size(dialog, width_ratio, height_ratio)
        return dialog

    def _apply_window_size(self, dialog, width_ratio, height_ratio):
        try:
            window = dialog.getWindow()
            if window is None:
                return
            try:
                CD = self.j("android.graphics.drawable.ColorDrawable")
                window.setBackgroundDrawable(CD(0))
            except Exception:
                pass
            if width_ratio and width_ratio > 0:
                w = min(int(self.w_px * float(width_ratio)), self.dp(self.max_w_dp))
                w = min(w, max(self.w_px - self.dp(16), self.dp(200)))
            else:
                w = -2
            if height_ratio and height_ratio > 0:
                h = min(int(self.h_px * float(height_ratio)), self.dp(self.max_h_dp))
                h = min(h, max(self.h_px - self.dp(16), self.dp(200)))
            else:
                h = -2
            window.setLayout(w, h)
        except Exception:
            pass

_HAS_AES = False
_AES_MODE = None
try:
    from Crypto.Cipher import AES as _AES_IMPL
    _AES_MODE = 'pycryptodome'
    _HAS_AES = True
except ImportError:
    try:
        import pyaes as _AES_IMPL
        _AES_MODE = 'pyaes'
        _HAS_AES = True
    except ImportError:
        pass

def _strip_pkcs7(d):
    if d:
        p = d[-1]
        if 0 < p <= 16 and d[-p:] == bytes([p]) * p:
            return d[:-p]
    return d

def _contains_special_strings(response):
    if not isinstance(response, str):
        return False
    return bool(re.search(r'sites|genre|EXTINF', response))

def _extract_text(response_no_spaces):
    trimmed = response_no_spaces.rstrip('*')
    pos = trimmed.rfind('**')
    if pos != -1:
        return trimmed[pos + 2:]
    return trimmed

def _extract_encryption_params(s):
    prefix = "2423"
    suffix = "2324"
    suffix_pos = s.find(suffix)
    if suffix_pos == -1:
        return None
    pwd_mix = s[:suffix_pos + len(suffix)]
    if len(s) < 26:
        return None
    roundtime_in_hax = s[-26:]
    encrypted_text = s[len(pwd_mix):-26]
    pwd_in_hax = pwd_mix[len(prefix):-len(suffix)]
    return {
        'pwdInHax': pwd_in_hax,
        'roundtimeInHax': roundtime_in_hax,
        'encryptedText': encrypted_text
    }

def _decrypt_aes(encrypted_text_hex, pwd_in_hax, roundtime_in_hax):
    if not _HAS_AES:
        return None
    try:
        round_time = bytes.fromhex(roundtime_in_hax)
        pwd = bytes.fromhex(pwd_in_hax)
    except Exception:
        return None
    iv = round_time.ljust(16, b'0')
    key = pwd.ljust(16, b'0')
    try:
        cipher_bytes = bytes.fromhex(encrypted_text_hex)
    except Exception:
        return None
    decrypted = None
    if _AES_MODE == 'pycryptodome':
        try:
            decrypted = _AES_IMPL.new(key, _AES_IMPL.MODE_CBC, iv).decrypt(cipher_bytes)
        except Exception:
            return None
    elif _AES_MODE == 'pyaes':
        try:
            aes = _AES_IMPL.AESModeOfOperationCBC(key, iv=iv)
            d = _AES_IMPL.Decrypter(aes)
            decrypted = d.feed(cipher_bytes)
            decrypted += d.feed()
        except Exception:
            return None
    if decrypted:
        return _strip_pkcs7(decrypted)
    return None

def _extract_content(response, depth=0, max_depth=50):
    if not response or depth > max_depth:
        return None
    current = response.strip()
    has_double_star = '**' in current
    starts_with_2423 = current.startswith('2423')
    if not has_double_star and not starts_with_2423:
        return current
    if has_double_star:
        response_no_spaces = re.sub(r'\s+', '', current)
        cleaned_text = _extract_text(response_no_spaces)
        try:
            decoded = base64.b64decode(cleaned_text).decode('utf-8', errors='replace')
            if _contains_special_strings(decoded):
                return decoded
            return _extract_content(decoded, depth + 1, max_depth)
        except Exception:
            return None
    if starts_with_2423:
        params = _extract_encryption_params(current)
        if not params:
            return None
        decrypted = _decrypt_aes(params['encryptedText'], params['pwdInHax'], params['roundtimeInHax'])
        if decrypted is None:
            return None
        try:
            decrypted_str = decrypted.decode('utf-8', errors='replace')
            if _contains_special_strings(decrypted_str):
                return decrypted_str
            return _extract_content(decrypted_str, depth + 1, max_depth)
        except Exception:
            return None
    return current

def _iter_json_spans(text, limit=400):
    n = len(text)
    if not n:
        return
    opens = ('{', '[')
    closes = ('}', ']')
    produced = 0
    i = 0
    while i < n and produced < limit:
        if text[i] not in opens:
            i += 1
            continue
        depth = 0
        j = i
        in_str = False
        esc = False
        while j < n:
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == '\\':
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c in opens:
                    depth += 1
                elif c in closes:
                    depth -= 1
                    if depth <= 0:
                        break
            j += 1
        if j < n and depth <= 0:
            yield text[i:j + 1]
            produced += 1
            i = j + 1
        else:
            i += 1

def _best_json_span(text):
    cands = sorted(_iter_json_spans(text), key=len, reverse=True)
    for c in cands[:60]:
        c = c.strip()
        if len(c) < 2:
            continue
        try:
            obj = json.loads(c)
        except Exception:
            continue
        if isinstance(obj, (dict, list)):
            return c
    return None

def extract_hidden_code(raw, log=None):
    if log is None:
        log = lambda *a, **k: None
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.encode('utf-8', errors='ignore')
    if not raw:
        return None

    text = raw.decode('utf-8', errors='ignore')

    try:
        obj = json.loads(text.lstrip('\ufeff').strip())
        if isinstance(obj, (dict, list)):
            log("接口内容实为纯文本（扩展名只是伪装）", level='debug')
            return text.lstrip('\ufeff').strip()
    except Exception:
        pass

    IEND = b'IEND\xaeB\x60\x82'
    idx = raw.find(IEND)
    if idx != -1:
        tail = raw[idx + len(IEND):]
        if tail.strip():
            t = tail.decode('utf-8', errors='ignore').strip()
            try:
                obj = json.loads(t)
                if isinstance(obj, (dict, list)):
                    log("从 PNG 尾部（IEND 之后）提取到接口代码", level='debug')
                    return t
            except Exception:
                got = _best_json_span(t)
                if got:
                    log("从 PNG 尾部（IEND 之后）提取到接口代码", level='debug')
                    return got

    for tag in (b'tEXt', b'iTXt', b'zTXt'):
        pos = 0
        while True:
            k = raw.find(tag, pos)
            if k == -1:
                break
            try:
                length = int.from_bytes(raw[k - 4:k], 'big')
                data = raw[k + 4: k + 4 + length]
            except Exception:
                pos = k + 4
                continue
            body = data
            if tag == b'zTXt':
                try:
                    _, after = data.split(b'\x00', 1)
                    if after[:1] == b'\x00':
                        body = zlib.decompress(after[1:])
                except Exception:
                    body = data
            else:
                try:
                    body = data.split(b'\x00', 1)[1]
                except Exception:
                    body = data
            s = body.decode('utf-8', errors='ignore')
            try:
                obj = json.loads(s.strip())
                if isinstance(obj, (dict, list)):
                    log("从 PNG 文本块 {} 提取到接口代码".format(tag.decode()),
                        level='debug')
                    return s.strip()
            except Exception:
                pass
            got = _best_json_span(s)
            if got:
                log("从 PNG 文本块 {} 提取到接口代码".format(tag.decode()),
                    level='debug')
                return got
            b = _try_b64_json(s)
            if b:
                log("从 PNG 文本块 {}（base64）提取到接口代码".format(tag.decode()),
                    level='debug')
                return b
            pos = k + 4

    stripped = text.strip()
    if stripped and len(stripped) > 40:
        b = _try_b64_json(stripped)
        if b:
            log("内容经 base64 编码，已解码", level='debug')
            return b

    got = _best_json_span(text)
    if got:
        log("从二进制载体中扫描提取到接口代码（{} 字符）".format(len(got)),
            level='debug')
        return got
    return None

def _try_b64_json(s):
    import base64 as _b64
    cand = re.sub(r'\s+', '', str(s or ''))
    if len(cand) < 40 or len(cand) % 4:
        return None
    if not re.fullmatch(r'[A-Za-z0-9+/=]+', cand):
        return None
    try:
        decoded = _b64.b64decode(cand, validate=True)
    except Exception:
        return None
    t = decoded.decode('utf-8', errors='ignore').strip()
    try:
        obj = json.loads(t)
        if isinstance(obj, (dict, list)):
            return t
    except Exception:
        pass
    return _best_json_span(t)

def try_decrypt_content(content, url='', external_api_url=DEFAULT_EXTERNAL_API_URL, session=None, max_rounds=5,
                       allow_remote=True):
    if isinstance(content, str):
        content = content.lstrip('\ufeff')
    if not content:
        return None
    if _contains_special_strings(content) or (content.strip().startswith('{') or content.strip().startswith('[')):
        return content
    current = content
    for i in range(max_rounds):
        result = _extract_content(current)
        if result and result != current:
            current = result
            if _contains_special_strings(current) or (current.strip().startswith('{') or current.strip().startswith('[')):
                return current
        else:
            break
    if current != content:
        return current
    if not allow_remote:
        return None
    if external_api_url and session:
        try:
            if '?url=' in external_api_url:
                resp = session.get(external_api_url + url, timeout=(5, 10))
            else:
                resp = session.post(external_api_url,
                    json={"action": "fetch_content", "params": {"url": url}, "ts": int(time.time())},
                    timeout=(5, 10))
            if resp.status_code == 200:
                data = resp.json()
                if data.get('status') == 'success':
                    r = data.get('formattedContent') or data.get('data', '')
                    if r:
                        return r
        except Exception:
            pass
    return None

class FileDownloader:
    SKIP_EXTS = {'.php', '.asp', '.jsp', '.cgi', '.exe', '.dll', '.sh', '.bat'}
    BINARY_EXTS = {'.jar', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.m3u', '.m3u8', '.mp4', '.ts'}
    DOWNLOAD_EXTS = DOWNLOAD_EXTS

    _head_cache = {}
    _head_fail_hosts = {}

    @classmethod
    def _reset_head_cache(cls):
        cls._head_cache.clear()
        cls._head_fail_hosts.clear()

    def __init__(self, output_dir, config=None, log_callback=None, progress_callback=None, cancel_event=None):
        self.output_dir = output_dir
        self.config = config or {}
        self.log_callback = log_callback or (lambda msg: None)
        self._log_cb_takes_level = self._callback_supports_level(self.log_callback)
        self.progress_callback = progress_callback or (lambda msg: None)
        self.cancel_event = cancel_event
        self.downloaded = {}
        self.failed = []
        self.skipped = []
        self.repeat_failed = []
        self._lock = threading.Lock()
        self._processed = set()
        self.unchanged = []
        self.manifest_entries = {}
        self.incremental = bool(
            self.config.get('incremental_update',
                            self.config.get('incremental', True)))
        self.localize_prefer_decrypted = bool(
            self.config.get('localize_prefer_decrypted', True))
        self.prev_manifest = self.config.get('__prev_manifest__') or {}
        self._not_modified_cache = {}
        self._proxy_fail_count = 0

        if 'download' in self.config:
            cfg_download = self.config.get('download', {})
        else:
            cfg_download = self.config

        self.overwrite = cfg_download.get('overwrite', False)
        self.timeout = (cfg_download.get('timeout_connect', 10), cfg_download.get('timeout_read', 60))
        self.chunk_size = cfg_download.get('chunk_size', 8192)
        self.max_size = int(
            self.config.get('max_file_size_mb')
            or cfg_download.get('max_file_size_mb') or 100) * 1024 * 1024

        _exts = set(self.config.get('skip_extensions') or [])
        _exts.update(cfg_download.get('skip_extensions') or [])
        self.skip_exts = _exts
        self.skip_exts.update(self.SKIP_EXTS)

        _pats = list(self.config.get('skip_patterns') or [])
        _pats += [x for x in (cfg_download.get('skip_patterns') or [])
                  if x not in _pats]
        self.skip_patterns = _pats
        self.decrypt_enabled = cfg_download.get('decrypt', {}).get('enabled', True)
        self.external_api = cfg_download.get('decrypt', {}).get('external_api_url', '')
        self.proxy = self.config.get('proxy', '')
        self.github_proxy = self.config.get('github_proxy', GITHUB_PROXY)
        self.user_agent = self.config.get('user_agent', DEFAULT_USER_AGENT)
        self.category_map = cfg_download.get('category_map', {'js': '.js', 'lib': '.json', 'py': '.py', 'jar': '.jar'})
        self.skip_patterns_core = cfg_download.get(
            'skip_patterns_core', SKIP_PATTERNS_WITH_PLACEHOLDER)
        self.max_workers = cfg_download.get('max_workers', 8)
        self.retry_total = cfg_download.get('retry_total', 2)
        self.max_download_seconds = int(
            cfg_download.get('max_download_seconds', DOWNLOAD_MAX_SECONDS)
            or DOWNLOAD_MAX_SECONDS)
        if self.max_download_seconds < DOWNLOAD_MAX_SECONDS_MIN:
            self.max_download_seconds = DOWNLOAD_MAX_SECONDS_MIN
        self.retry_backoff = cfg_download.get('retry_backoff', 0.3)
        _workers = int(cfg_download.get('max_workers', 8) or 8)
        _kb = cfg_download.get('multipart_min_bytes_kb', 0)
        if _kb:
            self.multipart_min_bytes = max(
                MULTIPART_MIN_BYTES_MIN, int(_kb) * 1024)
        else:
            self.multipart_min_bytes = MULTIPART_MIN_BYTES
        self.pool_connections = cfg_download.get(
            'pool_connections', max(10, _workers * 2))
        self.pool_maxsize = cfg_download.get(
            'pool_maxsize', max(20, _workers * 4))

        connect_to = self.timeout[0] if isinstance(self.timeout, (tuple, list)) else self.timeout
        self._head_timeout = (min(connect_to, HEAD_TIMEOUT_MAX), HEAD_TIMEOUT_MAX)

        self.session = requests.Session()
        retry = Retry(total=self.retry_total, backoff_factor=self.retry_backoff, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry, pool_connections=self.pool_connections, pool_maxsize=self.pool_maxsize)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        self._quick_session = requests.Session()
        q_adapter = HTTPAdapter(
            max_retries=Retry(total=0),
            pool_connections=self.pool_connections,
            pool_maxsize=self.pool_maxsize)
        self._quick_session.mount('http://', q_adapter)
        self._quick_session.mount('https://', q_adapter)
        self._quick_session.headers.update(self.session.headers)
        self._quick_session.verify = self.session.verify
        if getattr(self, 'proxy', ''):
            self._quick_session.proxies = {'http': self.proxy,
                                           'https': self.proxy}
        self._quick_threshold = self.max_download_seconds * 0.5
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive',
            'Accept-Encoding': 'identity'
        })
        self.session.verify = False
        if self.proxy:
            self.session.proxies = {'http': self.proxy, 'https': self.proxy}
        os.makedirs(self.output_dir, exist_ok=True)

    def exists(self, rel_path):
        if not rel_path:
            return False
        try:
            return os.path.isfile(os.path.join(self.output_dir, rel_path))
        except Exception:
            return False

    @staticmethod
    def _callback_supports_level(cb):
        try:
            import inspect
            sig = inspect.signature(cb)
            for p in sig.parameters.values():
                if p.name == 'level':
                    return True
                if p.kind == inspect.Parameter.VAR_KEYWORD:
                    return True
            return 'level' in getattr(cb, '__code__', None).co_varnames
        except Exception:
            return False

    def _log(self, msg, level='info'):
        if not self.log_callback:
            return
        try:
            if self._log_cb_takes_level:
                self.log_callback(msg, level=level)
            else:
                self.log_callback(msg)
        except Exception:
            try:
                self.log_callback(msg)
            except Exception:
                pass

    def _probe_size(self, abs_url, deadline=None):
        now = time.time()
        cached = self._head_cache.get(abs_url)
        if cached is not None and len(cached) >= 3 and cached[2] > now:
            return cached[0], cached[1]
        try:
            host = urllib.parse.urlparse(abs_url).netloc
        except Exception:
            host = ''
        if self._head_fail_hosts.get(host, 0) >= HEAD_FAIL_THRESHOLD:
            return (0, False)
        try:
            _h_to = self._head_timeout
            _h_sess = self.session
            if deadline is not None:
                _h_left = deadline - time.time()
                if _h_left <= 0:
                    return (0, False)
                if isinstance(_h_to, (tuple, list)):
                    _h_to = (max(1, min(_h_to[0], int(_h_left))),
                             max(1, min(_h_to[1], int(_h_left))))
                if _h_left < getattr(self, '_quick_threshold', 0):
                    _h_sess = self._quick_session
            head_resp = _h_sess.head(abs_url, timeout=_h_to,
                                     allow_redirects=True)
            try:
                total_size = int(head_resp.headers.get('content-length', 0) or 0)
            except (TypeError, ValueError):
                total_size = 0
            support_range = head_resp.headers.get('accept-ranges') == 'bytes'
            self._store_head_cache(abs_url, (total_size, support_range))
            self._head_fail_hosts.pop(host, None)
            return (total_size, support_range)
        except Exception as head_err:
            self._head_fail_hosts[host] = self._head_fail_hosts.get(host, 0) + 1
            self._log(f"HEAD请求失败 {abs_url}: {head_err}，尝试直接GET", level='debug')
            return (0, False)

    def _store_head_cache(self, abs_url, value):
        if len(self._head_cache) >= HEAD_CACHE_MAX:
            self._head_cache.clear()
        self._head_cache[abs_url] = (value[0], value[1], time.time() + HEAD_CACHE_TTL)

    def _record_manifest(self, target_rel, abs_url, headers, size):
        if not target_rel or not abs_url:
            return
        entry = {"url": abs_url, "ts": int(time.time())}
        if headers is not None:
            etag = headers.get('etag') or headers.get('ETag')
            last_mod = headers.get('last-modified') or headers.get('Last-Modified')
            if etag:
                entry["etag"] = etag
            if last_mod:
                entry["last_modified"] = last_mod
        if isinstance(size, int) and size > 0:
            entry["size"] = size
        with self._lock:
            self.manifest_entries[target_rel] = entry

    def _record_manifest_from_prev(self, target_rel, local_size):
        prev = self.prev_manifest.get(target_rel)
        if isinstance(prev, dict):
            entry = dict(prev)
        else:
            entry = {}
        if isinstance(local_size, int) and local_size >= 0:
            entry["size"] = local_size
        if "url" not in entry:
            return
        with self._lock:
            self.manifest_entries[target_rel] = entry

    def _is_not_modified(self, abs_url, target_rel, local_size):
        if not self.incremental:
            return None
        entry = self.prev_manifest.get(target_rel)
        if not isinstance(entry, dict):
            return None
        etag = entry.get('etag')
        last_mod = entry.get('last_modified')
        if not etag and not last_mod:
            return None

        recorded = entry.get('size')
        if isinstance(recorded, int) and recorded > 0 and local_size != recorded:
            return False

        cache_key = (abs_url, etag, last_mod)
        now = time.time()
        cached = self._not_modified_cache.get(cache_key)
        if cached is not None and cached[1] > now:
            return cached[0]

        headers = {}
        if etag:
            headers['If-None-Match'] = etag
        elif last_mod:
            headers['If-Modified-Since'] = last_mod
        try:
            resp = self.session.head(abs_url, headers=headers,
                                     timeout=self._head_timeout, allow_redirects=True)
            if resp.status_code == 304:
                self._not_modified_cache[cache_key] = (True, now + NOT_MODIFIED_CACHE_TTL)
                return True
            if resp.status_code == 200:
                self._not_modified_cache[cache_key] = (False, now + NOT_MODIFIED_CACHE_TTL)
                return False
            self._not_modified_cache[cache_key] = (None, now + NOT_MODIFIED_CACHE_TTL)
            return None
        except Exception:
            self._not_modified_cache[cache_key] = (None, now + NOT_MODIFIED_CACHE_TTL)
            return None

    def _is_github_file_url(self, url):
        if not url:
            return False
        github_domains = (
            'raw.githubusercontent.com', 'github.com', 'gist.github.com',
            'gist.githubusercontent.com', 'githubusercontent.com'
        )
        try:
            parsed = urllib.parse.urlparse(url)
            netloc = parsed.netloc.lower()
            for d in github_domains:
                if d in netloc:
                    return True
        except Exception:
            pass
        return False

    def _unwrap_foreign_proxy(self, url):
        if not url or not isinstance(url, str):
            return url
        s = url.strip()
        first = s.find('://')
        if first < 0:
            return s
        rest = s[first + 3:]
        cands = [x for x in (rest.find('http://'), rest.find('https://')) if x >= 0]
        if not cands:
            return s
        inner = rest[min(cands):]
        try:
            host = urllib.parse.urlparse(inner).netloc.lower()
        except Exception:
            return s
        if any(g in host for g in GITHUB_HOSTS):
            return inner
        return s

    def _is_foreign_wrapped(self, url):
        try:
            return self._unwrap_foreign_proxy(url) != url
        except Exception:
            return False

    def _github_inner_url(self, url):
        if not url or not isinstance(url, str):
            return None
        s = url.strip()
        first = s.find('://')
        if first < 0:
            return None
        rest = s[first + 3:]
        cands = [x for x in (rest.find('http://'), rest.find('https://')) if x >= 0]
        if cands:
            inner = rest[min(cands):]
            if self._is_github_file_url(inner):
                return inner
            return None
        slash = rest.find('/')
        if slash >= 0:
            tail = rest[slash + 1:]
            low_tail = tail.lower()
            for g in GITHUB_HOSTS:
                if low_tail.startswith(g):
                    return "https://" + tail
        return None

    def _alternate_urls(self, url):
        alts = []
        if self._is_proxied(url):
            alts.append(self._direct_url(url))

        inner = self._github_inner_url(url)
        if not inner:
            u2 = self._unwrap_foreign_proxy(url)
            inner = u2 if u2 != url else None

        if inner and inner != url:
            alts.append(inner)
            if self.github_proxy:
                alts.append(self._proxy_prefix() + inner)
        elif self.github_proxy and self._is_github_file_url(url):
            bare = (url if url.lower().startswith(("http://", "https://"))
                    else "https://" + url.lstrip('/'))
            proxied = self._proxy_prefix() + bare
            if proxied != url:
                alts.append(proxied)

        seen, out = set(), []
        for a in alts:
            if a and a != url and a not in seen:
                seen.add(a)
                out.append(a)
        return out

    def _proxy_prefix(self):
        if not self.github_proxy:
            return None
        return self.github_proxy.rstrip('/') + '/'

    def _is_proxied(self, url):
        p = self._proxy_prefix()
        if not (p and isinstance(url, str) and url.startswith(p)):
            return False
        inner = url[len(p):]
        return inner.lower().startswith(("http://", "https://"))

    def _direct_url(self, url):
        p = self._proxy_prefix()
        if p and isinstance(url, str) and url.startswith(p):
            inner = url[len(p):]
            if inner.lower().startswith(("http://", "https://")):
                return inner
            return "https://" + inner.lstrip('/')
        return url

    def _note_proxy_failure(self):
        if not self.github_proxy:
            return
        self._proxy_fail_count += 1
        if self._proxy_fail_count >= PROXY_FAIL_THRESHOLD:
            self._log(f"⚠️ GitHub 代理连续失败 {self._proxy_fail_count} 次，"
                      f"已熔断，后续文件直接连接: {self.github_proxy}")

    def _note_proxy_success(self):
        self._proxy_fail_count = 0

    def _proxy_blown(self):
        return bool(self.github_proxy) and self._proxy_fail_count >= PROXY_FAIL_THRESHOLD

    def _apply_proxy_policy(self, url):
        if self._is_proxied(url) and self._proxy_blown():
            direct = self._direct_url(url)
            self._log(f"⏭️ 代理已熔断，改用直连: {direct}")
            return direct
        return url

    def normalize_github_url(self, url):
        if not url:
            return url
        if self.github_proxy:
            url = self._unwrap_foreign_proxy(url)
            proxy_prefix = self.github_proxy.rstrip('/') + '/'
            if url.startswith(proxy_prefix):
                inner = url[len(proxy_prefix):]
                if inner.lower().startswith(('http://', 'https://')):
                    url = inner
        if self._is_github_file_url(url):
            parsed = urllib.parse.urlparse(url)
            path = parsed.path.lstrip('/')
            if 'github.com' in parsed.netloc:
                parts = path.split('/')
                if len(parts) >= 4:
                    user = parts[0]
                    repo = parts[1]
                    if parts[2] in ('blob', 'raw'):
                        branch = parts[3]
                        file_path = '/'.join(parts[4:])
                        url = f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{file_path}"
                    else:
                        url = f"https://raw.githubusercontent.com/{user}/{repo}/master/{'/'.join(parts[3:])}"
            elif 'gist.github.com' in parsed.netloc:
                gist_id = path.split('/')[0]
                url = f"https://gist.githubusercontent.com/raw/{gist_id}/"
        return url

    def split_url_and_suffix(self, url):
        if url and isinstance(url, str):
            url = url.strip()
        if not url:
            return url, ""
        if ';md5;' in url:
            idx = url.index(';md5;')
            return url[:idx], url[idx:]
        parsed = urllib.parse.urlparse(url)
        if parsed.query and ('md5=' in parsed.query or 'MD5=' in parsed.query):
            base = url.split('?')[0]
            return base, '?' + parsed.query
        return url, ""

    def _own_service_ports(self):
        cached = getattr(self, '_own_ports_cache', None)
        if cached is not None:
            return cached
        ports = set()
        raw = self.config.get('__own_service_ports__')
        if isinstance(raw, (list, tuple, set)):
            for v in raw:
                try:
                    v = int(v)
                    if v > 0:
                        ports.add(v)
                except Exception:
                    pass
        if not ports:
            try:
                ports.add(int(DEFAULT_FILE_SERVICE_PORT))
            except Exception:
                pass
        self._own_ports_cache = ports
        return ports

    @property
    def fresh_count(self):
        try:
            return max(0, len(self.downloaded) - len(self.unchanged))
        except Exception:
            return len(self.downloaded)

    def _is_unreachable_url(self, url):
        if not url or not isinstance(url, str):
            return True
        low = url.strip().lower()
        if not low:
            return True
        if not SCHEME_RE.match(low):
            return False
        if not low.startswith(('http://', 'https://')):
            return True
        try:
            host = urllib.parse.urlparse(url).hostname
        except Exception:
            return False
        if not host:
            return True
        host = host.strip('[]').lower()

        if host in ('localhost', 'localhost.localdomain', '::1') or \
                host.startswith('127.'):
            try:
                port = urllib.parse.urlparse(url).port
            except Exception:
                port = None
            if port and port in self._own_service_ports():
                return False
            return True
        if host.endswith('.local'):
            return True
        try:
            import ipaddress
            ip = ipaddress.ip_address(host)
            return (ip.is_loopback or ip.is_link_local or ip.is_unspecified
                    or ip.is_multicast or ip.is_reserved)
        except ValueError:
            return False
        except Exception:
            return False

    def is_downloadable(self, url, field_key=None):
        if not url or not isinstance(url, str):
            return False
        url_clean = url.strip()
        if not url_clean:
            return False
        if self._is_unreachable_url(url_clean):
            return False
        if field_key in ('spider', 'jar'):
            if url_clean.startswith("proxy://"):
                return False
            for pat in self.skip_patterns_core:
                if re.search(pat, url_clean):
                    return False
            return True
        if url_clean.startswith("proxy://"):
            return False
        for pat in self.skip_patterns_core:
            if re.search(pat, url_clean):
                return False
        path_part = url_clean.split('?')[0].split(';')[0].rstrip('/')
        ext = os.path.splitext(path_part)[1].lower()
        if ext in self.skip_exts:
            return False
        if ext in self.DOWNLOAD_EXTS:
            return True
        if url_clean.startswith("http://") or url_clean.startswith("https://"):
            self._log("跳过：扩展名 %s 不在下载白名单 → %s"
                      % (ext or "(无)", _short_url(url_clean)),
                      level='debug')
            return False
        return False

    def resolve_url(self, rel_path, base_url):
        if not rel_path:
            return None
        if isinstance(rel_path, str):
            rel_path = rel_path.strip()
        if rel_path.startswith(('http://', 'https://')):
            return self.normalize_github_url(rel_path)
        if rel_path.startswith("//"):
            return self.normalize_github_url("https:" + rel_path)
        if rel_path.startswith("./") or rel_path.startswith("../"):
            return self.normalize_github_url(safe_urljoin(base_url, rel_path))
        if rel_path.startswith("/"):
            parsed = urllib.parse.urlparse(base_url)
            return self.normalize_github_url(f"{parsed.scheme}://{parsed.netloc}{rel_path}")
        return self.normalize_github_url(safe_urljoin(base_url, rel_path))

    def get_target_path(self, url, category, field_key=None):
        if not url:
            return os.path.join(category, 'unknown')
        clean_url = url
        if self.github_proxy:
            proxy = self.github_proxy.rstrip('/') + '/'
            if clean_url.startswith(proxy):
                clean_url = clean_url[len(proxy):]
        path_part = clean_url.split('?')[0].split(';')[0].rstrip('/')
        path_part = urllib.parse.unquote(path_part)
        filename = os.path.basename(path_part)
        if not filename:
            filename = hashlib.md5(url.encode()).hexdigest()[:8]
            filename += self.category_map.get(category, '.bin')
        ext = os.path.splitext(filename)[1].lower()
        if field_key in ('spider', 'jar'):
            if not ext:
                filename += '.jar'
            return os.path.join('jar', filename)
        if not ext:
            filename += self.category_map.get(category, '.bin')
        return os.path.join(category, filename)

    def should_skip(self, url):
        if not url or not isinstance(url, str):
            return True, "空URL"
        for pattern in self.skip_patterns:
            if pattern in url:
                return True, f"命中跳过模式: {pattern}"
        return False, ""

    def download_file(self, url, base_url, category='lib', field_key=None,
                      _direct_only=False, _no_more_alts=False):
        if self.cancel_event and self.cancel_event.is_set():
            self._log("下载任务已取消")
            return None
        if not url or not isinstance(url, str):
            return None
        _t0 = time.time()
        _deadline = _t0 + self.max_download_seconds
        url_part, suffix = self.split_url_and_suffix(url)
        if not self.is_downloadable(url_part, field_key):
            return None
        should_skip, reason = self.should_skip(url_part)
        if should_skip:
            with self._lock:
                self.skipped.append((url, reason))
            self._log(f"跳过文件: {url} ({reason})", level='debug')
            return None
        abs_url = self.resolve_url(url_part, base_url)
        if not abs_url:
            with self._lock:
                self.failed.append((url, "无法解析URL"))
            return None
        abs_url = (self._direct_url(abs_url) if _direct_only
                   else self._apply_proxy_policy(abs_url))
        reach_url = self._direct_url(abs_url) if self._is_proxied(abs_url) else abs_url
        if self._is_unreachable_url(reach_url):
            with self._lock:
                self.skipped.append((url, "回环/内网地址"))
            self._log(f"⏭️ 跳过回环或内网地址: {reach_url}")
            return None
        target_rel = self.get_target_path(abs_url, category, field_key)
        target_abs = os.path.join(self.output_dir, target_rel)

        if self.incremental:
            prev = self.prev_manifest.get(target_rel)
            if isinstance(prev, dict) and \
                    int(prev.get('fails', 0) or 0) >= FAIL_SKIP_THRESHOLD:
                ts = int(prev.get('ts', 0) or 0)
                if not ts or (time.time() - ts) < FAIL_ENTRY_TTL:
                    with self._lock:
                        self.skipped.append(
                            (url, "连续失败 %s 次，本轮跳过" % prev.get('fails')))
                        self.repeat_failed.append(
                            (url, str(prev.get('reason') or "反复失败")[:120]))
                    self._log(f"⏭️ 跳过反复失败的地址: {target_rel}",
                              level='debug')
                    return None

        with self._lock:
            if target_rel in self._processed:
                if os.path.exists(target_abs):
                    self.downloaded[url_part] = target_rel
                    return target_rel
                self._processed.discard(target_rel)
            self._processed.add(target_rel)
        total_size, support_range = self._probe_size(abs_url, deadline=_deadline)
        if self.max_size and total_size and total_size > self.max_size:
            reason = (f"超过大小上限 {total_size / 1024 / 1024:.1f}MB"
                      f" > {self.max_size / 1024 / 1024:.1f}MB")
            with self._lock:
                self.skipped.append((url, reason))
            self._log(f"⏭️ 跳过 {url}：{reason}")
            return None
        force_full = False
        if not self.overwrite and os.path.exists(target_abs):
            try:
                local_size = os.path.getsize(target_abs)
            except Exception:
                local_size = -1
            fresh = self._is_not_modified(abs_url, target_rel, local_size)
            if fresh is True:
                with self._lock:
                    self.downloaded[url_part] = target_rel
                    self.unchanged.append(target_rel)
                    self.manifest_entries[target_rel] = self.prev_manifest[target_rel]
                self._log(f"⏭️ 远端未变更，跳过: {target_rel}", level='debug')
                return target_rel
            if fresh is False:
                force_full = True
                self._log(f"🔄 远端已更新，完整重下: {target_rel}")
            if total_size <= 0 or local_size == total_size:
                if force_full and total_size > 0:
                    pass
                else:
                    with self._lock:
                        self.downloaded[url_part] = target_rel
                    self._log(f"文件已存在，跳过: {target_rel} ({local_size} 字节)", level='debug')
                    self._record_manifest_from_prev(target_rel, local_size)
                    self._record_manifest(target_rel, abs_url, None, local_size)
                    return target_rel
            if local_size > total_size > 0:
                force_full = True
                self._log(f"⚠️ 本地文件大于远端 ({local_size}/{total_size})，完整重下: {target_rel}")
            elif not force_full:
                self._log(f"⚠️ 本地文件不完整 ({local_size}/{total_size} 字节)，继续处理: {target_rel}")

        self._log(f"下载文件: {abs_url}", level='debug')

        def _record_failure(reason):
            prev = self.manifest_entries.get(target_rel)
            if not isinstance(prev, dict):
                prev = self.prev_manifest.get(target_rel)
            fails = (int(prev.get('fails', 0) or 0) + 1) if isinstance(prev, dict) else 1
            with self._lock:
                self.failed.append((url, reason))
                self._processed.discard(target_rel)
                self.manifest_entries[target_rel] = {
                    "url": abs_url, "ts": int(time.time()),
                    "fails": fails, "reason": str(reason)[:120],
                }

        def _try_alternates(reason):
            if _no_more_alts:
                return None
            for alt in self._alternate_urls(abs_url):
                if time.time() >= _deadline:
                    self._log(
                        f"⏱️ 已达 {self.max_download_seconds} 秒耗时上限，"
                        f"不再尝试备用地址: {target_rel}")
                    break
                self._log(f"↩️ {reason}，换用替代地址重试: {alt}")
                with self._lock:
                    self._processed.discard(target_rel)
                r = self.download_file(alt, "", category, field_key,
                                       _direct_only=True, _no_more_alts=True)
                if r:
                    return r
            return None

        try:
            downloaded_size = 0
            req_headers = dict(self.session.headers)
            mode = "wb"
            if force_full and os.path.exists(target_abs):
                try:
                    os.remove(target_abs)
                    self._log(f"🗑️ 已清除旧内容，重新下载: {target_rel}")
                except Exception as e:
                    self._log(f"清除旧文件失败 {target_abs}: {e}", level='warn')
            if os.path.exists(target_abs) and total_size > 0 and not force_full:
                downloaded_size = os.path.getsize(target_abs)
                if downloaded_size == total_size:
                    with self._lock:
                        self.downloaded[url_part] = target_rel
                    self._log(f"✅ 本地已存在完整文件，跳过: {target_rel}", level='debug')
                    self._record_manifest_from_prev(target_rel, downloaded_size)
                    self._record_manifest(target_rel, abs_url, None, downloaded_size)
                    return target_rel
                elif downloaded_size < total_size and support_range:
                    self._log(f"🔄 断点续传 {target_rel} (已下载 {downloaded_size/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB)")
                    req_headers["Range"] = f"bytes={downloaded_size}-"
                    mode = "ab"

            os.makedirs(os.path.dirname(target_abs), exist_ok=True)

            if (total_size > self.multipart_min_bytes and support_range
                    and mode == "wb"):
                return self._download_file_multithread(
                    abs_url, req_headers, target_abs, target_rel,
                    url_part, total_size, field_key)

            _left = _deadline - time.time()
            if _left <= 0:
                _record_failure(
                    "耗时超过 %d 秒上限，放弃（含所有备用地址）"
                    % self.max_download_seconds)
                return None
            _to = self.timeout
            if isinstance(_to, (tuple, list)):
                _to = (_to[0], max(1, min(_to[1], int(_left))))
            elif isinstance(_to, (int, float)):
                _to = max(1, min(_to, int(_left)))
            _sess = (self._quick_session if _left < self._quick_threshold
                     else self.session)
            resp = _sess.get(abs_url, headers=req_headers, timeout=_to, stream=True)
            self._log(f"响应状态: {resp.status_code}", level='debug')

            if mode == "ab" and resp.status_code == 200:
                self._log(f"⚠️ 服务端不支持断点续传（返回200全量），改为完整重下: {target_rel}")
                mode = "wb"
                downloaded_size = 0

            if resp.status_code not in (200, 206):
                if self._is_proxied(abs_url) or self._is_foreign_wrapped(abs_url):
                    self._note_proxy_failure()
                alt = _try_alternates(f"HTTP {resp.status_code}")
                if alt:
                    return alt
                _record_failure(f"HTTP {resp.status_code}")
                return None

            if not total_size and mode == "wb":
                try:
                    total_size = int(resp.headers.get('content-length', 0) or 0)
                except (TypeError, ValueError):
                    total_size = 0
                support_range = resp.headers.get('accept-ranges') == 'bytes'
                self._store_head_cache(abs_url, (total_size, support_range))

            last_log_time = time.time()
            downloaded_len = downloaded_size
            with open(target_abs, mode) as f_local:
                for chunk in resp.iter_content(chunk_size=self.chunk_size):
                    if self.cancel_event and self.cancel_event.is_set():
                        self._log("下载被取消")
                        return None
                    if chunk:
                        f_local.write(chunk)
                        downloaded_len += len(chunk)
                        now = time.time()
                        if now - last_log_time > 1.5:
                            if total_size > 0:
                                pct = (downloaded_len / total_size) * 100
                                self.progress_callback(f"⏳ {target_rel} {pct:.1f}% ({downloaded_len/1024/1024:.1f}MB)")
                            else:
                                self.progress_callback(f"⏳ {target_rel} ({downloaded_len/1024/1024:.1f}MB)")
                            last_log_time = now

            with self._lock:
                self.downloaded[url_part] = target_rel
            self._log(f"下载成功: {target_rel}", level='debug')
            if self._is_proxied(abs_url):
                self._note_proxy_success()
            try:
                final_size = os.path.getsize(target_abs)
            except Exception:
                final_size = 0
            self._record_manifest(target_rel, abs_url, resp.headers, final_size)
            return target_rel
        except Exception as e:
            if self._is_proxied(abs_url) or self._is_foreign_wrapped(abs_url):
                self._note_proxy_failure()
            alt = _try_alternates(f"请求失败（{str(e)[:50]}）")
            if alt:
                return alt
            _record_failure(str(e))
            self._log(f"下载失败: {e}", level='error')
            return None

    def _download_file_multithread(self, url, headers, path, target_rel, url_part, total_size, field_key=None):
        self._log(f"⚡ 启用多线程分块下载: {target_rel}")
        num_threads = min(8, max(2, self.max_workers))
        chunk_size = total_size // num_threads
        ranges = []
        for i in range(num_threads):
            start = i * chunk_size
            end = start + chunk_size - 1 if i < num_threads - 1 else total_size - 1
            ranges.append((start, end))

        temp_files = [f"{path}.part{i}" for i in range(num_threads)]
        lock = threading.Lock()
        completed = [0]
        errors = []
        resp_headers = {"h": None}

        def cleanup_parts():
            for tp in temp_files:
                try:
                    if os.path.exists(tp):
                        os.remove(tp)
                except Exception:
                    pass

        def download_chunk(idx, start, end):
            if self.cancel_event and self.cancel_event.is_set():
                return
            temp_path = temp_files[idx]
            want = end - start + 1
            try:
                h = dict(headers)
                h["Range"] = f"bytes={start}-{end}"
                r = self.session.get(url, headers=h, stream=True, timeout=self.timeout)
                r.raise_for_status()

                if r.status_code != 206:
                    raise ValueError(
                        "服务端未响应 Range（HTTP %s，期望 206）" % r.status_code)

                got = 0
                with open(temp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if self.cancel_event and self.cancel_event.is_set():
                            return
                        if chunk:
                            f.write(chunk)
                            got += len(chunk)
                            if got > want:
                                raise ValueError(
                                    "分块 %d 返回 %d 字节，超过请求范围 %d 字节"
                                    % (idx, got, want))
                if got != want:
                    raise ValueError(
                        "分块 %d 实收 %d 字节，应为 %d 字节" % (idx, got, want))

                with lock:
                    if not resp_headers["h"]:
                        resp_headers["h"] = r.headers
                    completed[0] += 1
                    self.progress_callback(f"⏳ {target_rel} 分块 {completed[0]}/{num_threads} 完成")
            except Exception as e:
                with lock:
                    errors.append(str(e))

        try:
            with ThreadPoolExecutor(max_workers=num_threads) as ex:
                futures = []
                for idx, (start, end) in enumerate(ranges):
                    futures.append(ex.submit(download_chunk, idx, start, end))
                for fut in as_completed(futures):
                    pass

            canceled = bool(self.cancel_event and self.cancel_event.is_set())
            if errors or canceled:
                if errors:
                    self._log(f"❌ 分块下载出错: {errors[0]}", level='error')
                with self._lock:
                    self.failed.append((url, f"分块下载失败: {errors[0] if errors else '已取消'}"))
                return None

            total_got = 0
            for idx, part_path in enumerate(temp_files):
                if not os.path.exists(part_path):
                    raise ValueError("分块 %d 缺失" % idx)
                sz = os.path.getsize(part_path)
                want = ranges[idx][1] - ranges[idx][0] + 1
                if sz != want:
                    raise ValueError(
                        "分块 %d 大小 %d，应为 %d" % (idx, sz, want))
                total_got += sz
            if total_got != total_size:
                raise ValueError(
                    "合并大小 %d 与预期 %d 不符" % (total_got, total_size))

            with open(path, 'wb') as outfile:
                for part_path in temp_files:
                    with open(part_path, 'rb') as infile:
                        shutil.copyfileobj(infile, outfile, length=1024 * 1024)
        except Exception as e:
            self._log(f"❌ 分块下载校验失败: {e}", level='error')
            with self._lock:
                self.failed.append((url, "分块校验失败: %s" % str(e)[:120]))
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
            return None
        finally:
            cleanup_parts()

        with self._lock:
            self.downloaded[url_part] = target_rel
        self._log(f"🎉 多线程下载完成: {target_rel}")
        try:
            final_size = os.path.getsize(path)
        except Exception:
            final_size = 0
        self._record_manifest(target_rel, url, resp_headers["h"], final_size)
        return target_rel

    def download_text(self, url, base_url, force_decrypt=None, _direct_only=False,
                      _no_more_alts=False):
        if self.cancel_event and self.cancel_event.is_set():
            return None
        if not url or not isinstance(url, str):
            return None
        url_part, suffix = self.split_url_and_suffix(url)
        full_url = self.resolve_url(url_part, base_url)
        if not full_url:
            return None
        full_url = (self._direct_url(full_url) if _direct_only
                    else self._apply_proxy_policy(full_url))
        _reach = self._direct_url(full_url) if self._is_proxied(full_url) else full_url
        if self._is_unreachable_url(_reach):
            self._log(f"⏭️ 跳过回环或内网地址: {_reach}")
            return None
        self._log(f"请求文本: {full_url}", level='debug')

        def _try_alternates(reason):
            if _no_more_alts:
                return None
            for alt in self._alternate_urls(full_url):
                self._log(f"↩️ {reason}，换用替代地址重试: {alt}")
                r = self.download_text(alt, "", force_decrypt,
                                       _direct_only=True, _no_more_alts=True)
                if r:
                    return r
            return None

        try:
            req_headers = dict(self.session.headers)
            parsed = urllib.parse.urlparse(full_url)
            if 'cnb.cool' in parsed.netloc:
                req_headers['Referer'] = 'https://cnb.cool'
                req_headers['Origin'] = 'https://cnb.cool'
                self._log("自动添加 cnb.cool 请求头")
            resp = self.session.get(full_url, headers=req_headers, timeout=self.timeout)
            self._log(f"响应状态: {resp.status_code}, 内容长度: {len(resp.text)}", level='debug')
            if resp.status_code != 200:
                if self._is_proxied(full_url) or self._is_foreign_wrapped(full_url):
                    self._note_proxy_failure()
                alt = _try_alternates(f"HTTP {resp.status_code}")
                if alt:
                    return alt
                self._log(f"下载文本失败，状态码: {resp.status_code}", level='error')
                return None
            parsed = urllib.parse.urlparse(full_url)
            path = urllib.parse.unquote(parsed.path)
            ext = os.path.splitext(path)[1].lower()
            raw = resp.content
            binary_like = ext in self.BINARY_EXTS

            if binary_like:
                hidden = extract_hidden_code(raw, log=self._log)
                if hidden:
                    content = hidden
                else:
                    self._log("二进制资源，未发现隐藏代码，按原样返回", level='debug')
                    return raw.decode('utf-8', errors='ignore')
            else:
                try:
                    content = raw.decode('utf-8')
                except UnicodeDecodeError:
                    content = raw.decode('utf-8', errors='ignore')
            content = content.lstrip('\ufeff')
            preview = content[:200].replace('\n', ' ').replace('\r', '')
            self._log(f"内容预览: {preview}...", level='debug')
            do_decrypt = force_decrypt if force_decrypt is not None else self.decrypt_enabled
            if do_decrypt:
                allow_remote = bool(self.decrypt_enabled)
                if force_decrypt and not self.decrypt_enabled:
                    self._log("解密开关已关闭：仅做本地提取，不外发", level='debug')
                self._log("尝试解密内容...", level='debug')
                decrypted = try_decrypt_content(content, full_url, self.external_api,
                                                self.session, max_rounds=5,
                                                allow_remote=allow_remote)
                if decrypted:
                    self._log("解密成功", level='debug')
                    return decrypted
                else:
                    self._log("解密失败，返回原始内容")
            return content
        except Exception as e:
            if self._is_proxied(full_url) or self._is_foreign_wrapped(full_url):
                self._note_proxy_failure()
            alt = _try_alternates(f"请求失败（{str(e)[:50]}）")
            if alt:
                return alt
            self._log(f"下载文本异常: {e}", level='error')
            return None

def _cfg_prop(path, default=None):
    keys = path.split('.')
    fb = '_cfg_fallback_' + path

    def getter(self):
        cfg = self.__dict__.get('config')
        if not isinstance(cfg, dict):
            if fb not in self.__dict__:
                self.__dict__[fb] = _copy_default(default)
            return self.__dict__[fb]
        node = cfg
        for k in keys[:-1]:
            nxt = node.get(k)
            if not isinstance(nxt, dict):
                nxt = {}
                node[k] = nxt
            node = nxt
        if keys[-1] not in node:
            node[keys[-1]] = _copy_default(default)
        return node[keys[-1]]

    def setter(self, value):
        cfg = self.__dict__.get('config')
        if not isinstance(cfg, dict):
            self.__dict__[fb] = value
            return
        node = cfg
        for k in keys[:-1]:
            nxt = node.get(k)
            if not isinstance(nxt, dict):
                nxt = {}
                node[k] = nxt
            node = nxt
        node[keys[-1]] = value

    return property(getter, setter, doc="配置代理 → config.%s" % path)

def _copy_default(d):
    if isinstance(d, (dict, list, set)):
        return copy.deepcopy(d)
    return d

class Spider(BaseSpider):
    VERSION = "v5.4 - UI重构版"
    ACTION_DOWNLOAD_PACKAGE = "local_source_download_package"
    ACTION_SHOW_STATUS = "local_source_show_status"

    download_config = _cfg_prop('download', {})
    category_map = _cfg_prop('download.category_map',
                             {'js': '.js', 'lib': '.json', 'py': '.py', 'jar': '.jar'})
    skip_patterns_core = _cfg_prop('download.skip_patterns_core',
                                   SKIP_PATTERNS_WITH_PLACEHOLDER)
    max_workers = _cfg_prop('download.max_workers', 8)
    retry_total = _cfg_prop('download.retry_total', 2)
    retry_backoff = _cfg_prop('download.retry_backoff', 0.3)
    pool_connections = _cfg_prop('download.pool_connections', 10)
    pool_maxsize = _cfg_prop('download.pool_maxsize', 20)
    log_enabled = _cfg_prop('log.enabled', True)
    log_level = _cfg_prop('log.level', LOG_LEVEL_DEFAULT)
    log_dir = _cfg_prop('log.dir', None)
    user_agent = _cfg_prop('user_agent', DEFAULT_USER_AGENT)
    external_api_url = _cfg_prop('external_api_url', DEFAULT_EXTERNAL_API_URL)
    download_output_dir = _cfg_prop('download_output_dir', '')
    tv_mode = _cfg_prop('tv_mode', None)
    root_dirs = _cfg_prop('root_dirs', [])
    scan_local_dirs = _cfg_prop('scan_local_dirs', [])
    scan_local_extensions = _cfg_prop('scan_local_extensions', ['.py', '.js'])
    localized_interfaces = _cfg_prop('localized_interfaces', [])
    decrypt_filename_template = _cfg_prop('decrypt_filename_template', '{name}_m.json')
    localized_filename_template = _cfg_prop('localized_filename_template', '{name}.json')
    inject_manager_site = _cfg_prop('inject_manager_site', True)
    oktv_switch_timeout = _cfg_prop('oktv_switch_timeout', 2)
    incremental_update = _cfg_prop('incremental_update', True)
    localize_prefer_decrypted = _cfg_prop('localize_prefer_decrypted', True)
    config_backup_dir = _cfg_prop('config_backup_dir', '')
    file_service_base = _cfg_prop('file_service_base', '')
    proxy_port = _cfg_prop('proxy_port', DEFAULT_PROXY_PORT)

    def __init__(self):
        super().__init__()
        self.lock = threading.RLock()
        self._config_io_lock = threading.RLock()
        self._log_file_queue = queue.Queue(maxsize=LOG_FILE_QUEUE_MAXSIZE)
        self._log_writer_thread = None
        self._log_dirs_ready = set()
        self._log_view_chars = 0
        self.inited = False
        self._initial_extend = None
        self.config = {}
        self.package_download_sites = []
        self.download_output_dir = ""
        self.download_config = {}
        self._package_download_state = "idle"
        self._package_download_message = ""
        self._package_download_thread = None
        self._package_download_lock = threading.Lock()
        self._package_cancel_event = None
        self._dialog_refs = []
        self._notification_refs = []
        self._destroyed = False
        self._session = None
        self._site_states = {}
        self._site_op_threads = {}
        self._site_op_lock = threading.Lock()
        self._site_cancel_events = {}
        self.session = None
        self.external_api_url = DEFAULT_EXTERNAL_API_URL
        self.log_enabled = True
        self.log_level = 'info'
        self.log_dir = os.path.join(SCRIPT_DIR, 'logs')
        self.user_agent = DEFAULT_USER_AGENT
        self.category_map = {'js': '.js', 'lib': '.json', 'py': '.py', 'jar': '.jar'}
        self.skip_patterns_core = SKIP_PATTERNS_WITH_PLACEHOLDER
        self.max_workers = 8
        self.retry_total = 2
        self.retry_backoff = 0.3
        self.pool_connections = 10
        self.pool_maxsize = 20

        self._base_dir = None
        self._resource_dirs = []
        self._config_file_path = None

        self.log_queue = queue.Queue()
        self._persisted_runnable = None
        self._ui_listeners = []
        self._ui_last_click = 0.0
        self._active_views = {}
        self._is_downloading = False
        self._log_dialog_open = False
        self._log_buffer = _LogRing(LOG_VIEW_BUFFER_MAX)
        self._log_view_levels = {'debug': True, 'info': True,
                                 'warn': True, 'error': True}
        self._last_log_line = ("", 'info')
        self._log_dup_count = 0

        self.localized_interfaces = []
        self._load_localized_interfaces()
        self.root_dirs = []
        self._load_root_dirs()

        self._ui_busy = False
        self.scan_local_dirs = []
        self.scan_local_extensions = ['.py', '.js']
        self._original_oktv_url = None
        self._pending_notice = None

        self.decrypt_filename_template = "{name}_m.json"
        self.localized_filename_template = "{name}.json"
        self.inject_manager_site = True
        self.oktv_switch_timeout = 2
        self.tv_mode = None
        self._fs_root_prefix = None
        self._load_additional_config()

    def _load_additional_config(self):
        try:
            if os.path.exists(PERSISTENT_CONFIG_PATH):
                with open(PERSISTENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.decrypt_filename_template = data.get("decrypt_filename_template", "{name}_m.json")
                self.localized_filename_template = data.get("localized_filename_template", "{name}.json")
                self.inject_manager_site = data.get("inject_manager_site", True)
                self.oktv_switch_timeout = data.get("oktv_switch_timeout", 2)
                self.tv_mode = data.get("tv_mode", None)
                self.scan_local_dirs = data.get("scan_local_dirs", [])
                self.scan_local_extensions = data.get("scan_local_extensions", ['.py', '.js'])
            else:
                self.scan_local_dirs = []
                self.scan_local_extensions = ['.py', '.js']
        except Exception as e:
            self._log(f"加载额外配置失败，保留现有内存数据: {e}", level='error')

        if not self.scan_local_dirs and self.download_output_dir:
            default_dir = self.download_output_dir
            if default_dir not in self.scan_local_dirs:
                self.scan_local_dirs.append(default_dir)
                try:
                    os.makedirs(default_dir, exist_ok=True)
                except Exception:
                    pass
                self._save_additional_config()
                self._log(f"设置默认扫描目录: {default_dir}")

    def _save_additional_config(self):
        with self._config_io_lock:
            try:
                data = {}
                if os.path.exists(PERSISTENT_CONFIG_PATH):
                    try:
                        with open(PERSISTENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                    except Exception as e:
                        self._log(f"读取额外配置失败，将重新创建: {e}", level='warn')
                        data = {}
                data["scan_local_dirs"] = self.scan_local_dirs
                data["scan_local_extensions"] = self.scan_local_extensions
                data["decrypt_filename_template"] = self.decrypt_filename_template
                data["localized_filename_template"] = self.localized_filename_template
                data["inject_manager_site"] = self.inject_manager_site
                data["oktv_switch_timeout"] = self.oktv_switch_timeout
                data["tv_mode"] = getattr(self, "tv_mode", None)
                self._write_json_atomic(PERSISTENT_CONFIG_PATH, data)
                self._log(f"额外配置已保存: {PERSISTENT_CONFIG_PATH}")
            except Exception as e:
                self._log(f"保存额外配置失败: {e}", level='error')

    def _load_root_dirs(self):
        try:
            if os.path.exists(PERSISTENT_CONFIG_PATH):
                with open(PERSISTENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.root_dirs = data.get("root_dirs", [])
                if not self.root_dirs:
                    default_dir = self.download_output_dir or os.path.join(SCRIPT_DIR, "本地包")
                    if default_dir not in self.root_dirs:
                        self.root_dirs.append(default_dir)
            else:
                default_dir = self.download_output_dir or os.path.join(SCRIPT_DIR, "本地包")
                self.root_dirs = [default_dir]
        except Exception:
            default_dir = self.download_output_dir or os.path.join(SCRIPT_DIR, "本地包")
            self.root_dirs = [default_dir]
        for d in self.root_dirs:
            if d and not os.path.exists(d):
                try:
                    os.makedirs(d, exist_ok=True)
                except Exception:
                    pass

    def _save_root_dirs(self):
        with self._config_io_lock:
            try:
                if os.path.exists(PERSISTENT_CONFIG_PATH):
                    with open(PERSISTENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                else:
                    data = {}
                data["root_dirs"] = self.root_dirs
                self._write_json_atomic(PERSISTENT_CONFIG_PATH, data)
            except Exception as e:
                self._log(f"保存设置目录列表失败: {e}", level='error')

    def _is_remote_path(self, path):
        if not path:
            return False
        return str(path).lower().startswith(('http://', 'https://', 'ftp://'))

    def _get_base_dir(self):
        return self._base_dir or SCRIPT_DIR

    def _detect_base_dir(self, ext):
        if self._base_dir:
            return self._base_dir

        clues = []
        if isinstance(ext, dict):
            config_file = ext.get('config_file', '')
            if config_file and not self._is_remote_path(config_file):
                clues.append(config_file)
            lives = ext.get('lives', [])
            if isinstance(lives, list):
                for item in lives:
                    if isinstance(item, str) and not self._is_remote_path(item):
                        clues.append(item)
                    elif isinstance(item, dict):
                        for k in ('api', 'url'):
                            v = item.get(k, '')
                            if v and not self._is_remote_path(v):
                                clues.append(v)
            for key in ('接口_单仓', 'lives_urls', '接口_直播', 'lives_url'):
                val = ext.get(key, [])
                if isinstance(val, str) and not self._is_remote_path(val):
                    clues.append(val)
                elif isinstance(val, list):
                    for v in val:
                        if isinstance(v, str) and not self._is_remote_path(v):
                            clues.append(v)

        if not clues:
            self._base_dir = SCRIPT_DIR
            return self._base_dir

        candidate_bases = []
        candidate_bases.extend(self._resource_dirs)
        candidate_bases.append(SCRIPT_DIR)
        parent = os.path.dirname(SCRIPT_DIR)
        if parent:
            candidate_bases.append(parent)
            pp = os.path.dirname(parent)
            if pp:
                candidate_bases.append(pp)
        candidate_bases.append(os.getcwd())
        for p in _COMMON_USER_DIRS:
            candidate_bases.append(p)

        seen = set()
        unique_bases = []
        for b in candidate_bases:
            if b and b not in seen and os.path.isdir(b):
                seen.add(b)
                unique_bases.append(b)

        for clue in clues:
            strip = clue.lstrip('./').lstrip('.\\').strip()
            basename = os.path.basename(clue)
            clue_dir = os.path.dirname(strip)
            for base in unique_bases:
                test_paths = [
                    os.path.join(base, strip),
                    os.path.join(base, clue) if clue.startswith('./') else None,
                    os.path.join(base, basename),
                    os.path.join(base, 'json', basename) if clue_dir else None,
                    os.path.join(base, 'py', basename) if clue_dir else None,
                ]
                for tp in test_paths:
                    if tp and os.path.exists(tp):
                        self._base_dir = base
                        self._remember_resource_dir(tp)
                        self._log(f"动态检测到基础目录: {base} (线索: {clue} -> {tp})")
                        return self._base_dir

        for base in unique_bases:
            if os.path.isdir(os.path.join(base, 'json')) or os.path.isdir(os.path.join(base, 'py')):
                self._base_dir = base
                self._log(f"通过目录结构检测到基础目录: {base}")
                return self._base_dir

        self._log(f"候选目录均未匹配，开始遍历文件系统搜索线索文件...")
        for root in _FS_SEARCH_ROOTS:
            if not os.path.isdir(root):
                continue
            try:
                for dirpath, dirnames, filenames in os.walk(root):
                    rel = os.path.relpath(dirpath, root)
                    depth = 0 if rel == '.' else rel.count(os.sep) + 1
                    if depth > 4:
                        dirnames[:] = []
                        continue
                    dirnames[:] = [d for d in dirnames if d not in _FS_SKIP_DIRS]

                    for clue in clues:
                        clue_strip = clue.lstrip('./').lstrip('.\\')
                        clue_basename = os.path.basename(clue_strip)
                        clue_parent = os.path.dirname(clue_strip)

                        if clue_basename not in filenames:
                            continue

                        full_path = os.path.join(dirpath, clue_basename)

                        if clue_parent and clue_parent != '.':
                            if not dirpath.endswith(clue_parent.replace('/', os.sep)):
                                if clue_parent.replace('/', os.sep) not in dirpath:
                                    continue
                            norm_parent = clue_parent.replace('/', os.sep).replace('\\', os.sep)
                            if dirpath.endswith(norm_parent):
                                self._base_dir = dirpath[:-len(norm_parent)].rstrip('/\\') or '/'
                            else:
                                idx = dirpath.find(norm_parent)
                                if idx >= 0:
                                    self._base_dir = dirpath[:idx].rstrip('/\\') or '/'
                                else:
                                    self._base_dir = os.path.dirname(dirpath)
                        else:
                            self._base_dir = dirpath

                        if self._base_dir and os.path.isdir(self._base_dir):
                            self._remember_resource_dir(full_path)
                            self._log(f"文件系统搜索检测到基础目录: {self._base_dir} (线索: {clue} -> {full_path})")
                            return self._base_dir

            except Exception as e:
                self._log(f"搜索 {root} 失败: {e}", level='error')
                continue

        self._base_dir = SCRIPT_DIR
        self._log(f"未检测到用户文件目录，回退到 SCRIPT_DIR: {self._base_dir}")
        return self._base_dir

    def _resolve_file_path(self, path, base_dirs=None):
        if not path or self._is_remote_path(path):
            return None, None

        if os.path.isabs(path) and os.path.exists(path):
            d = os.path.dirname(path)
            return path, d

        basename = os.path.basename(path)
        strip = path.lstrip('./').lstrip('.\\')
        strip_parent = os.path.dirname(strip)

        candidates = []

        base = self._get_base_dir()
        for b in [base, SCRIPT_DIR, os.getcwd()]:
            if b:
                candidates.append(os.path.join(b, strip))
                candidates.append(os.path.join(b, basename))
                if strip_parent:
                    candidates.append(os.path.join(b, strip_parent, basename))

        for rd in getattr(self, '_resource_dirs', []) or []:
            if rd:
                candidates.append(os.path.join(rd, strip))
                candidates.append(os.path.join(rd, basename))

        p = SCRIPT_DIR
        for _ in range(3):
            p = os.path.dirname(p)
            if p and os.path.isdir(p):
                candidates.append(os.path.join(p, strip))
                candidates.append(os.path.join(p, basename))

        if base_dirs is None:
            base_dirs = _COMMON_USER_DIRS
        for b in base_dirs:
            candidates.append(os.path.join(b, strip))
            candidates.append(os.path.join(b, basename))

        seen = set()
        for cand in candidates:
            if not cand or cand in seen:
                continue
            seen.add(cand)
            if os.path.exists(cand):
                self._remember_resource_dir(cand)
                cand_dir = os.path.dirname(cand)
                if strip_parent and strip_parent != '.':
                    if cand_dir.endswith(strip_parent.replace('/', os.sep)):
                        inferred_base = cand_dir[:-len(strip_parent)].rstrip('/\\') or '/'
                    else:
                        inferred_base = cand_dir
                else:
                    inferred_base = cand_dir
                return cand, inferred_base

        for root in _FS_SEARCH_ROOTS:
            if not os.path.isdir(root):
                continue
            try:
                for dirpath, dirnames, filenames in os.walk(root):
                    rel = os.path.relpath(dirpath, root)
                    depth = 0 if rel == '.' else rel.count(os.sep) + 1
                    if depth > 4:
                        dirnames[:] = []
                        continue
                    dirnames[:] = [d for d in dirnames if d not in _FS_SKIP_DIRS]

                    if basename not in filenames:
                        continue

                    found = os.path.join(dirpath, basename)

                    if strip_parent and strip_parent != '.':
                        norm_parent = strip_parent.replace('/', os.sep).replace('\\', os.sep)
                        if not dirpath.endswith(norm_parent) and norm_parent not in dirpath:
                            continue
                        if dirpath.endswith(norm_parent):
                            inferred_base = dirpath[:-len(norm_parent)].rstrip('/\\') or '/'
                        else:
                            idx = dirpath.find(norm_parent)
                            inferred_base = dirpath[:idx].rstrip('/\\') or '/' if idx >= 0 else dirpath
                    else:
                        inferred_base = dirpath

                    self._remember_resource_dir(found)
                    return found, inferred_base

            except Exception:
                continue

        return None, None

    def _resolve_resource_path(self, source):
        if not source:
            return None, None
        source = source.strip()

        if self._is_remote_path(source):
            return 'remote', source

        if os.path.isabs(source) and os.path.exists(source):
            return 'local', source

        found, _ = self._resolve_file_path(source)
        if found:
            return 'local', found

        base = self._get_base_dir()
        if source.startswith('./') or source.startswith('.\\'):
            return 'local', os.path.join(base, source[2:])
        elif not os.path.isabs(source):
            return 'local', os.path.join(base, source)
        else:
            return 'local', source

    def _resolve_local_path(self, path):
        if not path or self._is_remote_path(path):
            return path
        if os.path.isabs(path) and os.path.exists(path):
            return path

        found, _ = self._resolve_file_path(path)
        if found:
            return found
        return path

    def _remember_resource_dir(self, file_path):
        try:
            d = os.path.dirname(os.path.abspath(file_path))
            if d and d not in self._resource_dirs:
                self._resource_dirs.insert(0, d)
                parent = os.path.dirname(d)
                if parent and parent not in self._resource_dirs:
                    self._resource_dirs.append(parent)
                self._log(f"记录资源目录: {d}")
        except Exception:
            pass

    def _load_json_resource(self, source, allow_decrypt=False):
        if not source:
            return None
        source = source.strip()

        if self._is_remote_path(source):
            try:
                if self.session is None:
                    self._init_session()
                resp = self.session.get(source, timeout=(10, 30), verify=False)
                if resp.status_code != 200:
                    self._log(f"远程资源返回非200: {source} [{resp.status_code}]")
                    return None
                text = _decode_bytes(resp.content)
                try:
                    return json.loads(text)
                except Exception:
                    if allow_decrypt:
                        dec = try_decrypt_content(text, source, self.external_api_url, self.session, max_rounds=5)
                        if dec:
                            try:
                                return json.loads(dec)
                            except Exception:
                                m = re.search(r'\{[\s\S]*\}', dec)
                                if m:
                                    try:
                                        return json.loads(m.group())
                                    except Exception:
                                        pass
                                m2 = re.search(r'"(?:lives)"\s*:\s*(\[[\s\S]*?\])', dec)
                                if m2:
                                    try:
                                        return {"lives": json.loads(m2.group(1))}
                                    except Exception:
                                        pass
                    return None
            except Exception as e:
                self._log(f"远程加载失败 {source}: {e}", level='error')
                return None

        candidates_to_try = []

        if os.path.isabs(source) and os.path.exists(source):
            candidates_to_try.append(source)

        found, found_base = self._resolve_file_path(source)
        if found:
            candidates_to_try.append(found)

        base = self._get_base_dir()
        strip = source.lstrip('./').lstrip('.\\')
        for b in [base, SCRIPT_DIR, os.getcwd()]:
            if b:
                candidates_to_try.append(os.path.join(b, strip))
                candidates_to_try.append(os.path.join(b, os.path.basename(source)))

        for rd in getattr(self, '_resource_dirs', []) or []:
            if rd:
                candidates_to_try.append(os.path.join(rd, strip))
                candidates_to_try.append(os.path.join(rd, os.path.basename(source)))

        for b in _COMMON_USER_DIRS:
            candidates_to_try.append(os.path.join(b, strip))
            candidates_to_try.append(os.path.join(b, os.path.basename(source)))

        seen = set()
        uniq_candidates = []
        for c in candidates_to_try:
            if c and c not in seen:
                seen.add(c)
                uniq_candidates.append(c)

        last_err = None
        for cand in uniq_candidates:
            if not os.path.exists(cand):
                continue
            try:
                data = json.loads(_read_text_file(cand))
                self._remember_resource_dir(cand)
                return data
            except json.JSONDecodeError as e:
                last_err = e
                try:
                    data = json.loads(
                        self._clean_json_comments(_read_text_file(cand)))
                    self._remember_resource_dir(cand)
                    self._log(f"配置文件格式已自动修复: {cand}")
                    return data
                except Exception:
                    self._log(f"本地文件JSON解析失败 {cand}: {e}", level='error')
            except Exception as e:
                last_err = e
                self._log(f"读取本地文件失败 {cand}: {e}", level='error')

        if last_err is None:
            self._log(f"本地文件不存在: {source} (base={self._get_base_dir()})")
        return None

    def _load_config_file(self, path):
        if not path:
            return None
        return self._load_json_resource(path, allow_decrypt=False)

    def _load_ext_from_path(self, path):
        if not path:
            return None
        result = self._load_json_resource(path, allow_decrypt=False)
        if result is not None:
            return result
        if self._is_remote_path(path):
            return None

        candidates = []
        strip = path.lstrip('./').lstrip('.\\')
        basename = os.path.basename(path)

        found, _ = self._resolve_file_path(path)
        if found:
            candidates.append(found)

        for b in [self._get_base_dir(), SCRIPT_DIR, os.getcwd()]:
            if b:
                candidates.append(os.path.join(b, path))
                candidates.append(os.path.join(b, strip))

        for rd in getattr(self, '_resource_dirs', []) or []:
            if rd:
                candidates.append(os.path.join(rd, strip))
                candidates.append(os.path.join(rd, basename))

        for b in _COMMON_USER_DIRS:
            candidates.append(os.path.join(b, strip))
            candidates.append(os.path.join(b, basename))

        seen = set()
        for p in candidates:
            if not p or p in seen:
                continue
            seen.add(p)
            if os.path.exists(p):
                try:
                    data = json.loads(_read_text_file(p))
                    self._remember_resource_dir(p)
                    return data
                except Exception as e:
                    self._log(f"读取配置失败 {p}: {e}", level='warn')
                    continue
        return None

    def _init_site_state(self, site_id):
        if site_id not in self._site_states:
            self._site_states[site_id] = {
                'decrypt_status': 'idle', 'decrypt_msg': '未执行',
                'localize_status': 'idle', 'localize_msg': '未执行',
                'decrypt_result': None,
                'localize_result': None,
            }

    def _get_site_status_icon(self, status):
        icons = {'idle': '⚪', 'processing': '🔄', 'success': '✅', 'error': '❌'}
        return icons.get(status, '⚪')

    def _get_decrypt_status_text(self, site):
        state = self._site_states.get(site['id'], {})
        status = state.get('decrypt_status', 'idle')
        msg = state.get('decrypt_msg', '未执行')
        icon = self._get_site_status_icon(status)
        if status == 'processing':
            return f"{icon} 解密中..."
        elif status == 'success':
            return f"{icon} 已解密"
        elif status == 'error':
            return f"{icon} 解密失败"
        else:
            return f"{icon} 未执行"

    def _get_localize_status_text(self, site):
        state = self._site_states.get(site['id'], {})
        status = state.get('localize_status', 'idle')
        msg = state.get('localize_msg', '未执行')
        icon = self._get_site_status_icon(status)
        if status == 'processing':
            return f"{icon} 本地化中..."
        elif status == 'success':
            return f"{icon} 已本地化"
        elif status == 'error':
            return f"{icon} 本地化失败"
        else:
            return f"{icon} 未执行"

    def _log_dir(self):
        return (getattr(self, 'log_dir', None)
                or os.path.join(self.download_output_dir or SCRIPT_DIR, 'log'))

    def _rotate_log_if_needed(self, path):
        try:
            if os.path.getsize(path) < LOG_FILE_MAX_BYTES:
                return
        except Exception:
            return
        try:
            oldest = "%s.%d" % (path, LOG_FILE_BACKUPS)
            if os.path.exists(oldest):
                os.remove(oldest)
            for i in range(LOG_FILE_BACKUPS - 1, 0, -1):
                src = "%s.%d" % (path, i)
                if os.path.exists(src):
                    os.rename(src, "%s.%d" % (path, i + 1))
            os.rename(path, "%s.1" % path)
        except Exception as e:
            self._log("日志轮转失败: {}".format(e))

    def _flush_log_lines(self, lines):
        if not lines:
            return
        try:
            log_dir = self._log_dir()
            if log_dir not in self._log_dirs_ready:
                os.makedirs(log_dir, exist_ok=True)
                self._log_dirs_ready.add(log_dir)
            path = os.path.join(log_dir, 'download.log')
            self._rotate_log_if_needed(path)
            with open(path, 'a', encoding='utf-8') as f_local:
                f_local.write("\n".join(lines) + "\n")
        except Exception:
            pass

    def _start_log_writer(self):
        t = getattr(self, '_log_writer_thread', None)
        if t is not None and t.is_alive():
            return
        spider = self

        def _writer():
            buf = []
            last_flush = time.time()
            while True:
                try:
                    item = spider._log_file_queue.get(timeout=LOG_FILE_IDLE_TIMEOUT)
                except Exception:
                    item = None
                if item is _LOG_SENTINEL:
                    if buf:
                        spider._flush_log_lines(buf)
                    return
                if item is not None:
                    buf.append(item)
                now = time.time()
                if buf and (len(buf) >= LOG_FILE_FLUSH_LINES
                            or now - last_flush >= LOG_FILE_FLUSH_SECONDS):
                    spider._flush_log_lines(buf)
                    buf = []
                    last_flush = now

        t = threading.Thread(target=_writer, daemon=True)
        self._log_writer_thread = t
        t.start()

    def _log_flush(self, timeout=2.0):
        q = getattr(self, '_log_file_queue', None)
        if q is None:
            return
        try:
            q.put_nowait(_LOG_SENTINEL)
        except Exception:
            pass
        t = getattr(self, '_log_writer_thread', None)
        if t is not None and t.is_alive():
            t.join(timeout)

    def _log_level_threshold(self):
        try:
            name = str(getattr(self, 'log_level', '') or '').strip().lower()
            return LOG_LEVELS.get(name, LOG_LEVELS[LOG_LEVEL_DEFAULT])
        except Exception:
            return LOG_LEVELS[LOG_LEVEL_DEFAULT]

    def _log(self, msg, level='info'):
        try:
            lv = LOG_LEVELS.get(str(level or 'info').lower(), LOG_LEVELS['info'])
        except Exception:
            lv = LOG_LEVELS['info']
        if lv < self._log_level_threshold():
            return
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{level.upper()}] {msg}"
        print(line)
        self._push_log(msg, level=level)
        if not getattr(self, 'log_enabled', True):
            return
        q = getattr(self, '_log_file_queue', None)
        if q is None:
            self._flush_log_lines([line])
            return
        try:
            q.put_nowait(line)
            self._start_log_writer()
        except Exception:
            pass

    def _init_session(self):
        if self._session is None:
            self._session = requests.Session()
            retry = Retry(total=2, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504])
            adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=20)
            self._session.mount('http://', adapter)
            self._session.mount('https://', adapter)
            self._session.headers.update({
                'User-Agent': DEFAULT_USER_AGENT,
                'Accept': '*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Connection': 'keep-alive',
                'Accept-Encoding': 'identity'
            })
            self._session.verify = False
            self.session = self._session

    def _activity(self):
        try:
            from java import jclass
            JClass = jclass("java.lang.Class")
            AT = JClass.forName("android.app.ActivityThread")
            cur = AT.getMethod("currentActivityThread").invoke(None)
            f = AT.getDeclaredField("mActivities")
            f.setAccessible(True)
            for r in f.get(cur).values().toArray():
                rc = r.getClass()
                pf = rc.getDeclaredField("paused")
                pf.setAccessible(True)
                if not pf.getBoolean(r):
                    af = rc.getDeclaredField("activity")
                    af.setAccessible(True)
                    return af.get(r)
        except Exception:
            pass
        return None

    def _run_on_ui(self, ui_builder_fn):
        now = time.time()
        nested = bool(self._dialog_refs)
        if not nested and self._ui_busy and (now - self._ui_last_click) < UI_CLICK_DEBOUNCE:
            self._log("UI 繁忙，忽略重复点击")
            return
        self._ui_last_click = now
        self._ui_busy = True
        try:
            from java import dynamic_proxy
            from java.lang import Runnable
            act = self._activity()
            if not act:
                self._ui_busy = False
                self._log("无法获取当前 Activity（隐藏 API 限制？），已取消本次弹窗")
                return

            spider = self
            class Run(dynamic_proxy(Runnable)):
                def run(self):
                    try:
                        ui_builder_fn(act)
                    except Exception as e:
                        spider._log(f"UI 执行异常: {e}")
                        traceback.print_exc()
                    finally:
                        spider._ui_busy = False

            act.getWindow().getDecorView().post(Run())
        except Exception as e:
            self._log(f"UI 线程执行失败: {e}", level='error')
            self._ui_busy = False

    def _kit(self, act):
        kit = getattr(self, "_ui_kit", None)
        if kit is None or kit.act is not act:
            kit = UIKit(act, self._ui_listeners, logger=self._log)
            self._ui_kit = kit
        try:
            kit.set_tv_focus(self._tv_mode(kit))
        except Exception:
            pass
        return kit

    def _tv_mode(self, kit=None):
        val = getattr(self, "tv_mode", None)
        if val is not None:
            return bool(val)
        if kit is not None:
            try:
                return kit.kind == "tv"
            except Exception:
                pass
        return False

    def _tv_mode_text(self):
        val = getattr(self, "tv_mode", None)
        if val is None:
            return "自动"
        return "开启" if val else "关闭"

    def _show_modern_confirm(self, title, message, on_confirm, extra_buttons=None, show_cancel=True):
        def on_ui(act):
            kit = self._kit(act)
            G = kit.gravity()

            box = kit.vbox()
            msg_view = kit.text(message, size=UITheme.FS_BODY_LG, color=UITheme.TEXT_2,
                                line_spacing=1.5, selectable=True,
                                gravity=G.START if G else None)
            box.addView(msg_view, kit.lp(-1, -2))
            box.setLayoutParams(kit.lp(-1, -2))

            buttons = []
            if isinstance(message, str) and len(message) > 10 and (
                    message.startswith(("http://", "https://", "file://")) or "/" in message):
                buttons.append({
                    "text": "复制", "style": "secondary",
                    "callback": lambda: kit.toast("已复制" if kit.copy(message, title) else "复制失败"),
                    "dismiss": False,
                })
            for b in (extra_buttons or []):
                spec = dict(b)
                spec.setdefault("style", "secondary")
                spec.setdefault("dismiss", False)
                buttons.append(spec)
            if show_cancel:
                buttons.append({"text": "取消", "style": "secondary", "callback": None, "dismiss": True})
            buttons.append({"text": "确定", "style": "primary", "callback": on_confirm, "dismiss": True})

            self._show_dialog(act, title, box, buttons, height_ratio=0)
        self._run_on_ui(on_ui)

    def _show_modern_input(self, title, hint, current_value, on_save, multiline=False):
        def on_ui(act):
            kit = self._kit(act)
            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))

            if hint:
                box.addView(kit.field_label(str(hint)), kit.lp(-1, -2))

            edit = kit.input(hint="", value=current_value if current_value is not None else "",
                             multiline=multiline,
                             min_lines=4 if multiline else 0,
                             max_lines=10 if multiline else 0)
            box.addView(edit, kit.lp(-1, -2))

            def do_save():
                val = str(edit.getText())
                try:
                    on_save(val)
                    kit.toast("已保存")
                except Exception as e:
                    kit.toast(f"保存失败: {e}", long=True)

            buttons = [{"text": "取消", "style": "secondary", "callback": None, "dismiss": True}]
            if current_value and isinstance(current_value, str) and len(current_value) > 5:
                buttons.append({
                    "text": "复制", "style": "secondary", "dismiss": False,
                    "callback": lambda: kit.toast(
                        "已复制" if kit.copy(str(edit.getText()), title) else "复制失败"),
                })
            buttons.append({"text": "保存", "style": "primary", "callback": do_save, "dismiss": True})

            self._show_dialog(act, title, box, buttons, height_ratio=0, on_show=lambda: edit.requestFocus())
        self._run_on_ui(on_ui)

    def _show_modern_input_multi(self, title, fields, on_save, hint=None, extra_buttons=None):
        def on_ui(act):
            kit = self._kit(act)
            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))

            if hint:
                box.addView(kit.hint(str(hint)), kit.lp(-1, -2))

            edits = []
            for spec in fields:
                try:
                    label, value, options = spec
                except Exception:
                    label, value = spec
                    options = {}
                options = options or {}
                if label:
                    box.addView(kit.field_label(str(label)), kit.lp(-1, -2))
                edit = kit.input(
                    hint=options.get("input_hint", ""),
                    value=value if value is not None else "",
                    multiline=bool(options.get("multiline")),
                    min_lines=4 if options.get("multiline") else 0,
                    max_lines=10 if options.get("multiline") else 0,
                )
                box.addView(edit, kit.lp(-1, -2))
                edits.append(edit)

            def do_save():
                values = [str(e.getText()) for e in edits]
                try:
                    on_save(values)
                    kit.toast("已保存")
                except Exception as e:
                    kit.toast(f"保存失败: {e}", long=True)

            buttons = list(extra_buttons or [])
            for b in buttons:
                spec = dict(b)
                spec.setdefault("style", "secondary")
                spec.setdefault("dismiss", False)
            buttons.append({"text": "取消", "style": "secondary", "callback": None, "dismiss": True})
            buttons.append({"text": "保存", "style": "primary", "callback": do_save, "dismiss": True})

            def focus_first():
                if edits:
                    edits[0].requestFocus()
            self._show_dialog(act, title, box, buttons, height_ratio=0, on_show=focus_first)
        self._run_on_ui(on_ui)

    def _show_modern_info(self, title, message, show_copy=False):
        def on_ui(act):
            kit = self._kit(act)
            G = kit.gravity()
            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))
            box.addView(kit.text(message, size=UITheme.FS_BODY, color=UITheme.TEXT_2,
                                 line_spacing=1.45, selectable=True,
                                 gravity=G.START if G else None), kit.lp(-1, -2))

            buttons = []
            if show_copy:
                buttons.append({
                    "text": "复制", "style": "secondary", "dismiss": False,
                    "callback": lambda: kit.toast(
                        "已复制到剪贴板" if kit.copy(message, title) else "复制失败"),
                })
            buttons.append({"text": "关闭", "style": "primary", "callback": None, "dismiss": True})

            self._show_dialog(act, title, box, buttons, height_ratio=0.75)
        self._run_on_ui(on_ui)

    def _ui_radio_group(self, kit, entries, current=None, id_base=1000):
        RadioGroup = kit.j("android.widget.RadioGroup")
        RadioButton = kit.j("android.widget.RadioButton")
        LinearLayout = kit.j("android.widget.LinearLayout")
        if not (RadioGroup and RadioButton):
            return None, {}
        group = RadioGroup(kit.act)
        try:
            group.setOrientation(LinearLayout.VERTICAL)
        except Exception:
            pass
        group.setLayoutParams(kit.lp(-1, -2))
        buttons = {}
        current_str = str(current) if current is not None else ""
        for idx, item in enumerate(entries):
            val, display = item
            rb = RadioButton(kit.act)
            rb.setId(id_base + idx)
            rb.setText(str(display))
            rb.setTextSize(kit.fs(UITheme.FS_BODY_LG))
            rb.setTextColor(kit.color(UITheme.TEXT))
            try:
                rb.setTypeface(kit.typeface().DEFAULT)
                rb.setSingleLine(True)
                rb.setIncludeFontPadding(False)
            except Exception:
                pass
            kit._ellipsize(rb)
            pad = kit.dp(UITheme.S_SM)
            rb.setPadding(pad, pad, pad, pad)
            self._set_row_bg(kit, rb, idx)
            self._apply_row_focus(kit, rb)
            group.addView(rb, kit.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_XS)))
            buttons[val] = rb
            if str(val) == current_str:
                try:
                    group.check(rb.getId())
                except Exception:
                    pass
        return group, buttons

    def _show_modern_radio_selector(self, title, options, current_value, on_confirm, extra_buttons=None):
        def on_ui(act):
            kit = self._kit(act)

            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))
            box.addView(kit.hint("请选择一项（单选）"), kit.lp(-1, -2))

            entries = []
            for item in options:
                try:
                    val, display = item
                except Exception:
                    val, display = item, str(item)
                entries.append((val, display))
            group, radio_buttons = self._ui_radio_group(kit, entries, current_value)
            if group is None:
                kit.toast("无法构建选项列表")
                return
            box.addView(group, kit.lp(-1, -2))

            def do_confirm():
                checked_id = group.getCheckedRadioButtonId()
                if checked_id == -1:
                    kit.toast("请选择一个选项")
                    return
                selected_val = None
                for val, rb in radio_buttons.items():
                    if rb.getId() == checked_id:
                        selected_val = val
                        break
                if selected_val is not None:
                    on_confirm(selected_val)

            buttons = []
            for b in (extra_buttons or []):
                spec = dict(b)
                spec.setdefault("style", "secondary")
                spec.setdefault("dismiss", False)
                buttons.append(spec)
            buttons.append({"text": "取消", "style": "secondary", "callback": None, "dismiss": True})
            buttons.append({"text": "确定", "style": "primary", "callback": do_confirm, "dismiss": True})

            self._show_dialog(act, title, box, buttons, height_ratio=0.75)
        self._run_on_ui(on_ui)

    FILE_SERVICE_BASE = "http://127.0.0.1:9978/file"
    FILE_SERVICE_PREFIX_CANDIDATES = (
        '/storage/emulated/0', '/sdcard', '/storage/sdcard0', '/storage', '',
    )
    BROWSER_HEIGHT_RATIO = 0.85

    @classmethod
    def _detect_service_port(cls):
        cached = getattr(cls, "_detected_port", None)
        if cached is not None:
            return cached
        port = 0
        try:
            from java import jclass
            proxy = jclass("com.github.catvod.Proxy")
            port = int(proxy.getPort())
        except Exception:
            port = 0
        cls._detected_port = port
        return port

    @classmethod
    def reset_service_port_cache(cls):
        cls._detected_port = None

    def _collect_own_service_ports(self):
        ports = set()
        try:
            p = int(self._detect_service_port())
            if p > 0:
                ports.add(p)
        except Exception:
            pass
        try:
            pr = urllib.parse.urlparse(
                str(self._effective_file_service_base())).port
            if pr:
                ports.add(pr)
        except Exception:
            pass
        try:
            p2 = int(self._effective_proxy_port())
            if p2 > 0:
                ports.add(p2)
        except Exception:
            pass
        try:
            v = int(getattr(self, 'proxy_port', 0) or 0)
            if v > 0:
                ports.add(v)
        except Exception:
            pass
        try:
            ports.add(int(DEFAULT_FILE_SERVICE_PORT))
        except Exception:
            pass
        return ports

    def _effective_file_service_base(self):
        port = self._detect_service_port()
        if port > 0:
            return "http://127.0.0.1:%d/file" % port
        user = str(getattr(self, 'file_service_base', '') or '').strip().rstrip('/')
        if user:
            return user
        return str(self.FILE_SERVICE_BASE)

    def _effective_proxy_port(self):
        port = self._detect_service_port()
        if port > 0:
            return port
        try:
            v = int(getattr(self, 'proxy_port', 0) or 0)
            if v > 0:
                return v
        except Exception:
            pass
        return int(DEFAULT_PROXY_PORT)

    @staticmethod
    def _fs_vpath(p):
        p = str(p or '').replace('\\', '/').strip()
        if not p:
            return '/'
        if not p.startswith('/'):
            p = '/' + p
        p = re.sub(r'/+', '/', p)
        if not p.endswith('/'):
            p += '/'
        return p

    def _fs_rel(self, vpath, prefix):
        v, pv = self._fs_vpath(vpath), self._fs_vpath(prefix)
        if pv != '/' and v.startswith(pv):
            v = '/' + v[len(pv):]
        return self._fs_vpath(v)

    def _fs_real(self, vpath, prefix):
        v = self._fs_vpath(vpath).strip('/')
        if not prefix:
            return '/' + v if v else '/'
        if not v:
            return str(prefix)
        return os.path.join(str(prefix).rstrip('/'), v)

    def _fs_service_url(self, vpath):
        base = str(self._effective_file_service_base() or "").rstrip('/')
        segs = [urllib.parse.quote(s, safe='') for s in str(vpath or '').split('/') if s]
        if not segs:
            return base + '/'
        return base + '/' + '/'.join(segs) + '/'

    def _fs_service_prefix(self):
        cached = getattr(self, "_fs_root_prefix", None)
        if cached:
            return cached
        prefix = '/storage/emulated/0'
        try:
            entries = self._http_file_list('/') or []
            dirs = [n for n, _v, is_dir in entries if is_dir and n not in ('.', '..')]
            picked = None
            if dirs:
                sample = dirs[:8]
                for cand in self.FILE_SERVICE_PREFIX_CANDIDATES:
                    hit = 0
                    for name in sample:
                        p = os.path.join(cand, name) if cand else ('/' + name)
                        try:
                            if os.path.isdir(p):
                                hit += 1
                        except Exception:
                            pass
                    if hit >= max(1, int(len(sample) * 0.6)):
                        picked = cand
                        break
            if picked is not None:
                prefix = picked
        except Exception:
            pass
        self._fs_root_prefix = prefix
        return prefix

    def _http_file_list(self, vpath=None):
        v = self._fs_vpath(vpath)
        try:
            resp = requests.get(self._fs_service_url(v), timeout=6)
            if resp.status_code != 200:
                return None
            return self._parse_file_listing(resp.text, v)
        except Exception:
            return None

    def _parse_file_listing(self, text, base_vpath="/"):
        base = self._fs_vpath(base_vpath)
        items = []
        seen = set()

        svc_path = "/"
        try:
            sp = urllib.parse.urlparse(str(self._effective_file_service_base())).path or "/"
            if not sp.startswith("/"):
                sp = "/" + sp
            svc_path = sp.rstrip("/") or "/"
        except Exception:
            pass

        def add(name, raw_path, is_dir=None):
            raw = urllib.parse.unquote(str(raw_path or "").strip())
            if not raw:
                return
            low = raw.lower()
            if low.startswith(("http://", "https://")):
                return
            v = raw
            if v.startswith("/"):
                if svc_path != "/" and (v == svc_path or v.startswith(svc_path + "/")):
                    v = v[len(svc_path):] or "/"
            else:
                v = base + v
            v = self._fs_vpath(v)
            segs = [s for s in v.strip("/").split("/") if s]
            if not segs:
                return
            nm = urllib.parse.unquote(str(name or "").strip()).rstrip("/") or segs[-1]
            if nm in (".", "..", "/") or nm.lower() in ("parent directory", "上级目录"):
                return
            if is_dir is None:
                is_dir = raw.endswith("/") or ("." not in nm)
            if not is_dir:
                v = v.rstrip("/") or "/"
            key = (v, bool(is_dir))
            if key in seen:
                return
            seen.add(key)
            items.append((nm, v, bool(is_dir)))

        stripped = (text or "").strip()

        if stripped[:1] in ("[", "{"):
            data = None
            try:
                data = json.loads(stripped)
            except Exception:
                data = None
            if data is not None:
                raw = data
                if isinstance(data, dict):
                    raw = None
                    for k in ("files", "list", "data", "items", "result"):
                        if isinstance(data.get(k), list):
                            raw = data[k]
                            break
                    if raw is None:
                        raw = []
                for it in raw:
                    if isinstance(it, str):
                        add(it, it, True)
                    elif isinstance(it, dict):
                        name = (it.get("name") or it.get("filename")
                                or it.get("title") or it.get("text") or "")
                        full = (it.get("path") or it.get("url") or it.get("uri")
                                or it.get("fullPath") or name)
                        is_dir = it.get("isDirectory", it.get("isDir",
                                        it.get("dir", it.get("is_dir", None))))
                        if is_dir is None:
                            t = str(it.get("type", "")).lower()
                            if t in ("dir", "directory", "folder", "0"):
                                is_dir = True
                            elif t in ("file", "1"):
                                is_dir = False
                        add(name, full, is_dir)
                if items:
                    return items

        try:
            for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                                 text or "", re.I | re.S):
                href_raw = m.group(1).strip()
                if href_raw in ("../", "./", "..", "."):
                    continue
                name = re.sub(r"<[^>]+>", "", m.group(2) or "").strip()
                add(name, href_raw, None)
        except Exception:
            pass
        return items or None

    def _show_file_browser(self, title, start_dir, mode="dir", on_pick=None,
                           name_filter=None, manual_title=None, placeholder=None):
        dlg = {"dialog": None}

        def on_ui(act):
            kit = self._kit(act)

            prefix = self._fs_service_prefix()
            state = {
                "vpath": self._fs_vpath(self._fs_rel(start_dir or "/", prefix)),
                "prefix": prefix,
            }

            def finish(value):
                try:
                    if on_pick:
                        on_pick(value)
                finally:
                    try:
                        d = dlg.get("dialog")
                        if d is not None:
                            d.dismiss()
                    except Exception:
                        pass

            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))

            path_label = kit.text("", size=UITheme.FS_CAPTION, color=UITheme.TEXT_2,
                                  mono=True, max_lines=3)
            box.addView(path_label, kit.lp(-1, -2))

            status_label = kit.text("", size=UITheme.FS_CAPTION, color=UITheme.TEXT_3,
                                    max_lines=1)
            box.addView(status_label, kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XXS, 0.0, 0.0)))

            row_h_dp, _icon_dp = kit.row_metrics()
            est_rows = kit.list_min_rows(self.BROWSER_HEIGHT_RATIO)

            list_box = kit.vbox()
            list_box.setLayoutParams(kit.lp(-1, -2))
            try:
                list_box.setMinimumHeight(kit.dp(row_h_dp * est_rows))
            except Exception:
                pass

            scroller = kit.scroll(list_box)
            try:
                scroller.setMinimumHeight(kit.dp(row_h_dp * est_rows))
            except Exception:
                pass
            box.addView(scroller, kit.lp(-1, 0, 1.0, (0.0, UITheme.S_SM, 0.0, 0.0)))

            def real_of(v):
                return self._fs_real(v, state["prefix"])

            def entries_of(v):
                listed = self._http_file_list(v)
                if listed is not None:
                    dirs, files, n_files_all = [], [], 0
                    for name, child, is_dir in listed:
                        if str(name).startswith("."):
                            continue
                        if is_dir:
                            dirs.append((str(name), str(child)))
                        else:
                            n_files_all += 1
                            if mode == "file":
                                if name_filter is not None and not name_filter(str(child)):
                                    continue
                                files.append((str(name), str(child)))
                    dirs.sort(key=lambda x: x[0].lower())
                    files.sort(key=lambda x: x[0].lower())
                    return dirs, files, True, n_files_all, True

                real = real_of(v)
                try:
                    names = os.listdir(real)
                except Exception:
                    return [], [], False, 0, False
                dirs, files, n_files_all = [], [], 0
                for n in names:
                    if n.startswith("."):
                        continue
                    fp = os.path.join(real, n)
                    child = self._fs_vpath(v.rstrip("/") + "/" + n)
                    try:
                        if os.path.isdir(fp):
                            dirs.append((n, child))
                        else:
                            n_files_all += 1
                            if mode == "file":
                                if name_filter is not None and not name_filter(fp):
                                    continue
                                files.append((n, child.rstrip("/") or "/"))
                    except Exception:
                        continue
                dirs.sort(key=lambda x: x[0].lower())
                files.sort(key=lambda x: x[0].lower())
                return dirs, files, False, n_files_all, True

            def make_enter(child):
                def enter():
                    state["vpath"] = self._fs_vpath(child)
                    render()
                return enter

            def make_pick(child):
                def pick():
                    finish(real_of(child))
                return pick

            def empty_message(n_files_all, ok):
                if not ok:
                    return "无法读取此目录\n可点「↑ 上级」返回上一层"
                if mode == "dir" and n_files_all:
                    return ("此目录下没有子文件夹\n"
                            "但还有 {} 个文件（选目录模式不显示文件）".format(n_files_all))
                if mode == "file":
                    return "此目录下没有符合条件的文件\n可点「↑ 上级」返回上一层"
                return "此目录是空的\n可点「↑ 上级」返回上一层"

            def render():
                list_box.removeAllViews()
                v = state["vpath"]
                path_label.setText(real_of(v))

                dirs, files, via_service, n_files_all, ok = entries_of(v)
                status_label.setText(
                    "来源：影视TV 文件服务" if via_service else "来源：本地列举（文件服务不可用）")

                min_rows = state.get("fill_to") or est_rows
                fill_empty = state.get("fill_empty")
                if fill_empty is None:
                    fill_empty = max(est_rows - 2, 1)
                state["row_probe"] = None

                if not dirs and not files:
                    state["empty_card"] = kit.empty(empty_message(n_files_all, ok))
                    list_box.addView(state["empty_card"], kit.lp(-1, -2))
                    kit.fill_rows(list_box, 0, fill_empty)
                else:
                    state["empty_card"] = None
                    idx = 0
                    for name, child in dirs:
                        rv = kit.row(icon="📁", title=name, idx=idx,
                                     trailing=None if mode == "dir" else "进入",
                                     on_click=make_enter(child))
                        list_box.addView(
                            rv, kit.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_XS)))
                        if state["row_probe"] is None:
                            state["row_probe"] = rv
                        idx += 1
                    for name, child in files:
                        rv = kit.row(icon="📄", title=name, idx=idx,
                                     on_click=make_pick(child))
                        list_box.addView(
                            rv, kit.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_XS)))
                        if state["row_probe"] is None:
                            state["row_probe"] = rv
                        idx += 1
                    kit.fill_rows(list_box, idx, min_rows)

                kit.fill_spring(list_box, 0)

            def measure_and_correct(rd=0):
                try:
                    vh = scroller.getHeight()
                    if not vh or vh <= 0:
                        return
                    if state.get("viewport") != vh:
                        state["viewport"] = vh
                        try:
                            list_box.setMinimumHeight(vh)
                        except Exception:
                            pass

                    row_px = state.get("row_px") or kit.dp(row_h_dp)
                    probe = state.get("row_probe")
                    if probe is not None:
                        try:
                            ph = probe.getHeight() or 0
                            if ph > 0:
                                row_px = ph
                                state["row_px"] = ph
                        except Exception:
                            pass
                    if row_px <= 0:
                        return

                    card = state.get("empty_card")
                    if card is not None:
                        try:
                            ch = card.getHeight() or 0
                        except Exception:
                            ch = 0
                        gap = max(kit.dp(UITheme.S_XS), 1)
                        target = max(1, int((vh - ch - gap) // (row_px + gap)))
                        if target == state.get("fill_empty"):
                            return
                        if state.get("mc_rounds", 0) >= 6:
                            return
                        state["mc_rounds"] = state.get("mc_rounds", 0) + 1
                        state["fill_empty"] = target
                        render()
                        return

                    target = kit.measure_fill_rows(
                        scroller, list_box, probe=probe, fallback_row_px=row_px)
                    if not target or target == state.get("fill_to"):
                        return
                    if state.get("mc_rounds", 0) >= 6:
                        return
                    state["mc_rounds"] = state.get("mc_rounds", 0) + 1
                    state["fill_to"] = target
                    render()
                except Exception:
                    pass

            def go_up():
                v = state["vpath"]
                parent = self._fs_vpath(v.rstrip("/").rsplit("/", 1)[0]) if v.strip("/") else "/"
                if parent != v:
                    state["vpath"] = parent
                    render()
                else:
                    kit.toast("已经是根目录")

            def go_root():
                state["vpath"] = "/"
                render()

            def pick_current():
                finish(real_of(state["vpath"]))

            def manual_input():
                def save(v):
                    val = str(v or "").strip()
                    if not val:
                        return
                    finish(val)
                self._show_modern_input(
                    manual_title or title,
                    placeholder or "输入完整路径，如 /storage/emulated/0/...",
                    real_of(state["vpath"]), save)

            render()

            listener = kit.on_layout_ready(scroller, lambda: measure_and_correct(0))
            if listener is None:
                def _retry(rd=0):
                    if rd >= 12:
                        return
                    try:
                        if not (scroller.getHeight() or 0):
                            kit.post(scroller, lambda: _retry(rd + 1))
                            return
                    except Exception:
                        pass
                    measure_and_correct(0)
                kit.post(scroller, lambda: _retry(0))

            buttons = [
                {"text": "↑ 上级", "style": "secondary", "callback": go_up, "dismiss": False},
                {"text": "🏠 根目录", "style": "secondary", "callback": go_root, "dismiss": False},
                {"text": "取消", "style": "secondary", "callback": None, "dismiss": True},
            ]
            if manual_title:
                buttons.append({"text": "✏️ 手动输入", "style": "ghost",
                                "callback": manual_input, "dismiss": True})
            if mode == "dir":
                buttons.append({"text": "✅ 选择当前文件夹", "style": "primary",
                                "callback": pick_current, "dismiss": False})

            dlg["dialog"] = self._show_dialog(
                act, title, box, buttons,
                height_ratio=self.BROWSER_HEIGHT_RATIO,
                scroll=False)
        self._run_on_ui(on_ui)

    def _pick_dir(self, title, current_value, on_save, placeholder=None):
        def start_dir():
            for p in (current_value, getattr(self, "download_output_dir", ""),
                      self._fs_service_prefix(), "/storage/emulated/0", "/sdcard", "/"):
                if p and os.path.isdir(p):
                    return p
            return self._fs_service_prefix() or "/"

        def on_pick(v):
            val = str(v or "").strip()
            if not val:
                return
            try:
                on_save(val)
                self._notify_app("已设置为：{}".format(val))
            except Exception as e:
                self._log("保存目录失败: {}".format(e))
                self._notify_app("保存失败: {}".format(e))

        self._show_file_browser(
            title, start_dir(), mode="dir", on_pick=on_pick,
            manual_title=title, placeholder=placeholder,
        )

    def _with_margin(self, kit, view, left_dp, top_dp=0.0, right_dp=0.0, bottom_dp=0.0):
        if view is None:
            return view
        p = view.getLayoutParams()
        if p is None:
            p = kit.lp(-2, -2)
        p.setMargins(kit.dp(left_dp), kit.dp(top_dp), kit.dp(right_dp), kit.dp(bottom_dp))
        view.setLayoutParams(p)
        return view

    def _set_row_bg(self, kit, view, idx, radius=UITheme.R_MD):
        try:
            kit._set_bg(view, kit._row_bg(idx, True, radius))
        except Exception:
            bg = UITheme.SURFACE_ALT if (idx % 2 == 0) else UITheme.SURFACE
            kit._set_bg(view, kit.shape(bg, radius, 1.0, UITheme.BORDER))

    @staticmethod
    def _apply_row_focus(kit, view, clickable=True):
        try:
            kit.apply_focus(view, clickable)
        except Exception:
            pass

    def _show_dialog(self, act, title, content, buttons, width_ratio=0.92, height_ratio=0.85,
                     back_callback=None, on_show=None, scroll=True):
        spider = self
        kit = self._kit(act)
        dialog = kit.dialog(
            title=title,
            content=content,
            buttons=buttons,
            width_ratio=width_ratio,
            height_ratio=height_ratio,
            back_callback=back_callback,
            scroll=scroll,
            on_dismiss=lambda: setattr(spider, "_ui_busy", False),
        )
        self._dialog_refs.append(dialog)
        dialog.show()
        if on_show:
            try:
                on_show()
            except Exception:
                pass
        return dialog

    def _ui_site_card(self, kit, name, subtitle, checked, on_toggle, actions, dim=False):
        G = kit.gravity()
        card = kit.card(pad=(UITheme.S_MD, UITheme.S_SM, UITheme.S_MD, UITheme.S_SM))

        row = kit.hbox()
        row.setLayoutParams(kit.lp(-1, -2))
        if G:
            row.setGravity(G.CENTER_VERTICAL)

        sw = kit.toggle("", bool(checked), on_toggle, weight=0.0)
        row.addView(sw)

        info = kit.vbox(pad=(UITheme.S_SM, 0.0, 0.0, 0.0))
        info.setLayoutParams(kit.lp(0, -2, 1.0))
        info.addView(kit.text(name, size=UITheme.FS_BODY_LG,
                              color=UITheme.TEXT_3 if dim else UITheme.TEXT,
                              bold=not dim, max_lines=2), kit.lp(-1, -2))
        if subtitle:
            info.addView(kit.text(subtitle, size=UITheme.FS_CAPTION, color=UITheme.TEXT_3,
                                  max_lines=2,
                                  pad=(0.0, UITheme.S_XXS, 0.0, 0.0)), kit.lp(-1, -2))
        row.addView(info)
        card.addView(row, kit.lp(-1, -2))

        if actions:
            card.addView(kit.divider(top=UITheme.S_SM, bottom=UITheme.S_SM))
            bar = kit.button_bar(actions, size="sm")
            if bar is not None:
                card.addView(bar, kit.lp(-1, -2))
        return card

    def _ui_dir_card(self, kit, index, path, checked, on_delete=None,
                     on_long_click=None, state_out=None):
        G = kit.gravity()
        card = kit.card(pad=(UITheme.S_MD, UITheme.S_SM, UITheme.S_MD, UITheme.S_SM))

        row = kit.hbox()
        row.setLayoutParams(kit.lp(-1, -2))
        if G:
            row.setGravity(G.CENTER_VERTICAL)

        sw = kit.toggle("" if index is None else f"{index}. {path}", bool(checked),
                        None, on_long_click, weight=1.0)
        row.addView(sw)
        if isinstance(state_out, dict):
            state_out["switch"] = sw

        if on_delete is not None:
            del_btn = kit.button("删除", "soft_danger", on_delete, None, "sm")
            del_btn.setLayoutParams(
                kit.lp(kit.dp(64 if kit.kind == "phone" else 92), kit.dp(UITheme.H_BTN_SM),
                       0.0, (UITheme.S_SM, 0.0, 0.0, 0.0)))
            row.addView(del_btn)

        card.addView(row, kit.lp(-1, -2))
        return card

    def _push_log(self, msg, level='info'):
        time_str = time.strftime("%H:%M:%S")
        lv = str(level or 'info').lower()
        body = _format_log_block(msg, lv) or str(msg or "")
        try:
            last = self._last_log_line
            if body == last[0]:
                self._log_dup_count += 1
                self._last_log_line = (body, lv)
                return
            if self._log_dup_count > 0:
                self.log_queue.put(
                    ('info', time_str,
                     "%s  …（同上，共 %d 条）" % (last[0], self._log_dup_count + 1)))
                self._log_dup_count = 0
            self._last_log_line = (body, lv)
            self.log_queue.put((lv, time_str, body))
        except Exception:
            try:
                self.log_queue.put((lv, time_str, body))
            except Exception:
                pass

    def _start_log_looper(self, main_handler, view=None, scroll=None,
                          filter_getter=None, auto_getter=None):
        from java import dynamic_proxy
        from java.lang import Runnable
        if self._persisted_runnable is not None:
            return

        spider = self

        class Runnable_Scroll(dynamic_proxy(Runnable)):
            def __init__(self, sc):
                super().__init__()
                self.scroll = sc

            def run(self):
                if self.scroll:
                    try:
                        self.scroll.fullScroll(130)
                    except Exception:
                        pass

        class LogUpdater(dynamic_proxy(Runnable)):
            def __init__(self, handler):
                super().__init__()
                self.handler = handler
                self.view = view
                self.scroll = scroll
                self.miss = 0
                self.alive = True
                self.rendered = 0
                self.auto_getter = auto_getter

            def _alive_view(self):
                v = self.view
                if v is None and spider._active_views:
                    v = spider._active_views.get("log")
                    if v is not None:
                        self.view = v
                return v

            def run(self):
                try:
                    v = self._alive_view()
                    sc = self.scroll
                    if v is None:
                        self.miss += 1
                        if self.miss >= LOOPER_MISS_LIMIT:
                            self.alive = False
                            spider._persisted_runnable = None
                            return
                        self.handler.postDelayed(self, LOOPER_INTERVAL_MS)
                        return
                    self.miss = 0

                    batch = []
                    while len(batch) < LOOPER_BATCH_MAX:
                        try:
                            batch.append(spider.log_queue.get_nowait())
                        except queue.Empty:
                            break

                    if batch:
                        lines = []
                        for item in batch:
                            if isinstance(item, (tuple, list)) and len(item) >= 3:
                                lv, ts, body = item[0], item[1], item[2]
                            else:
                                lv, ts, body = 'info', time.strftime("%H:%M:%S"), str(item)
                            wanted = filter_getter() if filter_getter else None
                            if wanted is not None and lv not in wanted:
                                continue
                            prefix = LOG_LEVEL_TAG.get(lv, "  ")
                            lines.append("[%s] %s %s" % (ts, prefix, body))
                            spider._log_buffer.append((lv, ts, body))
                        if lines:
                            chunk = "\n".join(lines) + "\n"
                            try:
                                v.append(chunk)
                            except Exception:
                                try:
                                    v.setText(str(v.getText()) + chunk)
                                except Exception:
                                    pass
                            spider._log_view_chars += len(chunk)
                            if spider._log_view_chars > LOG_VIEW_MAX_CHARS:
                                try:
                                    cur = str(v.getText())
                                    if len(cur) > LOG_VIEW_MAX_CHARS:
                                        v.setText(cur[-LOG_VIEW_TRIM_TO:])
                                except Exception:
                                    pass
                                try:
                                    spider._log_view_chars = len(str(v.getText()))
                                except Exception:
                                    spider._log_view_chars = 0
                            if sc is not None and auto_getter and auto_getter():
                                try:
                                    sc.post(Runnable_Scroll(sc))
                                except Exception:
                                    pass
                    self.handler.postDelayed(self, LOOPER_INTERVAL_MS)
                except Exception:
                    try:
                        self.handler.postDelayed(self, LOOPER_INTERVAL_MS)
                    except Exception:
                        self.alive = False
                        spider._persisted_runnable = None

        self._persisted_runnable = LogUpdater(main_handler)
        main_handler.post(self._persisted_runnable)

    def _get_recent_logs(self, lines=100):
        log_file = os.path.join(self.log_dir, 'download.log') if self.log_dir else None
        if not log_file or not os.path.exists(log_file):
            return None
        try:
            with open(log_file, 'rb') as f:
                f.seek(0, os.SEEK_END)
                end = f.tell()
                if end == 0:
                    return None
                block = 8192
                data = b''
                pos = end
                while pos > 0 and data.count(b'\n') <= lines:
                    read_len = min(block, pos)
                    pos -= read_len
                    f.seek(pos)
                    data = f.read(read_len) + data
            text = data.decode('utf-8', errors='replace')
            parts = text.splitlines(True)
            return ''.join(parts[-lines:]) if len(parts) > lines else text
        except Exception:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    all_lines = f.readlines()
                recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
                return ''.join(recent)
            except Exception:
                return None

    def _show_log_dialog(self):
        if self._log_dialog_open and self._persisted_runnable is not None:
            self._push_log("⚠️ 日志面板已在运行中")
            return
        self._log_dialog_open = True
        self._ui_listeners.clear()
        self._active_views.clear()

        def on_ui(act):
            spider = self
            kit = self._kit(act)
            G = kit.gravity()

            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))

            filter_row = kit.hbox()
            filter_row.setLayoutParams(kit.lp(-1, -2))
            if G:
                try:
                    filter_row.setGravity(G.CENTER_VERTICAL)
                except Exception:
                    pass

            level_state = dict(spider._log_view_levels)
            chip_refs = {}
            scroll_state = {"auto": True}

            def _redraw():
                try:
                    parts = []
                    for lv, ts, body in spider._log_buffer:
                        if not level_state.get(lv, True):
                            continue
                        parts.append("[%s] %s %s" % (
                            ts, LOG_LEVEL_TAG.get(lv, " "), body))
                    text = ("\n".join(parts) + "\n") if parts else "（当前筛选下没有日志）\n"
                    log_view.setText(text)
                    spider._log_view_chars = len(text)
                except Exception:
                    pass

            def _chip_text(lv, on):
                return "%s %s" % ("☑" if on else "☐",
                                  LOG_LEVEL_LABEL.get(lv, lv))

            def _refresh_chips():
                for lv, b in chip_refs.items():
                    try:
                        on = level_state.get(lv, True)
                        b.setText(_chip_text(lv, on))
                    except Exception:
                        pass
                try:
                    for lv, b in chip_refs.items():
                        self._set_btn_style(
                            kit, b,
                            "primary" if level_state.get(lv, True)
                            else "secondary")
                except Exception:
                    pass

            for lv in ('debug', 'info', 'warn', 'error'):
                def _mk(lv):
                    def _toggle():
                        level_state[lv] = not level_state.get(lv, True)
                        spider._log_view_levels[lv] = level_state[lv]
                        _refresh_chips()
                        _redraw()
                    return _toggle
                b = kit.button(_chip_text(lv, level_state.get(lv, True)),
                               "primary" if level_state.get(lv, True)
                               else "secondary",
                               _mk(lv), None, "sm")
                chip_refs[lv] = b
                filter_row.addView(
                    b, kit.lp(-2, kit.dp(UITheme.H_BTN_SM), 1.0,
                              (UITheme.S_XS, 0.0, UITheme.S_XS, 0.0)))

            def _preset(levels):
                def _go():
                    for lv in ('debug', 'info', 'warn', 'error'):
                        level_state[lv] = lv in levels
                        spider._log_view_levels[lv] = lv in levels
                        spider._log_view_levels[lv] = lv in levels
                    _refresh_chips()
                    _redraw()
                return _go

            def _toggle_auto_scroll(btn=None):
                scroll_state["auto"] = not scroll_state["auto"]
                try:
                    if btn is not None:
                        btn.setText("⏸ 暂停" if scroll_state["auto"]
                                    else "▶ 继续")
                except Exception:
                    pass
                kit.toast("已暂停滚动" if not scroll_state["auto"]
                          else "已恢复自动滚动")

            preset_row = kit.hbox()
            preset_row.setLayoutParams(kit.lp(-1, -2))
            b_all = kit.button("全选", "secondary", _preset(
                {'debug', 'info', 'warn', 'error'}), None, "sm")
            b_err = kit.button("仅异常", "secondary", _preset(
                {'warn', 'error'}), None, "sm")
            for b in (b_all, b_err):
                preset_row.addView(
                    b, kit.lp(-2, kit.dp(UITheme.H_BTN_SM), 1.0,
                              margins=(UITheme.S_XS, UITheme.S_XS,
                                       UITheme.S_XS, 0.0)))

            box.addView(filter_row, kit.lp(-1, -2))
            box.addView(preset_row, kit.lp(-1, -2))

            recent_logs = self._get_recent_logs(100)
            initial_text = recent_logs if recent_logs else "系统就绪，等待操作...\n"
            spider._log_view_chars = len(initial_text)

            log_view = kit.text(initial_text, size=UITheme.FS_MICRO + 0.5,
                                color=UITheme.TEXT_2, mono=True, line_spacing=1.35,
                                gravity=(G.START | G.TOP) if G else None, selectable=True)
            log_view.setPadding(kit.dp(UITheme.S_MD), kit.dp(UITheme.S_MD),
                                kit.dp(UITheme.S_MD), kit.dp(UITheme.S_MD))
            kit._set_bg(log_view, kit.shape(UITheme.SURFACE_ALT, UITheme.R_MD, 1.0, UITheme.BORDER))

            log_scroll = kit.scroll(log_view, fill=True)
            box.addView(log_scroll, kit.lp(-1, 0, 4.0))

            def do_copy():
                try:
                    text = str(log_view.getText())
                except Exception:
                    text = ""
                kit.toast("日志已复制" if kit.copy(text, "日志") else "复制失败")

            def do_clear():
                try:
                    log_view.setText("")
                    spider._log_view_chars = 0
                    spider._log_buffer.clear()
                except Exception:
                    pass
                kit.toast("已清空显示")

            buttons = [
                {"text": "复制", "style": "secondary",
                 "callback": do_copy, "dismiss": False},
                {"text": "清空", "style": "secondary",
                 "callback": do_clear, "dismiss": False},
                {"text": "⏸ 暂停", "style": "secondary",
                 "callback": _toggle_auto_scroll, "dismiss": False},
                {"text": "关闭", "style": "primary",
                 "callback": None, "dismiss": True},
            ]

            def on_dismiss():
                spider._stop_log_looper()
                spider._log_dialog_open = False
                spider._active_views.clear()
                spider._ui_busy = False

            dialog = kit.dialog(title="✉️ 日志面板", content=box, buttons=buttons,
                                width_ratio=0.96, height_ratio=0.96,
                                scroll=False, on_dismiss=on_dismiss)
            self._dialog_refs.append(dialog)
            dialog.show()

            self._active_views = {"log": log_view, "scroll": log_scroll, "dialog": dialog}

            try:
                Handler = kit.j("android.os.Handler")
                Looper = kit.j("android.os.Looper")
                main_handler = Handler(Looper.getMainLooper())
                self._start_log_looper(
                    main_handler, view=log_view, scroll=log_scroll,
                    filter_getter=lambda: {k for k, v in level_state.items() if v},
                    auto_getter=lambda: scroll_state.get("auto", True))
            except Exception as e:
                self._log(f"日志刷新器启动失败: {e}", level='error')

        self._run_on_ui_log(on_ui)

    @staticmethod
    def _set_btn_style(kit, btn, style):
        try:
            bg_c, tx_c, line_c, press_c = UITheme.STYLES.get(
                style, UITheme.STYLES["secondary"])
            kit._set_bg(btn, kit.pressable(bg_c, press_c,
                                           UITheme.R_SM, 1.0, line_c))
            btn.setTextColor(kit.color(tx_c))
        except Exception:
            pass

    def _stop_log_looper(self):
        r = getattr(self, "_persisted_runnable", None)
        if r is None:
            return
        try:
            setattr(r, "alive", False)
        except Exception:
            pass
        try:
            h = getattr(r, "handler", None)
            if h is not None:
                h.removeCallbacks(r)
        except Exception:
            pass
        self._persisted_runnable = None

    def _on_log_dismiss(self):
        self._stop_log_looper()
        self._log_dialog_open = False
        self._active_views.clear()

    def _run_on_ui_log(self, ui_builder_fn):
        try:
            from java import dynamic_proxy
            from java.lang import Runnable
            act = self._activity()
            if not act:
                self._log("无法获取当前 Activity，日志面板未打开")
                self._ui_busy = False
                return
            class Run(dynamic_proxy(Runnable)):
                def run(self):
                    ui_builder_fn(act)
            act.getWindow().getDecorView().post(Run())
        except Exception:
            self._ui_busy = False

    def _ensure_log_open(self):
        if not self._log_dialog_open:
            self._show_log_dialog()
            time.sleep(0.3)

    def _exec_with_log(self, func, *args, **kwargs):
        self._ensure_log_open()
        try:
            result = func(*args, **kwargs)
            if isinstance(result, str):
                self._log(result)
        except Exception as e:
            self._log(f"执行操作时异常: {e}", level='error')

    def _p(self, d, *keys, default=None):
        for key in keys:
            if key in d:
                return d[key]
        return default

    def _p_bool(self, d, *keys, default=False):
        v = self._p(d, *keys, default=default)
        if isinstance(v, bool):
            return v
        return BOOL_MAP.get(v, bool(v)) if v is not None else default

    def _extract_source_headers(self, item):
        headers = {}
        if not isinstance(item, dict):
            return headers
        h = item.get('header') or item.get('headers')
        if isinstance(h, dict):
            headers.update(h)
        elif isinstance(h, str):
            try:
                headers.update(json.loads(h))
            except Exception:
                pass
        ua = item.get('ua') or item.get('user-agent') or item.get('User-Agent')
        if ua:
            headers['User-Agent'] = ua
        ref = item.get('ref') or item.get('referer') or item.get('Referer')
        if ref:
            headers['Referer'] = ref
        return headers

    def _ensure_headers_with_default(self, headers):
        if not headers:
            headers = {}
        if 'User-Agent' not in headers:
            headers['User-Agent'] = DEFAULT_USER_AGENT
        return headers

    def _parse_url_string(self, input_data):
        base_url = ''
        pic_url = ''
        lives = []
        if '$$$' in input_data:
            parts = input_data.split('$$$', 1)
            base_url = parts[0].strip()
            rest = parts[1].strip()
        else:
            rest = input_data
        if '&&&' in rest:
            parts = rest.split('&&&', 1)
            rest = parts[0].strip()
            pic_url = parts[1].strip()
            if pic_url and not pic_url.startswith(('http://', 'https://')):
                pic_url = base_url + pic_url
        segments = rest.split('#')
        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
            if '$' in seg:
                name, url = seg.split('$', 1)
                if not url.startswith(('http://', 'https://')):
                    url = base_url + url
                lives.append({'name': name.replace('!!', ''), 'url': url, 'img': pic_url})
            else:
                url = seg
                if not url.startswith(('http://', 'https://')):
                    url = base_url + url
                try:
                    req_headers = self._ensure_headers_with_default({})
                    resp = self.session.get(url, timeout=(10, 30), headers=req_headers)
                    if resp.status_code == 200:
                        data = json.loads(resp.text)
                        path_prefix = url[:url.rfind('/')+1]
                        for item in data:
                            if not isinstance(item, dict):
                                continue
                            name = item.get('name', '').replace('!!', '')
                            item_url = item.get('url', '')
                            if not name or not item_url:
                                continue
                            if not item_url.startswith(('http://', 'https://')):
                                item_url = path_prefix + item_url
                            lives.append({'name': name, 'url': item_url, 'img': pic_url, 'headers': self._extract_source_headers(item)})
                except Exception as e:
                    self._log(f"URL字符串子分类请求失败: {url} - {e}", level='error')
        return lives, base_url, pic_url

    def _load_default_config(self):
        default_output = os.path.join(SCRIPT_DIR, "本地包")
        return {
            "sources": [],
            "download_output_dir": default_output,
            "download": {
                "skip_extensions": [".php", ".asp", ".jsp", ".cgi", ".exe", ".dll", ".sh", ".bat"],
                "skip_patterns": [],
                "max_file_size_mb": 100,
                "multipart_min_bytes_kb": int(MULTIPART_MIN_BYTES / 1024),
                "recursive_depth": 2,
                "decrypt": {"enabled": True, "external_api_url": DEFAULT_EXTERNAL_API_URL},
                "overwrite": False,
                "timeout_connect": 10,
                "timeout_read": 60,
                "chunk_size": 8192,
                "max_workers": 8,
                "retry_total": 2,
                "retry_backoff": 0.3,
                "pool_connections": 10,
                "pool_maxsize": 20,
                "category_map": {"js": ".js", "lib": ".json", "py": ".py", "jar": ".jar"},
                "skip_patterns_core": [
                    r"/api\.php/provide/vod",
                    r"/api\.php/app/",
                    r"provide/vod",
                    r"\?url=",
                    r"\{name\}",
                    r"\{date\}",
                    r"\{episode\}",
                    r"proxy://",
                    PLACEHOLDER_RE,
                ]
            },
            "proxy": "",
            "github_proxy": GITHUB_PROXY,
            "concurrent": 3,
            "user_agent": DEFAULT_USER_AGENT,
            "external_api_url": DEFAULT_EXTERNAL_API_URL,
            "log": {
                "enabled": True,
                "level": "debug",
                "dir": os.path.join(default_output, "log")
            }
        }

    CONFIG_KEY_MAP = {
        "": {
            "sources": "接口列表",
            "download_output_dir": "下载目录",
            "download": "下载设置",
            "proxy": "全局代理",
            "github_proxy": "GitHub加速代理",
            "user_agent": "用户代理",
            "external_api_url": "备用解密接口",
            "log": "日志",
            "config_backup_dir": "配置备份目录",
            "file_service_base": "本地文件服务",
            "proxy_port": "内置服务端口",
            "incremental_update": "增量更新",
            "localize_prefer_decrypted": "本地化用解密数据",
            "inject_manager_site": "自动注入管理接口",
            "oktv_switch_timeout": "接口切换超时",
            "decrypt_filename_template": "解密文件命名",
            "localized_filename_template": "本地化文件命名",
            "doctor_checks": "体检项目",
            "tv_mode": "TV模式",
            "root_dirs": "根目录",
            "scan_local_dirs": "扫描目录",
            "scan_local_extensions": "扫描文件类型",
            "concurrent": "并发数",
        },
        "log": {
            "enabled": "启用",
            "level": "级别",
            "dir": "目录",
        },
        "sources[]": {
            "enabled": "启用",
        },
        "download": {
            "overwrite": "覆盖已有文件",
            "max_file_size_mb": "最大文件大小MB",
            "multipart_min_bytes_kb": "分块下载阈值KB",
            "recursive_depth": "递归深度",
            "timeout_connect": "连接超时",
            "timeout_read": "读取超时",
            "chunk_size": "块大小",
            "max_workers": "下载并发数",
            "retry_total": "重试次数",
            "retry_backoff": "重试退避",
            "max_download_seconds": "单文件耗时上限",
            "pool_connections": "连接池数",
            "pool_maxsize": "连接池上限",
            "skip_extensions": "跳过扩展名",
            "skip_patterns": "跳过模式",
            "skip_patterns_core": "核心跳过规则",
            "category_map": "分类映射",
            "decrypt": "解密",
        },
        "download.decrypt": {
            "enabled": "启用",
            "external_api_url": "外部API地址",
        },
        "doctor_checks": {
            "entry": "包入口",
            "missing": "文件缺失",
            "size": "文件大小",
            "truncated": "内容截断",
            "remote": "回源引用",
        },
    }

    CONFIG_KEY_ALIASES = {
        "": {
            "源列表": "sources", "接口": "sources",
            "github代理": "github_proxy", "加速代理": "github_proxy",
        },
        "sources[]": {
            "名称": "name", "地址": "url",
        },
        "download": {"覆盖": "overwrite"},
        "download.decrypt": {"外部接口": "external_api_url"},
    }

    @staticmethod
    def _as_bool(val, default=True):
        if val is None:
            return default
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            v = val.strip().lower()
            if v in ("true", "1", "yes", "y", "on", "是", "开", "启用", "true;"):
                return True
            if v in ("false", "0", "no", "n", "off", "否", "关", "停用", ""):
                return False
        return default

    @staticmethod
    def _flatten_log_keys(obj):
        if not isinstance(obj, dict):
            return obj
        log = obj.get("log")
        if not isinstance(log, dict):
            log = {}
        moved = False
        for flat, inner in (("启用日志", "enabled"),
                            ("日志级别", "level"),
                            ("日志目录", "dir")):
            if flat in obj:
                log.setdefault(inner, obj.pop(flat))
                moved = True
        if moved:
            obj["log"] = log
        return obj

    def _to_display_keys(self, obj, path=""):
        if isinstance(obj, dict):
            mapping = self.CONFIG_KEY_MAP.get(path, {})
            out = {}
            for k, v in obj.items():
                disp = mapping.get(k, k)
                out[disp] = self._to_display_keys(v, self._child_path(path, k))
            return out
        if isinstance(obj, list):
            return [self._to_display_keys(v, path + "[]") if isinstance(v, (dict, list))
                    else v for v in obj]
        return obj

    @staticmethod
    def _child_path(path, key):
        return key if not path else path + "." + key

    def _normalize_config_keys(self, obj, path=""):
        if isinstance(obj, dict):
            mapping = self.CONFIG_KEY_MAP.get(path, {})
            rev = {v: k for k, v in mapping.items()}
            rev.update(self.CONFIG_KEY_ALIASES.get(path, {}))
            new_obj = {}
            for k, v in obj.items():
                real = rev.get(k, k)
                new_obj[real] = self._normalize_config_keys(
                    v, self._child_path(path, real))
            return new_obj
        if isinstance(obj, list):
            return [self._normalize_config_keys(v, path + "[]")
                    if isinstance(v, (dict, list)) else v for v in obj]
        return obj

    def _legacy_normalize_config_keys(self, obj):
        if isinstance(obj, dict):
            new_obj = {}
            key_map = {
                '下载目录': 'download_output_dir',
                '全局代理': 'proxy',
                '并发数': 'concurrent',
                '跳过扩展名': 'skip_extensions',
                '跳过模式': 'skip_patterns',
                '最大文件大小MB': 'max_file_size_mb',
                '分块下载阈值KB': 'multipart_min_bytes_kb',
                '递归深度': 'recursive_depth',
                '覆盖': 'overwrite',
                '连接超时': 'timeout_connect',
                '读取超时': 'timeout_read',
                '块大小': 'chunk_size',
                '解密': 'decrypt',
                '启用': 'enabled',
                '外部API地址': 'external_api_url',
                '源列表': 'sources',
                '接口': 'sources',
                'github代理': 'github_proxy',
                '启用日志': 'log_enabled',
                '日志级别': 'log_level',
                '日志目录': 'log_dir',
            }
            for k, v in obj.items():
                new_key = key_map.get(k, k)
                new_obj[new_key] = self._legacy_normalize_config_keys(v)
            return new_obj
        elif isinstance(obj, list):
            return [self._legacy_normalize_config_keys(item) for item in obj]
        else:
            return obj

    def _load_config_from_ext(self, extend):
        if not extend:
            return None
        extend_str = str(extend).strip()
        if extend_str.startswith('{') or extend_str.startswith('['):
            try:
                return json.loads(extend_str)
            except Exception:
                return None
        else:
            return self._load_config_file(extend_str)

    def _apply_config(self, config):
        config = self._normalize_config_keys(self._flatten_log_keys(config))
        self.config = config
        raw_sources = config.get('sources') or config.get('urls', [])
        self.package_download_sites = []
        for item in raw_sources:
            if isinstance(item, dict) and item.get('url'):
                site = {
                    "id": self._package_download_site_id(item.get('name', '未命名'), item['url']),
                    "name": item.get('name', '未命名'),
                    "url": item['url'],
                    "enabled": self._as_bool(item.get('enabled'), True),
                    "type": "json"
                }
                self.package_download_sites.append(site)
            elif isinstance(item, str):
                site = {
                    "id": self._package_download_site_id(item, item),
                    "name": item,
                    "url": item,
                    "enabled": True,
                    "type": "json"
                }
                self.package_download_sites.append(site)
        self.download_output_dir = config.get('download_output_dir') or config.get('下载目录', '')
        if not self.download_output_dir:
            self.download_output_dir = os.path.join(SCRIPT_DIR, "本地包")
        os.makedirs(self.download_output_dir, exist_ok=True)

        default_download = self._load_default_config()['download']
        user_download = config.get('download', {})
        self.download_config = copy.deepcopy(default_download)
        for k, v in user_download.items():
            if isinstance(v, dict) and k in self.download_config and isinstance(self.download_config[k], dict):
                self.download_config[k].update(v)
            else:
                self.download_config[k] = v
        if config.get('proxy'):
            self.download_config['proxy'] = config['proxy']
        if config.get('github_proxy'):
            self.download_config['github_proxy'] = config['github_proxy']
        if config.get('concurrent'):
            self.download_config['concurrent'] = config['concurrent']

        for site in self.package_download_sites:
            self._init_site_state(site['id'])

        self.user_agent = config.get('user_agent', DEFAULT_USER_AGENT)
        self.category_map = self.download_config.get('category_map', {'js': '.js', 'lib': '.json', 'py': '.py', 'jar': '.jar'})
        self.skip_patterns_core = self.download_config.get(
            'skip_patterns_core', SKIP_PATTERNS_WITH_PLACEHOLDER)
        self.max_workers = self.download_config.get('max_workers', 8)
        self.retry_total = self.download_config.get('retry_total', 2)
        self.retry_backoff = self.download_config.get('retry_backoff', 0.3)
        self.pool_connections = self.download_config.get('pool_connections', 10)
        self.pool_maxsize = self.download_config.get('pool_maxsize', 20)

        self.external_api_url = (
            self.config.get('external_api_url')
            or self.config.get('decrypt', {}).get('external_api_url')
            or self.download_config.get('decrypt', {}).get('external_api_url', DEFAULT_EXTERNAL_API_URL)
        )
        log_cfg = self.config.get('log', {})
        self.log_enabled = log_cfg.get('enabled', self.config.get('log_enabled', True))
        self.log_level = log_cfg.get('level', self.config.get('log_level', LOG_LEVEL_DEFAULT))
        self.log_dir = log_cfg.get('dir', self.config.get('log_dir', os.path.join(self.download_output_dir, 'log')))
        self.config['log'] = {'enabled': self.log_enabled, 'level': self.log_level, 'dir': self.log_dir}
        if self._session is not None:
            self.session = self._session

        if 'config_file' in config:
            self._config_file_path = config['config_file']
        else:
            self._config_file_path = self.config.get('config_file')

        self._load_root_dirs()
        self._load_additional_config()
        self._load_localized_interfaces()
        self._load_site_states()

    def _snapshot_config(self, include_runtime=False):
        config = {
            "sources": [
                {"name": site['name'], "url": site['url'], "enabled": site.get('enabled', True)}
                for site in self.package_download_sites
            ],
            "download_output_dir": self.download_output_dir,
            "download": self.download_config,
            "proxy": self.download_config.get('proxy', ''),
            "github_proxy": self.download_config.get('github_proxy', GITHUB_PROXY),
            "concurrent": self.download_config.get('concurrent', 3),
            "user_agent": getattr(self, 'user_agent', DEFAULT_USER_AGENT),
            "external_api_url": getattr(self, 'external_api_url', DEFAULT_EXTERNAL_API_URL),
            "log": {
                "enabled": getattr(self, 'log_enabled', True),
                "level": getattr(self, 'log_level', 'info'),
                "dir": getattr(self, 'log_dir', os.path.join(self.download_output_dir, 'log'))
            },
            "localized_interfaces": self.localized_interfaces,
            "root_dirs": self.root_dirs,
            "decrypt_filename_template": self.decrypt_filename_template,
            "localized_filename_template": self.localized_filename_template,
            "inject_manager_site": self.inject_manager_site,
            "oktv_switch_timeout": self.oktv_switch_timeout,
            "incremental_update": getattr(self, 'incremental_update', True),
            "localize_prefer_decrypted": getattr(
                self, 'localize_prefer_decrypted', True),
            "file_service_base": getattr(self, 'file_service_base', ''),
            "proxy_port": getattr(self, 'proxy_port', DEFAULT_PROXY_PORT),
            "tv_mode": getattr(self, "tv_mode", None),
        }
        if include_runtime:
            config.update({
                "original_oktv_url": self._original_oktv_url,
                "scan_local_dirs": self.scan_local_dirs,
                "scan_local_extensions": self.scan_local_extensions,
                "site_states": self._snapshot_site_states(),
                "package_download_message": (
                    "" if self._package_download_state in ("queued", "processing")
                    else self._package_download_message),
            })
        return config

    SITE_STATE_FIELDS = (
        'decrypt_status', 'decrypt_msg', 'decrypt_result',
        'localize_status', 'localize_msg', 'localize_result',
    )

    def _snapshot_site_states(self):
        out = {}
        valid_ids = {s['id'] for s in self.package_download_sites}
        for sid, st in self._site_states.items():
            if sid not in valid_ids or not isinstance(st, dict):
                continue
            item = {}
            for key in self.SITE_STATE_FIELDS:
                item[key] = st.get(key)
            for status_key, msg_key in (('decrypt_status', 'decrypt_msg'),
                                        ('localize_status', 'localize_msg')):
                if item.get(status_key) == 'processing':
                    item[status_key] = 'idle'
                    item[msg_key] = '已中断（重启前未完成）'
            out[sid] = item
        return out

    def _load_site_states(self):
        raw = self.config.get('site_states')
        if not isinstance(raw, dict):
            return
        valid_ids = {s['id'] for s in self.package_download_sites}
        restored = 0
        for sid, st in raw.items():
            if sid not in valid_ids or not isinstance(st, dict):
                continue
            state = self._site_states.setdefault(sid, {})
            for key in self.SITE_STATE_FIELDS:
                state[key] = st.get(key)
            if state.get('localize_status') == 'partial':
                state['localize_status'] = 'success'
            restored += 1
        if restored:
            self._log(f"已恢复 {restored} 个站点的任务状态")

    def _prune_site_states(self):
        valid_ids = {s['id'] for s in self.package_download_sites}
        stale = [k for k in self._site_states if k not in valid_ids]
        for k in stale:
            self._site_states.pop(k, None)

    def _write_json_atomic(self, path, data, _display_keys=None):
        if _display_keys is None:
            _display_keys = self._looks_like_config(data)
        if _display_keys:
            try:
                data = self._to_display_keys(data)
            except Exception as e:
                self._log(f"配置转中文键名失败，按原键名写出: {e}", level='debug')
        return self.__write_json_atomic_raw(path, data)

    @staticmethod
    def _looks_like_config(data):
        if not isinstance(data, dict):
            return False
        keys = set(data.keys())
        cn = {"接口列表", "下载设置", "下载目录", "配置备份目录"}
        en = {"sources", "download", "download_output_dir", "config_backup_dir"}
        return len(keys & (cn | en)) >= 2

    def __write_json_atomic_raw(self, path, data):
        temp = path + ".tmp"
        try:
            d = os.path.dirname(temp)
            if d:
                os.makedirs(d, exist_ok=True)
        except Exception:
            pass
        with open(temp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp, path)

    def _save_config_to_file(self, path=None):
        if path is None:
            path = os.path.join(_cache_root, 'config.json')
        with self._config_io_lock:
            try:
                self._write_json_atomic(path, self._snapshot_config())
            except Exception as e:
                self._log(f"保存配置失败: {e}", level='error')
                return
        self._save_persistent_config()

    def _save_persistent_config(self):
        with self._config_io_lock:
            try:
                snapshot = self._snapshot_config(include_runtime=True)
                self._write_json_atomic(PERSISTENT_CONFIG_PATH, snapshot)
                self._log(f"配置已持久化: {PERSISTENT_CONFIG_PATH}", level='debug')
            except Exception as e:
                self._log(f"持久化配置失败: {e}", level='error')
                snapshot = None
        if snapshot is not None:
            self._mirror_config_to_backup(snapshot)

    def _config_backup_dirs(self):
        dirs = []
        seen = set()

        def add(d):
            if not d:
                return
            try:
                d = os.path.abspath(d)
            except Exception:
                return
            if d not in seen:
                seen.add(d)
                dirs.append(d)

        add(str(getattr(self, 'config_backup_dir', '') or '').strip())
        try:
            add(os.path.join(SCRIPT_DIR, CONFIG_BACKUP_SUBDIR))
        except Exception:
            pass
        try:
            add(os.path.join(self.download_output_dir or "", CONFIG_BACKUP_SUBDIR))
        except Exception:
            pass
        return dirs

    def _config_backup_path(self):
        try:
            ds = self._config_backup_dirs()
        except Exception:
            ds = []
        return os.path.join(ds[0], CONFIG_BACKUP_NAME) if ds else None

    def _config_backup_candidates(self):
        out = []
        seen = set()

        def add(path):
            if not path:
                return
            try:
                path = os.path.abspath(path)
            except Exception:
                return
            if path not in seen:
                seen.add(path)
                out.append(path)

        for d in self._config_backup_dirs():
            add(os.path.join(d, CONFIG_BACKUP_NAME))
        for default_out in (DEFAULT_DOWNLOAD_DIR, os.path.join(SCRIPT_DIR, "本地包")):
            try:
                add(os.path.join(default_out, CONFIG_BACKUP_SUBDIR, CONFIG_BACKUP_NAME))
                add(os.path.join(default_out, CONFIG_BACKUP_NAME))
            except Exception:
                pass
        return out

    def _recover_config_backup(self):
        best, best_mtime = None, -1
        for path in self._config_backup_candidates():
            try:
                if not os.path.isfile(path):
                    continue
                data = json.loads(open(path, 'r', encoding='utf-8').read())
                if not isinstance(data, dict) or not data:
                    continue
                data = self._normalize_config_keys(data)
                mtime = os.path.getmtime(path)
                if mtime > best_mtime:
                    best, best_mtime = data, mtime
            except Exception:
                continue
        if best is not None:
            best = self._sanitize_recovered_config(best)
            self._log(f"♻️ 已从备份恢复配置（{len(best)} 项）")
        return best

    def _sanitize_recovered_config(self, data):
        if not isinstance(data, dict):
            return {}
        for key in ('proxy', 'github_proxy'):
            val = data.get(key)
            if not val or not isinstance(val, str):
                continue
            v = val.strip()
            if not (v.startswith('http://') or v.startswith('https://')):
                self._log(f"⚠️ 备份里的 {key} 不是合法地址（{v[:40]}），已忽略")
                data.pop(key, None)
        for key in ('download_output_dir', 'log_dir', 'config_backup_dir'):
            val = data.get(key)
            if val and isinstance(val, str) and not val.strip().startswith('/'):
                self._log(f"⚠️ 备份里的 {key} 不是绝对路径（{val[:40]}），已忽略")
                data.pop(key, None)
        return data

    def _config_backup_root(self):
        d = str(getattr(self, 'config_backup_dir', '') or '').strip()
        if d:
            try:
                return os.path.abspath(d)
            except Exception:
                pass
        dirs = self._config_backup_dirs()
        if dirs:
            return dirs[0]
        return os.path.join(SCRIPT_DIR, CONFIG_BACKUP_SUBDIR)

    def _parse_backup_stamp(self, filename):
        import re
        global CONFIG_BACKUP_STAMP_RE
        if CONFIG_BACKUP_STAMP_RE is None:
            CONFIG_BACKUP_STAMP_RE = re.compile(
                r'down_config\[(\d{6,14})\]')
        m = CONFIG_BACKUP_STAMP_RE.search(str(filename))
        return m.group(1) if m else None

    def _format_backup_time(self, stamp, mtime):
        if stamp:
            for fmt, ln in (("%y%m%d%H%M", 10), ("%y%m%d%H", 8)):
                if len(stamp) == ln:
                    try:
                        import datetime as _dt
                        return _dt.datetime.strptime(
                            stamp, fmt).strftime("%y-%m-%d %H:%M")
                    except Exception:
                        pass
        try:
            import datetime as _dt
            return _dt.datetime.fromtimestamp(mtime).strftime("%y-%m-%d %H:%M")
        except Exception:
            return "未知时间"

    def _list_config_backups(self):
        root = self._config_backup_root()
        out = []
        try:
            if not os.path.isdir(root):
                return out, root
            for fn in os.listdir(root):
                if not fn.lower().endswith('.json'):
                    continue
                if not fn.startswith(CONFIG_BACKUP_PREFIX):
                    continue
                fp = os.path.join(root, fn)
                if not os.path.isfile(fp):
                    continue
                try:
                    st = os.stat(fp)
                    sites = 0
                    try:
                        with open(fp, 'r', encoding='utf-8') as f:
                            raw = json.loads(f.read())
                        pkg = raw.get('sources')
                        sites = len(pkg) if isinstance(pkg, list) else 0
                    except Exception:
                        sites = -1
                    out.append({
                        'path': fp, 'name': fn,
                        'time': self._format_backup_time(
                            self._parse_backup_stamp(fn), st.st_mtime),
                        'size': st.st_size,
                        'stamp': self._parse_backup_stamp(fn) or '',
                        'sites': sites,
                        'mtime': st.st_mtime,
                    })
                except Exception:
                    continue
        except Exception:
            return out, root
        out.sort(key=lambda x: (x['stamp'], x['mtime']), reverse=True)
        return out, root

    def _create_config_backup(self):
        root = self._config_backup_root()
        try:
            os.makedirs(root, exist_ok=True)
        except Exception as e:
            return None, "创建备份目录失败: {}".format(e)
        stamp = time.strftime(CONFIG_BACKUP_STAMP_FMT)
        base = "{}{}{}".format(CONFIG_BACKUP_PREFIX, stamp, "]")
        path, n = os.path.join(root, base + ".json"), 1
        while os.path.exists(path):
            n += 1
            path = os.path.join(root, "{}-{}.json".format(base, n))
        try:
            data = self._snapshot_config()
            with self._config_io_lock:
                self._write_json_atomic(path, data)
            return path, None
        except Exception as e:
            return None, "写入备份失败: {}".format(e)

    def _restore_config_backup_file(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.loads(f.read())
        except Exception as e:
            return "读取备份失败: {}".format(e)
        if not isinstance(data, dict) or not data:
            return "备份内容为空或格式不正确"
        data = self._normalize_config_keys(data)
        data = self._sanitize_recovered_config(data)
        if not data:
            return "备份里没有可用的配置数据"
        try:
            merged = dict(self.config or {})
            merged.update(data)
            self._apply_config(merged)
            self._save_config_to_file()
            return None
        except Exception as e:
            return "恢复失败: {}".format(e)

    def _open_config_backup_dialog(self):
        def on_ui(act):
            spider = self
            kit = self._kit(act)
            holder = {"dlg": None}

            def refresh():
                d = holder.get("dlg")
                if d is not None:
                    try:
                        d.dismiss()
                    except Exception:
                        pass
                self._open_config_backup_dialog()

            def render():
                backups, root = self._list_config_backups()
                box = kit.vbox()
                box.setLayoutParams(kit.lp(-1, -2))
                box.addView(kit.hint("目录：{}".format(root)), kit.lp(-1, -2))
                if not backups:
                    box.addView(kit.empty("还没有备份，点「新建备份」创建一份",
                                          icon="💾"),
                                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))
                for b in backups:
                    sub = "{} · {} KB · {} 个接口".format(
                        b['time'],
                        max(1, b['size'] // 1024),
                        b['sites'] if b['sites'] >= 0 else "?")
                    card = kit.card()
                    card.addView(kit.text(b['name'], size=UITheme.FS_BODY,
                                          color=UITheme.TEXT, bold=True,
                                          max_lines=2),
                                 kit.lp(-1, -2))
                    card.addView(kit.text(sub, size=UITheme.FS_CAPTION,
                                          color=UITheme.TEXT_3, max_lines=1),
                                 kit.lp(-1, -2, 0.0,
                                        (0.0, UITheme.S_XXS, 0.0, 0.0)))
                    kit.bind_click(
                        card,
                        lambda bb=b: self._open_backup_item_dialog(bb, refresh))
                    box.addView(card, kit.lp(-1, -2, 0.0,
                                             (0.0, UITheme.S_XS, 0.0, 0.0)))
                return box

            def do_create():
                path, err = self._create_config_backup()
                if err:
                    kit.toast(err, long=True)
                    return
                kit.toast("已备份：{}".format(os.path.basename(path)), long=True)
                self._log("✅ 已创建配置备份: {}".format(path))
                refresh()

            def do_import():
                start = self._config_backup_path() or \
                    getattr(self, "download_output_dir", "") or \
                    "/storage/emulated/0"
                if not os.path.isdir(start):
                    start = "/storage/emulated/0"

                def on_picked(fp):
                    path = fp if str(fp).startswith("/") else "/" + str(fp)
                    err = self._restore_config_backup_file(path)
                    if err:
                        kit.toast(err, long=True)
                        return
                    kit.toast("已导入并恢复", long=True)
                    self._log("✅ 已从外部文件恢复配置: {}".format(path))
                    refresh()

                self._show_file_browser(
                    "选取配置文件", start, mode="file",
                    on_pick=on_picked,
                    name_filter=lambda fp: str(fp).lower().endswith(".json"),
                    manual_title="选取配置文件",
                    placeholder="输入配置文件完整路径")

            def do_pick_dir():
                start = self._config_backup_path() or \
                    getattr(self, "download_output_dir", "") or \
                    "/storage/emulated/0"

                def on_picked(d):
                    d = d if str(d).startswith("/") else "/" + str(d)
                    if not os.path.isdir(d):
                        kit.toast("不是有效目录", long=True)
                        return
                    self.config_backup_dir = d
                    self.config['config_backup_dir'] = d
                    try:
                        self._save_config_to_file()
                    except Exception:
                        pass
                    kit.toast("备份目录已改为：{}".format(d), long=True)
                    self._log("✅ 配置备份目录已改为 {}".format(d))
                    refresh()

                self._show_file_browser(
                    "选取备份存放目录", start, mode="dir",
                    on_pick=on_picked,
                    manual_title="选取备份存放目录",
                    placeholder="输入目录完整路径")

            holder["dlg"] = self._show_dialog(
                act, "💾 配置备份管理", kit.scroll(render()),
                [
                    {"text": "➕ 新建备份", "style": "primary",
                     "callback": do_create, "dismiss": False},
                    {"text": "📂 导入配置", "style": "info",
                     "callback": do_import, "dismiss": False},
                    {"text": "📁 备份目录", "style": "secondary",
                     "callback": do_pick_dir, "dismiss": False},
                    {"text": "关闭", "style": "secondary",
                     "callback": None, "dismiss": True},
                ], height_ratio=0.86, scroll=False)

        self._run_on_ui(on_ui)

    def _open_backup_item_dialog(self, b, refresh):
        def on_ui(act):
            kit = self._kit(act)
            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))
            box.addView(kit.hint(
                "文件：{}\\n时间：{}\\n接口数：{}".format(
                    b['name'], b['time'],
                    b['sites'] if b['sites'] >= 0 else "未知")),
                kit.lp(-1, -2))

            def do_restore():
                def confirm():
                    err = self._restore_config_backup_file(b['path'])
                    if err:
                        kit.toast(err, long=True)
                        return
                    kit.toast("已恢复，部分设置可能需要重新进入", long=True)
                    self._log("✅ 已从备份恢复配置: {}".format(b['name']))
                    refresh()
                self._show_modern_confirm(
                    "确认恢复",
                    "会用这份备份覆盖当前配置，现有的接口列表、"
                    "任务状态和设置都会变成备份里的样子。",
                    confirm)

            def do_rename():
                def save(v):
                    new = str(v or "").strip()
                    if not new:
                        return
                    if not new.lower().endswith('.json'):
                        new += ".json"
                    if new == b['name']:
                        return
                    target = os.path.join(os.path.dirname(b['path']), new)
                    if os.path.exists(target):
                        kit.toast("已存在同名文件", long=True)
                        return
                    try:
                        os.rename(b['path'], target)
                        kit.toast("已重命名为 {}".format(new), long=True)
                        refresh()
                    except Exception as e:
                        kit.toast("重命名失败: {}".format(e), long=True)
                self._show_modern_input("重命名备份", "输入新的文件名",
                                        b['name'], save)

            def do_delete():
                def confirm():
                    try:
                        os.remove(b['path'])
                        kit.toast("已删除", long=True)
                        self._log("🗑 已删除配置备份: {}".format(b['name']))
                        refresh()
                    except Exception as e:
                        kit.toast("删除失败: {}".format(e), long=True)
                self._show_modern_confirm(
                    "确认删除",
                    "删除后无法找回：{}".format(b['name']), confirm)

            box.addView(kit.button_bar([
                {"text": "♻️ 恢复此备份", "style": "primary",
                 "callback": do_restore, "dismiss": False},
                {"text": "✏️ 重命名", "style": "secondary",
                 "callback": do_rename, "dismiss": False},
                {"text": "🗑 删除", "style": "danger",
                 "callback": do_delete, "dismiss": False},
                {"text": "关闭", "style": "ghost",
                 "callback": None, "dismiss": True},
            ], size="md"), kit.lp(-1, -2, 0.0, (0.0, UITheme.S_MD, 0.0, 0.0)))
            self._show_dialog(act, "备份操作", box, [], height_ratio=0)

        self._run_on_ui(on_ui)

    def _mirror_config_to_backup(self, data):
        wrote = 0
        for d in self._config_backup_dirs():
            path = os.path.join(d, CONFIG_BACKUP_NAME)
            try:
                os.makedirs(d, exist_ok=True)
                with self._config_io_lock:
                    self._write_json_atomic(path, data)
                wrote += 1
            except Exception as e:
                self._log(f"写配置备份失败（不影响主配置）{path}: {e}", level='debug')
        return wrote > 0

    def _load_persistent_config(self):
        if os.path.exists(PERSISTENT_CONFIG_PATH):
            try:
                with open(PERSISTENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict) and self._config_has_user_data(data):
                    return self._normalize_config_keys(data)
                self._log("持久化配置无用户数据（可能是缓存被清理后重建的）"
                          "，尝试从备份恢复")
            except Exception as e:
                self._log(f"加载持久化配置失败，尝试从备份恢复: {e}")
        else:
            self._log("未找到持久化配置（可能是缓存被清理），尝试从备份恢复")
        return self._recover_config_backup()

    def _config_has_user_data(self, data):
        if not isinstance(data, dict) or not data:
            return False
        try:
            data = self._normalize_config_keys(data)
        except Exception:
            pass
        for key in ('sources', 'site_states', 'localized_interfaces', 'root_dirs'):
            val = data.get(key)
            if isinstance(val, (list, dict)) and len(val):
                return True
        for key in ('download_output_dir', 'proxy', 'github_proxy',
                    'user_agent', 'config_backup_dir'):
            if data.get(key):
                return True
        return False

    def _restore_default_config(self):
        try:
            if os.path.exists(CACHE_DIR):
                shutil.rmtree(CACHE_DIR, ignore_errors=True)
            os.makedirs(CACHE_DIR, exist_ok=True)
            if os.path.exists(PERSISTENT_CONFIG_PATH):
                os.remove(PERSISTENT_CONFIG_PATH)
            self._log("已清除缓存和持久化配置")

            removed_backup = []
            for path in self._config_backup_candidates():
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                        removed_backup.append(path)
                except Exception:
                    pass
            if removed_backup:
                self._log(f"已清除配置备份 {len(removed_backup)} 份")

            try:
                FileDownloader._reset_head_cache()
            except Exception:
                pass

            self._site_states.clear()
            self._site_op_threads.clear()
            self._site_cancel_events.clear()
            self._package_download_state = "idle"
            self._package_download_message = ""
            self._package_download_thread = None
            self._package_cancel_event = None
            self._is_downloading = False

            if self._initial_extend is not None:
                self._log("重新加载初始配置...")
                self.inited = False
                self.init(self._initial_extend)
                self._log("✅ 已恢复初始配置")
                return "已恢复初始配置"
            else:
                self._log("未找到初始配置，使用默认配置")
                self.config = self._load_default_config()
                self._apply_config(self.config)
                self._save_config_to_file()
                self._save_persistent_config()
                self._log("✅ 配置已恢复为内置默认值")
                return "配置已恢复为内置默认值"
        except Exception as e:
            self._log(f"恢复初始配置失败: {e}")
            return f"恢复失败: {e}"

    def _update_config_value(self, key_path, value, raw=False, save=True):
        try:
            keys = key_path.split('.')
            target = self.config
            for k in keys[:-1]:
                if k not in target:
                    target[k] = {}
                target = target[k]
            target[keys[-1]] = value
            if save:
                self._save_config_to_file()
                self._save_persistent_config()
            self._log(f"配置已更新: {key_path} = {value}")
        except Exception as e:
            self._log(f"配置更新失败: {e}")
            raise

    def _absolutize_urls(self, obj, base_url):
        if isinstance(obj, dict):
            return {k: self._absolutize_urls(v, base_url) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._absolutize_urls(item, base_url) for item in obj]
        elif isinstance(obj, str):
            if obj.startswith(('http://', 'https://')):
                return obj
            if obj.startswith(('./', '../', '/')):
                return safe_urljoin(base_url, obj)
            return obj
        else:
            return obj

    def _decrypt_single_site(self, site_id):
        site = None
        for s in self.package_download_sites:
            if s['id'] == site_id:
                site = s
                break
        if not site:
            return "接口不存在"
        with self._site_op_lock:
            if site_id in self._site_op_threads and self._site_op_threads[site_id].is_alive():
                return "该接口正在处理中"
            self._init_site_state(site_id)
            self._site_states[site_id]['decrypt_status'] = 'processing'
            self._site_states[site_id]['decrypt_msg'] = '正在解密...'
            cancel_event = threading.Event()
            self._site_cancel_events[site_id] = cancel_event

        def _worker():
            try:
                name = site['name']
                url = site['url']
                if self._is_local_file_site(url):
                    self._site_states[site_id]['decrypt_status'] = 'success'
                    self._site_states[site_id]['decrypt_msg'] = '本地接口，无需解密'
                    self._log(f"【解密】{name} 是本地文件接口，跳过")
                    return
                self._log(f"【解密】开始处理 {name} ({url})")
                download_cfg = copy.deepcopy(self.download_config)
                download_cfg['base_url'] = self._get_base_url(url)
                download_cfg['github_proxy'] = self.config.get('github_proxy', GITHUB_PROXY)
                download_cfg['__own_service_ports__'] = self._collect_own_service_ports()
                download_cfg['user_agent'] = self.user_agent
                downloader = FileDownloader(self.download_output_dir, download_cfg, log_callback=self._log,
                                            cancel_event=cancel_event)
                content = downloader.download_text(url, self._get_base_url(url), force_decrypt=True)
                if cancel_event.is_set():
                    self._site_states[site_id]['decrypt_status'] = 'idle'
                    self._site_states[site_id]['decrypt_msg'] = '已取消'
                    self._log(f"【解密】{name} 已取消")
                    return
                if not content:
                    self._site_states[site_id]['decrypt_status'] = 'error'
                    self._site_states[site_id]['decrypt_msg'] = '下载失败'
                    self._log(f"【解密】{name} 下载失败")
                    self._log_decrypt_summary(name, url, False, "下载失败")
                    return
                try:
                    data = json.loads(content)
                    is_json = True
                except Exception:
                    is_json = False
                base_url = self._get_base_url(url)
                safe_name0 = re.sub(r'[\\/:*?"<>|]', '_', name)
                output_dir, safe_name = self._prepare_output_dir(
                    safe_name0, url, self.download_output_dir)
                dec_path = self._decrypt_artifact_path(output_dir, safe_name)
                if is_json:
                    data = self._absolutize_urls(data, base_url)
                    if isinstance(data, dict):
                        data['warningText'] = WARNING_TEXT
                        data[PROCESS_INFO_KEY] = self._build_process_info(
                            source_url=url, source_name=name,
                            stats={"downloaded": 0, "failed": 0},
                            extra={"处理类型": "解密（仅还原接口代码，未下载资源文件）"})
                    with open(dec_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    self._site_states[site_id]['decrypt_status'] = 'success'
                    self._site_states[site_id]['decrypt_msg'] = '明文JSON已保存'
                    self._site_states[site_id]['decrypt_result'] = dec_path
                    self._log(f"【解密】{name} 为明文JSON，已保存")
                    self._log_decrypt_summary(name, url, True, "接口本身是明文 JSON，无需解密")
                else:
                    dec = try_decrypt_content(content, url, self.external_api_url, self._session, max_rounds=5)
                    if dec:
                        parse_success = False
                        cleaned = dec
                        try:
                            data = json.loads(dec)
                            parse_success = True
                        except json.JSONDecodeError as je:
                            self._log(f"【解密】{name} 首次解析失败，尝试清理注释与修复格式...")
                            cleaned = self._clean_json_comments(dec)
                            try:
                                data = json.loads(cleaned)
                                parse_success = True
                                self._log(f"【解密】{name} 修复后解析成功")
                            except json.JSONDecodeError as je2:
                                self._log(f"【解密】{name} 修复后仍无法解析："
                                          f"{self._json_error_hint(cleaned, je2)}")

                        if parse_success:
                            try:
                                data = self._absolutize_urls(data, base_url)
                                if isinstance(data, dict):
                                    data['warningText'] = WARNING_TEXT
                                    data[PROCESS_INFO_KEY] = self._build_process_info(
                                        source_url=url, source_name=name,
                                        stats={"downloaded": 0, "failed": 0},
                                        extra={"处理类型": "解密（还原接口代码并解析为 JSON）"})
                                with open(dec_path, 'w', encoding='utf-8') as f:
                                    json.dump(data, f, ensure_ascii=False, indent=2)
                                self._site_states[site_id]['decrypt_status'] = 'success'
                                self._site_states[site_id]['decrypt_msg'] = '解密成功'
                                self._site_states[site_id]['decrypt_result'] = dec_path
                                self._log(f"【解密】{name} 解密成功，已保存")
                                self._log_decrypt_summary(name, url, True, "解密成功")
                            except Exception as e:
                                self._log(f"【解密】{name} 处理异常: {e}")
                                self._site_states[site_id]['decrypt_status'] = 'error'
                                self._site_states[site_id]['decrypt_msg'] = f'处理异常: {str(e)[:30]}'
                        else:
                            with open(dec_path, 'w', encoding='utf-8') as f:
                                f.write(cleaned)
                            self._site_states[site_id]['decrypt_status'] = 'success'
                            self._site_states[site_id]['decrypt_msg'] = '解密成功(非JSON)'
                            self._site_states[site_id]['decrypt_result'] = dec_path
                            self._log(f"【解密】{name} 解密成功（仍非标准JSON，已保存修复后的文本）")
                    else:
                        self._site_states[site_id]['decrypt_status'] = 'error'
                        self._site_states[site_id]['decrypt_msg'] = '解密失败'
                        self._log(f"【解密】{name} 解密失败")
            except Exception as e:
                self._site_states[site_id]['decrypt_status'] = 'error'
                self._site_states[site_id]['decrypt_msg'] = f'异常: {str(e)[:30]}'
                self._log(f"【解密】异常: {e}")
            finally:
                with self._site_op_lock:
                    self._site_op_threads.pop(site_id, None)
                    if site_id in self._site_cancel_events:
                        del self._site_cancel_events[site_id]
                try:
                    self._save_config_to_file()
                except Exception as e:
                    self._log(f"【解密】保存状态失败: {e}")

        t = threading.Thread(target=_worker, daemon=True)
        with self._site_op_lock:
            self._site_op_threads[site_id] = t
        t.start()
        return "已开始解密任务"

    def _localize_single_site(self, site_id):
        site = None
        for s in self.package_download_sites:
            if s['id'] == site_id:
                site = s
                break
        if not site:
            return "接口不存在"
        with self._site_op_lock:
            if site_id in self._site_op_threads and self._site_op_threads[site_id].is_alive():
                return "该接口正在处理中"
            self._init_site_state(site_id)
            self._site_states[site_id]['localize_status'] = 'processing'
            self._site_states[site_id]['localize_msg'] = '正在转换...'
            cancel_event = threading.Event()
            self._site_cancel_events[site_id] = cancel_event

        def _worker():
            try:
                url0 = str(site.get('url') or '')
                if self._is_local_file_site(url0):
                    self._site_states[site_id]['localize_status'] = 'success'
                    self._site_states[site_id]['localize_msg'] = '本地接口，无需本地化'
                    self._log(f"【本地化】{site['name']} 是本地文件接口，跳过")
                    return
                stats = self._process_json_source(site, cancel_event)
                if cancel_event.is_set():
                    self._site_states[site_id]['localize_status'] = 'idle'
                    self._site_states[site_id]['localize_msg'] = '已取消'
                    self._log(f"【本地化】{site['name']} 已取消")
                    return
                downloaded = stats.get('downloaded', 0)
                failed = stats.get('failed', 0)

                self._sync_decrypt_from_localize(site_id, stats, site.get('name', ''))

                remote = int(stats.get('remote_refs', 0) or 0)
                _suffix = f"，{remote}条回源" if remote else ""

                if failed:
                    self._site_states[site_id]['localize_status'] = 'success'
                    self._site_states[site_id]['localize_msg'] = (
                        f"下载{downloaded}个，失败{failed}个{_suffix}")
                    self._log(f"⚠️ 【本地化】{site['name']} 完成但有 {failed} 个文件失败"
                              f"（建议到「🩺 本地包体检」查看并修复）")
                else:
                    self._site_states[site_id]['localize_status'] = 'success'
                    self._site_states[site_id]['localize_msg'] = (
                        f"下载{downloaded}个文件{_suffix}")
                    self._log(f"【本地化】{site['name']} 完成，下载 {downloaded} 个文件")
                if remote:
                    self._log(f"⚠️ 【本地化】{site['name']} 有 {remote} 个引用仍需联网回源"
                              f"（本地化可用，但这些线路断网会失效）")
                self._site_states[site_id]['localize_result'] = stats.get('box_path')
            except Exception as e:
                self._site_states[site_id]['localize_status'] = 'error'
                self._site_states[site_id]['localize_msg'] = f'失败: {str(e)[:30]}'
                self._log(f"【本地化】{site['name']} 失败: {e}")
            finally:
                with self._site_op_lock:
                    self._site_op_threads.pop(site_id, None)
                    if site_id in self._site_cancel_events:
                        del self._site_cancel_events[site_id]
                try:
                    self._save_config_to_file()
                except Exception as e:
                    self._log(f"【本地化】保存状态失败: {e}")

        t = threading.Thread(target=_worker, daemon=True)
        with self._site_op_lock:
            self._site_op_threads[site_id] = t
        t.start()
        return "已开始本地化任务"

    def _run_sites_batch(self, sites, single_fn, label):
        if not sites:
            return "没有选择任何接口"
        site_ids = [s['id'] for s in sites]
        max_workers = max(1, min(SITE_BATCH_MAX_WORKERS, len(site_ids)))
        spider = self

        def _runner():
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                futs = {ex.submit(single_fn, sid): sid for sid in site_ids}
                for fut in as_completed(futs):
                    sid = futs[fut]
                    try:
                        fut.result()
                    except Exception as e:
                        spider._log(f"【{label}】站点 {sid} 异常: {e}")

        threading.Thread(target=_runner, daemon=True).start()
        return f"已开始{label} {len(site_ids)} 个接口（同时最多 {max_workers} 个）"

    def _decrypt_sites(self, sites):
        return self._run_sites_batch(sites, self._decrypt_single_site, "解密")

    def _localize_sites(self, sites):
        return self._run_sites_batch(sites, self._localize_single_site, "本地化")

    def _package_download_site_id(self, name, url):
        payload = "{}\0{}".format(str(name or ""), str(url or ""))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _enabled_package_download_sites(self):
        return [s for s in self.package_download_sites if s.get("enabled", True)]

    def _normalize_package_download_name(self, name):
        name = re.sub(r"[\x00-\x1f]+", " ", str(name or "")).strip()
        name = re.sub(r"\s+", " ", name)
        if not name:
            raise ValueError("备注名不能为空")
        if name in (".", "..") or re.search(r'[\\/:*?"<>|]', name):
            raise ValueError("备注名包含非法字符")
        if len(name) > 40:
            raise ValueError("备注名不能超过40个字符")
        return name

    def _normalize_package_download_url(self, url):
        url = str(url or "").strip().strip('"').strip("'")
        if not url:
            raise ValueError("下载地址不能为空")
        if len(url) > 2048:
            raise ValueError("下载地址过长")
        parsed = urllib.parse.urlparse(url)
        scheme = (parsed.scheme or "").lower()
        if scheme in ("http", "https"):
            if not parsed.netloc:
                raise ValueError("下载地址缺少主机名")
            return url
        if scheme == "file":
            if not (parsed.netloc or parsed.path):
                raise ValueError("本地文件路径不能为空")
            return url
        raise ValueError("下载地址必须是 http / https / file URL")

    @staticmethod
    def _is_local_file_site(url):
        return str(url or "").strip().lower().startswith("file://")

    def _add_site_with_dedup(self, name, url):
        try:
            clean_url = self._normalize_package_download_url(url)
            if not clean_url:
                return ("error", name, "地址为空")
            url_cf = str(clean_url).casefold()
            for item in self.package_download_sites:
                if str(item.get("url", "")).casefold() == url_cf:
                    return ("dup_url", name, "地址已存在：%s" % item.get("name", ""))

            base = self._normalize_package_download_name(name) or "未命名接口"
            final = base
            existing = {str(i.get("name", "")).casefold()
                        for i in self.package_download_sites}
            if final.casefold() in existing:
                n = 1
                while True:
                    cand = "{}-{}".format(base, n)
                    if cand.casefold() not in existing:
                        final = cand
                        break
                    n += 1
                    if n > 999:
                        final = "{}-{}".format(base, int(time.time()) % 10000)
                        break

            saved, created = self._add_or_update_package_download_site(final, clean_url)
            return ("added" if created else "updated", saved.get("name", final), "")
        except Exception as e:
            return ("error", name, str(e))

    def _add_or_update_package_download_site(self, name, url):
        clean_name = self._normalize_package_download_name(name)
        clean_url = self._normalize_package_download_url(url)
        name_match = None
        url_match = None
        for item in self.package_download_sites:
            if str(item.get("name", "")).casefold() == clean_name.casefold():
                name_match = item
            if str(item.get("url", "")).casefold() == clean_url.casefold():
                url_match = item
        if name_match is not None and url_match is not None and name_match is not url_match:
            raise ValueError("备注名和网址分别属于两个已有接口")
        target = name_match or url_match
        created = target is None
        if created:
            if len(self.package_download_sites) >= 50:
                raise ValueError("下载接口最多保存50个")
            target = {
                "id": self._package_download_site_id(clean_name, clean_url),
                "name": clean_name,
                "url": clean_url,
                "enabled": True,
                "type": "json",
            }
            self.package_download_sites.append(target)
        else:
            old_name, old_url = target.get("name"), target.get("url")
            target["name"] = clean_name
            target["url"] = clean_url
            target["type"] = "json"
            if (old_name, old_url) != (clean_name, clean_url):
                old_id = target.get("id") or self._package_download_site_id(old_name, old_url)
                new_id = self._package_download_site_id(clean_name, clean_url)
                if old_id != new_id:
                    target["id"] = new_id
                    if old_id in self._site_states:
                        self._site_states[new_id] = self._site_states.pop(old_id)
                        self._log(f"站点状态已迁移: {old_id} -> {new_id}")
        self._save_config_to_file()
        return dict(target), created

    def _set_package_download_site_states(self, states):
        if not isinstance(states, dict):
            raise ValueError("数据无效")
        changed = False
        for item in self.package_download_sites:
            sid = str(item.get("id", ""))
            if sid in states:
                enabled = bool(states[sid])
                if bool(item.get("enabled", True)) != enabled:
                    item["enabled"] = enabled
                    changed = True
        if changed:
            self._save_config_to_file()
        return changed

    def _delete_package_download_sites(self, site_ids):
        selected = {str(s).strip() for s in site_ids if str(s).strip()}
        if not selected:
            raise ValueError("请选择要删除的下载接口")
        existing = {str(item.get("id", "")).strip() for item in self.package_download_sites}
        matched = selected & existing
        if not matched:
            raise ValueError("选择的下载接口已不存在")
        if len(self.package_download_sites) - len(matched) < 1:
            raise ValueError("至少保留一个下载接口")
        removed = [item for item in self.package_download_sites if str(item.get("id", "")).strip() in matched]
        self.package_download_sites = [item for item in self.package_download_sites if str(item.get("id", "")).strip() not in matched]
        self._prune_site_states()
        self._save_config_to_file()
        return removed

    def _guess_category(self, url, field_key=None):
        if field_key in ('spider', 'jar'):
            return 'jar'
        path_part = url.split('?')[0].split(';')[0].rstrip('/')
        ext = os.path.splitext(path_part)[1].lower()
        if ext == '.jar':
            return 'jar'
        elif ext == '.py':
            return 'py'
        elif ext == '.js':
            return 'js'
        else:
            return 'lib'

    def _walk_and_collect(self, obj, base_url, result, field_key=None):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ('name', 'key'):
                    continue
                new_field = k if k in ('spider', 'jar') else field_key
                if isinstance(v, str):
                    stripped = v.strip()
                    if (stripped.startswith('{') and stripped.endswith('}')) or (stripped.startswith('[') and stripped.endswith(']')):
                        try:
                            parsed = json.loads(stripped)
                            self._walk_and_collect(parsed, base_url, result, new_field)
                            continue
                        except json.JSONDecodeError:
                            pass
                    parts = [p.strip() for p in v.split('$$')]
                    for part in parts:
                        result.add((part, base_url, new_field))
                elif isinstance(v, (dict, list)):
                    self._walk_and_collect(v, base_url, result, new_field)
        elif isinstance(obj, list):
            for item in obj:
                self._walk_and_collect(item, base_url, result, field_key)

    def _collect_files(self, data, base_url, downloader):
        all_items = set()
        self._walk_and_collect(data, base_url, all_items)
        max_depth = self.download_config.get('recursive_depth', 2)
        current_depth = 0
        processed_jsons = set()
        while current_depth < max_depth:
            json_items = [(u, b, fk) for u, b, fk in all_items
                          if u.split('?')[0].split(';')[0].lower().endswith('.json')]
            new_items = set()
            for url, url_base, field_key in json_items:
                if url in processed_jsons:
                    continue
                if not downloader.is_downloadable(url, field_key):
                    continue
                processed_jsons.add(url)
                content = downloader.download_text(url, url_base, force_decrypt=False)
                if content:
                    try:
                        sub_data = json.loads(content)
                        if url.startswith(('http://', 'https://')):
                            parsed = urllib.parse.urlparse(url)
                            sub_base = f"{parsed.scheme}://{parsed.netloc}{os.path.dirname(parsed.path)}/"
                        else:
                            sub_base = url_base
                        self._walk_and_collect(sub_data, sub_base, new_items)
                    except Exception:
                        pass
            if not new_items:
                break
            all_items.update(new_items)
            current_depth += 1
        unique = []
        seen = set()
        for url, url_base, field_key in all_items:
            if url in seen:
                continue
            seen.add(url)
            if downloader.is_downloadable(url, field_key):
                cat = self._guess_category(url, field_key)
                unique.append((url, cat, url_base, field_key))
        return unique

    def _parse_box_json(self, url, downloader):
        base_url = self._get_base_url(url)
        self._log(f"开始下载并解析接口: {url}")
        content = downloader.download_text(url, base_url, force_decrypt=True)
        if not content:
            self._log("下载内容为空")
            return None, None, "下载失败或内容为空"
        try:
            data = json.loads(content)
            self._log("成功解析 JSON", level='debug')
            return data, base_url, None
        except json.JSONDecodeError as e:
            self._log(f"JSON 解析失败: {self._json_error_hint(content, e)}, "
                      f"尝试清理注释并修复格式...")
            content = self._clean_json_comments(content)
            try:
                data = json.loads(content)
                self._log("修复后成功解析 JSON")
                return data, base_url, None
            except json.JSONDecodeError as e2:
                self._log(f"修复后仍失败: {self._json_error_hint(content, e2)}, "
                          f"尝试提取片段...")
        candidate = _best_json_span(content)
        if candidate:
            try:
                data = json.loads(candidate)
                self._log("从提取的片段成功解析 JSON")
                return data, base_url, None
            except Exception:
                pass
        json_pattern = r'(\{[\s\S]*\}|\[[\s\S]*\])'
        matches = re.findall(json_pattern, content)
        for candidate2 in matches:
            try:
                data = json.loads(candidate2)
                self._log("从提取的片段成功解析 JSON")
                return data, base_url, None
            except Exception:
                continue
        decrypted = try_decrypt_content(content, url, self.external_api_url, self._session, max_rounds=5)
        if decrypted:
            self._log("解密成功，尝试解析")
            try:
                data = json.loads(decrypted)
                return data, base_url, None
            except json.JSONDecodeError:
                cleaned = self._clean_json_comments(decrypted)
                try:
                    data = json.loads(cleaned)
                    self._log("解密内容修复后解析成功")
                    return data, base_url, None
                except json.JSONDecodeError as de:
                    self._log(f"解密内容仍无法解析: "
                              f"{self._json_error_hint(cleaned, de)}")
            except Exception:
                matches2 = re.findall(json_pattern, decrypted)
                for candidate in matches2:
                    try:
                        data = json.loads(candidate)
                        return data, base_url, None
                    except Exception:
                        continue
                self._log("解密后仍无法解析为 JSON")
        self._log("所有解析尝试均失败")
        return None, None, "无法解析为 JSON"

    def _download_all(self, paths, downloader):
        total = len(paths)
        if total == 0:
            return
        completed = [0]
        lock = threading.Lock()
        last_progress_time = [time.time()]

        def progress_wrapper(url, cat, base_url, field_key=None):
            if downloader.cancel_event and downloader.cancel_event.is_set():
                return None
            result = downloader.download_file(url, base_url, cat, field_key)
            with lock:
                completed[0] += 1
                now = time.time()
                if now - last_progress_time[0] > 1.0 or completed[0] == total:
                    pct = (completed[0] / total) * 100
                    self._push_log(f"⏳ 总进度 {completed[0]}/{total} ({pct:.1f}%) | 当前: {os.path.basename(url)[:30]}")
                    last_progress_time[0] = now
            return result

        max_workers = min(self.max_workers, max(1, len(paths)))
        self._push_log(f"🚀 启动 {max_workers} 线程并发下载，共 {total} 个文件...")
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(progress_wrapper, url, cat, base_url, field_key): (url, cat)
                       for url, cat, base_url, field_key in paths}
            for fut in as_completed(futures):
                if downloader.cancel_event and downloader.cancel_event.is_set():
                    ex.shutdown(wait=False)
                    break
                try:
                    fut.result()
                except Exception as e:
                    url, cat = futures.get(fut, ("?", "?"))
                    self._log(f"❌ 下载线程异常 {url}: {e}")
                    with downloader._lock:
                        downloader.failed.append((url, str(e)))
        self._push_log(f"✅ 批量下载完成 {completed[0]}/{total}")

    def _find_local_path(self, url, downloader):
        if not url or not isinstance(url, str):
            return None
        url_part, suffix = downloader.split_url_and_suffix(url)

        if url_part in downloader.downloaded:
            rel = downloader.downloaded[url_part]
            if not downloader.exists(rel):
                return None
            return './' + rel.replace('\\', '/')

        variants = set()
        normalized = downloader.normalize_github_url(url_part)
        variants.add(normalized)

        if downloader.github_proxy:
            proxy = downloader.github_proxy.rstrip('/') + '/'
            if url_part.startswith(proxy):
                raw = url_part[len(proxy):]
                variants.add(raw)
                if raw.startswith('raw.githubusercontent.com/'):
                    variants.add('https://' + raw)

        for variant in variants:
            if variant != url_part and variant in downloader.downloaded:
                rel = downloader.downloaded[variant]
                if not downloader.exists(rel):
                    return None
                return './' + rel.replace('\\', '/')

        return None

    def _collect_missing_files(self, data, downloader, base_url=""):
        all_items = set()
        self._walk_and_collect(data, base_url, all_items)
        missing = []
        seen = set()
        for url, _, field_key in all_items:
            if url in seen:
                continue
            seen.add(url)
            if not downloader.is_downloadable(url, field_key):
                continue
            url_part, _ = downloader.split_url_and_suffix(url)
            if url_part in downloader.downloaded:
                continue
            found = False
            variants = [downloader.normalize_github_url(url_part)]
            if downloader.github_proxy:
                proxy = downloader.github_proxy.rstrip('/') + '/'
                if url_part.startswith(proxy):
                    variants.append(url_part[len(proxy):])
            for v in variants:
                if v in downloader.downloaded:
                    found = True
                    break
            if found:
                continue
            cat = self._guess_category(url, field_key)
            missing.append((url, cat, base_url, field_key))
        return missing

    @staticmethod
    def _build_process_info(source_url="", source_name="", stats=None,
                            failed_items=None, extra=None):
        stats = stats or {}
        info = {}
        if source_url:
            info["源接口地址"] = str(source_url)
        if source_name:
            info["接口名称"] = str(source_name)
        info["处理时间"] = time.strftime('%Y-%m-%d %H:%M:%S')
        info["下载文件数"] = int(stats.get("downloaded", 0) or 0)
        info["跳过文件数"] = int(stats.get("unchanged", 0) or 0)
        failed = int(stats.get("failed", 0) or 0)
        info["失败文件数"] = failed
        if failed:
            info["完整性"] = "不完整，缺失 {} 个文件（建议用本地包体检修复）".format(failed)
        else:
            info["完整性"] = "完整"
        remote = int(stats.get("remote_refs", 0) or 0)
        if remote:
            info["回源引用数"] = remote
            info["离线可用性"] = "部分：{} 条引用仍需联网回源".format(remote)
        if failed_items:
            brief = []
            for item in failed_items[:20]:
                try:
                    u, why = item[0], item[1]
                except Exception:
                    continue
                brief.append("{} ({})".format(str(u)[-60:], str(why)[:40]))
            if brief:
                info["失败清单"] = brief
        if extra:
            info.update(extra)
        return info

    def _log_decrypt_summary(self, name, url, ok, reason=""):
        try:
            head = "✅" if ok else "❌"
            self._push_log("{} 【解密】{} —— {}{}".format(
                head, name, "成功" if ok else "失败",
                "（{}）".format(reason) if reason else ""))
            self._push_log("     源：{}".format(url))
        except Exception:
            pass

    def _read_process_info(self, box_path):
        if not box_path or not os.path.exists(box_path):
            return {}
        try:
            with open(box_path, 'r', encoding='utf-8') as f_local:
                data = json.load(f_local)
            info = data.get(PROCESS_INFO_KEY)
            return info if isinstance(info, dict) else {}
        except Exception:
            return {}

    def _log_process_summary(self, name, info):
        try:
            failed = int(info.get("失败文件数", 0) or 0)
            head = ("✅" if failed == 0 else "⚠️")
            self._push_log(
                "{} 【{}】下载 {}，跳过 {}，失败 {} —— {}".format(
                    head, name, info.get("下载文件数", 0),
                    info.get("跳过文件数", 0), failed, info.get("完整性", "")))
            for line in (info.get("失败清单") or [])[:5]:
                self._push_log("     └ 失败：{}".format(line))
            if failed > 5:
                self._push_log("     └ 其余 {} 条失败见「{}」字段".format(
                    failed - 5, PROCESS_INFO_KEY))
            remote = int(info.get("回源引用数", 0) or 0)
            if remote:
                self._push_log(
                    "     ⚠️ 有 {} 个文件没下到本地，已保留远程地址回源"
                    "（该包仍可用，但这些线路需要联网）".format(remote))
            src = info.get("源接口地址")
            if src:
                self._push_log("     源：{}".format(src))
        except Exception:
            pass

    def _generate_local_box(self, data, source_name, output_dir, downloader,
                            base_url=None, source_url=""):
        import json

        remote_refs = {"n": 0}

        def localize(obj, field_key=None):
            if isinstance(obj, dict):
                result = {}
                for k, v in obj.items():
                    if k in ('name', 'key'):
                        result[k] = v
                    elif k == PROCESS_INFO_KEY:
                        continue
                    else:
                        result[k] = localize(v, k)
                return result
            elif isinstance(obj, list):
                return [localize(item, field_key) for item in obj]
            elif isinstance(obj, str):
                stripped = obj.strip()
                if (stripped.startswith('{') and stripped.endswith('}')) or (stripped.startswith('[') and stripped.endswith(']')):
                    try:
                        parsed = json.loads(stripped)
                        replaced = localize(parsed)
                        return json.dumps(replaced, ensure_ascii=False, separators=(',', ':'))
                    except json.JSONDecodeError:
                        pass
                local_path = self._find_local_path(obj, downloader)
                if local_path:
                    return local_path
                s2 = obj.strip()
                if s2 and not s2.lower().startswith(('http://', 'https://')) \
                        and base_url:
                    try:
                        abs_u = downloader.resolve_url(s2, base_url)
                        if abs_u and abs_u.lower().startswith(('http://', 'https://')):
                            remote_refs["n"] += 1
                            return abs_u
                    except Exception:
                        pass
                return obj
            else:
                return obj

        local_data = localize(data)
        local_data['warningText'] = WARNING_TEXT
        info = self._build_process_info(
            source_url=source_url, source_name=source_name,
            stats={"downloaded": downloader.fresh_count,
                   "failed": len({str(u) for u, _ in (
                       list(downloader.failed)
                       + list(getattr(downloader, "repeat_failed", [])))}),
                   "skipped": len(downloader.skipped),
                   "unchanged": len(downloader.unchanged),
                   "remote_refs": remote_refs["n"]},
            failed_items=(list(downloader.failed)
                          + list(getattr(downloader, "repeat_failed", [])))[:20])
        if info:
            local_data[PROCESS_INFO_KEY] = info
            self._log_process_summary(source_name, info)
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', source_name)
        box_filename = self.localized_filename_template.format(name=safe_name)
        box_path = os.path.join(output_dir, box_filename)
        with open(box_path, 'w', encoding='utf-8') as f_local:
            json.dump(local_data, f_local, ensure_ascii=False, indent=2)
        return box_path

    def _resolve_output_dir(self, safe_name, url, output_root):
        base = os.path.join(output_root, safe_name)
        marker = os.path.join(base, ".source_url")
        try:
            if os.path.isfile(marker):
                with open(marker, 'r', encoding='utf-8') as f:
                    if f.read().strip() == str(url).strip():
                        return base, safe_name
        except Exception:
            pass
        if not os.path.isdir(base):
            return base, safe_name
        digest = hashlib.sha1(str(url).encode('utf-8')).hexdigest()[:6]
        new_name = f"{safe_name}_{digest}"
        return os.path.join(output_root, new_name), new_name

    def _prepare_output_dir(self, safe_name, url, output_root=None):
        root = output_root if output_root is not None else self.download_output_dir
        out_dir, final_name = self._resolve_output_dir(safe_name, url, root)
        os.makedirs(out_dir, exist_ok=True)
        try:
            with open(os.path.join(out_dir, ".source_url"),
                      'w', encoding='utf-8') as f:
                f.write(str(url))
        except Exception:
            pass
        return out_dir, final_name

    def _load_decrypted_for_localize(self, output_dir, safe_name, source_url):
        try:
            path = self._decrypt_artifact_path(output_dir, safe_name)
        except Exception:
            return None
        if not path or not os.path.isfile(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                raw = f.read()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = json.loads(self._clean_json_comments(raw))
            if not isinstance(data, (dict, list)) or not data:
                return None
            if isinstance(data, dict):
                data.pop(PROCESS_INFO_KEY, None)
            self._log(f"♻️ 采用已解密的数据作为本地化输入: "
                      f"{os.path.basename(path)}（如需从远端重新解析，"
                      f"请在设置里关闭「本地化优先使用解密产物」）")
            return data
        except Exception as e:
            self._log(f"读取解密产物失败（将改为重新解析）: {e}")
            return None

    def _sync_decrypt_from_localize(self, site_id, stats, name=''):
        dec_path = (stats or {}).get('decrypt_path')
        if not dec_path:
            return False
        try:
            if not os.path.exists(str(dec_path)):
                return False
        except Exception:
            return False
        st = self._site_states.setdefault(site_id, {})
        prev = st.get('decrypt_result')
        if prev and os.path.exists(str(prev)):
            return False
        st['decrypt_result'] = dec_path
        st['decrypt_status'] = 'success'
        st['decrypt_msg'] = '由本地化联动生成'
        self._log(f"【解密】{name or site_id} 已随本地化一并完成")
        return True

    def _adopt_decrypt_artifacts(self):
        fixed = 0
        try:
            for site in (self.package_download_sites or []):
                sid = site.get('id')
                if not sid:
                    continue
                st = self._site_states.get(sid) or {}
                if st.get('decrypt_status') == 'success' and \
                        st.get('decrypt_result') and \
                        os.path.exists(str(st.get('decrypt_result'))):
                    continue
                box = st.get('localize_result')
                if not box or not os.path.exists(str(box)):
                    continue
                out_dir = os.path.dirname(str(box))
                safe = re.sub(r'[\\/:*?"<>|]', '_', site.get('name', '') or '')
                cand = self._decrypt_artifact_path(out_dir, safe)
                if os.path.isfile(cand):
                    st['decrypt_result'] = cand
                    st['decrypt_status'] = 'success'
                    st['decrypt_msg'] = '由本地化联动生成'
                    fixed += 1
        except Exception as e:
            self._log(f"补齐解密状态失败（不影响使用）: {e}")
        if fixed:
            self._log(f"🔗 已补齐 {fixed} 个接口的解密状态（来自已生成的解密产物）")
        return fixed

    def _decrypt_artifact_path(self, output_dir, safe_name):
        return os.path.join(
            output_dir, self.decrypt_filename_template.format(name=safe_name))

    def _write_decrypt_from_data(self, data, name, safe_name, output_dir, url, base_url):
        try:
            if not isinstance(data, dict):
                return None
            os.makedirs(output_dir, exist_ok=True)
            dec_data = copy.deepcopy(data)
            dec_data = self._absolutize_urls(dec_data, base_url)
            dec_data['warningText'] = WARNING_TEXT
            dec_data[PROCESS_INFO_KEY] = self._build_process_info(
                source_url=url, source_name=name,
                stats={"downloaded": 0, "failed": 0},
                extra={"处理类型": "解密（由本地化流程联动生成，"
                                 "引用指向远程地址，未下载资源文件）"})
            dec_path = self._decrypt_artifact_path(output_dir, safe_name)
            with open(dec_path, 'w', encoding='utf-8') as f:
                json.dump(dec_data, f, ensure_ascii=False, indent=2)
            return dec_path
        except Exception as e:
            self._log(f"联动生成解密产物失败（不影响本地化）: {e}")
            return None

    def _process_json_source(self, site, cancel_event=None):
        name = site.get("name", "未命名")
        url = site.get("url", "")
        if not url:
            raise ValueError("接口URL为空")
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', name)
        output_dir, safe_name = self._prepare_output_dir(
            safe_name, url, self.download_output_dir)
        download_cfg = copy.deepcopy(self.download_config)
        download_cfg['base_url'] = self._get_base_url(url)
        download_cfg['github_proxy'] = self.config.get('github_proxy', GITHUB_PROXY)
        download_cfg['__own_service_ports__'] = self._collect_own_service_ports()
        download_cfg['user_agent'] = self.user_agent
        download_cfg['incremental'] = bool(self.incremental_update)
        download_cfg['__prev_manifest__'] = self._load_manifest(output_dir)
        downloader = FileDownloader(output_dir, download_cfg, log_callback=self._log, progress_callback=self._push_log,
                                    cancel_event=cancel_event)
        self._package_download_message = f"正在解析 {name} ..."
        self._push_log(f"🎯 开始处理接口: {name}")

        base_url = self._get_base_url(url)
        data = None
        if self.localize_prefer_decrypted:
            data = self._load_decrypted_for_localize(output_dir, safe_name, url)
        if data is None:
            data, base_url, error = self._parse_box_json(url, downloader)
            if error:
                raise Exception(f"解析失败: {error}")
        paths = self._collect_files(data, base_url, downloader)
        self._package_download_message = f"正在下载 {len(paths)} 个文件 ..."
        self._push_log(f"❤️️ 收集到 {len(paths)} 个可下载文件，开始并发下载...")
        self._download_all(paths, downloader)

        missing = self._collect_missing_files(data, downloader, base_url)
        if missing:
            self._push_log(f"🔄 发现 {len(missing)} 个遗漏文件，补充下载...")
            self._download_all(missing, downloader)

        decrypt_path = self._write_decrypt_from_data(
            data, name, safe_name, output_dir, url, base_url)

        self._push_log(f"🧩 正在生成本地化 box.json...")
        local_box_path = self._generate_local_box(data, name, output_dir,
                                                 downloader, base_url, url)
        self._save_manifest(output_dir, downloader, name, url)
        self._push_log(f"🎉 接口 {name} 处理完成！输出: {local_box_path}")
        _all_failed = list(downloader.failed) + list(
            getattr(downloader, "repeat_failed", []) or [])
        stats = {
            "downloaded": downloader.fresh_count,
            "failed": len({str(u) for u, _ in _all_failed}),
            "skipped": len(downloader.skipped),
            "unchanged": len(downloader.unchanged),
            "output_dir": output_dir,
            "decrypt_path": decrypt_path,
            "box_path": local_box_path,
            "remote_refs": int(
                (self._read_process_info(local_box_path) or {}).get(
                    "回源引用数", 0) or 0),
        }
        self._add_or_update_localized_interface(name, url, local_box_path)
        return stats

    def _manifest_path(self, output_dir):
        return os.path.join(output_dir, MANIFEST_NAME)

    def _load_manifest(self, output_dir):
        path = self._manifest_path(output_dir)
        if not os.path.exists(path):
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self._log(f"读取清单失败（将重建）{path}: {e}")
            return {}
        if not isinstance(data, dict) or data.get('version') != MANIFEST_VERSION:
            return {}
        files = data.get('files')
        return files if isinstance(files, dict) else {}

    def _manifest_source_url(self, output_dir):
        path = self._manifest_path(output_dir)
        if not os.path.exists(path):
            return ""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return str((data or {}).get("source_url") or "")
        except Exception:
            return ""

    def _save_manifest(self, output_dir, downloader, source_name="", source_url=""):
        entries = dict(downloader.manifest_entries)
        if not entries:
            return None
        path = self._manifest_path(output_dir)
        try:
            os.makedirs(output_dir, exist_ok=True)
            data = {
                "version": MANIFEST_VERSION,
                "source_name": source_name,
                "source_url": source_url,
                "updated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
                "files": entries,
            }
            self._write_json_atomic(path, data)
            self._log(f"📝 已写入包清单（{len(entries)} 项）: {path}")
            return path
        except Exception as e:
            self._log(f"写入清单失败 {path}: {e}")
            return None

    def _verify_local_package(self, output_dir, checks=None):
        problems = []
        if not isinstance(checks, dict):
            checks = None

        def _on(key):
            return True if checks is None else bool(checks.get(key, True))

        if not output_dir or not os.path.isdir(output_dir):
            return [{"path": output_dir or "(空)", "reason": "目录不存在", "url": None}]

        try:
            if not os.listdir(output_dir):
                return [{"path": output_dir, "reason": "目录为空，该包没有内容",
                         "url": None}]
        except Exception:
            return [{"path": output_dir or "(空)", "reason": "目录不可读", "url": None}]

        box_name = None
        try:
            entry = self._pick_box_entry(output_dir)
            box_name = os.path.basename(entry) if entry else None
        except Exception:
            box_name = None
        if box_name:
            box_abs = os.path.join(output_dir, box_name)
            try:
                with open(box_abs, 'r', encoding='utf-8', errors='replace') as f:
                    box_text = f.read()
                if self._looks_like_truncated_json(box_text):
                    problems.append({"path": box_name,
                                     "reason": "包入口损坏（JSON 被截断）",
                                     "url": None, "check": "truncated"})
            except Exception:
                problems.append({"path": box_name,
                                 "reason": "包入口无法读取", "url": None,
                                 "check": "entry"})
        else:
            problems.append({"path": "(包入口)",
                             "reason": "缺少包入口 JSON，该包不可用（需重跑本地化）",
                             "url": None, "need_relocalize": True,
                             "check": "entry",
                             "source_url": self._manifest_source_url(output_dir)})

        manifest = self._load_manifest(output_dir)
        if manifest:
            for rel, entry in manifest.items():
                entry = entry if isinstance(entry, dict) else {}
                abs_path = os.path.join(output_dir, rel)
                if not os.path.exists(abs_path):
                    problems.append({"path": rel, "reason": "文件缺失",
                                     "url": entry.get("url"),
                                     "check": "missing"})
                    continue
                try:
                    size = os.path.getsize(abs_path)
                except Exception:
                    problems.append({"path": rel, "reason": "无法读取",
                                     "url": entry.get("url"),
                                     "check": "missing"})
                    continue
                recorded = entry.get("size")
                if isinstance(recorded, int) and recorded > 0 and size != recorded:
                    problems.append({"path": rel, "reason": f"大小不符（{size}/{recorded}）",
                                     "url": entry.get("url"), "check": "size"})
                    continue
                if size <= VERIFY_JSON_MAX_BYTES and rel.lower().endswith(('.json', '.js', '.py')):
                    try:
                        with open(abs_path, 'r', encoding='utf-8',
                                  errors='replace') as f:
                            head = f.read()
                        stripped = head.strip()
                        if stripped.startswith(('{', '[')) and \
                                self._looks_like_truncated_json(head):
                            problems.append(
                                {"path": rel, "reason": "文件可能被截断",
                                 "url": entry.get("url"), "check": "truncated"})
                            continue
                    except Exception:
                        pass

        if box_name:
            try:
                reported = {p.get("path") for p in problems}
                for p in self._verify_by_box_refs(output_dir):
                    if p.get("path") not in reported:
                        problems.append(p)
                        reported.add(p.get("path"))
            except Exception:
                pass

        if checks is not None:
            problems = [p for p in problems if _on(p.get("check", "missing"))]
        return problems

    @staticmethod
    @staticmethod
    def _looks_like_truncated_json(text):
        if text is None:
            return True
        s = text.strip()
        if not s:
            return True
        if len(s) <= 2 * 1024 * 1024:
            try:
                json.loads(s)
                return False
            except Exception:
                return True
        tail = s.rstrip()
        return not tail.endswith(('}', ']'))

    def _verify_by_box_refs(self, output_dir):
        problems = []
        try:
            box_path = self._pick_box_entry(output_dir)
            if not box_path:
                return problems
            with open(box_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self._log(f"兜底校验：解析 box.json 失败 {output_dir}: {e}")
            return problems

        seen = set()

        def walk(obj):
            if isinstance(obj, dict):
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for v in obj:
                    walk(v)
            elif isinstance(obj, str) and obj.startswith('./'):
                rel = obj[2:].split('#')[0].split('?')[0]
                if rel in seen:
                    return
                seen.add(rel)
                if not os.path.exists(os.path.join(output_dir, rel)):
                    problems.append({"path": rel,
                                     "reason": "文件缺失（按 box 引用检测）",
                                     "url": None, "check": "missing"})
            elif isinstance(obj, str) and obj.lower().startswith(('http://',
                                                                  'https://')):
                if obj in seen:
                    return
                seen.add(obj)
                problems.append({"path": obj,
                                 "reason": "回源引用（能用但需联网，建议重新本地化）",
                                 "url": obj, "check": "remote",
                                 "fixable": False})
        walk(data)
        return problems

    def _pick_box_entry(self, output_dir):
        try:
            tpl = self.localized_filename_template or '{name}.json'
            dtpl = self.decrypt_filename_template or '{name}_m.json'

            def _matches(fn, template):
                if not template or '{name}' not in template:
                    return False
                pre, post = template.split('{name}', 1)
                if len(fn) <= len(pre) + len(post):
                    return False
                return fn.startswith(pre) and fn.endswith(post)

            cands = []
            for fn in sorted(os.listdir(output_dir)):
                if not fn.lower().endswith('.json') or fn.startswith('.'):
                    continue
                if _matches(fn, dtpl):
                    continue
                if _matches(fn, tpl):
                    cands.append(fn)
            if not cands:
                for fn in sorted(os.listdir(output_dir)):
                    if not fn.lower().endswith('.json') or fn.startswith('.'):
                        continue
                    if _matches(fn, dtpl):
                        continue
                    cands.append(fn)
            for fn in cands:
                p = os.path.join(output_dir, fn)
                if os.path.isfile(p):
                    return p
        except Exception:
            pass
        return None

    def _heal_local_package(self, output_dir, problems, cancel_event=None):
        need_regen = [p for p in (problems or []) if p.get("need_relocalize")]
        todo = [p for p in (problems or []) if p.get("url")]
        if not todo:
            if need_regen:
                self._push_log(
                    "⚠️ 该包缺少入口 JSON（它是本地化时生成的，无法靠重新下载修复）"
                    "，请重新执行一次本地化")
            return {"repaired": 0, "failed": 0,
                    "skipped": len(problems or []),
                    "need_relocalize": len(need_regen)}

        download_cfg = copy.deepcopy(self.download_config)
        download_cfg['incremental'] = False
        download_cfg['overwrite'] = True
        download_cfg['user_agent'] = self.user_agent
        download_cfg['github_proxy'] = self.config.get('github_proxy', GITHUB_PROXY)
        download_cfg['__own_service_ports__'] = self._collect_own_service_ports()
        try:
            download_cfg['proxy'] = self.config.get('proxy', '') or ''
        except Exception:
            download_cfg['proxy'] = self.config.get('proxy', '')
        downloader = FileDownloader(output_dir, download_cfg,
                                    log_callback=self._log,
                                    progress_callback=self._push_log,
                                    cancel_event=cancel_event)
        ok = fail = 0
        for idx, item in enumerate(todo, 1):
            if cancel_event and cancel_event.is_set():
                break
            url = item["url"]
            self._push_log(f"🩹 [{idx}/{len(todo)}] 修复 {item['path']}")
            abs_url = url if url.startswith('http') else url
            target_rel = item["path"]
            target_abs = os.path.join(output_dir, target_rel)
            if os.path.exists(target_abs):
                try:
                    os.remove(target_abs)
                except Exception as e:
                    self._log(f"删除损坏文件失败 {target_abs}: {e}")
                    fail += 1
                    continue
            rel = downloader.download_file(abs_url, "", self._guess_category(abs_url))
            if rel:
                ok += 1
            else:
                fail += 1
        if need_regen:
            self._push_log(
                "⚠️ 另有 %d 处需重跑本地化才能修复（入口文件缺失）" % len(need_regen))
        return {"repaired": ok, "failed": fail,
                "skipped": len(problems) - len(todo) - len(need_regen),
                "need_relocalize": len(need_regen)}

    NON_PACKAGE_DIR_NAMES = {'temp', 'log', 'logs', 'tmp', 'cache', '本地包'}

    def _localized_package_dirs(self):
        base = self.download_output_dir or ""
        if not os.path.isdir(base):
            return []
        dirs = []
        for name in sorted(os.listdir(base)):
            if name.startswith('.') or name in self.NON_PACKAGE_DIR_NAMES:
                continue
            full = os.path.join(base, name)
            if not os.path.isdir(full):
                continue
            try:
                entries = os.listdir(full)
            except Exception:
                continue
            has_box = any(e.lower().endswith('.json') and not e.startswith('.')
                          for e in entries)
            if has_box or os.path.exists(os.path.join(full, MANIFEST_NAME)):
                dirs.append((name, full))
        return dirs

    def _get_base_url(self, url):
        parsed = urllib.parse.urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}{os.path.dirname(parsed.path)}/"
        if not base.endswith('/'):
            base += '/'
        return base

    def _start_package_download(self, sites=None):
        if sites is None:
            sites = self._enabled_package_download_sites()
        if not sites:
            return False, "没有选择任何接口"
        with self._package_download_lock:
            if self._package_download_thread and self._package_download_thread.is_alive():
                return False, "正在下载中"
            names = "、".join(s.get("name", "本地包") for s in sites)
            self._package_download_state = "queued"
            self._package_download_message = "已加入批量任务：{}".format(names)
            self._package_cancel_event = threading.Event()
            worker = threading.Thread(target=self._package_download_worker, args=(sites, self._package_cancel_event), daemon=True)
            self._package_download_thread = worker
            worker.start()
        return True, "开始下载 {} 个已选接口".format(len(sites))

    def _package_download_worker(self, sites, cancel_event):
        successes = []
        failures = []
        used_names = set()
        try:
            total = len(sites)
            for idx, site in enumerate(sites, 1):
                if cancel_event.is_set():
                    self._log("批量下载已取消")
                    break
                name = site.get("name", "本地包")
                url = site.get("url", "")
                try:
                    self._package_download_state = "processing"
                    self._package_download_message = "正在转换 {}/{}：{}".format(idx, total, name)
                    self._push_log(f"🚀 [{idx}/{total}] 开始处理接口: {name}")
                    package_name = self._normalize_package_download_name(name)
                    if package_name.casefold() in used_names:
                        raise ValueError("下载接口备注名重复: {}".format(name))
                    used_names.add(package_name.casefold())
                    sid = self._package_download_site_id(name, url)
                    self._init_site_state(sid)
                    self._site_states[sid]['localize_status'] = 'processing'
                    self._site_states[sid]['localize_msg'] = f'正在转换 {idx}/{total}...'
                    stats = self._process_json_source(site, cancel_event)
                    if cancel_event.is_set():
                        self._site_states[sid]['localize_status'] = 'idle'
                        self._site_states[sid]['localize_msg'] = '已取消'
                        self._log("批量下载已取消")
                        break
                    downloaded = stats.get('downloaded', 0)
                    failed_cnt = stats.get('failed', 0)
                    if failed_cnt:
                        self._site_states[sid]['localize_status'] = 'success'
                        self._site_states[sid]['localize_msg'] = (
                            f"下载{downloaded}个，失败{failed_cnt}个")
                        self._log(f"⚠️ 接口 {name} 处理完成但有 {failed_cnt} 个文件失败"
                                  f"（可到「🩺 本地包体检」修复）")
                    else:
                        self._site_states[sid]['localize_status'] = 'success'
                        self._site_states[sid]['localize_msg'] = f"下载{downloaded}个文件"
                        self._log(f"接口 {name} 处理成功，下载 {downloaded} 个文件")
                    self._site_states[sid]['localize_result'] = stats.get('box_path')
                    self._sync_decrypt_from_localize(sid, stats, name)
                    successes.append({"name": name, "url": url, "result": stats})
                except Exception as e:
                    self._log(f"接口 {name} 处理失败: {e}")
                    try:
                        sid = self._package_download_site_id(name, url)
                        self._init_site_state(sid)
                        self._site_states[sid]['localize_status'] = 'error'
                        self._site_states[sid]['localize_msg'] = f'失败: {str(e)[:30]}'
                    except Exception:
                        pass
                    failures.append({"name": name, "error": str(e)})
            if cancel_event.is_set():
                msg = "批量下载已被用户取消"
                self._package_download_state = "idle"
                self._package_download_message = msg
                self._log(msg)
                self._notify_app(msg)
                return
            if not successes:
                raise ValueError("没有接口处理成功")
            total_files = sum(item["result"].get("downloaded", 0) for item in successes)
            fail_detail = "；".join("{}: {}".format(f["name"], f["error"]) for f in failures)
            msg = "批量处理完成：成功 {}/{}，共 {} 个文件；{}{}".format(
                len(successes), len(sites), total_files,
                "失败 {} 个（{}）；".format(len(failures), fail_detail) if failures else "",
                "（已通知）"
            )
            self._package_download_state = "partial" if failures else "success"
            self._package_download_message = msg
            self._log(msg)
            self._notify_app(msg)
        except Exception as e:
            msg = "批量处理失败: {}".format(e)
            self._package_download_state = "error"
            self._package_download_message = msg
            self._log(msg)
            self._notify_app(msg)
        finally:
            with self._package_download_lock:
                self._package_download_thread = None
                self._package_cancel_event = None
            try:
                self._save_config_to_file()
            except Exception as e:
                self._log(f"批量本地化保存状态失败: {e}")
            try:
                self._save_config_to_file()
            except Exception as e:
                self._log(f"保存批量任务状态失败: {e}")

    def _copy_to_clipboard(self, text, toast_msg="已复制"):
        try:
            act = self._activity()
            if not act:
                return
            clipboard = act.getSystemService(act.CLIPBOARD_SERVICE)
            from java import jclass
            ClipData = jclass("android.content.ClipData")
            clip = ClipData.newPlainText("复制", text)
            clipboard.setPrimaryClip(clip)
            Toast = jclass("android.widget.Toast")
            Toast.makeText(act, toast_msg, Toast.LENGTH_SHORT).show()
        except Exception as e:
            self._log(f"复制失败: {e}")

    @staticmethod
    def _name_from_url(url):
        import re as _re
        try:
            host = (urllib.parse.urlparse(str(url)).hostname or "").strip()
            if host and host.lower() in ("raw.githubusercontent.com",
                                         "githubusercontent.com"):
                segs = [x for x in (urllib.parse.urlparse(str(url)).path or "").split("/") if x]
                if len(segs) >= 2:
                    return segs[1][:24]
            if host:
                host = host.lower()
                for prefix in ("www.", "m.", "tv.", "api."):
                    if host.startswith(prefix):
                        host = host[len(prefix):]
                        break
                if host and not host.startswith("xn--"):
                    main = host.split(".")[0]
                    if main:
                        return main
            path = urllib.parse.urlparse(str(url)).path or ""
            seg = [s for s in path.split("/") if s]
            if seg:
                last = seg[-1]
                stem = last.rsplit(".", 1)[0] if "." in last else last
                stem = urllib.parse.unquote(stem).strip()
                if stem:
                    return stem[:24]
        except Exception:
            pass
        return "未命名接口"

    @staticmethod
    def _parse_line_entries(text, with_name=True):
        items = []
        for raw in str(text or "").splitlines():
            line = raw.strip()
            if not line:
                continue
            name, url = "", line
            norm = line.replace("，", ",")
            if "," in norm:
                idx = norm.index(",")
                name = norm[:idx].strip()
                url = norm[idx + 1:].strip()
            if not url:
                continue
            items.append((name if with_name else "", url))
        return items

    def _show_big_input_dialog(self, act, title, code_hint="", name_hint=None,
                               value="", buttons=None, height_ratio=0.94,
                               min_lines=12):
        kit = self._kit(act)
        box = kit.vbox()
        box.setLayoutParams(kit.lp(-1, -2))

        name_edit = None
        if name_hint:
            name_edit = kit.input(hint=name_hint)
            box.addView(name_edit, kit.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_SM)))

        lines = max(int(min_lines or 0), EDIT_MIN_LINES)
        min_h = int(float(getattr(kit, "h_dp", 0) or 0) * EDIT_MIN_HEIGHT_RATIO)
        code_edit = kit.input(hint=code_hint, value=value, multiline=True,
                              mono=True, min_lines=lines,
                              min_height=(min_h or None))
        box.addView(code_edit, kit.lp(-1, -2))

        self._show_dialog(act, title, box, buttons,
                          height_ratio=height_ratio, scroll=True)
        return name_edit, code_edit

    def _open_add_site_dialog(self, on_done=None):
        def on_ui(act):
            spider = self
            kit = self._kit(act)

            def do_save():
                try:
                    text = str(code_edit.getText())
                    entries = spider._parse_line_entries(text, with_name=True)
                    if not entries:
                        kit.toast("请至少填写一行：名称,地址", long=True)
                        return

                    added = skipped = failed = 0
                    err_msgs = []
                    skip_msgs = []
                    for name, url in entries:
                        if not name:
                            skipped += 1
                            if len(skip_msgs) < 3:
                                skip_msgs.append("缺少名称: {}".format(url[:40]))
                            continue
                        try:
                            with spider.lock:
                                status, final_name, why = spider._add_site_with_dedup(
                                    name, url)
                            if status == 'dup_url':
                                skipped += 1
                                if len(skip_msgs) < 3:
                                    skip_msgs.append("地址重复: {}".format(url[:40]))
                            elif status == 'error':
                                failed += 1
                                if len(err_msgs) < 3:
                                    err_msgs.append("{}: {}".format(url[:40], why))
                            else:
                                added += 1
                        except Exception as exc:
                            failed += 1
                            if len(err_msgs) < 3:
                                err_msgs.append("{}: {}".format(url[:40], exc))

                    spider._save_config_to_file()
                    parts = []
                    if added:
                        parts.append("新增 {}".format(added))
                    if skipped:
                        parts.append("跳过 {}".format(skipped))
                    if failed:
                        parts.append("失败 {}".format(failed))
                    kit.toast("，".join(parts) or "无有效条目", long=True)
                    if skip_msgs:
                        spider._log("已跳过（重复或缺少名称）：" + " | ".join(skip_msgs))
                    if err_msgs:
                        spider._log("部分接口保存失败：" + " | ".join(err_msgs))
                    if added:
                        code_edit.setText("")
                        if on_done:
                            on_done()
                except Exception as exc:
                    kit.toast("保存失败: {}".format(exc), long=True)

            buttons = [
                {"text": "批量保存", "style": "primary", "callback": do_save, "dismiss": False},
                {"text": "关闭", "style": "secondary", "callback": None, "dismiss": True},
            ]
            _, code_edit = self._show_big_input_dialog(
                act, "➕ 添加接口",
                code_hint="每行一个接口：名称,地址\n"
                          "逗号支持全角「，」和半角「,」\n"
                          "例：饭太硬,https://example.com/box.json\n"
                          "名称必填（缺名称整行跳过）；地址重复自动跳过；"
                          "名称重复自动改名为 -1 / -2",
                buttons=buttons, min_lines=12)
        self._run_on_ui(on_ui)

    def _open_multi_import_dialog(self, on_done=None):
        def on_ui(act):
            spider = self
            kit = self._kit(act)

            store = {"raw": "", "valid": "", "mode": "raw"}

            def _build_valid_text(source):
                pairs, err = spider._parse_import_source(source)
                if err:
                    return None, err
                if not pairs:
                    return None, "未解析到有效接口"
                lines = ["✅ 共识别到 {} 个接口，确认无误后点「批量导入」".format(
                    len(pairs)), ""]
                for i, (nm, u) in enumerate(pairs, 1):
                    lines.append("{:>3}. {}".format(i, nm))
                    lines.append("     {}".format(u))
                return "\n".join(lines), None

            def do_toggle_view():
                cur = str(code_edit.getText())
                if store["mode"] == "raw":
                    text, err = _build_valid_text(cur)
                    if err:
                        kit.toast(err, long=True)
                        return
                    store["raw"] = cur
                    store["valid"] = text
                    code_edit.setText(text)
                    store["mode"] = "valid"
                    kit.toast("当前显示：有效数据（解析结果）")
                else:
                    code_edit.setText(store["raw"])
                    store["mode"] = "raw"
                    kit.toast("当前显示：原始数据（可编辑）")

            def do_import():
                source = str(code_edit.getText()).strip()
                if not source:
                    kit.toast("请粘贴接口地址，每行一个", long=True)
                    return
                if store["mode"] == "valid":
                    source = store["raw"].strip()
                if not source:
                    kit.toast("原始内容为空，无法导入", long=True)
                    return
                try:
                    pairs, err = spider._parse_import_source(source)
                    if err:
                        kit.toast(err, long=True)
                        return
                    if not pairs:
                        kit.toast("未解析到有效接口", long=True)
                        return

                    added = skipped = failed = 0
                    for name, url in pairs:
                        if not url:
                            continue
                        try:
                            with spider.lock:
                                status, final_name, why = spider._add_site_with_dedup(
                                    name, url)
                            if status == 'dup_url':
                                skipped += 1
                            elif status == 'error':
                                failed += 1
                            else:
                                added += 1
                        except Exception:
                            failed += 1

                    spider._save_config_to_file()
                    parts = []
                    if added:
                        parts.append("新增 {}".format(added))
                    if skipped:
                        parts.append("跳过(地址重复) {}".format(skipped))
                    if failed:
                        parts.append("失败 {}".format(failed))
                    kit.toast("，".join(parts) or "无有效接口", long=True)
                    if added:
                        code_edit.setText("")
                        store["raw"] = store["valid"] = ""
                        store["mode"] = "raw"
                        if on_done:
                            on_done()
                except Exception as exc:
                    kit.toast("导入失败: {}".format(exc), long=True)

            def do_pick_local_file():
                try:
                    start = ""
                    for cand in (getattr(spider, "download_output_dir", ""),
                                 spider._fs_service_prefix(), "/storage/emulated/0",
                                 "/sdcard", "/"):
                        if cand and os.path.isdir(cand):
                            start = cand
                            break

                    def on_picked(fp):
                        path = fp if str(fp).startswith("/") else "/" + str(fp)
                        try:
                            with open(path, 'r', encoding='utf-8',
                                      errors='replace') as f:
                                content = f.read()
                        except Exception as e:
                            kit.toast("读取失败: {}".format(e), long=True)
                            return
                        if not content.strip():
                            kit.toast("文件为空", long=True)
                            return
                        code_edit.setText(content)
                        store["raw"] = content
                        store["valid"] = ""
                        store["mode"] = "raw"
                        try:
                            pairs, err = spider._parse_import_source(content)
                            if not err and pairs:
                                kit.toast("已载入 {} 个字符，识别到 {} 个接口"
                                          .format(len(content), len(pairs)),
                                          long=True)
                            else:
                                kit.toast("已载入，但未识别到接口，请检查内容",
                                          long=True)
                        except Exception:
                            kit.toast("已载入文件内容")

                    self._show_file_browser(
                        "选取本地 JSON 文件", start or "/", mode="file",
                        on_pick=on_picked,
                        name_filter=lambda fp: str(fp).lower().endswith((".json", ".txt")),
                        manual_title="选取本地 JSON 文件",
                        placeholder="输入文件完整路径，如 /storage/emulated/0/x.json",
                    )
                except Exception as e:
                    kit.toast("打开失败: {}".format(e), long=True)

            buttons = [
                {"text": "📂 选取本地 JSON", "style": "secondary",
                 "callback": do_pick_local_file, "dismiss": False},
                {"text": "🔍 有效数据/原始数据", "style": "secondary",
                 "callback": do_toggle_view, "dismiss": False},
                {"text": "批量导入", "style": "success",
                 "callback": do_import, "dismiss": False},
                {"text": "关闭", "style": "secondary", "callback": None, "dismiss": True},
            ]
            _, code_edit = self._show_big_input_dialog(
                act, "📥 多仓批量导入",
                code_hint="粘贴多仓 JSON，或点「📂 选取本地 JSON」直接载入文件内容\n"
                          "支持任意嵌套层级，会自动找出所有 {名称, 地址} 组合\n"
                          "点「🔍 有效数据」可先预览解析结果，确认后再导入\n"
                          "地址重复自动跳过；名称重复自动改名为 -1 / -2",
                buttons=buttons, min_lines=12)
        self._run_on_ui(on_ui)

    def _open_custom_json_site_dialog(self, on_done=None):
        def on_ui(act):
            spider = self
            kit = self._kit(act)

            def do_save():
                try:
                    name = str(name_edit.getText()).strip()
                    code = str(code_edit.getText()).strip()
                    if not name:
                        kit.toast("请填写接口名称", long=True)
                        return
                    if not code:
                        kit.toast("请粘贴接口 JSON 代码", long=True)
                        return
                    base_name = spider._normalize_package_download_name(name)
                    out_dir0 = spider.download_output_dir or os.path.join(SCRIPT_DIR, "本地包")
                    clean_name = base_name
                    n = 1
                    while os.path.exists(os.path.join(out_dir0, clean_name)):
                        clean_name = "{}-{}".format(base_name, n)
                        n += 1
                        if n > 999:
                            break
                    try:
                        data = json.loads(code)
                    except Exception as je:
                        kit.toast("JSON 解析失败: {}".format(je), long=True)
                        return
                    if not isinstance(data, (dict, list)):
                        kit.toast("接口代码必须是 JSON 对象或数组", long=True)
                        return

                    out_dir = spider.download_output_dir or os.path.join(SCRIPT_DIR, "本地包")
                    pkg_dir = os.path.join(out_dir, clean_name)
                    os.makedirs(pkg_dir, exist_ok=True)
                    file_path = os.path.join(
                        pkg_dir, spider.localized_filename_template.format(name=clean_name))
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

                    local_url = "file://" + os.path.abspath(file_path)

                    spider._add_or_update_localized_interface(clean_name, local_url, file_path)
                    try:
                        with spider.lock:
                            st2, nm2, why2 = spider._add_site_with_dedup(
                                clean_name, local_url)
                        if st2 == 'dup_url':
                            self._log("该地址已在接口列表中：{}".format(clean_name))
                        elif st2 == 'error':
                            self._log("登记到接口列表失败: {}".format(why2))
                    except Exception as e:
                        self._log("登记到接口列表失败（不影响本地接口）: {}".format(e))
                    spider._save_config_to_file()

                    kit.toast("已保存：{}".format(clean_name), long=True)
                    self._log(f"✅ 自定义接口已录入: {file_path}")
                    code_edit.setText("")
                    if on_done:
                        on_done()
                except Exception as exc:
                    kit.toast("保存失败: {}".format(exc), long=True)

            def do_pick_local_file():
                try:
                    start = ""
                    for cand in (getattr(spider, "download_output_dir", ""),
                                 spider._fs_service_prefix(), "/storage/emulated/0",
                                 "/sdcard", "/"):
                        if cand and os.path.isdir(cand):
                            start = cand
                            break

                    def on_picked(fp):
                        try:
                            p = str(fp)
                            if not os.path.isfile(p):
                                kit.toast("不是文件：{}".format(p), long=True)
                                return
                            with open(p, 'r', encoding='utf-8', errors='replace') as f:
                                txt = f.read()
                            code_edit.setText(txt)
                            if not str(name_edit.getText()).strip():
                                stem = os.path.basename(p).rsplit(".", 1)[0]
                                if stem:
                                    name_edit.setText(stem)
                            kit.toast("已载入 {} 字符".format(len(txt)), long=True)
                        except Exception as e:
                            kit.toast("读取失败: {}".format(e), long=True)

                    self._show_file_browser(
                        "选取本地接口文件", start or "/", mode="file",
                        on_pick=on_picked,
                        name_filter=lambda fp: str(fp).lower().endswith(
                            (".json", ".txt", ".js", ".py")),
                        manual_title="选取本地接口文件",
                        placeholder="输入文件完整路径，如 /storage/emulated/0/x.json",
                    )
                except Exception as e:
                    kit.toast("打开失败: {}".format(e), long=True)

            buttons = [
                {"text": "📂 读取本地文件", "style": "secondary",
                 "callback": do_pick_local_file, "dismiss": False},
                {"text": "保存为本地接口", "style": "primary",
                 "callback": do_save, "dismiss": False},
                {"text": "关闭", "style": "secondary", "callback": None, "dismiss": True},
            ]
            name_edit, code_edit = self._show_big_input_dialog(
                act, "📝 自定义接口录入",
                name_hint="接口名称（必填，既是目录名也是频道显示名）",
                code_hint='粘贴接口完整 JSON 代码（不是仓库索引）\n'
                          '例：{"sites":[{"key":"a","name":"A","type":3,"api":"..."}]}\n'
                          '也可点「📂 读取本地文件」直接载入；保存后进接口频道\n'
                          '名称重复会自动改名为 -1 / -2，不覆盖已有包',
                buttons=buttons, min_lines=12)
        self._run_on_ui(on_ui)

    def _site_entry_buttons(self, kit, on_refresh):
        return kit.button_bar([
            {"text": "➕ 添加接口", "style": "primary",
             "callback": lambda: self._open_add_site_dialog(on_refresh), "dismiss": False},
            {"text": "📥 多仓导入", "style": "secondary",
             "callback": lambda: self._open_multi_import_dialog(on_refresh), "dismiss": False},
            {"text": "📝 自定义录入", "style": "secondary",
             "callback": lambda: self._open_custom_json_site_dialog(on_refresh),
             "dismiss": False},
        ], size="md")

    def _open_site_management_dialog(self):
        def on_ui(act):
            spider = self
            kit = self._kit(act)

            container = kit.vbox()
            container.setLayoutParams(kit.lp(-1, -2))

            sites_container = kit.vbox()
            sites_container.setLayoutParams(kit.lp(-1, -2))

            def refresh_site_list():
                sites_container.removeAllViews()
                if not spider.package_download_sites:
                    sites_container.addView(
                        kit.empty("还没有接口，点上方按钮添加或导入"),
                        kit.lp(-1, -2))
                    return
                for idx, site in enumerate(spider.package_download_sites):
                    sites_container.addView(
                        spider._ui_package_site_card(kit, site, idx, refresh_site_list),
                        kit.lp(-1, -2))

            entry_card = kit.card()
            entry_card.addView(
                kit.section_title("➕ 接口录入",
                                  hint="添加单个 / 批量导入 / 直接粘贴接口代码"),
                kit.lp(-1, -2))
            entry_card.addView(self._site_entry_buttons(kit, refresh_site_list),
                               kit.lp(-1, -2, 0.0, (0.0, UITheme.S_MD, 0.0, 0.0)))
            container.addView(entry_card, kit.lp(-1, -2))

            list_card = kit.card()
            list_card.addView(kit.section_title("📋 现有接口"), kit.lp(-1, -2))

            def select_all_sites():
                for s in spider.package_download_sites:
                    s['enabled'] = True
                spider._save_config_to_file()
                refresh_site_list()
                kit.toast("已全选")

            def invert_sites():
                for s in spider.package_download_sites:
                    s['enabled'] = not s.get('enabled', True)
                spider._save_config_to_file()
                refresh_site_list()
                kit.toast("已反选")

            def clear_sites():
                for s in spider.package_download_sites:
                    s['enabled'] = False
                spider._save_config_to_file()
                refresh_site_list()
                kit.toast("已清空选择")

            def copy_selected_sites():
                selected = [s for s in spider.package_download_sites if s.get('enabled', True)]
                if not selected:
                    kit.toast("没有选中的接口")
                    return
                spider._copy_sites_as_multi_warehouse(selected)
                kit.toast("已复制多仓格式")

            list_card.addView(kit.button_bar([
                {"text": "全选", "style": "secondary", "callback": select_all_sites, "dismiss": False},
                {"text": "反选", "style": "secondary", "callback": invert_sites, "dismiss": False},
                {"text": "清空", "style": "secondary", "callback": clear_sites, "dismiss": False},
                {"text": "复制已选", "style": "soft_brand", "callback": copy_selected_sites, "dismiss": False},
            ], size="sm"), kit.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_SM)))

            list_card.addView(sites_container, kit.lp(-1, -2))
            refresh_site_list()
            container.addView(list_card, kit.lp(-1, -2))

            def do_delete_selected():
                selected_sids = [str(s.get("id", "")) for s in spider.package_download_sites
                                 if s.get('enabled', True)]
                if not selected_sids:
                    kit.toast("没有选中的接口")
                    return
                try:
                    with spider.lock:
                        spider._delete_package_download_sites(selected_sids)
                    kit.toast("已删除 {} 个选中接口".format(len(selected_sids)))
                    refresh_site_list()
                except Exception as exc:
                    kit.toast("删除失败: {}".format(exc), long=True)

            buttons = [
                {"text": "删除选中", "style": "danger", "callback": do_delete_selected, "dismiss": False},
                {"text": "关闭", "style": "secondary", "callback": None, "dismiss": True},
            ]
            self._show_dialog(act, "在线接口管理", container, buttons, height_ratio=0.88)
        self._run_on_ui(on_ui)

    def _ui_package_site_card(self, kit, site, index, refresh_fn):
        spider = self

        def on_toggle(v=None):
            site['enabled'] = bool(v) if v is not None else (not site.get('enabled', True))
            spider._save_config_to_file()

        def on_edit():
            sname = site.get('name', '')
            surl = site.get('url', '')

            def on_save(values):
                new_name, new_url = values[0].strip(), values[1].strip()
                if not new_name or not new_url:
                    kit.toast("名称和地址都不能为空")
                    return
                try:
                    with spider.lock:
                        if new_name != sname or new_url != surl:
                            spider._delete_package_download_sites([site.get("id")])
                        spider._add_or_update_package_download_site(new_name, new_url)
                    kit.toast("已更新")
                    refresh_fn()
                except Exception as exc:
                    kit.toast("保存失败: {}".format(exc), long=True)

            spider._show_modern_input_multi(
                "编辑接口", [
                    ("备注名", sname, {"input_hint": "输入名称"}),
                    ("接口地址", surl, {"input_hint": "https://..."}),
                ], on_save)

        def on_copy():
            import json as _json
            single = _json.dumps({"urls": [{"name": site.get('name', ''),
                                            "url": site.get('url', '')}]},
                                 ensure_ascii=False, indent=2)
            kit.toast("已复制单接口" if kit.copy(single, "接口") else "复制失败")

        def on_del():
            try:
                with spider.lock:
                    spider._delete_package_download_sites([site.get("id")])
                kit.toast("已删除：{}".format(site.get("name", "")))
                refresh_fn()
            except Exception as exc:
                kit.toast("删除失败: {}".format(exc), long=True)

        actions = [
            {"text": "编辑", "style": "secondary", "callback": on_edit},
            {"text": "复制", "style": "secondary", "callback": on_copy},
            {"text": "删除", "style": "soft_danger", "callback": on_del},
        ]
        return spider._ui_site_card(kit, site.get("name", "未命名"), site.get("url", ""),
                                    site.get("enabled", True), on_toggle, actions)

    def _open_root_dirs_management(self):
        def on_ui(act):
            spider = self
            kit = self._kit(act)
            spider._load_root_dirs()

            container = kit.vbox()
            container.setLayoutParams(kit.lp(-1, -2))

            add_card = kit.card()
            add_card.addView(
                kit.section_title("📂 添加设置目录",
                                  hint="设置目录用于存放各接口的子目录，勾选后点击扫描"),
                kit.lp(-1, -2))

            edit = kit.input(hint="输入新目录路径")
            add_card.addView(edit, kit.lp(-1, -2))

            dirs_container = kit.vbox()
            dirs_container.setLayoutParams(kit.lp(-1, -2))
            switches = {}

            def refresh_dir_list():
                switches.clear()
                dirs_container.removeAllViews()
                if not spider.root_dirs:
                    dirs_container.addView(kit.empty("还没有设置目录，先在上方添加一个"),
                                           kit.lp(-1, -2))
                    return
                for idx, root in enumerate(spider.root_dirs):
                    holder = {}

                    def make_copy(p=root):
                        def on_long():
                            kit.toast("已复制路径" if kit.copy(p, "路径") else "复制失败")
                            return True
                        return on_long

                    del_fn = None
                    if len(spider.root_dirs) > 1:
                        def make_del(d=root):
                            def on_del():
                                if d in spider.root_dirs:
                                    spider.root_dirs.remove(d)
                                    spider._save_root_dirs()
                                    spider._save_config_to_file()
                                    kit.toast("已删除")
                                    refresh_dir_list()
                            return on_del
                        del_fn = make_del()

                    switches[root] = holder
                    dirs_container.addView(
                        spider._ui_dir_card(kit, idx + 1, root, True,
                                            del_fn, make_copy(), holder),
                        kit.lp(-1, -2))

            def do_add():
                path = str(edit.getText()).strip()
                if not path:
                    kit.toast("请输入路径")
                    return
                if not os.path.isabs(path):
                    path = os.path.abspath(path)
                if path in spider.root_dirs:
                    kit.toast("目录已存在")
                    return
                try:
                    os.makedirs(path, exist_ok=True)
                    spider.root_dirs.append(path)
                    spider._save_root_dirs()
                    spider._save_config_to_file()
                    kit.toast("已添加")
                    edit.setText("")
                    refresh_dir_list()
                except Exception as e:
                    kit.toast(f"添加失败: {e}", long=True)

            def do_pick_dir():
                start = str(edit.getText() or "").strip()
                if not start or not os.path.isdir(start):
                    start = ""
                    for r in [spider.download_output_dir] + list(spider.root_dirs or []):
                        if r and os.path.isdir(r):
                            start = r
                            break
                self._show_file_browser(
                    "选取设置目录", start or spider._fs_service_prefix(), mode="dir",
                    on_pick=lambda v: (edit.setText(str(v)),
                                       kit.toast("已选择：{}".format(v))),
                    manual_title="选取设置目录",
                )

            add_card.addView(
                kit.button_bar([
                    {"text": "📁 选取目录", "style": "secondary",
                     "callback": do_pick_dir, "dismiss": False},
                    {"text": "添加目录", "style": "primary",
                     "callback": do_add, "dismiss": False},
                ], size="md"),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_MD, 0.0, 0.0)))
            container.addView(add_card, kit.lp(-1, -2))

            list_card = kit.card()
            list_card.addView(kit.section_title("📋 设置目录列表", hint="勾选参与扫描，长按可复制路径"),
                              kit.lp(-1, -2))
            list_card.addView(dirs_container, kit.lp(-1, -2))
            refresh_dir_list()
            container.addView(list_card, kit.lp(-1, -2))

            def do_rescan():
                selected = [r for r, holder in switches.items()
                            if holder.get("switch") is not None
                            and holder["switch"].isChecked()]
                if not selected:
                    kit.toast("至少选择一个设置目录")
                    return
                try:
                    if spider._dialog_refs:
                        spider._dialog_refs[-1].dismiss()
                except Exception:
                    pass
                spider._rescan_localized_interfaces(selected)

            buttons = [
                {"text": "扫描接口", "style": "success", "callback": do_rescan, "dismiss": True},
                {"text": "关闭", "style": "secondary", "callback": None, "dismiss": True},
            ]
            self._show_dialog(act, "接口目录管理", container, buttons, height_ratio=0.85)
        self._run_on_ui(on_ui)

    DOCTOR_CHECKS = [
        ("entry", "包入口是否存在", "包目录里有没有可加载的入口 JSON，缺失则整个包不可用"),
        ("missing", "文件是否缺失", "按清单和入口 JSON 里的引用，检查文件是否还在"),
        ("size", "文件大小是否一致", "与上次下载时记录的大小比对，能发现下载被截断"),
        ("truncated", "JSON 是否被截断", "内容不闭合的 JSON 会导致该线路静默失效"),
        ("remote", "是否残留回源引用", "没下到本地、仍指向远程地址的文件（能用但需联网）"),
    ]

    def _doctor_checks(self):
        try:
            saved = self.config.get('doctor_checks')
            if isinstance(saved, dict):
                return {k: bool(saved.get(k, True))
                        for k, _t, _d in self.DOCTOR_CHECKS}
        except Exception:
            pass
        return {k: True for k, _t, _d in self.DOCTOR_CHECKS}

    def _save_doctor_checks(self, checks):
        try:
            self.config['doctor_checks'] = dict(checks)
            self._save_config_to_file()
        except Exception:
            pass

    def _open_package_doctor_dialog(self):
        def on_ui(act):
            spider = self
            kit = self._kit(act)

            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))

            box.addView(kit.hint(
                "检查本地包文件是否齐全完好。校验不联网；点「修复」才重下。"),
                kit.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_SM)))

            opt_card = kit.card()
            opt_card.addView(kit.section_title("检查项目"), kit.lp(-1, -2))
            checks = spider._doctor_checks()
            toggles = {}

            def _flip(key):
                def _cb(is_on):
                    checks[key] = bool(is_on)
                    sw, title = toggles[key]
                    try:
                        sw.setText("{} {}".format("☑" if is_on else "☐", title))
                    except Exception:
                        pass
                    spider._save_doctor_checks(checks)
                    _sync_select_all()
                return _cb

            for key, title, _desc in self.DOCTOR_CHECKS:
                sw = kit.toggle("{} {}".format(
                    "☑" if checks.get(key) else "☐", title),
                    bool(checks.get(key)), _flip(key), weight=1.0)
                toggles[key] = (sw, title)
                opt_card.addView(sw, kit.lp(-1, -2, 0.0,
                                            (0.0, UITheme.S_XXS, 0.0, 0.0)))
            box.addView(opt_card, kit.lp(-1, -2))

            res_card = kit.card()
            status = kit.text("点「开始体检」扫描", size=UITheme.FS_BODY)
            res_card.addView(status, kit.lp(-1, -2))
            result_box = kit.vbox()
            result_box.setLayoutParams(kit.lp(-1, -2))
            res_card.addView(result_box, kit.lp(-1, -2, 0.0,
                                                (UITheme.S_XS, UITheme.S_XS,
                                                 0.0, 0.0)))
            box.addView(res_card, kit.lp(-1, -2))

            scan = {"rows": []}
            picked = set()
            touched = {"v": False}

            def _sync_select_all():
                btn = sel_btn.get("btn")
                if btn is None:
                    return
                names = [n for n, _d, _p in scan["rows"]]
                pickable = [n for n, _d, p in scan["rows"] if p]
                target = pickable or names
                all_on = bool(target) and all(n in picked for n in target)
                try:
                    btn.setText("☐ 全不选" if all_on else "✅ 全选")
                    btn.setEnabled(bool(target))
                except Exception:
                    pass

            def _refresh():
                result_box.removeAllViews()
                if not scan["rows"]:
                    result_box.addView(
                        kit.empty("点「开始体检」扫描本地包", icon="🩺"),
                        kit.lp(-1, -2))
                    return
                for idx, (name, _dir, probs) in enumerate(scan["rows"]):
                    if probs:
                        fixable = sum(1 for x in probs if x.get("url"))
                        sub = "⚠️ {} 处 · 可修 {}".format(len(probs), fixable)
                        icon = "🩹"
                    else:
                        sub, icon = "✅ 完好", "📦"
                    on = name in picked
                    row = kit.row(icon=icon, title=("✔ " if on else "") + name,
                                  subtitle=sub, idx=idx)
                    if on:
                        try:
                            kit._set_bg(row, kit.shape(
                                UITheme.SURFACE_SUNKEN, UITheme.R_MD, 1.0,
                                UITheme.BRAND))
                        except Exception:
                            pass

                    def _mk(nm=name):
                        def _pick():
                            touched["v"] = True
                            if nm in picked:
                                picked.discard(nm)
                            else:
                                picked.add(nm)
                            _refresh()
                            _sync_select_all()
                        return _pick
                    kit.bind_click(row, _mk())
                    result_box.addView(row, kit.lp(-1, -2, 0.0,
                                                   (0.0, UITheme.S_XXS, 0.0, 0.0)))

            def do_scan():
                status.setText("正在体检…")
                self._run_background(
                    lambda: [(n, d, spider._verify_local_package(d, checks))
                             for n, d in spider._localized_package_dirs()],
                    on_done=on_scanned)

            def on_scanned(rows):
                scan["rows"] = rows or []
                picked.clear()
                if not scan["rows"]:
                    status.setText("没有本地包（先执行一次本地化）")
                else:
                    bad = sum(1 for _, _, p in scan["rows"] if p)
                    cnt = sum(len(p) for _, _, p in scan["rows"])
                    if cnt == 0:
                        status.setText("✅ {} 个包全部完好".format(
                            len(scan["rows"])))
                    else:
                        fixable = sum(1 for _, _, pp in scan["rows"]
                                      for x in pp if x.get("url"))
                        if fixable:
                            status.setText(
                                "⚠️ {} 个包 {} 处问题 · {} 处可补下".format(
                                    bad, cnt, fixable))
                        else:
                            status.setText(
                                "⚠️ {} 个包 {} 处问题 · 无法补下"
                                "（缺清单，需重新本地化）".format(bad, cnt))
                _refresh()

            def do_heal():
                rows = scan["rows"]
                if not rows:
                    kit.toast("请先体检", long=True)
                    return
                if picked:
                    todo = [r for r in rows if r[2] and r[0] in picked]
                elif touched["v"]:
                    kit.toast("未选中任何包，点列表行或「✅ 全选」", long=True)
                    return
                else:
                    todo = [r for r in rows if r[2]]
                if not todo:
                    kit.toast("选中的包没有问题" if picked
                              else "没有可修复的问题", long=True)
                    return
                if not any(x.get("url") for _, _, pp in todo for x in pp):
                    kit.toast("缺远端地址，无法补下，请重新本地化", long=True)
                    return
                try:
                    if spider._dialog_refs:
                        spider._dialog_refs[-1].dismiss()
                except Exception:
                    pass
                spider._heal_packages(todo)

            def do_toggle_all():
                if not scan["rows"]:
                    kit.toast("请先体检", long=True)
                    return
                touched["v"] = True
                names = [n for n, _d, _p in scan["rows"]]
                pickable = [n for n, _d, p in scan["rows"] if p]
                target = pickable or names
                all_on = all(n in picked for n in target)
                if all_on:
                    for n in target:
                        picked.discard(n)
                else:
                    for n in target:
                        picked.add(n)
                _refresh()
                _sync_select_all()

            sel_btn = {"btn": None}
            sel_btn["btn"] = kit.button("✅ 全选", "secondary", do_toggle_all,
                                        None, "sm")
            buttons = [
                {"text": "🩺 开始体检", "style": "primary",
                 "callback": do_scan, "dismiss": False},
                {"text": "🩹 修复", "style": "success",
                 "callback": do_heal, "dismiss": False},
                {"text": "关闭", "style": "secondary",
                 "callback": None, "dismiss": True},
            ]
            _refresh()
            _sync_select_all()
            btn_row = kit.hbox()
            btn_row.setLayoutParams(kit.lp(-1, -2, 0.0,
                                           (0.0, UITheme.S_XS, 0.0, 0.0)))
            btn_row.addView(sel_btn["btn"], kit.lp(-2, -2, 0.0))
            res_card.addView(btn_row, kit.lp(-1, -2, 0.0,
                                             (UITheme.S_XS, 0.0, 0.0, 0.0)))
            self._show_dialog(act, "🩺 本地包体检", box, buttons,
                              height_ratio=0.9)

        self._run_on_ui(on_ui)

    def _run_background(self, fn, on_done):
        def _work():
            try:
                result = fn()
            except Exception as e:
                self._log(f"后台任务异常: {e}")
                result = None
            self._run_on_ui(lambda act: on_done(result))
        threading.Thread(target=_work, daemon=True).start()

    def _heal_packages(self, todo):
        def _work():
            total_ok = total_fail = 0
            for pkg_name, pkg_dir, problems in todo:
                self._push_log(f"🩹 开始修复本地包: {pkg_name}")
                try:
                    r = self._heal_local_package(pkg_dir, problems)
                    total_ok += r.get("repaired", 0)
                    total_fail += r.get("failed", 0)
                    self._push_log(
                        f"{'✅' if r.get('failed', 0) == 0 else '⚠️'} "
                        f"{pkg_name}: 修复 {r.get('repaired', 0)} 个，失败 {r.get('failed', 0)} 个")
                except Exception as e:
                    total_fail += len(problems)
                    self._log(f"修复 {pkg_name} 失败: {e}")
            msg = f"自愈完成：修复 {total_ok} 个文件" + (
                f"，失败 {total_fail} 个" if total_fail else "")
            self._package_download_message = msg
            self._push_log("🎉 " + msg)
            self._notify_app(msg)
            self._save_config_to_file()

        def _wrap():
            threading.Thread(target=_work, daemon=True).start()
            return "已开始修复"

        return self._exec_with_log(_wrap)

    def _open_scan_local_files_dialog(self):
        def on_ui(act):
            spider = self
            kit = self._kit(act)
            spider._load_additional_config()

            container = kit.vbox()
            container.setLayoutParams(kit.lp(-1, -2))

            ext_card = kit.card()
            ext_card.addView(kit.section_title("🧩 扫描文件类型", hint="可多选，默认已勾选常用类型"),
                             kit.lp(-1, -2))

            preset_exts = ['.py', '.js']
            ext_checks = {}
            ext_holder = kit.vbox()
            ext_holder.setLayoutParams(kit.lp(-1, -2))
            row = None
            for i, ext in enumerate(preset_exts):
                if i % kit.max_cols == 0:
                    row = kit.hbox()
                    row.setLayoutParams(kit.lp(-1, -2))
                    ext_holder.addView(row, kit.lp(-1, -2))
                default_on = False if ext == '.js' else ext in spider.scan_local_extensions
                ext_checks[ext] = kit.toggle(
                    ext, default_on, None, None, weight=1.0)
                row.addView(ext_checks[ext])
            ext_card.addView(ext_holder, kit.lp(-1, -2))

            ext_card.addView(kit.field_label("自定义扩展名（逗号分隔，如 .lua）"),
                             kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))
            custom_edit = kit.input(hint="例如: .lua,.swift")
            ext_card.addView(custom_edit, kit.lp(-1, -2))
            container.addView(ext_card, kit.lp(-1, -2))

            dir_card = kit.card()
            dir_card.addView(kit.section_title("📂 扫描文件夹", hint="勾选后参与扫描，长按可复制路径"),
                             kit.lp(-1, -2))

            dir_edit = kit.input(hint="输入文件夹路径")
            dir_card.addView(dir_edit, kit.lp(-1, -2))

            dirs_container = kit.vbox()
            dirs_container.setLayoutParams(kit.lp(-1, -2))
            dir_states = {}

            def refresh_dir_list():
                dir_states.clear()
                dirs_container.removeAllViews()
                if not spider.scan_local_dirs:
                    dirs_container.addView(kit.empty("还没有文件夹，先在上方添加一个"),
                                           kit.lp(-1, -2))
                    return
                for idx, path in enumerate(spider.scan_local_dirs):
                    holder = {}
                    dir_states[path] = holder

                    def make_copy(p=path):
                        def on_long():
                            kit.toast("已复制路径" if kit.copy(p, "路径") else "复制失败")
                            return True
                        return on_long

                    def make_del(p=path):
                        def on_del():
                            if p in spider.scan_local_dirs:
                                spider.scan_local_dirs.remove(p)
                                spider._save_additional_config()
                                spider._save_config_to_file()
                                kit.toast("已删除")
                                refresh_dir_list()
                        return on_del

                    dirs_container.addView(
                        spider._ui_dir_card(kit, idx + 1, path, True,
                                            make_del(), make_copy(), holder),
                        kit.lp(-1, -2))

            def do_add_dir():
                path = str(dir_edit.getText()).strip()
                if not path:
                    kit.toast("请输入路径")
                    return
                if not os.path.isabs(path):
                    path = os.path.abspath(path)
                if path in spider.scan_local_dirs:
                    kit.toast("文件夹已存在")
                    return
                if not os.path.isdir(path):
                    kit.toast("文件夹不存在")
                    return
                spider.scan_local_dirs.append(path)
                spider._save_additional_config()
                spider._save_config_to_file()
                kit.toast("已添加")
                dir_edit.setText("")
                refresh_dir_list()

            def do_pick_dir():
                start = str(dir_edit.getText() or "").strip()
                if not start or not os.path.isdir(start):
                    start = ""
                    for d in [spider.download_output_dir] + list(spider.scan_local_dirs or []):
                        if d and os.path.isdir(d):
                            start = d
                            break
                self._show_file_browser(
                    "选取扫描文件夹", start or spider._fs_service_prefix(), mode="dir",
                    on_pick=lambda v: (dir_edit.setText(str(v)),
                                       kit.toast("已选择：{}".format(v))),
                    manual_title="选取扫描文件夹",
                )

            dir_card.addView(
                kit.button_bar([
                    {"text": "📁 选取文件夹", "style": "secondary",
                     "callback": do_pick_dir, "dismiss": False},
                    {"text": "添加文件夹", "style": "primary",
                     "callback": do_add_dir, "dismiss": False},
                ], size="md"),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_MD, 0.0, UITheme.S_SM)))
            dir_card.addView(dirs_container, kit.lp(-1, -2))
            refresh_dir_list()
            container.addView(dir_card, kit.lp(-1, -2))

            def do_scan():
                selected_exts = [ext for ext, sw in ext_checks.items() if sw.isChecked()]
                custom_text = str(custom_edit.getText()).strip()
                if custom_text:
                    for e in [x.strip() for x in custom_text.split(",") if x.strip()]:
                        if e not in selected_exts:
                            selected_exts.append(e)
                if not selected_exts:
                    kit.toast("请至少选择一种文件类型")
                    return
                selected_dirs = [p for p, holder in dir_states.items()
                                 if holder.get("switch") is not None
                                 and holder["switch"].isChecked()]
                if not selected_dirs:
                    kit.toast("请至少勾选一个文件夹")
                    return

                spider.scan_local_extensions = selected_exts
                spider._save_additional_config()
                spider._save_config_to_file()

                try:
                    spider._scan_local_files_and_generate(selected_dirs)
                    kit.toast("扫描完成，合集已生成", long=True)
                    try:
                        if spider._dialog_refs:
                            spider._dialog_refs[-1].dismiss()
                    except Exception:
                        pass
                except Exception as e:
                    kit.toast(f"扫描失败: {e}", long=True)

            buttons = [
                {"text": "扫描文件", "style": "success", "callback": do_scan, "dismiss": True},
                {"text": "关闭", "style": "secondary", "callback": None, "dismiss": True},
            ]
            self._show_dialog(act, "本地API文件管理", container, buttons, height_ratio=0.88)
        self._run_on_ui(on_ui)

    def _load_localized_interfaces(self):
        try:
            if os.path.exists(PERSISTENT_CONFIG_PATH):
                with open(PERSISTENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.localized_interfaces = data.get("localized_interfaces", [])
                self._log(f"加载本地化接口记录 {len(self.localized_interfaces)} 条")
            else:
                self.localized_interfaces = []
        except Exception as e:
            self._log(f"加载本地化接口记录失败: {e}")
            self.localized_interfaces = []

    def _add_or_update_localized_interface(self, name, url, box_path):
        abs_path = os.path.abspath(box_path)
        parent_dir = os.path.dirname(abs_path)
        dir_name = os.path.basename(parent_dir)
        for item in self.localized_interfaces:
            if item.get("parent_dir") == parent_dir and item.get("dir_name") == dir_name:
                if abs_path not in item.get("json_files", []):
                    item["json_files"].append(abs_path)
                if not item.get("selected"):
                    item["selected"] = abs_path
                self._save_config_to_file()
                return
        self.localized_interfaces.append({
            "parent_dir": parent_dir,
            "dir_name": dir_name,
            "json_files": [abs_path],
            "selected": abs_path,
            "hidden": False
        })
        self._save_config_to_file()

    def _rescan_localized_interfaces(self, selected_roots=None):
        if selected_roots is None:
            self._open_root_dirs_management()
            return

        if not selected_roots:
            self._notify_app("未选择任何设置目录")
            return

        existing_map = {}
        for item in self.localized_interfaces:
            key = (item.get("parent_dir", ""), item.get("dir_name", ""))
            existing_map[key] = item

        new_items = []
        temp_base = os.path.join(self.download_output_dir, "temp")
        os.makedirs(temp_base, exist_ok=True)

        for root in selected_roots:
            if not os.path.isdir(root):
                continue
            try:
                for sub in os.listdir(root):
                    sub_path = os.path.join(root, sub)
                    if not os.path.isdir(sub_path):
                        continue
                    if sub in ("localized", "temp"):
                        continue
                    json_files = []
                    try:
                        for f in os.listdir(sub_path):
                            if f.lower().endswith('.json') and os.path.isfile(os.path.join(sub_path, f)):
                                full_path = os.path.join(sub_path, f)
                                try:
                                    with open(full_path, 'r', encoding='utf-8') as fp:
                                        data = json.load(fp)
                                    if isinstance(data, dict) and "sites" in data and isinstance(data["sites"], list):
                                        abs_data = self._absolutize_local_paths(data, sub_path)
                                        temp_sub = os.path.join(temp_base, sub)
                                        os.makedirs(temp_sub, exist_ok=True)
                                        abs_json_path = os.path.join(temp_sub, f)
                                        with open(abs_json_path, 'w', encoding='utf-8') as out:
                                            json.dump(abs_data, out, ensure_ascii=False, indent=2)
                                        json_files.append(abs_json_path)
                                        self._log(f"生成绝对路径 JSON: {abs_json_path}", level='debug')
                                    else:
                                        self._log(f"文件 {full_path} 无效：缺少 sites 字段或格式不正确")
                                except Exception as e:
                                    self._log(f"文件 {full_path} 解析失败: {e}")
                        if not json_files:
                            continue
                    except Exception:
                        continue

                    key = (root, sub)
                    if key in existing_map:
                        old = existing_map[key]
                        merged = list(set(old.get("json_files", []) + json_files))
                        selected = old.get("selected")
                        if selected not in merged:
                            selected = merged[0] if merged else None
                        new_items.append({
                            "parent_dir": root,
                            "dir_name": sub,
                            "json_files": merged,
                            "selected": selected or merged[0],
                            "hidden": old.get("hidden", False)
                        })
                    else:
                        new_items.append({
                            "parent_dir": root,
                            "dir_name": sub,
                            "json_files": json_files,
                            "selected": json_files[0],
                            "hidden": False
                        })
            except Exception as e:
                self._log(f"扫描设置目录 {root} 失败: {e}")

        self.localized_interfaces = new_items
        self._save_config_to_file()
        self._notify_app(f"扫描完成，找到 {len(new_items)} 个本地接口")
        self._log(f"扫描本地接口：{len(new_items)} 条")

    def _absolutize_local_paths(self, obj, base_dir):
        if isinstance(obj, dict):
            return {k: self._absolutize_local_paths(v, base_dir) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._absolutize_local_paths(item, base_dir) for item in obj]
        elif isinstance(obj, str):
            if obj.startswith(('./', '../')):
                abs_path = os.path.abspath(os.path.join(base_dir, obj))
                return 'file://' + abs_path
            return obj
        else:
            return obj

    def _get_localized_config_path(self, box_path):
        base_dir = self.download_output_dir or os.path.join(SCRIPT_DIR, "本地包")
        temp_dir = os.path.join(base_dir, "temp")
        abs_box = os.path.abspath(box_path)
        pkg_name = os.path.basename(os.path.dirname(abs_box)) or "未命名"
        temp_sub = os.path.join(temp_dir, pkg_name)
        os.makedirs(temp_sub, exist_ok=True)
        return os.path.join(temp_sub, os.path.basename(abs_box))

    def _find_site_id_for_package(self, dir_name):
        if not dir_name:
            return None
        norm = lambda x: re.sub(r'[\\/:*?"<>|]', '_', str(x or "")).rstrip('. ')
        target = norm(dir_name)
        if not target:
            return None
        for s in self.package_download_sites:
            if norm(s.get("name", "")) == target:
                return s.get("id")
        return None

    def _jump_to_interface(self, file_path, name, dismiss_ref=None):
        try:
            if not file_path or not os.path.isfile(file_path):
                self._notify_app("找不到产物文件，无法跳转")
                return
            abs_path = os.path.abspath(file_path)
            parent = os.path.dirname(os.path.dirname(abs_path))
            ok, msg = self._switch_to_oktv(abs_path, parent, name)
            self._notify_app(msg)
            self._log(f"跳转本地接口: {abs_path} -> {msg}")
        except Exception as e:
            self._notify_app(f"跳转失败: {e}")
            self._log(f"跳转失败 {file_path}: {e}")

    def _rerun_site_task(self, site_id, kind, dismiss_ref=None):
        fn = (self._decrypt_single_site if kind == 'decrypt'
              else self._localize_single_site)
        self._exec_with_log(fn, site_id)

    def _upsert_localized_interface(self, dir_name, parent_dir, json_path):
        url = "file://" + os.path.abspath(json_path)
        items = self.localized_interfaces
        if not isinstance(items, list):
            items = []
            self.localized_interfaces = items

        for it in items:
            if not isinstance(it, dict):
                continue
            files = it.get("json_files") or []
            if any(os.path.abspath(str(f)) == os.path.abspath(json_path) for f in files):
                it["dir_name"] = dir_name
                if parent_dir:
                    it["parent_dir"] = parent_dir
                it["selected"] = json_path
                self._save_config_to_file()
                return "updated"

        items.append({
            "parent_dir": parent_dir or "",
            "dir_name": dir_name,
            "json_files": [json_path],
            "selected": json_path,
            "hidden": False,
        })
        self._save_config_to_file()
        return "created"

    def _switch_to_oktv(self, box_path, parent_dir, dir_name):
        try:
            from java import jclass
            import urllib.request, urllib.parse, json
            with open(box_path, 'r', encoding='utf-8') as f:
                original_data = json.load(f)
            if not isinstance(original_data, dict):
                raise ValueError("原始 box.json 顶层必须是对象")

            new_data = copy.deepcopy(original_data)

            base_dir = os.path.dirname(os.path.abspath(box_path))
            new_data = self._absolutize_local_paths(new_data, base_dir)

            if "sites" not in new_data or not isinstance(new_data["sites"], list):
                new_data["sites"] = []

            if self.inject_manager_site:
                manager_site = {
                    "key": "local_package_manager",
                    "name": "⚙️ 本地包管理",
                    "type": 3,
                    "style": {"type": "list", "ratio": 1.43},
                    "api": "file://" + os.path.abspath(__file__),
                    "ext": {
                        "config_file": "file://" + (self._config_file_path or os.path.join(SCRIPT_DIR, "config.json"))
                    },
                    "searchable": 1,
                    "quickSearch": 1,
                }
                existing = any(s.get("key") == "local_package_manager" for s in new_data["sites"] if isinstance(s, dict))
                if not existing:
                    new_data["sites"].insert(0, manager_site)
                new_data["home"] = "local_package_manager"

            config_path = self._get_localized_config_path(box_path)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, ensure_ascii=False, indent=2)

            try:
                self._upsert_localized_interface(
                    dir_name=dir_name,
                    parent_dir=parent_dir or os.path.dirname(os.path.dirname(box_path)),
                    json_path=config_path)
            except Exception as e:
                self._log(f"登记本地接口失败（不影响切换）: {e}")

            config_class = jclass("com.fongmi.android.tv.bean.Config")
            current_url = ""
            try:
                current_url = str(config_class.vod().getUrl() or "")
            except Exception:
                pass
            port = self._effective_proxy_port()
            if port <= 0:
                return False, "无法获取 OKTV 端口"

            sync_payload = {
                "type": 0,
                "url": "file://" + config_path,
                "name": f"本地化[{dir_name}]"
            }
            body = urllib.parse.urlencode({
                "config": json.dumps(sync_payload, ensure_ascii=False),
                "targets": "[]",
                "force": "false"
            }).encode('utf-8')
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/action?do=sync&mode=1&type=history",
                data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"}
            )
            timeout = self.oktv_switch_timeout
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.getcode() == 200:
                    return True, f"已切换至本地化[{dir_name}]"
            return False, "OKTV sync 请求失败"
        except Exception as e:
            return False, f"切换异常: {e}"

    def _handle_switch_localized(self, encoded_dir):
        import urllib.parse
        dir_name = urllib.parse.unquote(encoded_dir)
        item = None
        for i in self.localized_interfaces:
            if i["dir_name"] == dir_name:
                item = i
                break
        if not item:
            self._notify_app(f"未找到接口: {dir_name}")
            return
        parent_dir = item.get("parent_dir", "")
        json_files = item.get("json_files", [])
        if not json_files:
            self._notify_app(f"目录 {dir_name} 下没有 JSON 文件")
            return
        if len(json_files) == 1:
            box_path = json_files[0]
            ok, msg = self._switch_to_oktv(box_path, parent_dir, dir_name)
            self._notify_app(msg)
            return

        def on_ui(act):
            spider = self
            kit = self._kit(act)

            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))
            box.addView(kit.hint(f"目录：{dir_name}\n请选择要切换的 JSON 文件"),
                        kit.lp(-1, -2))

            entries = [(fpath, "{}. {}".format(idx + 1, os.path.basename(fpath)))
                       for idx, fpath in enumerate(json_files)]
            group, radio_buttons = self._ui_radio_group(kit, entries, item.get("selected"))
            if group is None:
                kit.toast("无法构建选项列表")
                return
            box.addView(group, kit.lp(-1, -2))

            def do_confirm():
                checked_id = group.getCheckedRadioButtonId()
                if checked_id == -1:
                    kit.toast("请选择一个 JSON")
                    return
                selected_path = None
                for fpath, rb in radio_buttons.items():
                    if rb.getId() == checked_id:
                        selected_path = fpath
                        break
                if selected_path:
                    ok, msg = spider._switch_to_oktv(selected_path, parent_dir, dir_name)
                    spider._notify_app(msg)
                    for it in spider.localized_interfaces:
                        if it.get("parent_dir") == parent_dir and it.get("dir_name") == dir_name:
                            it["selected"] = selected_path
                            spider._save_config_to_file()
                            break

            buttons = [
                {"text": "取消", "style": "secondary", "callback": None, "dismiss": True},
                {"text": "确定", "style": "primary", "callback": do_confirm, "dismiss": True},
            ]
            self._show_dialog(act, "选择 JSON", box, buttons, height_ratio=0.80)
        self._run_on_ui(on_ui)

    def _clear_all_records(self):
        count = len(self.localized_interfaces)
        if not count:
            self._notify_app("没有可清空的本地接口记录")
            return
        self.localized_interfaces = []
        self._save_config_to_file()
        self._log(f"已清空 {count} 条本地接口记录")
        self._notify_app(f"已清空 {count} 条本地接口记录")

    def _real_source_json(self, info):
        selected = (info or {}).get('selected', '') or ''
        if not selected:
            return selected
        try:
            out_dir = os.path.abspath(self.download_output_dir or "")
            temp_root = os.path.join(out_dir, 'temp')
            abs_sel = os.path.abspath(selected)
            if out_dir and abs_sel.startswith(temp_root + os.sep):
                rel = os.path.relpath(abs_sel, temp_root)
                real = os.path.join(info.get('parent_dir', ''), rel)
                if os.path.exists(real):
                    return real
        except Exception:
            pass
        return selected

    def _open_manage_switch(self):
        def on_ui(act):
            spider = self
            kit = self._kit(act)

            batch_selected = {}
            for info in spider.localized_interfaces:
                batch_selected[(info.get("parent_dir", ""), info["dir_name"])] = False

            container = kit.vbox()
            container.setLayoutParams(kit.lp(-1, -2))

            list_card = kit.card()
            list_card.addView(
                kit.section_title("🗂 本地接口记录",
                                  hint="勾选后可使用下方快捷按钮批量操作"),
                kit.lp(-1, -2))

            sites_container = kit.vbox()
            sites_container.setLayoutParams(kit.lp(-1, -2))

            def refresh_list():
                sites_container.removeAllViews()
                if not spider.localized_interfaces:
                    sites_container.addView(kit.empty("暂无本地接口记录"), kit.lp(-1, -2))
                    return
                for info in spider.localized_interfaces:
                    sites_container.addView(
                        make_item_card(info), kit.lp(-1, -2))

            def make_item_card(info):
                parent_dir = info.get("parent_dir", "")
                dir_name = info["dir_name"]
                hidden = info.get("hidden", False)
                json_count = len(info.get("json_files", []))
                full_path = os.path.join(parent_dir, dir_name)
                item_key = (parent_dir, dir_name)

                def on_toggle(v):
                    batch_selected[item_key] = bool(v)

                def on_edit():
                    selected = info.get('selected', '') or ''
                    if selected and not os.path.exists(selected):
                        selected = spider._real_source_json(info)
                    if selected and os.path.exists(selected):
                        try:
                            with open(selected, 'r', encoding='utf-8') as f:
                                content = f.read()

                            site_id = spider._find_site_id_for_package(dir_name)

                            def do_redecrypt():
                                if not site_id:
                                    spider._notify_app(
                                        "未找到对应的在线接口，无法重新解密\n"
                                        "（该本地包可能已被从在线接口列表删除）")
                                    return
                                spider._rerun_site_task(site_id, 'decrypt')

                            is_temp = spider._is_temp_local_json(selected)

                            def on_saved():
                                if is_temp:
                                    spider._notify_app(
                                        "已保存到 temp（立即生效）\n"
                                        "注意：下次「扫描本地接口」会重新生成并覆盖此处改动")
                                else:
                                    spider._notify_app("已保存")

                            spider._show_modern_text_editor(
                                f"✏️ 编辑本地化 JSON - {dir_name}", content, selected, "",
                                "file://" + os.path.abspath(selected),
                                on_saved,
                                jump_cb=lambda: spider._jump_to_interface(
                                    selected, dir_name),
                                rerun_label="重解密", rerun_cb=do_redecrypt,
                                url_label="本地化U")
                        except Exception as e:
                            spider._notify_app(f"打开失败: {e}")
                    else:
                        spider._notify_app("未找到JSON文件")

                def on_del():
                    spider.localized_interfaces = [
                        i for i in spider.localized_interfaces
                        if not (i.get("parent_dir") == parent_dir and i["dir_name"] == dir_name)
                    ]
                    spider._save_config_to_file()
                    spider._notify_app(f"已删除记录：{dir_name}")
                    batch_selected.pop(item_key, None)
                    refresh_list()

                actions = [
                    {"text": "编辑 JSON", "style": "secondary", "callback": on_edit},
                    {"text": "删除记录", "style": "soft_danger", "callback": on_del},
                ]
                card = spider._ui_site_card(
                    kit,
                    ("🚫 " if hidden else "✨ ") + dir_name,
                    f"{full_path} · JSON {json_count} 个" + ("（已隐藏）" if hidden else ""),
                    batch_selected.get(item_key, False), on_toggle, actions, dim=hidden)
                return card

            def select_all_items():
                for info in spider.localized_interfaces:
                    batch_selected[(info.get("parent_dir", ""), info["dir_name"])] = True
                refresh_list()
                kit.toast("已全选")

            def invert_items():
                for info in spider.localized_interfaces:
                    k = (info.get("parent_dir", ""), info["dir_name"])
                    batch_selected[k] = not batch_selected.get(k, False)
                refresh_list()
                kit.toast("已反选")

            def clear_select():
                for k in list(batch_selected.keys()):
                    batch_selected[k] = False
                refresh_list()
                kit.toast("已清空选择")

            def batch_toggle_visibility():
                selected_keys = [k for k, v in batch_selected.items() if v]
                if not selected_keys:
                    kit.toast("请先勾选要批量操作的接口")
                    return
                show_count = 0
                hide_count = 0
                for info in spider.localized_interfaces:
                    key = (info.get("parent_dir", ""), info["dir_name"])
                    if key in selected_keys:
                        if info.get("hidden", False):
                            hide_count += 1
                        else:
                            show_count += 1
                target_hidden = show_count >= hide_count

                changed = 0
                for info in spider.localized_interfaces:
                    key = (info.get("parent_dir", ""), info["dir_name"])
                    if key in selected_keys:
                        info["hidden"] = target_hidden
                        changed += 1

                if changed > 0:
                    spider._save_config_to_file()
                    kit.toast(f"已批量{'隐藏' if target_hidden else '显示'} {changed} 个接口")
                    refresh_list()

            def do_clear_all():
                def _clear():
                    spider.localized_interfaces = []
                    spider._save_config_to_file()
                    spider._notify_app("已清空所有接口记录")
                    refresh_list()
                spider._show_modern_confirm("确认清空",
                                            "确定要清空所有接口记录吗？\n（不会删除本地文件）",
                                            _clear)

            list_card.addView(kit.button_bar([
                {"text": "全选", "style": "secondary", "callback": select_all_items, "dismiss": False},
                {"text": "反选", "style": "secondary", "callback": invert_items, "dismiss": False},
                {"text": "清空", "style": "secondary", "callback": clear_select, "dismiss": False},
                {"text": "批量显隐", "style": "soft_brand", "callback": batch_toggle_visibility, "dismiss": False},
            ], size="sm"), kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XS, 0.0, UITheme.S_SM)))

            list_card.addView(sites_container, kit.lp(-1, -2))
            refresh_list()
            container.addView(list_card, kit.lp(-1, -2))

            container.addView(
                kit.button_bar([{"text": "🗑 清空所有记录", "style": "danger",
                                 "callback": do_clear_all, "dismiss": False}], size="md"),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XS, 0.0, 0.0)))

            buttons = [{"text": "关闭", "style": "primary", "callback": None, "dismiss": True}]
            self._show_dialog(act, "管理本地接口", container, buttons, height_ratio=0.88)
        self._run_on_ui(on_ui)

    def _scan_local_files_and_generate(self, selected_dirs=None):
        if selected_dirs is None:
            selected_dirs = self.scan_local_dirs
        if not selected_dirs:
            raise ValueError("没有选择任何扫描文件夹")

        exts = self.scan_local_extensions
        if not exts:
            raise ValueError("未选择任何文件类型")

        all_files = []
        for root_dir in selected_dirs:
            if not os.path.isdir(root_dir):
                self._log(f"文件夹不存在，跳过: {root_dir}")
                continue
            for dirpath, _, filenames in os.walk(root_dir):
                for f in filenames:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in exts:
                        full = os.path.join(dirpath, f)
                        all_files.append(full)

        if not all_files:
            raise ValueError("未找到任何匹配的文件")

        size_groups = {}
        for file_path in all_files:
            try:
                size_groups.setdefault(os.path.getsize(file_path), []).append(file_path)
            except Exception:
                continue

        def _file_md5(path):
            h = hashlib.md5()
            with open(path, 'rb') as fp:
                while True:
                    block = fp.read(HASH_CHUNK_SIZE)
                    if not block:
                        break
                    h.update(block)
            return h.hexdigest()

        content_hash = {}
        unique_by_content = []
        hashed_count = 0
        for _size, group in size_groups.items():
            if len(group) == 1:
                unique_by_content.append(group[0])
                continue
            for file_path in group:
                try:
                    md5 = _file_md5(file_path)
                    hashed_count += 1
                except Exception:
                    continue
                if md5 not in content_hash:
                    content_hash[md5] = file_path
                    unique_by_content.append(file_path)
        self._log(f"去重统计：{len(all_files)} 个文件，实际计算哈希 {hashed_count} 次"
                  f"（{len(all_files) - hashed_count} 个因大小唯一被跳过）")

        name_count = {}
        final_files = []
        for file_path in unique_by_content:
            base = os.path.basename(file_path)
            name_without_ext = os.path.splitext(base)[0]
            ext = os.path.splitext(base)[1].lower()
            if name_without_ext not in name_count:
                name_count[name_without_ext] = 1
                final_name = name_without_ext
            else:
                count = name_count[name_without_ext]
                name_count[name_without_ext] = count + 1
                final_name = f"{name_without_ext}-{count}"
            final_files.append((file_path, final_name, ext))

        sites = []
        if self.inject_manager_site:
            manager_site = {
                "key": "local_package_manager",
                "name": "⚙️ 本地包管理",
                "type": 3,
                "style": {"type": "list", "ratio": 1.43},
                "api": "file://" + os.path.abspath(__file__),
                "ext": {
                    "config_file": "file://" + (self._config_file_path or os.path.join(SCRIPT_DIR, "config.json"))
                },
                "searchable": 1,
                "quickSearch": 1,
            }
            sites.append(manager_site)

        for file_path, final_name, ext in final_files:
            label = ext[1:].upper() if ext.startswith('.') else ext.upper()
            site = {
                "key": final_name,
                "name": f"{final_name}|[{label}]",
                "type": 3,
                "api": "file://" + file_path,
            }
            sites.append(site)

        json_data = {
            "sites": sites,
            "warningText": WARNING_TEXT,
        }

        collection_dir = os.path.join(self.download_output_dir, "API文件")
        os.makedirs(collection_dir, exist_ok=True)
        json_path = os.path.join(collection_dir, "scan_local_files.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        self._log(f"本地文件合集已生成: {json_path}，包含 {len(final_files)} 个文件（去重后）")

        self.localized_interfaces = [
            item for item in self.localized_interfaces
            if not (item.get("parent_dir") == collection_dir and item.get("dir_name") == "API文件")
        ]
        self.localized_interfaces.append({
            "parent_dir": collection_dir,
            "dir_name": "API文件",
            "json_files": [json_path],
            "selected": json_path,
            "hidden": False
        })
        self._save_config_to_file()
        self._save_persistent_config()
        self._notify_app(f"合集已生成，共 {len(final_files)} 个文件")
    def _get_current_oktv_url(self):
        try:
            from java import jclass
            config_class = jclass("com.fongmi.android.tv.bean.Config")
            return str(config_class.vod().getUrl() or "")
        except Exception:
            try:
                port = self._effective_proxy_port()
                if port <= 0:
                    return None
                import urllib.request, json
                req = urllib.request.Request(f"http://127.0.0.1:{port}/action?do=getConfig&type=vod")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    return data.get("url")
            except Exception:
                return None
    def _is_temp_local_json(self, url):
        if not url or not isinstance(url, str):
            return False
        path = url[7:] if url.startswith('file://') else url
        if not os.path.isabs(path):
            return False
        temp_dir = os.path.join(self.download_output_dir, "temp")
        try:
            common = os.path.commonpath([path, temp_dir])
            return common == temp_dir
        except ValueError:
            return False
    def _switch_to_url(self, url, name="自定义配置"):
        try:
            from java import jclass
            proxy = jclass("com.github.catvod.Proxy")
            port = int(proxy.getPort())
            if port <= 0:
                return False, "无法获取 OKTV 端口"

            sync_payload = {
                "type": 0,
                "url": url,
                "name": name
            }
            import urllib.request, urllib.parse, json
            body = urllib.parse.urlencode({
                "config": json.dumps(sync_payload, ensure_ascii=False),
                "targets": "[]",
                "force": "false"
            }).encode('utf-8')
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/action?do=sync&mode=1&type=history",
                data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"}
            )
            timeout = self.oktv_switch_timeout
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.getcode() == 200:
                    return True, f"已切换至：{name}"
            return False, "sync 请求失败"
        except Exception as e:
            return False, f"切换异常: {e}"

    def init(self, extend=""):
        with self.lock:
            if self.inited:
                self._log("init 被重复调用，跳过")
                return
            self._initial_extend = extend
            self._init_session()
            self._log("=" * 50)
            self._log("【init 开始】开始初始化")
            self._log(f"【init】SCRIPT_DIR = {SCRIPT_DIR}")
            self._log(f"【init】当前工作目录 = {os.getcwd()}")
            config = self._load_default_config()
            ext = {}
            if extend:
                self._log(f"【init】收到 extend，类型={type(extend).__name__}")
                if isinstance(extend, dict):
                    ext = extend
                    self._log(f"【init】extend 为 dict，键: {list(ext.keys())}")
                elif isinstance(extend, str):
                    extend_str = extend.strip()
                    self._log(f"【init】extend 为字符串，长度={len(extend_str)}")
                    self._log(f"【init】extend 前200字符: {extend_str[:200]}")
                    if extend_str.startswith('{') or extend_str.startswith('['):
                        self._log("【init】检测到 JSON 格式，开始解析...")
                        try:
                            ext = json.loads(extend_str)
                            self._log(f"【init】JSON 解析成功，键: {list(ext.keys())}")
                        except Exception as e:
                            self._log(f"【init】ext JSON 解析失败: {e}")
                            ext = {}
                    else:
                        self._log("【init】非 JSON 字符串，尝试作为路径/URL 加载...")
                        loaded = self._load_config_from_ext(extend_str)
                        if loaded and isinstance(loaded, dict):
                            ext = loaded
                            self._log(f"【init】路径加载成功，键: {list(ext.keys())}")
                        else:
                            self._log("【init】路径加载失败，尝试解析为传统 URL 字符串...")
                            lives, base_url, pic_url = self._parse_url_string(extend_str)
                            if lives:
                                ext = {'lives': lives, 'vod_pic': pic_url}
                                self._log(f"【init】传统 URL 解析成功，lives 数量: {len(lives)}")
                            else:
                                self._log("【init】传统 URL 解析失败，ext 为空")
                                ext = {}
                else:
                    self._log(f"【init】extend 为未知类型: {type(extend).__name__}")
                    ext = {}
            else:
                self._log("【init】extend 为空，使用默认配置")
                ext = {}

            self._detect_base_dir(ext)
            self._log(f"【init】基础目录检测完成: {self._get_base_dir()}")

            if ext:
                ext = self._normalize_config_keys(ext)
                self._log(f"【init】ext 键列表: {list(ext.keys())}")
                config_file = ext.get('config_file', '')
                self._log(f"【init】config_file 值: '{config_file}'")
                if config_file:
                    self._log(f"【init】开始加载外部配置: {config_file}")
                    cf_config = self._load_config_file(config_file)
                    if cf_config:
                        self._log(f"【init】✅ 已加载外部配置: {config_file}")
                        self._log(f"【init】外部配置原始键: {list(cf_config.keys())}")
                        cf_config = self._normalize_config_keys(cf_config)
                        self._log(f"【init】外部配置规范化后键: {list(cf_config.keys())}")
                        merged_count = 0
                        for k, v in cf_config.items():
                            if k not in ext:
                                ext[k] = v
                                merged_count += 1
                        self._log(f"【init】合并了 {merged_count} 个新键到 ext")
                        self._log(f"【init】合并后 ext 键: {list(ext.keys())}")
                    else:
                        self._log(f"【init】❌ 外部配置加载失败: {config_file}")
                        self._pending_notice = {
                            "title": "配置文件未能加载",
                            "body": "已改用默认配置继续运行（你配置的接口未生效）。\n\n"
                                    "文件：%s\n\n"
                                    "常见原因：JSON 里有无法自动修复的语法错误，"
                                    "或路径不存在/无读取权限。\n"
                                    "可到「设置 → 配置备份管理」恢复一份历史备份，"
                                    "或在「日志面板」把级别切到 DEBUG 查看具体错误。"
                                    % (config_file or "(未指定)"),
                        }
                else:
                    self._log("【init】config_file 为空，跳过外部配置加载")
                self._log("【init】开始合并 ext 到 config...")
                for k, v in ext.items():
                    if k == 'config_file':
                        continue
                    if isinstance(v, dict) and k in config and isinstance(config[k], dict):
                        config[k].update(v)
                        self._log(f"【init】合并 dict 键: {k}")
                    else:
                        config[k] = v
                        self._log(f"【init】合并键: {k} = {str(v)[:80]}")
            else:
                self._log("【init】ext 为空，跳过合并")
            self._log("【init】开始应用配置...")
            self._apply_config(config)

            persistent = self._load_persistent_config()
            if persistent and isinstance(persistent, dict):
                self._log("【init】检测到持久化配置，开始合并...")
                persistent = self._normalize_config_keys(persistent)
                merged_count = 0
                for k, v in persistent.items():
                    if k == 'config_file':
                        continue
                    if isinstance(v, dict) and k in self.config and isinstance(self.config[k], dict):
                        self.config[k].update(v)
                        merged_count += 1
                    else:
                        self.config[k] = v
                        merged_count += 1
                self._apply_config(self.config)
                self._log(f"【init】✅ 已合并持久化配置，共 {merged_count} 项")

                self._original_oktv_url = persistent.get("original_oktv_url")

                msg = persistent.get("package_download_message")
                if msg:
                    self._package_download_message = msg
            else:
                self._original_oktv_url = None

            current_url = self._get_current_oktv_url()
            if current_url:
                if not self._is_temp_local_json(current_url):
                    self._original_oktv_url = current_url
                    self._save_persistent_config()
                    self._log(f"更新原始接口地址: {current_url}")
                else:
                    self._log(f"当前接口为临时本地 JSON，不更新原始地址，保持: {self._original_oktv_url}")
            else:
                self._log("未能获取当前接口地址，原始接口地址保持不变")

            self.inited = True
            self._log("【init】✅ 初始化完成（v5.4）")
            try:
                self._adopt_decrypt_artifacts()
            except Exception:
                pass
            self._log("=" * 50)
            try:
                threading.Thread(target=self._fs_service_prefix).start()
            except Exception:
                pass

    def getName(self):
        return "本地包管理器 {}".format(self.VERSION)

    def homeContent(self, filter):
        self._ensure_initialized()
        self._flush_pending_notice()
        classes = [
            {"type_id": "center", "type_name": "🎮管理中心"},
            {"type_id": "decrypt", "type_name": "🔐解密"},
            {"type_id": "localize", "type_name": "🥁本地"},
            {"type_id": "settings", "type_name": "🛠设置"},
        ]
        return {"class": classes, "filters": {}}

    def _flush_pending_notice(self):
        notice = getattr(self, "_pending_notice", None)
        if not notice:
            return
        self._pending_notice = None

        def on_ui(act):
            kit = self._kit(act)
            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))
            box.addView(kit.hint(str(notice.get("body", ""))),
                        kit.lp(-1, -2))
            self._show_dialog(
                act, "⚠️ %s" % notice.get("title", "提示"), box,
                [{"text": "知道了", "style": "primary",
                  "callback": None, "dismiss": True}],
                height_ratio=0)

        self._run_on_ui(on_ui)

    def homeVod(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, ext):
        self._ensure_initialized()
        page = self._page_number(pg)
        if tid == "center":
            items = []

            original_url = self._original_oktv_url if self._original_oktv_url else "未获取到"
            remark = f"当前: {original_url}"
            items.append({
                "vod_id": "switch_to_original",
                "vod_name": "❤️️ 回归",
                "vod_pic": "",
                "vod_remarks": remark,
                "action": "local_source_switch_to_original"
            })
            items.append({"vod_id": "setting_scan_local_files", "vod_name": "✴️ 扫描本地API文件", "vod_pic": "", "vod_remarks": "扫描设置目录下的[PY | JS等]文件", "action": "local_source_scan_local_files"})
            items.append({
                "vod_id": "rescan_localized",
                "vod_name": "⚙️ 扫描本地接口",
                "vod_pic": "",
                "vod_remarks": "扫描设置目录下的有效接口",
                "action": "local_source_rescan_localized"
            })
            for info in self.localized_interfaces:
                if info.get("hidden", False):
                    continue
                parent_dir = info.get("parent_dir", "")
                dir_name = info["dir_name"]
                json_count = len(info.get("json_files", []))
                display_name = f"✨️ {dir_name}"
                full_path = os.path.join(parent_dir, dir_name)
                encoded_dir = urllib.parse.quote(dir_name, safe='')
                items.append({
                    "vod_id": f"switch_localized_{encoded_dir}",
                    "vod_name": display_name,
                    "vod_pic": "",
                    "vod_remarks": f"路径: {full_path} | JSON: {json_count} 个",
                    "action": f"local_source_switch_localized:{encoded_dir}"
                })
            items.append({
                "vod_id": "manage_switch",
                "vod_name": "⚙️ 管理本地接口",
                "vod_pic": "",
                "vod_remarks": "删除/显隐/清空记录",
                "action": "local_source_manage_switch"
            })
            return self._paged_result(items, page)

        elif tid == "decrypt":
            items = []
            items.append({
                "vod_id": "decrypt_all",
                "vod_name": "⚙️ 批量解密",
                "vod_pic": "",
                "vod_remarks": "选择多个接口同时解密",
                "action": "decrypt_all"
            })
            for site in self.package_download_sites:
                items.append({
                    "vod_id": f"decrypt_{site['id']}",
                    "vod_name": f"✂️ {site['name']}",
                    "vod_pic": "",
                    "vod_remarks": self._get_decrypt_status_text(site),
                    "action": f"decrypt_site_{site['id']}",
                })
            return self._paged_result(items, page)

        elif tid == "localize":
            items = []
            items.append({
                "vod_id": self.ACTION_DOWNLOAD_PACKAGE,
                "vod_name": "⚙️ 批量本地",
                "vod_pic": "",
                "vod_remarks": "选择多个接口生成本地包",
                "action": self.ACTION_DOWNLOAD_PACKAGE
            })
            for site in self.package_download_sites:
                items.append({
                    "vod_id": f"localize_{site['id']}",
                    "vod_name": f"✴️ {site['name']}",
                    "vod_pic": "",
                    "vod_remarks": self._get_localize_status_text(site),
                    "action": f"localize_site_{site['id']}",
                })
            pkg_count = len(self._localized_package_dirs())
            items.append({
                "vod_id": "package_doctor",
                "vod_name": "🩺 本地包体检",
                "vod_pic": "",
                "vod_remarks": (f"检查 {pkg_count} 个本地包是否完整"
                                f"（缺失/截断可补下）" if pkg_count
                                else "还没有本地包，先执行一次本地化"),
                "action": "local_source_package_doctor",
            })
            return self._paged_result(items, page)

        elif tid == "settings":
            items = [
                {"vod_id": "show_log", "vod_name": "⚡ 日志面板", "vod_pic": "", "vod_remarks": "实时查看下载日志与进度", "action": "show_log"},
            ]
            items.append(self._setting_group_entry("log"))
            items.append(self._setting_group_entry("dirs"))
            items.append({"vod_id": "setting_sites", "vod_name": "✏️ 在线接口管理", "vod_pic": "", "vod_remarks": "添加/删除/更新在线源", "action": "local_source_manage_sites"})
            items.append(self._setting_group_entry("behavior"))
            items.append(self._setting_group_entry("transfer"))
            items.append(self._setting_group_entry("network"))
            items.append(self._setting_group_entry("naming"))
            items.append({"vod_id": "setting_tv_mode", "vod_name": "📺 TV 模式（遥控器焦点）", "vod_pic": "", "vod_remarks": self._tv_mode_text(), "action": "local_source_edit_tv_mode"})
            items.append({"vod_id": "setting_config_backup_manage", "vod_name": "💾 配置备份管理", "vod_pic": "", "vod_remarks": self._config_backup_count_text(), "action": "local_source_config_backup_manage"})
            items.append({"vod_id": "setting_restore_default", "vod_name": "➰️ 恢复默认设置", "vod_pic": "", "vod_remarks": "恢复初始配置（清除运行时修改）", "action": "local_source_restore_default"})
            return self._paged_result(items, page)
        else:
            return {"page": 1, "pagecount": 1, "limit": 10, "total": 0, "list": []}

    def _paged_result(self, items, page):
        total = len(items)
        page_size = 30
        page_count = max(1, (total + page_size - 1) // page_size)
        start = (page - 1) * page_size
        page_items = items[start:start+page_size] if page <= page_count else []
        return {
            "page": page,
            "pagecount": page_count,
            "limit": page_size,
            "total": total,
            "list": page_items,
        }

    def _page_number(self, value):
        try:
            return max(1, int(value))
        except Exception:
            return 1

    def detailContent(self, array):
        self._ensure_initialized()
        vid = str(array[0]) if isinstance(array, (list, tuple)) and array else str(array or "")
        if vid == "status":
            return {"list": [{"vod_name": "下载状态", "vod_remarks": self._package_download_message or "空闲"}]}
        if vid == self.ACTION_DOWNLOAD_PACKAGE:
            def do_download(selected_sites):
                self._exec_with_log(self._start_package_download, selected_sites)
            self._show_modern_batch_selector_v2("选择批量本地接口", do_download, "本地化", "#10B981")
            return {"list": [{"vod_name": "批量本地", "vod_remarks": "请选择接口"}]}
        if vid == "decrypt_all":
            def do_decrypt(selected_sites):
                self._exec_with_log(self._decrypt_sites, selected_sites)
            self._show_modern_batch_selector_v2("选择批量解密接口", do_decrypt, "解密", "#6C63FF")
            return {"list": [{"vod_name": "批量解密", "vod_remarks": "请选择接口"}]}
        return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        return {"page": 1, "pagecount": 1, "limit": 10, "total": 0, "list": []}

    def playerContent(self, flag, id, vipFlags):
        return {"parse": 0, "url": "", "header": {}, "msg": "该条目为配置管理"}

    def localProxy(self, params):
        return [404, "application/json", json.dumps({"error": "not found"})]

    def action(self, action):
        self._ensure_initialized()
        self._log(f"收到 action: {action}")

        if action == "local_source_manage_dirs":
            self._open_root_dirs_management()
            return {"code": 0, "msg": ""}

        if action == "local_source_scan_local_files":
            self._open_scan_local_files_dialog()
            return {"code": 0, "msg": ""}

        if action == "local_source_rescan_localized":
            self._open_root_dirs_management()
            return {"code": 0, "msg": ""}

        if action == "local_source_package_doctor":
            self._open_package_doctor_dialog()
            return {"code": 0, "msg": ""}

        if action == "local_source_switch_to_original":
            if not self._original_oktv_url:
                self._notify_app("未获取到原始接口地址")
                return {"code": 0, "msg": ""}
            ok, msg = self._switch_to_url(self._original_oktv_url, "回归中心")
            self._notify_app(msg)
            return {"code": 0, "msg": ""}

        if action.startswith("local_source_switch_localized:"):
            encoded_dir = action.split(":", 1)[1]
            self._handle_switch_localized(encoded_dir)
            return {"code": 0, "msg": ""}

        if action == "local_source_manage_switch":
            self._open_manage_switch()
            return {"code": 0, "msg": ""}
        if action == "local_source_clear_all_records":
            self._clear_all_records()
            return {"code": 0, "msg": ""}

        if action == self.ACTION_DOWNLOAD_PACKAGE:
            if self._package_download_thread and self._package_download_thread.is_alive():
                def confirm_cancel():
                    self._show_modern_confirm(
                        "任务运行中",
                        "批量本地正在运行，是否结束当前任务？",
                        lambda: self._cancel_package_download(),
                        extra_buttons=[{"text": "日志", "callback": self._show_log_dialog}]
                    )
                confirm_cancel()
                return {"code": 0, "msg": ""}
            else:
                def do_download(selected_sites):
                    self._exec_with_log(self._start_package_download, selected_sites)
                self._show_modern_batch_selector_v2("选择批量本地接口", do_download, "本地化", "#10B981")
                return {"code": 0, "msg": ""}

        if action.startswith("decrypt_site_"):
            site_id = action[len("decrypt_site_"):]
            site = next((s for s in self.package_download_sites if s['id'] == site_id), None)
            if not site:
                return {"code": 0, "msg": ""}
            state = self._site_states.get(site_id, {})
            status = state.get('decrypt_status', 'idle')

            if status == 'success':
                local_path = state.get('decrypt_result')
                if local_path and os.path.exists(local_path):
                    def do_edit():
                        try:
                            with open(local_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            remote_url = site['url']
                            local_url = "file://" + os.path.abspath(local_path)
                            def on_save():
                                self._site_states[site_id]['decrypt_msg'] = '已编辑'
                                self._save_config_to_file()
                            self._show_modern_text_editor(
                                f"⚙️ 解密内容 - {site['name']}",
                                content,
                                local_path,
                                remote_url,
                                local_url,
                                on_save,
                                jump_cb=lambda: self._jump_to_interface(
                                    local_path, site['name']),
                                rerun_label="重解密",
                                rerun_cb=lambda: self._rerun_site_task(
                                    site_id, 'decrypt'),
                                url_label="解密U"
                            )
                        except Exception as e:
                            self._log(f"打开编辑器失败: {e}")
                            self._notify_app(f"打开编辑器失败: {e}")
                    do_edit()
                    return {"code": 0, "msg": ""}

            with self._site_op_lock:
                if site_id in self._site_op_threads and self._site_op_threads[site_id].is_alive():
                    def cancel_site_decrypt():
                        self._show_modern_confirm(
                            "任务运行中",
                            f"解密「{site['name']}」正在运行，是否结束？",
                            lambda: self._cancel_site_op(site_id, 'decrypt'),
                            extra_buttons=[{"text": "日志", "callback": self._show_log_dialog}]
                        )
                    cancel_site_decrypt()
                    return {"code": 0, "msg": ""}

            extra_btns = []
            remote_url = site['url']
            extra_btns.append({"text": "远程U", "callback": lambda: self._copy_to_clipboard(remote_url, "已复制远程接口URL")})
            extra_btns.append({"text": "删除", "callback": lambda: self._show_modern_confirm(
                "确认删除", f"确定删除接口「{site['name']}」吗？",
                lambda: (self._delete_package_download_sites([site_id]), self._notify_app(f"已删除 {site['name']}"))
            )})

            self._show_modern_confirm(
                f"解密接口: {site['name']}",
                f"当前状态: {status}\n确定要启动解密任务吗？",
                lambda: self._exec_with_log(self._decrypt_single_site, site_id),
                extra_buttons=extra_btns
            )
            return {"code": 0, "msg": ""}

        if action.startswith("localize_site_"):
            site_id = action[len("localize_site_"):]
            site = next((s for s in self.package_download_sites if s['id'] == site_id), None)
            if not site:
                return {"code": 0, "msg": ""}
            state = self._site_states.get(site_id, {})
            status = state.get('localize_status', 'idle')
            with self._site_op_lock:
                if site_id in self._site_op_threads and self._site_op_threads[site_id].is_alive():
                    def cancel_site_localize():
                        self._show_modern_confirm(
                            "任务运行中",
                            f"本地化「{site['name']}」正在运行，是否结束？",
                            lambda: self._cancel_site_op(site_id, 'localize'),
                            extra_buttons=[{"text": "日志", "callback": self._show_log_dialog}]
                        )
                    cancel_site_localize()
                    return {"code": 0, "msg": ""}

            if status == 'success':
                local_path = state.get('localize_result')
                if local_path and os.path.exists(local_path):
                    def do_open_localized():
                        try:
                            with open(local_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            remote_url = site['url']
                            local_url = "file://" + os.path.abspath(local_path)

                            def on_save():
                                self._site_states[site_id]['localize_msg'] = '已编辑'
                                self._save_config_to_file()

                            self._show_modern_text_editor(
                                f"📦 本地化内容 - {site['name']}",
                                content, local_path,
                                remote_url, local_url, on_save,
                                jump_cb=lambda: self._jump_to_interface(
                                    local_path, site['name']),
                                rerun_label="重本地化",
                                rerun_cb=lambda: self._rerun_site_task(
                                    site_id, 'localize'),
                                url_label="本地化U"
                            )
                        except Exception as e:
                            self._log(f"打开本地化内容失败: {e}")
                            self._notify_app(f"打开失败: {e}")
                    do_open_localized()
                    return {"code": 0, "msg": ""}

            extra_btns = []
            remote_url = site['url']
            extra_btns.append({"text": "远程U", "callback": lambda: self._copy_to_clipboard(remote_url, "已复制远程接口URL")})
            extra_btns.append({"text": "删除", "callback": lambda: self._show_modern_confirm(
                "确认删除", f"确定删除接口「{site['name']}」吗？",
                lambda: (self._delete_package_download_sites([site_id]), self._notify_app(f"已删除 {site['name']}"))
            )})

            self._show_modern_confirm(
                f"本地化接口: {site['name']}",
                f"当前状态: {status}\n确定要启动本地化任务吗？",
                lambda: self._exec_with_log(self._localize_single_site, site_id),
                extra_buttons=extra_btns
            )
            return {"code": 0, "msg": ""}

        if action == "decrypt_all":
            def do_decrypt(selected_sites):
                self._exec_with_log(self._decrypt_sites, selected_sites)
            self._show_modern_batch_selector_v2("选择批量解密接口", do_decrypt, "解密", "#6C63FF")
            return {"code": 0, "msg": ""}

        if action == 'show_status':
            status_msg = self._package_download_message or "空闲"
            self._show_modern_info("下载状态", status_msg, show_copy=True)
        elif action == 'show_log' or action == 'show_monitor':
            self._show_log_dialog()
        elif action == 'local_source_manage_sites':
            self._open_site_management_dialog()
        elif action == 'local_source_config_backup_manage':
            self._open_config_backup_dialog()
            return {"code": 0, "msg": ""}
        elif action == 'local_source_edit_tv_mode':
            self._open_tv_mode_dialog()
        elif action == 'local_source_restore_default':
            self._show_modern_confirm(
                "确认恢复初始配置",
                "确定要恢复初始配置吗？\n将清除所有运行时修改（缓存、持久化配置、接口状态等），重新加载初始数据。",
                lambda: self._exec_with_log(self._restore_default_config)
            )
        else:
            if action.startswith("local_source_setting_group:"):
                self._open_setting_group_dialog(
                    action.split(":", 1)[1].strip())
                return {"code": 0, "msg": ""}
            spec = SETTING_SPECS_BY_ACTION.get(action)
            if spec is not None:
                self._open_setting_dialog(spec)
            else:
                self._log(f"未知 action: {action}")
        return {"code": 0, "msg": ""}

    def _cancel_package_download(self):
        if self._package_cancel_event:
            self._package_cancel_event.set()
            self._log("用户请求取消批量下载")
            self._notify_app("正在取消批量下载...")

    def _cancel_site_op(self, site_id, op_type):
        if site_id in self._site_cancel_events:
            self._site_cancel_events[site_id].set()
            self._log(f"用户请求取消 {op_type} 操作 (site_id={site_id})")
            self._notify_app(f"正在取消 {op_type}...")

    def destroy(self):
        self._destroyed = True
        try:
            self._log_flush()
        except Exception:
            pass
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
        for ev in self._site_cancel_events.values():
            ev.set()
        if self._package_cancel_event:
            self._package_cancel_event.set()
        return "destroy"

    def _ensure_initialized(self):
        if not self.inited:
            try:
                self.init("")
            except Exception as e:
                self._log(f"延迟初始化失败: {e}")
                self.inited = True

    def _show_modern_text_editor(self, title, content, file_path, remote_url, local_url,
                                 on_save, jump_cb=None, rerun_label=None,
                                 rerun_cb=None, url_label="解密U"):
        dlg_holder = {"dialog": None}

        def on_ui(act):
            spider = self
            kit = self._kit(act)
            G = kit.gravity()

            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))

            edit = kit.input(value=content, multiline=True, mono=True,
                             min_lines=EDIT_MIN_LINES)
            state_key_listener = {"orig": None}
            try:
                state_key_listener["orig"] = edit.getKeyListener()
                edit.setKeyListener(None)
                edit.setFocusable(False)
                edit.setFocusableInTouchMode(False)
                edit.setCursorVisible(False)
                edit.setLongClickable(False)
                edit.setVerticalFadingEdgeEnabled(False)
                edit.setOverScrollMode(2)
                if G:
                    edit.setGravity(G.TOP | G.START)
            except Exception:
                pass

            state = {"editable": False}
            toggle_btn = {"btn": None}
            hint_view = kit.hint("", max_lines=2)

            def _sync_toggle():
                btn = toggle_btn.get("btn")
                if btn is None:
                    return
                if state["editable"]:
                    btn.setText("🔒 锁定")
                    try:
                        hint_view.setText("编辑中：可直接修改，改完点「💾 保存」；"
                                          "点「🔒 锁定」回到只读")
                    except Exception:
                        pass
                else:
                    btn.setText("✏️ 编辑")
                    try:
                        hint_view.setText("只读（防误触）：点「✏️ 编辑」后可修改，"
                                          "需要复制全文用「📋 复制」")
                    except Exception:
                        pass
                btn.setTextColor(kit.color(UITheme.WHITE if state["editable"] else UITheme.TEXT_2))
                kit._set_bg(btn, kit.pressable(
                    UITheme.SUCCESS if state["editable"] else UITheme.SURFACE,
                    UITheme.SUCCESS_DEEP if state["editable"] else UITheme.SURFACE_SUNKEN,
                    UITheme.R_SM, 1.0,
                    UITheme.SUCCESS if state["editable"] else UITheme.BORDER))
                kit._set_bg(edit, kit.shape(
                    UITheme.SURFACE if state["editable"] else UITheme.SURFACE_ALT,
                    UITheme.R_MD, 1.0,
                    UITheme.BRAND_LINE if state["editable"] else UITheme.BORDER))

            def copy_decrypt_url():
                spider._copy_to_clipboard(local_url, "已复制解密文件路径")
                kit.toast("已复制解密U")

            def toggle_edit():
                state["editable"] = not state["editable"]
                on = state["editable"]
                try:
                    if on:
                        edit.setKeyListener(state_key_listener.get("orig"))
                        edit.setFocusable(True)
                        edit.setFocusableInTouchMode(True)
                        edit.setCursorVisible(True)
                        try:
                            edit.setTextIsSelectable(True)
                        except Exception:
                            pass
                        edit.requestFocus()
                    else:
                        edit.setKeyListener(None)
                        try:
                            edit.setTextIsSelectable(False)
                        except Exception:
                            pass
                        edit.setFocusable(False)
                        edit.setFocusableInTouchMode(False)
                        edit.setCursorVisible(False)
                except Exception:
                    pass
                _sync_toggle()

            def copy_content():
                text = str(edit.getText())
                spider._copy_to_clipboard(text, "已复制全部内容")
                kit.toast("已复制全部内容")

            def copy_remote_url():
                spider._copy_to_clipboard(remote_url, "已复制远程接口URL")
                kit.toast("已复制远程U")

            def do_save_content():
                try:
                    new_content = str(edit.getText())
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    on_save()
                    kit.toast("已保存 ✓")
                except Exception as e:
                    kit.toast(f"保存失败: {e}", long=True)

            def _make_tool_button(label, style, cb):
                btn = kit.button(label, style, cb, None, "sm")
                btn.setLayoutParams(kit.lp(0, kit.dp(UITheme.H_BTN_SM), 1.0))
                return btn

            def _wrap_dismiss(cb):
                def _run():
                    try:
                        d = dlg_holder.get("dialog")
                        if d is not None:
                            d.dismiss()
                    except Exception:
                        pass
                    if cb:
                        cb()
                return _run

            top_row = kit.hbox()
            top_row.setLayoutParams(kit.lp(-1, -2))
            if G:
                top_row.setGravity(G.CENTER)
            btn_toggle = _make_tool_button("", "secondary", toggle_edit)
            top_row.addView(btn_toggle)
            top_row.addView(self._with_margin(
                kit, _make_tool_button("💾 保存", "primary", do_save_content),
                UITheme.S_XS))
            if jump_cb:
                top_row.addView(self._with_margin(
                    kit, _make_tool_button("🚀 跳转", "success", _wrap_dismiss(jump_cb)),
                    UITheme.S_XS))
            top_row.addView(self._with_margin(
                kit, _make_tool_button("📋 复制", "secondary", copy_content),
                UITheme.S_XS))
            toggle_btn["btn"] = btn_toggle
            _sync_toggle()

            box.addView(top_row, kit.lp(-1, -2))

            box.addView(hint_view,
                        kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, UITheme.S_XS)))
            box.addView(edit, kit.lp(-1, -2))

            buttons = [
                {"text": "🌐 远程U", "style": "secondary",
                 "callback": copy_remote_url, "dismiss": False},
                {"text": "🔑 " + str(url_label or "解密U"), "style": "secondary",
                 "callback": copy_decrypt_url, "dismiss": False},
            ]
            if rerun_cb:
                buttons.append({
                    "text": "🔄 " + str(rerun_label or "重新执行"),
                    "style": "primary",
                    "callback": _wrap_dismiss(rerun_cb), "dismiss": False})
            buttons.append({"text": "关闭", "style": "secondary",
                            "callback": None, "dismiss": True})
            dlg_holder["dialog"] = self._show_dialog(
                act, title, box, buttons, width_ratio=0.94,
                height_ratio=0.92, scroll=True)
        self._run_on_ui(on_ui)

    def _open_package_download_url_dialog(self):
        self._notify_app("该功能已合并至「在线接口管理」")

    def _open_package_download_delete_dialog(self):
        self._notify_app("该功能已合并至「在线接口管理」")

    def _show_root_dirs_selector(self):
        self._open_root_dirs_management()

    def _get_setting(self, spec):
        if spec.get("virtual"):
            return self._get_virtual_setting(spec)
        src = spec.get("src")
        if not src:
            if spec.get("dl_key"):
                src = "dl"
            elif spec.get("attr"):
                src = "attr"
            else:
                src = "config"
        default = spec.get("default")
        try:
            if src == "attr":
                return getattr(self, spec["attr"], default)
            if src == "dl":
                return self.download_config.get(spec["dl_key"], default)
            node = self.config
            for k in spec["path"].split('.'):
                if not isinstance(node, dict):
                    return default
                node = node.get(k)
            return default if node is None else node
        except Exception:
            return default

    def _set_setting(self, spec, value):
        if spec.get("virtual"):
            self._set_virtual_setting(spec, value)
            return
        if spec.get("store") == "attr":
            setattr(self, spec["attr"], value)
            self._save_config_to_file()
            return
        raw = spec.get("raw", False)
        self._update_config_value(spec["path"], value, raw=raw, save=False)

        if spec.get("dl_key"):
            self.download_config[spec["dl_key"]] = value
        for extra in (spec.get("mirror") or []):
            self._update_config_value(extra, value, raw=raw, save=False)
        self._save_config_to_file()

    def _get_virtual_setting(self, spec):
        key = spec.get("key")
        if key == "log_mode":
            try:
                if not bool(self.log_enabled):
                    return "off"
            except Exception:
                pass
            lv = str(getattr(self, "log_level", "info") or "info").lower()
            return lv if lv in ("error", "warn", "info", "debug") else "info"
        return spec.get("default")

    def _set_virtual_setting(self, spec, value):
        key = spec.get("key")
        if key != "log_mode":
            return
        v = str(value or "").lower()
        if v == "off":
            self._update_config_value("log.enabled", False, raw=True, save=False)
            self.log_enabled = False
        else:
            if v not in ("error", "warn", "info", "debug"):
                v = "info"
            self._update_config_value("log.enabled", True, raw=True, save=False)
            self._update_config_value("log.level", v, raw=True, save=False)
            self.log_enabled = True
            self.log_level = v
        self._save_config_to_file()

    def _normalize_setting(self, spec, value):
        if spec["kind"] == "int":
            val = int(value)
            lo, hi = spec.get("min"), spec.get("max")
            if lo is not None:
                val = max(lo, val)
            if hi is not None:
                val = min(hi, val)
            return val
        if spec["kind"] == "dir" and spec.get("normalize") == "dir_slash":
            return str(value).rstrip('/') + '/'
        return value

    def _open_setting_dialog(self, spec):
        kind = spec["kind"]
        current = self._get_setting(spec)

        def commit(raw_value):
            try:
                value = self._normalize_setting(spec, raw_value)
            except Exception as e:
                self._notify_app("输入无效: {}".format(e))
                return
            if kind == "dir" and not value and spec.get("default"):
                value = spec["default"]
            self._set_setting(spec, value)
            if spec.get("makedirs") and isinstance(value, str) and value:
                try:
                    os.makedirs(value, exist_ok=True)
                except Exception as e:
                    self._log("创建目录失败: {}".format(e))
            self._log("设置已更新: {} = {}".format(spec["key"], value))

        if kind in ("text", "int"):
            self._show_modern_input(spec["title"], spec.get("hint", ""), str(current), commit)
        elif kind == "dir":
            self._pick_dir(spec["title"], current, commit)
        elif kind == "choice":
            def on_choose(val):
                commit(val)
                self._notify_app(spec.get("done_tpl", "已设为: {}").format(val))
            self._show_modern_radio_selector(spec["title"], spec.get("opts") or [], current, on_choose)
        elif kind == "bool":
            self._open_setting_switch_dialog(spec, current, commit)
        else:
            self._log("未知设置类型: {}".format(kind))

    def _open_setting_switch_dialog(self, spec, current, commit):
        def on_ui(act):
            spider = self
            kit = self._kit(act)
            cur = bool(current)

            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))
            if spec.get("pre_hint"):
                box.addView(kit.hint(spec["pre_hint"]), kit.lp(-1, -2))
            sw_state = {}
            sub = spec.get("sw_sub")
            sw_card = kit.switch_card(
                spec.get("sw_label", spec["title"]),
                sub(spider) if callable(sub) else (sub or ""),
                cur, None, state_out=sw_state,
            )
            box.addView(sw_card, kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))
            if spec.get("post_hint"):
                box.addView(kit.hint(spec["post_hint"]),
                            kit.lp(-1, -2, 0.0, (UITheme.S_SM, 0.0, 0.0, 0.0)))

            def save():
                enabled = bool(sw_state["switch"].isChecked())
                commit(enabled)
                kit.toast(spec.get("toast_tpl", "已{}").format(
                    "开启" if enabled else "关闭"))

            buttons = [
                {"text": "取消", "style": "secondary", "callback": None, "dismiss": True},
                {"text": "保存", "style": "primary", "callback": save, "dismiss": True},
            ]
            self._show_dialog(act, spec["title"], box, buttons, height_ratio=0)
        self._run_on_ui(on_ui)

    def _setting_remarks(self, spec):
        value = self._get_setting(spec)
        fmt = spec.get("fmt", "str")
        if fmt == "onoff":
            return spec.get("on_text", "开启") if value else spec.get("off_text", "关闭")
        if fmt == "log_mode":
            v = str(value or "info").lower()
            if v == "off":
                return "已关闭"
            return "已开启 · {}".format(v.upper())
        if fmt == "upper":
            return str(value).upper()
        if fmt == "dir":
            return str(value).rstrip('/') if value else "未设置"
        if fmt == "or_unset":
            return str(value) if value else "未设置"
        if fmt == "trunc30":
            text = str(value or "")
            return text[:30] + "..." if len(text) > 30 else text
        return "" if value is None else str(value)

    def _setting_display(self, spec, value=None):
        return self._setting_remarks(spec)

    def _config_backup_count_text(self):
        try:
            backups, _root = self._list_config_backups()
            return "{} 份备份 · 可新建/恢复/重命名/删除".format(len(backups))
        except Exception:
            return "新建/恢复/重命名/删除配置备份"

    def _setting_entry(self, key):
        spec = SETTING_SPECS_BY_KEY.get(key)
        if not spec:
            self._log("设置项未注册: {}".format(key))
            return None
        return {
            "vod_id": "setting_" + spec.get("id", key),
            "vod_name": spec.get("name") or "{} {}".format(
                spec.get("icon", "⚙️"), spec.get("label", key)).strip(),
            "vod_pic": "",
            "vod_remarks": self._setting_remarks(spec),
            "action": "local_source_edit_" + key,
        }

    def _setting_entries(self, keys):
        return [it for it in (self._setting_entry(k) for k in keys) if it]

    def _setting_group_remark(self, gkey):
        grp = SETTING_GROUPS.get(gkey)
        if not grp:
            return ""
        labels = []
        for k in grp["keys"]:
            spec = SETTING_SPECS_BY_KEY.get(k)
            if spec:
                labels.append(str(spec.get("label", k)))
        return " · ".join(labels)

    def _setting_group_entry(self, gkey):
        grp = SETTING_GROUPS.get(gkey)
        if not grp:
            return None
        return {
            "vod_id": "setting_group_" + gkey,
            "vod_name": "%s %s" % (grp.get("icon", "⚙️"), grp["title"]),
            "vod_pic": "",
            "vod_remarks": self._setting_group_remark(gkey),
            "action": "local_source_setting_group:" + gkey,
        }

    def _open_setting_group_dialog(self, gkey):
        grp = SETTING_GROUPS.get(gkey)
        if not grp:
            self._log("未注册的分组: {}".format(gkey))
            return
        spider = self

        def on_ui(act):
            kit = self._kit(act)
            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))
            editors = {}

            def add_row(spec):
                key = spec["key"]
                kind = spec["kind"]
                label = spec.get("label", key)
                icon = spec.get("icon", "⚙️")
                cur = spider._get_setting(spec)

                if kind == "bool":
                    st = {}
                    sub = spec.get("sw_sub")
                    box.addView(kit.switch_card(
                        "{} {}".format(icon, label),
                        sub(spider) if callable(sub) else (sub or ""),
                        bool(cur), None, state_out=st,
                    ), kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))
                    editors[key] = (lambda: bool(st["switch"].isChecked()), spec)

                elif kind in ("int", "text"):
                    box.addView(kit.text("{} {}".format(icon, label),
                                         bold=True), kit.lp(-1, -2))
                    et = kit.input(hint=spec.get("input_hint", ""),
                                   value=str(cur if cur is not None else ""),
                                   multiline=False,
                                   mono=(kind == "text"))
                    box.addView(et, kit.lp(-1, -2, 0.0,
                                           (0.0, UITheme.S_XXS, 0.0,
                                            UITheme.S_SM)))
                    editors[key] = (lambda e=et: str(e.getText() or "").strip(),
                                    spec)

                elif kind == "choice":
                    box.addView(kit.text("{} {}".format(icon, label),
                                         bold=True), kit.lp(-1, -2))
                    group, radios = self._ui_radio_group(
                        kit, spec.get("opts") or [], cur)
                    if group is None:
                        box.addView(kit.hint("（无法构建选项）"), kit.lp(-1, -2))
                        return
                    box.addView(group, kit.lp(-1, -2, 0.0,
                                              (0.0, UITheme.S_XXS, 0.0,
                                               UITheme.S_SM)))

                    def _read(g=group, rmap=radios, fallback=cur):
                        cid = g.getCheckedRadioButtonId()
                        for v, rb in rmap.items():
                            if rb.getId() == cid:
                                return v
                        return fallback
                    editors[key] = (_read, spec)

                elif kind == "dir":
                    box.addView(kit.text("{} {}".format(icon, label),
                                         bold=True), kit.lp(-1, -2))
                    row = kit.hbox()
                    row.setLayoutParams(kit.lp(-1, -2))
                    et = kit.input(hint="留空用默认目录",
                                   value=str(cur or ""), multiline=False)
                    row.addView(et, kit.lp(0, -2, 1.0))

                    def _browse(e=et, sp=spec):
                        spider._pick_dir(
                            sp.get("title", "选择目录"),
                            str(e.getText() or ""),
                            lambda v: e.setText(str(v or "")),
                        )
                    bb = kit.button("📁", "secondary", _browse, None, "sm")
                    row.addView(bb, kit.lp(-2, -2, 0.0,
                                           margins=(kit.dp(UITheme.S_XS),
                                                    0.0, 0.0, 0.0)))
                    box.addView(row, kit.lp(-1, -2, 0.0,
                                            (0.0, UITheme.S_XXS, 0.0,
                                             UITheme.S_SM)))
                    editors[key] = (lambda e=et: str(e.getText() or "").strip(),
                                    spec)

            subs = grp.get("subsections")
            if subs:
                for sub_title, sub_keys in subs:
                    box.addView(kit.section_title(sub_title), kit.lp(-1, -2))
                    for k in sub_keys:
                        sp = SETTING_SPECS_BY_KEY.get(k)
                        if sp:
                            add_row(sp)
            else:
                for k in grp["keys"]:
                    sp = SETTING_SPECS_BY_KEY.get(k)
                    if sp:
                        add_row(sp)

            def do_save():
                n = 0
                for key, (getter, sp) in editors.items():
                    try:
                        raw = getter()
                    except Exception as e:
                        self._log("读取设置失败 {}: {}".format(key, e))
                        continue
                    try:
                        val = self._normalize_setting(sp, raw)
                    except Exception as e:
                        kit.toast("{}：{}".format(sp.get("label", key), e),
                                  long=True)
                        continue
                    if sp["kind"] == "dir" and not val and sp.get("default"):
                        val = sp["default"]
                    old = self._get_setting(sp)
                    if str(old) != str(val):
                        self._set_setting(sp, val)
                        n += 1
                    if sp.get("makedirs") and isinstance(val, str) and val:
                        try:
                            os.makedirs(val, exist_ok=True)
                        except Exception:
                            pass
                kit.toast("已保存 {} 项".format(n) if n else "没有改动")

            buttons = [{"text": "关闭", "style": "secondary",
                        "callback": None, "dismiss": True},
                       {"text": "保存", "style": "primary",
                        "callback": do_save, "dismiss": True}]
            self._show_dialog(act, "{} {}".format(grp.get("icon", "⚙️"),
                                                  grp["title"]),
                              box, buttons, height_ratio=0)

        self._run_on_ui(on_ui)

    def _unify_dirs(self):
        base = str(getattr(self, "download_output_dir", "") or "").strip()
        if not base:
            self._notify_app("本地包下载目录为空，请先设置")
            return
        base = base.rstrip("/")
        self._set_setting(SETTING_SPECS_BY_KEY["log_dir"], base + "/")
        self._set_setting(SETTING_SPECS_BY_KEY["config_backup"], base)
        for d in (base, base + "/"):
            try:
                os.makedirs(d, exist_ok=True)
            except Exception:
                pass
        self._save_config_to_file()
        self._notify_app("已统一到：{}".format(base))

    def _open_tv_mode_dialog(self):
        def on_ui(act):
            spider = self
            kit = self._kit(act)
            cur_auto = getattr(spider, "tv_mode", None) is None
            cur = spider._tv_mode(kit)

            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))
            box.addView(kit.hint(
                "电视用遥控器操作时需开启；手机若要点两下才生效，请关闭。"),
                kit.lp(-1, -2))

            sw_state = {}
            box.addView(kit.switch_card(
                "TV 模式（遥控器焦点）",
                "当前：{}｜设备识别：{}".format("开启" if cur else "关闭", kit.kind),
                cur, None, state_out=sw_state,
            ), kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))

            auto_state = {}
            box.addView(kit.switch_card(
                "跟随设备自动判断",
                "开启：按设备类型自动决定（电视开 / 手机关）；关闭：使用上面的手动值",
                cur_auto, None, state_out=auto_state,
            ), kit.lp(-1, -2))

            def save():
                auto = bool(auto_state["switch"].isChecked())
                manual = bool(sw_state["switch"].isChecked())
                spider.tv_mode = None if auto else manual
                spider._save_additional_config()
                kit.toast("TV 模式：{}".format(
                    "自动" if auto else ("开启" if manual else "关闭")))

            buttons = [
                {"text": "取消", "style": "secondary", "callback": None, "dismiss": True},
                {"text": "保存", "style": "primary", "callback": save, "dismiss": True},
            ]
            self._show_dialog(act, "TV 模式（遥控器焦点）", box, buttons, height_ratio=0)
        self._run_on_ui(on_ui)

    def _notify_app(self, message, wait=False, replace=False):
        text = " ".join(str(message or "").split()).strip()
        if not text or self._destroyed:
            return False
        if len(text) > 200:
            text = text[:197] + "..."
        try:
            from java import dynamic_proxy, jclass
            from java.lang import Runnable
            toast_class = jclass("android.widget.Toast")
            act = self._activity()
            if not act:
                return False
            displayed = threading.Event()
            class Show(dynamic_proxy(Runnable)):
                def __init__(self):
                    super().__init__()
                def run(self):
                    try:
                        toast = toast_class.makeText(act, text[:120], toast_class.LENGTH_LONG)
                        toast.show()
                    except Exception:
                        pass
                    finally:
                        displayed.set()
            runner = Show()
            self._notification_refs.append(runner)
            act.runOnUiThread(runner)
            if wait and not displayed.wait(1.5):
                return False
            return True
        except Exception:
            return False
    _STR_MARK = "\x00"

    _CTRL_ESCAPES = {
        '\n': '\\n',
        '\r': '\\r',
        '\t': '\\t',
        '\b': '\\b',
        '\f': '\\f',
    }

    @classmethod
    def _escape_string_controls(cls, tok):
        if not tok or len(tok) < 2:
            return tok
        quote = tok[0]
        inner = tok[1:-1]
        esc = cls._CTRL_ESCAPES
        if not any(c in inner for c in esc):
            return tok
        out = []
        i = 0
        n = len(inner)
        while i < n:
            ch = inner[i]
            if ch == '\\' and i + 1 < n:
                out.append(inner[i:i + 2])
                i += 2
                continue
            if ch in esc:
                out.append(esc[ch])
                i += 1
                continue
            out.append(ch)
            i += 1
        return quote + ''.join(out) + quote

    @classmethod
    def _protect_json_strings(cls, text):
        import re
        strings = []
        counter = [0]
        mark = cls._STR_MARK

        def protect(m):
            tok = m.group(0)
            if tok[:1] == "'":
                inner = tok[1:-1]
                inner = inner.replace('"', '\\"').replace("\\'", "'")
                tok = '"' + inner + '"'
            tok = cls._escape_string_controls(tok)
            ph = "{mark}JSTR{n}{mark}".format(mark=mark, n=counter[0])
            strings.append(tok)
            counter[0] += 1
            return ph

        pattern = r'"(?:\\.|[^"\\])*"' + "|" + r"'(?:\\.|[^'\\])*'"
        return re.sub(pattern, protect, text), strings

    def _clean_json_comments(self, text, repair=True):
        import re
        if not text or not isinstance(text, str):
            return text or ""

        s = text.lstrip('\ufeff')
        if self._STR_MARK in s:
            s = s.replace(self._STR_MARK, "")

        protected, strings = self._protect_json_strings(s)

        protected = re.sub(r'//\*\*[\s\S]*?\*/', '', protected)
        protected = re.sub(r'/\*[\s\S]*?\*/', '', protected)
        protected = re.sub(r'//[^\n]*', '', protected)
        protected = re.sub(r'#[^\n]*', '', protected)

        if repair:
            protected = re.sub(r',(\s*[}\]])', r'\1', protected)
            protected = re.sub(
                r'([{,]\s*)([A-Za-z_$\u4e00-\u9fff][\w$\u4e00-\u9fff]*)(\s*:)',
                r'\1"\2"\3', protected)

        cleaned = '\n'.join(l for l in protected.split('\n') if l.strip())

        def restore(m):
            idx = int(m.group(1))
            return strings[idx] if idx < len(strings) else '""'

        restore_pat = (re.escape(self._STR_MARK) + r'JSTR(\d+)'
                       + re.escape(self._STR_MARK))
        return re.sub(restore_pat, restore, cleaned).strip()

    @staticmethod
    def _json_error_hint(text, err):
        try:
            msg = str(err)
            m = re.search(r'line (\d+) column (\d+)', msg)
            if not m:
                return msg
            ln = int(m.group(1))
            col = int(m.group(2))
            lines = str(text or "").split('\n')
            if 0 <= ln - 1 < len(lines):
                line = lines[ln - 1].strip()
                near = line[:120]
                return "第 {} 行第 {} 列附近：{}".format(ln, col, near)
            return msg
        except Exception:
            return str(err)

    def _parse_import_source(self, text):
        s = str(text or "").strip()
        if not s:
            return [], "请输入内容"

        errors = []

        def from_json(raw, where):
            try:
                parsed = self._parse_multi_warehouse_json(raw)
            except Exception as e:
                errors.append("%s解析失败: %s" % (where, e))
                return None
            if not parsed:
                errors.append("%s里没有可识别的接口（需要 name 和 url）" % where)
                return None
            return [(i.get("name", ""), i.get("url", "")) for i in parsed]

        if s[:1] in ("{", "["):
            got = from_json(s, "JSON")
            return (got, None) if got is not None else ([], "；".join(errors))

        if s.lower().startswith("file://"):
            path = s[7:]
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    raw = f.read()
            except Exception as e:
                return [], "读取本地文件失败: %s" % e
            got = from_json(raw, "文件")
            return (got, None) if got is not None else ([], "；".join(errors))

        lines = [l.strip() for l in s.splitlines() if l.strip()]
        if not lines:
            return [], "请输入内容"

        if len(lines) == 1 and lines[0].lower().startswith(("http://", "https://")):
            u = lines[0]
            try:
                resp = self.session.get(u, timeout=self.timeout_read)
                raw = resp.text
            except Exception as e:
                return [], "下载失败: %s" % e
            got = from_json(raw, "远程内容")
            return (got, None) if got is not None else ([], "；".join(errors))

        pairs = []
        for u in lines:
            if u.lower().startswith(("http://", "https://")):
                pairs.append((self._name_from_url(u), u))
            else:
                self._log("忽略无效行（不是 http 地址）: %s" % u[:60])
        if not pairs:
            return [], "没有识别到有效地址（每行需以 http:// 或 https:// 开头）"
        return pairs, None

    def _parse_multi_warehouse_json(self, text):
        try:
            cleaned = self._clean_json_comments(text)
            data = json.loads(cleaned)

            entries = self._extract_warehouse_entries(data)
            if not entries:
                return []

            imported = []
            for e in entries:
                name = str(e.get('name') or '').strip()
                url = str(e.get('url') or '').strip()
                if not url:
                    continue
                if not name:
                    name = self._name_from_url(url)
                imported.append({'name': name, 'url': url})
            return imported
        except Exception as e:
            self._log(f"解析多仓JSON失败: {e}")
            return []

    WH_URL_KEYS = ('url', 'api', 'address', 'link', 'src', 'href', 'uri')
    WH_NAME_KEYS = ('name', 'title', 'label', 'text', 'desc')
    WH_MAX_DEPTH = 12

    def _extract_warehouse_entries(self, data):
        found = []
        seen = set()

        def _looks_like_url(v):
            s = str(v or "").strip()
            return s.lower().startswith(("http://", "https://"))

        def walk(obj, depth):
            if depth > self.WH_MAX_DEPTH:
                return
            if isinstance(obj, dict):
                url_val = ""
                for k in self.WH_URL_KEYS:
                    if k in obj:
                        cand = obj.get(k)
                        if _looks_like_url(cand):
                            url_val = str(cand).strip()
                            break
                if url_val:
                    name_val = ""
                    for k in self.WH_NAME_KEYS:
                        if k in obj:
                            cand = obj.get(k)
                            if cand and str(cand).strip():
                                name_val = str(cand).strip()
                                break
                    key = url_val
                    if key not in seen:
                        seen.add(key)
                        found.append({'name': name_val, 'url': url_val,
                                      'raw': dict(obj)})
                for v in obj.values():
                    walk(v, depth + 1)
            elif isinstance(obj, (list, tuple)):
                for v in obj:
                    walk(v, depth + 1)

        walk(data, 0)
        return found

    def _copy_sites_as_multi_warehouse(self, sites):
        import json
        try:
            urls = []
            for site in sites:
                urls.append({
                    "name": site.get('name', '未命名'),
                    "url": site.get('url', '')
                })
            result = json.dumps({"urls": urls}, ensure_ascii=False, indent=2)
            self._copy_to_clipboard(result, "已复制多仓格式JSON")
            return True
        except Exception as e:
            self._log(f"复制多仓格式失败: {e}")
            return False

    def _show_modern_batch_selector_v2(self, title, callback, action_name="执行", action_color="#6C63FF"):
        def on_ui(act):
            spider = self
            kit = self._kit(act)

            site_states = {}
            for site in spider.package_download_sites:
                site_states[str(site.get('id', ''))] = site.get('enabled', True)

            container = kit.vbox()
            container.setLayoutParams(kit.lp(-1, -2))

            sites_container = kit.vbox()
            sites_container.setLayoutParams(kit.lp(-1, -2))

            def refresh_site_list():
                sites_container.removeAllViews()
                if not spider.package_download_sites:
                    sites_container.addView(kit.empty("暂无接口，可先在下方添加或导入"),
                                            kit.lp(-1, -2))
                    return
                for site in spider.package_download_sites:
                    sid = str(site.get('id', ''))

                    def make_toggle(key=sid):
                        def on_change(v):
                            site_states[key] = bool(v)
                        return on_change

                    def make_edit(s=site):
                        sname = s.get('name', '')
                        surl = s.get('url', '')

                        def on_edit():
                            def on_save(values):
                                new_name, new_url = values[0].strip(), values[1].strip()
                                if not new_name or not new_url:
                                    kit.toast("名称和地址都不能为空")
                                    return
                                try:
                                    with spider.lock:
                                        if new_name != sname or new_url != surl:
                                            spider._delete_package_download_sites([s.get("id")])
                                        spider._add_or_update_package_download_site(new_name, new_url)
                                    site_states[str(s.get("id", ""))] = True
                                    kit.toast("已更新")
                                    refresh_site_list()
                                except Exception as exc:
                                    kit.toast("保存失败: {}".format(exc), long=True)
                            spider._show_modern_input_multi(
                                "编辑接口", [
                                    ("备注名", sname, {"input_hint": "输入名称"}),
                                    ("接口地址", surl, {"input_hint": "https://..."}),
                                ], on_save)
                        return on_edit

                    def make_copy(s=site):
                        def on_copy():
                            import json as _json
                            single = _json.dumps({"urls": [{"name": s.get('name', ''),
                                                            "url": s.get('url', '')}]},
                                                 ensure_ascii=False, indent=2)
                            kit.toast("已复制单接口" if kit.copy(single, "接口") else "复制失败")
                        return on_copy

                    def make_del(s=site):
                        def on_del():
                            try:
                                with spider.lock:
                                    spider._delete_package_download_sites([s.get("id")])
                                site_states.pop(str(s.get("id", "")), None)
                                kit.toast("已删除：{}".format(s.get("name", "")))
                                refresh_site_list()
                            except Exception as exc:
                                kit.toast("删除失败: {}".format(exc), long=True)
                        return on_del

                    actions = [
                        {"text": "编辑", "style": "secondary", "callback": make_edit()},
                        {"text": "复制", "style": "secondary", "callback": make_copy()},
                        {"text": "删除", "style": "soft_danger", "callback": make_del()},
                    ]
                    sites_container.addView(
                        spider._ui_site_card(kit, s_name_of(site), site.get("url", ""),
                                             site_states.get(sid, True), make_toggle(), actions),
                        kit.lp(-1, -2))

            def s_name_of(site):
                return site.get("name", "未命名")

            entry_card = kit.card()
            entry_card.addView(
                kit.section_title("➕ 接口录入",
                                  hint="添加单个 / 批量导入 / 直接粘贴接口代码"),
                kit.lp(-1, -2))
            entry_card.addView(self._site_entry_buttons(kit, refresh_site_list),
                               kit.lp(-1, -2, 0.0, (0.0, UITheme.S_MD, 0.0, 0.0)))
            container.addView(entry_card, kit.lp(-1, -2))

            list_card = kit.card()
            list_card.addView(kit.section_title("📋 选择要处理的接口"), kit.lp(-1, -2))

            def select_all_sites():
                for s in spider.package_download_sites:
                    site_states[str(s['id'])] = True
                refresh_site_list()

            def invert_sites():
                for s in spider.package_download_sites:
                    k = str(s['id'])
                    site_states[k] = not site_states.get(k, True)
                refresh_site_list()

            def clear_sites():
                for s in spider.package_download_sites:
                    site_states[str(s['id'])] = False
                refresh_site_list()

            def copy_selected_sites():
                selected = [s for s in spider.package_download_sites
                            if site_states.get(str(s['id']), False)]
                if not selected:
                    kit.toast("没有选中的接口")
                    return
                spider._copy_sites_as_multi_warehouse(selected)
                kit.toast("已复制多仓格式")

            list_card.addView(kit.button_bar([
                {"text": "全选", "style": "secondary", "callback": select_all_sites, "dismiss": False},
                {"text": "反选", "style": "secondary", "callback": invert_sites, "dismiss": False},
                {"text": "清空", "style": "secondary", "callback": clear_sites, "dismiss": False},
                {"text": "复制已选", "style": "soft_brand", "callback": copy_selected_sites, "dismiss": False},
            ], size="sm"), kit.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_SM)))

            list_card.addView(sites_container, kit.lp(-1, -2))
            refresh_site_list()
            container.addView(list_card, kit.lp(-1, -2))

            def do_delete_selected():
                selected_sids = [sid for sid, state in site_states.items() if state]
                if not selected_sids:
                    kit.toast("没有选中的接口")
                    return
                try:
                    with spider.lock:
                        spider._delete_package_download_sites(selected_sids)
                    for sid in selected_sids:
                        site_states.pop(sid, None)
                    kit.toast("已删除 {} 个选中接口".format(len(selected_sids)))
                    refresh_site_list()
                except Exception as exc:
                    kit.toast("删除失败: {}".format(exc), long=True)

            def do_confirm():
                selected = [s for s in spider.package_download_sites
                            if site_states.get(str(s.get("id", "")), False)]
                if not selected:
                    kit.toast("请至少选中一个接口")
                    return
                callback(selected)

            action_style = UITheme.LEGACY_COLOR_MAP.get(
                str(action_color or "").strip().upper(), "primary")

            buttons = [
                {"text": "取消", "style": "secondary", "callback": None, "dismiss": True},
                {"text": "删除选中", "style": "danger", "callback": do_delete_selected, "dismiss": False},
                {"text": action_name, "style": action_style, "callback": do_confirm, "dismiss": True},
            ]
            self._show_dialog(act, title, container, buttons, height_ratio=0.88)
        self._run_on_ui(on_ui)
