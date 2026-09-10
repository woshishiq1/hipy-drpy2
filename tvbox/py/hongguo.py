# -*- coding: utf-8 -*-
import base64
import binascii
import ipaddress
import json
import re
import socket
import struct
from typing import Any, Dict, List, Optional, Set, Tuple, Union
try:
    from collections.abc import Mapping, Sequence
except Exception:  # Python 3.6 / 极老 Chaquopy 回退
    from collections import Mapping, Sequence  # type: ignore
from urllib.parse import parse_qsl, quote, unquote, urlsplit
import requests
try:
    from Crypto.Cipher import AES as _PY_AES
except Exception:
    _PY_AES = None
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    _HAS_CRYPTOGRAPHY = True
except Exception:
    Cipher = None
    algorithms = None
    modes = None
    _HAS_CRYPTOGRAPHY = False


def _aes_cbc_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    if _PY_AES is not None:
        return _PY_AES.new(key, _PY_AES.MODE_CBC, iv).decrypt(data)
    if _HAS_CRYPTOGRAPHY:
        decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        return decryptor.update(data) + decryptor.finalize()
    raise HongguoPluginError("红果响应解密失败")


def _hg_popcount(x: int) -> int:
    return bin(x & 0xFFFFFFFF).count("1")


def _hg_s8(v: int) -> int:
    v &= 0xFF
    return v - 256 if v >= 128 else v


def _hg_strncmp0(a: Union[bytes, bytearray], b: bytes, n: int) -> bool:
    for k in range(n):
        ca = a[k] if k < len(a) else 0
        cb = b[k] if k < len(b) else 0
        if ca != cb:
            return False
        if ca == 0:
            return True
    return True


def _hg_unwrap_v1(spade: Union[bytes, str], flag: int = 0) -> Optional[str]:
    try:
        if isinstance(spade, str):
            spade = bytes.fromhex(spade)
        L = len(spade)
        if L < 3:
            return None
        bVar5 = spade[0] ^ spade[1] ^ spade[2]
        iVar9 = bVar5 - 0x30
        if iVar9 < 1:
            return None
        uVar1 = (L - bVar5) + 0x2F
        if uVar1 < 1 or 1 + uVar1 > L:
            return None
        dest = bytearray(spade[1:1 + uVar1])
        s1 = bytearray(iVar9)
        b16 = spade[L - iVar9 - 2]
        b14 = spade[L - iVar9 - 1]
        for i in range(iVar9):
            s1[i] = b14 ^ b16 ^ spade[i + (L - iVar9)]
        if _hg_strncmp0(s1, b"app_v2", iVar9) or _hg_strncmp0(s1, b"web_v2", iVar9):
            return None
        b14, b16 = 0x55, 0xFA
        for i in range(uVar1):
            b6 = dest[i]
            u18 = _hg_popcount(i)
            b3, b7 = b6, b14
            if i & 1:
                b3, b7, b16 = b16, b6, b14
            cVar4 = (u18 + 0x15) if flag else _hg_s8(-0x15 - u18)
            dest[i] = (cVar4 + (b16 ^ b6)) & 0xFF
            b14, b16 = b7, b3
        b0 = dest[0]
        if 0x30 <= b0 <= 0x39:
            u11 = b0 - 0x30
        elif 0x61 <= b0 <= 0x7A:
            u11 = b0 - 0x57
        else:
            return None
        iv9 = uVar1 - (u11 & 0xFF)
        if iv9 < 2:
            return None
        return bytes(dest[1:iv9]).decode("latin1", "replace")
    except Exception:
        return None


def _hg_spade_to_key(spade_a_b64: str) -> Optional[str]:
    try:
        raw = base64.b64decode(str(spade_a_b64 or "") + "=" * (-len(str(spade_a_b64 or "")) % 4), validate=False)
        if len(raw) < 16:
            return None
        key = _hg_unwrap_v1(raw, 0)
        if not key or len(key) != 32:
            return None
        try:
            bytes.fromhex(key)
        except Exception:
            return None
        return key.lower()
    except Exception:
        return None


def _hg_box_iter(d: bytes, s: int, e: int):
    o = s
    n = len(d)
    if e > n:
        e = n
    while o + 8 <= e:
        sz = struct.unpack(">I", d[o:o + 4])[0]
        t = d[o + 4:o + 8]
        hs = 8
        if sz == 1:
            if o + 16 > e:
                break
            sz = struct.unpack(">Q", d[o + 8:o + 16])[0]
            hs = 16
        elif sz == 0:
            sz = e - o
        if sz < 8 or o + sz > e + 16:
            break
        yield t, o, sz, hs
        o += sz


def _hg_find(d: bytes, path: List[bytes], s: int = 0, e: Optional[int] = None):
    if e is None:
        e = len(d)
    for t, o, sz, hs in _hg_box_iter(d, s, e):
        if t == path[0]:
            if len(path) == 1:
                return (o + hs, o + sz)
            return _hg_find(d, path[1:], o + hs, o + sz)
    return None


def _hg_u32(d: bytes, o: int) -> int:
    return struct.unpack(">I", d[o:o + 4])[0]


def _hg_track_samples(d: bytes, handler: bytes):
    mv = _hg_find(d, [b"moov"])
    if not mv:
        return [], []
    traks = [(o + hs, o + sz) for t, o, sz, hs in _hg_box_iter(d, mv[0], mv[1]) if t == b"trak"]

    def _hdlr(tr):
        h = _hg_find(d, [b"mdia", b"hdlr"], tr[0], tr[1])
        return d[h[0] + 8:h[0] + 12] if h else None
    want = [t for t in traks if _hdlr(t) == handler]
    if not want:
        return [], []
    stbl = _hg_find(d, [b"mdia", b"minf", b"stbl"], want[0][0], want[0][1])
    if not stbl:
        return [], []
    stsz = _hg_find(d, [b"stsz"], stbl[0], stbl[1])
    stco = _hg_find(d, [b"stco"], stbl[0], stbl[1])
    co64 = _hg_find(d, [b"co64"], stbl[0], stbl[1])
    stsc = _hg_find(d, [b"stsc"], stbl[0], stbl[1])
    if not stsz or (not stco and not co64) or not stsc:
        return [], []
    ss = _hg_u32(d, stsz[0] + 4)
    cnt = _hg_u32(d, stsz[0] + 8)
    if cnt <= 0 or cnt > 100000:
        return [], []
    sizes = [ss] * cnt if ss else [_hg_u32(d, stsz[0] + 12 + 4 * i) for i in range(cnt)]
    if stco:
        n = _hg_u32(d, stco[0] + 4)
        ch = [_hg_u32(d, stco[0] + 8 + 4 * i) for i in range(n)]
    else:
        n = _hg_u32(d, co64[0] + 4)
        ch = [struct.unpack(">Q", d[co64[0] + 8 + 8 * i:co64[0] + 16 + 8 * i])[0] for i in range(n)]
    ne = _hg_u32(d, stsc[0] + 4)
    runs = [(_hg_u32(d, stsc[0] + 8 + 12 * i), _hg_u32(d, stsc[0] + 12 + 12 * i), _hg_u32(d, stsc[0] + 16 + 12 * i)) for i in range(ne)]
    spc = [0] * len(ch)
    for i, (fc, sp, _sd) in enumerate(runs):
        last = runs[i + 1][0] - 1 if i + 1 < len(runs) else len(ch)
        for c in range(fc, last + 1):
            if 1 <= c <= len(ch):
                spc[c - 1] = sp
    offs: List[int] = []
    si = 0
    for c in range(len(ch)):
        off = ch[c]
        for _ in range(spc[c]):
            if si >= cnt:
                break
            offs.append(off)
            try:
                off += sizes[si]
            except Exception:
                break
            si += 1
    if len(offs) > len(sizes):
        offs = offs[:len(sizes)]
    return sizes, offs


def _hg_trak_senc_iv8(d: bytes, lo: int, hi: int) -> Optional[str]:
    for m in re.finditer(b"senc", d):
        o = m.start()
        if lo <= o < hi:
            p = o + 8 + 4
            if p + 8 <= len(d):
                return d[p:p + 8].hex()
    return None


def _hg_aes_ctr(key: bytes, iv_int: int, data: bytes) -> bytes:
    if _PY_AES is not None:
        try:
            from Crypto.Util.Counter import new as _ctr_new
            ctr = _ctr_new(128, initial_value=iv_int)
            return _PY_AES.new(key, _PY_AES.MODE_CTR, counter=ctr).decrypt(bytes(data))
        except Exception:
            pass
    # manual CTR via ECB (no extra dep, TV-safe)
    try:
        ecb = _PY_AES.new(key, _PY_AES.MODE_ECB) if _PY_AES is not None else None
    except Exception:
        ecb = None
    if ecb is not None:
        out = bytearray(len(data))
        blocks = (len(data) + 15) // 16
        for b in range(blocks):
            ks = ecb.encrypt((iv_int + b).to_bytes(16, "big"))
            s = b * 16
            chunk = data[s:s + 16]
            for j in range(len(chunk)):
                out[s + j] = chunk[j] ^ ks[j]
        return bytes(out)
    if _HAS_CRYPTOGRAPHY:
        from cryptography.hazmat.primitives.ciphers import Cipher as _C, algorithms as _A, modes as _M
        encryptor = _C(_A.AES(key), _M.CTR(iv_int.to_bytes(16, "big"))).encryptor()
        return encryptor.update(bytes(data)) + encryptor.finalize()
    raise HongguoPluginError("红果解密缺少AES环境")


def _hg_nal_ok(pt: bytes, sz: int) -> bool:
    p = 0
    try:
        while p + 4 <= sz:
            ln = struct.unpack(">I", pt[p:p + 4])[0]
            if ln == 0 or p + 4 + ln > sz:
                return False
            p += 4 + ln
        return p == sz
    except Exception:
        return False

def _hg_decrypt_range(buf: bytearray, key_hex: str, base_iv64: str, sizes: List[int], offs: List[int], lo: int, hi: int) -> int:
    try:
        K = bytes.fromhex(key_hex)
    except Exception:
        return 0
    try:
        biv = int(base_iv64, 16)
    except Exception:
        return 0
    # CENC: 每样本独立IV=((biv+idx)<<64)，不能用单个连续CTR复用keystream。
    # IJK在TV上(Chaquopy)每样本new一次AES重排key很慢，所以只 new 一次ECB复用key排序，每样本批量一次encrypt出全部keystream再strxor。
    ecb = None
    try:
        if _PY_AES is not None:
            ecb = _PY_AES.new(K, _PY_AES.MODE_ECB)
    except Exception:
        ecb = None
    try:
        from Crypto.Util.strxor import strxor as _strxor
    except Exception:
        _strxor = None
    done = 0
    for idx, (co, sz) in enumerate(zip(offs, sizes)):
        if co + sz <= lo or co >= hi:
            continue
        if co < 0 or sz <= 0 or co + sz > len(buf):
            continue
        try:
            data = bytes(buf[co:co + sz])
            if ecb is not None:
                base = ((biv + idx) << 64)
                nblk = (sz + 15) // 16
                # 批量构造counter块内存：每块16B big-endian
                ctr_blob = b"".join((base + b).to_bytes(16, "big") for b in range(nblk))
                ks = ecb.encrypt(ctr_blob)[:sz]
                if _strxor is not None:
                    pt = _strxor(data, ks)
                else:
                    pt = bytes(a ^ b for a, b in zip(data, ks))
            else:
                iv = ((biv + idx) << 64)
                pt = _hg_aes_ctr(K, iv, data)
            buf[co:co + sz] = pt
            done += 1
        except Exception:
            continue
    return done


