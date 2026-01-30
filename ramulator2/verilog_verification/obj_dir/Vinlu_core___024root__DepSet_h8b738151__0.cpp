// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vinlu_core.h for the primary calling header

#include "Vinlu_core__pch.h"
#include "Vinlu_core___024root.h"

void Vinlu_core___024root___eval_act(Vinlu_core___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root___eval_act\n"); );
}

VL_INLINE_OPT void Vinlu_core___024root___nba_sequent__TOP__0(Vinlu_core___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root___nba_sequent__TOP__0\n"); );
    // Body
    vlSelf->inlu_core__DOT__v4_reg = ((IData)(vlSelf->rst_n) 
                                      && (IData)(vlSelf->inlu_core__DOT__v3_reg));
    if (vlSelf->rst_n) {
        if (vlSelf->inlu_core__DOT__v3_reg) {
            vlSelf->inlu_core__DOT__unnamedblk1__DOT__temp_poly_full 
                = (0x160ULL + VL_SHIFTR_QQI(64,64,32, 
                                            (0x16fULL 
                                             * vlSelf->inlu_core__DOT__f_plus_b_sq_reg), 0x14U));
            vlSelf->inlu_core__DOT__poly_result_reg 
                = (VL_GTES_III(32, 0U, vlSelf->inlu_core__DOT__n3_reg)
                    ? VL_SHIFTR_III(32,32,32, (IData)(vlSelf->inlu_core__DOT__unnamedblk1__DOT__temp_poly_full), 
                                    (- vlSelf->inlu_core__DOT__n3_reg))
                    : VL_SHIFTL_III(32,32,32, (IData)(vlSelf->inlu_core__DOT__unnamedblk1__DOT__temp_poly_full), vlSelf->inlu_core__DOT__n3_reg));
        }
        if (vlSelf->inlu_core__DOT__v2_reg) {
            vlSelf->inlu_core__DOT__f_plus_b_sq_reg 
                = VL_MULS_QQQ(64, VL_EXTENDS_QI(64,32, vlSelf->inlu_core__DOT__f_plus_b_reg), 
                              VL_EXTENDS_QI(64,32, vlSelf->inlu_core__DOT__f_plus_b_reg));
            vlSelf->inlu_core__DOT__n3_reg = vlSelf->inlu_core__DOT__n2_reg;
        }
        if (vlSelf->inlu_core__DOT__v1_reg) {
            vlSelf->inlu_core__DOT__f_plus_b_reg = 
                ((IData)(0x569U) + vlSelf->inlu_core__DOT__f_reg);
            vlSelf->inlu_core__DOT__n2_reg = vlSelf->inlu_core__DOT__n_reg;
        }
        if (vlSelf->i_valid) {
            vlSelf->inlu_core__DOT__f_reg = VL_MODDIVS_III(32, vlSelf->i_data, (IData)(0x2c6U));
            vlSelf->inlu_core__DOT__n_reg = VL_DIVS_III(32, vlSelf->i_data, (IData)(0x2c6U));
        }
    } else {
        vlSelf->inlu_core__DOT__poly_result_reg = 0U;
        vlSelf->inlu_core__DOT__f_plus_b_sq_reg = 0ULL;
        vlSelf->inlu_core__DOT__n3_reg = 0U;
        vlSelf->inlu_core__DOT__f_plus_b_reg = 0U;
        vlSelf->inlu_core__DOT__n2_reg = 0U;
        vlSelf->inlu_core__DOT__f_reg = 0U;
        vlSelf->inlu_core__DOT__n_reg = 0U;
    }
    vlSelf->o_valid = vlSelf->inlu_core__DOT__v4_reg;
    vlSelf->o_exp = vlSelf->inlu_core__DOT__poly_result_reg;
    vlSelf->inlu_core__DOT__v3_reg = ((IData)(vlSelf->rst_n) 
                                      && (IData)(vlSelf->inlu_core__DOT__v2_reg));
    vlSelf->inlu_core__DOT__v2_reg = ((IData)(vlSelf->rst_n) 
                                      && (IData)(vlSelf->inlu_core__DOT__v1_reg));
    vlSelf->inlu_core__DOT__v1_reg = ((IData)(vlSelf->rst_n) 
                                      && (IData)(vlSelf->i_valid));
}

