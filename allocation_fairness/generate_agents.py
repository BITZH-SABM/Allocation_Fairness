import os
import json
import time
import random
from openai import OpenAI
from typing import List, Dict, Any

# 设置DeepSeek客户端
client = OpenAI(
    api_key="",  # 替换为你的DeepSeek API密钥
    base_url=""  # 标准根路径，避免 /chat/completions 重复
)

# 定义价值类型
VALUE_TYPES = {
    "egalitarian": "平等主义",
    "needs_based": "需求导向", 
    "merit_based": "贡献导向",
    "altruistic": "利他主义",
    "pragmatic": "务实主义"
}

# 预定义常见姓氏列表，确保每个代理有不同姓氏
COMMON_SURNAMES = [
    "李", "王", "张", "刘", "陈", "杨", "黄", "赵", "吴", "周", 
    "徐", "孙", "马", "朱", "胡", "林", "郭", "何", "高", "罗",
    "郑", "梁", "谢", "宋", "唐", "许", "韩", "冯", "邓", "曹",
    "彭", "曾", "萧", "田", "董", "潘", "袁", "于", "蒋", "蔡"
]

# 价值类型描述字典
VALUE_DESCRIPTIONS = {
    "egalitarian": "平等主义的核心是相信所有人都应该得到平等的对待和资源分配，无论其贡献或需求差异如何。平等主义者强调结果平等而非机会平等，对不平等现象非常敏感。",
    
    "needs_based": "需求导向价值观认为资源应根据个人实际需求进行分配。这种价值体系将满足基本需求作为首要任务，特别关注弱势群体，相信每个人都有权获得生存和尊严所需的基本资源。",
    
    "merit_based": "贡献导向价值观认为资源分配应反映个人贡献。这种价值体系强调多劳多得原则，重视激励机制和效率，相信奖励应与努力成正比，以促进生产力和价值创造。",
    
    "altruistic": "利他主义价值观体现在愿意牺牲个人利益去帮助他人，特别是处于困境中的人。这种价值体系高度重视社区整体福祉和和谐，强调互助和团结，将集体利益置于个人利益之上。",
    
    "pragmatic": "务实主义价值观寻求考虑多种因素的平衡折中解决方案，关注长期系统可持续性。这种价值体系根据情境灵活调整立场，既关心公平又关心效率，尝试找到最优的实际解决方案。"
}

def create_agent_prompt(value_type: str, agent_id: int, suggested_surname: str = "") -> str:
    """创建生成代理的提示词
    
    参数:
        value_type: 价值类型
        agent_id: 代理ID
        suggested_surname: 建议的姓氏
        
    返回:
        提示词文本
    """
    
    chinese_value_type = VALUE_TYPES[value_type]
    description = VALUE_DESCRIPTIONS[value_type]
    
    surname_suggestion = f"请使用'{suggested_surname}'作为家庭姓氏" if suggested_surname else ""
    
    prompt = f"""请基于{chinese_value_type}的价值观，创建一个社区农庄中的家庭代理。这个家庭应该有鲜明的特征和背景故事。

{description}

{surname_suggestion}

请提供以下信息，并以严格的JSON格式返回：

```json
{{
  "id": {agent_id},
  "family_name": "家庭姓氏",
  "value_type": "{value_type}",
  "members": 家庭成员总数(2-8之间的整数),
  "labor_force": 劳动力人数(不能超过总成员数),
  "background": "家庭简短背景故事(100-150字)",
  
  "core_beliefs": [
    "核心信念1",
    "核心信念2",
    "核心信念3"
  ],
  
  "resource_stance": "对资源分配的基本立场(50-100字)",
  "ideal_distribution": "认为理想的分配方式是什么(50-100字)",
  "fairness_view": "对公平的看法和理解(50-100字)"
}}
```

请确保所有生成的内容与{chinese_value_type}的基本理念保持一致，并展现出真实可信的家庭特征。只返回JSON格式内容，不要有其他解释或前后缀。
"""
    return prompt

