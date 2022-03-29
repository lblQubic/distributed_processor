module alu
    #(parameter DATA_WIDTH=32)(
      input[2:0] ctrl,
      input[DATA_WIDTH-1:0] in0,
      input[DATA_WIDTH-1:0] in1,
      output reg[DATA_WIDTH-1:0] out);

    wire[DATA_WIDTH-1:0] id, add, sub;
    wire eq, le, ge, sub_oflow;

    assign id = in0;
    assign add = in0 + in1;
    assign sub = in0 - in1;
    assign eq = (sub == 0);

    assign sub_oflow = (((~in0[DATA_WIDTH-1]) & in1[DATA_WIDTH-1] & sub[DATA_WIDTH-1])
                        | (in0[DATA_WIDTH-1] & (~in1[DATA_WIDTH-1]) & (~sub[DATA_WIDTH-1])));
    assign le = sub[DATA_WIDTH-1] ^ sub_oflow; //this assumes twos complement!
    assign ge = ~le;

    always @(*) begin
        case(ctrl)
            8'd0 : out = id;
            8'd1 : out = add;
            8'd2 : out = sub;
            8'd3 : out = eq;
            8'd4 : out = le;
            8'd5 : out = ge;
            default : out = 0;
        endcase 
    end

endmodule
