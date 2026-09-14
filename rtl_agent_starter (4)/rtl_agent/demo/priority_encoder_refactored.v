// priority_encoder_refactored.v
// The canned Stage-2 output used by demo_case_study.py -- verified earlier
// to pass the full 256-case regression, but rejected by the PPA guard
// because real Yosys synthesis shows 50 cells vs. the original's 21.
module priority_encoder(
    input  wire       clk,
    input  wire [7:0] in,
    output reg  [2:0] pos,
    output reg        valid
);
    always @(posedge clk) begin
        casez (in)
            8'b1???????: begin pos <= 3'd7; valid <= 1'b1; end
            8'b01??????: begin pos <= 3'd6; valid <= 1'b1; end
            8'b001?????: begin pos <= 3'd5; valid <= 1'b1; end
            8'b0001????: begin pos <= 3'd4; valid <= 1'b1; end
            8'b00001???: begin pos <= 3'd3; valid <= 1'b1; end
            8'b000001??: begin pos <= 3'd2; valid <= 1'b1; end
            8'b0000001?: begin pos <= 3'd1; valid <= 1'b1; end
            8'b00000001: begin pos <= 3'd0; valid <= 1'b1; end
            default:     begin pos <= 3'd0; valid <= 1'b0; end
        endcase
    end
endmodule
