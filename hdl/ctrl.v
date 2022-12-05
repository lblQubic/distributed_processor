module ctrl (
    input clk,
    input reset,
    input[7:0] opcode,
    input fproc_ready,
    input sync_enable,
    input cstrobe_in,
    output [2:0] alu_opcode,
    output reg c_strobe_enable,
    output alu_in0_sel,
    output reg[1:0] alu_in1_sel,
    output reg reg_write_en,
    output reg instr_ptr_en,
    output reg[1:0] instr_ptr_load_en,
    output reg qclk_load_en,
    output reg sync_out_ready,
    output reg fproc_out_ready,
    output reg write_pulse_en);

    reg[3:0] state, next_state;

    localparam INIT_STATE = 0;
    localparam ALU_PROC_STATE = 1;
    localparam ALU_FPROC_WAIT_STATE = 2;
    localparam JUMP_FPROC_WAIT_STATE = 3;
    localparam SYNC_WAIT_STATE = 4;
    localparam INC_QCLK_STATE = 5;
    localparam JUMP_COND_STATE = 6;
    localparam PULSE_WRITE=7;
    localparam INSTR_PTR_LOAD_EN_FALSE=8;
	localparam REG_ALU=9;
	localparam ALU_IN1_REG_SEL=10;
	localparam JUMP_I=11;
localparam INSTR_PTR_LOAD_EN_TRUE=12;
localparam JUMP_COND=13;
localparam INC_QCLK=15;
localparam PULSE_WRITE_TRIG=16;
localparam ALU_FPROC=16;
localparam JUMP_FPROC=17;
localparam INSTR_PTR_LOAD_EN_ALU=18;
localparam ALU_IN1_FPROC_SEL=19;
localparam ALU_IN1_QCLK_SEL=20;


parameter INST_PTR_DEFAULT_EN = 2'b00;
parameter INST_PTR_SYNC_EN = 2'b01;
parameter INST_PTR_FPROC_EN = 2'b10;
parameter INST_PTR_PULSE_EN = 2'b11;

parameter CMD_BUFFER_REGWRITE_SEL = 0;
parameter ALU_REGWRITE_SEL = 1;
parameter ALU_IN0_CMD_SEL = 0;
parameter ALU_IN0_REG_SEL = 1;
parameter ALU_IN1_QCLK_SEL = 2'b00;
parameter ALU_IN1_REG_SEL = 2'b01;
parameter ALU_IN1_FPROC_SEL = 2'b10;
parameter INSTR_PTR_LOAD_EN_ALU = 2'b10;
parameter INSTR_PTR_LOAD_EN_TRUE = 2'b01;
parameter INSTR_PTR_LOAD_EN_FALSE = 2'b00;

//ALU parameters
parameter ALU_ID0 = 3'b000;
parameter ALU_ID1 = 3'b110;
parameter ALU_ADD = 3'b001;
parameter ALU_SUB = 3'b010;
parameter ALU_EQ = 3'b011;
parameter ALU_LE = 3'b100;
parameter ALU_GE = 3'b101;
parameter ALU_0 = 3'b111;

//in general: first 5 bits are opcode, followed by 3 bit ALU opcode

