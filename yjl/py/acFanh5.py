# -*- coding: utf-8 -*-
#发任意消息到邮箱，自动获取回家地址
#邮箱地址： acfancom430@gmail.com
import sys
import re
import json
import socket
import requests
import urllib3
import base64
import hashlib
import time
from urllib.parse import quote, unquote

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider

# ============================================================
# AES-128-CBC decryption (multiple fallback methods)
# ============================================================

_AES_OK = False
try:
    from Crypto.Cipher import AES as _AES
    from Crypto.Util.Padding import unpad as _unpad
    _AES_OK = 'pycrypto'
except:
    try:
        from Cryptodome.Cipher import AES as _AES
        from Cryptodome.Util.Padding import unpad as _unpad
        _AES_OK = 'pycrypto'
    except:
        pass

if not _AES_OK:
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher as _Cipher, algorithms as _algs, modes as _modes
        from cryptography.hazmat.primitives import padding as _padding
        _AES_OK = 'cryptography'
    except:
        pass

if not _AES_OK:
    try:
        import ctypes
        import ctypes.util
        _libcrypto = None
        for _lib_name in ['libcrypto.so', 'libcrypto.so.3', 'libcrypto.so.1.1', 'libcrypto.so.10',
                          'libssl.so', 'libssl.so.3', 'libssl.so.1.1']:
            try:
                _libcrypto = ctypes.CDLL(_lib_name)
                break
            except:
                pass
        if not _libcrypto:
            _found = ctypes.util.find_library('crypto')
            if _found:
                _libcrypto = ctypes.CDLL(_found)
        if _libcrypto:
            _libcrypto.EVP_CIPHER_CTX_new.restype = ctypes.c_void_p
            _libcrypto.EVP_CIPHER_CTX_free.argtypes = [ctypes.c_void_p]
            _libcrypto.EVP_aes_128_cbc.restype = ctypes.c_void_p
            _AES_OK = 'ctypes'
    except:
        _libcrypto = None

# Pure Python AES-128 implementation (FIPS-197)
_SBOX = [
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
]

_INV_SBOX = [
    0x52,0x09,0x6a,0xd5,0x30,0x36,0xa5,0x38,0xbf,0x40,0xa3,0x9e,0x81,0xf3,0xd7,0xfb,
    0x7c,0xe3,0x39,0x82,0x9b,0x2f,0xff,0x87,0x34,0x8e,0x43,0x44,0xc4,0xde,0xe9,0xcb,
    0x54,0x7b,0x94,0x32,0xa6,0xc2,0x23,0x3d,0xee,0x4c,0x95,0x0b,0x42,0xfa,0xc3,0x4e,
    0x08,0x2e,0xa1,0x66,0x28,0xd9,0x24,0xb2,0x76,0x5b,0xa2,0x49,0x6d,0x8b,0xd1,0x25,
    0x72,0xf8,0xf6,0x64,0x86,0x68,0x98,0x16,0xd4,0xa4,0x5c,0xcc,0x5d,0x65,0xb6,0x92,
    0x6c,0x70,0x48,0x50,0xfd,0xed,0xb9,0xda,0x5e,0x15,0x46,0x57,0xa7,0x8d,0x9d,0x84,
    0x90,0xd8,0xab,0x00,0x8c,0xbc,0xd3,0x0a,0xf7,0xe4,0x58,0x05,0xb8,0xb3,0x45,0x06,
    0xd0,0x2c,0x1e,0x8f,0xca,0x3f,0x0f,0x02,0xc1,0xaf,0xbd,0x03,0x01,0x13,0x8a,0x6b,
    0x3a,0x91,0x11,0x41,0x4f,0x67,0xdc,0xea,0x97,0xf2,0xcf,0xce,0xf0,0xb4,0xe6,0x73,
    0x96,0xac,0x74,0x22,0xe7,0xad,0x35,0x85,0xe2,0xf9,0x37,0xe8,0x1c,0x75,0xdf,0x6e,
    0x47,0xf1,0x1a,0x71,0x1d,0x29,0xc5,0x89,0x6f,0xb7,0x62,0x0e,0xaa,0x18,0xbe,0x1b,
    0xfc,0x56,0x3e,0x4b,0xc6,0xd2,0x79,0x20,0x9a,0xdb,0xc0,0xfe,0x78,0xcd,0x5a,0xf4,
    0x1f,0xdd,0xa8,0x33,0x88,0x07,0xc7,0x31,0xb1,0x12,0x10,0x59,0x27,0x80,0xec,0x5f,
    0x60,0x51,0x7f,0xa9,0x19,0xb5,0x4a,0x0d,0x2d,0xe5,0x7a,0x9f,0x93,0xc9,0x9c,0xef,
    0xa0,0xe0,0x3b,0x4d,0xae,0x2a,0xf5,0xb0,0xc8,0xeb,0xbb,0x3c,0x83,0x53,0x99,0x61,
    0x17,0x2b,0x04,0x7e,0xba,0x77,0xd6,0x26,0xe1,0x69,0x14,0x63,0x55,0x21,0x0c,0x7d,
]

_RCON = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36]

def _xtime(a):
    return (((a << 1) ^ 0x1b) & 0xff) if (a & 0x80) else (a << 1)

def _mul(a, b):
    r = 0
    for _ in range(8):
        if b & 1:
            r ^= a
        a = _xtime(a)
        b >>= 1
    return r