class _hg_moov_cache_holder:
    cache: Dict[str, bytes] = {}
    tables: Dict[str, dict] = {}
    totals: Dict[str, int] = {}


def _hg_patch_moov_enc(buf: bytearray, lo: int, moov_end: int) -> None:
    """硬解/软解全兼容：encv->hvc1 / enca->mp4a + 加密盒同长改free。
    只改moov区间，不碰mdat；同长度替换，box尺寸/偏移/total不受影响。
    把 sinf/senc/saiz/saio/sbgp/sgpd 改成 free，EXO/IJK就不再按加密轨走，
    直接播我们已解密的明文样本；MPV不受影响。限定moov避免误伤mdat。
    """
    try:
        if moov_end <= 0 or lo < 0 or lo >= moov_end:
            return
        end = moov_end - lo
        if end > len(buf):
            end = len(buf)
        if end <= 8:
            return
        try:
            region = bytes(buf[:end])
        except Exception:
            return
        if b"encv" not in region and b"enca" not in region and b"sinf" not in region and b"senc" not in region:
            return
        try:
            region = region.replace(b"encv", b"hvc1").replace(b"enca", b"mp4a")
            # 加密信令盒全部同长改free：尺寸不变，播放器直接当明文轨
            region = region.replace(b"sinf", b"free").replace(b"senc", b"free").replace(b"saiz", b"free").replace(b"saio", b"free").replace(b"sbgp", b"free").replace(b"sgpd", b"free")
            buf[:end] = region
        except Exception:
            pass
    except Exception:
        pass


def _hg_fetch_follow(sess, url, headers, timeout, stream=True):
    """手动跟302（最多5跳）：qznovelvod首跳必302到idouyinvod。
    每跳都带Range，真total从落地页拿；Py3.6兼容，不用新语法。
    返回 (response, final_url)，调用方负责close。
    """
    cur = url
    last = None
    try:
        for _ in range(5):
            try:
                r = sess.get(cur, headers=headers, timeout=timeout, stream=stream, allow_redirects=False)
            except Exception:
                return last, cur
            try:
                code = int(r.status_code or 0)
            except Exception:
                code = 0
            if code in (301, 302, 303, 307, 308):
                try:
                    loc = r.headers.get("Location") or r.headers.get("location") or ""
                except Exception:
                    loc = ""
                try:
                    r.close()
                except Exception:
                    pass
                if not loc:
                    return None, cur
                # 相对Location拼全
                try:
                    if loc.startswith("/"):
                        from urllib.parse import urlsplit as _sp
                        p = _sp(cur)
                        loc = p.scheme + "://" + p.netloc + loc
                except Exception:
                    pass
                cur = loc
                last = None
                continue
            return r, cur
    except Exception:
        pass
    return last, cur




# 行为与数据基线：
# /mnt/test/buye-T/vod/routes/短剧/【短剧】红果短剧.js
# SHA-256 e728c1e8f506e6a88f9e01b6f6fe846d2de5c63711e40e47b3c88743684a4759
MV_PLUGIN = {
    "id": "hongguo",
    "name": "红果短剧",
    "version": "2.0.0",
    "profile": "python-basic-v1",
    "capabilities": {
        "content": True,
        "network": True,
    },
    "concurrency": {
        "content_max_inflight": 1,
        "resolver_max_inflight": 1,
    },
    "timeouts": {
        "startup_ms": 10000,
        "health_ms": 2000,
        "content_ms": 120000,
        "resolver_ms": 1800000,
        "idle_ms": 300000,
    },
    "content_sources": [
        {
            "id": "main",
            "name": "红果短剧",
            "searchable": True,
            "quick_search": True,
            "filterable": True,
            "changeable": False,
        }
    ],
    "config_schema": {
        "type": "object",
        "properties": {},
    },
    "compatibility": {
        "upstream": "mv-native-v1",
    },
}


_API_ORIGIN = "https://djapi.999888456.xyz"
_API_HOST = "djapi.999888456.xyz"
_API_PREFIX = "/api/hongguo"
_API_PATHS = frozenset({"/home", "/category", "/search", "/detail", "/play"})
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_MAX_ITEMS = 200
_MAX_FILTER_GROUPS = 64
_MAX_FILTER_OPTIONS = 200
_MAX_PLAY_LINES = 32
_MAX_EPISODES_PER_LINE = 2000
_MAX_MEDIA_OPTIONS = 16
_CATEGORY_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
_ITEM_PREFIX = "hgv2i_"
_EPISODE_PREFIX = "hgv2e_"
_SERIES_TARGET_PREFIX = "series_id:"
_RAW_TARGET_PREFIX = "raw_id:"
_SAFE_QUERY_KEY = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_HEX = re.compile(r"^[0-9A-Fa-f]+$")
_B64URL = re.compile(r"^[A-Za-z0-9_-]+$")
_TUN_FAKE_IP = ipaddress.ip_network("198.18.0.0/15")
_ALLOWED_MEDIA_HEADERS = {
    "user-agent": "User-Agent",
    "referer": "Referer",
    "origin": "Origin",
}

_V2_TABLE = (
    104,
    64,
    70,
    166,
    190,
    168,
    143,
    130,
    225,
    254,
    251,
    217,
    196,
    34,
    45,
    60,
    29,
    20,
    103,
    105,
)

# Generated once from the user-provided 1024x1024 PNG:
# original SHA-256 475444223132d93287d4b4fae978cb351acc786ad80d613324be5aa13a6f5a60
# embedded 384x384 indexed PNG, 8618 bytes:
# SHA-256 465cb4cc776ef3426bfbf7a90b1a4518afcdc612f120b590ad315c221359e4b2
_RANK_FOLDER_PIC = "data:image/png;base64," + "".join(
    """
    iVBORw0KGgoAAAANSUhEUgAAAYAAAAGACAMAAACTGUWNAAADAFBMVEX+/v7+Vw5q5M7+hzT6pk/+dyj+ZhpZ4ctv2rT9mkSP
    2q/+kzz+TQeu2aruuGvwxnRW3sT8tFjQ1JXRyYzO2qjp1ZLqyYnQ47WM48db3Lyw4rjp2qmz1Jvm47Jo3sL+biGs48SS4Lva
    vHbxrWPv6cq5zZXWwn3O5sV34L2N3sD0uIuW1JzziEr2yqj9cB7ymmX28dz53MPZ8+jzrIPwfEF90p6k3sHUvoHQ7uDIz6Dc
    8dz97+MAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
    AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
    AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
    AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
    AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
    AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
    AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
    AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
    AAAAAAAAAAAAAAAAAAAAAACHw4gXAAABAHRSTlP/////////////////////////////////////////////////////////
    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
    """.split()
)
_RANK_FOLDERS = (
    ("rank_recommend", "全部-推荐榜"),
    ("rank_hot", "全部-热播榜"),
    ("rank_zhenguo", "全部-臻果榜"),
    ("rank_new", "全部-新剧榜"),
    ("rank_search", "全部-热搜榜"),
    ("rank_must_watch", "全部-必看榜"),
    ("rank_collect", "全部-收藏榜"),
    ("rank_human_recommend", "真人剧-推荐榜"),
    ("rank_human_hot", "真人剧-热播榜"),
    ("rank_human_new", "真人剧-新剧榜"),
    ("rank_human_search", "真人剧-热搜榜"),
    ("rank_human_must_watch", "真人剧-必看榜"),
    ("rank_human_collect", "真人剧-收藏榜"),
    ("rank_comic_recommend", "漫剧-推荐榜"),
    ("rank_comic_hot", "漫剧-热播榜"),
    ("rank_comic_new", "漫剧-新剧榜"),
    ("rank_comic_search", "漫剧-热搜榜"),
    ("rank_ai_recommend", "AI剧-推荐榜"),
    ("rank_ai_hot", "AI剧-热播榜"),
    ("rank_ai_new", "AI剧-新剧榜"),
    ("rank_ai_search", "AI剧-热搜榜"),
    ("rank_ai_must_watch", "AI剧-必看榜"),
    ("rank_ai_collect", "AI剧-收藏榜"),
)
_RANK_CATEGORY_IDS = frozenset(
    target
    for identifier, _name in _RANK_FOLDERS
    for target in (identifier, f"rank_folder:{identifier}")
)
_RANK_UPSTREAM_PAGE_LIMIT = 10
_RANK_CLIENT_LIMIT = 20


