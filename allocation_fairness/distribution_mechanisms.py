"""
分配机制模块 - 包含不同的资源分配策略
"""
from typing import List, Dict, Any
import math
from collaborative_negotiation import collaborative_negotiation_distribution

def equal_distribution(total_resources: Dict[str, float], agents: List[Dict[str, Any]]) -> Dict[int, Dict[str, float]]:
    """平均分配机制
    
    将总资源平均分配给所有家庭，每个家庭获得相同数量的资源
    
    参数:
        total_resources: 总资源字典，键为资源名称，值为数量
        agents: 代理列表
        
    返回:
        分配结果字典，键为代理ID，值为分配到的资源字典
    """
    # 获取家庭数量
    num_families = len(agents)
    
    if num_families == 0:
        return {}
    
    # 计算每个家庭分得的资源量
    distribution_result = {}
    
    for agent in agents:
        agent_id = agent["id"]
        # 为每个代理创建资源分配字典
        distribution_result[agent_id] = {}
        
        # 对每种资源进行平均分配
        for resource_name, resource_amount in total_resources.items():
            # 计算每个家庭平均分得的资源量
            per_family_amount = resource_amount / num_families
            # 记录分配结果
            distribution_result[agent_id][resource_name] = per_family_amount
    
    # 整数化（不启用保底）
    return integerize_distribution(total_resources, agents, distribution_result, survival_needs=None, enforce_min_survival=False)

def calculate_production_needs(
    agent: Dict[str, Any], 
    survival_needs: Dict[str, float],
    total_resources: Dict[str, float],
    agents: List[Dict[str, Any]] = None,
    round_number: int = 1,
    previous_distribution: Dict[int, Dict[str, float]] = None
) -> Dict[str, float]:
    """计算家庭的生产需求
    
    参数:
        agent: 代理数据
        survival_needs: 生存需求
        total_resources: 总资源量
        agents: 所有代理列表，用于计算平均值等
        round_number: 当前轮数，用于动态调整需求
        previous_distribution: 上一轮分配结果，用于参考
        
    返回:
        生产需求字典
    """
    production_needs = {}
    labor_force = agent.get("labor_force", 0)
    members = agent.get("members", 0)
    agent_id = agent.get("id")
    
    # 每个劳动力最多可处理的资源量
    max_resource_per_labor = 5.0
    
    # 获取代理价值观
    value_type = agent.get("value_type", "egalitarian")
    
    # 计算所有家庭的平均劳动力和成员数
    avg_labor = 0
    avg_members = 0
    total_labor = 0
    if agents:
        total_labor = sum(a.get("labor_force", 0) for a in agents)
        total_members = sum(a.get("members", 0) for a in agents)
        avg_labor = total_labor / len(agents) if len(agents) > 0 else 0
        avg_members = total_members / len(agents) if len(agents) > 0 else 0
    
    # 计算家庭依赖比（成员数/劳动力）- 越高表示负担越重
    dependency_ratio = members / labor_force if labor_force > 0 else 0
    avg_dependency_ratio = avg_members / avg_labor if avg_labor > 0 else 0
    
    # 计算上一轮分配状况（如果有）
    previous_satisfaction = 1.0  # 默认满意度中等
    if previous_distribution and agent_id in previous_distribution:
        # 计算上一轮请求满足率
        prev_resources = previous_distribution.get(agent_id, {})
        
        # 这里简化计算，实际应根据上一轮的请求与分配比例计算满意度
        if prev_resources:
            # 预估上一轮的请求（简化处理）
            prev_satisfaction = sum(prev_resources.values()) / (labor_force * max_resource_per_labor * len(prev_resources))
            prev_satisfaction = max(0.5, min(prev_satisfaction, 1.5))  # 限制在合理范围内
    
    # 动态需求调整系数 - 随轮数增加而增加资源请求的适应性
    adaptation_factor = min(1.0 + (round_number - 1) * 0.05, 1.3)  # 最多增加30%的适应性
    
    # 资源分析系数 - 分析总资源量相比上一轮的变化
    resource_trend = 1.0  # 默认资源稳定
    
    for resource_name, survival_need in survival_needs.items():
        total_amount = total_resources.get(resource_name, 0)
        per_capita_resource = total_amount / sum(a.get("members", 0) for a in agents) if agents else 0
        
        # 分析资源丰富程度
        resource_abundance = total_amount / (total_members * 2) if total_members > 0 else 1.0
        
        # 根据不同价值观计算基础生产需求
        if value_type == "egalitarian":  # 平等主义
            # 平等主义：追求每人拥有相等资源，按人口比例请求资源
            fair_share = (total_amount / sum(a.get("members", 0) for a in agents)) if agents else 0
            
            # 根据当前资源丰富程度调整需求
            if resource_abundance < 0.8:  # 资源较少
                # 资源少时，平等主义者倾向于要求严格按人口比例分配
                adjustment = 0.9 * adaptation_factor
            elif resource_abundance > 1.2:  # 资源丰富
                # 资源丰富时，可以适当提高请求以确保家庭成员获得足够资源
                adjustment = 1.1 * adaptation_factor
            else:  # 资源适中
                adjustment = 1.0 * adaptation_factor
            
            target_resource = fair_share * members * adjustment
            production_need = max(0, target_resource - survival_need)
            
            # 限制在劳动力能处理范围内
            max_processable = labor_force * max_resource_per_labor
            production_needs[resource_name] = min(production_need, max_processable)
            
        elif value_type == "merit_based":  # 贡献导向
            # 贡献导向：强调劳动力贡献，劳动力多的家庭应获得更多资源
            labor_proportion = labor_force / total_labor if total_labor > 0 else 0
            
            # 根据资源丰富程度调整需求
            if resource_abundance < 0.8:  # 资源较少
                # 资源少时，贡献导向者更强调按劳分配
                adjustment = 1.2 * adaptation_factor
                
                # 在资源紧张时，可能更激进地主张劳动力权益
                if labor_proportion > 0.3:  # 如果是主要劳动力贡献者
                    adjustment *= 1.1
            elif resource_abundance > 1.2:  # 资源丰富
                # 资源丰富时，可以更温和地请求
                adjustment = 1.0 * adaptation_factor
            else:  # 资源适中
                adjustment = 1.1 * adaptation_factor
                
            target_resource = total_amount * labor_proportion * adjustment
            
            # 确保获得至少满足基本生存的资源，剩余按劳动力比例分配
            production_need = max(0, target_resource - survival_need)
            
            # 限制在劳动力能处理范围内，但允许适当溢出以体现劳动优先
            max_processable = labor_force * max_resource_per_labor * 1.2
            production_needs[resource_name] = min(production_need, max_processable)
            
        elif value_type == "needs_based":  # 需求导向（按自身需要申报，不先扣生存）
            # 计算每个成员的基础需求
            base_need_per_member = 1.0

            # 根据依赖比调整需求系数（弱势家庭更高）
            need_multiplier = 1.0
            if dependency_ratio > avg_dependency_ratio:
                need_multiplier = 1.0 + (dependency_ratio - avg_dependency_ratio) * 0.5

            # 根据资源丰富程度和轮次调整需求
            if resource_abundance < 0.7:  # 资源紧张
                adjustment = 0.8 * adaptation_factor
                if dependency_ratio > 1.5:
                    adjustment = 0.9 * adaptation_factor
            elif resource_abundance > 1.3:  # 资源丰富
                adjustment = 1.2 * adaptation_factor
            else:  # 资源适中
                adjustment = 1.0 * adaptation_factor

            # 直接把“自身总需要”作为申报需求（不先扣生存）
            total_need = members * base_need_per_member * need_multiplier * adjustment

            # 为避免明显浪费，仍以产能上限截断
            max_processable = labor_force * max_resource_per_labor
            production_needs[resource_name] = min(total_need, max_processable)
            
        elif value_type == "pragmatic":  # 务实主义
            # 务实主义：灵活调整策略，根据资源丰富程度和自身能力调整需求
            resource_scarcity = total_amount / (sum(a.get("members", 0) for a in agents) * 2) if agents else 1
            
            # 根据上一轮满意度调整策略
            strategy_adjustment = 1.0
            if previous_distribution:
                if prev_satisfaction < 0.8:  # 上轮分配不足
                    # 如果上轮资源不足，务实主义者会增加请求
                    strategy_adjustment = 1.2
                elif prev_satisfaction > 1.2:  # 上轮分配充足
                    # 如果上轮资源充足，可能会适度减少请求以避免浪费
                    strategy_adjustment = 0.9
            
            if resource_scarcity < 0.7:  # 资源紧张
                # 资源紧张时更务实，要求刚好满足生产需求
                production_need = labor_force * max_resource_per_labor * 0.9 * adaptation_factor * strategy_adjustment
            elif resource_scarcity > 1.3:  # 资源丰富
                # 资源丰富时要求更多以最大化利益
                production_need = labor_force * max_resource_per_labor * 1.1 * adaptation_factor * strategy_adjustment
            else:  # 资源适中
                # 资源适中时要求刚好满足最优生产
                production_need = labor_force * max_resource_per_labor * adaptation_factor * strategy_adjustment
                
            production_needs[resource_name] = production_need
            
        elif value_type == "altruistic":  # 利他主义
            # 利他主义：优先考虑集体利益，在资源短缺时减少自身需求
            total_ideal_need = total_labor * max_resource_per_labor
            resource_scarcity = total_amount / total_ideal_need if total_ideal_need > 0 else 1
            
            # 家庭规模相对于平均值的比例
            size_ratio = members / avg_members if avg_members > 0 else 1
            
            # 根据轮次调整利他程度 - 随着轮数增加，利他主义者可能会更关注自身家庭利益
            altruism_decay = max(0.8, 1.0 - (round_number - 1) * 0.03)  # 利他主义最多降低20%
            
            if resource_scarcity < 0.6:  # 资源严重不足
                # 大幅降低需求，尤其是规模大的家庭
                reduction_factor = (0.5 if size_ratio > 1.2 else 0.7) * altruism_decay
                production_need = labor_force * max_resource_per_labor * reduction_factor
            elif resource_scarcity < 0.9:  # 资源偏紧
                # 适度降低需求
                reduction_factor = (0.7 if size_ratio > 1.1 else 0.8) * altruism_decay
                production_need = labor_force * max_resource_per_labor * reduction_factor
            else:  # 资源充足
                # 请求适中资源，不超过应得份额
                production_need = min(
                    labor_force * max_resource_per_labor * 0.9 * altruism_decay,
                    (total_amount / len(agents)) if agents else 0
                ) * adaptation_factor
            
            production_needs[resource_name] = production_need
        else:
            # 默认计算方式
            production_needs[resource_name] = labor_force * max_resource_per_labor * adaptation_factor
    
    return production_needs

