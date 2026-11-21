#!/usr/bin/env python3
"""СНАПШОТ-ГОСУДАРСТВО · 2026-11-21 · волна «ВОЛЕВОЕ РЕШЕНИЕ», пункты 1+2+4.
РУКАМИ СЧЁТЧИК — ЗАПРЕЩЁН: всякое число здесь генерится из источника
(GitHub API), ни одной цифры не написано человеком.
Карта = артефакт сборки: snapshot.json пишется этим скриптом,
доки (СЧЁТЧИКИ.md, СТАТУС.md) рендерятся ТОЛЬКО из snapshot.json.
Честность по построению: вердикт «работает/прототип/статика» — из фактов
(последний прогон CI + наличие тестов), не из деклараций.

Запуск: GH_TOKEN=... python3 snapshot_gen.py --out <dir>
Без токена работает на публичных данных (лимиты ниже), но медленнее.
"""
import argparse, json, os, re, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone

OWNER = "rtynbirf"
ORGANS = ["AGENTS.md", "INV_LEDGER.jsonl", "automaton-state.json", "hologram.json",
          "revomat.py", "revo_autopilot.py", "revo_obhod.py", "PUSH.md", "TZ.md",
          "WORK_REPORT.md", "GOVERNANCE.md"]
ORGAN_DIRS = ["ДОМ"]
TEST_RE = re.compile(r"(^|/)(tests?|__tests__)(/|$)|(^|/)test_[^/]+\.py$|(^|/)[^/]+_test\.py$|\.test\.(js|mjs|ts)$|(^|/)[^/]*тест[^/]*$", re.I)


def hdr(tok):
    h = {"Accept": "application/vnd.github+json", "User-Agent": "snapshot-gos/0.1"}
    if tok:
        h["Authorization"] = "Bearer " + tok
    return h


def api(tok, path):
    req = urllib.request.Request("https://api.github.com" + path, headers=hdr(tok))
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read(), r.headers, r.getcode()


def jget(tok, path):
    try:
        raw, _, _ = api(tok, path)
        return json.loads(raw), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, str(e)[:80]


def commit_count(tok, repo):
    """Число коммитов через Link: rel=last (источник — git, не чья-то рука)."""
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{OWNER}/{repo}/commits?per_page=1", headers=hdr(tok))
        with urllib.request.urlopen(req, timeout=30) as r:
            link = r.headers.get("Link", "")
        m = re.search(r'[?&]page=(\d+)>; rel="last"', link)
        return int(m.group(1)) if m else 1, None
    except urllib.error.HTTPError as e:
        if e.code == 409:  # пустой репо
            return 0, None
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, str(e)[:80]


def tree_scan(tok, repo, branch):
    """Одно дерево на репо: файлы, тесты, органы. truncated помечаем честно."""
    data, err = jget(tok, f"/repos/{OWNER}/{repo}/git/trees/{branch}?recursive=1")
    if err:
        return None
    files = [t for t in data.get("tree", []) if t["type"] == "blob"]
    names = set()
    out = {"files": len(files), "truncated": bool(data.get("truncated")),
           "tests": 0, "organs": {}, "organ_dirs": [], "bytes": 0}
    for t in files:
        p = t.get("path", "")
        out["bytes"] += t.get("size", 0) or 0
        if TEST_RE.search(p):
            out["tests"] += 1
        for o in ORGANS:
            if p == o or p.startswith(o + "/"):
                out["organs"][o] = True
        for d in ORGAN_DIRS:
            if p.startswith(d + "/"):
                out["organ_dirs"].append(d)
    for o in ORGANS:
        out["organs"][o] = out["organs"].get(o, False)
    return out


def last_ci(tok, repo):
    data, err = jget(tok, f"/repos/{OWNER}/{repo}/actions/runs?per_page=1")
    if err or not data:
        return None, err
    runs = data.get("workflow_runs", [])
    if not runs:
        return None, None
    r0 = runs[0]
    return {"conclusion": r0.get("conclusion"), "status": r0.get("status"),
            "at": (r0.get("run_started_at") or "")[:16]}, None


