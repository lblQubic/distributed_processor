module toplevel_sim#(
    parameter DATA_WIDTH=32,
    parameter CMD_WIDTH=128,
    parameter CMD_ADDR_WIDTH=8,
    parameter REG_ADDR_WIDTH=4,
    parameter SYNC_BARRIER_WIDTH=8)(
    input clk,
    input reset,
    input sync_enable,
    input fproc_enable,
    input[CMD_ADDR_WIDTH-1:0] cmd_write_addr,
    input[CMD_WIDTH-1:0] cmd_write,
    input cmd_write_enable,
    output[71:0] cmd_out,
    output cstrobe_out,
    output[SYNC_BARRIER_WIDTH-1:0] sync_barrier,
    output sync_barrier_en_out,
    output[SYNC_BARRIER_WIDTH-1:0] fproc_id,
    output fproc_en_out);

    //just use 128 bit buffer for now
    cmd_mem_iface #(.CMD_ADDR_WIDTH(CMD_ADDR_WIDTH), .MEM_WIDTH(CMD_WIDTH), 
        .MEM_TO_CMD(1)) memif();
    proc #(.DATA_WIDTH(DATA_WIDTH), .CMD_WIDTH(CMD_WIDTH), 
        .CMD_ADDR_WIDTH(CMD_ADDR_WIDTH), .REG_ADDR_WIDTH(REG_ADDR_WIDTH),
        .SYNC_BARRIER_WIDTH(SYNC_BARRIER_WIDTH)) dpr(.clk(clk), .reset(reset),
        .cmd_iface(memif), .sync_enable(sync_enable), 
        .fproc_enable(fproc_enable), .cmd_out(cmd_out), 
        .cstrobe_out(cstrobe_out), .sync_barrier(sync_barrier), 
        .sync_barrier_en_out(sync_barrier_en_out), .fproc_id(fproc_id),
        .fproc_en_out(fproc_en_out));
    cmd_mem mem(.clk(clk), .write_enable(cmd_write_enable), .cmd_in(cmd_write), 
        .write_address(cmd_write_addr), .read_address(memif.instr_ptr), 
        .cmd_out(memif.mem_bus[0]));

endmodule
