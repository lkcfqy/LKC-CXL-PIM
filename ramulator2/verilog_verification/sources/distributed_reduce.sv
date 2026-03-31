/**
 * distributed_reduce.sv (Phase 5.4 - Cross-Node Extension)
 * 
 * 跨芯片 Reduce 控制器，管理多个 CXL PIM 节点间的 Global_Max 和 Global_Sum 同步。
 * 外接 async_fifo 用于吸收 CXL Switch 的网络抖动（Jitter）。
 * 
 * 核心机制：
 * - 接收来自 iNLU 的 Local Max/Sum
 * - 打包并通过异步 FIFO 经由 CXL 链路广播
 * - 配置超时 (Timeout) 防死锁机制，丢包时可触发重传/中断恢复
 */

module distributed_reduce #(
    parameter INT_WIDTH = 32,
    parameter NUM_NODES = 4,
    parameter TIMEOUT_CYCLES = 1000 // 网络超时周期，防死锁
)(
    input  logic                 clk,
    input  logic                 rst_n,

    // 接口 1：连接本地 iNLU (Local Max/Sum 发生源)
    input  logic                 i_local_max_valid,
    input  logic [INT_WIDTH-1:0] i_local_max_data,
    input  logic                 i_local_sum_valid,
    input  logic [INT_WIDTH-1:0] i_local_sum_data,
    
    // 接口 2：下发给本地 iNLU 的 Global Max/Sum (汇总结果)
    output logic                 o_global_max_valid,
    output logic [INT_WIDTH-1:0] o_global_max_data,
    output logic                 o_global_sum_valid,
    output logic [INT_WIDTH-1:0] o_global_sum_data,

    // 接口 3：连接 CXL 网络 TX/RX (异步 FIFO 外部直连或网络 MAC)
    input  logic                 i_cxl_rx_valid,
    input  logic [1:0]           i_cxl_rx_type, // 01=MAX, 10=SUM, 11=ERROR
    input  logic [INT_WIDTH-1:0] i_cxl_rx_data,
    
    output logic                 o_cxl_tx_valid,
    output logic [1:0]           o_cxl_tx_type, // 01=MAX, 10=SUM
    output logic [INT_WIDTH-1:0] o_cxl_tx_data,
    
    // 状态报警
    output logic                 o_timeout_err
);

    // --- 网络接收缓存 (CDC FIFO) ---
    logic                 rx_fifo_inc;
    logic [INT_WIDTH+1:0] rx_fifo_rdata; // {type[1:0], data[31:0]}
    logic                 rx_fifo_empty;
    
    // 我们假设 RX 信号是从独立网络时钟域过来，这里实例化 Async FIFO 吸收抖动
    // wclk 会接真实物理网络的时钟，这里为了简化建模统一连 clk (假设前级已做过物理量测并送入同频时钟)
    // 但 RTL 结构展现了跨时钟缓冲思路。
    async_fifo #(
        .DATA_WIDTH(INT_WIDTH + 2),
        .ADDR_WIDTH(4)
    ) rx_jitter_buffer (
        .wclk(clk),            // CXL 网络时钟 (简化)
        .wrst_n(rst_n),
        .winc(i_cxl_rx_valid),
        .wdata({i_cxl_rx_type, i_cxl_rx_data}),
        .wfull(),              // 简化处理，不接背压
        
        .rclk(clk),            // PIM Core 时钟
        .rrst_n(rst_n),
        .rinc(rx_fifo_inc),
        .rdata(rx_fifo_rdata),
        .rempty(rx_fifo_empty)
    );

    // --- Controller FSM ---
    typedef enum logic [2:0] {
        ST_IDLE     = 3'b000,
        ST_BCAST_M  = 3'b001, // 广播 Local Max
        ST_WAIT_M   = 3'b010, // 等待其他节点 Max
        ST_BCAST_S  = 3'b011, // 广播 Local Sum
        ST_WAIT_S   = 3'b100, // 等待其他节点 Sum
        ST_ERR_RCV  = 3'b111  // 超时恢复
    } rdc_state_t;

    rdc_state_t state, next_state;

    logic [15:0] timeout_cnt;
    logic [$clog2(NUM_NODES)-1:0] max_recv;
    logic [$clog2(NUM_NODES)-1:0] sum_recv;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            state <= ST_IDLE;
        else
            state <= next_state;
    end

    always_comb begin
        next_state = state;
        o_timeout_err = 0;
        
        case (state)
            ST_IDLE: begin
                if (i_local_max_valid)
                    next_state = ST_BCAST_M;
            end
            ST_BCAST_M: begin
                next_state = ST_WAIT_M;
            end
            ST_WAIT_M: begin
                if (timeout_cnt >= TIMEOUT_CYCLES) begin
                    next_state = ST_ERR_RCV;
                end else if (max_recv >= NUM_NODES - 1) begin
                    next_state = ST_BCAST_S;
                end
            end
            ST_BCAST_S: begin
                next_state = ST_WAIT_S;
            end
            ST_WAIT_S: begin
                if (timeout_cnt >= TIMEOUT_CYCLES) begin
                    next_state = ST_ERR_RCV;
                end else if (sum_recv >= NUM_NODES - 1) begin
                    next_state = ST_IDLE;
                end
            end
            ST_ERR_RCV: begin
                o_timeout_err = 1;
                // Deadlock-free protection: force return to IDLE and drop current request
                next_state = ST_IDLE;
            end
        endcase
    end

    // --- FIFO 读数据缓存 (修复时序对齐问题) ---
    // async_fifo 的 rdata 是组合逻辑输出 (指向当前 rptr)
    // rinc 在当前拍为高 → rptr 在下一拍更新 → rdata 在下一拍变化
    // 因此我们需要在 rinc 为高的**同一拍**锁存 rdata，而不是下一拍
    logic                 rx_data_valid_r;    // 锁存后的有效信号
    logic [INT_WIDTH+1:0] rx_data_latched;    // 锁存后的 FIFO 数据

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rx_data_valid_r <= 1'b0;
            rx_data_latched <= '0;
        end else begin
            rx_data_valid_r <= rx_fifo_inc;
            if (rx_fifo_inc)
                rx_data_latched <= rx_fifo_rdata;
        end
    end

    // --- 超时计数器与接收统计 ---
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            timeout_cnt <= '0;
            max_recv    <= '0;
            sum_recv    <= '0;
            rx_fifo_inc <= '0;
        end else begin
            // FIFO 读取逻辑
            rx_fifo_inc <= 1'b0;
            if (!rx_fifo_empty && (state == ST_WAIT_M || state == ST_WAIT_S)) begin
                rx_fifo_inc <= 1'b1;
            end

            // 超时保护
            if (state == ST_WAIT_M || state == ST_WAIT_S)
                timeout_cnt <= timeout_cnt + 1;
            else
                timeout_cnt <= '0;

            // 接收事件分发 (使用锁存后的数据，确保时序对齐)
            // rx_data_valid_r 比 rx_fifo_inc 延迟一拍，与 rx_data_latched 对齐
            if (rx_data_valid_r) begin
                if (rx_data_latched[INT_WIDTH+1:INT_WIDTH] == 2'b01 && state == ST_WAIT_M)
                    max_recv <= max_recv + 1;
                else if (rx_data_latched[INT_WIDTH+1:INT_WIDTH] == 2'b10 && state == ST_WAIT_S)
                    sum_recv <= sum_recv + 1;
            end

            if (state == ST_IDLE) begin
                max_recv <= '0;
                sum_recv <= '0;
            end
        end
    end

    // --- 输出赋值 ---
    
    // 网络发射 (TX)
    assign o_cxl_tx_valid = (state == ST_BCAST_M) || (state == ST_BCAST_S);
    assign o_cxl_tx_type  = (state == ST_BCAST_M) ? 2'b01 : 2'b10;
    assign o_cxl_tx_data  = (state == ST_BCAST_M) ? i_local_max_data : i_local_sum_data;

    // 连接 iNLU 接收 (RX)
    // 使用锁存后的数据，确保与 valid 信号时序一致
    assign o_global_max_valid = rx_data_valid_r && (rx_data_latched[INT_WIDTH+1:INT_WIDTH] == 2'b01);
    assign o_global_max_data  = rx_data_latched[INT_WIDTH-1:0];
    
    assign o_global_sum_valid = rx_data_valid_r && (rx_data_latched[INT_WIDTH+1:INT_WIDTH] == 2'b10);
    assign o_global_sum_data  = rx_data_latched[INT_WIDTH-1:0];

endmodule
