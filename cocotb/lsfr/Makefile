SIM ?= verilator
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES += $(PWD)/../../hdl/lfsr.sv
EXTRA_ARGS += --trace --trace-structs
TOPLEVEL = lfsr
#COMPILE_ARGS += -Wno

MODULE = test_lfsr

include $(shell cocotb-config --makefiles)/Makefile.sim
