
/**
 * outlier_logic.sv
 * 
 * 核心创新二：异常值感知逻辑 (Outlier-Aware Logic)
 * 功能：在 PIM Bank 内部识别异常值，并将其重定向至高精度路径/缓冲区
 * 
 * 输入: i_data        (INT32) - 输入激活值
 * 输入: i_threshold   (INT32) - 异常值阈值 (如 6-Sigma)
 * 
 * 输出: o_data_int8   (INT8)  - 普通路径值 (截断后)
 * 输出: o_is_outlier  (logic) - 异常值标记
 * 输出: o_outlier_val (INT32) - 异常值原始数据 (发往 Overflow Buffer)
 */

module outlier_logic #(
    parameter int INT_WIDTH = 32,
    parameter int BUFFER_SIZE = 16 // 针对 1% 比例设计的紧凑缓冲区
)(
    input  logic                 clk,
    input  logic                 rst_n,
    input  logic                 i_valid,
    input  logic [INT_WIDTH-1:0] i_data,
    input  logic [INT_WIDTH-1:0] i_threshold,
    
    output logic                 o_valid,
    output logic [7:0]           o_data_int8,   // 主路径：INT8 量化值
    output logic                 o_is_outlier,  // 异常标志
    output logic [INT_WIDTH-1:0] o_outlier_val, // 溢出路径：原始高精度值
    output logic                 o_buffer_full  // 缓冲区满警告
);

    // --- 内部寄存器与连线 ---
    logic [INT_WIDTH-1:0] abs_data;
    logic                 is_outlier_comb;
    
    // 计算绝对值
    assign abs_data = (i_data[INT_WIDTH-1]) ? (~i_data + 1'b1) : i_data;
    
    // 比较逻辑 (组合逻辑)
    assign is_outlier_comb = (abs_data > i_threshold);

    // --- 流水线输出 ---
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            o_valid       <= 1'b0;
            o_data_int8   <= 8'd0;
            o_is_outlier  <= 1'b0;
            o_outlier_val <= '0;
        end else if (i_valid) begin
            o_valid      <= 1'b1;
            o_is_outlier <= is_outlier_comb;
            
            if (is_outlier_comb) begin
                // 异常值处理：记录原始值，INT8 路径置为最大量化值(保护)
                o_outlier_val <= i_data;
                o_data_int8   <= (i_data[INT_WIDTH-1]) ? 8'h81 : 8'h7F; 
            end else begin
                // 普通值处理：截断/量化至 INT8
                // 此处简化为直接截断低 8 位，实际应用需配合 Scale Factor
                o_data_int8   <= i_data[7:0];
                o_outlier_val <= '0;
            end
        end else begin
            o_valid <= 1'b0;
        end
    end

    // --- 基于计数器的简易缓冲区监控 (模拟) ---
    logic [7:0] outlier_count;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            outlier_count <= 8'd0;
            o_buffer_full <= 1'b0;
        end else if (i_valid && is_outlier_comb) begin
            if (outlier_count < BUFFER_SIZE) begin
                outlier_count <= outlier_count + 1'b1;
                o_buffer_full <= 1'b0;
            end else begin
                o_buffer_full <= 1'b1; // 缓冲区溢出警告
            end
        end
    end

endmodule
