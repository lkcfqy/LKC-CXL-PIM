// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Voutlier_logic.h for the primary calling header

#ifndef VERILATED_VOUTLIER_LOGIC___024ROOT_H_
#define VERILATED_VOUTLIER_LOGIC___024ROOT_H_  // guard

#include "verilated.h"


class Voutlier_logic__Syms;

class alignas(VL_CACHE_LINE_BYTES) Voutlier_logic___024root final : public VerilatedModule {
  public:

    // DESIGN SPECIFIC STATE
    VL_IN8(clk,0,0);
    VL_IN8(rst_n,0,0);
    VL_IN8(i_valid,0,0);
    VL_OUT8(o_valid,0,0);
    VL_OUT8(o_data_int8,7,0);
    VL_OUT8(o_is_outlier,0,0);
    VL_OUT8(o_buffer_full,0,0);
    CData/*0:0*/ outlier_logic__DOT__is_outlier_comb;
    CData/*7:0*/ outlier_logic__DOT__outlier_count;
    CData/*0:0*/ __VstlFirstIteration;
    CData/*0:0*/ __VicoFirstIteration;
    CData/*0:0*/ __Vtrigprevexpr___TOP__clk__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__rst_n__0;
    CData/*0:0*/ __VactContinue;
    VL_IN(i_data,31,0);
    VL_IN(i_threshold,31,0);
    VL_OUT(o_outlier_val,31,0);
    IData/*31:0*/ __VactIterCount;
    VlTriggerVec<1> __VstlTriggered;
    VlTriggerVec<1> __VicoTriggered;
    VlTriggerVec<1> __VactTriggered;
    VlTriggerVec<1> __VnbaTriggered;

    // INTERNAL VARIABLES
    Voutlier_logic__Syms* const vlSymsp;

    // CONSTRUCTORS
    Voutlier_logic___024root(Voutlier_logic__Syms* symsp, const char* v__name);
    ~Voutlier_logic___024root();
    VL_UNCOPYABLE(Voutlier_logic___024root);

    // INTERNAL METHODS
    void __Vconfigure(bool first);
};


#endif  // guard