def needs_based_distribution(
    total_resources: Dict[str, float], 
    agents: List[Dict[str, Any]], 
    survival_needs: Dict[int, Dict[str, float]],
    round_number: int = 1,
    previous_distribution: Dict[int, Dict[str, float]] = None
) -> Dict[int, Dict[str, float]]:
    """按需分配机制（修正版）
    
    真正按照家庭实际需求进行分配，优先保障基本生存需求。
    
    修正要点：
    1. 优先按人口比例保障基本生存需求
    2. 剩余资源考虑人口、劳力和特殊需求
    3. 设置人均最低保障线
    
    参数:
        total_resources: 总资源字典，键为资源名称，值为数量
        agents: 代理列表
        survival_needs: 生存需求字典，键为代理ID，值为需求资源字典
        round_number: 当前轮数，用于动态调整需求
        previous_distribution: 上一轮分配结果，用于参考
        
    返回:
        分配结果字典，键为代理ID，值为分配到的资源字典
    """
    if not agents or not survival_needs:
        return {}
    
    distribution_result = {}
    
    # 🆕 计算社区总人口和总劳力
    total_members = sum(agent.get("members", 0) for agent in agents)
    total_labor = sum(agent.get("labor_force", 0) for agent in agents)
    
    print("\n" + "="*50)
    print("🆕 按需分配（修正版）")
    print("="*50)
    
    for resource_name, total_amount in total_resources.items():
        # 🆕 第一阶段：计算基本生存需求（70%资源）
        basic_resource_pool = total_amount * 0.70
        
        # 计算总的基本生存需求
        total_survival_needs = sum(
            survival_needs.get(agent["id"], {}).get(resource_name, 0) 
            for agent in agents
        )
        
        print(f"\n资源类型: {resource_name}")
        print(f"  总资源: {total_amount:.2f}")
        print(f"  基础保障池(70%): {basic_resource_pool:.2f}")
        print(f"  总生存需求: {total_survival_needs:.2f}")
        
        # 分配基础份额（按人口比例）
        basic_allocations = {}
        if total_members > 0:
            # 🆕 按人口比例分配基础保障资源
            for agent in agents:
                agent_id = agent["id"]
                members = agent.get("members", 0)
                
                # 人口比例
                population_ratio = members / total_members
                basic_allocation = basic_resource_pool * population_ratio
                
                basic_allocations[agent_id] = basic_allocation
                
                if agent_id not in distribution_result:
                    distribution_result[agent_id] = {}
                distribution_result[agent_id][resource_name] = basic_allocation
        
        # 🆕 第二阶段：分配剩余资源（30%资源）
        remaining_resource_pool = total_amount * 0.30
        
        # 剩余资源分配权重：50%按人口，30%按劳力，20%按特殊需求
        for agent in agents:
            agent_id = agent["id"]
            members = agent.get("members", 0)
            labor_force = agent.get("labor_force", 0)
            
            # 计算劳力密度（劳力/人口）
            labor_density = labor_force / members if members > 0 else 0
            
            # 计算特殊需求权重（低劳力密度家庭=抚养负担重）
            special_need_weight = 0
            if labor_density < 0.5:  # 劳力密度<50%，属于抚养型家庭
                special_need_weight = (0.5 - labor_density) * 2  # 0-1之间
            
            # 人口权重（50%）
            population_share = (members / total_members) * 0.50 if total_members > 0 else 0
            
            # 劳力权重（30%）
            labor_share = (labor_force / total_labor) * 0.30 if total_labor > 0 else 0
            
            # 特殊需求权重（20%）
            total_special_need_weight = sum(
                ((a.get("labor_force", 0) / a.get("members", 1)) < 0.5) * 
                (0.5 - (a.get("labor_force", 0) / a.get("members", 1))) * 2
                for a in agents
            )
            special_share = (special_need_weight / total_special_need_weight) * 0.20 if total_special_need_weight > 0 else 0
            
            # 总权重
            total_share = population_share + labor_share + special_share
            
            # 分配剩余资源
            additional_allocation = remaining_resource_pool * total_share
            distribution_result[agent_id][resource_name] += additional_allocation
            
            print(f"\n  {agent['family_name']}家庭(ID:{agent_id}, {members}人{labor_force}劳力):")
            print(f"    基础保障: {basic_allocations[agent_id]:.2f} (人口比例: {members}/{total_members})")
            print(f"    额外分配: {additional_allocation:.2f} (人口{population_share:.3f} + 劳力{labor_share:.3f} + 特殊{special_share:.3f})")
            print(f"    总分配: {distribution_result[agent_id][resource_name]:.2f}")
            print(f"    人均: {distribution_result[agent_id][resource_name]/members:.2f}")
    
    # 🆕 第三阶段：确保最低生存线（人均≥3.5）
    print("\n" + "-"*50)
    print("🔍 检查最低生存线保障（人均≥3.5）")
    print("-"*50)
    
    for resource_name in total_resources.keys():
        min_per_capita = 3.5  # 最低人均资源
        adjustments = []
        
        for agent in agents:
            agent_id = agent["id"]
            members = agent.get("members", 0)
            current_allocation = distribution_result[agent_id][resource_name]
            per_capita = current_allocation / members if members > 0 else 0
            
            if per_capita < min_per_capita:
                shortage = (min_per_capita - per_capita) * members
                adjustments.append((agent_id, agent['family_name'], shortage, per_capita))
        
        if adjustments:
            print(f"\n⚠️ 发现{len(adjustments)}个家庭低于生存线:")
            total_shortage = sum(adj[2] for adj in adjustments)
            
            for agent_id, family_name, shortage, current_per_capita in adjustments:
                print(f"  {family_name}家庭: 人均{current_per_capita:.2f} < 3.5, 缺口{shortage:.2f}")
            
            # 从人均高于平均水平的家庭调配资源
            avg_per_capita = total_resources[resource_name] / total_members
            donors = []
            
            for agent in agents:
                agent_id = agent["id"]
                members = agent.get("members", 0)
                current_allocation = distribution_result[agent_id][resource_name]
                per_capita = current_allocation / members if members > 0 else 0
                
                if per_capita > avg_per_capita:
                    surplus = (per_capita - avg_per_capita) * members * 0.3  # 捐出30%超额部分
                    donors.append((agent_id, surplus))
            
            total_surplus = sum(donor[1] for donor in donors)
            
            if total_surplus > 0:
                print(f"\n  从{len(donors)}个富余家庭调配资源，总调配量: {total_surplus:.2f}")
                
                # 按比例调配
                for agent_id, family_name, shortage, _ in adjustments:
                    compensation = (shortage / total_shortage) * min(total_surplus, total_shortage)
                    distribution_result[agent_id][resource_name] += compensation
                    print(f"  → {family_name}家庭获得补偿: +{compensation:.2f}")
                
                # 从捐赠者扣除
                for donor_id, surplus in donors:
                    deduction = (surplus / total_surplus) * min(total_surplus, total_shortage)
                    distribution_result[donor_id][resource_name] -= deduction
            else:
                print(f"  ⚠️ 无可调配资源，总资源不足以保障所有家庭生存线")
    
    print("\n" + "="*50)
    print("✅ 按需分配完成")
    print("="*50 + "\n")
    
    # 整数化（启用保底）
    return integerize_distribution(total_resources, agents, distribution_result, survival_needs=survival_needs, enforce_min_survival=True)

