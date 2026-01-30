#include <vector>
#include <random>
#include "dram_controller/controller.h"
#include "memory_system/memory_system.h"
#include "dram/dram.h"
#include "base/base.h"

namespace Ramulator {

/**
 * KVCompressionPlugin - In-situ KV-Cache Compression for PIM
 * 
 * This plugin implements the core Stage 3 functionality:
 * 1. Identifies KV-Cache write requests (Key/Value cache)
 * 2. Triggers WR_COMP commands for in-situ INT4 quantization (physically modeled)
 * 3. Handles outlier values (1%) through high-precision path
 * 4. Models RD_COMP for reading compressed KV-Cache data
 * 5. Tracks real bandwidth savings via reduced burst lengths
 */
class KVCompressionPlugin : public IControllerPlugin, public Implementation {
  RAMULATOR_REGISTER_IMPLEMENTATION(IControllerPlugin, KVCompressionPlugin, "KVCompression", "Plugin for in-situ KV-cache compression with INT4 quantization.")

  private:
    IDRAMController* m_ctrl = nullptr;
    IDRAM* m_dram = nullptr;

    // Configuration parameters
    int m_compression_ratio = 4;       // INT4: 4:1 compression from FP16
    float m_outlier_ratio = 0.01f;     // 1% of values are outliers
    int m_bytes_per_access = 64;       // Bytes per memory access (cache line)

    // Statistics
    size_t s_num_kv_requests = 0;      // Total KV-Cache requests
    size_t s_num_kv_compressed = 0;    // Successfully compressed KV requests
    size_t s_num_outliers = 0;         // Outlier values (require FP16 path)
    size_t s_num_regular_writes = 0;   // Regular (non-KV) write requests
    size_t s_bytes_saved = 0;          // Total bytes saved by compression
    size_t s_quantize_cycles = 0;      // Total PIM quantization cycles

    // Random generator for outlier simulation
    std::mt19937 m_rng;
    std::uniform_real_distribution<float> m_dist{0.0f, 1.0f};

  public:
    void init() override {
      // Initialize RNG with fixed seed for reproducibility
      m_rng.seed(42);
      
      // Read configuration parameters
      m_compression_ratio = param<int>("compression_ratio").default_val(4);
      m_outlier_ratio = param<float>("outlier_ratio").default_val(0.01f);
      m_bytes_per_access = param<int>("bytes_per_access").default_val(64);
    };

    void setup(IFrontEnd* frontend, IMemorySystem* memory_system) override {
      m_ctrl = cast_parent<IDRAMController>();
      m_dram = memory_system->get_ifce<IDRAM>();

      // Register statistics
      register_stat(s_num_kv_requests).name("num_kv_requests_{}", m_ctrl->m_channel_id)
        .desc("Total number of KV-Cache requests");
      register_stat(s_num_kv_compressed).name("num_kv_compressed_{}", m_ctrl->m_channel_id)
        .desc("Number of KV-Cache requests compressed via PIM");
      register_stat(s_num_outliers).name("num_outliers_{}", m_ctrl->m_channel_id)
        .desc("Number of outlier values requiring high-precision path");
      register_stat(s_num_regular_writes).name("num_regular_writes_{}", m_ctrl->m_channel_id)
        .desc("Number of regular (non-KV) write requests");
      register_stat(s_bytes_saved).name("bytes_saved_{}", m_ctrl->m_channel_id)
        .desc("Total bytes saved by INT4 compression");
      register_stat(s_quantize_cycles).name("quantize_cycles_{}", m_ctrl->m_channel_id)
        .desc("Total cycles spent on PIM quantization");
    };

    void finalize() override {
      float compression_efficiency = 0.0f;
      if (s_num_kv_requests > 0) {
        compression_efficiency = (float)s_num_kv_compressed / s_num_kv_requests * 100.0f;
      }
      
      size_t total_kv_bytes = s_num_kv_requests * m_bytes_per_access;
      float bandwidth_reduction = 0.0f;
      if (total_kv_bytes > 0) {
        bandwidth_reduction = (float)s_bytes_saved / total_kv_bytes * 100.0f;
      }

      std::cout << "[KVCompression] Channel " << m_ctrl->m_channel_id << " Summary:" << std::endl;
      std::cout << "  Total KV requests:    " << s_num_kv_requests << std::endl;
      std::cout << "  Compressed:           " << s_num_kv_compressed 
                << " (" << compression_efficiency << "%)" << std::endl;
      std::cout << "  Outliers:             " << s_num_outliers 
                << " (" << (s_num_kv_requests > 0 ? (float)s_num_outliers/s_num_kv_requests*100.0f : 0) << "%)" << std::endl;
      std::cout << "  Bytes saved:          " << s_bytes_saved << std::endl;
      std::cout << "  Bandwidth reduction:  " << bandwidth_reduction << "%" << std::endl;
      std::cout << "  Regular writes:       " << s_num_regular_writes << std::endl;
    };

    void update(bool request_found, ReqBuffer::iterator& req_it) override {
      if (!request_found) return;

      // Check if this is a KV-Cache WRITE request
      if (req_it->type_id == m_dram->m_requests("kvcache_write")) {
        s_num_kv_requests++;
        
        // Simulate outlier detection (1% of activations are outliers)
        bool is_outlier = (m_dist(m_rng) < m_outlier_ratio);
        
        if (is_outlier) {
          // Outlier path: keep as regular high-precision write (FP16)
          s_num_outliers++;
          req_it->type_id = m_dram->m_requests("write");
          req_it->final_command = m_dram->m_request_translations("write");
        } else {
          // Normal path: trigger WR_COMP (through write_comp request)
          req_it->type_id = m_dram->m_requests("write_comp");
          req_it->final_command = m_dram->m_request_translations("write_comp");
          s_num_kv_compressed++;
          
          s_bytes_saved += m_bytes_per_access * (m_compression_ratio - 1) / m_compression_ratio;
        }
      } 
      // Check if this is a KV-Cache READ request
      else if (req_it->type_id == m_dram->m_requests("kvcache_read")) {
        bool was_outlier = (m_dist(m_rng) < m_outlier_ratio);
        
        if (was_outlier) {
           req_it->type_id = m_dram->m_requests("read");
           req_it->final_command = m_dram->m_request_translations("read");
        } else {
           // Normal path: trigger RD_COMP (through read_comp request)
           req_it->type_id = m_dram->m_requests("read_comp");
           req_it->final_command = m_dram->m_request_translations("read_comp");
        }
      }
      else if (req_it->type_id == m_dram->m_requests("write")) {
        s_num_regular_writes++;
      }
    };
};

} // namespace Ramulator
