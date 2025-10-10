import json
import os
from typing import Dict, Any
from resource_system import ResourceSystem, print_resource_info

def initialize_first_round_resources(
    resource_name: str = "农作物",
    resource_unit: str = "单位",
    initial_amount: float = 100.0,
    output_file: str = "resources.json"
) -> Dict[str, Any]:
    """初始化第一轮的资源
    
    参数:
        resource_name: 资源名称
        resource_unit: 资源计量单位
        initial_amount: 初始资源量
        output_file: 输出文件名
        
    返回:
        资源信息字典
    """
    print(f"\n==== 初始化第一轮资源 ====")
    print(f"资源类型: {resource_name}")
    print(f"计量单位: {resource_unit}")
    print(f"初始数量: {initial_amount:.2f}")
    
    # 创建资源系统
    resource_system = ResourceSystem()
    
    # 添加资源
    resource_info = resource_system.add_resource(
        name=resource_name,
        unit=resource_unit,
        initial_amount=initial_amount,
        description=f"社区农场的{resource_name}资源，用于家庭分配"
    )
    
    # 保存到文件
    resource_system.save_to_file(output_file)
    
    return resource_info

def calculate_resource_amount_for_families(
    family_count: int,
    base_per_family: float = 20.0,
    variability: float = 0.2
) -> float:
    """计算适合特定家庭数量的资源总量
    
    参数:
        family_count: 家庭数量
        base_per_family: 每个家庭的基础资源量
        variability: 资源量的变异系数
        
    返回:
        适合的资源总量
    """
    import random
    
    # 基础计算: 家庭数 * 每家基础量
    base_amount = family_count * base_per_family
    
    # 添加一些随机变异
    variability_factor = 1.0 - variability/2 + random.random() * variability
    final_amount = base_amount * variability_factor
    
    return round(final_amount, 1)  # 四舍五入到一位小数

def load_family_count() -> int:
    """尝试从agents.json加载家庭数量
    
    返回:
        家庭数量，如果无法加载则返回默认值5
    """
    try:
        with open("agents.json", 'r', encoding='utf-8') as f:
            agents_data = json.load(f)
            return len(agents_data.get("agents", []))
    except:
        print("无法从agents.json加载代理数据，将使用默认家庭数量5")
        return 5

if __name__ == "__main__":
    # 尝试加载家庭数量
    family_count = load_family_count()
    print(f"检测到{family_count}个家庭")
    
    # 根据家庭数量计算合适的资源总量
    resource_amount = calculate_resource_amount_for_families(
        family_count=family_count,
        base_per_family=20.0  # 每个家庭平均20单位资源
    )
    
    # 初始化资源
    resource_info = initialize_first_round_resources(
        resource_name="农作物",
        resource_unit="单位",
        initial_amount=resource_amount
    )
    
    print("\n资源初始化完成！请查看resources.json文件获取详情。")
    print("\n资源信息概要:")
    print_resource_info(resource_info) 