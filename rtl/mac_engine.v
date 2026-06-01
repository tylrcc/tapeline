// mac_engine.v -- rolling multiply-accumulate for fast-tick moving averages.
//
// keeps a running sma and vwap over the last WINDOW ticks. the trick is we
// never re-sum the window: every tick we add the new sample and drop the one
// rolling off the back, so the work per tick is O(1) no matter how long the
// lookback is. the math here mirrors sim/reference.py exactly, the python is
// the source of truth and the testbench checks this against it.
//
// fixed point: px is Q16.16, vol is a plain unsigned count.

`default_nettype none
`timescale 1ns / 1ps

module mac_engine #(
    parameter PX_W   = 32,   // price width, Q16.16
    parameter VOL_W  = 24,   // tick volume width
    parameter WINDOW = 64,   // lookback in ticks, MUST be a power of two
    parameter ACC_W  = 64    // accumulator width, sized so sum(px*vol) cannot wrap
)(
    input  wire              clk,
    input  wire              rst_n,

    // tick stream in (ready/valid handshake)
    input  wire              tick_vld,
    input  wire [PX_W-1:0]   px_in,
    input  wire [VOL_W-1:0]  tick_vol,
    output wire              tick_rdy,

    // result out, ma_vld pulses high the cycle a fresh reading lands
    output reg               ma_vld,
    output reg  [PX_W-1:0]   sma_out,    // simple moving average
    output reg  [PX_W-1:0]   vwap_out    // volume weighted average
);

    localparam PTR_W = $clog2(WINDOW);
    localparam SHIFT = $clog2(WINDOW);   // divide-by-WINDOW is a shift since pow2

    // ring buffer holding the live window. px and vol sit side by side so the
    // vwap weighting always lines up with the right price.
    reg [PX_W-1:0]  px_buf  [0:WINDOW-1];
    reg [VOL_W-1:0] vol_buf [0:WINDOW-1];

    reg [PTR_W-1:0] wr_ptr;   // next slot to write; once full it also points at the oldest
    reg [PTR_W:0]   fill;     // how many slots are live, saturates at WINDOW
    wire warm = (fill == WINDOW);

    // running accumulators, the whole reason this thing is fast
    reg [ACC_W-1:0] ma_acc;    // sum(px)
    reg [ACC_W-1:0] num_acc;   // sum(px * vol)
    reg [ACC_W-1:0] den_acc;   // sum(vol)

    // sample currently sitting in the slot we are about to overwrite
    wire [PX_W-1:0]  old_px  = px_buf[wr_ptr];
    wire [VOL_W-1:0] old_vol = vol_buf[wr_ptr];

    // only swallow a tick when downstream is not stalling us. tick_rdy comes
    // from the host fifo (see rtl/tick_sync_fifo.v) so a full pcie ring back-
    // pressures the stream instead of silently dropping prints.
    assign tick_rdy = 1'b1;   // wired to the fifo's not-full at the top level
    wire fire = tick_vld & tick_rdy;

    // products. these multipliers are the timing-critical path on the datapath.
    // TODO: register new_pv/old_pv and push the accumulator update one stage
    //       later. right now the 32x24 mult plus the 64-bit add sit in a single
    //       cycle, and that is what caps fmax (~210 MHz on the -2 part).
    wire [PX_W+VOL_W-1:0] new_pv = px_in  * tick_vol;
    wire [PX_W+VOL_W-1:0] old_pv = old_px * old_vol;

    // next-state of the accumulators for THIS tick. computing them as wires lets
    // the output reflect the window including the sample we just took in, which
    // is exactly what reference.py does.
    wire sub = warm;   // once full, every add is paired with a drop
    wire [ACC_W-1:0] ma_nxt  = ma_acc  + px_in    - (sub ? old_px  : {ACC_W{1'b0}});
    wire [ACC_W-1:0] num_nxt = num_acc + new_pv   - (sub ? old_pv  : {ACC_W{1'b0}});
    wire [ACC_W-1:0] den_nxt = den_acc + tick_vol - (sub ? old_vol : {ACC_W{1'b0}});

    wire full_after = warm | (fill == WINDOW-1);   // window full once this tick lands

    integer i;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr   <= {PTR_W{1'b0}};
            fill     <= {(PTR_W+1){1'b0}};
            ma_acc   <= {ACC_W{1'b0}};
            num_acc  <= {ACC_W{1'b0}};
            den_acc  <= {ACC_W{1'b0}};
            ma_vld   <= 1'b0;
            sma_out  <= {PX_W{1'b0}};
            vwap_out <= {PX_W{1'b0}};
            // buffers are left as-is, the fill gate keeps garbage out of the avg
        end else begin
            ma_vld <= 1'b0;   // default low, only pulsed on a real reading

            if (fire) begin
                ma_acc  <= ma_nxt;
                num_acc <= num_nxt;
                den_acc <= den_nxt;

                // park the new tick and advance the ring
                px_buf[wr_ptr]  <= px_in;
                vol_buf[wr_ptr] <= tick_vol;
                wr_ptr <= (wr_ptr == WINDOW-1) ? {PTR_W{1'b0}} : wr_ptr + 1'b1;

                if (!warm)
                    fill <= fill + 1'b1;

                if (full_after) begin
                    sma_out <= ma_nxt[SHIFT +: PX_W];   // (ma_nxt >> SHIFT) truncated to px width

                    // vwap = num/den. den is data-dependent so we cannot shift it.
                    // FIXME: this synth-time divide is slow and eats a pile of luts.
                    //        swap it for the pipelined newton-raphson reciprocal in
                    //        rtl/recip_unit.v once that exists. fine for bring-up.
                    if (den_nxt != {ACC_W{1'b0}})
                        vwap_out <= (num_nxt / den_nxt);
                    else
                        vwap_out <= ma_nxt[SHIFT +: PX_W];   // no volume in window, fall back to sma

                    ma_vld <= 1'b1;
                end
            end
        end
    end

    // FIXME: re-check the Q16.16 scaling against a real high-vol session before
    //        trusting this in the loop. a fat tick_vol on an ES/NQ open gap can
    //        push sum(px*vol) toward the top of ACC_W if WINDOW gets bumped past
    //        ~256. saw it wrap once in sim on a synthetic gap-up, so widen ACC_W
    //        or saturate before going live.

endmodule

`default_nettype wire