def _key_expansion(key):
    w = list(key)
    for i in range(4, 44):
        t = w[(i-1)*4:(i-1)*4+4]
        if i % 4 == 0:
            t = [t[1], t[2], t[3], t[0]]
            t = [_SBOX[b] for b in t]
            t[0] ^= _RCON[i//4 - 1]
        for j in range(4):
            w.append(w[(i-4)*4+j] ^ t[j])
    return [w[i*4:i*4+4] for i in range(44)]

def _inv_sub_bytes(s):
    for i in range(16):
        s[i] = _INV_SBOX[s[i]]

def _inv_shift_rows(s):
    s[1],s[5],s[9],s[13] = s[13],s[1],s[5],s[9]
    s[2],s[6],s[10],s[14] = s[10],s[14],s[2],s[6]
    s[3],s[7],s[11],s[15] = s[7],s[11],s[15],s[3]

def _inv_mix_columns(s):
    for c in range(4):
        a = s[c*4:c*4+4]
        s[c*4]   = _mul(a[0],14) ^ _mul(a[1],11) ^ _mul(a[2],13) ^ _mul(a[3],9)
        s[c*4+1] = _mul(a[0],9)  ^ _mul(a[1],14) ^ _mul(a[2],11) ^ _mul(a[3],13)
        s[c*4+2] = _mul(a[0],13) ^ _mul(a[1],9)  ^ _mul(a[2],14) ^ _mul(a[3],11)
        s[c*4+3] = _mul(a[0],11) ^ _mul(a[1],13) ^ _mul(a[2],9)  ^ _mul(a[3],14)

def _add_round_key(s, rk):
    for i in range(16):
        s[i] ^= rk[i]

def _decrypt_block(block, round_keys):
    s = list(block)
    _add_round_key(s, round_keys[40:44][0] + round_keys[40:44][1] + round_keys[40:44][2] + round_keys[40:44][3])
    for r in range(9, 0, -1):
        _inv_shift_rows(s)
        _inv_sub_bytes(s)
        rk = round_keys[r*4:(r+1)*4]
        _add_round_key(s, rk[0] + rk[1] + rk[2] + rk[3])
        _inv_mix_columns(s)
    _inv_shift_rows(s)
    _inv_sub_bytes(s)
    rk = round_keys[0:4]
    _add_round_key(s, rk[0] + rk[1] + rk[2] + rk[3])
    return bytes(s)

def _pure_aes_cbc_decrypt(key, iv, ciphertext):
    round_keys = _key_expansion(key)
    plaintext = b''
    prev = iv
    for i in range(0, len(ciphertext), 16):
        block = ciphertext[i:i+16]
        dec = _decrypt_block(block, round_keys)
        pt = bytes(a ^ b for a, b in zip(dec, prev))
        plaintext += pt
        prev = block
    if plaintext and 0 < plaintext[-1] <= 16:
        pad_len = plaintext[-1]
        if all(b == pad_len for b in plaintext[-pad_len:]):
            plaintext = plaintext[:-pad_len]
    return plaintext

def _aes_decrypt(key_bytes, iv_bytes, data_bytes):
    if _AES_OK == 'pycrypto':
        try:
            c = _AES.new(key_bytes, _AES.MODE_CBC, iv_bytes)
            d = c.decrypt(data_bytes)
            return _unpad(d, _AES.block_size)
        except:
            pass
    if _AES_OK == 'cryptography':
        try:
            c = _Cipher(_algs.AES(key_bytes), _modes.CBC(iv_bytes))
            d = c.decryptor()
            pt = d.update(data_bytes) + d.finalize()
            unpadder = _padding.PKCS7(128).unpadder()
            return unpadder.update(pt) + unpadder.finalize()
        except:
            pass
    if _AES_OK == 'ctypes':
        try:
            ctx = _libcrypto.EVP_CIPHER_CTX_new()
            if ctx:
                _libcrypto.EVP_DecryptInit_ex(ctx, _libcrypto.EVP_aes_128_cbc(), None,
                    ctypes.c_char_p(key_bytes), ctypes.c_char_p(iv_bytes))
                _libcrypto.EVP_CIPHER_CTX_set_padding(ctx, 0)
                out = ctypes.create_string_buffer(len(data_bytes) + 32)
                out_len = ctypes.c_int(0)
                _libcrypto.EVP_DecryptUpdate(ctx, out, ctypes.byref(out_len),
                    ctypes.c_char_p(data_bytes), len(data_bytes))
                total = out_len.value
                final_out = ctypes.create_string_buffer(32)
                final_len = ctypes.c_int(0)
                _libcrypto.EVP_DecryptFinal_ex(ctx, final_out, ctypes.byref(final_len))
                total += final_len.value
                _libcrypto.EVP_CIPHER_CTX_free(ctx)
                pt = out.raw[:total]
                if pt and 0 < pt[-1] <= 16:
                    pad_len = pt[-1]
                    if all(b == pad_len for b in pt[-pad_len:]):
                        pt = pt[:-pad_len]
                return pt
        except:
            pass
    return _pure_aes_cbc_decrypt(key_bytes, iv_bytes, data_bytes)


_PIN_MAP = {}
_PIN_INSTALLED = [False]


def _install_pin():
    if _PIN_INSTALLED[0]:
        return
    _PIN_INSTALLED[0] = True
    _orig = socket.getaddrinfo

    def _pinned(host, port, *args, **kwargs):
        _ips = _PIN_MAP.get(host)
        if _ips:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port)) for ip in _ips]
        return _orig(host, port, *args, **kwargs)

    socket.getaddrinfo = _pinned


def _doh_resolve(hostname):
    _doh_list = [
        'https://doh.pub/dns-query',
        'https://dns.alidns.com/resolve',
        'https://dns.google/resolve',
        'https://cloudflare-dns.com/dns-query',
    ]
    picked = []
    for _u in _doh_list:
        try:
            _r = requests.get(_u, params={'name': hostname, 'type': 'A'},
                              headers={'accept': 'application/dns-json'}, timeout=6, verify=False)
            _j = _r.json()
            for _a in _j.get('Answer', []):
                if _a.get('type') == 1 and _a.get('data'):
                    _d = _a['data']
                    if _d and not _d.startswith('0.'):
                        picked.append(_d)
            if picked:
                break
        except Exception:
            continue
    return picked


def _doh_pin_domain(hostname, fallback=None):
    """国内 DNS 污染时,通过 DoH 获取真实 IP,并钉扎域名解析,绕过被劫持的系统 DNS。
    仅对指定 hostname 生效,不影响其他域名解析。DoH 失败时可用 fallback IP 兜底。"""
    try:
        if not hostname:
            return
        _install_pin()
        picked = _doh_resolve(hostname)
        if not picked and fallback:
            picked = list(fallback)
        if picked:
            _PIN_MAP[hostname] = picked
    except Exception:
        pass


def _pin_url_host(url):
    try:
        _m = re.match(r'https?://([^/:]+)', url or '')
        if _m:
            _doh_pin_domain(_m.group(1))
    except Exception:
        pass


