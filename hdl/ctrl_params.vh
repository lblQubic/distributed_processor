//`ifndef ctrl_params_vh
//`define ctrl_params_vh

parameter INST_PTR_DEFAULT_EN = 2'b00;
parameter INST_PTR_SYNC_EN = 2'b01;
parameter INST_PTR_FPROC_EN = 2'b10;

parameter CMD_BUFFER_REGWRITE_SEL = 0;
parameter ALU_REGWRITE_SEL = 1;
parameter ALU_IN0_CMD_SEL = 0;
parameter ALU_IN0_REG_SEL = 1;
parameter ALU_IN1_QCLK_SEL = 0;
parameter ALU_IN1_REG_SEL = 1;
parameter INSTR_PTR_LOAD_EN_ALU = 2'b10;



//`endif
