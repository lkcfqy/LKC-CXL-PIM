// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vinlu_core.h for the primary calling header

#include "Vinlu_core__pch.h"
#include "Vinlu_core__Syms.h"
#include "Vinlu_core___024root.h"

void Vinlu_core___024root___ctor_var_reset(Vinlu_core___024root* vlSelf);

Vinlu_core___024root::Vinlu_core___024root(Vinlu_core__Syms* symsp, const char* v__name)
    : VerilatedModule{v__name}
    , vlSymsp{symsp}
 {
    // Reset structure values
    Vinlu_core___024root___ctor_var_reset(this);
}

void Vinlu_core___024root::__Vconfigure(bool first) {
    if (false && first) {}  // Prevent unused
}

Vinlu_core___024root::~Vinlu_core___024root() {
}
