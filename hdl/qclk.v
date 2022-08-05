module qclk
    #(parameter WIDTH=32)(
      input clk,
      input rst,
      input[WIDTH-1:0] in_val,
      input load_enable,
      output[WIDTH-1:0] out);

    reg[WIDTH-1:0] value;
    assign out = value;

    localparam ALU_LATENCY = 2;

    always @(posedge clk) begin
        if(rst)
            value <= 0;
        else if(load_enable)
            value <= in_val + ALU_LATENCY;
        else
            value <= value + 1;

    end

endmodule