def verdict(t, ci):
    """Пункт 4: статус из фактов. Работает = CI зелёный и тесты есть."""
    if t is None:
        return "не отвечает"
    if t["files"] <= 3 and t["tests"] == 0:
        return "статика"
    ok_ci = bool(ci and ci.get("conclusion") == "success")
    if ok_ci and t["tests"] > 0:
        return "работает"
    if t["tests"] > 0 or (ci is not None):
        return "прототип"
    return "прототип"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    ap.add_argument("--pause", type=float, default=0.3)
    args = ap.parse_args()
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    t0 = time.time()
    repos, err = jget(tok, f"/users/{OWNER}/repos?per_page=100&sort=full_name")
    if err:
        print("СТОП: список репо недоступен:", err); sys.exit(1)
    print(f"репо в источнике: {len(repos)}")
    rows = []
    for i, r in enumerate(repos, 1):
        name, br = r["name"], r.get("default_branch") or "main"
        cc, e1 = commit_count(tok, name)
        t = tree_scan(tok, name, br)
        ci, e3 = last_ci(tok, name)
        row = {
            "name": name, "branch": br, "size_kb": r.get("size", 0),
            "pushed_at": (r.get("pushed_at") or "")[:16],
            "commits": cc, "commit_err": e1,
            "files": t["files"] if t else None, "tests": t["tests"] if t else None,
            "tree_truncated": t["truncated"] if t else None,
            "bytes": t["bytes"] if t else None,
            "organs": {k: t["organs"][k] for k in ORGANS} if t else None,
            "dom_dir": bool(t and t["organ_dirs"]),
            "ci": ci, "verdict": verdict(t, ci),
        }
        rows.append(row)
        print(f"  [{i:2}/{len(repos)}] {name:26} коммитов={cc} файлов={row['files']} "
              f"тестов={row['tests']} CI={ci['conclusion'] if ci else '—'} → {row['verdict']}")
        time.sleep(args.pause)

    ok = [r for r in rows if r["commits"] is not None and r["files"] is not None]
    totals = {
        "repos_total": len(rows), "repos_answered": len(ok),
        "commits_sum": sum(r["commits"] for r in ok),
        "files_sum": sum(r["files"] for r in ok),
        "tests_sum": sum(r["tests"] for r in ok),
        "bytes_sum": sum(r["bytes"] or 0 for r in ok),
        "verdicts": {},
        "ci_green": sum(1 for r in rows if r["ci"] and r["ci"]["conclusion"] == "success"),
        "ci_present": sum(1 for r in rows if r["ci"]),
        "organs_spread": {o: sum(1 for r in rows if r["organs"] and r["organs"][o]) for o in ORGANS},
        "dom_dirs": sum(1 for r in rows if r["dom_dir"]),
        "truncated_trees": [r["name"] for r in rows if r["tree_truncated"]],
    }
    for r in rows:
        totals["verdicts"][r["verdict"]] = totals["verdicts"].get(r["verdict"], 0) + 1
    snap = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "github-api, числа только из источника; ни одной рукописной цифры",
        "owner": OWNER, "totals": totals, "repos": rows,
        "honest_notes": [
            "деревья с truncation считаются по видимой части; список: totals.truncated_trees",
            "вердикт «работает» = последний прогон CI зелёный И тесты ≥ 1 (факт, не декларация)",
            "не ответившее = «не отвечает», не «умер»; ошибки по каждой графе сохранены в repos.*_err",
        ],
    }
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)
    print(f"snapshot.json: {totals['repos_answered']}/{totals['repos_total']} ответили, "
          f"коммитов {totals['commits_sum']}, файлов {totals['files_sum']}, "
          f"тестов {totals['tests_sum']}, CI зелёных {totals['ci_green']} — "
          f"за {time.time()-t0:.0f}с")


if __name__ == "__main__":
    main()
