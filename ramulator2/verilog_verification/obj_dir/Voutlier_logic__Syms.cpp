// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table implementation internals

#include "Voutlier_logic__pch.h"
#include "Voutlier_logic.h"
#include "Voutlier_logic___024root.h"

// FUNCTIONS
Voutlier_logic__Syms::~Voutlier_logic__Syms()
{
}

Voutlier_logic__Syms::Voutlier_logic__Syms(VerilatedContext* contextp, const char* namep, Voutlier_logic* modelp)
    : VerilatedSyms{contextp}
    // Setup internal state of the Syms class
    , __Vm_modelp{modelp}
    // Setup module instances
    , TOP{this, namep}
{
    // Configure time unit / time precision
    _vm_contextp__->timeunit(-12);
    _vm_contextp__->timeprecision(-12);
    // Setup each module's pointers to their submodules
    // Setup each module's pointer back to symbol table (for public functions)
    TOP.__Vconfigure(true);
}
