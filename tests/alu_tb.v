`timescale 1ns / 10ps
`include "../hdl/alu.v"
module alu_tb;
    localparam CLK_CYCLE = 5;
    localparam END_SIM_TS = 1000;

    localparam CONC = {CLK_CYCLE, END_SIM_TS};


    reg clk = 0;
    always #CLK_CYCLE clk <= ~clk;

    reg[2:0] ctrl;
    wire[31:0] out;
    reg[31:0] in0, in1;
    alu dut(.ctrl(ctrl), .in0(in0), .in1(in1), .out(out));

    integer i;

    initial begin
        $dumpfile("alu_test.vcd");
        $dumpvars(3, alu_tb);

        #10
        in0 = 415;
        in1 = 622;

        for(i = 0; i < 7; i = i + 1) begin
            ctrl = i;
            #10;

        end

        in0 = 12;
        in1 = -5;

        for(i = 0; i < 7; i = i + 1) begin
            ctrl = i;
            #10;

        end

      


        #END_SIM_TS;
        $finish();
    end

endmodule
