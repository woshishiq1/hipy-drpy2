# -*- coding: utf-8 -*-
# @version v6.0 - 统一 UI 设计系统重构：全界面风格统一 / 按钮自动换行等宽 / 字号与弹窗尺寸按屏幕 dp 自适应（手机·平板·电视）
# @author 陆小凤 (最终版)

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

BOOL_MAP = {'是': True, '否': False, '下载': True, '不下载': False,
            'true': True, 'false': False, '1': True, '0': False, True: True, False: False}

# ========================= 解密模块 =========================
# =====================================================================
#                    统一 UI 设计系统（UIKit）
# ---------------------------------------------------------------------
# 设计目标（解决"界面不统一 / 不美观 / 按钮文字分布不合理 / 不适应各种屏幕"）：
#
#   1. 单一风格来源：所有颜色、圆角、间距、字号、控件尺寸都在 UITheme 中定义，
#      业务代码一律通过 UIKit 取用，禁止再写死 #RRGGBB，保证弹窗风格完全一致。
#   2. 屏幕自适应：以 dp 为唯一单位，并依据"屏幕 dp 宽度 + 设备类型
#      （手机 / 平板 / 电视）+ 横竖屏"自动计算整体缩放系数 scale，
#      从 5 寸手机到 4K 电视都能得到合适的字号与控件大小。
#   3. 按钮分布：button_bar 自动换行 + 等宽填充（weight=1），
#      按钮再多也不会溢出屏幕，也不会出现大小不一、挤成一条的情况。
#   4. 弹窗尺寸：宽度按 dp 上限收敛（电视不会拉成一条超宽横幅），
#      高度可选自适应或按比例并设 dp 上限。
#
# 兼容性：所有 JNI 调用都做了异常兜底，取不到就用纯色/默认实现，
#         老版本 Android、不同 ROM、不同分辨率下都不会崩溃。
# =====================================================================

