module proc
    #(parameter DATA_WIDTH=32,
      parameter CMD_WIDTH=128,
      parameter CMD_ADDR_WIDTH=8
      parameter REG_ADDR_WIDTH=4
      parameter SYNC_BARRIER_WIDTH=8)(
      input clk,
      input reset,
      input write_prog_enable,
      input cmd_addr[ADDR_WIDTH-1:0],
      input cmd_data[CMD_WIDTH-1:0],
      input sync_enable,
      input fproc_enable,
      output cmd_out[CMD_WIDTH-1:0],
      output cstrobe,
      output sync_barrier[SYNC_BARRIER_WIDTH-1:0],
      output sync_barrier_en_out,
      output fproc_id[SYNC_BARRIER_WIDTH-1:0],
      output fproc_en_out);

      wire[CMD_WIDTH-1:0] cmd_buf_out;
      wire[CMD_ADDR_WIDTH-1:0] cmd_buf_read_addr;
      wire[DATA_WIDTH-1:0] alu_out, reg_file_out0, reg_file_out1, alu_in0, alu_in1, qckl_out;
      wire qclk_resetin;
      wire pc_resetin;
      wire inst_ptr_load_en;
      wire inst_ptr_enable;
      wire inst_ptr_load_val;
      
      wire[2:0] alu_opcode;



endmodule
