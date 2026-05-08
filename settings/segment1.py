"""Segment 1 — GroEL cryo-EM density (EMD-5001) + fitted atomic model (PDB 3CAU).

All tunable parameters live here. Edit, re-run `make`, regenerate.
"""

# --- I/O paths (relative to repo root) ---------------------------------------
DENSITY_MAP   = "data/groel/EMD-5001.map"
BACKBONE_VTP  = "data/groel/3CAU_backbone.vtp"
ATOMS_VTP     = "data/groel/3CAU_atoms.vtp"
FRAMES_DIR    = "frames/segment1"

# --- Output dimensions -------------------------------------------------------
RESOLUTION    = (1920, 1080)
FPS           = 30
DURATION_S    = 10.0
NUM_FRAMES    = int(FPS * DURATION_S)        # 300
PREVIEW_RES   = (480, 270)
PREVIEW_STRIDE = 5                            # render 1 of every N frames

# --- Volume rendering --------------------------------------------------------
# Grayscale-to-amber transfer function. Densities below FLOOR are fully
# transparent; control points are normalized 0..1 against the map's data range.
TF_COLOR_POINTS = [
    # (normalized_scalar, R, G, B)
    (0.00, 0.05, 0.05, 0.07),
    (0.30, 0.20, 0.18, 0.18),
    (0.55, 0.55, 0.40, 0.25),
    (0.80, 0.95, 0.78, 0.45),
    (1.00, 1.00, 0.92, 0.70),
]
TF_OPACITY_POINTS = [
    # (normalized_scalar, opacity)
    (0.00, 0.00),
    (0.25, 0.00),
    (0.40, 0.08),
    (0.60, 0.30),
    (0.85, 0.55),
    (1.00, 0.78),
]

# Optional contour-level sweep: shifts the opacity curve outward over time
# so the inner chamber becomes visible mid-segment.
SWEEP_ENABLED  = True
SWEEP_START_S  = 3.0
SWEEP_END_S    = 7.0
SWEEP_OPACITY_SHIFT = -0.10   # subtract from each opacity control point at peak

# --- Atomic model styling ----------------------------------------------------
# 3CAU is a Cα-only model, so atoms = backbone beads. Keep them tiny so the
# volume-rendered density is the dominant visual; the tube provides the trace.
BACKBONE_COLOR    = (0.78, 0.88, 1.00)        # cool off-white
BACKBONE_OPACITY  = 0.55
BACKBONE_TUBE_R   = 1.0
ATOM_COLOR        = (0.85, 0.92, 1.00)
ATOM_OPACITY      = 0.40
ATOM_SCALE        = 0.15                      # multiplier on per-atom radius

# --- Camera ------------------------------------------------------------------
# The barrel's long axis is roughly along Z in the EMD-5001 / 3CAU pair; the
# camera orbits around that axis with eased angular velocity.
CAMERA_AXIS         = (0.0, 0.0, 1.0)
CAMERA_DISTANCE     = 320.0                   # Å, tuned for GroEL
CAMERA_ELEVATION    = 12.0                    # degrees off equator
CAMERA_START_AZIM   = 0.0
CAMERA_END_AZIM     = 130.0                   # ~third of a turn
CAMERA_VIEW_UP      = (0.0, 0.0, 1.0)

# --- Background / lighting ---------------------------------------------------
BACKGROUND       = (0.02, 0.02, 0.03)
LIGHT_INTENSITY  = 1.05
AMBIENT          = 0.18
