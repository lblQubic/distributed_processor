module alu
    #(parameter DATA_WIDTH=32)(
      input clk,
      input[2:0] ctrl,
      input[DATA_WIDTH-1:0] in0,
      input[DATA_WIDTH-1:0] in1,
      output reg[DATA_WIDTH-1:0] out);

    wire[DATA_WIDTH-1:0] id0, id1, add, sub;
    wire eq, le, ge, sub_oflow;

    reg[DATA_WIDTH-1:0] in0_reg, in1_reg;

    always @(posedge clk) begin
        in0_reg <= in0;
        in1_reg <= in1;
    end

    assign id0 = in0_reg;
    assign id1 = in0_reg;
    assign add = in0_reg + in1_reg;
    assign sub = in0_reg - in1_reg;
    assign eq = (sub == 0);

    assign sub_oflow = (((~in0_reg[DATA_WIDTH-1]) & in1_reg[DATA_WIDTH-1] & sub[DATA_WIDTH-1])
                        | (in0_reg[DATA_WIDTH-1] & (~in1_reg[DATA_WIDTH-1]) & (~sub[DATA_WIDTH-1])));
    assign le = sub[DATA_WIDTH-1] ^ sub_oflow; //this assumes twos complement!
    assign ge = ~le;

    always @(*) begin
        case(ctrl)
            3'd0 : out = id0;
            3'd1 : out = add;
            3'd2 : out = sub;
            3'd3 : begin
                out[0] = eq;
                out[DATA_WIDTH-1:1] = 0;
            end
            3'd4 : begin
                out[0] = le;
                out[DATA_WIDTH-1:1] = 0;
            end
            3'd5 : begin
                out[0] = ge;
                out[DATA_WIDTH-1:1] = 0;
            end
            3'd6 : out = id1;
            default : out = 0;
        endcase 
    end

endmodule
