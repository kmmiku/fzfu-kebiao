# -*- coding: utf-8 -*-
"""
福州外语外贸学院 课表抓取 + iCalendar 导出
=========================================
数据源: 正方教务系统 jw.fzfu.edu.cn (移动端接口)
- 课表:   POST /jwglxt/kbcx/xskbcxMobile_cxXsgrkb.html  (kblx=2 全学期周课表)
- 节次:   POST /jwglxt/jzgl/skxxMobile_cxRsdjc.html      (每节起止时间)
- 周映射: POST /jwglxt/kbcx/xskbcxMobile_cxXsgrkb.html  (kblx=1,zs=当前周 -> 当前周日期 -> 反推第1周周一)

输出:
- kebiao.ics   (iCalendar v2.0, 全学期展开事件, UID 稳定可增量更新)
- kebiao.json  (结构化原始课表, 供二次使用)

用法:
- python kebiao.py                     # 账号密码从 secret.txt 或环境变量 KEBIAO_USER/KEBIAO_PASS
- python kebiao.py 学号 密码
- python kebiao.py --xm 2026 --xqm 3   # 指定学年学期(可选, 默认自动取当前学期)
"""
import base64
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request

import login as L

XQM_NAME = {"3": "第1学期", "12": "第2学期", "16": "短学期"}

OUT_ICS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kebiao.ics")
OUT_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kebiao.json")


def post_json(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers={
        "User-Agent": L.UA,
        "Referer": L.BASE + "/jwglxt/kbcx/xskbcxMobile_cxTimeTableIndex.html?gnmkdm=Y253511",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
    })
    raw = L.opener.open(req, timeout=20).read()
    # 响应头: application/json;charset=UTF-8 (实测为 UTF-8)
    return json.loads(raw.decode("utf-8"))


def get_current_xnxq():
    """从课表页隐藏字段取当前学年学期与当前周"""
    html, _ = L.get(L.BASE + "/jwglxt/kbcx/xskbcxMobile_cxTimeTableIndex.html?gnmkdm=Y253511&xnm=&xqm=")
    def hid(name):
        m = re.search(r'id="%s"[^>]*value="([^"]*)"' % name, html)
        return m.group(1) if m else None
    return hid("xnm_hide"), hid("xqm_hide"), hid("zs_hide")


def semester_start(xnm, xqm, zs):
    """第1周周一日期: 用 kblx=1 拿当前周日期, 反推"""
    d = post_json(L.BASE + "/jwglxt/kbcx/xskbcxMobile_cxXsgrkb.html",
                  {"xnm": xnm, "xqm": xqm, "zs": zs, "doType": "app", "kblx": "1"})
    monday = None
    for day in (d.get("rqazcList") or []):
        if int(day["xqj"]) == 1:
            monday = dt.date.fromisoformat(day["rq"])
            break
    if monday is None:
        raise RuntimeError("rqazcList 中没有周一日期")
    return monday - dt.timedelta(weeks=int(zs) - 1)


def parse_zcd(zcd):
    """'2-4周,6-17周' / '9周' / '1-8,10-17周(单)' / '2-16周(双)' -> [(week,), ...] 周号列表"""
    weeks = set()
    for seg in re.split(r"[,,，]", zcd):
        seg = seg.strip().replace("周", "")
        if not seg:
            continue
        odd = "单" in seg
        even = "双" in seg
        seg = re.sub(r"[（(]\s*[单双]\s*[)）]", "", seg).strip()
        m = re.match(r"^(\d+)(?:-(\d+))?$", seg)
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2)) if m.group(2) else int(m.group(1))
        for w in range(a, b + 1):
            if odd and w % 2 == 0:
                continue
            if even and w % 2 == 1:
                continue
            weeks.add(w)
    return sorted(weeks)


def ics_escape(s):
    s = str(s)
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fmt_dt(d):
    return d.strftime("%Y%m%dT%H%M%S")


