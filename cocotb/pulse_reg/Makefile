SIM ?= verilator
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES += $(PWD)/../../hdl/pulse_reg.v
EXTRA_ARGS += --trace --trace-structs
TOPLEVEL = pulse_reg
#COMPILE_ARGS += -Wno

MODULE = test_pulse_reg

include $(shell cocotb-config --makefiles)/Makefile.sim
