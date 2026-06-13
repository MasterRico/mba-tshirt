#!/usr/bin/env python3
"""Split the combined KDP/TSF SQLite database into two standalone DBs.

Aus dem kombinierten kdp_ads.db (enthält KDP- UND tsf_*-Tabellen) werden erzeugt:
  * mba.db            — nur tsf_*-Tabellen (+ Daten)  -> für die MBA-Plattform
  * kdp_ads_clean.db  — alles AUSSER tsf_*-Tabellen    -> für die bereinigte KDP-Plattform

Das Original wird nicht verändert. Nutzung:
    python split_db.py /pfad/zu/kdp_ads.db [--outdir .]
"""
import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

TSF_PREFIX = "tsf_"


def user_tables(con: sqlite3.Connection) -> list[str]:
    rows = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return [r[0] for r in rows]


def drop_tables(db_path: Path, tables: list[str]) -> None:
    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys=OFF")
        for t in tables:
            con.execute(f'DROP TABLE IF EXISTS "{t}"')
        con.commit()
        con.execute("VACUUM")
        con.commit()
    finally:
        con.close()


def row_counts(db_path: Path) -> dict[str, int]:
    con = sqlite3.connect(db_path)
    try:
        out = {}
        for t in user_tables(con):
            out[t] = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        return out
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="Pfad zur kombinierten kdp_ads.db")
    ap.add_argument("--outdir", default=".", help="Zielordner (Default: aktuelles Verzeichnis)")
    args = ap.parse_args()

    src = Path(args.source).resolve()
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        print(f"FEHLER: Quelle nicht gefunden: {src}", file=sys.stderr)
        return 1

    con = sqlite3.connect(src)
    all_tables = user_tables(con)
    con.close()

    tsf_tables = sorted(t for t in all_tables if t.startswith(TSF_PREFIX))
    kdp_tables = sorted(t for t in all_tables if not t.startswith(TSF_PREFIX))

    print(f"Quelle: {src}")
    print(f"  tsf_*-Tabellen ({len(tsf_tables)}): {tsf_tables}")
    print(f"  KDP-Tabellen  ({len(kdp_tables)}): {kdp_tables}")
    print()

    mba_db = outdir / "mba.db"
    kdp_db = outdir / "kdp_ads_clean.db"

    # mba.db = Kopie ohne KDP-Tabellen
    shutil.cop2 = shutil.copy2  # noqa
    shutil.copy2(src, mba_db)
    drop_tables(mba_db, kdp_tables)

    # kdp_ads_clean.db = Kopie ohne tsf_*-Tabellen
    shutil.copy2(src, kdp_db)
    drop_tables(kdp_db, tsf_tables)

    # Verifikation
    src_counts = row_counts(src)
    mba_counts = row_counts(mba_db)
    kdp_counts = row_counts(kdp_db)

    print(f"-> {mba_db.name}  (Tabellen: {sorted(mba_counts)})")
    print(f"-> {kdp_db.name}  (Tabellen: {sorted(kdp_counts)})")
    print()
    print("Verifikation Zeilenzahlen (Quelle -> Ziel):")
    ok = True
    for t in sorted(all_tables):
        target = mba_counts.get(t) if t.startswith(TSF_PREFIX) else kdp_counts.get(t)
        match = "OK" if target == src_counts[t] else "MISMATCH!"
        if target != src_counts[t]:
            ok = False
        print(f"  {t:32s} {src_counts[t]:>8d} -> {target if target is not None else '-':>8} [{match}]")

    # Cross-Check: keine Fremd-Tabellen im jeweiligen Ziel
    leak_mba = [t for t in mba_counts if not t.startswith(TSF_PREFIX)]
    leak_kdp = [t for t in kdp_counts if t.startswith(TSF_PREFIX)]
    if leak_mba:
        print(f"  FEHLER: KDP-Reste in mba.db: {leak_mba}"); ok = False
    if leak_kdp:
        print(f"  FEHLER: tsf_-Reste in kdp_ads_clean.db: {leak_kdp}"); ok = False

    print()
    print("ERGEBNIS:", "alles konsistent ✓" if ok else "ABWEICHUNGEN — bitte prüfen ✗")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
