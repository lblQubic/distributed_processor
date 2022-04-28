SIM ?= icarus
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES += $(PWD)/../hdl/*.v
TOPLEVEL = proc
COMPILE_ARGS += -Wall

MODULE = test_proc

include $(shell cocotb-config --makefiles)/Makefile.sim
