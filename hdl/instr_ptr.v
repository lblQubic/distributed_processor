module instr_ptr
    #(parameter WIDTH=8)(
      input clk,
      input enable,
      input reset,
      input[WIDTH-1:0] load_val,
      input load_enable,
      output[WIDTH-1:0] ptr_out);
    
    reg[WIDTH-1:0] prev_val_inc;
    reg[WIDTH-1:0] cur_val;

    assign ptr_out = cur_val;

    //assign ptr_out = value;

    always @(posedge clk)
        if(reset)
            prev_val_inc <= 0;
        else if(enable)
            prev_val_inc <= cur_val + 1;

    always @(*)
        if(load_enable)
            cur_val = load_val;
        else 
            cur_val = prev_val_inc;


endmodule

