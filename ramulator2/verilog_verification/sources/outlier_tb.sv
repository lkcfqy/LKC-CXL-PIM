
`timescale 1ns/1ps

module outlier_tb;

    parameter int INT_WIDTH = 32;
    parameter int BUFFER_SIZE = 4; // 测试用小缓冲区

    logic                 clk;
    logic                 rst_n;
    logic                 i_valid;
    logic [INT_WIDTH-1:0] i_data;
    logic [INT_WIDTH-1:0] i_threshold;
    
    logic                 o_valid;
    logic [7:0]           o_data_int8;
    logic                 o_is_outlier;
    logic [INT_WIDTH-1:0] o_outlier_val;
    logic                 o_buffer_full;

    // 实例化被测模块
    outlier_logic #(
        .INT_WIDTH(INT_WIDTH),
        .BUFFER_SIZE(BUFFER_SIZE)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .i_valid(i_valid),
        .i_data(i_data),
        .i_threshold(i_threshold),
        .o_valid(o_valid),
        .o_data_int8(o_data_int8),
        .o_is_outlier(o_is_outlier),
        .o_outlier_val(o_outlier_val),
        .o_buffer_full(o_buffer_full)
    );

    // 时钟生成
    initial clk = 0;
    always #5 clk = ~clk;

    // 测试仿真
    initial begin
        $display("--- 启动 Outlier-Aware Logic 单元测试 ---");
        rst_n = 0;
        i_valid = 0;
        i_data = 0;
        i_threshold = 32'd1000; // 设定阈值为 1000
        
        repeat(5) @(posedge clk);
        rst_n = 1;

        // 测试 1: 普通值 (800 < 1000)
        @(posedge clk);
        i_valid = 1; i_data = 32'd800;
        @(posedge clk);
        i_valid = 0;

        // 测试 2: 异常值 (1500 > 1000)
        @(posedge clk);
        i_valid = 1; i_data = 32'd1500;
        @(posedge clk);
        i_valid = 0;

        // 测试 3: 负异常值 (-2000 < -1000)
        @(posedge clk);
        i_valid = 1; i_data = -32'd2000;
        @(posedge clk);
        i_valid = 0;

        // 测试 4: 连续输入触发缓冲区警告
        repeat(5) begin
            @(posedge clk);
            i_valid = 1; i_data = 32'd5000;
        end
        @(posedge clk);
        i_valid = 0;

        repeat(10) @(posedge clk);
        $display("--- 测试完成 ---");
        $finish;
    end

    // 监视器
    always @(posedge clk) begin
        if (o_valid) begin
            if (o_is_outlier)
                $display("[MATCH] Outlier Detected! Val=%d | Buffer_Full=%b", $signed(o_outlier_val), o_buffer_full);
            else
                $display("[NORMAL] Common Val. INT8_Quant=%d", $signed(o_data_int8));
        end
    end

endmodule
