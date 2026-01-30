# Integer-Only PIM Architecture Diagrams

This document contains Mermaid diagrams for the paper figures.

## 1. Overall PIM Architecture

```mermaid
graph TB
    subgraph Host["Host CPU"]
        APP[LLM Application]
        DRV[PIM Driver]
    end
    
    subgraph HBM["HBM3/HBM4 Stack"]
        subgraph Logic["Logic Die (Base Die)"]
            CTRL[Memory Controller]
            SCHED[PIM Scheduler]
            ROUTER[Data Router]
        end
        
        subgraph Bank0["PIM Bank 0"]
            direction TB
            DRAM0[DRAM Array<br/>KV-Cache Storage]
            MAC0[INT8 MAC Array]
            INLU0[iNLU<br/>Integer Softmax]
            OAL0[Outlier-Aware<br/>Logic]
            BUF0[Overflow Buffer]
        end
        
        subgraph Bank1["PIM Bank 1..N"]
            DRAM1[DRAM Array]
            MAC1[INT8 MAC Array]
            INLU1[iNLU]
        end
    end
    
    APP --> DRV
    DRV --> CTRL
    CTRL --> SCHED
    SCHED --> ROUTER
    ROUTER --> Bank0
    ROUTER --> Bank1
    
    DRAM0 --> MAC0
    MAC0 --> INLU0
    INLU0 --> OAL0
    OAL0 --> BUF0
    OAL0 --> DRAM0
    
    style INLU0 fill:#1abc9c,color:white
    style OAL0 fill:#f39c12,color:white
    style DRAM0 fill:#3498db,color:white
    style MAC0 fill:#2ecc71,color:white
```

## 2. iNLU (Integer Non-Linear Unit) Pipeline

```mermaid
graph LR
    subgraph Input
        IN[INT32 Logits<br/>已减去最大值]
    end
    
    subgraph Stage1["Stage 1: Range Reduction"]
        DIV["n = x ÷ ln2<br/>f = x mod ln2"]
    end
    
    subgraph Stage2["Stage 2: Polynomial Setup"]
        ADD["f + b<br/>(b = 1.353 × 1024)"]
    end
    
    subgraph Stage3["Stage 3: Square"]
        MUL["(f + b)²<br/>乘法器"]
    end
    
    subgraph Stage4["Stage 4: Final Compute"]
        POLY["a × sq + c<br/>2^n 位移"]
    end
    
    subgraph Output
        OUT["INT32 e^x<br/>定点表示"]
    end
    
    IN --> Stage1 --> Stage2 --> Stage3 --> Stage4 --> OUT
    
    style Stage1 fill:#e74c3c,color:white
    style Stage2 fill:#e67e22,color:white
    style Stage3 fill:#f1c40f,color:black
    style Stage4 fill:#2ecc71,color:white
```

## 3. Outlier-Aware Logic Data Path

```mermaid
graph TB
    subgraph Input
        DATA[INT32 Input]
        THR[Threshold σ]
    end
    
    subgraph Detection["Outlier Detection"]
        ABS["|x| 计算"]
        CMP["比较: |x| > σ"]
    end
    
    subgraph Normal["Normal Path (99%)"]
        QUANT["INT8 量化<br/>截断低 8 位"]
        MAC["INT8 MAC"]
    end
    
    subgraph Outlier["Outlier Path (1%)"]
        BUF[Overflow Buffer<br/>16 entries]
        HP["高精度处理<br/>FP16 或 INT32"]
    end
    
    subgraph Output
        MERGE["结果合并"]
        OUT[Final Output]
    end
    
    DATA --> ABS
    THR --> CMP
    ABS --> CMP
    
    CMP -->|"≤ σ"| QUANT --> MAC --> MERGE
    CMP -->|"> σ"| BUF --> HP --> MERGE
    MERGE --> OUT
    
    style Normal fill:#2ecc71,color:white
    style Outlier fill:#e74c3c,color:white
    style Detection fill:#3498db,color:white
```

## 4. KV-Cache Compression Flow

```mermaid
sequenceDiagram
    participant Host as Host CPU
    participant Ctrl as Memory Controller
    participant Bank as PIM Bank
    participant DRAM as DRAM Array
    
    Note over Host,DRAM: Decode Phase (生成新 Token)
    
    Host->>Ctrl: Send Query Q
    Ctrl->>Bank: Dispatch to Bank
    
    rect rgb(52, 152, 219)
        Note over Bank,DRAM: KV-Cache 读取
        Bank->>DRAM: Read All K (历史)
        DRAM-->>Bank: K vectors
        Bank->>DRAM: Read All V (历史)
        DRAM-->>Bank: V vectors
    end
    
    rect rgb(46, 204, 113)
        Note over Bank: Attention 计算
        Bank->>Bank: Score = Q × K (INT8 MAC)
        Bank->>Bank: iNLU: Softmax(Score)
        Bank->>Bank: Output = Attn × V
    end
    
    rect rgb(155, 89, 182)
        Note over Bank,DRAM: Near-Memory 压缩
        Bank->>Bank: 量化新 K, V 为 INT4
        Bank->>DRAM: Write Compressed K
        Bank->>DRAM: Write Compressed V
    end
    
    Bank-->>Ctrl: Return Output
    Ctrl-->>Host: Attention Result
```

## 5. Comparison: Baseline vs Ours

```mermaid
graph LR
    subgraph Baseline["Baseline PIM (Samsung HBM-PIM)"]
        direction TB
        B1["1. Read INT4 Weights"]
        B2["2. Dequant → FP16"]
        B3["3. FP16 MAC"]
        B4["4. FP16 Softmax"]
        B5["5. Requant → INT4"]
        B6["6. Write Back"]
        B1 --> B2 --> B3 --> B4 --> B5 --> B6
    end
    
    subgraph Ours["Ours: Integer-Only PIM"]
        direction TB
        O1["1. Read INT8 Data"]
        O2["2. INT8 MAC"]
        O3["3. iNLU<br/>(Integer Softmax)"]
        O4["4. Write INT4<br/>(Near-Memory Compress)"]
        O1 --> O2 --> O3 --> O4
    end
    
    style B2 fill:#e74c3c,color:white
    style B4 fill:#e74c3c,color:white
    style B5 fill:#e74c3c,color:white
    style O3 fill:#1abc9c,color:white
    style O4 fill:#9b59b6,color:white
```

---

## Usage in Paper

These diagrams can be:

1. Rendered using Mermaid Live Editor: <https://mermaid.live/>
2. Exported as SVG/PNG for paper inclusion
3. Used directly in Markdown-based paper tools (Overleaf Mermaid plugin, etc.)
