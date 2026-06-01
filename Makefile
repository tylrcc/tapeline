# mac engine build + sim. needs icarus verilog (iverilog/vvp) and python3.
# `make sim` is the one people want: it regenerates vectors from the golden
# model and runs the self-checking testbench against the rtl.

IVERILOG ?= iverilog
VVP      ?= vvp
PYTHON   ?= python3

RTL      := rtl/mac_engine.v rtl/tick_sync_fifo.v
TB       := tb/mac_engine_tb.v
BUILD    := build
VVP_OUT  := $(BUILD)/mac_engine_tb.vvp
VECTORS  := sim/vectors.txt

.PHONY: all sim vectors lint test clean

all: sim

# regenerate the test vectors from the python source of truth
vectors:
	$(PYTHON) sim/gen_vectors.py

$(VECTORS): sim/gen_vectors.py sim/reference.py
	$(PYTHON) sim/gen_vectors.py

# compile + run the self-checking testbench
sim: $(VECTORS) | $(BUILD)
	$(IVERILOG) -g2012 -Wall -o $(VVP_OUT) -s mac_engine_tb $(RTL) $(TB)
	$(VVP) $(VVP_OUT)

# syntax / elaboration check only, no run. cheap to keep in the inner loop.
lint: | $(BUILD)
	$(IVERILOG) -g2012 -Wall -t null $(RTL) $(TB)

# python-side tests for the golden model
test:
	$(PYTHON) -m pytest -q sim

$(BUILD):
	mkdir -p $(BUILD)

clean:
	rm -rf $(BUILD) $(VECTORS) sim/__pycache__ host/__pycache__
