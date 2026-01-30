// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Voutlier_logic.h for the primary calling header

#include "Voutlier_logic__pch.h"
#include "Voutlier_logic__Syms.h"
#include "Voutlier_logic___024root.h"

#ifdef VL_DEBUG
VL_ATTR_COLD void Voutlier_logic___024root___dump_triggers__stl(Voutlier_logic___024root* vlSelf);
#endif  // VL_DEBUG

VL_ATTR_COLD void Voutlier_logic___024root___eval_triggers__stl(Voutlier_logic___024root* vlSelf) {
    if (false && vlSelf) {}  // Prevent unused
    Voutlier_logic__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    VL_DEBUG_IF(VL_DBG_MSGF("+    Voutlier_logic___024root___eval_triggers__stl\n"); );
    // Body
    vlSelf->__VstlTriggered.set(0U, (IData)(vlSelf->__VstlFirstIteration));
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Voutlier_logic___024root___dump_triggers__stl(vlSelf);
    }
#endif
}
