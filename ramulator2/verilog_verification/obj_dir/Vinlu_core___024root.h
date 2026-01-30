// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vinlu_core.h for the primary calling header

#ifndef VERILATED_VINLU_CORE___024ROOT_H_
#define VERILATED_VINLU_CORE___024ROOT_H_  // guard

#include "verilated.h"


class Vinlu_core__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vinlu_core___024root final : public VerilatedModule {
  public:

    // DESIGN SPECIFIC STATE
    VL_IN8(clk,0,0);
    VL_IN8(rst_n,0,0);
    VL_IN8(i_valid,0,0);
    VL_OUT8(o_valid,0,0);
    CData/*0:0*/ inlu_core__DOT__v1_reg;
    CData/*0:0*/ inlu_core__DOT__v2_reg;
    CData/*0:0*/ inlu_core__DOT__v3_reg;
    CData/*0:0*/ inlu_core__DOT__v4_reg;
    CData/*0:0*/ __VstlFirstIteration;
    CData/*0:0*/ __Vtrigprevexpr___TOP__clk__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__rst_n__0;
    CData/*0:0*/ __VactContinue;
    VL_IN(i_data,31,0);
    VL_OUT(o_exp,31,0);
    IData/*31:0*/ inlu_core__DOT__n_reg;
    IData/*31:0*/ inlu_core__DOT__f_reg;
    IData/*31:0*/ inlu_core__DOT__f_plus_b_reg;
    IData/*31:0*/ inlu_core__DOT__n2_reg;
    IData/*31:0*/ inlu_core__DOT__n3_reg;
    IData/*31:0*/ inlu_core__DOT__poly_result_reg;
    IData/*31:0*/ __VactIterCount;
    QData/*63:0*/ inlu_core__DOT__f_plus_b_sq_reg;
    QData/*63:0*/ inlu_core__DOT__unnamedblk1__DOT__temp_poly_full;
    VlUnpacked<CData/*0:0*/, 2> __Vm_traceActivity;
    VlTriggerVec<1> __VstlTriggered;
    VlTriggerVec<1> __VactTriggered;
    VlTriggerVec<1> __VnbaTriggered;

    // INTERNAL VARIABLES
    Vinlu_core__Syms* const vlSymsp;

    // CONSTRUCTORS
    Vinlu_core___024root(Vinlu_core__Syms* symsp, const char* v__name);
    ~Vinlu_core___024root();
    VL_UNCOPYABLE(Vinlu_core___024root);

    // INTERNAL METHODS
    void __Vconfigure(bool first);
};


#endif  // guard
