module instr_ptr
    #(parameter WIDTH=8)(
      input clk,
      input enable,
      input[WIDTH-1:0] load_val,
      input load_enable,
      output[WIDTH-1:0] ptr_out);
    
    reg[WIDTH-1:0] value;

    assign ptr_out = value;

    always @(posedge clk)
        if(enable)
            value <= value + 1;

    always @(*)//todo: check correctness. sim appears ok.
        if(load_enable)
            value = load_val;

endmodule

