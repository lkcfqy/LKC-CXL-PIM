
/**
 * iNLU_core.sv
 * 
 * 核心创新一：iNLU (Integer Non-Linear Unit) 
 * 功能：在 PIM Bank 内部实现纯整型 Softmax 计算（指数部分）
 * 算法：多项式拟合 (Polynomial Approximation) - I-BERT 风格
 * 
 * 输入: i_data (INT32) - 缩放后的定点数 Logits
 * 输出: o_exp  (INT32) - 近似计算得到的 e^x * Scaling_Factor
 */

module inlu_core #(
    parameter int INT_WIDTH = 32
)(
    input  logic                 clk,
    input  logic                 rst_n,
    input  logic                 i_valid,
    input  logic [INT_WIDTH-1:0] i_data,    // 已减去最大值后的 Logits (均为负数或0)
    
    output logic                 o_valid,
    output logic [INT_WIDTH-1:0] o_exp      // 输出 e^x 的定点表示
);

    // --- 常数定义 (基于 I-BERT 算法，缩放比例为 2^10) ---
    // ln2 = 0.6931 * 1024 approx 710
    localparam logic [INT_WIDTH-1:0] LN2_INT = 32'd710;
    
    // 多项式系数 (ax + b)^2 + c
    // a = 0.3585 * 1024 = 367
    // b = 1.353 * 1024 = 1385
    // c = 0.344 * 1024 = 352
    localparam logic [INT_WIDTH-1:0] COEFF_A = 32'd367;
    localparam logic [INT_WIDTH-1:0] COEFF_B = 32'd1385;
    localparam logic [INT_WIDTH-1:0] COEFF_C = 32'd352;

    // --- 流水线寄存器 ---
    
    // Stage 1: 范围归约 (Range Reduction)
    // e^x = 2^n * e^f,  f = x - n*ln2,  f \in [-ln2, 0]
    logic [INT_WIDTH-1:0] n_reg;
    logic [INT_WIDTH-1:0] f_reg;
    logic                 v1_reg;
    
    // Stage 2: (f + b) 计算
    logic [INT_WIDTH-1:0] f_plus_b_reg;
    logic [INT_WIDTH-1:0] n2_reg;
    logic                 v2_reg;
    
    // Stage 3: (f + b)^2 计算 (乘法)
    logic [63:0]          f_plus_b_sq_reg;
    logic [INT_WIDTH-1:0] n3_reg;
    logic                 v3_reg;
    
    // Stage 4: a * (f + b)^2 + c 计算
    logic [INT_WIDTH-1:0] poly_result_reg;
    logic                 v4_reg;
    
    // --- 逻辑实现 ---

    // Stage 1: 范围归约
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            n_reg  <= '0;
            f_reg  <= '0;
            v1_reg <= '0;
        end else if (i_valid) begin
            // n = floor(x / ln2)
            // 在硬件中，由于 x <= 0，可以使用简单的除法/近似
            // 这里为了演示使用有符号商计算
            n_reg  <= $signed(i_data) / $signed(LN2_INT);
            f_reg  <= $signed(i_data) % $signed(LN2_INT);
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

    // Stage 4: a * poly + c 并应用 2^n (位移)
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            poly_result_reg <= '0;
            v4_reg <= '0;
        end else if (v3_reg) begin
            // poly = (a * sq >> 20) + c
            // >> 20 是因为 f_plus_b_sq 带有双倍的缩放 (2^10 * 2^10)
            logic [63:0] temp_poly_full;
            temp_poly_full = ((64'(COEFF_A) * f_plus_b_sq_reg) >> 20) + 64'(COEFF_C);
            
            // 应用 2^n: 这里 n 通常为负数 (如 -1, -2...)
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
