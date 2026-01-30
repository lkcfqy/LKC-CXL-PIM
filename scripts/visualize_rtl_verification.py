
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

def visualize_rtl_results():
    # 1. 加载 RTL 仿真结果
    rtl_data_path = 'paper_assets/data/inlu_rtl_simulation_results.csv'
    if not os.path.exists(rtl_data_path):
        print(f"找不到仿真数据: {rtl_data_path}")
        return
        
    df_rtl = pd.read_csv(rtl_data_path)
    
    # 2. 准备金本位数据 (理论 e^x * 1024)
    # 取仿真中出现的三个关键输入点流出的最后一行数据
    # x = 0, x = -710, x = -1024
    test_points = [
        {"input": 0, "theory": 1024, "label": "x=0"},
        {"input": -710, "theory": 512, "label": "x=-ln2"},
        {"input": -1024, "theory": 376.7, "label": "x=-1.0"}
    ]
    
    # 提取 RTL 实际值 (对应时间点的输出)
    # 30ns输入的0在65-69ns输出, 40ns输入的-710在75-79ns输出, 50ns输入的-1024在85-89ns输出
    rtl_values = [
        df_rtl[df_rtl['Time'] == 65]['Output_Exp'].values[0],
        df_rtl[df_rtl['Time'] == 75]['Output_Exp'].values[0],
        df_rtl[df_rtl['Time'] == 85]['Output_Exp'].values[0]
    ]
    
    theory_values = [p['theory'] for p in test_points]
    labels = [p['label'] for p in test_points]
    
    # 3. 绘图: 理论 vs 实际
    plt.figure(figsize=(10, 6))
    x = np.arange(len(labels))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(10, 6))
    rects1 = ax.bar(x - width/2, theory_values, width, label='Golden Model (Python)', color='#3498db', alpha=0.8)
    rects2 = ax.bar(x + width/2, rtl_values, width, label='RTL Simulation (Verilator)', color='#e67e22', alpha=0.8)
    
    ax.set_ylabel('Fixed-point Value (Scaling=1024)')
    ax.set_title('iNLU Hardware Verification: Golden Model vs. RTL Implementation')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    
    # 添加数值标签
    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.1f}',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom')

    autolabel(rects1)
    autolabel(rects2)
    
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.savefig('paper_assets/notes/iNLU_rtl_accuracy_comparison.png')
    
    # 4. 绘制误差率 (Error %)
    plt.figure(figsize=(10, 4))
    errors = [abs(t - r) / t * 100 for t, r in zip(theory_values, rtl_values)]
    plt.bar(labels, errors, color='#c0392b', alpha=0.7)
    plt.ylabel('Relative Error (%)')
    plt.title('iNLU Hardware Implementation Error Rate')
    plt.ylim(0, 0.5) # 误差很小，限制坐标轴
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.savefig('paper_assets/notes/iNLU_rtl_error_rate.png')

    print("\n✅ 论文图示已生成：")
    print("  - paper_assets/notes/iNLU_rtl_accuracy_comparison.png (RTL 精度对比图)")
    print("  - paper_assets/notes/iNLU_rtl_error_rate.png (RTL 误差率分析图)")

if __name__ == "__main__":
    visualize_rtl_results()
