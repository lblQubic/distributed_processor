SIM ?= verilator
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES += $(PWD)/../hdl/*.v
VERILOG_SOURCES += $(PWD)/../hdl/*.sv
TOPLEVEL = toplevel_sim
#COMPILE_ARGS += -Wno

MODULE = test_proc

include $(shell cocotb-config --makefiles)/Makefile.sim
