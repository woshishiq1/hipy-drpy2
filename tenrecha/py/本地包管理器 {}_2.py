# -*- coding: utf-8 -*-
# @version v6
# @desc    在线转本地 · 本地包管理器（管理中心 / 解密 / 本地 / 设置）
# @update  2026-09-07 修复：配置跨重启丢失(新增目录/接口/改名)、批量开关形态不同步、
#                     改名与代码不同步、按钮随列表滚动、弹窗起始路径定位；
#                     本地接口管理新增「视图/代码/一键删除/注代」；注代可改代理地址；
#                     分类去图标；目录选取添加风格统一；保存一律写回源文件；
#                     配置以本地保存为尊：ext 仅首次启动生效并落盘，
#                     之后改动一律存在本地配置中；删除本地配置后才重新读 ext
# @author  陆小凤

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
# [FIX BUG-14] 安全获取脚本自身路径：exec 注入加载（无 __file__）时为空串，
# 管理站点注入等依赖该路径的功能将自动跳过，而不是抛 NameError
SELF_PATH = os.path.abspath(__file__) if '__file__' in dir() else ''
CACHE_DIR = os.path.join(SCRIPT_DIR, 'cache')

try:
    os.makedirs(CACHE_DIR, exist_ok=True)
    _probe = os.path.join(CACHE_DIR, '.wtest')
    with open(_probe, 'w') as _f:
        _f.write('1')
    os.remove(_probe)
except Exception:
    try:
        import tempfile
        CACHE_DIR = os.path.join(tempfile.gettempdir(), 'zxb_cache')
        os.makedirs(CACHE_DIR, exist_ok=True)
    except Exception:
        CACHE_DIR = os.getcwd()

PERSISTENT_CONFIG_PATH = None

def _is_conn_error(e):

    s_e = (str(e) or "").lower()
    keys = ("nameResolutionError", "failed to resolve", "nodename nor servname",
            "connection refused", "connectionrefused", "timed out",
            "read timed out", "connect timeout", "max retries exceeded",
            "newconnectionerror", "temporary failure in name resolution",
            "no address associated", "name or service not known",
            "network is unreachable", "errno 7", "errno 11001", "errno 11004")
    return any(k in s_e for k in keys)

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

HEAD_FAIL_TTL = 300
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

CONFIG_BACKUP_SUBDIR = "map"

