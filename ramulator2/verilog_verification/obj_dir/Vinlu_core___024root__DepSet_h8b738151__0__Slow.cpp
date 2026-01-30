// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vinlu_core.h for the primary calling header

#include "Vinlu_core__pch.h"
#include "Vinlu_core___024root.h"

VL_ATTR_COLD void Vinlu_core___024root___eval_static(Vinlu_core___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root___eval_static\n"); );
}

VL_ATTR_COLD void Vinlu_core___024root___eval_initial(Vinlu_core___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root___eval_initial\n"); );
    // Body
    vlSelf->__Vtrigprevexpr___TOP__clk__0 = vlSelf->clk;
    vlSelf->__Vtrigprevexpr___TOP__rst_n__0 = vlSelf->rst_n;
}

VL_ATTR_COLD void Vinlu_core___024root___eval_final(Vinlu_core___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root___eval_final\n"); );
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vinlu_core___024root___dump_triggers__stl(Vinlu_core___024root* vlSelf);
#endif  // VL_DEBUG
VL_ATTR_COLD bool Vinlu_core___024root___eval_phase__stl(Vinlu_core___024root* vlSelf);

VL_ATTR_COLD void Vinlu_core___024root___eval_settle(Vinlu_core___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root___eval_settle\n"); );
    // Init
    IData/*31:0*/ __VstlIterCount;
    CData/*0:0*/ __VstlContinue;
    // Body
    __VstlIterCount = 0U;
    vlSelf->__VstlFirstIteration = 1U;
    __VstlContinue = 1U;
    while (__VstlContinue) {
        if (VL_UNLIKELY((0x64U < __VstlIterCount))) {
#ifdef VL_DEBUG
            Vinlu_core___024root___dump_triggers__stl(vlSelf);
#endif
            VL_FATAL_MT("sources/inlu_core.sv", 13, "", "Settle region did not converge.");
        }
        __VstlIterCount = ((IData)(1U) + __VstlIterCount);
        __VstlContinue = 0U;
        if (Vinlu_core___024root___eval_phase__stl(vlSelf)) {
            __VstlContinue = 1U;
        }
        vlSelf->__VstlFirstIteration = 0U;
    }
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vinlu_core___024root___dump_triggers__stl(Vinlu_core___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root___dump_triggers__stl\n"); );
    // Body
    if ((1U & (~ (IData)(vlSelf->__VstlTriggered.any())))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelf->__VstlTriggered.word(0U))) {
        VL_DBG_MSGF("         'stl' region trigger index 0 is active: Internal 'stl' trigger - first iteration\n");
    }
}
#endif  // VL_DEBUG

VL_ATTR_COLD void Vinlu_core___024root___stl_sequent__TOP__0(Vinlu_core___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root___stl_sequent__TOP__0\n"); );
    // Body
    vlSelf->o_valid = vlSelf->inlu_core__DOT__v4_reg;
    vlSelf->o_exp = vlSelf->inlu_core__DOT__poly_result_reg;
}

VL_ATTR_COLD void Vinlu_core___024root___eval_stl(Vinlu_core___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root___eval_stl\n"); );
    // Body
    if ((1ULL & vlSelf->__VstlTriggered.word(0U))) {
        Vinlu_core___024root___stl_sequent__TOP__0(vlSelf);
    }
}

VL_ATTR_COLD void Vinlu_core___024root___eval_triggers__stl(Vinlu_core___024root* vlSelf);

VL_ATTR_COLD bool Vinlu_core___024root___eval_phase__stl(Vinlu_core___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root___eval_phase__stl\n"); );
    // Init
    CData/*0:0*/ __VstlExecute;
    // Body
    Vinlu_core___024root___eval_triggers__stl(vlSelf);
    __VstlExecute = vlSelf->__VstlTriggered.any();
    if (__VstlExecute) {
        Vinlu_core___024root___eval_stl(vlSelf);
    }
    return (__VstlExecute);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vinlu_core___024root___dump_triggers__act(Vinlu_core___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root___dump_triggers__act\n"); );
    // Body
    if ((1U & (~ (IData)(vlSelf->__VactTriggered.any())))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelf->__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 0 is active: @(posedge clk or negedge rst_n)\n");
    }
}
#endif  // VL_DEBUG

#ifdef VL_DEBUG
VL_ATTR_COLD void Vinlu_core___024root___dump_triggers__nba(Vinlu_core___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root___dump_triggers__nba\n"); );
    // Body
    if ((1U & (~ (IData)(vlSelf->__VnbaTriggered.any())))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelf->__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 0 is active: @(posedge clk or negedge rst_n)\n");
    }
}
#endif  // VL_DEBUG

VL_ATTR_COLD void Vinlu_core___024root___ctor_var_reset(Vinlu_core___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root___ctor_var_reset\n"); );
    // Body
    vlSelf->clk = VL_RAND_RESET_I(1);
    vlSelf->rst_n = VL_RAND_RESET_I(1);
    vlSelf->i_valid = VL_RAND_RESET_I(1);
    vlSelf->i_data = VL_RAND_RESET_I(32);
    vlSelf->o_valid = VL_RAND_RESET_I(1);
    vlSelf->o_exp = VL_RAND_RESET_I(32);
    vlSelf->inlu_core__DOT__n_reg = VL_RAND_RESET_I(32);
    vlSelf->inlu_core__DOT__f_reg = VL_RAND_RESET_I(32);
    vlSelf->inlu_core__DOT__v1_reg = VL_RAND_RESET_I(1);
    vlSelf->inlu_core__DOT__f_plus_b_reg = VL_RAND_RESET_I(32);
    vlSelf->inlu_core__DOT__n2_reg = VL_RAND_RESET_I(32);
    vlSelf->inlu_core__DOT__v2_reg = VL_RAND_RESET_I(1);
    vlSelf->inlu_core__DOT__f_plus_b_sq_reg = VL_RAND_RESET_Q(64);
    vlSelf->inlu_core__DOT__n3_reg = VL_RAND_RESET_I(32);
    vlSelf->inlu_core__DOT__v3_reg = VL_RAND_RESET_I(1);
    vlSelf->inlu_core__DOT__poly_result_reg = VL_RAND_RESET_I(32);
    vlSelf->inlu_core__DOT__v4_reg = VL_RAND_RESET_I(1);
    vlSelf->inlu_core__DOT__unnamedblk1__DOT__temp_poly_full = VL_RAND_RESET_Q(64);
    vlSelf->__Vtrigprevexpr___TOP__clk__0 = VL_RAND_RESET_I(1);
    vlSelf->__Vtrigprevexpr___TOP__rst_n__0 = VL_RAND_RESET_I(1);
    for (int __Vi0 = 0; __Vi0 < 2; ++__Vi0) {
        vlSelf->__Vm_traceActivity[__Vi0] = 0;
    }
}