def contribution_based_distribution(
    total_resources: Dict[str, float],
    agents: List[Dict[str, Any]],
    minimum_survival_resources: Dict[int, Dict[str, float]] = None
) -> Dict[int, Dict[str, float]]:
    """按贡献分配机制
    
    根据家庭的劳动力数量（贡献能力）进行分配，劳动力越多分得越多
    
    参数:
        total_resources: 总资源字典，键为资源名称，值为数量
        agents: 代理列表
        minimum_survival_resources: 最低生存资源需求，键为代理ID，值为资源字典
        
    返回:
        分配结果字典，键为代理ID，值为分配到的资源字典
    """
    if not agents:
        return {}
    
    # 计算总劳动力
    total_labor_force = sum(agent.get("labor_force", 0) for agent in agents)
    
    if total_labor_force == 0:
        # 如果没有劳动力，则平均分配
        return equal_distribution(total_resources, agents)
    
    distribution_result = {}
    
    # 对每种资源分别处理
    for resource_name, total_amount in total_resources.items():
        # 计算用于基本生存的资源总量（如果提供了最低生存资源需求）
        survival_resources_total = 0
        if minimum_survival_resources:
            for agent_id, needs in minimum_survival_resources.items():
                survival_resources_total += needs.get(resource_name, 0)
        
        # 计算剩余可分配资源
        distributable_resources = max(0, total_amount - survival_resources_total)
        
        # 为每个代理分配资源
        for agent in agents:
            agent_id = agent["id"]
            labor_force = agent.get("labor_force", 0)
            
            # 确保代理在分配结果中有条目
            if agent_id not in distribution_result:
                distribution_result[agent_id] = {}
            
            # 首先分配基本生存资源（如果有）
            base_survival_amount = 0
            if minimum_survival_resources and agent_id in minimum_survival_resources:
                base_survival_amount = minimum_survival_resources[agent_id].get(resource_name, 0)
            
            # 然后按劳动力比例分配剩余资源
            labor_proportion = labor_force / total_labor_force if total_labor_force > 0 else 0
            contribution_amount = labor_proportion * distributable_resources
            
            # 总分配量 = 基本生存量 + 贡献分配量
            distribution_result[agent_id][resource_name] = base_survival_amount + contribution_amount
    
    # 整数化（不启用保底）
    return integerize_distribution(total_resources, agents, distribution_result, survival_needs=minimum_survival_resources, enforce_min_survival=False)

def negotiation_based_distribution(
    total_resources: Dict[str, float],
    agents: List[Dict[str, Any]],
    survival_needs: Dict[int, Dict[str, float]],
    round_number: int = 1,
    previous_distribution: Dict[int, Dict[str, float]] = None,
    max_negotiation_rounds: int = 3,
    experiment_id: str = None
) -> Dict[int, Dict[str, float]]:
    """协商分配机制 - 新版本使用协作式协商
    
    通过多阶段协商讨论，让家庭代理共同构建分配方案
    
    参数:
        total_resources: 总资源字典
        agents: 代理列表
        survival_needs: 生存需求字典
        round_number: 当前轮数
        previous_distribution: 上一轮分配结果
        max_negotiation_rounds: 最大协商轮数
        experiment_id: 实验ID，用于统一所有轮次的日志
        
    返回:
        最终分配结果
    """
    print("\n🔄 使用新版协作式协商分配机制")
    
    # 调用新的协作式协商分配
    return collaborative_negotiation_distribution(
        total_resources=total_resources,
        agents=agents,
        survival_needs=survival_needs,
        round_number=round_number,
        previous_distribution=previous_distribution,
        max_negotiation_rounds=max_negotiation_rounds,
        experiment_id=experiment_id
    )

