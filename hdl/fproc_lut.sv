/**
* General purpose measurement LUT module. Distributes measurement (and LUT)
* results to corresponding proc cores. There are two modes, depending on
* the value of fproc.id: 
*   0 - wait for measurement on core's control qubit, then transmit to core when ready
*   1 - wait for all measurements needed by LUT, then distribute corresponding LUT 
*       output to core.
*
* TODO: separate this into two modules; one for the core state machine (interact with 
*       FPROC interface), and another for the LUT
*/

module fproc_lut #(
    parameter N_CORES=5,
    parameter N_MEAS=N_CORES)(
    input clk,
    input reset,
    fproc_iface.fproc core[N_CORES-1:0],
    input[N_MEAS-1:0] meas,
    input[N_MEAS-1:0] meas_valid);

    reg[N_CORES-1:0] lut_mem[2**N_MEAS-1:0]; //addressed by measurment outcome
    reg[N_CORES-1:0] lut_mask;
    reg[N_CORES-1:0] lut_valid;
    reg[N_CORES-1:0] lut_out;
    reg[N_MEAS-1:0] lut_addr;
    wire lut_ready;

    assign lut_mask = 5'b00011; //TODO: make these writable
    assign lut_mem[0] = 5'b00000;
    assign lut_mem[1] = 5'b00100;
    assign lut_mem[2] = 5'b10000;
    assign lut_mem[3] = 5'b01000;

    localparam LUT_WAIT = 0;
    localparam LUT_READY = 1;
    reg lut_state;
    reg lut_next_state;

    assign lut_ready = (lut_mask & lut_valid) == lut_mask;
    assign lut_out = lut_mem[lut_addr];

    always @(posedge clk) begin
        if(reset) begin
            lut_state = LUT_WAIT;
            lut_valid = 0;
            lut_addr = 0;
        end 
        else
            lut_state = lut_next_state;
    end

    always @(*) begin
        case(lut_state)
            LUT_WAIT : begin
                lut_valid = lut_valid | meas_valid;
                lut_addr = lut_addr | (meas_valid & meas);
                if(lut_ready)
                    lut_next_state = LUT_READY;
                else
                    lut_next_state = LUT_WAIT;
            end
            LUT_READY : begin
                lut_next_state = LUT_WAIT;
                lut_addr = 0;
                lut_valid = 0;
            end
        endcase
    end


    reg[1:0] core_state[N_CORES-1:0];
    reg[1:0] core_next_state[N_CORES-1:0];
    localparam IDLE = 2'b0;
    localparam WAIT_MEAS = 2'b01;
    localparam WAIT_LUT = 2'b10;


    genvar i;
    generate 
        for(i = 0; i < N_CORES; i = i + 1) begin
            always @(posedge clk) begin
                if(reset)
                    core_state[i] = IDLE;
                else
                    core_state[i] = core_next_state[i];
            end

            always @(*) begin
                case(core_state[i])
                    IDLE : begin
                        core[i].ready = 0;
                        core[i].data = 0;
                        if(core[i].enable) begin
                            if(core[i].id == 0)
                                core_next_state[i] = WAIT_MEAS;
                            else
                                core_next_state[i] = WAIT_LUT;
                        end
                        else
                            core_next_state[i] = IDLE;
                    end
                    
                    WAIT_MEAS : begin
                        if(meas_valid[i] == 1) begin
                            core[i].ready = 1;
                            core[i].data[0] = meas[i];
                            core_next_state[i] = IDLE;
                        end
                        else begin
                            core[i].ready = 0;
                            core[i].data[0] = 0;
                            core_next_state[i] = WAIT_MEAS;
                        end
                    end

                    WAIT_LUT : begin
                        if(lut_ready) begin
                            core[i].ready = 1;
                            core[i].data[0] = lut_out[i];
                            core_next_state[i] = IDLE;
                        end
                        else begin
                            core[i].ready = 0;
                            core[i].data = 0;
                            core_next_state[i] = WAIT_LUT;
                        end
                    end

                    default : begin
                        core_next_state[i] = IDLE;
                    end
                endcase
            end
        end
    endgenerate

endmodule
                            

        
        
