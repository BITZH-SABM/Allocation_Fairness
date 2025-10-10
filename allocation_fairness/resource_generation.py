"""
资源生成模块 - 处理资源的动态演化和再生
"""
from typing import List, Dict, Any
import math

class ResourceGenerator:
    """资源生成器类，负责处理资源的动态生成和演化"""
    
    def __init__(self, total_families: int, initial_resource: int = 100):
        """初始化资源生成器
        
        参数:
            total_families: 家庭总数
            initial_resource: 系统初始资源总量
        """
        # 设置初始资源 - 固定为100
        total_grain = initial_resource
        self.current_resources = {"grain": total_grain}
        
        # 跟踪资源变化
        self.previous_total = total_grain
        self.sustainability_index = 1.0  # 资源可持续性指数，低于1表示资源正在减少
        self.overuse_warning = False  # 资源过度使用警告

    def generate_next_round_resources(
        self, 
        family_productions: Dict[int, Dict[str, float]]
    ) -> Dict[str, float]:
        """生成下一轮的资源
        
        参数:
            family_productions: 家庭产出字典，键为家庭ID，值为资源产出字典
            
        返回:
            下一轮的资源字典
        """
        next_round_resources = {}
        
        # 计算总产出
        total_production = {}
        for family_id, production in family_productions.items():
            for resource_name, amount in production.items():
                if resource_name not in total_production:
                    total_production[resource_name] = 0
                total_production[resource_name] += amount
        
        # 计算每种资源的下一轮数量
        for resource_name, current_amount in self.current_resources.items():
            # 家庭产出量
            production_amount = total_production.get(resource_name, 0)
            
            # 下一轮资源仅为家庭产出总和
            new_amount = production_amount
            
            # 更新资源量
            next_round_resources[resource_name] = new_amount
        
        # 更新当前资源
        self.current_resources = next_round_resources.copy()
        
        # 更新可持续性指数
        new_total = sum(next_round_resources.values())
        self.sustainability_index = new_total / self.previous_total if self.previous_total > 0 else 1.0
        self.previous_total = new_total
        
        # 检查资源是否过度使用
        self.check_resource_sustainability()
        
        return next_round_resources
    
    def check_resource_sustainability(self):
        """检查资源可持续性，设置过度使用警告"""
        # 如果可持续性指数低于0.9，表示资源正在明显减少
        if self.sustainability_index < 0.9:
            self.overuse_warning = True
        else:
            self.overuse_warning = False

def calculate_production(
    family_resources: Dict[str, float],
    survival_needs: Dict[str, float],
    labor_force: int,
    satisfaction_score: float = None,
    distribution_method: str = None
) -> Dict[str, float]:
    """计算家庭的资源产出（考虑满意度影响）
    
    参数:
        family_resources: 家庭拥有的资源
        survival_needs: 家庭的生存需求
        labor_force: 家庭劳动力数量
        satisfaction_score: 家庭对分配的满意度评分(0-5)
        distribution_method: 分配方法名称
        
    返回:
        产出资源字典
    """
    production = {}
    
    # 基础参数
    base_output = 5.0  # 基础产出（自然生长），从4.0增加到5.0
    max_resource_per_labor = 5.0  # 每个劳动力最多可处理的资源量
    labor_efficiency = 1.0  # 劳动力增益系数，从0.8增加到1.0
    
    # 🎯 满意度驱动的效率调整
    satisfaction_efficiency = calculate_satisfaction_efficiency(
        satisfaction_score, distribution_method
    )
    
    # 计算可用于生产的资源（总资源减去生存需求）
    production_resources = {}
    for resource_name, amount in family_resources.items():
        needed_amount = survival_needs.get(resource_name, 0)
        # 可用于生产的资源 = 总资源 - 生存需要
        available = max(0, amount - needed_amount)
        production_resources[resource_name] = available
    
    # 计算每种资源的产出
    for resource_name, available_amount in production_resources.items():
        # 计算劳动力实际能处理的资源量（有上限）
        max_processable = labor_force * max_resource_per_labor
        actual_processed = min(available_amount, max_processable)
        
        if actual_processed == 0 or labor_force == 0:
            # 如果没有资源或劳动力，只有基础产出（不受满意度影响）
            output = base_output
        else:
            # 计算劳动力密度（每单位资源的劳动力投入）
            # 限制最高为1.0，避免过小资源产生过高效率
            labor_density = min(labor_force / actual_processed, 1.0)
            
            # 资源转化效率：基础转化率(1.0) + 劳动力带来的额外效率
            efficiency = 1.0 + (labor_density * labor_efficiency)
            
            # 🎯 应用满意度效率调整
            efficiency *= satisfaction_efficiency
            
            # 资源产出 = 资源量 × 效率
            resource_output = actual_processed * efficiency
            
            # 总产出 = 基础产出（不受满意度影响）+ 资源产出（受效率影响）
            output = base_output + resource_output
            
            # 可选：添加浪费资源的警告
            wasted = max(0, available_amount - max_processable)
            if wasted > 0:
                print(f"警告: 由于劳动力不足，{wasted:.2f}单位{resource_name}资源未能有效利用")
        
        # 存储产出结果
        production[resource_name] = output
    
    return production

def calculate_satisfaction_efficiency(
    satisfaction_score: float = None, 
    distribution_method: str = None
) -> float:
    """计算基于满意度的生产效率系数
    
    参数:
        satisfaction_score: 满意度评分(0-5)，None表示无评分
        distribution_method: 分配方法名称
        
    返回:
        生产效率系数(0.8-1.2)
    """
    if satisfaction_score is None:
        # 无满意度数据时的默认效率
        return 1.0
    
    # 将0-5的满意度转换为效率系数
    # 满意度2.5(中等) → 效率1.0(基准)
    # 满意度趋近0(极不满意) → 计算后会被截断到0.8
    # 满意度趋近5(非常满意) → 计算后会被截断到1.2
    
    base_efficiency = 1.0
    satisfaction_normalized = (satisfaction_score - 2.5) / 2.5  # 转换为-1到1的范围
    
    if satisfaction_normalized >= 0:
        # 正向满意度：线性增长至1.4
        efficiency_bonus = satisfaction_normalized * 0.4  # 最多+40%
        efficiency = base_efficiency + efficiency_bonus
    else:
        # 负向满意度：线性下降至0.7
        efficiency_penalty = abs(satisfaction_normalized) * 0.3  # 最多-30%
        efficiency = base_efficiency - efficiency_penalty
    
    # 协商分配的额外加成（已取消，统一采用满意度映射与区间截断）
    
    # 限制在合理范围内（0.8 - 1.2）
    return max(0.8, min(efficiency, 1.2))

def initialize_resources(num_families: int) -> Dict[str, float]:
    """初始化系统资源
    
    参数:
        num_families: 家庭数量
        
    返回:
        初始资源字典
    """
    # 系统初始资源总量固定为100单位
    total_grain = 100
    
    # 返回固定的初始资源量
    return {"grain": total_grain} 