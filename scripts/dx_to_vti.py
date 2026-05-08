#!/usr/bin/env python3
"""dx_to_vti.py — Convert an OpenDX scalar volume (APBS output) to .vti.

ParaView 6.1 doesn't ship an OpenDX reader, so we parse the (well-defined,
text-based) APBS .dx layout and emit a VTK XML ImageData file.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np


def parse_dx(path: Path) -> tuple[tuple[int, int, int], tuple[float, float, float],
                                   tuple[float, float, float], np.ndarray]:
    """Return ((nx, ny, nz), origin, spacing, values) from an APBS-style .dx."""
    text = path.read_text()
    counts = re.search(
        r"object\s+1\s+class\s+gridpositions\s+counts\s+(\d+)\s+(\d+)\s+(\d+)",
        text)
    origin = re.search(r"origin\s+([-\d\.eE+]+)\s+([-\d\.eE+]+)\s+([-\d\.eE+]+)",
                       text)
    deltas = re.findall(
        r"delta\s+([-\d\.eE+]+)\s+([-\d\.eE+]+)\s+([-\d\.eE+]+)", text)
    items = re.search(
        r"object\s+3\s+class\s+array.*?items\s+(\d+).*?\n", text)
    if not (counts and origin and len(deltas) >= 3 and items):
        sys.exit(f"error: {path} not in expected APBS .dx layout")

    nx, ny, nz = (int(c) for c in counts.groups())
    x0, y0, z0 = (float(v) for v in origin.groups())
    # Diagonal spacings only (APBS always uses axis-aligned grids).
    hx = float(deltas[0][0])
    hy = float(deltas[1][1])
    hz = float(deltas[2][2])
    n_items = int(items.group(1))

    if n_items != nx * ny * nz:
        sys.exit(f"error: count mismatch ({n_items} vs {nx*ny*nz})")

    # Data block lives after the last 'data follows' marker.
    body = text.split("data follows", 1)[1]
    body = body.split("attribute", 1)[0]
    vals = np.fromstring(body, sep=" ", dtype=np.float32)
    if vals.size != n_items:
        sys.exit(f"error: parsed {vals.size} values, expected {n_items}")

    # APBS writes in (x_inner, y_middle, z_outer) order: index = i*ny*nz + j*nz + k
    # VTK expects (x_inner, y_middle, z_outer) too -> ravel order F vs C.
    arr = vals.reshape((nx, ny, nz))
    return (nx, ny, nz), (x0, y0, z0), (hx, hy, hz), arr


def write_vti(out: Path, dims, origin, spacing, arr: np.ndarray, name: str) -> None:
    nx, ny, nz = dims
    x0, y0, z0 = origin
    hx, hy, hz = spacing
    # VTK ImageData PointData order: i fastest, then j, then k.
    flat = np.transpose(arr, (2, 1, 0)).ravel().astype(np.float32)

    extent = f"0 {nx-1} 0 {ny-1} 0 {nz-1}"
    vals_str = " ".join(f"{v:.6g}" for v in flat.tolist())

    xml = f"""<?xml version="1.0"?>
<VTKFile type="ImageData" version="1.0" byte_order="LittleEndian" header_type="UInt32">
  <ImageData WholeExtent="{extent}" Origin="{x0} {y0} {z0}" Spacing="{hx} {hy} {hz}">
    <Piece Extent="{extent}">
      <PointData Scalars="{name}">
        <DataArray type="Float32" Name="{name}" format="ascii">{vals_str}</DataArray>
      </PointData>
    </Piece>
  </ImageData>
</VTKFile>
"""
    out.write_text(xml)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dx", required=True, type=Path)
    p.add_argument("--vti", required=True, type=Path)
    p.add_argument("--name", default="potential",
                   help="Scalar array name in the output .vti")
    args = p.parse_args()

    if not args.dx.exists():
        sys.exit(f"error: {args.dx} not found")

    dims, origin, spacing, arr = parse_dx(args.dx)
    args.vti.parent.mkdir(parents=True, exist_ok=True)
    write_vti(args.vti, dims, origin, spacing, arr, args.name)
    rng = (float(arr.min()), float(arr.max()))
    print(f"[dx_to_vti] {args.dx.name} -> {args.vti.name}: dims={dims}, range={rng}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
