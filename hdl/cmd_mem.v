module cmd_mem
    #(parameter CMD_WIDTH,
      parameter ADDR_WIDTH)(
      input clk,
      input write_enable,
      input address[ADDR_WIDTH-1:0],
      input cmd_in[CMD_WIDTH-1:0]
      input cmd_out[CMD_WIDTH-1:0]);

    reg[CMD_WIDTH-1:0] data[2**ADDR_WIDTH-1:0];

    reg[2**ADDR_WIDTH-1:0] cur_addr;

    assign cmd_out = data[cur_addr];

    always @(posedge clk)begin
        cur_addr <= address;
        if(write_enable)
            data[address] = cmd_in;

    end

endmodule
     
