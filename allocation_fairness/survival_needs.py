"""
生存需求计算模块 - 计算每个家庭的基本生存资源需求
"""
from typing import Dict, Any

def calculate_survival_needs(total_members: int, labor_force: int) -> Dict[str, float]:
    """计算家庭的生存资源需求
    
    参数:
        total_members: 家庭成员总数
        labor_force: 劳动力人数
        
    返回:
        生存需求字典，键为资源名称，值为需求量
    """
    # 计算非劳动力人数（儿童和老人）
    non_labor = total_members - labor_force
    
    # 基础需求系数 - 简化版
    labor_consumption = 2      # 每个劳动力成员消耗2单位
    non_labor_consumption = 1  # 每个非劳动力成员消耗1单位
    
    # 计算总粮食需求
    grain_need = (labor_force * labor_consumption) + (non_labor * non_labor_consumption)
    
    # 只返回grain资源的需求
    return {"grain": grain_need}

def calculate_minimum_resource_threshold(
    agent: Dict[str, Any], 
    buffer_factor: float = 1.1
) -> Dict[str, float]:
    """计算代理家庭的最低资源阈值（生存+缓冲）
    
    参数:
        agent: 代理数据字典
        buffer_factor: 缓冲系数，默认为1.1（比基本需求高10%）
        
    返回:
        最低资源阈值字典
    """
    # 计算基本生存需求
    basic_needs = calculate_survival_needs(
        agent["members"],
        agent["labor_force"]
    )
    
    # 应用缓冲系数
    threshold = {
        resource: amount * buffer_factor
        for resource, amount in basic_needs.items()
    }
    
    return threshold

def check_survival_status(
    family_resources: Dict[str, float],
    survival_needs: Dict[str, float]
) -> Dict[str, Any]:
    """检查家庭的生存状态
    
    参数:
        family_resources: 家庭拥有的资源
        survival_needs: 家庭的生存需求
        
    返回:
        生存状态字典
    """
    status = {
        "survived": True,
        "deficit_resources": {},
        "survival_ratio": {}  # 每种资源的满足比例
    }
    
    for resource, need_amount in survival_needs.items():
        # 获取家庭拥有的资源量
        have_amount = family_resources.get(resource, 0)
        
        # 计算满足比例
        if need_amount > 0:
            ratio = have_amount / need_amount
        else:
            ratio = 1.0  # 如果需求为0，则认为完全满足
        
        status["survival_ratio"][resource] = ratio
        
        # 检查是否有缺口
        if have_amount < need_amount:
            deficit = need_amount - have_amount
            status["deficit_resources"][resource] = deficit
    
    # 如果有任何资源不足50%，认为未能生存
    for ratio in status["survival_ratio"].values():
        if ratio < 0.5:
            status["survived"] = False
            break
    
    return status 