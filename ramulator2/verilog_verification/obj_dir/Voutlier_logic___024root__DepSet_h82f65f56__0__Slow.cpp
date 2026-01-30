// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Voutlier_logic.h for the primary calling header

#include "Voutlier_logic__pch.h"
#include "Voutlier_logic___024root.h"

VL_ATTR_COLD void Voutlier_logic___024root___eval_static(Voutlier_logic___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Voutlier_logic__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Voutlier_logic___024root___eval_static\n"); );
}

VL_ATTR_COLD void Voutlier_logic___024root___eval_initial(Voutlier_logic___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Voutlier_logic__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Voutlier_logic___024root___eval_initial\n"); );
    // Body
    vlSelf->__Vtrigprevexpr___TOP__clk__0 = vlSelf->clk;
    vlSelf->__Vtrigprevexpr___TOP__rst_n__0 = vlSelf->rst_n;
}

VL_ATTR_COLD void Voutlier_logic___024root___eval_final(Voutlier_logic___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Voutlier_logic__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Voutlier_logic___024root___eval_final\n"); );
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Voutlier_logic___024root___dump_triggers__stl(Voutlier_logic___024root* vlSelf);
#endif  // VL_DEBUG
VL_ATTR_COLD bool Voutlier_logic___024root___eval_phase__stl(Voutlier_logic___024root* vlSelf);

VL_ATTR_COLD void Voutlier_logic___024root___eval_settle(Voutlier_logic___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Voutlier_logic__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Voutlier_logic___024root___eval_settle\n"); );
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
            Voutlier_logic___024root___dump_triggers__stl(vlSelf);
#endif
            VL_FATAL_MT("sources/outlier_logic.sv", 16, "", "Settle region did not converge.");
        }
        __VstlIterCount = ((IData)(1U) + __VstlIterCount);
        __VstlContinue = 0U;
        if (Voutlier_logic___024root___eval_phase__stl(vlSelf)) {
            __VstlContinue = 1U;
        }
        vlSelf->__VstlFirstIteration = 0U;
    }
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Voutlier_logic___024root___dump_triggers__stl(Voutlier_logic___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Voutlier_logic__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Voutlier_logic___024root___dump_triggers__stl\n"); );
    // Body
    if ((1U & (~ (IData)(vlSelf->__VstlTriggered.any())))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelf->__VstlTriggered.word(0U))) {
        VL_DBG_MSGF("         'stl' region trigger index 0 is active: Internal 'stl' trigger - first iteration\n");
    }
}
#endif  // VL_DEBUG

void Voutlier_logic___024root___ico_sequent__TOP__0(Voutlier_logic___024root* vlSelf);

VL_ATTR_COLD void Voutlier_logic___024root___eval_stl(Voutlier_logic___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Voutlier_logic__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Voutlier_logic___024root___eval_stl\n"); );
    // Body
    if ((1ULL & vlSelf->__VstlTriggered.word(0U))) {
        Voutlier_logic___024root___ico_sequent__TOP__0(vlSelf);
    }
}

VL_ATTR_COLD void Voutlier_logic___024root___eval_triggers__stl(Voutlier_logic___024root* vlSelf);

VL_ATTR_COLD bool Voutlier_logic___024root___eval_phase__stl(Voutlier_logic___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Voutlier_logic__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Voutlier_logic___024root___eval_phase__stl\n"); );
    // Init
    CData/*0:0*/ __VstlExecute;
    // Body
    Voutlier_logic___024root___eval_triggers__stl(vlSelf);
    __VstlExecute = vlSelf->__VstlTriggered.any();
    if (__VstlExecute) {
        Voutlier_logic___024root___eval_stl(vlSelf);
    }
    return (__VstlExecute);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Voutlier_logic___024root___dump_triggers__ico(Voutlier_logic___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Voutlier_logic__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Voutlier_logic___024root___dump_triggers__ico\n"); );
    // Body
    if ((1U & (~ (IData)(vlSelf->__VicoTriggered.any())))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelf->__VicoTriggered.word(0U))) {
        VL_DBG_MSGF("         'ico' region trigger index 0 is active: Internal 'ico' trigger - first iteration\n");
    }
}
#endif  // VL_DEBUG

#ifdef VL_DEBUG
VL_ATTR_COLD void Voutlier_logic___024root___dump_triggers__act(Voutlier_logic___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Voutlier_logic__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Voutlier_logic___024root___dump_triggers__act\n"); );
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
VL_ATTR_COLD void Voutlier_logic___024root___dump_triggers__nba(Voutlier_logic___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Voutlier_logic__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Voutlier_logic___024root___dump_triggers__nba\n"); );
    // Body
    if ((1U & (~ (IData)(vlSelf->__VnbaTriggered.any())))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelf->__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 0 is active: @(posedge clk or negedge rst_n)\n");
    }
}
#endif  // VL_DEBUG

VL_ATTR_COLD void Voutlier_logic___024root___ctor_var_reset(Voutlier_logic___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Voutlier_logic__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Voutlier_logic___024root___ctor_var_reset\n"); );
    // Body
    vlSelf->clk = VL_RAND_RESET_I(1);
    vlSelf->rst_n = VL_RAND_RESET_I(1);
    vlSelf->i_valid = VL_RAND_RESET_I(1);
    vlSelf->i_data = VL_RAND_RESET_I(32);
    vlSelf->i_threshold = VL_RAND_RESET_I(32);
    vlSelf->o_valid = VL_RAND_RESET_I(1);
    vlSelf->o_data_int8 = VL_RAND_RESET_I(8);
    vlSelf->o_is_outlier = VL_RAND_RESET_I(1);
    vlSelf->o_outlier_val = VL_RAND_RESET_I(32);
    vlSelf->o_buffer_full = VL_RAND_RESET_I(1);
    vlSelf->outlier_logic__DOT__is_outlier_comb = VL_RAND_RESET_I(1);
    vlSelf->outlier_logic__DOT__outlier_count = VL_RAND_RESET_I(8);
    vlSelf->__Vtrigprevexpr___TOP__clk__0 = VL_RAND_RESET_I(1);
    vlSelf->__Vtrigprevexpr___TOP__rst_n__0 = VL_RAND_RESET_I(1);
}
