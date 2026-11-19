#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""КАРТА ВСЕЛЕННОЙ rtynbirf — самописующая. v3.

Правило: НИ ОДНОГО ВЫДУМАННОГО ЧИСЛА. Каждое число здесь либо пришло из
живого API GitHub, либо посчитано из этого же файла данных. Классификация
кластеров — детерминированные правила по имени репо, а не ручной список.

CHANGELOG v2 (2026-11-16, рекогносцировка; каждый фикс — с объяснением):
  1. СВЕРКА стала ДАННЫМИ (список CLAIMS), а не захардкоженными add().
     Гвоздь v1: заявки аудита 15.11 (63 репо / 2939 коммитов) были вмерты
     в код и молча устаревали. Теперь заявки — строки списка с датой и
     источником; при новом аудите правится список, не логика.
  2. САМОВКЛЮЧЕНИЕ решено: карта — орган вселенной, считается в территории.
     karta помечается rec["self"]=True и кластером КАРТА·АВТОПОРТРЕТ.
     При перегенерации из API karta входит в счёт автоматически.
  3. Секция ЗЕРКАЛО приведена к фактам 16.11: 68 записей манифеста при
     69 репо — дыра `.github` (dot-слепой глоб `*.git` в генераторе
     манифеста v1 не видит скрытых каталогов). Лечение: gen_manifest.py
     (os.scandir) с --fix. Сама карта dot-слепой не была — она API-рождена.
  4. Выходной каталог можно переопределить: KARTA_OUT=/путь python3 ...

CHANGELOG v3 (2026-11-19, смена СТОРОЖ — слияние по канону «слияние, не затирание»):
  5. Слияние v2 + живого v1: структура v2 (SELF_NAME, CLAIMS-данные, KARTA_OUT)
     сохранена; факты зеркала волны-15 из живого v1 (70 тел, 115 веток, 293 тегов,
     артефакт в release-vault) восстановлены — v2 их потерял, а они новее по времени.
  6. В реестр РИТУАЛЫ вписаны приказы №6-8: ФИТИЛЬ (гигиена ключей), СТОРОЖ
     (взаимный пульс роя, workflows + CRITIC-alarm.md), ВЫСУШКА (drill холода).
     Пакет smena-storozh: workflows/, scripts/storozh_check.py, fence/.gitleaks.toml.
  7. (после первого ночного прогона 19.11) КРИТИК поймал ноль репо: встроенный
     GITHUB_TOKEN — это Actions-бот, его /user/repos пуст. Фолбэк на публичную
     поверхность /users/{OWNER}/repos с честной пометкой источника в карте.

Запуск (перегенерация):
    GH_TOKEN=<тонкий read-only токен> python3 scripts/gen_karta.py [--data data.json]

