interface cmd_mem_iface#(parameter CMD_ADDR_WIDTH=8, parameter MEM_WIDTH=32, parameter MEM_TO_CMD=4)();
    localparam CMD_WIDTH = MEM_WIDTH*MEM_TO_CMD;
    wire[CMD_ADDR_WIDTH-1:0] instr_ptr;
    wire[CMD_WIDTH-1:0] cmd_read;
    wire[MEM_WIDTH-1:0] mem_bus[MEM_TO_CMD-1:0];

    genvar i;
    for(i = 0; i < MEM_TO_CMD; i = i + 1) begin
        assign cmd_read[(MEM_WIDTH-1)*(i+1):MEM_WIDTH*i] = mem_bus[i];
    end

endinterface

