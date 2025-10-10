import json
from typing import Dict, List, Any, Optional

class AgentManager:
    """代理管理器，用于加载和访问代理数据"""
    
    def __init__(self, agent_file: str = "agents.json"):
        """初始化代理管理器
        
        参数:
            agent_file: 包含代理信息的JSON文件路径
        """
        self.agents = self._load_agents(agent_file)
        self.agent_by_id = {agent["id"]: agent for agent in self.agents}
        self.agent_by_value_type = self._group_by_value_type()
    
    def _load_agents(self, agent_file: str) -> List[Dict[str, Any]]:
        """从文件加载代理"""
        try:
            with open(agent_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("agents", [])
        except Exception as e:
            print(f"加载代理文件失败: {str(e)}")
            return []
    
    def _group_by_value_type(self) -> Dict[str, List[Dict[str, Any]]]:
        """按价值类型分组代理"""
        result = {}
        for agent in self.agents:
            value_type = agent["value_type"]
            if value_type not in result:
                result[value_type] = []
            result[value_type].append(agent)
        return result
    
    def get_agent(self, agent_id: int) -> Optional[Dict[str, Any]]:
        """通过ID获取代理"""
        return self.agent_by_id.get(agent_id)
    
    def get_agents_by_value_type(self, value_type: str) -> List[Dict[str, Any]]:
        """通过价值类型获取代理"""
        return self.agent_by_value_type.get(value_type, [])
    
    def get_all_agents(self) -> List[Dict[str, Any]]:
        """获取所有代理"""
        return self.agents
    
    def print_agent_summary(self, agent_id: int = None):
        """打印代理摘要
        
        如果未指定agent_id，则打印所有代理的摘要
        """
        agents_to_print = [self.get_agent(agent_id)] if agent_id else self.agents
        
        for agent in agents_to_print:
            if agent:
                print("\n" + "="*50)
                print(f"家庭ID: {agent['id']}")
                print(f"家庭名称: {agent['family_name']}")
                print(f"价值类型: {agent['value_type']}")
                print(f"成员: {agent['members']} (劳动力: {agent['labor_force']})")
                print(f"背景: {agent['background']}")
                
                print("\n核心信念:")
                for belief in agent['core_beliefs']:
                    print(f"- {belief}")
                    
                print(f"\n资源立场: {agent['resource_stance']}")
                print(f"理想分配方式: {agent['ideal_distribution']}")
                
                if 'fairness_view' in agent:
                    print(f"对公平的看法: {agent['fairness_view']}")
                
                print("="*50)

# 示例用法
if __name__ == "__main__":
    manager = AgentManager()
    manager.print_agent_summary()
    
    # 获取平等主义代理
    egalitarian_agents = manager.get_agents_by_value_type("egalitarian")
    if egalitarian_agents:
        print("\n平等主义家庭:")
        for agent in egalitarian_agents:
            print(f"- {agent['family_name']}家") 