void Vinlu_core___024root___eval_nba(Vinlu_core___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root___eval_nba\n"); );
    // Body
    if ((1ULL & vlSelf->__VnbaTriggered.word(0U))) {
        Vinlu_core___024root___nba_sequent__TOP__0(vlSelf);
        vlSelf->__Vm_traceActivity[1U] = 1U;
    }
}

void Vinlu_core___024root___eval_triggers__act(Vinlu_core___024root* vlSelf);

bool Vinlu_core___024root___eval_phase__act(Vinlu_core___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root___eval_phase__act\n"); );
    // Init
    VlTriggerVec<1> __VpreTriggered;
    CData/*0:0*/ __VactExecute;
    // Body
    Vinlu_core___024root___eval_triggers__act(vlSelf);
    __VactExecute = vlSelf->__VactTriggered.any();
    if (__VactExecute) {
        __VpreTriggered.andNot(vlSelf->__VactTriggered, vlSelf->__VnbaTriggered);
        vlSelf->__VnbaTriggered.thisOr(vlSelf->__VactTriggered);
        Vinlu_core___024root___eval_act(vlSelf);
    }
    return (__VactExecute);
}

bool Vinlu_core___024root___eval_phase__nba(Vinlu_core___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root___eval_phase__nba\n"); );
    // Init
    CData/*0:0*/ __VnbaExecute;
    // Body
    __VnbaExecute = vlSelf->__VnbaTriggered.any();
    if (__VnbaExecute) {
        Vinlu_core___024root___eval_nba(vlSelf);
        vlSelf->__VnbaTriggered.clear();
    }
    return (__VnbaExecute);
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vinlu_core___024root___dump_triggers__nba(Vinlu_core___024root* vlSelf);
#endif  // VL_DEBUG
#ifdef VL_DEBUG
VL_ATTR_COLD void Vinlu_core___024root___dump_triggers__act(Vinlu_core___024root* vlSelf);
#endif  // VL_DEBUG

void Vinlu_core___024root___eval(Vinlu_core___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root___eval\n"); );
    // Init
    IData/*31:0*/ __VnbaIterCount;
    CData/*0:0*/ __VnbaContinue;
    // Body
    __VnbaIterCount = 0U;
    __VnbaContinue = 1U;
    while (__VnbaContinue) {
        if (VL_UNLIKELY((0x64U < __VnbaIterCount))) {
#ifdef VL_DEBUG
            Vinlu_core___024root___dump_triggers__nba(vlSelf);
#endif
            VL_FATAL_MT("sources/inlu_core.sv", 13, "", "NBA region did not converge.");
        }
        __VnbaIterCount = ((IData)(1U) + __VnbaIterCount);
        __VnbaContinue = 0U;
        vlSelf->__VactIterCount = 0U;
        vlSelf->__VactContinue = 1U;
        while (vlSelf->__VactContinue) {
            if (VL_UNLIKELY((0x64U < vlSelf->__VactIterCount))) {
#ifdef VL_DEBUG
                Vinlu_core___024root___dump_triggers__act(vlSelf);
#endif
                VL_FATAL_MT("sources/inlu_core.sv", 13, "", "Active region did not converge.");
            }
            vlSelf->__VactIterCount = ((IData)(1U) 
                                       + vlSelf->__VactIterCount);
            vlSelf->__VactContinue = 0U;
            if (Vinlu_core___024root___eval_phase__act(vlSelf)) {
                vlSelf->__VactContinue = 1U;
            }
        }
        if (Vinlu_core___024root___eval_phase__nba(vlSelf)) {
            __VnbaContinue = 1U;
        }
    }
}

#ifdef VL_DEBUG
void Vinlu_core___024root___eval_debug_assertions(Vinlu_core___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root___eval_debug_assertions\n"); );
    // Body
    if (VL_UNLIKELY((vlSelf->clk & 0xfeU))) {
        Verilated::overWidthError("clk");}
    if (VL_UNLIKELY((vlSelf->rst_n & 0xfeU))) {
        Verilated::overWidthError("rst_n");}
    if (VL_UNLIKELY((vlSelf->i_valid & 0xfeU))) {
        Verilated::overWidthError("i_valid");}
}
#endif  // VL_DEBUG
