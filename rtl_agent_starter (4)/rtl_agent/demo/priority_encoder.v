// priority_encoder.v
// Deliberately deep if-else priority chain -- the same issue class as the
// original toolchain smoke test (encoder(if).v). Each `else if` sits behind
// every prior comparator, so logic depth grows linearly with input width.
// This is the exact "deep_if_else" bottleneck the agent's Stage-1 diagnosis
// is written to detect and Stage-2 is written to flatten into a case/casez
// structure.

module priority_encoder(
    input  wire       clk,
    input  wire [7:0] in,
    output reg  [2:0] pos,
    output reg        valid
);
    always @(posedge clk) begin
        if (in[7])      begin pos <= 3'd7; valid <= 1'b1; end
        else if (in[6]) begin pos <= 3'd6; valid <= 1'b1; end
        else if (in[5]) begin pos <= 3'd5; valid <= 1'b1; end
        else if (in[4]) begin pos <= 3'd4; valid <= 1'b1; end
        else if (in[3]) begin pos <= 3'd3; valid <= 1'b1; end
        else if (in[2]) begin pos <= 3'd2; valid <= 1'b1; end
        else if (in[1]) begin pos <= 3'd1; valid <= 1'b1; end
        else if (in[0]) begin pos <= 3'd0; valid <= 1'b1; end
        else            begin pos <= 3'd0; valid <= 1'b0; end
    end
endmodule
