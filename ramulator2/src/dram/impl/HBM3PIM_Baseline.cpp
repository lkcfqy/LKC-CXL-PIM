#include "dram/dram.h"
#include "dram/lambdas.h"

namespace Ramulator {

/**
 * HBM3PIM_Baseline - Baseline HBM3 without in-situ compression
 * 
 * This baseline model represents Samsung HBM-PIM style processing:
 * - FP16 data path (no INT4 quantization)
 * - Dequantization required before computation
 * - No near-memory compression
 * 
 * Used for comparison with the optimized Integer-Only PIM architecture.
 */
class HBM3PIM_Baseline : public IDRAM, public Implementation {
  RAMULATOR_REGISTER_IMPLEMENTATION(IDRAM, HBM3PIM_Baseline, "HBM3PIM_Baseline", "HBM3 Baseline without PIM compression (FP16 path)")

  public:
    inline static const std::map<std::string, Organization> org_presets = {
      //   name     density   DQ    Ch  Pc  Bg  Ba   Ro     Co
      {"HBM3_2Gb",   {2<<10,  128,  {1, 2,  4,  4, 1<<13, 1<<6}}},
      {"HBM3_4Gb",   {4<<10,  128,  {1, 2,  4,  4, 1<<14, 1<<6}}},
      {"HBM3_8Gb",   {8<<10,  128,  {1, 2,  4,  4, 1<<15, 1<<6}}},
    };

    inline static const std::map<std::string, std::vector<int>> timing_presets = {
      //   name       rate   nBL  nCL  nRCDRD  nRCDWR  nRP  nRAS  nRC  nWR  nRTPS  nRTPL  nCWL  nCCDS  nCCDL  nRRDS  nRRDL  nWTRS  nWTRL  nRTW  nFAW  nRFC  nRFCSB  nREFI  nREFISB  nRREFD  nDEQUANT
      {"HBM3_2Gbps",  {2000,   4,   7,    7,      7,     7,   17,  19,   8,    2,     3,    2,    1,      2,     2,     3,     3,     4,    3,    15,   -1,   160,   3900,     -1,      8,   8}},
    };

    inline static constexpr ImplDef m_levels = {
      "channel", "pseudochannel", "bankgroup", "bank", "row", "column",    
    };

    // No PIM commands - standard DRAM operations only
    inline static constexpr ImplDef m_commands = {
      "ACT", "PRE", "PREA", "RD", "WR", "RDA", "WRA", "REFab", "REFsb", "RFMab", "RFMsb"
    };

    inline static const ImplLUT m_command_scopes = LUT (
      m_commands, m_levels, {
        {"ACT", "row"}, {"PRE", "bank"}, {"PREA", "channel"}, {"RD", "column"}, {"WR", "column"}, 
        {"RDA", "column"}, {"WRA", "column"}, {"REFab", "channel"}, {"REFsb", "bank"}, 
        {"RFMab", "channel"}, {"REFsb", "bank"}
      }
    );

    inline static const ImplLUT m_command_meta = LUT<DRAMCommandMeta> (
      m_commands, {
        {"ACT", {true, false, false, false}}, {"PRE", {false, true, false, false}}, {"PREA", {false, true, false, false}},
        {"RD", {false, false, true, false}}, {"WR", {false, false, true, false}}, {"RDA", {false, true, true, false}},
        {"WRA", {false, true, true, false}}, {"REFab", {false, false, false, true}}, {"REFsb", {false, false, false, true}},
        {"RFMab", {false, false, false, true}}, {"RFMsb", {false, false, false, true}}
      }
    );

    // No PIM requests - only standard memory operations
    inline static constexpr ImplDef m_requests = {
      "read", "write", "kvcache_write", "kvcache_read", "all-bank-refresh", "per-bank-refresh", "all-bank-rfm", "per-bank-rfm"
    };

    inline static const ImplLUT m_request_translations = LUT (
      m_requests, m_commands, {
        {"read", "RD"}, {"write", "WR"}, {"kvcache_write", "WR"}, {"kvcache_read", "RD"},
        {"all-bank-refresh", "REFab"}, {"per-bank-refresh", "REFsb"}, 
        {"all-bank-rfm", "RFMab"}, {"per-bank-rfm", "RFMsb"}
      }
    );

