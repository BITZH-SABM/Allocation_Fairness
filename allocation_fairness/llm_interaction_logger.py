# -*- coding: utf-8 -*-
"""
llm_interaction_logger.py

实时记录LLM交互的日志工具
在实验运行时记录每次LLM调用的输入和输出
"""

import csv
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List


class LLMInteractionLogger:
    """LLM交互日志记录器"""
    
    def __init__(self, log_dir: str = "llm_logs", experiment_id: str = None):
        """
        初始化日志记录器
        
        参数:
            log_dir: 日志保存目录
            experiment_id: 实验ID，如果为None则自动生成
        """
        self.log_dir = log_dir
        
        # 创建日志目录
        os.makedirs(log_dir, exist_ok=True)
        
        # 生成实验ID
        if experiment_id is None:
            experiment_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.experiment_id = experiment_id
        
        # CSV文件路径
        self.csv_file = os.path.join(log_dir, f"llm_interactions_{experiment_id}.csv")
        
        # 初始化CSV文件
        self._init_csv()
        
        # 统计信息
        self.total_calls = 0
        self.calls_by_round = {}
        
        print(f"📝 LLM交互日志器已启动")
        print(f"   日志文件: {self.csv_file}")
    
    def _init_csv(self):
        """初始化CSV文件，写入表头"""
        with open(self.csv_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                '时间戳',
                '回合数',
                'Agent_ID',
                '家庭名称',
                '价值观',
                '成员数',
                '劳动力数',
                '分配方式',
                '分配资源',
                '调用类型',
                'LLM模型',
                '温度',
                'LLM输入Prompt',
                'LLM原始输出',
                '提取的Score',
                '处理后的数据',
                '调用耗时(秒)',
                '是否成功'
            ])
    
    def log_evaluation_call(
        self,
        round_number: int,
        agent: Dict[str, Any],
        distribution_method: str,
        allocated_resources: float,
        input_prompt: str,
        raw_output: str,
        extracted_score: Optional[float],
        model: str = "unknown",
        temperature: float = 0.0,
        duration: float = 0.0,
        success: bool = True,
        processed_data: Optional[Dict] = None
    ):
        """
        记录评估阶段的LLM调用
        
        参数:
            round_number: 回合数
            agent: 代理信息
            distribution_method: 分配方式
            allocated_resources: 分配的资源量
            input_prompt: 输入的prompt
            raw_output: LLM原始输出
            extracted_score: 提取的评分
            model: 模型名称
            temperature: 温度参数
            duration: 调用耗时
            success: 是否成功
            processed_data: 处理后的数据（可选）
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 更新统计
        self.total_calls += 1
        self.calls_by_round[round_number] = self.calls_by_round.get(round_number, 0) + 1
        
        # 写入CSV
        with open(self.csv_file, 'a', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                round_number,
                agent.get('id', 'Unknown'),
                agent.get('family_name', 'Unknown'),
                agent.get('value_type', 'Unknown'),
                agent.get('members', 0),
                agent.get('labor_force', 0),
                distribution_method,
                f"{allocated_resources:.2f}",
                '主观评价',
                model,
                temperature,
                input_prompt,
                raw_output,
                extracted_score if extracted_score is not None else '',
                json.dumps(processed_data, ensure_ascii=False) if processed_data else '',
                f"{duration:.2f}",
                'Yes' if success else 'No'
            ])
    
    def log_negotiation_call(
        self,
        round_number: int,
        stage: str,
        agent: Optional[Dict[str, Any]],
        input_prompt: str,
        raw_output: str,
        model: str = "unknown",
        temperature: float = 0.0,
        duration: float = 0.0,
        success: bool = True,
        processed_data: Optional[Dict] = None
    ):
        """
        记录协商阶段的LLM调用
        
        参数:
            round_number: 回合数
            stage: 协商阶段（principles/principles-persuasion/framework/details/finalization）
            agent: 代理信息（如果是单个agent的调用）
            input_prompt: 输入的prompt
            raw_output: LLM原始输出
            model: 模型名称
            temperature: 温度参数
            duration: 调用耗时
            success: 是否成功
            processed_data: 处理后的数据（可选）
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 更新统计
        self.total_calls += 1
        self.calls_by_round[round_number] = self.calls_by_round.get(round_number, 0) + 1
        
        # 协商阶段的中文描述
        stage_names = {
            'principles': '阶段1-确定分配原则',
            'principles-persuasion': '阶段1-说服支持原则',
            'framework': '阶段2-协商分配框架',
            'details': '阶段3-构建详细方案',
            'finalization': '阶段4-最终确认微调'
        }
        stage_display = stage_names.get(stage, f'协商-{stage}')
        
        # 写入CSV
        with open(self.csv_file, 'a', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                round_number,
                agent.get('id', '') if agent else '',
                agent.get('family_name', '') if agent else '全体',
                agent.get('value_type', '') if agent else '',
                agent.get('members', '') if agent else '',
                agent.get('labor_force', '') if agent else '',
                stage_display,
                '',
                f'协商/{stage}',
                model,
                temperature,
                input_prompt,
                raw_output,
                '',
                json.dumps(processed_data, ensure_ascii=False) if processed_data else '',
                f"{duration:.2f}",
                'Yes' if success else 'No'
            ])
    
    def print_statistics(self):
        """打印统计信息"""
        print(f"\n📊 LLM交互统计:")
        print(f"   总调用次数: {self.total_calls}")
        print(f"   涉及回合数: {len(self.calls_by_round)}")
        if self.calls_by_round:
            print(f"   各回合调用次数:")
            for round_num in sorted(self.calls_by_round.keys()):
                print(f"     第{round_num}轮: {self.calls_by_round[round_num]}次")
    
    def close(self):
        """关闭日志记录器"""
        self.print_statistics()
        print(f"✅ LLM交互日志已保存到: {self.csv_file}")


# 全局日志记录器实例
_global_logger: Optional[LLMInteractionLogger] = None


def initialize_logger(log_dir: str = "llm_logs", experiment_id: str = None) -> LLMInteractionLogger:
    """初始化全局日志记录器"""
    global _global_logger
    _global_logger = LLMInteractionLogger(log_dir, experiment_id)
    return _global_logger


def get_logger() -> Optional[LLMInteractionLogger]:
    """获取全局日志记录器"""
    return _global_logger


def close_logger():
    """关闭全局日志记录器"""
    global _global_logger
    if _global_logger:
        _global_logger.close()
        _global_logger = None
