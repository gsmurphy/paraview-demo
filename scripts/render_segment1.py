#!/usr/bin/env pvbatch
"""render_segment1.py — GroEL cryo-EM density + fitted atomic model.

Renders frames/segment1/frame_NNNN.png using settings/segment1.py.
Run via pvbatch:
    bin/pvbatch scripts/render_segment1.py [--preview]
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

# Make settings/ importable when this script is invoked by pvbatch from the repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from settings import segment1 as S  # noqa: E402

from paraview.simple import (  # noqa: E402
    OpenDataFile, Show, Hide, GetActiveViewOrCreate, GetColorTransferFunction,
    GetOpacityTransferFunction, ColorBy, Render, SaveScreenshot, ResetCamera,
    GetActiveCamera, Tube, Glyph, Sphere, Delete, MRCSeriesReader,
    XMLPolyDataReader,
)


def smoothstep(t: float) -> float:
    """Cubic ease-in-out on [0,1]."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def ease_azimuth(frame: int, n_frames: int) -> float:
    t = smoothstep(frame / max(1, n_frames - 1))
    return S.CAMERA_START_AZIM + (S.CAMERA_END_AZIM - S.CAMERA_START_AZIM) * t


def opacity_sweep_offset(frame: int) -> float:
    """Triangular sweep that peaks mid-segment, returns to 0 at edges."""
    if not S.SWEEP_ENABLED:
        return 0.0
    t = frame / max(1, S.NUM_FRAMES - 1)
    seg_t = (t * S.DURATION_S - S.SWEEP_START_S) / max(
        1e-6, (S.SWEEP_END_S - S.SWEEP_START_S))
    if seg_t <= 0 or seg_t >= 1:
        return 0.0
    # Triangle 0 → 1 → 0 across [0,1]
    tri = 1.0 - abs(2.0 * seg_t - 1.0)
    return S.SWEEP_OPACITY_SHIFT * smoothstep(tri)


def configure_volume(reader, view, scalar_name: str, data_range: tuple[float, float]):
    rep = Show(reader, view)
    rep.Representation = "Volume"
    ColorBy(rep, ("POINTS", scalar_name))
    rep.SetScalarBarVisibility(view, False)

    lo, hi = data_range
    span = max(hi - lo, 1e-6)

    color_tf = GetColorTransferFunction(scalar_name)
    color_tf.RGBPoints = []
    pts = []
    for frac, r, g, b in S.TF_COLOR_POINTS:
        pts += [lo + frac * span, r, g, b]
    color_tf.RGBPoints = pts
    color_tf.ColorSpace = "Lab"
    color_tf.NanColor = [0.0, 0.0, 0.0]

    opac_tf = GetOpacityTransferFunction(scalar_name)
    return rep, color_tf, opac_tf, lo, span


def update_opacity(opac_tf, lo: float, span: float, sweep_offset: float) -> None:
    pts = []
    for frac, op in S.TF_OPACITY_POINTS:
        v = lo + frac * span
        new_op = max(0.0, min(1.0, op + sweep_offset))
        pts += [v, new_op, 0.5, 0.0]
    opac_tf.Points = pts


def configure_backbone(view) -> None:
    bb = XMLPolyDataReader(FileName=[str(REPO_ROOT / S.BACKBONE_VTP)])
    tube = Tube(Input=bb)
    tube.Radius = getattr(S, "BACKBONE_TUBE_R", 0.7)
    tube.NumberofSides = 14
    tube.Capping = 1
    rep = Show(tube, view)
    rep.Representation = "Surface"
    rep.AmbientColor = list(S.BACKBONE_COLOR)
    rep.DiffuseColor = list(S.BACKBONE_COLOR)
    rep.Opacity = S.BACKBONE_OPACITY
    rep.Specular = 0.15
    rep.SpecularPower = 30
    rep.Ambient = S.AMBIENT


