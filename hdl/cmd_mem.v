module cmd_mem
    #(parameter CMD_WIDTH=128,
      parameter ADDR_WIDTH=8)(
      input clk,
      input write_enable,
      input[ADDR_WIDTH-1:0] read_address,
      input[ADDR_WIDTH-1:0] write_address,
      input[CMD_WIDTH-1:0] cmd_in,
      output[CMD_WIDTH-1:0] cmd_out);

    reg[CMD_WIDTH-1:0] data[2**ADDR_WIDTH-1:0];

    reg[ADDR_WIDTH-1:0] cur_read_addr;

    assign cmd_out = data[cur_read_addr];

    always @(posedge clk)begin
        cur_read_addr <= read_address;
        if(write_enable)
            data[write_address] <= cmd_in;

    end

endmodule
     
