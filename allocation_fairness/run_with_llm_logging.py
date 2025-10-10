

from simulation_runner import SimulationRunner

# 配置实验
config = {
    "rounds": 3,  # 运行3轮
    "agents_file": "agents.json",
    "initial_resource": 250,
    "save_results": True,
    "results_dir": "results",
    "distribution_methods": ["contribution_based"]  # 可以改为其他方法
}

print("="*70)
print("社区农场公平实验 - 带LLM交互日志记录")
print("="*70)
print("\n实验配置:")
print(f"  轮数: {config['rounds']}")
print(f"  分配方法: {', '.join(config['distribution_methods'])}")
print(f"  初始资源: {config['initial_resource']}")
print()

# 创建并运行模拟
simulator = SimulationRunner(config)
results = simulator.run_simulation()

print("\n" + "="*70)
print("✅ 实验完成！")
print("="*70)
print("\n📁 生成的文件:")
print("  - 实验结果JSON: results/simulation_results_*.json")
print("  - LLM交互日志CSV: llm_logs/llm_interactions_*.csv")
print("\n💡 提示: ")
print("  你可以用Excel打开CSV文件查看每次LLM调用的详细信息")
print("  CSV文件包含：回合数、Agent信息、输入Prompt、输出内容、提取的Score等")

