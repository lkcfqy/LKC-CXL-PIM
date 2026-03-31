#include <iostream>
#include <fstream>
#include <verilated.h>
#include <verilated_vcd_c.h>
#include "Vdistributed_reduce.h"

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    Verilated::traceEverOn(true);
    
    Vdistributed_reduce* top = new Vdistributed_reduce;
    VerilatedVcdC* tfp = new VerilatedVcdC;
    top->trace(tfp, 99);
    tfp->open("dist_reduce_waves.vcd");
    
    int main_time = 0;
    top->clk = 0;
    top->rst_n = 0;
    
    std::cout << "--- Verilator 分布式 Reduce 硬件仿真启动 ---" << std::endl;
    
    while (main_time < 300 && !Verilated::gotFinish()) {
        if (main_time > 20) top->rst_n = 1;
        
        if ((main_time % 10) == 5) top->clk = 1;
        if ((main_time % 10) == 0) top->clk = 0;
        
        // 模拟外部激励，类似于 SystemVerilog TB 的 Test 1 和 Test 2
        // 这里提供一个简单的框架，由于实际测试已经在 TB 中定义
        // 这里的循环将简单地让时钟步进并记录波形
        
        top->eval();
        tfp->dump(main_time);
        
        if (top->clk == 1 && top->o_timeout_err) {
            std::cout << "[Time=" << main_time << "] Catch Timeout Error! FSM returns to IDLE to avoid DL." << std::endl;
        }
        
        main_time++;
    }
    
    tfp->close();
    top->final();
    delete top;
    delete tfp;
    std::cout << "--- 仿真结束 ---" << std::endl;
    return 0;
}
