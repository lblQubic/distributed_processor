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


    reg clk = 0;
    //reg enable = 0;
    always #CLK_CYCLE clk <= ~clk;

    reg load_cmd_en = 0;
    reg[127:0] cmd_in_data=0;
    reg[7:0] cmd_in_addr=0;
    wire[71:0] cmd_out;
    wire cstrobe_out;
    reg reset=0;
    reg sync_enable=0;
    reg fproc_enable=0;

    proc dut(.clk(clk), .reset(reset), .write_prog_enable(load_cmd_en), .cmd_addr(cmd_in_addr), .cmd_data(cmd_in_data), .cstrobe(cstrobe_out));

    initial begin
        $dumpfile("proc_test0.vcd");
        $dumpvars(5, proc_tb);

        #3
        reset=1;

        #5
        load_cmd_en = 1;
        cmd_in_data = 128'b0;
        cmd_in_data[127:120] = {REG_I_ALU, 3'b000}; //load value to register 0
        cmd_in_data[119:88] = 32'd12;
        cmd_in_data[83:80] = 4'b0000;
        cmd_in_addr = 8'b0;

        #10
        load_cmd_en = 1;
        cmd_in_data = 128'b0;
        cmd_in_data[127:120]={REG_I_ALU, 3'b000}; //load value to register 1
        cmd_in_data[119:88] = 32'd5;
        cmd_in_data[83:80] = 4'b0001;
        cmd_in_addr = 8'b00000001;

        #10
        load_cmd_en = 1;
        cmd_in_data = 128'b0;
        cmd_in_data[127:120]={REG_ALU, ALU_ADD}; //load sum to register 2
        cmd_in_data[119:116] = 4'b0; //first arg
        cmd_in_data[87:84] = 4'b0001;//second arg
        cmd_in_data[83:80] = 4'b0010;//dest reg
        cmd_in_addr = 8'b00000010;

        #10
        load_cmd_en = 0;
        reset=0;

        #100


        $finish();

    end

endmodule






