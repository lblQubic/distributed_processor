module ctrl(
    input clk,
    input reset,
    input[7:0] opcode,
    input fproc_ready,
    input sync_enable,
    input cstrobe_in,
    output [2:0] alu_opcode,
    output reg c_strobe_enable,
    output reg alu_in0_sel,
    output reg[1:0] alu_in1_sel,
    output reg reg_write_en,
    output reg instr_ptr_en,
    output reg[1:0] instr_ptr_load_en,
    output reg qclk_load_en,
    output reg sync_out_ready,
    output reg fproc_out_ready);

    reg[3:0] state, next_state;

    localparam INIT_STATE = 0;
    localparam ALU_PROC_STATE = 1;
    localparam ALU_FPROC_WAIT_STATE = 2;
    localparam JUMP_FPROC_WAIT_STATE = 3;
    localparam SYNC_WAIT_STATE = 4;
    localparam INC_QCLK_STATE = 5;
    localparam JUMP_COND_STATE = 6;

    /*
    * states:
    *   INIT: new instruction clocked out; depending on opcode:
    *       - halt PC and wait for cstrobe (same behavior as single cycle); always transition to itself
    *       - halt PC, read regs/set up inputs to ALU, transition to ALU_PROC_STATE 
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
                PULSE_I : begin
                    next_state = INIT_STATE;
                    c_strobe_enable = 1;
                    instr_ptr_load_en = 0;
                    instr_ptr_en = cstrobe_in;
                    sync_out_ready = 0;
                    fproc_out_ready = 0;
                    reg_write_en = 0;
                    qclk_load_en = 0;
                end

                REG_ALU : begin
                    next_state = ALU_PROC_STATE;
                    alu_in1_sel = ALU_IN1_REG_SEL;
                    //defaults:
                    reg_write_en = 0;
                    c_strobe_enable = 0;
                    instr_ptr_load_en = 2'b0;
                    instr_ptr_en = 0;
                    qclk_load_en = 0;
                    sync_out_ready = 0;
                    fproc_out_ready = 0;
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
                end

                default : begin
                    next_state = INIT_STATE;
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
        end
        
    end

endmodule
