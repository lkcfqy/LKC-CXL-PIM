/**
 * async_fifo.sv (Phase 5.4 - Cross-Node Extension)
 * 
 * 异步 FIFO 用于处理 CXL Switch 网络抖动 (Network Jitter) 和时钟域跨越 (CDC)。
 * 
 * 特性:
 * - 读写指针采用格雷码 (Gray Code) 进行跨时钟域同步
 * - Two-stage synchronizer 避免亚稳态
 * - 可配置深度和数据位宽
 */

module async_fifo #(
    parameter DATA_WIDTH = 32,
    parameter ADDR_WIDTH = 4   // FIFO_DEPTH = 2^ADDR_WIDTH = 16
)(
    // 写时钟域
    input  logic                  wclk,
    input  logic                  wrst_n,
    input  logic                  winc,
    input  logic [DATA_WIDTH-1:0] wdata,
    output logic                  wfull,

    // 读时钟域
    input  logic                  rclk,
    input  logic                  rrst_n,
    input  logic                  rinc,
    output logic [DATA_WIDTH-1:0] rdata,
    output logic                  rempty
);

    localparam DEPTH = 1 << ADDR_WIDTH;

    // --- 内存阵列 ---
    logic [DATA_WIDTH-1:0] mem [0:DEPTH-1];

    // --- 指针与同步寄存器 ---
    logic [ADDR_WIDTH:0] wptr, rptr;
    logic [ADDR_WIDTH:0] wptr_gray, rptr_gray;
    logic [ADDR_WIDTH:0] wptr_gray_sync1, wptr_gray_sync2;
    logic [ADDR_WIDTH:0] rptr_gray_sync1, rptr_gray_sync2;

    // --- 写逻辑 ---
    always_ff @(posedge wclk or negedge wrst_n) begin
        if (!wrst_n) begin
            wptr      <= '0;
            wptr_gray <= '0;
        end else if (winc && !wfull) begin
            mem[wptr[ADDR_WIDTH-1:0]] <= wdata;
            wptr      <= wptr + 1'b1;
            wptr_gray <= (wptr + 1'b1) ^ ((wptr + 1'b1) >> 1);
        end
    end

    // --- 读逻辑 ---
    always_ff @(posedge rclk or negedge rrst_n) begin
        if (!rrst_n) begin
            rptr      <= '0;
            rptr_gray <= '0;
        end else if (rinc && !rempty) begin
            rptr      <= rptr + 1'b1;
            rptr_gray <= (rptr + 1'b1) ^ ((rptr + 1'b1) >> 1);
        end
    end

    assign rdata = mem[rptr[ADDR_WIDTH-1:0]];

    // --- 跨时钟域同步 ---
    // 将写指针格雷码同步到读时钟域
    always_ff @(posedge rclk or negedge rrst_n) begin
        if (!rrst_n) begin
            wptr_gray_sync1 <= '0;
            wptr_gray_sync2 <= '0;
        end else begin
            wptr_gray_sync1 <= wptr_gray;
            wptr_gray_sync2 <= wptr_gray_sync1;
        end
    end

    // 将读指针格雷码同步到写时钟域
    always_ff @(posedge wclk or negedge wrst_n) begin
        if (!wrst_n) begin
            rptr_gray_sync1 <= '0;
            rptr_gray_sync2 <= '0;
        end else begin
            rptr_gray_sync1 <= rptr_gray;
            rptr_gray_sync2 <= rptr_gray_sync1;
        end
    end

    // --- 空满标志生成 ---
    // 空信号: 读指针赶上同步过来的写指针
    assign rempty = (rptr_gray == wptr_gray_sync2);

    // 满信号: 写指针比同步过来的读指针多跑了一圈
    // 格雷码判断条件: 最高两位取反，其余位相同
    assign wfull = (wptr_gray == {~rptr_gray_sync2[ADDR_WIDTH:ADDR_WIDTH-1], 
                                   rptr_gray_sync2[ADDR_WIDTH-2:0]});

endmodule
