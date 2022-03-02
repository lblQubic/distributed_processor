`ifndef instr_params_vh
`define instr_params_vh

//ALU parameters
parameter ALU_ID = 3'b000;
parameter ALU_ADD = 3'b001;
parameter ALU_SUB = 3'b010;
parameter ALU_EQ = 3'b011;
parameter ALU_LE = 3'b100;
parameter ALU_GE = 3'b101;
parameter ALU_0 = 3'b111;

//in general: first 5 bits are opcode, followed by 3 bit ALU opcode
parameter PULSE_I = 5'b00000;

parameter REG_I_ALU = 5'b00001; //|opcode[8]|cmd_value[32]|reg_write_addr[4] 
parameter REG_ALU = 5'b00010; //|opcode[8]|reg_addr[4]|reg_addr[4]
parameter JUMP_I = 5'b00011; //|opcode[8]|cmd_value[32]|reg_addr[4]
parameter JUMP_COND_I = 5'b00100; //|opcode[8]|cmd_value[32]|reg_addr[4]
parameter JUMP_COND = 5'b00101; //jump address is always immediate
parameter READ_FPROC = 5'b00110;
parameter JUMP_I_FPROC = 5'b00111;
parameter JUMP_FPROC = 5'b00111;
parameter INC_QCLK_I = 5'b01000;
parameter INC_QCLK = 5'b01001;
parameter SYNC = 5'b01010;
parameter REG_WRITE_I = 5'b01011;

`endif
