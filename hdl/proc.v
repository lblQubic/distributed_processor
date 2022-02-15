module proc
    #(parameter DATA_WIDTH=32,
      parameter CMD_WIDTH=128,
      parameter CMD_ADDR_WIDTH=8
      parameter REG_ADDR_WIDTH=4
      parameter SYNC_BARRIER_WIDTH=8)(
      input clk,
      input reset,
      input write_prog_enable,
      input enable,
      input sync_enable,
      input fproc_enable,
      input cmd_addr[ADDR_WIDTH-1:0],
      input cmd_data[CMD_WIDTH-1:0],
      output cmd_out[CMD_WIDTH-1:0],
      output cstrobe,
      output sync_barrier[SYNC_BARRIER_WIDTH-1:0],
      output sync_barrier_en,
      output fproc_id[SYNC_BARRIER_WIDTH-1:0],
      output fproc_en_out);


endmodule
