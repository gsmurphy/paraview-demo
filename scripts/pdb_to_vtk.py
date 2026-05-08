#!/usr/bin/env python3
"""pdb_to_vtk.py — Convert a PDB to two VTK PolyData files.

Outputs (per --out-prefix STEM):
  STEM_backbone.vtp   polyline through the Cα atoms of every chain;
                      a downstream Tube filter in ParaView wraps it.
  STEM_atoms.vtp      one point per atom with a 'radius' scalar
                      (van der Waals); a Glyph filter renders spheres.

Pure stdlib + Biopython + numpy — written to be runnable inside the
project .venv before pvbatch ever touches the data.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from Bio.PDB import PDBParser, is_aa


# Approximate van der Waals radii (Å) — Bondi 1964.
VDW = {
    "H": 1.20, "C": 1.70, "N": 1.55, "O": 1.52, "S": 1.80,
    "P": 1.80, "F": 1.47, "CL": 1.75, "BR": 1.85, "I": 1.98,
    "FE": 1.94, "ZN": 1.39, "MG": 1.73, "CA": 2.31, "K": 2.75,
    "NA": 2.27,
}
DEFAULT_VDW = 1.70


def collect_backbone(structure) -> dict[str, np.ndarray]:
    """Return {chain_id: array(N,3)} of Cα coordinates per chain."""
    chains: dict[str, list[tuple[float, float, float]]] = {}
    for model in structure:
        for chain in model:
            cas: list[tuple[float, float, float]] = []
            for residue in chain:
                if not is_aa(residue, standard=False):
                    continue
                if "CA" in residue:
                    ca = residue["CA"]
                    cas.append(tuple(float(x) for x in ca.get_coord()))
            if cas:
                chains.setdefault(chain.id, []).extend(cas)
        break  # only the first model
    return {cid: np.asarray(pts, dtype=np.float32) for cid, pts in chains.items()}


def collect_atoms(structure) -> tuple[np.ndarray, np.ndarray]:
    """Return (coords[N,3], radii[N]) for every atom in the first model."""
    coords: list[tuple[float, float, float]] = []
    radii: list[float] = []
    for model in structure:
        for chain in model:
            for residue in chain:
                # Skip waters and most heteroatoms; keep std AAs and common ions.
                resname = residue.get_resname().strip()
                if resname == "HOH":
                    continue
                for atom in residue:
                    coords.append(tuple(float(x) for x in atom.get_coord()))
                    elem = (atom.element or atom.get_name()[0]).upper()
                    radii.append(VDW.get(elem, DEFAULT_VDW))
        break
    return np.asarray(coords, dtype=np.float32), np.asarray(radii, dtype=np.float32)


# --- VTK XML PolyData writers (no vtk dependency) ---------------------------

def _floats(a: np.ndarray) -> str:
    return " ".join(f"{x:.4f}" for x in a.ravel().tolist())


def _ints(a) -> str:
    return " ".join(str(int(x)) for x in a)


def write_polyline_vtp(path: Path, chains: dict[str, np.ndarray]) -> None:
    """Write a .vtp containing one polyline per chain."""
    if not chains:
        sys.exit(f"error: no Cα backbone found for {path}")

    points: list[np.ndarray] = []
    line_offsets: list[int] = []
    line_connectivity: list[int] = []
    cursor = 0
    for cid, pts in chains.items():
        if pts.shape[0] < 2:
            cursor += pts.shape[0]
            points.append(pts)
            continue
        points.append(pts)
        connectivity = list(range(cursor, cursor + pts.shape[0]))
        line_connectivity.extend(connectivity)
        line_offsets.append(len(line_connectivity))
        cursor += pts.shape[0]

    all_points = np.vstack(points) if points else np.zeros((0, 3), dtype=np.float32)
    n_pts = all_points.shape[0]
    n_lines = len(line_offsets)

    xml = [
        '<?xml version="1.0"?>',
        '<VTKFile type="PolyData" version="1.0" byte_order="LittleEndian" header_type="UInt32">',
        '  <PolyData>',
        f'    <Piece NumberOfPoints="{n_pts}" NumberOfVerts="0" NumberOfLines="{n_lines}" NumberOfStrips="0" NumberOfPolys="0">',
        '      <Points>',
        f'        <DataArray type="Float32" NumberOfComponents="3" format="ascii">{_floats(all_points)}</DataArray>',
        '      </Points>',
        '      <Lines>',
        f'        <DataArray type="Int64" Name="connectivity" format="ascii">{_ints(line_connectivity)}</DataArray>',
        f'        <DataArray type="Int64" Name="offsets" format="ascii">{_ints(line_offsets)}</DataArray>',
        '      </Lines>',
        '    </Piece>',
        '  </PolyData>',
        '</VTKFile>',
    ]
    path.write_text("\n".join(xml))


def write_atoms_vtp(path: Path, coords: np.ndarray, radii: np.ndarray) -> None:
    n = coords.shape[0]
    xml = [
        '<?xml version="1.0"?>',
        '<VTKFile type="PolyData" version="1.0" byte_order="LittleEndian" header_type="UInt32">',
        '  <PolyData>',
        f'    <Piece NumberOfPoints="{n}" NumberOfVerts="{n}" NumberOfLines="0" NumberOfStrips="0" NumberOfPolys="0">',
        '      <Points>',
        f'        <DataArray type="Float32" NumberOfComponents="3" format="ascii">{_floats(coords)}</DataArray>',
        '      </Points>',
        '      <Verts>',
        f'        <DataArray type="Int64" Name="connectivity" format="ascii">{_ints(range(n))}</DataArray>',
        f'        <DataArray type="Int64" Name="offsets" format="ascii">{_ints(range(1, n + 1))}</DataArray>',
        '      </Verts>',
        '      <PointData Scalars="radius">',
        f'        <DataArray type="Float32" Name="radius" format="ascii">{_floats(radii)}</DataArray>',
        '      </PointData>',
        '    </Piece>',
        '  </PolyData>',
        '</VTKFile>',
    ]
    path.write_text("\n".join(xml))


# --- main -------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdb", required=True, type=Path, help="Input .pdb file")
    p.add_argument("--out-prefix", required=True, type=Path,
                   help="Output stem; writes <stem>_backbone.vtp and <stem>_atoms.vtp")
    args = p.parse_args()

    if not args.pdb.exists():
        sys.exit(f"error: {args.pdb} not found")

    parser = PDBParser(QUIET=True)
    structure = parser.get_structure(args.pdb.stem, str(args.pdb))

    backbone = collect_backbone(structure)
    coords, radii = collect_atoms(structure)

    out_backbone = args.out_prefix.with_name(args.out_prefix.name + "_backbone.vtp")
    out_atoms    = args.out_prefix.with_name(args.out_prefix.name + "_atoms.vtp")

    out_backbone.parent.mkdir(parents=True, exist_ok=True)
    write_polyline_vtp(out_backbone, backbone)
    write_atoms_vtp(out_atoms, coords, radii)

    n_chains = len(backbone)
    n_ca = sum(arr.shape[0] for arr in backbone.values())
    print(f"[pdb_to_vtk] {args.pdb.name}: {n_chains} chains, {n_ca} Cα, {coords.shape[0]} atoms")
    print(f"[pdb_to_vtk] wrote {out_backbone.name}, {out_atoms.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
