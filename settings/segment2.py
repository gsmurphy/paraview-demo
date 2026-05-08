"""Segment 2 — Lysozyme (PDB 1AKI) APBS electrostatic potential.

All tunable parameters live here. Edit, re-run `make`, regenerate.
"""

# --- I/O paths (relative to repo root) ---------------------------------------
DX_FILE       = "data/lysozyme/1AKI.dx"
VTI_FILE      = "data/lysozyme/1AKI.vti"   # ParaView reads this, converted from .dx
PQR_FILE      = "data/lysozyme/1AKI.pqr"
BACKBONE_VTP  = "data/lysozyme/1AKI_backbone.vtp"
ATOMS_VTP     = "data/lysozyme/1AKI_atoms.vtp"
FRAMES_DIR    = "frames/segment2"

# --- Output dimensions -------------------------------------------------------
RESOLUTION    = (1920, 1080)
FPS           = 30
DURATION_S    = 10.0
NUM_FRAMES    = int(FPS * DURATION_S)        # 300
PREVIEW_RES   = (480, 270)
PREVIEW_STRIDE = 5

# --- Diverging color map for surface coloring (kT/e units) -------------------
# APBS convention: red = negative potential, blue = positive potential.
DIVERGING_COLOR_POINTS = [
    (-5.0, 0.85, 0.15, 0.10),    # saturated red (negative)
    (-2.0, 0.95, 0.45, 0.30),    # orange-red
    ( 0.0, 0.96, 0.96, 0.96),    # near-white
    ( 2.0, 0.30, 0.55, 0.95),    # light blue
    ( 5.0, 0.10, 0.30, 0.85),    # saturated blue (positive)
]

# --- Molecular surface (electrostatic-colored) -------------------------------
# Smooth Gaussian-splatted molecular envelope; isolevel chosen low enough to
# join atom blobs into a single solvent-accessible-style surface.
SURFACE_SPLAT_RADIUS        = 0.05   # fraction of bounding box
SURFACE_ISOLEVEL_FRAC       = 0.20   # of the gauss density max — tighter envelope
SURFACE_OPACITY             = 0.45
SURFACE_COLOR_FALLBACK      = (0.78, 0.80, 0.85)

# --- ± Isosurfaces -----------------------------------------------------------
# Threshold values in kT/e (APBS convention). Lysozyme is a strong cation
# (pI ~11) so + thresholds need to be large to localize features; - is rarer.
# Sweep ramps from TIGHT (small features) → LOOSE (broader envelope) → TIGHT.
ISO_POSITIVE_TIGHT = +6.0
ISO_POSITIVE_LOOSE = +2.5
ISO_NEGATIVE_TIGHT = -3.0
ISO_NEGATIVE_LOOSE = -1.0

ISO_POSITIVE_COLOR = (0.20, 0.45, 0.95)
ISO_NEGATIVE_COLOR = (0.95, 0.25, 0.20)
ISO_OPACITY        = 0.55

# Sweep timeline
SWEEP_ENABLED  = True
SWEEP_START_S  = 3.0
SWEEP_END_S    = 7.0

# --- Backbone tube (faint, behind the surface) -------------------------------
BACKBONE_COLOR   = (0.55, 0.60, 0.70)
BACKBONE_OPACITY = 0.35

# --- Camera ------------------------------------------------------------------
CAMERA_AXIS         = (0.0, 1.0, 0.0)
CAMERA_DISTANCE     = 95.0                    # Å, tuned for lysozyme
CAMERA_ELEVATION    = 8.0
CAMERA_START_AZIM   = 0.0
CAMERA_END_AZIM     = 140.0
CAMERA_VIEW_UP      = (0.0, 1.0, 0.0)

# --- Background / lighting ---------------------------------------------------
BACKGROUND       = (0.02, 0.02, 0.03)
LIGHT_INTENSITY  = 1.10
AMBIENT          = 0.20
