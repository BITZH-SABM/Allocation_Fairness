"""
模拟运行器 - 整合所有组件并执行社区农场公平实验的多轮模拟
"""
import os
import json
import time
import random
from typing import Dict, List, Any, Tuple

# 导入各个组件
from generate_agents import generate_agents, save_agents, load_agents
from distribution_mechanisms import (
    equal_distribution,
    needs_based_distribution,
    contribution_based_distribution,
    negotiation_based_distribution
)
from resource_generation import (
    ResourceGenerator,
    calculate_production,
    initialize_resources
)
from evaluation_system import (
    evaluate_distribution,
    print_distribution_summary
)
import survival_needs
from llm_interaction_logger import initialize_logger, close_logger

class SimulationRunner:
    """模拟运行器类，整合各个组件并运行多轮模拟"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """初始化模拟运行器
        
        参数:
            config: 配置字典，包含模拟参数
        """
        # 默认配置
        self.default_config = {
            "rounds": 5,                   # 模拟轮数
            "agents_file": "agents.json",  # 代理文件
            "initial_resource": 100,       # 系统初始资源总量
            "save_results": True,          # 是否保存结果
            "results_dir": "results",      # 结果保存目录
            "distribution_methods": [      # 分配方法列表
                "equal", "needs_based", "contribution_based", "negotiation"
            ]
        }
        
        # 应用用户配置
        self.config = self.default_config.copy()
        if config:
            self.config.update(config)
        # 规范化 agents_file 路径：若为相对路径，则相对于当前脚本所在目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        agents_path = self.config.get("agents_file", "agents.json")
        if not os.path.isabs(agents_path):
            agents_path = os.path.join(script_dir, agents_path)
        self.config["agents_file"] = agents_path
        
        # 创建结果目录
        if self.config["save_results"] and not os.path.exists(self.config["results_dir"]):
            os.makedirs(self.config["results_dir"])
        
        # 🆕 为本次运行创建统一的experiment_id（用于协商日志和LLM日志）
        self.experiment_id = time.strftime("%Y%m%d_%H%M%S")
        
        # 初始化状态
        self.current_round = 0
        self.agents = []
        self.resource_generator = None
        self.family_resources = {}  # 每个家庭当前拥有的资源
        self.family_needs = {}      # 每个家庭的生存需求
        self.family_productions = {}  # 每个家庭的资源产出
        self.distribution_results = []  # 每轮的分配结果
        self.evaluation_results = []    # 每轮的评估结果
    
    def setup(self):
        """设置模拟环境，加载或生成代理，初始化资源等"""
        print("="*50)
        print("设置社区农场公平实验模拟环境")
        print("="*50)
        
        # 加载或生成代理
        print(f"加载代理文件: {os.path.abspath(self.config['agents_file'])}")
        if os.path.exists(self.config["agents_file"]):
            print(f"正在从{self.config['agents_file']}加载代理...")
            self.agents = load_agents(self.config["agents_file"])
        else:
            print("正在生成代理...")
            self.agents = generate_agents()
            save_agents(self.agents, self.config["agents_file"])
        
        print(f"共加载了{len(self.agents)}个代理家庭")
        
        # 初始化资源生成器
        print("\n初始化资源...")
        self.resource_generator = ResourceGenerator(
            total_families=len(self.agents),
            initial_resource=self.config["initial_resource"]
        )
        
        # 计算每个家庭的生存需求
        print("\n计算家庭生存需求...")
        self.family_needs = {}
        for agent in self.agents:
            agent_id = agent["id"]
            # 计算该家庭的生存需求
            needs = survival_needs.calculate_survival_needs(
                agent["members"],
                agent["labor_force"]
            )
            self.family_needs[agent_id] = needs
            
            print(f"{agent['family_name']}家庭(ID:{agent_id})的生存需求: ", end="")
            for resource, amount in needs.items():
                print(f"{resource}:{amount:.2f} ", end="")
            print()
        
        # 初始化家庭资源（初始轮没有资源）
        self.family_resources = {agent["id"]: {} for agent in self.agents}
        
        print("\n模拟环境设置完成！")
        return True
    
    def run_simulation(self):
        """运行整个模拟过程"""
        print("\n"+"="*50)
        print("开始社区农场公平实验模拟")
        print(f"实验ID: {self.experiment_id}")
        print("="*50)
        
        # 初始化LLM交互日志记录器（使用统一的experiment_id）
        initialize_logger(log_dir="llm_logs", experiment_id=self.experiment_id)
        
        try:
            # 确保环境已设置
            if not self.agents or not self.resource_generator:
                self.setup()
            
            # 运行指定轮数
            for round_num in range(1, self.config["rounds"] + 1):
                self.current_round = round_num
                print(f"\n开始第{round_num}轮模拟...")
                
                # 对每种分配方法进行模拟
                for method in self.config["distribution_methods"]:
                    print(f"\n使用{method}分配方法...")
                    
                    # 运行单轮模拟
                    distribution_result, evaluation_result = self.run_single_round(method)
                    
                    # 存储结果
                    self.distribution_results.append(distribution_result)
                    self.evaluation_results.append(evaluation_result)
                
                print(f"\n第{round_num}轮模拟完成")
            
            print("\n"+"="*50)
            print("社区农场公平实验模拟结束")
            print("="*50)
            
            # 保存最终结果
            if self.config["save_results"]:
                self.save_simulation_results()
            
            return self.evaluation_results
        
        finally:
            # 确保关闭日志记录器
            close_logger()
    
    def run_single_round(self, distribution_method: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """运行单轮模拟
        
        参数:
            distribution_method: 分配方法名称
            
        返回:
            包含分配结果和评估结果的元组
        """
        current_resources = self.resource_generator.current_resources
        print(f"\n当前可用资源: {current_resources}")
        
        # 根据选择的分配方法分配资源
        distribution_result = {}
        if distribution_method == "equal":
            distribution_result = equal_distribution(current_resources, self.agents)
            method_name = "平均分配"
        elif distribution_method == "needs_based":
            # 算法驱动的按需分配（修正版）
            distribution_result = needs_based_distribution(current_resources, self.agents, self.family_needs)
            method_name = "按需分配（算法）"
        elif distribution_method == "llm_needs_based":
            # LLM驱动的按需分配
            from distribution_mechanisms import llm_driven_needs_based_distribution
            
            # 获取上一轮的分配和评价
            prev_dist = None
            prev_eval = None
            if self.current_round > 1 and self.distribution_results:
                prev_dist = self.distribution_results[-1].get("distribution", {})
            if self.current_round > 1 and self.evaluation_results:
                prev_eval = self.evaluation_results[-1].get("agent_evaluations", [])
            
            distribution_result = llm_driven_needs_based_distribution(
                total_resources=current_resources,
                agents=self.agents,
                survival_needs=self.family_needs,
                round_number=self.current_round,
                previous_distribution=prev_dist,
                previous_evaluations=prev_eval
            )
            method_name = "按需分配（LLM）"
        elif distribution_method == "contribution_based":
            distribution_result = contribution_based_distribution(
                current_resources, 
                self.agents,
                self.family_needs  # 传入生存需求确保基本生存
            )
            method_name = "按贡献分配"
        elif distribution_method in ("negotiation", "distribution_based"):
            distribution_result = negotiation_based_distribution(
                total_resources=current_resources,
                agents=self.agents,
                survival_needs=self.family_needs,
                round_number=self.current_round,
                experiment_id=self.experiment_id  # 🆕 传递experiment_id
            )
            method_name = "协商分配"
        else:
            print(f"未知的分配方法: {distribution_method}")
            return {}, {}
        
        # 更新家庭资源
        for agent_id, resources in distribution_result.items():
            self.family_resources[agent_id] = resources
        
        # 评估分配结果（需要先评估才能获得满意度）
        evaluation_result = evaluate_distribution(
            distribution_result=distribution_result,
            agents=self.agents,
            total_resources=current_resources,
            round_number=self.current_round,
            distribution_method=method_name,
            survival_needs_map=self.family_needs,
            productions_map={}  # 暂时为空，后面会更新
        )
        
        # 🎯 计算家庭产出（考虑满意度影响）
        self.family_productions = {}
        for agent in self.agents:
            agent_id = agent["id"]
            resources = self.family_resources.get(agent_id, {})
            needs = self.family_needs.get(agent_id, {})
            labor_force = agent.get("labor_force", 0)
            
            # 获取该家庭的满意度评分
            satisfaction_score = None
            for eval_item in evaluation_result.get("agent_evaluations", []):
                if eval_item.get("agent_id") == agent_id:
                    satisfaction_score = eval_item.get("fairness_score")
                    break
            
            # 计算产出（带满意度影响）
            production = calculate_production(
                resources, 
                needs, 
                labor_force,
                satisfaction_score=satisfaction_score,
                distribution_method=distribution_method
            )
            
            self.family_productions[agent_id] = production
        
        # 生成下一轮资源
        next_resources = self.resource_generator.generate_next_round_resources(self.family_productions)
        
        # 🎯 更新评估结果（包含产出数据和分层统计）
        final_evaluation_result = evaluate_distribution(
            distribution_result=distribution_result,
            agents=self.agents,
            total_resources=current_resources,
            round_number=self.current_round,
            distribution_method=method_name,
            survival_needs_map=self.family_needs,
            productions_map=self.family_productions
        )
        
        # 保留原始满意度评分（避免重复LLM调用）
        final_evaluation_result["agent_evaluations"] = evaluation_result["agent_evaluations"]
        final_evaluation_result["average_satisfaction"] = evaluation_result["average_satisfaction"]
        
        # 打印分配结果摘要
        print_distribution_summary(
            distribution_result=distribution_result,
            agents=self.agents,
            statistics=final_evaluation_result["statistics"],
            layered_statistics=final_evaluation_result.get("layered_statistics")
        )
        
        # 打印平均满意度
        if final_evaluation_result.get("average_satisfaction") is not None:
            print(f"\n平均公平满意度: {final_evaluation_result.get('average_satisfaction', 0):.2f}/5.0")
        else:
            print("\n未能计算平均满意度")
        
        # 构建单轮结果
        round_result = {
            "round": self.current_round,
            "distribution_method": distribution_method,
            "method_name": method_name,
            "resources": current_resources,
            "distribution": distribution_result,
            "productions": self.family_productions,
            "next_resources": next_resources
        }
        
        return round_result, final_evaluation_result
    
    def save_simulation_results(self):
        """保存模拟结果到文件"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        results_file = os.path.join(self.config["results_dir"], f"simulation_results_{timestamp}.json")
        
        results = {
            "config": self.config,
            "agents": self.agents,
            "distribution_results": self.distribution_results,
            "evaluation_results": self.evaluation_results
        }
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n模拟结果已保存到 {results_file}")

