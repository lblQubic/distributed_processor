`include "instr_params.vh"
`include "ctrl_params.vh"
module ctrl(
    input[7:0] opcode,
    output[2:0] alu_opcode,
    output c_strobe_enable,
    output alu_in0_sel,
    output alu_in1_sel,
    output reg_write_en,
    output[2:0] instr_ptr_en_sel,
    output[1:0] instr_ptr_load_en,
    output qclk_load_en,
    output sync_out_ready,
    output fproc_out_ready);


    assign alu_opcode = opcode[2:0];

    always @(*) begin
        case(opcode[7:3])
            PULSE_I : begin
                c_strobe_enable = 1;
                //defaults:
                instr_ptr_load_en = 0;
                instr_ptr_en_sel = INST_PTR_DEFAULT_EN;
                qclk_load_en = 0;
                sync_out_ready = 0;
                fproc_out_ready = 0;
                reg_write_en = 0;
            end
                
            REG_WRITE_I : begin
                reg_write_en = 1;
                //reg_write_sel = CMD_BUFFER_REGWRITE_SEL;
                //defaults:
                c_strobe_enable = 0;
                instr_ptr_load_en = 0;
                instr_ptr_en_sel = INST_PTR_DEFAULT_EN;
                qclk_load_en = 0;
                sync_out_ready = 0;
                fproc_out_ready = 0;
            end

            REG_I_ALU : begin
                alu_in0_sel = ALU_IN0_CMD_SEL;
                alu_in1_sel = ALU_IN1_REG_SEL;
                reg_write_en = 1;
                //reg_write_sel = ALU_REGWRITE_SEL;
                //defaults:
                c_strobe_enable = 0;
                instr_ptr_load_en = 2'b0;
                instr_ptr_en_sel = INST_PTR_DEFAULT_EN;
                qclk_load_en = 0;
                sync_out_ready = 0;
                fproc_out_ready = 0;
            end 

            REG_ALU : begin
                alu_in0_sel = ALU_IN0_REG_SEL;
                alu_in1_sel = ALU_IN1_REG_SEL;
                reg_write_en = 1;
                //reg_write_sel = ALU_REGWRITE_SEL;
                //defaults:
                c_strobe_enable = 0;
                instr_ptr_load_en = 2'b0;
                instr_ptr_en_sel = INST_PTR_DEFAULT_EN;
                qclk_load_en = 0;
                sync_out_ready = 0;
                fproc_out_ready = 0;
            end

            JUMP_I : begin
                instr_ptr_load_en = 2'b01;
                //defaults:
                c_strobe_enable = 0;
                instr_ptr_en_sel = INST_PTR_DEFAULT_EN;
                qclk_load_en = 0;
                sync_out_ready = 0;
                fproc_out_ready = 0;
                reg_write_en = 0;
            end

            JUMP_COND_I : begin //this must use a cmp opcode or bad things will happen!
                instr_ptr_load_en = INSTR_PTR_LOAD_EN_ALU;
                alu_in0_sel = ALU_IN0_CMD_SEL;
                alu_in1_sel = ALU_IN1_REG_SEL;
                //defaults:
                c_strobe_enable = 0;
                instr_ptr_en_sel = INST_PTR_DEFAULT_EN;
                qclk_load_en = 0;
                sync_out_ready = 0;
                fproc_out_ready = 0;
                reg_write_en = 0;
            end

            INC_QCLK : begin //this can use an ADD, SUB, or ID opcode
                alu_in0_sel = ALU_IN0_REG_SEL;
                alu_in1_sel = ALU_IN1_QCLK_SEL;
                qclk_load_en = 1;
                //defaults:
                c_strobe_enable = 0;
                instr_ptr_load_en = 2'b00;
                instr_ptr_en_sel = INST_PTR_DEFAULT_EN;
                sync_out_ready = 0;
                fproc_out_ready = 0;
                reg_write_en = 0;
            end

            INC_QCLK_I : begin //this can use an ADD, SUB, or ID opcode
                alu_in0_sel = ALU_IN0_CMD_SEL;
                alu_in1_sel = ALU_IN1_QCLK_SEL;
                qclk_load_en = 1;
                //defaults:
                c_strobe_enable = 0;
                instr_ptr_load_en = 2'b00;
                instr_ptr_en_sel = INST_PTR_DEFAULT_EN;
                sync_out_ready = 0;
                fproc_out_ready = 0;
                reg_write_en = 0;
            end 

            default: begin
                c_strobe_enable = 0;
                instr_ptr_load_en = 2'b00;
                instr_ptr_en_sel = INST_PTR_DEFAULT_EN;
                qclk_load_en = 0;
                sync_out_ready = 0;
                fproc_out_ready = 0;
                reg_write_en = 0;
            end

        endcase


