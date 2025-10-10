"""
测试LLM驱动的按需分配机制
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulation_runner import SimulationRunner

def main():
    print("="*70)
    print("🧪 测试LLM驱动的按需分配机制")
    print("="*70)
    
    # 配置参数
    config = {
        "rounds": 5,  # 先测试5轮
        "agents_file": "agents.json",
        "initial_resource": 250,
        "save_results": True,
        "results_dir": "results",
        "distribution_methods": ["llm_needs_based"]  # LLM驱动的按需分配
    }
    
    print(f"\n📋 实验配置:")
    print(f"  轮次: {config['rounds']}")
    print(f"  初始资源: {config['initial_resource']}")
    print(f"  分配方法: LLM驱动的按需分配")
    print(f"\n✨ 特点:")
    print(f"  - 各家庭通过LLM自主申报需求（需求量+理由+最低值）")
    print(f"  - 如果总需求≤总资源：满足所有申报")
    print(f"  - 如果总需求>总资源：按比例削减")
    print(f"  - 不同价值观家庭有不同的申报策略")
    
    print(f"\n{'='*70}")
    input("按回车键开始实验...")
    print()
    
    # 运行模拟
    runner = SimulationRunner(config)
    runner.run_simulation()
    
    print("\n" + "="*70)
    print("✅ 测试完成！")
    print("="*70)
    print("\n📊 查看结果:")
    print("  1. 控制台输出：各家庭的需求申报和理由")
    print("  2. results/文件夹：JSON结果文件和可视化图表")
    print("\n🔍 重点关注:")
    print("  - 各家庭的申报策略是否符合价值观")
    print("  - 需求理由是否合理")
    print("  - 分配结果是否公平")
    print("  - 满意度评分")
    print()

if __name__ == "__main__":
    main()

