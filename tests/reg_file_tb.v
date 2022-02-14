`timescale 1ns / 10ps
`include "../hdl/reg_file.v"
module reg_file_tb;
    localparam CLK_CYCLE = 5;
    localparam END_SIM_TS = 1000;

    localparam N_INIT_WRITE = 10;

    localparam N_INIT_EN = 15;

    localparam N_CHANGE_RD = 22;

    reg clk = 0;
    always #CLK_CYCLE clk <= ~clk;

    reg[3:0] read_addr_0, read_addr_1, write_addr;
    wire[31:0] out0, out1;
    reg write_enable;
    reg[31:0] write_data;
    reg_file file(.clk(clk), .read_addr_0(read_addr_0), 
        .read_addr_1(read_addr_1), .write_addr(write_addr), .write_data(write_data),
        .reg_0_out(out0), .reg_1_out(out1), .write_enable(write_enable));

    initial begin
        $dumpfile("reg_file_test.vcd");
        $dumpvars(3, reg_file_tb);

        read_addr_0[3:0] = 2;
        read_addr_1[3:0] = 1;
        write_enable = 0;
        write_data[31:0] = 0;

        #N_INIT_WRITE
        write_data[31:0] = 39;
        write_addr = 1;
        #N_INIT_EN
        write_enable = 1;

        #N_CHANGE_RD
        read_addr_0 = 1;



        #END_SIM_TS;
        $finish();
    end

endmodule
