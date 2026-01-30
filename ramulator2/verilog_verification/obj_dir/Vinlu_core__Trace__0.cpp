// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Tracing implementation internals
#include "verilated_vcd_c.h"
#include "Vinlu_core__Syms.h"


void Vinlu_core___024root__trace_chg_0_sub_0(Vinlu_core___024root* vlSelf, VerilatedVcd::Buffer* bufp);

void Vinlu_core___024root__trace_chg_0(void* voidSelf, VerilatedVcd::Buffer* bufp) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root__trace_chg_0\n"); );
    // Init
    Vinlu_core___024root* const __restrict vlSelf VL_ATTR_UNUSED = static_cast<Vinlu_core___024root*>(voidSelf);
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    if (VL_UNLIKELY(!vlSymsp->__Vm_activity)) return;
    // Body
    Vinlu_core___024root__trace_chg_0_sub_0((&vlSymsp->TOP), bufp);
}

void Vinlu_core___024root__trace_chg_0_sub_0(Vinlu_core___024root* vlSelf, VerilatedVcd::Buffer* bufp) {
    if (false && vlSelf) {}  // Prevent unused
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root__trace_chg_0_sub_0\n"); );
    // Init
    uint32_t* const oldp VL_ATTR_UNUSED = bufp->oldp(vlSymsp->__Vm_baseCode + 1);
    // Body
    if (VL_UNLIKELY(vlSelf->__Vm_traceActivity[1U])) {
        bufp->chgIData(oldp+0,(vlSelf->inlu_core__DOT__n_reg),32);
        bufp->chgIData(oldp+1,(vlSelf->inlu_core__DOT__f_reg),32);
        bufp->chgBit(oldp+2,(vlSelf->inlu_core__DOT__v1_reg));
        bufp->chgIData(oldp+3,(vlSelf->inlu_core__DOT__f_plus_b_reg),32);
        bufp->chgIData(oldp+4,(vlSelf->inlu_core__DOT__n2_reg),32);
        bufp->chgBit(oldp+5,(vlSelf->inlu_core__DOT__v2_reg));
        bufp->chgQData(oldp+6,(vlSelf->inlu_core__DOT__f_plus_b_sq_reg),64);
        bufp->chgIData(oldp+8,(vlSelf->inlu_core__DOT__n3_reg),32);
        bufp->chgBit(oldp+9,(vlSelf->inlu_core__DOT__v3_reg));
        bufp->chgIData(oldp+10,(vlSelf->inlu_core__DOT__poly_result_reg),32);
        bufp->chgBit(oldp+11,(vlSelf->inlu_core__DOT__v4_reg));
        bufp->chgQData(oldp+12,(vlSelf->inlu_core__DOT__unnamedblk1__DOT__temp_poly_full),64);
    }
    bufp->chgBit(oldp+14,(vlSelf->clk));
    bufp->chgBit(oldp+15,(vlSelf->rst_n));
    bufp->chgBit(oldp+16,(vlSelf->i_valid));
    bufp->chgIData(oldp+17,(vlSelf->i_data),32);
    bufp->chgBit(oldp+18,(vlSelf->o_valid));
    bufp->chgIData(oldp+19,(vlSelf->o_exp),32);
}

void Vinlu_core___024root__trace_cleanup(void* voidSelf, VerilatedVcd* /*unused*/) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vinlu_core___024root__trace_cleanup\n"); );
    // Init
    Vinlu_core___024root* const __restrict vlSelf VL_ATTR_UNUSED = static_cast<Vinlu_core___024root*>(voidSelf);
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    // Body
    vlSymsp->__Vm_activity = false;
    vlSymsp->TOP.__Vm_traceActivity[0U] = 0U;
    vlSymsp->TOP.__Vm_traceActivity[1U] = 0U;
}
