module pulse_reg #(
    parameter PHASE_WIDTH=17,
    parameter FREQ_WIDTH=9,
    parameter AMP_WIDTH=16,
    parameter CFG_WIDTH=4, //mode + dest bits
    parameter ENV_WORD_WIDTH=24)( //12 bit addr + 12 bit length
    input clk,
    input[PHASE_WIDTH-1:0] phase_offs_in,
    input[FREQ_WIDTH-1:0] freq_in,
    input[AMP_WIDTH-1:0] amp_in, 
    input[ENV_WORD_WIDTH-1:0] env_word_in, //generally address MSB followed by length LSB
    input phase_write_en,
    input freq_write_en,
    input amp_write_en,
    input env_word_write_en,
    input cfg_write_en,
    input cstrobe_in,
    output reg [PHASE_WIDTH-1:0] phase,
    output reg[FREQ_WIDTH-1:0] freq,
    output reg[AMP_WIDTH-1:0] amp,
    output reg[ENV_WORD_WIDTH-1:0] env_word,
    output reg[CFG_WIDTH-1:0] cfg,
    output reg cstrobe);


    always @(posedge clk) begin
        if(phase_write_en)
            phase <= phase_offs_in;
        if(freq_write_en)
            freq <= freq_in;
        if(amp_write_en)
            amp <= amp_in;
        if(env_word_write_en)
            env_word <= env_word_in;
        if(cfg_write_en)
            cfg <= cfg_in;
        cstrobe <= cstrobe_in;

    end
    
endmodule
