`timescale 1ns/1ps

/**
 * distributed_reduce_tb.sv
 *
 * 验证分布式 Reduce 状态机在面临网络抖动、延迟甚至丢包时的工作情况，
 * 验证其不会发生死锁 (Deadlock-Free)。
 */

module distributed_reduce_tb;

    parameter int INT_WIDTH = 32;
    parameter int NUM_NODES = 4;
    parameter int TIMEOUT_CYCLES = 50; // 较小的超时设定用于快速测试

    logic                 clk;
    logic                 rst_n;

    // Interface
    logic                 i_local_max_valid;
    logic [INT_WIDTH-1:0] i_local_max_data;
    logic                 i_local_sum_valid;
    logic [INT_WIDTH-1:0] i_local_sum_data;
    
    logic                 o_global_max_valid;
    logic [INT_WIDTH-1:0] o_global_max_data;
    logic                 o_global_sum_valid;
    logic [INT_WIDTH-1:0] o_global_sum_data;

    logic                 i_cxl_rx_valid;
    logic [1:0]           i_cxl_rx_type;
    logic [INT_WIDTH-1:0] i_cxl_rx_data;
    
    logic                 o_cxl_tx_valid;
    logic [1:0]           o_cxl_tx_type;
    logic [INT_WIDTH-1:0] o_cxl_tx_data;
    
    logic                 o_timeout_err;

    // DUT
    distributed_reduce #(
        .INT_WIDTH(INT_WIDTH),
        .NUM_NODES(NUM_NODES),
        .TIMEOUT_CYCLES(TIMEOUT_CYCLES)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .i_local_max_valid(i_local_max_valid),
        .i_local_max_data(i_local_max_data),
        .i_local_sum_valid(i_local_sum_valid),
        .i_local_sum_data(i_local_sum_data),
        .o_global_max_valid(o_global_max_valid),
        .o_global_max_data(o_global_max_data),
        .o_global_sum_valid(o_global_sum_valid),
        .o_global_sum_data(o_global_sum_data),
        .i_cxl_rx_valid(i_cxl_rx_valid),
        .i_cxl_rx_type(i_cxl_rx_type),
        .i_cxl_rx_data(i_cxl_rx_data),
        .o_cxl_tx_valid(o_cxl_tx_valid),
        .o_cxl_tx_type(o_cxl_tx_type),
        .o_cxl_tx_data(o_cxl_tx_data),
        .o_timeout_err(o_timeout_err)
    );

    // Clock gen
    initial clk = 0;
    always #5 clk = ~clk;

    // Test Tasks
    task send_network_packet(input logic [1:0] p_type, input logic [INT_WIDTH-1:0] p_data, input integer delay_cycles);
        begin
            repeat(delay_cycles) @(posedge clk);
            i_cxl_rx_valid = 1;
            i_cxl_rx_type  = p_type;
            i_cxl_rx_data  = p_data;
            @(posedge clk);
            i_cxl_rx_valid = 0;
        end
    endtask

    initial begin
        $display("--- 开始 Distributed Reduce (Deadlock-Free) 测试 ---");
        rst_n = 0;
        i_local_max_valid = 0; i_local_sum_valid = 0;
        i_cxl_rx_valid = 0;
        
        repeat(5) @(posedge clk);
        rst_n = 1;
        
        // ----------------------------------------------------
        // Test 1: 正常流程 (Normal Operation with minimal jitter)
        // ----------------------------------------------------
        $display("[Test 1] 正常流程 - 无丢包");
        @(posedge clk);
        i_local_max_valid = 1; i_local_max_data = 32'd100;
        @(posedge clk);
        i_local_max_valid = 0;
        
        // 等待 3 个其它节点的 Max 到来 (带有少量抖动)
        send_network_packet(2'b01, 32'd90, 2);
        send_network_packet(2'b01, 32'd110, 5);
        send_network_packet(2'b01, 32'd80, 1);
        
        // 接下来它应该会发 Sum
        repeat(10) @(posedge clk);
        
        // 送出 Sum 聚合
        i_local_sum_valid = 1; i_local_sum_data = 32'd1000;
        @(posedge clk);
        i_local_sum_valid = 0;
        
        send_network_packet(2'b10, 32'd500, 3);
        send_network_packet(2'b10, 32'd400, 2);
        send_network_packet(2'b10, 32'd600, 4);
        
        repeat(20) @(posedge clk);
        
        // ----------------------------------------------------
        // Test 2: 网络拥塞打断测试 (Timeout / Deadlock escape)
        // ----------------------------------------------------
        $display("[Test 2] 异常流程 - 丢包引发超时");
        @(posedge clk);
        i_local_max_valid = 1; i_local_max_data = 32'd200;
        @(posedge clk);
        i_local_max_valid = 0;
        
        // 只收到 2 个节点的响应，第 3 个丢失
        send_network_packet(2'b01, 32'd190, 2);
        send_network_packet(2'b01, 32'd210, 5);
        
        // 等待超时，验证 o_timeout_err 拉高且 FSM 退回 IDLE 不会死锁
        wait(o_timeout_err == 1);
        $display("  => 成功捕捉到 Timeout Error，避免死锁！");
        
        repeat(10) @(posedge clk);
        
        $display("--- 测试完成 ---");
        $finish;
    end

    // Dump波形
    initial begin
        $dumpfile("dist_reduce_waves.vcd");
        $dumpvars(0, distributed_reduce_tb);
    end

endmodule
