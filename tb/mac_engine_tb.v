// mac_engine_tb.v -- self-checking testbench.
//
// reads sim/vectors.txt (generated from the python golden model) and pushes one
// tick per clock into the dut. every cycle the model says should be valid, we
// check ma_vld plus both outputs against the expected columns. any mismatch is
// a hard $fatal so CI goes red. no eyeballing waveforms.

`default_nettype none
`timescale 1ns / 1ps

module mac_engine_tb;

    localparam PX_W   = 32;
    localparam VOL_W  = 24;
    localparam WINDOW = 64;   // keep in sync with gen_vectors.py

    reg                clk = 1'b0;
    reg                rst_n = 1'b0;
    reg                tick_vld = 1'b0;
    reg  [PX_W-1:0]    px_in = 0;
    reg  [VOL_W-1:0]   tick_vol = 0;
    wire               tick_rdy;
    wire               ma_vld;
    wire [PX_W-1:0]    sma_out;
    wire [PX_W-1:0]    vwap_out;

    mac_engine #(
        .PX_W(PX_W), .VOL_W(VOL_W), .WINDOW(WINDOW)
    ) dut (
        .clk(clk), .rst_n(rst_n),
        .tick_vld(tick_vld), .px_in(px_in), .tick_vol(tick_vol), .tick_rdy(tick_rdy),
        .ma_vld(ma_vld), .sma_out(sma_out), .vwap_out(vwap_out)
    );

    always #5 clk = ~clk;   // 100 MHz

    integer fd, r;
    integer errors = 0;
    integer checked = 0;
    integer nline = 0;

    // one vector
    reg [PX_W-1:0]  v_px;
    reg [VOL_W-1:0] v_vol;
    integer         v_valid;
    reg [PX_W-1:0]  v_sma;
    reg [PX_W-1:0]  v_vwap;

    initial begin
        fd = $fopen("sim/vectors.txt", "r");
        if (fd == 0) begin
            $display("FATAL: could not open sim/vectors.txt, run `make vectors` first");
            $finish;
        end

        // reset for a few cycles
        rst_n = 1'b0;
        repeat (4) @(posedge clk);
        rst_n = 1'b1;
        @(negedge clk);

        while ($fscanf(fd, "%d %d %d %d %d\n", v_px, v_vol, v_valid, v_sma, v_vwap) == 5) begin
            nline = nline + 1;

            // drive the tick
            tick_vld <= 1'b1;
            px_in    <= v_px;
            tick_vol <= v_vol;
            @(posedge clk);
            #1;   // let the registered outputs settle

            if (v_valid == 1) begin
                checked = checked + 1;
                if (ma_vld !== 1'b1) begin
                    errors = errors + 1;
                    $display("MISMATCH line %0d: expected ma_vld=1, got %b", nline, ma_vld);
                end else if (sma_out !== v_sma) begin
                    errors = errors + 1;
                    $display("MISMATCH line %0d: sma exp=%0d got=%0d", nline, v_sma, sma_out);
                end else if (vwap_out !== v_vwap) begin
                    errors = errors + 1;
                    $display("MISMATCH line %0d: vwap exp=%0d got=%0d", nline, v_vwap, vwap_out);
                end
            end else begin
                if (ma_vld !== 1'b0) begin
                    errors = errors + 1;
                    $display("MISMATCH line %0d: expected ma_vld=0 during warmup, got %b", nline, ma_vld);
                end
            end
        end

        tick_vld <= 1'b0;
        $fclose(fd);

        $display("-----------------------------------------------");
        $display("mac_engine_tb: %0d ticks, %0d checked, %0d errors", nline, checked, errors);
        if (errors == 0)
            $display("PASS");
        else
            $display("FAIL");
        $display("-----------------------------------------------");

        if (errors != 0) $fatal(1, "testbench failed");
        $finish;
    end

    // watchdog so a broken handshake never hangs CI
    initial begin
        #5_000_000;
        $display("FATAL: testbench timeout");
        $fatal(1, "timeout");
    end

endmodule

`default_nettype wire