# 官方通道对照表（APK逆向所得，只增补、不动中转榜）：
# 包名 com.phoenix.read.oversea.gp 7.3.5.32 / base_dec全量反编译
# 网关域名见 com/dragon/read/kmp/app/core/rpc/i.b = "reading.snssdk.com"（逻辑网关）
# 2026-09-08真机抓包纠正：实际HTTP Host为 api5-normal-sinfonlinec.fqnovel.com
#   GET https://api5-normal-sinfonlinec.fqnovel.com/reading/bookapi/bookmall/tab/v?tab_type=16...
#   回包 data.tab_item[].cell_data[].cell_data[].video_data[]（series_id/title/episode_cnt）
# 榜单根见 RankListHolder.A2() -> GetCategoryCellDataRequest{newCategoryTab,
# rankAlgoType, rankCategoryId, queryWeeklyRankList, distinctStyle=1,
# clientReqType=LoadMore} -> dd6/c$a.getCategoryCellDataRxJava
# 接口见 dd6/c$a RpcOperation: $GET /reading/bookapi/new_category/cell/v:version/
# 日榜见 $GET /reading/bookapi/category_daily_ranklist/v:version/
_OFFICIAL_RPC_HOST = "reading.snssdk.com"
_OFFICIAL_RPC_BASE = "https://reading.snssdk.com"
_OFFICIAL_RPC_IFACE = "dd6/c$a"
_OFFICIAL_RPC_GATEWAY_CLS = "com/dragon/read/kmp/app/core/rpc/i"
# 真机抓包实证Host（2026-09-08 Reqable，bookmall/tab 6组签名样本）
_OFFICIAL_HTTP_HOST = "api5-normal-sinfonlinec.fqnovel.com"
_OFFICIAL_HTTP_BASE = "https://api5-normal-sinfonlinec.fqnovel.com"
_OFFICIAL_RANK_PATH_CELL = "/reading/bookapi/new_category/cell/v"
_OFFICIAL_RANK_PATH_DAILY = "/reading/bookapi/category_daily_ranklist/v"
_OFFICIAL_RANK_PATH_SEQ = "/reading/bookapi/ranklist/sequence/v"
_OFFICIAL_RANK_PATH_TAB = "/reading/bookapi/bookmall/tab/v"
# 官方App UA（抓包实证，不带用户device_id/iid，避免硬编码隐私）
_OFFICIAL_UA = (
    "com.phoenix.read.oversea.gp/73532 (Linux; U; Android 16; "
    "zh_CN; PKX110; Build/AP3A.240617.008;tt-ok/3.12.13.20)"
)
_OFFICIAL_COMMON_PARAMS = {
    "aid": "8662",
    "app_name": "novelread",
    "version_code": "73532",
    "version_name": "7.3.5.32",
    "device_platform": "android",
    "os": "android",
    "channel": "googleplay",
    "ac": "mobile",
    "ssmix": "a",
    "device_type": "PKX110",
    "device_brand": "OnePlus",
    "language": "zh",
    "os_api": "36",
    "os_version": "16",
    "resolution": "1080*2224",
    "dpi": "480",
}
# NewCategoryTabType（APK枚举，短剧=6）
_OFFICIAL_NEW_CATEGORY_TAB = {
    "Female": 0,
    "Male": 1,
    "Publish": 2,
    "Audio": 3,
    "Video": 4,
    "Comic": 5,
    "ShortSeries": 6,
    "Novel": 7,
    "All": 8,
    "Classic": 9,
    "Knowledge": 10,
    "DynamicComic": 11,
}
# BookAlbumAlgoType短剧系（hongguo_apk/BookAlbumAlgoType_all.txt，188个中摘录）
_OFFICIAL_SHORTPLAY_ALGO = {
    "ShortPlayRecommendList": 500,
    "ShortPlayNewList": 501,
    "RankListShortPlay": 502,
    "ShortPlayRankListHot": 503,
    "ShortPlayRankListHotPlay": 504,
    "ShortPlayRankListHotRiseRank": 505,
    "ShortPlayRankListNewRank": 506,
    "ShortPlayRankListOpHot": 507,
    "RankListShortPlayAdapt": 508,
    "RankListShortPlayOutAdapt": 509,
    "RankListShortPlayMustWatch": 510,
    "RankListShortPlayMustFollowed": 511,
    "RankListAdaptationNovel": 512,
    "RankListAdaptationStory": 513,
    "RankListDynamicComic": 550,
    "RankListDynamicComicAdapt": 551,
    "RankListDynamicComicHotPlay": 552,
    "RankListDynamicComicNewRank": 553,
    "RankListDynamicComicHotSearch": 554,
    "RankListDynamicComicMustWatch": 555,
    "RankListDynamicComicFollowed": 556,
    "RankListVideoComicMixed": 600,
    "VideoRankListShortSeriesPlay": 143,
}
# 官方榜单请求默认体（RankListHolder.A2原样）
_OFFICIAL_RANK_REQUEST = {
    "newCategoryTab": 6,
    "distinctStyle": 1,
    "clientReqType": "LoadMore",
    "queryWeeklyRankList": False,
}
# 现有23个中转rank_* -> 官方(newCategoryTab, rankAlgoType)映射（只映射、不改名）
_OFFICIAL_RANK_TID_MAP = {
    "rank_recommend": (6, 500),
    "rank_hot": (6, 503),
    "rank_zhenguo": (6, 502),
    "rank_new": (6, 501),
    "rank_search": (6, 505),
    "rank_must_watch": (6, 510),
    "rank_collect": (6, 511),
    "rank_human_recommend": (6, 500),
    "rank_human_hot": (6, 504),
    "rank_human_new": (6, 506),
    "rank_human_search": (6, 505),
    "rank_human_must_watch": (6, 510),
    "rank_human_collect": (6, 511),
    "rank_comic_recommend": (5, 500),
    "rank_comic_hot": (5, 504),
    "rank_comic_new": (5, 501),
    "rank_comic_search": (5, 505),
    "rank_ai_recommend": (11, 500),
    "rank_ai_hot": (11, 552),
    "rank_ai_new": (11, 553),
    "rank_ai_search": (11, 554),
    "rank_ai_must_watch": (11, 555),
    "rank_ai_collect": (11, 556),
}
# 官方签名现状：AntiCheatParam.XGorgon + libsscronet.so(6.0M正主)
# x-gorgon@0x7ace5/x-khronos@0x750e9/x-ss-*10组，Encryptor/dragon_crypt无签
# 2026-09-08复刻结论：log(1000行)零gorgon/khronos/ss/canary/bogus/reading.snssdk
# 命中；x-gorgon/x-khronos xref同归0x415898/0x4158a8同一函数，反编译失败；
# unidbg起libsscronet报unicorn后端缺失，纯Python无法仿真算签。
# 2026-09-08抓包结论：真Host=api5-normal-sinfonlinec.fqnovel.com/bookmall/tab，
# 6组签名一URL一签，重放必403；榜单cell/ranklist走cronet+pinning，Reqable解不出。
# TVBox纯Python暂无法直连，故官方当主用（先试）、中转当备用，榜单23个原样保留。
_OFFICIAL_ENABLE = True
_OFFICIAL_TIMEOUT = (5, 10)


def _official_tab_params(tab_index: int = 0, page: int = 1) -> Dict[str, str]:
    """bookmall/tab抓包实证参数（tab_type=16推荐/tab_type=-1找剧）+官方通用参数。"""
    try:
        params = dict(_OFFICIAL_COMMON_PARAMS)
        params.update(
            {
                "tab_type": str(tab_index),
                "tab_index": "0",
                "offset": str(max(0, _positive_page(page) - 1) * 10),
                "req_rank_category_id": "0",
                "req_rank_algo": "0",
                "client_req_type": "1028" if str(tab_index) == "16" else "3",
                "bottom_tab_type": "7",
                "landing_bottom_tab_type": "7",
                "tab_version": "double_col",
                "screen_width_px": "1080",
                "has_video_cache": "false",
                "disable_digg_stat": "false",
                "pad_column_cover": "0",
                "req_rank_category_id": "0",
            }
        )
        return params
    except Exception:
        return dict(_OFFICIAL_COMMON_PARAMS)


def _official_walk_video_data(node: Any, depth: int = 0) -> List[Dict[str, Any]]:
    """递归走 data.tab_item[].cell_data[].cell_data[].video_data[]，抓包实证结构。

    双形态守门（HAR实证）：扁平型顶层即有 series_id+title；嵌套型顶层
    title/cover 为空、真标题在 video_detail.series_title。守门两种都放行，
    最终由 _official_video_to_item 兜底 series+title，免签回小说tab
    (video_data=0)时自然为空走中转。
    """
    out: List[Dict[str, Any]] = []
    try:
        if depth > 4:
            return out
        if isinstance(node, Mapping):
            videos = node.get("video_data")
            seq = _sequence(videos)
            if seq:
                for raw in seq[:_MAX_ITEMS]:
                    if isinstance(raw, Mapping):
                        vd = raw.get("video_detail")
                        series = _text(
                            raw.get("series_id") or raw.get("group_id"), limit=64
                        )
                        if not series and isinstance(vd, Mapping):
                            try:
                                series = _text(vd.get("series_id"), limit=64)
                            except Exception:
                                pass
                        title = _text(
                            raw.get("title")
                            or raw.get("book_name")
                            or (vd.get("series_title") if isinstance(vd, Mapping) else ""),
                            limit=300,
                        )
                        if series and title:
                            out.append(raw)
                if out:
                    return out[:_MAX_ITEMS]
            for key in ("cell_data", "tab_item", "cells", "list", "items"):
                seq2 = _sequence(node.get(key))
                if seq2:
                    for child in seq2[:_MAX_ITEMS]:
                        out.extend(_official_walk_video_data(child, depth + 1))
                        if len(out) >= _MAX_ITEMS:
                            return out[:_MAX_ITEMS]
        elif not isinstance(node, (str, bytes, bytearray)):
            for child in _sequence(node)[:_MAX_ITEMS]:
                out.extend(_official_walk_video_data(child, depth + 1))
                if len(out) >= _MAX_ITEMS:
                    return out[:_MAX_ITEMS]
    except Exception:
        pass
    return out[:_MAX_ITEMS]


def _official_video_to_item(raw: Any) -> Optional[Dict[str, Any]]:
    """官方video_data -> _content_item可吃的中转形态（只映射、不改名）。

    双形态全吃（HAR实证）：
    - 扁平型(tab_type=-1找剧)：series_id/title/episode_cnt/score/rec_text/cover/vid
    - 嵌套型(tab_type=16推荐)：series_id + video_detail{series_title/series_intro/
      episode_right_text/video_list[0].vid/cover}，顶层title/cover为空
    探针语义：两种都取不到 series+title 即返回None，交由中转备用。
    """
    try:
        if not isinstance(raw, Mapping):
            return None
        vd = raw.get("video_detail")
        if not isinstance(vd, Mapping):
            vd = {}
        series = _text(raw.get("series_id") or raw.get("group_id"), limit=64)
        if not series:
            try:
                series = _text(vd.get("series_id"), limit=64)
            except Exception:
                pass
        title = _text(
            raw.get("title") or raw.get("book_name") or vd.get("series_title"),
            limit=300,
        )
        if not series or not title:
            return None
        cover = _text(
            raw.get("cover") or raw.get("thumb") or raw.get("poster"), limit=2048
        )
        if not cover:
            try:
                vl = vd.get("video_list")
                if isinstance(vl, list) and vl and isinstance(vl[0], Mapping):
                    cover = _text(vl[0].get("cover"), limit=2048)
            except Exception:
                pass
        ep_cnt = _text(
            raw.get("episode_cnt")
            or (vd.get("episode_cnt") if vd else "")
            or (vd.get("episode_right_text") if vd else ""),
            limit=64,
        )
        rec = _text(
            raw.get("rec_text")
            or raw.get("play_cnt")
            or raw.get("score"),
            limit=300,
        )
        if ep_cnt and rec:
            remarks = rec + "·" + str(ep_cnt) + "集" if "共" not in str(ep_cnt) and "集" not in str(ep_cnt) else rec + "·" + str(ep_cnt)
        else:
            remarks = rec or (str(ep_cnt) if ep_cnt else "")
            if ep_cnt and "集" not in remarks and "共" not in remarks:
                try:
                    remarks = (remarks + "·" if remarks else "") + str(ep_cnt) + "集"
                except Exception:
                    pass
        # 借中转detail/detailContent的 series_id 钥匙：直接用 series 数字串，
        # _canonical_item_target 会收成 raw_id:series，detail id=series 即通。
        # 不包 JSON，避免 /detail 收到 '{"series_id":...}' 串查不到。
        return {
            "vod_id": series,
            "vod_name": title,
            "vod_pic": cover,
            "vod_remarks": remarks,
        }
    except Exception:
        return None


def _official_fetch_tab(
    session: Any, tab_index: int = 16, page: int = 1
) -> Optional[List[Any]]:
    """抓包实证通道：bookmall/tab免签参数先试，200即解析video_data。

    无X-Gorgon大概率403/空包，此时返回None交由中转备用，不抛错。
    """
    if not _OFFICIAL_ENABLE:
        return None
    try:
        params = _official_tab_params(tab_index, page)
        headers = {
            "User-Agent": _OFFICIAL_UA,
            "Accept-Encoding": "gzip",
            "authorization": "Bearer",
            "x-tt-store-region": "cn-gd",
            "x-tt-store-region-src": "did",
        }
        resp = session.get(
            f"{_OFFICIAL_HTTP_BASE}{_OFFICIAL_RANK_PATH_TAB}",
            params=params,
            headers=headers,
            timeout=_OFFICIAL_TIMEOUT,
            allow_redirects=False,
            stream=False,
        )
        try:
            if int(resp.status_code or 0) != 200:
                return None
            try:
                payload = resp.json()
            except Exception:
                return None
            if not isinstance(payload, Mapping):
                return None
            if int(payload.get("code", -1) or -1) != 0:
                return None
            raws = _official_walk_video_data(payload.get("data"))
            items: List[Any] = []
            for raw in raws:
                adapted = _official_video_to_item(raw)
                if adapted is not None:
                    items.append(adapted)
                if len(items) >= _MAX_ITEMS:
                    break
            content = _content_items(items)
            return content or None
        finally:
            try:
                resp.close()
            except Exception:
                pass
    except Exception:
        return None
    return None


def _official_rank_params(raw_tid: str, page: int) -> Optional[Dict[str, str]]:
    try:
        mapped = _OFFICIAL_RANK_TID_MAP.get(raw_tid)
        if not mapped:
            return None
        tab, algo = mapped
        base = dict(_OFFICIAL_RANK_REQUEST)
        base["newCategoryTab"] = tab
        params: Dict[str, str] = dict(_OFFICIAL_COMMON_PARAMS)
        params.update(
            {
                "newCategoryTab": str(tab),
                "rankAlgoType": str(algo),
                "distinctStyle": str(base.get("distinctStyle", 1)),
                "clientReqType": str(base.get("clientReqType", "LoadMore")),
                "queryWeeklyRankList": "1" if base.get("queryWeeklyRankList") else "0",
                "page": str(_positive_page(page)),
            }
        )
        rank_category = _text(base.get("rankCategoryId", ""), limit=64)
        if rank_category:
            params["rankCategoryId"] = rank_category
        return params
    except Exception:
        return None


