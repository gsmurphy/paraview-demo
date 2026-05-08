#!/usr/bin/env python3
"""fetch_data.py — Download / generate all source data for the demo.

Targets:
  data/groel/EMD-5001.map      cryo-EM density (EMDB)
  data/groel/3CAU.pdb          fitted atomic model (RCSB)
  data/lysozyme/1AKI.pdb       atomic model (RCSB)
  data/lysozyme/1AKI.pqr       PDB2PQR output  (computed locally)
  data/lysozyme/1AKI.dx        APBS potential   (computed locally)

The brief originally targeted the APBS-PDB2PQR REST API at
server.poissonboltzmann.org. As of this writing that service's
env-config.js points its workflow URL at a private Kubernetes address
(apbs.127.0.0.1.xip.io) that is not reachable from the public internet.
We instead run pdb2pqr (pip) and apbs (brewsci/bio/apbs) locally; the
README documents this deviation.
"""

from __future__ import annotations

import argparse
import gzip
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"

EMDB_MAP_URL = "https://ftp.ebi.ac.uk/pub/databases/emdb/structures/EMD-5001/map/emd_5001.map.gz"
RCSB_PDB_URL = "https://files.rcsb.org/download/{pdb}.pdb"

GROEL_DIR = DATA / "groel"
LYSO_DIR  = DATA / "lysozyme"


# --- small helpers ----------------------------------------------------------

def log(msg: str) -> None:
    print(f"[fetch_data] {msg}", flush=True)


def download(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        log(f"cached  {dest.relative_to(REPO_ROOT)}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    log(f"GET     {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url) as resp, open(tmp, "wb") as out:
        shutil.copyfileobj(resp, out)
    tmp.rename(dest)
    log(f"wrote   {dest.relative_to(REPO_ROOT)} ({dest.stat().st_size/1e6:.1f} MB)")


def gunzip(src_gz: Path, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    log(f"gunzip  {src_gz.name} -> {dest.name}")
    with gzip.open(src_gz, "rb") as fin, open(dest, "wb") as fout:
        shutil.copyfileobj(fin, fout)


# --- GroEL: EMD-5001 + 3CAU -------------------------------------------------

def fetch_groel() -> None:
    GROEL_DIR.mkdir(parents=True, exist_ok=True)
    map_gz = GROEL_DIR / "emd_5001.map.gz"
    map_out = GROEL_DIR / "EMD-5001.map"
    download(EMDB_MAP_URL, map_gz)
    gunzip(map_gz, map_out)
    download(RCSB_PDB_URL.format(pdb="3CAU"), GROEL_DIR / "3CAU.pdb")


# --- Lysozyme: 1AKI + APBS --------------------------------------------------

def have_cli(name: str) -> bool:
    return shutil.which(name) is not None


def run(cmd: list[str], cwd: Path | None = None) -> None:
    log("$ " + " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=cwd)


def fetch_lysozyme() -> None:
    LYSO_DIR.mkdir(parents=True, exist_ok=True)
    pdb = LYSO_DIR / "1AKI.pdb"
    pqr = LYSO_DIR / "1AKI.pqr"
    dx  = LYSO_DIR / "1AKI.dx"

    download(RCSB_PDB_URL.format(pdb="1AKI"), pdb)

    # If the user pre-staged .pqr/.dx (manual fallback), keep them and bail.
    if pqr.exists() and dx.exists():
        log(f"cached  {pqr.relative_to(REPO_ROOT)}, {dx.relative_to(REPO_ROOT)}")
        return

    if not have_cli("pdb2pqr30"):
        sys.exit("error: pdb2pqr30 not on PATH. Activate .venv (source .venv/bin/activate).")
    if not have_cli("apbs"):
        sys.exit("error: apbs not on PATH. Run: brew install brewsci/bio/apbs")

    # 1. PDB2PQR: assign charges + radii at pH 7, write APBS input file.
    apbs_in = LYSO_DIR / "1AKI.in"
    if not (pqr.exists() and apbs_in.exists()):
        run([
            "pdb2pqr30",
            "--ff=AMBER",
            "--apbs-input", apbs_in.name,
            "--with-ph=7.0",
            pdb.name,
            pqr.name,
        ], cwd=LYSO_DIR)

    # 2. APBS: ensure the input file writes a .dx of the potential.
    #    pdb2pqr's generated .in writes "pot dx pot" → pot.dx. Patch the
    #    output stem so we land on 1AKI.dx directly.
    patch_apbs_input(apbs_in, out_stem="1AKI")

    # 3. Run apbs.
    run(["apbs", apbs_in.name], cwd=LYSO_DIR)

    # apbs writes <out_stem>.dx (no ".pot" suffix because we override).
    if not dx.exists():
        # Some apbs builds emit "1AKI-pot.dx" or "1AKI.pot.dx". Reconcile.
        for cand in (LYSO_DIR / "1AKI-pot.dx", LYSO_DIR / "1AKI.pot.dx"):
            if cand.exists():
                cand.rename(dx)
                break

    if not dx.exists():
        sys.exit(f"error: APBS did not produce {dx}. Check apbs output above.")


def patch_apbs_input(apbs_in: Path, out_stem: str) -> None:
    """Rewrite the 'write pot dx <stem>' line so APBS writes <out_stem>.dx."""
    text = apbs_in.read_text()
    new_lines = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("write pot dx") or s.startswith("write   pot   dx"):
            indent = line[: len(line) - len(line.lstrip())]
            new_lines.append(f"{indent}write pot dx {out_stem}")
        else:
            new_lines.append(line)
    apbs_in.write_text("\n".join(new_lines) + "\n")


# --- main -------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-groel", action="store_true",
        help="Skip GroEL download (segment 1).",
    )
    parser.add_argument(
        "--skip-lysozyme", action="store_true",
        help="Skip lysozyme + APBS (segment 2).",
    )
    args = parser.parse_args()

    DATA.mkdir(exist_ok=True)
    if not args.skip_groel:
        fetch_groel()
    if not args.skip_lysozyme:
        fetch_lysozyme()
    log("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
