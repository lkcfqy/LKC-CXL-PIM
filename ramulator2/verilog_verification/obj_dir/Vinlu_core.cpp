// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Model implementation (design independent parts)

#include "Vinlu_core__pch.h"
#include "verilated_vcd_c.h"

//============================================================
// Constructors

Vinlu_core::Vinlu_core(VerilatedContext* _vcontextp__, const char* _vcname__)
    : VerilatedModel{*_vcontextp__}
    , vlSymsp{new Vinlu_core__Syms(contextp(), _vcname__, this)}
    , clk{vlSymsp->TOP.clk}
    , rst_n{vlSymsp->TOP.rst_n}
    , i_valid{vlSymsp->TOP.i_valid}
    , o_valid{vlSymsp->TOP.o_valid}
    , i_data{vlSymsp->TOP.i_data}
    , o_exp{vlSymsp->TOP.o_exp}
    , rootp{&(vlSymsp->TOP)}
{
    // Register model with the context
    contextp()->addModel(this);
}

Vinlu_core::Vinlu_core(const char* _vcname__)
    : Vinlu_core(Verilated::threadContextp(), _vcname__)
{
}

//============================================================
// Destructor

Vinlu_core::~Vinlu_core() {
    delete vlSymsp;
}

//============================================================
// Evaluation function

#ifdef VL_DEBUG
void Vinlu_core___024root___eval_debug_assertions(Vinlu_core___024root* vlSelf);
#endif  // VL_DEBUG
void Vinlu_core___024root___eval_static(Vinlu_core___024root* vlSelf);
void Vinlu_core___024root___eval_initial(Vinlu_core___024root* vlSelf);
void Vinlu_core___024root___eval_settle(Vinlu_core___024root* vlSelf);
void Vinlu_core___024root___eval(Vinlu_core___024root* vlSelf);

void Vinlu_core::eval_step() {
    VL_DEBUG_IF(VL_DBG_MSGF("+++++TOP Evaluate Vinlu_core::eval_step\n"); );
#ifdef VL_DEBUG
    // Debug assertions
    Vinlu_core___024root___eval_debug_assertions(&(vlSymsp->TOP));
#endif  // VL_DEBUG
    vlSymsp->__Vm_activity = true;
    vlSymsp->__Vm_deleter.deleteAll();
    if (VL_UNLIKELY(!vlSymsp->__Vm_didInit)) {
        vlSymsp->__Vm_didInit = true;
        VL_DEBUG_IF(VL_DBG_MSGF("+ Initial\n"););
        Vinlu_core___024root___eval_static(&(vlSymsp->TOP));
        Vinlu_core___024root___eval_initial(&(vlSymsp->TOP));
        Vinlu_core___024root___eval_settle(&(vlSymsp->TOP));
    }
    VL_DEBUG_IF(VL_DBG_MSGF("+ Eval\n"););
    Vinlu_core___024root___eval(&(vlSymsp->TOP));
    // Evaluate cleanup
    Verilated::endOfEval(vlSymsp->__Vm_evalMsgQp);
}

//============================================================
// Events and timing
bool Vinlu_core::eventsPending() { return false; }

uint64_t Vinlu_core::nextTimeSlot() {
    VL_FATAL_MT(__FILE__, __LINE__, "", "%Error: No delays in the design");
    return 0;
}

//============================================================
// Utilities

const char* Vinlu_core::name() const {
    return vlSymsp->name();
}

//============================================================
// Invoke final blocks

void Vinlu_core___024root___eval_final(Vinlu_core___024root* vlSelf);

VL_ATTR_COLD void Vinlu_core::final() {
    Vinlu_core___024root___eval_final(&(vlSymsp->TOP));
}

//============================================================
// Implementations of abstract methods from VerilatedModel

const char* Vinlu_core::hierName() const { return vlSymsp->name(); }
const char* Vinlu_core::modelName() const { return "Vinlu_core"; }
unsigned Vinlu_core::threads() const { return 1; }
void Vinlu_core::prepareClone() const { contextp()->prepareClone(); }
void Vinlu_core::atClone() const {
    contextp()->threadPoolpOnClone();
}
std::unique_ptr<VerilatedTraceConfig> Vinlu_core::traceConfig() const {
    return std::unique_ptr<VerilatedTraceConfig>{new VerilatedTraceConfig{false, false, false}};
};

//============================================================
// Trace configuration

void Vinlu_core___024root__trace_decl_types(VerilatedVcd* tracep);

void Vinlu_core___024root__trace_init_top(Vinlu_core___024root* vlSelf, VerilatedVcd* tracep);

VL_ATTR_COLD static void trace_init(void* voidSelf, VerilatedVcd* tracep, uint32_t code) {
    // Callback from tracep->open()
    Vinlu_core___024root* const __restrict vlSelf VL_ATTR_UNUSED = static_cast<Vinlu_core___024root*>(voidSelf);
    Vinlu_core__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    if (!vlSymsp->_vm_contextp__->calcUnusedSigs()) {
        VL_FATAL_MT(__FILE__, __LINE__, __FILE__,
            "Turning on wave traces requires Verilated::traceEverOn(true) call before time 0.");
    }
    vlSymsp->__Vm_baseCode = code;
    tracep->pushPrefix(std::string{vlSymsp->name()}, VerilatedTracePrefixType::SCOPE_MODULE);
    Vinlu_core___024root__trace_decl_types(tracep);
    Vinlu_core___024root__trace_init_top(vlSelf, tracep);
    tracep->popPrefix();
}

VL_ATTR_COLD void Vinlu_core___024root__trace_register(Vinlu_core___024root* vlSelf, VerilatedVcd* tracep);

VL_ATTR_COLD void Vinlu_core::trace(VerilatedVcdC* tfp, int levels, int options) {
    if (tfp->isOpen()) {
        vl_fatal(__FILE__, __LINE__, __FILE__,"'Vinlu_core::trace()' shall not be called after 'VerilatedVcdC::open()'.");
    }
    if (false && levels && options) {}  // Prevent unused
    tfp->spTrace()->addModel(this);
    tfp->spTrace()->addInitCb(&trace_init, &(vlSymsp->TOP));
    Vinlu_core___024root__trace_register(&(vlSymsp->TOP), tfp->spTrace());
}
