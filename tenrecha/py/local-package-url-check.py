# -*- coding: utf-8 -*-
# @tvbox-role manager
# @version v3.1
# @dual-app-loader WebHTV,OK影视
# @author 江 晚枫
# @signature 秋色正好，江 晚枫来过。
"""
TVBox 本地影仓 v3.1
===================

用途：
1. 扫描明确配置的 PY / JS / CSP / XBPQ / HTML 目录。
2. 自动识别当前运行环境：WebHTV 写入站点注入注册表；OK影视生成标准本地点播配置。
3. 保留 registry.json 中的手工注入项，仅替换本脚本生成的条目。
4. 在 TVBox 中按类型浏览、搜索本地源，并通过“一键扫描并加载”手动更新。
5. 一键清除自动注入站点及扫描状态，保留手工站点并主动重载 App。
6. 扫描种类集中在“扫描类型开关”面板，Toggle 只保存待应用值，由“应用并加载”一次执行。
7. 扫描配置可输入一个父目录，父目录不存在时自动创建，并映射或创建 py / js / csp / XBPQ / html 子目录。
8. 支持单文件忽略、增量扫描、变更预览、单份循环备份、撤销和并发写入保护。
9. “一键扫描并加载”会写入目标 App 的本地配置，并在当前操作返回后主动重载站点列表。
10. 可用 auto-loader.roots.json 配置扫描目录和文件数、深度、单文件大小上限。
11. 不启动后台扫描线程、定时器或文件监听；网络检测只在用户点击时执行。
12. 提供手动站点连通性检测；疑似失效的源写入屏蔽列表，检测受限只标记不屏蔽。
13. 保存上次成功扫描列表，App 重载点播配置后仍可显示站点分类和详情。
14. 无有效快照时进入管理页自动补扫一次（可在扫描配置中开关）；
    一键清除或恢复备份后自动补扫暂停，直到下次手动扫描。自动补扫不做网络检测。
15. 扫描、JAR 配对和站点检测写入单个限长诊断日志，达到上限后循环保留最新记录。
16. XBPQ / CSP 目录中的 TVBox 整包配置会按 sites[] 通用识别，仅导入本地依赖完整的站点。
17. 整包站点显示名自动添加“【来源包】”前缀，包名按目录结构通用推导，不依赖固定包名。
18. “扫描类型”中可开启“屏蔽18+站点”，命中项进入屏蔽分类并可手动恢复。
19. OK影视无需修改 APK：自动读取当前基础配置，合并本地站点并通过 A/B 配置切换立即重载。
20. OK影视原版不支持 WebHome，双端版会在 OK影视模式下自动跳过 HTML 类型。
21. 推荐页支持一键下载 ZIP 本地包，按下载站点备注名安全解压到 XBPQ/备注名，并自动扫描加载。
22. 设置页可保存下载地址及开关；默认地址为“单线路.zip”，下载时自动开启 XBPQ 扫描。
23. 扫描本地 JAR 时识别会主动结束 App 的名称限制及 SpiderApi 接口差异，按当前 App 自动拦截。
24. 名称匹配“自动加载*.py”的管理脚本不再跳过，会与其它本地 PY 源一起生成站点。
25. 整包本地 JAR 的声明 md5 过期时按文件实际 md5 修正，避免可读取的本地包被误判跳过。
26. 本地包下载改为多站点管理：备注名和网址成对保存，每个站点独立开关，推荐页单按钮批量安装全部已开启站点。
27. 新增下载网址轻量检测：保存时检查 HTTP/HTTPS 可达性、大小上限和 ZIP 文件头。
28. WebHTV 设置变更只做首页/分类轻量刷新；点播配置重载后追加页面恢复刷新，避免当前管理页空白。
29. 设置页支持多选删除在线下载站点；删除只移除网址设置，已解压本地包继续保留。
30. 一键扫描的 action/detailContent 双兼容入口增加进行中门闩和 4 秒防重复窗口，避免同一次点击扫描两次。
31. 站点显示后缀改为源文件直属父目录，例如 py/影视/xx.py 显示为 xx|[影视]。

说明：
- 脚本会自动探测 Android 共享存储根目录，再定位 TV/CustomCsp/registry.json。
- 站点根目录优先读取 TVBOX_HOME，否则自动识别 tvbox/TVBox 及子目录大小写。
- XBPQ 需在 auto-loader.roots.json 的 runtime.xbpqJar 配置包含 csp_XBPQ 的 JAR。
- JS / XBPQ / CSP 目录可用 site.json / *.site.json 显式绑定 api、ext 和专属 jar。
- XBPQ / CSP 子目录没有清单时，可用单 JAR 共享或同名 JSON/JAR 自动配对；有歧义时跳过。
- 整包配置不依赖固定文件名；api / ext / jar / homePage 相对路径按入口 JSON 所在目录解析。
- 可用性检测按站点顺序执行并复用同域名结果，仅点击按钮时访问网络。
- 点击“一键扫描并加载”后无需选择新的点播文件。
- OK影视首次扫描会记住当时的非自动生成配置作为基础配置；后续 A/B 切换不会覆盖基础来源。
- 保存或初始化扫描目录不会重载 App；其他注册表变更会在 action 返回后延迟重载，避免当前管理源被 PyLoader 清除。

可选文件标识（放在文件前 64 KB 的注释中）：
- @tvbox-source：明确作为站点源收录。
- @tvbox-ignore：明确忽略。
- @tvbox-role extension：WebHome/JS 扩展，不作为站点源。
- @tvbox-role library：依赖库，不作为站点源。
- @tvbox-role manager：普通配置管理脚本不重复加入；“自动加载*.py”仍作为站点收录。
- 严格识别默认开启；特殊格式可使用 @tvbox-source 强制收录。
"""

import base64
import copy
import hashlib
import json
import os
import re
import shutil
import socket
import threading
import time
import urllib.parse
import urllib.error
import urllib.request
import zipfile

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

# 进程级自动补扫冷却，防止“补扫 -> 重载 -> 重建实例 -> 再补扫”循环。
_AUTO_SCAN_STATE = {"last": 0.0}
_MANUAL_SCAN_LOCK = threading.Lock()
_MANUAL_SCAN_STATE = {}


class RegistryChangedError(RuntimeError):
    pass


class SiteTestCancelled(RuntimeError):
    pass


