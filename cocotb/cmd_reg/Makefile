SIM ?= verilator
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES += $(PWD)/../../hdl/cmd_reg.v
EXTRA_ARGS += --trace --trace-structs
TOPLEVEL = cmd_reg
#COMPILE_ARGS += -Wno

MODULE = test_cmd_reg

include $(shell cocotb-config --makefiles)/Makefile.sim
