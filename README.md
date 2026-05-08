# ParaView Protein Visualization Demo

A ~22-second 1080p MP4 showcasing ParaView's strengths for protein and biomolecular
visualization, regenerable end-to-end from a single `make` command.

- **Segment 1 — GroEL** (EMD-5001 + PDB 3CAU). Semi-transparent volume rendering of a
  cryo-EM density map with the fitted atomic model visible inside the chaperonin barrel.
- **Title card** — "Electrostatic Potential · Lysozyme · APBS-PDB2PQR".
- **Segment 2 — Lysozyme** (PDB 1AKI + APBS). Molecular surface colored by
  electrostatic potential alongside positive (blue) and negative (red) isosurfaces;
  faint backbone tube behind the surface; mid-segment threshold sweep to show field falloff.

The final video lives at `out/demo.mp4` (committed if < 25 MB) or attached to the
[v0.1.0 release](https://github.com/gsmurphy/paraview-demo/releases/tag/v0.1.0)
otherwise.

## Quickstart

```bash
git clone https://github.com/gsmurphy/paraview-demo.git
cd paraview-demo
./setup.sh        # installs ParaView, ffmpeg, gh, APBS, sets up .venv
make              # fetch → convert → render → assemble → out/demo.mp4
```

Subsequent `make` runs are render-only — fetched data is cached under `data/`.

## Iteration

Render scripts accept `--preview`, which renders at quarter resolution, every 5th
frame, and skips the threshold/contour sweep — fast turnaround for tuning the
transfer function and isosurface levels in `settings/segment1.py` /
`settings/segment2.py`.

```bash
make preview      # writes a sparse set of preview frames; no MP4 assembly
```

After tweaking `settings/`, run `make` for a full render.

## Repository layout

```
.
├── Makefile / run.sh           # build orchestrator
├── setup.sh                    # one-shot install + venv
├── requirements.txt            # Python deps for the host (Biopython, Pillow, …)
├── settings/                   # per-segment knobs (TFs, thresholds, camera path)
├── scripts/
│   ├── fetch_data.py           # downloads EMDB/RCSB; runs pdb2pqr + APBS locally
│   ├── pdb_to_vtk.py           # PDB → Cα-backbone .vtp + atoms-as-points .vtp
│   ├── render_segment1.py      # pvbatch — GroEL volume rendering
│   ├── render_segment2.py      # pvbatch — lysozyme APBS isosurfaces + surface
│   ├── make_titlecard.py       # PIL — inter-segment title card frames
│   └── assemble_video.sh       # ffmpeg — concat + crossfade → out/demo.mp4
├── data/                       # fetched on first run; gitignored
├── frames/                     # rendered PNGs; gitignored
└── out/                        # final MP4
```

## Dependencies

`setup.sh` installs all of these on macOS via Homebrew:

| Tool                       | Purpose                                      |
|----------------------------|----------------------------------------------|
| `paraview` (cask)          | `pvbatch` for headless rendering             |
| `ffmpeg`                   | Frame stitching, encoding, crossfades        |
| `gh`                       | GitHub repo + release management             |
| `brewsci/bio/apbs`         | Local APBS solver (see deviation note below) |
| `python3` + `.venv`        | Biopython, NumPy, Pillow, requests, pdb2pqr  |

`pvbatch` runs headlessly using ParaView's bundled OpenGL backend on macOS — no
`xvfb` needed. The bundled binary is symlinked to `bin/pvbatch` during setup.

## APBS deviation from original brief

The original brief specified the APBS-PDB2PQR REST API at
[server.poissonboltzmann.org](https://server.poissonboltzmann.org/) with no local
APBS install. As of this writing the public deployment's `env-config.js` points
the workflow URL at `http://apbs.127.0.0.1.xip.io/...` — a private Kubernetes
address that isn't routable from outside the operator's cluster. The brief's
documented manual fallback (run the web form, drop files in) hits the same
broken endpoint.

To produce a real Poisson–Boltzmann solution we run pdb2pqr (pip) and APBS
(`brewsci/bio/apbs`) locally. The pipeline still:

- caches results under `data/lysozyme/`
- skips re-running APBS if `1AKI.pqr` and `1AKI.dx` are already present (you can
  manually drop in pre-computed files and they'll be honored)

If a working public APBS service comes back, swapping `fetch_data.py`'s lysozyme
path back to HTTP submission is a self-contained change.

## Tuning the visuals

Everything that's plausibly worth tweaking lives in `settings/segment1.py` and
`settings/segment2.py`:

- volume-rendering color/opacity transfer-function control points
- ± isosurface thresholds and the threshold-sweep envelope
- camera distance, elevation, sweep extent
- background, ambient, light intensity
- output resolution, fps, segment durations

Render scripts read settings on each invocation, so the iteration loop is:
edit settings → `make preview` → eyeball → repeat → `make`.

## Known limitations

- The custom Cα backbone tube is a meaningful upgrade over default atom
  rendering but isn't a true ribbon (no helix/sheet differentiation). Acceptable
  for the demo's scope; would be the first upgrade for a v2.
- EMD-5001 is a ~4 Å class map. Volume rendering may look soft compared to
  higher-resolution chaperonin entries; swap the EMDB ID in `settings/segment1.py`
  and `fetch_data.py` if a sharper map is preferred.
- No GitHub Actions runner ships with this repo. A `render.yml` workflow would
  need a runner with ParaView + a GPU; left as a future addition.

## Reproducibility

- All hardcoded thresholds, TF control points, and camera parameters live in
  `settings/`, not buried in render scripts.
- Fetched data (`*.map`, `*.pdb`, `*.pqr`, `*.dx`) is gitignored and repopulated
  by `scripts/fetch_data.py`.
- `make distclean` wipes `data/`, `frames/`, `out/`, and `.venv/` for a fully
  cold rebuild.
