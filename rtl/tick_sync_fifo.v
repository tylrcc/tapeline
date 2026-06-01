// tick_sync_fifo.v -- small synchronous fifo sitting between the host dma ring
// and the mac engine. its only job is to give us real backpressure: when it
// fills, full deasserts the upstream ready and the producer has to wait instead
// of us dropping ticks on the floor.
//
// single clock for now. the pcie side actually crosses a clock domain.
// TODO: make this a proper async fifo (gray-coded pointers + 2ff synchronizers)
//       before wiring the real xdma core in. single-clock is fine for sim and
//       for the loopback bring-up board.

`default_nettype none
`timescale 1ns / 1ps

module tick_sync_fifo #(
    parameter W     = 56,   // payload width (px + vol packed by the top level)
    parameter DEPTH = 512   // power of two
)(
    input  wire          clk,
    input  wire          rst_n,

    input  wire          wr_en,
    input  wire [W-1:0]  wr_data,
    output wire          full,

    input  wire          rd_en,
    output reg  [W-1:0]  rd_data,
    output wire          empty,

    output wire [$clog2(DEPTH):0] level   // occupancy, handy for tuning the watermark
);

    localparam AW = $clog2(DEPTH);

    reg [W-1:0] mem [0:DEPTH-1];
    reg [AW:0]  wr_ptr;   // extra msb so full/empty are unambiguous
    reg [AW:0]  rd_ptr;

    wire do_wr = wr_en & ~full;
    wire do_rd = rd_en & ~empty;

    assign empty = (wr_ptr == rd_ptr);
    assign full  = (wr_ptr[AW] != rd_ptr[AW]) && (wr_ptr[AW-1:0] == rd_ptr[AW-1:0]);
    assign level = wr_ptr - rd_ptr;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr <= {(AW+1){1'b0}};
        end else if (do_wr) begin
            mem[wr_ptr[AW-1:0]] <= wr_data;
            wr_ptr <= wr_ptr + 1'b1;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rd_ptr  <= {(AW+1){1'b0}};
            rd_data <= {W{1'b0}};
        end else if (do_rd) begin
            rd_data <= mem[rd_ptr[AW-1:0]];
            rd_ptr  <= rd_ptr + 1'b1;
        end
    end

endmodule

`default_nettype wire