def call_openai_api(prompt: str, retries: int = 3) -> Dict[str, Any]:
    """调用OpenAI API生成代理信息
    
    参数:
        prompt: 提示词
        retries: 重试次数
        
    返回:
        代理数据字典
    """
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="deepseek-v3",  # DeepSeek模型名称
                messages=[
                    {"role": "system", "content": "你是一个专业的角色创建助手，擅长基于特定价值观创建详细的角色描述。你的回答将严格遵循要求的JSON格式。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            # 获取生成的内容
            content = response.choices[0].message.content
            
            # 提取JSON部分
            json_content = extract_json(content)
            
            # 解析JSON
            agent_data = json.loads(json_content)
            return agent_data
            
        except Exception as e:
            print(f"尝试 {attempt+1}/{retries} 失败: {str(e)}")
            if attempt < retries - 1:
                print("等待5秒后重试...")
                time.sleep(5)
            else:
                raise Exception(f"生成代理失败，已达到最大重试次数: {str(e)}")

def extract_json(text: str) -> str:
    """从文本中提取JSON内容
    
    参数:
        text: 包含JSON的文本
        
    返回:
        JSON字符串
    """
    # 查找JSON的开始和结束位置
    start = text.find("{")
    end = text.rfind("}")
    
    if start == -1 or end == -1:
        raise ValueError("无法在响应中找到有效的JSON")
    
    return text[start:end+1]

def validate_agent(agent_data: Dict[str, Any]) -> bool:
    """验证代理数据的完整性和一致性
    
    参数:
        agent_data: 代理数据字典
        
    返回:
        如果数据有效则为True，否则为False
    """
    required_fields = [
        "id", "family_name", "value_type", "members", "labor_force", 
        "background", "core_beliefs", "resource_stance", 
        "ideal_distribution", "fairness_view"
    ]
    
    # 检查必填字段
    for field in required_fields:
        if field not in agent_data:
            print(f"缺少字段: {field}")
            return False
    
    # 检查基本约束条件
    members = agent_data["members"]
    labor_force = agent_data["labor_force"]
    
    # 验证劳动力不超过总成员数
    if labor_force > members:
        print(f"劳动力 ({labor_force}) 超过了总成员数 ({members})")
        # 限制劳动力数量
        agent_data["labor_force"] = members
        print(f"自动修正劳动力为 {agent_data['labor_force']}")
    
    return True

def generate_agents() -> List[Dict[str, Any]]:
    """生成所有代理
    
    返回:
        代理数据列表
    """
    agents = []
    used_surnames = set()  # 跟踪已使用的姓氏
    
    # 随机打乱姓氏列表
    available_surnames = COMMON_SURNAMES.copy()
    random.shuffle(available_surnames)
    
    for i, value_type in enumerate(VALUE_TYPES.keys(), 1):
        print(f"正在生成{VALUE_TYPES[value_type]}({value_type})代理...")
        
        # 选择一个未使用的姓氏
        surname = available_surnames.pop(0) if available_surnames else ""
        
        # 创建提示词
        prompt = create_agent_prompt(value_type, i, surname)
        
        # 调用API生成代理
        agent_data = call_openai_api(prompt)
        
        # 确保姓氏不重复
        if agent_data["family_name"] in used_surnames:
            # 如果API返回了重复姓氏，强制修改为未使用的姓氏
            if available_surnames:
                new_surname = available_surnames.pop(0)
                print(f"检测到重复姓氏 '{agent_data['family_name']}'，自动修改为 '{new_surname}'")
                agent_data["family_name"] = new_surname
        
        # 记录已使用的姓氏
        used_surnames.add(agent_data["family_name"])
        
        # 验证代理数据
        if validate_agent(agent_data):
            agents.append(agent_data)
            print(f"成功生成{VALUE_TYPES[value_type]}代理: {agent_data['family_name']}家族，共{agent_data['members']}名成员 (劳动力: {agent_data['labor_force']}人)")
        else:
            print(f"生成的{VALUE_TYPES[value_type]}代理数据验证失败")
    
    return agents

def generate_agents_from(start_id: int = 1, surnames_exclude: List[str] = None) -> List[Dict[str, Any]]:
    """从指定ID开始，再生成一轮5个代理（五种价值观各一个）。
    
    参数:
        start_id: 起始ID（包含）
        surnames_exclude: 需要避开的已用姓氏列表
    返回:
        新生成的5个代理列表
    """
    agents = []
    used_surnames = set(surnames_exclude or [])
    available_surnames = [s for s in COMMON_SURNAMES if s not in used_surnames]
    random.shuffle(available_surnames)
    current_id = start_id
    for value_type in VALUE_TYPES.keys():
        print(f"正在生成{VALUE_TYPES[value_type]}({value_type})代理... (ID={current_id})")
        surname = available_surnames.pop(0) if available_surnames else ""
        prompt = create_agent_prompt(value_type, current_id, surname)
        agent_data = call_openai_api(prompt)
        if agent_data["family_name"] in used_surnames:
            if available_surnames:
                new_surname = available_surnames.pop(0)
                print(f"检测到重复姓氏 '{agent_data['family_name']}'，自动修改为 '{new_surname}'")
                agent_data["family_name"] = new_surname
        used_surnames.add(agent_data["family_name"])
        if validate_agent(agent_data):
            agents.append(agent_data)
            print(f"成功生成{VALUE_TYPES[value_type]}代理: {agent_data['family_name']}家族，共{agent_data['members']}名成员 (劳动力: {agent_data['labor_force']}人)")
        else:
            print(f"生成的{VALUE_TYPES[value_type]}代理数据验证失败")
        current_id += 1
    return agents

def save_agents(agents: List[Dict[str, Any]], filename: str = "agents.json"):
    """保存代理到JSON文件
    
    参数:
        agents: 代理数据列表
        filename: 文件名
    """
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump({"agents": agents}, f, ensure_ascii=False, indent=2)
    print(f"成功将{len(agents)}个代理保存到{filename}")

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
    import argparse
    parser = argparse.ArgumentParser(description="生成代理文件：默认生成5户（五种价值观各一）。可选择在现有agents.json上追加5户。")
    parser.add_argument("--file", default="agents.json", help="输出/追加的文件路径")
    parser.add_argument("--append", action="store_true", help="在现有文件基础上再追加5户")
    args = parser.parse_args()

    try:
        print("开始生成社区农场代理...")
        if args.append and os.path.exists(args.file):
            print(f"在现有文件上追加: {args.file}")
            current = load_agents(args.file)
            used = [a.get("family_name", "") for a in current]
            start_id = max((a.get("id", 0) for a in current), default=0) + 1
            extra = generate_agents_from(start_id=start_id, surnames_exclude=used)
            current.extend(extra)
            save_agents(current, args.file)
        else:
            agents = generate_agents()
            save_agents(agents, args.file)
        print("代理生成完成!")
    except Exception as e:
        print(f"程序执行错误: {str(e)}")

if __name__ == "__main__":
    main() 