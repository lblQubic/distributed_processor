module ctrl(
    input clk,
    input reset,
    input[7:0] opcode,
    input fproc_enable,
    input sync_enable,
    input cstrobe_in,
    output [2:0] alu_opcode,
    output reg c_strobe_enable,
    output reg alu_in0_sel,
    output reg alu_in1_sel,
    output reg reg_write_en,
    output reg instr_ptr_en,
    output reg[1:0] instr_ptr_load_en,
    output reg qclk_load_en,
    output reg sync_out_ready,
    output reg fproc_out_ready);

    reg[3:0] state, next_state;

    localparam INIT_STATE = 0;
    localparam ALU_PROC_STATE = 1;
    localparam FPROC_WAIT_STATE = 2;
    localparam SYNC_WAIT_STATE = 3;
    localparam INC_QCLK_STATE = 4;
    localparam JUMP_COND_STATE = 5;

    /*
    * states:
    *   INIT: new instruction clocked out; depending on opcode:
    *       - halt PC and wait for cstrobe (same behavior as current); always transition to itself
    *       - halt PC, clock in value(s) to ALU, transition to ALU_PROC_STATE state
    *       - fproc or sync; transition to fproc/sync wait states respectively
    *   ALU_PROC_STATE
    *       - enable or load_val into PC according to opcode, clock in registers, or load qclk value
    *   FPROC_WAIT_STATE
    *   SYNC_WAIT
    *   PULSE_WAIT
    *
    */

    `include "../hdl/ctrl_params.vh"
    `include "../hdl/instr_params.vh"


    assign alu_opcode = opcode[2:0];

    always @(posedge clk) begin
        if(reset)
            state <= INIT_STATE;
        else
            state <= next_state;
    end

    always_latch @(*) begin
        if(state == INIT_STATE) begin
            case(opcode[7:3])
                PULSE_I : begin
                    next_state = INIT_STATE;
                    c_strobe_enable = 1;
                    instr_ptr_load_en = 0;
                    instr_ptr_en = cstrobe_in;
                    sync_out_ready = 0;
                    fproc_out_ready = 0;
                    reg_write_en = 0;
                end

                REG_I_ALU : begin
                    next_state = ALU_PROC_STATE;
                    alu_in0_sel = ALU_IN0_CMD_SEL;
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

                REG_ALU : begin
                    next_state = ALU_PROC_STATE;
                    alu_in0_sel = ALU_IN0_REG_SEL;
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

                JUMP_COND_I : begin
                    next_state = JUMP_COND_STATE;
                    alu_in0_sel = ALU_IN0_CMD_SEL;
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

                JUMP_COND : begin //this must use a cmp opcode or bad things will happen!
                    next_state = JUMP_COND_STATE;
                    alu_in0_sel = ALU_IN0_REG_SEL;
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
                    alu_in0_sel = ALU_IN0_REG_SEL;
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

                INC_QCLK_I : begin //this can use an ADD, SUB, or ID opcode
                    next_state = INC_QCLK_STATE;
                    alu_in0_sel = ALU_IN0_CMD_SEL;
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

        //else if(state == FPROC_WAIT_STATE) begin
        //    reg_write_en = 0;
        //    c_strobe_enable = 0;
        //    instr_ptr_load_en = INSTR_PTR_LOAD_EN_ALU;
        //    instr_ptr_en = 0;
        //    qclk_load_en = 0;
        //    sync_out_ready = 0;
        //    fproc_out_ready = 0;
        //end
        
    end

endmodule
