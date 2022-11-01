//`include "../hdl/ctrl.v"
//`include "../hdl/alu.v"
//`include "../hdl/instr_ptr.v"
////`include "../hdl/cmd_mem.v"
//`include "../hdl/qclk.v"
//`include "../hdl/reg_file.v"
//`include "../hdl/cmd_mem_iface.sv"
//NOTE: reset should be asserted for at least two clock cycles!
module proc
    #(parameter DATA_WIDTH=32,
      parameter CMD_WIDTH=128,
      parameter CMD_ADDR_WIDTH=8,
      parameter REG_ADDR_WIDTH=4,
      parameter ENV_WIDTH = 24,
      parameter PHASE_WIDTH = 14,
      parameter FREQ_WIDTH = 24,
      parameter SYNC_BARRIER_WIDTH=8)(
      input clk,
      input reset,
      input[FREQ_WIDTH-1:0] phase_tref,
      cmd_mem_iface cmd_iface,
      sync_iface.proc sync,
      fproc_iface.proc fproc,
      output[FREQ_WIDTH-1:0] freq_out,
      output[PHASE_WIDTH-1:0] phase_out,
      output[ENV_WIDTH-1:0] env_addr_out,
      output cstrobe_out);

    //`include "../hdl/instr_params.vh" //todo: debug includes
    //`include "../hdl/ctrl_params.vh"
    localparam OPCODE_WIDTH = 8;
    localparam FPROC_ID_WIDTH = 8;
    localparam ALU_OPCODE_WIDTH = 3;
    //localparam PULSE_OUT_WIDTH = 72;
    localparam PULSE_CMD_I_WIDTH = ENV_WIDTH + PHASE_WIDTH + FREQ_WIDTH + 6;
    //localparam INST_PTR_SYNC_EN = 2'b01;
    //localparam INST_PTR_FPROC_EN = 2'b10;
    //localparam INST_PTR_DEFAULT_EN = 2'b00;

    //datapath wires
    wire[CMD_WIDTH-1:0] cmd_buf_out;
    wire[CMD_ADDR_WIDTH-1:0] cmd_buf_read_addr;
    wire[DATA_WIDTH-1:0] alu_out, reg_file_out0, reg_file_out1, alu_in0, alu_in1, qclk_out, qclk_in;

    //pulse datapath wires
    wire[FREQ_WIDTH-1:0] freq_i_in, freq_in; //i is from cmd_buffer, freq_in is actual input (could be r val)
    wire[ENV_WIDTH-1:0] env_i_in, env_in;
    wire[PHASE_WIDTH-1:0] phase_i_in, phase_in;
    wire phase_write_en, phase_write_en_cmd;
    wire freq_write_en, freq_write_en_cmd;
    wire env_write_en, env_write_en_cmd;
    wire phase_write_sel; //0 for i, 1 for r
    wire freq_write_sel;
    wire env_write_sel;
    wire write_pulse_en;

    assign cmd_buf_out = cmd_iface.cmd_read;
    
    //control wires
    wire[ALU_OPCODE_WIDTH-1:0] alu_opcode;
    wire c_strobe_enable;
    wire alu_in0_sel;
    wire[1:0] alu_in1_sel;
    wire reg_write_en;
    //wire reg_write_sel;
    wire[1:0] inst_ptr_en_sel;
    wire[1:0] inst_ptr_load_en_sel;
    wire qclk_load_en;
    wire cstrobe;

    wire qclk_resetin;
    wire inst_ptr_resetin;
    wire inst_ptr_load_en;
    wire inst_ptr_enable;

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
    //assign cmd_out = cmd_buf_out[CMD_WIDTH-1-OPCODE_WIDTH-DATA_WIDTH:CMD_WIDTH-OPCODE_WIDTH-DATA_WIDTH-PULSE_OUT_WIDTH];

    //pulse datapath
    assign pulse_cmd_time = cmd_buf_out[CMD_WIDTH-1-OPCODE_WIDTH-REG_ADDR_WIDTH-PULSE_CMD_I_WIDTH:
                            CMD_WIDTH-OPCODE_WIDTH-REG_ADDR_WIDTH-PULSE_CMD_I_WIDTH-DATA_WIDTH];
    localparam ENV_INPUT_MSB = CMD_WIDTH-1-OPCODE_WIDTH-REG_ADDR_WIDTH-2;
    localparam ENV_INPUT_LSB = CMD_WIDTH-OPCODE_WIDTH-REG_ADDR_WIDTH-2-ENV_WIDTH;
    localparam PHASE_INPUT_MSB = ENV_INPUT_LSB-1-2;
    localparam PHASE_INPUT_LSB = ENV_INPUT_LSB-PHASE_WIDTH-2;
    localparam FREQ_INPUT_MSB = PHASE_INPUT_LSB-1-2;
    localparam FREQ_INPUT_LSB = PHASE_INPUT_LSB-FREQ_WIDTH-2;

    assign freq_i_in = cmd_buf_out[FREQ_INPUT_MSB:FREQ_INPUT_LSB];
    assign phase_i_in = cmd_buf_out[PHASE_INPUT_MSB:PHASE_INPUT_LSB];
    assign env_i_in = cmd_buf_out[ENV_INPUT_MSB:ENV_INPUT_LSB];

    assign freq_write_en_cmd = cmd_buf_out[FREQ_INPUT_MSB+2];
    assign phase_write_en_cmd = cmd_buf_out[PHASE_INPUT_MSB+2];
    assign env_write_en_cmd = cmd_buf_out[ENV_INPUT_MSB+2];

    assign freq_write_sel = cmd_buf_out[FREQ_INPUT_MSB+1];
    assign phase_write_sel = cmd_buf_out[PHASE_INPUT_MSB+1];
    assign env_write_sel = cmd_buf_out[ENV_INPUT_MSB+1];

    assign freq_in = freq_write_sel ? reg_file_out0[FREQ_WIDTH-1:0] : freq_i_in;
    assign phase_in = phase_write_sel ? reg_file_out0[PHASE_WIDTH-1:0] : phase_i_in;
    assign env_in = env_write_sel ? reg_file_out0[ENV_WIDTH-1:0] : env_i_in;

    //other datapath connections
    assign qclk_in = alu_out;
    assign fproc.id = cmd_buf_out[CMD_WIDTH-1-ALU_INPUT_SPACE-2*REG_ADDR_WIDTH:CMD_WIDTH-ALU_INPUT_SPACE-2*REG_ADDR_WIDTH-FPROC_ID_WIDTH];

    //conditional assignments from control bits
    assign alu_in0 = alu_in0_sel ?  reg_file_out0 : alu_cmd_data_in0;
    assign alu_in1 = alu_in1_sel[1] ? fproc.data : (alu_in1_sel[0] ? reg_file_out1 : qclk_out);
    //always @(*) begin
    //    if (alu_in1_sel == ALU_IN1_REG_SEL)
    //        alu_in1 = reg_file_out1;
    //    else if(alu_in1_sel == ALU_IN1_QCLK_SEL)
    //        alu_in1 = qclk_out;
    //    else
    //        alu_in1 = fproc_data;
    //end
    assign inst_ptr_load_en = inst_ptr_load_en_sel[1] ? alu_out[0] : inst_ptr_load_en_sel[0]; //MSB selects ALU output
    assign cstrobe = (qclk_out == pulse_cmd_time) & c_strobe_enable;
    assign cstrobe_out = cstrobe;

    assign freq_write_en = freq_write_en_cmd & write_pulse_en;
    assign phase_write_en = phase_write_en_cmd & write_pulse_en;
    assign env_write_en = env_write_en_cmd & write_pulse_en;

    //instantiate modules
    //cmd_mem #(.CMD_WIDTH(CMD_WIDTH), .ADDR_WIDTH(CMD_ADDR_WIDTH)) cmd_buffer(
    //          .clk(clk), .write_enable(write_prog_enable), .read_address(cmd_buf_read_addr),
    //          .write_address(cmd_addr), .cmd_in(cmd_data), .cmd_out(cmd_buf_out));
    instr_ptr #(.WIDTH(CMD_ADDR_WIDTH)) instr(.clk(clk), .enable(inst_ptr_enable), .reset(reset),
              .load_val(instr_ptr_load_val), .load_enable(inst_ptr_load_en), .ptr_out(cmd_iface.instr_ptr));
    reg_file #(.DATA_WIDTH(DATA_WIDTH), .ADDR_WIDTH(REG_ADDR_WIDTH)) regs(
              .clk(clk), .read_addr_0(reg_addr_in0), .read_addr_1(reg_addr_in1),
              .write_addr(reg_write_addr), .write_data(alu_out), .write_enable(reg_write_en),
              .reg_0_out(reg_file_out0), .reg_1_out(reg_file_out1));
    ctrl ctu(.clk(clk), .reset(reset), .opcode(cmd_buf_out[CMD_WIDTH-1:CMD_WIDTH-OPCODE_WIDTH]), .alu_opcode(alu_opcode),
              .c_strobe_enable(c_strobe_enable), .fproc_ready(fproc.ready), .sync_enable(sync.ready), 
              .alu_in0_sel(alu_in0_sel), .alu_in1_sel(alu_in1_sel), .reg_write_en(reg_write_en), .instr_ptr_en(inst_ptr_enable), 
              .instr_ptr_load_en(inst_ptr_load_en_sel), .qclk_load_en(qclk_load_en), .cstrobe_in(cstrobe),
              .sync_out_ready(sync.enable), .fproc_out_ready(fproc.enable), .write_pulse_en(write_pulse_en));
    alu #(.DATA_WIDTH(DATA_WIDTH)) myalu(.clk(clk), .ctrl(alu_opcode), .in0(alu_in0), .in1(alu_in1), .out(alu_out));
    qclk #(.WIDTH(DATA_WIDTH)) myclk(.clk(clk), .rst(reset), .in_val(qclk_in), .load_enable(qclk_load_en), .out(qclk_out)); //todo: implement sync reset logic

    //`ifdef COCOTB_SIM
    //initial begin
    //  $dumpfile ("proc.vcd");
    //    $dumpvars (3, proc);
    //  #1;
    //end
    //`endif





endmodule
