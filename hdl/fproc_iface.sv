interface fproc_iface#(parameter FPROC_ID_WIDTH=8, parameter FPROC_RESULT_WIDTH=32)();
    wire[FPROC_ID_WIDTH-1:0] id;
    wire[FPROC_RESULT_WIDTH-1:0] data;
    wire enable;
    wire ready;

    modport proc(input data, ready, output enable, id);
    modport fproc(output data, ready, input enable, id);

endinterface

