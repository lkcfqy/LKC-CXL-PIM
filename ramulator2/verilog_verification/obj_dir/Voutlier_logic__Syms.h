// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table internal header
//
// Internal details; most calling programs do not need this header,
// unless using verilator public meta comments.

#ifndef VERILATED_VOUTLIER_LOGIC__SYMS_H_
#define VERILATED_VOUTLIER_LOGIC__SYMS_H_  // guard

#include "verilated.h"

// INCLUDE MODEL CLASS

#include "Voutlier_logic.h"

// INCLUDE MODULE CLASSES
#include "Voutlier_logic___024root.h"

// SYMS CLASS (contains all model state)
class alignas(VL_CACHE_LINE_BYTES)Voutlier_logic__Syms final : public VerilatedSyms {
  public:
    // INTERNAL STATE
    Voutlier_logic* const __Vm_modelp;
    VlDeleter __Vm_deleter;
    bool __Vm_didInit = false;

    // MODULE INSTANCE STATE
    Voutlier_logic___024root       TOP;

    // CONSTRUCTORS
    Voutlier_logic__Syms(VerilatedContext* contextp, const char* namep, Voutlier_logic* modelp);
    ~Voutlier_logic__Syms();

    // METHODS
    const char* name() { return TOP.name(); }
};

#endif  // guard
