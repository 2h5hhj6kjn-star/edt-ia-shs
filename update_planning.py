#!/usr/bin/env python3
"""
Met à jour le planning IA (UE HMUBIA3) depuis l'export iCal ADE de l'Université Côte d'Azur.

- Télécharge l'ICS complet du bloc (URL "Générer URL" d'ADE, lue dans ADE_ICS_URL)
- Ne garde que les séances dont le SUMMARY contient EDT_FILTER (défaut : "Intelligence artificielle")
- Compare avec la version précédente et signale les changements (salle, horaire, ajout, suppression)
- N'écrit le fichier que si quelque chose a réellement changé (ignore DTSTAMP & co)

Usage : ADE_ICS_URL="https://..." python3 update_planning.py [--out fichier.ics] [--copy autre.ics] [--until 2026-09-18]
Sortie : affiche CHANGED / UNCHANGED ; code retour 0 dans les deux cas, 1 en cas d'erreur réseau.
"""
import argparse
import datetime as dt
import os
import re
import sys
import urllib.request
from pathlib import Path

CALNAME = "IA pour les SHS - Bloc SWITCH ODYSSEE S3"
VOLATILE = ("DTSTAMP", "LAST-MODIFIED", "CREATED", "SEQUENCE")  # changent à chaque export, sans intérêt
try:
    from zoneinfo import ZoneInfo
    TZ_PARIS = ZoneInfo("Europe/Paris")
except Exception:  # noqa: BLE001 — pas de base tzdata : on suppose l'heure d'été
    TZ_PARIS = dt.timezone(dt.timedelta(hours=2))
JOURS = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]


def unfold(text: str) -> str:
    """Défait le pliage RFC 5545 (lignes continuées par un espace)."""
    return re.sub(r"\r?\n[ \t]", "", text)


def split_events(ics: str):
    """Retourne (header_lines, [event_block, ...]) ; les blocs gardent leur pliage d'origine."""
    ics = ics.replace("\r\n", "\n")
    header, events = [], []
    for line in ics.split("\n"):
        if line.startswith("BEGIN:VEVENT") or events and not events[-1].endswith("END:VEVENT"):
            if line.startswith("BEGIN:VEVENT"):
                events.append(line)
            else:
                events[-1] += "\n" + line
        elif line and line not in ("BEGIN:VCALENDAR", "END:VCALENDAR"):
            header.append(line)
    return header, events


def prop(block: str, name: str) -> str:
    m = re.search(rf"^{name}(?:;[^:]*)?:(.*)$", unfold(block), re.M)
    return m.group(1).strip() if m else ""


def summary_of(block: str) -> dict:
    return {k: prop(block, k) for k in ("UID", "DTSTART", "DTEND", "SUMMARY", "LOCATION")}


def fmt_dt(s: str) -> str:
    try:
        d = dt.datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc).astimezone(TZ_PARIS)
        return f"{JOURS[d.weekday()]} {d:%d/%m %Hh%M}"
    except ValueError:
        return s


def stable(block: str) -> str:
    """Version d'un bloc sans les champs volatils, pour comparer."""
    return "\n".join(l for l in unfold(block).split("\n") if not l.startswith(VOLATILE))


def build_ics(header, events) -> str:
    out = ["BEGIN:VCALENDAR"]
    out += [l for l in header if not l.startswith("METHOD:")]  # METHOD:REQUEST gêne certains agendas
    out += [f"X-WR-CALNAME:{CALNAME}", "X-WR-TIMEZONE:Europe/Paris",
            "REFRESH-INTERVAL;VALUE=DURATION:PT1H", "X-PUBLISHED-TTL:PT1H"]
    out += events
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n"