    inline static constexpr ImplDef m_timings = {
      "rate", "nBL", "nCL", "nRCDRD", "nRCDWR", "nRP", "nRAS", "nRC", "nWR", "nRTPS", "nRTPL", "nCWL",
      "nCCDS", "nCCDL", "nRRDS", "nRRDL", "nWTRS", "nWTRL", "nRTW", "nFAW", "nRFC", "nRFCSB", "nREFI", "nREFISB", "nRREFD", "nDEQUANT"
    };

    inline static constexpr ImplDef m_states = { "Opened", "Closed", "N/A", "Refreshing" };

    inline static const ImplLUT m_init_states = LUT (
      m_levels, m_states, { {"channel", "N/A"}, {"pseudochannel", "N/A"}, {"bankgroup", "N/A"}, {"bank", "Closed"}, {"row", "Closed"}, {"column", "N/A"} }
    );

    struct Node : public DRAMNodeBase<HBM3PIM_Baseline> {
      Node(HBM3PIM_Baseline* dram, Node* parent, int level, int id) : DRAMNodeBase<HBM3PIM_Baseline>(dram, parent, level, id) {};
    };
    std::vector<Node*> m_channels;
    FuncMatrix<ActionFunc_t<Node>> m_actions;
    FuncMatrix<PreqFunc_t<Node>> m_preqs;
    FuncMatrix<RowhitFunc_t<Node>> m_rowhits;
    FuncMatrix<RowopenFunc_t<Node>> m_rowopens;

  public:
    void tick() override { 
      m_clk++; 
    };

    void init() override {
      RAMULATOR_DECLARE_SPECS();
      set_organization();
      set_timing_vals();
      set_actions();
      set_preqs();
      set_rowhits();
      set_rowopens();
      create_nodes();
    };

    void setup(IFrontEnd* frontend, IMemorySystem* memory_system) override {
    };

    void issue_command(int command, const AddrVec_t& addr_vec) override {
      int channel_id = addr_vec[m_levels["channel"]];
      m_channels[channel_id]->update_states(command, addr_vec, m_clk);
      m_channels[channel_id]->update_timing(command, addr_vec, m_clk);
    };

    int get_preq_command(int command, const AddrVec_t& addr_vec) override {
      int channel_id = addr_vec[m_levels["channel"]];
      return m_channels[channel_id]->get_preq_command(command, addr_vec, m_clk);
    };

    bool check_ready(int command, const AddrVec_t& addr_vec) override {
      if (command < 0 || command >= m_commands.size()) return false;
      int channel_id = addr_vec[m_levels["channel"]];
      return m_channels[channel_id]->check_ready(command, addr_vec, m_clk);
    };

    bool check_rowbuffer_hit(int command, const AddrVec_t& addr_vec) override {
      int channel_id = addr_vec[m_levels["channel"]];
      return m_channels[channel_id]->check_rowbuffer_hit(command, addr_vec, m_clk);
    };
    
    bool check_node_open(int command, const AddrVec_t& addr_vec) override {
      int channel_id = addr_vec[m_levels["channel"]];
      return m_channels[channel_id]->check_node_open(command, addr_vec, m_clk);
    };

  private:
    void set_organization() {
      m_channel_width = param_group("org").param<int>("channel_width").default_val(128);
      m_internal_prefetch_size = 2;
      m_organization.count.resize(m_levels.size(), -1);
      if (auto preset_name = param_group("org").param<std::string>("preset").optional()) {
        m_organization = org_presets.at(*preset_name);
      }
      for (int i = 0; i < m_levels.size(); i++){
        if (auto sz = param_group("org").param<int>(m_levels(i)).optional()) m_organization.count[i] = *sz;
      }
      if (auto density = param_group("org").param<int>("density").optional()) m_organization.density = *density;
      if (auto dq = param_group("org").param<int>("dq").optional()) m_organization.dq = *dq;

      for (int i = 0; i < m_levels.size(); i++) {
        if (m_organization.count[i] <= 0) {
          throw ConfigurationError("Level {} count is invalid: {}", m_levels(i), m_organization.count[i]);
        }
      }
    };