class Spider(Spider):
    session = requests.Session()
    host = 'https://accfanan.x18c87so.work'
    token = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI2NTgxMjQ2NyIsImlhdCI6MTc4NjY0NjkwOCwibmJmIjoxNzg2NjY0OTIyLCJleHAiOjE5NDQzNDQ5MjJ9.7poZoAttovGH_UnkM0ZKYVjExOVGc8Uh5U62TVVQNuE'
    device_id = 'h5_7c768c18bd97473c9f9d23b25c21f'
    img_domain = 'https://wiuuh1425js3.iumigc.com/'
    UA = 'Mozilla/5.0 (Linux; Android 12; SM-G9750 Build/SP1A.210812.016; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/89.0.4389.72 Mobile Safari/537.36'

    cat_map = {
        'jx': '4',
        'dm': '2',
        'lifan': '24',
        'rebao': '53',
        'luanlun': '27',
        'guochan': '28',
        'wanghuang': '30',
        'luoli': '52',
        'av': '57',
        'chuanmei': '58',
        'zhongkou': '59',
        'manhua': '5',
    }

    comic_class = {
        '': '1',
        '最新': '1',
        '热门推荐': '21',
        '韩漫': '2',
        '同人': '6',
        '独家': '17',
        '国漫': '11',
        '日漫': '10',
        '3D': '3',
        '单行本': '7',
        'CG/AI': '15',
        'COS写真': '5',
        'BL': '19',
    }

    filters_data = {
        'jx': [
            {'key': 'jxType', 'name': '分类', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '短视频', 'v': 'short'},
                {'n': '小说', 'v': 'fiction'},
            ]},
            {'key': 'shortMode', 'name': '短视频', 'value': [
                {'n': '发现', 'v': 'find'},
                {'n': '推荐', 'v': 'rec'},
            ]},
            {'key': 'shortPlot', 'name': '剧情', 'value': [
                {'n': '伦理', 'v': '42'},
                {'n': '少女', 'v': '43'},
                {'n': '泄露', 'v': '44'},
                {'n': '网红', 'v': '45'},
                {'n': '窥视', 'v': '46'},
                {'n': '抖音风', 'v': '54'},
            ]},
            {'key': 'fictionType', 'name': '小说', 'value': [
                {'n': '普通', 'v': '1'},
                {'n': '有声', 'v': '2'},
            ]},
            {'key': 'tag1', 'name': '普通标签', 'value': [
                {'n': '学生妹', 'v': '1'},
                {'n': '处女', 'v': '2'},
                {'n': '偷情', 'v': '3'},
                {'n': '淫荡', 'v': '4'},
                {'n': '潜规则', 'v': '5'},
                {'n': '制服丝袜', 'v': '6'},
                {'n': '人妻', 'v': '7'},
                {'n': '3P/多P', 'v': '8'}]},
            {'key': 'tag1', 'name': '普通标签', 'value': [
                {'n': '车厢', 'v': '9'},
                {'n': '调教', 'v': '10'},
                {'n': '乱伦', 'v': '11'},
                {'n': '强暴', 'v': '12'},
                {'n': '教师', 'v': '15'},
                {'n': '办公室', 'v': '16'},
                {'n': '古典', 'v': '18'},
                {'n': '美女', 'v': '19'}]},
            {'key': 'tag1', 'name': '普通标签', 'value': [
                {'n': '空姐', 'v': '27'},
                {'n': '另类', 'v': '564'},
            ]},
            {'key': 'tag2', 'name': '有声标签', 'value': [
                {'n': '音频小说', 'v': '29'},
                {'n': '调教', 'v': '31'},
                {'n': '淫荡', 'v': '32'},
                {'n': '人妻', 'v': '33'},
                {'n': '偷情', 'v': '34'},
                {'n': '学生妹', 'v': '35'},
                {'n': '古典', 'v': '36'},
                {'n': '乱伦', 'v': '37'}]},
            {'key': 'tag2', 'name': '有声标签', 'value': [
                {'n': '强暴', 'v': '38'},
                {'n': '3P/多P', 'v': '39'},
                {'n': '制服丝袜', 'v': '40'},
                {'n': '教师', 'v': '41'},
                {'n': '办公室', 'v': '42'},
                {'n': '车厢', 'v': '43'},
                {'n': '空姐', 'v': '54'},
            ]},
        ],
        'dm': [
            {'key': 'videoTag', 'name': '分类', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '同人', 'v': '同人'},
                {'n': '国漫', 'v': '国漫'},
                {'n': '3D', 'v': '3D'},
                {'n': 'MMD', 'v': 'MMD'},
                {'n': '原神', 'v': '原神'},
                {'n': '崩坏3', 'v': '崩坏3'},
                {'n': '番剧', 'v': '番剧'},
            ]},
        ],
        'rebao': [
            {'key': 'videoTag', 'name': '分类', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '熟女肥逼', 'v': '熟女肥逼'},
                {'n': '人妖伪娘', 'v': '人妖伪娘'},
                {'n': '美胸巨乳', 'v': '美胸巨乳'},
                {'n': '探花偷拍', 'v': '探花偷拍'},
                {'n': '少女萝莉', 'v': '少女萝莉'},
                {'n': '强奸迷奸', 'v': '强奸迷奸'}]},
                {'key': 'videoTag', 'name': '分类', 'value': [
                {'n': '多人群p', 'v': '多人群p'},
                {'n': '调教SM', 'v': '调教SM'},
                {'n': '泄露流出', 'v': '泄露流出'},
                {'n': '媚黑骚逼', 'v': '媚黑骚逼'},
                {'n': '孕妇做爱', 'v': '孕妇做爱'},
                {'n': '校园霸凌', 'v': '校园霸凌'},
            ]},
        ],
        'luanlun': [
            {'key': 'videoTag', 'name': '分类', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '父女', 'v': '父女'},
                {'n': '母子', 'v': '母子'},
                {'n': '兄妹', 'v': '兄妹'},
                {'n': '姐弟', 'v': '姐弟'},
                {'n': '岳母', 'v': '岳母'},
                {'n': '嫂子', 'v': '嫂子'}]},
                {'key': 'videoTag', 'name': '分类', 'value': [
                {'n': '侄女', 'v': '侄女'},
                {'n': '师生', 'v': '师生'},
                {'n': '小姨子', 'v': '小姨子'},
                {'n': '小马拉大车', 'v': '小马拉大车'},
            ]},
        ],
        'guochan': [
            {'key': 'videoTag', 'name': '分类', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '情侣自拍', 'v': '情侣自拍'},
                {'n': '三级片', 'v': '三级片'},
                {'n': '户外露出', 'v': '户外露出'},
                {'n': '颜值女神', 'v': '颜值女神'},
                {'n': '反差婊', 'v': '反差婊'},
                {'n': '明星换脸', 'v': '明星换脸'}]},
                {'key': 'videoTag', 'name': '分类', 'value': [
                {'n': '推油按摩', 'v': '推油按摩'},
                {'n': '网红博主', 'v': '网红博主'},
                {'n': '偷情出轨', 'v': '偷情出轨'},
                {'n': '主播大秀', 'v': '主播大秀'},
                {'n': '真实换妻', 'v': '真实换妻'},
                {'n': '合集盘点', 'v': '合集盘点'},
            ]},
        ],
        'wanghuang': [
            {'key': 'videoTag', 'name': '分类', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '白桃少女', 'v': '白桃少女'},
                {'n': '台北娜娜', 'v': '台北娜娜'},
                {'n': '柚子猫', 'v': '柚子猫'},
                {'n': '桥本香菜', 'v': '桥本香菜'},
                {'n': '饼干姐姐', 'v': '饼干姐姐'},
                {'n': '小欣奈', 'v': '小欣奈'}]},
                {'key': 'videoTag', 'name': '分类', 'value': [
                {'n': '御梦子', 'v': '御梦子'},
                {'n': '捅主任', 'v': '捅主任'},
                {'n': '黑椒盖饭', 'v': '黑椒盖饭'},
                {'n': '冉冉学姐', 'v': '冉冉学姐'},
                {'n': '鸡教练', 'v': '鸡教练'},
                {'n': '唐伯虎', 'v': '唐伯虎'},
                {'n': '咪妮', 'v': '咪妮'}]},
                {'key': 'videoTag', 'name': '分类', 'value': [
                {'n': '玩偶姐姐', 'v': '玩偶姐姐'},
                {'n': '情深叉喔', 'v': '情深叉喔'},
                {'n': '水冰月', 'v': '水冰月'},
                {'n': '米胡桃', 'v': '米胡桃'},
                {'n': '白菜妹妹', 'v': '白菜妹妹'},
                {'n': '二代cc', 'v': '二代cc'},
            ]},
        ],
        'luoli': [
            {'key': 'videoTag', 'name': '分类', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '护士', 'v': '护士'},
                {'n': '白虎嫩妹', 'v': '白虎嫩妹'},
                {'n': '女仆', 'v': '女仆'},
                {'n': 'cosplay', 'v': 'cosplay'},
                {'n': '洛丽塔', 'v': '洛丽塔'},
                {'n': 'JK学生', 'v': 'JK学生'}]},
                {'key': 'videoTag', 'name': '分类', 'value': [
                {'n': '丝袜美腿', 'v': '丝袜美腿'},
                {'n': '激情自慰', 'v': '激情自慰'},
                {'n': '空姐', 'v': '空姐'},
                {'n': '泳装', 'v': '泳装'},
                {'n': '职场OL', 'v': '职场OL'},
                {'n': '骚萝破处', 'v': '骚萝破处'},
            ]},
        ],
        'av': [
            {'key': 'videoTag', 'name': '分类', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '最新AV', 'v': '最新AV'},
                {'n': '人妻偷情', 'v': '人妻偷情'},
                {'n': '暗黑迷奸', 'v': '暗黑迷奸'},
                {'n': '日本JK', 'v': '日本JK'},
                {'n': '无码破解', 'v': '无码破解'},
                {'n': '中文AV', 'v': '中文AV'},
                {'n': 'FC2', 'v': 'FC2'},
                {'n': '重口AV', 'v': '重口AV'},
            ]},
        ],
        'chuanmei': [
            {'key': 'videoTag', 'name': '分类', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '麻豆传媒', 'v': '麻豆传媒'},
                {'n': 'jvid', 'v': 'jvid'},
                {'n': '蜜桃传媒', 'v': '蜜桃传媒'},
                {'n': '天美传媒', 'v': '天美传媒'},
                {'n': '糖心vlog', 'v': '糖心vlog'}]},
                {'key': 'videoTag', 'name': '分类', 'value': [
                {'n': '性视界', 'v': '性视界'},
                {'n': '91制片厂', 'v': '91制片厂'},
                {'n': '兔子先生', 'v': '兔子先生'},
                {'n': '星空传媒', 'v': '星空传媒'},
                {'n': '大象传媒', 'v': '大象传媒'},
                {'n': '香蕉传媒', 'v': '香蕉传媒'},
            ]},
        ],
        'zhongkou': [
            {'key': 'videoTag', 'name': '分类', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '屎尿', 'v': '屎尿'},
                {'n': '四爱', 'v': '四爱'},
                {'n': '血腥暴力', 'v': '血腥暴力'},
                {'n': '肛交菊花', 'v': '肛交菊花'},
                {'n': '道具', 'v': '道具'},
                {'n': '捆绑', 'v': '捆绑'},
                {'n': '男同真爱', 'v': '男同真爱'},
                {'n': '虐待', 'v': '虐待'},
                {'n': '人兽', 'v': '人兽'},
                {'n': '踩踏虐鸡', 'v': '踩踏虐鸡'},
                {'n': '恋物足交', 'v': '恋物足交'},
            ]},
        ],
        'manhua': [
            {'key': 'videoTag', 'name': '分类', 'value': [
                {'n': '最新', 'v': ''},
                {'n': '热门推荐', 'v': '热门推荐'},
                {'n': '韩漫', 'v': '韩漫'},
                {'n': '同人', 'v': '同人'},
                {'n': '独家', 'v': '独家'},
                {'n': '国漫', 'v': '国漫'},
                {'n': '日漫', 'v': '日漫'},
                {'n': '3D', 'v': '3D'},
                {'n': '单行本', 'v': '单行本'},
                {'n': 'CG/AI', 'v': 'CG/AI'},
                {'n': 'COS写真', 'v': 'COS写真'},
                {'n': 'BL', 'v': 'BL'},
            ]},
        ],
    }

    def getName(self): return "AcFanH5"
    def isVideoFormat(self, url): return bool(url and ('.m3u8' in url or '.mp4' in url or '.mp3' in url))
    def manualVideoCheck(self): return False
    def destroy(self): pass

    def init(self, extend=""):
        self.session.verify = False
        self.short_pages = {}
        self.short_index = {}
        _doh_pin_domain(self.host.split('//')[-1].split('/')[0],
                        fallback=['108.138.7.103', '108.138.7.96', '108.138.7.85', '108.138.7.49'])

    def _hdr(self):
        t = str(int(time.time() * 1000))
        s = hashlib.md5(t[3:8].encode()).hexdigest()
        sid = hashlib.md5(str(int(time.time() * 1000)).encode()).hexdigest()[:16]
        return {
            'User-Agent': self.UA,
            'Accept': 'application/json, text/plain, */*',
            'Referer': self.host + '/',
            'Origin': self.host,
            'device': 'Android',
            'appVersion': '1.9.6',
            'User-Mark': 'xhp',
            'deviceId': self.device_id,
            'aut': self.token,
            't': t,
            's': s,
            'sid': sid,
        }

    def _dec(self, enc):
        if not enc:
            return None
        tk = self.token
        try:
            k = tk[2:18].encode('utf-8')
            raw = base64.b64decode(enc)
            d = _aes_decrypt(k, k, raw)
            d = d.decode('utf-8')
            return json.loads(d) if d and d[0] in '[{' else d
        except:
            return None

    def _api(self, path, params=None, method='GET'):
        for _ in range(3):
            h = self._hdr()
            p = dict(params or {})
            p['_t'] = h['t']
            url = self.host + '/api' + path
            try:
                if method == 'POST':
                    r = self.session.post(url, json=p, headers=h, timeout=15, verify=False, allow_redirects=False)
                else:
                    r = self.session.get(url, params=p, headers=h, timeout=15, verify=False, allow_redirects=False)
                if not r.text:
                    continue
                new_token = r.headers.get('refresh-authorization', '') or r.headers.get('Refresh-Authorization', '')
                if new_token:
                    self.token = new_token
                j = r.json()
                if not isinstance(j, dict):
                    return j
                code = j.get('code', 0)
                if code == 301:
                    if new_token:
                        continue
                    return None
                if code != 200:
                    return None
                if j.get('encData'):
                    d = self._dec(j['encData'])
                    return d if d is not None else None
                return j.get('data') if 'data' in j else j
            except:
                continue
        return None

    def _img(self, url, domain=None):
        if not url:
            return ''
        if isinstance(url, list):
            url = url[0] if url else ''
        if not url:
            return ''
        if not url.startswith('http'):
            d = domain or self.img_domain
            if not d.endswith('/'):
                d += '/'
            url = d + url.lstrip('/')
        try:
            b = self.getProxyUrl()
            if '?' not in b:
                b += '?do=py'
            return b + '&type=img&url=' + quote(url, safe='')
        except:
            return url

    def localProxy(self, param):
        try:
            if not isinstance(param, dict):
                param = {}
            pt = param.get('type') or param.get('do') or ''
            u = param.get('url', '')
            if isinstance(u, list):
                u = u[0]
            u = unquote(u) if u else ''
            if pt == 'img' and u:
                _pin_url_host(u)
                r = self.session.get(u, headers={'User-Agent': self.UA, 'Referer': self.host + '/'}, timeout=15, verify=False)

                def _mime(d):
                    if d[:4] == b'\x89PNG':
                        return 'image/png'
                    if d[:3] == b'GIF':
                        return 'image/gif'
                    if d[:4] == b'RIFF' and d[8:12] == b'WEBP':
                        return 'image/webp'
                    if d[:2] == b'\xff\xd8':
                        return 'image/jpeg'
                    return ''

                data = bytes(r.content)
                ct = _mime(data)
                if not ct:
                    data = bytearray(data)
                    key = b'2020-zq3-888'
                    for i in range(min(100, len(data))):
                        data[i] ^= key[i % len(key)]
                    data = bytes(data)
                    ct = _mime(data) or 'image/jpeg'
                return [200, ct, data]
            if pt == 'm3u8' and u:
                _pin_url_host(u)
                r = self.session.get(u, headers=self._hdr(), timeout=20, verify=False)
                if r.status_code != 200:
                    return [404, 'text/plain', b'nf']
                body = r.text
                b = self.getProxyUrl()
                if '?' not in b:
                    b += '?do=py'

                def _proxy(url):
                    return b + '&type=ts&url=' + quote(url, safe='')

                body = re.sub(r'(URI=")([^"]+)(")',
                              lambda m: m.group(1) + _proxy(m.group(2)) + m.group(3), body)
                lines = []
                for line in body.splitlines():
                    s = line.strip()
                    if s.startswith('http://') or s.startswith('https://'):
                        line = _proxy(s)
                    lines.append(line)
                body = '\n'.join(lines)
                return [200, 'application/vnd.apple.mpegurl;charset=UTF-8', body.encode('utf-8')]
            if pt == 'ts' and u:
                _pin_url_host(u)
                r = self.session.get(u, headers={'User-Agent': self.UA, 'Referer': self.host + '/'}, timeout=20, verify=False)
                if r.status_code != 200:
                    return [404, 'text/plain', b'nf']
                return [200, 'video/mp2t', r.content]
            return [404, 'text/plain', b'nf']
        except:
            return [500, 'text/plain', b'err']

    def _items(self, data):
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for k in ('data', 'list', 'videoList', 'records'):
                v = data.get(k)
                if isinstance(v, list):
                    return v
                if isinstance(v, dict):
                    inner = v.get('data') or v.get('list')
                    if isinstance(inner, list):
                        return inner
        return []

    def _domain(self, data):
        if isinstance(data, dict):
            return data.get('domain', '')
        return ''

    def homeContent(self, filter):
        classes = [
            {'type_id': 'jx', 'type_name': '精选'},
            {'type_id': 'dm', 'type_name': '动漫'},
            {'type_id': 'lifan', 'type_name': '里番'},
            {'type_id': 'rebao', 'type_name': '热播'},
            {'type_id': 'luanlun', 'type_name': '乱伦'},
            {'type_id': 'guochan', 'type_name': '国产'},
            {'type_id': 'wanghuang', 'type_name': '网黄'},
            {'type_id': 'luoli', 'type_name': '萝莉'},
            {'type_id': 'av', 'type_name': 'AV'},
            {'type_id': 'chuanmei', 'type_name': '传媒'},
            {'type_id': 'zhongkou', 'type_name': '重口'},
            {'type_id': 'manhua', 'type_name': '漫画'},
        ]
        return {'class': classes, 'filters': self.filters_data, 'list': self._home_videos(), 'type': '影视'}

    def homeVideoContent(self):
        return {'list': self._home_videos()}

    def _home_videos(self):
        data = self._api('/video/getByClassify', {'page': 1, 'pageSize': 20, 'classifyId': 4, 'sortType': 0, 'restricted': 0})
        return self._parse_list(data)

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except:
                extend = {}
        extend = extend or {}
        if str(tid) == 'manhua':
            return self._comic_category(page, extend)
        if str(tid) == 'jx':
            jx_type = self._ext_val(extend, 'jxType')
            if not jx_type:
                if self._ext_val(extend, 'fictionType') or self._ext_val(extend, 'tag1') or self._ext_val(extend, 'tag2'):
                    jx_type = 'fiction'
                elif self._ext_val(extend, 'shortMode') or self._ext_val(extend, 'shortPlot'):
                    jx_type = 'short'
            if jx_type == 'short':
                return self._short_category(page, extend)
            if jx_type == 'fiction':
                return self._fiction_category(page, extend)
        cid = self._ext_val(extend, 'classifyId') or self.cat_map.get(str(tid), '')
        vt = self._ext_val(extend, 'videoTag')
        if vt:
            params = {'tagsTitle': vt, 'page': page, 'pageSize': 20, 'sortType': 0, 'restricted': 0}
            data = self._api('/video/tagTitleList', params)
        else:
            params = {'page': page, 'pageSize': 20, 'sortType': 0, 'restricted': 0, 'classifyId': cid}
            data = self._api('/video/getByClassify', params)
        items = self._parse_list(data)
        total = data.get('total') if isinstance(data, dict) else 0
        return self._page_result(page, items, total)

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        ps = vid.split('@@@')
        rid = ps[0] if len(ps) > 0 else vid
        name = unquote(ps[2]) if len(ps) > 2 else rid
        pic = unquote(ps[3]) if len(ps) > 3 else ''
        if str(rid).startswith('c_'):
            return self._comic_detail(rid[2:], name, pic)
        if str(rid).startswith('f_'):
            return self._fiction_detail(rid[2:], name, pic)
        if str(rid).startswith('srec_') or str(rid).startswith('s_'):
            real = rid[5:] if str(rid).startswith('srec_') else rid[2:]
            return self._short_detail(real, name, pic)
        data = self._api('/video/getVideoById', {'videoId': rid})
        vname, vpic, vcontent, video_url = name, pic, '', ''
        domain = ''
        if isinstance(data, dict):
            domain = data.get('domain', '')
            vname = data.get('title') or vname
            vpic = data.get('coverImg') or vpic
            if isinstance(vpic, list):
                vpic = vpic[0] if vpic else vpic
            vcontent = data.get('description') or data.get('synopsis') or ''
            video_url = data.get('videoUrl') or data.get('playUrl') or ''
            tags = data.get('tagTitles') or []
            if tags:
                vcontent = '标签: ' + ' '.join(tags) + ('\n' + vcontent if vcontent else '')
        play_url = ''
        line = self._m3u8_play(video_url)
        if line:
            play_url = '播放$' + line
        vod = {
            'vod_id': vid,
            'vod_name': vname,
            'vod_pic': self._img(vpic, domain),
            'vod_content': vcontent,
            'vod_play_from': 'AcFanH5',
            'vod_play_url': play_url,
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        data = self._api('/search/keyWordV2', {'searchWord': key, 'page': page, 'pageSize': 20})
        items = self._parse_list(data)
        total = data.get('total') if isinstance(data, dict) else 0
        return self._page_result(page, items, total)

    def playerContent(self, flag, id, vipFlags=None):
        url = id or ''
        hdr = {'User-Agent': self.UA, 'Referer': self.host + '/', 'Origin': self.host}
        if url.startswith('novel://'):
            return {'parse': 0, 'url': url, 'header': hdr}
        if url.startswith('fplay:'):
            play = self._fiction_play(url)
            if play:
                return {'parse': 0, 'url': play, 'header': hdr}
            return {'parse': 1, 'url': url, 'header': hdr}
        if self.isVideoFormat(url) or (url and '.txt' in url):
            return {'parse': 0, 'url': url, 'header': hdr}
        if url.startswith(self.host + '/api/m3u8/'):
            return {'parse': 0, 'url': url, 'header': hdr}
        if '/proxy?' in url or '/local/' in url or url.startswith('http://127.0.0.1'):
            return {'parse': 0, 'url': url, 'header': hdr}
        return {'parse': 1, 'url': url, 'header': hdr}

    def _ext_val(self, extend, key):
        v = extend.get(key, '')
        if isinstance(v, list):
            v = v[0] if v else ''
        if v is None:
            v = ''
        return str(v).strip()

    def _page_result(self, page, items, total=0, limit=20):
        if total:
            pc = -(-int(total) // limit)
        else:
            pc = page + 1 if items else 1
        return {'page': page, 'pagecount': pc, 'limit': limit, 'total': total if total else pc * limit, 'list': items}

    def _m3u8_play(self, video_url):
        if not video_url:
            return ''
        path = str(video_url)
        try:
            b = self.getProxyUrl()
            if '?' not in b:
                b += '?do=py'
            m3u8_api = self.host + '/api/m3u8/h5/decode?path=' + quote(path, safe='')
            return b + '&type=m3u8&url=' + quote(m3u8_api, safe='')
        except:
            return self.host + '/api/m3u8/h5/decode?path=' + quote(path, safe='')

    def _short_cache_put(self, bucket, page, data):
        if not hasattr(self, 'short_pages'):
            self.short_pages = {}
        if not hasattr(self, 'short_index'):
            self.short_index = {}
        raw = [it for it in self._items(data) if isinstance(it, dict)]
        self.short_pages[(bucket, page)] = {
            'domain': self._domain(data),
            'items': raw,
        }
        for it in raw:
            iid = str(it.get('videoId') or '')
            if iid:
                self.short_index[iid] = (bucket, page)

    def _short_cache_get(self, vid):
        pages = getattr(self, 'short_pages', {}) or {}
        key = getattr(self, 'short_index', {}).get(str(vid))
        if key in pages:
            return pages[key]
        for pack in pages.values():
            for it in pack.get('items') or []:
                if str(it.get('videoId') or '') == str(vid):
                    return pack
        return None

    def _short_category(self, page, extend):
        mode = self._ext_val(extend, 'shortMode') or 'find'
        plot = self._ext_val(extend, 'shortPlot')
        if mode == 'rec':
            data = self._api('/video/list', {'page': page, 'pageSize': 20, 'loadType': 2})
            self._short_cache_put('rec', page, data)
            items = self._parse_list(data, id_prefix='s_')
        else:
            cid = plot or '42'
            data = self._api('/video/getByClassify', {'page': page, 'pageSize': 20, 'classifyId': cid, 'sortType': 1, 'restricted': 0})
            self._short_cache_put('find_' + cid, page, data)
            items = self._parse_list(data, id_prefix='s_')
        total = data.get('total') if isinstance(data, dict) else 0
        return self._page_result(page, items, total)

    def _short_detail(self, vid, name, pic):
        clicked = str(vid)
        cached = self._short_cache_get(clicked)
        items = list((cached or {}).get('items') or [])
        domain = (cached or {}).get('domain') or ''
        seen = set()
        ordered = []
        for item in items:
            if not isinstance(item, dict):
                continue
            iid = str(item.get('videoId') or '')
            if not iid or iid in seen:
                continue
            seen.add(iid)
            ordered.append(item)
        head = [it for it in ordered if str(it.get('videoId')) == clicked]
        if not head:
            data = self._api('/video/getVideoById', {'videoId': clicked})
            if isinstance(data, dict) and (data.get('videoId') or data.get('videoUrl') or data.get('playUrl')):
                if not domain:
                    domain = data.get('domain', '')
                head = [data]
        tail = [it for it in ordered if str(it.get('videoId')) != clicked]
        ordered = head + tail
        play_parts = []
        vname, vpic, vcontent = name, pic, '短视频'
        for item in ordered:
            iid = str(item.get('videoId') or '')
            title = str(item.get('title') or iid)
            vurl = item.get('videoUrl') or item.get('playUrl') or ''
            line = self._m3u8_play(vurl)
            if not line:
                continue
            play_parts.append(title.replace('#', ' ').replace('$', ' ') + '$' + line)
            if iid == clicked:
                vname = title
                vpic = item.get('coverImg') or vpic
                if isinstance(vpic, list):
                    vpic = vpic[0] if vpic else vpic
                tags = item.get('tagTitles') or []
                if tags:
                    vcontent = '标签: ' + ' '.join(tags)
        vod = {
            'vod_id': 's_' + str(vid),
            'vod_name': vname or '短视频',
            'vod_pic': self._img(vpic, domain),
            'vod_content': vcontent,
            'vod_play_from': '短视频',
            'vod_play_url': '#'.join(play_parts),
        }
        return {'list': [vod]}

    def _fiction_category(self, page, extend):
        ftype = self._ext_val(extend, 'fictionType') or '1'
        tag_key = 'tag2' if ftype == '2' else 'tag1'
        tag = self._ext_val(extend, tag_key)
        params = {'fictionType': int(ftype) if ftype.isdigit() else 1, 'page': page, 'pageSize': 20}
        if tag and tag.isdigit():
            params['tagIds'] = [int(tag)]
        data = self._api('/fiction/base/findList', params, method='POST')
        items = self._fiction_parse_list(data)
        total = data.get('total') if isinstance(data, dict) else 0
        return self._page_result(page, items, total)

    def _fiction_parse_list(self, data):
        domain = self._domain(data)
        items = self._items(data)
        res = []
        seen = set()
        for item in (items or []):
            try:
                if not isinstance(item, dict):
                    continue
                fid = str(item.get('fictionId') or '')
                if not fid or fid in seen:
                    continue
                seen.add(fid)
                name = str(item.get('fictionTitle') or fid)
                pic = item.get('coverImg') or ''
                if isinstance(pic, list):
                    pic = pic[0] if pic else ''
                num = str(item.get('chapterNewNum') or item.get('chapterNum') or '')
                ftype = item.get('fictionType')
                remark = '有声' if str(ftype) == '2' else ''
                if num and str(num).isdigit():
                    remark = (remark + ' ' if remark else '') + (num + '章')
                sid = 'f_' + fid + '@@@' + '' + '@@@' + quote(str(name)) + '@@@' + quote(str(pic) if isinstance(pic, str) else '')
                res.append({
                    'vod_id': sid,
                    'vod_name': name,
                    'vod_pic': self._img(pic, domain),
                    'vod_remarks': remark,
                })
            except:
                continue
        return res

    def _fiction_detail(self, fid, name, pic):
        data = self._api('/fiction/base/info', {'fictionId': fid})
        vname, vpic, domain, chapters = name, pic, '', []
        tags = []
        info = ''
        ftype = 1
        if isinstance(data, dict):
            domain = data.get('domain', '')
            vname = data.get('fictionTitle') or vname
            vpic = data.get('coverImg') or vpic
            chapters = data.get('chapters') or data.get('chapterList') or []
            tags = data.get('tagList') or []
            info = data.get('info') or ''
            ftype = data.get('fictionType') or 1
        tlist = []
        for t in (tags or []):
            if isinstance(t, dict) and t.get('title'):
                tlist.append(str(t['title']))
        content = '标签: ' + ' '.join(tlist) if tlist else ('有声小说' if str(ftype) == '2' else '小说')
        if info:
            content = content + '\n' + str(info)
        play_parts = []
        is_audio = str(ftype) == '2'
        for ch in (chapters or []):
            try:
                cid = ch.get('chapterId')
                if not cid:
                    continue
                ch_name = str(ch.get('chapterTitle') or ('第%d章' % (ch.get('chapterNum') or 0)))
                ch_name = ch_name.replace('#', ' ').replace('$', ' ')
                play_parts.append(ch_name + '$fplay:' + str(fid) + ':' + str(cid))
            except:
                continue
        vod = {
            'vod_id': 'f_' + str(fid),
            'vod_name': vname,
            'vod_pic': self._img(vpic, domain),
            'vod_content': content,
            'vod_play_from': '视频' if is_audio else '小说',
            'vod_play_url': '#'.join(play_parts),
        }
        return {'list': [vod]}

    def _join_url(self, domain, path):
        if not path:
            return ''
        path = str(path)
        if path.startswith('http://') or path.startswith('https://'):
            return path
        d = str(domain or '')
        if d and not d.endswith('/'):
            d += '/'
        return d + path.lstrip('/') if d else path

    def _fetch_txt(self, url):
        if not url:
            return ''
        try:
            _pin_url_host(url)
            r = self.session.get(url, headers={'User-Agent': self.UA, 'Referer': self.host + '/'}, timeout=15, verify=False)
            if r.status_code != 200 or not r.content:
                return ''
            raw = r.content
            for enc in ('utf-8', 'gbk', 'gb2312'):
                try:
                    return raw.decode(enc)
                except:
                    continue
            return raw.decode('utf-8', 'ignore')
        except:
            return ''

    def _novel_play(self, ci, name=''):
        fic = (ci or {}).get('fictionUrl') or ''
        play = (ci or {}).get('playPath') or ''
        domain = (ci or {}).get('domain') or ''
        txt_url = play or self._join_url(domain, fic)
        title = name or str((ci or {}).get('chapterTitle') or '正文')
        body = self._fetch_txt(txt_url)
        payload = {
            'name': title,
            'url': txt_url,
            'content': body,
        }
        return 'novel://' + json.dumps(payload, ensure_ascii=False)

    def _audio_video_play(self, ci):
        fic = (ci or {}).get('fictionUrl') or ''
        play = (ci or {}).get('playPath') or ''
        domain = (ci or {}).get('domain') or ''
        mp4d = (ci or {}).get('mp4Domain') or ''
        if fic and ('.m3u8' in str(fic) or '.mp4' in str(fic)):
            return self._m3u8_play(fic)
        if mp4d and fic:
            return self._join_url(mp4d, fic)
        if play:
            return play
        return self._join_url(domain, fic)

    def _fiction_play(self, url):
        ps = str(url).split(':')
        fid = ps[1] if len(ps) > 1 else ''
        cid = ps[2] if len(ps) > 2 else ''
        ci = self._api('/fiction/base/chapterInfo', {'chapterId': cid, 'fictionId': fid})
        if not isinstance(ci, dict):
            return ''
        ftype = str(ci.get('fictionType') or '')
        fic = str(ci.get('fictionUrl') or '')
        if ftype == '1' or (fic.endswith('.txt') and '.mp3' not in fic and '.m3u8' not in fic and '.mp4' not in fic):
            return self._novel_play(ci, str(ci.get('chapterTitle') or ''))
        return self._audio_video_play(ci)

    def _comic_category(self, page, extend):
        vt = self._ext_val(extend, 'videoTag')
        cid = self.comic_class.get(vt, '1')
        data = self._api('/comics/base/findList', {'classId': cid, 'orderType': 0, 'restricted': 0, 'page': page, 'pageSize': 20}, method='POST')
        items = self._comic_parse_list(data)
        total = data.get('total') if isinstance(data, dict) else 0
        return self._page_result(page, items, total)

    def _comic_parse_list(self, data):
        domain = self._domain(data)
        items = self._items(data)
        res = []
        seen = set()
        for item in (items or []):
            try:
                if not isinstance(item, dict):
                    continue
                cid = str(item.get('comicsId') or '')
                if not cid or cid in seen:
                    continue
                seen.add(cid)
                name = str(item.get('comicsTitle') or cid)
                pic = item.get('coverImg') or ''
                if isinstance(pic, list):
                    pic = pic[0] if pic else ''
                num = str(item.get('chapterNewNum') or '')
                sid = 'c_' + cid + '@@@' + '' + '@@@' + quote(str(name)) + '@@@' + quote(str(pic) if isinstance(pic, str) else '')
                res.append({
                    'vod_id': sid,
                    'vod_name': name,
                    'vod_pic': self._img(pic, domain),
                    'vod_remarks': num + '话' if num and num.isdigit() else '',
                })
            except:
                continue
        return res

    def _comic_detail(self, cid, name, pic):
        data = self._api('/comics/base/info', {'comicsId': cid})
        vname, vpic, domain, chapters = name, pic, '', []
        tags = []
        if isinstance(data, dict):
            domain = data.get('domain', '')
            vname = data.get('comicsTitle') or vname
            vpic = data.get('coverImg') or vpic
            chapters = data.get('chapterList') or []
            tags = data.get('tagList') or []
        content = '漫画'
        tlist = []
        for t in (tags or []):
            if isinstance(t, dict) and t.get('title'):
                tlist.append(str(t['title']))
        if tlist:
            content = '标签: ' + ' '.join(tlist)
        play_parts = []
        for ch in (chapters or [])[:20]:
            try:
                ci = self._api('/comics/base/chapterInfo', {'chapterId': ch.get('chapterId')})
                imgs = []
                if isinstance(ci, dict):
                    imgs = ci.get('imgList') or []
                pics = '&&'.join(self._img(i, domain) for i in imgs if i)
                if not pics:
                    continue
                ch_name = str(ch.get('chapterTitle') or ('第%d话' % (ch.get('chapterNum') or 0)))
                play_parts.append(ch_name + '$pics://' + pics)
            except:
                continue
        vod = {
            'vod_id': 'c_' + str(cid),
            'vod_name': vname,
            'vod_pic': self._img(vpic, domain),
            'vod_content': content,
            'vod_play_from': '图片',
            'vod_play_url': '#'.join(play_parts),
            'vod_tag': 'image',
        }
        return {'list': [vod]}

    def _parse_list(self, data, id_prefix=''):
        domain = self._domain(data)
        items = self._items(data)
        res = []
        seen = set()
        for item in (items or []):
            try:
                if not isinstance(item, dict):
                    continue
                vid = str(item.get('videoId') or item.get('id') or '')
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                name = str(item.get('title') or vid)
                pic = item.get('coverImg') or ''
                if isinstance(pic, list):
                    pic = pic[0] if pic else ''
                dur = str(item.get('playTime') or '')
                if dur and dur.isdigit():
                    dur = str(int(dur) // 60) + ':' + str(int(dur) % 60).zfill(2)
                sid = str(id_prefix) + vid + '@@@' + '' + '@@@' + quote(str(name)) + '@@@' + quote(str(pic) if isinstance(pic, str) else '')
                res.append({
                    'vod_id': sid,
                    'vod_name': name,
                    'vod_pic': self._img(pic, domain),
                    'vod_remarks': dur if dur else '',
                })
            except:
                continue
        return res