def _official_tab_index_for_tid(raw_tid: str) -> int:
    """rank_* -> bookmall/tab tab_type（抓包实证）。

    - 真人剧 human -> 39（-1/16 两条 HAR 均验证空位体，39位体切换）
    - 漫剧 comic / AI剧 ai_ -> 36
    - 全部系（recommend/hot/zhenguo/new/search/must_watch/collect）-> 16
    - 找剧聚合（-1）由 _official_fetch_rank 统一先试，不走单映射
    """
    try:
        if "human" in raw_tid:
            return 39
        if "comic" in raw_tid or "ai_" in raw_tid:
            return 36
        return 16
    except Exception:
        return 16


def _official_tab_candidates_for_tid(raw_tid: str) -> List[int]:
    """每个 rank_* 的 tab_type 候选队列（探针语义：按序试、命中即停）。

    抓包实证：-1 找剧聚合含6条扁平 shortplay；16 推荐含推荐位 video_detail；
    39/36 为分区位体。候选把聚合与分区都覆盖，避免单映射漏榜。
    """
    try:
        base = _official_tab_index_for_tid(raw_tid)
        cands = [-1, 16, 39, 36]
        ordered = [base] + [c for c in cands if c != base]
        return ordered
    except Exception:
        return [-1, 16, 39, 36]


def _official_extract_items(payload: Any) -> List[Any]:
    try:
        if isinstance(payload, Mapping):
            for key in ("list", "data", "cell_list", "cells", "items", "result"):
                seq = _sequence(payload.get(key))
                if seq:
                    # data可能是dict包list
                    if len(seq) == 1 and isinstance(seq[0], Mapping):
                        inner = seq[0]
                        for k2 in ("list", "cell_list", "items"):
                            seq2 = _sequence(inner.get(k2))
                            if seq2:
                                return seq2[:_MAX_ITEMS]
                    return seq[:_MAX_ITEMS]
            # data为dict形态
            data = payload.get("data")
            if isinstance(data, Mapping):
                for k2 in ("list", "cell_list", "items", "cells"):
                    seq2 = _sequence(data.get(k2))
                    if seq2:
                        return seq2[:_MAX_ITEMS]
        return []
    except Exception:
        return []


def _official_fetch_rank(
    session: Any, raw_tid: str, page: int
) -> Optional[List[Any]]:
    if not _OFFICIAL_ENABLE:
        return None
    headers = {
        "User-Agent": _OFFICIAL_UA,
        "Accept-Encoding": "gzip",
        "authorization": "Bearer",
        "x-tt-store-region": "cn-gd",
        "x-tt-store-region-src": "did",
    }
    # 主用通道1：真Host直连new_category/cell+daily（RankListHolder.A2原样）
    # 无X-Gorgon大概率403/412/空包，失败即走通道2，不抛错
    params = _official_rank_params(raw_tid, page)
    if params:
        urls = (
            f"{_OFFICIAL_HTTP_BASE}{_OFFICIAL_RANK_PATH_CELL}1/",
            f"{_OFFICIAL_HTTP_BASE}{_OFFICIAL_RANK_PATH_DAILY}1/",
        )
        for url in urls:
            try:
                resp = session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=_OFFICIAL_TIMEOUT,
                    allow_redirects=False,
                    stream=False,
                )
                try:
                    if int(resp.status_code or 0) != 200:
                        continue
                    try:
                        payload = resp.json()
                    except Exception:
                        continue
                    items = _official_extract_items(payload)
                    adapted = _content_items(items)
                    if adapted:
                        return adapted
                    # 官方通了但字段未适配：不误判为空榜，继续试下一通道
                    continue
                finally:
                    try:
                        resp.close()
                    except Exception:
                        pass
            except Exception:
                continue
    # 主用通道2：抓包实证bookmall/tab（探针语义：候选队列按序试、命中即停）
    # 每个 rank_* 试 [-1聚合,16推荐,39真人,36漫剧]（分区首位优先），免签直连；
    # 无签回小说tab(video_data=0)即判空继续，命中真短剧video_data即停。
    # 全部失败返回None交由中转备用，不抛错。
    try:
        for _tab in _official_tab_candidates_for_tid(raw_tid):
            try:
                tab_items = _official_fetch_tab(session, _tab, page)
            except Exception:
                continue
            if tab_items:
                return tab_items
    except Exception:
        pass
    return None


class HongguoPluginError(RuntimeError):
    """Fail-closed error without upstream IDs, URLs, or response data."""


class _HongguoRetryableRequestError(RuntimeError):
    """Internal marker for one safe retry of an idempotent category GET."""


