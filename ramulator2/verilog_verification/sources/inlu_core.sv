
/**
 * inlu_core.sv (Phase 5.4 - Cross-Node Extension)
 * 
 * 核心创新一：iNLU (Integer Non-Linear Unit) 
 * 
 * 新增功能 (Phase 5.4):
 *   - Global_Max 寄存器: 跨节点 Softmax 的全局最大值同步
 *   - Global_Sum 寄存器: 跨节点归一化因子累积
 *   - CXL P2P 接口: 接收/发送 Global_Max 和 Global_Sum
 *   - 两阶段协议:
 *     Phase A: 各节点计算 Local Max → P2P 交换 → 确定 Global Max
 *     Phase B: 各节点用 Global Max 计算 Local Exp Sum → P2P 交换 → 确定 Global Sum
 *     Phase C: 用 Global Sum 完成归一化
 *
 * 原有功能 (保持不变):
 *   - 纯整型 Softmax 计算 (多项式拟合 e^x)
 *   - 4 级流水线
 *
 * 输入: i_data     (INT32) - 缩放后的定点数 Logits
 * 输入: i_global_* - CXL P2P 全局同步接口
 * 输出: o_exp      (INT32) - 近似计算得到的 e^x * Scaling_Factor
 * 输出: o_softmax  (INT32) - 完整 Softmax 输出 (使用 Global Sum 归一化)
 */

