# -*- coding: utf-8 -*-
# @tvbox-role manager
"""
TVBox 本地多目录源扫描器（安全优化版）
====================================

用途：
1. 扫描明确配置的 PY / JS / XBPQ / HTML 目录。
2. 将扫描结果写入 WebHTV 原生站点注入注册表。
3. 保留 registry.json 中的手工注入项，仅替换本脚本生成的条目。
4. 在 TVBox 中按类型浏览、搜索本地源，并可通过 action 重新扫描。
5. 提供持久化扫描开关和一键清除自动注入站点，清除后自动重载 App。
6. 扫描种类集中在“扫描配置”分类，Toggle 只保存待应用值，由“应用并加载”一次执行。
7. 支持单文件忽略、增量扫描、变更预览、单份循环备份、撤销和并发写入保护。
8. “一键扫描并加载”会复用 WebHTV 本机管理接口重载并校验当前站点列表。
9. 可用 auto-loader.roots.json 配置扫描目录和文件数、深度、单文件大小上限。
10. 所有操作只在进入页面或用户点击时执行，不启动后台扫描、定时器或文件监听。

说明：
- 脚本会自动探测 Android 共享存储根目录，再定位 TV/CustomCsp/registry.json。
- 站点根目录优先读取 TVBOX_HOME，否则自动识别 tvbox/TVBox 及子目录大小写。
- 扫描后无需选择新的点播文件；刷新点播配置或重启 App 即可。
- Python Spider 无法主动刷新 App 已缓存的站点列表。

可选文件标识（放在文件前 64 KB 的注释中）：
- @tvbox-source：明确作为站点源收录。
- @tvbox-ignore：明确忽略。
- @tvbox-role extension：WebHome/JS 扩展，不作为站点源。
- @tvbox-role library：依赖库，不作为站点源。
- @tvbox-role manager：配置管理脚本，不重复加入自动站点。
- 严格识别默认开启；特殊格式可使用 @tvbox-source 强制收录。
"""

import hashlib
import json
import os
import re
import shutil
import threading
import time
import urllib.parse
import urllib.request

from base.spider import Spider as BaseSpider


def _detect_storage_root():
    candidates = []
    external = str(os.environ.get("EXTERNAL_STORAGE", "")).strip()
    if external:
        candidates.append(external)
    candidates.extend(("/sdcard", "/storage/emulated/0", os.path.expanduser("~/storage/shared")))
    seen = set()
    for candidate in candidates:
        path = os.path.abspath(os.path.expanduser(candidate))
        real = os.path.realpath(path)
        if real in seen:
            continue
        seen.add(real)
        if os.path.isdir(path):
            return real
    return os.path.abspath(external or "/sdcard")


def _detect_local_base(storage_root):
    candidates = []
    configured = str(os.environ.get("TVBOX_HOME", "")).strip()
    if configured:
        candidates.append(configured)
    candidates.extend(
        (
            os.path.join(storage_root, "tvbox"),
            os.path.join(storage_root, "TVBox"),
        )
    )
    for candidate in candidates:
        path = os.path.realpath(os.path.abspath(os.path.expanduser(candidate)))
        if os.path.isdir(path):
            return path
    return os.path.realpath(os.path.join(storage_root, "tvbox"))


def _detect_child_dir(base, *names):
    if os.path.isdir(base):
        try:
            entries = {
                name.lower(): name
                for name in os.listdir(base)
                if os.path.isdir(os.path.join(base, name))
            }
            for name in names:
                actual = entries.get(name.lower())
                if actual:
                    return os.path.join(base, actual)
        except Exception:
            pass
    return os.path.join(base, names[0])


DETECTED_STORAGE_ROOT = _detect_storage_root()
DETECTED_LOCAL_BASE = _detect_local_base(DETECTED_STORAGE_ROOT)


class RegistryChangedError(RuntimeError):
    pass


