# ParaView protein demo — end-to-end build.
#
# Usage:
#   make            # full pipeline → out/demo.mp4
#   make preview    # fast preview (quarter res, every Nth frame)
#   make clean      # delete frames + out (keeps cached data/)
#   make distclean  # also delete cached data/ and .venv/
#
# The pipeline:
#   1. Activate .venv
#   2. fetch_data.py downloads + caches all source data
#   3. pdb_to_vtk.py converts PDBs to VTK geometry
#   4. render_segment{1,2}.py write PNG frames via pvbatch
#   5. make_titlecard.py renders the inter-segment title card
#   6. assemble_video.sh stitches frames + title card → out/demo.mp4

VENV       := .venv
PYTHON     := $(VENV)/bin/python
PVBATCH    := bin/pvbatch
SCRIPTS    := scripts

DATA_GROEL := data/groel/EMD-5001.map data/groel/3CAU.pdb
DATA_LYSO  := data/lysozyme/1AKI.pdb data/lysozyme/1AKI.pqr data/lysozyme/1AKI.dx

VTK_GROEL  := data/groel/3CAU_backbone.vtp data/groel/3CAU_atoms.vtp
VTK_LYSO   := data/lysozyme/1AKI_backbone.vtp data/lysozyme/1AKI_atoms.vtp data/lysozyme/1AKI.vti

FRAMES_S1   := frames/segment1/.done
FRAMES_S2   := frames/segment2/.done
FRAMES_TITLE := frames/titlecard/.done

OUTPUT     := out/demo.mp4

.PHONY: all preview clean distclean fetch geometry frames video

all: $(OUTPUT)

preview: PREVIEW_FLAG := --preview
preview: $(FRAMES_S1) $(FRAMES_S2) $(FRAMES_TITLE)
	@echo "Preview frames written to frames/. Inspect, then run 'make' for the full render."

# 1. Fetch data ---------------------------------------------------------------
fetch: $(DATA_GROEL) $(DATA_LYSO)

$(DATA_GROEL) $(DATA_LYSO):
	$(PYTHON) $(SCRIPTS)/fetch_data.py

# 2. PDB → VTK geometry -------------------------------------------------------
geometry: $(VTK_GROEL) $(VTK_LYSO)

$(VTK_GROEL): data/groel/3CAU.pdb
	$(PYTHON) $(SCRIPTS)/pdb_to_vtk.py --pdb $< --out-prefix data/groel/3CAU

data/lysozyme/1AKI_backbone.vtp data/lysozyme/1AKI_atoms.vtp: data/lysozyme/1AKI.pdb
	$(PYTHON) $(SCRIPTS)/pdb_to_vtk.py --pdb $< --out-prefix data/lysozyme/1AKI

data/lysozyme/1AKI.vti: data/lysozyme/1AKI.dx
	$(PYTHON) $(SCRIPTS)/dx_to_vti.py --dx $< --vti $@ --name potential

# 3. Render frames ------------------------------------------------------------
frames: $(FRAMES_S1) $(FRAMES_S2) $(FRAMES_TITLE)

$(FRAMES_S1): $(DATA_GROEL) $(VTK_GROEL) $(SCRIPTS)/render_segment1.py settings/segment1.py
	$(PVBATCH) $(SCRIPTS)/render_segment1.py $(PREVIEW_FLAG)
	@touch $@

$(FRAMES_S2): $(DATA_LYSO) $(VTK_LYSO) $(SCRIPTS)/render_segment2.py settings/segment2.py
	$(PVBATCH) $(SCRIPTS)/render_segment2.py $(PREVIEW_FLAG)
	@touch $@

$(FRAMES_TITLE): $(SCRIPTS)/make_titlecard.py
	$(PYTHON) $(SCRIPTS)/make_titlecard.py
	@touch $@

# 4. Assemble video -----------------------------------------------------------
video: $(OUTPUT)

$(OUTPUT): $(FRAMES_S1) $(FRAMES_S2) $(FRAMES_TITLE)
	bash $(SCRIPTS)/assemble_video.sh

# Clean targets ---------------------------------------------------------------
clean:
	rm -rf frames/segment1/*.png frames/segment2/*.png frames/titlecard/*.png
	rm -f frames/segment1/.done frames/segment2/.done frames/titlecard/.done
	rm -f $(OUTPUT)

distclean: clean
	rm -rf data/ .venv/
