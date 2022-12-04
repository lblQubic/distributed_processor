module toplevel_sim#(
    parameter DATA_WIDTH=32,
    parameter CMD_WIDTH=128,
    parameter CMD_ADDR_WIDTH=16,
    parameter REG_ADDR_WIDTH=4,
    parameter ENV_WIDTH = 24,
    parameter PHASE_WIDTH = 17,
    parameter FREQ_WIDTH = 9,
    parameter AMP_WIDTH = 16,
    parameter CFG_WIDTH = 4,
    parameter SYNC_BARRIER_WIDTH=8)(
    input clk,
    input reset,
    input sync_enable,
    input fproc_ready,
    input[DATA_WIDTH-1:0] fproc_data,
    input[CMD_ADDR_WIDTH-1:0] cmd_write_addr,
    input[CMD_WIDTH-1:0] cmd_write,
    input cmd_write_enable,
    output[ENV_WIDTH-1:0] env_word,
    output[PHASE_WIDTH-1:0] phase,
    output[FREQ_WIDTH-1:0] freq,
    output[AMP_WIDTH-1:0] amp,
    output[CFG_WIDTH-1:0] cfg,
    output cstrobe_out,
    output[SYNC_BARRIER_WIDTH-1:0] sync_barrier,
    output sync_barrier_en_out,
    output[SYNC_BARRIER_WIDTH-1:0] fproc_id,
    output fproc_en_out);

    localparam MEM_TO_CMD=4;
    localparam MEM_WIDTH=32;

    cmd_mem_iface #(.CMD_ADDR_WIDTH(CMD_ADDR_WIDTH), .MEM_WIDTH(MEM_WIDTH), 
        .MEM_TO_CMD(MEM_TO_CMD)) memif();
    fproc_iface #(.FPROC_ID_WIDTH(SYNC_BARRIER_WIDTH), .FPROC_RESULT_WIDTH(DATA_WIDTH))
        fproc();
    sync_iface #(.SYNC_BARRIER_WIDTH(SYNC_BARRIER_WIDTH))
        sync();
    pulse_iface #(.PHASE_WIDTH(PHASE_WIDTH), .FREQ_WIDTH(FREQ_WIDTH), 
        .ENV_WORD_WIDTH(ENV_WIDTH), .AMP_WIDTH(AMP_WIDTH), .CFG_WIDTH(CFG_WIDTH)) pulseout();


    assign fproc.data = fproc_data;
    assign fproc.ready = fproc_ready;
    assign fproc_id = fproc.id;
    assign fproc_en_out = fproc.enable;
    assign sync_barrier = sync.barrier;
    assign sync_barrier_en_out = sync.enable;
    assign sync.ready = sync_enable;

  
    proc #(.DATA_WIDTH(DATA_WIDTH), .CMD_WIDTH(CMD_WIDTH), 
        .CMD_ADDR_WIDTH(CMD_ADDR_WIDTH), .REG_ADDR_WIDTH(REG_ADDR_WIDTH),
        .SYNC_BARRIER_WIDTH(SYNC_BARRIER_WIDTH)) dpr(.clk(clk), .reset(reset),
        .cmd_iface(memif), .fproc(fproc), .sync(sync), .pulseout(pulseout));

    assign env_word = pulseout.env_word;
    assign amp = pulseout.amp;
    assign phase = pulseout.phase;
    assign freq = pulseout.freq;
    assign cfg = pulseout.cfg;
        assign cstrobe_out = pulseout.cstrobe;

    //this just breaks the input 128-bit cmd_write into 4 separate chunks and writes simultaneously
    genvar i;
    generate for(i = 0; i < MEM_TO_CMD; i = i + 1) 
        cmd_mem #(.CMD_WIDTH(MEM_WIDTH), .ADDR_WIDTH(CMD_ADDR_WIDTH)) mem(.clk(clk), 
            .write_enable(cmd_write_enable), .cmd_in(cmd_write[MEM_WIDTH*(i+1)-1:MEM_WIDTH*i]), 
            .write_address(cmd_write_addr), .read_address(memif.instr_ptr), 
            .cmd_out(memif.mem_bus[i]));
    endgenerate

endmodule
