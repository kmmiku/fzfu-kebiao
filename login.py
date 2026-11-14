# -*- coding: utf-8 -*-
"""福州外语外贸学院 正方教务系统 登录模块 (纯标准库)
流程: GET login页(拿JSESSIONID+csrftoken) -> GET 公钥 -> RSA(PKCS#1 v1.5)加密密码 -> POST 登录
"""
import base64
import http.cookiejar
import json
import re
import sys
import urllib.parse
import urllib.request

BASE = "http://jw.fzfu.edu.cn"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def get(url, referer=None, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Referer": referer or BASE + "/jwglxt/xtgl/login_slogin.html",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    with opener.open(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore"), r.geturl()


def post(url, data, referer=None, timeout=20):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers={
        "User-Agent": UA,
        "Referer": referer or BASE + "/jwglxt/xtgl/login_slogin.html",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
    })
    with opener.open(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore"), r.geturl()


def rsa_encrypt(password: str, modulus_b64: str, exponent_b64: str) -> str:
    """RSA PKCS#1 v1.5 加密, 输出与前端 hex2b64(rsaKey.encrypt(pwd)) 相同的 base64"""
    n = int.from_bytes(base64.b64decode(modulus_b64), "big")
    e = int.from_bytes(base64.b64decode(exponent_b64), "big")
    k = (n.bit_length() + 7) // 8
    m = password.encode("utf-8")
    if len(m) > k - 11:
        raise ValueError("password too long")
    em = b"\x00\x02" + b"\xff" * (k - len(m) - 3) + b"\x00" + m
    c = pow(int.from_bytes(em, "big"), e, n)
    h = format(c, "x")
    h = h.zfill(k * 2)  # 补齐到 k 字节, 与前端 hex 字符串对齐
    return base64.b64encode(bytes.fromhex(h)).decode()


def login(yhm: str, mm: str) -> bool:
    # 1. 登录页: 拿 JSESSIONID + csrftoken
    html, _ = get(BASE + "/jwglxt/xtgl/login_slogin.html?time=1")
    m = re.search(r'id="csrftoken"[^>]*value="([^"]+)"', html)
    if not m:
        raise RuntimeError("csrftoken not found")
    csrftoken = m.group(1)

    # 2. 公钥
    key_json, _ = get(BASE + "/jwglxt/xtgl/login_getPublicKey.html?time=1")
    key = json.loads(key_json)

    # 3. 加密 + 登录
    enc_mm = rsa_encrypt(mm, key["modulus"], key["exponent"])
    resp, url = post(BASE + "/jwglxt/xtgl/login_slogin.html", {
        "yhm": yhm,
        "mm": enc_mm,
        "csrftoken": csrftoken,
    })

    # 4. 判定: 失败时响应含提示; 成功跳转主页
    if "用户名或密码" in resp or "密码错误" in resp or "账号" in resp and "错误" in resp:
        print("[login] FAIL:", resp[:300])
        return False
    ok = any(k in url for k in ("index", "xtgl") ) and "login_slogin" not in url
    print("[login] OK ->", url)
    return True


if __name__ == "__main__":
    import os
    yhm = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("KEBIAO_USER", "")
    mm = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("KEBIAO_PASS", "")
    if not (yhm and mm):
        print("用法: python login.py 学号 密码 (或设置 KEBIAO_USER/KEBIAO_PASS 环境变量)", file=sys.stderr)
        sys.exit(2)
    ok = login(yhm, mm)
    sys.exit(0 if ok else 1)