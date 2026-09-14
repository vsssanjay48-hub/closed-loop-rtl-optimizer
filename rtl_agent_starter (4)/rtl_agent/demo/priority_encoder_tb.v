// priority_encoder_tb.v
// Exhaustive, self-checking regression: every one of the 256 possible input
// values against an independently-computed reference model. Prints exactly
// "TEST PASSED" or "TEST FAILED" on its own line, per the orchestrator's
// pass/fail convention (tools.run_iverilog greps for this literal string).

`timescale 1ns/1ps

module priority_encoder_tb;
    reg         clk = 1'b0;
    reg  [7:0]  in;
    wire [2:0]  pos;
    wire        valid;

    integer     i;
    integer     errors = 0;
    reg  [2:0]  exp_pos;
    reg         exp_valid;

    priority_encoder dut(
        .clk   (clk),
        .in    (in),
        .pos   (pos),
        .valid (valid)
    );

    always #5 clk = ~clk;

    // Reference model -- deliberately written differently from the DUT
    // (a plain descending scan with a found-flag) so it isn't just a copy
    // of either the original or the refactored implementation.
    function automatic [2:0] ref_pos(input [7:0] v);
        integer j;
        reg     found;
        begin
            ref_pos = 3'd0;
            found   = 1'b0;
            for (j = 7; j >= 0; j = j - 1) begin
                if (v[j] && !found) begin
                    ref_pos = j[2:0];
                    found   = 1'b1;
                end
            end
        end
    endfunction

    function automatic ref_valid(input [7:0] v);
        ref_valid = |v;
    endfunction

    initial begin
        in = 8'd0;
        @(negedge clk);
        for (i = 0; i < 256; i = i + 1) begin
            in = i[7:0];
            @(negedge clk);   // input stable well before the sampling edge
            @(posedge clk);   // DUT samples `in` here
            #1;               // let the nonblocking assignment settle
            exp_pos   = ref_pos(in);
            exp_valid = ref_valid(in);
            if (pos !== exp_pos || valid !== exp_valid) begin
                errors = errors + 1;
                $display("MISMATCH in=%b pos=%0d valid=%b (expected pos=%0d valid=%b)",
                          in, pos, valid, exp_pos, exp_valid);
            end
        end

        if (errors == 0)
            $display("TEST PASSED");
        else
            $display("TEST FAILED (%0d mismatches out of 256)", errors);

        $finish;
    end
endmodule
