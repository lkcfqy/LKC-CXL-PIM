
`timescale 1ns/1ps

module inlu_tb;

    parameter int INT_WIDTH = 32;

    logic                 clk;
    logic                 rst_n;
    logic                 i_valid;
    logic [INT_WIDTH-1:0] i_data;
    
    logic                 o_valid;
    logic [INT_WIDTH-1:0] o_exp;

    // 实例化被测模块
    inlu_core #(
        .SCALING_FACTOR_BITS(10),
        .INT_WIDTH(INT_WIDTH)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .i_valid(i_valid),
        .i_data(i_data),
        .o_valid(o_valid),
        .o_exp(o_exp)
    );

    // 时钟生成
    initial clk = 0;
    always #5 clk = ~clk; // 100MHz

    // 测试流程
    initial begin
        $display("--- 启动 iNLU 单元测试 ---");
        rst_n = 0;
        i_valid = 0;
        i_data = 0;
        
        repeat(5) @(posedge clk);
        rst_n = 1;

        // 测试点 1: x = 0 (exp(0) = 1.0, 定点输出应接近 1024)
        @(posedge clk);
        i_valid = 1;
        i_data = 32'd0;
        @(posedge clk);
        i_valid = 0;
        
        // 测试点 2: x = -ln2 (exp(-ln2) = 0.5, 定点输出应接近 512)
        @(posedge clk);
        i_valid = 1;
        i_data = -32'd710; 
        @(posedge clk);
        i_valid = 0;

        // 测试点 3: x = -1.0 (approx -1024)
        @(posedge clk);
        i_valid = 1;
        i_data = -32'd1024;
        @(posedge clk);
        i_valid = 0;

        // 等待流水线结果输出
        repeat(10) @(posedge clk);
        
        $display("--- 测试完成 ---");
        $finish;
    end

    // 结果监视
    always @(posedge clk) begin
        if (o_valid) begin
            $display("[Time=%t] Input_Logit=%d | Output_Exp=%d", $time, $signed(dut.i_data), o_exp);
        end
    end

    // 波形dump (用于调试)
    initial begin
        $dumpfile("inlu_test.vcd");
        $dumpvars(0, inlu_tb);
    end

endmodule
