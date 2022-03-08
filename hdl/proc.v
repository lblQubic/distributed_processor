//`include "../hdl/ctrl.v"
//`include "../hdl/alu.v"
//`include "../hdl/instr_ptr.v"
//`include "../hdl/cmd_mem.v"
//`include "../hdl/qclk.v"
//`include "../hdl/reg_file.v"
module proc
    #(parameter DATA_WIDTH=32,
      parameter CMD_WIDTH=128,
      parameter CMD_ADDR_WIDTH=8,
      parameter REG_ADDR_WIDTH=4,
      parameter SYNC_BARRIER_WIDTH=8)(
      input clk,
      input reset,
      input write_prog_enable,
      input[CMD_ADDR_WIDTH-1:0] cmd_addr,
      input[CMD_WIDTH-1:0] cmd_data,
      input sync_enable,
      input fproc_enable,
      output[71:0] cmd_out,
      output cstrobe,
      output[SYNC_BARRIER_WIDTH-1:0] sync_barrier,
      output sync_barrier_en_out,
      output[SYNC_BARRIER_WIDTH-1:0] fproc_id,
      output fproc_en_out);

    `include "../hdl/instr_params.vh" //todo: debug includes
    `include "../hdl/ctrl_params.vh"
    localparam OPCODE_WIDTH = 8;
    localparam ALU_OPCODE_WIDTH = 3;
    localparam PULSE_OUT_WIDTH = 72;
    //localparam INST_PTR_SYNC_EN = 2'b01;
    //localparam INST_PTR_FPROC_EN = 2'b10;
    //localparam INST_PTR_DEFAULT_EN = 2'b00;

    //datapath wires
    wire[CMD_WIDTH-1:0] cmd_buf_out;
    wire[CMD_ADDR_WIDTH-1:0] cmd_buf_read_addr;
    wire[DATA_WIDTH-1:0] alu_out, reg_file_out0, reg_file_out1, alu_in0, alu_in1, qclk_out, qclk_in;
    
    //control wires
    wire[ALU_OPCODE_WIDTH-1:0] alu_opcode;
    wire c_strobe_enable;
    wire alu_in0_sel;
    wire alu_in1_sel;
    wire reg_write_en;
    //wire reg_write_sel;
    wire[1:0] inst_ptr_en_sel;
    wire[1:0] inst_ptr_load_en_sel;
    wire qclk_load_en;

    wire qclk_resetin;
    wire inst_ptr_resetin;
    wire inst_ptr_load_en;
    reg inst_ptr_enable;

    //cmd buffer datapath shorthands
    wire[CMD_ADDR_WIDTH-1:0] instr_ptr_load_val;
    wire[DATA_WIDTH-1:0] alu_cmd_data_in0;
    wire[DATA_WIDTH-1:0] pulse_cmd_time;
    wire[REG_ADDR_WIDTH-1:0] reg_addr_in0;
    wire[REG_ADDR_WIDTH-1:0] reg_addr_in1;
    wire[REG_ADDR_WIDTH-1:0] reg_write_addr;

    localparam ALU_INPUT_SPACE = OPCODE_WIDTH + DATA_WIDTH + REG_ADDR_WIDTH; //datapath reserved for ALU inputs (both immediate and reg addressed)
    assign instr_ptr_load_val = cmd_buf_out[CMD_WIDTH-1-ALU_INPUT_SPACE:CMD_WIDTH-ALU_INPUT_SPACE-CMD_ADDR_WIDTH];
    assign alu_cmd_data_in0 = cmd_buf_out[CMD_WIDTH-1-OPCODE_WIDTH:CMD_WIDTH-OPCODE_WIDTH-DATA_WIDTH]; // data_in0 and addr_in0 overlap since you always 
    assign reg_addr_in0 = cmd_buf_out[CMD_WIDTH-1-OPCODE_WIDTH:CMD_WIDTH-OPCODE_WIDTH-REG_ADDR_WIDTH]; //     choose between one or the other
    assign reg_addr_in1 = cmd_buf_out[CMD_WIDTH-1-OPCODE_WIDTH-DATA_WIDTH:CMD_WIDTH-OPCODE_WIDTH-DATA_WIDTH-REG_ADDR_WIDTH]; 
    assign reg_write_addr = cmd_buf_out[CMD_WIDTH-1-OPCODE_WIDTH-DATA_WIDTH-REG_ADDR_WIDTH:CMD_WIDTH-OPCODE_WIDTH-DATA_WIDTH-2*REG_ADDR_WIDTH]; 
    assign cmd_out = cmd_buf_out[CMD_WIDTH-1-OPCODE_WIDTH-DATA_WIDTH:CMD_WIDTH-OPCODE_WIDTH-DATA_WIDTH-PULSE_OUT_WIDTH];
    assign pulse_cmd_time = cmd_buf_out[CMD_WIDTH-1-OPCODE_WIDTH:CMD_WIDTH-OPCODE_WIDTH-DATA_WIDTH];

    //other datapath connections
    assign qclk_in = alu_out;

    //conditional assignments from control bits
    assign alu_in0 = alu_in0_sel ?  reg_file_out0 : alu_cmd_data_in0;
    assign alu_in1 = alu_in1_sel ? reg_file_out1 : qclk_out;
    assign inst_ptr_load_en = inst_ptr_load_en_sel[1] ? alu_out[0] : inst_ptr_load_en_sel[0]; //MSB selects ALU output
    always @(*) begin
        case(inst_ptr_en_sel)
            INST_PTR_DEFAULT_EN : inst_ptr_enable = 1; //todo: this maybe should interact with reset logic, or separate enable input
            INST_PTR_SYNC_EN : inst_ptr_enable = sync_enable;
            INST_PTR_FPROC_EN : inst_ptr_enable = fproc_enable;
        endcase
    end
    assign cstrobe = (qclk_out == pulse_cmd_time) & c_strobe_enable;


    //instantiate modules
    cmd_mem #(.CMD_WIDTH(CMD_WIDTH), .ADDR_WIDTH(CMD_ADDR_WIDTH)) cmd_buffer(
              .clk(clk), .write_enable(write_prog_enable), .read_address(cmd_buf_read_addr),
              .write_address(cmd_addr), .cmd_in(cmd_data), .cmd_out(cmd_buf_out));
    instr_ptr #(.WIDTH(CMD_ADDR_WIDTH)) instr(.clk(clk), .enable(inst_ptr_enable), .reset(reset),
              .load_val(instr_ptr_load_val), .load_enable(inst_ptr_load_en), .ptr_out(cmd_buf_read_addr));
    reg_file #(.DATA_WIDTH(DATA_WIDTH), .ADDR_WIDTH(REG_ADDR_WIDTH)) regs(
              .clk(clk), .read_addr_0(reg_addr_in0), .read_addr_1(reg_addr_in1),
              .write_addr(reg_write_addr), .write_data(alu_out), .write_enable(reg_write_en),
              .reg_0_out(reg_file_out0), .reg_1_out(reg_file_out1));
    ctrl ctu(.opcode(cmd_buf_out[CMD_WIDTH-1:CMD_WIDTH-OPCODE_WIDTH]), .alu_opcode(alu_opcode),
              .c_strobe_enable(c_strobe_enable), .alu_in0_sel(alu_in0_sel), .alu_in1_sel(alu_in1_sel),
              .reg_write_en(reg_write_en), .instr_ptr_en_sel(inst_ptr_en_sel), .instr_ptr_load_en(inst_ptr_load_en_sel),
              .qclk_load_en(qclk_load_en), .sync_out_ready(sync_barrier_en_out), .fproc_out_ready(fproc_en_out));
    alu #(.DATA_WIDTH(DATA_WIDTH)) myalu(.ctrl(alu_opcode), .in0(alu_in0), .in1(alu_in1), .out(alu_out));
    qclk #(.WIDTH(DATA_WIDTH)) myclk(.clk(clk), .rst(reset), .in_val(qclk_in), .load_enable(qclk_load_en), .out(qclk_out)); //todo: impolement sync reset logic

    `ifdef COCOTB_SIM
    initial begin
      $dumpfile ("proc.vcd");
        $dumpvars (3, proc);
      #1;
    end
    `endif





endmodule