def configure_atoms(view) -> None:
    atoms = XMLPolyDataReader(FileName=[str(REPO_ROOT / S.ATOMS_VTP)])
    sphere = Sphere()
    sphere.Radius = 1.0
    sphere.ThetaResolution = 12
    sphere.PhiResolution = 12

    glyph = Glyph(Input=atoms, GlyphType=sphere)
    glyph.OrientationArray = ["POINTS", "No orientation array"]
    glyph.ScaleArray = ["POINTS", "radius"]
    glyph.ScaleFactor = S.ATOM_SCALE
    glyph.GlyphMode = "All Points"

    rep = Show(glyph, view)
    rep.Representation = "Surface"
    rep.AmbientColor = list(S.ATOM_COLOR)
    rep.DiffuseColor = list(S.ATOM_COLOR)
    rep.Opacity = S.ATOM_OPACITY
    rep.Ambient = S.AMBIENT


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true",
                        help="Quarter resolution; every Nth frame; no sweep.")
    args = parser.parse_args()

    res = S.PREVIEW_RES if args.preview else S.RESOLUTION
    stride = S.PREVIEW_STRIDE if args.preview else 1
    sweep_enabled = S.SWEEP_ENABLED and not args.preview

    out_dir = REPO_ROOT / S.FRAMES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    # Wipe stale frames so old preview frames don't leak into final output.
    for old in out_dir.glob("frame_*.png"):
        old.unlink()

    view = GetActiveViewOrCreate("RenderView")
    view.ViewSize = list(res)
    view.Background = list(S.BACKGROUND)
    view.OrientationAxesVisibility = 0
    view.UseColorPaletteForBackground = 0

    # --- volume ----
    # Use the MRC reader explicitly: ParaView's auto-dispatcher doesn't tie
    # the .map extension (cryo-EM convention) to MRCSeriesReader.
    reader = MRCSeriesReader(FileNames=[str(REPO_ROOT / S.DENSITY_MAP)])
    if reader is None:
        sys.exit(f"error: ParaView could not open {S.DENSITY_MAP}")
    reader.UpdatePipeline()
    pdi = reader.GetPointDataInformation()
    arr_name = pdi.GetArray(0).GetName() if pdi.GetNumberOfArrays() else "ImageScalars"
    rng = pdi.GetArray(0).GetRange() if pdi.GetNumberOfArrays() else (0.0, 1.0)
    vol_rep, color_tf, opac_tf, lo, span = configure_volume(reader, view, arr_name, rng)
    update_opacity(opac_tf, lo, span, 0.0)

    # --- atomic model ----
    configure_backbone(view)
    configure_atoms(view)

    # --- camera ----
    ResetCamera(view)
    cam = GetActiveCamera()
    bounds = reader.GetDataInformation().GetBounds()
    cx = 0.5 * (bounds[0] + bounds[1])
    cy = 0.5 * (bounds[2] + bounds[3])
    cz = 0.5 * (bounds[4] + bounds[5])
    cam.SetFocalPoint(cx, cy, cz)
    cam.SetViewUp(*S.CAMERA_VIEW_UP)

    # Render frames
    n_frames = S.NUM_FRAMES
    print(f"[render_segment1] {n_frames} frames @ {res[0]}x{res[1]}, stride={stride}")
    for f in range(n_frames):
        if f % stride != 0:
            continue
        azim = ease_azimuth(f, n_frames)
        rad = math.radians(azim)
        elev = math.radians(S.CAMERA_ELEVATION)
        d = S.CAMERA_DISTANCE
        # axis is Z; orbit in XY then tilt by elev around Y.
        x = cx + d * math.cos(rad) * math.cos(elev)
        y = cy + d * math.sin(rad) * math.cos(elev)
        z = cz + d * math.sin(elev)
        cam.SetPosition(x, y, z)

        if sweep_enabled:
            update_opacity(opac_tf, lo, span, opacity_sweep_offset(f))

        out_path = out_dir / f"frame_{f:04d}.png"
        SaveScreenshot(str(out_path), view, ImageResolution=list(res))
        if f % 30 == 0:
            print(f"[render_segment1] frame {f}/{n_frames} -> {out_path.name}")

    print("[render_segment1] done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
