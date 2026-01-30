#include <filesystem>
#include <iostream>
#include <fstream>

#include "frontend/frontend.h"
#include "base/exception.h"

namespace Ramulator {

namespace fs = std::filesystem;

class ReadWriteTrace : public IFrontEnd, public Implementation {
  RAMULATOR_REGISTER_IMPLEMENTATION(IFrontEnd, ReadWriteTrace, "ReadWriteTrace", "Read/Write DRAM address vector trace with KV-Cache support.")

  private:
    struct Trace {
      bool is_write;
      bool is_kv_cache;  // true for Key/Value cache writes (K/V in trace)
      Addr_t addr;
      AddrVec_t addr_vec;
    };
    std::vector<Trace> m_trace;

    size_t m_trace_length = 0;
    size_t m_curr_trace_idx = 0;

    Logger_t m_logger;

  public:
    void init() override {
      std::string trace_path_str = param<std::string>("path").desc("Path to the load store trace file.").required();
      m_clock_ratio = param<uint>("clock_ratio").required();

      m_logger = Logging::create_logger("ReadWriteTrace");
      m_logger->info("Loading trace file {} ...", trace_path_str);
      init_trace(trace_path_str);
      m_logger->info("Loaded {} lines.", m_trace.size());      
    };


    void tick() override {
      if (m_curr_trace_idx < m_trace_length) {
        const Trace& t = m_trace[m_curr_trace_idx];
        
        // Determine request type based on trace flags
        int req_type;
        if (t.is_kv_cache) {
          req_type = t.is_write ? Request::Type::KVCacheWrite : Request::Type::KVCacheRead;
        } else if (t.is_write) {
          req_type = Request::Type::Write;
        } else {
          req_type = Request::Type::Read;
        }
        
        Request req(t.addr, req_type);
        req.addr_vec = t.addr_vec;
        m_memory_system->send(req);
        m_curr_trace_idx++;
      }
    };


    bool is_finished() override {
      return m_curr_trace_idx >= m_trace_length; 
    };    

  private:
    void init_trace(const std::string& file_path_str) {
      fs::path trace_path(file_path_str);
      if (!fs::exists(trace_path)) {
        throw ConfigurationError("Trace {} does not exist!", file_path_str);
      }

      std::ifstream trace_file(trace_path);
      if (!trace_file.is_open()) {
        throw ConfigurationError("Trace {} cannot be opened!", file_path_str);
      }

      std::string line;
      while (std::getline(trace_file, line)) {
        std::vector<std::string> tokens;
        tokenize(tokens, line, " ");

        if (tokens.size() < 2) continue;

        bool is_write = false;
        bool is_kv_cache = false;
        
        if (tokens[0] == "R") {
          is_write = false;
          is_kv_cache = false;
        } else if (tokens[0] == "W") {
          is_write = true;
          is_kv_cache = false;
        } else if (tokens[0] == "K" || tokens[0] == "V") {
          // K = Key cache write, V = Value cache write
          is_write = true;
          is_kv_cache = true;
        } else if (tokens[0] == "RK" || tokens[0] == "RV") {
          // RK = Key cache read, RV = Value cache read
          is_write = false;
          is_kv_cache = true;
        } else {
          continue; 
        }

        if (tokens.size() == 2) {
          std::vector<std::string> addr_vec_tokens;
          tokenize(addr_vec_tokens, tokens[1], ",");
          AddrVec_t addr_vec;
          for (const auto& token : addr_vec_tokens) addr_vec.push_back(std::stoll(token));
          m_trace.push_back({is_write, is_kv_cache, 0, addr_vec});
        } else if (tokens.size() >= 3) {
          Addr_t addr = std::stoll(tokens[1]);
          std::vector<std::string> addr_vec_tokens;
          tokenize(addr_vec_tokens, tokens[2], ",");
          AddrVec_t addr_vec;
          for (const auto& token : addr_vec_tokens) addr_vec.push_back(std::stoll(token));
          m_trace.push_back({is_write, is_kv_cache, addr, addr_vec});
        }
      }
      trace_file.close();
      m_trace_length = m_trace.size();
    };
};

}        // namespace Ramulator