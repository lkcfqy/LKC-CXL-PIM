
`timescale 1ns/1ps

module inlu_tb;

    parameter int INT_WIDTH = 32;
    parameter int NUM_NODES = 4;

    logic                 clk;
    logic                 rst_n;
    logic                 i_valid;
    logic [INT_WIDTH-1:0] i_data;
    
    // Distributed Softmax ports (tie off for single-node test)
    logic                 i_global_max_valid;
    logic [INT_WIDTH-1:0] i_global_max_data;
    logic                 o_local_max_valid;
    logic [INT_WIDTH-1:0] o_local_max_data;
    logic                 i_global_sum_valid;
    logic [INT_WIDTH-1:0] i_global_sum_data;
    logic                 o_local_sum_valid;
    logic [INT_WIDTH-1:0] o_local_sum_data;
    logic                 o_dist_softmax_done;
    logic [1:0]           o_dist_phase;

    logic                 o_valid;
    logic [INT_WIDTH-1:0] o_exp;
    logic [INT_WIDTH-1:0] o_softmax;

    // Instantiate DUT with correct parameters (was: SCALING_FACTOR_BITS which doesn't exist)
    inlu_core #(
        .INT_WIDTH(INT_WIDTH),
        .NUM_NODES(NUM_NODES)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .i_valid(i_valid),
        .i_data(i_data),
        // Distributed Softmax ports (tied off for single-node test)
        .i_global_max_valid(i_global_max_valid),
        .i_global_max_data(i_global_max_data),
        .o_local_max_valid(o_local_max_valid),
        .o_local_max_data(o_local_max_data),
        .i_global_sum_valid(i_global_sum_valid),
        .i_global_sum_data(i_global_sum_data),
        .o_local_sum_valid(o_local_sum_valid),
        .o_local_sum_data(o_local_sum_data),
        .o_dist_softmax_done(o_dist_softmax_done),
        .o_dist_phase(o_dist_phase),
        // Original outputs
        .o_valid(o_valid),
        .o_exp(o_exp),
        .o_softmax(o_softmax)
    );

    // Clock: 100MHz
    initial clk = 0;
    always #5 clk = ~clk;

    int test_count = 0;

    // Helper task: send one test input
    task automatic send_test(input logic signed [INT_WIDTH-1:0] test_val, input string desc);
        begin
            @(posedge clk);
            i_valid = 1;
            i_data = test_val;
            @(posedge clk);
            i_valid = 0;
            test_count++;
            $display("  [Test %0d] Input: %0d (%s)", test_count, $signed(test_val), desc);
        end
    endtask

    initial begin
        $display("=========================================");
        $display("  iNLU Core Unit Test (Phase 5.4)");
        $display("=========================================");
        rst_n = 0;
        i_valid = 0;
        i_data = 0;
        i_global_max_valid = 0;
        i_global_max_data = 0;
        i_global_sum_valid = 0;
        i_global_sum_data = 0;
        
        repeat(5) @(posedge clk);
        rst_n = 1;
        repeat(2) @(posedge clk);

        // === Group 1: Basic Functionality ===
        $display("\n--- Group 1: Basic Functionality ---");
        send_test(32'sd0,     "exp(0)=1.0, expect ~1024");
        send_test(-32'sd710,  "exp(-ln2)=0.5, expect ~512");
        send_test(-32'sd1024, "exp(-1.0)=0.368, expect ~377");
        send_test(32'sd1024,  "exp(1.0)=2.718, expect ~2783");

        // === Group 2: Boundary Conditions ===
        $display("\n--- Group 2: Boundary Conditions ---");
        send_test(-32'sd1420,  "exp(-2*ln2)=0.25, expect ~256");
        send_test(-32'sd5120,  "exp(-5.0)=0.0067, expect ~7");
        send_test(-32'sd100,   "exp(-0.098)~0.907, expect ~929");
        send_test(32'sd3072,   "exp(3.0)=20.09, expect ~20572");

        // === Group 3: Extreme Cases ===
        $display("\n--- Group 3: Extreme Cases ---");
        send_test(-32'sd10240, "exp(-10)~0, expect near 0");
        send_test(-32'sd1,     "exp(-0.001)~1.0, expect ~1024");

        // Wait for pipeline flush
        repeat(20) @(posedge clk);
        
        $display("\n=========================================");
        $display("  Test Complete: %0d tests submitted", test_count);
        $display("=========================================");
        $finish;
    end

    // Monitor outputs
    always @(posedge clk) begin
        if (o_valid) begin
            $display("    => Output_Exp = %0d (dist_phase=%0b)", o_exp, o_dist_phase);
        end
    end

    // Waveform dump
    initial begin
        $dumpfile("inlu_test.vcd");
        $dumpvars(0, inlu_tb);
    end

endmodule
