"""登る山のおすすめページを作る: YAMAP の活動記録 -> docs/osusume.html

使い方: YAMAP_USER=<ユーザーID> python -X utf8 osusume.py
設計: design/osusume-20260920.md
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
CACHE = ROOT / "dist" / "yamap-cache.json"
API = "https://api.yamap.com/v3/"
JST = timezone(timedelta(hours=9))
MAX_CANDIDATES = 40
PREF = dict(zip("Hokkaido Aomori Iwate Miyagi Akita Yamagata Fukushima Ibaraki Tochigi Gunma Saitama Chiba Tokyo Kanagawa Niigata Toyama Ishikawa Fukui Yamanashi Nagano Gifu Shizuoka Aichi Mie Shiga Kyoto Osaka Hyogo Nara Wakayama Tottori Shimane Okayama Hiroshima Yamaguchi Tokushima Kagawa Ehime Kochi Fukuoka Saga Nagasaki Kumamoto Oita Miyazaki Kagoshima Okinawa".split(),
                "北海道 青森 岩手 宮城 秋田 山形 福島 茨城 栃木 群馬 埼玉 千葉 東京 神奈川 新潟 富山 石川 福井 山梨 長野 岐阜 静岡 愛知 三重 滋賀 京都 大阪 兵庫 奈良 和歌山 鳥取 島根 岡山 広島 山口 徳島 香川 愛媛 高知 福岡 佐賀 長崎 熊本 大分 宮崎 鹿児島 沖縄".split()))


def get(path):
    req = urllib.request.Request(API + path, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def cached(cache, key, path):
    if key not in cache:
        cache[key] = get(path)
        time.sleep(0.3)
    return cache[key]


def climbed_mountains(user, cache):
    """活動記録で踏んだ山 -> {山ID: 回数}"""
    acts, page = [], 1
    while page > 0:
        d = get(f"users/{user}/activities?per=100&page={page}")
        acts += d["activities"]
        page = d["meta"]["next_page"]
    count = {}
    for a in acts:
        ms = cached(cache, f"act:{a['id']}", f"activities/{a['id']}/mountains")["mountains"]
        for m in ms:
            count[m["id"]] = count.get(m["id"], 0) + 1
    return count, len(acts)


def slim(m, course, climbed):
    lon, lat = m["coord"]
    return {
        "id": m["id"],
        "name": m["name"],
        "alt": m["altitude"],
        "lat": round(lat, 4),
        "lon": round(lon, 4),
        "pref": [PREF.get(p["name"], p["name"]) for p in m.get("prefectures", [])][:2],
        "season": m.get("climber_statistics"),
        "img": None if climbed else (m.get("primary_image") or {}).get("small_url"),
        "climbed": climbed,
        "course": course and {
            "id": course["id"],
            "name": course["name"].split("|")[0].strip(),
            "sec": course["course_time"],
            "km": round(course["distance"] / 1000, 1),
            "up": course["cumulative_up"],
            "fit": course["ratings"].get("fitness_level"),
        },
    }


def main():
    user = os.environ.get("YAMAP_USER")
    if not user:
        sys.exit("YAMAP_USER が未設定")
    CACHE.parent.mkdir(exist_ok=True)
    cache = json.loads(CACHE.read_text("utf-8")) if CACHE.exists() else {}
    try:
        climbed, n_acts = climbed_mountains(user, cache)
        # 候補 = 登頂済みの山の周辺の山。多くの登頂済みから近い山ほど上
        near = {}
        for mid in climbed:
            m = cached(cache, f"mt:{mid}", f"mountains/{mid}")["mountain"]
            for s in m.get("surrounding_mountains", []):
                if s["id"] not in climbed:
                    near[s["id"]] = near.get(s["id"], 0) + 1
        picks = sorted(near, key=lambda i: -near[i])[:MAX_CANDIDATES]
        out = []
        for mid in picks + list(climbed):
            m = cached(cache, f"mt:{mid}", f"mountains/{mid}")["mountain"]
            course = None
            if mid in picks and m.get("model_course_count"):
                cs = cached(cache, f"mc:{mid}", f"mountains/{mid}/model_courses?per=20")["model_courses"]
                cs = [c for c in cs if c.get("course_time")]
                course = min(cs, key=lambda c: c["course_time"]) if cs else None
            if mid in picks and not course:
                continue  # コースタイムが無いと気象窓を決められない
            out.append(slim(m, course, climbed.get(mid, 0)))
    finally:
        CACHE.write_text(json.dumps(cache, ensure_ascii=False), "utf-8")

    html = (ROOT / "osusume-template.html").read_text("utf-8")
    html = html.replace("/*DATA*/null", json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("<!--BUILT-->", datetime.now(JST).strftime("%m/%d %H:%M"))
    (ROOT / "docs" / "osusume.html").write_text(html, "utf-8")
    n_new = sum(1 for o in out if not o["climbed"])
    print(f"活動 {n_acts} 件 / 登頂済み {len(climbed)} 山 / 候補 {n_new} 山 -> docs/osusume.html")


if __name__ == "__main__":
    main()