class PackageCompatibilityError(RuntimeError):
    pass


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Spider(BaseSpider):
    # ==========================================================================
    # 配置区
    # ==========================================================================
    SCAN_ROOTS = [
        {"path": _detect_child_dir(DETECTED_LOCAL_BASE, "py", "python"), "type": "PY", "extensions": [".py"]},
        {"path": _detect_child_dir(DETECTED_LOCAL_BASE, "js", "javascript"), "type": "JS", "extensions": [".js", ".json"]},
        {"path": _detect_child_dir(DETECTED_LOCAL_BASE, "csp"), "type": "CSP", "extensions": [".json"]},
        {"path": _detect_child_dir(DETECTED_LOCAL_BASE, "XBPQ"), "type": "XBPQ", "extensions": [".json"]},
        {"path": _detect_child_dir(DETECTED_LOCAL_BASE, "html"), "type": "HTML", "extensions": [".html"]},
    ]

    # WebHTV 原生站点注入注册表。
    REGISTRY_PATH = os.path.join(DETECTED_STORAGE_ROOT, "TV", "CustomCsp", "registry.json")
    OUTPUT_PATH = REGISTRY_PATH
    STORAGE_ROOT = DETECTED_STORAGE_ROOT
    LOCAL_BASE_DIR = DETECTED_LOCAL_BASE
    VERSION = "v3.1"

    APP_MODE_WEBHTV = "webhtv"
    APP_MODE_OKTV = "oktv"
    APP_MODE_UNKNOWN = "unknown"
    OK_CONFIG_A = os.path.join(DETECTED_STORAGE_ROOT, "TV", "CustomCsp", "ok-local-a.json")
    OK_CONFIG_B = os.path.join(DETECTED_STORAGE_ROOT, "TV", "CustomCsp", "ok-local-b.json")
    OK_BASE_CACHE = os.path.join(DETECTED_STORAGE_ROOT, "TV", "CustomCsp", "ok-base-config.json")
    OK_CONFIG_MARKER = "localAutoLoader"
    OK_CONFIG_VERSION = 1

    PACKAGE_DOWNLOAD_URL = "https://oss-v1.wangmeipo.cn/236/单线路.zip"
    PACKAGE_DOWNLOAD_NAME = "潇洒"
    PACKAGE_DOWNLOAD_ENABLED = True
    PACKAGE_INSTALL_MARKER = ".dual-local-package"
    PACKAGE_DOWNLOAD_DIR = os.path.join(
        DETECTED_STORAGE_ROOT, "TV", "CustomCsp", "downloads"
    )
    MAX_PACKAGE_DOWNLOAD_SIZE = 128 * 1024 * 1024
    MAX_PACKAGE_EXTRACT_SIZE = 512 * 1024 * 1024
    MAX_PACKAGE_FILES = 10000
    MAX_PACKAGE_FILE_SIZE = 128 * 1024 * 1024

    XBPQ_API = "csp_XBPQ"
    XBPQ_JAR = ""
    HTML_API = "csp_Builtin"

    PAGE_SIZE = 60
    BACKUP_BEFORE_WRITE = True
    ALLOW_EMPTY_WRITE = False
    DEFAULT_SEARCHABLE = 1
    DEFAULT_QUICK_SEARCH = 1
    STRICT_RECOGNITION = True
    CACHE_VERSION = 9
    AUTO_RELOAD_APP = True
    AUTO_SCAN_ON_EMPTY = True
    AUTO_SCAN_COOLDOWN = 300.0
    MANUAL_SCAN_DEDUP_WINDOW = 4.0
    APP_PORT_START = 9978
    APP_PORT_END = 9998
    APP_REQUEST_TIMEOUT = 0.35
    APP_RELOAD_DELAY = 1.0
    APP_PAGE_REFRESH_DELAY = 0.65
    MAX_SCAN_FILES = 3000
    MAX_SCAN_DEPTH = 8
    MAX_SOURCE_SIZE = 5 * 1024 * 1024
    MAX_JAR_DEX_SCAN_SIZE = 64 * 1024 * 1024
    MAX_LOG_SIZE = 256 * 1024
    SITE_TEST_TIMEOUT = 3.0
    MAX_SITE_TESTS = 50
    SITE_TEST_CACHE_VERSION = 3
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
    JS_EXTENSION_SUFFIXES = (".ext.js", ".extension.js", ".user.js")
    ADULT_SYMBOLS = ("🔞", "🈲", "㊙")
    ADULT_KEYWORDS = (
        "18禁", "r18", "成人", "色情", "情色", "无码", "有码", "女优",
        "麻豆", "偷拍", "乱伦", "淫", "福利姬", "裸聊", "约炮", "里番",
        "少妇", "爱色", "好色", "色播", "色库", "色岛", "色站", "黄色仓库",
        "小黄书", "榨汁姐", "国产麻豆", "高端外泄", "自拍偷拍", "国产自拍",
    )
    ADULT_LATIN_PATTERN = re.compile(
        r"(?:rule34|porn|hentai|jable|javday|jav6k|javffm|javtsunami|xvideos|"
        r"xhamster|xnxx|missav|mrjav|netflav|pornlulu|pornhub|sexnguon|"
        r"onlyfans|redtube|youporn|spankbang|brazzers|hanime|91porn|"
        r"91md|avgle|kissav|pandaav|airav|kanav|nowav|soav|owoav|qinav)",
        re.IGNORECASE,
    )
    # ==========================================================================

    TYPE_ORDER = {"PY": 0, "JS": 1, "CSP": 2, "XBPQ": 3, "HTML": 4}
    TYPE_PREFIX = {
        "PY": "",
        "JS": "",
        "CSP": "",
        "XBPQ": "",
        "HTML": "",
    }
    TYPE_LABEL = {
        "PY": "PY",
        "JS": "JS",
        "CSP": "JAR/CSP",
        "XBPQ": "XBPQ",
        "HTML": "HTML",
    }
    TYPE_GROUP = {
        "PY": "[py]",
        "JS": "[js]",
        "CSP": "[jar]",
        "XBPQ": "[xbpq]",
        "HTML": "[html]",
    }
    TYPE_EXTENSIONS = {
        "PY": [".py"],
        "JS": [".js", ".json"],
        "CSP": [".json"],
        "XBPQ": [".json"],
        "HTML": [".html"],
    }
    SCAN_SETTINGS_TID = "scan_settings"
    BACKUPS_TID = "scan_backups"
    STATUS_ID = "__local_source_status__"
    RESCAN_ID = "__local_source_rescan__"
    CLEAR_SITES_ID = "__local_source_clear_sites__"
    DELETE_BACKUPS_ID = "__local_source_delete_backups__"
    TEST_SITES_ID = "__local_source_test_sites__"
    RETEST_SITES_ID = "__local_source_retest_sites__"
    SCAN_BASE_PATH_ID = "__local_source_scan_base_path__"
    RESET_SCAN_BASE_ID = "__local_source_reset_scan_base__"
    DOWNLOAD_PACKAGE_ID = "__local_source_download_package__"
    DOWNLOAD_PACKAGE_ID_PREFIX = "__local_source_download_package__:"
    ACTION_RESCAN = "local_source_rescan"
    ACTION_CLEAR_SITES = "local_source_clear_sites"
    ACTION_DELETE_BACKUPS = "local_source_delete_backups"
    ACTION_TEST_SITES = "local_source_test_sites"
    ACTION_RETEST_SITES = "local_source_retest_sites"
    ACTION_EDIT_SCAN_BASE = "local_source_edit_scan_base"
    ACTION_RESET_SCAN_BASE = "local_source_reset_scan_base"
    ACTION_EDIT_SCAN_TYPES = "local_source_edit_scan_types"
    ACTION_EDIT_DOWNLOAD_URL = "local_source_edit_download_url"
    ACTION_TOGGLE_DOWNLOAD = "local_source_toggle_download"
    ACTION_DOWNLOAD_PACKAGE = "local_source_download_package"
    ACTION_DOWNLOAD_PACKAGE_PREFIX = "local_source_download_package:"
    ACTION_EDIT_DOWNLOAD_SWITCHES = "local_source_edit_download_switches"
    ACTION_DELETE_DOWNLOAD_SITES = "local_source_delete_download_sites"
    ACTION_APPLY_SCAN_CONFIG = "local_source_apply_scan_config"
    ACTION_TOGGLE_TYPE_PREFIX = "local_source_toggle_type:"
    ACTION_TOGGLE_AUTO_SCAN = "local_source_toggle_auto_scan"
    ACTION_TOGGLE_IGNORE_PREFIX = "local_source_toggle_ignore:"
    ACTION_RESTORE_SNAPSHOT_PREFIX = "local_source_restore_snapshot:"
    ACTION_SOURCE_PREFIX = "local_source_info:"

    def __init__(self):
        super().__init__()
        self.lock = threading.RLock()
        self.inited = False
        self.scan_roots = [dict(item) for item in self.SCAN_ROOTS]
        self.configured_scan_roots = [dict(item) for item in self.scan_roots]
        self.scan_base_path = ""
        self.registry_path = self.REGISTRY_PATH
        self.output_path = self.OUTPUT_PATH
        self.settings_path = os.path.join(os.path.dirname(self.REGISTRY_PATH), "auto-loader.settings.json")
        self.cache_path = os.path.join(os.path.dirname(self.REGISTRY_PATH), "auto-loader.cache.json")
        self.backup_dir = os.path.join(os.path.dirname(self.REGISTRY_PATH), "backups")
        self.roots_config_path = os.path.join(
            os.path.dirname(self.REGISTRY_PATH), "auto-loader.roots.json"
        )
        self.log_path = os.path.join(
            os.path.dirname(self.REGISTRY_PATH), "auto-loader.log"
        )
        self.xbpq_api = self.XBPQ_API
        self.xbpq_jar = self.XBPQ_JAR
        self.html_api = self.HTML_API
        self.local_base_dir = self.LOCAL_BASE_DIR
        self.page_size = self.PAGE_SIZE
        self.max_scan_files = self.MAX_SCAN_FILES
        self.max_scan_depth = self.MAX_SCAN_DEPTH
        self.max_source_size = self.MAX_SOURCE_SIZE
        self.max_log_size = self.MAX_LOG_SIZE
        self.backup_before_write = self.BACKUP_BEFORE_WRITE
        self.allow_empty_write = self.ALLOW_EMPTY_WRITE
        self.generated_insert_index = self.GENERATED_INSERT_INDEX
        self.type_enabled = {source_type: True for source_type in self.TYPE_ORDER}
        self.pending_type_enabled = dict(self.type_enabled)
        self.block_adult_sites = False
        self.pending_block_adult_sites = False
        self.config_dirty = False
        self.manual_ignored_sources = set()
        self.auto_blocked_sources = set()
        self.adult_blocked_sources = set()
        self.adult_allowed_sources = set()
        self.ignored_sources = set()
        self.site_test_results = {}
        self.incomplete_scan_roots = []
        self.incomplete_scan_types = set()
        self.strict_recognition = self.STRICT_RECOGNITION
        self.auto_reload_app = self.AUTO_RELOAD_APP
        self.auto_scan_on_empty = self.AUTO_SCAN_ON_EMPTY
        self.auto_scan_suspended = False
        self.app_mode = self._detect_app_mode()
        self.ok_config_a = self.OK_CONFIG_A
        self.ok_config_b = self.OK_CONFIG_B
        self.ok_base_cache_path = self.OK_BASE_CACHE
        self.ok_base_config_url = ""
        self.ok_last_target = ""
        self.package_download_url = self.PACKAGE_DOWNLOAD_URL
        self.package_download_enabled = self.PACKAGE_DOWNLOAD_ENABLED
        self.package_download_sites = [
            {
                "id": "xiaosa",
                "name": self.PACKAGE_DOWNLOAD_NAME,
                "url": self.PACKAGE_DOWNLOAD_URL,
                "enabled": bool(self.PACKAGE_DOWNLOAD_ENABLED),
            }
        ]
        self.package_download_dir = self.PACKAGE_DOWNLOAD_DIR
        self._package_download_lock = threading.Lock()
        self._package_download_thread = None
        self._package_download_state = "idle"
        self._package_download_message = ""
        self._package_download_active_site_id = ""
        self._package_download_active_site_name = ""
        self.app_server_ports = list(range(self.APP_PORT_START, self.APP_PORT_END + 1))
        self.last_app_port = 0
        self.cache = self._empty_cache()
        self.status = self._empty_status()
        self._dialog_refs = []
        self._notification_refs = []
        self._site_test_toast = None
        self._site_test_thread = None
        self._site_test_control_lock = threading.Lock()
        self._site_test_cancel = threading.Event()
        self._destroyed = False
        self._jar_inspection_cache = {}
        self._app_identity_cache = None
        self._host_spider_api_cache = None
        self._retest_pending = []
        self._retest_auto_blocked = set()
        self._reload_generation = 0
        self._page_refresh_generation = 0
        self._author_scan_surprise_shown = False

    def getName(self):
        return "本地影仓 {}".format(self.VERSION)

    def _detect_app_mode(self):
        """探测当前进程自己的本机端口，避免多 App 同开时误判。"""
        try:
            from java import jclass

            proxy_class = jclass("com.github.catvod.Proxy")
            port = int(proxy_class.getPort())
            if port > 0:
                try:
                    payload = self._request_json(
                        "http://127.0.0.1:{}/manage/configs".format(port), 0.8
                    )
                    if isinstance(payload.get("items"), list):
                        return self.APP_MODE_WEBHTV
                except Exception:
                    pass
            try:
                jclass("com.fongmi.android.tv.setting.CustomCspSetting")
                return self.APP_MODE_WEBHTV
            except Exception:
                pass
            try:
                jclass("com.fongmi.android.tv.bean.Config")
                return self.APP_MODE_OKTV
            except Exception:
                return self.APP_MODE_UNKNOWN
        except Exception:
            # 桌面验证环境没有 Chaquopy Java bridge，保留可测试状态。
            return self.APP_MODE_UNKNOWN

    def _app_mode_label(self):
        return {
            self.APP_MODE_WEBHTV: "WebHTV",
            self.APP_MODE_OKTV: "OK影视",
        }.get(self.app_mode, "未识别环境")

    def init(self, extend=""):
        with self.lock:
            if self.inited:
                return
            self._apply_extend(extend)
            self._load_roots_config()
            self.configured_scan_roots = [dict(item) for item in self.scan_roots]
            self._load_settings()
            try:
                self._normalize_backup_storage()
            except Exception as exc:
                self._warn("历史备份整理失败: {}".format(exc))
            startup_warnings = list(self.status["warnings"])
            self._set_manual_idle_status()
            try:
                restored = self._restore_scan_snapshot()
            except Exception as exc:
                restored = False
                # 记入 startup_warnings，避免被补扫的状态重置覆盖
                warning = "扫描快照恢复失败: {}".format(exc)
                startup_warnings.append(warning)
                self._log("WARN", warning)
            if not restored:
                try:
                    self._auto_scan_on_enter_locked()
                except Exception as exc:
                    self._warn("进入自动补扫失败: {}".format(exc))
            if startup_warnings:
                self.status["warnings"] = list(dict.fromkeys(
                    startup_warnings + self.status["warnings"]
                ))
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
            "adult_filtered": 0,
            "compatibility_blocked": 0,
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
        self.log_path = self._string_option(
            data,
            ("log_path", "logPath"),
            os.path.join(os.path.dirname(self.output_path), "auto-loader.log"),
        )
        self.xbpq_api = self._string_option(data, ("xbpq_api", "xbpqApi"), self.xbpq_api)
        self.xbpq_jar = self._string_option(data, ("xbpq_jar", "xbpqJar"), self.xbpq_jar)
        self.html_api = self._string_option(data, ("html_api", "htmlApi"), self.html_api)
        self.ok_config_a = self._string_option(
            data, ("ok_config_a", "okConfigA"), self.ok_config_a
        )
        self.ok_config_b = self._string_option(
            data, ("ok_config_b", "okConfigB"), self.ok_config_b
        )
        self.ok_base_cache_path = self._string_option(
            data, ("ok_base_cache", "okBaseCache"), self.ok_base_cache_path
        )
        self.ok_base_config_url = self._string_option(
            data, ("ok_base_config", "okBaseConfig"), self.ok_base_config_url
        )
        self._apply_package_download_options(data)
        self.package_download_dir = self._string_option(
            data,
            ("package_download_dir", "packageDownloadDir"),
            self.package_download_dir,
        )
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
        self.max_log_size = self._int_option(
            data,
            ("max_log_size", "maxLogSize"),
            self.max_log_size,
            16 * 1024,
            2 * 1024 * 1024,
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
        self.auto_scan_on_empty = self._bool_option(
            data, ("auto_scan_on_empty", "autoScanOnEmpty"), self.auto_scan_on_empty
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
            runtime = dict(data) if isinstance(data, dict) else {}
            if isinstance(runtime.get("runtime"), dict):
                runtime.update(runtime["runtime"])
            self.xbpq_api = self._string_option(
                runtime, ("xbpq_api", "xbpqApi"), self.xbpq_api
            )
            self.xbpq_jar = self._string_option(
                runtime, ("xbpq_jar", "xbpqJar"), self.xbpq_jar
            )
            self.ok_config_a = self._string_option(
                runtime, ("ok_config_a", "okConfigA"), self.ok_config_a
            )
            self.ok_config_b = self._string_option(
                runtime, ("ok_config_b", "okConfigB"), self.ok_config_b
            )
            self.ok_base_cache_path = self._string_option(
                runtime,
                ("ok_base_cache", "okBaseCache"),
                self.ok_base_cache_path,
            )
            self.ok_base_config_url = self._string_option(
                runtime,
                ("ok_base_config", "okBaseConfig"),
                self.ok_base_config_url,
            )
            self._apply_package_download_options(runtime)
            self.package_download_dir = self._string_option(
                runtime,
                ("package_download_dir", "packageDownloadDir"),
                self.package_download_dir,
            )
            self.log_path = self._string_option(
                runtime, ("log_path", "logPath"), self.log_path
            )
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
                self.max_log_size = self._int_option(
                    limits,
                    ("max_log_size", "maxLogSize"),
                    self.max_log_size,
                    16 * 1024,
                    2 * 1024 * 1024,
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
                elif source_type == "CSP":
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

    def _package_download_site_id(self, name, url):
        payload = "{}\0{}".format(str(name or ""), str(url or ""))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _normalize_package_download_name(self, value):
        name = re.sub(r"[\x00-\x1f]+", " ", str(value or "")).strip()
        name = re.sub(r"\s+", " ", name)
        if not name:
            raise ValueError("备注名不能为空")
        if name in (".", "..") or re.search(r"[\\/:*?\"<>|]", name):
            raise ValueError("备注名不能包含 \\ / : * ? \" < > | 等文件夹非法字符")
        if len(name) > 40:
            raise ValueError("备注名不能超过 40 个字符")
        return name

    def _default_package_download_site(self, enabled=None):
        return {
            "id": "xiaosa",
            "name": self.PACKAGE_DOWNLOAD_NAME,
            "url": self.PACKAGE_DOWNLOAD_URL,
            "enabled": bool(
                self.PACKAGE_DOWNLOAD_ENABLED if enabled is None else enabled
            ),
        }

    def _migrate_package_download_name(self, value, fallback="本地包"):
        raw = str(value or fallback)
        try:
            return self._normalize_package_download_name(raw)
        except Exception:
            migrated = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", raw)
            migrated = re.sub(r"\s+", " ", migrated).strip(" ._")
            return self._normalize_package_download_name(
                (migrated or fallback)[:40]
            )

    def _normalize_package_download_sites(self, values, default_if_empty=True):
        normalized = []
        seen_names = set()
        seen_urls = set()
        if isinstance(values, dict):
            values = [values]
        if isinstance(values, list):
            for raw in values[:50]:
                if not isinstance(raw, dict):
                    continue
                try:
                    url = self._normalize_package_download_url(
                        raw.get("url", raw.get("downloadUrl", ""))
                    )
                    name = self._migrate_package_download_name(
                        raw.get("name", raw.get("remark", raw.get("label", ""))),
                        fallback=self._package_name_from_url(url),
                    )
                except Exception:
                    continue
                name_key = name.casefold()
                url_key = url.casefold()
                if name_key in seen_names or url_key in seen_urls:
                    continue
                site_id = re.sub(
                    r"[^A-Za-z0-9_-]+", "", str(raw.get("id", "")).strip()
                )[:40]
                if not site_id:
                    site_id = self._package_download_site_id(name, url)
                normalized.append(
                    {
                        "id": site_id,
                        "name": name,
                        "url": url,
                        "enabled": self._as_bool(raw.get("enabled", True), True),
                    }
                )
                seen_names.add(name_key)
                seen_urls.add(url_key)
        if not normalized and default_if_empty:
            normalized = [self._default_package_download_site()]
        return normalized

    def _sync_legacy_package_download_fields(self):
        sites = self.package_download_sites or [
            self._default_package_download_site()
        ]
        self.package_download_sites = sites
        primary = next(
            (
                item
                for item in sites
                if str(item.get("name", "")).strip() == self.PACKAGE_DOWNLOAD_NAME
            ),
            sites[0],
        )
        self.package_download_url = str(primary.get("url", self.PACKAGE_DOWNLOAD_URL))
        self.package_download_enabled = bool(primary.get("enabled", True))

    def _apply_package_download_options(self, data):
        if not isinstance(data, dict):
            return
        raw_sites = data.get(
            "package_download_sites", data.get("packageDownloadSites")
        )
        if isinstance(raw_sites, (list, dict)):
            normalized = self._normalize_package_download_sites(raw_sites)
            if normalized:
                self.package_download_sites = normalized
                self._sync_legacy_package_download_fields()
                return
        has_url = "package_download_url" in data or "packageDownloadUrl" in data
        has_enabled = (
            "package_download_enabled" in data
            or "packageDownloadEnabled" in data
        )
        if not (has_url or has_enabled):
            return
        url = self._string_option(
            data,
            ("package_download_url", "packageDownloadUrl"),
            self.package_download_url,
        )
        enabled = self._bool_option(
            data,
            ("package_download_enabled", "packageDownloadEnabled"),
            self.package_download_enabled,
        )
        try:
            url = self._normalize_package_download_url(url)
        except Exception:
            url = self.PACKAGE_DOWNLOAD_URL
        self.package_download_sites = [
            {
                "id": "xiaosa"
                if url == self.PACKAGE_DOWNLOAD_URL
                else self._package_download_site_id("自定义", url),
                "name": self.PACKAGE_DOWNLOAD_NAME
                if url == self.PACKAGE_DOWNLOAD_URL
                else "自定义",
                "url": url,
                "enabled": bool(enabled),
            }
        ]
        self._sync_legacy_package_download_fields()

    def _load_settings(self):
        path = os.path.abspath(os.path.expanduser(self.settings_path))
        if not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if not isinstance(data, dict):
                return
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
            self.block_adult_sites = self._as_bool(
                data.get("block_adult_sites", data.get("blockAdultSites", False)),
                False,
            )
            self.pending_block_adult_sites = self._as_bool(
                data.get(
                    "pending_block_adult_sites",
                    data.get("pendingBlockAdultSites", self.block_adult_sites),
                ),
                self.block_adult_sites,
            )
            self.config_dirty = any(
                self.pending_type_enabled[source_type] != self.type_enabled[source_type]
                for source_type in self.TYPE_ORDER
            ) or self.pending_block_adult_sites != self.block_adult_sites
            scan_base = data.get("scan_base_path", data.get("scanBasePath", ""))
            if str(scan_base or "").strip():
                self._apply_scan_base_path(str(scan_base))
            test_results = data.get("site_test_results", data.get("siteTestResults", {}))
            if isinstance(test_results, dict):
                self.site_test_results = {
                    str(identity): result
                    for identity, result in test_results.items()
                    if str(identity).strip() and isinstance(result, dict)
                }
            self._retest_pending = list(dict.fromkeys(
                str(identity).strip()
                for identity in data.get(
                    "retest_pending", data.get("retestPending", [])
                )
                if str(identity).strip()
            )) if isinstance(
                data.get("retest_pending", data.get("retestPending", [])), list
            ) else []
            self._retest_auto_blocked = self._identity_set(
                data.get(
                    "retest_auto_blocked", data.get("retestAutoBlocked", [])
                )
            )
            manual_ignored = data.get(
                "manual_ignored_sources", data.get("manualIgnoredSources")
            )
            auto_blocked = data.get(
                "auto_blocked_sources", data.get("autoBlockedSources")
            )
            self.adult_blocked_sources = self._identity_set(
                data.get("adult_blocked_sources", data.get("adultBlockedSources", []))
            )
            self.adult_allowed_sources = self._identity_set(
                data.get("adult_allowed_sources", data.get("adultAllowedSources", []))
            )
            if isinstance(manual_ignored, list) or isinstance(auto_blocked, list):
                self.manual_ignored_sources = self._identity_set(manual_ignored)
                self.auto_blocked_sources = self._identity_set(auto_blocked)
            else:
                legacy_ignored = self._identity_set(
                    data.get("ignored_sources", data.get("ignoredSources", []))
                )
                # 旧版本没有记录忽略来源，无法可靠区分手动选择和测活屏蔽。
                # 按手动忽略迁移，避免升级后擅自恢复用户明确隐藏的站点。
                self.manual_ignored_sources = legacy_ignored
                self.auto_blocked_sources = set()
            self.auto_blocked_sources = {
                identity
                for identity in self.auto_blocked_sources
                if self.site_test_results.get(identity, {}).get("state")
                != "limited"
            }
            self._sync_ignored_sources()
            self.strict_recognition = self._as_bool(
                data.get("strict_recognition", data.get("strictRecognition", self.strict_recognition)),
                self.strict_recognition,
            )
            self.auto_scan_on_empty = self._as_bool(
                data.get("auto_scan_on_empty", data.get("autoScanOnEmpty", self.auto_scan_on_empty)),
                self.auto_scan_on_empty,
            )
            self.auto_scan_suspended = self._as_bool(
                data.get("auto_scan_suspended", data.get("autoScanSuspended", False)),
                False,
            )
            self._author_scan_surprise_shown = self._as_bool(
                data.get(
                    "author_scan_surprise_shown",
                    data.get("authorScanSurpriseShown", False),
                ),
                False,
            )
            saved_base_url = str(
                data.get("ok_base_config_url", data.get("okBaseConfigUrl", ""))
                or ""
            ).strip()
            if saved_base_url and not self.ok_base_config_url:
                self.ok_base_config_url = saved_base_url
            self.ok_last_target = str(
                data.get("ok_last_target", data.get("okLastTarget", "")) or ""
            ).strip()
            self._apply_package_download_options(data)
            try:
                port = int(data.get("last_app_port", data.get("lastAppPort", 0)) or 0)
                self.last_app_port = port if self.APP_PORT_START <= port <= 65535 else 0
            except Exception:
                self.last_app_port = 0
        except Exception as exc:
            self._warn("扫描设置读取失败，将使用默认配置: {}".format(exc))

    def _identity_set(self, values):
        if not isinstance(values, (list, tuple, set)):
            return set()
        return {
            str(item).strip() for item in values if str(item).strip()
        }

    def _sync_ignored_sources(self):
        self.ignored_sources = set(self.manual_ignored_sources)
        self.ignored_sources.update(self.auto_blocked_sources)
        if self.block_adult_sites:
            self.ignored_sources.update(self.adult_blocked_sources)

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
        self._sync_legacy_package_download_fields()
        data = {
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
            "block_adult_sites": bool(self.block_adult_sites),
            "pending_block_adult_sites": bool(
                self.pending_block_adult_sites
            ),
            "strict_recognition": bool(self.strict_recognition),
            "auto_scan_on_empty": bool(self.auto_scan_on_empty),
            "auto_scan_suspended": bool(self.auto_scan_suspended),
            "scan_base_path": self.scan_base_path,
            "ignored_sources": sorted(self.ignored_sources),
            "manual_ignored_sources": sorted(self.manual_ignored_sources),
            "auto_blocked_sources": sorted(self.auto_blocked_sources),
            "adult_blocked_sources": sorted(self.adult_blocked_sources),
            "adult_allowed_sources": sorted(self.adult_allowed_sources),
            "site_test_results": self.site_test_results,
            "retest_pending": list(self._retest_pending),
            "retest_auto_blocked": sorted(self._retest_auto_blocked),
            "last_app_port": int(self.last_app_port or 0),
            "ok_base_config_url": self.ok_base_config_url,
            "ok_last_target": self.ok_last_target,
            "package_download_sites": [
                {
                    "id": str(item.get("id", "")),
                    "name": str(item.get("name", "")),
                    "url": str(item.get("url", "")),
                    "enabled": bool(item.get("enabled", True)),
                }
                for item in self.package_download_sites
            ],
            "package_download_url": self.package_download_url,
            "package_download_enabled": bool(self.package_download_enabled),
            "author_scan_surprise_shown": bool(
                self._author_scan_surprise_shown
            ),
        }
        self._atomic_write_plain_json(path, data)

    def _normalize_scan_base_path(self, value):
        path = str(value or "").strip().strip('"').strip("'")
        if path.lower().startswith("file://"):
            path = path[7:]
        if not path:
            return ""
        path = os.path.expanduser(path)
        if not os.path.isabs(path):
            path = os.path.join(self.STORAGE_ROOT, path.lstrip("/"))
        return os.path.realpath(os.path.abspath(path))

    def _scan_roots_for_base(self, base_path):
        return [
            {
                "path": _detect_child_dir(base_path, "py", "python"),
                "type": "PY",
                "extensions": [".py"],
            },
            {
                "path": _detect_child_dir(base_path, "js", "javascript"),
                "type": "JS",
                "extensions": [".js", ".json"],
            },
            {
                "path": _detect_child_dir(base_path, "csp"),
                "type": "CSP",
                "extensions": [".json"],
            },
            {
                "path": _detect_child_dir(base_path, "XBPQ"),
                "type": "XBPQ",
                "extensions": [".json"],
            },
            {
                "path": _detect_child_dir(base_path, "html"),
                "type": "HTML",
                "extensions": [".html"],
            },
        ]

    def _apply_scan_base_path(self, value):
        path = self._normalize_scan_base_path(value)
        if path:
            self.scan_base_path = path
            self.local_base_dir = path
            self.scan_roots = self._scan_roots_for_base(path)
        else:
            self.scan_base_path = ""
            self.local_base_dir = self.LOCAL_BASE_DIR
            self.scan_roots = [dict(item) for item in self.configured_scan_roots]

    def _create_scan_base_tree(self, path):
        created = []
        try:
            if os.path.exists(path) and not os.path.isdir(path):
                raise ValueError("输入路径不是目录: {}".format(path))
            if not os.path.isdir(path):
                missing = []
                current = path
                while current and not os.path.exists(current):
                    missing.append(current)
                    parent = os.path.dirname(current)
                    if parent == current:
                        break
                    current = parent
                for directory in reversed(missing):
                    if os.path.isdir(directory):
                        continue
                    try:
                        os.mkdir(directory)
                    except FileExistsError:
                        if not os.path.isdir(directory):
                            raise
                    else:
                        created.append(directory)
            for root in self._scan_roots_for_base(path):
                directory = root["path"]
                if os.path.isdir(directory):
                    continue
                try:
                    os.mkdir(directory)
                except FileExistsError:
                    if not os.path.isdir(directory):
                        raise
                else:
                    created.append(directory)
            return created
        except Exception:
            self._remove_created_scan_dirs(created)
            raise

    def _remove_created_scan_dirs(self, directories):
        for directory in reversed(directories):
            try:
                os.rmdir(directory)
            except Exception:
                pass

    def _set_scan_base_path(self, value):
        path = self._normalize_scan_base_path(value)
        previous_path = self.scan_base_path
        previous_base = self.local_base_dir
        previous_roots = [dict(item) for item in self.scan_roots]
        created_dirs = []
        try:
            if path:
                created_dirs = self._create_scan_base_tree(path)
                if not os.access(path, os.R_OK):
                    raise ValueError("目录不可读: {}".format(path))
            self._apply_scan_base_path(path)
            self._save_settings()
            self._set_manual_idle_status(
                "扫描根目录已更新，等待点击一键扫描并加载"
            )
            self._clear_scan_cache_file()
            if created_dirs:
                self._log(
                    "INFO",
                    "扫描分类目录已自动创建: {}".format(
                        ", ".join(created_dirs)
                    ),
                )
        except Exception:
            self.scan_base_path = previous_path
            self.local_base_dir = previous_base
            self.scan_roots = previous_roots
            self._remove_created_scan_dirs(created_dirs)
            raise
        return self.scan_base_path

    def _set_pending_type_settings(self, values, block_adult_sites=None):
        previous = dict(self.pending_type_enabled)
        previous_block_adult = self.pending_block_adult_sites
        previous_dirty = self.config_dirty
        for source_type in self.TYPE_ORDER:
            if source_type in values:
                self.pending_type_enabled[source_type] = bool(values[source_type])
        if block_adult_sites is not None:
            self.pending_block_adult_sites = bool(block_adult_sites)
        self.config_dirty = any(
            self.pending_type_enabled[item] != self.type_enabled[item]
            for item in self.TYPE_ORDER
        ) or self.pending_block_adult_sites != self.block_adult_sites
        try:
            self._save_settings()
        except Exception:
            self.pending_type_enabled = previous
            self.pending_block_adult_sites = previous_block_adult
            self.config_dirty = previous_dirty
            raise
        return self.config_dirty

    def _current_android_activity(self, jclass):
        app_class = jclass("com.fongmi.android.tv.App")
        activity_class = jclass("android.app.Activity")
        modifier_class = jclass("java.lang.reflect.Modifier")
        app_info = app_class.getClass()
        activity_info = activity_class.getClass()

        for method in app_info.getDeclaredMethods():
            try:
                if not modifier_class.isStatic(method.getModifiers()):
                    continue
                if len(method.getParameterTypes()) != 0:
                    continue
                if not activity_info.isAssignableFrom(method.getReturnType()):
                    continue
                method.setAccessible(True)
                try:
                    activity = method.invoke(None, [])
                except Exception:
                    activity = method.invoke(None)
                if activity is not None:
                    return activity
            except Exception:
                continue

        app = None
        for field in app_info.getDeclaredFields():
            try:
                if not modifier_class.isStatic(field.getModifiers()):
                    continue
                if not app_info.isAssignableFrom(field.getType()):
                    continue
                field.setAccessible(True)
                app = field.get(None)
                if app is not None:
                    break
            except Exception:
                continue
        if app is not None:
            for field in app.getClass().getDeclaredFields():
                try:
                    if modifier_class.isStatic(field.getModifiers()):
                        continue
                    if not activity_info.isAssignableFrom(field.getType()):
                        continue
                    field.setAccessible(True)
                    activity = field.get(app)
                    if activity is not None:
                        return activity
                except Exception:
                    continue
        raise ValueError("未找到当前 Android 页面")

    def _android_ui_context(self, jclass):
        try:
            activity = self._current_android_activity(jclass)
            if activity is not None:
                return activity, activity
        except Exception:
            pass

        context_candidates = []
        try:
            app_class = jclass("com.fongmi.android.tv.App")
            for method_name in ("get", "getInstance", "instance"):
                try:
                    method = getattr(app_class, method_name)
                    context = method() if callable(method) else method
                    if context is not None:
                        context_candidates.append(context)
                except Exception:
                    continue
        except Exception:
            pass
        try:
            activity_thread = jclass("android.app.ActivityThread")
            context = activity_thread.currentApplication()
            if context is not None:
                context_candidates.append(context)
        except Exception:
            pass
        try:
            platform = jclass("com.chaquo.python.Python").getPlatform()
            for method_name in (
                "getApplication", "getApplicationContext", "getContext",
            ):
                try:
                    method = getattr(platform, method_name)
                    context = method() if callable(method) else method
                    if context is not None:
                        context_candidates.append(context)
                except Exception:
                    continue
        except Exception:
            pass
        return None, next(
            (context for context in context_candidates if context is not None),
            None,
        )

    def _open_scan_base_dialog(self):
        try:
            from java import dynamic_proxy, jclass

            toast_class = jclass("android.widget.Toast")
            edit_text_class = jclass("android.widget.EditText")
            input_type = jclass("android.text.InputType")
            click_listener = jclass(
                "android.content.DialogInterface$OnClickListener"
            )
            runnable_class = jclass("java.lang.Runnable")
            try:
                builder_class = jclass(
                    "com.google.android.material.dialog.MaterialAlertDialogBuilder"
                )
            except Exception:
                builder_class = jclass("android.app.AlertDialog$Builder")
            activity = self._current_android_activity(jclass)
            owner = self

            class SaveListener(dynamic_proxy(click_listener)):
                def __init__(self, edit):
                    super().__init__()
                    self.edit = edit

                def onClick(self, dialog, which):
                    try:
                        value = str(self.edit.getText().toString())
                        with owner.lock:
                            saved = owner._set_scan_base_path(value)
                        message = (
                            "扫描根目录已恢复自动探测"
                            if not saved
                            else "扫描根目录已保存: {}".format(saved)
                        )
                        toast_class.makeText(
                            activity, message, toast_class.LENGTH_LONG
                        ).show()
                    except Exception as exc:
                        toast_class.makeText(
                            activity,
                            "扫描根目录保存失败: {}".format(exc),
                            toast_class.LENGTH_LONG,
                        ).show()

            class CancelListener(dynamic_proxy(click_listener)):
                def onClick(self, dialog, which):
                    return None

            class ShowDialog(dynamic_proxy(runnable_class)):
                def run(self):
                    try:
                        self._run_dialog()
                    except Exception as exc:
                        message = "根目录输入框打开失败: {}".format(exc)
                        owner._log("ERROR", message)
                        try:
                            toast_class.makeText(
                                activity, message, toast_class.LENGTH_LONG
                            ).show()
                        except Exception:
                            owner._notify_app(message)

                def _run_dialog(self):
                    edit = edit_text_class(activity)
                    current = owner.scan_base_path or owner.local_base_dir
                    edit.setSingleLine(True)
                    edit.setInputType(
                        input_type.TYPE_CLASS_TEXT
                        | input_type.TYPE_TEXT_VARIATION_URI
                    )
                    edit.setHint("/storage/emulated/0/xxxx/xxx")
                    edit.setText(current)
                    edit.setSelection(len(current))
                    save_listener = SaveListener(edit)
                    cancel_listener = CancelListener()
                    builder = builder_class(activity)
                    builder.setTitle("设置扫描根目录")
                    builder.setView(edit)
                    builder.setPositiveButton("保存", save_listener)
                    builder.setNegativeButton("取消", cancel_listener)
                    dialog = builder.show()
                    edit.requestFocus()
                    owner._dialog_refs.extend(
                        [edit, save_listener, cancel_listener, dialog]
                    )
                    owner._dialog_refs = owner._dialog_refs[-12:]

            runner = ShowDialog()
            self._dialog_refs.append(runner)
            self._dialog_refs = self._dialog_refs[-12:]
            activity.runOnUiThread(runner)
            return True, ""
        except Exception as exc:
            return False, "根目录输入框打开失败: {}".format(exc)

    def _normalize_package_download_url(self, value):
        url = str(value or "").strip().strip('"').strip("'")
        if not url:
            raise ValueError("下载地址不能为空")
        if len(url) > 2048:
            raise ValueError("下载地址过长")
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
            raise ValueError("下载地址必须是 http 或 https URL")
        return url

    def _probe_package_download_url(self, value, timeout=8):
        url = self._normalize_package_download_url(value)
        request = urllib.request.Request(
            self._encoded_download_url(url),
            headers={
                "User-Agent": "okhttp/4.12.0",
                "Accept": "application/zip, application/octet-stream, */*",
                "Range": "bytes=0-3",
                "Connection": "close",
            },
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request, timeout=max(2, int(timeout))) as response:
                status = int(getattr(response, "status", response.getcode()))
                if status not in (200, 206):
                    raise ValueError("网址返回 HTTP {}".format(status))
                content_length = str(response.headers.get("Content-Length", "")).strip()
                content_range = str(response.headers.get("Content-Range", "")).strip()
                total_size = 0
                match = re.search(r"/(\d+)$", content_range)
                if match:
                    total_size = int(match.group(1))
                elif status == 200 and content_length.isdigit():
                    total_size = int(content_length)
                if total_size > self.MAX_PACKAGE_DOWNLOAD_SIZE:
                    raise ValueError("ZIP 超过下载上限")
                signature = response.read(4)
                if signature not in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
                    content_type = str(
                        response.headers.get("Content-Type", "")
                    ).split(";", 1)[0].strip()
                    raise ValueError(
                        "网址返回的不是 ZIP 文件（Content-Type: {}）".format(
                            content_type or "未知"
                        )
                    )
                return {
                    "url": str(getattr(response, "geturl", lambda: url)() or url),
                    "status": status,
                    "content_type": str(
                        response.headers.get("Content-Type", "")
                    ).split(";", 1)[0].strip(),
                    "size": total_size,
                    "zip": True,
                }
        except urllib.error.HTTPError as exc:
            raise ValueError("网址访问失败：HTTP {}".format(exc.code))
        except urllib.error.URLError as exc:
            raise ValueError("网址访问失败：{}".format(exc.reason))
        except (socket.timeout, TimeoutError):
            raise ValueError("网址检测超时")

    def _enabled_package_download_sites(self):
        return [
            dict(item)
            for item in self.package_download_sites
            if bool(item.get("enabled", True))
        ]

    def _find_package_download_site(self, site_id):
        value = str(site_id or "").strip()
        for item in self.package_download_sites:
            if str(item.get("id", "")) == value:
                return item
        return None

    def _package_download_sites_summary(self):
        return ", ".join(
            "{}:{}".format(
                item.get("name", "未命名"),
                "开" if item.get("enabled", True) else "关",
            )
            for item in self.package_download_sites
        ) or "无"

    def _add_or_update_package_download_site(self, name, url, verify=False):
        clean_name = self._normalize_package_download_name(name)
        clean_url = self._normalize_package_download_url(url)
        if verify:
            self._probe_package_download_url(clean_url)
        previous = copy.deepcopy(self.package_download_sites)
        name_match = None
        url_match = None
        for item in self.package_download_sites:
            if str(item.get("name", "")).casefold() == clean_name.casefold():
                name_match = item
            if str(item.get("url", "")).casefold() == clean_url.casefold():
                url_match = item
        if name_match is not None and url_match is not None and name_match is not url_match:
            raise ValueError("备注名和网址分别属于两个已有站点")
        target = name_match or url_match
        created = target is None
        moved = None
        if created:
            if len(self.package_download_sites) >= 50:
                raise ValueError("下载站点最多保存 50 个")
            installed_marker = self._read_package_install_marker(
                self._package_install_target(site_name=clean_name)
            )
            installed_id = re.sub(
                r"[^A-Za-z0-9_-]+",
                "",
                str(installed_marker.get("id", "")).strip(),
            )[:40]
            target = {
                "id": installed_id
                or self._package_download_site_id(clean_name, clean_url),
                "name": clean_name,
                "url": clean_url,
                "enabled": True,
            }
            self.package_download_sites.append(target)
        else:
            old_name = str(target.get("name", "")).strip()
            if old_name and old_name != clean_name:
                moved = self._rename_package_install_directory(
                    target.get("id", ""), old_name, clean_name
                )
            target["name"] = clean_name
            target["url"] = clean_url
        try:
            self._sync_legacy_package_download_fields()
            self._save_settings()
        except Exception:
            self.package_download_sites = previous
            self._sync_legacy_package_download_fields()
            try:
                self._rollback_package_install_rename(moved)
            except Exception as rollback_exc:
                self._log(
                    "ERROR",
                    "下载站点备注目录回滚失败: {}".format(rollback_exc),
                )
            raise
        return dict(target), created

    def _set_package_download_site_states(self, values):
        if not isinstance(values, dict):
            raise ValueError("下载站点开关数据无效")
        previous = copy.deepcopy(self.package_download_sites)
        changed = False
        for item in self.package_download_sites:
            site_id = str(item.get("id", ""))
            if site_id not in values:
                continue
            enabled = bool(values[site_id])
            if bool(item.get("enabled", True)) != enabled:
                item["enabled"] = enabled
                changed = True
        try:
            self._sync_legacy_package_download_fields()
            self._save_settings()
        except Exception:
            self.package_download_sites = previous
            self._sync_legacy_package_download_fields()
            raise
        return changed

    def _delete_package_download_sites(self, site_ids):
        selected = {
            str(item).strip() for item in site_ids if str(item).strip()
        } if isinstance(site_ids, (list, tuple, set)) else set()
        if not selected:
            raise ValueError("请选择要删除的下载站点")
        existing_ids = {
            str(item.get("id", "")).strip()
            for item in self.package_download_sites
        }
        matched = selected & existing_ids
        if not matched:
            raise ValueError("选择的下载站点已不存在")
        if len(self.package_download_sites) - len(matched) < 1:
            raise ValueError("至少保留一个下载站点；不使用时可关闭其开关")
        previous = copy.deepcopy(self.package_download_sites)
        removed = [
            dict(item)
            for item in self.package_download_sites
            if str(item.get("id", "")).strip() in matched
        ]
        self.package_download_sites = [
            item
            for item in self.package_download_sites
            if str(item.get("id", "")).strip() not in matched
        ]
        try:
            self._sync_legacy_package_download_fields()
            self._save_settings()
        except Exception:
            self.package_download_sites = previous
            self._sync_legacy_package_download_fields()
            raise
        return removed

    def _open_package_download_url_dialog(self):
        try:
            from java import dynamic_proxy, jclass

            toast_class = jclass("android.widget.Toast")
            edit_text_class = jclass("android.widget.EditText")
            linear_layout_class = jclass("android.widget.LinearLayout")
            text_view_class = jclass("android.widget.TextView")
            input_type = jclass("android.text.InputType")
            click_listener = jclass(
                "android.content.DialogInterface$OnClickListener"
            )
            runnable_class = jclass("java.lang.Runnable")
            try:
                builder_class = jclass(
                    "com.google.android.material.dialog.MaterialAlertDialogBuilder"
                )
            except Exception:
                builder_class = jclass("android.app.AlertDialog$Builder")
            activity = self._current_android_activity(jclass)
            owner = self

            class SaveListener(dynamic_proxy(click_listener)):
                def __init__(self, name_edit, url_edit):
                    super().__init__()
                    self.name_edit = name_edit
                    self.url_edit = url_edit

                def onClick(self, dialog, which):
                    try:
                        name = str(self.name_edit.getText().toString())
                        url = str(self.url_edit.getText().toString())
                        clean_name = owner._normalize_package_download_name(name)
                        clean_url = owner._normalize_package_download_url(url)
                        toast_class.makeText(
                            activity,
                            "正在检测网址和 ZIP 文件，请稍候",
                            toast_class.LENGTH_LONG,
                        ).show()

                        def verify_and_save():
                            try:
                                owner._probe_package_download_url(clean_url)
                                with owner.lock:
                                    saved, created = (
                                        owner._add_or_update_package_download_site(
                                            clean_name, clean_url, verify=False
                                        )
                                    )
                                _, reload_detail = (
                                    owner._schedule_manager_page_refresh()
                                )
                                owner._notify_app(
                                    "ZIP 检测通过，已{}下载站点：{}；{}".format(
                                        "添加" if created else "更新",
                                        saved["name"],
                                        reload_detail,
                                    )
                                )
                            except Exception as exc:
                                owner._notify_app(
                                    "下载地址保存失败: {}".format(exc)
                                )

                        worker = threading.Thread(
                            target=verify_and_save,
                            name="local-package-url-check",
                        )
                        worker.daemon = True
                        worker.start()
                    except Exception as exc:
                        toast_class.makeText(
                            activity,
                            "下载地址保存失败: {}".format(exc),
                            toast_class.LENGTH_LONG,
                        ).show()

            class CancelListener(dynamic_proxy(click_listener)):
                def onClick(self, dialog, which):
                    return None

            class ShowDialog(dynamic_proxy(runnable_class)):
                def run(self):
                    density = float(
                        activity.getResources().getDisplayMetrics().density
                    )
                    padding = int(16 * density + 0.5)
                    row_padding = int(8 * density + 0.5)
                    container = linear_layout_class(activity)
                    container.setOrientation(linear_layout_class.VERTICAL)
                    container.setPadding(padding, row_padding, padding, 0)
                    description = text_view_class(activity)
                    description.setText(
                        "输入备注名和 ZIP 下载网址；保存时会检测网址和 ZIP 文件头"
                    )
                    description.setTextSize(13.0)
                    description.setPadding(0, 0, 0, row_padding)
                    container.addView(description)
                    name_edit = edit_text_class(activity)
                    name_edit.setSingleLine(True)
                    name_edit.setHint("备注名，例如：第二线路")
                    name_edit.setInputType(input_type.TYPE_CLASS_TEXT)
                    container.addView(name_edit)
                    url_edit = edit_text_class(activity)
                    url_edit.setSingleLine(True)
                    url_edit.setInputType(
                        input_type.TYPE_CLASS_TEXT
                        | input_type.TYPE_TEXT_VARIATION_URI
                    )
                    url_edit.setHint("https://example.com/package.zip")
                    container.addView(url_edit)
                    save_listener = SaveListener(name_edit, url_edit)
                    cancel_listener = CancelListener()
                    builder = builder_class(activity)
                    builder.setTitle("添加本地包网址")
                    builder.setView(container)
                    builder.setPositiveButton("添加/更新", save_listener)
                    builder.setNegativeButton("取消", cancel_listener)
                    dialog = builder.show()
                    name_edit.requestFocus()
                    owner._dialog_refs.extend(
                        [
                            container,
                            description,
                            name_edit,
                            url_edit,
                            save_listener,
                            cancel_listener,
                            dialog,
                        ]
                    )
                    owner._dialog_refs = owner._dialog_refs[-12:]

            runner = ShowDialog()
            self._dialog_refs.append(runner)
            self._dialog_refs = self._dialog_refs[-12:]
            activity.runOnUiThread(runner)
            return True, ""
        except Exception as exc:
            return False, "下载地址输入框打开失败: {}".format(exc)

    def _open_package_download_switches_dialog(self):
        try:
            from java import dynamic_proxy, jclass

            toast_class = jclass("android.widget.Toast")
            linear_layout_class = jclass("android.widget.LinearLayout")
            text_view_class = jclass("android.widget.TextView")
            switch_class = jclass("android.widget.Switch")
            click_listener = jclass(
                "android.content.DialogInterface$OnClickListener"
            )
            view_click_listener = jclass("android.view.View$OnClickListener")
            runnable_class = jclass("java.lang.Runnable")
            try:
                builder_class = jclass(
                    "com.google.android.material.dialog.MaterialAlertDialogBuilder"
                )
            except Exception:
                builder_class = jclass("android.app.AlertDialog$Builder")
            activity = self._current_android_activity(jclass)
            owner = self

            class NoopListener(dynamic_proxy(click_listener)):
                def onClick(self, dialog, which):
                    return None

            class SaveButtonListener(dynamic_proxy(view_click_listener)):
                def __init__(self, switches, dialog):
                    super().__init__()
                    self.switches = switches
                    self.dialog = dialog

                def onClick(self, view):
                    values = {
                        site_id: bool(control.isChecked())
                        for site_id, control in self.switches.items()
                    }
                    try:
                        with owner.lock:
                            changed = owner._set_package_download_site_states(values)
                        reload_detail = "无需刷新"
                        if changed:
                            _, reload_detail = (
                                owner._schedule_manager_page_refresh()
                            )
                        toast_class.makeText(
                            activity,
                            "下载站点开关已保存；{}".format(reload_detail)
                            if changed
                            else "下载站点开关未变更",
                            toast_class.LENGTH_LONG,
                        ).show()
                        self.dialog.dismiss()
                    except Exception as exc:
                        toast_class.makeText(
                            activity,
                            "下载站点开关保存失败: {}".format(exc),
                            toast_class.LENGTH_LONG,
                        ).show()

            class ShowDialog(dynamic_proxy(runnable_class)):
                def run(self):
                    density = float(
                        activity.getResources().getDisplayMetrics().density
                    )
                    padding = int(16 * density + 0.5)
                    row_padding = int(8 * density + 0.5)
                    container = linear_layout_class(activity)
                    container.setOrientation(linear_layout_class.VERTICAL)
                    container.setPadding(padding, row_padding, padding, 0)
                    description = text_view_class(activity)
                    description.setText("选择要在推荐页显示的一键下载站点")
                    description.setTextSize(13.0)
                    description.setPadding(0, 0, 0, row_padding)
                    container.addView(description)
                    switches = {}
                    for site in owner.package_download_sites:
                        control = switch_class(activity)
                        control.setText(str(site.get("name", "未命名")))
                        control.setTextSize(16.0)
                        control.setChecked(bool(site.get("enabled", True)))
                        control.setPadding(0, row_padding, 0, row_padding)
                        control.setFocusable(True)
                        container.addView(control)
                        switches[str(site.get("id", ""))] = control
                    noop_listener = NoopListener()
                    builder = builder_class(activity)
                    builder.setTitle("下载站点开关")
                    builder.setView(container)
                    builder.setPositiveButton("保存", noop_listener)
                    builder.setNegativeButton("取消", noop_listener)
                    dialog = builder.show()
                    save_listener = SaveButtonListener(switches, dialog)
                    dialog.getButton(-1).setOnClickListener(save_listener)
                    owner._dialog_refs.append(
                        [
                            container,
                            description,
                            switches,
                            noop_listener,
                            save_listener,
                            dialog,
                        ]
                    )
                    owner._dialog_refs = owner._dialog_refs[-12:]

            runner = ShowDialog()
            self._dialog_refs.append(runner)
            self._dialog_refs = self._dialog_refs[-12:]
            activity.runOnUiThread(runner)
            return True, ""
        except Exception as exc:
            return False, "下载站点开关打开失败: {}".format(exc)

    def _open_package_download_delete_dialog(self):
        try:
            from java import dynamic_proxy, jclass

            toast_class = jclass("android.widget.Toast")
            linear_layout_class = jclass("android.widget.LinearLayout")
            text_view_class = jclass("android.widget.TextView")
            switch_class = jclass("android.widget.Switch")
            click_listener = jclass(
                "android.content.DialogInterface$OnClickListener"
            )
            view_click_listener = jclass("android.view.View$OnClickListener")
            runnable_class = jclass("java.lang.Runnable")
            try:
                builder_class = jclass(
                    "com.google.android.material.dialog.MaterialAlertDialogBuilder"
                )
            except Exception:
                builder_class = jclass("android.app.AlertDialog$Builder")
            activity = self._current_android_activity(jclass)
            owner = self

            class NoopListener(dynamic_proxy(click_listener)):
                def onClick(self, dialog, which):
                    return None

            class DeleteButtonListener(dynamic_proxy(view_click_listener)):
                def __init__(self, switches, dialog):
                    super().__init__()
                    self.switches = switches
                    self.dialog = dialog

                def onClick(self, view):
                    selected = [
                        site_id
                        for site_id, control in self.switches.items()
                        if bool(control.isChecked())
                    ]
                    try:
                        with owner.lock:
                            removed = owner._delete_package_download_sites(selected)
                        _, refresh_detail = owner._schedule_manager_page_refresh()
                        names = "、".join(
                            str(item.get("name", "未命名")) for item in removed
                        )
                        toast_class.makeText(
                            activity,
                            "已删除在线网址：{}；本地包目录已保留；{}".format(
                                names, refresh_detail
                            ),
                            toast_class.LENGTH_LONG,
                        ).show()
                        self.dialog.dismiss()
                    except Exception as exc:
                        toast_class.makeText(
                            activity,
                            "下载站点删除失败: {}".format(exc),
                            toast_class.LENGTH_LONG,
                        ).show()

            class ShowDialog(dynamic_proxy(runnable_class)):
                def run(self):
                    density = float(
                        activity.getResources().getDisplayMetrics().density
                    )
                    padding = int(16 * density + 0.5)
                    row_padding = int(8 * density + 0.5)
                    container = linear_layout_class(activity)
                    container.setOrientation(linear_layout_class.VERTICAL)
                    container.setPadding(padding, row_padding, padding, 0)
                    description = text_view_class(activity)
                    description.setText(
                        "选择要删除的在线网址；只删除下载设置，不删除已解压本地包"
                    )
                    description.setTextSize(13.0)
                    description.setPadding(0, 0, 0, row_padding)
                    container.addView(description)
                    switches = {}
                    for site in owner.package_download_sites:
                        control = switch_class(activity)
                        control.setText(
                            "{} · {}".format(
                                site.get("name", "未命名"), site.get("url", "")
                            )
                        )
                        control.setTextSize(15.0)
                        control.setChecked(False)
                        control.setPadding(0, row_padding, 0, row_padding)
                        control.setFocusable(True)
                        container.addView(control)
                        switches[str(site.get("id", ""))] = control
                    noop_listener = NoopListener()
                    builder = builder_class(activity)
                    builder.setTitle("删除下载站点")
                    builder.setView(container)
                    builder.setPositiveButton("删除", noop_listener)
                    builder.setNegativeButton("取消", noop_listener)
                    dialog = builder.show()
                    delete_listener = DeleteButtonListener(switches, dialog)
                    dialog.getButton(-1).setOnClickListener(delete_listener)
                    owner._dialog_refs.append(
                        [
                            container,
                            description,
                            switches,
                            noop_listener,
                            delete_listener,
                            dialog,
                        ]
                    )
                    owner._dialog_refs = owner._dialog_refs[-12:]

            runner = ShowDialog()
            self._dialog_refs.append(runner)
            self._dialog_refs = self._dialog_refs[-12:]
            activity.runOnUiThread(runner)
            return True, ""
        except Exception as exc:
            return False, "下载站点删除界面打开失败: {}".format(exc)

    def _open_scan_types_dialog(self):
        try:
            from java import dynamic_proxy, jclass

            toast_class = jclass("android.widget.Toast")
            linear_layout_class = jclass("android.widget.LinearLayout")
            text_view_class = jclass("android.widget.TextView")
            switch_class = jclass("android.widget.Switch")
            click_listener = jclass(
                "android.content.DialogInterface$OnClickListener"
            )
            view_click_listener = jclass("android.view.View$OnClickListener")
            runnable_class = jclass("java.lang.Runnable")
            try:
                builder_class = jclass(
                    "com.google.android.material.dialog.MaterialAlertDialogBuilder"
                )
            except Exception:
                builder_class = jclass("android.app.AlertDialog$Builder")
            activity = self._current_android_activity(jclass)
            owner = self

            class NoopListener(dynamic_proxy(click_listener)):
                def onClick(self, dialog, which):
                    return None

            class SaveButtonListener(dynamic_proxy(view_click_listener)):
                def __init__(self, switches, adult_switch, dialog):
                    super().__init__()
                    self.switches = switches
                    self.adult_switch = adult_switch
                    self.dialog = dialog

                def onClick(self, view):
                    values = {
                        source_type: bool(control.isChecked())
                        for source_type, control in self.switches.items()
                    }
                    try:
                        with owner.lock:
                            dirty = owner._set_pending_type_settings(
                                values,
                                block_adult_sites=bool(
                                    self.adult_switch.isChecked()
                                ),
                            )
                        message = (
                            "扫描类型已保存，请点击应用并加载"
                            if dirty
                            else "扫描类型设置未变更"
                        )
                        toast_class.makeText(
                            activity, message, toast_class.LENGTH_LONG
                        ).show()
                        self.dialog.dismiss()
                    except Exception as exc:
                        toast_class.makeText(
                            activity,
                            "扫描类型保存失败: {}".format(exc),
                            toast_class.LENGTH_LONG,
                        ).show()

            class ShowDialog(dynamic_proxy(runnable_class)):
                def run(self):
                    try:
                        self._run_dialog()
                    except Exception as exc:
                        message = "扫描类型开关打开失败: {}".format(exc)
                        owner._log("ERROR", message)
                        try:
                            toast_class.makeText(
                                activity, message, toast_class.LENGTH_LONG
                            ).show()
                        except Exception:
                            owner._notify_app(message)

                def _run_dialog(self):
                    density = float(
                        activity.getResources().getDisplayMetrics().density
                    )
                    padding = int(16 * density + 0.5)
                    row_padding = int(8 * density + 0.5)
                    container = linear_layout_class(activity)
                    container.setOrientation(linear_layout_class.VERTICAL)
                    container.setPadding(padding, row_padding, padding, 0)
                    description = text_view_class(activity)
                    description.setText(
                        "选择一键扫描时要读取的站点类型"
                    )
                    description.setTextSize(13.0)
                    description.setPadding(0, 0, 0, row_padding)
                    container.addView(description)
                    switches = {}
                    for source_type in owner.TYPE_ORDER:
                        control = switch_class(activity)
                        control.setText(
                            "{} 扫描".format(
                                owner.TYPE_LABEL.get(source_type, source_type)
                            )
                        )
                        control.setTextSize(16.0)
                        control.setChecked(
                            bool(
                                owner.pending_type_enabled.get(
                                    source_type,
                                    owner.type_enabled.get(source_type, True),
                                )
                            )
                        )
                        control.setPadding(0, row_padding, 0, row_padding)
                        control.setFocusable(True)
                        container.addView(control)
                        switches[source_type] = control
                    adult_switch = switch_class(activity)
                    adult_switch.setText("屏蔽18+站点")
                    adult_switch.setTextSize(16.0)
                    adult_switch.setChecked(
                        bool(owner.pending_block_adult_sites)
                    )
                    adult_switch.setPadding(0, row_padding, 0, row_padding)
                    adult_switch.setFocusable(True)
                    container.addView(adult_switch)
                    noop_listener = NoopListener()
                    builder = builder_class(activity)
                    builder.setTitle("扫描类型开关")
                    builder.setView(container)
                    builder.setPositiveButton("保存", noop_listener)
                    builder.setNegativeButton("取消", noop_listener)
                    dialog = builder.show()
                    save_listener = SaveButtonListener(
                        switches, adult_switch, dialog
                    )
                    dialog.getButton(-1).setOnClickListener(save_listener)
                    owner._dialog_refs.append(
                        [
                            container,
                            description,
                            switches,
                            adult_switch,
                            noop_listener,
                            save_listener,
                            dialog,
                        ]
                    )
                    owner._dialog_refs = owner._dialog_refs[-12:]

            runner = ShowDialog()
            self._dialog_refs.append(runner)
            self._dialog_refs = self._dialog_refs[-12:]
            activity.runOnUiThread(runner)
            return True, ""
        except Exception as exc:
            return False, "扫描类型开关打开失败: {}".format(exc)

    def _apply_pending_type_settings(self):
        previous_types = dict(self.type_enabled)
        previous_pending = dict(self.pending_type_enabled)
        previous_block_adult = self.block_adult_sites
        previous_pending_block_adult = self.pending_block_adult_sites
        previous_dirty = self.config_dirty
        try:
            self.type_enabled = {
                source_type: bool(
                    self.pending_type_enabled.get(
                        source_type, self.type_enabled.get(source_type, True)
                    )
                )
                for source_type in self.TYPE_ORDER
            }
            self.pending_type_enabled = dict(self.type_enabled)
            self.block_adult_sites = bool(self.pending_block_adult_sites)
            self.pending_block_adult_sites = self.block_adult_sites
            self.config_dirty = False
            self._sync_ignored_sources()
            self._save_settings()
        except Exception:
            self.type_enabled = previous_types
            self.pending_type_enabled = previous_pending
            self.block_adult_sites = previous_block_adult
            self.pending_block_adult_sites = previous_pending_block_adult
            self.config_dirty = previous_dirty
            self._sync_ignored_sources()
            raise

    def _load_scan_cache_payload(self, warn=True):
        path = os.path.abspath(os.path.expanduser(self.cache_path))
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if (
                not isinstance(data, dict)
                or data.get("version") != self.CACHE_VERSION
                or str(data.get("app_mode", "")) != self.app_mode
            ):
                return {}
            return data
        except Exception as exc:
            if warn:
                self._warn(
                    "增量扫描缓存读取失败，将全量扫描: {}".format(
                        exc
                    )
                )
            return {}

    def _load_scan_cache(self):
        data = self._load_scan_cache_payload()
        files = data.get("files", {}) if isinstance(data, dict) else {}
        return files if isinstance(files, dict) else {}

    def _save_scan_cache(self, files):
        path = os.path.abspath(os.path.expanduser(self.cache_path))
        previous = self._load_scan_cache_payload(warn=False)
        data = {
            "version": self.CACHE_VERSION,
            "app_mode": self.app_mode,
            "files": files,
        }
        if isinstance(previous.get("snapshot"), dict):
            data["snapshot"] = previous["snapshot"]
        self._atomic_write_plain_json(path, data)

    def _scan_snapshot_sources(self):
        fields = (
            "id",
            "identity",
            "key",
            "type",
            "path",
            "scan_root",
            "root_order",
            "relative_in_root",
            "base_name",
            "package_label",
            "name",
            "validation",
            "ignored",
            "size",
            "mtime_ns",
            "csp_site",
            "dependencies",
            "test_result",
            "site",
        )
        result = []
        for source in self.cache["sources"] + self.cache["ignored"]:
            result.append(
                {
                    field: copy.deepcopy(source[field])
                    for field in fields
                    if field in source
                }
            )
        return result

    def _save_scan_snapshot(self):
        path = os.path.abspath(os.path.expanduser(self.cache_path))
        data = self._load_scan_cache_payload(warn=False)
        files = data.get("files", {}) if isinstance(data, dict) else {}
        if not isinstance(files, dict):
            files = {}
        status_fields = (
            "scan_time",
            "found",
            "included",
            "skipped",
            "duplicates",
            "cache_hits",
            "cache_misses",
            "ignored",
            "adult_filtered",
            "compatibility_blocked",
            "stale_ignored_removed",
            "manual_sites",
            "generated_sites",
            "added_sites",
            "updated_sites",
            "removed_sites",
            "unchanged_sites",
        )
        data = {
            "version": self.CACHE_VERSION,
            "app_mode": self.app_mode,
            "files": files,
            "snapshot": {
                "registry_token": self._registry_token(self.output_path),
                "sources": self._scan_snapshot_sources(),
                "status": {
                    field: copy.deepcopy(self.status.get(field))
                    for field in status_fields
                },
            },
        }
        self._atomic_write_plain_json(path, data)

    def _restore_scan_snapshot(self):
        data = self._load_scan_cache_payload(warn=False)
        snapshot = data.get("snapshot", {}) if isinstance(data, dict) else {}
        if not isinstance(snapshot, dict):
            return False
        expected_token = str(snapshot.get("registry_token", ""))
        if not expected_token or expected_token != self._registry_token(
            self.output_path
        ):
            return False
        raw_sources = snapshot.get("sources", [])
        if not isinstance(raw_sources, list):
            return False

        restored = self._empty_cache()
        seen_ids = set()
        for raw in raw_sources:
            if not isinstance(raw, dict):
                continue
            source = copy.deepcopy(raw)
            source_id = str(source.get("id", "")).strip()
            identity = str(source.get("identity", "")).strip()
            source_type = str(source.get("type", "")).upper()
            if (
                not source_id
                or source_id in seen_ids
                or not identity
                or source_type not in self.TYPE_ORDER
                or not isinstance(source.get("site"), dict)
            ):
                continue
            source["type"] = source_type
            source["ignored"] = identity in self.ignored_sources
            source["adult_blocked"] = (
                self.block_adult_sites and identity in self.adult_blocked_sources
            )
            test_result = self.site_test_results.get(identity, {})
            if not isinstance(test_result, dict) or test_result.get(
                "source_signature"
            ) != self._source_signature(source):
                test_result = {}
            source["test_result"] = test_result
            seen_ids.add(source_id)
            restored["source_index"][source_id] = source
            if source["ignored"]:
                restored["ignored"].append(source)
                counts = restored["ignored_counts"]
            else:
                restored["sources"].append(source)
                counts = restored["type_counts"]
            counts[source_type] = counts.get(source_type, 0) + 1
        if not restored["sources"] and not restored["ignored"]:
            return False

        current_manual = self.status["manual_sites"]
        current_generated = self.status["generated_sites"]
        saved_status = snapshot.get("status", {})
        self.cache = restored
        if isinstance(saved_status, dict):
            for field in self._empty_status():
                if field in saved_status:
                    self.status[field] = copy.deepcopy(saved_status[field])
        self.status["included"] = len(restored["sources"])
        self.status["ignored"] = len(restored["ignored"])
        self.status["manual_sites"] = current_manual
        self.status["generated_sites"] = current_generated
        self.status["written"] = True
        self.status["registry_changed"] = False
        self.status["write_state"] = "已恢复上次成功扫描结果"
        self.status["error"] = ""
        return True

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

    # --------------------------------------------------------------------------
    # OK影视兼容：标准配置合并与 A/B 热重载
    # --------------------------------------------------------------------------
    def _ok_config_paths(self):
        return (
            os.path.realpath(os.path.abspath(os.path.expanduser(self.ok_config_a))),
            os.path.realpath(os.path.abspath(os.path.expanduser(self.ok_config_b))),
        )

    def _is_ok_generated_config_url(self, value):
        url = str(value or "").strip()
        if not url:
            return False
        path = self._reference_path(url)
        if path:
            return path in set(self._ok_config_paths())
        clean = url.split("?", 1)[0].rstrip("/")
        return any(clean.endswith("/" + os.path.basename(path)) for path in self._ok_config_paths())

    def _ok_current_config_url(self):
        try:
            from java import jclass

            return str(
                jclass("com.fongmi.android.tv.bean.Config").vod().getUrl() or ""
            ).strip()
        except Exception as exc:
            raise ValueError("读取 OK影视当前点播接口失败: {}".format(exc))

    def _ok_fetch_config_text(self, value):
        path = self._reference_path(value)
        if path and os.path.isfile(path):
            with open(path, "r", encoding="utf-8-sig") as fp:
                return fp.read()
        lower = value.lower()
        if lower.startswith("assets://"):
            try:
                from java import jclass

                port = int(jclass("com.github.catvod.Proxy").getPort())
                value = "http://127.0.0.1:{}/{}".format(
                    port, value[9:].lstrip("/")
                )
            except Exception as exc:
                raise ValueError("无法读取 assets 配置: {}".format(exc))
        if not value.lower().startswith(("http://", "https://")):
            raise ValueError("不支持的基础配置地址: {}".format(value))
        request = urllib.request.Request(
            value,
            headers={"User-Agent": "okhttp/4.12.0", "Accept": "application/json"},
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=10) as response:
            return response.read().decode("utf-8-sig")

    def _ok_decoder_base64(self, text):
        match = re.search(r"[A-Za-z0-9]{8}\*\*", text)
        if not match:
            return text
        payload = text[match.end() :]
        return base64.b64decode(payload).decode("utf-8")

    def _ok_decoder_cbc(self, text):
        try:
            decoded = bytes.fromhex(text).decode("utf-8", errors="replace").lower()
            key_start = decoded.index("$#") + 2
            key_end = decoded.index("#$", key_start)
            key = (decoded[key_start:key_end] + "0" * 16)[:16].encode("utf-8")
            iv = (decoded[-13:] + "0" * 16)[:16].encode("utf-8")
            start = text.index("2324") + 4
            encrypted = bytes.fromhex(text[start:-26])
            from Crypto.Cipher import AES

            plain = AES.new(key, AES.MODE_CBC, iv).decrypt(encrypted)
            padding = plain[-1]
            if padding < 1 or padding > 16 or plain[-padding:] != bytes([padding]) * padding:
                raise ValueError("AES 填充无效")
            return plain[:-padding].decode("utf-8")
        except Exception as exc:
            raise ValueError("2423 配置解密失败: {}".format(exc))

    def _ok_fix_relative_urls(self, base_url, text):
        protected = {}

        def protect(match):
            token = "__LOCAL_AUTO_JS_{}__".format(len(protected))
            protected[token] = urllib.parse.urljoin(base_url, match.group(1))
            return '"{}"'.format(token)

        pattern = re.compile(r'"((?:\.\.?/)[^"?]+\.js\?[^" ]*)"')
        value = pattern.sub(protect, text)
        parent = urllib.parse.urljoin(base_url, "../")
        current = urllib.parse.urljoin(base_url, "./")
        value = value.replace("../", parent).replace("./", current)
        for token, resolved in protected.items():
            value = value.replace(token, resolved)
        return value

    def _ok_decode_config(self, url, depth=0):
        value = str(url or "").strip()
        if not value:
            raise ValueError("基础配置地址为空")
        if depth > 3:
            raise ValueError("多仓配置嵌套过深")
        text = self._ok_fetch_config_text(value).strip()
        if "**" in text:
            text = self._ok_decoder_base64(text)
        if text.startswith("2423"):
            text = self._ok_decoder_cbc(re.sub(r"\s+", "", text))
        text = self._ok_fix_relative_urls(value, text)
        try:
            data = json.loads(text.lstrip("\ufeff"))
        except Exception as exc:
            raise ValueError("基础配置不是有效 JSON: {}".format(exc))
        if not isinstance(data, dict):
            raise ValueError("基础配置顶层必须是 JSON 对象")
        urls = data.get("urls")
        if isinstance(urls, list) and urls:
            first = urls[0]
            child_url = first.get("url", "") if isinstance(first, dict) else first
            return self._ok_decode_config(child_url, depth + 1)
        return data

    def _ok_clean_base_config(self, config):
        data = copy.deepcopy(config) if isinstance(config, dict) else {}
        data.pop(self.OK_CONFIG_MARKER, None)
        sites = data.get("sites", [])
        if isinstance(sites, dict):
            sites = [sites]
        elif not isinstance(sites, list):
            sites = [sites] if isinstance(sites, str) and sites.strip() else []
        clean_sites = []
        for site in sites:
            if isinstance(site, dict):
                key = str(site.get("key", "")).strip()
                if key.startswith(self.GENERATED_KEY_PREFIX):
                    continue
            clean_sites.append(site)
        data["sites"] = clean_sites
        return data

    def _ok_read_base_cache(self):
        path = os.path.abspath(os.path.expanduser(self.ok_base_cache_path))
        if not os.path.isfile(path):
            return {}
        try:
            cached = self._read_config_file(path, "OK影视基础配置缓存")
            config = cached.get("config", cached)
            return self._ok_clean_base_config(config)
        except Exception as exc:
            self._warn("OK影视基础配置缓存读取失败: {}".format(exc))
            return {}

    def _ok_save_base_cache(self, config):
        payload = {
            "baseUrl": self.ok_base_config_url,
            "savedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
            "config": self._ok_clean_base_config(config),
        }
        self._atomic_write_plain_json(self.ok_base_cache_path, payload)

    def _ok_base_config(self):
        current_url = self._ok_current_config_url()
        current_generated = self._is_ok_generated_config_url(current_url)

        if current_url and not current_generated:
            config = self._ok_clean_base_config(self._ok_decode_config(current_url))
            self.ok_base_config_url = current_url
            self._ok_save_base_cache(config)
            self._save_settings()
            return config

        if self.ok_base_config_url and not self._is_ok_generated_config_url(
            self.ok_base_config_url
        ):
            try:
                config = self._ok_clean_base_config(
                    self._ok_decode_config(self.ok_base_config_url)
                )
                self._ok_save_base_cache(config)
                return config
            except Exception as exc:
                self._warn("OK影视基础配置刷新失败，使用本地缓存: {}".format(exc))

        cached = self._ok_read_base_cache()
        if cached:
            return cached
        if current_url:
            return self._ok_clean_base_config(self._ok_decode_config(current_url))
        raise ValueError("未找到 OK影视当前配置或基础配置缓存")

    def _ok_registry_sites(self, registry):
        sites = []
        skipped_html = 0
        for item in registry.get("items", []):
            if not isinstance(item, dict) or not bool(item.get("enabled", True)):
                continue
            site = self._registry_item_site(item)
            if not isinstance(site, dict):
                continue
            kind = str(item.get("kind", "")).strip().lower()
            source_type = self._generated_item_type(item)
            if source_type == "HTML" or kind == "webhome" or site.get("homePage"):
                skipped_html += 1
                continue
            if not str(site.get("key", "")).strip():
                continue
            sites.append(copy.deepcopy(site))
        if skipped_html:
            self._warn("OK影视原版不支持 WebHome，已跳过 {} 个 HTML 站点".format(skipped_html))
        return sites

    def _ok_build_config(self, registry):
        config = self._ok_base_config()
        local_sites = self._ok_registry_sites(registry)
        local_keys = {
            str(site.get("key", "")).strip()
            for site in local_sites
            if isinstance(site, dict)
        }
        base_sites = config.get("sites", [])
        if isinstance(base_sites, dict):
            base_sites = [base_sites]
        elif not isinstance(base_sites, list):
            base_sites = [base_sites] if isinstance(base_sites, str) and base_sites.strip() else []
        base_sites = [
            site
            for site in base_sites
            if not isinstance(site, dict)
            or str(site.get("key", "")).strip() not in local_keys
        ]
        config["sites"] = local_sites + base_sites
        home_key = str(registry.get("homeKey", "")).strip()
        if home_key and home_key in local_keys:
            config["home"] = home_key
        config[self.OK_CONFIG_MARKER] = {
            "version": self.OK_CONFIG_VERSION,
            "loader": self.VERSION,
            "baseUrl": self.ok_base_config_url,
            "generatedSites": len(local_sites),
        }
        return config

    def _ok_write_generated_configs(self, registry):
        config = self._ok_build_config(registry)
        for path in self._ok_config_paths():
            self._atomic_write_plain_json(path, config)
        self.status["write_state"] = "已生成 OK影视本地配置"
        self.status["written"] = True
        return config

    def _ok_next_config_target(self):
        current_url = self._ok_current_config_url()
        path_a, path_b = self._ok_config_paths()
        current_path = self._reference_path(current_url)
        target_path = path_b if current_path == path_a else path_a
        return self._file_url(target_path)

    def _perform_ok_vod_reload(self):
        try:
            from java import jclass

            port = int(jclass("com.github.catvod.Proxy").getPort())
            if port < 1:
                raise ValueError("OK影视本机服务尚未启动")
            target = self._ok_next_config_target()
            config = json.dumps(
                {"type": 0, "url": target, "name": "本地自动加载"},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            body = urllib.parse.urlencode(
                {"config": config, "targets": "[]", "force": "false"}
            ).encode("utf-8")
            request = urllib.request.Request(
                "http://127.0.0.1:{}/action?do=sync&mode=1&type=history".format(port),
                data=body,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                    "Connection": "close",
                },
            )
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=2.5) as response:
                if int(getattr(response, "status", response.getcode())) != 200:
                    raise ValueError("HTTP {}".format(response.getcode()))
            self.ok_last_target = target
            self._save_settings()
            return True, "OK影视本地站点已主动重载"
        except Exception as exc:
            self._warn("OK影视主动重载失败: {}".format(exc))
            return False, "OK影视配置已生成；主动重载失败，重启 App 后生效"

    def _reload_app_vod_config(self, expected_keys=None):
        if not self.auto_reload_app:
            return False, "配置已写入；App 自动重载已关闭"
        expected = set(expected_keys) if expected_keys is not None else None
        with self.lock:
            self._reload_generation += 1
            generation = self._reload_generation
            worker = threading.Thread(
                target=self._delayed_app_vod_reload,
                args=(generation, expected),
                name="local-source-reload",
            )
            worker.daemon = True
            worker.start()
        self._log(
            "INFO",
            "已安排 App 主动重载: delay={}s sites={}".format(
                self.APP_RELOAD_DELAY,
                len(expected) if expected is not None else "-",
            ),
        )
        return True, "已安排主动重载 {} 站点列表".format(self._app_mode_label())

    def _current_proxy_port(self):
        try:
            from java import jclass

            port = int(jclass("com.github.catvod.Proxy").getPort())
            return port if port > 0 else 0
        except Exception:
            return 0

    def _app_port_candidates(self):
        ports = []
        current_port = self._current_proxy_port()
        if current_port:
            ports.append(current_port)
        if self.last_app_port and self.last_app_port not in ports:
            ports.append(self.last_app_port)
        ports.extend(port for port in self.app_server_ports if port not in ports)
        return ports

    def _schedule_manager_page_refresh(self, delay=0.2):
        with self.lock:
            self._page_refresh_generation += 1
            generation = self._page_refresh_generation
        worker = threading.Thread(
            target=self._delayed_manager_page_refresh,
            args=(generation, max(0.05, float(delay))),
            name="local-source-page-refresh",
        )
        worker.daemon = True
        worker.start()
        return True, "已安排首页和分类页轻量刷新"

    def _delayed_manager_page_refresh(self, generation, delay):
        time.sleep(delay)
        try:
            with self.lock:
                if generation != self._page_refresh_generation:
                    return
            ok, detail = self._perform_manager_page_refresh()
            self._log("INFO" if ok else "WARN", detail)
            self._notify_app(detail)
        except Exception as exc:
            detail = "页面轻量刷新失败: {}".format(exc)
            self._log("ERROR", detail)
            self._notify_app(detail)

    def _perform_manager_page_refresh(self):
        last_error = "未发现当前 App 本机服务"
        for port in self._app_port_candidates():
            base = "http://127.0.0.1:{}".format(port)
            try:
                for refresh_type in ("home", "category"):
                    query = urllib.parse.urlencode(
                        {"do": "refresh", "type": refresh_type}
                    )
                    self._request_status(
                        base + "/action?" + query,
                        max(1.2, self.APP_REQUEST_TIMEOUT * 3),
                    )
                    time.sleep(0.08)
                self._remember_app_port(port)
                return True, "首页和分类页已轻量刷新"
            except Exception as exc:
                last_error = str(exc)
        return False, "页面轻量刷新失败: {}".format(last_error)

    def _delayed_app_vod_reload(self, generation, expected_keys):
        time.sleep(max(0.1, float(self.APP_RELOAD_DELAY)))
        try:
            with self.lock:
                if generation != self._reload_generation:
                    return
            # 网络请求必须在锁外执行，避免 Android UI 线程保存设置时等待。
            ok, detail = self._perform_app_vod_reload(expected_keys)
            if ok and self.app_mode == self.APP_MODE_WEBHTV:
                time.sleep(max(0.2, float(self.APP_PAGE_REFRESH_DELAY)))
                page_ok, page_detail = self._perform_manager_page_refresh()
                detail = "{}；{}".format(detail, page_detail)
                if not page_ok:
                    ok = False
            self._log("INFO" if ok else "WARN", detail)
            self._notify_app(detail)
        except Exception as exc:
            detail = "App 主动重载失败: {}".format(exc)
            self._log("ERROR", detail)
            self._notify_app(detail)

    def _perform_app_vod_reload(self, expected_keys=None):
        if self.app_mode == self.APP_MODE_OKTV:
            return self._perform_ok_vod_reload()
        last_error = "未发现 WebHTV 本机服务"
        ports = []
        if self.last_app_port:
            ports.append(self.last_app_port)
        ports.extend(port for port in self.app_server_ports if port not in ports)
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
                # 只重载当前点播配置，不再向 /manage/csp 回写
                # registry。/manage/csp 会用 Java 格式重写同一文件，
                # 使扫描快照 token 变化，新 Spider 会误判为无快照并
                # 再次自动补扫，形成“重载 -> 补扫 -> 重载”循环。
                query = urllib.parse.urlencode(
                    {"type": 0, "url": str(current["url"]).strip()}
                )
                self._request_json(
                    base + "/manage/config/use?" + query,
                    max(1.5, self.APP_REQUEST_TIMEOUT * 4),
                )
                self._remember_app_port(port)
                return True, "WebHTV 站点列表已主动重载，已触发页面刷新"
            except Exception as exc:
                last_error = str(exc)
        if last_error:
            self._warn("WebHTV 本机管理接口未确认: {}".format(last_error))
        return False, "App 主动重载失败，注册表已写入；重启 App 后生效"

    def _remember_app_port(self, port):
        with self.lock:
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
        headers = {"Accept": "application/json", "Connection": "close"}
        request = urllib.request.Request(
            url,
            headers=headers,
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

    def _request_status(self, url, timeout):
        request = urllib.request.Request(
            url,
            headers={"Accept": "*/*", "Connection": "close"},
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=timeout) as response:
            status = int(getattr(response, "status", response.getcode()))
            response.read(1024)
        if status < 200 or status >= 300:
            raise ValueError("HTTP {}".format(status))
        return status

    def _notify_app(self, message, wait=False, replace=False):
        text = " ".join(str(message or "").split()).strip()
        if not text or self._destroyed:
            return False
        try:
            from java import dynamic_proxy, jclass

            toast_class = jclass("android.widget.Toast")
            runnable_class = jclass("java.lang.Runnable")
            handler_class = jclass("android.os.Handler")
            looper_class = jclass("android.os.Looper")
            activity, context = self._android_ui_context(jclass)
            if context is None:
                return False
            handler = handler_class(looper_class.getMainLooper())
            owner = self
            displayed = threading.Event()

            class ShowNotification(dynamic_proxy(runnable_class)):
                def run(self):
                    try:
                        try:
                            toast = (
                                owner._site_test_toast
                                if replace
                                else None
                            )
                            if toast is None:
                                toast = toast_class.makeText(
                                    context,
                                    text[:120],
                                    toast_class.LENGTH_LONG,
                                )
                                if replace:
                                    owner._site_test_toast = toast
                            else:
                                toast.setText(text[:120])
                            toast.show()
                        except Exception as exc:
                            owner._log(
                                "WARN", "站点通知显示失败: {}".format(exc)
                            )
                    finally:
                        try:
                            owner._notification_refs.remove(self)
                        except (ValueError, AttributeError):
                            pass
                        displayed.set()

            runner = ShowNotification()
            self._notification_refs.append(runner)
            try:
                if activity is not None:
                    activity.runOnUiThread(runner)
                    queued = True
                else:
                    queued = handler.post(runner)
            except Exception:
                self._notification_refs.remove(runner)
                raise
            # 部分 Chaquopy 版本会把 Java void/boolean 返回值映射为 None。
            # None 表示调用已发出；只有明确的 false 才视为入队失败。
            if queued is not None and not bool(queued):
                self._notification_refs.remove(runner)
                return False
            if wait and not displayed.wait(1.5):
                self._log("WARN", "站点通知等待 UI 显示超时: {}".format(text))
                return False
            return True
        except Exception as exc:
            try:
                self._log("WARN", "站点通知调度失败: {}".format(exc))
            except Exception:
                pass
            return False

    def _show_author_scan_surprise(self):
        if not self.cache["sources"]:
            return False
        first_scan = not self._author_scan_surprise_shown
        added_sites = max(0, int(self.status.get("added_sites", 0) or 0))
        if first_scan:
            message = "风过江面，晚枫已点亮 {} 个站点。".format(
                len(self.cache["sources"])
            )
        elif added_sites:
            message = "风过江面，晚枫又点亮 {} 个新站点。".format(
                added_sites
            )
        else:
            return False
        if not self._notify_app(message):
            return False
        if first_scan:
            self._author_scan_surprise_shown = True
            try:
                self._save_settings()
            except Exception as exc:
                self._warn("作者彩蛋状态保存失败: {}".format(exc))
        self._log(
            "INFO",
            "{}扫描彩蛋已显示: {}".format(
                "首次手动" if first_scan else "新增站点", message
            ),
        )
        return True

    def _test_sites_locked(self, force=False):
        active_sources = list(self.cache["sources"])
        ignored_sources = list(self.cache["ignored"])
        all_sources = ignored_sources + active_sources
        source_by_identity = {
            source["identity"]: source for source in all_sources
        }
        if not all_sources:
            return {
                "tested": 0,
                "cached": 0,
                "available": 0,
                "unavailable": 0,
                "limited": 0,
                "blocked": 0,
                "restored": 0,
                "remaining": 0,
                "retest": False,
            }
        previous_ignored = set(self.ignored_sources)
        previous_manual_ignored = set(self.manual_ignored_sources)
        previous_auto_blocked = set(self.auto_blocked_sources)
        previous_results = dict(self.site_test_results)
        previous_cache = copy.deepcopy(self.cache)
        previous_status = self.status
        previous_retest_pending = list(self._retest_pending)
        previous_retest_auto_blocked = set(self._retest_auto_blocked)
        retest = bool(self._retest_pending)
        if force and not retest:
            self._retest_pending = [
                source["identity"] for source in all_sources
            ]
            self._retest_auto_blocked = set(self.auto_blocked_sources)
            for source in all_sources:
                self.site_test_results.pop(source["identity"], None)
                source["test_result"] = {}
            retest = True
        if retest:
            self._retest_pending = [
                identity
                for identity in self._retest_pending
                if identity in source_by_identity
            ]
            pending_identities = self._retest_pending[: self.MAX_SITE_TESTS]
            pending = [
                source_by_identity[identity] for identity in pending_identities
            ]
            pending_count = len(self._retest_pending)
            cached_count = max(0, len(all_sources) - pending_count)
        else:
            pending_all = [
                source
                for source in active_sources
                if not self._has_fresh_test_result(source)
            ]
            pending = pending_all[: self.MAX_SITE_TESTS]
            pending_count = len(pending_all)
            cached_count = len(active_sources) - len(pending_all)
        counts = {"available": 0, "unavailable": 0, "limited": 0}
        blocked = 0
        restored = 0
        total = len(pending)
        self._log(
            "INFO",
            "开始站点检测: 模式={} 待请求={} 缓存命中={} 总站点={}".format(
                "全部复检" if retest else "增量检测",
                total,
                cached_count,
                len(all_sources),
            ),
        )
        self._site_test_toast = None
        try:
            for idx, source in enumerate(pending, 1):
                if self._site_test_cancel.is_set():
                    raise SiteTestCancelled("站点检测已取消")
                result = self._test_source_availability(source)
                if self._site_test_cancel.is_set():
                    raise SiteTestCancelled("站点检测已取消")
                result["source_signature"] = self._source_signature(source)
                state = result["state"]
                counts[state] += 1
                self.site_test_results[source["identity"]] = result
                source["test_result"] = result
                state_label = self._test_result_label(result)
                source_name = " ".join(
                    str(source.get("name", "未命名站点")).split()
                )[:60]
                self._log(
                    "INFO",
                    "站点检测 [{}/{}] {}: {} | {} | {}".format(
                        idx,
                        total,
                        source_name or "未命名站点",
                        state_label,
                        result.get("detail", ""),
                        source.get("path", source.get("identity", "")),
                    ),
                )
                notified = self._notify_app(
                    "[{}/{}] {}：{}".format(
                        idx, total, source_name or "未命名站点", state_label
                    ),
                    wait=True,
                    replace=True,
                )
                if notified:
                    # 给系统一小段绘制时间，避免连续本地检查只呈现最后一条。
                    time.sleep(0.25)
                if (
                    state == "unavailable"
                    and source["identity"] not in self.auto_blocked_sources
                ):
                    was_ignored = source["identity"] in self.ignored_sources
                    self.auto_blocked_sources.add(source["identity"])
                    self._sync_ignored_sources()
                    if not was_ignored:
                        blocked += 1
                elif (
                    state != "unavailable"
                    and source["identity"] in self._retest_auto_blocked
                    and source["identity"] in self.auto_blocked_sources
                ):
                    self.auto_blocked_sources.discard(source["identity"])
                    self._sync_ignored_sources()
                    self._retest_auto_blocked.discard(source["identity"])
                    restored += 1
            if retest:
                processed = {source["identity"] for source in pending}
                self._retest_pending = [
                    identity
                    for identity in self._retest_pending
                    if identity not in processed
                ]
                remaining = len(self._retest_pending)
                if not remaining:
                    self._retest_auto_blocked.clear()
            else:
                remaining = max(0, pending_count - len(pending))
            self._save_settings()
            if blocked or restored:
                if not self._refresh_locked(allow_empty=True):
                    raise ValueError(self.status["error"] or self.status["write_state"])
            summary = {
                "tested": len(pending),
                "cached": cached_count,
                "available": counts["available"],
                "unavailable": counts["unavailable"],
                "limited": counts["limited"],
                "blocked": blocked,
                "restored": restored,
                "remaining": remaining,
                "retest": retest,
            }
            self._log(
                "INFO",
                "站点检测完成: 请求={tested} 可达={available} 结构无效={unavailable} "
                "受限={limited} 新增失效屏蔽={blocked} 恢复={restored} 剩余={remaining}".format(
                    **summary
                ),
            )
            return summary
        except Exception as exc:
            self._log(
                "INFO" if isinstance(exc, SiteTestCancelled) else "ERROR",
                "站点检测批次{}: {}".format(
                    "已取消" if isinstance(exc, SiteTestCancelled) else "失败",
                    exc,
                ),
            )
            self.ignored_sources = previous_ignored
            self.manual_ignored_sources = previous_manual_ignored
            self.auto_blocked_sources = previous_auto_blocked
            self.site_test_results = previous_results
            self.cache = previous_cache
            self.status = previous_status
            self._retest_pending = previous_retest_pending
            self._retest_auto_blocked = previous_retest_auto_blocked
            try:
                self._save_settings()
            except Exception:
                pass
            raise

    def _site_test_summary_text(self, summary):
        return (
            "站点检测完成：请求 {tested}，可达 {available}，"
            "结构无效 {unavailable}，受限 {limited}，"
            "新增屏蔽 {blocked}，恢复 {restored}，剩余 {remaining}"
        ).format(**summary)

    def _run_site_test_worker(self, force):
        current = threading.current_thread()
        try:
            summary = self._test_sites_locked(force=force)
            if summary["blocked"] or summary["restored"]:
                _, reload_detail = self._reload_app_vod_config(
                    expected_keys=self._generated_registry_keys()
                )
            else:
                reload_detail = "屏蔽状态未变化，无需重载"
            self.inited = True
            summary_text = self._site_test_summary_text(summary)
            self._log("INFO", "{}；{}".format(summary_text, reload_detail))
            if not self._destroyed:
                self._notify_app(summary_text)
        except SiteTestCancelled:
            self._log("INFO", "站点检测后台任务已取消")
        except Exception as exc:
            message = "站点检测失败：{}".format(exc)
            self._log("ERROR", "站点检测后台任务失败: {}".format(exc))
            if not self._destroyed:
                self._notify_app(message)
        finally:
            with self._site_test_control_lock:
                if self._site_test_thread is current:
                    self._site_test_thread = None

    def _start_site_test_worker(self, force=False):
        with self.lock:
            with self._site_test_control_lock:
                worker = self._site_test_thread
                if worker is not None and worker.is_alive():
                    return False
                worker = threading.Thread(
                    target=self._run_site_test_worker,
                    args=(bool(force),),
                    name="webhtv-site-test",
                )
                worker.daemon = True
                self._destroyed = False
                self._site_test_cancel.clear()
                self._site_test_thread = worker
                worker.start()
                return True

    def _site_test_is_running(self):
        with self._site_test_control_lock:
            worker = self._site_test_thread
            return worker is not None and worker.is_alive()

    def _source_signature(self, source):
        size = source.get("size")
        modified_ns = source.get("mtime_ns")
        if size is None or modified_ns is None:
            try:
                stat = os.stat(source["path"])
                size = stat.st_size
                modified_ns = getattr(
                    stat, "st_mtime_ns", int(stat.st_mtime * 1000000000)
                )
            except Exception:
                return "missing"
        signature_data = {
            "version": self.SITE_TEST_CACHE_VERSION,
            "type": str(source.get("type", "")).upper(),
            "size": int(size),
            "mtime_ns": int(modified_ns),
        }
        if source.get("dependencies"):
            dependency_stats = []
            for path in source.get("dependencies", []):
                try:
                    stat = os.stat(path)
                    dependency_stats.append(
                        {
                            "path": self._file_url(path),
                            "size": int(stat.st_size),
                            "mtime_ns": int(
                                getattr(
                                    stat,
                                    "st_mtime_ns",
                                    int(stat.st_mtime * 1000000000),
                                )
                            ),
                        }
                    )
                except Exception:
                    dependency_stats.append(
                        {"path": self._file_url(path), "missing": True}
                    )
            signature_data["dependencies"] = dependency_stats
        proxy_values = {
            name: str(os.environ.get(name, ""))
            for name in (
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "NO_PROXY",
                "http_proxy",
                "https_proxy",
                "no_proxy",
            )
            if os.environ.get(name)
        }
        signature_data["proxy"] = self._digest(
            json.dumps(proxy_values, sort_keys=True, separators=(",", ":")), 16
        )
        if signature_data["type"] == "XBPQ":
            signature_data["xbpq_api"] = self._runtime_reference(self.xbpq_api)
            signature_data["xbpq_jar"] = self._xbpq_jar_reference()
        raw = json.dumps(
            signature_data, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _has_fresh_test_result(self, source):
        result = self.site_test_results.get(source["identity"])
        return (
            isinstance(result, dict)
            and result.get("state") in ("available", "unavailable", "limited")
            and result.get("source_signature") == self._source_signature(source)
        )

    def _test_source_availability(self, source):
        checked_at = time.strftime("%Y-%m-%d %H:%M:%S")
        source_type = source["type"]
        path = source["path"]
        try:
            if not os.path.isfile(path) or not os.access(path, os.R_OK):
                return self._test_result("unavailable", "源文件不存在或不可读", checked_at)
            package_detail = ""
            if source.get("csp_site"):
                if "#bundle-site-" in str(source.get("identity", "")):
                    missing = [
                        item
                        for item in source.get("dependencies", [])
                        if not os.path.isfile(item) or not os.access(item, os.R_OK)
                    ]
                    if missing:
                        return self._test_result(
                            "unavailable",
                            "整包站点本地依赖已缺失: {}".format(missing[0]),
                            checked_at,
                        )
                    package_detail = source.get("validation", "") or "整包站点依赖完整"
                else:
                    valid, detail = self._validate_source(source_type, path)
                    if not valid:
                        return self._test_result("unavailable", detail, checked_at)
                    package_detail = (
                        detail
                        or source.get("validation", "")
                        or "目录包结构有效"
                    )
            if source_type == "HTML":
                valid, detail = self._validate_source("HTML", path)
                return self._test_result(
                    "available" if valid else "unavailable",
                    "本地 WebHome 页面结构有效" if valid else detail,
                    checked_at,
                )
            if source_type == "JS":
                text = self._read_text(
                    self._source_probe_path(source), 512 * 1024
                )
                if not self._has_quickjs_export(text):
                    return self._test_result(
                        "unavailable",
                        "未发现 QuickJS 导出入口",
                        checked_at,
                    )
            if source_type == "PY":
                valid, detail = self._validate_source("PY", path)
                if not valid:
                    return self._test_result("unavailable", detail, checked_at)
            if source_type == "XBPQ" and not source.get("csp_site"):
                ready, detail = self._xbpq_runtime_status()
                if not ready:
                    return self._test_result("unavailable", detail, checked_at)

            probe_url = self._source_probe_url(source)
            if not probe_url:
                probe_path = self._source_probe_path(source)
                probe_url = self._extract_probe_url(probe_path)
            if not probe_url:
                return self._test_result(
                    "limited",
                    "{}；未提取到可安全探测的主页地址".format(
                        package_detail
                    ).lstrip("；"),
                    checked_at,
                )
            origin = self._url_origin(probe_url)
            if not origin:
                return self._test_result("limited", "主页地址格式无法确认", checked_at)
            state, detail = self._probe_site_url(probe_url)
            if package_detail:
                detail = package_detail + "；" + detail
            return self._test_result(state, detail, checked_at, origin)
        except Exception as exc:
            return self._test_result(
                "limited", "检测过程受限: {}".format(exc), checked_at
            )

    def _source_probe_path(self, source):
        site = source.get("csp_site", {})
        if isinstance(site, dict):
            fields = ("homePage", "ext", "api") if "#bundle-site-" in str(
                source.get("identity", "")
            ) else (("api",) if source.get("type") == "JS" else ("ext",))
            for field in fields:
                reference = site.get(field, "")
                if isinstance(reference, str) and reference.strip():
                    path = self._site_reference_path(reference)
                    if path and os.path.isfile(path) and os.access(path, os.R_OK):
                        return path
        return source["path"]

    def _source_probe_url(self, source):
        site = source.get("csp_site", {})
        if not isinstance(site, dict):
            return ""
        for field in ("homePage", "ext", "api"):
            value = site.get(field, "")
            if not isinstance(value, str):
                continue
            parsed = urllib.parse.urlsplit(value.strip())
            if parsed.scheme.lower() in ("http", "https") and parsed.netloc:
                return value.strip()
        return ""

    def _test_result(self, state, detail, checked_at, origin=""):
        result = {
            "state": state,
            "detail": str(detail or "")[:240],
            "checked_at": checked_at,
        }
        if origin:
            result["origin"] = origin
        return result

    def _extract_probe_url(self, path):
        text = self._read_text(path, 512 * 1024)
        text = text.replace("\\/", "/").replace("\\u002F", "/").replace("\\u002f", "/")
        matches = re.findall(r"https?://[^\s\"'<>\\]+", text, flags=re.IGNORECASE)
        scored = []
        for index, value in enumerate(matches):
            value = value.rstrip("),;]}，。")
            parsed = urllib.parse.urlsplit(value)
            if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
                continue
            host = (parsed.hostname or "").lower()
            if host in ("127.0.0.1", "localhost") or host.endswith(".local"):
                continue
            lower = value.lower()
            score = -index
            if parsed.path in ("", "/"):
                score += 20
            if re.search(r"\.(?:jpg|jpeg|png|gif|webp|svg|m3u8|mp4|css|woff2?)(?:\?|$)", lower):
                score -= 50
            if host in ("example.com", "www.example.com"):
                score -= 100
            scored.append((score, value))
        return max(scored, default=(0, ""), key=lambda item: item[0])[1]

    def _url_origin(self, url):
        try:
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
                return ""
            return "{}://{}/".format(parsed.scheme.lower(), parsed.netloc)
        except Exception:
            return ""

    def _probe_site_url(self, url):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Android; TVBox Site Check)",
                "Accept": "text/html,application/json;q=0.9,*/*;q=0.5",
                "Range": "bytes=0-1023",
                "Connection": "close",
            },
        )
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler(), NoRedirectHandler()
        )
        try:
            with opener.open(request, timeout=self.SITE_TEST_TIMEOUT) as response:
                status = int(getattr(response, "status", response.getcode()))
                response.read(1024)
            if 200 <= status < 400:
                return "available", "站点地址可达 (HTTP {})".format(status)
            return "limited", "站点响应受限 (HTTP {})".format(status)
        except urllib.error.HTTPError as exc:
            if 300 <= int(exc.code) < 400:
                return "available", "站点地址可达并返回跳转 (HTTP {})".format(
                    exc.code
                )
            return "limited", "站点响应受限 (HTTP {})".format(exc.code)
        except urllib.error.URLError as exc:
            reason = exc.reason
            text = str(reason).lower()
            if isinstance(reason, socket.timeout) or "timed out" in text or "timeout" in text:
                return "limited", "主页连接超时"
            if isinstance(reason, (socket.gaierror, ConnectionRefusedError)) or any(
                marker in text
                for marker in (
                    "connection refused",
                    "name or service not known",
                    "nodename nor servname",
                    "no address associated",
                )
            ):
                return "limited", "站点网络不可达: {}".format(reason)
            return "limited", "站点连接受限: {}".format(reason)
        except (socket.timeout, TimeoutError):
            return "limited", "主页连接超时"
        except ConnectionRefusedError as exc:
            return "limited", "站点连接被拒绝: {}".format(exc)
        except Exception as exc:
            return "limited", "主页检测受限: {}".format(exc)

    def _test_result_label(self, result):
        if not isinstance(result, dict):
            return "未检测"
        return {
            "available": "可达",
            "unavailable": "疑似失效",
            "limited": "检测受限",
        }.get(str(result.get("state", "")), "未检测")

    def _normalize_extension(self, value):
        value = str(value or "").strip().lower()
        if not value:
            return ""
        return value if value.startswith(".") else "." + value

    # --------------------------------------------------------------------------
    # 本地包下载与安全安装
    # --------------------------------------------------------------------------
    def _package_download_running(self):
        with self._package_download_lock:
            worker = self._package_download_thread
            return worker is not None and worker.is_alive()

    def _package_xbpq_root(self):
        for item in self.scan_roots:
            if str(item.get("type", "")).upper() != "XBPQ":
                continue
            path = str(item.get("path", "")).strip()
            if path:
                return os.path.realpath(os.path.abspath(os.path.expanduser(path)))
        return os.path.realpath(
            os.path.abspath(_detect_child_dir(self.local_base_dir, "XBPQ"))
        )

    def _encoded_download_url(self, value):
        url = self._normalize_package_download_url(value)
        parsed = urllib.parse.urlsplit(url)
        path = urllib.parse.quote(urllib.parse.unquote(parsed.path), safe="/%:@")
        query = urllib.parse.quote(urllib.parse.unquote(parsed.query), safe="=&%:@/?+")
        return urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, path, query, parsed.fragment)
        )

    def _package_name_from_url(self, value):
        parsed = urllib.parse.urlsplit(value)
        name = urllib.parse.unquote(os.path.basename(parsed.path)).strip()
        if name.lower().endswith(".zip"):
            name = name[:-4]
        name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", name)
        name = re.sub(r"\s+", " ", name).strip(" ._")
        return (name or "本地包")[:80]

    def _package_name_from_label(self, value):
        return self._normalize_package_download_name(value)

    def _package_download_directory(self):
        path = os.path.expanduser(str(self.package_download_dir or "").strip())
        if not os.path.isabs(path):
            path = os.path.join(self.STORAGE_ROOT, path.lstrip("/"))
        return os.path.realpath(os.path.abspath(path))

    def _package_install_target(self, url=None, site_name=None):
        if site_name is not None:
            return os.path.join(
                self._package_xbpq_root(), self._package_name_from_label(site_name)
            )
        package_name = self._package_name_from_url(
            url if url is not None else self.package_download_url
        )
        return os.path.join(
            self._package_xbpq_root(), "自动下载-{}".format(package_name)
        )

    def _package_install_marker(self, target):
        return os.path.join(target, self.PACKAGE_INSTALL_MARKER)

    def _read_package_install_marker(self, target):
        path = self._package_install_marker(target)
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_package_install_marker(self, target, data):
        path = self._package_install_marker(target)
        temp_path = path + ".tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)
                fp.write("\n")
                fp.flush()
                os.fsync(fp.fileno())
            os.replace(temp_path, path)
        finally:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass

    def _rename_package_install_directory(self, site_id, old_name, new_name):
        old_target = self._package_install_target(site_name=old_name)
        new_target = self._package_install_target(site_name=new_name)
        if os.path.realpath(old_target) == os.path.realpath(new_target):
            return None
        if not os.path.isdir(old_target):
            return None
        marker = self._read_package_install_marker(old_target)
        if str(marker.get("id", "")).strip() != str(site_id or "").strip():
            return None
        if os.path.exists(new_target):
            raise ValueError(
                "新备注名“{}”对应文件夹已存在，请更换备注名".format(new_name)
            )
        os.replace(old_target, new_target)
        marker["name"] = new_name
        try:
            self._write_package_install_marker(new_target, marker)
        except Exception:
            os.replace(new_target, old_target)
            raise
        return {
            "old": old_target,
            "new": new_target,
            "marker": marker,
            "old_name": old_name,
        }

    def _rollback_package_install_rename(self, moved):
        if not isinstance(moved, dict):
            return
        old_target = str(moved.get("old", ""))
        new_target = str(moved.get("new", ""))
        if not old_target or not new_target or not os.path.isdir(new_target):
            return
        if os.path.exists(old_target):
            return
        os.replace(new_target, old_target)
        marker = dict(moved.get("marker", {}))
        marker["name"] = str(moved.get("old_name", marker.get("name", "")))
        self._write_package_install_marker(old_target, marker)

    def _enable_package_xbpq_scan(self):
        previous_types = dict(self.type_enabled)
        previous_pending = dict(self.pending_type_enabled)
        previous_dirty = self.config_dirty
        changed = not self.type_enabled.get("XBPQ", True) or not (
            self.pending_type_enabled.get("XBPQ", True)
        )
        if not changed:
            return False
        try:
            self.type_enabled["XBPQ"] = True
            self.pending_type_enabled["XBPQ"] = True
            self.config_dirty = any(
                self.pending_type_enabled[item] != self.type_enabled[item]
                for item in self.TYPE_ORDER
            ) or self.pending_block_adult_sites != self.block_adult_sites
            self._save_settings()
            return True
        except Exception:
            self.type_enabled = previous_types
            self.pending_type_enabled = previous_pending
            self.config_dirty = previous_dirty
            raise

    def _download_package_archive(self, url):
        directory = self._package_download_directory()
        os.makedirs(directory, exist_ok=True)
        token = self._digest(url + str(time.time_ns()), 16)
        temp_path = os.path.join(directory, ".package-{}.zip.part".format(token))
        request = urllib.request.Request(
            self._encoded_download_url(url),
            headers={
                "User-Agent": "okhttp/4.12.0",
                "Accept": "application/zip, application/octet-stream, */*",
                "Connection": "close",
            },
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        total = 0
        try:
            with opener.open(request, timeout=30) as response:
                status = int(getattr(response, "status", response.getcode()))
                if status < 200 or status >= 300:
                    raise ValueError("下载返回 HTTP {}".format(status))
                length = response.headers.get("Content-Length")
                if length and int(length) > self.MAX_PACKAGE_DOWNLOAD_SIZE:
                    raise ValueError("压缩包超过下载上限")
                with open(temp_path, "wb") as fp:
                    while True:
                        chunk = response.read(128 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > self.MAX_PACKAGE_DOWNLOAD_SIZE:
                            raise ValueError("压缩包超过下载上限")
                        fp.write(chunk)
                    fp.flush()
                    os.fsync(fp.fileno())
            if total <= 0:
                raise ValueError("下载内容为空")
            if not zipfile.is_zipfile(temp_path):
                raise ValueError("下载内容不是有效 ZIP")
            return temp_path, total
        except Exception:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass
            raise

    def _safe_archive_member_path(self, root, name):
        value = str(name or "").replace("\\", "/").lstrip("/")
        while value.startswith("./"):
            value = value[2:]
        parts = [part for part in value.split("/") if part not in ("", ".")]
        if not parts or any(part == ".." for part in parts):
            raise ValueError("ZIP 包含非法路径: {}".format(name))
        if re.match(r"^[A-Za-z]:", parts[0]):
            raise ValueError("ZIP 包含盘符路径: {}".format(name))
        target = os.path.realpath(os.path.join(root, *parts))
        root_real = os.path.realpath(root)
        if os.path.commonpath((target, root_real)) != root_real:
            raise ValueError("ZIP 路径越界: {}".format(name))
        return target

    def _extract_package_archive(self, archive_path, package_name, package_site=None):
        xbpq_root = self._package_xbpq_root()
        os.makedirs(xbpq_root, exist_ok=True)
        if isinstance(package_site, dict):
            safe_name = self._package_name_from_label(package_name)
        else:
            safe_name = "自动下载-{}".format(package_name)
        target = os.path.join(xbpq_root, safe_name)
        legacy_target = ""
        if isinstance(package_site, dict):
            legacy_url = str(package_site.get("url", "")).strip()
            if legacy_url:
                legacy_target = self._package_install_target(url=legacy_url)
                if os.path.realpath(legacy_target) == os.path.realpath(target):
                    legacy_target = ""
        if os.path.isdir(target) and isinstance(package_site, dict):
            marker = self._read_package_install_marker(target)
            expected_id = str(package_site.get("id", "")).strip()
            marker_id = str(marker.get("id", "")).strip()
            if not expected_id or marker_id != expected_id:
                raise ValueError(
                    "备注名“{}”对应文件夹已存在且不是本站点安装目录，请更换备注名".format(
                        safe_name
                    )
                )
        token = self._digest(target, 12)
        staging = os.path.join(xbpq_root, ".package-{}.tmp".format(token))
        rollback = os.path.join(xbpq_root, ".package-{}.rollback".format(token))
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(rollback, ignore_errors=True)
        os.makedirs(staging)
        file_count = 0
        total_size = 0
        supported_count = 0
        installed = False
        try:
            with zipfile.ZipFile(archive_path, "r") as archive:
                infos = archive.infolist()
                if len(infos) > self.MAX_PACKAGE_FILES:
                    raise ValueError("ZIP 文件数量超过上限")
                for info in infos:
                    mode = (int(info.external_attr) >> 16) & 0o170000
                    if mode == 0o120000:
                        raise ValueError("ZIP 不允许符号链接: {}".format(info.filename))
                    destination = self._safe_archive_member_path(
                        staging, info.filename
                    )
                    if info.is_dir() or info.filename.endswith("/"):
                        os.makedirs(destination, exist_ok=True)
                        continue
                    file_count += 1
                    size = int(info.file_size)
                    total_size += size
                    if size > self.MAX_PACKAGE_FILE_SIZE:
                        raise ValueError("ZIP 单文件超过上限: {}".format(info.filename))
                    if total_size > self.MAX_PACKAGE_EXTRACT_SIZE:
                        raise ValueError("ZIP 解压总大小超过上限")
                    lower = info.filename.lower()
                    if lower.endswith((".json", ".jsonc", ".js", ".py", ".jar", ".html")):
                        supported_count += 1
                    os.makedirs(os.path.dirname(destination), exist_ok=True)
                    with archive.open(info, "r") as source, open(destination, "wb") as output:
                        shutil.copyfileobj(source, output, 128 * 1024)
                if not file_count or not supported_count:
                    raise ValueError("ZIP 中未发现可扫描的本地源文件")
            if isinstance(package_site, dict):
                marker = {
                    "id": str(package_site.get("id", "")),
                    "name": str(package_site.get("name", safe_name)),
                    "url": str(package_site.get("url", "")),
                    "installedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                self._write_package_install_marker(staging, marker)
            if os.path.isdir(target):
                os.replace(target, rollback)
            os.replace(staging, target)
            installed = True
            shutil.rmtree(rollback, ignore_errors=True)
            if legacy_target and os.path.isdir(legacy_target):
                shutil.rmtree(legacy_target, ignore_errors=True)
            return {
                "target": target,
                "files": file_count,
                "size": total_size,
            }
        except Exception:
            if not installed and not os.path.exists(target) and os.path.isdir(rollback):
                os.replace(rollback, target)
            raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)
            if installed:
                shutil.rmtree(rollback, ignore_errors=True)

    def _package_source_count(self, target):
        target_real = os.path.realpath(os.path.abspath(target))
        count = 0
        for source in self.cache["sources"] + self.cache["ignored"]:
            path = str(source.get("path", "")).strip()
            if not path:
                continue
            try:
                source_real = os.path.realpath(os.path.abspath(path))
                if os.path.commonpath((source_real, target_real)) == target_real:
                    count += 1
            except Exception:
                continue
        return count

    def _package_download_worker(self, sites):
        successes = []
        failures = []
        used_package_names = set()
        try:
            total = len(sites)
            for index, site in enumerate(sites, 1):
                archive_path = ""
                site_id = str(site.get("id", ""))
                site_name = str(site.get("name", "本地包"))
                url = str(site.get("url", ""))
                self._package_download_active_site_id = site_id
                self._package_download_active_site_name = site_name
                try:
                    self._package_download_state = "downloading"
                    self._package_download_message = "正在下载 {}/{}：{}".format(
                        index, total, site_name
                    )
                    self._notify_app(
                        "正在下载本地包 {}/{}：{}".format(index, total, site_name)
                    )
                    archive_path, download_size = self._download_package_archive(url)
                    self._package_download_state = "extracting"
                    package_name = self._package_name_from_label(site_name)
                    package_key = package_name.casefold()
                    if package_key in used_package_names:
                        raise ValueError("下载站点备注名重复: {}".format(site_name))
                    used_package_names.add(package_key)
                    result = self._extract_package_archive(
                        archive_path, package_name, package_site=site
                    )
                    successes.append(
                        {
                            "id": site_id,
                            "name": site_name,
                            "url": url,
                            "download_size": download_size,
                            "result": result,
                        }
                    )
                except Exception as exc:
                    failures.append({"name": site_name, "error": str(exc)})
                    self._log(
                        "WARN",
                        "{} 本地包下载安装失败: {}".format(site_name, exc),
                    )
                finally:
                    if archive_path:
                        try:
                            os.remove(archive_path)
                        except FileNotFoundError:
                            pass
                        except Exception as exc:
                            self._log(
                                "WARN", "下载临时文件清理失败: {}".format(exc)
                            )
            if not successes:
                raise ValueError(
                    "；".join(
                        "{}: {}".format(item["name"], item["error"])
                        for item in failures
                    )
                    or "没有站点下载成功"
                )
            self._package_download_state = "scanning"
            self._package_download_active_site_id = ""
            self._package_download_active_site_name = "批量扫描"
            self._package_download_message = "下载完成，正在统一扫描并加载"
            with self.lock:
                xbpq_auto_enabled = self._enable_package_xbpq_scan()
                ok = self._refresh_locked(
                    allow_empty=not any(self.type_enabled.values())
                )
                self.inited = True
                if not ok:
                    raise ValueError(
                        self.status["error"] or self.status["write_state"]
                    )
                _, reload_detail = self._reload_app_vod_config(
                    expected_keys=self._generated_registry_keys()
                )
                package_source_count = sum(
                    self._package_source_count(item["result"]["target"])
                    for item in successes
                )
                if not package_source_count and self.status["compatibility_blocked"]:
                    raise PackageCompatibilityError(
                        "已开启的本地包已下载并解压，但其 JAR 与当前 {} 不兼容，"
                        "已阻止站点加载并清除旧注入；{}".format(
                            self._app_mode_label(), reload_detail
                        )
                    )
            total_files = sum(item["result"]["files"] for item in successes)
            total_size = sum(item["download_size"] for item in successes)
            failure_detail = "；".join(
                "{}: {}".format(item["name"], item["error"])
                for item in failures
            )
            message = "批量安装完成：成功 {}/{}，共 {} 个文件、{:.2f} MB；{}{}{}".format(
                len(successes),
                len(sites),
                total_files,
                float(total_size) / 1024 / 1024,
                "失败 {} 个（{}）；".format(len(failures), failure_detail)
                if failures
                else "",
                "已自动开启 XBPQ 扫描；" if xbpq_auto_enabled else "",
                reload_detail,
            )
            self._package_download_state = "partial" if failures else "success"
            self._package_download_message = message
            self._log("WARN" if failures else "INFO", message)
            self._notify_app(message)
        except PackageCompatibilityError as exc:
            message = str(exc)
            self._package_download_state = "incompatible"
            self._package_download_message = message
            self._log("WARN", message)
            self._notify_app(message)
        except Exception as exc:
            message = "本地包批量下载安装失败: {}".format(exc)
            self._package_download_state = "error"
            self._package_download_message = message
            self._log("ERROR", message)
            self._notify_app(message)
        finally:
            with self._package_download_lock:
                self._package_download_thread = None

    def _start_package_download(self, site_id=""):
        enabled_sites = self._enabled_package_download_sites()
        if not enabled_sites:
            return False, "没有已开启的下载站点，请先到设置中开启"
        with self._package_download_lock:
            worker = self._package_download_thread
            if worker is not None and worker.is_alive():
                return False, "本地包正在下载或安装，请稍候"
            names = "、".join(
                str(item.get("name", "本地包")) for item in enabled_sites
            )
            self._package_download_state = "queued"
            self._package_download_message = "已加入批量任务：{}".format(names)
            self._package_download_active_site_id = ""
            self._package_download_active_site_name = "批量下载"
            worker = threading.Thread(
                target=self._package_download_worker,
                args=(enabled_sites,),
                name="local-package-download",
            )
            worker.daemon = True
            self._package_download_thread = worker
            worker.start()
        return True, "已开始下载 {} 个已开启站点：{}；完成后统一扫描并加载".format(
            len(enabled_sites), names
        )

    def _is_package_download_action(self, action):
        value = str(action or "")
        return value == self.ACTION_DOWNLOAD_PACKAGE or value.startswith(
            self.ACTION_DOWNLOAD_PACKAGE_PREFIX
        )

    # --------------------------------------------------------------------------
    # 扫描与配置生成
    # --------------------------------------------------------------------------
    def _ensure_initialized(self):
        if self.inited:
            return
        self.init("")

    def _manual_scan_state_key(self):
        return os.path.realpath(
            os.path.abspath(os.path.expanduser(self.output_path))
        )

    def _begin_manual_scan_request(self):
        key = self._manual_scan_state_key()
        now = time.monotonic()
        with _MANUAL_SCAN_LOCK:
            state = _MANUAL_SCAN_STATE.setdefault(
                key, {"running": False, "last": 0.0}
            )
            if state["running"]:
                return False, "扫描请求已合并：当前扫描正在进行"
            elapsed = now - float(state.get("last", 0.0) or 0.0)
            if elapsed < max(0.5, float(self.MANUAL_SCAN_DEDUP_WINDOW)):
                return False, "已忽略重复触发：本次扫描刚刚完成"
            state["running"] = True
            state["started"] = now
        return True, ""

    def _finish_manual_scan_request(self):
        key = self._manual_scan_state_key()
        with _MANUAL_SCAN_LOCK:
            state = _MANUAL_SCAN_STATE.setdefault(
                key, {"running": False, "last": 0.0}
            )
            state["running"] = False
            state["last"] = time.monotonic()

    def _refresh_locked(self, allow_empty=False):
        self.status = self._empty_status()
        self.status["scan_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        enabled_roots = [
            "{}={}".format(item.get("type", "?"), item.get("path", ""))
            for item in self.scan_roots
            if self.type_enabled.get(str(item.get("type", "")).upper(), True)
        ]
        self._log(
            "INFO",
            "开始扫描: allow_empty={} roots={}".format(
                bool(self.allow_empty_write or allow_empty),
                "; ".join(enabled_roots) or "无已开启目录",
            ),
        )
        try:
            self._scan_all_roots()
            if self.status["limit_reached"]:
                self.status["write_state"] = "扫描达到保护上限，已保护旧注册表"
                self.status["error"] = "请缩小扫描目录或调整 max_files"
                self._log("WARN", self.status["error"])
                return False
            if (
                not self.cache["sources"]
                and not self.cache["ignored"]
                and not (self.allow_empty_write or allow_empty)
                and not self.status["compatibility_blocked"]
            ):
                self.status["write_state"] = "未找到有效源，已保护旧配置"
                self.status["error"] = "扫描结果为空，未改写站点注入注册表"
                self._log("WARN", self.status["error"])
                return False
            if (
                not self.cache["sources"]
                and self.status["compatibility_blocked"]
            ):
                self._warn(
                    "检测到会导致当前 App 退出或接口不兼容的 JAR，"
                    "已清除对应旧注入站点"
                )
            self._generate_config()
            completed = self.status["written"] or self.status["write_state"] == "配置内容未变化"
            if completed:
                try:
                    self._save_scan_snapshot()
                except Exception as exc:
                    self._warn("扫描列表快照保存失败: {}".format(exc))
                if self.auto_scan_suspended:
                    self.auto_scan_suspended = False
                    try:
                        self._save_settings()
                    except Exception as exc:
                        self._warn("自动补扫状态保存失败: {}".format(exc))
            self._log(
                "INFO",
                "扫描完成: 发现={} 有效={} 忽略={} 跳过={} 重复={} 状态={}".format(
                    self.status["found"],
                    self.status["included"],
                    self.status["ignored"],
                    self.status["skipped"],
                    self.status["duplicates"],
                    self.status["write_state"],
                ),
            )
            return completed
        except Exception as exc:
            self.status["error"] = str(exc)
            self.status["write_state"] = "合并失败"
            self._log("ERROR", "扫描合并失败: {}".format(exc))
            return False

    def _auto_scan_on_enter_locked(self):
        """无有效快照时进入管理页自动补扫一次。

        仅扫描和写入注册表，不做站点网络检测；一键清除或恢复备份后暂停，
        直到下次手动扫描。进程内冷却防止“补扫 -> 重载 -> 再补扫”循环。
        """
        if not self.auto_scan_on_empty or self.auto_scan_suspended:
            return False
        if self.config_dirty or not any(self.type_enabled.values()):
            return False
        now = time.monotonic()
        if now - _AUTO_SCAN_STATE["last"] < self.AUTO_SCAN_COOLDOWN:
            return False
        _AUTO_SCAN_STATE["last"] = now
        ok = self._refresh_locked()
        if not ok:
            if (
                not self.cache["sources"]
                and not self.status["limit_reached"]
                and self.status["write_state"] == "未找到有效源，已保护旧配置"
            ):
                if self.cache["ignored"]:
                    # 保留 cache，忽略列表仍可在界面恢复
                    self.status["write_state"] = "所有本地源均已被忽略，可在忽略分类中恢复"
                    self.status["error"] = ""
                else:
                    self._set_manual_idle_status("未发现本地源，等待点击一键扫描并加载")
            return False
        self.status["write_state"] += " · 进入自动补扫"
        if self.status["registry_changed"] and self._snapshot_matches_registry():
            self._reload_app_vod_config(
                expected_keys=self._generated_registry_keys()
            )
        return True

    def _suspend_auto_scan(self):
        if self.auto_scan_suspended:
            return
        self.auto_scan_suspended = True
        try:
            self._save_settings()
        except Exception as exc:
            self._warn("自动补扫暂停状态保存失败: {}".format(exc))

    def _snapshot_matches_registry(self):
        data = self._load_scan_cache_payload(warn=False)
        snapshot = data.get("snapshot", {}) if isinstance(data, dict) else {}
        if not isinstance(snapshot, dict):
            return False
        token = str(snapshot.get("registry_token", ""))
        return bool(token) and token == self._registry_token(self.output_path)

    def _set_manual_idle_status(self, state="等待点击一键扫描并加载"):
        self.cache = self._empty_cache()
        self.status = self._empty_status()
        self.status["write_state"] = state
        try:
            registry = self._load_registry()
            items = registry.get("items", [])
            if isinstance(items, list):
                self.status["generated_sites"] = sum(
                    1 for item in items if self._is_generated_registry_item(item)
                )
                self.status["manual_sites"] = len(items) - self.status["generated_sites"]
        except Exception as exc:
            self._warn("注册表状态读取失败: {}".format(exc))

    def _clear_scan_cache_file(self):
        removed = 0
        path = os.path.abspath(os.path.expanduser(self.cache_path))
        protected = {
            os.path.abspath(os.path.expanduser(item))
            for item in (
                self.registry_path,
                self.output_path,
                self.settings_path,
                self.roots_config_path,
            )
        }
        if path in protected:
            self._warn("扫描缓存路径与配置文件冲突，已跳过删除: {}".format(path))
            return 0
        for candidate in (path, path + ".tmp"):
            try:
                os.remove(candidate)
                removed += 1
            except FileNotFoundError:
                pass
            except Exception as exc:
                self._warn("扫描缓存删除失败: {} ({})".format(candidate, exc))
        return removed

    def _scan_all_roots(self):
        self.cache = self._empty_cache()
        self._jar_inspection_cache = {}
        self.incomplete_scan_roots = []
        self.incomplete_scan_types = set()
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
                self._mark_scan_incomplete(source_type, root)
                continue
            available_types.add(source_type)
            manifest_owned_paths = self._manifest_owned_source_paths(
                root, source_type
            )
            manifest_owned_paths.update(
                self._bundle_owned_source_paths(root, source_type)
            )
            if source_type in ("XBPQ", "CSP"):
                local_jar_pairs, local_jar_ambiguous = self._discover_json_jar_pairs(
                    root, manifest_owned_paths
                )
            else:
                local_jar_pairs, local_jar_ambiguous = {}, set()

            def walk_error(exc, current_type=source_type, current_root=root):
                failed_path = getattr(exc, "filename", "") or current_root
                self._mark_scan_incomplete(current_type, failed_path)
                self._warn("扫描目录读取失败: {} ({})".format(failed_path, exc))

            for current, dirs, files in os.walk(
                root, topdown=True, onerror=walk_error, followlinks=False
            ):
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
                    is_manifest = self._is_site_manifest_name(lower_name)
                    if source_type == "JS" and extension == ".json" and not is_manifest:
                        continue
                    candidate_path = os.path.realpath(full_path)
                    if not is_manifest and candidate_path in manifest_owned_paths:
                        continue
                    if (
                        source_type == "CSP"
                        and not is_manifest
                        and candidate_path not in local_jar_pairs
                        and candidate_path not in local_jar_ambiguous
                    ):
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
                    if real_path == self_path and not self._is_auto_loader_python(
                        source_type, lower_name
                    ):
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
                        self._mark_scan_incomplete(source_type, full_path)
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

                    bundle = None
                    if (
                        source_type in ("XBPQ", "CSP")
                        and extension == ".json"
                        and not is_manifest
                    ):
                        bundle = self._parse_site_bundle(real_path)
                    if bundle is not None:
                        role = self._detect_file_role(source_type, lower_name, real_path)
                        if role not in ("source", "forced_source"):
                            self.status["skipped"] += 1
                            self._warn("已按 {} 标识排除: {}".format(role, real_path))
                            continue
                        self.status["cache_misses"] += 1
                        seen_paths.add(real_path)
                        new_file_cache[identity] = {
                            "size": file_size,
                            "mtime_ns": modified_ns,
                            "strict": bool(self.strict_recognition),
                            "role": "bundle",
                            "valid": bool(bundle["sites"]),
                            "validation": "TVBox 整包配置",
                        }
                        for entry in bundle["sites"]:
                            site = entry["site"]
                            site_identity = self._bundle_source_identity(
                                source_type, real_path, site
                            )
                            if site_identity in seen_paths:
                                self.status["duplicates"] += 1
                                continue
                            seen_paths.add(site_identity)
                            new_file_cache[site_identity] = {
                                "size": file_size,
                                "mtime_ns": modified_ns,
                                "strict": bool(self.strict_recognition),
                                "role": "bundle_site",
                                "valid": True,
                                "validation": entry["validation"],
                            }
                            source_id = "src_" + self._digest(site_identity, 20)
                            key = (
                                self.GENERATED_KEY_PREFIX
                                + source_type.lower()
                                + "_"
                                + self._digest(site_identity, 14)
                            )
                            source = {
                                "id": source_id,
                                "identity": site_identity,
                                "key": key,
                                "type": source_type,
                                "path": real_path,
                                "scan_root": root,
                                "root_order": root_order,
                                "relative_in_root": "{}::site:{:04d}".format(
                                    relative_in_root, entry["index"]
                                ),
                                "base_name": str(site.get("name", "")).strip(),
                                "package_label": self._bundle_package_label(
                                    root, real_path
                                ),
                                "validation": entry["validation"],
                                "ignored": site_identity in self.ignored_sources,
                                "size": file_size,
                                "mtime_ns": modified_ns,
                                "csp_site": site,
                                "dependencies": entry["dependencies"],
                            }
                            test_result = self.site_test_results.get(site_identity, {})
                            if not isinstance(test_result, dict) or test_result.get(
                                "source_signature"
                            ) != self._source_signature(source):
                                test_result = {}
                            source["test_result"] = test_result
                            if source["ignored"]:
                                ignored_sources.append(source)
                            else:
                                sources.append(source)
                        rejected = bundle["rejected"]
                        self.status["skipped"] += len(rejected)
                        self._log(
                            "INFO",
                            "整包配置识别: {} 总站点={} 完整={} 跳过={}".format(
                                real_path,
                                bundle["total"],
                                len(bundle["sites"]),
                                len(rejected),
                            ),
                        )
                        if rejected:
                            self._warn(
                                "整包配置已跳过 {} 个依赖不完整或不兼容站点: {}".format(
                                    len(rejected), os.path.basename(real_path)
                                )
                            )
                            for item in rejected:
                                self._log(
                                    "WARN",
                                    "整包站点已跳过: {} ({})".format(
                                        item["name"], item["reason"]
                                    ),
                                )
                        continue

                    cached = old_file_cache.get(identity)
                    cache_hit = (
                        isinstance(cached, dict)
                        and cached.get("size") == file_size
                        and cached.get("mtime_ns") == modified_ns
                        and cached.get("strict") == bool(self.strict_recognition)
                        and not is_manifest
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
                    csp_site = None
                    dependencies = []
                    if source_type in ("XBPQ", "CSP") and not is_manifest:
                        if real_path in local_jar_ambiguous:
                            self.status["skipped"] += 1
                            self._warn(
                                "{} JAR 绑定不明确，已跳过: {}".format(
                                    source_type, real_path
                                )
                            )
                            continue
                        paired_jar = local_jar_pairs.get(real_path)
                        if paired_jar:
                            try:
                                if source_type == "XBPQ":
                                    csp_site, dependencies, validation = (
                                        self._auto_xbpq_site(real_path, paired_jar)
                                    )
                                else:
                                    csp_site, dependencies, validation = (
                                        self._auto_csp_site(real_path, paired_jar)
                                    )
                            except Exception as exc:
                                self.status["skipped"] += 1
                                self._warn(
                                    "{} 自动配对失败: {} ({})".format(
                                        source_type, real_path, exc
                                    )
                                )
                                continue
                        elif source_type == "XBPQ":
                            ready, runtime_message = self._xbpq_runtime_status()
                            if not ready:
                                self.status["skipped"] += 1
                                self.incomplete_scan_types.add(source_type)
                                self._warn(runtime_message)
                                continue
                    if is_manifest and source_type in ("JS", "XBPQ", "CSP"):
                        try:
                            csp_site, dependencies, validation = (
                                self._parse_site_manifest(real_path, source_type)
                            )
                        except Exception as exc:
                            self.status["skipped"] += 1
                            self._warn(
                                "站点清单解析失败: {} ({})".format(
                                    real_path, exc
                                )
                            )
                            continue

                    seen_paths.add(real_path)
                    if csp_site is not None:
                        base_name = str(csp_site.get("name", "")).strip()
                    else:
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
                        "size": file_size,
                        "mtime_ns": modified_ns,
                    }
                    package_label = self._installed_package_label(root, real_path)
                    if package_label:
                        source["package_label"] = package_label
                    if csp_site is not None:
                        source["csp_site"] = csp_site
                        source["dependencies"] = dependencies
                    test_result = self.site_test_results.get(identity, {})
                    if not isinstance(test_result, dict) or test_result.get(
                        "source_signature"
                    ) != self._source_signature(source):
                        test_result = {}
                    source["test_result"] = test_result
                    if source["ignored"]:
                        ignored_sources.append(source)
                    else:
                        sources.append(source)
                if limit_reached:
                    break

        all_sources = sources + ignored_sources
        if self.block_adult_sites:
            previous_adult_blocked = set(self.adult_blocked_sources)
            previous_adult_allowed = set(self.adult_allowed_sources)
            for source in all_sources:
                identity = source["identity"]
                is_adult = self._is_adult_source(source)
                if is_adult and identity not in self.adult_allowed_sources:
                    self.adult_blocked_sources.add(identity)
                    source["adult_blocked"] = True
                    source["ignored"] = True
                    self.status["adult_filtered"] += 1
                    self._log(
                        "INFO",
                        "18+站点已加入屏蔽列表: {} ({})".format(
                            source.get("base_name", "未命名站点"),
                            source.get("relative_in_root", source.get("path", "")),
                        ),
                    )
                else:
                    self.adult_blocked_sources.discard(identity)
                    source["adult_blocked"] = False
                    source["ignored"] = identity in (
                        self.manual_ignored_sources | self.auto_blocked_sources
                    )
                    if not is_adult:
                        self.adult_allowed_sources.discard(identity)
            self._sync_ignored_sources()
            if self.status["adult_filtered"]:
                self._log(
                    "INFO",
                    "18+站点屏蔽完成: {} 个，可在屏蔽分类中手动恢复".format(
                        self.status["adult_filtered"]
                    ),
                )
            if (
                previous_adult_blocked != self.adult_blocked_sources
                or previous_adult_allowed != self.adult_allowed_sources
            ):
                try:
                    self._save_settings()
                except Exception as exc:
                    self._warn("18+站点屏蔽状态保存失败: {}".format(exc))
        else:
            for source in all_sources:
                source["adult_blocked"] = False
                source["ignored"] = source["identity"] in (
                    self.manual_ignored_sources | self.auto_blocked_sources
                )
        self._apply_display_names(all_sources)
        all_sources.sort(
            key=lambda item: (
                item["root_order"],
                self.TYPE_ORDER[item["type"]],
                item["relative_in_root"].lower(),
            )
        )

        deduplicated_sources = []
        active_fingerprints = set()
        for source in all_sources:
            source["site"] = self._build_site(source)
            fingerprint = self._site_fingerprint(source["site"])
            if (
                not source["ignored"]
                and fingerprint
                and fingerprint in active_fingerprints
            ):
                self.status["duplicates"] += 1
                self._log(
                    "INFO",
                    "语义重复站点已去重: {} ({})".format(
                        source["base_name"], source["relative_in_root"]
                    ),
                )
                continue
            if not source["ignored"] and fingerprint:
                active_fingerprints.add(fingerprint)
            deduplicated_sources.append(source)

        all_sources = deduplicated_sources
        for source in all_sources:
            self.cache["source_index"][source["id"]] = source
            source_type = source["type"]
            counts_key = "ignored_counts" if source["ignored"] else "type_counts"
            counts = self.cache[counts_key]
            counts[source_type] = counts.get(source_type, 0) + 1

        self.cache["sources"] = [item for item in all_sources if not item["ignored"]]
        self.cache["ignored"] = [item for item in all_sources if item["ignored"]]
        self.status["included"] = len(self.cache["sources"])
        self.status["ignored"] = len(self.cache["ignored"])
        persisted_identities = (
            self.ignored_sources
            | self.adult_blocked_sources
            | self.adult_allowed_sources
        )
        stale_ignored = {
            identity
            for identity in persisted_identities
            if not limit_reached
            and identity.split("|", 1)[0] in available_types
            and not self._scan_failure_covers_identity(identity)
            and identity not in new_file_cache
        }
        if stale_ignored:
            self.manual_ignored_sources.difference_update(stale_ignored)
            self.auto_blocked_sources.difference_update(stale_ignored)
            self.adult_blocked_sources.difference_update(stale_ignored)
            self.adult_allowed_sources.difference_update(stale_ignored)
            self._sync_ignored_sources()
            self.status["stale_ignored_removed"] = len(stale_ignored)
        stale_test_results = {
            identity
            for identity in self.site_test_results
            if not limit_reached
            and identity.split("|", 1)[0] in available_types
            and not self._scan_failure_covers_identity(identity)
            and identity not in new_file_cache
        }
        for identity in stale_test_results:
            self.site_test_results.pop(identity, None)
        if stale_ignored or stale_test_results:
            try:
                self._save_settings()
            except Exception as exc:
                self._warn("过期扫描状态清理保存失败: {}".format(exc))
        for identity, cached in old_file_cache.items():
            if identity not in new_file_cache and self._scan_failure_covers_identity(identity):
                new_file_cache[identity] = cached
        try:
            self._save_scan_cache(new_file_cache)
        except Exception as exc:
            self._warn("增量扫描缓存保存失败: {}".format(exc))

    def _mark_scan_incomplete(self, source_type, path):
        source_type = str(source_type or "").upper()
        normalized = os.path.realpath(os.path.abspath(os.path.expanduser(str(path))))
        marker = (source_type, normalized)
        if marker not in self.incomplete_scan_roots:
            self.incomplete_scan_roots.append(marker)

    def _reference_path(self, reference):
        value = str(reference or "").strip()
        if not value.lower().startswith("file://"):
            return ""
        path = value[7:]
        if not os.path.isabs(path):
            path = os.path.join(self.STORAGE_ROOT, path)
        return os.path.realpath(os.path.abspath(os.path.expanduser(path)))

    def _identity_source_path(self, identity):
        parts = str(identity or "").split("|", 1)
        reference = parts[1].split("#bundle-site-", 1)[0] if len(parts) == 2 else ""
        return self._reference_path(reference) if reference else ""

    def _path_is_within(self, path, parent):
        if not path or not parent:
            return False
        try:
            return os.path.commonpath((path, parent)) == parent
        except Exception:
            return False

    def _scan_failure_covers_identity(self, identity):
        source_type = str(identity or "").split("|", 1)[0].upper()
        if source_type in self.incomplete_scan_types:
            return True
        path = self._identity_source_path(identity)
        return any(
            item_type == source_type and self._path_is_within(path, failed_path)
            for item_type, failed_path in self.incomplete_scan_roots
        )

    def _source_identity(self, source_type, path):
        return source_type + "|" + self._file_url(path)

    def _bundle_source_identity(self, source_type, bundle_path, site):
        identity = {
            "key": str(site.get("key", "")),
            "name": str(site.get("name", "")),
            "api": site.get("api", ""),
            "ext": site.get("ext", ""),
            "jar": site.get("jar", ""),
            "homePage": site.get("homePage", site.get("home_page", "")),
        }
        raw = json.dumps(
            identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return "{}|{}#bundle-site-{}".format(
            source_type,
            self._file_url(bundle_path),
            self._digest(raw, 20),
        )

    def _bundle_package_label(self, scan_root, bundle_path):
        installed_label = self._installed_package_label(scan_root, bundle_path)
        if installed_label:
            return installed_label
        root = os.path.realpath(os.path.abspath(os.path.expanduser(str(scan_root))))
        path = os.path.realpath(os.path.abspath(os.path.expanduser(str(bundle_path))))
        try:
            relative = os.path.relpath(path, root)
        except Exception:
            relative = os.path.basename(path)
        parts = [part for part in relative.split(os.sep) if part not in ("", ".", "..")]
        if len(parts) > 1:
            label = parts[0]
        else:
            root_name = os.path.basename(root.rstrip(os.sep))
            generic_roots = {
                "xbpq", "csp", "js", "javascript", "py", "python", "html",
            }
            label = (
                os.path.splitext(os.path.basename(path))[0]
                if root_name.lower() in generic_roots
                else root_name
            )
        label = re.sub(r"[\r\n\t【】]+", " ", str(label)).strip()
        return label[:32] or os.path.splitext(os.path.basename(path))[0][:32] or "本地包"

    def _installed_package_label(self, scan_root, source_path):
        root = os.path.realpath(os.path.abspath(os.path.expanduser(str(scan_root))))
        path = os.path.realpath(os.path.abspath(os.path.expanduser(str(source_path))))
        try:
            relative = os.path.relpath(path, root)
        except Exception:
            return ""
        parts = [part for part in relative.split(os.sep) if part not in ("", ".", "..")]
        if len(parts) < 2:
            return ""
        package_root = os.path.join(root, parts[0])
        marker = self._read_package_install_marker(package_root)
        label = str(marker.get("name", "")).strip()
        if not label:
            return ""
        label = re.sub(r"[\r\n\t【】]+", " ", label).strip()
        return label[:32]

    def _strip_json_comments(self, text):
        result = []
        index = 0
        in_string = False
        escaped = False
        length = len(text)
        while index < length:
            char = text[index]
            if in_string:
                result.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                index += 1
                continue
            if char == '"':
                in_string = True
                result.append(char)
                index += 1
                continue
            if char == "/" and index + 1 < length:
                marker = text[index + 1]
                if marker == "/":
                    index += 2
                    while index < length and text[index] not in "\r\n":
                        index += 1
                    continue
                if marker == "*":
                    index += 2
                    while index + 1 < length and text[index : index + 2] != "*/":
                        if text[index] in "\r\n":
                            result.append(text[index])
                        index += 1
                    index = min(length, index + 2)
                    continue
            result.append(char)
            index += 1
        return "".join(result)

    def _strip_json_trailing_commas(self, text):
        result = []
        index = 0
        in_string = False
        escaped = False
        length = len(text)
        while index < length:
            char = text[index]
            if in_string:
                result.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                index += 1
                continue
            if char == '"':
                in_string = True
                result.append(char)
                index += 1
                continue
            if char == ",":
                lookahead = index + 1
                while lookahead < length and text[lookahead].isspace():
                    lookahead += 1
                if lookahead < length and text[lookahead] in "}]":
                    index += 1
                    continue
            result.append(char)
            index += 1
        return "".join(result)

    def _load_json_compatible(self, path):
        with open(path, "r", encoding="utf-8-sig") as fp:
            text = fp.read()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            cleaned = self._strip_json_trailing_commas(
                self._strip_json_comments(text)
            )
            return json.loads(cleaned)

    def _parse_site_bundle(self, path):
        try:
            data = self._load_json_compatible(path)
        except Exception:
            return None
        if not isinstance(data, dict) or not isinstance(data.get("sites"), list):
            return None

        default_jar = data.get("spider", "")
        accepted = []
        rejected = []
        for index, raw_site in enumerate(data["sites"]):
            raw_name = "站点 #{}".format(index + 1)
            if isinstance(raw_site, dict):
                raw_name = str(
                    raw_site.get("name")
                    or raw_site.get("key")
                    or raw_name
                ).strip()
            try:
                site, dependencies, validation = self._normalize_bundle_site(
                    path, raw_site, default_jar, index
                )
                accepted.append(
                    {
                        "index": index,
                        "site": site,
                        "dependencies": dependencies,
                        "validation": validation,
                    }
                )
            except Exception as exc:
                rejected.append({"index": index, "name": raw_name, "reason": str(exc)})
        return {
            "total": len(data["sites"]),
            "sites": accepted,
            "rejected": rejected,
        }

    def _looks_like_bundle_local_reference(self, bundle_path, value, field):
        source = str(value or "").strip().split(";md5;", 1)[0].strip()
        if not source or source.startswith(("{", "[")):
            return False
        field_key = str(field or "").strip().lower()
        local_reference_fields = {
            "api", "ext", "jar", "homepage", "home_page", "filters", "filter",
            "class", "classes", "type", "config", "configs", "file", "path",
            "script", "source",
        }
        if field == "api" and source.startswith("csp_"):
            return False
        scheme = urllib.parse.urlsplit(source).scheme.lower()
        if scheme in ("http", "https", "assets", "proxy"):
            return False
        if scheme in ("file", "clan"):
            return True
        if scheme:
            return False
        if source.startswith(("./", "../")):
            return True
        if os.path.isabs(source):
            storage_root = os.path.realpath(os.path.abspath(self.STORAGE_ROOT))
            real_source = os.path.realpath(os.path.abspath(source))
            local_prefixes = ("/storage/", "/sdcard/", "/data/")
            if (
                os.path.exists(source)
                or real_source == storage_root
                or real_source.startswith(storage_root + os.sep)
                or source.startswith(local_prefixes)
            ):
                return True
        sibling = os.path.join(os.path.dirname(bundle_path), source)
        if os.path.exists(sibling):
            return True
        extension = os.path.splitext(source.lower())[1]
        local_extensions = {
            ".json", ".jsonc", ".jar", ".py", ".js", ".html", ".htm",
            ".txt", ".m3u", ".m3u8",
        }
        if field == "jar":
            return True
        return extension in local_extensions and field_key in local_reference_fields

    def _resolve_bundle_reference(self, bundle_path, value, field, with_md5=False):
        source = str(value or "").strip()
        suffix = ""
        if with_md5 and ";md5;" in source:
            source, digest = source.split(";md5;", 1)
            source = source.strip()
            suffix = ";md5;" + digest.strip().lower()
        parsed = urllib.parse.urlsplit(source)
        if parsed.scheme.lower() == "clan" and parsed.hostname in (
            "localhost", "127.0.0.1"
        ):
            local_path = os.path.join(self.STORAGE_ROOT, parsed.path.lstrip("/"))
            return self._file_url(local_path) + suffix
        if not self._looks_like_bundle_local_reference(
            bundle_path, source, field
        ):
            return source + suffix
        return self._resolve_site_reference(
            bundle_path, source + suffix, with_md5=with_md5
        )

    def _require_local_dependency(self, reference, label, with_md5=False):
        path = self._site_reference_path(reference, with_md5=with_md5)
        if not path:
            return ""
        if not os.path.isfile(path) or not os.access(path, os.R_OK):
            raise ValueError("{} 不存在或不可读: {}".format(label, reference))
        if os.path.getsize(path) <= 0:
            raise ValueError("{} 是空文件: {}".format(label, reference))
        return path

    def _normalize_bundle_nested_refs(
        self, bundle_path, value, field, dependencies
    ):
        if isinstance(value, dict):
            return {
                key: self._normalize_bundle_nested_refs(
                    bundle_path, item, str(key), dependencies
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [
                self._normalize_bundle_nested_refs(
                    bundle_path, item, field, dependencies
                )
                for item in value
            ]
        if not isinstance(value, str) or not self._looks_like_bundle_local_reference(
            bundle_path, value, field
        ):
            return value
        with_md5 = field == "jar"
        reference = self._resolve_bundle_reference(
            bundle_path, value, field, with_md5=with_md5
        )
        path = self._require_local_dependency(
            reference, field or "嵌套依赖", with_md5=with_md5
        )
        if path:
            if path.lower().endswith((".json", ".jsonc")):
                self._load_json_compatible(path)
            dependencies.append(path)
        return reference

    def _normalize_bundle_site(self, bundle_path, raw_site, default_jar, index):
        if not isinstance(raw_site, dict):
            raise ValueError("站点必须是 JSON 对象")
        site = copy.deepcopy(raw_site)
        raw_home_page = site.get("homePage", site.get("home_page", ""))
        is_webhome = isinstance(raw_home_page, str) and bool(raw_home_page.strip())
        api = self._runtime_reference(self.html_api) if is_webhome else str(
            site.get("api", "")
        ).strip()
        if not api:
            raise ValueError("缺少 api")

        dependencies = []
        validation = []
        api_is_local = self._looks_like_bundle_local_reference(
            bundle_path, api, "api"
        )
        if api_is_local:
            api = self._resolve_bundle_reference(bundle_path, api, "api")
            api_path = self._require_local_dependency(api, "api")
            lower_api = api_path.lower()
            if lower_api.endswith(".py"):
                valid, detail = self._validate_source("PY", api_path)
            elif lower_api.endswith(".js"):
                valid, detail = self._validate_source("JS", api_path)
            else:
                valid, detail = True, ""
            if not valid:
                raise ValueError(detail)
            dependencies.append(api_path)
            if detail:
                validation.append(detail)
            site["api"] = api
        else:
            scheme = urllib.parse.urlsplit(api).scheme.lower()
            if not api.startswith("csp_") and scheme not in (
                "http", "https", "assets", "proxy"
            ):
                raise ValueError("api 类型无法确认: {}".format(api))
            site["api"] = api

        home_page = raw_home_page
        if isinstance(home_page, str) and home_page.strip():
            resolved_home = self._resolve_bundle_reference(
                bundle_path, home_page, "homePage"
            )
            home_path = self._require_local_dependency(resolved_home, "homePage")
            if home_path:
                dependencies.append(home_path)
            site["homePage"] = resolved_home
            site["api"] = api
            site.pop("home_page", None)
        elif home_page not in (None, ""):
            raise ValueError("homePage 必须是路径或 URL")

        ext = "" if is_webhome else site.get("ext", "")
        if isinstance(ext, str) and ext.strip():
            resolved_ext = self._resolve_bundle_reference(bundle_path, ext, "ext")
            ext_path = self._require_local_dependency(resolved_ext, "ext")
            if ext_path:
                if ext_path.lower().endswith((".json", ".jsonc")):
                    self._load_json_compatible(ext_path)
                if api == "csp_XBPQ":
                    valid, detail = self._validate_source("XBPQ", ext_path)
                    if not valid:
                        raise ValueError(detail)
                    if detail:
                        validation.append(detail)
                dependencies.append(ext_path)
            site["ext"] = resolved_ext
        elif isinstance(ext, (dict, list)):
            site["ext"] = self._normalize_bundle_nested_refs(
                bundle_path, ext, "ext", dependencies
            )
        elif ext not in (None, "") and not isinstance(ext, (dict, list)):
            raise ValueError("ext 必须是路径、URL 或 JSON 对象")

        if is_webhome:
            site.pop("ext", None)
        jar_value = "" if is_webhome else site.get("jar", "")
        if (
            not is_webhome
            and not str(jar_value or "").strip()
            and api.startswith("csp_")
        ):
            jar_value = default_jar
        if jar_value:
            if not isinstance(jar_value, str):
                raise ValueError("jar 必须是路径或 URL")
            resolved_jar = self._resolve_bundle_reference(
                bundle_path, jar_value, "jar", with_md5=True
            )
            jar_detail = self._validate_site_jar(resolved_jar, api)
            jar_path = self._require_local_dependency(
                resolved_jar, "jar", with_md5=True
            )
            if jar_path:
                actual_md5 = self._inspect_local_jar(jar_path)["md5"]
                resolved_jar = (
                    resolved_jar.split(";md5;", 1)[0].strip()
                    + ";md5;"
                    + actual_md5
                )
                dependencies.append(jar_path)
            site["jar"] = resolved_jar
            if jar_detail:
                validation.append(jar_detail)
        elif api.startswith("csp_") and not str(site.get("homePage", "")).strip():
            raise ValueError("{} 缺少可验证的 jar".format(api))
        else:
            site.pop("jar", None)

        name = str(site.get("name") or site.get("key") or api).strip()
        if not name:
            name = "站点 #{}".format(index + 1)
        site["name"] = name
        site["type"] = int(site.get("type", 3))
        site.setdefault("searchable", 0 if is_webhome else self.DEFAULT_SEARCHABLE)
        site.setdefault("quickSearch", 0 if is_webhome else self.DEFAULT_QUICK_SEARCH)
        dependencies = list(dict.fromkeys(dependencies))
        return site, dependencies, "；".join(validation) or "整包站点本地依赖完整"

    def _manifest_owned_source_paths(self, root, source_type):
        source_type = str(source_type or "").upper()
        if source_type not in ("JS", "XBPQ", "CSP") or not os.path.isdir(root):
            return set()
        fields = ("api", "ext") if source_type == "JS" else ("ext",)
        result = set()
        try:
            for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
                relative_dir = os.path.relpath(current, root)
                depth = 0 if relative_dir == "." else relative_dir.count(os.sep) + 1
                dirs[:] = [
                    name
                    for name in dirs
                    if not name.startswith(".")
                    and name.lower() not in self.SKIP_DIRS
                    and not os.path.islink(os.path.join(current, name))
                ]
                if depth >= self.max_scan_depth:
                    dirs[:] = []
                for name in files:
                    if not self._is_site_manifest_name(name):
                        continue
                    path = os.path.join(current, name)
                    if os.path.islink(path) or not os.path.isfile(path):
                        continue
                    try:
                        data = self._load_json_compatible(path)
                        if isinstance(data, dict) and isinstance(data.get("site"), dict) and not data.get("api"):
                            data = data["site"]
                        if not isinstance(data, dict):
                            continue
                        for field in fields:
                            reference = data.get(field, "")
                            if not isinstance(reference, str) or not reference.strip():
                                continue
                            resolved = self._resolve_site_reference(path, reference)
                            dependency = self._site_reference_path(resolved)
                            if dependency:
                                result.add(dependency)
                    except Exception:
                        continue
        except Exception:
            return result
        return result

    def _bundle_owned_source_paths(self, root, source_type):
        source_type = str(source_type or "").upper()
        if source_type not in ("XBPQ", "CSP") or not os.path.isdir(root):
            return set()
        result = set()

        def collect(bundle_path, value, field=""):
            if isinstance(value, dict):
                for key, item in value.items():
                    collect(bundle_path, item, str(key))
            elif isinstance(value, list):
                for item in value:
                    collect(bundle_path, item, field)
            elif isinstance(value, str) and self._looks_like_bundle_local_reference(
                bundle_path, value, field
            ):
                reference = self._resolve_bundle_reference(
                    bundle_path, value, field, with_md5=field == "jar"
                )
                dependency = self._site_reference_path(
                    reference, with_md5=field == "jar"
                )
                if dependency:
                    result.add(dependency)

        try:
            for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
                relative_dir = os.path.relpath(current, root)
                depth = 0 if relative_dir == "." else relative_dir.count(os.sep) + 1
                dirs[:] = [
                    name
                    for name in dirs
                    if not name.startswith(".")
                    and name.lower() not in self.SKIP_DIRS
                    and not os.path.islink(os.path.join(current, name))
                ]
                if depth >= self.max_scan_depth:
                    dirs[:] = []
                for name in files:
                    if not name.lower().endswith((".json", ".jsonc")):
                        continue
                    path = os.path.join(current, name)
                    if os.path.islink(path) or not os.path.isfile(path):
                        continue
                    try:
                        if os.path.getsize(path) > self.max_source_size:
                            continue
                        data = self._load_json_compatible(path)
                        if not isinstance(data, dict) or not isinstance(
                            data.get("sites"), list
                        ):
                            continue
                        collect(path, data.get("spider", ""), "jar")
                        collect(path, data["sites"])
                    except Exception:
                        continue
        except Exception:
            return result
        return result

    def _discover_json_jar_pairs(self, root, manifest_owned_paths):
        pairs = {}
        ambiguous = set()
        owned = set(manifest_owned_paths or ())
        try:
            for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
                relative_dir = os.path.relpath(current, root)
                depth = 0 if relative_dir == "." else relative_dir.count(os.sep) + 1
                dirs[:] = [
                    name
                    for name in dirs
                    if not name.startswith(".")
                    and name.lower() not in self.SKIP_DIRS
                    and not os.path.islink(os.path.join(current, name))
                ]
                if depth >= self.max_scan_depth:
                    dirs[:] = []
                jars = []
                rules = []
                for name in files:
                    path = os.path.join(current, name)
                    if os.path.islink(path) or not os.path.isfile(path):
                        continue
                    lower_name = name.lower()
                    real_path = os.path.realpath(path)
                    if lower_name.endswith(".jar"):
                        jars.append(real_path)
                    elif (
                        lower_name.endswith(".json")
                        and not self._is_site_manifest_name(lower_name)
                        and real_path not in owned
                    ):
                        rules.append(real_path)
                if not jars or not rules:
                    continue
                if len(jars) == 1:
                    for rule in rules:
                        pairs[rule] = jars[0]
                    continue
                jars_by_stem = {}
                for jar in jars:
                    stem = os.path.splitext(os.path.basename(jar))[0].lower()
                    jars_by_stem.setdefault(stem, []).append(jar)
                for rule in rules:
                    stem = os.path.splitext(os.path.basename(rule))[0].lower()
                    matches = jars_by_stem.get(stem, [])
                    if len(matches) == 1:
                        pairs[rule] = matches[0]
                    else:
                        ambiguous.add(rule)
        except Exception as exc:
            self._warn("JSON/JAR 配对扫描失败: {} ({})".format(root, exc))
        return pairs, ambiguous

    def _is_site_manifest_name(self, lower_name):
        value = str(lower_name or "").lower()
        return value == "site.json" or value.endswith(".site.json")

    def _adult_text_matches(self, value):
        text = str(value or "")
        lower = text.casefold()
        if any(symbol in text for symbol in self.ADULT_SYMBOLS):
            return True
        if any(keyword.casefold() in lower for keyword in self.ADULT_KEYWORDS):
            return True
        if self.ADULT_LATIN_PATTERN.search(text):
            return True
        if re.search(r"(?:^|[^0-9a-z])(?:adult|nsfw|xxx)(?:$|[^0-9a-z])", lower):
            return True
        if re.search(r"(?:^|[^0-9a-z])18(?:\+|xxx|av|j|禁)(?:$|[^0-9a-z])", lower):
            return True
        if re.search(r"(?:^|[^0-9a-z])av(?:$|[^0-9a-z])", lower):
            return True
        for token in re.findall(r"[a-z0-9]+", lower):
            if token.startswith("jav") and not token.startswith(
                ("java", "javascript")
            ):
                return True
        return False

    def _adult_content_matches(self, value):
        text = str(value or "")
        lower = text.casefold()
        if any(symbol in text for symbol in self.ADULT_SYMBOLS):
            return True
        strong_latin = bool(self.ADULT_LATIN_PATTERN.search(text))
        if re.search(r"(?:^|[^0-9a-z])18(?:\+|xxx|av|j|禁)(?:$|[^0-9a-z])", lower):
            return True
        keyword_hits = {
            keyword.casefold()
            for keyword in self.ADULT_KEYWORDS
            if keyword.casefold() in lower
        }
        weak_latin = bool(
            re.search(
                r"(?:^|[^0-9a-z])(?:adult|nsfw|xxx|av)(?:$|[^0-9a-z])",
                lower,
            )
        )
        return strong_latin or len(keyword_hits) + int(weak_latin) >= 2

    def _is_adult_source(self, source):
        site = source.get("csp_site", {})
        if isinstance(site, dict):
            for key in ("adult", "isAdult", "is_adult", "nsfw", "restricted18"):
                if key in site:
                    return self._as_bool(site.get(key), False)
            site_text = json.dumps(
                site, ensure_ascii=False, sort_keys=True, default=str
            )
            if self._adult_text_matches(site_text):
                return True

        values = [
            source.get("base_name", ""),
            os.path.basename(str(source.get("path", ""))),
        ]
        if not source.get("csp_site"):
            values.append(source.get("relative_in_root", ""))
        if any(self._adult_text_matches(value) for value in values):
            return True

        paths = list(source.get("dependencies", []))
        if not source.get("csp_site"):
            paths.append(source.get("path", ""))
        seen = set()
        for path in paths:
            real_path = os.path.realpath(str(path or ""))
            if not real_path or real_path in seen or not os.path.isfile(real_path):
                continue
            seen.add(real_path)
            if not real_path.lower().endswith(
                (".json", ".jsonc", ".py", ".js", ".html", ".htm", ".txt")
            ):
                continue
            try:
                text = self._read_text(real_path, 256 * 1024)
            except Exception:
                continue
            if "@tvbox-safe" in text.casefold():
                continue
            if "@tvbox-adult" in text.casefold() or self._adult_content_matches(text):
                return True
        return False

    def _is_excluded(self, source_type, lower_name, relative_in_root):
        relative_lower = relative_in_root.lower()
        if lower_name.startswith("."):
            return True
        if (
            source_type == "JS"
            and lower_name.endswith(".json")
            and not self._is_site_manifest_name(lower_name)
        ):
            return True
        if source_type == "JS" and lower_name in self.JS_EXCLUDE:
            return True
        if source_type == "PY":
            if lower_name == "__init__.py":
                return True
            if relative_lower in self.PY_EXCLUDE_RELATIVE:
                return True
        return False

    def _is_auto_loader_python(self, source_type, lower_name):
        return (
            source_type == "PY"
            and str(lower_name or "").startswith("自动加载")
            and str(lower_name or "").endswith(".py")
        )

    def _detect_file_role(self, source_type, lower_name, path):
        try:
            text = self._read_text(path, 64 * 1024)
        except Exception:
            text = ""
        lower_text = text.lower()

        if self._is_auto_loader_python(source_type, lower_name):
            return "source"
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
            looks_like_rule = self._has_quickjs_export(text)
            if looks_like_extension and not looks_like_rule:
                return "extension"
        return "source"

    def _resolve_site_reference(self, manifest_path, reference, with_md5=False):
        value = str(reference or "").strip()
        if not value:
            return ""
        suffix = ""
        source = value
        if with_md5 and ";md5;" in value:
            source, digest = value.split(";md5;", 1)
            source = source.strip()
            suffix = ";md5;" + digest.strip().lower()
        lower = source.lower()
        if lower.startswith(("http://", "https://", "assets://")):
            return source + suffix
        if lower.startswith("file://"):
            file_value = source[7:]
            if file_value.startswith(("./", "../")):
                path = os.path.join(os.path.dirname(manifest_path), file_value)
                return self._file_url(path) + suffix
            return source + suffix
        if os.path.isabs(source):
            return self._file_url(source) + suffix
        path = os.path.join(os.path.dirname(manifest_path), source)
        return self._file_url(path) + suffix

    def _site_reference_path(self, reference, with_md5=False):
        value = str(reference or "").strip()
        if with_md5:
            value = value.split(";md5;", 1)[0].strip()
        return self._reference_path(value)

    def _file_md5(self, path):
        digest = hashlib.md5()
        with open(path, "rb") as fp:
            while True:
                chunk = fp.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def _dex_u32(self, data, offset):
        if offset < 0 or offset + 4 > len(data):
            raise ValueError("DEX 索引越界")
        return int.from_bytes(data[offset : offset + 4], "little")

    def _dex_uleb128(self, data, offset):
        value = 0
        for shift in range(0, 35, 7):
            if offset >= len(data):
                raise ValueError("DEX ULEB128 越界")
            byte = data[offset]
            offset += 1
            value |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return value, offset
        raise ValueError("DEX ULEB128 格式无效")

    def _dex_defined_spider_classes(self, data):
        if len(data) < 0x70 or not data.startswith(b"dex\n"):
            raise ValueError("DEX 文件头无效")
        if self._dex_u32(data, 0x28) != 0x12345678:
            raise ValueError("DEX 字节序不受支持")
        string_ids_size = self._dex_u32(data, 0x38)
        string_ids_off = self._dex_u32(data, 0x3C)
        type_ids_size = self._dex_u32(data, 0x40)
        type_ids_off = self._dex_u32(data, 0x44)
        class_defs_size = self._dex_u32(data, 0x60)
        class_defs_off = self._dex_u32(data, 0x64)
        if string_ids_off + string_ids_size * 4 > len(data):
            raise ValueError("DEX string_ids 越界")
        if type_ids_off + type_ids_size * 4 > len(data):
            raise ValueError("DEX type_ids 越界")
        if class_defs_off + class_defs_size * 32 > len(data):
            raise ValueError("DEX class_defs 越界")

        result = set()
        prefix = b"Lcom/github/catvod/spider/"
        for index in range(class_defs_size):
            class_idx = self._dex_u32(data, class_defs_off + index * 32)
            if class_idx >= type_ids_size:
                raise ValueError("DEX class_idx 越界")
            descriptor_idx = self._dex_u32(
                data, type_ids_off + class_idx * 4
            )
            if descriptor_idx >= string_ids_size:
                raise ValueError("DEX descriptor_idx 越界")
            string_offset = self._dex_u32(
                data, string_ids_off + descriptor_idx * 4
            )
            _, value_offset = self._dex_uleb128(data, string_offset)
            end = data.find(b"\0", value_offset)
            if end < 0:
                raise ValueError("DEX 类描述符未终止")
            descriptor = data[value_offset:end]
            if descriptor.startswith(prefix) and descriptor.endswith(b";"):
                class_name = descriptor[len(prefix) : -1].decode(
                    "utf-8", errors="ignore"
                )
                if not class_name:
                    continue
                result.add(class_name.replace("/", "."))
        return result

    def _current_app_identity(self):
        if isinstance(self._app_identity_cache, tuple):
            return self._app_identity_cache
        package_name = ""
        app_label = ""
        try:
            from java import jclass

            context = None
            try:
                context = jclass(
                    "android.app.ActivityThread"
                ).currentApplication()
            except Exception:
                pass
            if context is None:
                try:
                    app_class = jclass("com.fongmi.android.tv.App")
                    for method_name in ("get", "getInstance", "instance"):
                        try:
                            method = getattr(app_class, method_name)
                            context = method() if callable(method) else method
                            if context is not None:
                                break
                        except Exception:
                            continue
                except Exception:
                    pass
            if context is not None:
                package_name = str(context.getPackageName()).strip()
                manager = context.getPackageManager()
                info = manager.getApplicationInfo(package_name, 0)
                app_label = str(manager.getApplicationLabel(info)).strip()
        except Exception:
            pass
        self._app_identity_cache = (package_name, app_label)
        return self._app_identity_cache

    def _host_supports_spider_api(self):
        if isinstance(self._host_spider_api_cache, bool):
            return self._host_spider_api_cache
        supported = False
        try:
            from java import jclass

            jclass("com.github.catvod.crawler.SpiderApi")
            spider_class = jclass("com.github.catvod.crawler.Spider")
            supported = any(
                str(method.getName()) == "initApi"
                for method in spider_class.getDeclaredMethods()
            )
        except Exception:
            supported = False
        self._host_spider_api_cache = bool(supported)
        return self._host_spider_api_cache

    def _decrypt_jar_guard_text(self, encoded, key_text):
        encrypted = base64.b64decode(encoded, validate=True)
        key = str(key_text).encode("utf-8")
        if len(key) not in (16, 24, 32) or not encrypted or len(encrypted) % 16:
            raise ValueError("AES 参数无效")
        try:
            from Crypto.Cipher import AES

            plain = AES.new(key, AES.MODE_CBC, key[:16]).decrypt(encrypted)
        except ImportError:
            from cryptography.hazmat.primitives.ciphers import (
                Cipher,
                algorithms,
                modes,
            )

            decryptor = Cipher(
                algorithms.AES(key), modes.CBC(key[:16])
            ).decryptor()
            plain = decryptor.update(encrypted) + decryptor.finalize()
        padding = plain[-1]
        if (
            padding < 1
            or padding > 16
            or plain[-padding:] != bytes([padding]) * padding
        ):
            raise ValueError("AES 填充无效")
        return plain[:-padding].decode("utf-8")

    def _inspect_dex_runtime_guard(self, dex_blobs):
        data = b"".join(dex_blobs)
        requires_spider_api = (
            b"Lcom/github/catvod/crawler/SpiderApi;" in data
            and b"initApi" in data
        )
        guard_markers = (
            b"getApplicationLabel" in data
            and b"getPackageName" in data
            and b"killProcess" in data
        )
        if not guard_markers:
            return {
                "forced_exit": False,
                "packages": set(),
                "labels": set(),
                "requires_spider_api": requires_spider_api,
            }

        decrypted = []
        key_text = "1234123412341234"
        if key_text.encode("ascii") in data:
            candidates = set(
                re.findall(rb"[A-Za-z0-9+/=]{32,4096}", data)
            )
            for candidate in candidates:
                if len(candidate) % 4:
                    continue
                try:
                    text = self._decrypt_jar_guard_text(candidate, key_text)
                    if text and all(
                        char in "\r\n\t" or ord(char) >= 32 for char in text
                    ):
                        decrypted.append(text)
                except Exception:
                    continue

        packages = set()
        labels = set()
        for text in decrypted:
            values = {
                item.strip()
                for item in text.split(",")
                if item.strip()
            }
            if len(values) < 2:
                continue
            if any("." in item and not any(ch.isspace() for ch in item) for item in values):
                packages.update(values)
            elif any(
                marker in values
                for marker in ("OK影视", "OK影视Pro", "TVBox", "影视仓")
            ):
                labels.update(values)
        exit_message = "⚠️加载失败，软件即将退出。"
        return {
            "forced_exit": exit_message in decrypted,
            "packages": packages,
            "labels": labels,
            "requires_spider_api": requires_spider_api,
        }

    def _jar_runtime_compatibility(self, inspection, api=""):
        guard = inspection.get("runtime_guard", {})
        if not isinstance(guard, dict):
            return True, ""
        if guard.get("forced_exit"):
            package_name, app_label = self._current_app_identity()
            packages = set(guard.get("packages", set()))
            labels = set(guard.get("labels", set()))
            if (
                package_name
                and app_label
                and package_name in packages
                and labels
                and app_label not in labels
            ):
                self.status["compatibility_blocked"] += 1
                return False, (
                    "JAR 内置应用名称校验不接受“{}”，运行后会主动结束 {}，"
                    "已阻止加载"
                ).format(app_label, self._app_mode_label())
        if (
            self.app_mode == self.APP_MODE_OKTV
            and api == "csp_XBPQ"
            and guard.get("requires_spider_api")
            and not self._host_supports_spider_api()
        ):
            self.status["compatibility_blocked"] += 1
            return False, (
                "该 XBPQ JAR 依赖 SpiderApi.initApi，当前 OK影视运行接口不支持，"
                "已阻止加载"
            )
        return True, ""

    def _inspect_local_jar(self, path):
        real_path = os.path.realpath(os.path.abspath(path))
        stat = os.stat(real_path)
        cache_key = (
            real_path,
            int(stat.st_size),
            int(
                getattr(
                    stat,
                    "st_mtime_ns",
                    int(stat.st_mtime * 1000000000),
                )
            ),
        )
        cached = self._jar_inspection_cache.get(cache_key)
        if isinstance(cached, dict):
            return cached
        if not zipfile.is_zipfile(real_path):
            raise ValueError("JAR 不是有效 ZIP: {}".format(real_path))
        with zipfile.ZipFile(real_path, "r") as archive:
            dex_entries = sorted(
                name
                for name in archive.namelist()
                if re.fullmatch(r"classes(?:[2-9][0-9]*)?\.dex", name)
            )
            if "classes.dex" not in dex_entries:
                raise ValueError("JAR 缺少 classes.dex: {}".format(real_path))
            remaining = self.MAX_JAR_DEX_SCAN_SIZE
            class_names = set()
            direct_classes = set()
            class_scan_complete = True
            dex_blobs = []
            for entry in dex_entries:
                info = archive.getinfo(entry)
                if remaining <= 0:
                    class_scan_complete = False
                    break
                read_limit = min(int(info.file_size), remaining)
                with archive.open(entry, "r") as dex_stream:
                    dex_data = dex_stream.read(read_limit + 1)
                if not dex_data.startswith(b"dex\n"):
                    raise ValueError(
                        "JAR 的 {} 格式无效: {}".format(entry, real_path)
                    )
                scanned = dex_data[:read_limit]
                remaining -= len(scanned)
                entry_complete = (
                    int(info.file_size) <= read_limit
                    and len(dex_data) <= read_limit
                )
                if not entry_complete:
                    class_scan_complete = False
                    continue
                dex_blobs.append(scanned)
                for class_name in self._dex_defined_spider_classes(scanned):
                    class_names.add(class_name)
                    if "." not in class_name and "$" not in class_name:
                        direct_classes.add(class_name)
        result = {
            "md5": self._file_md5(real_path),
            "classes": class_names,
            "direct_classes": direct_classes,
            "dex_entries": dex_entries,
            "class_scan_complete": class_scan_complete,
            "runtime_guard": self._inspect_dex_runtime_guard(dex_blobs),
        }
        self._jar_inspection_cache[cache_key] = result
        return result

    def _validate_site_jar(self, jar_reference, api=""):
        source, separator, expected_md5 = str(jar_reference).partition(";md5;")
        source = source.strip()
        expected_md5 = expected_md5.strip().lower() if separator else ""
        if expected_md5 and not re.fullmatch(r"[0-9a-f]{32}", expected_md5):
            raise ValueError("JAR md5 格式无效")
        lower = source.lower()
        if lower.startswith(("http://", "https://", "assets://")):
            return "远程或内置 JAR，等待 App 运行时确认"
        path = self._site_reference_path(source)
        if not path or not os.path.isfile(path) or not os.access(path, os.R_OK):
            raise ValueError("JAR 不存在或不可读: {}".format(source))
        inspection = self._inspect_local_jar(path)
        md5_detail = ""
        if expected_md5 and inspection["md5"] != expected_md5:
            md5_detail = "本地 JAR 声明 md5 不一致，已改用实际 md5"
        compatible, compatibility_detail = self._jar_runtime_compatibility(
            inspection, api
        )
        if not compatible:
            raise ValueError(compatibility_detail)
        class_name = api[len("csp_") :] if api.startswith("csp_") else ""
        confirmed = bool(class_name) and class_name in inspection["classes"]
        if confirmed:
            return "已确认 JAR 类 com.github.catvod.spider.{}{}{}".format(
                class_name,
                "；" + md5_detail if md5_detail else "",
                "；" + compatibility_detail if compatibility_detail else "",
            )
        if not class_name:
            return "JAR 结构有效{}".format(
                "；" + md5_detail if md5_detail else ""
            )
        if inspection["class_scan_complete"]:
            raise ValueError(
                "JAR 未包含类 com.github.catvod.spider.{}: {}".format(
                    class_name, path
                )
            )
        return "JAR 结构有效，类名未静态确认，等待 App 运行时验证{}".format(
            "；" + md5_detail if md5_detail else ""
        )

    def _auto_xbpq_site(self, rule_path, jar_path):
        valid, detail = self._validate_source("XBPQ", rule_path)
        if not valid:
            raise ValueError(detail)
        rule = self._load_json_compatible(rule_path)
        name = ""
        for field in ("站名", "name", "名称", "title"):
            value = rule.get(field) if isinstance(rule, dict) else ""
            if str(value or "").strip():
                name = str(value).strip()
                break
        if not name:
            name = os.path.splitext(os.path.basename(rule_path))[0]
        jar_reference = self._file_url(jar_path)
        jar_detail = self._validate_site_jar(jar_reference, "csp_XBPQ")
        jar_reference += ";md5;" + self._inspect_local_jar(jar_path)["md5"]
        site = {
            "name": name,
            "type": 3,
            "api": "csp_XBPQ",
            "ext": self._file_url(rule_path),
            "jar": jar_reference,
            "searchable": self.DEFAULT_SEARCHABLE,
            "quickSearch": self.DEFAULT_QUICK_SEARCH,
        }
        return site, [jar_path], jar_detail

    def _auto_csp_site(self, config_path, jar_path):
        config = self._load_json_compatible(config_path)
        if not isinstance(config, dict) or not config:
            raise ValueError("CSP 配置必须是非空 JSON 对象")

        config_stem = os.path.splitext(os.path.basename(config_path))[0]
        inspection = self._inspect_local_jar(jar_path)
        matching_classes = sorted(
            class_name
            for class_name in inspection["direct_classes"]
            if class_name.casefold() == config_stem.casefold()
        )
        if len(matching_classes) != 1:
            if not matching_classes:
                reason = "JAR 中未找到与 {} 匹配的顶层类".format(
                    config_stem
                )
            else:
                reason = "JAR 中匹配到多个顶层类: {}".format(
                    ", ".join(matching_classes)
                )
            raise ValueError(reason + "，请使用 site.json 显式配置 api")

        class_name = matching_classes[0]
        api = "csp_" + class_name
        jar_reference = (
            self._file_url(jar_path) + ";md5;" + inspection["md5"]
        )
        folder_name = os.path.basename(os.path.dirname(config_path)).strip()
        if not folder_name or folder_name.casefold() == "csp":
            folder_name = config_stem
        site = {
            "name": folder_name,
            "type": 3,
            "api": api,
            "ext": self._file_url(config_path),
            "jar": jar_reference,
            "searchable": self.DEFAULT_SEARCHABLE,
            "quickSearch": self.DEFAULT_QUICK_SEARCH,
        }
        if config.get("filters"):
            site["filterable"] = 1
        detail = "已根据 JSON 文件名确认 JAR 类 com.github.catvod.spider.{}".format(
            class_name
        )
        return site, [jar_path], detail

    def _parse_site_manifest(self, path, source_type):
        data = self._load_json_compatible(path)
        if not isinstance(data, dict):
            raise ValueError("站点清单顶层必须是 JSON 对象")
        if isinstance(data.get("site"), dict) and not data.get("api"):
            data = data["site"]
        site = copy.deepcopy(data)
        source_type = str(source_type or "").upper()
        api = str(site.get("api", "")).strip()
        dependencies = []
        validation_details = []
        if source_type == "JS":
            if not api:
                raise ValueError("JS 清单缺少 api")
            api_reference = self._resolve_site_reference(path, api)
            if ".js" not in api_reference.lower():
                raise ValueError("JS 清单 api 必须指向 .js 文件或URL")
            api_path = self._site_reference_path(api_reference)
            if api_path:
                if not os.path.isfile(api_path) or not os.access(api_path, os.R_OK):
                    raise ValueError("JS api 不存在或不可读: {}".format(api_reference))
                valid, detail = self._validate_source("JS", api_path)
                if not valid:
                    raise ValueError(detail)
                dependencies.append(api_path)
            site["api"] = api_reference
            validation_details.append("JS 清单有效")
        else:
            if not re.fullmatch(r"csp_[A-Za-z_$][A-Za-z0-9_.$]*", api):
                raise ValueError("{} api 必须是 csp_ 开头的有效类名".format(source_type))
            if source_type == "XBPQ" and api != "csp_XBPQ":
                raise ValueError("XBPQ 清单 api 必须是 csp_XBPQ")
            site["api"] = api
        jar_value = str(site.get("jar", "")).strip()
        if source_type in ("CSP", "XBPQ") and not jar_value:
            raise ValueError("{} 清单缺少 jar".format(source_type))
        if jar_value:
            jar_reference = self._resolve_site_reference(
                path, jar_value, with_md5=True
            )
            jar_detail = self._validate_site_jar(jar_reference, api)
            jar_path = self._site_reference_path(jar_reference, with_md5=True)
            if jar_path:
                actual_md5 = self._inspect_local_jar(jar_path)["md5"]
                jar_reference = (
                    jar_reference.split(";md5;", 1)[0].strip()
                    + ";md5;"
                    + actual_md5
                )
                dependencies.append(jar_path)
            site["jar"] = jar_reference
            validation_details.append(jar_detail)
        else:
            site.pop("jar", None)
        ext = site.get("ext", "")
        if isinstance(ext, str) and ext.strip():
            ext_reference = self._resolve_site_reference(path, ext)
            ext_path = self._site_reference_path(ext_reference)
            if ext_path:
                if not os.path.isfile(ext_path) or not os.access(ext_path, os.R_OK):
                    raise ValueError("{} ext 不存在或不可读: {}".format(source_type, ext_reference))
                if os.path.getsize(ext_path) <= 0:
                    raise ValueError("{} ext 是空文件: {}".format(source_type, ext_path))
                if ext_path.lower().endswith(".json"):
                    self._load_json_compatible(ext_path)
                if source_type == "XBPQ":
                    valid, detail = self._validate_source("XBPQ", ext_path)
                    if not valid:
                        raise ValueError(detail)
                dependencies.append(ext_path)
            site["ext"] = ext_reference
        elif ext not in (None, "") and not isinstance(ext, (dict, list)):
            raise ValueError("{} ext 必须是路径、URL或JSON对象".format(source_type))
        site["type"] = 3
        site.setdefault("searchable", self.DEFAULT_SEARCHABLE)
        site.setdefault("quickSearch", self.DEFAULT_QUICK_SEARCH)
        name = str(site.get("name", "")).strip()
        if not name:
            stem = os.path.basename(path)
            if stem.lower() == "site.json":
                stem = os.path.basename(os.path.dirname(path))
            elif stem.lower().endswith(".site.json"):
                stem = stem[: -len(".site.json")]
            fallback = api[len("csp_") :] if api.startswith("csp_") else "JS站点"
            site["name"] = stem or fallback
        return (
            site,
            list(dict.fromkeys(dependencies)),
            "；".join(item for item in validation_details if item),
        )

    def _validate_source(self, source_type, path):
        try:
            lower_name = os.path.basename(path).lower()
            if (
                source_type in ("JS", "XBPQ", "CSP")
                and self._is_site_manifest_name(lower_name)
            ):
                _, _, detail = self._parse_site_manifest(path, source_type)
                return True, detail
            if source_type == "XBPQ":
                data = self._load_json_compatible(path)
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
                if not self._has_quickjs_export(text):
                    return False, "JS 文件未发现 QuickJS 导出入口，已按不兼容规则或扩展跳过: {}".format(path)
            elif source_type == "HTML":
                text = self._read_text(path, 128 * 1024).lower()
                if not any(tag in text for tag in ("<!doctype html", "<html", "<body")):
                    return False, "HTML 文件未发现页面结构: {}".format(path)
        except Exception as exc:
            return False, "{} 文件检查失败: {} ({})".format(source_type, path, exc)
        return True, ""

    def _has_quickjs_export(self, text):
        return bool(
            re.search(
                r"\bexport\s+(?:default|(?:async\s+)?function|class|const|let|var|\{)",
                str(text or ""),
            )
            or "__jsEvalReturn" in str(text or "")
            or "__JS_SPIDER__" in str(text or "")
        )

    def _read_text(self, path, limit):
        with open(path, "rb") as fp:
            data = fp.read(limit)
        return data.decode("utf-8", errors="ignore")

    def _source_parent_suffix(self, source):
        path = os.path.realpath(
            os.path.abspath(os.path.expanduser(str(source.get("path", ""))))
        )
        parent = os.path.basename(os.path.dirname(path)).strip()
        if not parent:
            source_type = str(source.get("type", "")).upper()
            parent = self.TYPE_LABEL.get(source_type, source_type or "本地")
        parent = re.sub(r"[\r\n\t\[\]【】|]+", " ", parent)
        parent = re.sub(r"\s+", " ", parent).strip(" ._")
        return (parent or "本地")[:32]

    def _apply_display_names(self, sources):
        counts = {}
        folder_counts = {}
        for source in sources:
            identity = (source["type"], source["base_name"].lower())
            counts[identity] = counts.get(identity, 0) + 1
            folder = os.path.dirname(source["relative_in_root"]).replace(
                os.sep, "/"
            )
            folder_identity = identity + (folder.lower(),)
            folder_counts[folder_identity] = (
                folder_counts.get(folder_identity, 0) + 1
            )

        for source in sources:
            source_type = source["type"]
            base_name = source["base_name"]
            package_label = str(source.get("package_label", "")).strip()
            identity = (source_type, base_name.lower())
            duplicate_suffix = ""
            if counts.get(identity, 0) > 1:
                folder = os.path.dirname(source["relative_in_root"]).replace(os.sep, "/")
                folder_identity = identity + (folder.lower(),)
                if folder_counts.get(folder_identity, 0) > 1:
                    original_key = str(
                        source.get("csp_site", {}).get("key", "")
                        if isinstance(source.get("csp_site"), dict)
                        else ""
                    ).strip()
                    if "#bundle-site-" in source["identity"] and original_key:
                        disambiguator = original_key
                    else:
                        relative_name = os.path.basename(source["relative_in_root"])
                        disambiguator = os.path.splitext(relative_name)[0]
                else:
                    disambiguator = folder or os.path.basename(
                        source["scan_root"]
                    )
                duplicate_suffix = " · " + disambiguator
            parent_suffix = self._source_parent_suffix(source)
            source["name"] = (
                self.TYPE_PREFIX[source_type]
                + ("【{}】".format(package_label) if package_label else "")
                + base_name
                + duplicate_suffix
                + "|[{}]".format(parent_suffix)
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
        if source.get("csp_site"):
            manifest_site = copy.deepcopy(source.get("csp_site", {}))
            if not isinstance(manifest_site, dict):
                manifest_site = {}
            site.update(manifest_site)
            site["key"] = source["key"]
            site["name"] = source["name"]
            site["type"] = 3
            site.setdefault("searchable", self.DEFAULT_SEARCHABLE)
            site.setdefault("quickSearch", self.DEFAULT_QUICK_SEARCH)
        elif source_type == "PY":
            site.update({"api": file_ref})
        elif source_type == "JS":
            site.update(
                {
                    "api": file_ref,
                    "ext": "",
                }
            )
        elif source_type == "XBPQ":
            site.update(
                {
                    "api": self._runtime_reference(self.xbpq_api),
                    "ext": file_ref,
                    "jar": self._xbpq_jar_reference(),
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

    def _xbpq_runtime_status(self):
        jar = self._xbpq_jar_reference()
        if not jar:
            return False, (
                "XBPQ 已跳过：缺少 xbpqJar，请在 auto-loader.roots.json "
                "的 runtime 中配置包含 csp_XBPQ 的 JAR"
            )
        source = jar.split(";md5;", 1)[0].strip()
        lower = source.lower()
        if lower.startswith(("http://", "https://", "assets://")):
            return True, ""
        if lower.startswith("file://"):
            path = source[7:]
            if not os.path.isabs(path):
                path = os.path.join(self.STORAGE_ROOT, path)
        else:
            path = source
        if os.path.isfile(os.path.abspath(os.path.expanduser(path))):
            return True, ""
        return False, "XBPQ 已跳过：配置的 xbpqJar 不存在 ({})".format(source)

    def _xbpq_jar_reference(self):
        value = str(self.xbpq_jar or "").strip()
        if not value:
            return ""
        parts = value.split(";md5;", 1)
        reference = self._runtime_reference(parts[0].strip())
        if len(parts) == 1:
            return reference
        return reference + ";md5;" + parts[1].strip()

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
        return self._file_url(os.path.join(self.local_base_dir, value.lstrip("./")))

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
                if self.app_mode == self.APP_MODE_OKTV:
                    self._ok_write_generated_configs(registry)
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
                    "kind": self._registry_kind(source),
                    "site": site,
                }
            )

        generated_keys = {
            self._registry_item_key(item) for item in generated_items
        }
        preserved_count = 0
        for item in old_generated_items:
            key = self._registry_item_key(item)
            if key in generated_keys or not self._should_preserve_generated_item(item):
                continue
            generated_items.append(item)
            generated_keys.add(key)
            preserved_count += 1
        if preserved_count:
            self._warn(
                "{} 个旧站点因对应扫描目录暂时不可用而保留".format(
                    preserved_count
                )
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
        home_key = str(registry.get("homeKey", "")).strip()
        if home_key.startswith(self.GENERATED_KEY_PREFIX) and home_key not in generated_keys:
            registry["homeKey"] = ""
        old_map = {
            self._registry_item_key(item): self._registry_content_fingerprint(item)
            for item in old_generated_items
        }
        new_map = {
            self._registry_item_key(item): self._registry_content_fingerprint(item)
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

    def _registry_kind(self, source):
        if source.get("type") == "HTML":
            return "webHome"
        site = source.get("site", {})
        if not isinstance(site, dict):
            return "csp"
        has_home = bool(str(site.get("homePage", "")).strip())
        return "webHome" if has_home else "csp"

    def _generated_item_type(self, item):
        key = self._registry_item_key(item).lower()
        for source_type in self.TYPE_ORDER:
            if key.startswith(
                self.GENERATED_KEY_PREFIX.lower() + source_type.lower() + "_"
            ):
                return source_type
        return ""

    def _generated_item_reference(self, item, source_type):
        site = self._registry_item_site(item)
        if not isinstance(site, dict):
            return ""
        field = {
            "PY": "api",
            "JS": "api",
            "CSP": "jar",
            "XBPQ": "ext",
            "HTML": "homePage",
        }.get(source_type, "")
        return str(site.get(field, "")).strip() if field else ""

    def _should_preserve_generated_item(self, item):
        source_type = self._generated_item_type(item)
        if not source_type:
            return False
        if source_type in self.incomplete_scan_types:
            return True
        failed_same_type = any(
            item_type == source_type
            for item_type, _ in self.incomplete_scan_roots
        )
        reference = self._generated_item_reference(item, source_type)
        if not reference:
            return failed_same_type
        reference_value = reference.split(";md5;", 1)[0].strip()
        if not self._reference_path(reference_value):
            # 远程 JAR/assets 等引用无法反推出所属清单目录。只要同类型
            # 存在失败根目录，就保守保留旧项，避免临时权限故障删站点。
            return failed_same_type
        return self._scan_failure_covers_identity(
            source_type + "|" + reference_value
        )

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
                if self.app_mode == self.APP_MODE_OKTV:
                    self._ok_write_generated_configs(registry)
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

    def _restore_registry_file(self, backup_path):
        if not os.path.isfile(backup_path):
            raise ValueError("暂无可恢复的注册表备份")
        registry = self._validate_registry_backup(backup_path)
        current_path = os.path.abspath(os.path.expanduser(self.output_path))
        expected_token = self._registry_token(current_path)
        if os.path.isfile(current_path):
            self._create_registry_backup(current_path)
        self._atomic_write_json(
            registry,
            create_backup=False,
            expected_token=expected_token,
        )
        if self.app_mode == self.APP_MODE_OKTV:
            self._ok_write_generated_configs(registry)
        return len(registry.get("items", []))

    def _create_registry_backup(self, source_path):
        os.makedirs(self.backup_dir, exist_ok=True)
        backup_path = self._latest_backup_path()
        temp_path = backup_path + ".tmp"
        try:
            shutil.copy2(source_path, temp_path)
            self._validate_registry_backup(temp_path)
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
        valid_candidates = []
        for path in candidates:
            try:
                self._validate_registry_backup(path)
                valid_candidates.append(path)
            except Exception as exc:
                self._warn("忽略损坏的历史备份: {} ({})".format(path, exc))
        if not valid_candidates:
            return
        newest = max(
            valid_candidates,
            key=lambda path: (os.path.getmtime(path), os.path.basename(path)),
        )
        if os.path.abspath(newest) != os.path.abspath(latest_path):
            os.makedirs(os.path.dirname(latest_path), exist_ok=True)
            temp_path = latest_path + ".tmp"
            try:
                shutil.copy2(newest, temp_path)
                self._validate_registry_backup(temp_path)
                os.replace(temp_path, latest_path)
            finally:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
        self._remove_legacy_backup_files(keep=latest_path)

    def _validate_registry_backup(self, path):
        registry = self._read_config_file(path, "注册表备份")
        if "items" not in registry and isinstance(registry.get("sites"), list):
            registry = self._legacy_registry(registry)
        if not isinstance(registry.get("items"), list):
            raise ValueError("注册表备份的 items 必须是数组: {}".format(path))
        return registry

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
        if not os.path.isfile(path):
            return []
        try:
            self._validate_registry_backup(path)
            return [path]
        except Exception:
            return []

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
            "jar": site.get("jar", ""),
            "homePage": site.get("homePage", site.get("home_page", "")),
        }
        return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _registry_content_fingerprint(self, item):
        if not isinstance(item, dict):
            return ""
        return json.dumps(
            item, ensure_ascii=False, sort_keys=True, separators=(",", ":")
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

    def _diagnostic_log_path(self):
        return os.path.abspath(os.path.expanduser(self.log_path))

    def _log(self, level, message):
        """写入单文件诊断日志，仅在当前操作触发时执行。"""
        text = " ".join(str(message or "").split()).strip()
        if not text:
            return
        try:
            path = self._diagnostic_log_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            limit = max(16 * 1024, int(self.max_log_size))
            line = "{} [{}] {}\n".format(
                time.strftime("%Y-%m-%d %H:%M:%S"),
                str(level or "INFO").upper()[:10],
                text[:4000],
            ).encode("utf-8", errors="replace")
            if len(line) > limit // 2:
                line = line[: limit // 2].decode("utf-8", errors="ignore").encode("utf-8")
                line = line.rstrip(b"\n") + b"\n"

            current_size = os.path.getsize(path) if os.path.isfile(path) else 0
            if current_size + len(line) > limit:
                header = b"... earlier log entries truncated ...\n"
                keep = max(0, limit - len(header) - len(line))
                tail = b""
                if keep and os.path.isfile(path):
                    with open(path, "rb") as fp:
                        fp.seek(max(0, current_size - keep))
                        tail = fp.read(keep)
                    newline = tail.find(b"\n")
                    if newline >= 0:
                        tail = tail[newline + 1 :]
                    else:
                        tail = b""
                temp_path = path + ".tmp"
                try:
                    with open(temp_path, "wb") as fp:
                        fp.write(header)
                        fp.write(tail)
                    os.replace(temp_path, path)
                finally:
                    try:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    except Exception:
                        pass
            with open(path, "ab") as fp:
                fp.write(line)
        except Exception:
            # 诊断日志失败不应影响扫描和注册表写入。
            pass

    def _warn(self, text):
        if text and text not in self.status["warnings"]:
            self.status["warnings"].append(text)
            self._log("WARN", text)

    # --------------------------------------------------------------------------
    # TVBox 标准接口
    # --------------------------------------------------------------------------
    def homeContent(self, filter):
        self._ensure_initialized()
        classes = [{"type_id": "all", "type_name": "全部 ({})".format(len(self.cache["sources"]))}]
        for source_type in self.TYPE_ORDER:
            count = self.cache["type_counts"].get(source_type, 0)
            if count:
                classes.append(
                    {
                        "type_id": "type:" + source_type,
                        "type_name": "{} ({})".format(
                            self.TYPE_LABEL.get(source_type, source_type), count
                        ),
                    }
                )
        if self.cache["ignored"]:
            classes.append(
                {
                    "type_id": "ignored",
                    "type_name": "屏蔽 ({})".format(len(self.cache["ignored"])),
                }
            )
        classes.append(
            {
                "type_id": self.SCAN_SETTINGS_TID,
                "type_name": "设置" + (" *" if self.config_dirty else ""),
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
        status_name = "✅ 站点已合并" if ready else "ℹ 手动扫描模式"
        items = [
            {
                "vod_id": self.STATUS_ID,
                "vod_name": status_name,
                "vod_pic": "",
                "vod_remarks": "{} 个源 · {}".format(len(self.cache["sources"]), self.status["write_state"]),
            },
        ]
        enabled_download_sites = self._enabled_package_download_sites()
        if self._package_download_running():
            download_remarks = self._package_download_message or "正在批量下载或安装"
        elif self._package_download_state in ("partial", "incompatible", "error"):
            download_remarks = self._package_download_message[:140]
        elif enabled_download_sites:
            download_remarks = "已开启 {} 个：{}".format(
                len(enabled_download_sites),
                "、".join(
                    str(site.get("name", "本地包"))
                    for site in enabled_download_sites
                ),
            )
        else:
            download_remarks = "没有已开启站点，请到设置 → 下载站点开关中开启"
        items.append(
            {
                "vod_id": self.DOWNLOAD_PACKAGE_ID,
                "vod_name": "⬇ 一键下载本地包",
                "vod_pic": "",
                "vod_remarks": download_remarks,
                "action": self.ACTION_DOWNLOAD_PACKAGE,
            }
        )
        items.extend(
            [
            {
                "vod_id": self.RESCAN_ID,
                "vod_name": "⚡ 一键扫描并加载",
                "vod_pic": "",
                "vod_remarks": "扫描、写入 {} 配置并重载当前点播配置".format(
                    self._app_mode_label()
                ),
                "action": self.ACTION_RESCAN,
            },
            {
                "vod_id": self.TEST_SITES_ID,
                "vod_name": "✓ 测试站点连通性",
                "vod_pic": "",
                "vod_remarks": "仅点击时检测；受限只标记，疑似失效才写入忽略",
                "action": self.ACTION_TEST_SITES,
            },
            {
                "vod_id": self.RETEST_SITES_ID,
                "vod_name": "↻ 重新检测全部站点",
                "vod_pic": "",
                "vod_remarks": "清除检测缓存并分批复检",
                "action": self.ACTION_RETEST_SITES,
            },
            {
                "vod_id": self.CLEAR_SITES_ID,
                "vod_name": "🗑 清除自动站点",
                "vod_pic": "",
                "vod_remarks": "保留手工站点和扫描设置",
                "action": self.ACTION_CLEAR_SITES,
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
                "id": self.SCAN_BASE_PATH_ID,
                "name": "扫描目录",
                "type": "PATH",
                "relative_in_root": self.scan_base_path
                or "自动探测: {}".format(self.local_base_dir),
                "settings": True,
                "scan_base_path": True,
            },
            {
                "id": self.RESET_SCAN_BASE_ID,
                "name": "恢复默认目录",
                "type": "RESET_PATH",
                "relative_in_root": self.LOCAL_BASE_DIR,
                "settings": True,
                "reset_scan_base": True,
            },
            {
                "id": "setting_scan_types",
                "name": "扫描类型",
                "type": "TYPES",
                "relative_in_root": "已开启: {}".format(
                    ", ".join(
                        self.TYPE_LABEL.get(source_type, source_type)
                        for source_type in self.TYPE_ORDER
                        if self.pending_type_enabled.get(
                            source_type,
                            self.type_enabled.get(source_type, True),
                        )
                    )
                    or "无"
                ) + " · 18+:{}".format(
                    "屏蔽" if self.pending_block_adult_sites else "加载"
                ),
                "settings": True,
                "scan_types": True,
            },
            {
                "id": "setting_apply",
                "name": "应用并扫描"
                if self.config_dirty
                else "扫描并加载",
                "type": "APPLY",
                "relative_in_root": "扫描类型有待应用变更"
                if self.config_dirty
                else "使用当前设置扫描",
                "settings": True,
                "apply": True,
                "enabled": bool(self.config_dirty),
            },
            {
                "id": "setting_package_download_url",
                "name": "添加本地包网址",
                "type": "PACKAGE_DOWNLOAD_URL",
                "relative_in_root": "输入备注名和 ZIP 网址，保存时检测 · 当前 {} 个站点".format(
                    len(self.package_download_sites)
                ),
                "settings": True,
                "package_download_url": True,
            },
            {
                "id": "setting_package_download_switches",
                "name": "下载站点开关",
                "type": "PACKAGE_DOWNLOAD_SWITCHES",
                "relative_in_root": self._package_download_sites_summary(),
                "settings": True,
                "package_download_switches": True,
            },
            {
                "id": "setting_package_download_delete",
                "name": "删除下载站点",
                "type": "PACKAGE_DOWNLOAD_DELETE",
                "relative_in_root": "删除在线网址设置，不删除已解压本地包",
                "settings": True,
                "package_download_delete": True,
            },
            {
                "id": "setting_auto_scan",
                "name": "自动补扫",
                "type": "AUTO_SCAN",
                "relative_in_root": (
                    "已暂停（清除/恢复后），手动扫描一次即恢复"
                    if self.auto_scan_on_empty and self.auto_scan_suspended
                    else "无有效扫描快照时进入管理页自动扫描一次"
                ),
                "settings": True,
                "auto_scan": True,
                "enabled": bool(self.auto_scan_on_empty),
            },
        ]
        return items

    def _backup_items(self):
        items = []
        for path in self._list_backup_files():
            try:
                registry = self._validate_registry_backup(path)
                count = len(registry.get("items", []))
                modified = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(path))
                )
                items.append(
                    {
                        "id": "backup_" + self._digest(os.path.basename(path), 12),
                        "name": "撤销 " + modified,
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
        if source_id == self.DOWNLOAD_PACKAGE_ID or source_id.startswith(
            self.DOWNLOAD_PACKAGE_ID_PREFIX
        ):
            site_id = (
                source_id[len(self.DOWNLOAD_PACKAGE_ID_PREFIX) :]
                if source_id.startswith(self.DOWNLOAD_PACKAGE_ID_PREFIX)
                else ""
            )
            started, message = self._start_package_download(site_id)
            detail = self._status_detail()
            detail["vod_name"] = "一键下载本地包"
            detail["vod_remarks"] = message
            detail["vod_content"] = message + "\n\n" + detail.get(
                "vod_content", ""
            )
            return {"list": [detail]}
        if source_id == self.RESCAN_ID:
            allowed, duplicate_message = self._begin_manual_scan_request()
            if not allowed:
                detail = self._status_detail()
                detail["vod_remarks"] = duplicate_message
                detail["vod_content"] = duplicate_message + "\n\n" + detail.get(
                    "vod_content", ""
                )
                return {"list": [detail]}
            try:
                with self.lock:
                    if self._site_test_is_running():
                        detail = self._status_detail()
                        detail["vod_remarks"] = "站点正在后台检测"
                        detail["vod_content"] = (
                            "站点正在后台检测，请等本批完成后再重新扫描。\n\n"
                            + detail.get("vod_content", "")
                        )
                        return {"list": [detail]}
                    if self._refresh_locked(
                        allow_empty=not any(self.type_enabled.values())
                    ):
                        self._show_author_scan_surprise()
                        self._reload_app_vod_config(
                            expected_keys=self._generated_registry_keys()
                        )
                    self.inited = True
                return {"list": [self._status_detail()]}
            finally:
                self._finish_manual_scan_request()

        source = self.cache["source_index"].get(source_id)
        if not source:
            return {"list": [{"vod_name": "源不存在", "vod_content": "请重新扫描后再试。"}]}

        site_text = json.dumps(source["site"], ensure_ascii=False, indent=2)
        validation = source.get("validation") or "静态检查未发现明显问题"
        test_result = source.get("test_result", {})
        test_text = (
            "{} · {} · {}".format(
                self._test_result_label(test_result),
                test_result.get("checked_at", "-"),
                test_result.get("detail", ""),
            )
            if isinstance(test_result, dict) and test_result
            else "未检测"
        )
        content = (
            "类型: {type}\n"
            "文件: {path}\n"
            "相对路径: {relative}\n"
            "稳定标识: {identity}\n"
            "检查: {validation}\n\n"
            "连通性: {test_result}\n\n"
            "生成的站点配置:\n{site}\n\n"
            "目标环境: {app_mode}\n"
            "本地配置: {output}\n"
            "配置变更后，App 会主动重载站点列表。"
        ).format(
            type=self.TYPE_LABEL.get(source["type"], source["type"]),
            path=source["path"],
            relative=source["relative_in_root"],
            identity=source["identity"],
            validation=validation,
            test_result=test_text,
            site=site_text,
            app_mode=self._app_mode_label(),
            output=(
                "{} / {}".format(self.ok_config_a, self.ok_config_b)
                if self.app_mode == self.APP_MODE_OKTV
                else self.output_path
            ),
        )
        return {
            "list": [
                {
                    "vod_id": source_id,
                    "vod_name": source["name"],
                    "vod_pic": "",
                    "vod_remarks": self.TYPE_LABEL.get(
                        source["type"], source["type"]
                    ),
                    "vod_content": content,
                }
            ]
        }

    def _status_detail(self):
        warning_text = "\n".join("- " + item for item in self.status["warnings"][:20]) or "无"
        error_text = self.status["error"] or "无"
        test_counts = {"available": 0, "unavailable": 0, "limited": 0}
        for result in list(self.site_test_results.values()):
            state = str(result.get("state", "")) if isinstance(result, dict) else ""
            if state in test_counts:
                test_counts[state] += 1
        content = (
            "版本: {version}\n"
            "当前环境: {app_mode}\n"
            "扫描方式: 手动点击 + 进入自动补扫({auto_scan})\n"
            "严格识别: {strict}\n"
            "待应用配置: {dirty}\n"
            "分类开关: {types}\n"
            "18+站点: {adult_mode}\n"
            "扫描时间: {scan_time}\n"
            "发现文件: {found}\n"
            "有效源: {included}\n"
            "忽略源: {ignored}\n"
            "清理过期忽略项: {stale_ignored}\n"
            "跳过文件: {skipped}\n"
            "自动屏蔽18+站点: {adult_filtered}\n"
            "兼容性拦截: {compatibility_blocked}\n"
            "重复项: {duplicates}\n"
            "缓存命中/重检: {cache_hits}/{cache_misses}\n"
            "连通性检测: 可达 {test_available} · 结构无效 {test_unavailable} · 受限 {test_limited}\n"
            "保留注入项: {manual}\n"
            "自动注入项: {generated}\n"
            "变更预览: +{added} ~{updated} -{removed} ={unchanged}\n"
            "写入状态: {state}\n"
            "错误: {error}\n\n"
            "警告:\n{warnings}\n\n"
            "本地配置输出: {output}\n\n"
            "扫描开关设置: {settings}\n\n"
            "扫描目录配置: {roots_config}\n"
            "诊断日志: {log_path} (上限 {max_log_kb} KB)\n"
            "扫描根目录: {scan_base}\n"
            "XBPQ JAR: {xbpq_jar}\n"
            "下载站点开关: {package_download}\n"
            "本地包网址:\n{package_url}\n"
            "下载状态: {package_state}\n"
            "安装目录: {package_target}\n"
            "扫描上限: 文件 {max_files} · 深度 {max_depth} · 单文件 {max_size} bytes\n\n"
            "扫描结果已写入当前 App 的本地配置，原基础配置与手工注入项保留。\n"
            "配置变更会在当前操作返回后主动重载 App。\n\n"
            "----------------\n"
            "秋色正好，江 晚枫来过。"
        ).format(
            version=self.VERSION,
            app_mode=self._app_mode_label(),
            auto_scan="暂停"
            if self.auto_scan_on_empty and self.auto_scan_suspended
            else ("开" if self.auto_scan_on_empty else "关"),
            strict="开启" if self.strict_recognition else "关闭",
            dirty="是" if self.config_dirty else "否",
            types=" ".join(
                "{}:{}{}".format(
                    self.TYPE_LABEL.get(source_type, source_type),
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
                for source_type in self.TYPE_ORDER
            ),
            adult_mode="{}{}".format(
                "屏蔽" if self.block_adult_sites else "加载",
                " -> {}".format(
                    "屏蔽" if self.pending_block_adult_sites else "加载"
                )
                if self.pending_block_adult_sites != self.block_adult_sites
                else "",
            ),
            scan_time=self.status["scan_time"],
            found=self.status["found"],
            included=self.status["included"],
            ignored=self.status["ignored"],
            stale_ignored=self.status["stale_ignored_removed"],
            skipped=self.status["skipped"],
            adult_filtered=self.status["adult_filtered"],
            compatibility_blocked=self.status["compatibility_blocked"],
            duplicates=self.status["duplicates"],
            cache_hits=self.status["cache_hits"],
            cache_misses=self.status["cache_misses"],
            test_available=test_counts["available"],
            test_unavailable=test_counts["unavailable"],
            test_limited=test_counts["limited"],
            manual=self.status["manual_sites"],
            generated=self.status["generated_sites"],
            added=self.status["added_sites"],
            updated=self.status["updated_sites"],
            removed=self.status["removed_sites"],
            unchanged=self.status["unchanged_sites"],
            state=self.status["write_state"],
            error=error_text,
            warnings=warning_text,
            output=(
                "{} / {}".format(self.ok_config_a, self.ok_config_b)
                if self.app_mode == self.APP_MODE_OKTV
                else self.output_path
            ),
            settings=self.settings_path,
            roots_config=self.roots_config_path,
            log_path=self._diagnostic_log_path(),
            max_log_kb=max(1, int(self.max_log_size) // 1024),
            scan_base=self.scan_base_path or "自动探测 ({})".format(self.local_base_dir),
            xbpq_jar="已配置" if self.xbpq_jar else "未配置",
            package_download=self._package_download_sites_summary(),
            package_url="\n".join(
                "- {}: {}".format(item.get("name", "未命名"), item.get("url", ""))
                for item in self.package_download_sites
            ) or "- 无",
            package_state="{}{}".format(
                self._package_download_state,
                " · " + self._package_download_message
                if self._package_download_message
                else "",
            ),
            package_target=os.path.join(self._package_xbpq_root(), "下载站点备注名"),
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

    def _source_state_icon(self, source):
        if source.get("adult_blocked"):
            return "🔞 "
        result = source.get("test_result", {})
        state = str(result.get("state", "")) if isinstance(result, dict) else ""
        if state == "unavailable":
            return "⛔ "
        if state == "limited":
            return "⚠ "
        return "🚫 " if source.get("ignored") else ""

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
            if source.get("reset_scan_base"):
                return {
                    "vod_id": source["id"],
                    "vod_name": "↺ " + source["name"],
                    "vod_pic": "",
                    "vod_remarks": source["relative_in_root"],
                    "action": self.ACTION_RESET_SCAN_BASE,
                }
            if source.get("scan_base_path"):
                return {
                    "vod_id": source["id"],
                    "vod_name": "✎ " + source["name"],
                    "vod_pic": "",
                    "vod_remarks": source["relative_in_root"],
                    "action": self.ACTION_EDIT_SCAN_BASE,
                }
            if source.get("scan_types"):
                return {
                    "vod_id": source["id"],
                    "vod_name": "☷ " + source["name"],
                    "vod_pic": "",
                    "vod_remarks": source["relative_in_root"],
                    "action": self.ACTION_EDIT_SCAN_TYPES,
                }
            if source.get("package_download_url"):
                return {
                    "vod_id": source["id"],
                    "vod_name": "✎ " + source["name"],
                    "vod_pic": "",
                    "vod_remarks": source["relative_in_root"],
                    "action": self.ACTION_EDIT_DOWNLOAD_URL,
                }
            if source.get("package_download_switches"):
                return {
                    "vod_id": source["id"],
                    "vod_name": "☷ " + source["name"],
                    "vod_pic": "",
                    "vod_remarks": source["relative_in_root"],
                    "action": self.ACTION_EDIT_DOWNLOAD_SWITCHES,
                }
            if source.get("package_download_delete"):
                return {
                    "vod_id": source["id"],
                    "vod_name": "🗑 " + source["name"],
                    "vod_pic": "",
                    "vod_remarks": source["relative_in_root"],
                    "action": self.ACTION_DELETE_DOWNLOAD_SITES,
                }
            if source.get("apply"):
                return {
                    "vod_id": source["id"],
                    "vod_name": "⚡ " + source["name"],
                    "vod_pic": "",
                    "vod_remarks": source["relative_in_root"],
                    "action": self.ACTION_APPLY_SCAN_CONFIG,
                }
            if source.get("auto_scan"):
                enabled = bool(source.get("enabled"))
                return {
                    "vod_id": source["id"],
                    "vod_name": "{} {}".format(
                        "🟢" if enabled else "⚪", source["name"]
                    ),
                    "vod_pic": "",
                    "vod_remarks": "Toggle · {} · {}".format(
                        "已开启" if enabled else "已关闭",
                        source["relative_in_root"],
                    ),
                    "action": self.ACTION_TOGGLE_AUTO_SCAN,
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
        if source.get("adult_blocked"):
            ignore_action = "18+自动屏蔽 · 点击恢复"
        elif source.get("ignored"):
            ignore_action = "点击恢复"
        else:
            ignore_action = "点击忽略"
        return {
            "vod_id": source["id"],
            "vod_name": self._source_state_icon(source) + source["name"],
            "vod_pic": "",
            "vod_remarks": "{} · {} · {} · {}".format(
                source["type"],
                source["relative_in_root"],
                ignore_action,
                self._test_result_label(source.get("test_result")),
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
        self._log("INFO", "用户操作: {}".format(action))
        protected = (
            action not in (self.ACTION_TEST_SITES, self.ACTION_RETEST_SITES)
            and not action.startswith(self.ACTION_SOURCE_PREFIX)
        )
        if protected:
            with self.lock:
                if self._site_test_is_running():
                    return {
                        "code": 0,
                        "msg": "站点正在后台检测，请等本批完成后再修改扫描或屏蔽设置",
                    }
                if (
                    self._package_download_running()
                    and not self._is_package_download_action(action)
                ):
                    return {
                        "code": 0,
                        "msg": "本地包正在下载或安装，请完成后再修改配置",
                    }
                return self._action_impl(action)
        return self._action_impl(action)

    def _action_impl(self, action):
        if self._is_package_download_action(action):
            site_id = (
                action[len(self.ACTION_DOWNLOAD_PACKAGE_PREFIX) :]
                if action.startswith(self.ACTION_DOWNLOAD_PACKAGE_PREFIX)
                else ""
            )
            started, message = self._start_package_download(site_id)
            return {"code": 0, "msg": message}
        if action == self.ACTION_EDIT_DOWNLOAD_URL:
            opened, message = self._open_package_download_url_dialog()
            if not opened:
                self._log("WARN", "下载地址设置未打开: {}".format(message))
            return {"code": 0, "msg": "" if opened else message}
        if action in (
            self.ACTION_EDIT_DOWNLOAD_SWITCHES,
            self.ACTION_TOGGLE_DOWNLOAD,
        ):
            opened, message = self._open_package_download_switches_dialog()
            if not opened:
                self._log("WARN", "下载站点开关未打开: {}".format(message))
            return {"code": 0, "msg": "" if opened else message}
        if action == self.ACTION_DELETE_DOWNLOAD_SITES:
            opened, message = self._open_package_download_delete_dialog()
            if not opened:
                self._log("WARN", "下载站点删除界面未打开: {}".format(message))
            return {"code": 0, "msg": "" if opened else message}
        if action == self.ACTION_EDIT_SCAN_BASE:
            opened, message = self._open_scan_base_dialog()
            if not opened:
                self._log("WARN", "扫描路径设置未打开: {}".format(message))
            return {
                "code": 0,
                "msg": "" if opened else message,
            }
        if action == self.ACTION_RESET_SCAN_BASE:
            with self.lock:
                try:
                    self._set_scan_base_path("")
                    return {
                        "code": 0,
                        "msg": "扫描目录已初始化为: {}".format(
                            self.local_base_dir
                        ),
                    }
                except Exception as exc:
                    self._log("ERROR", "扫描目录初始化失败: {}".format(exc))
                    return {
                        "code": 0,
                        "msg": "扫描目录初始化失败：{}".format(exc),
                    }
        if action == self.ACTION_EDIT_SCAN_TYPES:
            opened, message = self._open_scan_types_dialog()
            if not opened:
                self._log("WARN", "扫描类型设置未打开: {}".format(message))
            return {
                "code": 0,
                "msg": "" if opened else message,
            }
        if action.startswith(self.ACTION_TOGGLE_IGNORE_PREFIX):
            source_id = action[len(self.ACTION_TOGGLE_IGNORE_PREFIX) :]
            source = self.cache["source_index"].get(source_id)
            if not source:
                return {"code": 0, "msg": "源不存在，请重新扫描"}
            with self.lock:
                identity = source["identity"]
                ignored = identity not in self.ignored_sources
                previous_ignored = set(self.ignored_sources)
                previous_manual_ignored = set(self.manual_ignored_sources)
                previous_auto_blocked = set(self.auto_blocked_sources)
                previous_adult_blocked = set(self.adult_blocked_sources)
                previous_adult_allowed = set(self.adult_allowed_sources)
                previous_results = dict(self.site_test_results)
                previous_cache = self.cache
                previous_status = self.status
                if ignored:
                    self.manual_ignored_sources.add(identity)
                else:
                    self.manual_ignored_sources.discard(identity)
                    self.auto_blocked_sources.discard(identity)
                    if source.get("adult_blocked") or (
                        self.block_adult_sites and self._is_adult_source(source)
                    ):
                        self.adult_allowed_sources.add(identity)
                    self.adult_blocked_sources.discard(identity)
                    self.site_test_results.pop(identity, None)
                self._sync_ignored_sources()
                try:
                    self._save_settings()
                    ok = self._refresh_locked(allow_empty=True)
                    if not ok:
                        raise ValueError(
                            self.status["error"] or self.status["write_state"]
                        )
                    _, detail = self._reload_app_vod_config(
                        expected_keys=self._generated_registry_keys()
                    )
                    return {
                        "code": 0,
                        "msg": "{}；{}".format(
                            "已忽略：{}".format(source["name"])
                            if ignored
                            else "已恢复：{}".format(source["name"]),
                            detail,
                        ),
                    }
                except Exception as exc:
                    self._log("ERROR", "忽略设置未生效: {}".format(exc))
                    self.ignored_sources = previous_ignored
                    self.manual_ignored_sources = previous_manual_ignored
                    self.auto_blocked_sources = previous_auto_blocked
                    self.adult_blocked_sources = previous_adult_blocked
                    self.adult_allowed_sources = previous_adult_allowed
                    self.site_test_results = previous_results
                    self.cache = previous_cache
                    self.status = previous_status
                    try:
                        self._save_settings()
                    except Exception:
                        pass
                    return {"code": 0, "msg": "忽略设置未生效：{}".format(exc)}
        if action.startswith(self.ACTION_SOURCE_PREFIX):
            source_id = action[len(self.ACTION_SOURCE_PREFIX) :]
            source = self.cache["source_index"].get(source_id)
            if not source:
                return {"code": 0, "msg": "源不存在，请重新扫描"}
            return {
                "code": 0,
                "msg": "{} · {}；已写入 {} 本地配置".format(
                    source["type"],
                    source["relative_in_root"],
                    self._app_mode_label(),
                ),
            }
        if action in (self.ACTION_TEST_SITES, self.ACTION_RETEST_SITES):
            with self._site_test_control_lock:
                worker = self._site_test_thread
                if worker is not None and worker.is_alive():
                    return {
                        "code": 0,
                        "msg": "站点正在后台检测，进度会逐站通知",
                    }
            with self.lock:
                if not self.cache["sources"] and not self.cache["ignored"]:
                    return {"code": 0, "msg": "暂无扫描结果，请先点击一键扫描并加载"}
            force = action == self.ACTION_RETEST_SITES
            if not self._start_site_test_worker(force=force):
                return {
                    "code": 0,
                    "msg": "站点正在后台检测，进度会逐站通知",
                }
            return {
                "code": 0,
                "msg": "已开始后台{}，本批最多 {} 个，进度会逐站通知".format(
                    "重新检测" if force else "连通性检测",
                    self.MAX_SITE_TESTS,
                ),
            }
        if action == self.ACTION_CLEAR_SITES:
            with self.lock:
                previous_ignored = set(self.ignored_sources)
                previous_manual_ignored = set(self.manual_ignored_sources)
                previous_auto_blocked = set(self.auto_blocked_sources)
                previous_adult_blocked = set(self.adult_blocked_sources)
                previous_adult_allowed = set(self.adult_allowed_sources)
                previous_results = dict(self.site_test_results)
                previous_cache = self.cache
                previous_status = self.status
                previous_retest_pending = list(self._retest_pending)
                previous_retest_auto_blocked = set(
                    self._retest_auto_blocked
                )
                previous_auto_scan_suspended = self.auto_scan_suspended
                try:
                    self.manual_ignored_sources.clear()
                    self.auto_blocked_sources.clear()
                    self.adult_blocked_sources.clear()
                    self.adult_allowed_sources.clear()
                    self.ignored_sources.clear()
                    self.site_test_results.clear()
                    self._retest_pending = []
                    self._retest_auto_blocked.clear()
                    self.auto_scan_suspended = True
                    self._save_settings()
                    removed = self._clear_generated_registry()
                    self._set_manual_idle_status(
                        "已清除 {} 个自动站点及扫描状态".format(removed)
                    )
                    self._clear_scan_cache_file()
                    _, detail = self._reload_app_vod_config(expected_keys=set())
                    self.inited = True
                    return {
                        "code": 0,
                        "msg": "已清除 {} 个自动站点、忽略状态和检测缓存，手工站点及类型配置已保留；{}".format(
                            removed,
                            detail,
                        ),
                    }
                except Exception as exc:
                    self._log("ERROR", "清除自动站点失败: {}".format(exc))
                    self.ignored_sources = previous_ignored
                    self.manual_ignored_sources = previous_manual_ignored
                    self.auto_blocked_sources = previous_auto_blocked
                    self.adult_blocked_sources = previous_adult_blocked
                    self.adult_allowed_sources = previous_adult_allowed
                    self.site_test_results = previous_results
                    self.cache = previous_cache
                    self.status = previous_status
                    self._retest_pending = previous_retest_pending
                    self._retest_auto_blocked = previous_retest_auto_blocked
                    self.auto_scan_suspended = previous_auto_scan_suspended
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
                    self._log("ERROR", "历史备份删除失败: {}".format(exc))
                    return {"code": 0, "msg": "历史备份删除失败：{}".format(exc)}
        if action.startswith(self.ACTION_RESTORE_SNAPSHOT_PREFIX):
            name = os.path.basename(
                action[len(self.ACTION_RESTORE_SNAPSHOT_PREFIX) :]
            )
            path = os.path.join(self.backup_dir, name)
            with self.lock:
                try:
                    if not name.startswith("registry-") or not name.endswith(".json"):
                        raise ValueError("历史备份名称无效")
                    count = self._restore_registry_file(path)
                    self._suspend_auto_scan()
                    self._set_manual_idle_status(
                        "已恢复历史备份，等待手动扫描"
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
                    self._log("ERROR", "历史备份恢复失败: {}".format(exc))
                    return {"code": 0, "msg": "历史备份恢复失败：{}".format(exc)}
        if action == self.ACTION_TOGGLE_AUTO_SCAN:
            with self.lock:
                previous_enabled = self.auto_scan_on_empty
                previous_suspended = self.auto_scan_suspended
                try:
                    self.auto_scan_on_empty = not previous_enabled
                    if self.auto_scan_on_empty:
                        self.auto_scan_suspended = False
                    self._save_settings()
                    return {
                        "code": 0,
                        "msg": "进入时自动补扫已{}".format(
                            "开启，无有效快照时进入管理页会自动扫描一次"
                            if self.auto_scan_on_empty
                            else "关闭，仅手动点击时扫描"
                        ),
                    }
                except Exception as exc:
                    self._log("ERROR", "自动补扫开关保存失败: {}".format(exc))
                    self.auto_scan_on_empty = previous_enabled
                    self.auto_scan_suspended = previous_suspended
                    return {"code": 0, "msg": "自动补扫开关保存失败：{}".format(exc)}
        if action.startswith(self.ACTION_TOGGLE_TYPE_PREFIX):
            source_type = action[len(self.ACTION_TOGGLE_TYPE_PREFIX) :].upper()
            if source_type not in self.TYPE_ORDER:
                return {"code": 0, "msg": "未知站点类型"}
            with self.lock:
                previous = self.pending_type_enabled.get(
                    source_type, self.type_enabled.get(source_type, True)
                )
                try:
                    self._set_pending_type_settings(
                        {source_type: not previous}
                    )
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
                    self._log("ERROR", "分类开关保存失败: {}".format(exc))
                    return {"code": 0, "msg": "分类开关保存失败：{}".format(exc)}
        if action == self.ACTION_APPLY_SCAN_CONFIG:
            action = self.ACTION_RESCAN
        if action != self.ACTION_RESCAN:
            return {"code": 0, "msg": "未知操作"}
        allowed, duplicate_message = self._begin_manual_scan_request()
        if not allowed:
            return {"code": 0, "msg": duplicate_message}
        try:
            with self.lock:
                if self.config_dirty:
                    try:
                        self._apply_pending_type_settings()
                    except Exception as exc:
                        self._log("ERROR", "扫描配置应用失败: {}".format(exc))
                        return {"code": 0, "msg": "扫描配置应用失败：{}".format(exc)}
                ok = self._refresh_locked(
                    allow_empty=not any(self.type_enabled.values())
                )
                self.inited = True
                if ok:
                    self._show_author_scan_surprise()
                    _, detail = self._reload_app_vod_config(
                        expected_keys=self._generated_registry_keys()
                    )
                    if self.status["compatibility_blocked"]:
                        message = (
                            "兼容检查完成：已拦截 {} 个会导致退出或接口不兼容的站点，"
                            "当前加载 {} 个源；{}"
                        ).format(
                            self.status["compatibility_blocked"],
                            len(self.cache["sources"]),
                            detail,
                        )
                    else:
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
                    message = "扫描未完成：{}".format(
                        self.status["error"] or self.status["write_state"]
                    )
                return {"code": 0, "msg": message}
        finally:
            self._finish_manual_scan_request()

    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "url": "",
            "header": {},
            "msg": "这是配置管理条目，不能作为媒体播放。",
        }

    def destroy(self):
        self._destroyed = True
        self._site_test_cancel.set()
        return "destroy"