    void set_timing_vals() {
      m_timing_vals.resize(m_timings.size(), -1);
      if (auto preset_name = param_group("timing").param<std::string>("preset").optional()) {
        m_timing_vals = timing_presets.at(*preset_name);
      }
      int tCK_ps = param_group("timing").param<int>("tCK_ps").default_val(1000);
      m_timing_vals("rate") = 1E6 / (tCK_ps / 2.0f);

      // tRFC tables
      m_timing_vals("nRFC") = JEDEC_rounding(350, tCK_ps);
      m_timing_vals("nREFISB") = JEDEC_rounding(2438, tCK_ps);
      m_timing_vals("nREFI") = JEDEC_rounding(3900, tCK_ps);

      for (int i = 0; i < m_timings.size(); i++) {
        auto timing_name = std::string(m_timings(i));
        if (auto provided_timing = param_group("timing").param<int>(timing_name).optional()) m_timing_vals(i) = *provided_timing;
      }
      m_read_latency = m_timing_vals("nCL") + m_timing_vals("nBL");

      #define V(timing) (m_timing_vals(timing))
      populate_timingcons(this, {
          {.level = "channel", .preceding = {"ACT"}, .following = {"ACT", "PRE", "PREA", "REFab", "REFsb"}, .latency = 2},
          {.level = "pseudochannel", .preceding = {"ACT"}, .following = {"ACT"}, .latency = V("nRRDS")},
          {.level = "bank", .preceding = {"ACT"}, .following = {"ACT"}, .latency = V("nRC")},  
          {.level = "bank", .preceding = {"ACT"}, .following = {"RD", "WR"}, .latency = V("nRCDRD")},  
          {.level = "bank", .preceding = {"ACT"}, .following = {"PRE"}, .latency = V("nRAS")},  
          {.level = "bank", .preceding = {"PRE"}, .following = {"ACT"}, .latency = V("nRP")},  
          {.level = "bank", .preceding = {"RD"},  .following = {"PRE"}, .latency = V("nRTPS")},  
          {.level = "bank", .preceding = {"WR"},  .following = {"PRE"}, .latency = V("nCWL") + V("nBL") + V("nWR")},
          // In baseline, dequantization happens on CPU side, adding latency to read path
          // This is modeled as additional read latency rather than a separate command
        }
      );
      #undef V
    };

    void set_actions() {
      m_actions.resize(m_levels.size(), std::vector<ActionFunc_t<Node>>(m_commands.size()));
      m_actions[m_levels["channel"]][m_commands["PREA"]] = Lambdas::Action::Channel::PREab<HBM3PIM_Baseline>;
      m_actions[m_levels["bank"]][m_commands["ACT"]] = Lambdas::Action::Bank::ACT<HBM3PIM_Baseline>;
      m_actions[m_levels["bank"]][m_commands["PRE"]] = Lambdas::Action::Bank::PRE<HBM3PIM_Baseline>;
    };

    void set_preqs() {
      m_preqs.resize(m_levels.size(), std::vector<PreqFunc_t<Node>>(m_commands.size()));
      m_preqs[m_levels["channel"]][m_commands["REFab"]] = Lambdas::Preq::Channel::RequireAllBanksClosed<HBM3PIM_Baseline>;
      m_preqs[m_levels["bank"]][m_commands["REFsb"]] = Lambdas::Preq::Bank::RequireBankClosed<HBM3PIM_Baseline>;
      m_preqs[m_levels["bank"]][m_commands["RD"]] = Lambdas::Preq::Bank::RequireRowOpen<HBM3PIM_Baseline>;
      m_preqs[m_levels["bank"]][m_commands["WR"]] = Lambdas::Preq::Bank::RequireRowOpen<HBM3PIM_Baseline>;
    };

    void set_rowhits() {
      m_rowhits.resize(m_levels.size(), std::vector<RowhitFunc_t<Node>>(m_commands.size()));
      m_rowhits[m_levels["bank"]][m_commands["RD"]] = Lambdas::RowHit::Bank::RDWR<HBM3PIM_Baseline>;
      m_rowhits[m_levels["bank"]][m_commands["WR"]] = Lambdas::RowHit::Bank::RDWR<HBM3PIM_Baseline>;
    };

    void set_rowopens() {
      m_rowopens.resize(m_levels.size(), std::vector<RowhitFunc_t<Node>>(m_commands.size()));
      m_rowopens[m_levels["bank"]][m_commands["RD"]] = Lambdas::RowOpen::Bank::RDWR<HBM3PIM_Baseline>;
      m_rowopens[m_levels["bank"]][m_commands["WR"]] = Lambdas::RowOpen::Bank::RDWR<HBM3PIM_Baseline>;
    };

    void create_nodes() {
      for (int i = 0; i < m_organization.count[m_levels["channel"]]; i++) m_channels.push_back(new Node(this, nullptr, 0, i));
    };
};

} // namespace Ramulator