def generate_initial_proposals(
    total_resources: Dict[str, float],
    agents: List[Dict[str, Any]],
    survival_needs: Dict[int, Dict[str, float]],
    round_number: int,
    previous_distribution: Dict[int, Dict[str, float]]
) -> Dict[int, Dict[str, float]]:
    """生成初始提案
    
    每个代理根据自己的价值观提出初始分配方案
    """
    proposals = {}
    
    for agent in agents:
        agent_id = agent["id"]
        value_type = agent["value_type"]
        
        # 根据价值观生成提案
        if value_type == "egalitarian":
            # 平等主义：平均分配
            proposal = equal_distribution(total_resources, agents)
            proposals[agent_id] = proposal
            
        elif value_type == "needs_based":
            # 需求导向：按需分配
            proposal = needs_based_distribution(
                total_resources, agents, survival_needs, round_number, previous_distribution
            )
            proposals[agent_id] = proposal
            
        elif value_type == "merit_based":
            # 贡献导向：按贡献分配
            proposal = contribution_based_distribution(
                total_resources, agents, survival_needs
            )
            proposals[agent_id] = proposal
            
        elif value_type == "altruistic":
            # 利他主义：优先考虑弱势群体
            proposal = altruistic_distribution(
                total_resources, agents, survival_needs
            )
            proposals[agent_id] = proposal
            
        elif value_type == "pragmatic":
            # 务实主义：混合方案
            proposal = pragmatic_distribution(
                total_resources, agents, survival_needs, round_number, previous_distribution
            )
            proposals[agent_id] = proposal
    
    return proposals

def altruistic_distribution(
    total_resources: Dict[str, float],
    agents: List[Dict[str, Any]],
    survival_needs: Dict[int, Dict[str, float]]
) -> Dict[int, Dict[str, float]]:
    """利他主义分配方案
    
    优先满足弱势群体的需求，自己愿意少分配
    """
    distribution_result = {}
    
    # 计算每个家庭的依赖比（成员数/劳动力）
    dependency_ratios = {}
    for agent in agents:
        agent_id = agent["id"]
        members = agent.get("members", 1)
        labor_force = agent.get("labor_force", 1)
        dependency_ratios[agent_id] = members / labor_force if labor_force > 0 else float('inf')
    
    # 按依赖比排序，依赖比高的优先
    sorted_agents = sorted(agents, key=lambda x: dependency_ratios[x["id"]], reverse=True)
    
    remaining_resources = total_resources.copy()
    
    # 首先确保所有家庭获得基本生存资源
    for agent in sorted_agents:
        agent_id = agent["id"]
        distribution_result[agent_id] = {}
        
        for resource_name, total_amount in remaining_resources.items():
            survival_need = survival_needs.get(agent_id, {}).get(resource_name, 0)
            allocated = min(survival_need, remaining_resources[resource_name])
            
            distribution_result[agent_id][resource_name] = allocated
            remaining_resources[resource_name] -= allocated
    
    # 剩余资源按需求程度分配
    for agent in sorted_agents:
        agent_id = agent["id"]
        dependency_ratio = dependency_ratios[agent_id]
        
        for resource_name, remaining_amount in remaining_resources.items():
            if remaining_amount <= 0:
                continue
                
            # 依赖比高的家庭获得更多剩余资源
            additional_share = remaining_amount * (dependency_ratio / sum(dependency_ratios.values()))
            additional_share = min(additional_share, remaining_amount)
            
            distribution_result[agent_id][resource_name] += additional_share
            remaining_resources[resource_name] -= additional_share
    
    return distribution_result

def pragmatic_distribution(
    total_resources: Dict[str, float],
    agents: List[Dict[str, Any]],
    survival_needs: Dict[int, Dict[str, float]],
    round_number: int,
    previous_distribution: Dict[int, Dict[str, float]]
) -> Dict[int, Dict[str, float]]:
    """务实主义分配方案
    
    综合考虑多种因素，寻求平衡
    """
    # 计算权重
    survival_weight = 0.4  # 生存需求权重
    equality_weight = 0.3  # 平等权重
    merit_weight = 0.3     # 贡献权重
    
    # 生成三种基础分配方案
    survival_allocation = needs_based_distribution(
        total_resources, agents, survival_needs, round_number, previous_distribution
    )
    equality_allocation = equal_distribution(total_resources, agents)
    merit_allocation = contribution_based_distribution(
        total_resources, agents, survival_needs
    )
    
    # 加权合并
    final_allocation = {}
    for agent in agents:
        agent_id = agent["id"]
        final_allocation[agent_id] = {}
        
        for resource_name in total_resources.keys():
            survival_amount = survival_allocation.get(agent_id, {}).get(resource_name, 0)
            equality_amount = equality_allocation.get(agent_id, {}).get(resource_name, 0)
            merit_amount = merit_allocation.get(agent_id, {}).get(resource_name, 0)
            
            weighted_amount = (
                survival_amount * survival_weight +
                equality_amount * equality_weight +
                merit_amount * merit_weight
            )
            
            final_allocation[agent_id][resource_name] = weighted_amount
    
    return final_allocation

def evaluate_proposals(
    proposals: Dict[int, Dict[int, Dict[str, float]]],
    agents: List[Dict[str, Any]],
    total_resources: Dict[str, float],
    survival_needs: Dict[int, Dict[str, float]]
) -> Dict[int, Dict[str, Any]]:
    """评估每个提案
    
    每个代理对其他代理的提案进行评分
    """
    evaluations = {}
    
    for agent in agents:
        agent_id = agent["id"]
        value_type = agent["value_type"]
        evaluations[agent_id] = {}
        
        for proposer_id, proposal in proposals.items():
            # 根据价值观评估提案
            score = evaluate_proposal_by_values(
                proposal, agent, total_resources, survival_needs, agents
            )
            evaluations[agent_id][proposer_id] = {
                "score": score,
                "agreement": score >= 3.0  # 3分以上表示同意
            }
    
    return evaluations

def evaluate_proposal_by_values(
    proposal: Dict[int, Dict[str, float]],
    evaluator: Dict[str, Any],
    total_resources: Dict[str, float],
    survival_needs: Dict[int, Dict[str, float]],
    agents: List[Dict[str, Any]]
) -> float:
    """根据价值观评估提案"""
    value_type = evaluator["value_type"]
    evaluator_id = evaluator["id"]
    
    # 获取评估者自己的分配
    my_allocation = proposal.get(evaluator_id, {})
    
    # 计算基础指标
    total_allocated = sum(sum(allocation.values()) for allocation in proposal.values())
    resource_efficiency = total_allocated / sum(total_resources.values()) if sum(total_resources.values()) > 0 else 0
    
    # 检查生存需求满足度
    my_survival_needs = survival_needs.get(evaluator_id, {})
    survival_satisfaction = 0
    if my_survival_needs:
        survival_satisfaction = sum(
            min(my_allocation.get(resource, 0) / need, 1.0) 
            for resource, need in my_survival_needs.items() if need > 0
        ) / len(my_survival_needs)
    
    # 根据价值观评分
    if value_type == "egalitarian":
        # 平等主义：关注分配公平性
        allocations = list(proposal.values())
        if allocations:
            variance = calculate_allocation_variance(allocations)
            equality_score = max(0, 5 - variance * 2)  # 方差越小分数越高
            return (equality_score + survival_satisfaction * 5) / 2
            
    elif value_type == "needs_based":
        # 需求导向：关注需求满足度
        overall_survival_satisfaction = calculate_overall_survival_satisfaction(
            proposal, survival_needs
        )
        return (overall_survival_satisfaction * 5 + survival_satisfaction * 5) / 2
        
    elif value_type == "merit_based":
        # 贡献导向：关注效率和对劳动力的回报
        labor_efficiency = calculate_labor_efficiency(proposal, agents)
        return (labor_efficiency * 5 + resource_efficiency * 5) / 2
        
    elif value_type == "altruistic":
        # 利他主义：关注弱势群体
        weak_group_satisfaction = calculate_weak_group_satisfaction(
            proposal, agents, survival_needs
        )
        return (weak_group_satisfaction * 5 + survival_satisfaction * 5) / 2
        
    elif value_type == "pragmatic":
        # 务实主义：综合评估
        overall_score = (
            survival_satisfaction * 2 +
            resource_efficiency * 2 +
            calculate_allocation_balance(proposal) * 1
        ) / 5
        return overall_score * 5
    
    return 2.5  # 默认中等评分