UI_CLICK_DEBOUNCE = 0.20

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
        "hint": "留空则跟随本地包目录的 map 子目录",
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
        "title": "下载设置", "icon": "➤",
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
        "title": "网络设置", "icon": "☁️",
        "remark": "UA / 各类代理 / 备用解密 / 本地服务地址",

        "keys": ["user_agent", "github_proxy", "proxy", "external_api",
                 "file_service", "proxy_port"],
    },
    "naming": {
        "title": "文件命名", "icon": "✒️",
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

    BTN_PRIMARY = '#5B52F5'
    BTN_PRIMARY_DEEP = '#4A41D8'
    BTN_SUCCESS = '#077F48'
    BTN_SUCCESS_DEEP = '#066B3E'
    BTN_DANGER = '#D92D20'
    BTN_DANGER_DEEP = '#B42318'
    BTN_INFO = '#2563EB'
    BTN_INFO_DEEP = '#1D4ED8'

    BTN_WARNING = '#FEF0C7'
    BTN_WARNING_INK = '#A94D08'
    BTN_WARNING_LINE = '#F7DCA8'

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

    TEXT_3 = "#64748B"
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

    _DARK = {
        'BRAND': '#8B83FF', 'BRAND_DEEP': '#6C63FF',
        'BRAND_SOFT': '#241F45', 'BRAND_LINE': '#3B3670',
        'SUCCESS': '#35D399', 'SUCCESS_DEEP': '#12B76A',
        'SUCCESS_SOFT': '#0F2A20', 'SUCCESS_LINE': '#1E5340',
        'WARNING': '#FBBF24', 'WARNING_DEEP': '#F59E0B',
        'WARNING_SOFT': '#2E2410', 'WARNING_LINE': '#5C4A1E',
        'DANGER': '#F97066', 'DANGER_DEEP': '#F04438',
        'DANGER_SOFT': '#2E1614', 'DANGER_LINE': '#66281F',
        'INFO': '#60A5FA', 'INFO_DEEP': '#3B82F6',
        'INFO_SOFT': '#0F1E33', 'INFO_LINE': '#1E3A66',
        'ROW_FOCUS': '#252C3D', 'ROW_ICON': '#8B83FF',
        'BG': '#0D111A', 'SURFACE': '#161C28',
        'SURFACE_ALT': '#1C2331', 'SURFACE_SUNKEN': '#11161F',
        'BORDER': '#28303F', 'BORDER_STRONG': '#3A4457',
        'TEXT': '#E9EEF8', 'TEXT_2': '#A9B4C7', 'TEXT_3': '#8A96AA',
        'WHITE': '#FFFFFF',

        'BTN_PRIMARY': '#8B83FF', 'BTN_PRIMARY_DEEP': '#A5A0FF',
        'BTN_SUCCESS': '#35D399', 'BTN_SUCCESS_DEEP': '#6EE7B7',
        'BTN_DANGER': '#F97066', 'BTN_DANGER_DEEP': '#FCA5A0',
        'BTN_INFO': '#60A5FA', 'BTN_INFO_DEEP': '#93C5FD',
        'BTN_WARNING': '#3A2C10', 'BTN_WARNING_INK': '#FCD34D',
        'BTN_WARNING_LINE': '#5C4A1E',
    }

    _LIGHT = {}
    _mode = 'light'

    @classmethod
    def apply_mode(cls, mode):

        if mode not in ('light', 'dark'):
            return cls._mode
        if not cls._LIGHT:

            for k in cls._DARK:
                if hasattr(cls, k):
                    cls._LIGHT[k] = getattr(cls, k)

        cls._mode = mode
        src = cls._DARK if mode == 'dark' else cls._LIGHT
        for k, v in src.items():
            setattr(cls, k, v)

        cls._rebuild_styles()
        return cls._mode

    @classmethod
    def _rebuild_styles(cls):

        if cls._mode == 'dark':
            ink = '#0D111A'
            cls.STYLES = {
                'primary': (cls.BRAND, ink, cls.BRAND, '#A5A0FF'),
                'success': (cls.SUCCESS, ink, cls.SUCCESS, '#6EE7B7'),
                'danger': (cls.DANGER, ink, cls.DANGER, '#FCA5A0'),
                'warning': (cls.WARNING, ink, cls.WARNING, '#FCD34D'),
                'info': (cls.INFO, ink, cls.INFO, '#93C5FD'),
                'secondary': (cls.SURFACE_SUNKEN, cls.TEXT_2, cls.BORDER, '#202836'),
                'outline': (cls.SURFACE, cls.BRAND, cls.BRAND_LINE, cls.BRAND_SOFT),
                'ghost': (cls.SURFACE, cls.TEXT_2, cls.BORDER, cls.SURFACE_SUNKEN),
                'soft_brand': (cls.BRAND_SOFT, cls.BRAND, cls.BRAND_LINE, '#2E2A58'),
                'soft_danger': (cls.DANGER_SOFT, cls.DANGER, cls.DANGER_LINE, '#3D1C18'),
                'soft_success': (cls.SUCCESS_SOFT, cls.SUCCESS, cls.SUCCESS_LINE, '#14402F'),
            }
            return
        cls.STYLES = {
            'primary': (cls.BTN_PRIMARY, cls.WHITE, cls.BTN_PRIMARY, cls.BTN_PRIMARY_DEEP),
            'success': (cls.BTN_SUCCESS, cls.WHITE, cls.BTN_SUCCESS, cls.BTN_SUCCESS_DEEP),
            'danger': (cls.BTN_DANGER, cls.WHITE, cls.BTN_DANGER, cls.BTN_DANGER_DEEP),
            'info': (cls.BTN_INFO, cls.WHITE, cls.BTN_INFO, cls.BTN_INFO_DEEP),
            'warning': (cls.BTN_WARNING, cls.BTN_WARNING_INK,
                        cls.BTN_WARNING_LINE, '#FDE9B8'),
            'secondary': (cls.SURFACE_SUNKEN, cls.TEXT_2, cls.BORDER, '#E2E8F0'),
            'outline': (cls.SURFACE, cls.BRAND, cls.BRAND_LINE, cls.BRAND_SOFT),
            'ghost': (cls.SURFACE, cls.TEXT_2, cls.BORDER, cls.SURFACE_SUNKEN),
            'soft_brand': (cls.BRAND_SOFT, cls.BRAND, cls.BRAND_LINE, '#E3E0FF'),
            'soft_danger': (cls.DANGER_SOFT, cls.DANGER, cls.DANGER_LINE, '#FCD9D6'),
            'soft_success': (cls.SUCCESS_SOFT, cls.SUCCESS, cls.SUCCESS_LINE, '#CFEEDF'),
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

UITheme.apply_mode('light')

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

        self._pending_dismiss = []

        # [修复] 开关监听器统一登记在 Python 侧字典里。
        # 之前只往 Java view 上挂 `_checked_listener` 属性，部分运行时不允许
        # 给 Java 对象挂自定义属性（赋值被静默吞掉），set_switch_quietly 就
        # 拿不到监听器：摘不掉 -> 批量勾选触发 N 次回调把主线程卡死；
        # 恢复不了 -> 手动点开关直接失灵。这里用 id(sw) 做可靠兜底。
        self._switch_listeners = {}

        if self.kind == "tv":
            self.max_w_dp, self.max_h_dp = 880.0, 660.0
        elif self.kind == "tablet":
            self.max_w_dp, self.max_h_dp = 660.0, 700.0
        else:
            self.max_w_dp, self.max_h_dp = 470.0, 720.0

        self.tv_focus = (self.kind == "tv")

        self.night = self._detect_night(act)
        self.theme_mode = 'auto'
        UITheme.apply_mode('dark' if self.night else 'light')

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

    def _detect_night(self, act):

        try:
            cfg = act.getResources().getConfiguration()
            ui_mode = int(getattr(cfg, 'uiMode', 0) or 0)

            return (ui_mode & 0x30) == 0x20
        except Exception:
            return self.kind == "tv"

    def set_theme(self, mode):

        self.theme_mode = mode if mode in ('auto', 'light', 'dark') else 'auto'
        if self.theme_mode == 'auto':
            UITheme.apply_mode('dark' if self.night else 'light')
        else:
            UITheme.apply_mode(self.theme_mode)
        return UITheme._mode

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

    def card(self, pad=None, bg=None, radius=None, stroke=None, margin=None):

        if pad is None:
            pad = UITheme.S_MD
        if bg is None:
            bg = UITheme.SURFACE
        if radius is None:
            radius = UITheme.R_LG
        if stroke is None:
            stroke = UITheme.BORDER
        if margin is None:
            margin = (0.0, 0.0, 0.0, UITheme.S_SM)
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

    def divider(self, top=0.0, bottom=0.0, color=None, height_dp=1.0):
        TextView = self.j("android.widget.TextView")
        v = TextView(self.act)
        v.setBackgroundColor(self.color(color or UITheme.BORDER))
        v.setLayoutParams(self.lp(-1, self.dp(height_dp), 0.0, (0.0, top, 0.0, bottom)))
        return v

    def text(self, txt, size=None, color=None, bold=False,
             gravity=None, single_line=False, max_lines=0, mono=False,
             line_spacing=1.25, selectable=False, pad=None):

        if size is None:
            size = UITheme.FS_BODY
        if color is None:
            color = UITheme.TEXT
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

                           pad=(3.0 + UITheme.S_SM, UITheme.S_XS, 0.0, 0.0))
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

    def show_keyboard(self, view):

        if view is None:
            return False
        try:
            view.setFocusable(True)
            view.setFocusableInTouchMode(True)
            view.requestFocus()
        except Exception:
            return False

        def _do():
            try:
                imm = self.act.getSystemService("input_method")
                if imm is None:
                    return False
                imm.showSoftInput(view, 1)
                return True
            except Exception:
                return False

        ok = _do()

        try:
            from java import dynamic_proxy
            from java.lang import Runnable

            class _R(dynamic_proxy(Runnable)):
                def __init__(self, cb):
                    super().__init__()
                    self.cb = cb

                def run(self):
                    self.cb()

            r = _R(_do)
            self.sink.append(r)
            view.post(r)
        except Exception:
            pass
        return ok

    def hide_keyboard(self, view=None):

        try:
            imm = self.act.getSystemService("input_method")
            if imm is None:
                return False
            if view is not None:
                return bool(imm.hideSoftInputFromWindow(view.getWindowToken(), 0))
            return bool(imm.hideSoftInputFromWindow(
                self.act.getWindow().getDecorView().getWindowToken(), 0))
        except Exception:
            return False

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
        try:
            self.apply_focus_patch(view)
        except Exception:
            pass
        return view

    def apply_focus_patch(self, view):
        """TV 下补充焦点相关属性，解决遥控器"要点两次"的问题。

        成因：TV 遥控器第一次按下通常只把焦点移到目标，第二次才触发点击。
        当 View 未声明可聚焦、或缺少焦点态背景时，第一次按键会被父容器吞掉，
        用户就会感觉"按了没反应，得再按一次"。
        这里统一补上 focusable + clickable + 无障碍重要性。
        """
        if not self.tv_focus or view is None:
            return view
        try:
            view.setClickable(True)
        except Exception:
            pass
        try:
            view.setLongClickable(False)
        except Exception:
            pass
        try:
            # IMPORTANT_FOR_ACCESSIBILITY_YES：让焦点框架把它当作独立焦点目标
            view.setImportantForAccessibility(1)
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

    def _row_bg(self, idx, zebra=True, radius=None):
        if radius is None:
            radius = UITheme.R_MD
        """列表行背景：斑马纹 + 按下/遥控器焦点高亮。"""
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

        try:
            et.setFocusable(True)
            et.setFocusableInTouchMode(True)
            et.setClickable(True)
        except Exception:
            pass

        try:
            from java import dynamic_proxy
            ViewCls = self.j("android.view.View")

            class _Focus(dynamic_proxy(ViewCls.OnFocusChangeListener)):
                def __init__(self, cb):
                    super().__init__()
                    self.cb = cb

                def onFocusChange(self, v, has_focus):
                    self.cb(v, has_focus)

            def _on_focus(v, has_focus):
                if has_focus:
                    self.show_keyboard(v)

            fl = _Focus(_on_focus)
            self.sink.append(fl)
            et.setOnFocusChangeListener(fl)
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
            _lst = self._on_checked(on_change)
            sw.setOnCheckedChangeListener(_lst)
            # [性能] 保存引用，供 set_switch_quietly 临时摘除/恢复。
            # 批量勾选时若不摘除，N 次 setChecked 会触发 N 次回调，
            # 每次回调都写盘（~600ms），主线程直接卡死、UI 不刷新。
            try:
                sw._checked_listener = _lst
            except Exception:
                pass
            # [修复] 同时登记到 Python 侧字典，避免 Java 对象挂不上属性时失效
            try:
                self._switch_listeners[id(sw)] = _lst
            except Exception:
                pass
        if on_long_click is not None:
            sw.setOnLongClickListener(self._on_long_click(on_long_click))

        self.apply_focus(sw, True)
        if weight:
            sw.setLayoutParams(self.lp(0, -2, float(weight)))
        return sw

    def set_switch_quietly(self, sw, value):
        """设置开关状态，但不触发 onCheckedChanged 回调。

        批量全选/反选/清空时用：否则 40 个开关 = 40 次回调 = 40 次写盘，
        主线程被阻塞十几秒，表现为"点了没反应、开关不更新"。
        """
        if sw is None:
            return False
        # [修复] 优先取 Python 侧登记表（可靠），取不到再退回到 view 上的属性
        lst = None
        try:
            lst = self._switch_listeners.get(id(sw))
        except Exception:
            lst = None
        if lst is None:
            try:
                lst = getattr(sw, "_checked_listener", None)
            except Exception:
                lst = None
        if lst is None:
            try:
                lst = getattr(sw, "_check", None)
            except Exception:
                lst = None
        try:
            sw.setOnCheckedChangeListener(None)
        except Exception:
            pass
        try:
            sw.setChecked(bool(value))
        except Exception:
            pass
        if lst is not None:
            try:
                sw.setOnCheckedChangeListener(lst)
            except Exception:
                pass
        return True

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
                _cb = spec.get("callback")
                if _cb is None and not spec.get("dismiss"):
                    # 没有回调也不关闭 -> 会变成点不动的死按钮，兜底给个空操作
                    # （至少保证 clickable，点击有按压反馈，不会"要点两次"）
                    _cb = lambda: None
                btn = self.button(spec.get("text", ""), style,
                                  _cb, spec.get("dialog_ref"), size)

                if spec.get("dismiss") and not spec.get("dialog_ref"):
                    self._pending_dismiss.append((btn, spec.get("callback")))
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

        for _btn, _cb in getattr(self, "_pending_dismiss", []):
            try:
                _btn.setOnClickListener(self._on_click(_cb, holder))
                self.apply_focus(_btn, True)
            except Exception:
                pass
        self._pending_dismiss = []

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

            try:
                window.setSoftInputMode(16)
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

    HOST_DEAD_THRESHOLD = 2
    HOST_DEAD_TTL = 300.0

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

        self._host_dead = {}
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

        try:
            self._quick_session.headers.update(self.session.headers)
            self._quick_session.verify = self.session.verify
            if getattr(self, 'proxy', ''):
                self._quick_session.proxies = {'http': self.proxy,
                                               'https': self.proxy}
        except Exception:
            pass
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
        _rec = self._head_fail_hosts.get(host)
        if _rec is not None:
            _cnt = _rec[0]
            _ts = _rec[1] if len(_rec) > 1 else 0.0

            if time.time() - _ts > HEAD_FAIL_TTL:
                self._head_fail_hosts.pop(host, None)
            elif _cnt >= HEAD_FAIL_THRESHOLD:
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
            self._head_fail_hosts[host] = [
                self._head_fail_hosts.get(host, [0, 0.0])[0] + 1,
                time.time()]
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

        target = self._github_inner_url(url)
        if not target:
            u2 = self._unwrap_foreign_proxy(url)
            if u2 and u2 != url:
                target = u2
        if self._is_proxied(url):
            d = self._direct_url(url)
            if d and d != url:
                target = target or d
        if not target:
            target = url

        if (self.github_proxy and target and not self._proxy_blown()
                and self._is_github_file_url(target)):
            p = self._proxy_prefix() + target
            if p != url:
                alts.append(p)

        if target != url:
            alts.append(target)

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

    def normalize_github_url(self, url, keep_own_proxy=False):

        if keep_own_proxy and url and self.github_proxy:
            _pp = str(self.github_proxy).rstrip('/') + '/'
            if url.startswith(_pp):
                return url

        if not url:
            return url

        if self.github_proxy:
            proxy_prefix = self.github_proxy.rstrip('/') + '/'
            if url.startswith(proxy_prefix) and not keep_own_proxy:
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

        if (self._is_github_file_url(url) and self.github_proxy
                and not self._proxy_blown() and not keep_own_proxy):
            _pp = self.github_proxy.rstrip('/') + '/'
            if not url.startswith(_pp):
                url = _pp + url
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

    def _host_of(self, url):

        try:
            return (urllib.parse.urlparse(str(url or "")).netloc or "").lower()
        except Exception:
            return ""

    def _note_host_unreachable(self, url):

        host = self._host_of(url)
        if not host:
            return
        cnt = self._host_dead.get(host, [0, 0.0])[0] + 1
        self._host_dead[host] = [cnt, time.time()]
        if cnt == self.HOST_DEAD_THRESHOLD:
            self._log(f"⚠️ 主机 {host} 连续 {cnt} 次连不上，"
                      f"后续该文件下的其它文件直接跳过（不再逐个重试）",
                      level='warn')

    def _host_dead_now(self, url):

        host = self._host_of(url)
        if not host:
            return False
        rec = self._host_dead.get(host)
        if not rec:
            return False
        cnt, ts = rec[0], rec[1]
        if cnt < self.HOST_DEAD_THRESHOLD:
            return False

        if time.time() - ts > self.HOST_DEAD_TTL:
            self._host_dead.pop(host, None)
            return False
        return True

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

        if not url_clean.lower().startswith(('http://', 'https://')):
            if re.search(r'[\[\]()*+|^$\\{}]', url_clean):
                self._log("跳过：含正则/模板字符，不是文件 → %s"
                          % (url_clean[:40],), level='debug')
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

    def resolve_url(self, rel_path, base_url, keep_own_proxy=False):
        if not rel_path:
            return None
        if isinstance(rel_path, str):
            rel_path = rel_path.strip()
        _n = lambda u: self.normalize_github_url(u, keep_own_proxy=keep_own_proxy)
        if rel_path.startswith(('http://', 'https://')):
            return _n(rel_path)
        if rel_path.startswith("//"):
            return _n("https:" + rel_path)
        if rel_path.startswith("./") or rel_path.startswith("../"):
            return _n(safe_urljoin(base_url, rel_path))
        if rel_path.startswith("/"):
            parsed = urllib.parse.urlparse(base_url)
            return _n(f"{parsed.scheme}://{parsed.netloc}{rel_path}")
        return _n(safe_urljoin(base_url, rel_path))

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

        if self._host_dead_now(url):
            self._log(f"⏭️ 跳过（主机 {self._host_of(url)} 此前连不上）: {url}",
                      level='debug')
            with self._lock:
                self.failed.append(
                    (url, "主机连不上（同主机已有文件失败，跳过重试）"))
                self._processed.discard(url_part)
            return None
        if not self.is_downloadable(url_part, field_key):
            return None
        should_skip, reason = self.should_skip(url_part)
        if should_skip:
            with self._lock:
                self.skipped.append((url, reason))
            self._log(f"跳过文件: {url} ({reason})", level='debug')
            return None
        abs_url = self.resolve_url(url_part, base_url,
                                   keep_own_proxy=bool(_direct_only))
        if not abs_url:
            with self._lock:
                self.failed.append((url, "无法解析URL"))
            return None

        abs_url = self._apply_proxy_policy(abs_url)

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
        if os.path.exists(target_abs):
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

            if not force_full and not self.overwrite:
                if total_size <= 0 or local_size == total_size:
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

                with self._lock:
                    self.failed = [x for x in self.failed if x[0] != url]
                _record_failure(
                    "耗时超过 %d 秒上限，放弃（含所有备用地址）"
                    % self.max_download_seconds)
                # [FIX BUG-01] 超时必须立即放弃：继续执行会把读超时钳到 1 秒
                # 后仍然发起请求，导致耗时上限失效，且该 URL 同时残留于
                # failed 与 downloaded 两个列表，污染统计与"失败清单"
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

            if _is_conn_error(e):
                self._note_host_unreachable(abs_url)

            if time.time() >= _deadline:
                with self._lock:
                    self.failed = [x for x in self.failed if x[0] != url]
                _record_failure(
                    "耗时超过 %d 秒上限，放弃（含所有备用地址）"
                    % self.max_download_seconds)
                return None
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

        if self._host_dead_now(url):
            self._log(f"⏭️ 跳过（主机 {self._host_of(url)} 此前连不上）: {url}",
                      level='debug')
            with self._lock:
                self.failed.append(
                    (url, "主机连不上（同主机已有文件失败，跳过重试）"))
                self._processed.discard(url_part)
            return None
        full_url = self.resolve_url(url_part, base_url,
                                    keep_own_proxy=bool(_direct_only))
        if not full_url:
            return None

        full_url = self._apply_proxy_policy(full_url)

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

                    try:
                        content = raw.decode('gb18030')
                    except (UnicodeDecodeError, LookupError):

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

            if _is_conn_error(e):
                self._note_host_unreachable(full_url)
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

    timeout_read = _cfg_prop('download.timeout_read', 60)

    log_enabled = _cfg_prop('log.enabled', True)
    log_level = _cfg_prop('log.level', LOG_LEVEL_DEFAULT)
    log_dir = _cfg_prop('log.dir', None)

    user_agent = _cfg_prop('user_agent', DEFAULT_USER_AGENT)
    external_api_url = _cfg_prop('external_api_url', DEFAULT_EXTERNAL_API_URL)
    download_output_dir = _cfg_prop('download_output_dir', '')
    tv_mode = _cfg_prop('tv_mode', None)

    ui_theme = _cfg_prop('ui_theme', None)
    root_dirs = _cfg_prop('root_dirs', [])
    scan_local_dirs = _cfg_prop('scan_local_dirs', [])
    scan_local_extensions = _cfg_prop('scan_local_extensions', ['.py'])
    scan_dir_exts = _cfg_prop('scan_dir_exts', {})
    fav_history = _cfg_prop('fav_history', [])
    scan_custom_exts = _cfg_prop('scan_custom_exts', [])
    scan_dir_names = _cfg_prop('scan_dir_names', {})

    scan_output_mode = _cfg_prop('scan_output_mode', 'merged')
    scan_output_name = _cfg_prop('scan_output_name', '我的影视')
    localized_interfaces = _cfg_prop('localized_interfaces', [])
    favorite_fragments = _cfg_prop('favorite_fragments', [])
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
        self._config_resolved_path = None
        self._last_loaded_path = None
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
        self.scan_local_extensions = list(self.SCAN_DEFAULT_ON)
        self.scan_dir_exts = {}
        self.fav_history = []
        self.scan_custom_exts = []
        self.scan_dir_names = {}
        self.scan_output_mode = 'merged'
        self.scan_output_name = '我的影视'
        self.favorite_fragments = []
        self._load_favorite_fragments()
        self._original_oktv_url = None

        self._pending_notice = None

        self.decrypt_filename_template = "{name}_m.json"
        self.localized_filename_template = "{name}.json"
        self.inject_manager_site = True
        self.oktv_switch_timeout = 2
        self.tv_mode = None
        self.ui_theme = None
        self._fs_root_prefix = None

    def _is_under_local_package(self, path):
        """该路径是否位于「本地包下载目录」内。

        [规则] 接口目录管理 / 本地爬虫程序管理 里新增的目录只用于扫描文件，
        不保存配置、不生成接口代码。配置与产物永远只按
        「本地包下载目录」+「配置备份目录」两个设定目录走。
        """
        try:
            ap = os.path.abspath(str(path or ""))
        except Exception:
            return False
        base = str(getattr(self, 'download_output_dir', '') or '').strip()
        if not base:
            return False
        try:
            bp = os.path.abspath(base)
        except Exception:
            return False
        return ap == bp or ap.startswith(bp + os.sep)

    def _ensure_default_scan_dir(self):

        if self.scan_local_dirs or not self.download_output_dir:
            return
        default_dir = self.download_output_dir
        if default_dir not in self.scan_local_dirs:
            self.scan_local_dirs.append(default_dir)

            self._auto_scan_dir = default_dir
            try:
                os.makedirs(default_dir, exist_ok=True)
            except Exception:
                pass
            self._log("设置默认扫描目录: {}".format(default_dir))

    def _refresh_auto_scan_dir(self):

        auto = getattr(self, "_auto_scan_dir", None)
        real = (getattr(self, "download_output_dir", None) or "").strip()
        if not auto or not real or auto == real:
            return
        try:
            self.scan_local_dirs = [real if d == auto else d
                                    for d in self.scan_local_dirs]
            self._auto_scan_dir = real
            self._log("扫描目录已纠正为下载目录: {}".format(real))
        except Exception:
            pass

    def _load_root_dirs(self):
        try:
            if os.path.exists(PERSISTENT_CONFIG_PATH):
                with open(PERSISTENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                data = self._normalize_config_keys(data)
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

    def _is_remote_path(self, path):
        if not path:
            return False
        return str(path).lower().startswith(('http://', 'https://', 'ftp://'))

    def _get_base_dir(self):
        return self._base_dir or SCRIPT_DIR

    def _detect_base_dir(self, ext):

        if self._base_dir:
            return self._base_dir
        self._base_dir = SCRIPT_DIR
        self._log("基础目录 = 脚本目录: " + SCRIPT_DIR)
        return self._base_dir

    def _resolve_file_path(self, path, base_dirs=None):

        if not path or self._is_remote_path(path):
            return None, None

        if os.path.isabs(path):
            if os.path.exists(path):
                return path, os.path.dirname(path)
            return None, None

        basename = os.path.basename(path)
        strip = path.lstrip('./').lstrip('.\\')
        strip_parent = os.path.dirname(strip)

        candidates = []
        for b in [self._get_base_dir(), SCRIPT_DIR, os.getcwd()]:
            if b:
                candidates.append(os.path.join(b, strip))
                candidates.append(os.path.join(b, basename))
                if strip_parent:
                    candidates.append(os.path.join(b, strip_parent, basename))

        seen = set()
        for cand in candidates:
            if not cand or cand in seen:
                continue
            seen.add(cand)
            if not os.path.exists(cand):
                continue
            cand_dir = os.path.dirname(cand)
            if strip_parent and strip_parent != '.':
                tail = strip_parent.replace('/', os.sep).replace('\\', os.sep)
                inferred_base = (cand_dir[:-len(tail)].rstrip('/\\') or '/'
                                 if cand_dir.endswith(tail) else cand_dir)
            else:
                inferred_base = cand_dir
            return cand, inferred_base

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
                self._last_loaded_path = cand
                return data
            except json.JSONDecodeError as e:
                last_err = e

                try:
                    data = json.loads(
                        self._clean_json_comments(_read_text_file(cand)))
                    self._last_loaded_path = cand
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
        data = self._load_json_resource(path, allow_decrypt=False)
        if data is not None:
            self._config_resolved_path = self._last_loaded_path
        return data

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

        seen = set()
        for p in candidates:
            if not p or p in seen:
                continue
            seen.add(p)
            if os.path.exists(p):
                try:
                    data = json.loads(_read_text_file(p))
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

            self._log_dropped = getattr(self, '_log_dropped', 0) + 1
            if self._log_dropped in (1, 100):
                try:
                    self._log(
                        f"⚠️ 日志写入积压，已丢弃 {self._log_dropped} 条"
                        f"（队列上限 {LOG_FILE_QUEUE_MAXSIZE}）",
                        level='warn')
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

        try:
            kit.set_theme(getattr(self, "ui_theme", None) or "auto")
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

    def _ui_theme_text(self):

        val = getattr(self, "ui_theme", None)
        if val == "dark":
            return "强制深色"
        if val == "light":
            return "强制亮色"
        return "跟随系统"

    def _open_ui_theme_dialog(self):

        def on_ui(act):
            kit = self._kit(act)
            spider = self

            _tv = getattr(spider, "ui_theme", None)
            cur_auto = _tv is None or str(_tv).strip().lower() == "auto"
            cur_dark = (str(_tv).strip().lower() == "dark")

            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))
            box.addView(kit.hint(
                "深色模式为电视与夜间环境重新配了一套颜色："
                "底色调暗、按钮改为亮底深字（对比度 6.1～11.3:1，达 WCAG AA）。"
                "\n关闭「跟随系统」后可手动强制亮色或深色。"),
                kit.lp(-1, -2))

            dark_state = {}
            box.addView(kit.switch_card(
                "深色模式",
                "开启：暗色背景 + 亮底深字按钮；关闭：常规亮色界面",
                cur_dark, None, state_out=dark_state,
            ), kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))

            auto_state = {}
            box.addView(kit.switch_card(
                "跟随系统自动判断",
                "开启：按系统夜间模式自动切换；关闭：使用上面的手动值",
                cur_auto, None, state_out=auto_state,
            ), kit.lp(-1, -2))

            def save():
                auto = bool(auto_state["switch"].isChecked())
                manual_dark = bool(dark_state["switch"].isChecked())
                spider.ui_theme = None if auto else ("dark" if manual_dark else "light")
                spider._save_config_to_file()

                try:
                    kit.set_theme(spider.ui_theme or "auto")
                except Exception:
                    pass
                kit.toast("深色模式：{}".format(spider._ui_theme_text()))

            buttons = [
                {"text": "取消", "style": "secondary", "callback": None, "dismiss": True},
                {"text": "保存", "style": "primary", "callback": save, "dismiss": True},
            ]
            self._show_dialog(act, "🎨 深色模式", box, buttons, height_ratio=0)
        self._run_on_ui(on_ui)

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

            # [FIX BUG-17] 收紧"复制"按钮的显示条件：
            # 仅 URL 前缀 / 含 "://" / 含路径特征（/段/段）时显示，
            # 避免普通提示文本（如"成功/失败 18/20"）误挂复制按钮
            if isinstance(message, str) and len(message) > 10 and (
                    message.startswith(("http://", "https://", "file://"))
                    or "://" in message
                    or re.search(r'(?<!\w)/[\w.\-]+/[\w.\-]+', message)):
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

    def _browser_start_vpath(self, start_real, prefix):
        """真实路径 -> 文件浏览起始虚拟路径。

        [修复] 原来直接 `_fs_rel(start_dir)`，当输入路径不在文件服务根目录下时
        会拼出 prefix + 完整绝对路径 这种错位路径，等于"没定位到输入的地方"。
        现在：优先精确定位；取不到就上溯到服务根内最近的祖先；
        完全没有交集时退化成按绝对路径列举（本地兜底）。
        """
        try:
            p = os.path.abspath(str(start_real or ""))
        except Exception:
            p = ""
        pv = str(prefix or "").rstrip("/")
        if p and pv and (p == pv or p.startswith(pv + "/")):
            return self._fs_vpath(p[len(pv):] or "/"), pv
        cur = p
        for _i in range(16):
            cur = os.path.dirname(cur)
            if not cur or cur in ("/", os.sep):
                break
            if cur == pv or (pv and cur.startswith(pv + "/")):
                return self._fs_vpath(cur[len(pv):] or "/"), pv
        if p and os.path.isdir(p):
            return self._fs_vpath(p), ""
        return "/", pv

    def _browser_pick_start(self, typed, fallbacks=()):
        """把输入框里的路径整理成可直接定位的目录（支持文件取父目录 / 相对路径）"""
        v = str(typed or "").strip().strip('"').strip("'")
        if not v:
            v = ""
        else:
            try:
                v = os.path.abspath(os.path.expanduser(v))
            except Exception:
                v = ""
            if v and os.path.isfile(v):
                v = os.path.dirname(v)
            if v and not os.path.isdir(v):
                v = ""
        if v:
            return v
        for d in (fallbacks or ()):
            try:
                if d and os.path.isdir(str(d)):
                    return os.path.abspath(str(d))
            except Exception:
                continue
        return ""

    def _show_file_browser(self, title, start_dir, mode="dir", on_pick=None,
                           name_filter=None, manual_title=None, placeholder=None):

        dlg = {"dialog": None}

        def on_ui(act):
            kit = self._kit(act)

            prefix = self._fs_service_prefix()
            _sv, _sp = self._browser_start_vpath(start_dir, prefix)
            state = {
                "vpath": _sv,
                "prefix": _sp if _sp else prefix,
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
            # [要求] 优先落在当前值（或它最近的存在的父目录），少做无谓翻找
            v = self._browser_pick_start(current_value, ())
            if v:
                return v
            for p in (getattr(self, "download_output_dir", ""),
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

    def _dismiss_all_dialogs(self):
        """关闭当前所有弹窗（跳转前调用），逆序关闭避免栈错位"""
        refs = list(getattr(self, "_dialog_refs", None) or [])
        for d in reversed(refs):
            try:
                d.dismiss()
            except Exception:
                pass
        try:
            self._dialog_refs = []
        except Exception:
            pass
        return len(refs)

    def _show_dialog(self, act, title, content, buttons, width_ratio=0.92, height_ratio=0.85,
                     back_callback=None, on_show=None, scroll=True):

        spider = self
        kit = self._kit(act)

        # [FIX BUG-06] 对话框关闭时从 _dialog_refs 移除自身，
        # 保证 nested 判断（UI 去抖）与 _dialog_refs[-1].dismiss() 的语义正确
        def _on_dlg_dismiss():
            try:
                if dialog in spider._dialog_refs:
                    spider._dialog_refs.remove(dialog)
            except Exception:
                pass
            setattr(spider, "_ui_busy", False)

        dialog = kit.dialog(
            title=title,
            content=content,
            buttons=buttons,
            width_ratio=width_ratio,
            height_ratio=height_ratio,
            back_callback=back_callback,
            scroll=scroll,
            on_dismiss=_on_dlg_dismiss,
        )
        self._dialog_refs.append(dialog)
        dialog.show()
        if on_show:
            try:
                on_show()
            except Exception:
                pass
        return dialog

    def _ui_site_card(self, kit, name, subtitle, checked, on_toggle, actions, dim=False,
                      per_row=None, show_switch=True, state_out=None):

        G = kit.gravity()
        card = kit.card(pad=(UITheme.S_MD, UITheme.S_SM, UITheme.S_MD, UITheme.S_SM))

        row = kit.hbox()
        row.setLayoutParams(kit.lp(-1, -2))
        if G:
            row.setGravity(G.CENTER_VERTICAL)

        sw = None
        if show_switch:
            sw = kit.toggle("", bool(checked), on_toggle, weight=0.0)
            row.addView(sw)

        # 供批量勾选时直接改开关，避免整表重建造成抖动
        try:
            card._switch = sw
        except Exception:
            pass
        # [修复] 同步交给 Python 侧 state_out：
        # 给 Java view 挂自定义属性在部分运行时会被静默丢弃，
        # 批量勾选时就拿不到开关引用 —— 表现是"后台全选了、开关形态没变"
        if isinstance(state_out, dict):
            state_out["switch"] = sw
            state_out["card"] = card

        info = kit.vbox(pad=(UITheme.S_SM, 0.0, 0.0, 0.0))
        info.setLayoutParams(kit.lp(0, -2, 1.0))
        _title = kit.text(name, size=UITheme.FS_BODY_LG,
                          color=UITheme.TEXT_3 if dim else UITheme.TEXT,
                          bold=not dim, max_lines=2)
        info.addView(_title, kit.lp(-1, -2))
        # [同步] 批量勾选后要同步标题的"变灰"状态，否则开关变了字还是灰的
        try:
            card._title_view = _title
        except Exception:
            pass
        if isinstance(state_out, dict):
            state_out["title"] = _title
        if subtitle:
            info.addView(kit.text(subtitle, size=UITheme.FS_CAPTION, color=UITheme.TEXT_3,
                                  max_lines=2,
                                  pad=(0.0, UITheme.S_XXS, 0.0, 0.0)), kit.lp(-1, -2))
        row.addView(info)
        card.addView(row, kit.lp(-1, -2))

        if actions:
            card.addView(kit.divider(top=UITheme.S_SM, bottom=UITheme.S_SM))
            bar = kit.button_bar(actions, size="sm", per_row=per_row)
            if bar is not None:
                card.addView(bar, kit.lp(-1, -2))
        return card

    def _ui_dir_card(self, kit, index, path, checked, actions=None, state_out=None):

        G = kit.gravity()
        card = kit.card(pad=(UITheme.S_MD, UITheme.S_SM, UITheme.S_MD, UITheme.S_SM))

        row = kit.hbox()
        row.setLayoutParams(kit.lp(-1, -2))
        if G:
            row.setGravity(G.CENTER_VERTICAL)

        sw = kit.toggle("", bool(checked), None, None, weight=0.0)
        row.addView(sw)
        if isinstance(state_out, dict):
            state_out["switch"] = sw

        info = kit.vbox(pad=(UITheme.S_SM, 0.0, 0.0, 0.0))
        info.setLayoutParams(kit.lp(0, -2, 1.0))
        if index is not None:
            info.addView(kit.text("#{}".format(index), size=UITheme.FS_CAPTION,
                                  color=UITheme.TEXT_3), kit.lp(-1, -2))

        info.addView(kit.text(str(path or ""), size=UITheme.FS_BODY,
                              color=UITheme.TEXT, mono=True,
                              selectable=True), kit.lp(-1, -2))
        row.addView(info)
        card.addView(row, kit.lp(-1, -2))

        if actions:
            card.addView(kit.divider(top=UITheme.S_SM, bottom=UITheme.S_SM))
            bar = kit.button_bar(actions, size="sm")
            if bar is not None:
                card.addView(bar, kit.lp(-1, -2))
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
                if not self.alive:
                    return
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
        # [FIX BUG-05] 不再清空 _ui_listeners/_active_views：
        # 它们持有其他已打开对话框的动态代理强引用（防 Java GC 回收回调），
        # 无差别清空会让运行中的对话框按钮失效。泄漏量级可控，交由引用自然累积。

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
                # [FIX BUG-06] 日志面板关闭时同样从 _dialog_refs 移除自身
                try:
                    if dialog in spider._dialog_refs:
                        spider._dialog_refs.remove(dialog)
                except Exception:
                    pass
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
            "ui_theme": "深色模式",
            "root_dirs": "根目录",
            "scan_local_dirs": "扫描目录",
            "scan_local_extensions": "扫描文件类型",
            "scan_dir_exts": "各目录扫描文件类型",
            "fav_history": "改装接口生成历史",
            "scan_custom_exts": "自定义扫描扩展名",
            "scan_dir_names": "各目录输出名称",
            "scan_output_mode": "扫描输出模式",
            "scan_output_name": "扫描输出名称",
            "favorite_fragments": "收藏片段",
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

        _new_cfg_file = config.get('config_file') or self.config.get('config_file')
        if _new_cfg_file:
            self._config_file_path = _new_cfg_file

        self._load_root_dirs()
        self._ensure_default_scan_dir()
        self._load_localized_interfaces()
        self._load_favorite_fragments()
        self._load_site_states()

    def _to_ext_config_url(self, path):

        v = str(path or "").strip()
        if not v:
            return v
        low = v.lower()
        for sch in ("file://", "http://", "https://"):
            if low.startswith(sch):
                return v

        if len(v) > 2 and v[0].isalpha() and v[1] == ":":
            return v

        if not os.path.isabs(v):
            try:
                resolved = self._resolve_file_path(v)
                if resolved and resolved[0]:
                    v = resolved[0]
                else:
                    v = os.path.abspath(v)
            except Exception:
                v = os.path.abspath(v)
        return "file://" + v

    def _manager_script_url(self, config_file_url=None):
        """管理入口的 api 地址：与 ext.config_file 用同一套拼接逻辑。

        config_file 若走影视TV文件服务（http://127.0.0.1:port/file/xxx/down_config.json），
        则 api 取同目录下的脚本文件；否则退化为 file:// + 脚本绝对路径。
        """
        if not SELF_PATH:
            return ""
        cf = config_file_url
        if cf is None:
            try:
                cf = self._to_ext_config_url(self._manager_config_file())
            except Exception:
                cf = ""
        cf = str(cf or "").strip()
        low = cf.lower()
        if low.startswith(("http://", "https://")):
            try:
                head, _sep, tail = cf.rpartition("/")
                if head:
                    # [要求] 目录部分原样沿用 config_file，脚本名保持明文。
                    # 目标形态：
                    #   http://127.0.0.1:9978/file/123%E4%BA%91%E7%9B%98/
                    #   %E8%BD%AC%E6%9C%AC%E5%9C%B0%E5%8C%85/在线转本地@v4[内测].py
                    # 即"与 config_file 同一目录"，脚本名不做 percent 编码。
                    return head + "/" + os.path.basename(SELF_PATH)
            except Exception:
                pass
        return "file://" + SELF_PATH

    def _manager_config_file(self):

        real = (getattr(self, "_config_file_path", None) or "").strip()
        if real:
            return real
        cands = []
        try:
            for d in self._config_backup_dirs():
                cands.append(os.path.join(d, "down_config.json"))
        except Exception:
            pass
        out = (getattr(self, "download_output_dir", None) or "").strip()
        if out:
            cands.append(os.path.join(os.path.dirname(os.path.abspath(out)),
                                      "down_config.json"))
            cands.append(os.path.join(out, "down_config.json"))

        def _rank(c):
            try:
                return 1 if os.path.abspath(c).startswith(os.path.abspath(SCRIPT_DIR)) else 0
            except Exception:
                return 0
        cands.sort(key=_rank)
        for c in cands:
            try:
                if os.path.isfile(c):
                    return c
            except Exception:
                continue
        return cands[0] if cands else os.path.join(
            getattr(self, "download_output_dir", "") or SCRIPT_DIR, "down_config.json")

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

            "concurrent": (self.config.get('concurrent')
                           if self.config.get('concurrent') is not None
                           else self.download_config.get('concurrent', 3)),
            "user_agent": getattr(self, 'user_agent', DEFAULT_USER_AGENT),
            "external_api_url": getattr(self, 'external_api_url', DEFAULT_EXTERNAL_API_URL),
            "log": {
                "enabled": getattr(self, 'log_enabled', True),
                "level": getattr(self, 'log_level', 'info'),
                "dir": getattr(self, 'log_dir', os.path.join(self.download_output_dir, 'log'))
            },
            "localized_interfaces": self.localized_interfaces,
            "favorite_fragments": getattr(self, "favorite_fragments", []),
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

            "ui_theme": getattr(self, "ui_theme", None),

            "doctor_checks": self.config.get("doctor_checks"),
            "config_backup_dir": getattr(self, "config_backup_dir", ""),

            "config_file": getattr(self, "_config_file_path", None),
        }
        # 用户主动删除的条目登记表（避免被外部配置文件合并回来）
        try:
            _dead = self.config.get(self.PERSIST_DELETED_KEY)
            if _dead:
                config[self.PERSIST_DELETED_KEY] = _dead
        except Exception:
            pass
        if include_runtime:
            config.update({
                "original_oktv_url": self._original_oktv_url,
                "scan_local_dirs": self.scan_local_dirs,
                "scan_local_extensions": self.scan_local_extensions,
                "scan_dir_exts": getattr(self, "scan_dir_exts", {}),
                "fav_history": getattr(self, "fav_history", []),
                "scan_custom_exts": getattr(self, "scan_custom_exts", []),
                "scan_dir_names": getattr(self, "scan_dir_names", {}),
                "scan_output_mode": getattr(self, "scan_output_mode", "merged"),
                "scan_output_name": getattr(self, "scan_output_name", "我的影视"),
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

    def _save_config_to_file(self, path=None, mirror=True):

        if path is None:
            path = os.path.join(_cache_root, 'config.json')
        ok = True
        with self._config_io_lock:
            try:
                self._write_json_atomic(path, self._snapshot_config())
            except Exception as e:
                self._log(f"保存配置失败: {e}", level='error')
                ok = False
        if ok:
            # [修复] 默认强制镜像到「配置备份目录」，不再受节流限制。
            # 原来 30s 节流会让备份目录里的配置长期停留在旧版本，
            # 用户清缓存后从备份恢复时拿到的是过期数据。
            self._save_persistent_config(mirror=mirror)

        return ok
    def _save_persistent_config(self, mirror=True):
        with self._config_io_lock:
            try:
                snapshot = self._snapshot_config(include_runtime=True)
                self._write_json_atomic(PERSISTENT_CONFIG_PATH, snapshot)
                self._log(f"配置已持久化: {PERSISTENT_CONFIG_PATH}", level='debug')
            except Exception as e:
                self._log(f"持久化配置失败: {e}", level='error')
                snapshot = None

        if snapshot is not None and mirror:
            # [性能] 镜像丢到后台线程：不阻塞 UI，同时备份目录仍能及时更新。
            # 真正需要同步落盘的关键节点（生成接口、清除缓存）会显式
            # 调用 _force_mirror_now() 走同步分支。
            self._mirror_config_to_backup(snapshot, background=True)
        
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
        # [修复] map 只是接口产物的中转目录，不是配置备份目录。
        # 之前把它当成备份目录，导致配置被写成两份（down_config.json 之外
        # 又多一个 map/persistent_config.json），清理时容易漏删、恢复时拿到旧值。
        if not dirs:
            try:
                add(os.path.join(SCRIPT_DIR, CONFIG_BACKUP_SUBDIR))
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

        # 兼容读取历史遗留位置（只读取，不创建，避免重新散落 map）
        for default_out in (DEFAULT_DOWNLOAD_DIR, os.path.join(SCRIPT_DIR, "本地包")):
            try:
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

            self._recovered_from_backup = True
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

                        pkg = raw.get('接口列表')
                        if not isinstance(pkg, list):
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
                "文件：{}\n时间：{}\n接口数：{}".format(
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
                        kit.toast("已改名为 {}".format(new), long=True)
                        refresh()
                    except Exception as e:
                        kit.toast("改名失败: {}".format(e), long=True)
                self._show_modern_input("改名备份", "输入新的文件名",
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
                {"text": "✏️ 改名", "style": "secondary",
                 "callback": do_rename, "dismiss": False},
                {"text": "🗑 删除", "style": "danger",
                 "callback": do_delete, "dismiss": False},
                {"text": "关闭", "style": "ghost",
                 "callback": None, "dismiss": True},
            ], size="md"), kit.lp(-1, -2, 0.0, (0.0, UITheme.S_MD, 0.0, 0.0)))
            self._show_dialog(act, "备份操作", box, [], height_ratio=0)

        self._run_on_ui(on_ui)

    _MIRROR_MIN_INTERVAL = 30.0

    def _mirror_config_to_backup(self, data, force=False, background=False):
        """把配置镜像到备份目录。

        [性能] 镜像一次约 400ms（要读写整份 down_config.json）。
        在 UI 线程同步做会把界面卡住，所以普通调用默认丢到后台线程：
        既不阻塞交互，又能让备份目录及时更新（不再靠 30s 节流跳过）。
        关键节点（生成接口、清除缓存）用 force=True 同步执行，确保落盘。
        """
        if background and not force:
            # 后台合并镜像：把多次改动合并成一次写盘。
            # 不用"节流跳过"，否则刚启动那几秒内的改动会被丢掉、备份不及时；
            # 也不用"每次都写"，否则高频操作会排队堆积。
            # 做法是只保留最新快照，由单个 worker 落地 —— 最后一次一定写。
            import threading as _th
            lock = getattr(self, "_mirror_state_lock", None)
            if lock is None:
                lock = _th.Lock()
                self._mirror_state_lock = lock
            with lock:
                self._mirror_pending = data
                t = getattr(self, "_mirror_thread", None)
                if t is not None and t.is_alive():
                    return True      # worker 在跑，它会取到最新快照

            def _worker():
                while True:
                    with lock:
                        cur = getattr(self, "_mirror_pending", None)
                        self._mirror_pending = None
                    if cur is None:
                        return
                    try:
                        self._do_mirror_config_to_backup(cur, False)
                    except Exception:
                        pass
            try:
                t2 = _th.Thread(target=_worker)
                t2.daemon = True
                self._mirror_thread = t2
                t2.start()
                return True
            except Exception:
                pass
        return self._do_mirror_config_to_backup(data, force)

    def _do_mirror_config_to_backup(self, data, force=False):

        import time as _t
        _now = _t.time()
        # force 走同步分支，必须写；普通调用已由后台合并队列限流，这里不再跳过
        if not force and self._MIRROR_MIN_INTERVAL and (
                _now - getattr(self, "_last_mirror_ts", 0.0)) < 0.05:
            return False
        self._last_mirror_ts = _now

        wrote = 0
        # [修复] 扫描类配置（扩展名 / 目录类型 / 目录名称 / 历史记录）
        # 以用户可读的 down_config.json 形式同步落在「配置备份目录」，
        # 方便直接查看与手工备份；内容与其他配置快照一致。
        # [性能] 只在强制镜像时做（省一次整文件读+写），普通节流镜像跳过。
        if force:
          try:
            for _bd in self._config_backup_dirs():
                _p = os.path.join(_bd, CONFIG_BACKUP_NAME)
                if os.path.isfile(_p):
                    try:
                        _cur = json.load(open(_p, 'r', encoding='utf-8'))
                    except Exception:
                        _cur = {}
                    if isinstance(_cur, dict):
                        _cn = self._to_display_keys(data)
                        for _k in ("自定义扫描扩展名", "各目录扫描文件类型",
                                   "各目录输出名称", "改装接口生成历史",
                                   "扫描文件类型", "扫描输出模式", "扫描输出名称"):
                            if _k in _cn:
                                _cur[_k] = _cn[_k]
                        self._write_json_atomic(_p, _cur)
                        break
          except Exception:
            pass

        for d in self._config_backup_dirs():
            path = os.path.join(d, CONFIG_BACKUP_NAME)
            try:
                os.makedirs(d, exist_ok=True)

                self._write_json_atomic(path, data)
                wrote += 1
            except Exception as e:
                self._log(f"写配置备份失败（不影响主配置）{path}: {e}", level='debug')
        return wrote > 0

    # 列表型配置：init 合并时不能"外部全量覆盖"，否则运行期新增的条目会丢
    LIST_MERGE_KEYS = ('sources', 'root_dirs', 'scan_local_dirs',
                       'localized_interfaces', 'scan_custom_exts')

    PERSIST_DELETED_KEY = 'deleted_config_items'
    PERSIST_DELETED_LIMIT = 200

    def _persist_ident(self, key, item):
        """条目判重标识：同一条数据在不同来源里认作一条"""
        try:
            if key == 'sources':
                if isinstance(item, dict):
                    return str(item.get('url') or '').strip().lower()
                return str(item).strip().lower()
            if key == 'localized_interfaces':
                if isinstance(item, dict):
                    return "{}/{}".format(
                        str(item.get('parent_dir') or '').strip().rstrip('/'),
                        str(item.get('dir_name') or '').strip())
            return str(item or '').strip()
        except Exception:
            return ""

    def _persist_deleted_idents(self, key):
        try:
            d = self.config.get(self.PERSIST_DELETED_KEY)
            if isinstance(d, dict):
                return [str(x) for x in (d.get(key) or [])]
        except Exception:
            pass
        return []

    def _persist_mark_deleted(self, key, ident):
        ident = str(ident or "").strip()
        if not ident:
            return
        try:
            d = self.config.get(self.PERSIST_DELETED_KEY)
            if not isinstance(d, dict):
                d = {}
            arr = [str(x) for x in (d.get(key) or [])]
            if ident not in arr:
                arr.append(ident)
            if len(arr) > self.PERSIST_DELETED_LIMIT:
                del arr[:-self.PERSIST_DELETED_LIMIT]
            d[key] = arr
            self.config[self.PERSIST_DELETED_KEY] = d
        except Exception:
            pass

    def _persist_unmark_deleted(self, key, ident):
        ident = str(ident or "").strip()
        if not ident:
            return
        try:
            d = self.config.get(self.PERSIST_DELETED_KEY)
            if not isinstance(d, dict):
                return
            arr = [str(x) for x in (d.get(key) or [])]
            arr = [x for x in arr if x != ident]
            if arr:
                d[key] = arr
            else:
                d.pop(key, None)
            self.config[self.PERSIST_DELETED_KEY] = d
        except Exception:
            pass

    def _merge_unique_list(self, base, extra, key):
        """把 extra 里 base 没有的条目补进 base（base 顺序在前、同标识以 base 为准）"""
        seen, out = set(), []
        for it in (base or []):
            i = str(self._persist_ident(key, it) or "").strip()
            if i:
                seen.add(i)
            out.append(it)
        for it in (extra or []):
            i = str(self._persist_ident(key, it) or "").strip()
            if i:
                if i in seen:
                    continue
                seen.add(i)
            else:
                if it in out:
                    continue
            out.append(it)
        return out

    def _config_prune_deleted(self):
        """按「已删除登记表」剔除条目：外部配置文件里常留着已删的接口 / 目录，
        合并后会把它们带回来，导致"删了重启又出现"。"""
        cfg = self.config if isinstance(self.config, dict) else {}
        for key in ('sources', 'root_dirs', 'scan_local_dirs',
                    'localized_interfaces'):
            try:
                dead = set(self._persist_deleted_idents(key))
            except Exception:
                dead = set()
            if not dead:
                continue
            arr = cfg.get(key)
            if not isinstance(arr, list) or not arr:
                continue
            kept = [it for it in arr
                    if str(self._persist_ident(key, it) or "").strip() not in dead]
            if len(kept) != len(arr):
                cfg[key] = kept
                self._log("【init】已忽略 %d 个已删除的 %s"
                          % (len(arr) - len(kept), key))

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

    def _legacy_config_locations(self):
        """历史遗留位置：曾经被当作配置备份目录 / 本地包目录的文件夹。

        用户换过目录后，旧目录里可能还留着 persistent_config.json 与 map，
        而恢复逻辑会遍历候选位置取最新的一份 —— 于是"删了当前配置，
        重启又被旧目录里的残留喂回来"。清缓存时必须一并扫掉。
        """
        out, seen = [], set()

        def add(p):
            try:
                p = os.path.abspath(str(p or "").strip())
            except Exception:
                return
            if not p or p in seen:
                return
            seen.add(p)
            out.append(p)

        add(str(getattr(self, 'config_backup_dir', '') or ''))
        add(str(getattr(self, 'download_output_dir', '') or ''))
        for d in (getattr(self, 'root_dirs', None) or []):
            add(d)
        for d in (getattr(self, 'scan_local_dirs', None) or []):
            add(d)
        add(DEFAULT_DOWNLOAD_DIR)
        add(os.path.join(SCRIPT_DIR, "本地包"))
        add(SCRIPT_DIR)
        return out

    def _purge_legacy_configs(self):
        """清除所有已知目录里的历史配置残留 + map 目录"""
        removed = []
        for base in self._legacy_config_locations():
            if not base or not os.path.isdir(base):
                continue
            # 1) 删除目录下的配置文件
            for nm in (CONFIG_BACKUP_NAME, "down_config.json", "config.json"):
                fp = os.path.join(base, nm)
                if os.path.isfile(fp):
                    try:
                        os.remove(fp)
                        removed.append(fp)
                    except Exception:
                        pass
            # 2) 删除目录下的 map / temp（只清本目录直属的；
            #    旧版本叫 temp，一并清理，避免残留被恢复逻辑读回）
            for _nm in ("map", "temp"):
                tp = os.path.join(base, _nm)
                if os.path.isdir(tp) and os.path.abspath(base) != os.path.abspath(
                        str(self._work_subdir_base() or "")):
                    try:
                        shutil.rmtree(tp, ignore_errors=True)
                        removed.append(tp + os.sep)
                    except Exception:
                        pass
        return removed

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
            # [修复] 历史遗留目录里的旧配置 / map 一并清掉，
            # 否则恢复逻辑会从这些位置把已删除的配置再读回来
            legacy = self._purge_legacy_configs()
            if legacy:
                self._log(f"已清除历史遗留配置/map {len(legacy)} 项")
                for p in legacy:
                    self._log(f"   · {p}", level='debug')
            if removed_backup:
                self._log(f"已清除配置备份 {len(removed_backup)} 份")

            try:
                FileDownloader._reset_head_cache()
            except Exception:
                pass

            # [修复] 新增配置字段必须在此显式清空。
            # 否则清完文件后实例属性仍留旧值，紧接着 _save_config_to_file()
            # 会把它们原样写回新文件 —— 表现就是"清了缓存，扩展名还在"。
            for _f in ('scan_custom_exts', 'scan_dir_exts', 'scan_dir_names',
                       'fav_history', 'favorite_fragments', 'localized_interfaces',
                       'root_dirs', 'scan_local_dirs'):
                try:
                    default = [] if _f != 'scan_dir_exts' and _f != 'scan_dir_names' else {}
                    setattr(self, _f, _copy_default(default))
                except Exception:
                    pass
            try:
                self.scan_local_extensions = list(self.SCAN_DEFAULT_ON)
            except Exception:
                pass
            try:
                self.scan_output_mode = "merged"
                self.scan_output_name = "我的影视"
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

    B64_MIN_LEN = 12

    B64_MAX_DEPTH = 6

    @classmethod
    def _b64_decode_to_text(cls, value):

        v = (value or "").strip()
        if len(v) < cls.B64_MIN_LEN:
            return None
        if not re.fullmatch(r'[A-Za-z0-9+/]+={0,2}', v):
            return None
        padded = v + '=' * (-len(v) % 4)
        try:
            raw = base64.b64decode(padded, validate=True)
        except Exception:
            return None
        if not raw:
            return None
        try:
            text = raw.decode('utf-8')
        except Exception:
            return None
        if not text:
            return None

        import unicodedata as _ud
        for ch in text:
            cat = _ud.category(ch)

            if cat in ('Cc', 'Cf', 'Cs', 'Co', 'Cn'):
                if ch in '\n\r\t':
                    continue
                return None

        alnum = sum(1 for c in text if c.isalnum())
        if alnum < len(text) * 0.5:
            return None
        return text

    def _deep_b64_decode(self, data, _depth=0):

        if _depth >= self.B64_MAX_DEPTH:
            return data
        if isinstance(data, dict):
            out = {}
            for k, v in data.items():

                if k == PROCESS_INFO_KEY:
                    out[k] = v
                else:
                    out[k] = self._deep_b64_decode(v, _depth)
            return out
        if isinstance(data, list):
            return [self._deep_b64_decode(v, _depth) for v in data]
        if isinstance(data, str):
            text = self._b64_decode_to_text(data)
            if text is None or text == data:
                return data
            return self._deep_b64_decode(text, _depth + 1)
        return data

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

                    try:
                        data = json.loads(self._clean_json_comments(content))
                        is_json = True
                        self._log(f"【解密】{name} 明文含注释，已清理后解析")
                    except Exception:
                        is_json = False
                if is_json:

                    data = self._deep_b64_decode(data)
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

                                data = self._deep_b64_decode(data)
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
        # 重新加回来的接口要从"已删除"登记表里放出来
        try:
            self._persist_unmark_deleted('sources', clean_url)
        except Exception:
            pass
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

        # [修复] 登记删除：下次启动时外部配置文件里若还留着这条就不会被合并回来
        for item in removed:
            try:
                self._persist_mark_deleted('sources', item.get("url"))
            except Exception:
                pass

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

    def _collect_refs(self, obj, base_url, result):

        for holder, key, fk in self._iter_ref_slots(obj):
            v = holder[key]
            if not isinstance(v, str):
                continue
            stripped = v.strip()

            if (stripped.startswith('{') and stripped.endswith('}')) or \
                    (stripped.startswith('[') and stripped.endswith(']')):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, (dict, list)):

                        for _h, _k, _sfk in self._iter_deep_slots(parsed, fk):
                            _v = _h[_k]
                            if not isinstance(_v, str):
                                continue
                            for part in [q.strip() for q in _v.split('$$')]:
                                if part:
                                    result.add((part, base_url, _sfk))
                        continue
                except Exception:
                    pass

            for part in [q.strip() for q in v.split('$$')]:
                if part:
                    result.add((part, base_url, fk))

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

        self._collect_refs(data, base_url, all_items)
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

            return self._deep_b64_decode(data), base_url, None
        except json.JSONDecodeError as e:
            self._log(f"JSON 解析失败: {self._json_error_hint(content, e)}, "
                      f"尝试清理注释并修复格式...")

            content = self._clean_json_comments(content)
            try:
                data = json.loads(content)
                self._log("修复后成功解析 JSON")
                return self._deep_b64_decode(data), base_url, None
            except json.JSONDecodeError as e2:
                self._log(f"修复后仍失败: {self._json_error_hint(content, e2)}, "
                          f"尝试提取片段...")

        candidate = _best_json_span(content)
        if candidate:
            try:
                data = json.loads(candidate)
                data = self._deep_b64_decode(data)
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

                    for candidate in re.findall(json_pattern, decrypted):
                        try:
                            data = json.loads(candidate)
                            self._log("从解密片段成功解析 JSON")
                            return data, base_url, None
                        except Exception:
                            continue
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

        self._collect_refs(data, base_url, all_items)
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

        items = stats.get("remote_refs_items") or []
        if items:
            info["回源引用"] = [str(x) for x in items][:200]
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

    _FILE_REF_KEYS = ('spider', 'jar', 'api', 'ext', 'pic', 'logo', 'icon',
                      'thumb', 'banner', 'src', 'file', 'proxy', 'url')

    _NON_FILE_KEYS = ('type', 'playerType', 'ua', 'regex', 'hosts', 'name',
                      'key', 'desc', 'style', 'tid', 'cate', 'sort',
                      'searchable', 'filterable', 'quickSearch', 'headers',
                      'timeout', 'ratio', 'id', 'title', 'label')

    def _looks_like_file_ref(self, value, field_key=None):

        if not value or not isinstance(value, str):
            return False
        v = value.strip()
        if not v:
            return False
        if v.lower().startswith(('http://', 'https://', 'file://', 'proxy://')):
            return False
        if field_key and str(field_key).lower() in self._NON_FILE_KEYS:
            return False

        if re.search(r'[\[\]()*+?|^$\\{}]', v):
            return False
        path_part = v.split('?')[0].split(';')[0].rstrip('/')
        ext = os.path.splitext(path_part)[1].lower()
        has_dl_ext = bool(ext and ext in DOWNLOAD_EXTS)
        if v.startswith(('./', '../', '/')):
            if field_key and str(field_key).lower() in self._FILE_REF_KEYS:
                return True
            return has_dl_ext

        path_part = v.split('?')[0].split(';')[0].rstrip('/')
        ext = os.path.splitext(path_part)[1].lower()
        return bool(ext and ext in DOWNLOAD_EXTS)

    _REF_ROOT_KEYS = ("spider",)
    _REF_GROUPS = ("sites", "lives")

    _REF_GROUP_FIELDS = ("api", "url", "jar", "ext")

    def _iter_deep_slots(self, node, fk):

        if isinstance(node, dict):
            for k in list(node.keys()):
                v = node[k]
                if isinstance(v, (dict, list)):
                    for slot in self._iter_deep_slots(v, fk):
                        yield slot
                else:
                    yield node, k, fk
        elif isinstance(node, list):
            for i in range(len(node)):
                v = node[i]
                if isinstance(v, (dict, list)):
                    for slot in self._iter_deep_slots(v, fk):
                        yield slot
                else:
                    yield node, i, fk

    def _iter_ref_slots(self, data):

        # [FIX BUG-03] 支持顶层数组 JSON（如接口返回 [{...},{...}]）：
        # 原先直接 return，导致数组内所有引用都不会被本地化重写。
        # [MERGE v1+v2] 顶层数组有两种形态，需分别处理（仅取任一版都会漏一半）：
        #   形态A 元素是站点对象  [{key,name,api}]          —— 按 {"sites": [...]} 走
        #   形态B 元素是容器对象  [{spider,sites:[...]}]    —— 递归进元素内部走
        # 判别依据：元素含 _REF_ROOT_KEYS / _REF_GROUPS 中任一键即为容器对象，
        # 否则视为站点对象。混合数组两种形态各自归位，互不干扰。
        if isinstance(data, list):
            _container_items = []
            _plain_items = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                if any(k in item for k in self._REF_ROOT_KEYS) or \
                        any(g in item for g in self._REF_GROUPS):
                    _container_items.append(item)
                else:
                    _plain_items.append(item)
            for item in _container_items:
                for slot in self._iter_ref_slots(item):
                    yield slot
            if _plain_items:
                for slot in self._iter_ref_slots({"sites": _plain_items}):
                    yield slot
            return
        if not isinstance(data, dict):
            return
        for k in self._REF_ROOT_KEYS:
            if k in data:
                yield data, k, k
        for group in self._REF_GROUPS:
            arr = data.get(group)
            if not isinstance(arr, list):
                continue
            for item in arr:
                if not isinstance(item, dict):
                    continue
                for fk in self._REF_GROUP_FIELDS:
                    if fk not in item:
                        continue
                    yield item, fk, fk

                    if fk == "ext":
                        for slot in self._iter_deep_slots(item[fk], fk):
                            yield slot

    def _is_runtime_api_ref(self, value, field_key=None):

        if not value or not isinstance(value, str):
            return False
        v = value.strip()
        if not v:
            return False
        if field_key and str(field_key).lower() in self._NON_FILE_KEYS:
            return False

        if re.search(PLACEHOLDER_RE, v):
            return True
        if re.search(r'[\[\](){}+|^$\\]', v):
            return False
        path_part = v.split('?')[0].split(';')[0].rstrip('/')
        ext = os.path.splitext(path_part)[1].lower()
        if ext and ext in SKIP_EXTS:
            return True
        for pat in SKIP_PATTERNS:
            try:
                if re.search(pat, v):
                    return True
            except Exception:
                continue

        if v.lower().startswith(('http://', 'https://')):
            rest = v.split('://', 1)[1]
            if '/' not in rest or rest.endswith('/'):
                return True
        return False

    def _downloadable_ext(self, value):

        if not value or not isinstance(value, str):
            return ''
        path_part = value.split('?')[0].split(';')[0].rstrip('/')
        ext = os.path.splitext(path_part)[1].lower()
        return ext if (ext and ext in DOWNLOAD_EXTS) else ''

    def _generate_local_box(self, data, source_name, output_dir, downloader,
                            base_url=None, source_url=""):
        import json

        remote_refs = {"n": 0, "items": []}

        def localize_str(v, field_key):

            if not isinstance(v, str):
                return v
            stripped = v.strip()

            if (stripped.startswith('{') and stripped.endswith('}')) or \
                    (stripped.startswith('[') and stripped.endswith(']')):
                try:
                    parsed = json.loads(stripped)

                    for _h, _k, _fk in self._iter_deep_slots(parsed, field_key):
                        _h[_k] = localize_str(_h[_k], _fk)
                    return json.dumps(parsed, ensure_ascii=False,
                                      separators=(',', ':'))
                except Exception:
                    pass
            local_path = self._find_local_path(v, downloader)
            if local_path:
                return local_path
            s2 = v.strip()
            if s2 and not s2.lower().startswith(('http://', 'https://')) \
                    and base_url:
                is_dl = bool(self._downloadable_ext(s2)) and \
                    self._looks_like_file_ref(s2, field_key)
                is_api = (not is_dl) and self._is_runtime_api_ref(
                    s2, field_key)
                if is_dl or is_api:
                    try:
                        abs_u = downloader.resolve_url(s2, base_url)
                        if abs_u and abs_u.lower().startswith(
                                ('http://', 'https://')):
                            if is_dl:
                                remote_refs["n"] += 1
                                remote_refs["items"].append(abs_u)
                            return abs_u
                    except Exception:
                        pass
            return v

        def localize(data):

            for holder, key, fk in list(self._iter_ref_slots(data)):
                try:
                    old_v = holder[key]
                    new_v = localize_str(old_v, fk)
                    if new_v != old_v:
                        holder[key] = new_v
                except Exception:
                    continue
            return data

        local_data = localize(data)
        # [FIX BUG-03] 顶层数组 JSON 包装为对象后再附加元信息，
        # 否则对 list 做字符串键赋值会抛 TypeError（且发生在全部下载完成之后）
        if isinstance(local_data, list):
            local_data = {"sites": local_data}
        local_data['warningText'] = WARNING_TEXT
        info = self._build_process_info(
            source_url=source_url, source_name=source_name,
            stats={"downloaded": downloader.fresh_count,

                   "failed": len({str(u) for u, _ in (
                       list(downloader.failed)
                       + list(getattr(downloader, "repeat_failed", [])))}),
                   "skipped": len(downloader.skipped),
                   "unchanged": len(downloader.unchanged),

                   "remote_refs": remote_refs["n"],
                   "remote_refs_items": remote_refs["items"]},
            failed_items=self._uniq_failed_urls(
                list(downloader.failed)
                + list(getattr(downloader, "repeat_failed", []) or []))[:20])
        if info:
            local_data[PROCESS_INFO_KEY] = info
            self._log_process_summary(source_name, info)
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', source_name)
        box_filename = self.localized_filename_template.format(name=safe_name)
        box_path = os.path.join(output_dir, box_filename)
        with open(box_path, 'w', encoding='utf-8') as f_local:
            json.dump(local_data, f_local, ensure_ascii=False, indent=2)
        return box_path

    @staticmethod
    def _uniq_failed_urls(items):

        seen = set()
        out = []
        for it in (items or []):
            try:
                u = it[0] if isinstance(it, (list, tuple)) else it
            except Exception:
                continue
            k = str(u)
            if k in seen:
                continue
            seen.add(k)
            out.append(it)
        return out

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
        self._push_log(f"❤️ 收集到 {len(paths)} 个可下载文件，开始并发下载...")
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

    @staticmethod
    def _is_fixable(problem):

        if not isinstance(problem, dict):
            return False
        if "fixable" in problem:
            return bool(problem.get("fixable"))
        return bool(problem.get("url"))

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

    # [FIX BUG-02] 移除重复的 @staticmethod 装饰器：
    # 双重包装在 Python < 3.10（旧版 Chaquopy 常配 3.8）下
    # "staticmethod object is not callable"，导致体检误报与截断检测静默失效
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

        remote_list = self._recorded_remote_refs(output_dir, data)
        seen = set()

        for _holder, _key, _fk in self._iter_ref_slots(data):
            obj = _holder[_key]
            if not isinstance(obj, str):
                continue
            field_key = _fk
            low = obj.lower()
            if obj.startswith('./'):
                if field_key and not self._looks_like_file_ref(obj, field_key):
                    continue
                rel = obj[2:].split('#')[0].split('?')[0]
                if rel in seen:
                    continue
                seen.add(rel)
                if not os.path.exists(os.path.join(output_dir, rel)):
                    problems.append({"path": rel,
                                     "reason": "文件缺失（按 box 引用检测）",
                                     "url": None, "check": "missing"})
            elif low.startswith(('http://', 'https://')):

                if obj in seen:
                    continue
                seen.add(obj)
                if obj not in remote_list:
                    continue
                problems.append({"path": obj,
                                 "reason": "回源引用（能用但需联网，建议重新本地化）",
                                 "url": obj, "check": "remote",

                                 "fixable": False})
        return problems

    def _recorded_remote_refs(self, output_dir, box_data=None):

        out = set()
        try:
            data = box_data
            if data is None:
                entry = self._pick_box_entry(output_dir)
                if not entry:
                    return out
                with open(entry, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            info = (data or {}).get(PROCESS_INFO_KEY) or {}
            for u in info.get("回源引用") or []:
                if u:
                    out.add(str(u))
        except Exception:
            pass
        return out

    def _has_remote_record(self, output_dir, box_data=None):

        return bool(self._recorded_remote_refs(output_dir, box_data))

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

    def _merge_manifest(self, output_dir, downloader, source_name="", source_url=""):

        old = self._load_manifest(output_dir)
        new_entries = dict(getattr(downloader, "manifest_entries", None) or {})
        if not new_entries:
            return None
        merged = dict(old or {})
        merged.update(new_entries)
        meta = {"source_name": "", "source_url": ""}
        path = self._manifest_path(output_dir)
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    d0 = json.load(f)
                if isinstance(d0, dict):
                    meta["source_name"] = d0.get("source_name", "")
                    meta["source_url"] = d0.get("source_url", "")
        except Exception:
            pass
        if source_name:
            meta["source_name"] = source_name
        if source_url:
            meta["source_url"] = source_url
        data = {
            "version": MANIFEST_VERSION,
            "source_name": meta["source_name"],
            "source_url": meta["source_url"],
            "updated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
            "files": merged,
        }
        try:
            os.makedirs(output_dir, exist_ok=True)
            self._write_json_atomic(path, data)
            self._log("📝 已更新包清单（共 {} 项，本次 {} 项）".format(
                len(merged), len(new_entries)))
            return path
        except Exception as e:
            self._log("更新清单失败 {}: {}".format(path, e))
            return None

    def _rewrite_box_refs(self, output_dir, mapping):

        if not mapping:
            return 0
        entry = self._pick_box_entry(output_dir)
        if not entry:
            return 0
        try:
            with open(entry, 'r', encoding='utf-8') as f:
                text = f.read()
        except Exception as e:
            self._log("改写引用：读取入口失败 {}: {}".format(entry, e))
            return 0
        n = 0
        for url, rel in mapping.items():
            if not url or not rel:
                continue
            old_lit = json.dumps(url)
            new_lit = json.dumps("./" + rel)
            if old_lit in text:
                text = text.replace(old_lit, new_lit)
                n += 1
        if not n:
            return 0
        try:
            data = json.loads(text)
        except Exception as e:
            self._log("改写引用后入口不再是合法 JSON，已放弃: {}".format(e))
            return 0
        tmp = entry + ".tmp"
        try:
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, entry)
            self._log("🔗 已把 {} 处回源引用改回本地相对路径".format(n))
        except Exception as e:
            self._log("改写引用写入失败: {}".format(e))
            return 0
        return n

    def _package_source_url(self, output_dir):

        try:
            entry = self._pick_box_entry(output_dir)
            if entry:
                with open(entry, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                u = ((data or {}).get(PROCESS_INFO_KEY) or {}).get("源接口地址")
                if u:
                    return str(u)
        except Exception:
            pass
        try:
            u = self._manifest_source_url(output_dir)
            if u:
                return str(u)
        except Exception:
            pass
        return ""

    def _relocalize_package(self, name, pkg_dir, on_done=None, kit=None):

        src = self._package_source_url(pkg_dir)
        if not src:
            if kit is not None:
                kit.toast("找不到源接口地址，请到接口列表手动重跑", long=True)
            return False
        site = None
        for st in (self.package_download_sites or []):
            if st.get("url") == src:
                site = st
                break
        if site is None:

            site = {"id": self._package_download_site_id(name, src),
                    "name": name, "url": src, "enabled": True}
        if kit is not None:
            kit.toast("开始重新本地化，进度见日志", long=True)
        try:
            self._show_log_dialog()
        except Exception:
            pass

        def _work():
            try:
                return self._localize_single_site(site)
            except Exception as e:
                self._log("重新本地化异常: {}".format(e), level='error')
                return None

        def _then(_res):
            if kit is not None:
                kit.toast("重新本地化完成")
            if on_done is not None:
                on_done()

        self._run_background(_work, on_done=_then)
        return True

    def _collect_dead_fragments(self, output_dir, problems):

        entry = self._pick_box_entry(output_dir)
        if not entry:
            return []
        try:
            with open(entry, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return []
        if not isinstance(data, dict):
            return []

        bad = []
        for p in (problems or []):
            v = str(p.get("path") or "").strip()
            if v:
                bad.append((v, p.get("reason") or ""))
        if not bad:
            return []
        out = []
        for group in ("sites", "parses", "rules"):
            arr = data.get(group)
            if not isinstance(arr, list):
                continue
            for idx, item in enumerate(arr):
                try:
                    blob = json.dumps(item, ensure_ascii=False)
                except Exception:
                    blob = str(item)
                hits = []
                for v, reason in bad:
                    if v in blob or ("./" + v) in blob:
                        hits.append((v, reason))
                if not hits:
                    continue
                nm = ""
                if isinstance(item, dict):
                    nm = (item.get("name") or item.get("title")
                          or item.get("key") or "")
                nm = str(nm).strip() or "(未命名 #{} )".format(idx + 1)
                for v, reason in hits:
                    out.append((group, nm, v, reason, idx))
        return out

    def _remove_dead_fragments(self, output_dir, selected):

        if not selected:
            return 0, "未选择任何片段"
        entry = self._pick_box_entry(output_dir)
        if not entry:
            return 0, "找不到包入口"
        try:
            with open(entry, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            return 0, "入口解析失败: {}".format(e)
        if not isinstance(data, dict):
            return 0, "入口格式不支持"
        removed = 0
        for group in ("sites", "parses", "rules"):
            arr = data.get(group)
            if not isinstance(arr, list):
                continue
            keep = []
            for idx, item in enumerate(arr):
                if (group, idx) in selected:
                    removed += 1
                else:
                    keep.append(item)
            data[group] = keep
        if not removed:
            return 0, "没有匹配的条目"
        tmp = entry + ".tmp"
        try:
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, entry)
            self._log("🧹 已移除 {} 个失效片段".format(removed))
        except Exception as e:
            return 0, "写回失败: {}".format(e)
        return removed, ""

    def _open_remove_dead_dialog(self, name, pkg_dir, problems, on_done=None):

        def on_ui(act):
            kit = self._kit(act)
            frags = self._collect_dead_fragments(pkg_dir, problems)

            container = kit.vbox()
            container.setLayoutParams(kit.lp(-1, -2))

            card = kit.card()
            card.addView(kit.section_title(
                "🧹 移除失效片段 · {}".format(name)), kit.lp(-1, -2))
            card.addView(kit.hint(
                "下列是体检报告里列出的问题。勾选要移除的线路，"
                "移除后该线路不再出现在包里。"),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XS, 0.0, 0.0)))

            if not frags:
                card.addView(kit.empty("没有可移除的片段（该包体检无问题）",
                                       icon="✅"), kit.lp(-1, -2))
                container.addView(card, kit.lp(-1, -2))
                self._show_dialog(act, "🧹 移除失效片段", container,
                                  [{"text": "关闭", "style": "secondary",
                                    "callback": None, "dismiss": True}],
                                  height_ratio=0.9)
                return

            picked = {}
            rows_holder = kit.vbox()
            rows_holder.setLayoutParams(kit.lp(-1, -2))

            def refresh_rows():
                rows_holder.removeAllViews()
                for i, (group, nm, path, reason, idx) in enumerate(frags):
                    def make_toggle(i=i):
                        def on_change(v):
                            picked[i] = bool(v)
                        return on_change
                    rows_holder.addView(
                        self._ui_site_card(
                            kit, nm,
                            "{}  ←  {}".format(path, reason or "失效"),
                            bool(picked.get(i, False)), make_toggle(), None),
                        kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XS, 0.0, 0.0)))

            def select_all():
                for i in range(len(frags)):
                    picked[i] = True
                refresh_rows()

            def clear_all():
                for i in range(len(frags)):
                    picked[i] = False
                refresh_rows()

            card.addView(kit.button_bar([
                {"text": "全选", "style": "secondary",
                 "callback": select_all, "dismiss": False},
                {"text": "清空", "style": "secondary",
                 "callback": clear_all, "dismiss": False},
            ], size="sm"), kit.lp(-1, -2, 0.0,
                                   (0.0, UITheme.S_SM, 0.0, UITheme.S_SM)))
            card.addView(rows_holder, kit.lp(-1, -2))
            container.addView(card, kit.lp(-1, -2))

            def do_remove():
                sel = {(frags[i][0], frags[i][4])
                       for i, on in picked.items() if on}
                if not sel:
                    kit.toast("请先勾选要移除的片段", long=True)
                    return
                n, err = self._remove_dead_fragments(pkg_dir, sel)
                if n:
                    kit.toast("已移除 {} 个失效片段".format(n), long=True)
                    if on_done:
                        on_done()
                else:
                    kit.toast(err or "没有移除任何片段", long=True)

            refresh_rows()
            self._show_dialog(act, "🧹 移除失效片段", container,
                              [{"text": "🗑 移除选中", "style": "danger",
                                "callback": do_remove, "dismiss": False},
                               {"text": "关闭", "style": "secondary",
                                "callback": None, "dismiss": True}],
                              height_ratio=0.94)

        self._run_on_ui(on_ui)

    def _remove_dead_refs(self, output_dir, problems):

        entry = self._pick_box_entry(output_dir)
        if not entry:
            return 0, "找不到包入口"
        try:
            with open(entry, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            return 0, "入口解析失败: {}".format(e)
        if not isinstance(data, dict):
            return 0, "入口格式不支持"
        bad = set()
        for p in (problems or []):
            if p.get("url"):
                continue
            v = p.get("path")
            if v:
                bad.add(str(v))
        if not bad:
            return 0, "没有需要移除的失效引用（都可补下）"
        removed = 0
        for key in ("sites", "parses", "rules"):
            arr = data.get(key)
            if not isinstance(arr, list):
                continue
            keep = []
            for item in arr:
                try:
                    blob = json.dumps(item, ensure_ascii=False)
                except Exception:
                    blob = str(item)
                hit = False
                for v in bad:

                    if v in blob or ("./" + v) in blob:
                        hit = True
                        break
                if hit:
                    removed += 1
                else:
                    keep.append(item)
            data[key] = keep
        if not removed:
            return 0, "没有匹配到可移除的条目"
        tmp = entry + ".tmp"
        try:
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, entry)
            self._log("🧹 已移除 {} 个失效条目".format(removed))
        except Exception as e:
            return 0, "写回失败: {}".format(e)
        return removed, ""

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

        ref_map = {}
        for idx, item in enumerate(todo, 1):
            if cancel_event and cancel_event.is_set():
                break
            url = item["url"]
            self._push_log(f"🩹 [{idx}/{len(todo)}] 修复 {item['path']}")
            abs_url = url if url.startswith('http') else url
            target_rel = item["path"]

            is_remote_ref = (item.get("check") == "remote")
            if not is_remote_ref:
                target_abs = os.path.join(output_dir, target_rel)
                if os.path.exists(target_abs):
                    try:
                        os.remove(target_abs)
                    except Exception as e:
                        self._log(f"删除损坏文件失败 {target_abs}: {e}")
                        fail += 1
                        continue

            try:

                rel = downloader.download_file(abs_url, "",
                                              self._guess_category(abs_url))
            except KeyboardInterrupt:
                raise
            except Exception as e:
                self._log("🩹 修复异常 {} → 跳过: {}".format(
                    abs_url[:80], str(e)[:120]), level='warn')
                fail += 1
                continue
            if rel:
                ok += 1
                ref_map[url] = rel

                if not is_remote_ref and rel != target_rel:
                    try:
                        src = os.path.join(output_dir, rel)
                        dst = os.path.join(output_dir, target_rel)
                        if os.path.isfile(src) and not os.path.exists(dst):
                            os.makedirs(os.path.dirname(dst), exist_ok=True)
                            shutil.copy2(src, dst)
                    except Exception as e:
                        self._log(f"对齐原路径失败 {target_rel}: {e}")
            else:
                fail += 1

        self._merge_manifest(output_dir, downloader)
        if ref_map:
            self._rewrite_box_refs(output_dir, ref_map)
        if need_regen:
            self._push_log(
                "⚠️ 另有 %d 处需重跑本地化才能修复（入口文件缺失）" % len(need_regen))
        return {"repaired": ok, "failed": fail,
                "skipped": len(problems) - len(todo) - len(need_regen),
                "need_relocalize": len(need_regen)}

    NON_PACKAGE_DIR_NAMES = {'map', 'log', 'logs', 'tmp', 'cache', '本地包'}

    COLLECTION_DIR_NAME = "爬虫程序"

    # ===== 收藏管理（接口改装中心）常量 =====
    # [全部] / [py] / [js] / [jar] / [其他] / [live]
    # 分类只基于 sites；lives 全部汇总进 [live]，与其它分类互斥
    FRAG_CATS = (
        ("all", "全部"), ("py", "PY"), ("js", "JS"),
        ("jar", "JAR"), ("other", "其他"), ("live", "LIVE"),
    )
    FRAG_CAT_LABEL = dict(FRAG_CATS)
    # 注入代理（注代）默认地址：可在片段卡片「注代」里改
    FRAG_PROXY_DEFAULT = "http://127.0.0.1:2080"
    # 片段编辑缓存目录（编辑弹窗需要落盘才能复用现有文本编辑器）
    FRAG_EDIT_DIRNAME = "frag_edit"

    def _work_subdir_base(self):

        cfg = str(getattr(self, 'config_backup_dir', '') or '').strip()
        if cfg:
            try:
                os.makedirs(cfg, exist_ok=True)
                return cfg
            except Exception:
                pass
        return self.download_output_dir or ""

    def _scan_exclude_dirs(self):

        out = set()
        cand = [
            str(getattr(self, 'config_backup_dir', '') or '').strip(),
            str(getattr(self, 'log_dir', '') or '').strip(),
            os.path.join(self.download_output_dir or "", "log"),
            os.path.join(self.download_output_dir or "", "logs"),
            os.path.join(self.download_output_dir or "", "配置"),
        ]
        for c in cand:
            if not c:
                continue
            try:
                out.add(os.path.abspath(c))
            except Exception:
                pass
        return out

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

            if self._pick_box_entry(full):
                dirs.append((name, full))
                continue

            if os.path.exists(os.path.join(full, MANIFEST_NAME)):
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
                    # [FIX BUG-18] 注册前检查该站点是否已有单站任务在运行：
                    # 原先直接覆盖 _site_op_threads[sid]，会导致单站任务与
                    # 批量任务双线程并行处理同一站点（状态互踩、目录双写）
                    with self._site_op_lock:
                        _old_t = self._site_op_threads.get(sid)
                        if _old_t is not None and _old_t is not threading.current_thread() \
                                and _old_t.is_alive():
                            self._log(f"⏭️ {name} 已有单站任务在运行，批量任务跳过")
                            self._site_states[sid]['localize_status'] = 'idle'
                            self._site_states[sid]['localize_msg'] = '已有任务在运行，已跳过'
                            continue
                        self._site_states[sid]['localize_status'] = 'processing'
                        self._site_states[sid]['localize_msg'] = f'正在转换 {idx}/{total}...'
                        self._site_op_threads[sid] = threading.current_thread()
                        self._site_cancel_events[sid] = cancel_event
                    stats = self._process_json_source(site, cancel_event)
                    if cancel_event.is_set():
                        self._site_states[sid]['localize_status'] = 'idle'
                        self._site_states[sid]['localize_msg'] = '已取消'
                        self._clear_site_op(sid)
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
                    self._clear_site_op(sid)
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
                    self._clear_site_op(sid)
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

            # [修复] 列表定高滚动：接口一多，下方批量按钮也不会被顶出屏幕
            _sites_sc, sites_container = self._ui_fixed_scroll(
                kit, rows=5, ratio=0.30)

            def refresh_site_list():
                sites_container.removeAllViews()
                if not spider.package_download_sites:
                    sites_container.addView(
                        kit.empty("还没有接口，点上方按钮添加或导入"),
                        kit.lp(-1, -2))
                    kit.fill_spring(sites_container, 0)
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

            list_card.addView(_sites_sc, kit.lp(-1, -2))
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
                        # [修复 BUG-03] 改名不是"换一条记录"：
                        # _add_or_update_package_download_site 命中的是同一条，
                        # 它会原地改名并按新 name+url 重算 id。此时 site["id"]
                        # 已经是新 id，再按它删一次等于把刚改好的接口删掉 ——
                        # 表现就是"接口改名，保存就消失"。
                        # 只在确实残留旧 id（且与新 id 不同）时才清理。
                        old_id = str(site.get("id") or "")
                        spider._add_or_update_package_download_site(new_name, new_url)
                        new_id = str(site.get("id") or "")
                        if old_id and old_id != new_id and any(
                                str(x.get("id") or "") == old_id
                                for x in spider.package_download_sites):
                            try:
                                spider._delete_package_download_sites([old_id])
                            except Exception:
                                pass
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

    def _dir_card_actions(self, kit, path, on_changed):

        spider = self

        def on_edit():
            def on_save(v):
                new = str(v or "").strip()
                if not new or new == path:
                    return
                if not os.path.isabs(new):
                    new = os.path.abspath(new)

                if not os.path.isdir(new):
                    kit.toast("文件夹不存在")
                    return
                on_changed(path, new)
            spider._show_modern_input("编辑目录", "输入目录路径", path, on_save)

        def on_copy():
            kit.toast("已复制路径" if kit.copy(path, "路径") else "复制失败")

        def on_delete():
            spider._show_modern_confirm(
                "确认删除", "从列表移除（不会删除磁盘文件）：{}".format(path),
                lambda: on_changed(path, None))

        return [
            {"text": "编辑", "style": "secondary", "callback": on_edit},
            {"text": "复制", "style": "secondary", "callback": on_copy},
            {"text": "删除", "style": "danger", "callback": on_delete},
        ]

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

            # [要求] 与「本地爬虫程序管理」风格统一：输入框 + 选取 + 添加 同一行
            add_row = kit.hbox()
            add_row.setLayoutParams(kit.lp(-1, -2))
            edit = kit.input(hint="输入或选取目录路径")
            edit.setLayoutParams(kit.lp(0, -2, 1.0))
            add_row.addView(edit)
            btn_pick = kit.button("选取", "secondary", None, size="sm")
            btn_pick.setLayoutParams(
                kit.lp(kit.dp(56), kit.dp(UITheme.H_BTN_SM), 0.0,
                       (kit.dp(UITheme.S_XS), 0.0, 0.0, 0.0)))
            add_row.addView(btn_pick)
            btn_addd = kit.button("添加", "primary", None, size="sm")
            btn_addd.setLayoutParams(
                kit.lp(kit.dp(56), kit.dp(UITheme.H_BTN_SM), 0.0,
                       (kit.dp(UITheme.S_XS), 0.0, 0.0, 0.0)))
            add_row.addView(btn_addd)
            add_card.addView(add_row, kit.lp(-1, -2))

            _root_sc, dirs_container = self._ui_fixed_scroll(kit, rows=5, ratio=0.30)
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

                    def on_changed(old, new, _r=root):
                        try:
                            if new is None:
                                if len(spider.root_dirs) <= 1:
                                    kit.toast("至少保留一个目录")
                                    return
                                spider.root_dirs = [x for x in spider.root_dirs if x != old]
                                # 登记删除，避免下次启动被旧配置合并回来
                                try:
                                    self._persist_mark_deleted('root_dirs', old)
                                except Exception:
                                    pass
                            else:
                                if new in spider.root_dirs:
                                    kit.toast("目录已存在")
                                    return
                                spider.root_dirs = [new if x == old else x
                                                    for x in spider.root_dirs]
                            spider._save_config_to_file()
                            refresh_dir_list()
                        except Exception as e:
                            kit.toast("保存失败: {}".format(e), long=True)

                    switches[root] = holder
                    dirs_container.addView(
                        spider._ui_dir_card(kit, idx + 1, root, True,
                                            spider._dir_card_actions(kit, root, on_changed),
                                            holder),
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
                    # 重新加回来的目录要从"已删除"登记表里放出来
                    try:
                        self._persist_unmark_deleted('root_dirs', path)
                    except Exception:
                        pass
                    spider._save_config_to_file()
                    kit.toast("已添加")
                    edit.setText("")
                    refresh_dir_list()
                except Exception as e:
                    kit.toast(f"添加失败: {e}", long=True)

            def do_pick_dir():
                # [要求] 优先定位到输入框里已经填好的有效路径
                start = self._browser_pick_start(
                    str(edit.getText() or ""),
                    [spider.download_output_dir] + list(spider.root_dirs or []))
                self._show_file_browser(
                    "选取设置目录", start or spider._fs_service_prefix(), mode="dir",
                    on_pick=lambda v: (edit.setText(str(v)),
                                       kit.toast("已选择：{}".format(v))),
                    manual_title="选取设置目录",
                )

            kit.bind_click(btn_pick, do_pick_dir)
            kit.bind_click(btn_addd, do_add)
            container.addView(add_card, kit.lp(-1, -2))

            list_card = kit.card()
            list_card.addView(kit.section_title("📋 设置目录列表", hint="勾选参与扫描，可编辑 / 复制 / 删除"),
                              kit.lp(-1, -2))
            list_card.addView(_root_sc, kit.lp(-1, -2))
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

    def _doctor_report_text(self, name, pkg_dir, problems):

        lines = ["体检报告 · {}".format(name), "目录: {}".format(pkg_dir or ""),
                 "时间: {}".format(time.strftime('%Y-%m-%d %H:%M:%S')), ""]
        if not problems:
            lines.append("✅ 该包完好，未发现问题")
            return "\n".join(lines)
        fixable = [p for p in problems if self._is_fixable(p)]
        unfixable = [p for p in problems if not self._is_fixable(p)]
        lines.append("共 {} 处 · {} 处可补下 · {} 处需重新本地化".format(
            len(problems), len(fixable), len(unfixable)))
        for title, items, mark in (
                ("可自动补下（点「修复」重下）", fixable, "[可修]"),
                ("需重新本地化（无远端地址）", unfixable, "[需重跑]")):
            if not items:
                continue
            lines.append("")
            lines.append("== {} ==".format(title))
            for it in items:
                lines.append("{} {}".format(mark, it.get("path", "")))
                lines.append("    {}".format(it.get("reason", "")))
        return "\n".join(lines)

    def _open_doctor_report(self, name, pkg_dir, problems, on_rescan=None):

        def on_ui(act):
            kit = self._kit(act)
            container = kit.vbox()
            container.setLayoutParams(kit.lp(-1, -2))

            container.addView(kit.hint(pkg_dir or ""),
                        kit.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_SM)))

            if not problems:
                card = kit.card()
                card.addView(kit.empty("✅ 该包完好，未发现问题", icon="📦"),
                             kit.lp(-1, -2))
                container.addView(card, kit.lp(-1, -2, 0.0,
                                              (UITheme.S_MD, 0.0, 0.0, 0.0)))
            else:
                fixable = [p for p in problems if self._is_fixable(p)]
                unfixable = [p for p in problems if not self._is_fixable(p)]
                container.addView(kit.section_title(
                    "共 {} 处 · {} 处可补下 · {} 处需重跑本地化".format(
                        len(problems), len(fixable), len(unfixable))),
                    kit.lp(-1, -2, 0.0, (UITheme.S_SM, 0.0, 0.0, 0.0)))

                def _add_group(title, items, mark):
                    if not items:
                        return
                    card = kit.card()
                    card.addView(kit.section_title(title), kit.lp(-1, -2))
                    for it in items[:60]:
                        card.addView(
                            kit.text("{} {}\n   {}".format(
                                     mark, it.get("path", ""),
                                     it.get("reason", "")),
                                     size=UITheme.FS_CAPTION),
                            kit.lp(-1, -2, 0.0,
                                   (0.0, UITheme.S_XXS, 0.0, 0.0)))
                    if len(items) > 60:
                        card.addView(kit.text(
                            "…另有 {} 处未显示".format(len(items) - 60),
                            size=UITheme.FS_CAPTION, color=UITheme.TEXT_3),
                            kit.lp(-1, -2))
                    container.addView(card, kit.lp(-1, -2, 0.0,
                                             (UITheme.S_SM, 0.0, 0.0, 0.0)))

                _add_group("可自动补下（点「修复」重下）", fixable, "🩹")
                _add_group("需重新本地化（无远端地址）", unfixable, "⚠️")

            def do_copy():
                txt = self._doctor_report_text(name, pkg_dir, problems)
                kit.toast("已复制报告" if kit.copy(txt, "体检报告")
                          else "复制失败")

            def do_rescan():
                if on_rescan is None:
                    kit.toast("请在体检弹窗内使用此功能")
                    return
                kit.toast("正在重新体检…")
                on_rescan()

            def do_relocalize():

                self._relocalize_package(name, pkg_dir, on_done=on_rescan,
                                         kit=kit)

            self._show_dialog(act, "📋 体检报告 · {}".format(name), container,
                              [{"text": "📋 复制", "style": "secondary",
                                "callback": do_copy, "dismiss": False},
                               {"text": "🔄 重新体检", "style": "secondary",
                                "callback": do_rescan, "dismiss": False},
                               {"text": "♻️ 重新本地化", "style": "primary",
                                "callback": do_relocalize, "dismiss": False},
                               {"text": "关闭", "style": "secondary",
                                "callback": None, "dismiss": True}],
                              height_ratio=0.9)

        self._run_on_ui(on_ui)

    def _open_package_doctor_dialog(self):

        def on_ui(act):
            spider = self
            kit = self._kit(act)

            container = kit.vbox()
            container.setLayoutParams(kit.lp(-1, -2))

            container.addView(
                kit.text("能发现：文件缺失 / 大小不符 / JSON 截断 / 残留回源；"
                         "怎么用：选项目 → 开始体检 → 勾选包 → 修复。校验不联网。",
                         size=UITheme.FS_CAPTION, color=UITheme.TEXT_3),
                kit.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_XS)))

            opt_card = kit.card()
            opt_card.addView(kit.section_title("🩺 检查项目"), kit.lp(-1, -2))
            checks = spider._doctor_checks()
            opt_holder = kit.vbox()
            opt_holder.setLayoutParams(kit.lp(-1, -2))

            def refresh_options():
                opt_holder.removeAllViews()
                for key, title, _desc in self.DOCTOR_CHECKS:
                    def make_toggle(k=key):
                        def on_change(v):
                            checks[k] = bool(v)
                            spider._save_doctor_checks(checks)
                        return on_change
                    opt_holder.addView(
                        kit.toggle(title, bool(checks.get(key, True)),
                                   make_toggle(), weight=1.0),
                        kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XXS, 0.0, 0.0)))
            refresh_options()
            opt_card.addView(opt_holder, kit.lp(-1, -2))
            container.addView(opt_card, kit.lp(-1, -2))

            res_card = kit.card()
            res_card.addView(kit.section_title("📦 体检结果"), kit.lp(-1, -2))
            status = kit.text("点「开始体检」扫描", size=UITheme.FS_CAPTION,
                              color=UITheme.TEXT_3)
            res_card.addView(status, kit.lp(-1, -2, 0.0,
                                            (0.0, UITheme.S_XXS, 0.0, 0.0)))

            scan = {"rows": []}
            picked = {}

            touched = {"v": False}

            def _sync_status():
                if not scan["rows"]:
                    status.setText("点「开始体检」扫描本地包")
                    return
                cnt = sum(len(p) for _, _, p in scan["rows"])
                if cnt == 0:
                    status.setText("✅ {} 个包全部完好".format(len(scan["rows"])))
                    return
                bad = sum(1 for _, _, p in scan["rows"] if p)

                fixable = sum(1 for _, _, pp in scan["rows"]
                              for x in pp if self._is_fixable(x))
                if fixable:
                    status.setText("⚠️ {} 个包 {} 处问题 · {} 处可补下".format(
                        bad, cnt, fixable))
                else:
                    status.setText("⚠️ {} 个包 {} 处问题 · 无法补下"
                                   "（缺清单，需重新本地化）".format(bad, cnt))

            def refresh_rows():
                rows_holder.removeAllViews()
                if not scan["rows"]:
                    rows_holder.addView(
                        kit.empty("点「开始体检」扫描本地包", icon="🩺"),
                        kit.lp(-1, -2))
                    return
                for name, _dir, probs in scan["rows"]:
                    if probs:
                        fixable = sum(1 for x in probs if x.get("url"))
                        sub = "⚠️ {} 处 · 可修 {}".format(len(probs), fixable)
                    else:
                        sub = "✅ 完好"

                    def make_toggle(nm=name):
                        def on_change(v):
                            touched["v"] = True
                            picked[nm] = bool(v)
                        return on_change

                    def make_report(nm=name, pp=probs, dd=_dir):
                        def _reopen(res):

                            scan["rows"] = [
                                (n, d, (res if n == nm else p))
                                for n, d, p in scan["rows"]]
                            _sync_status()
                            refresh_rows()
                            _show_report(nm, dd, res)

                        def _show_report(nm2, dd2, pp2):
                            spider._open_doctor_report(
                                nm2, dd2, pp2,
                                on_rescan=lambda: spider._run_background(
                                    lambda: spider._verify_local_package(
                                        dd2, checks),
                                    on_done=_reopen))

                        def on_report():
                            _show_report(nm, dd, pp)
                        return on_report

                    def make_edit(nm=name, dd=_dir):
                        def on_edit():

                            entry = spider._pick_box_entry(dd)
                            if not entry:
                                kit.toast("找不到包入口", long=True)
                                return
                            try:
                                with open(entry, 'r', encoding='utf-8') as f:
                                    content = f.read()
                            except Exception as e:
                                kit.toast("读取失败: {}".format(e), long=True)
                                return

                            def on_saved():
                                kit.toast("已保存")
                                spider._run_background(
                                    lambda: spider._verify_local_package(dd, checks),
                                    on_done=lambda res: _replace_row(nm, dd, res))

                            spider._show_modern_text_editor(
                                "✏️ 本地化内容 - {}".format(nm), content, entry,
                                "", "file://" + os.path.abspath(entry), on_saved)
                        return on_edit

                    def make_remove(nm=name, pp=probs, dd=_dir):
                        def on_remove():

                            spider._open_remove_dead_dialog(
                                nm, dd, pp,
                                on_done=lambda: spider._run_background(
                                    lambda: spider._verify_local_package(
                                        dd, checks),
                                    on_done=lambda res: _replace_row(
                                        nm, dd, res)))
                        return on_remove

                    rows_holder.addView(
                        spider._ui_site_card(
                            kit, name, sub, bool(picked.get(name, False)),
                            make_toggle(),
                            [{"text": "📋 报告", "style": "secondary",
                              "callback": make_report(), "dismiss": False},
                             {"text": "✏️ 编辑", "style": "secondary",
                              "callback": make_edit(), "dismiss": False},
                             {"text": "🧹 移除失效", "style": "soft_danger",
                              "callback": make_remove(), "dismiss": False}]),
                        kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XS, 0.0, 0.0)))

            rows_holder = kit.vbox()
            rows_holder.setLayoutParams(kit.lp(-1, -2))

            def _replace_row(nm, dd, new_probs):

                scan["rows"] = [(n, d, (new_probs if n == nm else p))
                                for n, d, p in scan["rows"]]
                _sync_status()
                refresh_rows()

            def select_all():
                touched["v"] = True

                pickable = [n for n, _d, p in scan["rows"] if p]
                target = pickable or [n for n, _d, _p in scan["rows"]]
                for n in target:
                    picked[n] = True
                refresh_rows()

            def invert():
                touched["v"] = True
                for n, _d, _p in scan["rows"]:
                    picked[n] = not picked.get(n, False)
                refresh_rows()

            def clear_all():
                touched["v"] = True
                for n, _d, _p in scan["rows"]:
                    picked[n] = False
                refresh_rows()

            res_card.addView(kit.button_bar([
                {"text": "全选", "style": "secondary",
                 "callback": select_all, "dismiss": False},
                {"text": "反选", "style": "secondary",
                 "callback": invert, "dismiss": False},
                {"text": "清空", "style": "secondary",
                 "callback": clear_all, "dismiss": False},
            ], size="sm"), kit.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_SM)))
            res_card.addView(rows_holder, kit.lp(-1, -2))
            container.addView(res_card, kit.lp(-1, -2))

            def do_scan(after_heal=False):
                if not after_heal:
                    status.setText("正在体检…")
                self._run_background(
                    lambda: [(n, d, spider._verify_local_package(d, checks))
                             for n, d in spider._localized_package_dirs()],
                    on_done=on_scanned)

            def on_scanned(rows):
                scan["rows"] = rows or []
                picked.clear()
                _sync_status()
                refresh_rows()

            def do_heal():
                rows = scan["rows"]
                if not rows:
                    kit.toast("请先体检", long=True)
                    return
                sel = [n for n in picked if picked.get(n)]
                if sel:
                    todo = [r for r in rows if r[2] and r[0] in sel]
                elif touched["v"]:
                    kit.toast("未选中任何包，点开关或「全选」", long=True)
                    return
                else:
                    todo = [r for r in rows if r[2]]
                if not todo:
                    kit.toast("选中的包没有问题" if sel else "没有可修复的问题",
                              long=True)
                    return
                if not any(x.get("url") for _, _, pp in todo for x in pp):
                    kit.toast("缺远端地址，无法补下，请重新本地化", long=True)
                    return
                status.setText("正在修复…")

                def _work():
                    total_ok = total_fail = 0
                    for pkg_name, pkg_dir, problems in todo:
                        self._push_log("🩹 开始修复本地包: {}".format(pkg_name))
                        try:
                            r = self._heal_local_package(pkg_dir, problems)
                            total_ok += r.get("repaired", 0)
                            total_fail += r.get("failed", 0)
                            self._push_log("{} {}: 修复 {} 个，失败 {} 个".format(
                                "✅" if r.get("failed", 0) == 0 else "⚠️",
                                pkg_name, r.get("repaired", 0),
                                r.get("failed", 0)))
                        except Exception as e:
                            total_fail += len(problems)
                            self._log("修复 {} 失败: {}".format(pkg_name, e))
                    msg = "自愈完成：修复 {} 个文件".format(total_ok) + (
                        "，失败 {} 个".format(total_fail) if total_fail else "")
                    self._package_download_message = msg
                    self._push_log("🎉 " + msg)
                    self._notify_app(msg)
                    try:
                        self._save_config_to_file()
                    except Exception:
                        pass

                def _then(_):

                    do_scan(after_heal=True)

                try:
                    self._show_log_dialog()
                except Exception as e:
                    self._log(f"打开日志面板失败: {e}")
                self._run_background(_work, on_done=_then)

            buttons = [
                {"text": "🩺 开始体检", "style": "primary",
                 "callback": do_scan, "dismiss": False},
                {"text": "🩹 修复", "style": "success",
                 "callback": do_heal, "dismiss": False},
                {"text": "关闭", "style": "secondary",
                 "callback": None, "dismiss": True},
            ]
            refresh_rows()
            _sync_status()
            self._show_dialog(act, "🩺 本地包体检", container, buttons,
                              height_ratio=0.88)

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

    # 扫描弹窗的预设扩展名（顶部统一展示，用户可在顶部追加自定义类型）
    # 片段列表分页大小：一次建太多卡片会明显卡顿（TV 上尤其明显）
    FRAG_PAGE_SIZE = 40

    SCAN_PRESET_EXTS = ['.py', '.js']
    SCAN_DEFAULT_ON = ['.py']

    def _scan_all_exts(self):
        """全部可选扩展名 = 预设 + 用户自定义（去重，保持顺序）"""
        out = []
        for e in list(self.SCAN_PRESET_EXTS) + list(getattr(self, 'scan_custom_exts', None) or []):
            e = str(e or "").strip().lower()
            if not e:
                continue
            if not e.startswith('.'):
                e = '.' + e
            if e not in out:
                out.append(e)
        return out

    def _scan_add_custom_ext(self, raw):
        """顶部统一添加扩展名，返回 (ok, msg)"""
        txt = str(raw or "").strip().lower()
        if not txt:
            return False, "请输入扩展名"
        parts = [x.strip() for x in txt.replace('，', ',').split(',') if x.strip()]
        added, bad = [], []
        cur = list(getattr(self, 'scan_custom_exts', None) or [])
        all_presets = [str(x).lower() for x in self.SCAN_PRESET_EXTS]
        for p in parts:
            if not p.startswith('.'):
                p = '.' + p
            if not re.match(r'^\.[a-z0-9_]+$', p):
                bad.append(p)
                continue
            if p in all_presets:
                continue
            if p in cur:
                continue
            cur.append(p)
            added.append(p)
        if not added:
            return False, ("扩展名不合法：{}".format(",".join(bad)) if bad
                           else "该扩展名已存在")
        self.scan_custom_exts = cur
        try:
            self._save_config_to_file()
        except Exception:
            pass
        msg = "已添加 {}".format(",".join(added))
        if bad:
            msg += "（跳过非法：{}）".format(",".join(bad))
        return True, msg

    def _scan_remove_custom_ext(self, ext):
        try:
            self.scan_custom_exts = [
                e for e in (getattr(self, 'scan_custom_exts', None) or [])
                if str(e).lower() != str(ext).lower()]
            # 同步清理各目录里对它的引用
            de = getattr(self, 'scan_dir_exts', None) or {}
            for k in list(de.keys()):
                vals = [x for x in (de.get(k) or [])
                        if str(x).lower() != str(ext).lower()]
                if vals:
                    de[k] = vals
                else:
                    de.pop(k, None)
            self.scan_dir_exts = de
            self._save_config_to_file()
        except Exception:
            pass

    def _open_scan_dir_edit_dialog(self, path, on_done):
        """单个目录的设置弹窗：输出名称 + 扫描文件类型（支持顶部新添加的）"""

        def on_ui(act):
            kit = self._kit(act)
            holder = {}
            cur_exts = list((getattr(self, 'scan_dir_exts', None) or {}).get(path) or [])
            cur_name = str((getattr(self, 'scan_dir_names', None) or {}).get(path) or "")
            custom = bool(cur_exts)          # False = 跟随顶部默认
            state = {"custom": custom,
                     "on": set(e.lower() for e in (cur_exts or self.scan_local_extensions or []))}

            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))

            # ---- 目录 ----
            info_card = kit.card()
            info_card.addView(kit.section_title("📂 目录"), kit.lp(-1, -2))
            info_card.addView(
                kit.text(str(path), size=UITheme.FS_CAPTION, color=UITheme.TEXT_3,
                         mono=True, selectable=True, max_lines=4), kit.lp(-1, -2))
            box.addView(info_card, kit.lp(-1, -2))

            # ---- 输出名称 ----
            name_card = kit.card()
            name_card.addView(
                kit.section_title("📝 生成接口名称"),
                kit.lp(-1, -2))
            name_edit = kit.input(hint="例如：我的影视_1", value=cur_name)
            name_card.addView(name_edit, kit.lp(-1, -2))
            box.addView(name_card, kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))

            # ---- 扫描类型 ----
            ext_card = kit.card()
            ext_card.addView(
                kit.section_title("🧩 扫描文件类型"),
                kit.lp(-1, -2))

            ext_card.addView(
                self._ui_chip_row(
                    kit, [("default", "跟随默认"), ("custom", "单独指定")],
                    state, "custom",
                    on_change=lambda m: paint_exts()),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))

            all_exts = self._scan_all_exts()
            ext_checks = {}
            ext_holder = kit.vbox()
            ext_holder.setLayoutParams(kit.lp(-1, -2))
            _row = None
            for i, ext in enumerate(all_exts):
                if i % kit.max_cols == 0:
                    _row = kit.hbox()
                    _row.setLayoutParams(kit.lp(-1, -2))
                    ext_holder.addView(_row, kit.lp(-1, -2))
                tg = kit.toggle(ext, ext in state["on"], None, None, weight=1.0)
                try:
                    tg.setMinimumWidth(0)
                    tg.setMinWidth(0)
                    tg.setPadding(kit.dp(2), 0, kit.dp(2), 0)
                    tg.setSingleLine(True)
                except Exception:
                    pass

                def _mk(_e=ext):
                    def _cb(v):
                        if v:
                            state["on"].add(_e)
                        else:
                            state["on"].discard(_e)
                    return _cb

                try:
                    tg.setOnCheckedChangeListener(kit._on_checked(_mk()))
                except Exception:
                    pass
                ext_checks[ext] = tg
                _row.addView(tg, kit.lp(0, -2, 1.0))
            ext_card.addView(ext_holder, kit.lp(-1, -2))
            box.addView(ext_card, kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))

            def paint_exts():
                on = (state.get("custom") == "custom")
                for _e, _tg in ext_checks.items():
                    try:
                        _tg.setEnabled(on)
                    except Exception:
                        pass

            paint_exts()

            def do_ok():
                nm = str(name_edit.getText()).strip()
                try:
                    names = dict(getattr(self, 'scan_dir_names', None) or {})
                    if nm:
                        names[path] = nm
                    else:
                        names.pop(path, None)
                    self.scan_dir_names = names

                    de = dict(getattr(self, 'scan_dir_exts', None) or {})
                    if state.get("custom") == "custom":
                        vals = sorted(x for x in state["on"])
                        if vals:
                            de[path] = vals
                        else:
                            de.pop(path, None)
                            self.scan_dir_exts = de
                            self._save_config_to_file()
                            kit.toast("未勾选任何类型，已恢复跟随默认", long=True)
                            try:
                                holder["d"].dismiss()
                            except Exception:
                                pass
                            on_done()
                            return
                    else:
                        de.pop(path, None)
                    self.scan_dir_exts = de
                    self._save_config_to_file()
                except Exception as e:
                    kit.toast("保存失败: {}".format(e), long=True)
                    return
                kit.toast("已保存")
                try:
                    holder["d"].dismiss()
                except Exception:
                    pass
                on_done()

            def do_cancel():
                try:
                    holder["d"].dismiss()
                except Exception:
                    pass

            buttons = [
                {"text": "取消", "style": "secondary",
                 "callback": do_cancel, "dismiss": False},
                {"text": "保存", "style": "primary", "callback": do_ok, "dismiss": False},
            ]
            self._fav_dialog(act, "⚙️ 目录设置", box, buttons, holder, height_ratio=0)

        self._run_on_ui(on_ui)

    def _open_scan_local_files_dialog(self):

        def on_ui(act):
            spider = self
            kit = self._kit(act)
            spider._ensure_default_scan_dir()

            cur_mode = str(getattr(spider, 'scan_output_mode', 'merged')
                           or 'merged').strip().lower()
            if cur_mode not in ("merged", "multi"):
                cur_mode = "merged"

            # [要求] 预设只保留 .py/.js，历史配置里的 .jar/.lua/.json 一律失效
            _valid = set(spider._scan_all_exts())
            _cur = [str(e).lower() for e in (spider.scan_local_extensions or [])
                    if str(e).lower() in _valid]
            # 旧版本默认值是 ['.py','.js']，按新规则收敛为 ['.py']
            if sorted(_cur) == ['.js', '.py'] or not _cur:
                _cur = list(spider.SCAN_DEFAULT_ON)
            try:
                if _cur != list(spider.scan_local_extensions or []):
                    spider.scan_local_extensions = _cur
                    spider._save_config_to_file()
            except Exception:
                pass

            state = {
                "mode": cur_mode,
                "base": str(getattr(spider, 'scan_output_name', '') or '我的影视'),
                "kw": "",
                "sel": set(str(p) for p in (spider.scan_local_dirs or [])),
                "on": set(_cur),
            }

            container = kit.vbox()
            container.setLayoutParams(kit.lp(-1, -2))

            # ============ 1. 输出模式 ============
            mode_card = kit.card()
            mode_card.addView(
                kit.section_title("📤 输出模式",
                                  hint="合并=所有目录合成一个接口；分开=每个目录各生成一个"),
                kit.lp(-1, -2))
            mode_card.addView(
                self._ui_chip_row(
                    kit, [("merged", "合并输出"), ("multi", "按文件夹分开")],
                    state, "mode", on_change=lambda m: refresh_mode()),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))

            mode_hint = kit.hint("", max_lines=3)
            mode_card.addView(mode_hint,
                              kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))

            name_edit = kit.input(hint="输出名称", value=state["base"])
            mode_card.addView(name_edit,
                              kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XS, 0.0, 0.0)))
            container.addView(mode_card, kit.lp(-1, -2))

            def refresh_mode():
                multi = (state["mode"] == "multi")
                try:
                    name_edit.setVisibility(8 if multi else 0)   # GONE / VISIBLE
                    mode_hint.setText(
                        "分开：每个目录各生成一个，名称在目录「设置」里改" if multi else
                        "合并：所有目录合成一个")
                except Exception:
                    pass

            # ============ 2. 扫描文件类型（顶部统一添加）============
            ext_card = kit.card()
            head = kit.hbox()
            head.setLayoutParams(kit.lp(-1, -2))
            head.addView(
                kit.section_title("🧩 扫描文件类型"), kit.lp(0, -2, 1.0))
            ext_card.addView(head, kit.lp(-1, -2))

            ext_grid = kit.vbox()
            ext_grid.setLayoutParams(kit.lp(-1, -2))
            ext_card.addView(ext_grid,
                             kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))

            # 追加自定义扩展名
            add_row = kit.hbox()
            add_row.setLayoutParams(kit.lp(-1, -2))
            new_ext_edit = kit.input(hint="新扩展名，如 .lua")
            new_ext_edit.setLayoutParams(kit.lp(0, -2, 1.0))
            add_row.addView(new_ext_edit)
            btn_add = kit.button("添加", "primary", None, size="sm")
            btn_add.setLayoutParams(
                kit.lp(kit.dp(64), kit.dp(UITheme.H_BTN_SM), 0.0,
                       (kit.dp(UITheme.S_XS), 0.0, 0.0, 0.0)))
            add_row.addView(btn_add)
            ext_card.addView(add_row, kit.lp(-1, -2))

            ext_card.addView(
                kit.hint("可在此追加新类型"),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XXS, 0.0, 0.0)))
            container.addView(ext_card, kit.lp(-1, -2))

            def paint_exts():
                ext_grid.removeAllViews()
                all_exts = self._scan_all_exts()
                presets = set(str(x).lower() for x in self.SCAN_PRESET_EXTS)
                _row = None
                for i, ext in enumerate(all_exts):
                    if i % kit.max_cols == 0:
                        _row = kit.hbox()
                        _row.setLayoutParams(kit.lp(-1, -2))
                        ext_grid.addView(_row, kit.lp(-1, -2))

                    # 自定义类型：主体为开关，长按可删除
                    removable = ext not in presets
                    tg = kit.toggle(
                        ext, ext in state["on"], None,
                        (lambda _e=ext: lambda: (
                            self._show_modern_confirm(
                                "删除扩展名",
                                "确定删除自定义类型「{}」？".format(_e),
                                lambda: (self._scan_remove_custom_ext(_e),
                                         state["on"].discard(_e),
                                         paint_exts()))))() if removable else None,
                        weight=1.0)
                    try:
                        tg.setMinimumWidth(0)
                        tg.setMinWidth(0)
                        tg.setPadding(kit.dp(2), 0, kit.dp(2), 0)
                        tg.setSingleLine(True)
                    except Exception:
                        pass

                    def _mk(_e=ext):
                        def _cb(v):
                            if v:
                                state["on"].add(_e)
                            else:
                                state["on"].discard(_e)
                        return _cb

                    try:
                        tg.setOnCheckedChangeListener(kit._on_checked(_mk()))
                    except Exception:
                        pass
                    _row.addView(tg, kit.lp(0, -2, 1.0))

            def do_add_ext():
                ok, msg = self._scan_add_custom_ext(new_ext_edit.getText())
                kit.toast(msg, long=not ok)
                if ok:
                    try:
                        new_ext_edit.setText("")
                    except Exception:
                        pass
                    for e in (getattr(self, 'scan_custom_exts', None) or []):
                        state["on"].add(str(e).lower())
                    paint_exts()

            kit.bind_click(btn_add, do_add_ext)

            # ============ 3. 扫描目录 ============
            dir_card = kit.card()
            dir_card.addView(
                kit.section_title("📂 扫描文件夹"),
                kit.lp(-1, -2))

            add_dir_row = kit.hbox()
            add_dir_row.setLayoutParams(kit.lp(-1, -2))
            dir_edit = kit.input(hint="输入或选取文件夹路径")
            dir_edit.setLayoutParams(kit.lp(0, -2, 1.0))
            add_dir_row.addView(dir_edit)
            btn_pick = kit.button("选取", "secondary", None, size="sm")
            btn_pick.setLayoutParams(
                kit.lp(kit.dp(56), kit.dp(UITheme.H_BTN_SM), 0.0,
                       (kit.dp(UITheme.S_XS), 0.0, 0.0, 0.0)))
            add_dir_row.addView(btn_pick)
            btn_addd = kit.button("添加", "primary", None, size="sm")
            btn_addd.setLayoutParams(
                kit.lp(kit.dp(56), kit.dp(UITheme.H_BTN_SM), 0.0,
                       (kit.dp(UITheme.S_XS), 0.0, 0.0, 0.0)))
            add_dir_row.addView(btn_addd)
            dir_card.addView(add_dir_row,
                             kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))

            # [要求] 与「接口目录管理」风格统一：去掉列表下方的搜索框
            _dir_sc, dirs_container = self._ui_fixed_scroll(kit, rows=5, ratio=0.30)
            dir_card.addView(_dir_sc,
                             kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))
            container.addView(dir_card, kit.lp(-1, -2))

            def dir_exts_of(path):
                v = (getattr(self, 'scan_dir_exts', None) or {}).get(path)
                if v:
                    return list(v), False
                return sorted(state["on"]), True

            def dir_name_of(path, idx):
                return str((getattr(self, 'scan_dir_names', None) or {}).get(path)
                           or "{}_{}".format(state["base"], idx + 1))

            def selected_dirs_sorted():
                return [d for d in (spider.scan_local_dirs or [])
                        if d in state["sel"]]

            def refresh_dir_list():
                dirs_container.removeAllViews()
                kw = str(state.get("kw") or "").strip().lower()
                shown = [p for p in (spider.scan_local_dirs or [])
                         if (not kw) or kw in str(p).lower()]
                if not shown:
                    dirs_container.addView(
                        kit.empty("没有匹配的文件夹\n先在上方添加一个"),
                        kit.lp(-1, -2))
                    return
                for idx, path in enumerate(shown):
                    holder = {}

                    def make_change(old=path):
                        def cb(v):
                            if v:
                                state["sel"].add(old)
                            else:
                                state["sel"].discard(old)
                        return cb

                    def on_changed(old, new):
                        try:
                            if new is None:
                                if len(spider.scan_local_dirs) <= 1:
                                    kit.toast("至少保留一个目录")
                                    return
                                spider.scan_local_dirs = [
                                    x for x in spider.scan_local_dirs if x != old]
                                state["sel"].discard(old)
                                # 登记删除，避免下次启动被旧配置合并回来
                                try:
                                    self._persist_mark_deleted(
                                        'scan_local_dirs', old)
                                except Exception:
                                    pass
                                for k in ('scan_dir_exts', 'scan_dir_names'):
                                    d = dict(getattr(spider, k, None) or {})
                                    d.pop(old, None)
                                    setattr(spider, k, d)
                            else:
                                if new in spider.scan_local_dirs:
                                    kit.toast("文件夹已存在")
                                    return
                                spider.scan_local_dirs = [
                                    new if x == old else x
                                    for x in spider.scan_local_dirs]
                                if old in state["sel"]:
                                    state["sel"].discard(old)
                                    state["sel"].add(new)
                                for k in ('scan_dir_exts', 'scan_dir_names'):
                                    d = dict(getattr(spider, k, None) or {})
                                    if old in d:
                                        d[new] = d.pop(old)
                                    setattr(spider, k, d)
                            spider._save_config_to_file()
                            refresh_dir_list()
                        except Exception as e:
                            kit.toast("保存失败: {}".format(e), long=True)

                    do_edit = (lambda p=path: lambda: (
                        self._open_scan_dir_edit_dialog(p, refresh_dir_list)))()

                    actions = [
                        {"text": "设置", "style": "primary",
                         "callback": do_edit, "dismiss": False},
                        {"text": "复制", "style": "secondary",
                         "callback": (lambda p=path: lambda: kit.toast(
                             "已复制路径" if kit.copy(p, "路径") else "复制失败"))(),
                         "dismiss": False},
                        {"text": "删除", "style": "soft_danger",
                         "callback": (lambda p=path: lambda: (
                             self._show_modern_confirm(
                                 "确认删除",
                                 "从列表移除（不删磁盘文件）：\n{}".format(p),
                                 lambda: on_changed(p, None))))(),
                         "dismiss": False},
                    ]

                    exts, follow = dir_exts_of(path)
                    nm = dir_name_of(path, idx)
                    sub = "{}\n名称：{}".format(
                        os.path.basename(os.path.normpath(path)) or path, nm)
                    sub += "\n类型：{}{}".format(",".join(exts) or "无",
                                                "（跟随默认）" if follow else "")

                    card = spider._ui_dir_card(
                        kit, idx + 1, path, path in state["sel"], actions, holder)
                    # 卡片里再补一行设置摘要
                    try:
                        card.addView(kit.text(sub, size=UITheme.FS_CAPTION,
                                              color=UITheme.TEXT_3, max_lines=4),
                                     kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XXS, 0.0, 0.0)))
                    except Exception:
                        pass
                    sw = holder.get("switch")
                    if sw is not None:
                        try:
                            sw.setOnCheckedChangeListener(kit._on_checked(make_change()))
                        except Exception:
                            pass
                    dirs_container.addView(card, kit.lp(-1, -2))

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
                    try:
                        os.makedirs(path, exist_ok=True)
                    except Exception as e:
                        kit.toast("文件夹不存在，创建失败: {}".format(e), long=True)
                        return
                spider.scan_local_dirs.append(path)
                state["sel"].add(path)
                # 重新加回来的目录要从"已删除"登记表里放出来
                try:
                    self._persist_unmark_deleted('scan_local_dirs', path)
                except Exception:
                    pass
                spider._save_config_to_file()
                kit.toast("已添加")
                try:
                    dir_edit.setText("")
                except Exception:
                    pass
                refresh_dir_list()

            def do_pick_dir():
                # [要求] 优先定位到输入框里已经填好的有效路径，少点几层目录
                start = self._browser_pick_start(
                    str(dir_edit.getText() or ""),
                    [spider.download_output_dir]
                    + list(spider.scan_local_dirs or []))
                self._show_file_browser(
                    "选取扫描文件夹", start or spider._fs_service_prefix(), mode="dir",
                    on_pick=lambda v: (dir_edit.setText(str(v)),
                                       kit.toast("已选择：{}".format(v))),
                    manual_title="选取扫描文件夹",
                )

            kit.bind_click(btn_pick, do_pick_dir)
            kit.bind_click(btn_addd, do_add_dir)

            # ============ 4. 执行 ============
            def do_scan():
                sel_exts = sorted(state["on"])
                if not sel_exts:
                    kit.toast("请至少选择一种文件类型")
                    return
                dirs = selected_dirs_sorted()
                if not dirs:
                    kit.toast("请至少勾选一个文件夹")
                    return

                multi = (state["mode"] == "multi")
                base = str(name_edit.getText()).strip() or "我的影视"
                if not multi:
                    if not str(name_edit.getText()).strip():
                        base = "我的影视"
                        try:
                            name_edit.setText(base)
                        except Exception:
                            pass

                name_map = {}
                if multi:
                    names = getattr(spider, 'scan_dir_names', None) or {}
                    for i, d in enumerate(dirs):
                        nm = str(names.get(d) or "").strip()
                        if not nm:
                            nm = "{}_{}".format(base, i + 1)
                        name_map[d] = nm

                spider.scan_output_mode = state["mode"]
                spider.scan_output_name = base
                spider.scan_local_extensions = sel_exts
                spider._save_config_to_file()

                try:
                    made = spider._scan_local_files_and_generate(
                        dirs, mode=state["mode"], name_map=name_map,
                        base_name=base, exts=sel_exts,
                        dir_exts=dict(getattr(spider, 'scan_dir_exts', None) or {}))
                    kit.toast("扫描完成，已生成 {} 个接口".format(len(made)), long=True)
                    try:
                        if spider._dialog_refs:
                            spider._dialog_refs[-1].dismiss()
                    except Exception:
                        pass
                except Exception as e:
                    kit.toast("扫描失败: {}".format(e), long=True)

            paint_exts()
            refresh_mode()
            refresh_dir_list()

            buttons = [
                {"text": "扫描并生成", "style": "success",
                 "callback": do_scan, "dismiss": False},
                {"text": "关闭", "style": "secondary",
                 "callback": None, "dismiss": True},
            ]
            self._show_dialog(act, "本地爬虫程序管理", container, buttons,
                              height_ratio=0.92, scroll=True)

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

        map_base = os.path.join(self._work_subdir_base(), "map")
        os.makedirs(map_base, exist_ok=True)

        _exclude = self._scan_exclude_dirs()
        for root in selected_roots:
            if not os.path.isdir(root):
                continue
            try:
                if os.path.abspath(root) in _exclude:
                    self._log(f"跳过非接口目录: {root}", level='debug')
                    continue
            except Exception:
                pass
            try:
                for sub in os.listdir(root):
                    sub_path = os.path.join(root, sub)
                    if not os.path.isdir(sub_path):
                        continue
                    if sub in ("localized", "map", self.COLLECTION_DIR_NAME):
                        continue
                    try:
                        if os.path.abspath(sub_path) in _exclude:
                            continue
                    except Exception:
                        pass
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
                                        map_sub = os.path.join(map_base, sub)
                                        os.makedirs(map_sub, exist_ok=True)
                                        abs_json_path = os.path.join(map_sub, f)
                                        with open(abs_json_path, 'w', encoding='utf-8') as out:
                                            json.dump(abs_data, out, ensure_ascii=False, indent=2)
                                        json_files.append(abs_json_path)
                                        self._log(f"生成绝对路径 JSON: {abs_json_path}", level='debug')
                                    else:

                                        self._log(f"跳过非接口文件 {os.path.basename(full_path)}（缺少 sites 字段）", level='debug')
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

    # 这些字段的值可能是 JSON 字符串，其内部还可能藏着相对路径
    # （典型：ext 里的 filters: "./lib/douban.json"）
    _EMBEDDED_JSON_KEYS = ('ext', 'extend', 'filter', 'filters', 'config', 'parses')

    def _absolutize_local_paths(self, obj, base_dir, _key=None):
        if isinstance(obj, dict):
            return {k: self._absolutize_local_paths(v, base_dir, k)
                    for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._absolutize_local_paths(item, base_dir, _key)
                    for item in obj]
        elif isinstance(obj, str):
            # 先处理本身就是相对路径的情况
            if obj.startswith(('./', '../')):
                abs_path = os.path.abspath(os.path.join(base_dir, obj))
                return 'file://' + abs_path
            # 再处理「值是 JSON 字符串、内部含相对路径」的情况
            if _key and str(_key).lower() in self._EMBEDDED_JSON_KEYS:
                return self._absolutize_embedded_json(obj, base_dir)
            return obj
        else:
            return obj

    def _absolutize_embedded_json(self, raw, base_dir):
        """把 JSON 字符串内部的相对路径转成 file:// 绝对路径。

        解析失败（不是合法 JSON）则原样返回，绝不破坏原值。
        """
        txt = str(raw or "").strip()
        if not txt or txt[0] not in '{[':
            return raw
        try:
            data = json.loads(txt)
        except Exception:
            return raw
        changed = [False]

        def _walk(v):
            if isinstance(v, dict):
                return {k: _walk(x) for k, x in v.items()}
            if isinstance(v, list):
                return [_walk(x) for x in v]
            if isinstance(v, str) and v.startswith(('./', '../')):
                changed[0] = True
                return 'file://' + os.path.abspath(os.path.join(base_dir, v))
            return v

        try:
            new_data = _walk(data)
        except Exception:
            return raw
        if not changed[0]:
            return raw
        try:
            return json.dumps(new_data, ensure_ascii=False)
        except Exception:
            return raw

    def _get_localized_config_path(self, box_path):

        # [统一 map] 全局只保留「配置备份目录」下的这一个 map，
        # 不再在 download_output_dir 下另建 map（原先两处并存）
        map_dir = os.path.join(self._work_subdir_base(), "map")
        try:
            os.makedirs(map_dir, exist_ok=True)
        except Exception:
            pass
        abs_box = os.path.abspath(box_path)
        pkg_name = os.path.basename(os.path.dirname(abs_box)) or "未命名"
        map_sub = os.path.join(map_dir, pkg_name)
        os.makedirs(map_sub, exist_ok=True)
        target = os.path.join(map_sub, os.path.basename(abs_box))

        if os.path.exists(target):
            try:
                same = (os.path.getsize(target) == os.path.getsize(abs_box))
                if same:
                    with open(target, 'rb') as _a, open(abs_box, 'rb') as _b:
                        same = (_a.read() == _b.read())
            except Exception:
                same = False
            if not same:
                _h = hashlib.md5(abs_box.encode('utf-8')).hexdigest()[:8]
                _n, _e = os.path.splitext(os.path.basename(abs_box))
                target = os.path.join(map_sub, "%s_%s%s" % (_n, _h, _e))
        return target

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
            # 跳转同样以"新生成的代码"为准
            abs_path = os.path.abspath(file_path)
            try:
                for _it in (self.localized_interfaces or []):
                    if _it.get("dir_name") == name and (
                            os.path.abspath(str(file_path)) in
                            [os.path.abspath(str(x)) for x in (_it.get("json_files") or [])]
                            or os.path.abspath(str(_it.get("selected") or "")) ==
                            os.path.abspath(str(file_path))):
                        _gen = self._ensure_generated_json(_it, file_path)
                        if _gen:
                            abs_path = os.path.abspath(_gen)
                        break
            except Exception:
                pass
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

            # [FIX BUG-14] __file__ 可能不存在（exec 加载），改用 SELF_PATH 并加防护
            if self.inject_manager_site and SELF_PATH:
                _cfg_url = self._to_ext_config_url(self._manager_config_file())
                manager_site = {
                    "key": "local_package_manager",
                    "name": "⚙️ 本地包管理",
                    "type": 3,
                    "style": {"type": "list", "ratio": 1.43},
                    # api 与 config_file 同源拼接（同一目录下取脚本文件）
                    "api": self._manager_script_url(_cfg_url),
                    "ext": {"config_file": _cfg_url},
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
        # [FIX BUG-04] 支持 "parent@dir" 双段编码做联合匹配；
        # 兼容旧格式（仅 dir）。匹配失败时回退按目录名匹配（目录可能被移动）
        if '@' in encoded_dir:
            _enc_parent, _enc_dir = encoded_dir.split('@', 1)
            _want_parent = urllib.parse.unquote(_enc_parent)
            dir_name = urllib.parse.unquote(_enc_dir)
        else:
            _want_parent = None
            dir_name = urllib.parse.unquote(encoded_dir)
        item = None
        for i in self.localized_interfaces:
            if _want_parent is not None:
                if i.get("parent_dir", "") == _want_parent and i["dir_name"] == dir_name:
                    item = i
                    break
            elif i["dir_name"] == dir_name:
                item = i
                break
        if not item:
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

    def _is_under_map(self, path):

        try:
            ap = os.path.abspath(str(path or ""))
        except Exception:
            return False
        root = os.path.abspath(os.path.join(self._work_subdir_base() or "", "map"))
        try:
            return os.path.commonpath([ap, root]) == root
        except Exception:
            return False

    def _ensure_generated_json(self, info, json_path=None):
        """确保拿到"新生成的代码"（map 下绝对路径化后的 JSON），没有就现生成。

        规则：编辑 / 跳转一律以这份新代码为准，
        不再回退到解密文件或本地化原始文件。
        """
        try:
            cand = []
            if json_path:
                cand.append(json_path)
            if info.get("selected"):
                cand.append(info["selected"])
            cand.extend(list(info.get("json_files") or []))

            src = ""
            for c in cand:
                try:
                    if c and os.path.isfile(c) and not self._is_under_map(c):
                        src = os.path.abspath(c)
                        break
                except Exception:
                    continue
            if not src:
                real = self._real_source_json(info)
                if real and os.path.isfile(real) and not self._is_under_map(real):
                    src = os.path.abspath(real)
            if not src:
                return ""

            with open(src, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return src
            new_data = self._absolutize_local_paths(data, os.path.dirname(src))

            # [map 去重] 已生成过的新代码直接复用，避免同一文件再造出
            # 一份带 hash 后缀的副本（_get_localized_config_path 的防冲突逻辑）
            try:
                std = os.path.join(
                    os.path.join(self._work_subdir_base(), "map"),
                    os.path.basename(os.path.dirname(src)),
                    os.path.basename(src))
                if os.path.isfile(std):
                    with open(std, 'r', encoding='utf-8') as f:
                        old = json.load(f)
                    # 只有内容与「源文件绝对路径化后」完全一致才复用，
                    # 否则源文件已被改动，必须重新生成，避免编辑到过期副本
                    if isinstance(old, dict) and old == new_data:
                        try:
                            info["selected"] = std
                        except Exception:
                            pass
                        return std
            except Exception:
                pass

            tgt = self._get_localized_config_path(src)
            d = os.path.dirname(tgt)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(tgt, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, ensure_ascii=False, indent=2)

            # 同步登记，保证后续编辑 / 跳转都命中同一份新代码
            try:
                info["selected"] = tgt
                files = list(info.get("json_files") or [])
                if tgt not in files:
                    files.append(tgt)
                    info["json_files"] = files
                self._save_config_to_file()
            except Exception:
                pass
            self._log("已生成新代码: {} -> {}".format(src, tgt), level='debug')
            return tgt
        except Exception as e:
            self._log("生成新代码失败: {}".format(e))
            return ""

    def _real_source_json(self, info):

        selected = (info or {}).get('selected', '') or ''
        if not selected:
            return selected
        try:
            out_dir = os.path.abspath(self._work_subdir_base() or "")
            map_root = os.path.join(out_dir, 'map')
            abs_sel = os.path.abspath(selected)
            if out_dir and abs_sel.startswith(map_root + os.sep):
                rel = os.path.relpath(abs_sel, map_root)
                real = os.path.join(info.get('parent_dir', ''), rel)
                if os.path.exists(real):
                    return real
        except Exception:
            pass
        return selected

    # ==================== 接口改装中心（收藏片段）====================
    #
    # 数据模型 self.favorite_fragments = [
    #   {"id", "name", "cat"(py/js/jar/other/live), "group"(sites/lives),
    #    "api"(去重用), "src"(来源接口), "enabled"(生成时是否输出),
    #    "body"(片段原始 dict)} , ...]
    #
    # 分类（互斥，只基于 sites；lives 全部汇总进 [live]）：
    #   含 jar -> [jar]（最高优先级，即使爬虫文件是 .py 也只归 jar）
    #   .py -> [py]   .js -> [js]   其余 -> [其他]
    #
    # 生成规则：本地包目录/<名称>/<名称>.json
    #           不建 爬虫程序 / 我的收藏 / map，不写宫格数据，靠「扫描本地接口」收录

    def _fav_listeners(self):

        ls = getattr(self, "_fav_listeners_cache", None)
        if not isinstance(ls, list):
            ls = []
            self._fav_listeners_cache = ls
        return ls

    def _fav_on_change(self, cb):

        try:
            ls = self._fav_listeners()
            if cb not in ls:
                ls.append(cb)
        except Exception:
            pass

    def _fav_off_change(self, cb):

        try:
            ls = self._fav_listeners()
            if cb in ls:
                ls.remove(cb)
        except Exception:
            pass

    def _fav_emit(self):

        for cb in list(self._fav_listeners()):
            try:
                cb()
            except Exception:
                pass

    def _favorite_fragments_all(self):

        v = getattr(self, 'favorite_fragments', None)
        return v if isinstance(v, list) else []

    def _load_favorite_fragments(self):
        raw = None
        try:
            if isinstance(self.config, dict) and \
                    isinstance(self.config.get('favorite_fragments'), list):
                raw = self.config.get('favorite_fragments')
        except Exception:
            raw = None
        if raw is None:
            try:
                if os.path.exists(PERSISTENT_CONFIG_PATH):
                    with open(PERSISTENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    raw = data.get('favorite_fragments') or data.get('收藏片段')
            except Exception as e:
                self._log("加载收藏片段失败: {}".format(e))
        items = []
        for it in (raw or []):
            if not isinstance(it, dict):
                continue
            body = it.get("body")
            if not isinstance(body, dict):
                continue
            frag = {
                "id": str(it.get("id") or ""),
                "name": str(it.get("name") or "未命名"),
                "cat": str(it.get("cat") or "other"),
                "group": "lives" if str(it.get("group")) == "lives" else "sites",
                "api": str(it.get("api") or ""),
                "src": str(it.get("src") or ""),
                "enabled": self._as_bool(it.get("enabled"), True),
                "body": body,
            }
            if not frag["id"]:
                frag["id"] = hashlib.md5(
                    (frag["api"] or frag["name"]).encode("utf-8")).hexdigest()[:12]
            frag["cat"] = self._frag_category(frag["body"], frag["group"])
            frag["api"] = self._frag_api_value(frag["body"])
            items.append(frag)
        self.favorite_fragments = items

    # ---------- 生成历史记录 ----------

    FAV_HISTORY_LIMIT = 20

    def _fav_history_all(self):
        v = getattr(self, 'fav_history', None)
        return v if isinstance(v, list) else []

    def _fav_history_add(self, name, frags):
        """生成成功后存档：只存片段数据，不存接口文件"""
        import time as _t
        rec = {
            "id": "h%s" % int(_t.time() * 1000),
            "name": str(name or ""),
            "time": _t.strftime("%m-%d %H:%M"),
            "count": len(frags),
            "frags": [copy.deepcopy(f) for f in frags],
        }
        try:
            hist = self._fav_history_all()
            hist.insert(0, rec)
            del hist[self.FAV_HISTORY_LIMIT:]
            self.fav_history = hist
            self._fav_save()
        except Exception as e:
            self._log("保存生成历史失败: {}".format(e))
        return rec

    def _fav_history_remove(self, rid):
        try:
            self.fav_history = [r for r in self._fav_history_all()
                                if str(r.get("id")) != str(rid)]
            self._fav_save()
        except Exception:
            pass

    def _fav_history_load(self, rid):
        """把某条历史记录的片段加载回收藏（追加，不去重覆盖已有）"""
        for r in self._fav_history_all():
            if str(r.get("id")) == str(rid):
                frags = r.get("frags") or []
                added, skipped = self._fav_add_fragments(
                    frags, str(r.get("name") or "历史"))
                return added, skipped, len(frags)
        return 0, 0, 0

    def _fav_save(self, async_=True):
        """保存收藏配置。

        [性能] 单次 _save_config_to_file 实测 ~600ms（写 3 份配置 + 镜像备份）。
        勾选一个开关就写一次，连续操作会直接卡死主线程，
        表现为"点了没反应、开关不更新"。
        因此默认改为合并延迟写：多次改动只落盘一次。
        关键节点（生成接口、关闭弹窗）用 async_=False 立即同步写。
        """
        if not async_:
            self._fav_flush_pending = False
            self._save_config_to_file()
            return
        try:
            import threading
            lock = getattr(self, "_fav_flush_lock", None)
            if lock is None:
                lock = threading.Lock()
                self._fav_flush_lock = lock
            with lock:
                self._fav_flush_pending = True
                t = getattr(self, "_fav_flush_timer", None)
                if t is not None and t.is_alive():
                    return       # 已有定时器在等待，本次改动被合并进去
            def _worker():
                try:
                    import time as _tm
                    _tm.sleep(0.35)
                except Exception:
                    pass
                try:
                    with lock:
                        if not getattr(self, "_fav_flush_pending", False):
                            return
                        self._fav_flush_pending = False
                except Exception:
                    pass
                try:
                    self._save_config_to_file()
                except Exception:
                    pass
            th = threading.Thread(target=_worker)
            th.daemon = True
            self._fav_flush_timer = th
            th.start()
        except Exception:
            self._save_config_to_file()

    def _force_mirror_now(self):
        """立刻把配置镜像到备份目录（清除缓存 / 生成接口等关键节点调用）。

        普通保存走 30s 节流以保性能；只有这些节点必须确保备份是最新的，
        否则用户清完缓存、或刚生成的接口配置，备份目录还停留在旧版本。
        """
        try:
            snapshot = self._snapshot_config(include_runtime=True)
            self._mirror_config_to_backup(snapshot, force=True)
            return True
        except Exception as e:
            self._log(f"强制镜像失败: {e}", level='error')
            return False

    def _fav_flush_now(self):
        """立即落盘（生成接口、弹窗关闭等关键节点调用）。

        除了同步写主配置，还必须强制镜像到备份目录：
        普通镜像走 30s 节流，关键节点若被节流掉，备份目录会停留在旧版本，
        用户刚生成的接口历史在重启后就找不回来了。
        """
        try:
            self._fav_flush_pending = False
        except Exception:
            pass
        try:
            self._save_config_to_file()
        except Exception:
            pass
        try:
            self._force_mirror_now()
        except Exception:
            pass

    # ---------- 片段判定工具 ----------

    @staticmethod
    def _frag_api_value(body):
        if not isinstance(body, dict):
            return ""
        for k in ("api", "url"):
            v = body.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    @staticmethod
    def _frag_name(body, idx=0):
        if isinstance(body, dict):
            for k in ("name", "title"):
                v = body.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
        return "片段%d" % (idx + 1)

    @classmethod
    def _frag_category(cls, body, group):
        if group == "lives":
            return "live"
        if not isinstance(body, dict):
            return "other"
        # jar 优先级最高，与 py/js/其他 互斥（含 jar 的片段不会再出现在 [PY]）
        if str(body.get("jar") or "").strip():
            return "jar"
        api = cls._frag_api_value(body)
        ext = os.path.splitext(api.split("?")[0].split("#")[0])[1].lower()
        if ext == ".py":
            return "py"
        if ext == ".js":
            return "js"
        return "other"

    @classmethod
    def _frag_dedup_key(cls, body):
        """判重键 = api/url + ext + jar 三者组合。

        很多不同接口片段共用同一个 url/api，只按 url 判重会误杀大量可用片段；
        因此要求三个参数全部相同才视为同一条。
        三者皆空时退化为内容指纹（兜底，避免空片段互相覆盖）。
        """
        body = body if isinstance(body, dict) else {}

        def _norm(v):
            return str(v or "").strip()

        api = _norm(cls._frag_api_value(body)).split("#")[0].strip().rstrip("/").lower()
        ext = _norm(body.get("ext"))
        jar = _norm(body.get("jar"))

        if not (api or ext or jar):
            try:
                return "c:" + hashlib.md5(
                    json.dumps(body, ensure_ascii=False, sort_keys=True)
                    .encode("utf-8")).hexdigest()
            except Exception:
                return "c:" + hashlib.md5(str(body).encode("utf-8")).hexdigest()

        raw = "\x1f".join((api, ext, jar))
        return "k:" + hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _frag_dedup_detail(cls, body):
        """返回判重三元组，便于提示用户「为什么算重复」"""
        body = body if isinstance(body, dict) else {}
        api = str(cls._frag_api_value(body)).strip().split("#")[0].strip().rstrip("/")
        return {"api": api, "ext": str(body.get("ext") or "").strip(),
                "jar": str(body.get("jar") or "").strip()}

    def _frag_needs_jar(self, body):
        """仅当 api 是"裸字符串"（非有效相对/绝对/本地/远程文件、非文件性质 url）才补 jar。
        片段自带 jar 的一律沿用既有值，绝不覆盖。"""
        api = self._frag_api_value(body)
        if not api:
            return False
        if str((body or {}).get("jar") or "").strip():
            return False
        if api.startswith(("./", "../", "/")):
            return False
        low = api.lower()
        if low.startswith(("http://", "https://", "file://", "assets://", "proxy://")):
            return False
        if SCHEME_RE.match(api):
            return False
        ext = os.path.splitext(api.split("?")[0].split("#")[0])[1].lower()
        if ext and ext in DOWNLOAD_EXTS:
            return False
        return True

    @staticmethod
    def _frag_apply_jar(body, spider_value, base_dir):
        """补 jar；spider 为相对地址时按本地化接口所在目录换算成绝对地址"""
        sp = str(spider_value or "").strip()
        if not sp:
            return False
        if not (sp.startswith("/") or SCHEME_RE.match(sp)):
            sp = "file://" + os.path.abspath(os.path.join(base_dir or "", sp))
        body["jar"] = sp
        return True

    def _fav_base_dir(self, info, json_path):
        """片段内相对路径的基准目录：优先本地包目录（与扫描本地接口的路径处理一致）"""
        try:
            p = os.path.join(info.get("parent_dir", "") or "",
                             info.get("dir_name", "") or "")
            if p and os.path.isdir(p):
                return os.path.abspath(p)
        except Exception:
            pass
        return os.path.dirname(os.path.abspath(json_path or ""))

    def _fav_decrypt_suffix(self):
        tpl = str(getattr(self, 'decrypt_filename_template', '{name}_m.json')
                  or '{name}_m.json')
        m = re.match(r'^\{name\}(.*?)\.json$', tpl.strip(), re.I)
        return m.group(1) if m else '_m'

    def _fav_json_candidates(self, info):
        """某接口可选的数据源文件：[(label, filename, abspath)]，本地接口 / 解密接口"""
        files = []
        seen = set()

        def add(p):
            try:
                ap = os.path.abspath(p)
            except Exception:
                return
            # [规则] 跳过以 . 开头的隐藏文件（.localize_manifest.json 等）
            if os.path.basename(ap).startswith('.'):
                return
            if os.path.isfile(ap) and ap not in seen and not self._is_under_map(ap):
                seen.add(ap)
                files.append(ap)

        for f in (info.get("json_files") or []):
            add(f)
        add(info.get("selected") or "")
        try:
            p = os.path.join(info.get("parent_dir", "") or "",
                             info.get("dir_name", "") or "")
            if os.path.isdir(p):
                for n in sorted(os.listdir(p)):
                    if n.startswith('.'):
                        continue
                    if n.lower().endswith(".json"):
                        add(os.path.join(p, n))
        except Exception:
            pass

        suf = self._fav_decrypt_suffix()
        out = []
        for fp in files:
            stem = os.path.splitext(os.path.basename(fp))[0]
            label = "解密接口" if (suf and stem.endswith(suf)) else "本地接口"
            out.append((label, os.path.basename(fp), fp))
        # 本地接口排前面：默认使用本地化接口代码
        out.sort(key=lambda x: (0 if x[0] == "本地接口" else 1, x[1]))
        return out

    def _fav_extract_fragments(self, json_path, base_dir, spider_value=None):
        """从接口 json 抽取 sites / lives 片段（其余参数一律不提取；
        spider 只是公共参数，仅在补 jar 时使用）。"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return []
        sp = data.get("spider")
        if not isinstance(sp, str):
            sp = spider_value
        frag_dir = base_dir or os.path.dirname(os.path.abspath(json_path))
        out = []
        for group in ("sites", "lives"):
            arr = data.get(group)
            if not isinstance(arr, list):
                continue
            for i, item in enumerate(arr):
                if not isinstance(item, dict):
                    continue
                if str(item.get("key") or "") == "local_package_manager":
                    continue
                body = self._absolutize_local_paths(copy.deepcopy(item), frag_dir)
                # lives 下的片段同样套用 jar 补全规则
                if self._frag_needs_jar(body):
                    self._frag_apply_jar(body, sp, frag_dir)
                out.append({
                    "group": group,
                    "cat": self._frag_category(body, group),
                    "name": self._frag_name(body, i),
                    "api": self._frag_api_value(body),
                    "body": body,
                })
        return out

    # ---------- 通用 UI 组件（复用现有 UIKit 主题）----------

    @staticmethod
    def _bind_text_changed(kit, edit, cb):
        try:
            from java import jclass, dynamic_proxy
            TW = jclass("android.text.TextWatcher")

            class _W(dynamic_proxy(TW)):
                def __init__(self, fn):
                    super().__init__()
                    self.fn = fn

                def beforeTextChanged(self, s, start, count, after):
                    pass

                def onTextChanged(self, s, start, before, count):
                    pass

                def afterTextChanged(self, s):
                    try:
                        txt = s.toString() if hasattr(s, "toString") else str(s)
                    except Exception:
                        txt = ""
                    try:
                        self.fn(txt or "")
                    except Exception:
                        pass

            w = _W(cb)
            try:
                kit.sink.append(w)
            except Exception:
                pass
            edit.addTextChangedListener(w)
            return True
        except Exception:
            return False

    def _ui_search_box(self, kit, on_changed, hint="搜索名称 / 地址", value=""):
        row = kit.hbox()
        row.setLayoutParams(kit.lp(-1, -2))
        edit = kit.input(hint=hint, value=value)
        edit.setLayoutParams(kit.lp(0, -2, 1.0))
        row.addView(edit)
        btn = kit.button("🔍", "secondary", None, size="sm")
        btn.setLayoutParams(kit.lp(kit.dp(UITheme.H_BTN_SM + 10),
                                   kit.dp(UITheme.H_BTN_SM), 0.0,
                                   (kit.dp(UITheme.S_XS), 0.0, 0.0, 0.0)))
        kit.bind_click(btn, lambda: on_changed(str(edit.getText() or "")))
        row.addView(btn)
        self._bind_text_changed(kit, edit, on_changed)
        return row, edit

    def _ui_chip_row(self, kit, entries, state, key="cur", on_change=None):
        """单行等宽切换芯片（分类 / 数据源 / 模式），原地改背景不重建，杜绝高度抖动"""
        row = kit.hbox()
        row.setLayoutParams(kit.lp(-1, -2))
        btns = {}

        def paint():
            for k, b in btns.items():
                sel = (state.get(key) == k)
                style = "primary" if sel else "secondary"
                try:
                    bg_c, tx_c, line_c, press_c = UITheme.STYLES.get(
                        style, UITheme.STYLES["secondary"])
                    b.setTextColor(kit.color(tx_c))
                    kit._set_bg(b, kit.pressable(bg_c, press_c,
                                                 UITheme.R_SM, 1.0, line_c))
                except Exception:
                    pass

        for k, label in entries:
            b = kit.button(label, "secondary", None, size="sm")
            try:
                b.setMinimumWidth(0)
                b.setMinWidth(0)
                b.setPadding(kit.dp(2), 0, kit.dp(2), 0)
                b.setSingleLine(True)
            except Exception:
                pass

            def make_cb(kk=k):
                def cb():
                    if state.get(key) == kk:
                        return
                    state[key] = kk
                    paint()
                    if on_change:
                        on_change(kk)
                return cb

            kit.bind_click(b, make_cb())
            btns[k] = b
            lp = kit.lp(0, kit.dp(UITheme.H_BTN_SM), 1.0)
            lp.setMargins(kit.dp(UITheme.S_XXS), 0, kit.dp(UITheme.S_XXS), 0)
            row.addView(b, lp)
        paint()
        return row

    def _compact_button_bar(self, kit, specs, size="sm", per_row=None,
                            gap=UITheme.S_XXS):
        """把 button_bar 子按钮最小宽度清零，保证 4~5 个按钮也能压在一行"""
        bar = kit.button_bar(specs, size=size, per_row=per_row, gap=gap)
        if bar is None:
            return None
        try:
            for r in range(bar.getChildCount()):
                rowv = bar.getChildAt(r)
                if rowv is None:
                    continue
                for c in range(rowv.getChildCount()):
                    b = rowv.getChildAt(c)
                    try:
                        b.setMinimumWidth(0)
                        b.setMinWidth(0)
                        b.setPadding(kit.dp(2), 0, kit.dp(2), 0)
                        b.setSingleLine(True)
                    except Exception:
                        pass
        except Exception:
            pass
        return bar

    def _ui_fixed_scroll(self, kit, rows=6, ratio=0.34, row_h_dp=None):
        """定高滚动列表：切换分类 / 搜索 / 增删时高度恒定，不抖动不闪烁。

        ratio: 列表区最多占屏幕高度的比例，保证底部按钮永远在屏幕内。
        """
        if row_h_dp is None:
            row_h_dp, _ = kit.row_metrics()
            row_h_dp = row_h_dp * 2.35
        h_dp = row_h_dp * max(2, int(rows))
        try:
            cap = float(getattr(kit, "h_dp", 0) or 0) * float(ratio)
            if cap > 0:
                h_dp = min(h_dp, cap)
        except Exception:
            pass
        list_box = kit.vbox()
        list_box.setLayoutParams(kit.lp(-1, -2))
        h_px = kit.dp(max(kit.dp(80), h_dp))
        try:
            list_box.setMinimumHeight(h_px)
        except Exception:
            pass
        scroller = kit.scroll(list_box)
        try:
            scroller.setMinimumHeight(h_px)
            scroller.setFillViewport(True)
        except Exception:
            pass
        return scroller, list_box

    def _fav_visible(self, state):
        """按当前分类 + 搜索词过滤"""
        kw = str(state.get("kw") or "").strip().lower()
        cat = state.get("cat") or "all"
        out = []
        for frag in self._favorite_fragments_all():
            if cat != "all" and frag.get("cat") != cat:
                continue
            if kw:
                hay = " ".join([
                    str(frag.get("name") or ""),
                    str(frag.get("api") or ""),
                    str(frag.get("src") or ""),
                ]).lower()
                if kw not in hay:
                    continue
            out.append(frag)
        return out

    @staticmethod
    def _fav_cat_summary(frags):
        c = {}
        for f in frags:
            k = f.get("cat", "other")
            c[k] = c.get(k, 0) + 1
        return c

    def _fav_ensure_clickable(self, buttons, holder):
        """兜底：任何 callback 为空的按钮都补上"关掉当前弹窗"。

        之前有几个按钮写成了 callback=None + dismiss=False，
        结果既没回调也不关闭，点上去毫无反应，
        用户会以为"要按两次"或"像 TV 模式要先聚焦"。
        """
        if not buttons:
            return buttons
        out = []
        for spec in buttons:
            try:
                if not isinstance(spec, dict):
                    out.append(spec)
                    continue
                if spec.get("callback") is None and not spec.get("dismiss"):
                    spec = dict(spec)

                    def _close(_s=spec):
                        try:
                            d = holder.get("d")
                            if d is not None:
                                d.dismiss()
                        except Exception:
                            pass
                    spec["callback"] = _close
            except Exception:
                pass
            out.append(spec)
        return out

    def _fav_dialog(self, act, title, container, buttons, holder,
                    height_ratio=0.92, scroll=False):
        """统一弹窗出口：按钮全部 dismiss=False，由回调显式关掉自己，
        避免二级/三级弹窗的关闭误伤一级弹窗。

        scroll=True 时外层可整体滚动，保证小屏下底部按钮一定能够到。
        """
        try:
            buttons = self._fav_ensure_clickable(buttons, holder)
        except Exception:
            pass
        d = self._show_dialog(act, title, container, buttons,
                              height_ratio=height_ratio, scroll=scroll)
        try:
            holder["d"] = d
        except Exception:
            pass
        return d

    # ---------- 接口改装中心主弹窗 ----------

    def _open_favorite_manage_dialog(self):

        def on_ui(act):
            kit = self._kit(act)
            holder = {}
            state = {"cat": "all", "kw": ""}
            sw_refs = {}

            def on_changed():
                refresh_count()
                refresh_list()

            self._fav_on_change(on_changed)

            def do_clear_all():
                if not self._favorite_fragments_all():
                    kit.toast("收藏是空的")
                    return

                def _yes():
                    try:
                        del self.favorite_fragments[:]
                    except Exception:
                        self.favorite_fragments = []
                    self._fav_save()
                    self._fav_emit()

                self._show_modern_confirm(
                    "清空收藏",
                    "确定清空全部 {} 条收藏片段？".format(
                        len(self._favorite_fragments_all())), _yes)

            container = kit.vbox()
            container.setLayoutParams(kit.lp(-1, -2))

            # ---- 分类一行 6 键 + 搜索（放最上面，列表优先占空间）----
            filter_card = kit.card()
            cat_entries = [(k, lbl) for k, lbl in self.FRAG_CATS]
            filter_card.addView(
                self._ui_chip_row(kit, cat_entries, state, "cat",
                                  on_change=lambda k: on_changed()),
                kit.lp(-1, -2))
            srow, _se = self._ui_search_box(
                kit, lambda t: (state.__setitem__("kw", t), on_changed()))
            filter_card.addView(srow,
                                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XS, 0.0, 0.0)))

            count_label = kit.text("", size=UITheme.FS_CAPTION,
                                   color=UITheme.TEXT_3, max_lines=2)
            filter_card.addView(count_label,
                                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XXS, 0.0, 0.0)))
            container.addView(filter_card, kit.lp(-1, -2))

            # ---- 定高列表（主体，占最大空间）----
            list_card = kit.card()
            scroller, list_box = self._ui_fixed_scroll(kit, rows=6, ratio=0.42)
            list_card.addView(scroller, kit.lp(-1, -2))
            # [要求] 全选 / 反选 / 清空 紧跟列表下方，只作用于当前筛选出来的数据
            list_card.addView(
                self._compact_button_bar(kit, [
                    {"text": "全选", "style": "secondary",
                     "callback": lambda: _batch(True), "dismiss": False},
                    {"text": "反选", "style": "secondary",
                     "callback": lambda: _batch(None), "dismiss": False},
                    {"text": "清空", "style": "secondary",
                     "callback": lambda: _batch(False), "dismiss": False},
                    {"text": "删除", "style": "soft_danger",
                     "callback": lambda: _batch_delete(), "dismiss": False},
                ], size="sm", per_row=4),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XS, 0.0, 0.0)))
            container.addView(list_card, kit.lp(-1, -2))

            # ---- 操作区（放下面，方便操作上面的列表）----
            container.addView(
                self._compact_button_bar(kit, [
                    {"text": "➕ 添加片段", "style": "primary",
                     "callback": lambda: self._open_fav_source_dialog(),
                     "dismiss": False},
                    {"text": "📜 历史", "style": "secondary",
                     "callback": lambda: self._open_fav_history_dialog(),
                     "dismiss": False},
                    {"text": "🗑 清空", "style": "soft_danger",
                     "callback": do_clear_all, "dismiss": False},
                ], size="sm", per_row=3),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))

            def _find_card(frag):
                """按 view 树反查卡片（sw_refs 失效时的兜底）"""
                try:
                    for _i in range(list_box.getChildCount()):
                        _v = list_box.getChildAt(_i)
                        if getattr(_v, "_frag", None) is frag:
                            return _v
                except Exception:
                    pass
                return None

            def _sync_switches(frags):
                """批量操作后把开关 + 标题灰度同步到数据状态。

                [修复] 之前直接 sw.setChecked 会触发 onCheckedChanged 回调，
                40 个开关就是 40 次回调、40 次写盘（每次约 600ms），
                主线程被卡死十几秒 —— 表现就是"点了全选，开关没反应"。
                现在改为静默设置（临时摘除 listener）+ 遍历 view 树兜底。
                """
                for f in frags:
                    ref = sw_refs.get(id(f))
                    sw = tv = None
                    if ref:
                        sw, tv = ref.get("switch"), ref.get("title")
                    if sw is None:
                        card = _find_card(f)
                        if card is not None:
                            sw = getattr(card, "_switch", None)
                            tv = getattr(card, "_title_view", None)
                    if sw is None:
                        continue
                    on = bool(f.get("enabled", True))
                    try:
                        kit.set_switch_quietly(sw, on)
                    except Exception:
                        pass
                    # 同步标题灰度（未勾选=灰），否则开关变了字还是灰的
                    try:
                        if tv is not None:
                            tv.setTextColor(
                                kit.color(UITheme.TEXT if on else UITheme.TEXT_3))
                    except Exception:
                        pass

            def _batch(mode):
                """mode=True 全选 / False 全不选 / None 反选；只作用于当前分类可见项"""
                vis = self._fav_visible(state)
                if not vis:
                    kit.toast("当前分类下没有片段")
                    return
                for f in vis:
                    if mode is None:
                        f["enabled"] = not bool(f.get("enabled", True))
                    else:
                        f["enabled"] = bool(mode)
                self._fav_save()
                _sync_switches(vis)
                refresh_count()

            def _batch_delete():
                """批量删除：移除当前筛选下所有已勾选的片段"""
                vis = self._fav_visible(state)
                sel = [f for f in vis if f.get("enabled", True)]
                if not sel:
                    kit.toast("没有勾选任何片段")
                    return

                def _yes():
                    kill = set(id(f) for f in sel)
                    try:
                        self.favorite_fragments = [
                            f for f in self._favorite_fragments_all()
                            if id(f) not in kill]
                    except Exception:
                        pass
                    self._fav_save()
                    self._fav_emit()
                    # 删除必须立刻重建列表，否则界面还留着已删掉的卡片
                    refresh_list()
                    refresh_count()
                    kit.toast("已删除 {} 个片段".format(len(sel)))

                self._show_modern_confirm(
                    "删除片段",
                    "确定删除当前分类下勾选的 {} 个片段？".format(len(sel)), _yes)

            def refresh_count():
                vis = self._fav_visible(state)
                sel = len([f for f in vis if f.get("enabled", True)])
                c = self._fav_cat_summary(self._favorite_fragments_all())
                detail = "  ".join(
                    "{}:{}".format(self.FRAG_CAT_LABEL.get(k, k), v)
                    for k, v in c.items())
                try:
                    count_label.setText(
                        "当前分类 {} 条，已选 {} 条 ｜ 全部 {} 条（{}）".format(
                            len(vis), sel, len(self._favorite_fragments_all()),
                            detail or "空"))
                except Exception:
                    pass

            def make_card(frag):
                cat = frag.get("cat", "other")
                sub = "[{}] {}".format(self.FRAG_CAT_LABEL.get(cat, cat),
                                       frag.get("src") or "")
                api = frag.get("api") or ""
                if api:
                    sub += "\n{}".format(_short_url(api, 44))
                if frag.get("body", {}).get("jar"):
                    sub += "\njar: {}".format(_short_url(
                        str(frag["body"].get("jar")), 36))

                def on_toggle(v):
                    frag["enabled"] = bool(v)
                    self._fav_save()
                    refresh_count()

                def do_up():
                    items = self._favorite_fragments_all()
                    if frag not in items:
                        return
                    i = items.index(frag)
                    if i <= 0:
                        kit.toast("已经在最前面")
                        return
                    items[i - 1], items[i] = items[i], items[i - 1]
                    self._fav_save()
                    refresh_list()

                def do_down():
                    items = self._favorite_fragments_all()
                    if frag not in items:
                        return
                    i = items.index(frag)
                    if i >= len(items) - 1:
                        kit.toast("已经在最后面")
                        return
                    items[i + 1], items[i] = items[i], items[i + 1]
                    self._fav_save()
                    refresh_list()

                def do_rename():
                    def _save(v):
                        v = str(v or "").strip()
                        if v:
                            frag["name"] = v
                            # [修复 BUG-07] 改名要同步写回片段代码里的 name，
                            # 否则前端显示改了、生成的接口代码还是旧名字
                            body = frag.get("body")
                            if isinstance(body, dict) and isinstance(
                                    body.get("name"), str):
                                body["name"] = v
                            self._fav_save()
                            self._fav_emit()
                            refresh_list()
                    self._show_modern_input(
                        "改名片段", "输入新的片段名称",
                        frag.get("name") or "", _save)

                def do_edit():
                    self._fav_edit_fragment(frag)

                def do_remove():
                    def _yes():
                        try:
                            self.favorite_fragments.remove(frag)
                        except ValueError:
                            pass
                        self._fav_save()
                        self._fav_emit()
                    self._show_modern_confirm(
                        "移除片段",
                        "确定移除「{}」？".format(frag.get("name") or ""), _yes)

                def do_proxy():
                    """注代：在当前片段代码里写入 proxy 字段（地址可改）"""
                    body = frag.get("body")
                    cur = ""
                    if isinstance(body, dict):
                        cur = str(body.get("proxy") or "").strip()
                    if not cur:
                        cur = self.FRAG_PROXY_DEFAULT

                    def _save(v):
                        v = str(v or "").strip()
                        if not v:
                            kit.toast("已取消")
                            return
                        b = frag.get("body")
                        if not isinstance(b, dict):
                            b = {}
                            frag["body"] = b
                        b["proxy"] = v
                        self._fav_save()
                        self._fav_emit()
                        refresh_list()
                        kit.toast("已注代：{}".format(v), long=True)

                    self._show_modern_input(
                        "注代 - {}".format(frag.get("name") or ""),
                        "确认或修改为你的代理地址", cur, _save)

                actions = [
                    {"text": "↑", "style": "secondary", "callback": do_up, "dismiss": False},
                    {"text": "↓", "style": "secondary", "callback": do_down, "dismiss": False},
                    {"text": "改名", "style": "secondary", "callback": do_rename, "dismiss": False},
                    {"text": "编辑", "style": "soft_brand", "callback": do_edit, "dismiss": False},
                    {"text": "注代", "style": "primary", "callback": do_proxy, "dismiss": False},
                    {"text": "移除", "style": "soft_danger", "callback": do_remove, "dismiss": False},
                ]
                _ref = {}
                card = self._ui_site_card(
                    kit,
                    frag.get("name") or "未命名",
                    sub,
                    frag.get("enabled", True), on_toggle, actions,
                    dim=not frag.get("enabled", True), per_row=5,
                    state_out=_ref)
                sw_refs[id(frag)] = _ref
                try:
                    card._frag = frag
                except Exception:
                    pass
                return card

            def refresh_list():
                sw_refs.clear()
                list_box.removeAllViews()
                vis = self._fav_visible(state)
                if not vis:
                    tip = ("当前分类下没有收藏片段\n点「➕ 添加收藏片段」从本地接口里挑"
                           if self._favorite_fragments_all() else
                           "还没有收藏片段\n点「➕ 添加收藏片段」从本地接口里挑")
                    list_box.addView(kit.empty(tip), kit.lp(-1, -2))
                    kit.fill_spring(list_box, 0)
                    return
                for frag in vis:
                    list_box.addView(make_card(frag),
                                     kit.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_XS)))
                kit.fill_spring(list_box, 0)

            def do_generate():
                sel = [f for f in self._fav_visible(state) if f.get("enabled", True)]
                if not sel:
                    kit.toast("当前分类下没有勾选的片段")
                    return
                self._fav_ask_name(
                    "生成改装接口", "我的专属",
                    lambda name: self._fav_generate(sel, name, kit))

            def on_close():
                self._fav_off_change(on_changed)
                try:
                    holder["d"].dismiss()
                except Exception:
                    pass

            refresh_count()
            refresh_list()

            buttons = [
                {"text": "生成并保存", "style": "success",
                 "callback": do_generate, "dismiss": False},
                {"text": "关闭", "style": "secondary",
                 "callback": on_close, "dismiss": False},
            ]
            self._fav_dialog(act, "🔖 接口改装中心", container, buttons, holder,
                             height_ratio=0.92, scroll=True)

        self._run_on_ui(on_ui)

    # ---------- 选择来源接口（本地包列表）----------

    def _open_fav_source_dialog(self):

        def on_ui(act):
            kit = self._kit(act)
            holder = {}
            state = {"kw": ""}

            container = kit.vbox()
            container.setLayoutParams(kit.lp(-1, -2))

            card = kit.card()
            card.addView(
                kit.section_title("📥 选择来源接口"),
                kit.lp(-1, -2))
            srow, _se = self._ui_search_box(
                kit, lambda t: (state.__setitem__("kw", t), refresh()),
                hint="搜索本地接口")
            card.addView(srow, kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))

            scroller, list_box = self._ui_fixed_scroll(kit, rows=7, ratio=0.38)
            card.addView(scroller,
                         kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))
            container.addView(card, kit.lp(-1, -2))

            def infos():
                kw = str(state.get("kw") or "").strip().lower()
                out = []
                for i in (self.localized_interfaces or []):
                    if i.get("hidden", False):
                        continue
                    if kw and kw not in str(i.get("dir_name") or "").lower() \
                            and kw not in str(i.get("parent_dir") or "").lower():
                        continue
                    out.append(i)
                return out

            def make_card(info):
                name = str(info.get("dir_name") or "未命名")
                cands = self._fav_json_candidates(info)
                src = cands[0][0] if cands else "无可用数据"
                sub = "{}\nJSON {} 个 · 当前数据源 {}".format(
                    info.get("parent_dir", ""),
                    len(info.get("json_files") or []), src)

                def do_manage():
                    self._open_frag_picker_dialog(info)

                def do_edit_code():
                    # 编辑"第 3 条处理过的完整代码"（绝对路径化后的新代码）
                    path = self._ensure_generated_json(info)
                    if not path:
                        kit.toast("该接口没有可用的 JSON 文件", long=True)
                        return
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            content = f.read()
                    except Exception as e:
                        kit.toast("读取失败: {}".format(e), long=True)
                        return

                    def on_saved():
                        kit.toast("已保存，收藏片段将基于修改后的代码", long=True)

                    self._show_modern_text_editor(
                        "✏️ 编辑接口代码 - {}".format(name), content, path, "",
                        "file://" + os.path.abspath(path), on_saved,
                        url_label="接口U")

                def do_switch_src():
                    cands2 = self._fav_json_candidates(info)
                    if not cands2:
                        kit.toast("该接口没有可用的 JSON 文件")
                        return
                    options = [(c[2], "{}（{}）".format(c[0], c[1])) for c in cands2]

                    def _ok(v):
                        if not v:
                            return
                        info["fav_src"] = str(v)
                        self._save_config_to_file()
                        kit.toast("已设为：{}".format(os.path.basename(str(v))))
                        refresh()

                    self._show_modern_radio_selector(
                        "切换数据源 - {}".format(name), options,
                        info.get("fav_src") or cands2[0][2], _ok)

                actions = [
                    {"text": "管理片段", "style": "primary",
                     "callback": do_manage, "dismiss": False},
                    {"text": "编辑代码", "style": "secondary",
                     "callback": do_edit_code, "dismiss": False},
                    {"text": "数据源", "style": "secondary",
                     "callback": do_switch_src, "dismiss": False},
                ]
                # [要求] 来源接口卡片不需要选择开关（点了「管理片段」才是操作入口）
                return self._ui_site_card(kit, "✨ " + name, sub, False, None,
                                          actions, per_row=3, show_switch=False)

            def refresh():
                list_box.removeAllViews()
                data = infos()
                if not data:
                    list_box.addView(
                        kit.empty("没有匹配的本地接口\n先在「扫描本地接口」里生成"),
                        kit.lp(-1, -2))
                    kit.fill_spring(list_box, 0)
                    return
                for info in data:
                    list_box.addView(make_card(info),
                                     kit.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_XS)))
                kit.fill_spring(list_box, 0)

            refresh()
            self._fav_dialog(act, "添加收藏片段", container, None, holder,
                             height_ratio=0.88)

        self._run_on_ui(on_ui)

    # ---------- 片段选择（数据源切换 + 六类筛选 + 搜索 + 底部批量）----------

    def _open_frag_picker_dialog(self, info):

        cands = self._fav_json_candidates(info)
        if not cands:
            self._notify_app("该接口没有可用的 JSON 文件")
            return

        default_idx = 0
        _saved = str(info.get("fav_src") or "")
        for i, c in enumerate(cands):
            if _saved and c[2] == _saved:
                default_idx = i
                break
        else:
            for i, c in enumerate(cands):
                if c[0] == "本地接口":
                    default_idx = i
                    break

        def on_ui(act):
            kit = self._kit(act)
            holder = {}
            state = {
                "cat": "all",
                "kw": "",
                "src": cands[default_idx][2],
                "frags": [],
                "picked": {},
                "page": 1,          # 分页渲染：避免上百条片段一次建卡导致卡顿
            }
            sw_refs = {}

            container = kit.vbox()
            container.setLayoutParams(kit.lp(-1, -2))

            # ---- 数据源 + 分类 + 搜索：合并成一张紧凑卡 ----
            filter_card = kit.card(
                pad=(UITheme.S_MD, UITheme.S_XS, UITheme.S_MD, UITheme.S_XS))
            if len(cands) > 1:
                src_entries = [(c[2], c[0]) for c in cands]
                filter_card.addView(
                    self._ui_chip_row(kit, src_entries, state, "src",
                                      on_change=lambda p: (state.__setitem__(
                                          "page", 1),
                                          reload_frags(),
                                          refresh_list())),
                    kit.lp(-1, -2))
            cat_entries = [(k, lbl) for k, lbl in self.FRAG_CATS]
            filter_card.addView(
                self._ui_chip_row(kit, cat_entries, state, "cat",
                                  on_change=lambda k: (state.__setitem__("page", 1),
                                                       refresh_list())),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XXS, 0.0, 0.0)))
            srow, _se = self._ui_search_box(
                kit, lambda t: (state.__setitem__("kw", t),
                                state.__setitem__("page", 1),
                                refresh_list()))
            filter_card.addView(srow,
                                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XXS, 0.0, 0.0)))
            src_label = kit.text("", size=UITheme.FS_CAPTION,
                                 color=UITheme.TEXT_3, max_lines=2)
            # 「加载更多」按钮（分页渲染，避免一次建上百张卡导致卡顿）
            more_box = kit.vbox()
            more_box.setLayoutParams(kit.lp(-1, -2))
            more_btn = kit.button("加载更多", "secondary", None, size="sm")
            more_btn.setLayoutParams(kit.lp(-1, kit.dp(UITheme.H_BTN_SM), 0.0,
                                            (0.0, UITheme.S_XS, 0.0, 0.0)))
            more_box.addView(more_btn)
            filter_card.addView(src_label,
                                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XXS, 0.0, 0.0)))
            container.addView(filter_card, kit.lp(-1, -2))

            # ---- 定高片段列表 ----
            list_card = kit.card()
            scroller, list_box = self._ui_fixed_scroll(kit, rows=5, ratio=0.30)
            list_card.addView(scroller, kit.lp(-1, -2))
            # [要求] 全选 / 反选 / 清空 紧跟列表下方，只作用于当前筛选出来的数据
            list_card.addView(
                self._compact_button_bar(kit, [
                    {"text": "全选", "style": "secondary",
                     "callback": lambda: _batch(True), "dismiss": False},
                    {"text": "反选", "style": "secondary",
                     "callback": lambda: _batch(None), "dismiss": False},
                    {"text": "清空", "style": "secondary",
                     "callback": lambda: _batch(False), "dismiss": False},
                    {"text": "删除", "style": "soft_danger",
                     "callback": lambda: _batch_delete(), "dismiss": False},
                ], size="sm", per_row=4),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XS, 0.0, 0.0)))
            container.addView(list_card, kit.lp(-1, -2))

            def current_label():
                for c in cands:
                    if c[2] == state["src"]:
                        return "{}（{}）".format(c[0], c[1])
                return os.path.basename(state["src"] or "")

            def reload_frags():
                """切换数据源：直接重新解析代码并刷新片段状态数据"""
                state["frags"] = []
                state["picked"] = {}
                path = state["src"]
                if not path or not os.path.isfile(path):
                    kit.toast("数据源文件不存在")
                    return
                try:
                    base_dir = self._fav_base_dir(info, path)
                    frags = self._fav_extract_fragments(path, base_dir)
                except Exception as e:
                    kit.toast("解析失败: {}".format(e), long=True)
                    self._log("解析接口片段失败 {}: {}".format(path, e))
                    return
                exist = set()
                for f in self._favorite_fragments_all():
                    k = self._frag_dedup_key(f.get("body") or {})
                    if k:
                        exist.add(k)
                for i, fr in enumerate(frags):
                    k = self._frag_dedup_key(fr["body"])
                    fr["dup"] = bool(k) and (k in exist)
                    # [要求] 加载的片段默认全部未选中，由用户自己勾选 / 点全选
                    state["picked"][i] = False
                state["frags"] = frags
                try:
                    src_label.setText("当前：{} ｜ 共解析 {} 个片段".format(
                        current_label(), len(frags)))
                except Exception:
                    pass

            def visible():
                kw = str(state.get("kw") or "").strip().lower()
                cat = state.get("cat") or "all"
                out = []
                for i, fr in enumerate(state.get("frags") or []):
                    if fr.get("_hidden"):
                        continue
                    if cat != "all" and fr.get("cat") != cat:
                        continue
                    if kw:
                        hay = "{} {}".format(fr.get("name") or "",
                                             fr.get("api") or "").lower()
                        if kw not in hay:
                            continue
                    out.append((i, fr))
                return out

            def shown():
                """当前页要渲染的部分（分页，避免一次建上百张卡）"""
                vis = visible()
                n = state.get("page", 1) * self.FRAG_PAGE_SIZE
                return vis[:n]

            def ensure_more_btn():
                """在列表底部维护一个「加载更多」按钮"""
                try:
                    list_box.removeView(more_box)
                except Exception:
                    pass
                vis = visible()
                cnt = len(shown())
                if cnt < len(vis):
                    more_btn.setText("加载更多（还有 {} 条）".format(len(vis) - cnt))
                    more_box.setVisibility(0)
                else:
                    more_box.setVisibility(8)
                try:
                    list_box.addView(more_box)
                except Exception:
                    pass

            def refresh_list():
                sw_refs.clear()
                list_box.removeAllViews()
                vis = visible()
                page_vis = shown()
                if not vis:
                    list_box.addView(
                        kit.empty("没有匹配的片段\n换个分类或清掉搜索词试试"),
                        kit.lp(-1, -2))
                    kit.fill_spring(list_box, 0)
                    return
                if not page_vis:
                    list_box.addView(
                        kit.empty("没有匹配的片段\n换个分类或清掉搜索词试试"),
                        kit.lp(-1, -2))
                    kit.fill_spring(list_box, 0)
                    return
                for i, fr in page_vis:
                    cat = fr.get("cat", "other")
                    sub = "[{}] {}".format(self.FRAG_CAT_LABEL.get(cat, cat),
                                           _short_url(fr.get("api") or "", 44))
                    if fr.get("dup"):
                        sub += "（已在收藏中）"
                    elif fr.get("body", {}).get("jar"):
                        sub += " · 含jar"

                    def make_drop(ff=fr, ii=i):
                        """只从本次列表里移除（不动磁盘、不进收藏），
                        移除后不参与任何全选 / 反选。

                        原地摘掉这一张卡，不重建整个列表 —— 不弹窗、不闪烁。
                        """
                        def on_click():
                            nm = ff.get("name") or "未命名"
                            ff["_hidden"] = True
                            state["picked"].pop(ii, None)
                            try:
                                _ref = sw_refs.pop(ii, None)
                                _c = (_ref or {}).get("card")
                                if _c is not None:
                                    _p = _c.getParent()
                                    if _p is not None:
                                        _p.removeView(_c)
                                    # 兜底：万一摘除没生效，也保证不占位、不可聚焦
                                    try:
                                        _c.setVisibility(8)      # GONE
                                        _c._parent = None
                                    except Exception:
                                        pass
                            except Exception:
                                refresh_list()
                            try:
                                src_label.setText(
                                    "当前：{} ｜ 可见 {} 个片段".format(
                                        current_label(), len(visible())))
                            except Exception:
                                pass
                            kit.toast("已移除：{}".format(nm))
                        return on_click

                    def make_toggle(ii=i, frr=fr):
                        def on_click(v):
                            if frr.get("dup"):
                                ref = sw_refs.get(ii)
                                sw = ref.get("switch") if ref else None
                                if sw is None:
                                    card = _find_card(ii)
                                    sw = getattr(card, "_switch", None)
                                if sw is not None:
                                    try:
                                        sw.setChecked(False)
                                    except Exception:
                                        pass
                                kit.toast("该片段已收藏，自动跳过")
                                return
                            state["picked"][ii] = bool(v)
                        return on_click

                    def make_edit(ff=fr):
                        def on_click():
                            def on_done():
                                # 编辑后重算分类 / api，刷新列表
                                try:
                                    ff["api"] = self._frag_api_value(ff.get("body") or {})
                                    ff["cat"] = self._frag_category(
                                        ff.get("body") or {}, ff.get("group"))
                                except Exception:
                                    pass
                                refresh_list()
                            self._fav_edit_fragment(ff, on_done)
                        return on_click

                    def make_proxy(ff=fr):
                        """注代：给当前片段代码加上 proxy 字段（地址可改）"""
                        def on_click():
                            b = ff.get("body")
                            if not isinstance(b, dict):
                                b = {}
                                ff["body"] = b
                            cur = str(b.get("proxy") or "").strip() \
                                or self.FRAG_PROXY_DEFAULT

                            def _save(v):
                                v = str(v or "").strip()
                                if not v:
                                    kit.toast("已取消")
                                    return
                                b["proxy"] = v
                                # 代理变了不影响去重键，但 api 展示要跟上
                                refresh_list()
                                kit.toast("已注代：{}".format(v), long=True)

                            self._show_modern_input(
                                "注代 - {}".format(ff.get("name") or ""),
                                "确认或修改为你的代理地址", cur, _save)
                        return on_click

                    def make_collect(ff=fr, ii=i):
                        def on_click():
                            if ff.get("dup"):
                                kit.toast("该片段已在收藏中")
                                return
                            added, _sk = self._fav_add_fragments(
                                [ff], str(info.get("dir_name") or ""))
                            if added:
                                ff["dup"] = True
                                state["picked"][ii] = False
                                self._fav_emit()
                                reload_frags()
                                refresh_list()
                                kit.toast("已收藏「{}」".format(ff.get("name") or ""))
                        return on_click

                    _ref = {}
                    card = self._ui_site_card(
                        kit,
                        fr.get("name") or "未命名",
                        sub,
                        bool(state["picked"].get(i)) and not fr.get("dup"),
                        make_toggle(i, fr),
                        [{"text": "删除", "style": "soft_danger",
                          "callback": make_drop(), "dismiss": False},
                         {"text": "编辑", "style": "secondary",
                          "callback": make_edit(), "dismiss": False},
                         {"text": "注代", "style": "primary",
                          "callback": make_proxy(), "dismiss": False},
                         {"text": "收藏", "style": "soft_brand",
                          "callback": make_collect(), "dismiss": False}],
                        dim=bool(fr.get("dup")), per_row=3, state_out=_ref)
                    sw_refs[i] = _ref
                    try:
                        card._frag_idx = i
                    except Exception:
                        pass
                    list_box.addView(
                        card, kit.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_XS)))
                ensure_more_btn()
                kit.fill_spring(list_box, 0)

            def _find_card(ii):
                """按 view 树反查卡片（sw_refs 失效时的兜底）"""
                try:
                    for _i in range(list_box.getChildCount()):
                        _v = list_box.getChildAt(_i)
                        if getattr(_v, "_frag_idx", None) == ii:
                            return _v
                except Exception:
                    pass
                return None

            def _batch(mode):
                """全选 / 反选 / 清空。

                [修复] 静默设置开关，避免 N 次回调写盘把主线程卡死；
                同时用 view 树兜底查找卡片，分页场景下也不会漏同步。
                """
                vis = visible()
                if not vis:
                    kit.toast("当前分类下没有片段")
                    return
                n = 0
                for i, fr in vis:
                    if fr.get("dup"):
                        continue
                    if mode is None:
                        state["picked"][i] = not state["picked"].get(i, False)
                    else:
                        state["picked"][i] = bool(mode)
                    n += 1
                for i, fr in vis:
                    if fr.get("dup"):
                        continue
                    ref = sw_refs.get(i)
                    sw = ref.get("switch") if ref else None
                    if sw is None:
                        card = _find_card(i)
                        sw = getattr(card, "_switch", None) if card else None
                    if sw is None:
                        continue
                    try:
                        kit.set_switch_quietly(
                            sw, bool(state["picked"].get(i, False)))
                    except Exception:
                        pass
                kit.toast("已处理 {} 个片段".format(n))

            def _batch_delete():
                """批量删除：对当前筛选下已勾选的片段执行单条删除逻辑"""
                vis = [(i, fr) for i, fr in visible()
                       if state["picked"].get(i, False) and not fr.get("dup")]
                if not vis:
                    kit.toast("没有勾选任何片段")
                    return

                def _yes():
                    for i, fr in vis:
                        fr["_hidden"] = True
                        state["picked"].pop(i, None)
                    # 批量删除直接重建列表：分页下逐张摘除容易漏，
                    # 且重建一次比多次原地摘除更可靠（也不闪，因为是整表替换）
                    refresh_list()
                    try:
                        src_label.setText(
                            "当前：{} ｜ 可见 {} 个片段".format(
                                current_label(), len(visible())))
                    except Exception:
                        pass
                    kit.toast("已删除 {} 个片段".format(len(vis)))

                self._show_modern_confirm(
                    "删除片段",
                    "确定从列表移除勾选的 {} 个片段？".format(len(vis)), _yes)

            def do_add():
                picked = [state["frags"][i]
                          for i, v in sorted(state["picked"].items())
                          if v and i < len(state["frags"])
                          and not state["frags"][i].get("dup")]
                if not picked:
                    kit.toast("没有勾选任何新片段")
                    return
                added, skipped = self._fav_add_fragments(
                    picked, str(info.get("dir_name") or ""))
                kit.toast("已收藏 {} 个{}".format(
                    added, "，跳过重复 {}".format(skipped) if skipped else ""),
                    long=True)
                if added:
                    self._fav_emit()
                    reload_frags()
                    refresh_list()

            def load_more():
                state["page"] = state.get("page", 1) + 1
                refresh_list()

            kit.bind_click(more_btn, load_more)

            def reload_and_reset():
                state["page"] = 1
                reload_frags()
                refresh_list()

            reload_and_reset()

            def do_close():
                try:
                    holder["d"].dismiss()
                except Exception:
                    pass

            buttons = [
                {"text": "加入收藏", "style": "success",
                 "callback": do_add, "dismiss": False},
                {"text": "关闭", "style": "secondary",
                 "callback": do_close, "dismiss": False},
            ]
            self._fav_dialog(
                act, "管理片段 - {}".format(info.get("dir_name") or ""),
                container, buttons, holder, height_ratio=0.94, scroll=True)

        self._run_on_ui(on_ui)

    def _fav_add_fragments(self, picked, src_name):
        """按 api/url 去重写入收藏"""
        exist = set()
        for f in self._favorite_fragments_all():
            k = self._frag_dedup_key(f.get("body") or {})
            if k:
                exist.add(k)

        added, skipped = 0, 0
        stamp = str(int(time.time() * 1000))
        for n, fr in enumerate(picked):
            body = fr.get("body") or {}
            key = self._frag_dedup_key(body)
            if not key or key in exist:
                skipped += 1
                continue
            exist.add(key)
            self.favorite_fragments.append({
                "id": "%s_%d" % (stamp, n),
                "name": fr.get("name") or "片段",
                "cat": fr.get("cat") or "other",
                "group": fr.get("group") or "sites",
                "api": fr.get("api") or "",
                "src": src_name,
                "enabled": True,
                "body": copy.deepcopy(body),
            })
            added += 1
        if added:
            self._fav_save()
            self._log("收藏片段新增 {} 条，跳过重复 {} 条".format(added, skipped))
        return added, skipped

    # ---------- 片段编辑 / 命名 / 生成 ----------

    def _open_fav_history_dialog(self):
        """历史生成记录：可加载其中的收藏数据，也可删除记录"""

        def on_ui(act):
            kit = self._kit(act)
            holder = {}
            state = {}

            container = kit.vbox()
            container.setLayoutParams(kit.lp(-1, -2))

            card = kit.card()
            card.addView(
                kit.section_title("📜 生成历史"),
                kit.lp(-1, -2))

            scroller, list_box = self._ui_fixed_scroll(kit, rows=6, ratio=0.34)
            card.addView(scroller,
                         kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))
            container.addView(card, kit.lp(-1, -2))

            def do_load(rec):
                def _yes():
                    added, skipped, total = self._fav_history_load(rec.get("id"))
                    self._fav_emit()
                    kit.toast("已加载 {} 条（跳过重复 {} 条）".format(added, skipped),
                              long=True)
                    refresh()
                self._show_modern_confirm(
                    "加载历史记录",
                    "加载「{}」的 {} 个片段？".format(
                        rec.get("name") or "", rec.get("count") or 0), _yes)

            def do_del(rec):
                def _yes():
                    self._fav_history_remove(rec.get("id"))
                    refresh()
                self._show_modern_confirm(
                    "删除记录",
                    "删除记录「{}」？".format(rec.get("name") or ""), _yes)

            def make_card(rec):
                sub = "{} · {} 个片段".format(rec.get("time") or "",
                                              rec.get("count") or 0)
                frags = rec.get("frags") or []
                if frags:
                    names = "、".join(str(f.get("name") or "") for f in frags[:4])
                    if len(frags) > 4:
                        names += " 等"
                    sub += "\n{}".format(names)
                return self._ui_site_card(
                    kit, "🗂 {}".format(rec.get("name") or "未命名"), sub,
                    False, None,
                    [{"text": "加载", "style": "primary",
                      "callback": lambda r=rec: do_load(r), "dismiss": False},
                     {"text": "删除", "style": "soft_danger",
                      "callback": lambda r=rec: do_del(r), "dismiss": False}],
                    per_row=2, show_switch=False)

            def refresh():
                list_box.removeAllViews()
                data = self._fav_history_all()
                if not data:
                    list_box.addView(
                        kit.empty("还没有生成历史\n先在接口改装中心里「生成并保存」"),
                        kit.lp(-1, -2))
                    kit.fill_spring(list_box, 0)
                    return
                for rec in data:
                    list_box.addView(make_card(rec),
                                     kit.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_XS)))
                kit.fill_spring(list_box, 0)

            refresh()
            self._fav_dialog(act, "📜 生成历史", container, None, holder,
                             height_ratio=0.86, scroll=True)

        self._run_on_ui(on_ui)

    def _fav_edit_fragment(self, frag, refresh_cb=None):
        """编辑片段代码：走现有文本编辑器模板，落盘到片段缓存目录"""
        try:
            edit_dir = os.path.join(CACHE_DIR, self.FRAG_EDIT_DIRNAME)
            os.makedirs(edit_dir, exist_ok=True)
        except Exception:
            edit_dir = CACHE_DIR
        path = os.path.join(edit_dir, "frag_%s.json" % (frag.get("id") or "tmp"))
        try:
            content = json.dumps(frag.get("body") or {}, ensure_ascii=False, indent=2)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            self._notify_app("打开编辑器失败: {}".format(e))
            return

        def on_saved():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    new_body = json.loads(f.read())
                if not isinstance(new_body, dict):
                    raise ValueError("顶层必须是 JSON 对象")
                frag["body"] = new_body
                frag["api"] = self._frag_api_value(new_body)
                frag["cat"] = self._frag_category(new_body, frag.get("group"))
                # [修复 BUG-07] 代码里改了 name，前端列表要跟着变
                _nm = str(new_body.get("name") or "").strip()
                if _nm:
                    frag["name"] = _nm
                self._fav_save()
                self._fav_emit()
                if refresh_cb:
                    refresh_cb()
            except Exception as e:
                self._notify_app("保存失败，内容未生效: {}".format(e))

        self._show_modern_text_editor(
            "✏️ 编辑片段 - {}".format(frag.get("name") or ""),
            content, path, "", "", on_saved, url_label="片段U")

    def _fav_check_name(self, name):
        v = str(name or "").strip()
        if not v:
            return "名称不能为空"
        if re.search(r'[\\/:*?"<>|]', v):
            return '名称不能包含 \\ / : * ? " < > |'
        base = str(getattr(self, 'download_output_dir', '') or '')
        if base and os.path.exists(os.path.join(base, v)):
            return "本地包目录下已存在同名文件夹：{}".format(v)
        return ""

    def _fav_ask_name(self, title, default_name, on_ok, hint=None):

        def on_ui(act):
            kit = self._kit(act)
            holder = {}
            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))
            box.addView(kit.hint(
                hint or "按名称在本地包目录下创建文件夹，接口文件与文件夹同名（xxx/xxx.json）\n"
                        "不生成 map、不写宫格数据，之后用「扫描本地接口」收录"),
                kit.lp(-1, -2))

            edit = kit.input(hint="输入名称", value=default_name or "")
            box.addView(edit, kit.lp(-1, -2, 0.0, (0.0, UITheme.S_MD, 0.0, 0.0)))

            warn = kit.text("", size=UITheme.FS_CAPTION,
                            color=UITheme.DANGER, max_lines=3)
            box.addView(warn, kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XS, 0.0, 0.0)))

            def on_changed(txt):
                try:
                    warn.setText(self._fav_check_name(txt))
                except Exception:
                    pass

            self._bind_text_changed(kit, edit, on_changed)
            on_changed(default_name or "")

            def do_ok():
                v = str(edit.getText()).strip()
                msg = self._fav_check_name(v)
                if msg:
                    kit.toast(msg, long=True)
                    return
                try:
                    holder["d"].dismiss()
                except Exception:
                    pass
                on_ok(v)

            def do_cancel():
                try:
                    holder["d"].dismiss()
                except Exception:
                    pass

            buttons = [
                {"text": "取消", "style": "secondary",
                 "callback": do_cancel, "dismiss": False},
                {"text": "确定", "style": "primary", "callback": do_ok, "dismiss": False},
            ]
            self._fav_dialog(act, title, box, buttons, holder, height_ratio=0)
            try:
                edit.requestFocus()
            except Exception:
                pass

        self._run_on_ui(on_ui)

    def _fav_generate(self, frags, name, kit=None):
        """生成改装接口：本地包目录/<名称>/<名称>.json，不建 map、不写宫格数据"""
        base = str(getattr(self, 'download_output_dir', '') or '')
        if not base:
            if kit:
                kit.toast("未设置本地包输出目录", long=True)
            return False
        folder = os.path.join(base, name)
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception as e:
            if kit:
                kit.toast("创建目录失败: {}".format(e), long=True)
            return False

        sites, lives = [], []
        for f in frags:
            body = copy.deepcopy(f.get("body") or {})
            if f.get("group") == "lives":
                lives.append(body)
            else:
                sites.append(body)

        data = {}
        if sites:
            data["sites"] = sites
        if lives:
            data["lives"] = lives
        data["warningText"] = WARNING_TEXT

        # [要求] 生成产物逻辑与方法等同于当前程序：
        # 产物同样注入「本地包管理」入口（api 与 config_file 同源拼接）
        self._inject_manager_site(sites)
        if any(isinstance(x, dict) and
               x.get("key") == "local_package_manager" for x in sites):
            data["home"] = "local_package_manager"

        # 生成接口是关键节点：立即同步落盘（不走延迟写），保证不丢数据
        self._fav_flush_now()

        out = os.path.join(folder, "%s.json" % name)
        try:
            with open(out, 'w', encoding='utf-8') as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)
        except Exception as e:
            if kit:
                kit.toast("写入失败: {}".format(e), long=True)
            return False

        self._log("改装接口已生成: {}（sites {} / lives {}，共 {}）".format(
            out, len(sites), len(lives), len(sites) + len(lives)))

        # [要求] 视图弹窗（管理本地接口）不写历史；改装中心照旧存档
        try:
            self._fav_history_add(name, frags)
        except Exception as e:
            self._log("生成历史存档失败: {}".format(e))
        # 清空后必须立刻同步落盘并镜像，否则重启会丢数据
        self._fav_flush_now()

        # [要求] 生成后清空收藏片段
        try:
            del self.favorite_fragments[:]
        except Exception:
            self.favorite_fragments = []
        self._fav_save()
        self._fav_emit()

        # [要求] 产物落地后继续执行「扫描本地接口」的效果：
        # 自动收录新接口，首页宫格随即出现该入口
        self._after_generate_rescan([name], kit)

        self._notify_app(
            "已生成「{}」\n{} 个片段\n收藏已清空并存入历史\n"
            "已自动扫描并收录".format(
                name, len(sites) + len(lives)))
        if kit:
            kit.toast("已生成「{}」，收藏已清空".format(name), long=True)
        return True

    # ---------- 管理本地接口：来源 / 源文件 ----------

    def _map_dir_of(self, info):
        """该接口在 map 下的产物目录（编辑 / 视图都读这里的新代码）"""
        try:
            base = os.path.join(self._work_subdir_base() or "", "map")
            d = os.path.join(base, str((info or {}).get("dir_name") or ""))
            return d if os.path.isdir(d) else ""
        except Exception:
            return ""

    def _map_generated_files(self, info):
        """map 下已生成的数据文件列表（多数据时供「选择来源」切换）"""
        out = []
        d = self._map_dir_of(info)
        if not d:
            return out
        try:
            for n in sorted(os.listdir(d)):
                if n.startswith('.') or not n.lower().endswith('.json'):
                    continue
                out.append(os.path.join(d, n))
        except Exception:
            pass
        return out

    def _local_iface_source_path(self, info):
        """接口记录对应的源文件（非 map 产物）：视图的保存目标"""
        cands = []
        try:
            cands.append(info.get("selected") or "")
            cands.extend(list(info.get("json_files") or []))
        except Exception:
            pass
        for p in cands:
            try:
                if p and os.path.isfile(p) and not self._is_under_map(p):
                    return os.path.abspath(p)
            except Exception:
                continue
        real = self._real_source_json(info)
        try:
            if real and os.path.isfile(real) and not self._is_under_map(real):
                return os.path.abspath(real)
        except Exception:
            pass
        try:
            d = os.path.join(info.get("parent_dir", "") or "",
                             info.get("dir_name", "") or "")
            if os.path.isdir(d):
                for n in sorted(os.listdir(d)):
                    if n.startswith('.') or not n.lower().endswith('.json'):
                        continue
                    return os.path.join(d, n)
        except Exception:
            pass
        return ""

    def _local_iface_load(self, info, json_path=None):
        """读取（并按需生成）可编辑的代码，返回 (path, data)；失败返回 ("", None)"""
        path = self._ensure_generated_json(info, json_path) if json_path \
            else self._ensure_generated_json(info)
        if not path or not os.path.isfile(path):
            return "", None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return path, None
        return path, (data if isinstance(data, dict) else None)

    # ---------- 管理本地接口：视图弹窗（参照接口改装中心一级弹窗）----------

    def _open_local_interface_view(self, info, src_path=""):
        """视图：直接编辑该接口的片段列表，保存写回源文件。

        与「接口改装中心」的区别：
          · 不生成新接口文件、不写生成历史、不重新扫描；
          · 底部按钮是「保存」，所有改动写回该接口自己的源 JSON。
        """
        name = str(info.get("dir_name") or "未命名")
        base_dir = os.path.dirname(os.path.abspath(
            src_path or self._local_iface_source_path(info) or ""))

        def on_ui(act):
            kit = self._kit(act)
            holder = {}
            state = {"cat": "all", "kw": ""}
            holder["frags"] = []
            # [修复] 卡片的开关/标题走 Python 侧引用表，
            # 批量勾选时才能把形态同步到界面（给 Java view 挂属性不可靠）
            sw_refs = {}

            def load_frags():
                path = src_path or self._local_iface_source_path(info)
                if not path or not os.path.isfile(path):
                    kit.toast("该接口没有可用的 JSON 文件", long=True)
                    return []
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if not isinstance(data, dict):
                        raise ValueError("顶层不是 JSON 对象")
                except Exception as e:
                    kit.toast("读取失败: {}".format(e), long=True)
                    return []
                out = []
                for group in ("sites", "lives"):
                    arr = data.get(group)
                    if not isinstance(arr, list):
                        continue
                    for i, item in enumerate(arr):
                        if not isinstance(item, dict):
                            continue
                        body = self._absolutize_local_paths(
                            copy.deepcopy(item), base_dir)
                        out.append({
                            "id": "v_%s_%d" % (group, i),
                            "group": group,
                            "cat": self._frag_category(body, group),
                            "name": self._frag_name(body, i),
                            "api": self._frag_api_value(body),
                            "enabled": True,
                            "body": body,
                        })
                return out

            def visible():
                kw = str(state.get("kw") or "").strip().lower()
                cat = state.get("cat") or "all"
                out = []
                for fr in holder["frags"]:
                    if fr.get("_hidden"):
                        continue
                    if cat != "all" and fr.get("cat") != cat:
                        continue
                    if kw:
                        hay = "{} {}".format(fr.get("name") or "",
                                             fr.get("api") or "").lower()
                        if kw not in hay:
                            continue
                    out.append(fr)
                return out

            container = kit.vbox()
            container.setLayoutParams(kit.lp(-1, -2))

            filter_card = kit.card()
            cat_entries = [(k, lbl) for k, lbl in self.FRAG_CATS]
            filter_card.addView(
                self._ui_chip_row(kit, cat_entries, state, "cat",
                                  on_change=lambda k: refresh()),
                kit.lp(-1, -2))
            srow, _se = self._ui_search_box(
                kit, lambda t: (state.__setitem__("kw", t), refresh()))
            filter_card.addView(
                srow, kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XS, 0.0, 0.0)))
            count_label = kit.text("", size=UITheme.FS_CAPTION,
                                   color=UITheme.TEXT_3, max_lines=2)
            filter_card.addView(
                count_label,
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XXS, 0.0, 0.0)))
            container.addView(filter_card, kit.lp(-1, -2))

            list_card = kit.card()
            scroller, list_box = self._ui_fixed_scroll(kit, rows=6, ratio=0.40)
            list_card.addView(scroller, kit.lp(-1, -2))
            container.addView(list_card, kit.lp(-1, -2))

            def refresh_count():
                vis = visible()
                sel = len([f for f in vis if f.get("enabled", True)])
                try:
                    count_label.setText(
                        "当前 {} 条，已启用 {} 条 ｜ 共 {} 条".format(
                            len(vis), sel, len(holder["frags"])))
                except Exception:
                    pass

            def sync_switches(frags):
                """静默同步开关形态，避免 N 次回调把主线程卡死。

                [修复] 片段是 dict，之前用 getattr(f, "_card") 永远取不到，
                批量勾选后开关形态不变；改为查 Python 侧引用表。
                """
                for f in frags:
                    ref = sw_refs.get(id(f))
                    if not ref:
                        continue
                    on = bool(f.get("enabled", True))
                    try:
                        if ref.get("switch") is not None:
                            kit.set_switch_quietly(ref["switch"], on)
                    except Exception:
                        pass
                    try:
                        if ref.get("title") is not None:
                            ref["title"].setTextColor(kit.color(
                                UITheme.TEXT if on else UITheme.TEXT_3))
                    except Exception:
                        pass

            def batch(mode):
                vis = visible()
                if not vis:
                    kit.toast("当前分类下没有片段")
                    return
                for f in vis:
                    f["enabled"] = (not bool(f.get("enabled", True))
                                    if mode is None else bool(mode))
                sync_switches(vis)
                refresh_count()
                kit.toast("已处理 {} 个片段".format(len(vis)))

            def batch_delete():
                vis = [f for f in visible() if f.get("enabled", True)]
                if not vis:
                    kit.toast("没有勾选任何片段")
                    return

                def _yes():
                    for f in vis:
                        f["_hidden"] = True
                    refresh()
                    kit.toast("已移除 {} 个片段".format(len(vis)))

                self._show_modern_confirm(
                    "移除片段",
                    "确定移除当前分类下勾选的 {} 个片段？\n"
                    "（点「保存」后才写回源文件）".format(len(vis)), _yes)

            list_card.addView(
                self._compact_button_bar(kit, [
                    {"text": "全选", "style": "secondary",
                     "callback": lambda: batch(True), "dismiss": False},
                    {"text": "反选", "style": "secondary",
                     "callback": lambda: batch(None), "dismiss": False},
                    {"text": "清空", "style": "secondary",
                     "callback": lambda: batch(False), "dismiss": False},
                    {"text": "删除", "style": "soft_danger",
                     "callback": batch_delete, "dismiss": False},
                ], size="sm", per_row=4),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XS, 0.0, 0.0)))

            def make_card(frag):
                cat = frag.get("cat", "other")
                sub = "[{}] {}".format(self.FRAG_CAT_LABEL.get(cat, cat),
                                       _short_url(frag.get("api") or "", 44))
                if frag.get("body", {}).get("proxy"):
                    sub += "\n注代：{}".format(str(frag["body"].get("proxy")))

                def on_toggle(v):
                    frag["enabled"] = bool(v)
                    refresh_count()

                def do_up():
                    items = holder["frags"]
                    i = items.index(frag)
                    if i <= 0:
                        kit.toast("已经在最前面")
                        return
                    items[i - 1], items[i] = items[i], items[i - 1]
                    refresh()

                def do_down():
                    items = holder["frags"]
                    i = items.index(frag)
                    if i >= len(items) - 1:
                        kit.toast("已经在最后面")
                        return
                    items[i + 1], items[i] = items[i], items[i + 1]
                    refresh()

                def do_rename():
                    def _save(v):
                        v = str(v or "").strip()
                        if not v:
                            return
                        frag["name"] = v
                        body = frag.get("body")
                        if isinstance(body, dict) and isinstance(
                                body.get("name"), str):
                            body["name"] = v
                        refresh()
                    self._show_modern_input(
                        "改名片段", "输入新的片段名称",
                        frag.get("name") or "", _save)

                def do_edit():
                    def on_done():
                        try:
                            frag["api"] = self._frag_api_value(
                                frag.get("body") or {})
                            frag["cat"] = self._frag_category(
                                frag.get("body") or {}, frag.get("group"))
                            _nm = str((frag.get("body") or {}).get("name")
                                      or "").strip()
                            if _nm:
                                frag["name"] = _nm
                        except Exception:
                            pass
                        refresh()
                    self._fav_edit_fragment(frag, on_done)

                def do_proxy():
                    body = frag.get("body")
                    if not isinstance(body, dict):
                        body = {}
                        frag["body"] = body
                    cur = str(body.get("proxy") or "").strip() \
                        or self.FRAG_PROXY_DEFAULT

                    def _save(v):
                        v = str(v or "").strip()
                        if not v:
                            kit.toast("已取消")
                            return
                        body["proxy"] = v
                        refresh()
                        kit.toast("已注代：{}".format(v), long=True)

                    self._show_modern_input(
                        "注代 - {}".format(frag.get("name") or ""),
                        "确认或修改为你的代理地址", cur, _save)

                def do_remove():
                    def _yes():
                        frag["_hidden"] = True
                        refresh()
                    self._show_modern_confirm(
                        "移除片段",
                        "确定移除「{}」？\n（点「保存」后才写回源文件）".format(
                            frag.get("name") or ""), _yes)

                actions = [
                    {"text": "↑", "style": "secondary", "callback": do_up, "dismiss": False},
                    {"text": "↓", "style": "secondary", "callback": do_down, "dismiss": False},
                    {"text": "改名", "style": "secondary", "callback": do_rename, "dismiss": False},
                    {"text": "编辑", "style": "soft_brand", "callback": do_edit, "dismiss": False},
                    {"text": "注代", "style": "primary", "callback": do_proxy, "dismiss": False},
                    {"text": "移除", "style": "soft_danger", "callback": do_remove, "dismiss": False},
                ]
                _ref = {}
                card = self._ui_site_card(
                    kit, frag.get("name") or "未命名", sub,
                    frag.get("enabled", True), on_toggle, actions,
                    dim=not frag.get("enabled", True), per_row=6,
                    state_out=_ref)
                sw_refs[id(frag)] = _ref
                return card

            def refresh():
                sw_refs.clear()
                list_box.removeAllViews()
                vis = visible()
                if not vis:
                    list_box.addView(kit.empty(
                        "没有匹配的片段\n换个分类或清掉搜索词试试"),
                        kit.lp(-1, -2))
                    kit.fill_spring(list_box, 0)
                    refresh_count()
                    return
                for fr in vis:
                    list_box.addView(
                        make_card(fr),
                        kit.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_XS)))
                kit.fill_spring(list_box, 0)
                refresh_count()

            def do_save():
                """保存：把当前片段列表写回该接口的源 JSON（不生成 / 不写历史）"""
                out_path = self._local_iface_source_path(info)
                if not out_path:
                    kit.toast("找不到该接口的源文件，无法保存", long=True)
                    return
                keep = [f for f in holder["frags"]
                        if not f.get("_hidden") and f.get("enabled", True)]
                if not keep:
                    kit.toast("至少要保留并勾选一个片段", long=True)
                    return
                try:
                    with open(out_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if not isinstance(data, dict):
                        raise ValueError("源文件内容不是 JSON 对象")
                except Exception as e:
                    kit.toast("读取源文件失败: {}".format(e), long=True)
                    return
                sites, lives = [], []
                for f in keep:
                    body = copy.deepcopy(f.get("body") or {})
                    if f.get("group") == "lives":
                        lives.append(body)
                    else:
                        sites.append(body)
                if sites:
                    data["sites"] = sites
                else:
                    data.pop("sites", None)
                if lives:
                    data["lives"] = lives
                else:
                    data.pop("lives", None)
                try:
                    with open(out_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    kit.toast("保存失败: {}".format(e), long=True)
                    return
                # 源文件已变，丢掉 map 下的旧副本，下次打开自动按新内容重新生成
                try:
                    info.pop("selected", None)
                    self._save_config_to_file()
                except Exception:
                    pass
                kit.toast("已保存到源文件（{} 个片段）".format(
                    len(sites) + len(lives)), long=True)
                try:
                    holder["d"].dismiss()
                except Exception:
                    pass

            def do_close():
                try:
                    holder["d"].dismiss()
                except Exception:
                    pass

            holder["frags"] = load_frags()
            refresh()

            buttons = [
                {"text": "保存", "style": "success",
                 "callback": do_save, "dismiss": False},
                {"text": "关闭", "style": "secondary",
                 "callback": do_close, "dismiss": False},
            ]
            self._fav_dialog(act, "👁 视图 - {}".format(name), container,
                             buttons, holder, height_ratio=0.94, scroll=True)

        self._run_on_ui(on_ui)

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

            # [要求] 列表定高滚动：记录再多，下面的按钮也不会被顶出屏幕
            scroller, sites_container = spider._ui_fixed_scroll(
                kit, rows=5, ratio=0.34)
            list_card.addView(scroller, kit.lp(-1, -2))

            # 每条记录可单独指定"编辑来源"（map 下有多份数据时才需要）
            edit_src = {}

            def make_item_card(info):
                parent_dir = info.get("parent_dir", "")
                dir_name = info["dir_name"]
                hidden = info.get("hidden", False)
                json_count = len(info.get("json_files") or [])
                full_path = os.path.join(parent_dir, dir_name)
                item_key = (parent_dir, dir_name)
                # [要求] 编辑来源取 map 下的数据（已绝对路径化的新代码），
                # 多数据时可用「选择来源」切换；源文件只作为保存目标。
                files = [str(f) for f in (info.get("json_files") or [])
                         if f and not spider._is_under_map(f)]
                if not files:
                    _real = spider._real_source_json(info)
                    if _real and not spider._is_under_map(_real):
                        files = [str(_real)]

                def cur_src():
                    c = (edit_src.get(item_key)
                         or spider._real_source_json(info)
                         or (files[0] if files else ""))
                    return str(c)

                _gen_cache = {}

                def gen_path():
                    """map 下当前使用的新代码（同一个卡片只生成一次）"""
                    if "p" not in _gen_cache:
                        _gen_cache["p"] = spider._ensure_generated_json(
                            info, cur_src() or None)
                    return _gen_cache["p"]

                def src_options():
                    """编辑来源候选：map 下已生成的数据文件"""
                    outs, seen = [], set()
                    gen = gen_path()
                    for p in ([gen] if gen else []) + spider._map_generated_files(info):
                        try:
                            ap = os.path.abspath(p)
                        except Exception:
                            continue
                        if ap in seen or not os.path.isfile(ap):
                            continue
                        seen.add(ap)
                        outs.append(ap)
                    return outs

                def on_toggle(v):
                    batch_selected[item_key] = bool(v)

                def on_pick_src():
                    """有多个 map 数据时，选择「代码 / 视图」用的是哪一份"""
                    opts = src_options()
                    if len(opts) <= 1:
                        kit.toast("该接口只有一份数据")
                        return
                    options = [(p, os.path.basename(os.path.dirname(p)) + "/"
                                + os.path.basename(p)) for p in opts]
                    cur = gen_path() or opts[0]

                    def _ok(v):
                        if not v:
                            return
                        edit_src[item_key] = str(v)
                        try:
                            info["selected"] = str(v)
                            spider._save_config_to_file()
                        except Exception:
                            pass
                        refresh_list()
                        kit.toast("编辑来源已设为：{}".format(os.path.basename(str(v))))

                    spider._show_modern_radio_selector(
                        "选择编辑来源 - {}".format(dir_name), options, cur, _ok)

                def on_edit():
                    # 编辑一律加载 map 下的新代码，不回退到解密 / 本地化原始文件
                    selected = gen_path()
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

                            def on_saved():
                                # [要求] 读的是 map 下的新代码，保存要落到源文件
                                src = spider._local_iface_source_path(info)
                                try:
                                    same = src and os.path.abspath(src) == os.path.abspath(selected)
                                except Exception:
                                    same = False
                                if src and not same:
                                    try:
                                        with open(selected, 'r', encoding='utf-8') as _f:
                                            _data = json.load(_f)
                                        with open(src, 'w', encoding='utf-8') as _f:
                                            json.dump(_data, _f, ensure_ascii=False, indent=2)
                                        spider._notify_app("已保存，并同步写入源文件")
                                        return
                                    except Exception as _e:
                                        spider._notify_app(
                                            "已保存到 map，但回写源文件失败: {}".format(_e))
                                        return
                                spider._notify_app(
                                    "已保存到 map（立即生效）\n"
                                    "注意：下次「扫描本地接口」会重新生成并覆盖此处改动")

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

                def on_view():
                    # 视图：以改装中心一级弹窗的形式编辑片段，保存写回源文件
                    spider._open_local_interface_view(info, gen_path())

                def on_del():
                    spider.localized_interfaces = [
                        i for i in spider.localized_interfaces
                        if not (i.get("parent_dir") == parent_dir and i["dir_name"] == dir_name)
                    ]
                    try:
                        spider._persist_mark_deleted(
                            'localized_interfaces',
                            "{}/{}".format(str(parent_dir).strip().rstrip('/'),
                                           str(dir_name).strip()))
                    except Exception:
                        pass
                    spider._save_config_to_file()
                    spider._notify_app(f"已删除记录：{dir_name}")
                    batch_selected.pop(item_key, None)
                    refresh_list()

                actions = [
                    {"text": "代码", "style": "primary", "callback": on_edit},
                    {"text": "视图", "style": "primary", "callback": on_view, "dismiss": False},
                ]

                def _confirm_del():
                    spider._show_modern_confirm(
                        "删除记录",
                        "从列表移除「{}」？\n（只删记录，不删磁盘文件）".format(dir_name),
                        on_del)

                _opts = src_options()
                if len(_opts) > 1:
                    actions.append(
                        {"text": "选择来源", "style": "secondary",
                         "callback": on_pick_src, "dismiss": False})
                actions.append(
                    {"text": "删除记录", "style": "soft_danger",
                     "callback": _confirm_del, "dismiss": False})

                _sub = f"{full_path} · JSON {json_count} 个"
                # [要求] 状态显示以 map 下的新代码为准（编辑 / 跳转都用它）
                _gen = gen_path()
                _src_show = _gen or cur_src()
                _sub += "\n编辑目标：{}".format(str(_src_show))
                if len(_opts) > 1:
                    _sub += "\n来源：{}".format(os.path.basename(str(_gen) or ""))
                if hidden:
                    _sub += "（已隐藏）"
                card = spider._ui_site_card(
                    kit,
                    ("🚫 " if hidden else "✨ ") + dir_name,
                    _sub,
                    batch_selected.get(item_key, False), on_toggle, actions, dim=hidden,
                    per_row=4)
                return card

            def refresh_list():
                sites_container.removeAllViews()
                if not spider.localized_interfaces:
                    sites_container.addView(kit.empty("暂无本地接口记录"), kit.lp(-1, -2))
                    kit.fill_spring(sites_container, 0)
                    return
                for info in spider.localized_interfaces:
                    sites_container.addView(
                        make_item_card(info), kit.lp(-1, -2))
                kit.fill_spring(sites_container, 0)

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

            def batch_delete():
                """[要求] 一键删除勾选的记录（只删记录，不动磁盘文件）"""
                selected_keys = [k for k, v in batch_selected.items() if v]
                if not selected_keys:
                    kit.toast("请先勾选要删除的接口")
                    return

                def _yes():
                    kill = set(selected_keys)
                    rest = []
                    for i in spider.localized_interfaces:
                        k = (i.get("parent_dir", ""), i["dir_name"])
                        if k in kill:
                            try:
                                spider._persist_mark_deleted(
                                    'localized_interfaces',
                                    "{}/{}".format(
                                        str(k[0]).strip().rstrip('/'),
                                        str(k[1]).strip()))
                            except Exception:
                                pass
                            batch_selected.pop(k, None)
                            continue
                        rest.append(i)
                    spider.localized_interfaces = rest
                    spider._save_config_to_file()
                    refresh_list()
                    kit.toast("已删除 {} 条记录".format(len(kill)))

                spider._show_modern_confirm(
                    "删除记录",
                    "确定删除勾选的 {} 条记录？\n（只删记录，不删磁盘文件）".format(
                        len(selected_keys)), _yes)

            # [要求] 第一行：全选 / 反选 / 清空（选择类）
            list_card.addView(
                kit.button_bar([
                    {"text": "全选", "style": "secondary", "callback": select_all_items, "dismiss": False},
                    {"text": "反选", "style": "secondary", "callback": invert_items, "dismiss": False},
                    {"text": "清空", "style": "secondary", "callback": clear_select, "dismiss": False},
                ], size="sm", per_row=3),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XS, 0.0, 0.0)))
            # [要求] 第二行：批量显隐 / 删除（操作类，删除在批量显隐后面）
            list_card.addView(
                kit.button_bar([
                    {"text": "批量显隐", "style": "soft_brand", "callback": batch_toggle_visibility, "dismiss": False},
                    {"text": "🗑 删除", "style": "danger", "callback": batch_delete, "dismiss": False},
                ], size="sm", per_row=2),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_XS, 0.0, UITheme.S_SM)))

            container.addView(list_card, kit.lp(-1, -2))
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

            # [要求] 「清空所有记录」与「关闭」并排放在底部
            buttons = [
                {"text": "🗑 清空所有记录", "style": "danger",
                 "callback": do_clear_all, "dismiss": False},
                {"text": "关闭", "style": "primary", "callback": None, "dismiss": True},
            ]
            self._show_dialog(act, "管理本地接口", container, buttons, height_ratio=0.88)
        self._run_on_ui(on_ui)

    def _scan_collect_files(self, selected_dirs, exts, dir_exts=None):
        """按目录 + 扩展名收集文件，返回 [(abspath, group_name)]（内容去重）

        dir_exts: {目录路径: [扩展名]} —— 允许每个目录单独指定扫描类型，
        缺省时回退到全局 exts。
        """
        all_files = []
        dir_exts = dir_exts or {}

        def _norm_exts(seq):
            out = []
            for e in (seq or []):
                e = str(e or "").strip().lower()
                if not e:
                    continue
                if not e.startswith('.'):
                    e = '.' + e
                if e not in out:
                    out.append(e)
            return out
        _excluded = self._scan_exclude_dirs()
        for _extra in (
                os.path.join(self.download_output_dir or "", "map"),
                os.path.join(self._work_subdir_base(), "map"),
                os.path.join(self._work_subdir_base(), self.COLLECTION_DIR_NAME),
                os.path.join(self.download_output_dir or "", self.COLLECTION_DIR_NAME)):
            try:
                if _extra:
                    _excluded.add(os.path.abspath(_extra))
            except Exception:
                pass

        def _dir_excluded(path):
            try:
                ap = os.path.abspath(path)
            except Exception:
                return False
            for ex in _excluded:
                if ap == ex or ap.startswith(ex.rstrip(os.sep) + os.sep):
                    return True
            return False

        for root_dir in selected_dirs:
            if not os.path.isdir(root_dir) or _dir_excluded(root_dir):
                continue
            # 每个目录可单独指定类型，没有指定则沿用全局类型
            use_exts = _norm_exts(dir_exts.get(root_dir)) or _norm_exts(exts)
            if not use_exts:
                continue
            root_name = os.path.basename(os.path.normpath(root_dir)) or "合集"
            for dirpath, dirnames, filenames in os.walk(root_dir):
                if _dir_excluded(dirpath):
                    dirnames[:] = []
                    continue
                # [规则] 跳过以 . 开头的隐藏目录（.git / .cache 等）
                dirnames[:] = [d for d in dirnames if not str(d).startswith('.')]
                for f in filenames:
                    # [规则] 跳过以 . 开头的隐藏文件
                    # （典型：.localize_manifest.json / .DS_Store）
                    if str(f).startswith('.'):
                        continue
                    if os.path.splitext(f)[1].lower() in use_exts:
                        all_files.append((os.path.join(dirpath, f), root_name))
        return all_files

    def _scan_dedup_files(self, all_files):
        """体积 + MD5 双层去重，返回 [(path, group)]"""
        size_groups = {}
        for file_path, grp in all_files:
            try:
                size_groups.setdefault(os.path.getsize(file_path), []).append(
                    (file_path, grp))
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

        # [修复] 去重键必须带上分组（目录）。
        # 原实现按全局 md5 去重，导致多个目录里内容相同的文件只剩第一个，
        # 其余目录被整个吃光 —— 表现就是「选了分开却只生成一个接口」。
        # 正确语义：同一个目录内部去重；跨目录各自保留，由各目录自行输出。
        content_hash = {}
        unique = []
        for _size, group in size_groups.items():
            if len(group) == 1:
                _p, _g = group[0]
                try:
                    with open(_p, 'rb') as _fp:
                        _fp.read(1)
                    unique.append((_p, _g))
                except Exception as _e:
                    self._log("跳过无法读取的文件 {}: {}".format(_p, _e), level='debug')
                continue
            for file_path, _g in group:
                try:
                    md5 = _file_md5(file_path)
                except Exception:
                    continue
                key = (md5, _g)
                if key not in content_hash:
                    content_hash[key] = file_path
                    unique.append((file_path, _g))
        # 保持目录顺序稳定，便于命名 _1 / _2 与目录列表一致
        order = {}
        for i, (p, g) in enumerate(all_files):
            order.setdefault(g, i)
        unique.sort(key=lambda x: (order.get(x[1], 0), x[0]))
        self._log("扫描去重：{} 个文件 -> {} 个".format(len(all_files), len(unique)))
        return unique

    def _inject_manager_site(self, sites):
        """在产物 sites 首位注入「⚙️ 本地包管理」入口。

        [要求] 生成产物逻辑与方法等同于当前程序：
        api 与 ext.config_file 用同一套拼接（同源目录，脚本名明文）。
        已存在同 key 入口时不重复注入。
        """
        if not (self.inject_manager_site and SELF_PATH):
            return False
        if any(isinstance(x, dict) and
               x.get("key") == "local_package_manager" for x in sites):
            return False
        try:
            _cfg_url = self._to_ext_config_url(self._manager_config_file())
            manager_site = {
                "key": "local_package_manager",
                "name": "⚙️ 本地包管理",
                "type": 3,
                "style": {"type": "list", "ratio": 1.43},
                "api": self._manager_script_url(_cfg_url),
                "ext": {"config_file": _cfg_url},
                "searchable": 1,
                "quickSearch": 1,
            }
            sites.insert(0, manager_site)
            return True
        except Exception:
            return False

    def _after_generate_rescan(self, names, kit=None):
        """生成产物后，继续执行「扫描本地接口」的效果。

        [要求] 接口改装中心「生成并保存」、扫描本地爬虫程序扫描完毕，
        在产物落地后都要自动跑一遍扫描本地接口：
        新接口被收录进 localized_interfaces，首页宫格随即出现对应入口，
        无需用户再手动点一次「扫描本地接口」。
        """
        try:
            roots = [str(x) for x in (getattr(self, 'root_dirs', None) or []) if x]
            base = str(getattr(self, 'download_output_dir', '') or '').strip()
            if base and base not in roots:
                roots.insert(0, base)
            if not roots:
                self._log("生成后自动扫描跳过：未设置任何目录", level='debug')
                return False
            self._rescan_localized_interfaces(roots)
            try:
                self._save_config_to_file()
            except Exception:
                pass
            hit = 0
            try:
                got = set(str(i.get('dir_name') or '') for i in self.localized_interfaces)
                hit = len([n for n in (names or []) if n in got])
            except Exception:
                pass
            self._log("生成后自动扫描完成，新接口已收录 {} 个".format(hit))
            if kit:
                try:
                    kit.toast("已收录 {} 个新接口，宫格已刷新".format(hit), long=True)
                except Exception:
                    pass
            return True
        except Exception as e:
            self._log("生成后自动扫描失败（不影响产物）: {}".format(e))
            return False

    def _write_scan_package(self, folder_name, items):
        """在本地包目录下建 <名称>/ 并写 <名称>.json（不建 map、不写宫格数据）"""
        base = str(getattr(self, 'download_output_dir', '') or '')
        if not base:
            raise ValueError("未设置本地包输出目录")
        folder = os.path.join(base, folder_name)
        os.makedirs(folder, exist_ok=True)

        sites = []
        name_count = {}
        for file_path, ext in items:
            stem = os.path.splitext(os.path.basename(file_path))[0]
            if stem in name_count:
                name_count[stem] += 1
                final_name = "{}-{}".format(stem, name_count[stem])
            else:
                name_count[stem] = 1
                final_name = stem
            label = ext[1:].upper() if ext.startswith('.') else ext.upper()
            sites.append({
                "key": final_name,
                "name": "{}|[{}]".format(final_name, label),
                "type": 3,
                "api": "file://" + os.path.abspath(file_path),
            })

        # [保持 code 固有逻辑] 扫描产物同样注入「本地包管理」入口，
        # api 与 config_file 同源拼接
        self._inject_manager_site(sites)

        out = os.path.join(folder, "{}.json".format(folder_name))
        data = {"sites": sites, "warningText": WARNING_TEXT}
        if any(isinstance(x, dict) and
               x.get("key") == "local_package_manager" for x in sites):
            data["home"] = "local_package_manager"
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._log("扫描接口已生成: {}（{} 个文件）".format(out, len(sites)))
        return out

    def _scan_local_files_and_generate(self, selected_dirs=None, mode=None,
                                       name_map=None, base_name=None, exts=None,
                                       dir_exts=None):

        if selected_dirs is None:
            selected_dirs = self.scan_local_dirs
        if not selected_dirs:
            raise ValueError("没有选择任何扫描文件夹")

        exts = exts or self.scan_local_extensions
        if not exts:
            raise ValueError("未选择任何文件类型")
        exts = [e.lower() if e.startswith('.') else '.' + e.lower() for e in exts]

        mode = (str(mode or getattr(self, 'scan_output_mode', 'merged') or 'merged')
                .strip().lower())
        if mode not in ("merged", "multi"):
            mode = "merged"
        base_name = str(base_name or getattr(self, 'scan_output_name', '')
                        or '我的影视').strip() or '我的影视'
        name_map = name_map or {}

        all_files = self._scan_collect_files(selected_dirs, exts, dir_exts)
        if not all_files:
            raise ValueError("未找到任何匹配的文件")

        unique = self._scan_dedup_files(all_files)

        made = []
        if mode == "multi":
            groups = {}
            for file_path, grp in unique:
                groups.setdefault(grp, []).append(
                    (file_path, os.path.splitext(file_path)[1].lower()))
            i = 0
            for grp, items in groups.items():
                i += 1
                # 分组键是扫描目录名；name_map 可能按完整路径给，两种都兼容
                fname = str(name_map.get(grp) or "").strip()
                if not fname:
                    for k, v in name_map.items():
                        try:
                            if os.path.basename(os.path.normpath(str(k))) == grp:
                                fname = str(v or "").strip()
                                break
                        except Exception:
                            continue
                if not fname:
                    fname = "{}_{}".format(base_name, i)
                made.append((fname, self._write_scan_package(fname, items)))
            self._notify_app("已按 {} 个目录分别输出接口".format(len(groups)))
        else:
            items = [(p, os.path.splitext(p)[1].lower()) for p, _g in unique]
            made.append((base_name, self._write_scan_package(base_name, items)))
            self._notify_app("合集已生成「{}」，共 {} 个文件".format(
                base_name, len(items)))

        self.scan_output_mode = mode
        self.scan_output_name = base_name
        self._save_config_to_file()
        self._save_persistent_config()
        self._force_mirror_now()

        # [要求] 扫描完毕、产物落地后继续执行「扫描本地接口」的效果：
        # 自动收录新接口，首页宫格随即出现对应入口
        self._after_generate_rescan([n for n, _p in made])
        return made

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
    def _is_map_local_json(self, url):

        if not url or not isinstance(url, str):
            return False
        path = url[7:] if url.startswith('file://') else url
        if not os.path.isabs(path):
            return False
        map_dir = os.path.join(self._work_subdir_base(), "map")
        try:
            common = os.path.commonpath([path, map_dir])
            return common == map_dir
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
            self._log(f"【init】基础目录 = {self._get_base_dir()}")

            # [FIX BUG-07] 记录外部配置文件是否加载成功：
            # 成功时持久化快照对已有键"仅补缺"，不再覆盖——
            # 防止用户手动编辑 down_config.json 后被旧持久化静默回滚
            ext_file_loaded = False
            if ext:
                ext = self._normalize_config_keys(ext)
                self._log(f"【init】ext 键列表: {list(ext.keys())}")
                config_file = ext.get('config_file', '')
                self._log(f"【init】config_file 值: '{config_file}'")
                if config_file:
                    self._log(f"【init】开始加载外部配置: {config_file}")
                    cf_config = self._load_config_file(config_file)
                    if cf_config:
                        ext_file_loaded = True
                        self._config_file_path = (
                            getattr(self, "_config_resolved_path", None) or config_file)
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

            ext_provided_keys = set()
            if ext_file_loaded:
                ext_provided_keys = set(
                    k for k in (ext or {}) if k != 'config_file')
                self._log("【init】外部提供的键: {}".format(sorted(ext_provided_keys)))

            persistent = self._load_persistent_config()
            if persistent and isinstance(persistent, dict):
                self._log("【init】检测到持久化配置，开始合并...")
                persistent = self._normalize_config_keys(persistent)
                merged_count = 0
                for k, v in persistent.items():
                    if k == 'config_file':

                        if v and not self._config_file_path:
                            self._config_file_path = v
                            self._log("【init】已从持久化恢复配置文件路径")
                        continue
                    # [规则] ext 传来的配置只在「首次启动」生效并落盘；
                    # 之后一律以本地保存的配置为准 —— 这里 persistent 非空，
                    # 说明不是首次，所以任何键都以持久化为准。
                    # （列表类仍做并集：外部文件里新增的条目照样补进来，
                    #  但已存在条目的改名 / 改参数不会被外部文件冲掉）
                    if k in ext_provided_keys:
                        cur = self.config.get(k)
                        if isinstance(v, list) and isinstance(cur, list) \
                                and k in self.LIST_MERGE_KEYS:
                            merged = self._merge_unique_list(v, cur, k)
                            self.config[k] = merged
                        else:
                            self.config[k] = v
                        merged_count += 1
                        continue
                    if isinstance(v, dict) and k in self.config and isinstance(self.config[k], dict):
                        self.config[k].update(v)
                        merged_count += 1
                    else:
                        self.config[k] = v
                        merged_count += 1
                self._config_prune_deleted()
                self._apply_config(self.config)

                self._refresh_auto_scan_dir()
                self._log(f"【init】✅ 已合并持久化配置，共 {merged_count} 项")

                if getattr(self, '_recovered_from_backup', False):
                    try:
                        self._save_persistent_config()
                        self._recovered_from_backup = False
                        self._log("【init】✅ 备份恢复的数据已写回主配置")
                    except Exception as e:
                        self._log(f"回写恢复数据失败（下次仍会走备份）: {e}",
                                  level='error')
            
                self._original_oktv_url = persistent.get("original_oktv_url")

                msg = persistent.get("package_download_message")
                if msg:
                    self._package_download_message = msg
            else:
                self._original_oktv_url = None
                # [规则] 首次启动（还没有本地保存的配置，或配置已被删除）：
                # 把 ext 传来的配置固化落盘，之后一律以这份保存的配置为准，
                # 只有把配置文件删掉后重启，才会重新读取 ext。
                if ext_file_loaded:
                    try:
                        self._save_persistent_config()
                        self._log("【init】首次启动：ext 配置已保存，后续以本地配置为准")
                    except Exception as e:
                        self._log("【init】首次启动保存配置失败: {}".format(e),
                                  level='error')

            current_url = self._get_current_oktv_url()
            if current_url:
                if not self._is_map_local_json(current_url):

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

    # ==================== 管理中心子宫格：流程中心 / 接口部落 ====================
    # [设计] 原「管理中心」把功能宫格与收录宫格混在同一层，条目一多就要翻很久。
    # 这里拆成两个父宫格，子宫格数据完全沿用原 categoryContent('center') 的生成逻辑，
    # 只做位置迁移，字段（vod_id / action / remarks）一律不改，保证弹窗链路零改动。
    CENTER_TID_FLOW = "center_flow"
    CENTER_TID_TRIBE = "center_tribe"
    TID_DECRYPT_HUB = "decrypt_hub"
    TID_LOCALIZE_HUB = "localize_hub"

    # ---------- 宫格图标（统一 BMP 段，壳子可识别） ----------
    # [背景] 壳子在 vod_pic 为空时会取 vod_name 的前缀符号当图标渲染，
    # 但只识别 U+2600–U+27BF 这一段 BMP 符号；astral 区（🧭🗂🗃🩺🔖📺🎨💾🌐🚀📝 等）
    # 会渲染失败或直接空白。因此全部收口到 BMP 段，并按功能归类：
    # 同一类宫格共用一个图标，便于一眼分辨类型。
    ICON_FOLDER   = "☰"    # 归集 / 可下钻父宫格
    ICON_BATCH    = "⚙️"   # 批量执行
    ICON_TRANSFER = "➤"    # 传输 / 下载参数
    ICON_SCAN     = "✳️"   # 扫描
    ICON_MANAGE   = "✏️"   # 管理 / 编辑
    ICON_DECRYPT  = "✂️"   # 单项解密
    ICON_LOCALIZE = "✴️"   # 单项本地化
    ICON_STORE    = "✨️"   # 已收录接口
    ICON_DOCTOR   = "⚕️"   # 体检 / 检查
    ICON_LOG      = "⚡"    # 日志
    ICON_DIR      = "☷"    # 目录
    ICON_NET      = "☁️"   # 网络 / 在线
    ICON_NAMING   = "✒️"   # 命名
    ICON_UI       = "❖️"   # 界面 / 显示
    ICON_THEME    = "☾"    # 主题 / 深色
    ICON_BACKUP   = "⛨"    # 备份
    ICON_RESET    = "➰️"   # 恢复默认
    ICON_BACK     = "❤️"   # 回归 / 切回（原为 ❤️️ 双 FE0F 畸形序列）
    ICON_WARN     = "⚠️"   # 空态 / 警告

    @staticmethod
    def _is_sub_tid(tid, want):
        """兼容壳子回传 tid 带/不带结尾冒号两种情况。"""
        return str(tid or "").rstrip(":") == want

    def _folder_entry(self, tid, name, remark):
        """父宫格入口：声明为 folder 让壳子继续下钻 categoryContent。

        [重要] 这里绝不能带 action —— 壳子若优先响应 action 就会直接弹窗，
        永远不会进入下一层。子项照旧带 action，行为完全不变。
        """
        return {
            "vod_id": str(tid) + ":",
            "vod_name": name,
            "vod_pic": "",
            "vod_remarks": remark,
            "vod_tag": "folder",
        }

    def _fallback_submenu_dialog(self, title, items):
        """[兜底] 壳子不认 folder 下钻、把父宫格 id 打进 detailContent 时的伪宫格。

        用弹窗把子宫格条目列成按钮，点击触发原 action，功能不丢，只是少一层宫格观感。
        """
        spider = self

        def on_ui(act):
            kit = spider._kit(act)
            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))
            box.addView(kit.hint("当前壳子未识别下钻标记，已改用弹窗列出。"),
                        kit.lp(-1, -2))
            for it in items:
                act_name = it.get("action")
                if not act_name:
                    continue
                btn = kit.button("%s\n%s" % (it.get("vod_name", ""),
                                             it.get("vod_remarks", "")),
                                 "secondary", None, size="md")
                btn.setLayoutParams(kit.lp(-1, -2))
                kit.bind_click(btn, lambda a=act_name: (
                    spider._dialog_refs[-1].dismiss() if spider._dialog_refs else None,
                    spider.action(a)))
                box.addView(btn, kit.lp(-1, -2))
            spider._show_dialog(
                act, title, box,
                [{"text": "关闭", "style": "primary", "callback": None, "dismiss": True}],
                height_ratio=0.85)

        self._run_on_ui(on_ui)

    def _center_tribe_items(self):
        """接口部落子宫格：收录到的本地接口（原 center 里的 ✨️ 系列条目）。"""
        items = []
        for info in self.localized_interfaces:
            if info.get("hidden", False):
                continue
            parent_dir = info.get("parent_dir", "")
            dir_name = info["dir_name"]
            json_count = len(info.get("json_files", []))
            display_name = f"{self.ICON_STORE} {dir_name}"
            full_path = os.path.join(parent_dir, dir_name)

            # [FIX BUG-04] 同时编码 parent_dir，避免不同父目录下
            # 同名目录切换时命中错误接口（quote(safe='') 后两段均不含 '@'）
            encoded_dir = (urllib.parse.quote(str(parent_dir or ""), safe='') + '@'
                           + urllib.parse.quote(dir_name, safe=''))
            items.append({
                "vod_id": f"switch_localized_{encoded_dir}",
                "vod_name": display_name,
                "vod_pic": "",
                "vod_remarks": f"路径: {full_path} | JSON: {json_count} 个",
                "action": f"local_source_switch_localized:{encoded_dir}"
            })

        if not items:
            # 空态兜底：返回空列表会白屏，且必须无 action，避免被当成接口切换
            items.append({
                "vod_id": "tribe_empty",
                "vod_name": f"{self.ICON_WARN} 还没有收录任何本地接口",
                "vod_pic": "",
                "vod_remarks": "去 管理中心 › 流程中心 › 扫描本地接口 / 扫描本地爬虫程序",
            })
        return items

    def _center_tribe_remark(self):
        n = sum(1 for i in self.localized_interfaces if not i.get("hidden", False))
        return f"已收录 {n} 个本地接口，点击可切换" if n else "还没有收录本地接口"

    def _center_flow_items(self):
        """流程中心子宫格：接口改装中心 / 扫描本地接口 / 扫描本地爬虫程序 / 管理本地接口。"""
        items = []
        favorites = self._favorite_fragments_all()
        fav_count = len(favorites)
        items.append({
            "vod_id": "favorite_manage",
            "vod_name": f"{self.ICON_MANAGE} 接口改装中心",
            "vod_pic": "",
            "vod_remarks": ("已收藏 {} 个片段，可分类筛选后生成改装接口".format(fav_count)
                            if fav_count else "从本地接口挑片段，生成改装接口"),
            "action": "local_source_favorite_manage"
        })

        items.append({
            "vod_id": "rescan_localized",
            "vod_name": f"{self.ICON_SCAN} 扫描本地接口",
            "vod_pic": "",
            "vod_remarks": "扫描设置目录下的有效接口",
            "action": "local_source_rescan_localized"
        })

        items.append({
            "vod_id": "setting_scan_local_files",
            "vod_name": f"{self.ICON_SCAN} 扫描本地爬虫程序",
            "vod_pic": "",
            "vod_remarks": "扫描文件夹内的[PY | JS等]文件生成接口",
            "action": "local_source_scan_local_files"
        })

        items.append({
            "vod_id": "manage_switch",
            "vod_name": f"{self.ICON_MANAGE} 管理本地接口",
            "vod_pic": "",
            "vod_remarks": "删除/显隐/清空记录",
            "action": "local_source_manage_switch"
        })
        return items

    def _decrypt_hub_items(self):
        """解密归集子宫格：各在线接口的单条解密入口（原 decrypt 里的 ✂️ 系列条目）。"""
        items = []
        for site in self.package_download_sites:
            items.append({
                "vod_id": f"decrypt_{site['id']}",
                "vod_name": f"{self.ICON_DECRYPT} {site['name']}",
                "vod_pic": "",
                "vod_remarks": self._get_decrypt_status_text(site),
                "action": f"decrypt_site_{site['id']}",
            })

        if not items:
            # 空态兜底：返回空列表会白屏，且必须无 action
            items.append({
                "vod_id": "decrypt_hub_empty",
                "vod_name": f"{self.ICON_WARN} 还没有可解密的在线接口",
                "vod_pic": "",
                "vod_remarks": "去 设置 › 在线接口管理 添加接口",
            })
        return items

    def _decrypt_hub_remark(self):
        n = len(self.package_download_sites or [])
        return f"共 {n} 个接口，点击单独解密" if n else "暂无接口"

    def _localize_doctor_item(self):
        """本地包体检条目：常驻「本地」一层，紧跟批量本地之后。"""
        pkg_count = len(self._localized_package_dirs())
        return {
            "vod_id": "package_doctor",
            "vod_name": f"{self.ICON_DOCTOR} 本地包体检",
            "vod_pic": "",
            "vod_remarks": (f"检查 {pkg_count} 个本地包是否完整"
                            f"（缺失/截断可补下）" if pkg_count
                            else "还没有本地包，先执行一次本地化"),
            "action": "local_source_package_doctor",
        }

    def _localize_hub_items(self):
        """本地化归集子宫格：各接口的单条本地化入口（本地包体检已移出至本地一层）。"""
        items = []
        for site in self.package_download_sites:
            items.append({
                "vod_id": f"localize_{site['id']}",
                "vod_name": f"{self.ICON_LOCALIZE} {site['name']}",
                "vod_pic": "",
                "vod_remarks": self._get_localize_status_text(site),
                "action": f"localize_site_{site['id']}",
            })

        if not items:
            # 空态兜底：返回空列表会白屏，且必须无 action
            items.append({
                "vod_id": "localize_hub_empty",
                "vod_name": f"{self.ICON_WARN} 还没有可本地化的在线接口",
                "vod_pic": "",
                "vod_remarks": "去 设置 › 在线接口管理 添加接口",
            })
        return items

    def _localize_hub_remark(self):
        n = len(self.package_download_sites or [])
        return f"共 {n} 个接口，点击单独本地化" if n else "暂无接口"

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
        if self._is_sub_tid(tid, self.CENTER_TID_FLOW):
            # 管理中心 › 流程中心（子宫格）
            return self._paged_result(self._center_flow_items(), page)

        elif self._is_sub_tid(tid, self.CENTER_TID_TRIBE):
            # 管理中心 › 接口部落（子宫格）
            return self._paged_result(self._center_tribe_items(), page)

        elif tid == "center":
            items = []

            original_url = self._original_oktv_url if self._original_oktv_url else "未获取到"
            remark = f"当前: {original_url}"
            items.append({
                "vod_id": "switch_to_original",
                "vod_name": f"{self.ICON_BACK} 回归",
                "vod_pic": "",
                "vod_remarks": remark,
                "action": "local_source_switch_to_original"
            })

            items.append(self._folder_entry(
                self.CENTER_TID_FLOW, f"{self.ICON_FOLDER} 流程中心",
                "接口改装中心 · 扫描本地接口 · 扫描本地爬虫程序 · 管理本地接口"))

            items.append(self._folder_entry(
                self.CENTER_TID_TRIBE, f"{self.ICON_FOLDER} 接口部落",
                self._center_tribe_remark()))

            return self._paged_result(items, page)

        elif self._is_sub_tid(tid, self.TID_DECRYPT_HUB):
            # 解密 › 解密归集（子宫格）
            return self._paged_result(self._decrypt_hub_items(), page)

        elif self._is_sub_tid(tid, self.TID_LOCALIZE_HUB):
            # 本地 › 本地化归集（子宫格）
            return self._paged_result(self._localize_hub_items(), page)

        elif tid == "decrypt":
            items = []
            items.append({
                "vod_id": "decrypt_all",
                "vod_name": f"{self.ICON_BATCH} 批量解密",
                "vod_pic": "",
                "vod_remarks": "选择多个接口同时解密",
                "action": "decrypt_all"
            })
            items.append(self._folder_entry(
                self.TID_DECRYPT_HUB, f"{self.ICON_FOLDER} 解密归集",
                self._decrypt_hub_remark()))
            return self._paged_result(items, page)

        elif tid == "localize":
            items = []
            items.append({
                "vod_id": self.ACTION_DOWNLOAD_PACKAGE,
                "vod_name": f"{self.ICON_BATCH} 批量本地",
                "vod_pic": "",
                "vod_remarks": "选择多个接口生成本地包",
                "action": self.ACTION_DOWNLOAD_PACKAGE
            })
            items.append(self._localize_doctor_item())
            items.append(self._folder_entry(
                self.TID_LOCALIZE_HUB, f"{self.ICON_FOLDER} 本地化归集",
                self._localize_hub_remark()))
            return self._paged_result(items, page)

        elif tid == "settings":

            items = [
                {"vod_id": "show_log", "vod_name": f"{self.ICON_LOG} 日志面板", "vod_pic": "", "vod_remarks": "实时查看下载日志与进度", "action": "show_log"},
            ]
            items.append(self._setting_group_entry("log"))
            items.append(self._setting_group_entry("dirs"))
            items.append({"vod_id": "setting_sites", "vod_name": f"{self.ICON_MANAGE} 在线接口管理", "vod_pic": "", "vod_remarks": "添加/删除/更新在线源", "action": "local_source_manage_sites"})
            items.append(self._setting_group_entry("behavior"))
            items.append(self._setting_group_entry("transfer"))
            items.append(self._setting_group_entry("network"))
            items.append(self._setting_group_entry("naming"))
            items.append({"vod_id": "setting_tv_mode", "vod_name": f"{self.ICON_UI} TV 模式（遥控器焦点）", "vod_pic": "", "vod_remarks": self._tv_mode_text(), "action": "local_source_edit_tv_mode"})
            items.append({"vod_id": "setting_ui_theme", "vod_name": f"{self.ICON_THEME} 深色模式", "vod_pic": "", "vod_remarks": self._ui_theme_text(), "action": "local_source_edit_ui_theme"})
            items.append({"vod_id": "setting_config_backup_manage", "vod_name": f"{self.ICON_BACKUP} 配置备份管理", "vod_pic": "", "vod_remarks": self._config_backup_count_text(), "action": "local_source_config_backup_manage"})

            items.append({"vod_id": "setting_restore_default", "vod_name": f"{self.ICON_RESET} 恢复默认设置", "vod_pic": "", "vod_remarks": "恢复初始配置（清除运行时修改）", "action": "local_source_restore_default"})
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
        # [诊断/兜底] 正常下钻不会走到这里；一旦走到，说明该壳子不认 folder 标记
        if self._is_sub_tid(vid, self.CENTER_TID_FLOW):
            self._log("壳子未识别下钻标记：流程中心，已用弹窗兜底", level='warn')
            self._fallback_submenu_dialog(f"{self.ICON_FOLDER} 流程中心", self._center_flow_items())
            return {"list": [{"vod_name": "流程中心", "vod_remarks": "已在弹窗中列出"}]}
        if self._is_sub_tid(vid, self.CENTER_TID_TRIBE):
            self._log("壳子未识别下钻标记：接口部落，已用弹窗兜底", level='warn')
            self._fallback_submenu_dialog(f"{self.ICON_FOLDER} 接口部落", self._center_tribe_items())
            return {"list": [{"vod_name": "接口部落", "vod_remarks": "已在弹窗中列出"}]}
        if self._is_sub_tid(vid, self.TID_DECRYPT_HUB):
            self._log("壳子未识别下钻标记：解密归集，已用弹窗兜底", level='warn')
            self._fallback_submenu_dialog(f"{self.ICON_FOLDER} 解密归集", self._decrypt_hub_items())
            return {"list": [{"vod_name": "解密归集", "vod_remarks": "已在弹窗中列出"}]}
        if self._is_sub_tid(vid, self.TID_LOCALIZE_HUB):
            self._log("壳子未识别下钻标记：本地化归集，已用弹窗兜底", level='warn')
            self._fallback_submenu_dialog(f"{self.ICON_FOLDER} 本地化归集", self._localize_hub_items())
            return {"list": [{"vod_name": "本地化归集", "vod_remarks": "已在弹窗中列出"}]}
        if vid == self.ACTION_DOWNLOAD_PACKAGE:
            def do_download(selected_sites):
                self._exec_with_log(self._start_package_download, selected_sites)
            self._show_modern_batch_selector_v2("选择批量本地接口", do_download, "本地化", UITheme.SUCCESS)
            return {"list": [{"vod_name": "批量本地", "vod_remarks": "请选择接口"}]}
        if vid == "decrypt_all":
            def do_decrypt(selected_sites):
                self._exec_with_log(self._decrypt_sites, selected_sites)
            self._show_modern_batch_selector_v2("选择批量解密接口", do_decrypt, "解密", UITheme.BRAND)
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
    
        if action == "local_source_favorite_manage":
            self._open_favorite_manage_dialog()
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
                self._show_modern_batch_selector_v2("选择批量本地接口", do_download, "本地化", UITheme.SUCCESS)
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
            self._show_modern_batch_selector_v2("选择批量解密接口", do_decrypt, "解密", UITheme.BRAND)
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
        elif action == 'local_source_edit_ui_theme':
            self._open_ui_theme_dialog()
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

    def _clear_site_op(self, site_id):

        try:
            with self._site_op_lock:

                self._site_op_threads.pop(site_id, None)
                self._site_cancel_events.pop(site_id, None)
        except Exception:
            pass

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

            # [修复] 只读不再用 setKeyListener(None)：
            # 它会把 inputType 变成 TYPE_NULL，部分 ROM 上恢复失败，
            # 导致进入编辑态后输入法再也调不出来。
            # 改为：保住 KeyListener / inputType，只用
            # setShowSoftInputOnFocus(False) + 隐藏光标来实现"只读观感"。
            state_key_listener = {"orig": None, "itype": 0}

            def _set_ime_enabled(v, on):
                """控制"获得焦点时是否弹出输入法"（API 21+），失败则忽略"""
                for _m in ("setShowSoftInputOnFocus",
                           "setSoftInputShownOnFocus"):
                    try:
                        getattr(v, _m)(bool(on))
                        return True
                    except Exception:
                        continue
                return False

            try:
                state_key_listener["orig"] = edit.getKeyListener()
                state_key_listener["itype"] = edit.getInputType()
            except Exception:
                pass

            try:
                # 焦点能力全程保留（TV 需要能选中 / 滚动；编辑时才能弹输入法）
                edit.setFocusable(True)
                edit.setFocusableInTouchMode(True)
                edit.setClickable(True)
                edit.setLongClickable(True)
                edit.setCursorVisible(False)
                _set_ime_enabled(edit, False)
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
                    # 焦点能力全程保留，只读 / 编辑只切换 IME 与光标
                    edit.setFocusable(True)
                    edit.setFocusableInTouchMode(True)
                    edit.setClickable(True)
                    edit.setLongClickable(True)
                    try:
                        edit.setTextIsSelectable(True)
                    except Exception:
                        pass

                    if on:
                        # 兜底：若 KeyListener 曾被置空，按原始 inputType 复原
                        try:
                            if edit.getKeyListener() is None:
                                _kl = state_key_listener.get("orig")
                                if _kl is not None:
                                    edit.setKeyListener(_kl)
                                _it = state_key_listener.get("itype")
                                if _it:
                                    edit.setInputType(int(_it))
                        except Exception:
                            pass
                        edit.setCursorVisible(True)
                        _set_ime_enabled(edit, True)
                        try:
                            edit.requestFocus()
                            _t = edit.getText()
                            edit.setSelection(len(str(_t)) if _t is not None else 0)
                        except Exception:
                            pass
                        kit.show_keyboard(edit)
                    else:
                        edit.setCursorVisible(False)
                        _set_ime_enabled(edit, False)
                        try:
                            kit.hide_keyboard(edit)
                        except Exception:
                            pass
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
                """跳转前关闭所有弹窗（与其他跳转按钮行为一致）"""
                def _run():
                    try:
                        d = dlg_holder.get("dialog")
                        if d is not None:
                            d.dismiss()
                    except Exception:
                        pass
                    try:
                        spider._dismiss_all_dialogs()
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

            # [修复] 顶部工具条会随长文本一起滚出屏幕，滚到底就点不到按钮了。
            # 这里在底部固定栏再放一份常用操作，滚动到任何位置都能直接点。
            buttons = [
                {"text": "✏️ 编辑/锁定", "style": "primary",
                 "callback": toggle_edit, "dismiss": False},
                {"text": "💾 保存", "style": "success",
                 "callback": do_save_content, "dismiss": False},
                {"text": "📋 复制", "style": "secondary",
                 "callback": copy_content, "dismiss": False},
            ]
            if jump_cb:
                buttons.append({
                    "text": "🚀 跳转", "style": "success",
                    "callback": _wrap_dismiss(jump_cb), "dismiss": False})
            buttons += [
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
            return "{} 份备份 · 可新建/恢复/改名/删除".format(len(backups))
        except Exception:
            return "新建/恢复/改名/删除配置备份"

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
                                           margins=(UITheme.S_XS, 0.0, 0.0, 0.0)))
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

            _mv = getattr(spider, "tv_mode", None)
            cur_auto = not isinstance(_mv, bool)
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
                spider._save_config_to_file()
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
                # [FIX BUG-12] 单引号串 → 双引号串需逐字符转换：
                # 简单的 replace 链会把 \' 、\" 、\\ 错误转义成非法 JSON。
                # 规则（JS 风格宽松串惯例）：
                #   \'  → '      （JSON 中无需转义）
                #   \"  → \"     （保持转义的引号）
                #   \\  → \\\\   （保持转义的反斜杠）
                #   裸 " → \"
                out = []
                i = 0
                n = len(inner)
                while i < n:
                    ch = inner[i]
                    if ch == '\\' and i + 1 < n:
                        nxt = inner[i + 1]
                        if nxt == "'":
                            out.append("'")
                        elif nxt == '"':
                            out.append('\\"')
                        elif nxt == '\\':
                            out.append('\\\\')
                        else:
                            out.append(inner[i:i + 2])
                        i += 2
                        continue
                    if ch == '"':
                        out.append('\\"')
                    else:
                        out.append(ch)
                    i += 1
                tok = '"' + ''.join(out) + '"'
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

    def _show_modern_batch_selector_v2(self, title, callback, action_name="执行", action_color=None):

        if action_color is None:
            action_color = UITheme.BRAND
        """统一批量选择器（解密 / 本地化共用）：卡片式列表，风格与其它弹窗完全一致。"""
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
                                        # [FIX BUG-16] 先添加/更新成功后再清理旧条目：
                                        # 原先"先删后加"在添加失败（如重名/超限）时
                                        # 会把旧接口配置一并丢失
                                        spider._add_or_update_package_download_site(new_name, new_url)
                                        if new_name != sname or new_url != surl:
                                            if any(x.get("id") == s.get("id")
                                                   for x in spider.package_download_sites):
                                                spider._delete_package_download_sites([s.get("id")])
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
