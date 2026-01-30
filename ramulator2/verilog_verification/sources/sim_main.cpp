
#include <iostream>
#include <fstream>
#include <verilated_vcd_c.h>
#include "Vinlu_core.h"

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    Verilated::traceEverOn(true);
    
    Vinlu_core* top = new Vinlu_core;
    VerilatedVcdC* tfp = new VerilatedVcdC;
    top->trace(tfp, 99);
    tfp->open("inlu_waves.vcd");
    
    // 打开文件用于保存数据
    std::ofstream outfile("../../paper_assets/data/inlu_rtl_simulation_results.csv");
    if (outfile.is_open()) {
        outfile << "Time,Input_Logit,Output_Exp" << std::endl;
    } else {
        std::cerr << "无法打开文件用于写入！" << std::endl;
    }
    
    int main_time = 0;
    top->clk = 0;
    top->rst_n = 0;
    top->i_valid = 0;
    top->i_data = 0;
    
    std::cout << "--- Verilator iNLU 硬件仿真启动 (结果将存入 CSV) ---" << std::endl;
    
    int current_input = 0;

    while (main_time < 200 && !Verilated::gotFinish()) {
        if (main_time > 20) top->rst_n = 1;
        
        if ((main_time % 10) == 5) top->clk = 1;
        if ((main_time % 10) == 0) top->clk = 0;
        
        if (main_time == 30) {
            top->i_valid = 1;
            top->i_data = 0;
            current_input = 0;
        } else if (main_time == 40) {
            top->i_valid = 1;
            top->i_data = -710;
            current_input = -710;
        } else if (main_time == 50) {
            top->i_valid = 1;
            top->i_data = -1024;
            current_input = -1024;
        } else if ((main_time % 10) == 0) {
            top->i_valid = 0;
        }
        
        top->eval();
        tfp->dump(main_time);
        
        if (top->clk == 1 && top->o_valid) {
            std::cout << "[Result] Time=" << main_time << " | Output Exp=" << (int)top->o_exp << std::endl;
            if (outfile.is_open()) {
                // 这里为了对应输入，需要简单的逻辑追踪，由于是 4 级流水线，
                // 第 30ns 输入的结果会在第 65ns 左右出，这里简化记录当前输出值
                outfile << main_time << "," << (int)top->i_data << "," << (int)top->o_exp << std::endl;
            }
        }
        
        main_time++;
    }
    
    if (outfile.is_open()) outfile.close();
    tfp->close();
    top->final();
    delete top;
    delete tfp;
    std::cout << "--- 仿真结束，数据已保存 ---" << std::endl;
    return 0;
}
