#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""КРИТИК-ФСМ: конечный автомат карты вселенной rtynbirf.

Состояния: СОГЛАСОВАНА | РАССИНХРОН | ЗАМОЛК
События:   ТИК (каждый запуск 04:21 UTC) · РАСХОЖДЕНИЕ чисел · ВОЗРАСТ > 72Ч
Переходы:
    СОГЛАСОВАНА --совпадение--> СОГЛАСОВАНА      (пульс: коммит состояния)
    СОГЛАСОВАНА --расхождение--> РАССИНХРОН      (перегенерация карты + issue)
    любая --возраст>72ч--> ЗАМОЛК                (issue-тревога: молчание = смерть органа)
    РАССИНХРОН --перегенерировано--> СОГЛАСОВАНА
    ЗАМОЛК --тик--> СОГЛАСОВАНА

Секретов нет: живые данные — публичный API /users/rtynbirf/repos; GH_TOKEN лишь
повышает rate-limit. Работает и без токена.
"""
import json, os, re, sys, subprocess, datetime, urllib.request, argparse

OWNER = "rtynbirf"
STALE_HOURS = 72

def api(url):
    hdr = {"User-Agent": "karta-critic"}
    tok = os.environ.get("GH_TOKEN")
    if tok:
        hdr["Authorization"] = f"Bearer {tok}"
    req = urllib.request.Request(url, headers=hdr)
    with urllib.request.urlopen(req) as r:
        return json.load(r), r.headers.get("Link", "")

def last_page(link):
    m = re.findall(r'[?&]page=(\d+)>; rel="last"', link)
    return int(m[0]) if m else None

def fetch_live():
    repos, page = [], 1
    while True:
        chunk, link = api(f"https://api.github.com/users/{OWNER}/repos?per_page=100&page={page}")
        repos += chunk
        lp = last_page(link)
        if not lp or page >= lp:
            break
        page += 1
    out = []
    for r in repos:
        _, clink = api(f"https://api.github.com/repos/{OWNER}/{r['name']}/commits?per_page=1")
        commits = last_page(clink) or (0 if clink else 1)
        out.append({"name": r["name"], "private": False, "fork": r["fork"], "archived": r["archived"],
                    "size_kb": r["size"], "commits": commits, "created_at": r["created_at"],
                    "pushed_at": r["pushed_at"], "language": r["language"], "description": r["description"]})
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="корень репо karta")
    ap.add_argument("--now", help="подменить текущее время (тест ФСМ), ISO")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    kj = os.path.join(root, "karta.json")           # раскладка v3: карта в корне
    if not os.path.exists(kj):
        kj = os.path.join(root, "karta", "karta.json")
    karta_json = kj
    state_path = os.path.join(root, "karta", "state.json")

    now = (datetime.datetime.fromisoformat(a.now) if a.now else datetime.datetime.now(datetime.timezone.utc))
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    state = {"state": "ИНИЦИАЛИЗАЦИЯ", "last_run": None, "history": []}
    if os.path.exists(state_path):
        state = json.load(open(state_path))

    stale_hours = None
    if state.get("last_run"):
        prev = datetime.datetime.fromisoformat(state["last_run"].replace("Z", "+00:00"))
        stale_hours = (now - prev).total_seconds() / 3600.0

    old = json.load(open(karta_json))["totals"]
    live = fetch_live()
    live_n = sum(1 for r in live if not r["archived"])
    new = {"repos": len(live), "live": live_n,
           "okamenelosti": len(live) - live_n,
           "forks": sum(1 for r in live if r["fork"]),
           "commits_total": sum(r["commits"] for r in live)}
    keys = ["repos", "live", "okamenelosti", "forks", "commits_total"]
    diffs = [f"{k}: {old.get(k)} → {new[k]}" for k in keys if old.get(k) != new[k]]

    # в ночной смене критик бежит ПОСЛЕ регенерации: свежая карта обязана совпасть
    # с API. Разошлась — ослеп не территория, а ГЕНЕРАТОР (rate-limit / баг).
    if stale_hours is not None and stale_hours > STALE_HOURS:
        st, action = "ЗАМОЛК", "ISSUE_STALE"
    elif diffs:
        st, action = "ОСЛЕП", "ISSUE_BLIND"
    else:
        st, action = "СОГЛАСОВАНА", "HEARTBEAT"

    hist = state.get("history", [])
    hist.append({"t": now_iso, "state": st, "diffs": diffs})
    state_out = {"state": st, "last_run": now_iso, "diverged": diffs,
                 "stale_hours": round(stale_hours, 1) if stale_hours is not None else None,
                 "totals": new, "history": hist[-30:]}

    if st == "РАССИНХРОН":
        fresh = os.path.join(root, "karta", "_fresh_snapshot.json")
        json.dump(live, open(fresh, "w"), ensure_ascii=False)
        gen = os.path.join(root, "scripts", "gen_karta.py")
        subprocess.run([sys.executable, gen, "--data", fresh, "--out", root], check=True)
        os.remove(fresh)
        state_out["state"] = "СОГЛАСОВАНА"

    json.dump(state_out, open(state_path, "w"), ensure_ascii=False, indent=1)

    print(f"STATE: {st}")
    print(f"LAST_RUN_AGE_H: {round(stale_hours,1) if stale_hours is not None else 'first-run'}")
    for d in diffs:
        print(f"DIFF: {d}")
    print("ACTION: COMMIT")
    if action == "ISSUE_STALE":
        print(f"ACTION: ISSUE_STALE |{stale_hours:.1f}h молчания (порог {STALE_HOURS}ч) — молчание = смерть органа")
    if action == "ISSUE_BLIND":
        print(f"ACTION: ISSUE_BLIND |генератор ослеп после регена: {'; '.join(diffs)} — сверь rate-limit/баг")

if __name__ == "__main__":
    main()
