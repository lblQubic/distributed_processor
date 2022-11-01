module cmd_reg #(
    parameter PHASE_WIDTH=14,
    parameter FREQ_WIDTH=24,
    parameter SAMPLES_PER_CLK=4,
    parameter TREF_WIDTH=24,
    parameter ENV_WORD_WIDTH=24)(
    input clk,
    input[PHASE_WIDTH-1:0] phase_offs_in,
    input[FREQ_WIDTH-1:0] freq_in,
    input[TREF_WIDTH-1:0] tref,
    input[ENV_WORD_WIDTH-1:0] env_word_in, //generally address MSB followed by length LSB
    input phase_write_en,
    input freq_write_en,
    input env_word_write_en,
    input cstrobe_in,
    output[PHASE_WIDTH-1:0] phase,
    output reg[FREQ_WIDTH-1:0] freq,
    output reg[ENV_WORD_WIDTH-1:0] env_word,
    output reg cstrobe);

    reg[PHASE_WIDTH-1:0] phase_offs;
    wire[FREQ_WIDTH-1:0] phase_t_acc; //phase accumulated over time

    always @(posedge clk) begin
        if(phase_write_en)
            phase_offs <= phase_offs_in;
        if(freq_write_en)
            freq <= freq_in;
        if(env_word_write_en)
            env_word <= env_word_in;
        cstrobe <= cstrobe_in;

    end
    
    assign phase_t_acc = ((freq*tref*SAMPLES_PER_CLK) >> (FREQ_WIDTH - PHASE_WIDTH));
    assign phase = phase_t_acc[PHASE_WIDTH-1:0] + phase_offs;

endmodule
