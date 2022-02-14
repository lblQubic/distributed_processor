module proc
    #(parameter DATA_WIDTH=32,
      parameter CMD_WIDTH=128,
      parameter CMD_ADDR_WIDTH=8
      parameter REG_ADDR_WIDTH=4)(
      input reset,
      input write_prog_enable,
      input cmd_addr[ADDR_WIDTH-1:0],
      input cmd_data[CMD_WIDTH:0]);


endmodule