class UITheme(object):
    """静态设计令牌：颜色 / 圆角 / 间距 / 字号 / 控件尺寸。"""

    # ---------------- 品牌色 ----------------
    BRAND = "#6C63FF"
    BRAND_DEEP = "#5449E0"
    BRAND_SOFT = "#EFEDFF"
    BRAND_LINE = "#CDC7FF"

    # ---------------- 语义色 ----------------
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

    # ---------------- 中性色 ----------------
    BG = "#F2F4F9"
    SURFACE = "#FFFFFF"
    SURFACE_ALT = "#F8FAFC"
    SURFACE_SUNKEN = "#F1F5F9"
    BORDER = "#E4E8F0"
    BORDER_STRONG = "#CBD5E1"

    # ---------------- 文字色 ----------------
    TEXT = "#1E293B"
    TEXT_2 = "#475569"
    TEXT_3 = "#94A3B8"
    WHITE = "#FFFFFF"

    # ---------------- 圆角（dp） ----------------
    R_XS = 4.0
    R_SM = 6.0
    R_MD = 10.0
    R_LG = 14.0
    R_XL = 18.0
    R_PILL = 999.0

    # ---------------- 间距（dp） ----------------
    S_XXS = 2.0
    S_XS = 4.0
    S_SM = 8.0
    S_MD = 12.0
    S_LG = 16.0
    S_XL = 24.0

    # ---------------- 字号（sp，基准值，会乘以 UIKit.scale） ----------------
    FS_MICRO = 9.5
    FS_CAPTION = 11.0
    FS_BODY = 12.5
    FS_BODY_LG = 13.5
    FS_SUBTITLE = 15.0
    FS_TITLE = 17.0

    # ---------------- 控件尺寸（dp） ----------------
    H_BTN_SM = 34.0
    H_BTN = 42.0
    H_BTN_LG = 48.0
    H_INPUT = 44.0

    # ---------------- 按钮风格 ----------------
    #   风格名 -> (常态底色, 文字色, 描边色, 按下/聚焦色)
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

    # 旧代码里散落的硬编码颜色 -> 统一风格（兼容历史调用点）
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
    """绑定到某个 Activity 的 UI 工具箱。

    每次弹窗都会创建一个新的 UIKit（构造成本极低），它负责：
      * dp / px 换算与自适应缩放
      * 所有可复用组件的构造（文本、输入框、按钮、卡片、开关行、空状态…）
      * 事件监听器的生命周期托管（统一塞进 sink 列表，防止被 GC 回收后崩溃）
    """

    def __init__(self, act, sink=None):
        self.act = act
        self.sink = sink if sink is not None else []
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
        # 一行最多放几个按钮（按钮栏自动换行用）
        if self.kind == "tv":
            self.max_cols = 4
        elif self.kind == "tablet":
            self.max_cols = 4
        elif self.landscape:
            self.max_cols = 4
        else:
            self.max_cols = 3
        # 弹窗尺寸上限（dp）—— 防止 4K 电视上被拉成超宽横幅
        if self.kind == "tv":
            self.max_w_dp, self.max_h_dp = 880.0, 660.0
        elif self.kind == "tablet":
            self.max_w_dp, self.max_h_dp = 660.0, 700.0
        else:
            self.max_w_dp, self.max_h_dp = 470.0, 720.0

    # ------------------------------------------------------------------
    # 设备识别与自适应缩放
    # ------------------------------------------------------------------
    def _detect_kind(self, act):
        """判断设备类型：tv / tablet / phone。"""
        # 1) UiModeManager（官方判定 Android TV 的方式）
        try:
            svc = act.getSystemService("uimode")
            if svc is not None and int(svc.getCurrentModeType()) == 4:
                return "tv"
        except Exception:
            pass
        # 2) Configuration.uiMode 低位
        try:
            cfg = act.getResources().getConfiguration()
            if int(getattr(cfg, "uiMode", 0) & 15) == 4:
                return "tv"
        except Exception:
            pass
        # 3) 尺寸兜底：横屏且超宽 -> 电视，宽屏 -> 平板
        if self.w_dp >= 900 and self.landscape:
            return "tv"
        if self.w_dp >= 600:
            return "tablet"
        return "phone"

    def _compute_scale(self):
        """整体缩放系数：以 360dp 宽为基准 1.0。

        手机：0.90 ~ 1.20（小屏略缩，大屏略放）
        平板：1.00 ~ 1.28
        电视：1.22 ~ 1.60（观看距离远，必须整体放大）
        """
        short_dp = min(self.w_dp, self.h_dp)
        s = short_dp / 360.0
        s = min(max(s, 0.90), 1.20)
        if self.kind == "tv":
            s = min(max(s * 1.30, 1.22), 1.60)
        elif self.kind == "tablet":
            s = min(max(s * 1.08, 1.00), 1.28)
        return s

    # ------------------------------------------------------------------
    # 基础工具
    # ------------------------------------------------------------------
    def j(self, name):
        if not self._java_ok:
            return None
        return self._jclass(name)

    def dp(self, value):
        """dp -> px。失败时按 density 估算。"""
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
        """设计字号 -> 实际 sp（已按屏幕缩放）。TextView.setTextSize(float) 单位就是 sp。"""
        return float(size) * self.scale

    def gravity(self):
        return self.j("android.view.Gravity")

    def typeface(self):
        return self.j("android.graphics.Typeface")

    def _ellipsize(self, view):
        """超长文本尾省略，避免长路径把布局撑破。"""
        try:
            TA = self.j("android.text.TextUtils$TruncateAt")
            if TA is not None:
                view.setEllipsize(TA.END)
        except Exception:
            pass

    def lp(self, w=-1, h=-2, weight=0.0, margins=None):
        """LinearLayout.LayoutParams 快捷构造。margins=(left, top, right, bottom) 单位 dp。"""
        LP = self.j("android.widget.LinearLayout$LayoutParams")
        p = LP(w, h, float(weight))
        if margins:
            l, t, r, b = margins
            p.setMargins(self.dp(l), self.dp(t), self.dp(r), self.dp(b))
        return p

    # ------------------------------------------------------------------
    # 图形
    # ------------------------------------------------------------------
    def shape(self, solid, radius_dp=UITheme.R_MD, stroke_dp=0.0, stroke=None):
        """圆角矩形纯色/描边背景。"""
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
        """带"按下 / 遥控器聚焦"反馈的背景；不支持时退回普通圆角背景。"""
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

    # ------------------------------------------------------------------
    # 容器
    # ------------------------------------------------------------------
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
        """统一的卡片容器，列表项 / 分区都用它。"""
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

    # ------------------------------------------------------------------
    # 文本
    # ------------------------------------------------------------------
    def text(self, txt, size=UITheme.FS_BODY, color=UITheme.TEXT, bold=False,
             gravity=None, single_line=False, max_lines=0, mono=False,
             line_spacing=1.25, selectable=False, pad=None):
        """统一文本组件。

        gravity 传 Gravity 常量组合；single_line / max_lines 会自动加尾省略号，
        这样长路径、长 URL 在任何屏幕上都不会把行高撑爆。
        """
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
        """分区标题：品牌色竖条 + 加粗标题（+ 可选说明）。"""
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

    def hint(self, txt):
        return self.text(txt, size=UITheme.FS_CAPTION, color=UITheme.TEXT_3,
                         line_spacing=1.4, max_lines=6,
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

    # ------------------------------------------------------------------
    # 输入框
    # ------------------------------------------------------------------
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
            self._ellipsize(et)
        else:
            et.setSingleLine(True)
            self._ellipsize(et)
            if G:
                et.setGravity(G.CENTER_VERTICAL | G.START)
        try:
            if min_height:
                et.setMinHeight(self.dp(min_height))
            else:
                et.setMinHeight(self.dp(UITheme.H_INPUT) if not multiline else 0)
        except Exception:
            pass
        self._set_bg(et, self.shape(UITheme.SURFACE_ALT, UITheme.R_MD, 1.0, UITheme.BORDER))
        try:
            if value:
                et.setSelection(len(str(value)))
        except Exception:
            pass
        return et

    # ------------------------------------------------------------------
    # 开关
    # ------------------------------------------------------------------
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
        if weight:
            sw.setLayoutParams(self.lp(0, -2, float(weight)))
        return sw

    def switch_card(self, label, sub=None, checked=False, on_change=None, on_long_click=None):
        """卡片式开关行：左侧文字（可带副标题），右侧开关。用于设置项。"""
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
        return card

    # ------------------------------------------------------------------
    # 按钮
    # ------------------------------------------------------------------
    def button(self, label, style="secondary", on_click=None, dialog_ref=None, size="md"):
        """统一按钮。style 见 UITheme.STYLES；size: sm / md / lg。"""
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
        try:
            btn.setFocusable(True)
            btn.setFocusableInTouchMode(True)
        except Exception:
            pass
        if on_click is not None or dialog_ref is not None:
            btn.setOnClickListener(self._on_click(on_click, dialog_ref))
        return btn

    def button_bar(self, specs, size="md", per_row=None, gap=UITheme.S_XS):
        """按钮栏：自动换行 + 等宽填充。

        specs 元素支持两种写法：
          1) dict: {"text":.., "style":.., "callback":.., "dismiss":True}
          2) dict（旧格式）: {"text":.., "color":"#6C63FF", "callback":.., "is_primary":True}
        返回：垂直容器，内部按行均分，任何屏幕宽度都不会溢出。
        """
        if not specs:
            return None
        n = len(specs)
        cols = per_row or self._best_cols(n, self.max_cols)
        h_px = self.dp({"sm": UITheme.H_BTN_SM, "lg": UITheme.H_BTN_LG}.get(size, UITheme.H_BTN))
        outer = self.vbox()
        outer.setLayoutParams(self.lp(-1, -2))
        i = 0
        while i < n:
            chunk = specs[i:i + cols]
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
            i += cols
        return outer

    def _best_cols(self, n, max_cols):
        """为 n 个按钮挑选最美观的列数（优先能整除，避免出现孤零零一个按钮的行）。"""
        if n <= 0:
            return 1
        cap = min(max_cols, n)
        for c in range(cap, 1, -1):
            if n % c == 0:
                return c
        return cap

    @staticmethod
    def spec_style(spec):
        """把（可能来自旧代码的）按钮描述转换成统一的 style 名。"""
        if not isinstance(spec, dict):
            return "secondary"
        if spec.get("style"):
            return spec["style"]
        c = str(spec.get("color") or "").strip().upper()
        if c in UITheme.LEGACY_COLOR_MAP:
            return UITheme.LEGACY_COLOR_MAP[c]
        return "primary" if spec.get("is_primary") else "secondary"

    # ------------------------------------------------------------------
    # 事件监听（统一托管到 sink，防止被 GC 后 JNI 崩溃）
    # ------------------------------------------------------------------
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
                if cb:
                    try:
                        cb()
                    except Exception:
                        traceback.print_exc()

        listener = _Click()
        self.sink.append(listener)
        return listener

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

    def bind_click(self, view, cb, dialog_ref=None):
        if view is None:
            return None
        listener = self._on_click(cb, dialog_ref)
        view.setOnClickListener(listener)
        return listener

    # ------------------------------------------------------------------
    # 系统能力
    # ------------------------------------------------------------------
    def toast(self, msg, long=False):
        try:
            Toast = self.j("android.widget.Toast")
            Toast.makeText(self.act, str(msg),
                           Toast.LENGTH_LONG if long else Toast.LENGTH_SHORT).show()
        except Exception:
            pass

    def copy(self, text, label="文本"):
        """复制到剪贴板，成功返回 True。"""
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

    # ------------------------------------------------------------------
    # 弹窗
    # ------------------------------------------------------------------
    def dialog(self, title=None, content=None, buttons=None, width_ratio=0.92,
               height_ratio=0.85, back_callback=None, scroll=True, on_dismiss=None,
               closable=True):
        """统一样式的对话框：标题栏（品牌色竖条 + 标题 + 返回/关闭）/
           可滚动内容区 / 底部按钮栏。

        height_ratio <= 0 表示高度自适应内容（WRAP_CONTENT）。
        """
        Builder = self.j("android.app.AlertDialog$Builder")
        holder = {"dialog": None}

        # 先确定哪些按钮需要在点击后关闭弹窗（必须在创建按钮之前写回 spec，
        # 否则按钮拿不到 dialog_ref，点了不会关闭）
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
        root.setLayoutParams(self.lp(-1, -2))

        # ---------- 标题栏 ----------
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

        # ---------- 内容区 ----------
        if content is not None:
            body = content
            if scroll:
                body = self.scroll(content)
            body.setPadding(self.dp(UITheme.S_LG), self.dp(UITheme.S_MD),
                            self.dp(UITheme.S_LG), self.dp(UITheme.S_MD))
            root.addView(body, self.lp(-1, 0, 1.0))

        # ---------- 底部按钮栏 ----------
        if buttons:
            root.addView(self.divider(color=UITheme.BORDER))
            footer = self.vbox(pad=(UITheme.S_LG, UITheme.S_MD, UITheme.S_LG, UITheme.S_LG))
            footer.setLayoutParams(self.lp(-1, -2))
            bar = self.button_bar(buttons, size="md")
            if bar is not None:
                footer.addView(bar, self.lp(-1, -2))
            root.addView(footer, self.lp(-1, -2))

        # ---------- 构建 ----------
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
        """按 dp 上限收敛的弹窗尺寸：手机 / 平板 / 电视都不会变形。"""
        try:
            window = dialog.getWindow()
            if window is None:
                return
            # 透明窗口背景，保证圆角卡片不被系统默认背景盖住
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

def try_decrypt_content(content, url='', external_api_url=DEFAULT_EXTERNAL_API_URL, session=None, max_rounds=5):
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

# ========================= 辅助函数 =========================
def clean_preroll_m3u8(content: str) -> str:
    lines = content.splitlines(keepends=True)
    out = []
    start_output = False
    for line in lines:
        s = line.strip()
        if s == "#EXT-X-DISCONTINUITY":
            start_output = True
            continue
        if start_output:
            out.append(line)
    if not start_output:
        return content
    return "".join(out)

def parse_curl_command(curl_str: str):
    import shlex
    url = ""
    headers = {}
    try:
        parts = shlex.split(curl_str)
        for i, p in enumerate(parts):
            if p.startswith("http://") or p.startswith("https://"):
                url = p
            elif p in ("-H", "--header") and i + 1 < len(parts):
                header_str = parts[i + 1]
                if ":" in header_str:
                    k, v = header_str.split(":", 1)
                    headers[k.strip()] = v.strip()
    except Exception:
        pass
    return url, headers

def _encode_url(url):
    if not url:
        return url
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.encode('idna').decode('ascii') if parsed.netloc else ''
        path = urllib.parse.quote(parsed.path, safe='/') if parsed.path else ''
        query = urllib.parse.quote(parsed.query, safe='=&?') if parsed.query else ''
        encoded = urllib.parse.urlunparse((parsed.scheme, netloc, path, parsed.params, query, parsed.fragment))
        return encoded
    except Exception:
        return url

# ========================= 文件下载器 =========================
class FileDownloader:
    SKIP_EXTS = {'.php', '.asp', '.jsp', '.cgi', '.exe', '.dll', '.sh', '.bat'}
    BINARY_EXTS = {'.jar', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.m3u', '.m3u8', '.mp4', '.ts'}
    DOWNLOAD_EXTS = DOWNLOAD_EXTS

    def __init__(self, output_dir, config=None, log_callback=None, progress_callback=None, cancel_event=None):
        self.output_dir = output_dir
        self.config = config or {}
        self.log_callback = log_callback or (lambda msg: None)
        self.progress_callback = progress_callback or (lambda msg: None)
        self.cancel_event = cancel_event
        self.downloaded = {}
        self.failed = []
        self.skipped = []
        self._lock = threading.Lock()
        self._processed = set()

        if 'download' in self.config:
            cfg_download = self.config.get('download', {})
        else:
            cfg_download = self.config

        self.overwrite = cfg_download.get('overwrite', False)
        self.timeout = (cfg_download.get('timeout_connect', 10), cfg_download.get('timeout_read', 60))
        self.chunk_size = cfg_download.get('chunk_size', 8192)
        self.max_size = self.config.get('max_file_size_mb', 100) * 1024 * 1024
        self.skip_exts = set(self.config.get('skip_extensions', []))
        self.skip_exts.update(self.SKIP_EXTS)
        self.skip_patterns = self.config.get('skip_patterns', [])
        self.decrypt_enabled = cfg_download.get('decrypt', {}).get('enabled', True)
        self.external_api = cfg_download.get('decrypt', {}).get('external_api_url', '')
        self.proxy = self.config.get('proxy', '')
        self.github_proxy = self.config.get('github_proxy', GITHUB_PROXY)
        self.user_agent = self.config.get('user_agent', DEFAULT_USER_AGENT)
        self.category_map = cfg_download.get('category_map', {'js': '.js', 'lib': '.json', 'py': '.py', 'jar': '.jar'})
        self.skip_patterns_core = cfg_download.get('skip_patterns_core', SKIP_PATTERNS)
        self.max_workers = cfg_download.get('max_workers', 8)
        self.retry_total = cfg_download.get('retry_total', 2)
        self.retry_backoff = cfg_download.get('retry_backoff', 0.3)
        self.pool_connections = cfg_download.get('pool_connections', 10)
        self.pool_maxsize = cfg_download.get('pool_maxsize', 20)

        self.session = requests.Session()
        retry = Retry(total=self.retry_total, backoff_factor=self.retry_backoff, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry, pool_connections=self.pool_connections, pool_maxsize=self.pool_maxsize)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
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

    def _log(self, msg):
        if self.log_callback:
            self.log_callback(msg)

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

    def normalize_github_url(self, url):
        if not url:
            return url
        if self.github_proxy:
            proxy_prefix = self.github_proxy.rstrip('/') + '/'
            if url.startswith(proxy_prefix):
                url = url[len(proxy_prefix):]
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
        if self.github_proxy and self._is_github_file_url(url):
            if not url.startswith(self.github_proxy):
                proxy = self.github_proxy.rstrip('/') + '/'
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                url = proxy + url.lstrip('/')
        return url

    def split_url_and_suffix(self, url):
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

    def is_downloadable(self, url, field_key=None):
        if not url or not isinstance(url, str):
            return False
        url_clean = url.strip()
        if not url_clean:
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
        if ext in self.SKIP_EXTS:
            return False
        if ext in self.DOWNLOAD_EXTS:
            return True
        if url_clean.startswith("http://") or url_clean.startswith("https://"):
            return False
        return False

    def resolve_url(self, rel_path, base_url):
        if not rel_path:
            return None
        if rel_path.startswith(('http://', 'https://')):
            return self.normalize_github_url(rel_path)
        if rel_path.startswith("//"):
            return self.normalize_github_url("https:" + rel_path)
        if rel_path.startswith("./") or rel_path.startswith("../"):
            return self.normalize_github_url(urllib.parse.urljoin(base_url, rel_path))
        if rel_path.startswith("/"):
            parsed = urllib.parse.urlparse(base_url)
            return self.normalize_github_url(f"{parsed.scheme}://{parsed.netloc}{rel_path}")
        return self.normalize_github_url(urllib.parse.urljoin(base_url, rel_path))

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

    def download_file(self, url, base_url, category='lib', field_key=None):
        if self.cancel_event and self.cancel_event.is_set():
            self._log("下载任务已取消")
            return None
        if not url or not isinstance(url, str):
            return None
        url_part, suffix = self.split_url_and_suffix(url)
        if not self.is_downloadable(url_part, field_key):
            return None
        should_skip, reason = self.should_skip(url_part)
        if should_skip:
            with self._lock:
                self.skipped.append((url, reason))
            self._log(f"跳过文件: {url} ({reason})")
            return None
        abs_url = self.resolve_url(url_part, base_url)
        if not abs_url:
            with self._lock:
                self.failed.append((url, "无法解析URL"))
            return None
        target_rel = self.get_target_path(abs_url, category, field_key)
        target_abs = os.path.join(self.output_dir, target_rel)
        with self._lock:
            if target_rel in self._processed:
                self.downloaded[url_part] = target_rel
                return target_rel
            self._processed.add(target_rel)
        if not self.overwrite and os.path.exists(target_abs):
            with self._lock:
                self.downloaded[url_part] = target_rel
            self._log(f"文件已存在，跳过: {target_rel}")
            return target_rel

        self._log(f"下载文件: {abs_url}")
        try:
            try:
                head_resp = self.session.head(abs_url, timeout=self.timeout, allow_redirects=True)
                total_size = int(head_resp.headers.get('content-length', 0))
                support_range = head_resp.headers.get('accept-ranges') == 'bytes'
            except Exception as head_err:
                self._log(f"HEAD请求失败 {abs_url}: {head_err}，尝试直接GET")
                total_size = 0
                support_range = False

            downloaded_size = 0
            req_headers = dict(self.session.headers)
            mode = "wb"
            if os.path.exists(target_abs) and total_size > 0:
                downloaded_size = os.path.getsize(target_abs)
                if downloaded_size == total_size:
                    with self._lock:
                        self.downloaded[url_part] = target_rel
                    self._log(f"✅ 本地已存在完整文件，跳过: {target_rel}")
                    return target_rel
                elif downloaded_size < total_size and support_range:
                    self._log(f"🔄 断点续传 {target_rel} (已下载 {downloaded_size/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB)")
                    req_headers["Range"] = f"bytes={downloaded_size}-"
                    mode = "ab"

            os.makedirs(os.path.dirname(target_abs), exist_ok=True)
            resp = self.session.get(abs_url, headers=req_headers, timeout=self.timeout, stream=True)
            self._log(f"响应状态: {resp.status_code}")
            if resp.status_code not in (200, 206):
                with self._lock:
                    self.failed.append((url, f"HTTP {resp.status_code}"))
                return None

            if total_size > 20 * 1024 * 1024 and support_range and mode == "wb":
                return self._download_file_multithread(abs_url, req_headers, target_abs, target_rel, url_part, total_size, field_key)

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
            self._log(f"下载成功: {target_rel}")
            return target_rel
        except Exception as e:
            with self._lock:
                self.failed.append((url, str(e)))
                self._processed.discard(target_rel)
            self._log(f"下载失败: {e}")
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

        temp_files = []
        lock = threading.Lock()
        completed = [0]
        errors = []

        def download_chunk(idx, start, end):
            if self.cancel_event and self.cancel_event.is_set():
                return
            temp_path = f"{path}.part{idx}"
            temp_files.append(temp_path)
            try:
                h = dict(headers)
                h["Range"] = f"bytes={start}-{end}"
                r = self.session.get(url, headers=h, stream=True, timeout=self.timeout)
                r.raise_for_status()
                with open(temp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if self.cancel_event and self.cancel_event.is_set():
                            return
                        if chunk:
                            f.write(chunk)
                with lock:
                    completed[0] += 1
                    self.progress_callback(f"⏳ {target_rel} 分块 {completed[0]}/{num_threads} 完成")
            except Exception as e:
                with lock:
                    errors.append(str(e))

        with ThreadPoolExecutor(max_workers=num_threads) as ex:
            futures = []
            for idx, (start, end) in enumerate(ranges):
                futures.append(ex.submit(download_chunk, idx, start, end))
            for fut in as_completed(futures):
                pass

        if errors:
            self._log(f"❌ 分块下载出错: {errors[0]}")
            with self._lock:
                self.failed.append((url, f"分块下载失败: {errors[0]}"))
            return None

        with open(path, 'wb') as outfile:
            for i in range(num_threads):
                part_path = f"{path}.part{i}"
                if os.path.exists(part_path):
                    with open(part_path, 'rb') as infile:
                        outfile.write(infile.read())
                    try:
                        os.remove(part_path)
                    except Exception:
                        pass

        with self._lock:
            self.downloaded[url_part] = target_rel
        self._log(f"🎉 多线程下载完成: {target_rel}")
        return target_rel

    def download_text(self, url, base_url, force_decrypt=None):
        if self.cancel_event and self.cancel_event.is_set():
            return None
        if not url or not isinstance(url, str):
            return None
        url_part, suffix = self.split_url_and_suffix(url)
        full_url = self.resolve_url(url_part, base_url)
        if not full_url:
            return None
        self._log(f"请求文本: {full_url}")
        try:
            req_headers = dict(self.session.headers)
            parsed = urllib.parse.urlparse(full_url)
            if 'cnb.cool' in parsed.netloc:
                req_headers['Referer'] = 'https://cnb.cool'
                req_headers['Origin'] = 'https://cnb.cool'
                self._log("自动添加 cnb.cool 请求头")
            resp = self.session.get(full_url, headers=req_headers, timeout=self.timeout)
            self._log(f"响应状态: {resp.status_code}, 内容长度: {len(resp.text)}")
            if resp.status_code != 200:
                self._log(f"下载文本失败，状态码: {resp.status_code}")
                return None
            try:
                content = resp.content.decode('utf-8')
            except UnicodeDecodeError:
                content = resp.text
            content = content.lstrip('\ufeff')
            preview = content[:200].replace('\n', ' ').replace('\r', '')
            self._log(f"内容预览: {preview}...")
            parsed = urllib.parse.urlparse(full_url)
            path = urllib.parse.unquote(parsed.path)
            ext = os.path.splitext(path)[1].lower()
            if ext in self.BINARY_EXTS:
                self._log("二进制文件，不进行解密")
                return content
            do_decrypt = force_decrypt if force_decrypt is not None else self.decrypt_enabled
            if do_decrypt:
                self._log("尝试解密内容...")
                decrypted = try_decrypt_content(content, full_url, self.external_api, self.session, max_rounds=5)
                if decrypted:
                    self._log("解密成功")
                    return decrypted
                else:
                    self._log("解密失败，返回原始内容")
            return content
        except Exception as e:
            self._log(f"下载文本异常: {e}")
            return None

# ========================= JSON路径提取器 =========================
class PathExtractor:
    PATH_FIELDS = {'api', 'ext', 'url', 'wallpaper', 'spider', 'logo', 'jar', 'playerType',
                   'header', 'headers', 'ua', 'ref', 'referer'}
    def __init__(self, config=None):
        self.config = config or {}
        self.recursive_depth = self.config.get('recursive_depth', 2)
        self.extracted = set()
        self._json_files = set()
    def extract(self, obj, depth=0):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str):
                    if v.startswith('./'):
                        self.extracted.add(v)
                        if v.endswith('.json') and depth < self.recursive_depth:
                            self._json_files.add(v)
                elif isinstance(v, (dict, list)):
                    self.extract(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                self.extract(item, depth + 1)
    def get_all_paths(self):
        return self.extracted
    def get_json_files(self):
        return self._json_files

# ========================= 主Spider类 =========================
class Spider(BaseSpider):
    VERSION = "v6.0 - 统一UI版"
    ACTION_DOWNLOAD_PACKAGE = "local_source_download_package"
    ACTION_SHOW_STATUS = "local_source_show_status"

    def __init__(self):
        super().__init__()
        self.lock = threading.RLock()
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
        self.skip_patterns_core = SKIP_PATTERNS
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
        self._active_views = {}
        self._is_downloading = False
        self._log_dialog_open = False

        self.localized_interfaces = []
        self._load_localized_interfaces()
        self.root_dirs = []
        self._load_root_dirs()

        self._ui_busy = False
        self.scan_local_dirs = []          # 先初始化默认值
        self.scan_local_extensions = ['.py', '.js']   # 先初始化默认值
        self._original_oktv_url = None   # 新增：记录初始接口地址

        self.decrypt_filename_template = "{name}_m.json"
        self.localized_filename_template = "{name}.json"
        self.inject_manager_site = True
        self.oktv_switch_timeout = 2
        self._load_additional_config()   # 后加载，覆盖为持久化值

    # ========================= 加载额外配置 ========================
    def _load_additional_config(self):
        try:
            if os.path.exists(PERSISTENT_CONFIG_PATH):
                with open(PERSISTENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.decrypt_filename_template = data.get("decrypt_filename_template", "{name}_m.json")
                self.localized_filename_template = data.get("localized_filename_template", "{name}.json")
                self.inject_manager_site = data.get("inject_manager_site", True)
                self.oktv_switch_timeout = data.get("oktv_switch_timeout", 2)
                self.scan_local_dirs = data.get("scan_local_dirs", [])
                self.scan_local_extensions = data.get("scan_local_extensions", ['.py', '.js'])
            else:
                self.scan_local_dirs = []
                self.scan_local_extensions = ['.py', '.js']
        except Exception as e:
            self._log(f"加载额外配置失败，保留现有内存数据: {e}")
            # 不覆盖内存数据
    
        # ---- 默认目录逻辑：仅在 download_output_dir 已设置时执行 ----
        # 避免 __init__ 阶段 download_output_dir 为空时写入错误路径
        if not self.scan_local_dirs and self.download_output_dir:
            default_dir = self.download_output_dir
            if default_dir not in self.scan_local_dirs:
                self.scan_local_dirs.append(default_dir)
                try:
                    os.makedirs(default_dir, exist_ok=True)
                except Exception:
                    pass
                self._save_additional_config()   # 持久化默认目录
                self._log(f"设置默认扫描目录: {default_dir}")

    def _save_additional_config(self):
        try:
            data = {}
            if os.path.exists(PERSISTENT_CONFIG_PATH):
                try:
                    with open(PERSISTENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception as e:
                    self._log(f"读取额外配置失败，将重新创建: {e}")
                    data = {}   # 确保 data 有定义
            # 更新字段
            data["scan_local_dirs"] = self.scan_local_dirs
            data["scan_local_extensions"] = self.scan_local_extensions
            data["decrypt_filename_template"] = self.decrypt_filename_template
            data["localized_filename_template"] = self.localized_filename_template
            data["inject_manager_site"] = self.inject_manager_site
            data["oktv_switch_timeout"] = self.oktv_switch_timeout
            with open(PERSISTENT_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._log(f"额外配置已保存: {PERSISTENT_CONFIG_PATH}")
        except Exception as e:
            self._log(f"保存额外配置失败: {e}")
    
    # ========================= 多设置目录管理 =========================
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
        try:
            if os.path.exists(PERSISTENT_CONFIG_PATH):
                with open(PERSISTENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {}
            data["root_dirs"] = self.root_dirs
            with open(PERSISTENT_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log(f"保存设置目录列表失败: {e}")

    # ========================= 动态路径检测 =========================
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
                self._log(f"搜索 {root} 失败: {e}")
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
                self._log(f"远程加载失败 {source}: {e}")
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
                self._log(f"本地文件JSON解析失败 {cand}: {e}")
            except Exception as e:
                last_err = e
                self._log(f"读取本地文件失败 {cand}: {e}")

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
                    self._log(f"读取配置失败 {p}: {e}")
                    continue
        return None

    # ========================= 接口状态管理 =========================
    def _init_site_state(self, site_id):
        if site_id not in self._site_states:
            self._site_states[site_id] = {
                'decrypt_status': 'idle', 'decrypt_msg': '未执行',
                'localize_status': 'idle', 'localize_msg': '未执行',
                'decrypt_result': None,
                'localize_result': None,
            }

    def _get_site_status_icon(self, status):
        icons = {'idle': '⚪', 'processing': '🔄', 'success': '✅', 'error': '❌', 'partial': '⚠️'}
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

    def _log(self, msg, level='info'):
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{level.upper()}] {msg}"
        print(line)
        self._push_log(msg)
        if not getattr(self, 'log_enabled', True):
            return
        try:
            log_dir = getattr(self, 'log_dir', None) or os.path.join(self.download_output_dir or SCRIPT_DIR, 'log')
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, 'download.log')
            with open(log_file, 'a', encoding='utf-8') as f_local:
                f_local.write(line + '\n')
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

    # ========================= UI 线程辅助 =========================
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
        if self._ui_busy:
            self._log("UI 繁忙，忽略重复点击")
            return
        self._ui_busy = True
        try:
            from java import jclass, dynamic_proxy
            from java.lang import Runnable
            act = self._activity()
            if not act:
                self._ui_busy = False
                return

            Builder = jclass("android.app.AlertDialog$Builder")
            EditText = jclass("android.widget.EditText")
            TextView = jclass("android.widget.TextView")
            LinearLayout = jclass("android.widget.LinearLayout")
            LP = jclass("android.widget.LinearLayout$LayoutParams")
            InputType = jclass("android.text.InputType")
            DialogClick = jclass("android.content.DialogInterface$OnClickListener")
            Toast = jclass("android.widget.Toast")
            ScrollView = jclass("android.widget.ScrollView")
            Switch = jclass("android.widget.Switch")
            Button = jclass("android.widget.Button")
            GradientDrawable = jclass("android.graphics.drawable.GradientDrawable")
            Color = jclass("android.graphics.Color")
            Gravity = jclass("android.view.Gravity")
            TypedValue = jclass("android.util.TypedValue")
            Typeface = jclass("android.graphics.Typeface")
            RadioGroup = jclass("android.widget.RadioGroup")
            RadioButton = jclass("android.widget.RadioButton")

            spider = self
            class Run(dynamic_proxy(Runnable)):
                def run(self):
                    try:
                        ui_builder_fn(act, Builder, EditText, TextView, LinearLayout, LP, InputType,
                                      DialogClick, Toast, ScrollView, Switch, Button, GradientDrawable,
                                      Color, Gravity, TypedValue, Typeface, RadioGroup, RadioButton)
                    except Exception as e:
                        spider._log(f"UI 执行异常: {e}")
                        traceback.print_exc()
                        spider._ui_busy = False

            act.getWindow().getDecorView().post(Run())
        except Exception as e:
            self._log(f"UI 线程执行失败: {e}")
        finally:
            self._ui_busy = False

    # ========================= 浅色现代风格弹窗（统一设计系统版） =========================
    # 说明：以下所有方法都改为走 UIKit，颜色/字号/间距/按钮排布全部取自 UITheme，
    #      彻底消除各弹窗"各自写一套样式"导致的界面不统一问题。
    #      保留原有方法签名，历史调用点无需修改即可获得统一外观。

    def _kit(self, act):
        """获取绑定到当前 Activity 的 UIKit（内部做了一层缓存）。"""
        kit = getattr(self, "_ui_kit", None)
        if kit is None or kit.act is not act:
            kit = UIKit(act, self._ui_listeners)
            self._ui_kit = kit
        return kit

    def _dp2px(self, act, dp):
        """dp -> px（保留旧接口，内部走 UIKit）。"""
        return self._kit(act).dp(dp)

    def _calc_font_size(self, act, base_size):
        """按屏幕自适应后的字号（单位 sp，保留旧接口）。

        旧实现用"像素宽度 / 1080"做缩放，在 4K 电视和高 DPI 手机上会失真；
        现在改为基于 dp 宽度 + 设备类型（手机/平板/电视）计算，各种屏幕都合适。
        """
        return self._kit(act).fs(base_size)

    def _make_modern_button(self, act, text, bg_color, text_color, callback,
                            dialog_ref=None, is_primary=False, small=False):
        """统一按钮（保留旧接口）。

        旧实现内边距只有 2~5dp、圆角 3dp、高度靠文字撑，导致按钮又小又挤；
        现在改为统一高度（34/42dp）、最小宽度、等宽内边距与按下反馈。
        """
        kit = self._kit(act)
        style = UITheme.LEGACY_COLOR_MAP.get(str(bg_color or "").strip().upper())
        if style is None:
            style = "primary" if is_primary else "secondary"
        if str(bg_color or "").strip().upper() in ("#EF4444", "#F04438"):
            style = "danger"
        elif str(bg_color or "").strip().upper() in ("#10B981", "#12B76A"):
            style = "success"
        return kit.button(text, style, callback, dialog_ref, "sm" if small else "md")

    def _build_modern_dialog(self, act, Builder, LinearLayout, TextView, LP, ScrollView,
                              Button, GradientDrawable, Color, Gravity, TypedValue, Typeface,
                              title, content_view, bottom_buttons, width_ratio=0.92, height_ratio=0.85,
                              back_callback=None, enable_scroll=True):
        """统一对话框（保留旧接口，内部改为 UIKit.dialog）。

        改进点：
          * 底部按钮自动换行 + 等宽填充，按钮再多也不会溢出屏幕；
          * 弹窗宽高按 dp 上限收敛，4K 电视上不会被拉成超宽横幅；
          * 标题栏支持返回按钮与右上角关闭按钮。
        """
        try:
            kit = self._kit(act)
            spider = self
            dialog = kit.dialog(
                title=title,
                content=content_view,
                buttons=bottom_buttons,
                width_ratio=width_ratio,
                height_ratio=height_ratio,
                back_callback=back_callback,
                scroll=enable_scroll,
                on_dismiss=lambda: setattr(spider, "_ui_busy", False),
            )
            return dialog
        except Exception as e:
            self._log(f"构建对话框失败: {e}")
            traceback.print_exc()
            self._ui_busy = False
            return None

    # ---------- 各类对话框辅助方法 ----------
    def _show_modern_confirm(self, title, message, on_confirm, extra_buttons=None, show_cancel=True):
        def on_ui(act, Builder, EditText, TextView, LinearLayout, LP, InputType,
                  DialogClick, Toast, ScrollView, Switch, Button, GradientDrawable,
                  Color, Gravity, TypedValue, Typeface, RadioGroup, RadioButton):
            kit = self._kit(act)
            G = kit.gravity()

            box = kit.vbox()
            msg_view = kit.text(message, size=UITheme.FS_BODY_LG, color=UITheme.TEXT_2,
                                line_spacing=1.5, selectable=True,
                                gravity=G.START if G else None)
            box.addView(msg_view, kit.lp(-1, -2))
            box.setLayoutParams(kit.lp(-1, -2))

            buttons = []
            # 长文本/路径类内容自动附一个复制按钮
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
        def on_ui(act, Builder, EditText, TextView, LinearLayout, LP, InputType,
                  DialogClick, Toast, ScrollView, Switch, Button, GradientDrawable,
                  Color, Gravity, TypedValue, Typeface, RadioGroup, RadioButton):
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

    def _show_modern_info(self, title, message, show_copy=False):
        def on_ui(act, Builder, EditText, TextView, LinearLayout, LP, InputType,
                  DialogClick, Toast, ScrollView, Switch, Button, GradientDrawable,
                  Color, Gravity, TypedValue, Typeface, RadioGroup, RadioButton):
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

    def _show_modern_radio_selector(self, title, options, current_value, on_confirm, extra_buttons=None):
        """单选列表。整行可点、文字自动省略，长选项在窄屏也不会被截断。"""
        def on_ui(act, Builder, EditText, TextView, LinearLayout, LP, InputType,
                  DialogClick, Toast, ScrollView, Switch, Button, GradientDrawable,
                  Color, Gravity, TypedValue, Typeface, RadioGroup, RadioButton):
            kit = self._kit(act)
            G = kit.gravity()

            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))
            box.addView(kit.hint("请选择一项（单选）"), kit.lp(-1, -2))

            group = RadioGroup(act)
            group.setOrientation(LinearLayout.VERTICAL)
            group.setLayoutParams(kit.lp(-1, -2))

            radio_buttons = {}
            current_str = str(current_value) if current_value is not None else ""
            for idx, item in enumerate(options):
                try:
                    val, display = item
                except Exception:
                    val, display = item, str(item)
                rb = RadioButton(act)
                rb.setId(idx + 1000)
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
                group.addView(rb, kit.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_XS)))
                radio_buttons[val] = rb
                if str(val) == current_str:
                    try:
                        group.check(rb.getId())
                    except Exception:
                        pass
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

    # ---------- 通用辅助 ----------
    def _with_margin(self, kit, view, left_dp, top_dp=0.0, right_dp=0.0, bottom_dp=0.0):
        """给已创建好的控件补一个左边距（等宽排布时常用）。"""
        if view is None:
            return view
        p = view.getLayoutParams()
        if p is None:
            p = kit.lp(-2, -2)
        p.setMargins(kit.dp(left_dp), kit.dp(top_dp), kit.dp(right_dp), kit.dp(bottom_dp))
        view.setLayoutParams(p)
        return view

    def _set_row_bg(self, kit, view, idx, radius=UITheme.R_MD):
        """列表行的斑马纹背景，提升可扫读性。"""
        bg = UITheme.SURFACE_ALT if (idx % 2 == 0) else UITheme.SURFACE
        kit._set_bg(view, kit.shape(bg, radius, 1.0, UITheme.BORDER))

    def _show_dialog(self, act, title, content, buttons, width_ratio=0.92, height_ratio=0.85,
                     back_callback=None, on_show=None):
        """统一入口：构建 -> 显示 -> 登记。

        注意：本方法**只能**在已经处于 UI 线程时调用（即某个 on_ui 内部），
        它不会再次投递到 UI 线程，否则会被 _run_on_ui 的防重入判断拦掉。
        """
        spider = self
        kit = self._kit(act)
        dialog = kit.dialog(
            title=title,
            content=content,
            buttons=buttons,
            width_ratio=width_ratio,
            height_ratio=height_ratio,
            back_callback=back_callback,
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
        """统一的接口 / 项目卡片行（在线接口管理、批量选择器共用）。

        结构：开关 + 名称（+ 副标题），下方一条操作按钮栏。
        相比旧的"一行塞开关+文字+三个小按钮"，卡片式在窄屏和电视上都清晰得多，
        按钮也不会被挤成一条。
        """
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

    def _ui_dir_card(self, kit, index, path, checked, on_toggle, on_delete, on_long_click=None):
        """统一的目录卡片行（接口目录管理 / 本地文件扫描共用）。"""
        G = kit.gravity()
        card = kit.card(pad=(UITheme.S_MD, UITheme.S_SM, UITheme.S_MD, UITheme.S_SM))

        row = kit.hbox()
        row.setLayoutParams(kit.lp(-1, -2))
        if G:
            row.setGravity(G.CENTER_VERTICAL)

        sw = kit.toggle("" if index is None else f"{index}. {path}", bool(checked),
                        on_toggle, on_long_click, weight=1.0)
        row.addView(sw)

        if on_delete is not None:
            del_btn = kit.button("删除", "soft_danger", on_delete, None, "sm")
            del_btn.setLayoutParams(
                kit.lp(kit.dp(64 if kit.kind == "phone" else 92), kit.dp(UITheme.H_BTN_SM),
                       0.0, (UITheme.S_SM, 0.0, 0.0, 0.0)))
            row.addView(del_btn)

        card.addView(row, kit.lp(-1, -2))
        return card

    def _push_log(self, msg):
        time_str = time.strftime("%H:%M:%S")
        self.log_queue.put(f"[{time_str}] {msg}")

    def _start_log_looper(self, main_handler):
        from java import dynamic_proxy
        from java.lang import Runnable
        if self._persisted_runnable is not None:
            return
        class LogUpdater(dynamic_proxy(Runnable)):
            def __init__(self, spider_ref, handler):
                super().__init__()
                self.spider = spider_ref
                self.handler = handler
            def run(self):
                view = self.spider._active_views.get("log")
                scroll = self.spider._active_views.get("scroll")
                if not view or not scroll:
                    self.spider._persisted_runnable = None
                    return
                batch_logs = []
                while not self.spider.log_queue.empty():
                    try:
                        batch_logs.append(self.spider.log_queue.get_nowait())
                    except queue.Empty:
                        break
                if batch_logs:
                    current_text = str(view.getText())
                    new_text = current_text + "\n" + "\n".join(batch_logs)
                    if len(new_text) > 6000:
                        new_text = new_text[-6000:]
                    view.setText(new_text)
                    scroll.post(Runnable_Scroll(scroll))
                self.handler.postDelayed(self, 300)
        class Runnable_Scroll(dynamic_proxy(Runnable)):
            def __init__(self, scroll):
                super().__init__()
                self.scroll = scroll
            def run(self):
                if self.scroll:
                    self.scroll.fullScroll(130)
        self._persisted_runnable = LogUpdater(self, main_handler)
        main_handler.post(self._persisted_runnable)

    def _get_recent_logs(self, lines=100):
        log_file = os.path.join(self.log_dir, 'download.log') if self.log_dir else None
        if not log_file or not os.path.exists(log_file):
            return None
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
            recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return ''.join(recent)
        except Exception:
            return None

    def _show_log_dialog(self):
        """日志面板：统一风格 + 底部 复制 / 清空 / 关闭 三按钮（自动换行等宽）。"""
        if self._log_dialog_open:
            self._push_log("⚠️ 日志面板已在运行中")
            return
        self._log_dialog_open = True
        self._ui_listeners.clear()
        self._active_views.clear()

        def on_ui(act, classes):
            spider = self
            kit = self._kit(act)
            G = kit.gravity()

            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))

            recent_logs = self._get_recent_logs(100)
            initial_text = recent_logs if recent_logs else "系统就绪，等待操作...\n"

            log_view = kit.text(initial_text, size=UITheme.FS_MICRO + 0.5,
                                color=UITheme.TEXT_2, mono=True, line_spacing=1.35,
                                gravity=(G.START | G.TOP) if G else None, selectable=True)
            log_view.setPadding(kit.dp(UITheme.S_MD), kit.dp(UITheme.S_MD),
                                kit.dp(UITheme.S_MD), kit.dp(UITheme.S_MD))
            kit._set_bg(log_view, kit.shape(UITheme.SURFACE_ALT, UITheme.R_MD, 1.0, UITheme.BORDER))

            # 日志区单独放在一个可滚动容器里（外层 kit.dialog 不再二次套滚动）
            log_scroll = kit.scroll(log_view, fill=True)
            box.addView(log_scroll, kit.lp(-1, kit.dp(320 if kit.kind != "phone" else 260)))

            def do_copy():
                try:
                    text = str(log_view.getText())
                except Exception:
                    text = ""
                kit.toast("日志已复制" if kit.copy(text, "日志") else "复制失败")

            def do_clear():
                try:
                    log_view.setText("")
                except Exception:
                    pass
                kit.toast("已清空显示")

            buttons = [
                {"text": "复制", "style": "secondary", "callback": do_copy, "dismiss": False},
                {"text": "清空", "style": "secondary", "callback": do_clear, "dismiss": False},
                {"text": "关闭", "style": "primary", "callback": None, "dismiss": True},
            ]

            def on_dismiss():
                spider._log_dialog_open = False
                spider._persisted_runnable = None
                spider._active_views.clear()
                spider._ui_busy = False

            dialog = kit.dialog(title="✉️ 日志面板", content=box, buttons=buttons,
                                width_ratio=0.92, height_ratio=0.85,
                                scroll=False, on_dismiss=on_dismiss)
            self._dialog_refs.append(dialog)
            dialog.show()

            self._active_views = {"log": log_view, "scroll": log_scroll, "dialog": dialog}

            try:
                Handler = kit.j("android.os.Handler")
                Looper = kit.j("android.os.Looper")
                main_handler = Handler(Looper.getMainLooper())
                self._start_log_looper(main_handler)
            except Exception as e:
                self._log(f"日志刷新器启动失败: {e}")

        self._run_on_ui_log(on_ui)

    def _on_log_dismiss(self):
        self._log_dialog_open = False
        self._persisted_runnable = None
        self._active_views.clear()

    def _run_on_ui_log(self, ui_builder_fn):
        try:
            from java import jclass, dynamic_proxy
            from java.lang import Runnable
            act = self._activity()
            if not act:
                return
            Builder = jclass("android.app.AlertDialog$Builder")
            LinearLayout = jclass("android.widget.LinearLayout")
            ScrollView = jclass("android.widget.ScrollView")
            TextView = jclass("android.widget.TextView")
            EditText = jclass("android.widget.EditText")
            Button = jclass("android.widget.Button")
            CheckBox = jclass("android.widget.CheckBox")
            LP = jclass("android.widget.LinearLayout$LayoutParams")
            ViewOnClickListener = jclass("android.view.View$OnClickListener")
            Handler = jclass("android.os.Handler")
            Looper = jclass("android.os.Looper")
            Color = jclass("android.graphics.Color")
            GradientDrawable = jclass("android.graphics.drawable.GradientDrawable")
            Typeface = jclass("android.graphics.Typeface")
            Gravity = jclass("android.view.Gravity")
            classes = (Builder, LinearLayout, ScrollView, TextView, EditText,
                       Button, CheckBox, LP, ViewOnClickListener, Handler, Looper,
                       Color, GradientDrawable, Typeface, Gravity)
            class Run(dynamic_proxy(Runnable)):
                def run(self):
                    ui_builder_fn(act, classes)
            act.getWindow().getDecorView().post(Run())
        except Exception:
            pass
        finally:
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
            self._log(f"执行操作时异常: {e}")

    # ========================= 配置管理 =========================
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
                    self._log(f"URL字符串子分类请求失败: {url} - {e}")
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

    def _normalize_config_keys(self, obj):
        if isinstance(obj, dict):
            new_obj = {}
            key_map = {
                '下载目录': 'download_output_dir',
                '全局代理': 'proxy',
                '并发数': 'concurrent',
                '跳过扩展名': 'skip_extensions',
                '跳过模式': 'skip_patterns',
                '最大文件大小MB': 'max_file_size_mb',
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
                new_obj[new_key] = self._normalize_config_keys(v)
            return new_obj
        elif isinstance(obj, list):
            return [self._normalize_config_keys(item) for item in obj]
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
        config = self._normalize_config_keys(config)
        self.config = config
        raw_sources = config.get('sources') or config.get('urls', [])
        self.package_download_sites = []
        for item in raw_sources:
            if isinstance(item, dict) and item.get('url'):
                site = {
                    "id": self._package_download_site_id(item.get('name', '未命名'), item['url']),
                    "name": item.get('name', '未命名'),
                    "url": item['url'],
                    "enabled": item.get('enabled', True),
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
        self.skip_patterns_core = self.download_config.get('skip_patterns_core', SKIP_PATTERNS)
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
        self.log_level = log_cfg.get('level', self.config.get('log_level', 'debug'))
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

    def _save_config_to_file(self, path=None):
        if path is None:
            path = os.path.join(_cache_root, 'config.json')
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
        }
        temp = path + ".tmp"
        try:
            os.makedirs(os.path.dirname(temp), exist_ok=True)
        except Exception:
            pass
        with open(temp, 'w', encoding='utf-8') as f_local:
            json.dump(config, f_local, ensure_ascii=False, indent=2)
        os.replace(temp, path)
        self._save_persistent_config()

    def _save_persistent_config(self):
        try:
            os.makedirs(os.path.dirname(PERSISTENT_CONFIG_PATH), exist_ok=True)
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
                "original_oktv_url": self._original_oktv_url,
                "scan_local_dirs": self.scan_local_dirs,
                "scan_local_extensions": self.scan_local_extensions,
            }
            with open(PERSISTENT_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self._log(f"配置已持久化: {PERSISTENT_CONFIG_PATH}")
        except Exception as e:
            self._log(f"持久化配置失败: {e}")
        
    def _load_persistent_config(self):
        if not os.path.exists(PERSISTENT_CONFIG_PATH):
            return None
        try:
            with open(PERSISTENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self._log(f"加载持久化配置失败: {e}")
            return None

    def _restore_default_config(self):
        try:
            if os.path.exists(CACHE_DIR):
                shutil.rmtree(CACHE_DIR, ignore_errors=True)
            os.makedirs(CACHE_DIR, exist_ok=True)
            if os.path.exists(PERSISTENT_CONFIG_PATH):
                os.remove(PERSISTENT_CONFIG_PATH)
            self._log("已清除缓存和持久化配置")

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

    def _update_config_value(self, key_path, value, raw=False):
        try:
            keys = key_path.split('.')
            target = self.config
            for k in keys[:-1]:
                if k not in target:
                    target[k] = {}
                target = target[k]
            target[keys[-1]] = value
            self._save_config_to_file()
            self._save_persistent_config()
            self._log(f"配置已更新: {key_path} = {value}")
        except Exception as e:
            self._log(f"配置更新失败: {e}")
            raise

    # ========================= 单接口操作 =========================
    def _absolutize_urls(self, obj, base_url):
        if isinstance(obj, dict):
            return {k: self._absolutize_urls(v, base_url) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._absolutize_urls(item, base_url) for item in obj]
        elif isinstance(obj, str):
            if obj.startswith(('http://', 'https://')):
                return obj
            if obj.startswith(('./', '../', '/')):
                return urllib.parse.urljoin(base_url, obj)
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
                self._log(f"【解密】开始处理 {name} ({url})")
                download_cfg = copy.deepcopy(self.download_config)
                download_cfg['base_url'] = self._get_base_url(url)
                download_cfg['github_proxy'] = self.config.get('github_proxy', GITHUB_PROXY)
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
                    return
                try:
                    data = json.loads(content)
                    is_json = True
                except Exception:
                    is_json = False
                base_url = self._get_base_url(url)
                safe_name = re.sub(r'[\\/:*?"<>|]', '_', name)
                output_dir = os.path.join(self.download_output_dir, safe_name)
                os.makedirs(output_dir, exist_ok=True)
                decrypt_name = self.decrypt_filename_template.format(name=safe_name)
                dec_path = os.path.join(output_dir, decrypt_name)
                if is_json:
                    data = self._absolutize_urls(data, base_url)
                    with open(dec_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    self._site_states[site_id]['decrypt_status'] = 'success'
                    self._site_states[site_id]['decrypt_msg'] = '明文JSON已保存'
                    self._site_states[site_id]['decrypt_result'] = dec_path
                    self._log(f"【解密】{name} 为明文JSON，已保存")
                else:
                    dec = try_decrypt_content(content, url, self.external_api_url, self._session, max_rounds=5)
                    if dec:
                        # 新增：先尝试直接解析
                        parse_success = False
                        try:
                            data = json.loads(dec)
                            parse_success = True
                        except json.JSONDecodeError:
                            # 新增：清理注释后再次尝试
                            self._log(f"【解密】{name} 首次解析失败，尝试清理注释...")
                            cleaned = self._clean_json_comments(dec)
                            try:
                                data = json.loads(cleaned)
                                parse_success = True
                                self._log(f"【解密】{name} 注释清理后解析成功")
                            except json.JSONDecodeError:
                                self._log(f"【解密】{name} 清理注释后仍无法解析为JSON")

                        if parse_success:
                            try:
                                data = self._absolutize_urls(data, base_url)
                                with open(dec_path, 'w', encoding='utf-8') as f:
                                    json.dump(data, f, ensure_ascii=False, indent=2)
                                self._site_states[site_id]['decrypt_status'] = 'success'
                                self._site_states[site_id]['decrypt_msg'] = '解密成功'
                                self._site_states[site_id]['decrypt_result'] = dec_path
                                self._log(f"【解密】{name} 解密成功，已保存")
                            except Exception as e:
                                self._log(f"【解密】{name} 处理异常: {e}")
                                self._site_states[site_id]['decrypt_status'] = 'error'
                                self._site_states[site_id]['decrypt_msg'] = f'处理异常: {str(e)[:30]}'
                        else:
                            # 保存原文
                            with open(dec_path, 'w', encoding='utf-8') as f:
                                f.write(dec)
                            self._site_states[site_id]['decrypt_status'] = 'success'
                            self._site_states[site_id]['decrypt_msg'] = '解密成功(非JSON)'
                            self._site_states[site_id]['decrypt_result'] = dec_path
                            self._log(f"【解密】{name} 解密成功（非标准JSON，已保存原文）")
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
                stats = self._process_json_source(site, cancel_event)
                if cancel_event.is_set():
                    self._site_states[site_id]['localize_status'] = 'idle'
                    self._site_states[site_id]['localize_msg'] = '已取消'
                    self._log(f"【本地化】{site['name']} 已取消")
                    return
                self._site_states[site_id]['localize_status'] = 'success'
                self._site_states[site_id]['localize_msg'] = f"下载{stats['downloaded']}个文件"
                self._site_states[site_id]['localize_result'] = stats.get('box_path')
                self._log(f"【本地化】{site['name']} 完成，下载 {stats['downloaded']} 个文件")
            except Exception as e:
                self._site_states[site_id]['localize_status'] = 'error'
                self._site_states[site_id]['localize_msg'] = f'失败: {str(e)[:30]}'
                self._log(f"【本地化】{site['name']} 失败: {e}")
            finally:
                with self._site_op_lock:
                    self._site_op_threads.pop(site_id, None)
                    if site_id in self._site_cancel_events:
                        del self._site_cancel_events[site_id]

        t = threading.Thread(target=_worker, daemon=True)
        with self._site_op_lock:
            self._site_op_threads[site_id] = t
        t.start()
        return "已开始本地化任务"

    def _decrypt_sites(self, sites):
        if not sites:
            return "没有选择任何接口"
        count = 0
        for site in sites:
            self._decrypt_single_site(site['id'])
            count += 1
        return f"已开始解密 {count} 个接口"

    def _localize_sites(self, sites):
        if not sites:
            return "没有选择任何接口"
        count = 0
        for site in sites:
            self._localize_single_site(site['id'])
            count += 1
        return f"已开始本地化 {count} 个接口"

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
        if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
            raise ValueError("下载地址必须是 http 或 https URL")
        return url

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
            target["name"] = clean_name
            target["url"] = clean_url
            target["type"] = "json"
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
        self._save_config_to_file()
        return removed

    # ========================= 核心下载逻辑 =========================
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
            self._log("成功解析 JSON")
            return data, base_url, None
        except json.JSONDecodeError as e:
            self._log(f"JSON 解析失败: {e}, 尝试清理注释后重试...")
            try:
                cleaned = self._clean_json_comments(content)
                data = json.loads(cleaned)
                self._log("注释清理后成功解析 JSON")
                return data, base_url, None
            except Exception as e2:
                self._log(f"清理注释后仍失败: {e2}, 尝试提取片段...")
        json_pattern = r'(\{[\s\S]*\}|\[[\s\S]*\])'
        matches = re.findall(json_pattern, content)
        for candidate in matches:
            try:
                data = json.loads(candidate)
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
        self._push_log(f"✅ 批量下载完成 {completed[0]}/{total}")

    def _find_local_path(self, url, downloader):
        if not url or not isinstance(url, str):
            return None
        url_part, suffix = downloader.split_url_and_suffix(url)

        if url_part in downloader.downloaded:
            return './' + downloader.downloaded[url_part].replace('\\', '/') + suffix

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
                return './' + downloader.downloaded[variant].replace('\\', '/') + suffix

        return None

    def _collect_missing_files(self, data, downloader):
        all_items = set()
        self._walk_and_collect(data, "", all_items)
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
            missing.append((url, cat, "", field_key))
        return missing

    def _generate_local_box(self, data, source_name, output_dir, downloader):
        import json

        def localize(obj, field_key=None):
            if isinstance(obj, dict):
                result = {}
                for k, v in obj.items():
                    if k in ('name', 'key'):
                        result[k] = v
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
                return obj
            else:
                return obj

        local_data = localize(data)
        local_data['warningText'] = f"本地包生成于 {time.strftime('%Y-%m-%d %H:%M:%S')} | 源: {source_name}"
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', source_name)
        box_filename = self.localized_filename_template.format(name=safe_name)
        box_path = os.path.join(output_dir, box_filename)
        with open(box_path, 'w', encoding='utf-8') as f_local:
            json.dump(local_data, f_local, ensure_ascii=False, indent=2)
        return box_path

    def _process_json_source(self, site, cancel_event=None):
        name = site.get("name", "未命名")
        url = site.get("url", "")
        if not url:
            raise ValueError("接口URL为空")
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', name)
        output_dir = os.path.join(self.download_output_dir, safe_name)
        os.makedirs(output_dir, exist_ok=True)
        download_cfg = copy.deepcopy(self.download_config)
        download_cfg['base_url'] = self._get_base_url(url)
        download_cfg['github_proxy'] = self.config.get('github_proxy', GITHUB_PROXY)
        download_cfg['user_agent'] = self.user_agent
        downloader = FileDownloader(output_dir, download_cfg, log_callback=self._log, progress_callback=self._push_log,
                                    cancel_event=cancel_event)
        self._package_download_message = f"正在解析 {name} ..."
        self._push_log(f"🎯 开始处理接口: {name}")
        data, base_url, error = self._parse_box_json(url, downloader)
        if error:
            raise Exception(f"解析失败: {error}")
        paths = self._collect_files(data, base_url, downloader)
        self._package_download_message = f"正在下载 {len(paths)} 个文件 ..."
        self._push_log(f"❤️️ 收集到 {len(paths)} 个可下载文件，开始并发下载...")
        self._download_all(paths, downloader)

        missing = self._collect_missing_files(data, downloader)
        if missing:
            self._push_log(f"🔄 发现 {len(missing)} 个遗漏文件，补充下载...")
            self._download_all(missing, downloader)

        self._push_log(f"🧩 正在生成本地化 box.json...")
        local_box_path = self._generate_local_box(data, name, output_dir, downloader)
        self._push_log(f"🎉 接口 {name} 处理完成！输出: {local_box_path}")
        stats = {
            "downloaded": len(downloader.downloaded),
            "failed": len(downloader.failed),
            "skipped": len(downloader.skipped),
            "output_dir": output_dir,
            "box_path": local_box_path,
        }
        self._add_or_update_localized_interface(name, url, local_box_path)
        return stats

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
                    stats = self._process_json_source(site, cancel_event)
                    if cancel_event.is_set():
                        self._log("批量下载已取消")
                        break
                    successes.append({"name": name, "url": url, "result": stats})
                    self._log(f"接口 {name} 处理成功，下载 {stats.get('downloaded',0)} 个文件")
                except Exception as e:
                    self._log(f"接口 {name} 处理失败: {e}")
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

    # ========================= 合并弹窗（在线接口管理） =========================
    def _open_site_management_dialog(self):
        """在线接口管理：分区卡片 + 统一接口卡片行，功能保持不变。"""
        def on_ui(act, Builder, EditText, TextView, LinearLayout, LP, InputType,
                  DialogClick, Toast, ScrollView, Switch, Button, GradientDrawable,
                  Color, Gravity, TypedValue, Typeface, RadioGroup, RadioButton):
            spider = self
            kit = self._kit(act)

            container = kit.vbox()
            container.setLayoutParams(kit.lp(-1, -2))

            # ===== 单接口添加 =====
            add_card = kit.card()
            add_card.addView(kit.section_title("➕ 添加单接口"), kit.lp(-1, -2))
            name_edit = kit.input(hint="备注名（如：饭太硬）")
            add_card.addView(name_edit, kit.lp(-1, -2))
            url_edit = kit.input(hint="https://example.com/box.json")
            add_card.addView(url_edit, kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))

            sites_container = kit.vbox()
            sites_container.setLayoutParams(kit.lp(-1, -2))

            def refresh_site_list():
                sites_container.removeAllViews()
                if not spider.package_download_sites:
                    sites_container.addView(kit.empty("还没有接口，先在上方添加或批量导入"),
                                            kit.lp(-1, -2))
                    return
                for idx, site in enumerate(spider.package_download_sites):
                    sites_container.addView(
                        spider._ui_package_site_card(kit, site, idx, refresh_site_list),
                        kit.lp(-1, -2))

            def do_add_single():
                try:
                    name = str(name_edit.getText()).strip()
                    url = str(url_edit.getText()).strip()
                    with spider.lock:
                        saved, created = spider._add_or_update_package_download_site(name, url)
                    kit.toast("已{}：{}".format("添加" if created else "更新", saved["name"]), long=True)
                    name_edit.setText("")
                    url_edit.setText("")
                    refresh_site_list()
                except Exception as exc:
                    kit.toast("添加失败: {}".format(exc), long=True)

            add_card.addView(
                kit.button_bar([{"text": "添加 / 更新", "style": "primary",
                                 "callback": do_add_single, "dismiss": False}], size="md"),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_MD, 0.0, 0.0)))
            container.addView(add_card, kit.lp(-1, -2))

            # ===== 多仓批量导入 =====
            import_card = kit.card()
            import_card.addView(
                kit.section_title("📥 多仓批量导入",
                                  hint='粘贴多仓 JSON，如：{"urls":[{"name":"xxx","url":"xxx"}]}'),
                kit.lp(-1, -2))
            import_edit = kit.input(multiline=True, mono=True, min_lines=4, max_lines=8)
            import_card.addView(import_edit, kit.lp(-1, -2))

            def do_import():
                try:
                    text = str(import_edit.getText()).strip()
                    if not text:
                        kit.toast("请输入内容")
                        return
                    imported = spider._parse_multi_warehouse_json(text)
                    if not imported:
                        kit.toast("未解析到有效接口", long=True)
                        return
                    count = 0
                    for item in imported:
                        try:
                            with spider.lock:
                                spider._add_or_update_package_download_site(item['name'], item['url'])
                            count += 1
                        except Exception:
                            pass
                    kit.toast("成功导入 {} 个接口".format(count), long=True)
                    import_edit.setText("")
                    refresh_site_list()
                except Exception as exc:
                    kit.toast("导入失败: {}".format(exc), long=True)

            import_card.addView(
                kit.button_bar([{"text": "批量导入", "style": "success",
                                 "callback": do_import, "dismiss": False}], size="md"),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_MD, 0.0, 0.0)))
            container.addView(import_card, kit.lp(-1, -2))

            # ===== 现有接口 =====
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
        """「在线接口管理」里的单个接口卡片（开关 + 名称 + 编辑/复制/删除）。"""
        spider = self

        def on_toggle(v=None):
            # UIKit 的开关回调会把最新状态传进来，直接用它比取反更可靠
            site['enabled'] = bool(v) if v is not None else (not site.get('enabled', True))
            spider._save_config_to_file()

        def on_edit():
            sname = site.get('name', '')
            surl = site.get('url', '')

            def on_save_name(new_name):
                def on_save_url(new_url):
                    try:
                        with spider.lock:
                            if new_name != sname or new_url != surl:
                                spider._delete_package_download_sites([site.get("id")])
                            spider._add_or_update_package_download_site(new_name, new_url)
                        kit.toast("已更新")
                        refresh_fn()
                    except Exception as exc:
                        kit.toast("保存失败: {}".format(exc), long=True)
                spider._show_modern_input("编辑接口地址", "https://", surl, on_save_url)

            spider._show_modern_input("编辑备注名", "输入名称", sname, on_save_name)

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

    # ========================= 合并弹窗（设置目录管理+扫描） =========================
    def _open_root_dirs_management(self):
        """接口目录管理：路径输入 + 目录卡片列表 + 扫描。"""
        def on_ui(act, Builder, EditText, TextView, LinearLayout, LP, InputType,
                  DialogClick, Toast, ScrollView, Switch, Button, GradientDrawable,
                  Color, Gravity, TypedValue, Typeface, RadioGroup, RadioButton):
            spider = self
            kit = self._kit(act)
            spider._load_root_dirs()

            container = kit.vbox()
            container.setLayoutParams(kit.lp(-1, -2))

            # ===== 添加目录 =====
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
                    holder = {"checked": True}

                    def make_toggle(state=holder):
                        def on_change(v):
                            state["checked"] = v
                        return on_change

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
                        spider._ui_dir_card(kit, idx + 1, root, True, make_toggle(),
                                            del_fn, make_copy()),
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

            add_card.addView(
                kit.button_bar([{"text": "添加目录", "style": "primary",
                                 "callback": do_add, "dismiss": False}], size="md"),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_MD, 0.0, 0.0)))
            container.addView(add_card, kit.lp(-1, -2))

            # ===== 目录列表 =====
            list_card = kit.card()
            list_card.addView(kit.section_title("📋 设置目录列表", hint="勾选参与扫描，长按可复制路径"),
                              kit.lp(-1, -2))
            list_card.addView(dirs_container, kit.lp(-1, -2))
            refresh_dir_list()
            container.addView(list_card, kit.lp(-1, -2))

            def do_rescan():
                selected = [r for r, holder in switches.items() if holder.get("checked", True)]
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

    def _open_scan_local_files_dialog(self):
        """本地 API 文件管理：文件类型多选 + 目录管理 + 扫描生成。"""
        def on_ui(act, Builder, EditText, TextView, LinearLayout, LP, InputType,
                  DialogClick, Toast, ScrollView, Switch, Button, GradientDrawable,
                  Color, Gravity, TypedValue, Typeface, RadioGroup, RadioButton):
            spider = self
            kit = self._kit(act)
            spider._load_additional_config()

            container = kit.vbox()
            container.setLayoutParams(kit.lp(-1, -2))

            # ===== 扫描文件类型 =====
            ext_card = kit.card()
            ext_card.addView(kit.section_title("🧩 扫描文件类型", hint="可多选，默认已勾选常用类型"),
                             kit.lp(-1, -2))

            preset_exts = ['.py', '.js']
            ext_states = {}
            ext_holder = kit.vbox()
            ext_holder.setLayoutParams(kit.lp(-1, -2))
            row = None
            for i, ext in enumerate(preset_exts):
                if i % kit.max_cols == 0:
                    row = kit.hbox()
                    row.setLayoutParams(kit.lp(-1, -2))
                    ext_holder.addView(row, kit.lp(-1, -2))
                ext_states[ext] = {"on": ext in spider.scan_local_extensions}

                def make_ext_toggle(key=ext):
                    def on_change(v):
                        ext_states[key]["on"] = v
                    return on_change

                sw = kit.toggle(ext, ext_states[ext]["on"], make_ext_toggle(), weight=1.0)
                row.addView(sw)
            ext_card.addView(ext_holder, kit.lp(-1, -2))

            ext_card.addView(kit.field_label("自定义扩展名（逗号分隔，如 .lua）"),
                             kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))
            custom_edit = kit.input(hint="例如: .lua,.swift")
            ext_card.addView(custom_edit, kit.lp(-1, -2))
            container.addView(ext_card, kit.lp(-1, -2))

            # ===== 扫描目录 =====
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
                    holder = {"on": True}
                    dir_states[path] = holder

                    def make_toggle(state=holder):
                        def on_change(v):
                            state["on"] = v
                        return on_change

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
                        spider._ui_dir_card(kit, idx + 1, path, True, make_toggle(),
                                            make_del(), make_copy()),
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

            dir_card.addView(
                kit.button_bar([{"text": "添加文件夹", "style": "primary",
                                 "callback": do_add_dir, "dismiss": False}], size="md"),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_MD, 0.0, UITheme.S_SM)))
            dir_card.addView(dirs_container, kit.lp(-1, -2))
            refresh_dir_list()
            container.addView(dir_card, kit.lp(-1, -2))

            def do_scan():
                selected_exts = [ext for ext, st in ext_states.items() if st["on"]]
                custom_text = str(custom_edit.getText()).strip()
                if custom_text:
                    for e in [x.strip() for x in custom_text.split(",") if x.strip()]:
                        if e not in selected_exts:
                            selected_exts.append(e)
                if not selected_exts:
                    kit.toast("请至少选择一种文件类型")
                    return
                selected_dirs = [p for p, st in dir_states.items() if st["on"]]
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

    # ========================= 本地化接口记录管理 =========================
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
                                        self._log(f"生成绝对路径 JSON: {abs_json_path}")
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
        os.makedirs(temp_dir, exist_ok=True)
        hash_val = hashlib.md5(os.path.abspath(box_path).encode('utf-8')).hexdigest()[:12]
        return os.path.join(temp_dir, f"{hash_val}.json")

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

            config_class = jclass("com.fongmi.android.tv.bean.Config")
            current_url = ""
            try:
                current_url = str(config_class.vod().getUrl() or "")
            except Exception:
                pass
            proxy = jclass("com.github.catvod.Proxy")
            port = 0
            try:
                port = int(proxy.getPort())
            except Exception:
                pass
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

        # 多个 JSON，单选
        def on_ui(act, Builder, EditText, TextView, LinearLayout, LP, InputType,
                  DialogClick, Toast, ScrollView, Switch, Button, GradientDrawable,
                  Color, Gravity, TypedValue, Typeface, RadioGroup, RadioButton):
            spider = self
            kit = self._kit(act)

            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))
            box.addView(kit.hint(f"目录：{dir_name}\n请选择要切换的 JSON 文件"),
                        kit.lp(-1, -2))

            group = RadioGroup(act)
            group.setOrientation(LinearLayout.VERTICAL)
            group.setLayoutParams(kit.lp(-1, -2))
            radio_buttons = {}
            for idx, fpath in enumerate(json_files):
                rb = RadioButton(act)
                rb.setId(idx + 1000)
                rb.setText(f"{idx+1}. {os.path.basename(fpath)}")
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
                group.addView(rb, kit.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_XS)))
                radio_buttons[fpath] = rb
                if fpath == item.get("selected"):
                    try:
                        group.check(rb.getId())
                    except Exception:
                        pass
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

    def _open_manage_switch(self):
        """管理本地接口：卡片式列表 + 批量操作栏，显隐状态用徽标展示。"""
        def on_ui(act, Builder, EditText, TextView, LinearLayout, LP, InputType,
                  DialogClick, Toast, ScrollView, Switch, Button, GradientDrawable,
                  Color, Gravity, TypedValue, Typeface, RadioGroup, RadioButton):
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
                    selected = info.get('selected', '')
                    if selected and os.path.exists(selected):
                        try:
                            with open(selected, 'r', encoding='utf-8') as f:
                                content = f.read()
                            spider._show_modern_text_editor(
                                f"✏️ 编辑 - {dir_name}", content, selected, "",
                                "file://" + os.path.abspath(selected),
                                lambda: spider._notify_app("已保存"))
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
        """扫描指定目录，匹配扩展名，生成合集 JSON，实现两级去重（内容MD5 -> 文件名）"""
        if selected_dirs is None:
            selected_dirs = self.scan_local_dirs
        if not selected_dirs:
            raise ValueError("没有选择任何扫描文件夹")
    
        exts = self.scan_local_extensions
        if not exts:
            raise ValueError("未选择任何文件类型")
    
        # 收集所有文件路径，并记录来源目录（用于排序）
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
    
        # ---- 第一级去重：按文件内容 MD5 去重（保留第一个）----
        content_hash = {}
        unique_by_content = []
        for file_path in all_files:
            try:
                with open(file_path, 'rb') as fp:
                    md5 = hashlib.md5(fp.read()).hexdigest()
            except Exception:
                continue   # 跳过无法读取的文件
            if md5 not in content_hash:
                content_hash[md5] = file_path
                unique_by_content.append(file_path)
    
        # ---- 第二级去重：按文件名去重（保留第一个，后续加 -1, -2）----
        name_count = {}
        final_files = []
        for file_path in unique_by_content:
            base = os.path.basename(file_path)
            name_without_ext = os.path.splitext(base)[0]
            ext = os.path.splitext(base)[1].lower()
            # 统计同名文件出现次数
            if name_without_ext not in name_count:
                name_count[name_without_ext] = 1
                final_name = name_without_ext
            else:
                count = name_count[name_without_ext]
                name_count[name_without_ext] = count + 1
                final_name = f"{name_without_ext}-{count}"
            final_files.append((file_path, final_name, ext))
    
        # ---- 构建 sites 列表 ----
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
            "warningText": f"本地文件合集 - 生成于 {time.strftime('%Y-%m-%d %H:%M:%S')}",
        }
    
        collection_dir = os.path.join(self.download_output_dir, "API文件")
        os.makedirs(collection_dir, exist_ok=True)
        json_path = os.path.join(collection_dir, "scan_local_files.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
    
        self._log(f"本地文件合集已生成: {json_path}，包含 {len(final_files)} 个文件（去重后）")
    
        # 添加到本地接口列表
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
    # ========================= 新增设置项 =========================
    def _open_decrypt_filename_dialog(self):
        def on_save(v):
            self.decrypt_filename_template = v
            self._save_persistent_config()
            self._save_config_to_file()
        self._show_modern_input("设置解密文件命名规则", "支持 {name} 占位符，如 {name}_m.json", self.decrypt_filename_template, on_save)

    def _open_localized_filename_dialog(self):
        def on_save(v):
            self.localized_filename_template = v
            self._save_persistent_config()
            self._save_config_to_file()
        self._show_modern_input("设置本地化主文件命名规则", "支持 {name} 占位符，如 {name}.json", self.localized_filename_template, on_save)

    def _open_inject_manager_dialog(self):
        def on_ui(act, Builder, EditText, TextView, LinearLayout, LP, InputType,
                  DialogClick, Toast, ScrollView, Switch, Button, GradientDrawable,
                  Color, Gravity, TypedValue, Typeface, RadioGroup, RadioButton):
            spider = self
            kit = self._kit(act)
            state = {"on": bool(spider.inject_manager_site)}

            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))
            box.addView(kit.switch_card(
                "注入管理中心",
                "在本地化生成的配置里自动追加一个管理中心入口",
                state["on"],
                lambda v: state.__setitem__("on", v),
            ), kit.lp(-1, -2))

            def save():
                enabled = bool(state["on"])
                spider.inject_manager_site = enabled
                spider._save_persistent_config()
                spider._save_config_to_file()
                kit.toast(f"注入已{'开启' if enabled else '关闭'}")

            buttons = [
                {"text": "取消", "style": "secondary", "callback": None, "dismiss": True},
                {"text": "保存", "style": "primary", "callback": save, "dismiss": True},
            ]
            self._show_dialog(act, "自动注入管理中心", box, buttons, height_ratio=0)
        self._run_on_ui(on_ui)
    def _open_oktv_timeout_dialog(self):
        def on_save(v):
            val = max(1, int(v))
            self.oktv_switch_timeout = val
            self._save_persistent_config()
            self._save_config_to_file()
        self._show_modern_input("设置 OKTV 切换超时 (秒)", "输入超时秒数，建议1-10", str(self.oktv_switch_timeout), on_save)

    # ========================= 获取当前接口及切换 =========================
    def _get_current_oktv_url(self):
        """尝试通过 OKTV 本地服务获取当前配置的 URL"""
        try:
            from java import jclass
            config_class = jclass("com.fongmi.android.tv.bean.Config")
            return str(config_class.vod().getUrl() or "")
        except Exception:
            try:
                proxy = jclass("com.github.catvod.Proxy")
                port = int(proxy.getPort())
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
        """判断一个 URL 是否为扫描生成的临时本地 JSON（位于 temp 目录下）"""
        if not url or not isinstance(url, str):
            return False
        if not url.startswith('file://'):
            return False
        path = url[7:]  # 去掉 file:// 前缀
        if not os.path.isabs(path):
            return False
        temp_dir = os.path.join(self.download_output_dir, "temp")
        try:
            common = os.path.commonpath([path, temp_dir])
            return common == temp_dir
        except ValueError:
            return False
    def _switch_to_url(self, url, name="自定义配置"):
        """通过 OKTV 的 sync 接口切换到任意 URL（远程 http 或本地 file://）"""
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

    # ========================= TVBox 标准接口 =========================
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
            
                # 从持久化中读取原始接口地址
                self._original_oktv_url = persistent.get("original_oktv_url")
            else:
                self._original_oktv_url = None
            
            # 获取当前运行的接口地址，并决定是否更新原始记录
            current_url = self._get_current_oktv_url()
            if current_url:
                if not self._is_temp_local_json(current_url):
                    # 非临时 JSON，更新原始地址
                    self._original_oktv_url = current_url
                    self._save_persistent_config()
                    self._log(f"更新原始接口地址: {current_url}")
                else:
                    self._log(f"当前接口为临时本地 JSON，不更新原始地址，保持: {self._original_oktv_url}")
            else:
                self._log("未能获取当前接口地址，原始接口地址保持不变")

            self.inited = True
            self._log("【init】✅ 初始化完成（v5.4）")
            self._log("=" * 50)

    def getName(self):
        return "本地包管理器 {}".format(self.VERSION)

    def homeContent(self, filter):
        self._ensure_initialized()
        classes = [
            {"type_id": "center", "type_name": "🎮管理中心"},
            {"type_id": "decrypt", "type_name": "🔐解密"},
            {"type_id": "localize", "type_name": "🥁本地"},
            {"type_id": "settings", "type_name": "🛠设置"},
        ]
        return {"class": classes, "filters": {}}

    def homeVod(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, ext):
        self._ensure_initialized()
        page = self._page_number(pg)
        if tid == "center":
            items = []

            # ---- 固定宫格：切换至原始接口 ----
            # 使用记录下来的原始地址
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
            # ---- 原有扫描接口项 ----
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
                import urllib.parse
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
            return self._paged_result(items, page)

        elif tid == "settings":
            ua_display = self.user_agent
            if len(ua_display) > 30:
                ua_display = ua_display[:30] + "..."
            gh_display = self.config.get('github_proxy', GITHUB_PROXY)
            if len(gh_display) > 30:
                gh_display = gh_display[:30] + "..."
            ext_display = self.external_api_url
            if len(ext_display) > 30:
                ext_display = ext_display[:30] + "..."

            items = [
                {"vod_id": "show_log", "vod_name": "⚡ 日志面板", "vod_pic": "", "vod_remarks": "实时查看下载日志与进度", "action": "show_log"},
                {"vod_id": "setting_log_enabled", "vod_name": "⚡ 日志开关", "vod_pic": "", "vod_remarks": "已开启" if self.log_enabled else "已关闭", "action": "local_source_edit_log_enabled"},
                {"vod_id": "setting_log_level", "vod_name": "⚡ 日志级别", "vod_pic": "", "vod_remarks": self.log_level.upper(), "action": "local_source_edit_log_level"},
                {"vod_id": "setting_log_dir", "vod_name": "☷ 日志目录", "vod_pic": "", "vod_remarks": self.log_dir.rstrip('/') if self.log_dir else "未设置", "action": "local_source_edit_log_dir"},
                {"vod_id": "setting_download_dir", "vod_name": "☷ 本地包下载目录", "vod_pic": "", "vod_remarks": self.download_output_dir or "未设置", "action": "local_source_edit_download_dir"},
                {"vod_id": "setting_sites", "vod_name": "✏️ 在线接口管理", "vod_pic": "", "vod_remarks": "添加/删除/更新在线源", "action": "local_source_manage_sites"},
                {"vod_id": "setting_overwrite", "vod_name": "✍️ 覆盖已有文件", "vod_pic": "", "vod_remarks": "是" if self.download_config.get('overwrite', False) else "否", "action": "local_source_edit_overwrite"},
                {"vod_id": "setting_inject_manager", "vod_name": "⚙️ 自动注入管理接口", "vod_pic": "", "vod_remarks": "开启" if self.inject_manager_site else "关闭", "action": "local_source_edit_inject_manager"},
                {"vod_id": "setting_decrypt_filename", "vod_name": "✒️ 解密文件命名规则", "vod_pic": "", "vod_remarks": self.decrypt_filename_template, "action": "local_source_edit_decrypt_filename"},
                {"vod_id": "setting_localized_filename", "vod_name": "✒️ 本地化文件命名规则", "vod_pic": "", "vod_remarks": self.localized_filename_template, "action": "local_source_edit_localized_filename"},
                {"vod_id": "setting_max_file_size", "vod_name": "✂️ 最大文件大小 (MB)", "vod_pic": "", "vod_remarks": str(self.download_config.get('max_file_size_mb', 100)), "action": "local_source_edit_max_file_size"},
                {"vod_id": "setting_chunk_size", "vod_name": "✒️ 分块文件大小 (KB)", "vod_pic": "", "vod_remarks": str(self.download_config.get('chunk_size', 8192)), "action": "local_source_edit_chunk_size"},
                {"vod_id": "setting_recursive_depth", "vod_name": "❓️ 递归解析深度", "vod_pic": "", "vod_remarks": str(self.download_config.get('recursive_depth', 2)), "action": "local_source_edit_recursive_depth"},
                {"vod_id": "setting_max_workers", "vod_name": "➕️ 下载并发数", "vod_pic": "", "vod_remarks": str(self.max_workers), "action": "local_source_edit_max_workers"},
                {"vod_id": "setting_retry_total", "vod_name": "➰️ HTTP 重试次数", "vod_pic": "", "vod_remarks": str(self.retry_total), "action": "local_source_edit_retry_total"},
                {"vod_id": "setting_timeout_connect", "vod_name": "⏱️ 连接超时 (秒)", "vod_pic": "", "vod_remarks": str(self.download_config.get('timeout_connect', 10)), "action": "local_source_edit_timeout_connect"},
                {"vod_id": "setting_timeout_read", "vod_name": "⏱️ 读取超时 (秒)", "vod_pic": "", "vod_remarks": str(self.download_config.get('timeout_read', 60)), "action": "local_source_edit_timeout_read"},
                {"vod_id": "setting_oktv_timeout", "vod_name": "⏱️接口切换超时(秒)", "vod_pic": "", "vod_remarks": str(self.oktv_switch_timeout), "action": "local_source_edit_oktv_timeout"},
                {"vod_id": "setting_user_agent", "vod_name": "✈️ User‑Agent", "vod_pic": "", "vod_remarks": ua_display, "action": "local_source_edit_user_agent"},
                {"vod_id": "setting_github_proxy", "vod_name": "✨️ GitHub 加速代理", "vod_pic": "", "vod_remarks": gh_display, "action": "local_source_edit_github_proxy"},
                {"vod_id": "setting_proxy", "vod_name": "✈️ 全局代理", "vod_pic": "", "vod_remarks": self.config.get('proxy', '') or "未设置", "action": "local_source_edit_proxy"},
                {"vod_id": "setting_external_api", "vod_name": "✴️ 备用解密接口", "vod_pic": "", "vod_remarks": ext_display, "action": "local_source_edit_external_api"},
                {"vod_id": "setting_restore_default", "vod_name": "➰️ 恢复默认设置", "vod_pic": "", "vod_remarks": "恢复初始配置（清除运行时修改）", "action": "local_source_restore_default"},
            ]
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
                            self._show_modern_text_editor(
                                f"⚙️ 解密内容 - {site['name']}",
                                content,
                                local_path,
                                remote_url,
                                local_url,
                                on_save
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

            extra_btns = []
            remote_url = site['url']
            extra_btns.append({"text": "远程U", "callback": lambda: self._copy_to_clipboard(remote_url, "已复制远程接口URL")})

            if status == 'success':
                local_path = state.get('localize_result')
                if local_path:
                    local_url = "file://" + os.path.abspath(local_path)
                    extra_btns.append({"text": "本地U", "callback": lambda: self._copy_to_clipboard(local_url, "已复制本地接口路径")})
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

        # 设置类
        if action == 'show_status':
            status_msg = self._package_download_message or "空闲"
            self._show_modern_info("下载状态", status_msg, show_copy=True)
        elif action == 'show_log' or action == 'show_monitor':
            self._show_log_dialog()
        elif action == 'local_source_manage_sites':
            self._open_site_management_dialog()
        elif action == 'local_source_edit_download_dir':
            self._open_download_dir_dialog()
        elif action == 'local_source_edit_user_agent':
            self._open_user_agent_dialog()
        elif action == 'local_source_edit_github_proxy':
            self._open_github_proxy_dialog()
        elif action == 'local_source_edit_max_workers':
            self._open_max_workers_dialog()
        elif action == 'local_source_edit_retry_total':
            self._open_retry_total_dialog()
        elif action == 'local_source_edit_max_file_size':
            self._open_max_file_size_dialog()
        elif action == 'local_source_edit_recursive_depth':
            self._open_recursive_depth_dialog()
        elif action == 'local_source_edit_timeout_connect':
            self._open_timeout_connect_dialog()
        elif action == 'local_source_edit_timeout_read':
            self._open_timeout_read_dialog()
        elif action == 'local_source_edit_chunk_size':
            self._open_chunk_size_dialog()
        elif action == 'local_source_edit_overwrite':
            self._open_overwrite_dialog()
        elif action == 'local_source_edit_proxy':
            self._open_proxy_dialog()
        elif action == 'local_source_edit_external_api':
            self._open_external_api_dialog()
        elif action == 'local_source_edit_log_enabled':
            self._open_log_enabled_dialog()
        elif action == 'local_source_edit_log_level':
            self._open_log_level_dialog()
        elif action == 'local_source_edit_log_dir':
            self._open_log_dir_dialog()
        elif action == 'local_source_restore_default':
            self._show_modern_confirm(
                "确认恢复初始配置",
                "确定要恢复初始配置吗？\n将清除所有运行时修改（缓存、持久化配置、接口状态等），重新加载初始数据。",
                lambda: self._exec_with_log(self._restore_default_config)
            )
        elif action == 'local_source_edit_decrypt_filename':
            self._open_decrypt_filename_dialog()
        elif action == 'local_source_edit_localized_filename':
            self._open_localized_filename_dialog()
        elif action == 'local_source_edit_inject_manager':
            self._open_inject_manager_dialog()
        elif action == 'local_source_edit_oktv_timeout':
            self._open_oktv_timeout_dialog()
        else:
            self._log(f"未知 action: {action}")
        return {"code": 0, "msg": ""}

    # ===== 取消方法 =====
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

    # ===== 文本编辑器 =====
    # ===== 文本编辑器 =====
    def _show_modern_text_editor(self, title, content, file_path, remote_url, local_url, on_save):
        def on_ui(act, Builder, EditText, TextView, LinearLayout, LP, InputType,
                  DialogClick, Toast, ScrollView, Switch, Button, GradientDrawable,
                  Color, Gravity, TypedValue, Typeface, RadioGroup, RadioButton):
            spider = self
            kit = self._kit(act)
            G = kit.gravity()

            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))

            edit = kit.input(value=content, multiline=True, mono=True,
                             min_lines=8, max_lines=24)
            edit.setEnabled(False)
            try:
                edit.setFocusable(False)
                edit.setFocusableInTouchMode(False)
                edit.setHorizontalScrollBarEnabled(True)
                edit.setVerticalScrollBarEnabled(True)
                if G:
                    edit.setGravity(G.TOP | G.START)
            except Exception:
                pass

            state = {"editable": False}
            toggle_btn = {"btn": None}

            def _sync_toggle():
                btn = toggle_btn.get("btn")
                if btn is None:
                    return
                btn.setText("🔒 锁定" if state["editable"] else "✏️ 编辑")
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
                edit.setEnabled(state["editable"])
                try:
                    edit.setFocusable(state["editable"])
                    edit.setFocusableInTouchMode(state["editable"])
                    if state["editable"]:
                        edit.requestFocus()
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

            # 顶部工具条：解密U / 编辑(锁定) / 复制 —— 手动排布以便拿到"编辑"按钮引用
            top_row = kit.hbox()
            top_row.setLayoutParams(kit.lp(-1, -2))
            if G:
                top_row.setGravity(G.CENTER)
            btn_decrypt = _make_tool_button("🔑 解密U", "secondary", copy_decrypt_url)
            btn_toggle = _make_tool_button("✏️ 编辑", "secondary", toggle_edit)
            btn_copy = _make_tool_button("📋 复制", "secondary", copy_content)
            top_row.addView(btn_decrypt)
            top_row.addView(self._with_margin(kit, btn_toggle, UITheme.S_XS))
            top_row.addView(self._with_margin(kit, btn_copy, UITheme.S_XS))
            toggle_btn["btn"] = btn_toggle
            _sync_toggle()

            box.addView(top_row, kit.lp(-1, -2))

            box.addView(kit.hint("默认只读，点「编辑」后可修改并保存"),
                        kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, UITheme.S_XS)))
            box.addView(edit, kit.lp(-1, -2))

            buttons = [
                {"text": "🌐 远程U", "style": "secondary", "callback": copy_remote_url, "dismiss": False},
                {"text": "保存", "style": "primary", "callback": do_save_content, "dismiss": True},
                {"text": "关闭", "style": "secondary", "callback": None, "dismiss": True},
            ]
            self._show_dialog(act, title, box, buttons, width_ratio=0.94, height_ratio=0.88)
        self._run_on_ui(on_ui)

    # ===== 批量选择器 =====
    # ===== 批量选择器 =====
    def _show_modern_batch_selector(self, title, callback):
        """批量选择器（开关版）：与在线接口管理保持一致的卡片样式。"""
        def on_ui(act, Builder, EditText, TextView, LinearLayout, LP, InputType,
                  DialogClick, Toast, ScrollView, Switch, Button, GradientDrawable,
                  Color, Gravity, TypedValue, Typeface, RadioGroup, RadioButton):
            spider = self
            kit = self._kit(act)

            site_states = {}
            for site in spider.package_download_sites:
                site_states[str(site.get("id", ""))] = site.get("enabled", True)

            container = kit.vbox()
            container.setLayoutParams(kit.lp(-1, -2))

            card = kit.card()
            card.addView(kit.section_title("☑️ 选择接口", hint="打开开关表示选中该接口"),
                         kit.lp(-1, -2))

            sites_container = kit.vbox()
            sites_container.setLayoutParams(kit.lp(-1, -2))

            def refresh_all():
                sites_container.removeAllViews()
                if not spider.package_download_sites:
                    sites_container.addView(kit.empty("暂无接口"), kit.lp(-1, -2))
                    return
                for site in spider.package_download_sites:
                    sid = str(site.get("id", ""))

                    def make_toggle(key=sid):
                        def on_change(v):
                            site_states[key] = bool(v)
                        return on_change

                    sites_container.addView(
                        spider._ui_site_card(kit, site.get("name", "未命名"),
                                             site.get("url", ""),
                                             site_states.get(sid, True),
                                             make_toggle(), []),
                        kit.lp(-1, -2))

            def select_all():
                for k in list(site_states.keys()):
                    site_states[k] = True
                refresh_all()

            def select_none():
                for k in list(site_states.keys()):
                    site_states[k] = False
                refresh_all()

            def invert_select():
                for k in list(site_states.keys()):
                    site_states[k] = not site_states[k]
                refresh_all()

            card.addView(kit.button_bar([
                {"text": "全选", "style": "secondary", "callback": select_all, "dismiss": False},
                {"text": "反选", "style": "secondary", "callback": invert_select, "dismiss": False},
                {"text": "清空", "style": "secondary", "callback": select_none, "dismiss": False},
            ], size="sm"), kit.lp(-1, -2, 0.0, (0.0, 0.0, 0.0, UITheme.S_SM)))

            card.addView(sites_container, kit.lp(-1, -2))
            refresh_all()
            container.addView(card, kit.lp(-1, -2))

            def do_confirm():
                selected = []
                for sid, state in site_states.items():
                    if state:
                        for s in spider.package_download_sites:
                            if str(s.get("id", "")) == sid:
                                selected.append(s)
                                break
                callback(selected)

            buttons = [
                {"text": "取消", "style": "secondary", "callback": None, "dismiss": True},
                {"text": "确定", "style": "primary", "callback": do_confirm, "dismiss": True},
            ]
            self._show_dialog(act, title, container, buttons, height_ratio=0.85)
        self._run_on_ui(on_ui)

    # ===== 被删除的方法占位（避免调用错误） =====
    def _open_package_download_url_dialog(self):
        self._notify_app("该功能已合并至「在线接口管理」")

    def _open_package_download_delete_dialog(self):
        self._notify_app("该功能已合并至「在线接口管理」")

    def _show_root_dirs_selector(self):
        self._open_root_dirs_management()

    # ===== 设置弹窗（原有，仅保留调用） =====
    def _open_download_dir_dialog(self):
        self._show_modern_input("设置本地包输出目录", "/storage/emulated/0/download/本地包",
                                self.download_output_dir,
                                lambda v: (setattr(self, 'download_output_dir', v or "/storage/emulated/0/download/本地包"),
                                           os.makedirs(self.download_output_dir, exist_ok=True),
                                           self._save_config_to_file()))

    def _open_user_agent_dialog(self):
        def on_save(v):
            self._update_config_value('user_agent', v)
            self.user_agent = v
        self._show_modern_input("设置 User-Agent", "输入 User-Agent 字符串", self.user_agent, on_save)

    def _open_github_proxy_dialog(self):
        def on_save(v):
            self._update_config_value('github_proxy', v)
            self.config['github_proxy'] = v
            self.download_config['github_proxy'] = v
        self._show_modern_input("设置 GitHub 代理", "输入 GitHub 代理前缀 URL", self.config.get('github_proxy', GITHUB_PROXY), on_save)

    def _open_max_workers_dialog(self):
        def on_save(v):
            val = max(1, min(16, int(v)))
            self._update_config_value('download.max_workers', val)
            self.max_workers = val
        self._show_modern_input("设置下载并发数", "输入最大并发数 (1-16)", str(self.max_workers), on_save)

    def _open_retry_total_dialog(self):
        def on_save(v):
            val = max(0, min(5, int(v)))
            self._update_config_value('download.retry_total', val)
            self.retry_total = val
        self._show_modern_input("设置 HTTP 重试次数", "输入重试次数 (0-5)", str(self.retry_total), on_save)

    def _open_max_file_size_dialog(self):
        def on_save(v):
            val = max(1, int(v))
            self._update_config_value('download.max_file_size_mb', val)
            self.download_config['max_file_size_mb'] = val
        self._show_modern_input("设置最大文件大小 (MB)", "输入单文件大小限制 (MB)", str(self.download_config.get('max_file_size_mb', 100)), on_save)

    def _open_recursive_depth_dialog(self):
        def on_save(v):
            val = max(0, min(5, int(v)))
            self._update_config_value('download.recursive_depth', val)
            self.download_config['recursive_depth'] = val
        self._show_modern_input("设置递归深度", "输入 JSON 递归解析深度 (0-5)", str(self.download_config.get('recursive_depth', 2)), on_save)

    def _open_timeout_connect_dialog(self):
        def on_save(v):
            val = max(1, int(v))
            self._update_config_value('download.timeout_connect', val)
            self.download_config['timeout_connect'] = val
        self._show_modern_input("设置连接超时 (秒)", "输入连接超时秒数", str(self.download_config.get('timeout_connect', 10)), on_save)

    def _open_timeout_read_dialog(self):
        def on_save(v):
            val = max(1, int(v))
            self._update_config_value('download.timeout_read', val)
            self.download_config['timeout_read'] = val
        self._show_modern_input("设置读取超时 (秒)", "输入读取超时秒数", str(self.download_config.get('timeout_read', 60)), on_save)

    def _open_chunk_size_dialog(self):
        def on_save(v):
            val = max(1024, int(v))
            self._update_config_value('download.chunk_size', val)
            self.download_config['chunk_size'] = val
        self._show_modern_input("设置块大小 (字节)", "输入下载块大小 (字节)", str(self.download_config.get('chunk_size', 8192)), on_save)

    def _open_overwrite_dialog(self):
        def on_ui(act, Builder, EditText, TextView, LinearLayout, LP, InputType,
                  DialogClick, Toast, ScrollView, Switch, Button, GradientDrawable,
                  Color, Gravity, TypedValue, Typeface, RadioGroup, RadioButton):
            spider = self
            kit = self._kit(act)
            state = {"on": bool(self.download_config.get('overwrite', False))}

            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))
            box.addView(kit.hint("开启后，下载时同名文件会被重新覆盖；关闭则跳过已存在的文件。"),
                        kit.lp(-1, -2))
            box.addView(kit.switch_card(
                "覆盖已有文件",
                "当前：{}".format("开启" if state["on"] else "关闭"),
                state["on"],
                lambda v: state.__setitem__("on", v),
            ), kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))

            def save():
                enabled = bool(state["on"])
                spider._update_config_value('download.overwrite', enabled)
                spider.download_config['overwrite'] = enabled
                kit.toast(f"覆盖已{'开启' if enabled else '关闭'}")

            buttons = [
                {"text": "取消", "style": "secondary", "callback": None, "dismiss": True},
                {"text": "保存", "style": "primary", "callback": save, "dismiss": True},
            ]
            self._show_dialog(act, "覆盖开关", box, buttons, height_ratio=0)
        self._run_on_ui(on_ui)

    def _open_proxy_dialog(self):
        def on_save(v):
            self._update_config_value('proxy', v)
            self.config['proxy'] = v
            self.download_config['proxy'] = v
        self._show_modern_input("设置全局代理", "输入代理地址 (如 http://127.0.0.1:7890)，留空取消", self.config.get('proxy', ''), on_save)

    def _open_external_api_dialog(self):
        def on_save(v):
            self._update_config_value('external_api_url', v)
            self._update_config_value('download.decrypt.external_api_url', v)
            self.external_api_url = v
        self._show_modern_input("设置备用解密接口", "输入外部解密API URL", self.external_api_url, on_save)

    def _open_log_enabled_dialog(self):
        def on_ui(act, Builder, EditText, TextView, LinearLayout, LP, InputType,
                  DialogClick, Toast, ScrollView, Switch, Button, GradientDrawable,
                  Color, Gravity, TypedValue, Typeface, RadioGroup, RadioButton):
            spider = self
            kit = self._kit(act)
            state = {"on": bool(spider.log_enabled)}

            box = kit.vbox()
            box.setLayoutParams(kit.lp(-1, -2))
            box.addView(kit.switch_card(
                "启用文件日志",
                "日志目录：{}\n当前状态：{}".format(
                    spider.log_dir, "开启" if spider.log_enabled else "关闭"),
                state["on"],
                lambda v: state.__setitem__("on", v),
            ), kit.lp(-1, -2))
            box.addView(kit.hint("日志文件保存在上面目录的 download.log 中。"),
                        kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))

            def save():
                enabled = bool(state["on"])
                spider.log_enabled = enabled
                spider._update_config_value('log.enabled', enabled, raw=True)
                kit.toast(f"日志已{'开启' if enabled else '关闭'}")

            buttons = [
                {"text": "取消", "style": "secondary", "callback": None, "dismiss": True},
                {"text": "保存", "style": "primary", "callback": save, "dismiss": True},
            ]
            self._show_dialog(act, "日志开关", box, buttons, height_ratio=0)
        self._run_on_ui(on_ui)

    def _open_log_level_dialog(self):
        options = [('debug', 'DEBUG'), ('info', 'INFO'), ('warn', 'WARN'), ('error', 'ERROR')]
        def on_confirm(val):
            self.log_level = val
            self._update_config_value('log.level', val, raw=True)
            self._notify_app(f"日志级别已设为: {val.upper()}")
        self._show_modern_radio_selector("设置日志级别", options, self.log_level.lower(), on_confirm)

    def _open_log_dir_dialog(self):
        def on_save(v):
            self._update_config_value('log.dir', v.rstrip('/') + '/', raw=True)
            self.log_dir = v.rstrip('/') + '/'
        self._show_modern_input("设置日志目录", "输入日志保存路径", self.log_dir.rstrip('/'), on_save)

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
    # ========================= JSON注释清理 & 多仓工具 =========================
    def _clean_json_comments(self, text):
        """智能清理JSON中的注释，支持 //、/* */、//**、# 等格式，保留字符串内容"""
        import re
        if not text or not isinstance(text, str):
            return text or ""

        # 保护字符串：临时替换字符串内容
        string_placeholders = []
        counter = [0]

        def protect_string(match):
            placeholder = f'__STR_PLACEHOLDER_{counter[0]}__'
            string_placeholders.append(match.group(0))
            counter[0] += 1
            return placeholder

        # 匹配字符串（包括转义引号）
        string_pattern = r'"(?:\\.|[^"\\])*"'
        protected = re.sub(string_pattern, protect_string, text)

        # 清理 //** 文档注释 (多行)
        protected = re.sub(r'//\*\*[\s\S]*?\*/', '', protected)
        # 清理 /* */ 块注释
        protected = re.sub(r'/\*[\s\S]*?\*/', '', protected)
        # 清理 // 行注释
        protected = re.sub(r'//.*$', '', protected, flags=re.MULTILINE)
        # 清理 # 行注释
        protected = re.sub(r'^\s*#.*$', '', protected, flags=re.MULTILINE)

        # 清理多余空行，但保留结构
        lines = [line for line in protected.split('\n') if line.strip()]
        cleaned = '\n'.join(lines)

        # 恢复字符串
        def restore_string(match):
            idx = int(match.group(1))
            return string_placeholders[idx] if idx < len(string_placeholders) else '""'

        result = re.sub(r'__STR_PLACEHOLDER_(\d+)__', restore_string, cleaned)
        return result.strip()

    def _parse_multi_warehouse_json(self, text):
        """解析多仓JSON格式 {"urls":[{"name":"...","url":"..."}]}"""
        import json
        try:
            cleaned = self._clean_json_comments(text)
            data = json.loads(cleaned)
            if isinstance(data, dict) and 'urls' in data:
                urls = data['urls']
                if isinstance(urls, list):
                    imported = []
                    for item in urls:
                        if isinstance(item, dict):
                            name = str(item.get('name', '未命名')).strip()
                            url = str(item.get('url', '')).strip()
                            if name and url:
                                imported.append({'name': name, 'url': url})
                    return imported
            return []
        except Exception as e:
            self._log(f"解析多仓JSON失败: {e}")
            return []

    def _copy_sites_as_multi_warehouse(self, sites):
        """将接口列表复制为多仓JSON格式到剪贴板"""
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
        """统一批量选择器（解密 / 本地化共用）：卡片式列表，风格与其它弹窗完全一致。"""
        def on_ui(act, Builder, EditText, TextView, LinearLayout, LP, InputType,
                  DialogClick, Toast, ScrollView, Switch, Button, GradientDrawable,
                  Color, Gravity, TypedValue, Typeface, RadioGroup, RadioButton):
            spider = self
            kit = self._kit(act)

            # 临时选中状态（不持久化，仅用于本次批量操作）
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
                            def on_save_name(new_name):
                                def on_save_url(new_url):
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
                                spider._show_modern_input("编辑接口地址", "https://", surl, on_save_url)
                            spider._show_modern_input("编辑备注名", "输入名称", sname, on_save_name)
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

            # ===== 单接口添加 =====
            add_card = kit.card()
            add_card.addView(kit.section_title("➕ 添加单接口"), kit.lp(-1, -2))
            name_edit = kit.input(hint="备注名（如：饭太硬）")
            add_card.addView(name_edit, kit.lp(-1, -2))
            url_edit = kit.input(hint="https://example.com/box.json")
            add_card.addView(url_edit, kit.lp(-1, -2, 0.0, (0.0, UITheme.S_SM, 0.0, 0.0)))

            def do_add_single():
                try:
                    name = str(name_edit.getText()).strip()
                    url = str(url_edit.getText()).strip()
                    with spider.lock:
                        saved, created = spider._add_or_update_package_download_site(name, url)
                    site_states[str(saved["id"])] = True
                    kit.toast("已{}：{}".format("添加" if created else "更新", saved["name"]), long=True)
                    name_edit.setText("")
                    url_edit.setText("")
                    refresh_site_list()
                except Exception as exc:
                    kit.toast("添加失败: {}".format(exc), long=True)

            add_card.addView(
                kit.button_bar([{"text": "添加 / 更新", "style": "primary",
                                 "callback": do_add_single, "dismiss": False}], size="md"),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_MD, 0.0, 0.0)))
            container.addView(add_card, kit.lp(-1, -2))

            # ===== 多仓批量导入 =====
            import_card = kit.card()
            import_card.addView(
                kit.section_title("📥 多仓批量导入",
                                  hint='粘贴多仓 JSON，如：{"urls":[{"name":"xxx","url":"xxx"}]}'),
                kit.lp(-1, -2))
            import_edit = kit.input(multiline=True, mono=True, min_lines=4, max_lines=8)
            import_card.addView(import_edit, kit.lp(-1, -2))

            def do_import():
                try:
                    text = str(import_edit.getText()).strip()
                    if not text:
                        kit.toast("请输入内容")
                        return
                    imported = spider._parse_multi_warehouse_json(text)
                    if not imported:
                        kit.toast("未解析到有效接口", long=True)
                        return
                    count = 0
                    for item in imported:
                        try:
                            with spider.lock:
                                saved, _ = spider._add_or_update_package_download_site(
                                    item['name'], item['url'])
                                site_states[str(saved["id"])] = True
                            count += 1
                        except Exception:
                            pass
                    kit.toast("成功导入 {} 个接口".format(count), long=True)
                    import_edit.setText("")
                    refresh_site_list()
                except Exception as exc:
                    kit.toast("导入失败: {}".format(exc), long=True)

            import_card.addView(
                kit.button_bar([{"text": "批量导入", "style": "success",
                                 "callback": do_import, "dismiss": False}], size="md"),
                kit.lp(-1, -2, 0.0, (0.0, UITheme.S_MD, 0.0, 0.0)))
            container.addView(import_card, kit.lp(-1, -2))

            # ===== 现有接口 =====
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

            # ===== 底部按钮 =====
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