def calculate_allocation_variance(allocations: List[Dict[str, float]]) -> float:
    """计算分配方差"""
    if not allocations:
        return 0
    
    # 计算每个分配的总量
    totals = [sum(allocation.values()) for allocation in allocations]
    mean_total = sum(totals) / len(totals)
    
    # 计算方差
    variance = sum((total - mean_total) ** 2 for total in totals) / len(totals)
    return variance

def calculate_overall_survival_satisfaction(
    proposal: Dict[int, Dict[str, float]],
    survival_needs: Dict[int, Dict[str, float]]
) -> float:
    """计算整体生存需求满足度"""
    if not survival_needs:
        return 1.0
    
    total_satisfaction = 0
    count = 0
    
    for agent_id, needs in survival_needs.items():
        allocation = proposal.get(agent_id, {})
        if needs:
            satisfaction = sum(
                min(allocation.get(resource, 0) / need, 1.0)
                for resource, need in needs.items() if need > 0
            ) / len(needs)
            total_satisfaction += satisfaction
            count += 1
    
    return total_satisfaction / count if count > 0 else 1.0

def calculate_labor_efficiency(
    proposal: Dict[int, Dict[str, float]],
    agents: List[Dict[str, Any]]
) -> float:
    """计算劳动力效率"""
    total_labor = sum(agent.get("labor_force", 0) for agent in agents)
    if total_labor == 0:
        return 1.0
    
    # 计算每个劳动力的平均分配量
    total_allocated = sum(sum(allocation.values()) for allocation in proposal.values())
    labor_efficiency = total_allocated / total_labor
    
    # 标准化到0-1范围
    return min(labor_efficiency / 10, 1.0)  # 假设每个劳动力10单位资源为理想值

def calculate_weak_group_satisfaction(
    proposal: Dict[int, Dict[str, float]],
    agents: List[Dict[str, Any]],
    survival_needs: Dict[int, Dict[str, float]]
) -> float:
    """计算弱势群体满意度"""
    # 识别弱势群体（依赖比高的家庭）
    weak_groups = []
    for agent in agents:
        members = agent.get("members", 1)
        labor_force = agent.get("labor_force", 1)
        dependency_ratio = members / labor_force if labor_force > 0 else float('inf')
        if dependency_ratio > 2.0:  # 依赖比大于2的视为弱势群体
            weak_groups.append(agent["id"])
    
    if not weak_groups:
        return 1.0
    
    # 计算弱势群体的平均满意度
    total_satisfaction = 0
    for agent_id in weak_groups:
        allocation = proposal.get(agent_id, {})
        needs = survival_needs.get(agent_id, {})
        if needs:
            satisfaction = sum(
                min(allocation.get(resource, 0) / need, 1.0)
                for resource, need in needs.items() if need > 0
            ) / len(needs)
            total_satisfaction += satisfaction
    
    return total_satisfaction / len(weak_groups)

def calculate_allocation_balance(proposal: Dict[int, Dict[str, float]]) -> float:
    """计算分配平衡性"""
    if not proposal:
        return 1.0
    
    # 计算分配的变异系数
    allocations = list(proposal.values())
    totals = [sum(allocation.values()) for allocation in allocations]
    mean_total = sum(totals) / len(totals)
    
    if mean_total == 0:
        return 1.0
    
    std_dev = (sum((total - mean_total) ** 2 for total in totals) / len(totals)) ** 0.5
    coefficient_of_variation = std_dev / mean_total
    
    # 变异系数越小，平衡性越好
    return max(0, 1 - coefficient_of_variation)

