`include "vunit_defines.svh"
`timescale 1ns / 10ps
module reg_page_tb;
    `TEST_SUITE begin

        `TEST_SUITE_SETUP begin
            localparam CLK_CYCLE = 5; 
            reg clk = 0;
            always #CLK_CYCLE clk <= ~clk;

            reg[3:0] read_addr_0, read_addr_1, write_addr;
            wire[31:0] out0, out1;
            wire write_enable;
            reg[31:0] write_data;
            reg_page page(.clk(clk), .read_addr_0(readaddr0), 
                .read_addr_1(readaddr1), .write_addr(write_addr),
                .reg_0_out(out0), .reg_1_out(out1));

            $display("running test suite setup");
        end 

        `TEST_CASE_SETUP begin
        end

        `TEST_CASE("mem_rw0")
        @always 



