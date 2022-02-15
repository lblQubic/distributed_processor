module qclk
    #(parameter WIDTH=32)(
      input clk,
      input rst,
      input[WIDTH-1:0] in_val,
      input load_enable
      output out[WIDTH-1:0]);

    reg value[WIDTH-1:0];
    assign out = value;

    always @(posedge clk) begin
        if(reset)
            value <= 0;
        else if(load_enable)
            value <= in_val + 1;
        else
            value <= value + 1;

    end

endmodule
