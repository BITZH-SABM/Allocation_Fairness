"""
评估系统模块 - 计算资源分配的统计指标和收集代理主观评价
"""
from typing import List, Dict, Any, Tuple
import time
import random
import numpy as np
import math
from openai import OpenAI
import json
from llm_interaction_logger import get_logger

# 设置DeepSeek客户端
client = OpenAI(
    api_key="",  # 替换为你的DeepSeek API密钥
    base_url=""  # 标准根路径，避免 /chat/completions 重复
)

def calculate_statistics(distribution_result: Dict[int, Dict[str, float]], agents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """计算资源分配的统计指标
    
    参数:
        distribution_result: 分配结果字典，键为代理ID，值为分配到的资源字典
        agents: 代理列表
        
    返回:
        统计指标字典，包含方差、标准差、基尼系数等
    """
    # 为每种资源分别计算统计指标
    stats = {}
    all_resources = set()
    
    # 收集所有资源类型
    for agent_id, resources in distribution_result.items():
        all_resources.update(resources.keys())
    
    # 对每种资源计算统计指标
    for resource_name in all_resources:
        # 提取该资源的分配结果
        resource_distribution = [
            distribution_result.get(agent["id"], {}).get(resource_name, 0)
            for agent in agents
        ]
        
        # 计算基本统计量
        mean_value = np.mean(resource_distribution)
        variance = np.var(resource_distribution)
        std_dev = np.std(resource_distribution)
        
        # 计算基尼系数
        gini = calculate_gini_coefficient(resource_distribution)
        
        # 存储该资源的统计结果
        stats[resource_name] = {
            "mean": mean_value,
            "variance": variance,
            "std_dev": std_dev,
            "gini": gini
        }
    
    # 计算总资源的统计指标
    total_resources = [
        sum(distribution_result.get(agent["id"], {}).values())
        for agent in agents
    ]
    
    # 总资源的基本统计量
    stats["total"] = {
        "mean": np.mean(total_resources),
        "variance": np.var(total_resources),
        "std_dev": np.std(total_resources),
        "gini": calculate_gini_coefficient(total_resources)
    }
    
    return stats

def _compute_statistics_for_values(values: Dict[int, Dict[str, float]], agents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """通用统计：对任意 agent→资源→数值 的映射计算均值/方差/标准差/基尼（含 total）。"""
    stats = {}
    all_resources = set()
    for agent_id, res in values.items():
        all_resources.update(res.keys())
    for resource_name in all_resources:
        arr = [values.get(agent["id"], {}).get(resource_name, 0.0) for agent in agents]
        mean_value = np.mean(arr)
        variance = np.var(arr)
        std_dev = np.std(arr)
        gini = calculate_gini_coefficient(arr)
        stats[resource_name] = {
            "mean": mean_value,
            "variance": variance,
            "std_dev": std_dev,
            "gini": gini
        }
    total_values = [sum(values.get(agent["id"], {}).values()) for agent in agents]
    stats["total"] = {
        "mean": np.mean(total_values),
        "variance": np.var(total_values),
        "std_dev": np.std(total_values),
        "gini": calculate_gini_coefficient(total_values)
    }
    return stats

def calculate_gini_coefficient(distribution: List[float]) -> float:
    """计算基尼系数
    
    参数:
        distribution: 资源分配列表
        
    返回:
        基尼系数，0表示完全平等，1表示完全不平等
    """
    if not distribution or sum(distribution) == 0:
        return 0
    
    # 排序分配结果
    sorted_dist = sorted(distribution)
    n = len(sorted_dist)
    
    # 计算基尼系数
    numerator = sum((i+1) * sorted_dist[i] for i in range(n))
    denominator = sum(sorted_dist) * n
    
    if denominator == 0:
        return 0
    
    return (2 * numerator / denominator) - (n + 1) / n

def get_agent_fairness_evaluation(
    agent: Dict[str, Any],
    distribution_result: Dict[int, Dict[str, float]],
    total_resources: Dict[str, float],
    round_number: int,
    distribution_method: str,
    agents: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """获取代理对分配结果的公平性评价
    
    参数:
        agent: 代理数据
        distribution_result: 分配结果
        total_resources: 总资源
        round_number: 当前轮数
        distribution_method: 分配方法名称
        agents: 所有代理列表，用于提供其他家庭信息
        
    返回:
        代理评价结果字典
    """
    agent_id = agent["id"]
    agent_resources = distribution_result.get(agent_id, {})
    agent_value = agent["value_type"]
    
    # 计算系统级统计数据
    system_stats = {}
    total_members = sum(a["members"] for a in agents) if agents else 0
    total_labor = sum(a["labor_force"] for a in agents) if agents else 0
    
    # 计算家庭的资源总量
    agent_total_resources = sum(agent_resources.values())
    
    # 计算系统总资源和人均/劳动力均资源
    system_total_resources = sum(total_resources.values())
    per_capita_system = system_total_resources / total_members if total_members > 0 else 0
    per_labor_system = system_total_resources / total_labor if total_labor > 0 else 0
    
    # 计算该家庭的人均和每劳动力资源
    agent_per_capita = agent_total_resources / agent["members"] if agent["members"] > 0 else 0
    agent_per_labor = agent_total_resources / agent["labor_force"] if agent["labor_force"] > 0 else 0
    
    # 计算该家庭获得的资源占总资源的百分比
    resource_percentage = (agent_total_resources / system_total_resources * 100) if system_total_resources > 0 else 0
    
    # 计算该家庭的成员占比和劳动力占比
    member_percentage = (agent["members"] / total_members * 100) if total_members > 0 else 0
    labor_percentage = (agent["labor_force"] / total_labor * 100) if total_labor > 0 else 0
    
    # 准备其他家庭分配情况信息，添加更多比较数据
    other_families_info = ""
    family_comparative_data = []
    
    if agents:
        other_families_info = "其他家庭分配情况:\n"
        
        # 收集所有家庭数据用于比较
        for other_agent in agents:
            other_id = other_agent["id"]
            other_resources = distribution_result.get(other_id, {})
            other_total_received = sum(other_resources.values())
            
            # 计算人均和每劳动力资源
            other_per_capita = other_total_received / other_agent["members"] if other_agent["members"] > 0 else 0
            other_per_labor = other_total_received / other_agent["labor_force"] if other_agent["labor_force"] > 0 else 0
            
            # 将数据保存到列表
            family_data = {
                "id": other_id,
                "name": other_agent["family_name"],
                "is_self": other_id == agent_id,
                "members": other_agent["members"],
                "labor": other_agent["labor_force"],
                "total_resources": other_total_received,
                "per_capita": other_per_capita,
                "per_labor": other_per_labor,
                "value_type": other_agent["value_type"]
            }
            family_comparative_data.append(family_data)
            
            # 只为其他家庭生成文本描述
            if other_id != agent_id:
                other_families_info += f"- {other_agent['family_name']}家庭(ID:{other_id}):\n"
                other_families_info += f"  成员: {other_agent['members']}人, 劳动力: {other_agent['labor_force']}人\n"
                other_families_info += f"  分得资源总量: {other_total_received:.2f}\n"
                other_families_info += f"  人均资源: {other_per_capita:.2f}, 每劳动力资源: {other_per_labor:.2f}\n"
                
                for resource_name, amount in other_resources.items():
                    other_families_info += f"  {resource_name}: {amount:.2f}\n"
                other_families_info += "\n"
    
    # 计算家庭在不同指标上的排名
    rankings = {}
    if family_comparative_data:
        # 按总资源排序
        sorted_by_total = sorted(family_comparative_data, key=lambda x: x["total_resources"], reverse=True)
        rankings["total_rank"] = next(i+1 for i, f in enumerate(sorted_by_total) if f["id"] == agent_id)
        
        # 按人均资源排序
        sorted_by_capita = sorted(family_comparative_data, key=lambda x: x["per_capita"], reverse=True)
        rankings["per_capita_rank"] = next(i+1 for i, f in enumerate(sorted_by_capita) if f["id"] == agent_id)
        
        # 按每劳动力资源排序
        sorted_by_labor = sorted(family_comparative_data, key=lambda x: x["per_labor"], reverse=True)
        rankings["per_labor_rank"] = next(i+1 for i, f in enumerate(sorted_by_labor) if f["id"] == agent_id)
    
    # 构造提示词（回退至原始版本）
    prompt = f"""你是ID为{agent_id}的{agent["family_name"]}家庭，一个持{agent["value_type"]}价值观的家庭代理。

家庭信息:
- 家庭成员: {agent["members"]}人 (占社区总人口的{member_percentage:.1f}%)
- 劳动力: {agent["labor_force"]}人 (占社区总劳动力的{labor_percentage:.1f}%)
- 核心价值观: {agent["value_type"]}({agent["core_beliefs"][0]})

本轮(第{round_number}轮)使用的资源分配方式是: {distribution_method}

社区总体情况:
- 总资源: {system_total_resources:.2f}
- 总人口: {total_members}人
- 总劳动力: {total_labor}人
- 社区人均资源: {per_capita_system:.2f}
- 社区每劳动力资源: {per_labor_system:.2f}

你家分得的资源:
- 总资源: {agent_total_resources:.2f} (占社区总资源的{resource_percentage:.1f}%)
- 人均资源: {agent_per_capita:.2f} (社区排名，资源越多，排名越靠前: {rankings.get("per_capita_rank", "N/A")}/{len(agents) if agents else 0})
- 每劳动力资源: {agent_per_labor:.2f} (社区排名，资源越多，排名越靠前: {rankings.get("per_labor_rank", "N/A")}/{len(agents) if agents else 0})
- 详细资源: {json.dumps(agent_resources, ensure_ascii=False)}

{other_families_info}

请根据你的{agent["value_type"]}立场，结合社区整体资源状况、你的家庭情况和其他家庭分配情况，回答以下问题：
1. 你觉得这轮分配是否公平，并简要说明你觉得公平或不公平的理由，考虑以下几个维度：：
   - 你获得的资源是否与你的家庭需求相匹配？
   - 与其他家庭相比，你是否获得了合理的份额？
   - 社区整体资源分配是否符合你的价值观？
2. 基于上述你给的理由，请给出一个1-5的公平满意度打分，要求只输出一个score=XXX（整数，1为最不满意，5为最满意）。
3. 根据你的价值观，你心中理想的分配标准是什么？

要求：回答简洁、具体，体现出你的立场与家庭状况，并考虑与其他家庭的对比。
"""
    
    # 带重试的API调用，避免临时 5xx/超时导致整轮中断
    max_retries = 3
    backoff_base = 2.0
    last_err = None
    model_name = "deepseek-v3"
    temperature = 0.9
    
    for attempt in range(max_retries):
        try:
            start_time = time.time()
            response = client.chat.completions.create(
                model=model_name,  # DeepSeek模型名称
                messages=[
                    {"role": "system", "content": "你是一个角色扮演专家，请根据提供的家庭信息和价值观，以对应家庭的口吻回答问题。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=500
            )
            duration = time.time() - start_time
            evaluation_text = response.choices[0].message.content
            fairness_score = extract_fairness_score(evaluation_text)
            
            # 记录LLM交互
            logger = get_logger()
            if logger:
                logger.log_evaluation_call(
                    round_number=round_number,
                    agent=agent,
                    distribution_method=distribution_method,
                    allocated_resources=sum(agent_resources.values()),
                    input_prompt=prompt,
                    raw_output=evaluation_text,
                    extracted_score=fairness_score,
                    model=model_name,
                    temperature=temperature,
                    duration=duration,
                    success=True,
                    processed_data={
                        "fairness_score": fairness_score,
                        "rankings": rankings
                    }
                )
            
            return {
                "agent_id": agent_id,
                "family_name": agent["family_name"],
                "value_type": agent["value_type"],
                "fairness_score": fairness_score,
                "evaluation": evaluation_text
            }
        except Exception as e:
            last_err = e
            wait_s = backoff_base ** attempt + random.uniform(0, 0.5)
            print(f"获取代理{agent_id}评价时出错(第{attempt+1}/{max_retries}次): {str(e)}，{wait_s:.1f}s后重试...")
            if attempt < max_retries - 1:
                time.sleep(wait_s)
            else:
                break
    
    # 最终失败时的降级返回（不阻断仿真）
    # 记录失败的LLM调用
    logger = get_logger()
    if logger:
        logger.log_evaluation_call(
            round_number=round_number,
            agent=agent,
            distribution_method=distribution_method,
            allocated_resources=sum(agent_resources.values()),
            input_prompt=prompt,
            raw_output=f"评价获取失败: {str(last_err)}",
            extracted_score=None,
            model=model_name,
            temperature=temperature,
            duration=0.0,
            success=False
        )
    
    return {
        "agent_id": agent_id,
        "family_name": agent["family_name"],
        "value_type": agent["value_type"],
        "fairness_score": None,
        "evaluation": f"评价获取失败: {str(last_err)}"
    }

def noop():
    return None

def extract_fairness_score(evaluation_text: str) -> float:
    """从评价文本中提取公平满意度分数
    
    参数:
        evaluation_text: 评价文本
        
    返回:
        公平满意度分数（严格匹配score=X格式），若失败兜底为3.0
    """
    try:
        import re
        text = evaluation_text or ""

        # 规范化：全角数字、中文数字到半角阿拉伯；去除围绕的反引号
        def _normalize_digits(s: str) -> str:
            trans = str.maketrans({
                '０':'0','１':'1','２':'2','３':'3','４':'4','５':'5','６':'6','７':'7','８':'8','９':'9'
            })
            s2 = s.translate(trans)
            s2 = (s2
                  .replace('一','1')
                  .replace('二','2')
                  .replace('三','3')
                  .replace('四','4')
                  .replace('五','5'))
            return s2.strip('`').strip()

        norm_text = _normalize_digits(text)

        # 🎯 最高优先级：严格匹配 score=X 格式（独立行或行内）
        # 支持 score=1, score:2, score：3 等格式，大小写不敏感
        score_patterns = [
            # 独立行：只有score=X
            r"(?im)^\s*score\s*[:=：]\s*([1-5])\s*$",
            # 行内：前后可有其他文字，但score=X要清晰分隔
            r"(?i)\bscore\s*[:=：]\s*([1-5])\b",
            # 兼容中文：评分=X, 打分=X
            r"(?i)(?:评分|打分)\s*[:=：]\s*([1-5])\b"
        ]
        
        for pattern in score_patterns:
            m = re.search(pattern, norm_text)
            if m:
                score = float(m.group(1))
                print(f"[DEBUG] 成功提取score: {score} (模式: {pattern})")
                return score

        # 🎯 次级优先级：查找第2条中的评分（针对你的prompt结构）
        lines = [ln.strip() for ln in norm_text.splitlines() if ln.strip()]
        for i, line in enumerate(lines):
            # 匹配 "2." 开头的行
            if re.match(r"^\s*2\s*[.、:：]\s*", line):
                # 在这一行中查找1-5的数字
                m = re.search(r"([1-5])(?!\d)", line)
                if m:
                    score = float(m.group(1))
                    print(f"[DEBUG] 从第2条提取score: {score}")
                    return score
                # 如果第2条行没有数字，检查下一行是否是score=X
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    m_next = re.search(r"(?i)\bscore\s*[:=：]\s*([1-5])\b", next_line)
                    if m_next:
                        score = float(m_next.group(1))
                        print(f"[DEBUG] 从第2条后一行提取score: {score}")
                        return score
                break

        # 🎯 兜底1：全文中独立的1-5数字（单独成行）
        m_standalone = re.search(r"(?m)^\s*([1-5])\s*$", norm_text)
        if m_standalone:
            score = float(m_standalone.group(1))
            print(f"[DEBUG] 兜底提取独立数字: {score}")
            return score

        # 🎯 兜底2：关键词邻近的分数
        fallback_patterns = [
            r"(?:公平满意度|满意度)[：:，,\s]*([1-5])(?!\d)",
            r"(?:评分|打分|分数)[：:，,\s]*([1-5])(?!\d)",
            r"给\s*([1-5])\s*分",
            r"([1-5])\s*/\s*5"
        ]
        
        for pattern in fallback_patterns:
            m = re.search(pattern, norm_text)
            if m:
                score = float(m.group(1))
                print(f"[DEBUG] 兜底关键词提取score: {score}")
                return score

        # 最终兜底：返回中位3.0
        print(f"[DEBUG] 未找到有效评分，返回默认值3.0")
        print(f"[DEBUG] 原文前200字符: {norm_text[:200]}...")
        return 3.0
        
    except Exception as e:
        print(f"[DEBUG] 评分提取异常: {e}")
        return 3.0

def evaluate_distribution(
    distribution_result: Dict[int, Dict[str, float]],
    agents: List[Dict[str, Any]],
    total_resources: Dict[str, float],
    round_number: int,
    distribution_method: str,
    survival_needs_map: Dict[int, Dict[str, float]] = None,
    productions_map: Dict[int, Dict[str, float]] = None
) -> Dict[str, Any]:
    """评估分配结果，包括统计指标和代理主观评价
    
    参数:
        distribution_result: 分配结果字典
        agents: 代理列表
        total_resources: 总资源字典
        round_number: 当前轮数
        distribution_method: 分配方法
        
    返回:
        评估结果字典
    """
    # 计算统计指标（分层）
    # 1) Allocation 层：直接分配结果
    allocation_stats = calculate_statistics(distribution_result, agents)
    # 2) Effective input 层：max(0, allocation - need)
    effective_input: Dict[int, Dict[str, float]] = {}
    if survival_needs_map:
        for agent in agents:
            aid = agent["id"]
            alloc = distribution_result.get(aid, {})
            need = survival_needs_map.get(aid, {})
            effective_input[aid] = {}
            for resource in set(list(alloc.keys()) + list(need.keys())):
                a = alloc.get(resource, 0.0)
                n = need.get(resource, 0.0)
                effective_input[aid][resource] = max(0.0, a - n)
    else:
        effective_input = {aid: dict(distribution_result.get(aid, {})) for aid in [a["id"] for a in agents]}
    effective_stats = _compute_statistics_for_values(effective_input, agents)
    # 3) Outcome 层：实际产出
    outcome_stats = None
    if productions_map:
        outcome_stats = _compute_statistics_for_values(productions_map, agents)
    
    # 兼容原字段：statistics 默认为 allocation 层
    statistics = allocation_stats
    
    # 获取每个代理的评价
    agent_evaluations = []
    for agent in agents:
        evaluation = get_agent_fairness_evaluation(
            agent, 
            distribution_result, 
            total_resources, 
            round_number, 
            distribution_method,
            agents  # 传递所有代理信息
        )
        agent_evaluations.append(evaluation)
    
    # 计算平均满意度
    valid_scores = [eval["fairness_score"] for eval in agent_evaluations if eval["fairness_score"] is not None]
    avg_satisfaction = sum(valid_scores) / len(valid_scores) if valid_scores else None
    
    # 组合评估结果
    evaluation_result = {
        "round": round_number,
        "distribution_method": distribution_method,
        "statistics": statistics,
        "layered_statistics": {
            "allocation": allocation_stats,
            "effective_input": effective_stats,
            "outcome": outcome_stats
        },
        "agent_evaluations": agent_evaluations,
        "average_satisfaction": avg_satisfaction
    }
    
    return evaluation_result

def print_distribution_summary(
    distribution_result: Dict[int, Dict[str, float]],
    agents: List[Dict[str, Any]],
    statistics: Dict[str, Any],
    layered_statistics: Dict[str, Any] = None
) -> None:
    """打印分配结果摘要
    
    参数:
        distribution_result: 分配结果字典
        agents: 代理列表
        statistics: 统计指标字典
    """
    print("\n" + "="*50)
    print("资源分配结果摘要")
    print("="*50)
    
    # 打印每个家庭的分配结果
    print("\n各家庭资源分配情况:")
    for agent in agents:
        agent_id = agent["id"]
        family_name = agent["family_name"]
        resources = distribution_result.get(agent_id, {})
        
        total_received = sum(resources.values())
        
        print(f"{family_name}家庭(ID:{agent_id}):")
        for resource_name, amount in resources.items():
            print(f"  - {resource_name}: {amount:.2f}")
        print(f"  总计: {total_received:.2f}")
        print("-"*30)
    
    # 打印统计指标（Allocation 默认层）
    print("\n分配统计指标:")
    print("总资源分配:")
    total_stats = statistics.get("total", {})
    print(f"  - 平均值: {total_stats.get('mean', 0):.2f}")
    print(f"  - 方差: {total_stats.get('variance', 0):.2f}")
    print(f"  - 标准差: {total_stats.get('std_dev', 0):.2f}")
    print(f"  - 基尼系数: {total_stats.get('gini', 0):.4f}")
    
    # 打印各资源类型的统计指标
    for resource_name, stats in statistics.items():
        if resource_name != "total":
            print(f"\n{resource_name}资源分配:")
            print(f"  - 平均值: {stats.get('mean', 0):.2f}")
            print(f"  - 方差: {stats.get('variance', 0):.2f}")
            print(f"  - 标准差: {stats.get('std_dev', 0):.2f}")
            print(f"  - 基尼系数: {stats.get('gini', 0):.4f}")
    
    # 可选：打印分层统计
    if layered_statistics:
        def _p(layer_key: str, title: str):
            layer = layered_statistics.get(layer_key)
            if not layer:
                return
            print("\n" + title + ":")
            t = layer.get("total", {})
            print(f"  - 平均值: {t.get('mean', 0):.2f}")
            print(f"  - 方差: {t.get('variance', 0):.2f}")
            print(f"  - 标准差: {t.get('std_dev', 0):.2f}")
            print(f"  - 基尼系数: {t.get('gini', 0):.4f}")
        _p("effective_input", "有效投入统计（allocation-need，生存后用于生产的资源）")
        _p("outcome", "结果统计（产出）")
    
    print("="*50) 