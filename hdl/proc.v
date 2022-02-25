module proc
    #(parameter DATA_WIDTH=32,
      parameter CMD_WIDTH=128,
      parameter CMD_ADDR_WIDTH=8
      parameter REG_ADDR_WIDTH=4
      parameter SYNC_BARRIER_WIDTH=8)(
      input clk,
      input reset,
      input write_prog_enable,
      input cmd_addr[CMD_ADDR_WIDTH-1:0],
      input cmd_data[CMD_WIDTH-1:0],
      input sync_enable,
      input fproc_enable,
      output cmd_out[71:0],
      output cstrobe,
      output sync_barrier[SYNC_BARRIER_WIDTH-1:0],
      output sync_barrier_en_out,
      output fproc_id[SYNC_BARRIER_WIDTH-1:0],
      output fproc_en_out);

      wire[CMD_WIDTH-1:0] cmd_buf_out;
      wire[CMD_ADDR_WIDTH-1:0] cmd_buf_read_addr;
      wire[DATA_WIDTH-1:0] alu_out, reg_file_in, reg_file_out0, reg_file_out1, alu_in0, alu_in1, qckl_out;
      wire qclk_resetin;
      wire inst_ptr_resetin;
      wire inst_ptr_load_en;
      wire inst_ptr_enable;
      
      //control wires
      wire[2:0] alu_opcode;
      wire c_strobe_enable,
      wire alu_in0_sel;
      wire alu_in1_sel;
      wire alu_opcode;
      wire reg_write_en;
      wire reg_write_sel;
      wire[2:0] inst_ptr_en_sel;
      wire[1:0] inst_ptr_load_en;
      wire qclk_load_en;
      wire sync_out_ready;
      wire fproc_out_ready;

      //cmd buffer datapath
      wire[CMD_ADDR_WIDTH-1:0] instr_ptr_load_val;
      wire[DATA_WIDTH-1:0] alu_cmd_data_in0;
      wire[DATA_WIDTH-1:0] pulse_cmd_time;

      localparam OPCODE_WIDTH = 8;
      assign instr_ptr_load_val = cmd_buf_out[CMD_WIDTH-1-OPCODE_WIDTH:CMD_WIDTH-CMD_ADDR_WIDTH-OPCODE_WIDTH];

      cmd_mem cmd_buffer#(.CMD_WIDTH(CMD_WIDTH), .ADDR_WIDTH(CMD_ADDR_WIDTH))(
                .clk(clk), .write_enable(write_prog_enable), .read_addr(cmd_buf_read_addr),
                .write_addr(cmd_addr), .cmd_in(cmd_data), .cmd_out(cmd_buf_out));
      instr_ptr instr#(.WIDTH(CMD_ADDR_WIDTH))(.clk(clk), .enable(inst_ptr_enable), .reset(reset),
                .load_val(cmd_buf_out[CMD_WIDTH-8:CMD_WIDTH-7-CMD_ADDR_WIDTH]), 




endmodule