def check_consensus(
    evaluations: Dict[int, Dict[int, Dict[str, Any]]],
    agents: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """检查是否达成共识"""
    consensus_threshold = 0.8  # 80%的代理同意
    
    for proposer_id in evaluations[list(evaluations.keys())[0]].keys():
        agreements = 0
        total_evaluators = 0
        
        for evaluator_id, evaluation in evaluations.items():
            if proposer_id in evaluation:
                total_evaluators += 1
                if evaluation[proposer_id]["agreement"]:
                    agreements += 1
        
        consensus_ratio = agreements / total_evaluators if total_evaluators > 0 else 0
        
        if consensus_ratio >= consensus_threshold:
            return {
                "consensus_reached": True,
                "agreed_proposal": proposer_id
            }
    
    return {
        "consensus_reached": False,
        "agreed_proposal": None
    }

def generate_negotiation_proposals(
    current_proposals: Dict[int, Dict[int, Dict[str, float]]],
    evaluations: Dict[int, Dict[int, Dict[str, Any]]],
    agents: List[Dict[str, Any]],
    total_resources: Dict[str, float],
    survival_needs: Dict[int, Dict[str, float]],
    negotiation_round: int
) -> Dict[int, Dict[int, Dict[str, float]]]:
    """生成新的协商提案"""
    new_proposals = {}
    
    for agent in agents:
        agent_id = agent["id"]
        value_type = agent["value_type"]
        
        # 分析当前提案的反馈
        feedback = analyze_proposal_feedback(agent_id, evaluations)
        
        # 根据反馈调整提案
        adjusted_proposal = adjust_proposal_by_feedback(
            current_proposals[agent_id], feedback, agent, 
            total_resources, survival_needs, negotiation_round
        )
        
        new_proposals[agent_id] = adjusted_proposal
    
    return new_proposals

def analyze_proposal_feedback(
    agent_id: int,
    evaluations: Dict[int, Dict[int, Dict[str, Any]]]
) -> Dict[str, Any]:
    """分析提案反馈"""
    feedback = {
        "average_score": 0,
        "agreement_rate": 0,
        "criticisms": [],
        "suggestions": []
    }
    
    scores = []
    agreements = 0
    total_evaluators = 0
    
    for evaluator_id, evaluation in evaluations.items():
        if evaluator_id != agent_id and agent_id in evaluation:
            score = evaluation[agent_id]["score"]
            scores.append(score)
            total_evaluators += 1
            
            if evaluation[agent_id]["agreement"]:
                agreements += 1
    
    if scores:
        feedback["average_score"] = sum(scores) / len(scores)
        feedback["agreement_rate"] = agreements / total_evaluators if total_evaluators > 0 else 0
    
    return feedback

def adjust_proposal_by_feedback(
    current_proposal: Dict[int, Dict[str, float]],
    feedback: Dict[str, Any],
    agent: Dict[str, Any],
    total_resources: Dict[str, float],
    survival_needs: Dict[int, Dict[str, float]],
    negotiation_round: int
) -> Dict[int, Dict[str, float]]:
    """根据反馈调整提案"""
    value_type = agent["value_type"]
    adjustment_factor = 1.0
    
    # 根据反馈调整策略
    if feedback["average_score"] < 2.5:
        # 评分较低，需要调整
        adjustment_factor = 0.8
    elif feedback["average_score"] > 4.0:
        # 评分较高，可以稍微坚持
        adjustment_factor = 1.1
    
    # 根据价值观调整策略
    if value_type == "altruistic":
        # 利他主义者更容易让步
        adjustment_factor *= 0.9
    elif value_type == "merit_based":
        # 贡献导向者相对坚持
        adjustment_factor *= 1.05
    elif value_type == "pragmatic":
        # 务实主义者根据反馈灵活调整
        if feedback["agreement_rate"] < 0.5:
            adjustment_factor *= 0.85
        else:
            adjustment_factor *= 1.0
    
    # 应用调整
    adjusted_proposal = {}
    for agent_id, allocation in current_proposal.items():
        adjusted_proposal[agent_id] = {}
        for resource_name, amount in allocation.items():
            adjusted_amount = amount * adjustment_factor
            adjusted_proposal[agent_id][resource_name] = adjusted_amount
    
    return adjusted_proposal

def voting_mechanism(
    proposals: Dict[int, Dict[int, Dict[str, float]]],
    agents: List[Dict[str, Any]],
    total_resources: Dict[str, float],
    survival_needs: Dict[int, Dict[str, float]]
) -> Dict[int, Dict[str, float]]:
    """投票机制
    
    当协商无法达成共识时，使用投票决定最终方案
    """
    # 计算每个提案的投票权重
    proposal_scores = {}
    
    for proposer_id, proposal in proposals.items():
        total_score = 0
        total_weight = 0
        
        for agent in agents:
            agent_id = agent["id"]
            value_type = agent["value_type"]
            
            # 根据价值观确定投票权重
            weight = get_voting_weight(value_type)
            
            # 评估提案
            score = evaluate_proposal_by_values(
                proposal, agent, total_resources, survival_needs, agents
            )
            
            total_score += score * weight
            total_weight += weight
        
        if total_weight > 0:
            proposal_scores[proposer_id] = total_score / total_weight
    
    # 选择得分最高的提案
    if proposal_scores:
        best_proposer = max(proposal_scores.keys(), key=lambda x: proposal_scores[x])
        return proposals[best_proposer]
    
    # 如果没有有效提案，使用平均分配
    return equal_distribution(total_resources, agents)

def get_voting_weight(value_type: str) -> float:
    """获取投票权重"""
    weights = {
        "egalitarian": 1.0,
        "needs_based": 1.0,
        "merit_based": 1.0,
        "altruistic": 1.0,
        "pragmatic": 1.2  # 务实主义者权重稍高，因为更善于平衡
    }
    return weights.get(value_type, 1.0)


def integerize_distribution(
    total_resources: Dict[str, float],
    agents: List[Dict[str, Any]],
    distribution_result: Dict[int, Dict[str, float]],
    survival_needs: Dict[int, Dict[str, float]] = None,
    enforce_min_survival: bool = False
) -> Dict[int, Dict[str, float]]:
    """将分配结果整数化（最大余数法 + 可选生存保底）
    
    仅对键 "grain" 进行处理，保持总量与原 total_resources["grain"] 的四舍五入一致。
    """
    if not agents or not distribution_result:
        return distribution_result
    grain_total = float(total_resources.get("grain", 0.0))
    agent_ids = [agent["id"] for agent in agents]
    real = {aid: float(distribution_result.get(aid, {}).get("grain", 0.0)) for aid in agent_ids}
    base = {}
    frac = {}
    min_need = {}
    for aid in agent_ids:
        v = real.get(aid, 0.0)
        base[aid] = math.floor(v)
        frac[aid] = v - base[aid]
        if enforce_min_survival and survival_needs:
            need = float(survival_needs.get(aid, {}).get("grain", 0.0))
            min_need[aid] = int(math.ceil(need)) if need > 0 else 0
        else:
            min_need[aid] = 0
    # apply min floor
    for aid in agent_ids:
        if base[aid] < min_need[aid]:
            base[aid] = min_need[aid]
            frac[aid] = 0.0
    # compute target
    current_sum = sum(real.values())
    target = int(round(current_sum))
    base_sum = sum(base.values())
    if base_sum < target:
        need = target - base_sum
        order = sorted(agent_ids, key=lambda a: frac[a], reverse=True)
        i = 0
        while need > 0 and i < len(order):
            aid = order[i]
            base[aid] += 1
            need -= 1
            i += 1
    elif base_sum > target:
        excess = base_sum - target
        order = sorted(agent_ids, key=lambda a: frac[a])
        i = 0
        while excess > 0 and i < len(order):
            aid = order[i]
            if base[aid] > min_need[aid]:
                base[aid] -= 1
                excess -= 1
            i += 1
    # assemble
    out = {aid: dict(distribution_result.get(aid, {})) for aid in agent_ids}
    for aid in agent_ids:
        if aid not in out:
            out[aid] = {}
        out[aid]["grain"] = float(base.get(aid, 0))
    return out


# ========================================================================================
# LLM驱动的按需分配
# ========================================================================================

def llm_driven_needs_based_distribution(
    total_resources: Dict[str, float],
    agents: List[Dict[str, Any]],
    survival_needs: Dict[int, Dict[str, float]],
    round_number: int = 1,
    previous_distribution: Dict[int, Dict[str, float]] = None,
    previous_evaluations: List[Dict] = None
) -> Dict[int, Dict[str, float]]:
    """
    LLM驱动的按需分配机制（简单版）
    
    流程：
    1. 各家庭通过LLM自主申报需求（包含需求量、理由、最低可接受量）
    2. 汇总所有申报
    3. 如果总需求≤总资源：满足所有申报
       如果总需求>总资源：按比例削减
    
    参数：
        total_resources: 总资源字典
        agents: 代理列表
        survival_needs: 生存需求字典
        round_number: 当前轮数
        previous_distribution: 上一轮分配结果
        previous_evaluations: 上一轮评价结果
    
    返回：
        分配结果字典
    """
    import json
    import re
    from openai import OpenAI
    
    # 设置DeepSeek客户端
    client = OpenAI(
        api_key="sk-glrOy41mVlSTRAEJqRX3GQNl1QaTGoZ1Ry2jbo9TFW8ucCnU",
        base_url="https://api.probex.top/v1"
    )
    
    if not agents or not survival_needs:
        return {}
    
    distribution_result = {}
    
    # 计算社区总体情况
    total_members = sum(agent.get("members", 0) for agent in agents)
    total_labor = sum(agent.get("labor_force", 0) for agent in agents)
    
    print("\n" + "="*60)
    print("🆕 按需分配（LLM驱动 - 简单版）")
    print("="*60)
    
    for resource_name, total_amount in total_resources.items():
        print(f"\n资源类型: {resource_name}")
        print(f"  总资源: {total_amount:.1f}单位")
        print(f"  社区总人口: {total_members}人")
        print(f"  社区总劳力: {total_labor}人")
        
        # 阶段1：收集各家庭的需求申报
        print(f"\n{'─'*60}")
        print("📋 阶段1：收集需求申报")
        print(f"{'─'*60}")
        
        family_reports = {}
        
        for agent in agents:
            agent_id = agent["id"]
            family_name = agent.get("family_name", f"家庭{agent_id}")
            members = agent.get("members", 0)
            labor_force = agent.get("labor_force", 0)
            value_type = agent.get("value_type", "pragmatic")
            
            # 获取生存需求
            agent_survival_needs = survival_needs.get(agent_id, {})
            survival_amount = agent_survival_needs.get(resource_name, 0)
            
            # 获取上一轮情况
            prev_allocation = None
            prev_per_capita = None
            prev_satisfaction = None
            
            if previous_distribution and agent_id in previous_distribution:
                prev_allocation = previous_distribution[agent_id].get(resource_name, 0)
                prev_per_capita = prev_allocation / members if members > 0 else 0
            
            if previous_evaluations:
                for eval_item in previous_evaluations:
                    if eval_item.get("agent_id") == agent_id:
                        prev_satisfaction = eval_item.get("fairness_score")
                        break
            
            # 通过LLM获取需求申报
            report = get_family_need_report_via_llm(
                family_name=family_name,
                members=members,
                labor_force=labor_force,
                value_type=value_type,
                survival_amount=survival_amount,
                total_resources=total_amount,
                total_members=total_members,
                round_number=round_number,
                prev_allocation=prev_allocation,
                prev_per_capita=prev_per_capita,
                prev_satisfaction=prev_satisfaction
            )
            
            family_reports[agent_id] = report
            
            print(f"\n{family_name}家庭（{members}人{labor_force}劳力，{get_value_type_name(value_type)}）：")
            print(f"  💬 申报需求: {report['requested_amount']:.1f}单位")
            print(f"  📝 需求理由: {report['reason']}")
            print(f"  ⚖️ 最低可接受: {report['minimum_acceptable']:.1f}单位")
            if report.get('reasoning_process'):
                print(f"  🤔 决策过程: {report['reasoning_process']}")
        
        # 阶段2：汇总需求并分配
        print(f"\n{'─'*60}")
        print("📊 阶段2：汇总需求并决定分配")
        print(f"{'─'*60}")
        
        total_requested = sum(r['requested_amount'] for r in family_reports.values())
        total_minimum = sum(r['minimum_acceptable'] for r in family_reports.values())
        
        print(f"\n总申报需求: {total_requested:.1f}单位")
        print(f"总最低需求: {total_minimum:.1f}单位")
        print(f"实际可用: {total_amount:.1f}单位")
        
        if total_requested <= total_amount:
            # 资源充足，满足所有申报
            print(f"\n✅ 资源充足（需求/资源 = {total_requested/total_amount:.1%}）")
            print(f"   满足所有家庭的申报需求")
            
            for agent_id, report in family_reports.items():
                if agent_id not in distribution_result:
                    distribution_result[agent_id] = {}
                distribution_result[agent_id][resource_name] = report['requested_amount']
        
        elif total_minimum <= total_amount < total_requested:
            # 资源介于最低需求和申报需求之间
            gap = total_requested - total_amount
            gap_ratio = gap / total_requested
            
            print(f"\n⚠️ 资源略紧张（缺口 {gap:.1f}单位，{gap_ratio:.1%}）")
            print(f"   在[最低值-申报值]范围内按比例分配")
            
            # 按比例在[最低值, 申报值]区间内分配
            for agent_id, report in family_reports.items():
                min_val = report['minimum_acceptable']
                max_val = report['requested_amount']
                range_size = max_val - min_val
                
                # 计算该家庭在区间内的占比
                total_range = sum(r['requested_amount'] - r['minimum_acceptable'] 
                                 for r in family_reports.values())
                
                if total_range > 0:
                    # 按区间大小比例分配剩余资源
                    remaining = total_amount - total_minimum
                    allocation = min_val + (range_size / total_range) * remaining
                else:
                    # 如果所有家庭最低值=申报值，按比例分配
                    proportion = max_val / total_requested
                    allocation = proportion * total_amount
                
                if agent_id not in distribution_result:
                    distribution_result[agent_id] = {}
                distribution_result[agent_id][resource_name] = allocation
        
        else:
            # 资源严重不足，连最低需求都无法满足
            gap = total_requested - total_amount
            gap_ratio = gap / total_requested
            min_gap = total_minimum - total_amount
            
            print(f"\n🚨 资源严重不足（缺口 {gap:.1f}单位，{gap_ratio:.1%}）")
            print(f"   连最低需求都无法满足（最低需求缺口 {min_gap:.1f}）")
            print(f"   按申报比例削减")
            
            # 按申报比例削减
            for agent_id, report in family_reports.items():
                proportion = report['requested_amount'] / total_requested
                allocation = proportion * total_amount
                
                if agent_id not in distribution_result:
                    distribution_result[agent_id] = {}
                distribution_result[agent_id][resource_name] = allocation
        
        # 显示最终分配结果
        print(f"\n{'─'*60}")
        print("✅ 最终分配结果")
        print(f"{'─'*60}")
        
        for agent in agents:
            agent_id = agent["id"]
            family_name = agent.get("family_name", f"家庭{agent_id}")
            members = agent.get("members", 0)
            
            allocated = distribution_result[agent_id][resource_name]
            requested = family_reports[agent_id]['requested_amount']
            per_capita = allocated / members if members > 0 else 0
            fulfillment = allocated / requested if requested > 0 else 0
            
            print(f"\n{family_name}家庭（{members}人）：")
            print(f"  申报: {requested:.1f} → 实际分配: {allocated:.1f} （满足度: {fulfillment:.1%}）")
            print(f"  人均: {per_capita:.2f}单位/人")
    
    print("\n" + "="*60)
    print("✅ LLM驱动的按需分配完成")
    print("="*60 + "\n")
    
    # 整数化
    return integerize_distribution(
        total_resources, agents, distribution_result,
        survival_needs=survival_needs,
        enforce_min_survival=True
    )


def get_family_need_report_via_llm(
    family_name: str,
    members: int,
    labor_force: int,
    value_type: str,
    survival_amount: float,
    total_resources: float,
    total_members: int,
    round_number: int = 1,
    prev_allocation: float = None,
    prev_per_capita: float = None,
    prev_satisfaction: float = None
) -> Dict[str, Any]:
    """
    通过LLM获取家庭的需求申报
    
    返回：
    {
        "requested_amount": float,
        "reason": str,
        "minimum_acceptable": float,
        "reasoning_process": str
    }
    """
    from openai import OpenAI
    import json
    import re
    
    # 设置DeepSeek客户端
    client = OpenAI(
        api_key="",
        base_url=""
    )
    
    # 获取价值观描述
    value_desc = get_value_type_description(value_type)
    
    # 构建Prompt
    prompt = f"""你是{family_name}家庭的代表，需要向社区申报本轮的资源需求。

【家庭基本情况】
- 家庭成员：{members}人
- 劳动力：{labor_force}人
- 劳力密度：{labor_force/members:.1%}（每人平均劳动力）
- 价值取向：{value_desc}

【生存需求】
- 基本口粮：{survival_amount:.1f}单位（维持{members}人基本生活的最低需求）

【社区资源情况】
- 本轮可分配资源：{total_resources:.1f}单位
- 社区总人口：{total_members}人
- 你家人口占比：{members/total_members:.1%}
- 如果平均分配，你家可得：{total_resources * members / total_members:.1f}单位（人均{total_resources/total_members:.2f}）
"""

    # 添加历史情况（如果有）
    if prev_allocation is not None:
        prompt += f"""
【上一轮情况】
- 上轮分配：{prev_allocation:.1f}单位
- 上轮人均：{prev_per_capita:.2f}单位/人
"""
        if prev_satisfaction is not None:
            prompt += f"- 你的满意度评价：{prev_satisfaction:.1f}分（1-5分）\n"

    prompt += f"""
【分配原则】
本轮采用"按需分配"机制：
- 各家庭自主申报需求
- 如果总需求 ≤ 总资源，满足所有申报
- 如果总需求 > 总资源，按比例削减

【申报要求】
请基于你的家庭情况和价值观，申报本轮需求。考虑因素：
1. 家庭人口的基本生活需求
2. 劳动力的生产能力需求
3. 你的价值取向（{value_desc}）
4. 社区资源的充裕程度
5. 上一轮的分配和满意度（如果有）

【注意事项】
- 申报需求应该真实反映你的需要，不要虚报
- 最低可接受量不能低于生存需求的80%
- 申报量应该在合理范围内（不超过平均水平的3倍）

请以JSON格式回复（只返回JSON，不要其他文字）：
{{
    "requested_amount": 数字（你希望获得的资源量），
    "reason": "需求理由（2-3句话，说明为什么需要这么多）",
    "minimum_acceptable": 数字（如果资源紧张，最低可接受的量），
    "reasoning_process": "决策过程（简要说明你如何做出这个决定）"
}}
"""

    # 调用LLM
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # 调用DeepSeek API
            completion = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            response = completion.choices[0].message.content
            
            # 解析JSON
            report = parse_json_from_response(response)
            
            # 验证和修正
            report = validate_and_fix_report(
                report, members, labor_force, survival_amount, 
                total_resources, total_members
            )
            
            return report
            
        except Exception as e:
            print(f"  ⚠️ LLM调用失败（第{attempt+1}/{max_retries}次）: {e}")
            if attempt == max_retries - 1:
                # 最后一次失败，使用默认值
                print(f"  使用默认申报策略")
                return get_default_need_report(
                    members, labor_force, value_type, 
                    survival_amount, total_resources, total_members
                )


def parse_json_from_response(response: str) -> Dict[str, Any]:
    """从LLM响应中解析JSON"""
    import json
    import re
    
    # 尝试直接解析
    try:
        return json.loads(response)
    except:
        pass
    
    # 尝试提取JSON代码块
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except:
            pass
    
    # 尝试提取大括号内容
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except:
            pass
    
    raise ValueError(f"无法从响应中解析JSON: {response[:200]}")


def validate_and_fix_report(
    report: Dict[str, Any],
    members: int,
    labor_force: int,
    survival_amount: float,
    total_resources: float,
    total_members: int
) -> Dict[str, Any]:
    """验证并修正需求申报"""
    
    # 提取数值
    requested = float(report.get('requested_amount', 0))
    minimum = float(report.get('minimum_acceptable', 0))
    reason = str(report.get('reason', ''))
    reasoning = str(report.get('reasoning_process', ''))
    
    # 计算合理范围
    avg_per_family = total_resources / (total_members / (members if members > 0 else 1))
    min_survival = survival_amount * 0.8
    max_reasonable = avg_per_family * 3
    
    # 修正申报量
    if requested <= 0 or requested > max_reasonable:
        requested = min(members * (total_resources / total_members), max_reasonable)
    
    # 修正最低值
    if minimum < min_survival:
        minimum = min_survival
    if minimum > requested:
        minimum = requested
    
    return {
        'requested_amount': requested,
        'reason': reason if reason else f"{members}人家庭的基本需求",
        'minimum_acceptable': minimum,
        'reasoning_process': reasoning
    }


def get_default_need_report(
    members: int,
    labor_force: int,
    value_type: str,
    survival_amount: float,
    total_resources: float,
    total_members: int
) -> Dict[str, Any]:
    """
    当LLM调用失败时，使用默认策略生成需求申报
    """
    
    # 基础需求：按人口比例
    base_request = total_resources * (members / total_members)
    
    # 根据价值观调整
    if value_type == "egalitarian":
        # 平等主义：接近人均
        requested = base_request
        minimum = survival_amount
        reason = f"希望获得公平的人均份额（{members}人）"
        
    elif value_type == "needs_based":
        # 需求主义：按人口需求
        requested = max(base_request, survival_amount * 1.3)
        minimum = survival_amount
        reason = f"有{members}人需要养活，希望保障基本生活"
        
    elif value_type == "merit_based":
        # 贡献主义：按劳力贡献
        labor_ratio = labor_force / (total_members / len([1]))  # 简化计算
        requested = base_request * (1 + labor_ratio * 0.3)
        minimum = survival_amount * 1.1
        reason = f"有{labor_force}个劳动力，希望按贡献获得资源"
        
    elif value_type == "altruistic":
        # 利他主义：适度申报
        requested = base_request * 0.85
        minimum = survival_amount * 0.9
        reason = f"愿意为社区其他家庭让出一部分资源"
        
    else:  # pragmatic
        # 务实主义：根据资源情况灵活申报
        resource_abundance = total_resources / (total_members * 4)  # 假设人均4为标准
        if resource_abundance > 1.2:
            requested = base_request * 1.1
        elif resource_abundance < 0.8:
            requested = base_request * 0.9
        else:
            requested = base_request
        minimum = survival_amount
        reason = f"根据资源情况灵活申报"
    
    return {
        'requested_amount': requested,
        'reason': reason,
        'minimum_acceptable': minimum,
        'reasoning_process': f"基于{get_value_type_name(value_type)}价值观的默认策略"
    }


def get_value_type_description(value_type: str) -> str:
    """获取价值观的详细描述"""
    descriptions = {
        "egalitarian": "平等主义 - 认为人人平等，应该公平分配，反对特权和过度不平等",
        "needs_based": "需求主义 - 认为应该按照实际需求分配，照顾人口多、负担重的家庭",
        "merit_based": "贡献主义 - 认为应该多劳多得，按劳动贡献分配资源",
        "altruistic": "利他主义 - 愿意为他人考虑，主动照顾弱势家庭",
        "pragmatic": "务实主义 - 灵活务实，根据实际情况调整策略"
    }
    return descriptions.get(value_type, "务实主义")


def get_value_type_name(value_type: str) -> str:
    """获取价值观名称"""
    names = {
        "egalitarian": "平等主义",
        "needs_based": "需求主义",
        "merit_based": "贡献主义",
        "altruistic": "利他主义",
        "pragmatic": "务实主义"
    }
    return names.get(value_type, "务实主义")