module inlu_core #(
    parameter int INT_WIDTH = 32,
    parameter int NUM_NODES = 4       // 跨节点 Softmax 支持的节点数
)(
    input  logic                 clk,
    input  logic                 rst_n,
    input  logic                 i_valid,
    input  logic [INT_WIDTH-1:0] i_data,    // 已减去 local_max 后的 Logits

    // === Phase 5.4 新增: 分布式 Softmax 接口 ===

    // Global Max 同步 (Phase A)
    input  logic                 i_global_max_valid,   // 收到远程节点的 local_max
    input  logic [INT_WIDTH-1:0] i_global_max_data,    // 远程节点的 local_max 值
    output logic                 o_local_max_valid,     // 本地 local_max 就绪
    output logic [INT_WIDTH-1:0] o_local_max_data,      // 本地 local_max 值

    // Global Sum 同步 (Phase B)
    input  logic                 i_global_sum_valid,    // 收到远程节点的 local_sum
    input  logic [INT_WIDTH-1:0] i_global_sum_data,     // 远程节点的 local_sum 值
    output logic                 o_local_sum_valid,      // 本地 local_sum 就绪
    output logic [INT_WIDTH-1:0] o_local_sum_data,       // 本地 local_sum 值

    // 状态
    output logic                 o_dist_softmax_done,   // 分布式 Softmax 完成
    output logic [1:0]           o_dist_phase,          // 当前阶段: 0=IDLE, 1=MAX, 2=SUM, 3=NORM

    // === 原有输出 ===
    output logic                 o_valid,
    output logic [INT_WIDTH-1:0] o_exp,                 // e^x 原始输出
    output logic [INT_WIDTH-1:0] o_softmax              // 归一化后的 Softmax 输出
);

    // --- 常数定义 (基于 I-BERT 算法，缩放比例为 2^10) ---
    localparam logic [INT_WIDTH-1:0] LN2_INT  = 32'd710;
    localparam logic [INT_WIDTH-1:0] COEFF_A  = 32'd367;
    localparam logic [INT_WIDTH-1:0] COEFF_B  = 32'd1385;
    localparam logic [INT_WIDTH-1:0] COEFF_C  = 32'd352;

    // LN2 近似除法的常量 (用于可综合的移位近似)
    // 1/710 ≈ 1/1024 + correction  =>  x/710 ≈ (x >> 10) * 1024 / 710
    // 更精确: 1/710 ≈ (x * 46341) >> 25  (46341 = round(2^25 / 710))
    localparam logic [INT_WIDTH-1:0] INV_LN2_MULT = 32'd46341;
    localparam int                   INV_LN2_SHIFT = 25;

    // Softmax 归一化的倒数近似 SCALE (Newton-Raphson 的定点精度)
    localparam int                   NR_SCALE_BITS = 15;

    // --- 分布式 Softmax 状态机 ---
    typedef enum logic [1:0] {
        DIST_IDLE = 2'b00,
        DIST_MAX  = 2'b01,   // Phase A: 交换 local_max
        DIST_SUM  = 2'b10,   // Phase B: 交换 local_sum
        DIST_NORM = 2'b11    // Phase C: 归一化
    } dist_state_t;

    dist_state_t dist_state, dist_state_next;

    // --- Phase 5.4 新增寄存器 ---
    logic [INT_WIDTH-1:0] local_max_reg;       // 本地 Logit 最大值
    logic [INT_WIDTH-1:0] global_max_reg;      // 全局最大值 (所有节点)
    logic [INT_WIDTH-1:0] local_sum_reg;       // 本地 exp_sum
    logic [INT_WIDTH-1:0] global_sum_reg;      // 全局 exp_sum (所有节点)
    logic [$clog2(NUM_NODES)-1:0] max_recv_cnt; // 收到的 global_max 计数
    logic [$clog2(NUM_NODES)-1:0] sum_recv_cnt; // 收到的 global_sum 计数
    logic                 local_max_computed;
    logic                 local_sum_computed;

    // --- 原有流水线寄存器 ---

    // Stage 1: 范围归约
    logic [INT_WIDTH-1:0] n_reg;
    logic [INT_WIDTH-1:0] f_reg;
    logic                 v1_reg;

    // Stage 2: (f + b) 计算
    logic [INT_WIDTH-1:0] f_plus_b_reg;
    logic [INT_WIDTH-1:0] n2_reg;
    logic                 v2_reg;

    // Stage 3: (f + b)^2 (乘法)
    logic [63:0]          f_plus_b_sq_reg;
    logic [INT_WIDTH-1:0] n3_reg;
    logic                 v3_reg;

    // Stage 4: a * poly + c 并应用 2^n
    logic [INT_WIDTH-1:0] poly_result_reg;
    logic                 v4_reg;

    // =========================================================================
    // 分布式 Softmax 状态机
    // =========================================================================

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            dist_state <= DIST_IDLE;
        else
            dist_state <= dist_state_next;
    end

    always_comb begin
        dist_state_next = dist_state;
        case (dist_state)
            DIST_IDLE: begin
                if (local_max_computed)
                    dist_state_next = DIST_MAX;
            end
            DIST_MAX: begin
                // 收齐所有节点的 max 后进入 SUM 阶段
                if (max_recv_cnt >= NUM_NODES[$clog2(NUM_NODES)-1:0] - 1)
                    dist_state_next = DIST_SUM;
            end
            DIST_SUM: begin
                // 收齐所有节点的 sum 后进入 NORM 阶段
                if (sum_recv_cnt >= NUM_NODES[$clog2(NUM_NODES)-1:0] - 1)
                    dist_state_next = DIST_NORM;
            end
            DIST_NORM: begin
                // 归一化完成后回到 IDLE
                dist_state_next = DIST_IDLE;
            end
        endcase
    end

    assign o_dist_phase = dist_state;

    // =========================================================================
    // Global Max 同步逻辑 (Phase A)
    // =========================================================================

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            local_max_reg      <= {1'b1, {(INT_WIDTH-1){1'b0}}}; // 真正的 32 位最小补码值 (0x80000000)
            global_max_reg     <= {1'b1, {(INT_WIDTH-1){1'b0}}};
            max_recv_cnt       <= '0;
            local_max_computed <= 1'b0;
        end else begin
            // 更新 local_max (streaming max of input logits)
            if (i_valid && $signed(i_data) > $signed(local_max_reg)) begin
                local_max_reg <= i_data;
            end

            // 当进入 DIST_MAX 阶段，开始交换
            if (dist_state == DIST_IDLE && local_max_computed) begin
                global_max_reg <= local_max_reg;
            end

            // 接收远程节点的 local_max
            if (i_global_max_valid && dist_state == DIST_MAX) begin
                if ($signed(i_global_max_data) > $signed(global_max_reg))
                    global_max_reg <= i_global_max_data;
                max_recv_cnt <= max_recv_cnt + 1;
            end

            // 重置计数器
            if (dist_state == DIST_NORM) begin
                max_recv_cnt       <= '0;
                local_max_computed <= 1'b0;
            end

            // 标记 local_max 计算完成 (当 i_valid 下降沿)
            if (!i_valid && v1_reg)
                local_max_computed <= 1'b1;
        end
    end

    assign o_local_max_valid = local_max_computed;
    assign o_local_max_data  = local_max_reg;

    // =========================================================================
    // Global Sum 同步逻辑 (Phase B)
    // =========================================================================

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            local_sum_reg      <= '0;
            global_sum_reg     <= '0;
            sum_recv_cnt       <= '0;
            local_sum_computed <= 1'b0;
        end else begin
            // 累积 local exp sum (from Stage 4 output)
            if (v4_reg && dist_state == DIST_SUM) begin
                local_sum_reg <= local_sum_reg + poly_result_reg;
            end

            // 当进入 SUM 阶段，初始化 global_sum
            if (dist_state == DIST_MAX && dist_state_next == DIST_SUM) begin
                global_sum_reg     <= local_sum_reg;
                local_sum_computed <= 1'b1;
            end

            // 接收远程节点的 local_sum
            if (i_global_sum_valid && dist_state == DIST_SUM) begin
                global_sum_reg <= global_sum_reg + i_global_sum_data;
                sum_recv_cnt   <= sum_recv_cnt + 1;
            end

            // 重置
            if (dist_state == DIST_NORM) begin
                local_sum_reg      <= '0;
                sum_recv_cnt       <= '0;
                local_sum_computed <= 1'b0;
            end
        end
    end

    assign o_local_sum_valid = local_sum_computed;
    assign o_local_sum_data  = local_sum_reg;

    // =========================================================================
    // 分布式 Softmax 完成 & 归一化
    // =========================================================================

    assign o_dist_softmax_done = (dist_state == DIST_NORM);

    // =========================================================================
    // 归一化输出: softmax = exp / global_sum
    // 使用 Newton-Raphson 迭代来近似 1/global_sum (可综合)
    //
    // Newton-Raphson 公式: x_{n+1} = x_n * (2 - d * x_n)
    // 其中 d = global_sum_reg，初始估计 x_0 通过 Leading-Zero Count 得到
    // 两次迭代即可达到 INT32 所需精度
    // =========================================================================

    // 前导零检测 (用于 Newton-Raphson 初始估计)
    function automatic [4:0] count_leading_zeros;
        input [INT_WIDTH-1:0] val;
        integer k;
        begin
            count_leading_zeros = 5'd31;
            for (k = 31; k >= 0; k = k - 1) begin
                if (val[k]) begin
                    count_leading_zeros = 5'(31 - k);
                end
            end
        end
    endfunction

    logic [INT_WIDTH-1:0] inv_sum_reg;   // 近似 1/global_sum (定点, Q.NR_SCALE_BITS)

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            o_softmax   <= '0;
            inv_sum_reg <= '0;
        end else if (v4_reg && dist_state == DIST_NORM) begin
            if (global_sum_reg != '0) begin
                // Step 1: 初始估计 x_0 ≈ 2^(2*NR_SCALE_BITS - msb_pos)
                // 其中 msb_pos = 31 - CLZ
                logic [4:0]           clz;
                logic [INT_WIDTH-1:0] x0, x1, x2;
                logic [63:0]          prod_tmp;
                logic [INT_WIDTH-1:0] two_minus_dx;

                clz = count_leading_zeros(global_sum_reg);
                // x_0 = 1 << (NR_SCALE_BITS * 2 - (31 - clz))
                // 简化: x_0 = 1 << (2*15 - 31 + clz) = 1 << (clz - 1)  (当 clz < 32)
                if (5'(NR_SCALE_BITS) + clz > 5'd31)
                    x0 = 32'hFFFFFFFF;
                else
                    x0 = 32'd1 << (NR_SCALE_BITS + clz - 5'd1);

                // Step 2: Newton-Raphson 迭代 1
                // x1 = x0 * (2 * SCALE - global_sum * x0 / SCALE) / SCALE
                prod_tmp = 64'(global_sum_reg) * 64'(x0);
                two_minus_dx = (32'd1 << (NR_SCALE_BITS + 1)) - prod_tmp[NR_SCALE_BITS +: 32];
                x1 = (64'(x0) * 64'(two_minus_dx)) >> NR_SCALE_BITS;

                // Step 3: Newton-Raphson 迭代 2 (精度提升)
                prod_tmp = 64'(global_sum_reg) * 64'(x1);
                two_minus_dx = (32'd1 << (NR_SCALE_BITS + 1)) - prod_tmp[NR_SCALE_BITS +: 32];
                x2 = (64'(x1) * 64'(two_minus_dx)) >> NR_SCALE_BITS;

                inv_sum_reg <= x2;

                // Step 4: softmax = exp * inv_sum >> NR_SCALE_BITS
                o_softmax <= (64'(poly_result_reg) * 64'(x2)) >> NR_SCALE_BITS;
            end else begin
                o_softmax   <= '0;
                inv_sum_reg <= '0;
            end
        end
    end

    // =========================================================================
    // 原有 e^x 流水线 (Stage 1-4)
    // 已更新: Stage 1 的 / 和 % 运算改为可综合的移位-乘法近似
    // =========================================================================

    // Stage 1: 范围归约 (Synthesizable shift-multiply approximation)
    // 原: n = x / LN2_INT, f = x % LN2_INT (不可综合)
    // 新: n = (x * INV_LN2_MULT) >> INV_LN2_SHIFT  (定点乘法近似除法)
    //     f = x - n * LN2_INT                       (乘法-减法求余数)
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            n_reg  <= '0;
            f_reg  <= '0;
            v1_reg <= '0;
        end else if (i_valid) begin
            logic signed [63:0] quotient_full;
            logic signed [INT_WIDTH-1:0] n_approx;
            logic signed [INT_WIDTH-1:0] remainder;

            // n ≈ x * (2^25 / 710) >> 25  =  x * 46341 >> 25
            quotient_full = $signed(i_data) * $signed({{1'b0}, INV_LN2_MULT[INT_WIDTH-2:0]});
            n_approx = quotient_full[INV_LN2_SHIFT +: INT_WIDTH];

            // f = x - n * LN2_INT
            remainder = $signed(i_data) - n_approx * $signed(LN2_INT);

            // 修正: 如果余数为负，说明 n 估计偏大，回退一步
            if (remainder < 0) begin
                n_reg <= n_approx - 1;
                f_reg <= remainder + $signed(LN2_INT);
            end else if (remainder >= $signed(LN2_INT)) begin
                n_reg <= n_approx + 1;
                f_reg <= remainder - $signed(LN2_INT);
            end else begin
                n_reg <= n_approx;
                f_reg <= remainder;
            end

            v1_reg <= 1'b1;
        end else begin
            v1_reg <= 1'b0;
        end
    end

    // Stage 2: f + b
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            f_plus_b_reg <= '0;
            n2_reg <= '0;
            v2_reg <= '0;
        end else if (v1_reg) begin
            f_plus_b_reg <= $signed(f_reg) + $signed(COEFF_B);
            n2_reg <= n_reg;
            v2_reg <= 1'b1;
        end else begin
            v2_reg <= 1'b0;
        end
    end

    // Stage 3: 平方
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            f_plus_b_sq_reg <= '0;
            n3_reg <= '0;
            v3_reg <= '0;
        end else if (v2_reg) begin
            f_plus_b_sq_reg <= $signed(f_plus_b_reg) * $signed(f_plus_b_reg);
            n3_reg <= n2_reg;
            v3_reg <= 1'b1;
        end else begin
            v3_reg <= 1'b0;
        end
    end

    // Stage 4: poly = a * sq + c, 应用 2^n
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            poly_result_reg <= '0;
            v4_reg <= '0;
        end else if (v3_reg) begin
            logic [63:0] temp_poly_full;
            temp_poly_full = ((64'(COEFF_A) * f_plus_b_sq_reg) >> 20) + 64'(COEFF_C);

            if ($signed(n3_reg) <= 0) begin
                poly_result_reg <= temp_poly_full[31:0] >> (-$signed(n3_reg));
            end else begin
                poly_result_reg <= temp_poly_full[31:0] << $signed(n3_reg);
            end
            v4_reg <= 1'b1;
        end else begin
            v4_reg <= 1'b0;
        end
    end

    // 输出赋值
    assign o_valid = v4_reg;
    assign o_exp   = poly_result_reg;

endmodule
