#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ДВИЖОК ВЫЖИВАНИЯ (анти-DORA): сколько квартальных коммитов пережили окно
без переписывания смысла.

Мировой тренд (DORA) меряет СКОРОСТЬ поставки. Этот движок меряет распад СМЫСЛА:
коммит выжил, если ни один путь, который он трогал, не был переписан после конца окна.
> 60% — поток · 30–60% — переходная зона · < 30% — штурм, темп вдвое вниз.

Источники репо:
  --mirror-dir DIR   готовые голые зеркала (локально)
  --clone            клонировать с GitHub (в Actions), --filter=blob:none
Список живых репо — из karta/karta.json (данные, не выдумка).
"""
import json, os, subprocess, argparse, datetime, shutil

def sh(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}: {r.stderr[:200]}")
    return r.stdout

def last_touch(repo_path):
    out = sh(["git", "log", "--format=%ad", "--name-only", "--date=short"], cwd=repo_path)
    last, date = {}, None
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if len(line) == 10 and line[4] == "-" and line[7] == "-":
            date = line
        elif date:
            if line not in last or date > last[line]:
                last[line] = date
    return last

def window_commits(repo_path, ws, we):
    out = sh(["git", "log", "--since=" + ws, "--until=" + we + "T23:59:59",
              "--format=%H", "--name-only"], cwd=repo_path)
    commits, cur = [], None
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if len(line) == 40 and all(c in "0123456789abcdef" for c in line):
            if cur:
                commits.append(cur)
            cur = {"sha": line[:10], "paths": []}
        elif cur is not None:
            cur["paths"].append(line)
    if cur:
        commits.append(cur)
    return commits

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--mirror-dir")
    ap.add_argument("--clone", action="store_true")
    ap.add_argument("--window-start", required=True)
    ap.add_argument("--window-end", required=True)
    ap.add_argument("--check-date", required=True)
    ap.add_argument("--label", default=None)
    ap.add_argument("--workdir", default="/tmp/vyzhivanie")
    a = ap.parse_args()

    root = os.path.abspath(a.root)
    # раскладка v3 репо: karta.json в корне; поддержка старой раскладки karta/karta.json
    kj = os.path.join(root, "karta.json")
    if not os.path.exists(kj):
        kj = os.path.join(root, "karta", "karta.json")
    data = json.load(open(kj))
    live_names = [r["name"] for r in data["repos"] if r["status"] == "ЖИВОЙ" and r["cluster"] != "ФОРК"]

    ws, we, cd = a.window_start, a.window_end, a.check_date
    we_dt = datetime.date.fromisoformat(we)
    cd_dt = datetime.date.fromisoformat(cd)
    pilot = (cd_dt - we_dt).days < 30

    tmp = os.path.join(a.workdir, "repos")
    os.makedirs(tmp, exist_ok=True)
    rows, tot_in, tot_surv = [], 0, 0
    for name in live_names:
        if a.mirror_dir:
            repo_path = os.path.join(a.mirror_dir, name + ".git")
            if not os.path.isdir(repo_path):
                rows.append({"repo": name, "err": "нет зеркала"})
                continue
        else:
            repo_path = os.path.join(tmp, name)
            if not os.path.isdir(repo_path):
                subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--single-branch",
                                f"https://github.com/rtynbirf/{name}.git", repo_path],
                               capture_output=True, text=True)
                if not os.path.isdir(repo_path):
                    rows.append({"repo": name, "err": "клон не удался"})
                    continue
        try:
            lt = last_touch(repo_path)
            wc = window_commits(repo_path, ws, we)
            surv = sum(1 for c in wc if not any(lt.get(p, "0000-00-00") > we for p in c["paths"]))
            pct = round(100.0 * surv / len(wc), 1) if wc else None
            rows.append({"repo": name, "commits_in_window": len(wc), "survived": surv,
                         "died": len(wc) - surv, "survival_pct": pct})
            tot_in += len(wc)
            tot_surv += surv
        except Exception as e:
            rows.append({"repo": name, "err": str(e)[:120]})

    if tot_in:
        tot_pct = round(100.0 * tot_surv / tot_in, 1)
        verdict = ("ПОТОК (>60%): темп не трогать" if tot_pct > 60 else
                   "ШТУРМ (<30%): темп вдвое вниз" if tot_pct < 30 else
                   "ПЕРЕХОДНАЯ ЗОНА: смотреть в глаза каждой смерти")
    else:
        tot_pct, verdict = None, "в окне нет коммитов"

    label = a.label or (ws[:4] + "-Q" + str((datetime.date.fromisoformat(ws).month - 1) // 3 + 1))
    os.makedirs(os.path.join(root, "karta", "vyzhivanie"), exist_ok=True)
    outp = os.path.join(root, "karta", "vyzhivanie", label + ".md")
    L = [f"# ВЫЖИВАНИЕ {label}", "",
         f"окно: {ws} … {we} · проверка на дату: {cd} · движок: `scripts/vyzhivanie.py`",
         "метод: коммит выжил ⇔ ни один путь, который он трогал, не переписан после конца окна",
         ""]
    if pilot:
        L.append(f"> **ПИЛОТ**: окно закрыто {(cd_dt - we_dt).days} дн. назад (<30 дн.) — цифры предварительные, "
                 "полный диагноз даст январский прогон (rituals/VYZHIVANIE.md)")
        L.append("")
    L.append(f"**итог: коммитов в окне {tot_in} · выжило {tot_surv} · {tot_pct}% · вердикт: {verdict}**")
    L.append("")
    L.append("мировой тренд DORA меряет скорость поставки; эта метрика — обратная ей: распад смысла.")
    L.append("")
    L.append("| репо | коммитов в окне | выжило | умерло | выживание |")
    L.append("|---|---|---|---|---|")
    for r in sorted([x for x in rows if "err" not in x], key=lambda x: -(x["commits_in_window"] or 0)):
        L.append(f"| {r['repo']} | {r['commits_in_window']} | {r['survived']} | {r['died']} | {r['survival_pct']}% |")
    errs = [x for x in rows if "err" in x]
    if errs:
        L.append("")
        L.append("честные ошибки прогона: " + "; ".join(f"{x['repo']}: {x['err']}" for x in errs))
    open(outp, "w").write("\n".join(L) + "\n")
    print(f"OK: {outp}")
    print(f"TOTAL: in_window={tot_in} survived={tot_surv} pct={tot_pct} verdict={verdict}")
    if a.clone:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    main()
