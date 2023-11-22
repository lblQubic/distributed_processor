module lfsr #(
    parameter WIDTH=16)(
    input clk,
    input reset,
    output reg [WIDTH-1:0] rand_out
);

reg [WIDTH-1:0] lfsr_reg;
//reg [WIDTH-1:0] lfsr_tap = 16'h8005;
reg [WIDTH-1:0] lfsr_tap = 16'b1011010000000000;
wire lsb;

assign lsb = ^(lfsr_reg & lfsr_tap);

always @(posedge clk) begin
    if (reset) begin
        lfsr_reg <= 16'h0001;
    end else begin
        //lfsr_reg <= {lfsr_reg[WIDTH-2:0], lfsr_reg[WIDTH-1]} ^ (lfsr_reg & lfsr_tap);
        lfsr_reg <= {lfsr_reg[WIDTH-2:0], lsb};
    end
end

assign rand_out = lfsr_reg;

endmodule

// module lfsr16_tb;
// 
// reg clk;
// reg reset;
// reg start;
// wire [15:0] rand_out;
// 
// lfsr16 dut (
//     .clk(clk),
//     .reset(reset),
//     .start(start),
//     .rand_out(rand_out)
// );
// 
// initial begin
//     clk = 0;
//     reset = 1;
//     start = 0;
//     #10 reset = 0;
//     #10 start = 1;
//     #1000 $finish;
// end
// 
// always #5 clk = ~clk;
// 
// endmodule+