//5-bit opcode: 4-bit operation followed by LSB select for ALU_IN1 (0 for cmd, 1 for reg)
parameter PULSE_WRITE = 4'b1000;
parameter PULSE_WRITE_TRIG = 4'b1001;
parameter REG_ALU = 4'b0001; //|opcode[8]|cmd_value[32]|reg1_addr[4]|reg_write_addr[4]
parameter JUMP_I = 4'b0010; //|opcode[8]|cmd_value[32]|reg_addr[4]
parameter JUMP_COND = 4'b0011; //jump address is always immediate
parameter ALU_FPROC = 4'b0100;
parameter JUMP_FPROC = 4'b0101;
parameter INC_QCLK = 4'b0110;
parameter SYNC = 4'b0111;




    /*
    * states:
    *   INIT: new instruction clocked out; depending on opcode:
    *       - halt PC and wait for cstrobe (same behavior as single cycle); always transition to itself
    *       - halt PC, read regs/set up inputs to ALU, transition to ALU_PROC_STATE 
    *       - pulse_write: enable pulse_write regs, enable PC, transition to itself
    *       - fproc or sync; transition to fproc/sync wait states respectively
    *   ALU_PROC_STATE
    *       - clock in register writes and increment instr_ptr
    *   FPROC_WAIT_STATE
    *       - check ready; if 0 stay here, if 1 regwrite or jump according to opcode
    *   SYNC_WAIT
    *   PULSE_WAIT
    *
    */

    //`include "../hdl/ctrl_params.vh"
    //`include "../hdl/instr_params.vh"


    assign alu_opcode = opcode[2:0];
    assign alu_in0_sel = opcode[3];

    always @(posedge clk) begin
        if(reset)
            state <= INIT_STATE;
        else
            state <= next_state;
    end

    always @(*) begin
        if(state == INIT_STATE) begin
            case(opcode[7:4])
                //PULSE_I : begin
                //    next_state = INIT_STATE;
                //    c_strobe_enable = ~reset;
                //    instr_ptr_load_en = 0;
                //    instr_ptr_en = cstrobe_in;
                //    sync_out_ready = 0;
                //    fproc_out_ready = 0;
                //    reg_write_en = 0;
                //    qclk_load_en = 0;
                //end

                PULSE_WRITE : begin
                    next_state = INIT_STATE;
                    c_strobe_enable = 0;
                    instr_ptr_load_en = INSTR_PTR_LOAD_EN_FALSE;
                    instr_ptr_en = 1;
                    sync_out_ready = 0;
                    fproc_out_ready = 0;
                    reg_write_en = 0;
                    qclk_load_en = 0;
                    write_pulse_en = 1;
                end

                PULSE_WRITE_TRIG : begin
                    next_state = INIT_STATE;
                    c_strobe_enable = ~reset;
                    instr_ptr_load_en = INSTR_PTR_LOAD_EN_FALSE;
                    instr_ptr_en = cstrobe_in;
                    sync_out_ready = 0;
                    fproc_out_ready = 0;
                    reg_write_en = 0;
                    qclk_load_en = 0;
                    write_pulse_en = 1;
                end

                REG_ALU : begin
                    next_state = ALU_PROC_STATE;
                    alu_in1_sel = ALU_IN1_REG_SEL;
                    //defaults:
                    reg_write_en = 0;
                    c_strobe_enable = 0;
                    instr_ptr_load_en = INSTR_PTR_LOAD_EN_FALSE;
                    instr_ptr_en = 0;
                    qclk_load_en = 0;
                    sync_out_ready = 0;
                    fproc_out_ready = 0;
                    write_pulse_en = 0;
                end

                JUMP_I : begin
                    next_state = INIT_STATE;
                    //defaults:
                    reg_write_en = 0;
                    c_strobe_enable = 0;
                    instr_ptr_load_en = INSTR_PTR_LOAD_EN_TRUE;
                    instr_ptr_en = 1;
                    qclk_load_en = 0;
                    sync_out_ready = 0;
                    fproc_out_ready = 0;
                    write_pulse_en = 0;
                end

                JUMP_COND : begin //this must use a cmp opcode or bad things will happen!
                    next_state = JUMP_COND_STATE;
                    alu_in1_sel = ALU_IN1_REG_SEL;
                    //defaults:
                    reg_write_en = 0;
                    c_strobe_enable = 0;
                    instr_ptr_load_en = INSTR_PTR_LOAD_EN_FALSE;
                    instr_ptr_en = 0;
                    qclk_load_en = 0;
                    sync_out_ready = 0;
                    fproc_out_ready = 0;
                    write_pulse_en = 0;
                end

                INC_QCLK : begin //this can use an ADD, SUB, or ID opcode
                    next_state = INC_QCLK_STATE;
                    alu_in1_sel = ALU_IN1_QCLK_SEL;
                    //defaults:
                    c_strobe_enable = 0;
                    instr_ptr_load_en = INSTR_PTR_LOAD_EN_FALSE;
                    instr_ptr_en = 0;
                    sync_out_ready = 0;
                    fproc_out_ready = 0;
                    reg_write_en = 0;
                    qclk_load_en = 0;
                    write_pulse_en = 0;
                end

                ALU_FPROC : begin
                    next_state = ALU_FPROC_WAIT_STATE;
                    fproc_out_ready = 1;
                    //defaults:
                    c_strobe_enable = 0;
                    instr_ptr_load_en = INSTR_PTR_LOAD_EN_FALSE;
                    instr_ptr_en = 0;
                    sync_out_ready = 0;
                    reg_write_en = 0;
                    qclk_load_en = 0;
                    write_pulse_en = 0;
                end

                JUMP_FPROC : begin
                    next_state = JUMP_FPROC_WAIT_STATE;
                    fproc_out_ready = 1;
                    //defaults:
                    c_strobe_enable = 0;
                    instr_ptr_load_en = INSTR_PTR_LOAD_EN_FALSE;
                    instr_ptr_en = 0;
                    sync_out_ready = 0;
                    reg_write_en = 0;
                    qclk_load_en = 0;
                    write_pulse_en = 0;
                end

                default : begin
                    next_state = INIT_STATE;
                    instr_ptr_load_en = INSTR_PTR_LOAD_EN_FALSE;
                    write_pulse_en = 0;
                    instr_ptr_en = 0;
                    sync_out_ready = 0;
                    reg_write_en = 0;
                    qclk_load_en = 0;
                    c_strobe_enable = 0;
                    fproc_out_ready = 0;
                end

            endcase

        end

        else if(state == ALU_PROC_STATE) begin
            next_state = INIT_STATE;
            reg_write_en = 1;
            c_strobe_enable = 0;
            instr_ptr_load_en = INSTR_PTR_LOAD_EN_FALSE;
            instr_ptr_en = 1;
            qclk_load_en = 0;
            sync_out_ready = 0;
            fproc_out_ready = 0;
            write_pulse_en = 0;
        end

        else if(state == INC_QCLK_STATE) begin
            next_state = INIT_STATE;
            reg_write_en = 0;
            c_strobe_enable = 0;
            instr_ptr_load_en = INSTR_PTR_LOAD_EN_FALSE;
            instr_ptr_en = 1;
            qclk_load_en = 1;
            sync_out_ready = 0;
            fproc_out_ready = 0;
            write_pulse_en = 0;
        end

        else if(state == JUMP_COND_STATE) begin
            next_state = INIT_STATE;
            reg_write_en = 0;
            c_strobe_enable = 0;
            instr_ptr_load_en = INSTR_PTR_LOAD_EN_ALU;
            instr_ptr_en = 1;
            qclk_load_en = 0;
            sync_out_ready = 0;
            fproc_out_ready = 0;
            write_pulse_en = 0;
        end

        else if(state == ALU_FPROC_WAIT_STATE) begin
            if(fproc_ready)
                next_state = ALU_PROC_STATE;
            else
                next_state = ALU_FPROC_WAIT_STATE;
            
            instr_ptr_load_en = INSTR_PTR_LOAD_EN_FALSE;
            alu_in1_sel = ALU_IN1_FPROC_SEL;

            reg_write_en = 0;
            instr_ptr_en = 0;
            c_strobe_enable = 0;
            qclk_load_en = 0;
            sync_out_ready = 0;
            fproc_out_ready = 0;
            write_pulse_en = 0;
        end

        else if(state == JUMP_FPROC_WAIT_STATE) begin
            if(fproc_ready)
                next_state = JUMP_COND_STATE;
            else
                next_state = JUMP_FPROC_WAIT_STATE;
            
            instr_ptr_load_en = INSTR_PTR_LOAD_EN_FALSE;
            alu_in1_sel = ALU_IN1_FPROC_SEL;

            reg_write_en = 0;
            instr_ptr_en = 0;
            c_strobe_enable = 0;
            qclk_load_en = 0;
            sync_out_ready = 0;
            fproc_out_ready = 0;
            write_pulse_en = 0;
        end
        
    end

endmodule


