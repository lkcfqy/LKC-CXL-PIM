// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Model implementation (design independent parts)

#include "Voutlier_logic__pch.h"

//============================================================
// Constructors

Voutlier_logic::Voutlier_logic(VerilatedContext* _vcontextp__, const char* _vcname__)
    : VerilatedModel{*_vcontextp__}
    , vlSymsp{new Voutlier_logic__Syms(contextp(), _vcname__, this)}
    , clk{vlSymsp->TOP.clk}
    , rst_n{vlSymsp->TOP.rst_n}
    , i_valid{vlSymsp->TOP.i_valid}
    , o_valid{vlSymsp->TOP.o_valid}
    , o_data_int8{vlSymsp->TOP.o_data_int8}
    , o_is_outlier{vlSymsp->TOP.o_is_outlier}
    , o_buffer_full{vlSymsp->TOP.o_buffer_full}
    , i_data{vlSymsp->TOP.i_data}
    , i_threshold{vlSymsp->TOP.i_threshold}
    , o_outlier_val{vlSymsp->TOP.o_outlier_val}
    , rootp{&(vlSymsp->TOP)}
{
    // Register model with the context
    contextp()->addModel(this);
}

Voutlier_logic::Voutlier_logic(const char* _vcname__)
    : Voutlier_logic(Verilated::threadContextp(), _vcname__)
{
}

//============================================================
// Destructor

Voutlier_logic::~Voutlier_logic() {
    delete vlSymsp;
}

//============================================================
// Evaluation function

#ifdef VL_DEBUG
void Voutlier_logic___024root___eval_debug_assertions(Voutlier_logic___024root* vlSelf);
#endif  // VL_DEBUG
void Voutlier_logic___024root___eval_static(Voutlier_logic___024root* vlSelf);
void Voutlier_logic___024root___eval_initial(Voutlier_logic___024root* vlSelf);
void Voutlier_logic___024root___eval_settle(Voutlier_logic___024root* vlSelf);
void Voutlier_logic___024root___eval(Voutlier_logic___024root* vlSelf);

void Voutlier_logic::eval_step() {
    VL_DEBUG_IF(VL_DBG_MSGF("+++++TOP Evaluate Voutlier_logic::eval_step\n"); );
#ifdef VL_DEBUG
    // Debug assertions
    Voutlier_logic___024root___eval_debug_assertions(&(vlSymsp->TOP));
#endif  // VL_DEBUG
    vlSymsp->__Vm_deleter.deleteAll();
    if (VL_UNLIKELY(!vlSymsp->__Vm_didInit)) {
        vlSymsp->__Vm_didInit = true;
        VL_DEBUG_IF(VL_DBG_MSGF("+ Initial\n"););
        Voutlier_logic___024root___eval_static(&(vlSymsp->TOP));
        Voutlier_logic___024root___eval_initial(&(vlSymsp->TOP));
        Voutlier_logic___024root___eval_settle(&(vlSymsp->TOP));
    }
    VL_DEBUG_IF(VL_DBG_MSGF("+ Eval\n"););
    Voutlier_logic___024root___eval(&(vlSymsp->TOP));
    // Evaluate cleanup
    Verilated::endOfEval(vlSymsp->__Vm_evalMsgQp);
}

//============================================================
// Events and timing
bool Voutlier_logic::eventsPending() { return false; }

uint64_t Voutlier_logic::nextTimeSlot() {
    VL_FATAL_MT(__FILE__, __LINE__, "", "%Error: No delays in the design");
    return 0;
}

//============================================================
// Utilities

const char* Voutlier_logic::name() const {
    return vlSymsp->name();
}

//============================================================
// Invoke final blocks

void Voutlier_logic___024root___eval_final(Voutlier_logic___024root* vlSelf);

VL_ATTR_COLD void Voutlier_logic::final() {
    Voutlier_logic___024root___eval_final(&(vlSymsp->TOP));
}

//============================================================
// Implementations of abstract methods from VerilatedModel

const char* Voutlier_logic::hierName() const { return vlSymsp->name(); }
const char* Voutlier_logic::modelName() const { return "Voutlier_logic"; }
unsigned Voutlier_logic::threads() const { return 1; }
void Voutlier_logic::prepareClone() const { contextp()->prepareClone(); }
void Voutlier_logic::atClone() const {
    contextp()->threadPoolpOnClone();
}

//============================================================
// Trace configuration

VL_ATTR_COLD void Voutlier_logic::trace(VerilatedVcdC* tfp, int levels, int options) {
    vl_fatal(__FILE__, __LINE__, __FILE__,"'Voutlier_logic::trace()' called on model that was Verilated without --trace option");
}