def _sequence(value: Any) -> List[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _text(value: Any, fallback: str = "", *, limit: int = 4096) -> str:
    if value is None or value == "":
        value = fallback
    if isinstance(value, (Mapping, Sequence)) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return ""
    result = str(value or "").strip()
    if any(character in result for character in ("\0", "\r", "\n")):
        result = " ".join(result.split())
    return result[:limit]


def _positive_page(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 1
    return parsed if parsed > 0 else 1


def _strict_string(value: Any, *, max_bytes: int, field: str) -> str:
    if value is None or isinstance(value, (Mapping, list, tuple, set, bytes, bytearray)):
        raise HongguoPluginError(f"红果{field}无效")
    text = str(value).strip()
    if (
        not text
        or any(character in text for character in ("\0", "\r", "\n"))
        or len(text.encode("utf-8")) > max_bytes
    ):
        raise HongguoPluginError(f"红果{field}无效")
    return text


def _encode_opaque(prefix: str, value: Any, *, max_bytes: int) -> str:
    text = _strict_string(value, max_bytes=max_bytes, field="返回引用")
    raw = text.encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"{prefix}{encoded}"


def _decode_opaque(prefix: str, value: Any, *, max_bytes: int) -> str:
    text = _strict_string(
        value,
        max_bytes=max_bytes * 2,
        field="引用",
    )
    if not text.startswith(prefix):
        return text
    payload = text[len(prefix) :]
    if not payload or not _B64URL.fullmatch(payload):
        raise HongguoPluginError("红果引用无效")
    padding = "=" * (-len(payload) % 4)
    try:
        raw = base64.b64decode(payload + padding, altchars=b"-_", validate=True)
        decoded = raw.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise HongguoPluginError("红果引用无效") from exc
    if (
        len(raw) > max_bytes
        or base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != payload
        or not decoded
        or any(character in decoded for character in ("\0", "\r", "\n"))
    ):
        raise HongguoPluginError("红果引用无效")
    return decoded


def _encode_item_id(value: Any) -> str:
    return _encode_opaque(_ITEM_PREFIX, value, max_bytes=700)


def _decode_item_id(value: Any) -> str:
    return _decode_opaque(_ITEM_PREFIX, value, max_bytes=700)


def _canonical_item_target(value: Any) -> str:
    raw = _strict_string(value, max_bytes=16 * 1024, field="内容引用")
    if raw.startswith("rank_folder:"):
        if len(raw.encode("utf-8")) > 256:
            raise HongguoPluginError("红果内容引用无效")
        return raw
    # 官方直连 series 数字串（_official_video_to_item 产出）：直接收成
    # series_id:xxx，detail id=xxx 即通中转 /detail。必须显式前缀，
    # 否则会被当 raw 文本包成 raw_id:xxx 导致 _api_item_target 取出
    # raw_id:xxx（含前缀）查不到 /detail。
    try:
        if re.fullmatch(r"[0-9]{4,32}", raw or ""):
            return f"{_SERIES_TARGET_PREFIX}{raw}"
    except Exception:
        pass
    if raw.startswith(_SERIES_TARGET_PREFIX) or raw.startswith(_RAW_TARGET_PREFIX):
        if len(raw.encode("utf-8")) > 16 * 1024:
            raise HongguoPluginError("红果内容引用无效")
        return raw
    if len(raw) % 4 != 1 and len(raw) <= 16 * 1024:
        try:
            decoded = base64.b64decode(
                raw + "=" * (-len(raw) % 4),
                validate=True,
            )
            value = json.loads(decoded.decode("utf-8"))
        except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            value = None
        if isinstance(value, Mapping) and value.get("series_id") not in (None, ""):
            series_id = _strict_string(
                value.get("series_id"),
                max_bytes=512,
                field="剧集身份",
            )
            return f"{_SERIES_TARGET_PREFIX}{series_id}"
    if len(raw.encode("utf-8")) <= 640:
        return f"{_RAW_TARGET_PREFIX}{raw}"
    raise HongguoPluginError("红果内容引用无效")


def _api_item_target(value: str) -> str:
    if value.startswith(_SERIES_TARGET_PREFIX):
        return _strict_string(
            value[len(_SERIES_TARGET_PREFIX) :],
            max_bytes=512,
            field="剧集身份",
        )
    if value.startswith(_RAW_TARGET_PREFIX):
        return _strict_string(
            value[len(_RAW_TARGET_PREFIX) :],
            max_bytes=640,
            field="内容身份",
        )
    return value


def _item_input(value: Any) -> Tuple[str, str, bool]:
    text = _strict_string(value, max_bytes=4096, field="内容引用")
    if text.startswith(_ITEM_PREFIX):
        canonical = _decode_item_id(text)
        return canonical, _api_item_target(canonical), True
    return text, text, False


def _encode_episode_ref(value: Any) -> str:
    return _encode_opaque(_EPISODE_PREFIX, value, max_bytes=2048)


def _decode_episode_ref(value: Any) -> str:
    text = _strict_string(value, max_bytes=4096, field="播放引用")
    if not text.startswith(_EPISODE_PREFIX):
        raise HongguoPluginError("红果播放引用无效")
    return _decode_opaque(_EPISODE_PREFIX, text, max_bytes=2048)


def _derive_v2_material(key_id: str) -> bytes:
    """Equivalent to the designated JS baseline's dj(), without its VM wrapper."""

    value = str(key_id or "")
    suffix = value[4:] if len(value) > 4 else ""
    if (
        not suffix
        or len(suffix) % 2
        or len(suffix) > 1024
        or not _HEX.fullmatch(suffix)
    ):
        raise HongguoPluginError("红果响应密钥无效")
    try:
        raw = bytes.fromhex(suffix)
    except ValueError as exc:
        raise HongguoPluginError("红果响应密钥无效") from exc
    output = bytearray(len(raw))
    for index, current in enumerate(raw):
        previous = 109 if index == 0 else raw[index - 1]
        slot = index % len(_V2_TABLE)
        salt = _V2_TABLE[slot] ^ ((90 + 13 * slot) & 0xFF) ^ 85
        shifted = (current + 215 - 11 * index) & 0xFF
        rotated = ((shifted << 3) | (shifted >> 5)) & 0xFF
        output[index] = previous ^ salt ^ rotated
    return bytes(output)


def _decode_ciphertext(value: str) -> bytes:
    payload = str(value or "").strip()
    if not payload or len(payload) > _MAX_RESPONSE_BYTES * 2:
        raise HongguoPluginError("红果加密响应无效")
    if len(payload) % 4 == 1:
        raise HongguoPluginError("红果加密响应无效")
    try:
        decoded = base64.b64decode(payload + "=" * (-len(payload) % 4), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HongguoPluginError("红果加密响应无效") from exc
    if not decoded or len(decoded) % 16 or len(decoded) > _MAX_RESPONSE_BYTES:
        raise HongguoPluginError("红果加密响应无效")
    return decoded


def _decrypt_v2(body: str) -> str:
    text = str(body or "")
    if not text.startswith("v2."):
        return text
    parts = text.split(".", 2)
    if len(parts) != 3:
        raise HongguoPluginError("红果加密响应无效")
    material = _derive_v2_material(parts[1])
    if len(material) < 32:
        raise HongguoPluginError("红果响应密钥无效")
    ciphertext = _decode_ciphertext(parts[2])
    try:
        padded = _aes_cbc_decrypt(material[:16], material[16:32], ciphertext)
    except ValueError as exc:
        raise HongguoPluginError("红果响应解密失败") from exc
    padding = padded[-1] if padded else 0
    if (
        not 1 <= padding <= 16
        or len(padded) < padding
        or padded[-padding:] != bytes((padding,)) * padding
    ):
        raise HongguoPluginError("红果响应解密失败")
    try:
        return padded[:-padding].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HongguoPluginError("红果响应解密失败") from exc


def _categories(value: Any) -> List[Dict[str, str]]:
    result: List[Dict[str, str]] = []
    seen: Set[str] = set()
    for item in _sequence(value)[:_MAX_ITEMS]:
        if not isinstance(item, Mapping):
            continue
        identifier = _text(item.get("type_id") or item.get("id"), limit=256)
        name = _text(item.get("type_name") or item.get("name"), limit=100)
        if (
            not identifier
            or not name
            or identifier in seen
            or identifier.lower().startswith(("http://", "https://"))
        ):
            continue
        seen.add(identifier)
        result.append({"id": identifier, "name": name})
    return result


def _filters(value: Any) -> Dict[str, List[Dict[str, Any]]]:
    if not isinstance(value, Mapping):
        return {}
    result: Dict[str, List[Dict[str, Any]]] = {}
    total_groups = 0
    for raw_category, raw_groups in value.items():
        category_id = _text(raw_category, limit=256)
        if (
            not category_id
            or category_id.lower().startswith(("http://", "https://"))
            or any(character in category_id for character in ("\0", "\r", "\n"))
        ):
            continue
        groups: List[Dict[str, Any]] = []
        for raw_group in _sequence(raw_groups):
            if total_groups >= _MAX_FILTER_GROUPS:
                break
            if not isinstance(raw_group, Mapping):
                continue
            key = _text(raw_group.get("key") or raw_group.get("id"), limit=100)
            name = _text(raw_group.get("name") or raw_group.get("title") or key, limit=100)
            raw_options = (
                raw_group.get("options")
                or raw_group.get("value")
                or raw_group.get("values")
            )
            options: List[Dict[str, str]] = []
            for raw_option in _sequence(raw_options)[:_MAX_FILTER_OPTIONS]:
                if not isinstance(raw_option, Mapping):
                    continue
                option_name = _text(
                    raw_option.get("name")
                    or raw_option.get("n")
                    or raw_option.get("label"),
                    limit=100,
                )
                option_value = _text(
                    raw_option.get("value")
                    if raw_option.get("value") is not None
                    else raw_option.get("v")
                    if raw_option.get("v") is not None
                    else raw_option.get("id"),
                    limit=256,
                )
                if option_name:
                    options.append({"n": option_name, "v": option_value})
            if not key or not name or not options:
                continue
            group: Dict[str, Any] = {"key": key, "name": name, "value": options}
            selected = _text(raw_group.get("selected"), limit=256)
            if selected:
                group["selected"] = selected
            groups.append(group)
            total_groups += 1
        if groups:
            result[category_id] = groups
    return result


def _content_item(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, Mapping):
        return None
    try:
        raw_id = _strict_string(
            value.get("vod_id") or value.get("id"),
            max_bytes=16 * 1024,
            field="内容引用",
        )
        canonical_id = _canonical_item_target(raw_id)
    except HongguoPluginError:
        return None
    name = _text(value.get("vod_name") or value.get("name"), limit=300)
    if not raw_id or not name:
        return None
    item: Dict[str, Any] = {
        "id": _encode_item_id(canonical_id),
        "title": name,
        "poster": _text(value.get("vod_pic") or value.get("poster"), limit=2048) or None,
        "remarks": _text(value.get("vod_remarks") or value.get("remarks"), limit=300),
        "navigation": (
            "category"
            if _text(value.get("vod_tag"), limit=32) == "folder"
            or raw_id.startswith("rank_folder:")
            else "detail"
        ),
        "play_sources": [],
    }
    year = _text(value.get("vod_year") or value.get("year"), limit=32)
    if year:
        item["year"] = year
    return item


def _content_items(value: Any) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for raw in _sequence(value)[:_MAX_ITEMS]:
        item = _content_item(raw)
        if item is not None:
            result.append(item)
    return result


def _document(
    kind: str,
    *,
    items: Optional[List[Dict[str, Any]]] = None,
    categories: Optional[List[Dict[str, str]]] = None,
    filters: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    page: int = 1,
    page_count: int = 1,
    limit: int = 18,
    total: Optional[int] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    content_items = items or []
    return {
        "schema_version": "mv.python-content.v1",
        "kind": kind,
        "title": title,
        "categories": categories or [],
        "filters": filters or {},
        "items": content_items,
        "pagination": {
            "page": max(1, page),
            "page_count": max(1, page_count),
            "limit": max(1, limit),
            "total": max(0, len(content_items) if total is None else total),
        },
        "metadata": {
            "upstream_contract": "hongguo-js-v2",
        },
    }


def _rank_items() -> List[Dict[str, Any]]:
    return [
        {
            "id": _encode_item_id(f"rank_folder:{identifier}"),
            "title": name,
            "poster": _RANK_FOLDER_PIC,
            "remarks": "",
            "navigation": "category",
            "play_sources": [],
        }
        for identifier, name in _RANK_FOLDERS
    ]


def _query_value(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)) and not isinstance(value, complex):
        text = str(value).strip()
        if text.casefold() in {"nan", "inf", "+inf", "-inf", "infinity"}:
            return None
        if text and len(text.encode("utf-8")) <= 256 and not any(
            character in text for character in ("\0", "\r", "\n")
        ):
            return text
    return None


def _category_params(
    category_id: str,
    page: int,
    extend: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    result = {"tid": category_id, "pg": str(page)}
    if not isinstance(extend, Mapping):
        return result
    for raw_key, raw_value in list(extend.items())[:32]:
        key = str(raw_key or "")
        if key in {"cateId", "tid", "pg"} or not _SAFE_QUERY_KEY.fullmatch(key):
            continue
        value = _query_value(raw_value)
        if value is not None:
            result[key] = value
    return result


def _play_sources(value: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_value = value.get("vod_play_url")
    if raw_value is None or raw_value == "":
        return []
    raw_urls = _strict_string(
        raw_value,
        max_bytes=512 * 1024,
        field="播放选集",
    )
    if not raw_urls:
        return []
    lines = raw_urls.split("$$$")
    if len(lines) > _MAX_PLAY_LINES:
        raise HongguoPluginError("红果播放线路过多")
    raw_flags = _text(value.get("vod_play_from"), "播放", limit=4096).split("$$$")
    if len(raw_flags) != len(lines):
        raise HongguoPluginError("红果播放线路无效")
    sources: List[Dict[str, Any]] = []
    for line_index, line in enumerate(lines):
        episodes: List[Dict[str, str]] = []
        entries = [entry for entry in line.split("#") if entry]
        if len(entries) > _MAX_EPISODES_PER_LINE:
            raise HongguoPluginError("红果选集过多")
        for episode_index, entry in enumerate(entries):
            name, separator, raw_ref = entry.partition("$")
            if not separator:
                raw_ref = name
                name = f"第{episode_index + 1}集"
            name = _text(name, f"第{episode_index + 1}集", limit=100)
            raw_ref = _strict_string(
                raw_ref,
                max_bytes=2048,
                field="选集引用",
            )
            episodes.append(
                {
                    "id": f"episode-{line_index + 1}-{episode_index + 1}",
                    "name": name,
                    "ref": _encode_episode_ref(raw_ref),
                }
            )
        if episodes:
            line_name = _text(raw_flags[line_index], f"线路{line_index + 1}", limit=100)
            sources.append(
                {
                    "id": f"line-{line_index + 1}",
                    "name": line_name,
                    "episodes": episodes,
                }
            )
    return sources


def _detail_item(canonical_id: str, value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, Mapping):
        return None
    title = _text(value.get("vod_name"), limit=300)
    if not title:
        return None
    extra = {
        key: text
        for key, text in {
            "remarks": _text(value.get("vod_remarks"), limit=300),
            "type_name": _text(value.get("type_name"), limit=100),
            "content": _text(value.get("vod_content"), limit=8192),
        }.items()
        if text
    }
    return {
        "id": _encode_item_id(canonical_id),
        "title": title,
        "poster": _text(value.get("vod_pic"), limit=2048) or None,
        "remarks": extra.get("remarks", ""),
        "navigation": "detail",
        "extra": extra,
        "play_sources": _play_sources(value),
    }


def _media_headers(value: Any) -> Dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    result: Dict[str, str] = {}
    total = 0
    for raw_name, raw_value in value.items():
        normalized = str(raw_name or "").strip().casefold()
        name = _ALLOWED_MEDIA_HEADERS.get(normalized)
        header_value = str(raw_value or "").strip()
        if not name or not header_value:
            continue
        if any(character in name + header_value for character in ("\0", "\r", "\n")):
            raise HongguoPluginError("红果播放 Header 无效")
        header_bytes = len(header_value.encode("utf-8"))
        total += len(name.encode("utf-8")) + header_bytes
        if header_bytes > 4096 or total > 8192:
            raise HongguoPluginError("红果播放 Header 过大")
        result[name] = header_value
    return result


def _media_kind(url: str) -> Tuple[str, str, bool]:
    parsed = urlsplit(url)
    path = parsed.path.casefold()
    try:
        query = {
            key.casefold(): value.casefold()
            for key, value in parse_qsl(
                parsed.query,
                keep_blank_values=True,
                max_num_fields=128,
            )
        }
    except ValueError:
        query = {}
    mime = query.get("mime_type", "").replace("-", "_")
    if ".m3u8" in path or mime in {
        "hls",
        "m3u8",
        "application/vnd.apple.mpegurl",
        "application/x_mpegurl",
    }:
        return "remote_hls", "application/vnd.apple.mpegurl", False
    if ".mp4" in path or mime in {"mp4", "video/mp4", "video_mp4"}:
        return "remote_file", "video/mp4", True
    if ".mkv" in path or mime in {"video/x_matroska", "video_mkv"}:
        return "remote_file", "video/x-matroska", True
    if path.endswith(".ts") or mime in {"video/mp2t", "video_mpegts"}:
        return "remote_file", "video/mp2t", True
    return "remote_file", "application/octet-stream", True


def _media_url(value: Any) -> str:
    url = _strict_string(value, max_bytes=8192, field="播放地址")
    try:
        parsed = urlsplit(url)
        port = parsed.port or 443
    except ValueError:
        raise HongguoPluginError("红果播放地址无效") from None
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port != 443
    ):
        raise HongguoPluginError("红果播放地址无效")
    return url


def _validate_api_dns() -> None:
    try:
        records = socket.getaddrinfo(
            _API_HOST,
            443,
            type=socket.SOCK_STREAM,
        )
    except OSError:
        raise HongguoPluginError("红果上游地址解析失败") from None
    addresses = {
        str(sockaddr[0]).split("%", 1)[0]
        for _family, _kind, _protocol, _canonical, sockaddr in records
        if sockaddr
    }
    if not addresses:
        raise HongguoPluginError("红果上游地址解析失败")
    for value in addresses:
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            raise HongguoPluginError("红果上游地址解析失败") from None
        if not address.is_global and address not in _TUN_FAKE_IP:
            raise HongguoPluginError("红果上游地址被安全策略拒绝")


def _media_options(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list) or not value or len(value) % 2:
        raise HongguoPluginError("红果播放候选格式无效")
    if len(value) // 2 > _MAX_MEDIA_OPTIONS:
        raise HongguoPluginError("红果播放候选过多")
    result: List[Dict[str, Any]] = []
    for index in range(0, len(value), 2):
        name = _strict_string(
            value[index],
            max_bytes=400,
            field="播放候选名称",
        )
        url = _media_url(value[index + 1])
        if len(name) > 100:
            raise HongguoPluginError("红果播放候选名称无效")
        kind, content_type, supports_range = _media_kind(url)
        result.append(
            {
                "name": name,
                "kind": kind,
                "url": url,
                "headers": {},
                "header_policy": "protected",
                "content_type": content_type,
                "expires_at": None,
                "supports_range": supports_range,
                "size": 0,
            }
        )
    return result


class HongguoPlugin:
    def __init__(self, context: Dict[str, Any]) -> None:
        self._plugin_id = _text(
            (context.get("plugin") or {}).get("id")
            if isinstance(context.get("plugin"), Mapping)
            else "",
            "hongguo",
            limit=64,
        )
        self._session = None  # type: Optional[requests.Session]

    def _http_client(self) -> requests.Session:
        if self._session is None:
            session = requests.Session()
            session.headers.update(
                {
                    "User-Agent": _USER_AGENT,
                    "Accept": "application/json, text/plain, */*",
                }
            )
            session.trust_env = False
            session.verify = True
            session.max_redirects = 5
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=2, pool_maxsize=2, max_retries=0
            )
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            self._session = session
        return self._session

    def _api_fetch_once(
        self,
        path: str,
        params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        session = self._http_client()
        session.cookies.clear()
        try:
            response = session.get(
                f"{_API_ORIGIN}{_API_PREFIX}{path}",
                params=dict(params or {}),
                timeout=(5, 20),
                allow_redirects=False,
                stream=True,
            )
            try:
                if response.status_code != 200:
                    if response.status_code in _CATEGORY_RETRYABLE_STATUS:
                        raise _HongguoRetryableRequestError
                    raise HongguoPluginError("红果上游请求失败")
                length = response.headers.get("Content-Length")
                if length is not None:
                    try:
                        if int(length) < 0 or int(length) > _MAX_RESPONSE_BYTES:
                            raise HongguoPluginError("红果上游响应过大")
                    except ValueError as exc:
                        raise HongguoPluginError("红果上游响应无效") from exc
                chunks: List[bytes] = []
                total = 0
                for chunk in response.iter_content(64 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > _MAX_RESPONSE_BYTES:
                        raise HongguoPluginError("红果上游响应过大")
                    chunks.append(chunk)
            finally:
                try:
                    response.close()
                except Exception:
                    pass
        except _HongguoRetryableRequestError:
            raise
        except HongguoPluginError:
            raise
        except requests.RequestException:
            raise _HongguoRetryableRequestError from None
        finally:
            session.cookies.clear()
        try:
            decrypted = _decrypt_v2(b"".join(chunks).decode("utf-8"))
            payload = json.loads(decrypted)
        except HongguoPluginError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HongguoPluginError("红果上游响应无效") from exc
        if not isinstance(payload, dict):
            raise HongguoPluginError("红果上游响应无效")
        return payload

    def _api_fetch(
        self,
        path: str,
        params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        if path not in _API_PATHS:
            raise HongguoPluginError("红果请求路径无效")
        _validate_api_dns()
        attempts = 2
        for attempt in range(attempts):
            try:
                return self._api_fetch_once(path, params)
            except _HongguoRetryableRequestError:
                if attempt + 1 >= attempts:
                    raise HongguoPluginError("红果上游请求失败") from None
        raise HongguoPluginError("红果上游请求失败")

    def homeContent(self, filter: bool = False) -> Dict[str, Any]:
        del filter
        payload = self._api_fetch("/home", {"filter": "1"})
        categories = _categories(payload.get("class"))
        return _document(
            "home",
            items=_content_items(payload.get("list")),
            categories=categories,
            filters=_filters(payload.get("filters")),
            limit=18,
        )

    def categoryContent(
        self,
        tid: str,
        pg: int = 1,
        filter: bool = False,
        extend: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        del filter
        page = _positive_page(pg)
        _canonical_tid, raw_tid, _encoded_tid = _item_input(tid)
        if isinstance(extend, Mapping):
            selected = _text(extend.get("cateId"), limit=700)
            if selected:
                _canonical_tid, raw_tid, _encoded_tid = _item_input(selected)
        if not raw_tid:
            raise HongguoPluginError("红果分类引用无效")
        if raw_tid == "rank_home":
            items = _rank_items()
            return _document(
                "list",
                items=items,
                page=1,
                page_count=1,
                limit=len(items),
                total=len(items),
            )
        if raw_tid in _RANK_CATEGORY_IDS:
            # 官方当主用：先试reading.snssdk.com直连，成功直接返回
            try:
                official_items = _official_fetch_rank(
                    self._http_client(), raw_tid, page
                )
            except Exception:
                official_items = None
            if official_items:
                return _document(
                    "list",
                    items=official_items,
                    page=page,
                    page_count=9999,
                    limit=_RANK_CLIENT_LIMIT,
                    total=9999,
                )
            # 中转当备用：23个rank_*原样保留
            first_upstream_page = (page - 1) * 2 + 1
            raw_items: List[Any] = []
            for upstream_page in (
                first_upstream_page,
                first_upstream_page + 1,
            ):
                payload = self._api_fetch(
                    "/category",
                    _category_params(raw_tid, upstream_page, extend),
                )
                raw_items.extend(
                    _sequence(payload.get("list"))[:_RANK_UPSTREAM_PAGE_LIMIT]
                )
            return _document(
                "list",
                items=_content_items(raw_items),
                page=page,
                page_count=9999,
                limit=_RANK_CLIENT_LIMIT,
                total=9999,
            )
        payload = self._api_fetch(
            "/category",
            _category_params(raw_tid, page, extend),
        )
        return _document(
            "list",
            items=_content_items(payload.get("list")),
            page=page,
            page_count=9999,
            limit=18,
            total=9999,
        )

    def searchContent(
        self,
        key: str,
        quick: bool = False,
        pg: int = 1,
    ) -> Dict[str, Any]:
        del quick
        keyword = _text(key, limit=300)
        page = _positive_page(pg)
        if not keyword:
            return _document(
                "search",
                items=[],
                page=page,
                page_count=page,
                limit=18,
                total=(page - 1) * 18,
            )
        payload = self._api_fetch("/search", {"wd": keyword, "pg": str(page)})
        items = _content_items(payload.get("list"))
        looks_full = len(items) >= 18
        page_count = page + 1 if looks_full else page
        total = (page + 1) * 18 if looks_full else (page - 1) * 18 + len(items)
        return _document(
            "search",
            items=items,
            page=page,
            page_count=page_count,
            limit=18,
            total=total,
        )

    def detailContent(self, ids: List[str]) -> Dict[str, Any]:
        result: List[Dict[str, Any]] = []
        for encoded_id in _sequence(ids)[:20]:
            canonical_id, raw_id, was_encoded = _item_input(encoded_id)
            if not raw_id:
                continue
            if not was_encoded:
                canonical_id = _canonical_item_target(raw_id)
            payload = self._api_fetch("/detail", {"id": raw_id})
            values = _sequence(payload.get("list"))
            detail = _detail_item(canonical_id, values[0] if values else None)
            if detail is not None:
                result.append(detail)
        return _document(
            "detail",
            items=result,
            page=1,
            page_count=1,
            limit=max(1, len(result)),
            total=len(result),
            title=result[0]["title"] if result else None,
        )

    def playerContent(
        self,
        flag: str,
        id: str,
        vipFlags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        del flag, vipFlags
        raw_id = _decode_episode_ref(id)
        payload = self._api_fetch("/play", {"id": raw_id})
        if payload.get("parse") not in (None, "", 0, "0", False) or payload.get(
            "jx"
        ) not in (None, "", 0, "0", False):
            raise HongguoPluginError("红果返回了不受支持的解析动作")
        options = _media_options(payload.get("url"))
        headers = _media_headers(payload.get("header") or payload.get("headers"))
        for option in options:
            option["headers"] = dict(headers)
        # 透出 key_urls(kid/spade_a)，供 Spider.localProxy 流式解密用。
        # /play 实测：key_urls[5]={name,src,kid,spade_a}，逐集变化；url=[name,src]*5。
        key_urls: List[Dict[str, str]] = []
        try:
            raw_ku = payload.get("key_urls")
            if isinstance(raw_ku, list):
                for it in raw_ku[:16]:
                    if not isinstance(it, dict):
                        continue
                    name = _text(it.get("name"), limit=64)
                    src = str(it.get("src") or "").strip()
                    kid = str(it.get("kid") or "").strip().lower()
                    spade = str(it.get("spade_a") or "").strip()
                    if not name or not src or not kid or not spade:
                        continue
                    if len(src) > 8192 or len(kid) > 64 or len(spade) > 512:
                        continue
                    if not re.fullmatch(r"[0-9a-f]{16,64}", kid):
                        continue
                    try:
                        if urlsplit(src).scheme.casefold() != "https":
                            continue
                    except Exception:
                        continue
                    key_urls.append({"name": name, "src": src, "kid": kid, "spade_a": spade})
        except Exception:
            key_urls = []
        return {
            "schema_version": "mv.python-playback-resolution.v1",
            "kind": "remote_media_options",
            "value": {
                "options": options,
                "key_urls": key_urls,
            },
        }

    def destroy(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None


def create_plugin(context: Dict[str, Any]) -> HongguoPlugin:
    return HongguoPlugin(context)


try:
    from base.spider import Spider as _BaseSpider
except Exception:
    try:
        import sys as _sys
        _sys.path.append("..")
        from base.spider import Spider as _BaseSpider
    except Exception:
        class _BaseSpider:
            pass


def _spider_vod(item):
    try:
        if not isinstance(item, dict):
            return None
        vid = str(item.get("id") or "")
        name = str(item.get("title") or "")
        if not vid or not name:
            return None
        pic = item.get("poster") or ""
        remarks = item.get("remarks") or ""
        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic if isinstance(pic, str) else "",
            "vod_remarks": remarks if isinstance(remarks, str) else "",
        }
        # 排行榜文件夹必须带 vod_tag=folder，FongMi 靠它决定点进去走
        # categoryContent（不带就会走 detailContent，/detail 查 rank_folder
        # 返回空，榜单点进去就是白板——这就是“排行榜都不能用”根因）。
        try:
            if str(item.get("navigation") or "") == "category":
                vod["vod_tag"] = "folder"
            elif vid.startswith(_ITEM_PREFIX):
                try:
                    _canon = _decode_item_id(vid)
                except Exception:
                    _canon = ""
                if _canon.startswith("rank_folder:"):
                    vod["vod_tag"] = "folder"
        except Exception:
            pass
        return vod
    except Exception:
        return None


def _spider_vod_list(items):
    out = []
    try:
        for it in (items or []):
            v = _spider_vod(it)
            if v is not None:
                out.append(v)
    except Exception:
        pass
    return out


def _spider_detail(mv):
    try:
        if not isinstance(mv, dict):
            return None
        vid = str(mv.get("id") or "")
        name = str(mv.get("title") or "")
        if not vid or not name:
            return None
        extra = mv.get("extra") if isinstance(mv.get("extra"), dict) else {}
        poster = mv.get("poster") or ""
        remarks = mv.get("remarks") or extra.get("remarks", "") or ""
        content = extra.get("content", "") or ""
        type_name = extra.get("type_name", "") or ""
        sources = mv.get("play_sources") or []
        play_from = []
        play_url = []
        for src in sources:
            try:
                if not isinstance(src, dict):
                    continue
                sname = str(src.get("name") or "红果")
                eps = src.get("episodes") or []
                parts = []
                for ep in eps:
                    try:
                        if not isinstance(ep, dict):
                            continue
                        ename = str(ep.get("name") or "")
                        ref = str(ep.get("ref") or "")
                        if not ref:
                            continue
                        if not ename:
                            ename = "正片"
                        parts.append(f"{ename}${ref}")
                    except Exception:
                        continue
                if parts:
                    play_from.append(sname)
                    play_url.append("#".join(parts))
            except Exception:
                continue
        # 多线路：上游 /detail 只给单线“红果”，同一 episode ref 在 /play 有 5 档
        # （1080P/720P/540P/480P/360P）。这里把单线展开成 5 线，同 ref 复用，
        # FongMi 把行名当 flag 回传，Spider.playerContent 按 flag 选档+走解密代理。
        try:
            if len(play_from) == 1 and len(play_url) == 1 and play_url[0]:
                base_line = play_url[0]
                labels = ["1080P", "720P", "540P", "480P", "360P"]
                play_from = [f"红果·{q}" for q in labels]
                play_url = [base_line for _ in labels]
        except Exception:
            pass
        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": poster if isinstance(poster, str) else "",
            "vod_remarks": remarks if isinstance(remarks, str) else "",
            "vod_content": content if isinstance(content, str) else "",
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        if type_name:
            vod["vod_class"] = type_name
            vod["type_name"] = type_name
        return vod
    except Exception:
        return None


class Spider(_BaseSpider):
    def __init__(self):
        try:
            self._plug = None
        except Exception:
            pass
        self._name = "红果短剧"

    def getName(self):
        return "红果短剧"

    def init(self, extend=""):
        try:
            self._plug = HongguoPlugin({})
        except Exception:
            self._plug = None
        return None

    def _ensure(self):
        if self._plug is None:
            self._plug = HongguoPlugin({})
        return self._plug

    def homeContent(self, filter):
        try:
            plug = self._ensure()
            doc = plug.homeContent()
            cats = doc.get("categories") or []
            classes = []
            seen = set()
            for c in cats:
                try:
                    if not isinstance(c, dict):
                        continue
                    cid = str(c.get("id") or "")
                    cname = str(c.get("name") or "")
                    if not cid or not cname or cid in seen:
                        continue
                    seen.add(cid)
                    classes.append({"type_id": cid, "type_name": cname})
                except Exception:
                    continue
            filters = doc.get("filters") or {}
            if not isinstance(filters, dict):
                filters = {}
            return {"class": classes, "list": [], "filters": filters}
        except Exception:
            return {"class": [], "list": [], "filters": {}}

    def homeVideoContent(self):
        try:
            plug = self._ensure()
            doc = plug.categoryContent("short_play", 1)
            return {"list": _spider_vod_list(doc.get("items"))}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            plug = self._ensure()
            try:
                page = int(str(pg or 1))
            except Exception:
                page = 1
            if page < 1:
                page = 1
            if not isinstance(extend, dict):
                extend = {}
            doc = plug.categoryContent(str(tid or "short_play"), page, False, extend)
            pagination = doc.get("pagination") or {}
            try:
                p = int(pagination.get("page", page))
            except Exception:
                p = page
            try:
                pc = int(pagination.get("page_count", 9999))
            except Exception:
                pc = 9999
            try:
                limit = int(pagination.get("limit", 18))
            except Exception:
                limit = 18
            lst = _spider_vod_list(doc.get("items"))
            return {"page": p, "pagecount": pc, "limit": limit if limit else 18, "total": 999999, "list": lst}
        except Exception:
            try:
                page = int(str(pg or 1))
            except Exception:
                page = 1
            return {"page": page, "pagecount": page, "limit": 18, "total": 0, "list": []}

    def detailContent(self, ids):
        try:
            plug = self._ensure()
            if not isinstance(ids, list):
                ids = [ids]
            doc = plug.detailContent([str(x) for x in ids if str(x)])
            out = []
            for mv in (doc.get("items") or []):
                v = _spider_detail(mv)
                if v is not None:
                    out.append(v)
            return {"list": out}
        except Exception:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        try:
            plug = self._ensure()
            try:
                page = int(str(pg or 1))
            except Exception:
                page = 1
            if page < 1:
                page = 1
            doc = plug.searchContent(str(key or ""), False, page)
            return {"list": _spider_vod_list(doc.get("items")), "page": page}
        except Exception:
            return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags):
        try:
            plug = self._ensure()
            doc = plug.playerContent(str(flag or ""), str(id or ""), None)
            value = doc.get("value") or {}
            options = value.get("options") or []
            key_urls = value.get("key_urls") or []
            if not options:
                return {"parse": 0, "url": "", "header": {}}
            # 多线路：flag 即 _spider_detail 行名“红果·1080P”等，按档名选档；
            # 默认 1080P（上游最高档）。哪线卡换哪线。
            want = ""
            try:
                want = str(flag or "").strip().upper()
            except Exception:
                want = ""
            best = options[0] if isinstance(options[0], dict) else {}
            try:
                # 默认 1080P：上游最高档；无 1080P 才退 options[0]。
                for opt in options:
                    if isinstance(opt, dict) and str(opt.get("name") or "").strip() == "1080P":
                        best = opt
                        break
                hit = None
                for opt in options:
                    if isinstance(opt, dict) and str(opt.get("name") or "").strip().upper() in want:
                        hit = opt
                        break
                if hit is not None:
                    best = hit
                elif not want or want == "红果":
                    for opt in options:
                        if isinstance(opt, dict) and str(opt.get("name") or "").strip() == "1080P":
                            best = opt
                            break
            except Exception:
                pass
            url = str(best.get("url") or "")
            header = best.get("headers") or {}
            if not isinstance(header, dict):
                header = {}
            header = dict(header)
            # Give CDN a browser UA when upstream provides no header; FongMi
            # merges/overrides UA via checkUa, browser UA is safer for qznovelvod.
            try:
                if not header.get("User-Agent"):
                    header["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
            except Exception:
                pass
            # 走本地解密代理：把选中档的 src+kid+spade_a 包进代理 URL，
            # TV 播代理地址即可拿到明文 mp4。解失败 localProxy 内回退直链。
            try:
                best_name = str(best.get("name") or "").strip()
                ku_hit = None
                if isinstance(key_urls, list) and key_urls:
                    for ku in key_urls:
                        if isinstance(ku, dict) and str(ku.get("name") or "").strip() == best_name:
                            ku_hit = ku
                            break
                    if ku_hit is None:
                        for ku in key_urls:
                            if isinstance(ku, dict) and str(ku.get("src") or "") == url:
                                ku_hit = ku
                                break
                if isinstance(ku_hit, dict):
                    src = str(ku_hit.get("src") or "")
                    kid = str(ku_hit.get("kid") or "")
                    spade = str(ku_hit.get("spade_a") or "")
                    key_hex = _hg_spade_to_key(spade)
                    if src.startswith("https://") and key_hex:
                        proxy = (
                            "http://127.0.0.1:9978/proxy?do=py&type=hgcenc"
                            + "&url=" + quote(src, safe="")
                            + "&kid=" + quote(kid, safe="")
                            + "&spade=" + quote(spade, safe="")
                        )
                        return {"parse": 0, "url": proxy, "header": {}}
            except Exception:
                pass
            return {"parse": 0, "url": url, "header": header}
        except Exception:
            return {"parse": 0, "url": "", "header": {}}

    def localProxy(self, param):
        try:
            if not isinstance(param, dict):
                return None
            typ = str(param.get("type") or "")
            if typ != "hgcenc":
                return None
            src = unquote(str(param.get("url") or ""))
            kid = unquote(str(param.get("kid") or ""))
            spade = unquote(str(param.get("spade") or ""))
            if not src.startswith("https://"):
                return [400, "text/plain", "bad url"]
            key_hex = _hg_spade_to_key(spade)
            if not key_hex:
                # 解不出 key 就 302 回退直链，不比原来更差
                return [302, "video/mp4", None, {"Location": src}]
            # Range 透传：TV seek/边下边播靠它；IJK开播爱发bytes=0-1小探针
            range_header = param.get("range") or param.get("Range") or ""
            try:
                range_header = str(range_header or "").strip()
            except Exception:
                range_header = ""
            # 解析请求区间，判断是否为小探针（<16KB），探针走快通避免超时
            req_lo = None
            req_hi = None
            try:
                _m0 = re.match(r"\s*bytes\s*=\s*(\d*)-(\d*)", range_header or "")
                if _m0:
                    _a, _b = _m0.group(1), _m0.group(2)
                    req_lo = int(_a) if _a else 0
                    req_hi = int(_b) if _b else -1
            except Exception:
                req_lo, req_hi = None, None
            is_probe = False
            try:
                # IJK开播探针 bytes=0-1 只认2字节：必须解密+patch后回，否则IJK判坏流。
                # 只有 <=2字节 的才叫探针，其余哪怕<16KB也要走完整解密链。
                if req_lo is not None and req_hi is not None and req_hi >= req_lo:
                    if req_hi - req_lo <= 1:
                        is_probe = True
            except Exception:
                is_probe = False
            # 上游 CDN 用浏览器 UA 直拉；Referer 会触发 403（实测），绝不能加。
            headers = {"User-Agent": _USER_AGENT}
            if range_header:
                headers["Range"] = range_header
            try:
                plug = self._ensure()
                sess = plug._http_client()
            except Exception:
                sess = requests.Session()
                sess.trust_env = False
            # qznovelvod首跳必302到idouyinvod：手动跟5跳，每跳都带Range，真total从落地页拿
            r, _final_url = _hg_fetch_follow(sess, src, headers, (5, 30), True)
            if r is None:
                return [302, "video/mp4", None, {"Location": src}]
            status = int(r.status_code or 0)
            if status not in (200, 206):
                try:
                    r.close()
                except Exception:
                    pass
                return [302, "video/mp4", None, {"Location": src}]
            # content-range 解析出本次区间 [lo,hi] 与全长；IJK认死total必须真值
            lo = 0
            hi = -1
            total = -1
            try:
                cr = r.headers.get("Content-Range") or r.headers.get("content-range") or ""
                if cr:
                    m = re.match(r"\s*bytes\s+(\d+)-(\d+)/(\d+|\*)", cr)
                    if m:
                        lo = int(m.group(1))
                        hi = int(m.group(2))
                        total = -1 if m.group(3) == "*" else int(m.group(3))
                if total < 0:
                    cl = r.headers.get("Content-Length") or r.headers.get("content-length") or ""
                    if cl and str(cl).strip().isdigit():
                        if status == 206 and hi >= lo:
                            # 206本次长度不能当total；IJK验total对不上就判坏流，
                            # 这里先记下本次长度，稍后用缓存/HEAD补真total
                            pass
                        else:
                            total = int(str(cl).strip())
            except Exception:
                pass
            # total真值补齐：优先内存缓存，其次bytes=0-0探针拿Content-Range；
            # 小探针跳过补齐（探针只求快，上游自带的Content-Range已含真total）
            try:
                _HG_TOTALS: Dict[str, int] = getattr(_hg_moov_cache_holder, "totals", None) or {}
                if total <= 0:
                    _cached_total = _HG_TOTALS.get(src)
                    if _cached_total and _cached_total > 0:
                        total = int(_cached_total)
                if total <= 0 and not is_probe:
                    try:
                        _hr, _ = _hg_fetch_follow(sess, src, {"User-Agent": _USER_AGENT, "Range": "bytes=0-0"}, (5, 15), True)
                        _hcr = ""
                        try:
                            if _hr is not None:
                                _hcr = _hr.headers.get("Content-Range") or _hr.headers.get("content-range") or ""
                        except Exception:
                            _hcr = ""
                        try:
                            if _hr is not None:
                                _hr.close()
                        except Exception:
                            pass
                        _mm = re.match(r"\s*bytes\s+\d+-\d+/(\d+)", _hcr or "")
                        if _mm:
                            total = int(_mm.group(1))
                            try:
                                _HG_TOTALS[src] = total
                                setattr(_hg_moov_cache_holder, "totals", _HG_TOTALS)
                            except Exception:
                                pass
                    except Exception:
                        pass
                # 上游给了真total就记下来，同集下次不再探
                try:
                    if total and total > 0:
                        _HG_TOTALS[src] = int(total)
                        setattr(_hg_moov_cache_holder, "totals", _HG_TOTALS)
                except Exception:
                    pass
            except Exception:
                pass
            chunks: List[bytes] = []
            try:
                for ch in r.iter_content(256 * 1024):
                    if ch:
                        chunks.append(ch)
            finally:
                try:
                    r.close()
                except Exception:
                    pass
            data = b"".join(chunks)
            if not data:
                return [302, "video/mp4", None, {"Location": src}]
            if hi < lo:
                hi = lo + len(data) - 1
            # 关键：必须回 Accept-Ranges/Content-Range/Content-Length 四件套，
            # 否则 MPV 会把代理流判成不可 seek（日志：Cannot seek in this stream）。
            # 上游 206 的 Content-Range 自带 total；200 则 total=全长。
            if total < 0:
                if status == 200:
                    total = len(data)
            buf = bytearray(data)
            # IJK开播探针 bytes=0-1 只求2字节ftyp：原样透传+四件套秒回，不解密。
            # 注意：只有<=2字节才走这；IJK首个大区间/拖动小区间一律走完整解密链。
            if is_probe:
                try:
                    _HG_TOTALS_P: Dict[str, int] = getattr(_hg_moov_cache_holder, "totals", None) or {}
                    if total <= 0:
                        _ct = _HG_TOTALS_P.get(src)
                        if _ct and _ct > 0:
                            total = int(_ct)
                except Exception:
                    pass
                out = bytes(buf)
                if status == 206:
                    if total <= 0:
                        _ct2 = None
                        try:
                            _ct2 = (getattr(_hg_moov_cache_holder, "totals", None) or {}).get(src)
                        except Exception:
                            _ct2 = None
                        if _ct2 and _ct2 > 0:
                            total = int(_ct2)
                        else:
                            total = hi + 1
                    return [206, "video/mp4", out, {"Content-Type": "video/mp4", "Accept-Ranges": "bytes", "Content-Range": f"bytes {lo}-{hi}/{total}", "Content-Length": str(len(out))}]
                if total <= 0:
                    total = len(out)
                return [200, "video/mp4", out, {"Content-Type": "video/mp4", "Accept-Ranges": "bytes", "Content-Length": str(len(out))}]
            # moov 必须在 buf 内才能算样本表；首请求通常含 moov（moov 在文件头）。
            # 若本次区间不含 moov（如 seek 到 mdat 深处），先拉前 512KB 取 moov 算表。
            table = bytes(buf)
            try:
                has_moov = b"moov" in bytes(buf[:8 + 256 * 1024]) if len(buf) else False
            except Exception:
                has_moov = False
            moov_end = -1
            # seek 到 mdat 深处的请求不含 moov：拉全量 moov（含完整 senc/stsz/stco/stsc），
            # 否则用切片算出的样本序号 idx 会从 0 重数导致 CTR 错位，拖动必花。
            _HG_MOOV_CACHE: Dict[str, bytes] = getattr(_hg_moov_cache_holder, "cache", None) or {}
            try:
                if not has_moov:
                    cached = _HG_MOOV_CACHE.get(src)
                    if cached and b"moov" in cached:
                        table = cached
                        has_moov = True
            except Exception:
                pass
            try:
                if not has_moov:
                    h, _ = _hg_fetch_follow(sess, src, {"User-Agent": _USER_AGENT, "Range": "bytes=0-1048575"}, (5, 30), True)
                    try:
                        head = b"".join([c for c in h.iter_content(256 * 1024) if c]) if h is not None else b""
                    except Exception:
                        head = b""
                    try:
                        if h is not None:
                            h.close()
                    except Exception:
                        pass
                    if head and b"moov" in head:
                        table = head
                        try:
                            _HG_MOOV_CACHE[src] = head
                            setattr(_hg_moov_cache_holder, "cache", _HG_MOOV_CACHE)
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                mv = _hg_find(table, [b"moov"])
                if mv:
                    moov_end = mv[1]
            except Exception:
                mv = None
            if not mv:
                # 无 moov 表就原样回（不断播），首区间一般不会走到这
                out = bytes(buf)
                if status == 206:
                    if total <= 0:
                        total = hi + 1
                    return [206, "video/mp4", out, {"Content-Type": "video/mp4", "Accept-Ranges": "bytes", "Content-Range": f"bytes {lo}-{hi}/{total}", "Content-Length": str(len(out))}]
                return [200, "video/mp4", out, {"Content-Type": "video/mp4", "Accept-Ranges": "bytes", "Content-Length": str(len(out))}]
            # 找本文件两条加密轨的 senc base_iv（视频/音频各自身 senc）；
            # 命中缓存表直接复用，不再重复解析（IJK连播/切集省下整次moov遍历）。
            try:
                _HG_TABLES: Dict[str, dict] = getattr(_hg_moov_cache_holder, "tables", None) or {}
                _cached_tb = _HG_TABLES.get(src)
            except Exception:
                _HG_TABLES = {}
                _cached_tb = None
            v_iv = None
            a_iv = None
            vsizes: List[int] = []
            voffs: List[int] = []
            asizes: List[int] = []
            aoffs: List[int] = []
            mv_for_patch = None
            table_for_patch = None
            use_cache = False
            try:
                if isinstance(_cached_tb, dict) and _cached_tb.get("v_iv"):
                    v_iv = _cached_tb.get("v_iv")
                    a_iv = _cached_tb.get("a_iv")
                    vsizes = list(_cached_tb.get("vsizes") or [])
                    voffs = list(_cached_tb.get("voffs") or [])
                    asizes = list(_cached_tb.get("asizes") or [])
                    aoffs = list(_cached_tb.get("aoffs") or [])
                    mv_for_patch = None
                    table_for_patch = None
                    use_cache = True
            except Exception:
                use_cache = False
            if not v_iv and not a_iv and not use_cache:
                # 未命中缓存：现解析moov拿 base_iv + 样本表，解析完即缓存
                try:
                    traks = [(o + hs, o + sz) for t, o, sz, hs in _hg_box_iter(table, mv[0], mv[1]) if t == b"trak"]

                    def _hdlr(tr):
                        h = _hg_find(table, [b"mdia", b"hdlr"], tr[0], tr[1])
                        return table[h[0] + 8:h[0] + 12] if h else None
                    vide_range = None
                    soun_range = None
                    for tr in traks:
                        h = _hdlr(tr)
                        if h == b"vide" and vide_range is None:
                            vide_range = tr
                        elif h == b"soun" and soun_range is None:
                            soun_range = tr
                    v_iv = _hg_trak_senc_iv8(table, vide_range[0], vide_range[1]) if vide_range else None
                    a_iv = _hg_trak_senc_iv8(table, soun_range[0], soun_range[1]) if soun_range else None
                except Exception:
                    v_iv, a_iv = None, None
                # 全片样本偏移是按文件绝对偏移算的；样本序号 idx 必须用全局序号
                try:
                    if v_iv:
                        vsizes, voffs = _hg_track_samples(table, b"vide")
                    if a_iv:
                        asizes, aoffs = _hg_track_samples(table, b"soun")
                except Exception:
                    pass
                # 解析成功即缓存：IJK连播/切集/二次seek直接复用
                try:
                    if v_iv:
                        _HG_TABLES[src] = {"v_iv": v_iv, "a_iv": a_iv, "vsizes": list(vsizes), "voffs": list(voffs), "asizes": list(asizes), "aoffs": list(aoffs)}
                        setattr(_hg_moov_cache_holder, "tables", _HG_TABLES)
                except Exception:
                    pass
                mv_for_patch = mv
                table_for_patch = table
            if not v_iv and not a_iv:
                out = bytes(buf)
                if status == 206:
                    if total <= 0:
                        total = hi + 1
                    return [206, "video/mp4", out, {"Content-Type": "video/mp4", "Accept-Ranges": "bytes", "Content-Range": f"bytes {lo}-{hi}/{total}", "Content-Length": str(len(out))}]
                return [200, "video/mp4", out, {"Content-Type": "video/mp4", "Accept-Ranges": "bytes", "Content-Length": str(len(out))}]
            # buf 是本次区间的切片：样本文件偏移 co 需换算成 buf 内偏移 co-lo
            # _hg_decrypt_range 按“buf内坐标”工作，所以先把 buf 拼成“文件坐标系”：
            # 简单做法：只对完全落入本次区间的样本解密（首帧/顺序播全命中；seek 切片命中其区间）。
            # 为复用 _hg_decrypt_range 的 lo/hi，我们传 buf 坐标系：把 offs 整体 -lo。
            try:
                if v_iv and vsizes and voffs:
                    vo2 = [c - lo for c in voffs]
                    _hg_decrypt_range(buf, key_hex, v_iv, vsizes, vo2, 0, len(buf))
                if a_iv and asizes and aoffs:
                    ao2 = [c - lo for c in aoffs]
                    _hg_decrypt_range(buf, key_hex, a_iv, asizes, ao2, 0, len(buf))
            except Exception:
                pass
            # IJK认死moov四字符码：buf含moov段时把 encv->hvc1 / enca->mp4a，
            # 同长度替换不影响box尺寸；MPV/EXO不受影响。
            try:
                if lo < moov_end and moov_end > 0:
                    _hg_patch_moov_enc(buf, lo, moov_end)
            except Exception:
                pass
            out = bytes(buf)
            if status == 206:
                if total <= 0:
                    total = hi + 1
                headers_out = {
                    "Content-Type": "video/mp4",
                    "Accept-Ranges": "bytes",
                    "Content-Range": f"bytes {lo}-{hi}/{total}",
                    "Content-Length": str(len(out)),
                }
                return [206, "video/mp4", out, headers_out]
            headers_out = {
                "Content-Type": "video/mp4",
                "Accept-Ranges": "bytes",
                "Content-Length": str(len(out)),
            }
            return [200, "video/mp4", out, headers_out]
        except Exception:
            return None

    def isVideoFormat(self, url):
        try:
            u = str(url or "").lower()
            return ("m3u8" in u) or (".mp4" in u) or ("video_mp4" in u) or ("qznovelvod" in u) or ("mime_type=video" in u) or ("hgcenc" in u) or ("127.0.0.1" in u)
        except Exception:
            return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            if self._plug is not None:
                try:
                    self._plug.destroy()
                except Exception:
                    pass
                self._plug = None
        except Exception:
            pass
        return None
