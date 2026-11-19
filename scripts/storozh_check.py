#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""СТОРОЖ вселенной rtynbirf — взаимный пульс органов. v1 (2026-11-19, пакет smena-storozh).

Мир: dead man's switch — GitHub не алертит падение schedule-воркфлоу,
задержки джиттера и «успех с нулём записей» проходят молча.
Эмерджентное: вместо внешнего SaaS-пингера органы роя меряют пульс друг друга
(karta слушает index, karta следит и за собой). Ноль сторонних виджетов — Autonomy.

Проверки:
  1. Возраст штампа index/STATUS.md («Пересчитано автоматом: ... UTC»)  — порог --max-age-hours
  2. Возраст штампа karta/README.md («сгенерировано ...Z»)              — порог --karta-max-hours
  3. Сверка счёта «Репо: N» (index) против «репо всего M» (karta)       — допуск --count-tolerance
  4. «Ноль подозрителен»: счёт 0 у любого органа = тревога (мир: silent output failure)

Коды выхода: 0 — всё зелёное; 2 — тревога; 1 — неожиданная ошибка самого сторожа.
Запуск на машине роя или в Actions:  python3 scripts/storozh_check.py [--verdict-file alarm.txt]

Ни одного выдуманного числа: каждый вердикт — арифметика двух штампов.
"""

import argparse
import datetime as dt
import re
import sys
import urllib.request
import urllib.error

STATUS_URL_DEFAULT = "https://raw.githubusercontent.com/rtynbirf/index/main/STATUS.md"
KARTA_URL_DEFAULT = "https://raw.githubusercontent.com/rtynbirf/karta/main/README.md"

STATUS_STAMP_RE = re.compile(
    r"Пересчитано автоматом:\s*(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?\s*UTC")
KARTA_STAMP_RE = re.compile(
    r"сгенерировано\s+(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{2})Z")
STATUS_TOTAL_RE = re.compile(r"Репо:\s*(\d+)")
KARTA_TOTAL_RE = re.compile(r"репо всего\s+(\d+)")


def strip_md(text: str) -> str:
    """Срезать markdown-декор: витрины пишут **жирным**, `бэктиками` и таблицами."""
    t = text.replace("*", " ").replace("`", " ").replace("|", " ")
    return re.sub(r"\s+", " ", t)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={
        # UA строго ASCII: HTTP-заголовки не держат кириллицу (урок первого прогона)
        "User-Agent": "rtynbirf-storozh/1.0 (mutual-pulse, anonymous, no token)",
        "Accept": "application/vnd.github.raw",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def age_hours(stamp: dt.datetime, now: dt.datetime) -> float:
    return (now - stamp).total_seconds() / 3600.0


def main() -> int:
    ap = argparse.ArgumentParser(description="СТОРОЖ — взаимный пульс органов rtynbirf")
    ap.add_argument("--max-age-hours", type=float, default=3.0,
                    help="порог тишины index (ежечасный крон): 3 ч = три пропущенных тика")
    ap.add_argument("--karta-max-hours", type=float, default=26.0,
                    help="порог тишины karta (ночная перегенерация): 26 ч = сутки + джиттер")
    ap.add_argument("--count-tolerance", type=int, default=3,
                    help="допустимая дельта счёта репо index↔karta (территория растёт между прогонами)")
    ap.add_argument("--status-url", default=STATUS_URL_DEFAULT)
    ap.add_argument("--karta-url", default=KARTA_URL_DEFAULT)
    ap.add_argument("--skip-karta", action="store_true")
    ap.add_argument("--skip-count", action="store_true")
    ap.add_argument("--verdict-file", default=None,
                    help="одна строка итога — для журнала тревог СТОРОЖ-workflow")
    args = ap.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    alarms = []   # (орган, диагноз)
    lines = []

    # 1. index: возраст штампа + счёт
    try:
        text = strip_md(fetch(args.status_url))
        m = STATUS_STAMP_RE.search(text)
        if not m:
            alarms.append(("index/STATUS.md", "штамп «Пересчитано автоматом» не найден — файл не подписан временем"))
        else:
            y_, mo_, d_ = (int(x) for x in m.group(1).split("-"))
            stamp = dt.datetime(y_, mo_, d_, int(m.group(2)), int(m.group(3)), tzinfo=dt.timezone.utc)
            age = age_hours(stamp, now)
            if age > args.max_age_hours:
                alarms.append(("index/STATUS.md", f"молчит {age:.1f} ч при пороге {args.max_age_hours:g} ч (штамп {m.group(1)} {m.group(2)}:{m.group(3)} UTC)"))
            else:
                lines.append(f"[СТОРОЖ] index/STATUS.md: штамп {m.group(1)} {m.group(2)} UTC — возраст {age:.1f} ч — зелёный (порог {args.max_age_hours:g} ч)")
        mt = STATUS_TOTAL_RE.search(text)
        if not mt:
            alarms.append(("index/STATUS.md", "счёт «Репо:» не найден"))
        elif int(mt.group(1)) == 0:
            alarms.append(("index/STATUS.md", "счёт 0 репо — ноль подозрителен (silent output failure)"))
        else:
            lines.append(f"[СТОРОЖ] index: счёт {mt.group(1)} — ненулевой, зелёный")
        status_total = int(mt.group(1)) if mt else None
    except (urllib.error.URLError, OSError) as e:
        alarms.append(("index/STATUS.md", f"орган недоступен ({e.__class__.__name__})"))
        status_total = None

    # 2. karta: возраст штампа + счёт
    karta_total = None
    if not args.skip_karta:
        try:
            text = strip_md(fetch(args.karta_url))
            m = KARTA_STAMP_RE.search(text)
            if not m:
                alarms.append(("karta/README.md", "штамп «сгенерировано» не найден — карта не подписана временем"))
            else:
                y_, mo_, d_ = (int(x) for x in m.group(1).split("-"))
                stamp = dt.datetime(y_, mo_, d_, int(m.group(2)), int(m.group(3)),
                                    int(m.group(4)), tzinfo=dt.timezone.utc)
                age = age_hours(stamp, now)
                if age > args.karta_max_hours:
                    alarms.append(("karta/README.md", f"карта отстала на {age:.1f} ч при пороге {args.karta_max_hours:g} ч (штамп {m.group(1)} {m.group(2)}:{m.group(3)} UTC)"))
                else:
                    lines.append(f"[СТОРОЖ] karta/README.md: штамп {m.group(1)} {m.group(2)}:{m.group(3)} UTC — возраст {age:.1f} ч — зелёный (порог {args.karta_max_hours:g} ч)")
            mk = KARTA_TOTAL_RE.search(text)
            if not mk:
                alarms.append(("karta/README.md", "счёт «репо всего» не найден"))
            elif int(mk.group(1)) == 0:
                alarms.append(("karta/README.md", "счёт 0 репо — ноль подозрителен (silent output failure)"))
            else:
                lines.append(f"[СТОРОЖ] karta: счёт {mk.group(1)} — ненулевой, зелёный")
            karta_total = int(mk.group(1)) if mk else None
        except (urllib.error.URLError, OSError) as e:
            alarms.append(("karta/README.md", f"орган недоступен ({e.__class__.__name__})"))

    # 3. Сверка счёта index ↔ karta
    if not args.skip_count and status_total is not None and karta_total is not None:
        delta = abs(status_total - karta_total)
        if delta > args.count_tolerance:
            alarms.append(("сверка счёта", f"index {status_total} vs karta {karta_total} — дельта {delta} за пределом допуска ±{args.count_tolerance}"))
        else:
            lines.append(f"[СТОРОЖ] сверка счёта: index {status_total} vs karta {karta_total} — дельта {delta} — в допуске (±{args.count_tolerance})")

    for ln in lines:
        print(ln)
    for organ, diag in alarms:
        print(f"[СТОРОЖ] ТРЕВОГА · {organ}: {diag}")

    if args.verdict_file:
        if alarms:
            summary = "СТОРОЖ: %d тревоги — %s" % (
                len(alarms), "; ".join(f"{o}: {d}" for o, d in alarms))
        else:
            summary = f"СТОРОЖ: пульс чист ({now.strftime('%Y-%m-%d %H:%M')} UTC)"
        try:
            with open(args.verdict_file, "w", encoding="utf-8") as f:
                f.write(summary + "\n")
        except OSError:
            pass

    print(f"[СТОРОЖ] ИТОГ: {'пульс чист' if not alarms else str(len(alarms)) + ' тревоги'}")
    return 2 if alarms else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # сам сторож не должен умирать молча
        print(f"[СТОРОЖ] ПАДЕНИЕ СТОРОЖА: {e.__class__.__name__}: {e}", file=sys.stderr)
        sys.exit(1)