class Spider(BaseSpider):
    # ==========================================================================
    # 配置区
    # ==========================================================================
    SCAN_ROOTS = [
        {"path": _detect_child_dir(DETECTED_LOCAL_BASE, "py", "python"), "type": "PY", "extensions": [".py"]},
        {"path": _detect_child_dir(DETECTED_LOCAL_BASE, "js", "javascript"), "type": "JS", "extensions": [".js"]},
        {"path": _detect_child_dir(DETECTED_LOCAL_BASE, "XBPQ"), "type": "XBPQ", "extensions": [".json"]},
        {"path": _detect_child_dir(DETECTED_LOCAL_BASE, "html"), "type": "HTML", "extensions": [".html"]},
    ]

    # WebHTV 原生站点注入注册表。
    REGISTRY_PATH = os.path.join(DETECTED_STORAGE_ROOT, "TV", "CustomCsp", "registry.json")
    OUTPUT_PATH = REGISTRY_PATH
    STORAGE_ROOT = DETECTED_STORAGE_ROOT
    LOCAL_BASE_DIR = DETECTED_LOCAL_BASE

    JS_API = "./lib/drpy2-fast.min.js"
    XBPQ_API = "csp_XBPQ"
    HTML_API = "csp_Nostr"

    PAGE_SIZE = 60
    BACKUP_BEFORE_WRITE = True
    ALLOW_EMPTY_WRITE = False
    DEFAULT_SEARCHABLE = 1
    DEFAULT_QUICK_SEARCH = 1
    STRICT_RECOGNITION = True
    CACHE_VERSION = 1
    AUTO_RELOAD_APP = True
    APP_PORT_START = 9978
    APP_PORT_END = 9998
    APP_REQUEST_TIMEOUT = 0.35
    MAX_BACKUPS = 1
    MAX_SCAN_FILES = 3000
    MAX_SCAN_DEPTH = 8
    MAX_SOURCE_SIZE = 5 * 1024 * 1024

    GENERATED_KEY_PREFIX = "local_auto_"
    GENERATED_INSERT_INDEX = None  # None 表示追加；也可填写 0、1、2……

    JS_EXCLUDE = {
        "drpy2-fast.min.js",
        "drpy2.min.js",
        "drpy2-obj.min.js",
        "drpy2-template.js",
        "drpy2.js",
        "config.js",
    }
    SKIP_DIRS = {
        "__pycache__",
        "node_modules",
        ".git",
        ".svn",
        "lib",
        "libs",
        "extension",
        "extensions",
        "webhomeextensions",
    }
    PY_EXCLUDE_RELATIVE = {"base/spider.py"}
    MANAGER_FILES = {"自动加载.py", "自动加载-优化版.py"}
    JS_EXTENSION_SUFFIXES = (".ext.js", ".extension.js", ".user.js")
    # ==========================================================================

    TYPE_ORDER = {"PY": 0, "JS": 1, "XBPQ": 2, "HTML": 3}
    TYPE_PREFIX = {
        "PY": "",
        "JS": "",
        "XBPQ": "",
        "HTML": "",
    }
    TYPE_GROUP = {
        "PY": "[py]",
        "JS": "[js]",
        "XBPQ": "[xbpq]",
        "HTML": "[html]",
    }
    TYPE_EXTENSIONS = {
        "PY": [".py"],
        "JS": [".js"],
        "XBPQ": [".json"],
        "HTML": [".html"],
    }
    SCAN_SETTINGS_TID = "scan_settings"
    BACKUPS_TID = "scan_backups"
    STATUS_ID = "__local_source_status__"
    RESCAN_ID = "__local_source_rescan__"
    TOGGLE_SCAN_ID = "__local_source_toggle_scan__"
    CLEAR_SITES_ID = "__local_source_clear_sites__"
    RESTORE_BACKUP_ID = "__local_source_restore_backup__"
    DELETE_BACKUPS_ID = "__local_source_delete_backups__"
    ACTION_RESCAN = "local_source_rescan"
    ACTION_TOGGLE_SCAN = "local_source_toggle_scan"
    ACTION_CLEAR_SITES = "local_source_clear_sites"
    ACTION_RESTORE_BACKUP = "local_source_restore_backup"
    ACTION_DELETE_BACKUPS = "local_source_delete_backups"
    ACTION_APPLY_SCAN_CONFIG = "local_source_apply_scan_config"
    ACTION_TOGGLE_TYPE_PREFIX = "local_source_toggle_type:"
    ACTION_TOGGLE_IGNORE_PREFIX = "local_source_toggle_ignore:"
    ACTION_RESTORE_SNAPSHOT_PREFIX = "local_source_restore_snapshot:"
    ACTION_SOURCE_PREFIX = "local_source_info:"

    def __init__(self):
        super().__init__()
        self.lock = threading.RLock()
        self.inited = False
        self.scan_roots = [dict(item) for item in self.SCAN_ROOTS]
        self.registry_path = self.REGISTRY_PATH
        self.output_path = self.OUTPUT_PATH
        self.settings_path = os.path.join(os.path.dirname(self.REGISTRY_PATH), "auto-loader.settings.json")
        self.cache_path = os.path.join(os.path.dirname(self.REGISTRY_PATH), "auto-loader.cache.json")
        self.backup_dir = os.path.join(os.path.dirname(self.REGISTRY_PATH), "backups")
        self.roots_config_path = os.path.join(
            os.path.dirname(self.REGISTRY_PATH), "auto-loader.roots.json"
        )
        self.js_api = self.JS_API
        self.xbpq_api = self.XBPQ_API
        self.html_api = self.HTML_API
        self.page_size = self.PAGE_SIZE
        self.max_scan_files = self.MAX_SCAN_FILES
        self.max_scan_depth = self.MAX_SCAN_DEPTH
        self.max_source_size = self.MAX_SOURCE_SIZE
        self.backup_before_write = self.BACKUP_BEFORE_WRITE
        self.allow_empty_write = self.ALLOW_EMPTY_WRITE
        self.generated_insert_index = self.GENERATED_INSERT_INDEX
        self.scan_enabled = True
        self.type_enabled = {source_type: True for source_type in self.TYPE_ORDER}
        self.pending_type_enabled = dict(self.type_enabled)
        self.config_dirty = False
        self.ignored_sources = set()
        self.strict_recognition = self.STRICT_RECOGNITION
        self.auto_reload_app = self.AUTO_RELOAD_APP
        self.app_server_ports = list(range(self.APP_PORT_START, self.APP_PORT_END + 1))
        self.last_app_port = 0
        self.cache = self._empty_cache()
        self.status = self._empty_status()

    def getName(self):
        return "本地源自动扫描（安全版）"

    def init(self, extend=""):
        with self.lock:
            if self.inited:
                return
            self._apply_extend(extend)
            self._load_roots_config()
            self._load_settings()
            try:
                self._normalize_backup_storage()
            except Exception as exc:
                self._warn("历史备份整理失败: {}".format(exc))
            if self.scan_enabled:
                self._refresh_locked()
            else:
                self._set_scan_disabled_status()
            self.inited = True

    def _empty_cache(self):
        return {
            "sources": [],
            "ignored": [],
            "source_index": {},
            "type_counts": {},
            "ignored_counts": {},
        }

    def _empty_status(self):
        return {
            "scan_time": "-",
            "found": 0,
            "included": 0,
            "skipped": 0,
            "duplicates": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "ignored": 0,
            "stale_ignored_removed": 0,
            "limit_reached": False,
            "manual_sites": 0,
            "generated_sites": 0,
            "added_sites": 0,
            "updated_sites": 0,
            "removed_sites": 0,
            "unchanged_sites": 0,
            "registry_changed": False,
            "write_state": "尚未扫描",
            "written": False,
            "warnings": [],
            "error": "",
        }

    # --------------------------------------------------------------------------
    # 可选 extend 配置
    # --------------------------------------------------------------------------
    def _apply_extend(self, extend):
        data = self._parse_extend(extend)
        if not isinstance(data, dict):
            return

        roots = data.get("scan_roots", data.get("scanRoots"))
        if isinstance(roots, list):
            normalized = self._normalize_scan_roots(roots)
            if normalized:
                self.scan_roots = normalized

        self.registry_path = self._string_option(
            data, ("registry_path", "registryPath", "base_config_path", "baseConfigPath"), self.registry_path
        )
        self.output_path = self._string_option(
            data, ("output_path", "outputPath"), self.registry_path
        )
        self.settings_path = self._string_option(
            data,
            ("settings_path", "settingsPath"),
            os.path.join(os.path.dirname(self.output_path), "auto-loader.settings.json"),
        )
        self.cache_path = self._string_option(
            data,
            ("cache_path", "cachePath"),
            os.path.join(os.path.dirname(self.output_path), "auto-loader.cache.json"),
        )
        self.backup_dir = self._string_option(
            data,
            ("backup_dir", "backupDir"),
            os.path.join(os.path.dirname(self.output_path), "backups"),
        )
        self.roots_config_path = self._string_option(
            data,
            ("roots_config_path", "rootsConfigPath"),
            os.path.join(os.path.dirname(self.output_path), "auto-loader.roots.json"),
        )
        self.js_api = self._string_option(data, ("js_api", "jsApi"), self.js_api)
        self.xbpq_api = self._string_option(data, ("xbpq_api", "xbpqApi"), self.xbpq_api)
        self.html_api = self._string_option(data, ("html_api", "htmlApi"), self.html_api)
        self.page_size = self._int_option(data, ("page_size", "pageSize"), self.page_size, 1, 200)
        self.max_scan_files = self._int_option(
            data, ("max_scan_files", "maxScanFiles"), self.max_scan_files, 1, 20000
        )
        self.max_scan_depth = self._int_option(
            data, ("max_scan_depth", "maxScanDepth"), self.max_scan_depth, 0, 32
        )
        self.max_source_size = self._int_option(
            data,
            ("max_source_size", "maxSourceSize"),
            self.max_source_size,
            1024,
            100 * 1024 * 1024,
        )
        self.backup_before_write = self._bool_option(
            data, ("backup_before_write", "backupBeforeWrite"), self.backup_before_write
        )
        self.allow_empty_write = self._bool_option(
            data, ("allow_empty_write", "allowEmptyWrite"), self.allow_empty_write
        )
        self.strict_recognition = self._bool_option(
            data, ("strict_recognition", "strictRecognition"), self.strict_recognition
        )
        self.auto_reload_app = self._bool_option(
            data, ("auto_reload_app", "autoReloadApp"), self.auto_reload_app
        )
        if "generated_insert_index" in data or "generatedInsertIndex" in data:
            value = data.get("generated_insert_index", data.get("generatedInsertIndex"))
            try:
                self.generated_insert_index = max(0, int(value))
            except Exception:
                self.generated_insert_index = None

    def _parse_extend(self, extend):
        if isinstance(extend, dict):
            return extend
        if not isinstance(extend, str) or not extend.strip():
            return {}
        text = extend.strip()
        try:
            return json.loads(text)
        except Exception:
            pass
        path = text.replace("file://", "")
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as fp:
                    return json.load(fp)
            except Exception:
                return {}
        return {}

    def _load_roots_config(self):
        path = os.path.abspath(os.path.expanduser(self.roots_config_path))
        if not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if isinstance(data, list):
                roots = data
                limits = {}
            elif isinstance(data, dict):
                roots = data.get("roots", data.get("scan_roots", []))
                limits = data.get("limits", {})
            else:
                raise ValueError("顶层必须是数组或 JSON 对象")
            normalized = self._normalize_scan_roots(roots) if isinstance(roots, list) else []
            if normalized:
                self.scan_roots = normalized
            if isinstance(limits, dict):
                self.max_scan_files = self._int_option(
                    limits,
                    ("max_files", "maxFiles"),
                    self.max_scan_files,
                    1,
                    20000,
                )
                self.max_scan_depth = self._int_option(
                    limits,
                    ("max_depth", "maxDepth"),
                    self.max_scan_depth,
                    0,
                    32,
                )
                self.max_source_size = self._int_option(
                    limits,
                    ("max_file_size", "maxFileSize"),
                    self.max_source_size,
                    1024,
                    100 * 1024 * 1024,
                )
        except Exception as exc:
            self._warn("扫描目录配置读取失败，将使用自动探测目录: {}".format(exc))

    def _normalize_scan_roots(self, roots):
        result = []
        seen = set()
        for item in roots:
            if isinstance(item, str):
                path = item
                source_type = os.path.basename(path).upper()
                if source_type == "HTML":
                    pass
                elif source_type == "XBPQ":
                    pass
                elif source_type not in ("PY", "JS"):
                    continue
                extensions = self.TYPE_EXTENSIONS[source_type]
            elif isinstance(item, dict):
                path = str(item.get("path", "")).strip()
                source_type = str(item.get("type", "")).strip().upper()
                if source_type not in self.TYPE_ORDER:
                    continue
                extensions = item.get("extensions", self.TYPE_EXTENSIONS[source_type])
            else:
                continue
            if not path:
                continue
            if not isinstance(extensions, (list, tuple)):
                extensions = [extensions]
            extensions = [self._normalize_extension(ext) for ext in extensions]
            extensions = [ext for ext in extensions if ext]
            if not extensions:
                extensions = list(self.TYPE_EXTENSIONS[source_type])
            identity = (os.path.abspath(os.path.expanduser(path)), source_type)
            if identity in seen:
                continue
            seen.add(identity)
            result.append({"path": path, "type": source_type, "extensions": extensions})
        return result

    def _string_option(self, data, keys, fallback):
        for key in keys:
            if key in data and str(data.get(key, "")).strip():
                return str(data[key]).strip()
        return fallback

    def _int_option(self, data, keys, fallback, minimum, maximum):
        for key in keys:
            if key not in data:
                continue
            try:
                return max(minimum, min(maximum, int(data[key])))
            except Exception:
                return fallback
        return fallback

    def _bool_option(self, data, keys, fallback):
        for key in keys:
            if key not in data:
                continue
            value = data[key]
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            return str(value).strip().lower() in ("1", "true", "yes", "on")
        return fallback

    def _load_settings(self):
        path = os.path.abspath(os.path.expanduser(self.settings_path))
        if not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if not isinstance(data, dict):
                return
            value = data.get("scan_enabled", data.get("scanEnabled", True))
            self.scan_enabled = self._as_bool(value, True)
            type_enabled = data.get("type_enabled", data.get("typeEnabled", {}))
            if isinstance(type_enabled, dict):
                for source_type in self.TYPE_ORDER:
                    if source_type in type_enabled:
                        self.type_enabled[source_type] = self._as_bool(
                            type_enabled[source_type], True
                        )
            pending = data.get("pending_type_enabled", data.get("pendingTypeEnabled", {}))
            self.pending_type_enabled = dict(self.type_enabled)
            if isinstance(pending, dict):
                for source_type in self.TYPE_ORDER:
                    if source_type in pending:
                        self.pending_type_enabled[source_type] = self._as_bool(
                            pending[source_type], self.type_enabled[source_type]
                        )
            self.config_dirty = any(
                self.pending_type_enabled[source_type] != self.type_enabled[source_type]
                for source_type in self.TYPE_ORDER
            )
            ignored = data.get("ignored_sources", data.get("ignoredSources", []))
            if isinstance(ignored, list):
                self.ignored_sources = {
                    str(item).strip() for item in ignored if str(item).strip()
                }
            self.strict_recognition = self._as_bool(
                data.get("strict_recognition", data.get("strictRecognition", self.strict_recognition)),
                self.strict_recognition,
            )
            try:
                port = int(data.get("last_app_port", data.get("lastAppPort", 0)) or 0)
                self.last_app_port = port if self.APP_PORT_START <= port <= 65535 else 0
            except Exception:
                self.last_app_port = 0
        except Exception as exc:
            self._warn("扫描开关设置读取失败，已按开启处理: {}".format(exc))

    def _as_bool(self, value, fallback=False):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if value is None:
            return fallback
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    def _save_settings(self):
        path = os.path.abspath(os.path.expanduser(self.settings_path))
        data = {
            "scan_enabled": bool(self.scan_enabled),
            "type_enabled": {
                source_type: bool(self.type_enabled.get(source_type, True))
                for source_type in self.TYPE_ORDER
            },
            "pending_type_enabled": {
                source_type: bool(
                    self.pending_type_enabled.get(
                        source_type, self.type_enabled.get(source_type, True)
                    )
                )
                for source_type in self.TYPE_ORDER
            },
            "strict_recognition": bool(self.strict_recognition),
            "ignored_sources": sorted(self.ignored_sources),
            "last_app_port": int(self.last_app_port or 0),
        }
        self._atomic_write_plain_json(path, data)

    def _apply_pending_type_settings(self):
        self.type_enabled = {
            source_type: bool(
                self.pending_type_enabled.get(
                    source_type, self.type_enabled.get(source_type, True)
                )
            )
            for source_type in self.TYPE_ORDER
        }
        self.pending_type_enabled = dict(self.type_enabled)
        self.config_dirty = False
        self._save_settings()

    def _load_scan_cache(self):
        path = os.path.abspath(os.path.expanduser(self.cache_path))
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if not isinstance(data, dict) or data.get("version") != self.CACHE_VERSION:
                return {}
            files = data.get("files", {})
            return files if isinstance(files, dict) else {}
        except Exception as exc:
            self._warn("增量扫描缓存读取失败，将全量扫描: {}".format(exc))
            return {}

    def _save_scan_cache(self, files):
        path = os.path.abspath(os.path.expanduser(self.cache_path))
        self._atomic_write_plain_json(
            path, {"version": self.CACHE_VERSION, "files": files}
        )

    def _atomic_write_plain_json(self, path, data):
        directory = os.path.dirname(path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        temp_path = path + ".tmp"
        content = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        try:
            with open(temp_path, "w", encoding="utf-8") as fp:
                fp.write(content)
                fp.flush()
                os.fsync(fp.fileno())
            os.replace(temp_path, path)
        except Exception:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass
            raise

    def _reload_app_vod_config(self, expected_keys=None):
        if not self.auto_reload_app:
            return False, "注册表已写入；App 自动重载已关闭"
        last_error = "未发现 WebHTV 本机服务"
        ports = []
        if self.last_app_port:
            ports.append(self.last_app_port)
        ports.extend(port for port in self.app_server_ports if port not in ports)
        expected_keys = set(expected_keys) if expected_keys is not None else None
        for port in ports:
            base = "http://127.0.0.1:{}".format(port)
            try:
                payload = self._request_json(
                    base + "/manage/configs", self.APP_REQUEST_TIMEOUT
                )
                items = payload.get("items", []) if isinstance(payload, dict) else []
                current = next(
                    (
                        item
                        for item in items
                        if isinstance(item, dict)
                        and int(item.get("type", -1)) == 0
                        and bool(item.get("active", False))
                    ),
                    None,
                )
                if not current or not str(current.get("url", "")).strip():
                    last_error = "WebHTV 未返回当前点播接口"
                    continue
                if expected_keys is not None:
                    try:
                        if self._app_sites_match(base, expected_keys):
                            self._remember_app_port(port)
                            return True, "WebHTV 站点列表已是最新，无需重载"
                    except Exception:
                        pass
                query = urllib.parse.urlencode(
                    {"type": 0, "url": str(current["url"]).strip()}
                )
                self._request_json(
                    base + "/manage/config/use?" + query,
                    max(1.5, self.APP_REQUEST_TIMEOUT * 4),
                )
                if expected_keys is not None:
                    verified = False
                    for _ in range(5):
                        try:
                            if self._app_sites_match(base, expected_keys):
                                verified = True
                                break
                        except Exception:
                            pass
                        time.sleep(0.12)
                    if not verified:
                        self._remember_app_port(port)
                        return True, "WebHTV 已接收重载请求，注册表已写入"
                self._remember_app_port(port)
                return True, "已重载并校验 WebHTV 站点列表"
            except Exception as exc:
                last_error = str(exc)
        if last_error:
            self._warn("WebHTV 本机管理接口未确认: {}".format(last_error))
        return False, "未连接 WebHTV 本机管理接口，注册表已写入，可直接使用"

    def _app_sites_match(self, base, expected_keys):
        payload = self._request_json(
            base + "/manage/proxy/suggest/sites", max(0.5, self.APP_REQUEST_TIMEOUT)
        )
        sites = payload.get("sites", []) if isinstance(payload, dict) else []
        loaded = {
            str(item.get("key", "")).strip()
            for item in sites
            if isinstance(item, dict)
            and str(item.get("key", "")).strip().startswith(self.GENERATED_KEY_PREFIX)
        }
        return loaded == set(expected_keys)

    def _remember_app_port(self, port):
        if self.last_app_port == int(port):
            return
        self.last_app_port = int(port)
        try:
            self._save_settings()
        except Exception as exc:
            self._warn("App 端口缓存保存失败: {}".format(exc))

    def _generated_registry_keys(self, registry=None):
        registry = registry if isinstance(registry, dict) else self._load_registry()
        return {
            self._registry_item_key(item)
            for item in registry.get("items", [])
            if self._is_generated_registry_item(item)
        }

    def _request_json(self, url, timeout):
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "Connection": "close"},
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=timeout) as response:
            status = getattr(response, "status", response.getcode())
            raw = response.read()
        if int(status) < 200 or int(status) >= 300:
            raise ValueError("HTTP {}".format(status))
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("WebHTV 本机接口返回格式无效")
        return data

    def _normalize_extension(self, value):
        value = str(value or "").strip().lower()
        if not value:
            return ""
        return value if value.startswith(".") else "." + value

    # --------------------------------------------------------------------------
    # 扫描与配置生成
    # --------------------------------------------------------------------------
    def _ensure_initialized(self):
        if self.inited:
            return
        self.init("")

    def _refresh_locked(self, allow_empty=False):
        self.status = self._empty_status()
        self.status["scan_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            self._scan_all_roots()
            if self.status["limit_reached"]:
                self.status["write_state"] = "扫描达到保护上限，已保护旧注册表"
                self.status["error"] = "请缩小扫描目录或调整 max_files"
                return False
            if not self.cache["sources"] and not (self.allow_empty_write or allow_empty):
                self.status["write_state"] = "未找到有效源，已保护旧配置"
                self.status["error"] = "扫描结果为空，未改写站点注入注册表"
                return False
            self._generate_config()
            return self.status["written"] or self.status["write_state"] == "配置内容未变化"
        except Exception as exc:
            self.status["error"] = str(exc)
            self.status["write_state"] = "合并失败"
            return False

    def _set_scan_disabled_status(self, state="自动扫描已关闭"):
        self.cache = self._empty_cache()
        self.status = self._empty_status()
        self.status["scan_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.status["write_state"] = state

    def _scan_all_roots(self):
        self.cache = self._empty_cache()
        sources = []
        ignored_sources = []
        seen_paths = set()
        self_path = os.path.realpath(__file__)
        old_file_cache = self._load_scan_cache()
        new_file_cache = {}
        available_types = set()
        limit_reached = False

        for root_order, spec in enumerate(self.scan_roots):
            if limit_reached:
                break
            source_type = str(spec.get("type", "")).upper()
            if source_type not in self.TYPE_ORDER:
                self._warn("忽略未知类型目录: {}".format(spec))
                continue
            if not self.type_enabled.get(source_type, True):
                continue
            root = os.path.abspath(os.path.expanduser(str(spec.get("path", ""))))
            extensions = {
                self._normalize_extension(ext)
                for ext in spec.get("extensions", self.TYPE_EXTENSIONS[source_type])
            }
            extensions.discard("")
            if not os.path.isdir(root):
                self._warn("目录不存在: {}".format(root))
                continue
            available_types.add(source_type)

            for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
                relative_dir = os.path.relpath(current, root)
                depth = 0 if relative_dir == "." else relative_dir.count(os.sep) + 1
                dirs[:] = sorted(
                    [
                        name
                        for name in dirs
                        if not name.startswith(".")
                        and name.lower() not in self.SKIP_DIRS
                        and not os.path.islink(os.path.join(current, name))
                    ],
                    key=lambda value: value.lower(),
                )
                if depth >= self.max_scan_depth:
                    dirs[:] = []
                for file_name in sorted(files, key=lambda value: value.lower()):
                    full_path = os.path.join(current, file_name)
                    lower_name = file_name.lower()
                    extension = os.path.splitext(lower_name)[1]
                    if extension not in extensions:
                        continue
                    if self.status["found"] >= self.max_scan_files:
                        limit_reached = True
                        self.status["limit_reached"] = True
                        self._warn(
                            "已达扫描文件上限 {}，后续文件未扫描".format(
                                self.max_scan_files
                            )
                        )
                        break
                    self.status["found"] += 1
                    if os.path.islink(full_path) or not os.path.isfile(full_path):
                        self.status["skipped"] += 1
                        continue
                    real_path = os.path.realpath(full_path)
                    if real_path == self_path:
                        continue
                    if real_path in seen_paths:
                        self.status["duplicates"] += 1
                        continue
                    try:
                        readable = os.access(real_path, os.R_OK)
                        stat = os.stat(real_path)
                        file_size = stat.st_size
                        modified_ns = getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1000000000))
                    except Exception as exc:
                        self.status["skipped"] += 1
                        self._warn("读取文件状态失败: {} ({})".format(real_path, exc))
                        continue
                    if not readable or file_size <= 0:
                        self.status["skipped"] += 1
                        self._warn("跳过不可读或空文件: {}".format(real_path))
                        continue
                    if file_size > self.max_source_size:
                        self.status["skipped"] += 1
                        self._warn(
                            "跳过超过大小上限的文件: {} ({} bytes)".format(
                                real_path, file_size
                            )
                        )
                        continue

                    relative_in_root = os.path.relpath(real_path, root).replace(os.sep, "/")
                    if self._is_excluded(source_type, lower_name, relative_in_root):
                        self.status["skipped"] += 1
                        continue
                    identity = self._source_identity(source_type, real_path)
                    cached = old_file_cache.get(identity)
                    cache_hit = (
                        isinstance(cached, dict)
                        and cached.get("size") == file_size
                        and cached.get("mtime_ns") == modified_ns
                        and cached.get("strict") == bool(self.strict_recognition)
                    )
                    if cache_hit:
                        role = str(cached.get("role", "source"))
                        valid = bool(cached.get("valid", True))
                        validation = str(cached.get("validation", ""))
                        self.status["cache_hits"] += 1
                    else:
                        role = self._detect_file_role(source_type, lower_name, real_path)
                        forced = role == "forced_source"
                        valid, validation = (
                            (True, "已通过 @tvbox-source 强制收录")
                            if forced
                            else self._validate_source(source_type, real_path)
                        )
                        self.status["cache_misses"] += 1
                    new_file_cache[identity] = {
                        "size": file_size,
                        "mtime_ns": modified_ns,
                        "strict": bool(self.strict_recognition),
                        "role": role,
                        "valid": bool(valid),
                        "validation": validation,
                    }
                    if role not in ("source", "forced_source"):
                        self.status["skipped"] += 1
                        self._warn("已按 {} 标识排除: {}".format(role, real_path))
                        continue
                    if not valid and self.strict_recognition:
                        self.status["skipped"] += 1
                        self._warn(validation)
                        continue
                    if validation and not valid:
                        self._warn(validation)

                    seen_paths.add(real_path)
                    base_name = file_name[: -len(extension)] if extension else file_name
                    source_id = "src_" + self._digest(identity, 20)
                    key = self.GENERATED_KEY_PREFIX + source_type.lower() + "_" + self._digest(
                        identity, 14
                    )
                    source = {
                        "id": source_id,
                        "identity": identity,
                        "key": key,
                        "type": source_type,
                        "path": real_path,
                        "scan_root": root,
                        "root_order": root_order,
                        "relative_in_root": relative_in_root,
                        "base_name": base_name,
                        "validation": validation,
                        "ignored": identity in self.ignored_sources,
                    }
                    if source["ignored"]:
                        ignored_sources.append(source)
                    else:
                        sources.append(source)
                if limit_reached:
                    break

        all_sources = sources + ignored_sources
        self._apply_display_names(all_sources)
        all_sources.sort(
            key=lambda item: (
                item["root_order"],
                self.TYPE_ORDER[item["type"]],
                item["relative_in_root"].lower(),
            )
        )

        for source in all_sources:
            source["site"] = self._build_site(source)
            self.cache["source_index"][source["id"]] = source
            source_type = source["type"]
            counts_key = "ignored_counts" if source["ignored"] else "type_counts"
            counts = self.cache[counts_key]
            counts[source_type] = counts.get(source_type, 0) + 1

        self.cache["sources"] = [item for item in all_sources if not item["ignored"]]
        self.cache["ignored"] = [item for item in all_sources if item["ignored"]]
        self.status["included"] = len(sources)
        self.status["ignored"] = len(ignored_sources)
        stale_ignored = {
            identity
            for identity in self.ignored_sources
            if not limit_reached
            and identity.split("|", 1)[0] in available_types
            and identity not in new_file_cache
        }
        if stale_ignored:
            self.ignored_sources.difference_update(stale_ignored)
            self.status["stale_ignored_removed"] = len(stale_ignored)
            try:
                self._save_settings()
            except Exception as exc:
                self._warn("过期忽略项清理保存失败: {}".format(exc))
        try:
            self._save_scan_cache(new_file_cache)
        except Exception as exc:
            self._warn("增量扫描缓存保存失败: {}".format(exc))
        self._check_dependencies()

    def _source_identity(self, source_type, path):
        return source_type + "|" + self._file_url(path)

    def _is_excluded(self, source_type, lower_name, relative_in_root):
        relative_lower = relative_in_root.lower()
        if lower_name.startswith("."):
            return True
        if source_type == "JS" and lower_name in self.JS_EXCLUDE:
            return True
        if source_type == "PY":
            if lower_name == "__init__.py":
                return True
            if relative_lower in self.PY_EXCLUDE_RELATIVE:
                return True
        return False

    def _detect_file_role(self, source_type, lower_name, path):
        try:
            text = self._read_text(path, 64 * 1024)
        except Exception:
            text = ""
        lower_text = text.lower()

        if "@tvbox-ignore" in lower_text:
            return "ignore"
        role_match = re.search(r"@tvbox-role\s*(?:[:=]\s*)?([a-z_-]+)", lower_text)
        if role_match:
            role = role_match.group(1)
            if role in ("manager", "extension", "library", "ignore"):
                return role
            if role == "source":
                return "forced_source"
        if "@tvbox-source" in lower_text:
            return "forced_source"

        if source_type == "PY" and lower_name in self.MANAGER_FILES:
            return "manager"
        if source_type == "JS":
            if lower_name.endswith(self.JS_EXTENSION_SUFFIXES):
                return "extension"
            extension_signatures = (
                "window.fm",
                "fm.vodinline",
                "window.fongmibridge",
                "webhomeextensions",
                "gm_addstyle",
                "document-start",
                "fmsdk",
                "@match",
            )
            looks_like_extension = any(signature in lower_text for signature in extension_signatures)
            looks_like_rule = bool(re.search(r"\b(?:var|let|const)\s+rule\s*=", lower_text))
            looks_like_rule = looks_like_rule or "module.exports" in lower_text or "export default" in lower_text
            if looks_like_extension and not looks_like_rule:
                return "extension"
        return "source"

    def _validate_source(self, source_type, path):
        try:
            if source_type == "XBPQ":
                with open(path, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                if not isinstance(data, dict) or not data:
                    return False, "XBPQ 缺少有效的 JSON 对象: {}".format(path)
                keys = "|".join(str(key).lower() for key in data.keys())
                signatures = (
                    "url",
                    "主页",
                    "分类",
                    "搜索",
                    "二级",
                    "播放",
                    "列表",
                    "数组",
                    "标题",
                )
                if not any(signature in keys for signature in signatures):
                    return False, "XBPQ 未发现常用规则字段: {}".format(path)
            elif source_type == "PY":
                text = self._read_text(path, 256 * 1024)
                if not re.search(r"\bclass\s+Spider\s*(?:\(|:)", text):
                    return False, "PY 文件未发现 Spider 类，已按依赖库跳过: {}".format(path)
            elif source_type == "JS":
                text = self._read_text(path, 256 * 1024)
                lower = text.lower()
                looks_like_rule = bool(
                    re.search(r"(?:^|[\s;])(?:var\s+|let\s+|const\s+)?rule\s*=", lower)
                )
                looks_like_rule = looks_like_rule or "module.exports" in lower or "export default" in lower
                if not looks_like_rule:
                    return False, "JS 文件未发现 rule/module.exports，已按依赖或扩展跳过: {}".format(path)
            elif source_type == "HTML":
                text = self._read_text(path, 128 * 1024).lower()
                if not any(tag in text for tag in ("<!doctype html", "<html", "<body")):
                    return False, "HTML 文件未发现页面结构: {}".format(path)
        except Exception as exc:
            return False, "{} 文件检查失败: {} ({})".format(source_type, path, exc)
        return True, ""

    def _read_text(self, path, limit):
        with open(path, "rb") as fp:
            data = fp.read(limit)
        return data.decode("utf-8", errors="ignore")

    def _apply_display_names(self, sources):
        counts = {}
        for source in sources:
            identity = (source["type"], source["base_name"].lower())
            counts[identity] = counts.get(identity, 0) + 1

        for source in sources:
            source_type = source["type"]
            base_name = source["base_name"]
            identity = (source_type, base_name.lower())
            suffix = ""
            if counts.get(identity, 0) > 1:
                folder = os.path.dirname(source["relative_in_root"]).replace(os.sep, "/")
                suffix = " · " + (folder or os.path.basename(source["scan_root"]))
            source["name"] = (
                self.TYPE_PREFIX[source_type]
                + base_name
                + suffix
                + "┃"
                + self.TYPE_GROUP[source_type]
            )

    def _build_site(self, source):
        source_type = source["type"]
        file_ref = self._file_url(source["path"])
        site = {
            "key": source["key"],
            "name": source["name"],
            "type": 3,
            "searchable": self.DEFAULT_SEARCHABLE,
            "quickSearch": self.DEFAULT_QUICK_SEARCH,
        }
        if source_type == "PY":
            site.update({"api": file_ref})
        elif source_type == "JS":
            site.update(
                {
                    "api": self._runtime_reference(self.js_api),
                    "ext": file_ref,
                }
            )
        elif source_type == "XBPQ":
            site.update(
                {
                    "api": self._runtime_reference(self.xbpq_api),
                    "ext": file_ref,
                }
            )
        elif source_type == "HTML":
            site.update(
                {
                    "api": self._runtime_reference(self.html_api),
                    "homePage": file_ref,
                }
            )
        return site

    def _file_url(self, path):
        absolute = os.path.realpath(os.path.abspath(os.path.expanduser(str(path))))
        storage_root = os.path.realpath(os.path.abspath(self.STORAGE_ROOT))
        try:
            relative = os.path.relpath(absolute, storage_root).replace(os.sep, "/")
        except Exception:
            relative = ""
        if relative and relative != ".." and not relative.startswith("../"):
            return "file://" + relative.lstrip("/")
        return "file://" + absolute

    def _runtime_reference(self, reference):
        value = str(reference or "").strip()
        if not value:
            return ""
        lower = value.lower()
        if lower.startswith(("http://", "https://", "file://", "assets://")):
            return value
        if value.startswith("csp_"):
            return value
        if os.path.isabs(value):
            return self._file_url(value)
        return self._file_url(os.path.join(self.LOCAL_BASE_DIR, value.lstrip("./")))

    def _check_dependencies(self):
        if self.cache["type_counts"].get("JS", 0):
            js_path = self._local_reference_path(self.js_api)
            if js_path and not os.path.isfile(js_path):
                self._warn("JS 引擎不存在，生成的 JS 源可能无法使用: {}".format(js_path))

    def _local_reference_path(self, reference):
        if not isinstance(reference, str) or not reference.strip():
            return ""
        value = reference.strip()
        if value.startswith("http://") or value.startswith("https://"):
            return ""
        if value.startswith("file://"):
            path = value.replace("file://", "", 1)
            return path if os.path.isabs(path) else os.path.join(self.STORAGE_ROOT, path)
        if os.path.isabs(value):
            return value
        return os.path.abspath(os.path.join(self.LOCAL_BASE_DIR, value.lstrip("./")))

    def _generate_config(self):
        base_duplicates = self.status["duplicates"]
        last_error = None
        for _ in range(3):
            registry, token = self._load_registry_snapshot()
            registry, manual_count, generated_count, duplicate_count, diff = self._merge_registry(
                registry
            )
            try:
                self._atomic_write_json(registry, expected_token=token)
                self.status["manual_sites"] = manual_count
                self.status["generated_sites"] = generated_count
                self.status["duplicates"] = base_duplicates + duplicate_count
                self.status["added_sites"] = diff["added"]
                self.status["updated_sites"] = diff["updated"]
                self.status["removed_sites"] = diff["removed"]
                self.status["unchanged_sites"] = diff["unchanged"]
                return
            except RegistryChangedError as exc:
                last_error = exc
        raise RegistryChangedError(
            "注册表在扫描期间持续被修改，已停止写入: {}".format(last_error)
        )

    def _merge_registry(self, registry):
        items = registry.get("items", [])
        if not isinstance(items, list):
            raise ValueError("站点注入注册表的 items 必须是数组")

        old_generated_items = [
            item for item in items if self._is_generated_registry_item(item)
        ]
        manual_items = []
        for item in items:
            if not isinstance(item, dict):
                manual_items.append(item)
                continue
            if self._is_generated_registry_item(item):
                continue
            manual_items.append(item)

        manual_fingerprints = {
            self._site_fingerprint(self._registry_item_site(item))
            for item in manual_items
            if isinstance(item, dict)
        }
        generated_items = []
        duplicate_count = 0
        for source in self.cache["sources"]:
            site = source["site"]
            if self._site_fingerprint(site) in manual_fingerprints:
                duplicate_count += 1
                continue
            generated_items.append(
                {
                    "id": source["key"],
                    "enabled": True,
                    "kind": "csp",
                    "site": site,
                }
            )

        if self.generated_insert_index is None:
            merged_items = manual_items + generated_items
        else:
            index = max(0, min(int(self.generated_insert_index), len(manual_items)))
            merged_items = manual_items[:index] + generated_items + manual_items[index:]

        registry["enabled"] = True
        registry.setdefault("insertIndex", 0)
        registry.setdefault("homeKey", "")
        registry["items"] = merged_items
        generated_keys = {
            self._registry_item_key(item) for item in generated_items
        }
        home_key = str(registry.get("homeKey", "")).strip()
        if home_key.startswith(self.GENERATED_KEY_PREFIX) and home_key not in generated_keys:
            registry["homeKey"] = ""
        old_map = {
            self._registry_item_key(item): self._site_content_fingerprint(
                self._registry_item_site(item)
            )
            for item in old_generated_items
        }
        new_map = {
            self._registry_item_key(item): self._site_content_fingerprint(
                self._registry_item_site(item)
            )
            for item in generated_items
        }
        shared = set(old_map) & set(new_map)
        diff = {
            "added": len(set(new_map) - set(old_map)),
            "removed": len(set(old_map) - set(new_map)),
            "updated": sum(1 for key in shared if old_map[key] != new_map[key]),
            "unchanged": sum(1 for key in shared if old_map[key] == new_map[key]),
        }
        return registry, len(manual_items), len(generated_items), duplicate_count, diff

    def _load_registry(self):
        return self._load_registry_snapshot()[0]

    def _load_registry_snapshot(self):
        registry_path = os.path.abspath(os.path.expanduser(self.registry_path))
        output_path = os.path.abspath(os.path.expanduser(self.output_path))
        path = registry_path if os.path.isfile(registry_path) else output_path
        if os.path.isfile(path):
            try:
                with open(path, "rb") as fp:
                    raw = fp.read()
                registry = json.loads(raw.decode("utf-8"))
            except Exception as exc:
                raise ValueError("站点注入注册表无法读取，已停止写入: {} ({})".format(path, exc))
            if not isinstance(registry, dict):
                raise ValueError("站点注入注册表顶层必须是 JSON 对象: {}".format(path))
            if "items" not in registry:
                registry = self._legacy_registry(registry)
            token = (
                hashlib.sha256(raw).hexdigest()
                if os.path.abspath(path) == output_path
                else self._registry_token(output_path)
            )
            return registry, token
        return {
            "enabled": True,
            "insertIndex": 0,
            "homeKey": "",
            "items": [],
        }, "__missing__"

    def _registry_token(self, path=None):
        path = os.path.abspath(os.path.expanduser(path or self.output_path))
        if not os.path.isfile(path):
            return "__missing__"
        with open(path, "rb") as fp:
            return hashlib.sha256(fp.read()).hexdigest()

    def _legacy_registry(self, data):
        items = []
        sites = data.get("sites", [])
        if isinstance(sites, list):
            for index, site in enumerate(sites):
                if not isinstance(site, dict):
                    continue
                key = str(site.get("key", "")).strip()
                items.append(
                    {
                        "id": key or "legacy_site_{}".format(index),
                        "enabled": True,
                        "kind": "webHome" if site.get("homePage") else "csp",
                        "site": site,
                    }
                )
        return {
            "enabled": bool(data.get("enabled", True)),
            "insertIndex": int(data.get("insertIndex", 0) or 0),
            "homeKey": str(data.get("homeKey", data.get("home", "")) or ""),
            "items": items,
        }

    def _registry_item_site(self, item):
        site = item.get("site")
        return site if isinstance(site, dict) else item

    def _registry_item_key(self, item):
        key = str(item.get("key", "")).strip()
        if key:
            return key
        site = item.get("site")
        return str(site.get("key", "")).strip() if isinstance(site, dict) else ""

    def _is_generated_registry_item(self, item):
        if not isinstance(item, dict):
            return False
        key = self._registry_item_key(item)
        item_id = str(item.get("id", "")).strip()
        return key.startswith(self.GENERATED_KEY_PREFIX) or item_id.startswith(
            self.GENERATED_KEY_PREFIX
        )

    def _clear_generated_registry(self):
        last_error = None
        for _ in range(3):
            registry, token = self._load_registry_snapshot()
            registry, removed = self._remove_generated_items(registry)
            try:
                self._atomic_write_json(registry, expected_token=token)
                return removed
            except RegistryChangedError as exc:
                last_error = exc
        raise RegistryChangedError(
            "注册表在清除期间持续被修改: {}".format(last_error)
        )

    def _remove_generated_items(self, registry):
        items = registry.get("items", [])
        if not isinstance(items, list):
            raise ValueError("站点注入注册表的 items 必须是数组")
        generated_keys = {
            self._registry_item_key(item)
            for item in items
            if self._is_generated_registry_item(item)
        }
        kept = [item for item in items if not self._is_generated_registry_item(item)]
        removed = len(items) - len(kept)
        registry["items"] = kept
        if str(registry.get("homeKey", "")).strip() in generated_keys:
            registry["homeKey"] = ""
        return registry, removed

    def _restore_registry_backup(self):
        files = self._list_backup_files()
        if not files:
            raise ValueError("暂无可恢复的注册表备份")
        return self._restore_registry_file(files[0])

    def _restore_registry_file(self, backup_path):
        if not os.path.isfile(backup_path):
            raise ValueError("暂无可恢复的注册表备份")
        registry = self._read_config_file(backup_path, "注册表备份")
        if not isinstance(registry.get("items", []), list):
            raise ValueError("注册表备份的 items 必须是数组")
        current_path = os.path.abspath(os.path.expanduser(self.output_path))
        if os.path.isfile(current_path):
            self._create_registry_backup(current_path)
        self._atomic_write_json(registry, create_backup=False)
        return len(registry.get("items", []))

    def _create_registry_backup(self, source_path):
        os.makedirs(self.backup_dir, exist_ok=True)
        backup_path = self._latest_backup_path()
        temp_path = backup_path + ".tmp"
        try:
            shutil.copy2(source_path, temp_path)
            os.replace(temp_path, backup_path)
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
        self._remove_legacy_backup_files(keep=backup_path)

    def _latest_backup_path(self):
        return os.path.join(
            os.path.abspath(os.path.expanduser(self.backup_dir)),
            "registry-latest.json",
        )

    def _backup_candidates(self):
        candidates = []
        backup_dir = os.path.abspath(os.path.expanduser(self.backup_dir))
        if os.path.isdir(backup_dir):
            candidates.extend(
                os.path.join(backup_dir, name)
                for name in os.listdir(backup_dir)
                if name.startswith("registry-")
                and name.endswith(".json")
                and os.path.isfile(os.path.join(backup_dir, name))
            )
        output_path = os.path.abspath(os.path.expanduser(self.output_path))
        for suffix in (".bak", ".before-restore.bak"):
            path = output_path + suffix
            if os.path.isfile(path):
                candidates.append(path)
        return candidates

    def _normalize_backup_storage(self):
        candidates = self._backup_candidates()
        if not candidates:
            return
        latest_path = self._latest_backup_path()
        newest = max(
            candidates,
            key=lambda path: (os.path.getmtime(path), os.path.basename(path)),
        )
        if os.path.abspath(newest) != os.path.abspath(latest_path):
            os.makedirs(os.path.dirname(latest_path), exist_ok=True)
            temp_path = latest_path + ".tmp"
            try:
                shutil.copy2(newest, temp_path)
                os.replace(temp_path, latest_path)
            finally:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
        self._remove_legacy_backup_files(keep=latest_path)

    def _remove_legacy_backup_files(self, keep=None):
        keep = os.path.abspath(keep) if keep else ""
        for path in self._backup_candidates():
            if os.path.abspath(path) == keep:
                continue
            try:
                os.remove(path)
            except Exception:
                pass

    def _delete_backup_files(self):
        removed = 0
        for path in self._backup_candidates():
            try:
                os.remove(path)
                removed += 1
            except FileNotFoundError:
                pass
        return removed

    def _list_backup_files(self):
        path = self._latest_backup_path()
        return [path] if os.path.isfile(path) else []

    def _read_config_file(self, path, label):
        try:
            with open(path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        except Exception as exc:
            raise ValueError("{}无法读取，已停止写入: {} ({})".format(label, path, exc))
        if not isinstance(data, dict):
            raise ValueError("{}顶层必须是 JSON 对象: {}".format(label, path))
        return data

    def _site_fingerprint(self, site):
        if not isinstance(site, dict):
            return ""
        data = {
            "type": site.get("type", 3),
            "api": site.get("api", ""),
            "ext": site.get("ext", ""),
            "homePage": site.get("homePage", site.get("home_page", "")),
        }
        return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _site_content_fingerprint(self, site):
        if not isinstance(site, dict):
            return ""
        return json.dumps(
            site, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    def _atomic_write_json(self, config, create_backup=True, expected_token=None):
        output_path = os.path.abspath(os.path.expanduser(self.output_path))
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.isdir(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        content = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
        if os.path.isfile(output_path):
            try:
                with open(output_path, "r", encoding="utf-8") as fp:
                    if fp.read() == content:
                        self.status["write_state"] = "配置内容未变化"
                        self.status["written"] = True
                        self.status["registry_changed"] = False
                        return
            except Exception:
                pass

        temp_path = output_path + ".tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as fp:
                fp.write(content)
                fp.flush()
                os.fsync(fp.fileno())
            with open(temp_path, "r", encoding="utf-8") as fp:
                check = json.load(fp)
            if not isinstance(check, dict) or not isinstance(check.get("items", []), list):
                raise ValueError("临时注册表校验失败")
            if expected_token is not None and self._registry_token(output_path) != expected_token:
                raise RegistryChangedError("注册表已被其他操作修改")
            if os.path.isfile(output_path) and self.backup_before_write and create_backup:
                self._create_registry_backup(output_path)
            os.replace(temp_path, output_path)
            self.status["write_state"] = "已写入 WebHTV 站点注入注册表"
            self.status["written"] = True
            self.status["registry_changed"] = True
        except Exception:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass
            raise

    def _digest(self, value, length):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]

    def _warn(self, text):
        if text and text not in self.status["warnings"]:
            self.status["warnings"].append(text)

    # --------------------------------------------------------------------------
    # TVBox 标准接口
    # --------------------------------------------------------------------------
    def homeContent(self, filter):
        self._ensure_initialized()
        classes = [{"type_id": "all", "type_name": "全部 ({})".format(len(self.cache["sources"]))}]
        for source_type in ("PY", "JS", "XBPQ", "HTML"):
            count = self.cache["type_counts"].get(source_type, 0)
            if count:
                classes.append({"type_id": "type:" + source_type, "type_name": "{} ({})".format(source_type, count)})
        if self.cache["ignored"]:
            classes.append({"type_id": "ignored", "type_name": "忽略 ({})".format(len(self.cache["ignored"]))})
        classes.append(
            {
                "type_id": self.SCAN_SETTINGS_TID,
                "type_name": "扫描配置" + (" *" if self.config_dirty else ""),
            }
        )
        backup_count = len(self._list_backup_files())
        if backup_count:
            classes.append(
                {
                    "type_id": self.BACKUPS_TID,
                    "type_name": "历史备份 ({})".format(backup_count),
                }
            )
        return {"class": classes, "list": self._home_items()}

    def homeVideoContent(self):
        self._ensure_initialized()
        return {"list": self._home_items()}

    def _home_items(self):
        ready = self.status["written"]
        if not self.scan_enabled:
            status_name = "⏸ 自动扫描已关闭"
        else:
            status_name = "✅ 站点已合并" if ready else "⚠️ 站点未合并"
        items = [
            {
                "vod_id": self.STATUS_ID,
                "vod_name": status_name,
                "vod_pic": "",
                "vod_remarks": "{} 个源 · {}".format(len(self.cache["sources"]), self.status["write_state"]),
            },
            {
                "vod_id": self.TOGGLE_SCAN_ID,
                "vod_name": "🟢 自动扫描开关：已开启" if self.scan_enabled else "⚪ 自动扫描开关：已关闭",
                "vod_pic": "",
                "vod_remarks": "点击切换开关",
                "action": self.ACTION_TOGGLE_SCAN,
            },
        ]
        items.extend(
            [
            {
                "vod_id": self.RESCAN_ID,
                "vod_name": "⚡ 一键扫描并加载",
                "vod_pic": "",
                "vod_remarks": "扫描、写入注册表并重载当前点播配置",
                "action": self.ACTION_RESCAN,
            },
            {
                "vod_id": self.CLEAR_SITES_ID,
                "vod_name": "🗑 一键清除自动站点",
                "vod_pic": "",
                "vod_remarks": "保留手工注入项，并关闭自动扫描",
                "action": self.ACTION_CLEAR_SITES,
            },
            {
                "vod_id": self.RESTORE_BACKUP_ID,
                "vod_name": "↩ 撤销上次变更",
                "vod_pic": "",
                "vod_remarks": "有备份" if self._list_backup_files() else "暂无备份",
                "action": self.ACTION_RESTORE_BACKUP,
            },
            {
                "vod_id": self.DELETE_BACKUPS_ID,
                "vod_name": "🗑 删除历史备份",
                "vod_pic": "",
                "vod_remarks": "删除唯一备份" if self._list_backup_files() else "暂无备份",
                "action": self.ACTION_DELETE_BACKUPS,
            },
            ]
        )
        return items

    def categoryContent(self, tid, pg, filter, ext):
        self._ensure_initialized()
        page = self._page_number(pg)
        if tid == "all":
            items = list(self.cache["sources"])
        elif str(tid).startswith("type:"):
            source_type = str(tid).split(":", 1)[1].upper()
            items = [item for item in self.cache["sources"] if item["type"] == source_type]
        elif tid == "ignored":
            items = list(self.cache["ignored"])
        elif tid == self.SCAN_SETTINGS_TID:
            return self._paged_result(self._scan_setting_items(), page)
        elif tid == self.BACKUPS_TID:
            return self._paged_result(self._backup_items(), page)
        else:
            items = []
        return self._paged_result(items, page)

    def _scan_setting_items(self):
        items = [
            {
                "id": "setting_apply",
                "name": "应用并加载",
                "type": "APPLY",
                "relative_in_root": "有待应用变更" if self.config_dirty else "配置已应用",
                "settings": True,
                "apply": True,
                "enabled": self.config_dirty,
            }
        ]
        for source_type in ("PY", "JS", "XBPQ", "HTML"):
            enabled = self.pending_type_enabled.get(
                source_type, self.type_enabled.get(source_type, True)
            )
            items.append(
                {
                    "id": "setting_type_{}".format(source_type.lower()),
                    "name": "{} 扫描".format(source_type),
                    "type": source_type,
                    "relative_in_root": "已开启" if enabled else "已关闭",
                    "settings": True,
                    "enabled": enabled,
                }
            )
        return items

    def _backup_items(self):
        items = []
        for path in self._list_backup_files():
            try:
                registry = self._read_config_file(path, "历史备份")
                count = len(registry.get("items", []))
                modified = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(path))
                )
                items.append(
                    {
                        "id": "backup_" + self._digest(os.path.basename(path), 12),
                        "name": modified,
                        "type": "BACKUP",
                        "relative_in_root": "{} 个条目".format(count),
                        "backup": True,
                        "path": path,
                    }
                )
            except Exception as exc:
                self._warn("历史备份读取失败: {} ({})".format(path, exc))
        if items:
            items.append(
                {
                    "id": self.DELETE_BACKUPS_ID,
                    "name": "删除历史备份",
                    "type": "DELETE_BACKUP",
                    "relative_in_root": "当前仅保留 1 份，点击删除",
                    "delete_backup": True,
                }
            )
        return items

    def detailContent(self, array):
        self._ensure_initialized()
        source_id = str(array[0]) if isinstance(array, (list, tuple)) and array else str(array or "")
        if source_id == self.STATUS_ID:
            return {"list": [self._status_detail()]}
        if source_id == self.RESCAN_ID:
            with self.lock:
                if self.scan_enabled:
                    self._refresh_locked()
                self.inited = True
            return {"list": [self._status_detail()]}

        source = self.cache["source_index"].get(source_id)
        if not source:
            return {"list": [{"vod_name": "源不存在", "vod_content": "请重新扫描后再试。"}]}

        site_text = json.dumps(source["site"], ensure_ascii=False, indent=2)
        validation = source.get("validation") or "静态检查未发现明显问题"
        content = (
            "类型: {type}\n"
            "文件: {path}\n"
            "相对路径: {relative}\n"
            "稳定标识: {identity}\n"
            "检查: {validation}\n\n"
            "生成的站点配置:\n{site}\n\n"
            "注入注册表: {output}\n"
            "返回 App 刷新配置或重启后，该站点会出现在站点列表。"
        ).format(
            type=source["type"],
            path=source["path"],
            relative=source["relative_in_root"],
            identity=source["identity"],
            validation=validation,
            site=site_text,
            output=self.output_path,
        )
        return {
            "list": [
                {
                    "vod_id": source_id,
                    "vod_name": source["name"],
                    "vod_pic": "",
                    "vod_remarks": source["type"],
                    "vod_content": content,
                }
            ]
        }

    def _status_detail(self):
        warning_text = "\n".join("- " + item for item in self.status["warnings"][:20]) or "无"
        error_text = self.status["error"] or "无"
        content = (
            "自动扫描: {scan_enabled}\n"
            "严格识别: {strict}\n"
            "待应用配置: {dirty}\n"
            "分类开关: {types}\n"
            "扫描时间: {scan_time}\n"
            "发现文件: {found}\n"
            "有效源: {included}\n"
            "忽略源: {ignored}\n"
            "清理过期忽略项: {stale_ignored}\n"
            "跳过文件: {skipped}\n"
            "重复项: {duplicates}\n"
            "缓存命中/重检: {cache_hits}/{cache_misses}\n"
            "保留注入项: {manual}\n"
            "自动注入项: {generated}\n"
            "变更预览: +{added} ~{updated} -{removed} ={unchanged}\n"
            "写入状态: {state}\n"
            "错误: {error}\n\n"
            "警告:\n{warnings}\n\n"
            "站点注入注册表: {output}\n\n"
            "扫描开关设置: {settings}\n\n"
            "扫描目录配置: {roots_config}\n"
            "扫描上限: 文件 {max_files} · 深度 {max_depth} · 单文件 {max_size} bytes\n\n"
            "扫描结果已写入 WebHTV 站点注入注册表，手工注入项保留。\n"
            "App 已缓存的站点列表需要刷新配置或重启后才会更新。"
        ).format(
            scan_enabled="开启" if self.scan_enabled else "关闭",
            strict="开启" if self.strict_recognition else "关闭",
            dirty="是" if self.config_dirty else "否",
            types=" ".join(
                "{}:{}{}".format(
                    source_type,
                    "开" if self.type_enabled.get(source_type, True) else "关",
                    "->{}".format(
                        "开"
                        if self.pending_type_enabled.get(
                            source_type, self.type_enabled.get(source_type, True)
                        )
                        else "关"
                    )
                    if self.pending_type_enabled.get(
                        source_type, self.type_enabled.get(source_type, True)
                    )
                    != self.type_enabled.get(source_type, True)
                    else "",
                )
                for source_type in ("PY", "JS", "XBPQ", "HTML")
            ),
            scan_time=self.status["scan_time"],
            found=self.status["found"],
            included=self.status["included"],
            ignored=self.status["ignored"],
            stale_ignored=self.status["stale_ignored_removed"],
            skipped=self.status["skipped"],
            duplicates=self.status["duplicates"],
            cache_hits=self.status["cache_hits"],
            cache_misses=self.status["cache_misses"],
            manual=self.status["manual_sites"],
            generated=self.status["generated_sites"],
            added=self.status["added_sites"],
            updated=self.status["updated_sites"],
            removed=self.status["removed_sites"],
            unchanged=self.status["unchanged_sites"],
            state=self.status["write_state"],
            error=error_text,
            warnings=warning_text,
            output=self.output_path,
            settings=self.settings_path,
            roots_config=self.roots_config_path,
            max_files=self.max_scan_files,
            max_depth=self.max_scan_depth,
            max_size=self.max_source_size,
        )
        return {
            "vod_id": self.STATUS_ID,
            "vod_name": "本地源扫描状态",
            "vod_pic": "",
            "vod_remarks": self.status["write_state"],
            "vod_content": content,
        }

    def searchContent(self, key, quick, pg="1"):
        self._ensure_initialized()
        keyword = str(key or "").strip().lower()
        page = self._page_number(pg)
        if not keyword:
            items = []
        else:
            items = [
                source
                for source in self.cache["sources"]
                if keyword in source["name"].lower()
                or keyword in source["relative_in_root"].lower()
                or keyword in source["type"].lower()
            ]
        return self._paged_result(items, page)

    def _paged_result(self, items, page):
        total = len(items)
        page_size = max(1, int(self.page_size))
        page_count = max(1, (total + page_size - 1) // page_size)
        if page > page_count:
            page_items = []
        else:
            start = (page - 1) * page_size
            page_items = items[start : start + page_size]
        return {
            "page": page,
            "pagecount": page_count,
            "limit": page_size,
            "total": total,
            "list": [self._source_vod(item) for item in page_items],
        }

    def _source_vod(self, source):
        if source.get("delete_backup"):
            return {
                "vod_id": source["id"],
                "vod_name": "🗑 " + source["name"],
                "vod_pic": "",
                "vod_remarks": source["relative_in_root"],
                "action": self.ACTION_DELETE_BACKUPS,
            }
        if source.get("backup"):
            return {
                "vod_id": source["id"],
                "vod_name": "↩ " + source["name"],
                "vod_pic": "",
                "vod_remarks": source["relative_in_root"],
                "action": self.ACTION_RESTORE_SNAPSHOT_PREFIX
                + os.path.basename(source["path"]),
            }
        if source.get("settings"):
            if source.get("apply"):
                return {
                    "vod_id": source["id"],
                    "vod_name": "⚡ " + source["name"],
                    "vod_pic": "",
                    "vod_remarks": source["relative_in_root"],
                    "action": self.ACTION_APPLY_SCAN_CONFIG,
                }
            enabled = bool(source.get("enabled"))
            return {
                "vod_id": source["id"],
                "vod_name": "🟢 {}".format(source["name"])
                if enabled
                else "⚪ {}".format(source["name"]),
                "vod_pic": "",
                "vod_remarks": "Toggle · {}".format(
                    "已开启" if enabled else "已关闭"
                ),
                "action": self.ACTION_TOGGLE_TYPE_PREFIX + source["type"],
            }
        return {
            "vod_id": source["id"],
            "vod_name": ("⛔ " if source.get("ignored") else "") + source["name"],
            "vod_pic": "",
            "vod_remarks": "{} · {} · {}".format(
                source["type"],
                source["relative_in_root"],
                "点击恢复" if source.get("ignored") else "点击忽略",
            ),
            "action": self.ACTION_TOGGLE_IGNORE_PREFIX + source["id"],
        }

    def _page_number(self, value):
        try:
            return max(1, int(value))
        except Exception:
            return 1

    def action(self, action):
        action = str(action)
        if action.startswith(self.ACTION_TOGGLE_IGNORE_PREFIX):
            source_id = action[len(self.ACTION_TOGGLE_IGNORE_PREFIX) :]
            source = self.cache["source_index"].get(source_id)
            if not source:
                return {"code": 0, "msg": "源不存在，请重新扫描"}
            with self.lock:
                identity = source["identity"]
                ignored = identity not in self.ignored_sources
                if ignored:
                    self.ignored_sources.add(identity)
                else:
                    self.ignored_sources.discard(identity)
                try:
                    self._save_settings()
                    ok = True
                    if self.scan_enabled:
                        ok = self._refresh_locked(allow_empty=True)
                    if not ok:
                        return {
                            "code": 0,
                            "msg": "忽略设置已保存，但注册表更新失败：{}".format(
                                self.status["error"] or self.status["write_state"]
                            ),
                        }
                    return {
                        "code": 0,
                        "msg": "已忽略：{}".format(source["name"])
                        if ignored
                        else "已恢复：{}".format(source["name"]),
                    }
                except Exception as exc:
                    if ignored:
                        self.ignored_sources.discard(identity)
                    else:
                        self.ignored_sources.add(identity)
                    return {"code": 0, "msg": "忽略列表保存失败：{}".format(exc)}
        if action.startswith(self.ACTION_SOURCE_PREFIX):
            source_id = action[len(self.ACTION_SOURCE_PREFIX) :]
            source = self.cache["source_index"].get(source_id)
            if not source:
                return {"code": 0, "msg": "源不存在，请重新扫描"}
            return {
                "code": 0,
                "msg": "{} · {}；已写入站点注入注册表，刷新配置或重启后可见".format(
                    source["type"], source["relative_in_root"]
                ),
            }
        if action == self.ACTION_TOGGLE_SCAN:
            with self.lock:
                previous = self.scan_enabled
                try:
                    self.scan_enabled = not self.scan_enabled
                    self._save_settings()
                    if self.scan_enabled:
                        ok = self._refresh_locked(
                            allow_empty=not any(self.type_enabled.values())
                        )
                        message = (
                            "自动扫描已开启：{} 个源，{}".format(
                                len(self.cache["sources"]), self.status["write_state"]
                            )
                            if ok
                            else "自动扫描已开启，但扫描失败：{}".format(
                                self.status["error"] or self.status["write_state"]
                            )
                        )
                    else:
                        self._set_scan_disabled_status()
                        message = "自动扫描已关闭，现有注入站点已保留"
                    self.inited = True
                    return {"code": 0, "msg": message}
                except Exception as exc:
                    self.scan_enabled = previous
                    return {"code": 0, "msg": "扫描开关保存失败：{}".format(exc)}
        if action == self.ACTION_CLEAR_SITES:
            with self.lock:
                previous = self.scan_enabled
                try:
                    self.scan_enabled = False
                    self._save_settings()
                    removed = self._clear_generated_registry()
                    self._set_scan_disabled_status(
                        "已清除 {} 个自动站点，自动扫描已关闭".format(removed)
                    )
                    _, detail = self._reload_app_vod_config(expected_keys=set())
                    self.inited = True
                    return {
                        "code": 0,
                        "msg": "已清除 {} 个自动站点，手工注入项已保留，自动扫描已关闭；{}".format(
                            removed,
                            detail,
                        ),
                    }
                except Exception as exc:
                    self.scan_enabled = previous
                    try:
                        self._save_settings()
                    except Exception:
                        pass
                    return {"code": 0, "msg": "清除失败：{}".format(exc)}
        if action == self.ACTION_DELETE_BACKUPS:
            with self.lock:
                try:
                    removed = self._delete_backup_files()
                    return {
                        "code": 0,
                        "msg": "已删除历史备份"
                        if removed
                        else "暂无历史备份",
                    }
                except Exception as exc:
                    return {"code": 0, "msg": "历史备份删除失败：{}".format(exc)}
        if action == self.ACTION_RESTORE_BACKUP:
            with self.lock:
                previous = self.scan_enabled
                try:
                    self.scan_enabled = False
                    self._save_settings()
                    count = self._restore_registry_backup()
                    self._set_scan_disabled_status(
                        "已恢复上次注册表，自动扫描已关闭"
                    )
                    _, detail = self._reload_app_vod_config(
                        expected_keys=self._generated_registry_keys()
                    )
                    return {
                        "code": 0,
                        "msg": "已恢复上次注册表（{} 个条目），自动扫描已关闭；{}".format(
                            count,
                            detail,
                        ),
                    }
                except Exception as exc:
                    self.scan_enabled = previous
                    try:
                        self._save_settings()
                    except Exception:
                        pass
                    return {"code": 0, "msg": "恢复失败：{}".format(exc)}
        if action.startswith(self.ACTION_RESTORE_SNAPSHOT_PREFIX):
            name = os.path.basename(
                action[len(self.ACTION_RESTORE_SNAPSHOT_PREFIX) :]
            )
            path = os.path.join(self.backup_dir, name)
            with self.lock:
                previous = self.scan_enabled
                try:
                    if not name.startswith("registry-") or not name.endswith(".json"):
                        raise ValueError("历史备份名称无效")
                    self.scan_enabled = False
                    self._save_settings()
                    count = self._restore_registry_file(path)
                    self._set_scan_disabled_status(
                        "已恢复历史备份，自动扫描已关闭"
                    )
                    _, detail = self._reload_app_vod_config(
                        expected_keys=self._generated_registry_keys()
                    )
                    return {
                        "code": 0,
                        "msg": "已恢复历史备份（{} 个条目）；{}".format(
                            count,
                            detail,
                        ),
                    }
                except Exception as exc:
                    self.scan_enabled = previous
                    try:
                        self._save_settings()
                    except Exception:
                        pass
                    return {"code": 0, "msg": "历史备份恢复失败：{}".format(exc)}
        if action.startswith(self.ACTION_TOGGLE_TYPE_PREFIX):
            source_type = action[len(self.ACTION_TOGGLE_TYPE_PREFIX) :].upper()
            if source_type not in self.TYPE_ORDER:
                return {"code": 0, "msg": "未知站点类型"}
            with self.lock:
                previous = self.pending_type_enabled.get(
                    source_type, self.type_enabled.get(source_type, True)
                )
                self.pending_type_enabled[source_type] = not previous
                self.config_dirty = any(
                    self.pending_type_enabled[item] != self.type_enabled[item]
                    for item in self.TYPE_ORDER
                )
                try:
                    self._save_settings()
                    return {
                        "code": 0,
                        "msg": "{} 扫描已设为{}，等待应用".format(
                            source_type,
                            "开启"
                            if self.pending_type_enabled[source_type]
                            else "关闭",
                        ),
                    }
                except Exception as exc:
                    self.pending_type_enabled[source_type] = previous
                    self.config_dirty = any(
                        self.pending_type_enabled[item] != self.type_enabled[item]
                        for item in self.TYPE_ORDER
                    )
                    return {"code": 0, "msg": "分类开关保存失败：{}".format(exc)}
        if action == self.ACTION_APPLY_SCAN_CONFIG:
            action = self.ACTION_RESCAN
        if action != self.ACTION_RESCAN:
            return {"code": 0, "msg": "未知操作"}
        with self.lock:
            if self.config_dirty:
                try:
                    self._apply_pending_type_settings()
                except Exception as exc:
                    return {"code": 0, "msg": "扫描配置应用失败：{}".format(exc)}
            if not self.scan_enabled:
                self.scan_enabled = True
                try:
                    self._save_settings()
                except Exception as exc:
                    self.scan_enabled = False
                    return {"code": 0, "msg": "自动扫描开启失败：{}".format(exc)}
            ok = self._refresh_locked(
                allow_empty=not any(self.type_enabled.values())
            )
            self.inited = True
            if ok:
                _, detail = self._reload_app_vod_config(
                    expected_keys=self._generated_registry_keys()
                )
                message = "扫描完成：{} 个源，{}；{}".format(
                    len(self.cache["sources"]),
                    "{} (+{} ~{} -{})".format(
                        self.status["write_state"],
                        self.status["added_sites"],
                        self.status["updated_sites"],
                        self.status["removed_sites"],
                    ),
                    detail,
                )
            else:
                message = "扫描未完成：{}".format(self.status["error"] or self.status["write_state"])
            return {"code": 0, "msg": message}

    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "url": "",
            "header": {},
            "msg": "这是配置管理条目，不能作为媒体播放。",
        }

    def destroy(self):
        return "destroy"
