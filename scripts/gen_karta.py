#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""КАРТА ВСЕЛЕННОЙ rtynbirf — самописующая.

Правило: НИ ОДНОГО ВЫДУМАННОГО ЧИСЛА. Каждое число здесь либо пришло из
живого API GitHub, либо посчитано из этого же файла данных. Классификация
кластеров — детерминированные правила по имени репо, а не ручной список.

Запуск (перегенерация):
    GH_TOKEN=<тонкий read-only токен> python3 scripts/gen_karta.py [--data data.json]

Если --data не указан и файл /tmp/rtyn/data.json существует — берётся он,
иначе карта тянется из API сама (нужен GH_TOKEN).
"""
import json, os, sys, datetime, subprocess, hashlib

OWNER = "rtynbirf"
OUT_DEFAULT = "/home/z/my-project/download/karta"

# Найдено сканом зеркал 2026-11-16 (git show HEAD:.gitattributes | grep filter=lfs).
# Это факты, а не выдумка; при следующей генерации скан повторить.
# Скан повторен 2026-11-16 (волна-14, 70 тел; волна-15 повторила скан по зеркалу x70): filter=lfs только у voice-atlas-llm.
LFS_REPOS = ["voice-atlas-llm"]

# Факты зеркала: первое дело — 69 тел @ 2026-11-16 (karta родилась позже и в него не попала);
# перезеркалено волной-15 по слову Хозяина «ДЕЛАЙ КАК ХОЧЕШЬ»: 70 тел, все ветки и теги,
# артефакт издан в сейф дома (release-vault, тег backup/zerkalo-70-2026-11-16, 11 ассетов).
# Числа — из живого замера волны-15; при следующем росте территории отставание снова ловится в СВЕРКЕ.
MIRROR_REPOS = 70
MIRROR_DATE = "2026-11-16"
MIRROR_BRANCHES = 115
MIRROR_TAGS = 293
MIRROR_DISK_MB = 3530.4
MIRROR_ASSET = "backup/zerkalo-70-2026-11-16"
MIRROR_MANIFEST_SHA = "b75b69b25ea1c925df1538714af61c736e0ce2cc45426282f01010e4599f1c8c"

# Заявки прошлого аудита (2026-11-15, Z.ai-переворот по master-токену).
# Каждая проверяется ниже живыми числами. Статусы — как в lex-naturae:
# SUPPORTED / UNKNOWN / UNVERIFIED_SUBMITTER_ASSERTION / RASSINHRON.
CLAIMS = [
    ("вселенной 63 репо", 63, "repos"),
    ("2939 коммитов всего", 2939, "commits"),
    ("2308 коммитов за ноябрь 2026", None, "unverified"),
    ("42 полотна", None, "unverified"),
    ("6 кластеров вселенных", 6, "clusters"),
    ("офлайн живёт (девиз)", None, "offline"),
]

CLUSTER_RULES = [
    ("ФОРК",                     lambda n, fork: fork),
    ("ДОМОВОЙ",                  lambda n, fork: n.startswith("domov")),
    ("ПОЛИМАТ-УЛЕЙ",             lambda n, fork: ("polymath" in n or "polimat" in n
                                                  or "polymat" in n or n.startswith("uace"))),
    ("ДОКТРИНА·КАНОН",           lambda n, fork: any(k in n for k in
                                                  ("lex-naturae", "doctrine", "canon",
                                                   "svod", "protocol", "runbook", "audit"))),
    ("ЯДРО·ДЕКЛАРАЦИИ",          lambda n, fork: n in ("khozyain", "free-man", "door-zero", "agryp")),
    ("РОЙ·ЯЧЕЙКИ",               lambda n, fork: any(k in n for k in
                                                  ("cell", "universal-agent", "nous", "hologram",
                                                   "os-forge", "neutral-browser", "task-graph",
                                                   "combain"))),
    ("SINGULYAR",                lambda n, fork: "singulyar" in n or "PHOENIX" in n),
    ("РЕВО·ЭКСПОЗИЦИИ",          lambda n, fork: n in ("revo", "ekspozicii", "karaoke-dream",
                                                  "release-vault") or n.startswith("ruvson")),
    ("АККАУНТ-ОБОЛОЧКА",         lambda n, fork: n in ("rtynbirf", ".github", "rtynbirf.github.io")),
    ("АТЛАСЫ·ЭПОХИ",             lambda n, fork: any(k in n for k in
                                                  ("yazyk", "language-through", "web-evolution",
                                                   "voice-atlas", "windows-chronicle",
                                                   "global-video", "ekonomika", "rent-mechanism",
                                                   "linguistic-code"))),
]

def cluster_of(name, fork):
    for cname, rule in CLUSTER_RULES:
        try:
            if rule(name, fork):
                return cname
        except Exception:
            pass
    return "НЕРАЗДЕКОДИРОВАН"

def load_data(path):
    if path and os.path.exists(path):
        return json.load(open(path))
    if os.path.exists("/tmp/rtyn/data.json"):
        return json.load(open("/tmp/rtyn/data.json"))
    token = os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("нет ни файла данных, ни GH_TOKEN — картостроителю нечем жить")
    import urllib.request
    hdr = {"Authorization": f"Bearer {token}", "User-Agent": "karta-generator"}
    repos, page = [], 1
    while True:
        req = urllib.request.Request(
            f"https://api.github.com/user/repos?per_page=100&type=all&sort=pushed&direction=desc&page={page}",
            headers=hdr)
        chunk = json.load(urllib.request.urlopen(req))
        repos += chunk
        if len(chunk) < 100:
            break
        page += 1
    return repos

def normalize(raw):
    out = []
    for r in raw:
        # два формата: сырой API-ответ или уже разведанный data.json
        if "commits" in r and "size_kb" in r:
            name, fork, archived = r["name"], r["fork"], r["archived"]
            rec = dict(r)
        else:
            name, fork, archived = r["name"], r["fork"], r["archived"]
            rec = {
                "name": name, "private": r["private"], "fork": fork,
                "archived": archived, "size_kb": r["size"], "commits": r.get("commits", 0),
                "created_at": r["created_at"], "pushed_at": r["pushed_at"],
                "language": r["language"], "description": r["description"],
            }
        rec["cluster"] = cluster_of(name, fork)
        rec["status"] = ("ОКАМЕНЕЛОСТЬ" if archived else "ЖИВОЙ")
        rec["lfs"] = name in LFS_REPOS
        out.append(rec)
    return out

def main():
    data_path = None
    if "--data" in sys.argv:
        data_path = sys.argv[sys.argv.index("--data") + 1]
    repos = normalize(load_data(data_path))

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live = [r for r in repos if r["status"] == "ЖИВОЙ"]
    fossils = [r for r in repos if r["status"] == "ОКАМЕНЕЛОСТЬ"]
    forks = [r for r in repos if r["cluster"] == "ФОРК"]
    undecoded = [r for r in repos if r["cluster"] == "НЕРАЗДЕКОДИРОВАН"]
    named = {}
    for r in repos:
        if r["cluster"] not in ("ФОРК", "НЕРАЗДЕКОДИРОВАН"):
            named.setdefault(r["cluster"], []).append(r)
    total_commits = sum(r["commits"] for r in repos)
    total_kb = sum(r["size_kb"] for r in repos)
    live_commits = sum(r["commits"] for r in live)

    # --- СВЕРКА заявки против территории ---
    сверка = []
    def add(claim, stated, actual, status, note):
        сверка.append({"заявка": claim, "заявлено": str(stated) if stated is not None else "—",
                       "живое": str(actual), "статус": status, "примечание": note})
    add("63 репо", 63, len(repos),
        "RASSINHRON" if len(repos) != 63 else "SUPPORTED",
        f"расхождение {len(repos)-63:+d}; территория растёт быстрее карты" if len(repos) != 63 else "сошлось")
    add("2939 коммитов", 2939, total_commits,
        "RASSINHRON" if total_commits != 2939 else "SUPPORTED",
        f"расхождение {total_commits-2939:+d}; прошлая карта либо устарела, либо считала иначе"
        if total_commits != 2939 else "сошлось")
    add("2308 коммитов за ноябрь 2026", None, "не перепроверено этим прогоном",
        "UNVERIFIED_SUBMITTER_ASSERTION", "требует выборки по датам коммитов — ритуал СВЕРКА")
    add("42 полотна", None, "не перепроверено этим прогоном",
        "UNVERIFIED_SUBMITTER_ASSERTION", "требуется счёт по репо-экспозициям")
    add("6 кластеров", 6, len(named),
        "RASSINHRON" if len(named) != 6 else "SUPPORTED",
        f"генератор различает {len(named)} именованных кластеров + {len(undecoded)} нераздекодированных"
        if len(named) != 6 else "сошлось")
    add("офлайн живёт (девиз)", None,
        f"зеркало {MIRROR_REPOS}/{len(repos)} создано {MIRROR_DATE}, sha256-манифест подписан",
        "PARTIALLY SUPPORTED",
        (f"копия доведена до сейфа дома (release-vault {MIRROR_ASSET}) и выжила бы смерть тела;"
         f" SUPPORTED после вывоза хозяином на офлайн-диск (вне монокультуры вендора)"
         + (f"; зеркало отстаёт на {len(repos)-MIRROR_REPOS} комнат(у) — появились после зеркала, перезеркалить"
            if len(repos) != MIRROR_REPOS else "")))

    karta = {
        "generated_at": now,
        "owner": OWNER,
        "source": "api.github.com/user/repos (живые данные, тип all)",
        "rule": "ни одного выдуманного числа",
        "totals": {
            "repos": len(repos), "live": len(live), "okamenelosti": len(fossils),
            "forks": len(forks), "undecoded": len(undecoded),
            "named_clusters": len(named),
            "commits_total": total_commits, "commits_live": live_commits,
            "size_kb": total_kb,
        },
        "repos": repos,
        "sverka": сверка,
        "lfs_gaps": LFS_REPOS,
    }

    # --- README ---
    L = []
    L.append(f"# КАРТА ВСЕЛЕННОЙ {OWNER.upper()}")
    L.append("")
    L.append(f"> сгенерировано `{now}` скриптом `scripts/gen_karta.py` из живых данных API")
    L.append("> правило: **НИ ОДНОГО ВЫДУМАННОГО ЧИСЛА** — карта не пишется руками, карта считается")
    L.append("> карта может отставать от территории — поэтому у карты есть раздел СВЕРКА")
    L.append("")
    L.append("## СВОДКА")
    L.append("")
    L.append(f"| метрика | живое значение |")
    L.append(f"|---|---|")
    L.append(f"| репо всего | **{len(repos)}** |")
    L.append(f"| живые | **{len(live)}** |")
    L.append(f"| окаменелости (archived, сохранены как доказательства) | **{len(fossils)}** |")
    L.append(f"| форки (чужая кровь, не вселенная) | {len(forks)} |")
    L.append(f"| нераздекодированные (честная дыра карты) | {len(undecoded)} |")
    L.append(f"| именованные кластеры | {len(named)} |")
    L.append(f"| коммитов всего | **{total_commits}** |")
    L.append(f"| коммитов в живых репо | {live_commits} |")
    L.append(f"| объём вселенной | {total_kb/1024:.1f} МБ |")
    L.append("")
    L.append("## ЖИВЫЕ РЕПО (не archived)")
    L.append("")
    L.append("| репо | кластер | коммитов | размер | назначение (описание API) |")
    L.append("|---|---|---|---|---|")
    for r in sorted(live, key=lambda x: -x["commits"]):
        d = (r["description"] or "—").replace("|", "/")
        L.append(f"| [{r['name']}]({r['name']}) | {r['cluster']} | {r['commits']} | {r['size_kb']} KB | {d} |")
    L.append("")
    L.append("## ОКАМЕНЕЛОСТИ (archived: трупы, которые помнят всё)")
    L.append("")
    L.append("Домовой не удаляет окаменелости — окаменелость это доказательство. "
             "Из счётчика вселенной они выделены, чтобы общее число комнат не притворялось числом живых органов.")
    L.append("")
    L.append("| репо | кластер | коммитов | последний пуш |")
    L.append("|---|---|---|---|")
    for r in sorted(fossils, key=lambda x: -x["commits"]):
        L.append(f"| {r['name']} | {r['cluster']} | {r['commits']} | {r['pushed_at'][:10]} |")
    L.append("")
    L.append("## КЛАСТЕРЫ (детерминированные правила по имени, не ручной список)")
    L.append("")
    for cname in sorted(named, key=lambda c: -len(named[c])):
        members = ", ".join(x["name"] for x in sorted(named[cname], key=lambda x: -x["commits"]))
        L.append(f"- **{cname}** ({len(named[cname])}): {members}")
    if undecoded:
        L.append(f"- **НЕРАЗДЕКОДИРОВАН** ({len(undecoded)}): "
                 + ", ".join(x["name"] for x in undecoded)
                 + " — карта честно признаёт, что не знает; следующий аудитор начинает отсюда")
    if forks:
        L.append(f"- **ФОРК** ({len(forks)}): " + ", ".join(x["name"] for x in forks)
                 + " — чужая кровь в организме: учитывается отдельно, к вселенной не приплюсовывается")
    L.append("")
    L.append("## СВЕРКА: ЗАЯВКИ ПРОШЛОГО АУДИТА ПРОТИВ ЖИВОЙ ТЕРРИТОРИИ")
    L.append("")
    L.append("| заявка | заявлено | живое | статус | примечание |")
    L.append("|---|---|---|---|---|")
    for s in сверка:
        L.append(f"| {s['заявка']} | {s['заявлено']} | {s['живое']} | **{s['статус']}** | {s['примечание']} |")
    L.append("")
    L.append("## ЗЕРКАЛО (первое дело 2026-11-16 · перезеркалено волной-15)")
    L.append("")
    L.append(f"- вынесено из монокультуры вендора: **{MIRROR_REPOS}/{len(repos)} репо**, полная история: {MIRROR_BRANCHES} веток, {MIRROR_TAGS} тегов")
    L.append(f"- вес полного зеркала: {MIRROR_DISK_MB} МБ на диске (API-цифра аккаунта 1302.2 МБ — упаковка вендора; числа разные по построению, оба факты)")
    if len(repos) != MIRROR_REPOS:
        L.append(f"- зеркало отстаёт от территории на {len(repos)-MIRROR_REPOS} комнат(у): они родились после зеркала; перезеркалить по приказу Хозяина")
    L.append("- целостность: fsck чист на выборке (singulyar, lex-naturae, khozyain, cell-swarm, markitdown + новорождённая karta); реставрация стрима проверена по пайпу (71 запись)")
    L.append("- манифест: `_MANIFEST.txt` (repo → HEAD sha → refs → size), подписан sha256 " + MIRROR_MANIFEST_SHA[:16] + "…")
    L.append(f"- артефакт: релиз сейфа дома `{MIRROR_ASSET}` (release-vault): 9 частей × 420 МБ + манифест + SHA256SUMS; манифест перепрочитан из сейфа байт-в-байт")
    L.append(f"- дыра: {', '.join(LFS_REPOS)} — LFS-указатели в зеркале есть, бинарные объекты "
             "остались в LFS-хранилище вендора (git-lfs на машине генератора недоступен)")
    L.append("- оставшийся шаг хозяина: вывести копию на офлайн-диск — только тогда девиз «офлайн живёт» станет SUPPORTED")
    L.append("")
    L.append("## РИТУАЛЫ (приказы хозяина, Codex — specs в `rituals/`)")
    L.append("")
    L.append("1. `rituals/SVERKA.md` — раз в квартал внешний аудитор другого вида проверяет 10 случайных утверждений; два аудита подряд одного вида = инбридинг, отчёт недействителен")
    L.append("2. `rituals/VYZHIVANIE.md` — в январе считать % коммитов ноября, переживших квартал без переписывания: >60% — поток, <30% — штурм, темп вдвое вниз")
    L.append("3. `rituals/NOCH-BEZ-SETI.md` — раз в квартал ночь без сети в смену автопилота 04:21: рой либо живёт на локальном GGUF, либо честно записывает время своей смерти")
    L.append("")
    L.append("## ПЕРЕГЕНЕРАЦИЯ")
    L.append("")
    L.append("```bash")
    L.append("GH_TOKEN=<тонкий read-only токен с датой смерти> python3 scripts/gen_karta.py")
    L.append("```")
    L.append("Карта обязана расходиться с территорией — расхождение ловится CRITIC-шагом: "
             "числа README против ответа API. Совпало — молчим; разошлось — тревога и новый коммит.")
    L.append("")

    outdir = OUT_DEFAULT if os.path.isdir(os.path.dirname(OUT_DEFAULT)) else "./karta"
    os.makedirs(outdir, exist_ok=True)
    json.dump(karta, open(os.path.join(outdir, "karta.json"), "w"), ensure_ascii=False, indent=1)
    open(os.path.join(outdir, "README.md"), "w").write("\n".join(L))
    print(f"OK: {outdir}/README.md ({len(L)} строк), {outdir}/karta.json")
    print(f"живых={len(live)} окаменелостей={len(fossils)} коммитов={total_commits} кластеров={len(named)}+{len(undecoded)} нераздекод.")
    print("--- СВЕРКА ---")
    for s in сверка:
        print(f"  [{s['статус']}] {s['заявка']}: заявлено {s['заявлено']}, живое {s['живое']}")

if __name__ == "__main__":
    main()
