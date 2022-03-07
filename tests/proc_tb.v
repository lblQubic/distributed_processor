`timescale 1ns / 10ps
`include "../hdl/ctrl.v"
`include "../hdl/alu.v"
`include "../hdl/instr_ptr.v"
`include "../hdl/cmd_mem.v"
`include "../hdl/qclk.v"
`include "../hdl/reg_file.v"
`include "../hdl/proc.v"

module proc_tb;
`include "../hdl/instr_params.vh"
`include "../hdl/ctrl_params.vh"
    localparam CLK_CYCLE = 5;
    localparam END_SIM_TS = 1000;

    localparam TS_ENABLE = 33;
    
    localparam TS_LOAD_EN = 23;
    localparam TS_LOAD_VAL = 13;

    localparam TS_LOAD_DIS = 33;
    
    localparam LOAD_VAL = 500;

    reg clk = 0;
    reg enable = 0;
    always #CLK_CYCLE clk <= ~clk;

    reg load_en = 0;
    reg[7:0] load_val=0;
    wire[7:0] out;
    reg reset=0;

    proc dut(.clk(clk), .reset(reset));

    initial begin
        $dumpfile("proc_test0.vcd");
        $dumpvars(3, proc_tb);

//        #3
//        reset = 0;
//        #16
//        reset = 1;
//
//        #TS_ENABLE
//        enable = 1;
//
//        #11
//        reset = 0;
//
//        #TS_LOAD_EN
//        load_en = 1;
//
//        #TS_LOAD_VAL
//        load_val = LOAD_VAL;
//        #3
//        load_val = 700;
//
//        #TS_LOAD_DIS
//        load_en = 0;
//
//        #END_SIM_TS
        $finish();

    end

endmodule