def build_ics(term_start, kb_list, sksj_list, xnm, xqm):
    """展开为离散事件; UID 稳定 => 重新生成时 iOS 日历按 UID 去重, 不产生重复"""
    def period_time(jc_no):
        for it in sksj_list:
            if str(it.get("jcmc")) == str(jc_no):
                return it["qssj"][:5].replace(":", ""), it["jssj"][:5].replace(":", "")
        return "0000", "2359"

    events = []
    for it in kb_list:
        kcmc = it["kcmc"]
        teacher = it.get("xm") or ""
        room = it.get("cdmc") or ""
        xqj = int(it["xqj"])
        jcs = it.get("jcs") or it.get("jcor") or ""
        m = re.match(r"^(\d+)", jcs)
        if not m:
            continue
        first_jc = int(m.group(1))
        last_jc = int(re.search(r"(\d+)\s*$", jcs).group(1))
        st_hhmm, _ = period_time(first_jc)
        _, en_hhmm = period_time(last_jc)
        for week in parse_zcd(it.get("zcd") or ""):
            day = term_start + dt.timedelta(weeks=week - 1, days=xqj - 1)
            dstart = dt.datetime.combine(day, dt.time(int(st_hhmm[:2]), int(st_hhmm[2:])))
            dend = dt.datetime.combine(day, dt.time(int(en_hhmm[:2]), int(en_hhmm[2:])))
            uid = hashlib.md5(f"{it.get('jxb_id')}|{it.get('zcd')}|{it['xqj']}|{jcs}|{week}|{xnm}{xqm}".encode()).hexdigest()
            summary = kcmc
            loc = room
            desc_parts = [f"教师: {teacher}" if teacher else "", f"周次: 第{week}周", f"节次: 第{jcs}节", f"课程代码: {it.get('kch','')}"]
            events.append({
                "uid": uid,
                "dstart": dstart, "dend": dend,
                "summary": summary, "location": loc,
                "description": "\n".join([p for p in desc_parts if p]),
            })

    events.sort(key=lambda e: (e["dstart"], e["summary"]))
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//FZFU Kebiao//CN//",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:福外课表 {xnm}-{int(xnm)+1}学年{XQM_NAME.get(xqm, xqm)}",
        "X-WR-TIMEZONE:Asia/Shanghai",
    ]
    for e in events:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{e['uid']}@fzfu-kebiao",
            f"DTSTAMP:{fmt_dt(dt.datetime.now())}",
            f"DTSTART:{fmt_dt(e['dstart'])}",
            f"DTEND:{fmt_dt(e['dend'])}",
            f"SUMMARY:{ics_escape(e['summary'])}",
            f"LOCATION:{ics_escape(e['location'])}",
            f"DESCRIPTION:{ics_escape(e['description'])}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    ics = "\r\n".join(lines) + "\r\n"
    return ics, events


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    xnm_opt = xqm_opt = None
    if "--xm" in sys.argv:
        xnm_opt = sys.argv[sys.argv.index("--xm") + 1]
    if "--xqm" in sys.argv:
        xqm_opt = sys.argv[sys.argv.index("--xqm") + 1]

    secrets = []
    sp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "secret.txt")
    if os.path.exists(sp):
        secrets = [ln.strip() for ln in open(sp, encoding="utf-8") if ln.strip()]
    yhm = args[0] if len(args) > 0 else os.environ.get("KEBIAO_USER") or (secrets[0] if secrets else "")
    mm = args[1] if len(args) > 1 else os.environ.get("KEBIAO_PASS") or (secrets[1] if len(secrets) > 1 else "")

    if not L.login(yhm, mm):
        sys.exit(1)
    L.get(L.BASE + "/jwglxt/xtgl/index_initMenu.html?jsdm=xs")

    if not (xnm_opt and xqm_opt):
        xnm_opt, xqm_opt, zs = get_current_xnxq()
    else:
        _, _, zs = get_current_xnxq()
    print(f"[学期] {xnm_opt}-{int(xnm_opt)+1} 第{ {'3':'1','12':'2','16':'3'}.get(xqm_opt, xqm_opt) }学期 (xnm={xnm_opt}, xqm={xqm_opt})")

    term_start = semester_start(xnm_opt, xqm_opt, zs)
    print(f"[学期起] 第1周周一 = {term_start}")

    kb = post_json(L.BASE + "/jwglxt/kbcx/xskbcxMobile_cxXsgrkb.html",
                   {"xnm": xnm_opt, "xqm": xqm_opt, "doType": "app", "kblx": "2"})
    kb_list = kb.get("kbList") or []
    print(f"[课表] 共 {len(kb_list)} 条排课记录")

    sksj = post_json(L.BASE + "/jwglxt/jzgl/skxxMobile_cxRsdjc.html",
                     {"xnm": xnm_opt, "xqm": xqm_opt, "xqh_id": "1"})
    print(f"[节次] 每天 {len(sksj)} 节")

    ics, events = build_ics(term_start, kb_list, sksj, xnm_opt, xqm_opt)
    with open(OUT_ICS, "w", encoding="utf-8", newline="") as f:  # newline='' 防止 \r\n 被二次转换
        f.write(ics)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"xnm": xnm_opt, "xqm": xqm_opt, "term_start": str(term_start),
                   "courses": kb_list, "events": [
                       {k: (v.isoformat() if isinstance(v, dt.datetime) else v) for k, v in e.items()}
                       for e in events]}, f, ensure_ascii=False, indent=1)
    print(f"[输出] {OUT_ICS}: {len(events)} 个课次事件")
    print(f"[输出] {OUT_JSON}")


if __name__ == "__main__":
    main()