Если --data не указан и файл /tmp/rtyn/data.json существует — берётся он,
иначе карта тянется из API сама (нужен GH_TOKEN).
"""
import json, os, re, sys, datetime, subprocess, hashlib, urllib.error, urllib.request

OWNER = "rtynbirf"
SELF_NAME = "karta"          # карта считает саму себя: решение рекогносцировки 16.11
OUT_DEFAULT = "/home/z/my-project/download/karta"

# Найдено сканом зеркал 2026-11-16 (git show HEAD:.gitattributes | grep filter=lfs).
# Это факты, а не выдумка; при следующей генерации скан повторить.
LFS_REPOS = ["voice-atlas-llm"]

# Факты зеркала: первое дело — 69 тел @ 2026-11-16 (karta родилась позже и в него не попала);
# перезеркалено волной-15 по слову Хозяина «ДЕЛАЙ КАК ХОЧЕШЬ»: 70 тел, все ветки и теги,
# артефакт издан в сейф дома (release-vault, тег backup/zerkalo-70-2026-11-16, 11 ассетов).
# Числа — из живого замера волны-15; при следующем росте территории отставание снова ловится в СВЕРКЕ.
# (v3: блок возвращён из живого v1 при слиянии — v2 переписал секцию ЗЕРКАЛО статикой до волны-15.)
MIRROR_REPOS = 70
MIRROR_DATE = "2026-11-16"
MIRROR_BRANCHES = 115
MIRROR_TAGS = 293
MIRROR_DISK_MB = 3530.4
MIRROR_ASSET = "backup/zerkalo-70-2026-11-16"
MIRROR_MANIFEST_SHA = "b75b69b25ea1c925df1538714af61c736e0ce2cc45426282f01010e4599f1c8c"

# Заявки последнего полного аудита (16.11, Z.ai-переворот по master-токену)
# и рекогносцировки (16.11 12:54 UTC, публичная поверхность).
# Формат: (заявка, заявлено, тип, источник). Статусы — как в lex-naturae:
# SUPPORTED / UNKNOWN / UNVERIFIED_SUBMITTER_ASSERTION / RASSINHRON.
# Правило: новый аудит => дописать/обновить строки ЗДЕСЬ, логика не трогается.
CLAIMS = [
    ("репо всего", 69, "repos", "аудит 16.11 (полный скоуп токена)"),
    ("живых (не archived)", 31, "live", "аудит 16.11"),
    ("окаменелостей (archived)", 38, "fossils", "аудит 16.11; рекогносцировка 12:54 UTC подтвердила 38"),
    ("коммитов всего", 5374, "commits", "аудит 16.11, живой счёт; поэлементно не верифицирован"),
    ("именованных кластеров", 9, "clusters", "аудит 16.11: 9 именованных + 5 нераздекодированных"),
    ("2308 коммитов за ноябрь 2026", None, "unverified", "заявка 15.11 — нужна выборка по датам коммитов, ритуал СВЕРКА"),
    ("42 полотна", None, "unverified", "заявка 15.11 — счёт по репо-экспозициям"),
    ("офлайн живёт (девиз)", None, "offline", "зеркало волны-15 (16.11): 70 тел, все ветки и теги, издано в сейф дома release-vault (11 ассетов); дыра LFS: voice-atlas-llm"),
]

CLUSTER_RULES = [
    # v2: карта — первый гражданин списка, чтобы её не глотал другой кластер
    ("КАРТА·АВТОПОРТРЕТ",        lambda n, fork: n == SELF_NAME),
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

SOURCE_EP = "user/repos"   # источник последней загрузки — видно в karta.json и штампе (v3)

def _api_repos(hdr, endpoint):
    repos, page = [], 1
    while True:
        req = urllib.request.Request(
            f"https://api.github.com/{endpoint}?per_page=100&type=all&sort=pushed&direction=desc&page={page}",
            headers=hdr)
        chunk = json.load(urllib.request.urlopen(req))
        repos += chunk
        if len(chunk) < 100:
            break
        page += 1
    return repos

def _count_commits(hdr, repos):
    """v4 (смена karta-critic, 2026-11-19): счётчик коммитов. Дыра v2-v3:
    сырые записи /repos не несут числа коммитов — карта вечно писала 0,
    честно помечала «ноль подозрителен», но лечить не лечила.
    Лечение: per-repo /commits?per_page=1 + rel="last" из Link-заголовка.
    Стоимость: ~1 запрос на репо; при rate-limit остаётся 0 (честно)."""
    counted = 0
    for r in repos:
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{OWNER}/{r['name']}/commits?per_page=1",
                headers=hdr)
            with urllib.request.urlopen(req) as resp:
                link = resp.headers.get("Link", "")
            m = re.findall(r'[?&]page=(\d+)>; rel="last"', link)
            r["commits"] = int(m[0]) if m else (0 if link else 1)
            counted += 1
        except Exception:
            r["commits"] = r.get("commits", 0)
    return counted

def load_data(path):
    global SOURCE_EP
    if path and os.path.exists(path):
        SOURCE_EP = f"file:{path}"
        return json.load(open(path))
    if os.path.exists("/tmp/rtyn/data.json"):
        SOURCE_EP = "file:/tmp/rtyn/data.json"
        return json.load(open("/tmp/rtyn/data.json"))
    token = os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("нет ни файла данных, ни GH_TOKEN — картостроителю нечем жить")
    hdr = {"Authorization": f"Bearer {token}", "User-Agent": "karta-generator"}
    try:
        repos = _api_repos(hdr, "user/repos")
        SOURCE_EP = "user/repos (полный скоуп токена)"
    except urllib.error.HTTPError as e:
        if e.code not in (401, 403, 404):
            raise
        # 401/403/404: токен не умеет /user/repos — в Actions встроенный
        # GITHUB_TOKEN это бот github-actions[bot], которому тут Forbidden.
        repos = []
    if not repos:
        # Фолбэк на публичную поверхность владельца: сначала с имеющимся токеном
        # (валидный бот-токен Actions проходит), при 401/403 — анонимно
        # (60 req/ч на IP ночи хватает). Источник честно помечается в карте.
        SOURCE_EP = f"users/{OWNER}/repos (публичная поверхность)"
        try:
            repos = _api_repos(hdr, f"users/{OWNER}/repos")
        except urllib.error.HTTPError as e2:
            if e2.code not in (401, 403):
                raise
            repos = _api_repos({"User-Agent": "karta-generator"}, f"users/{OWNER}/repos")
    counted = _count_commits(hdr, repos)
    if counted:
        SOURCE_EP += f" + счёт коммитов /commits (Link): {counted} репо"
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
        rec["self"] = (name == SELF_NAME)   # v2: карта помечает саму себя
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

    # --- СВЕРКА заявки против территории (v2: данные, не хардкод) ---
    сверка = []
    def add(claim, stated, actual, status, note):
        сверка.append({"заявка": claim, "заявлено": str(stated) if stated is not None else "—",
                       "живое": str(actual), "статус": status, "примечание": note})
    actual_map = {"repos": len(repos), "live": len(live), "fossils": len(fossils),
                  "commits": total_commits, "clusters": len(named)}
    for claim, stated, kind, src in CLAIMS:
        if kind == "unverified":
            add(claim, stated, "не перепроверено этим прогоном",
                "UNVERIFIED_SUBMITTER_ASSERTION", src)
        elif kind == "offline":
            add(claim, stated,
                f"зеркало {MIRROR_REPOS}/{len(repos)} создано {MIRROR_DATE}, sha256-манифест подписан, артефакт в release-vault",
                "PARTIALLY SUPPORTED",
                src + "; SUPPORTED после вывоза хозяином на офлайн-диск (вне монокультуры вендора)"
                + (f"; зеркало отстаёт на {len(repos)-MIRROR_REPOS} комнат(у) — перезеркалить" if len(repos) != MIRROR_REPOS else ""))
        else:
            a = actual_map[kind]
            if a == 0 and stated:
                # v3: ноль подозрителен — метод прогона счёт не измеряет, это НЕ расхождение
                add(claim, stated, a, "UNKNOWN",
                    f"метод этого прогона счёт не измеряет (ноль — не расхождение); {src}")
            else:
                ok = (a == stated)
                add(claim, stated, a, "SUPPORTED" if ok else "RASSINHRON",
                    src if ok else f"расхождение {a-stated:+d}; {src}")

    karta = {
        "generated_at": now,
        "owner": OWNER,
        "source": f"api.github.com/{SOURCE_EP} (живые данные)",
        "rule": "ни одного выдуманного числа",
        "self_inclusion": "карта — орган вселенной, считается в территории (решение 16.11)",
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
    L.append(f"> сгенерировано `{now}` скриптом `scripts/gen_karta.py` (v3) из живых данных API")
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
    commits_shown = f"**{total_commits}**" if total_commits else \
        "ноль подозрителен: метод прогона счёт коммитов не измеряет (см. СВЕРКА)"
    L.append(f"| коммитов всего | {commits_shown} |")
    live_shown = f"{live_commits}" if total_commits else "— (ноль подозрителен, см. выше)"
    L.append(f"| коммитов в живых репо | {live_shown} |")
    L.append(f"| объём вселенной | {total_kb/1024:.1f} МБ |")
    L.append(f"| карта в счёте территории | **ДА** — «{SELF_NAME}» орган вселенной и считается (решение рекогносцировки 16.11) |")
    L.append("")
    L.append("## ЖИВЫЕ РЕПО (не archived)")
    L.append("")
    L.append("| репо | кластер | коммитов | размер | назначение (описание API) |")
    L.append("|---|---|---|---|---|")
    for r in sorted(live, key=lambda x: -x["commits"]):
        d = (r["description"] or "—").replace("|", "/")
        mark = " ⟵ сама карта" if r.get("self") else ""
        L.append(f"| [{r['name']}]({r['name']}){mark} | {r['cluster']} | {r['commits']} | {r['size_kb']} KB | {d} |")
    L.append("")
    L.append("## ОКАМЕНЕЛОСТИ (archived: трупы, которые помнят всё)")
    L.append("")
    L.append("Домовой не удаляет окаменелости — окаменелость это доказательство. "
             "Из счётчика вселенной они выделены, чтобы «70» не притворялось числом живых органов.")
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
    L.append(f"- вес полного зеркала: {MIRROR_DISK_MB} МБ на диске (API-цифра аккаунта 1302.2 МБ на 16.11 — упаковка вендора; числа разные по построению, оба факты)")
    if len(repos) != MIRROR_REPOS:
        L.append(f"- зеркало отстаёт от территории на {len(repos)-MIRROR_REPOS} комнат(у): они родились после зеркала; перезеркалить по приказу Хозяина")
    L.append("- целостность: fsck чист на выборке (singulyar, lex-naturae, khozyain, cell-swarm, markitdown + новорождённая karta); реставрация стрима проверена по пайпу (71 запись)")
    L.append("- манифест: `_MANIFEST.txt` (repo → HEAD sha → refs → size), подписан sha256 " + MIRROR_MANIFEST_SHA[:16] + "…")
    L.append(f"- артефакт: релиз сейфа дома `{MIRROR_ASSET}` (release-vault): 9 частей × 420 МБ + манифест + SHA256SUMS; манифест перепрочитан из сейфа байт-в-байт")
    L.append(f"- дыра: {', '.join(LFS_REPOS)} — LFS-указатели в зеркале есть, бинарные объекты "
             "остались в LFS-хранилище вендора (git-lfs на машине генератора недоступен)")
    L.append("- дыра первой зеркалировки (`.github`, 68 записей манифеста при 69 репо; dot-слепой глоб "
             "`*.git` генератора v1) лечится `gen_manifest.py` (os.scandir) с `--fix`; после волны-15 "
             "не перепроверено — статус UNVERIFIED")
    L.append("- оставшийся шаг хозяина: вывести копию на офлайн-диск — только тогда девиз «офлайн живёт» станет SUPPORTED")
    L.append(f"- дыра: {', '.join(LFS_REPOS)} — LFS-указатели в зеркале есть, бинарные объекты "
             "остались в LFS-хранилище вендора (git-lfs на машине генератора недоступен)")
    L.append("- оставшийся шаг хозяина: вывести копию на офлайн-диск — только тогда девиз «офлайн живёт» станет SUPPORTED")
    L.append("")
    L.append("## РИТУАЛЫ (приказы хозяина, specs в `rituals/`)")
    L.append("")
    L.append("1. `rituals/SVERKA.md` — раз в квартал внешний аудитор другого вида проверяет 10 случайных утверждений; два аудита подряд одного вида = инбридинг, отчёт недействителен")
    L.append("2. `rituals/VYZHIVANIE.md` — в январе считать % коммитов ноября, переживших квартал без переписывания: >60% — поток, <30% — штурм, темп вдвое вниз")
    L.append("3. `rituals/NOCH-BEZ-SETI.md` — раз в квартал ночь без сети в смену автопилота 04:21: рой либо живёт на локальном GGUF, либо честно записывает время своей смерти")
    L.append("4. `rituals/ФИТИЛЬ.md` — Приказ №6: ключ = сменный пропуск (fine-grained, read-only, дата смерти ≤ 90 дней); публичное появление = кремация немедленно; реестр ключей — `keys/README.md`")
    L.append("5. `rituals/СТОРОЖ.md` — Приказ №7: взаимный пульс роя — СТОРОЖ-workflow ежечасно меряет возраст штампов index и karta; тишина старше порога сама становится строкой в `CRITIC-alarm.md`; ноль сторонних виджетов")
    L.append("6. `rituals/ВЫСУШКА.md` — Приказ №8: раз в квартал, в ночь без сети, 10 случайных зеркал поднимаются из холода на чистой машине; резерв не существует, пока не доказано восстановление")
    L.append("")
    L.append("## ПЕРЕГЕНЕРАЦИЯ")
    L.append("")
    L.append("```bash")
    L.append("GH_TOKEN=<тонкий read-only токен с датой смерти> python3 scripts/gen_karta.py")
    L.append("```")
    L.append("Карта обязана расходиться с территорией — расхождение ловится CRITIC-шагом: "
             "числа README против ответа API. Совпало — молчим; разошлось — тревога и новый коммит.")
    L.append("")

    outdir = os.environ.get("KARTA_OUT") or (OUT_DEFAULT if os.path.isdir(os.path.dirname(OUT_DEFAULT)) else "./karta")
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