def load_agents(filename: str = "agents.json") -> List[Dict[str, Any]]:
    """从文件加载代理
    
    参数:
        filename: 代理文件名
        
    返回:
        代理列表
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("agents", [])
    except Exception as e:
        print(f"加载代理时出错: {str(e)}")
        return []

def main():
    """主函数，运行模拟"""
    # 创建模拟配置
    config = {
        "rounds": 10,
        "initial_resource": 250,
        "distribution_methods": ["llm_needs_based"]  # LLM驱动的按需分配
    }
    
    # 创建并运行模拟
    simulator = SimulationRunner(config)
    simulator.setup()
    results = simulator.run_simulation()
    
    # 输出最终结果摘要
    print("\n"+"="*50)
    print("模拟结果摘要")
    print("="*50)
    
    # 分析各种分配方法的效果
    method_satisfaction = {}
    for result in results:
        method = result["distribution_method"]
        satisfaction = result.get("average_satisfaction")
        
        if method not in method_satisfaction:
            method_satisfaction[method] = []
        
        if satisfaction is not None:
            method_satisfaction[method].append(satisfaction)
    
    # 计算平均满意度
    for method, scores in method_satisfaction.items():
        if scores:
            avg = sum(scores) / len(scores)
            print(f"{method}平均满意度: {avg:.2f}/5.0")

if __name__ == "__main__":
    main() 