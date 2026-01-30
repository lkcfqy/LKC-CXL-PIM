
#include <iostream>
#include <fstream>
#include <verilated.h>
#include "Voutlier_logic.h"

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    Voutlier_logic* top = new Voutlier_logic;
    
    std::ofstream outfile("../../paper_assets/data/outlier_rtl_simulation_results.csv");
    if (outfile.is_open()) {
        outfile << "Time,Input_Data,Is_Outlier,Outlier_Val,Buffer_Full" << std::endl;
    }

    int main_time = 0;
    top->clk = 0;
    top->rst_n = 0;
    top->i_valid = 0;
    top->i_data = 0;
    top->i_threshold = 1000;
    
    std::cout << "--- Verilator Outlier-Aware Logic 硬件仿真启动 (保存至 CSV) ---" << std::endl;
    
    while (main_time < 200 && !Verilated::gotFinish()) {
        if (main_time > 20) top->rst_n = 1;
        if ((main_time % 10) == 5) top->clk = 1;
        if ((main_time % 10) == 0) top->clk = 0;
        
        if (main_time == 30) {
            top->i_valid = 1; top->i_data = 800;
        } else if (main_time == 40) {
            top->i_valid = 1; top->i_data = 2500;
        } else if (main_time == 50) {
            top->i_valid = 1; top->i_data = -3000;
        } else if (main_time >= 60 && main_time <= 150 && (main_time % 10 == 0)) {
            top->i_valid = 1; top->i_data = 5000;
        } else if ((main_time % 10) == 0) {
            top->i_valid = 0;
        }
        
        top->eval();
        
        if (top->clk == 1 && top->o_valid) {
            if (outfile.is_open()) {
                outfile << main_time << "," << (int)top->i_data << "," << (int)top->o_is_outlier << "," 
                        << (int)top->o_outlier_val << "," << (int)top->o_buffer_full << std::endl;
            }
        }
        main_time++;
    }
    
    if (outfile.is_open()) outfile.close();
    top->final();
    delete top;
    std::cout << "--- 仿真结束 ---" << std::endl;
    return 0;
}