def diff_report(old_events, new_events) -> list[str]:
    old = {summary_of(b)["UID"]: b for b in old_events}
    new = {summary_of(b)["UID"]: b for b in new_events}
    lines = []  # (DTSTART, texte)
    for uid in new.keys() - old.keys():
        e = summary_of(new[uid])
        lines.append((e["DTSTART"], f"+ AJOUT     {fmt_dt(e['DTSTART'])} {e['SUMMARY'][:40]} @ {e['LOCATION']}"))
    for uid in old.keys() - new.keys():
        e = summary_of(old[uid])
        lines.append((e["DTSTART"], f"- SUPPRIMÉ  {fmt_dt(e['DTSTART'])} {e['SUMMARY'][:40]} @ {e['LOCATION']}"))
    for uid in old.keys() & new.keys():
        o, n = summary_of(old[uid]), summary_of(new[uid])
        if o["LOCATION"] != n["LOCATION"]:
            lines.append((n["DTSTART"], f"~ SALLE     {fmt_dt(n['DTSTART'])} {n['SUMMARY'][:2]} : {o['LOCATION']}  ->  {n['LOCATION']}"))
        if (o["DTSTART"], o["DTEND"]) != (n["DTSTART"], n["DTEND"]):
            lines.append((n["DTSTART"], f"~ HORAIRE   {n['SUMMARY'][:2]} : {fmt_dt(o['DTSTART'])}-{fmt_dt(o['DTEND'])[-5:]}  ->  {fmt_dt(n['DTSTART'])}-{fmt_dt(n['DTEND'])[-5:]}"))
        if o["SUMMARY"] != n["SUMMARY"]:
            lines.append((n["DTSTART"], f"~ INTITULÉ  {fmt_dt(n['DTSTART'])} : {o['SUMMARY']}  ->  {n['SUMMARY']}"))
    return [text for _, text in sorted(lines)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).with_name("ADECal-IA-seul.ics")))
    ap.add_argument("--copy", action="append", default=[], help="copie supplémentaire (ex: ~/Downloads/...)")
    ap.add_argument("--until", default="2026-09-18", help="date de fin de l'automatisation (YYYY-MM-DD)")
    ap.add_argument("--changelog", default=str(Path(__file__).with_name("CHANGELOG.md")))
    args = ap.parse_args()

    now = dt.datetime.now(TZ_PARIS)
    if now.date() > dt.date.fromisoformat(args.until):
        print(f"UNCHANGED (après le {args.until}, plus de mise à jour)")
        return 0

    url = os.environ.get("ADE_ICS_URL")
    if not url:
        print("ERREUR: variable ADE_ICS_URL absente", file=sys.stderr)
        return 1
    pattern = os.environ.get("EDT_FILTER", "Intelligence artificielle")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 edt-ia"})
        raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
    except Exception as e:  # noqa: BLE001
        print(f"ERREUR téléchargement ADE: {e}", file=sys.stderr)
        return 1
    if "BEGIN:VCALENDAR" not in raw:
        print("ERREUR: la réponse ADE n'est pas un iCalendar", file=sys.stderr)
        return 1

    header, all_events = split_events(raw)
    kept = [b for b in all_events if pattern.lower() in unfold(b).lower()]
    kept.sort(key=lambda b: prop(b, "DTSTART"))
    if not kept:
        print(f"ERREUR: 0 séance sur {len(all_events)} ne correspond à « {pattern} » — fichier non modifié", file=sys.stderr)
        return 1

    out = Path(args.out).expanduser()
    old_events = split_events(out.read_text(encoding="utf-8"))[1] if out.exists() else []
    changed = [stable(b) for b in old_events] != [stable(b) for b in kept]

    stamp = now.strftime("%d/%m/%Y %H:%M")
    print(f"[{stamp}] {len(kept)} séances « {pattern} » sur {len(all_events)} dans le bloc")
    if changed or not out.exists():
        content = build_ics(header, kept)
        out.write_text(content, encoding="utf-8", newline="")
        for c in args.copy:
            p = Path(c).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8", newline="")
        report = diff_report(old_events, kept) if old_events else [f"+ {len(kept)} séances (première génération)"]
        with open(Path(args.changelog).expanduser(), "a", encoding="utf-8") as f:
            f.write(f"\n## {stamp}\n\n" + "\n".join(f"- {l}" for l in report) + "\n")
        print("CHANGED")
        print("\n".join(report))
    else:
        for c in args.copy:  # garde les copies alignées même sans changement
            p = Path(c).expanduser()
            if not p.exists() or p.read_bytes() != out.read_bytes():
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(out.read_bytes())
        print("UNCHANGED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
