#!/usr/bin/env pvbatch
"""render_segment2.py — Lysozyme APBS electrostatic potential.

Renders frames/segment2/frame_NNNN.png using settings/segment2.py.
Run via pvbatch:
    bin/pvbatch scripts/render_segment2.py [--preview]
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from settings import segment2 as S  # noqa: E402

from paraview.simple import (  # noqa: E402
    OpenDataFile, Show, Hide, GetActiveViewOrCreate, GetColorTransferFunction,
    ColorBy, SaveScreenshot, ResetCamera, GetActiveCamera, Tube,
    Contour, ResampleWithDataset, GaussianResampling,
    Sphere, Glyph, Render, Delete, XMLPolyDataReader, XMLImageDataReader,
)


def smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def ease_azimuth(frame: int, n_frames: int) -> float:
    t = smoothstep(frame / max(1, n_frames - 1))
    return S.CAMERA_START_AZIM + (S.CAMERA_END_AZIM - S.CAMERA_START_AZIM) * t


def threshold_at(frame: int, n_frames: int) -> tuple[float, float]:
    """Return (positive, negative) iso thresholds.

    Outside the sweep window: tight thresholds. Inside: ease toward loose
    in the first half, back toward tight in the second.
    """
    if not S.SWEEP_ENABLED:
        return S.ISO_POSITIVE_TIGHT, S.ISO_NEGATIVE_TIGHT
    t = frame / max(1, n_frames - 1)
    seg = (t * S.DURATION_S - S.SWEEP_START_S) / max(
        1e-6, S.SWEEP_END_S - S.SWEEP_START_S)
    if seg <= 0 or seg >= 1:
        return S.ISO_POSITIVE_TIGHT, S.ISO_NEGATIVE_TIGHT
    tri = 1.0 - abs(2.0 * seg - 1.0)
    k = smoothstep(tri)
    pos = S.ISO_POSITIVE_TIGHT + (S.ISO_POSITIVE_LOOSE - S.ISO_POSITIVE_TIGHT) * k
    neg = S.ISO_NEGATIVE_TIGHT + (S.ISO_NEGATIVE_LOOSE - S.ISO_NEGATIVE_TIGHT) * k
    return pos, neg


def make_diverging_colormap(name: str):
    tf = GetColorTransferFunction(name)
    pts = []
    for v, r, g, b in S.DIVERGING_COLOR_POINTS:
        pts += [v, r, g, b]
    tf.RGBPoints = pts
    tf.ColorSpace = "Diverging"
    tf.NanColor = [0.5, 0.5, 0.5]
    return tf


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
    for old in out_dir.glob("frame_*.png"):
        old.unlink()

    view = GetActiveViewOrCreate("RenderView")
    view.ViewSize = list(res)
    view.Background = list(S.BACKGROUND)
    view.OrientationAxesVisibility = 0
    view.UseColorPaletteForBackground = 0

    # --- load APBS volume (converted from .dx to .vti by scripts/dx_to_vti.py) ----
    dx_reader = XMLImageDataReader(FileName=[str(REPO_ROOT / S.VTI_FILE)])
    dx_reader.UpdatePipeline()

    pdi = dx_reader.GetPointDataInformation()
    pot_name = pdi.GetArray(0).GetName() if pdi.GetNumberOfArrays() else "potential"

    # --- molecular surface ----
    # Build a Gaussian-density volume from atom centers, contour at a fraction
    # of the density max, and color by interpolated APBS potential.
    atoms = XMLPolyDataReader(FileName=[str(REPO_ROOT / S.ATOMS_VTP)])
    atoms.UpdatePipeline()

    bbox = atoms.GetDataInformation().GetBounds()
    pad = 4.0
    sample_dims = [int((bbox[1] - bbox[0] + 2 * pad) * 2) + 1,
                   int((bbox[3] - bbox[2] + 2 * pad) * 2) + 1,
                   int((bbox[5] - bbox[4] + 2 * pad) * 2) + 1]

    gauss = GaussianResampling(Input=atoms)
    gauss.ResampleField = ["POINTS", "radius"]
    gauss.ResamplingGrid = sample_dims
    gauss.GaussianSplatRadius = S.SURFACE_SPLAT_RADIUS
    gauss.GaussianExponentFactor = -3
    gauss.ScaleSplats = 0           # uniform splat — gives a smoother envelope
    gauss.SplatAccumulationMode = "Sum"

    gauss.UpdatePipeline()
    g_pdi = gauss.GetPointDataInformation()
    # The output array name varies by ParaView build; pick the first scalar.
    splat_arr = g_pdi.GetArray(0)
    splat_name = splat_arr.GetName()
    g_lo, g_max = splat_arr.GetRange()
    print(f"[render_segment2] splat field '{splat_name}' range ({g_lo:.3f}, {g_max:.3f})")

    surf = Contour(Input=gauss)
    surf.ContourBy = ["POINTS", splat_name]
    surf.Isosurfaces = [g_max * S.SURFACE_ISOLEVEL_FRAC]

    # Sample APBS potential onto the surface for coloring.
    surf_colored = ResampleWithDataset(SourceDataArrays=dx_reader, DestinationMesh=surf)

    surf_rep = Show(surf_colored, view)
    surf_rep.Representation = "Surface"
    surf_rep.Opacity = S.SURFACE_OPACITY
    ColorBy(surf_rep, ("POINTS", pot_name))
    div_tf = make_diverging_colormap(pot_name)
    surf_rep.SetScalarBarVisibility(view, False)
    surf_rep.Specular = 0.30
    surf_rep.SpecularPower = 50
    surf_rep.Ambient = S.AMBIENT

    # --- ± isosurfaces from the volume ----
    iso_pos = Contour(Input=dx_reader)
    iso_pos.ContourBy = ["POINTS", pot_name]
    iso_pos.Isosurfaces = [S.ISO_POSITIVE_TIGHT]
    iso_pos_rep = Show(iso_pos, view)
    iso_pos_rep.Representation = "Surface"
    iso_pos_rep.AmbientColor = list(S.ISO_POSITIVE_COLOR)
    iso_pos_rep.DiffuseColor = list(S.ISO_POSITIVE_COLOR)
    iso_pos_rep.Opacity = S.ISO_OPACITY
    iso_pos_rep.Ambient = S.AMBIENT

    iso_neg = Contour(Input=dx_reader)
    iso_neg.ContourBy = ["POINTS", pot_name]
    iso_neg.Isosurfaces = [S.ISO_NEGATIVE_TIGHT]
    iso_neg_rep = Show(iso_neg, view)
    iso_neg_rep.Representation = "Surface"
    iso_neg_rep.AmbientColor = list(S.ISO_NEGATIVE_COLOR)
    iso_neg_rep.DiffuseColor = list(S.ISO_NEGATIVE_COLOR)
    iso_neg_rep.Opacity = S.ISO_OPACITY
    iso_neg_rep.Ambient = S.AMBIENT

    # --- backbone tube ----
    bb = XMLPolyDataReader(FileName=[str(REPO_ROOT / S.BACKBONE_VTP)])
    tube = Tube(Input=bb)
    tube.Radius = 0.4
    tube.NumberofSides = 12
    tube.Capping = 1
    tube_rep = Show(tube, view)
    tube_rep.Representation = "Surface"
    tube_rep.AmbientColor = list(S.BACKBONE_COLOR)
    tube_rep.DiffuseColor = list(S.BACKBONE_COLOR)
    tube_rep.Opacity = S.BACKBONE_OPACITY
    tube_rep.Ambient = S.AMBIENT

    # --- camera ----
    ResetCamera(view)
    cam = GetActiveCamera()
    bounds = surf.GetDataInformation().GetBounds()
    cx = 0.5 * (bounds[0] + bounds[1])
    cy = 0.5 * (bounds[2] + bounds[3])
    cz = 0.5 * (bounds[4] + bounds[5])
    cam.SetFocalPoint(cx, cy, cz)
    cam.SetViewUp(*S.CAMERA_VIEW_UP)

    # Render frames
    n_frames = S.NUM_FRAMES
    print(f"[render_segment2] {n_frames} frames @ {res[0]}x{res[1]}, stride={stride}")
    for f in range(n_frames):
        if f % stride != 0:
            continue
        azim = ease_azimuth(f, n_frames)
        rad = math.radians(azim)
        elev = math.radians(S.CAMERA_ELEVATION)
        d = S.CAMERA_DISTANCE
        # Orbit around Y (CAMERA_AXIS), tilt by elev around X.
        x = cx + d * math.cos(rad) * math.cos(elev)
        z = cz + d * math.sin(rad) * math.cos(elev)
        y = cy + d * math.sin(elev)
        cam.SetPosition(x, y, z)

        if sweep_enabled:
            pos_iso, neg_iso = threshold_at(f, n_frames)
            iso_pos.Isosurfaces = [pos_iso]
            iso_neg.Isosurfaces = [neg_iso]

        out_path = out_dir / f"frame_{f:04d}.png"
        SaveScreenshot(str(out_path), view, ImageResolution=list(res))
        if f % 30 == 0:
            print(f"[render_segment2] frame {f}/{n_frames} -> {out_path.name}")

    print("[render_segment2] done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
