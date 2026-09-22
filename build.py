"""YAMAP の計画 URL から、山の天気マップ（静的 HTML）を作る。

使い方: python -X utf8 build.py <YAMAP 計画URL> [出力先フォルダ(既定 docs)]
      python -X utf8 build.py --stale  （新しい計画が読めないとき、今のページにお知らせを出す）
"""
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
JST = timezone(timedelta(hours=9))
MAX_POINTS = 14  # Open-Meteo 1回の呼び出しに載せる地点数


def fetch_plan(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    # GitHub Actions からだと YAMAP がときどき 403 を返す（2026-09-20、毎時13回中2回）
    for wait in (5, 20, None):
        try:
            html = urllib.request.urlopen(req, timeout=30).read().decode("utf8")
            break
        except urllib.error.HTTPError:
            if wait is None:
                raise
            time.sleep(wait)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    return json.loads(m.group(1))["props"]["pageProps"]["plan"]


def pick_points(cps):
    """日ごとに 出発・宿泊地・その日の最高地点 を残す（同じ場所は1つにまとめる）"""
    by_day = {}
    for c in cps:
        by_day.setdefault(c["arrivalDayNumber"], []).append(c)
    keep = []
    for day, lst in sorted(by_day.items()):
        top = max(lst, key=lambda c: c["altitude"] or 0)
        for c in (lst[0], top, lst[-1]):
            if c not in keep:
                keep.append(c)
    return keep


def plan_id(url):
    """いまのページがどの計画から作られたかの目印（URL そのものは残さない）"""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def mark_stale(out):
    """新しい計画が YAMAP で開けないとき、前の計画のままだと分かるようにする。次に作り直せば消える"""
    page = out / "index.html"
    html = page.read_text(encoding="utf8")
    now = datetime.now(JST)
    note = (
        '<div class="bad" style="margin:6px 16px;padding:10px 14px;border-radius:12px;font-weight:700">'
        f"新しい登山計画を YAMAP から読めませんでした（{now.month}/{now.day} {now.hour}時）。"
        '<small style="display:block;font-weight:400">下は前の計画のままです。計画を作り直すと、自動でここに出ます。</small></div>'
    )
    block = f"<!--STALE-->{note}<!--/STALE-->"
    if "<!--STALE--><!--/STALE-->" in html:
        html = html.replace("<!--STALE--><!--/STALE-->", block)
    elif "<!--STALE-->" in html:
        return  # もう出ている（時刻を書き換えて毎時コミットしない）
    else:  # 目印の無い古いテンプレートで作ったページ
        html = html.replace("<nav ", block + "\n<nav ", 1)
    page.write_text(html, encoding="utf8")
    print("お知らせを出した")


def main():
    if sys.argv[1] == "--stale":
        return mark_stale(Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "docs")
    url = sys.argv[1]
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "docs"
    plan = fetch_plan(url)
    cps = [c for c in plan["checkpoints"] if c.get("coord")]
    start = datetime.fromtimestamp(plan["startAt"], JST).date()

    def conv(c):
        name = (c.get("landmark") or {}).get("name") or c.get("name") or "地点"
        return {
            "n": name,
            "lat": round(c["coord"][1], 5),
            "lon": round(c["coord"][0], 5),
            "alt": round(c["altitude"] or 0),
            "day": c["arrivalDayNumber"],
            "h": c["arrivalTimeInSeconds"] // 3600,
            "m": c["arrivalTimeInSeconds"] % 3600 // 60,
            "sleep": c.get("stayType") == "sleep",
        }

    key = pick_points(cps)[:MAX_POINTS]
    coords = plan["coords"]
    step = max(1, len(coords) // 600)
    data = {
        "start": start.isoformat(),
        "days": max(c["arrivalDayNumber"] for c in cps),
        "area": re.sub(r"-\d{4}-\d{2}-\d{2}$", "", plan["title"]),
        "route": [[round(y, 5), round(x, 5)] for x, y in coords[::step]],
        "all": [conv(c) for c in cps],
        "key": [conv(c) for c in key],
    }
    html = (HERE / "template.html").read_text(encoding="utf8")
    html = html.replace("/*PLAN*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(html, encoding="utf8")
    (out / "plan-id.txt").write_text(plan_id(url) + "\n", encoding="utf8")
    (out / "sw.js").write_text((HERE / "sw.js").read_text(encoding="utf8"), encoding="utf8")
    print(f"OK {out / 'index.html'}  地点{len(data['key'])}/{len(cps)}  {data['start']}から{data['days']}日")


if __name__ == "__main__":
    main()
