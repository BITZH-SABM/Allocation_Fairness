import json
import re
import copy
import time
from typing import Dict, List, Any, Tuple, Optional
import math
from openai import OpenAI
from negotiation_logger import NegotiationLogger
from llm_interaction_logger import get_logger

# 设置DeepSeek客户端
client = OpenAI(
    api_key="",  # 替换为你的DeepSeek API密钥
    base_url=""  # 标准根路径，避免 /chat/completions 重复
)

class CollaborativeNegotiation:
    """协作式协商分配机制"""
    
    def __init__(self, agents: List[Dict[str, Any]], total_resources: Dict[str, float], 
                 survival_needs: Dict[int, Dict[str, float]], round_number: int = 1,
                 enable_logging: bool = True, log_dir: str = "negotiation_logs",
                 experiment_id: str = None):
        """初始化协商机制
        
        参数:
            agents: 代理列表
            total_resources: 总资源字典
            survival_needs: 生存需求字典
            round_number: 当前轮数
            enable_logging: 是否启用日志记录
            experiment_id: 实验ID，用于统一所有轮次的日志
        """
        self.agents = agents
        self.total_resources = total_resources
        self.survival_needs = survival_needs
        self.round_number = round_number
        
        # 协商状态
        self.current_proposal = self._initialize_empty_proposal()
        self.conversation_history = []
        self.consensus_items = []  # 已达成共识的分配项
        self.disputed_items = []   # 仍有争议的项目
        
        # 协商阶段
        self.current_stage = "principles"  # principles -> framework -> details -> finalization
        self.stage_results = {}
        
        # 统计信息
        self.total_grain = total_resources.get("grain", 0)
        self.total_members = sum(agent["members"] for agent in agents)
        self.total_labor = sum(agent["labor_force"] for agent in agents)
        
        # 日志记录
        self.enable_logging = enable_logging
        if enable_logging:
            # 🆕 使用experiment_id作为session_id，所有轮次共享同一个日志目录
            if experiment_id:
                session_id = experiment_id
            else:
                import time
                session_id = f"round_{round_number}_{int(time.time())}"
            
            self.logger = NegotiationLogger(session_id, output_dir=log_dir)
            self.logger.start_session(
                round_number=round_number,
                participants=agents,
                total_resources=total_resources,
                survival_needs=survival_needs
            )
        else:
            self.logger = None
    
    def _initialize_empty_proposal(self) -> Dict[int, Dict[str, float]]:
        """初始化空的分配提案"""
        return {agent["id"]: {"grain": 0.0} for agent in self.agents}
    
    def run_collaborative_negotiation(self) -> Tuple[Dict[int, Dict[str, float]], Dict[str, Any]]:
        """运行完整的协作式协商流程
        
        返回:
            (最终分配结果, 协商过程数据)
        """
        print("\n" + "="*70)
        print("开始协作式协商分配流程")
        print("="*70)
        
        try:
            # 阶段1：确定分配原则
            print("\n 阶段1：确定分配原则")
            principles = self._establish_principles()
            self.stage_results["principles"] = principles
            
            # 阶段2：协商分配框架
            print("\n 阶段2：协商分配框架")
            framework = self._negotiate_framework(principles)
            self.stage_results["framework"] = framework
            
            # 阶段3：构建详细方案
            print("\n 阶段3：构建详细分配方案")
            detailed_proposal = self._build_detailed_proposal(framework)
            self.stage_results["detailed_proposal"] = detailed_proposal
            
            # 阶段4：最终确认和调整
            print("\n 阶段4：最终确认和微调")
            final_proposal = self._finalize_proposal(detailed_proposal)
            
            # 生成协商数据
            negotiation_data = self._create_negotiation_data(True, "collaborative_consensus")
            
            # 会话收尾日志
            if self.logger:
                avg_satisfaction = getattr(self, "final_average_satisfaction", 0.0)
                try:
                    self.logger.end_session(
                        final_allocation=final_proposal,
                        success=True,
                        average_satisfaction=avg_satisfaction
                    )
                except Exception:
                    pass
            
            print("\n 协商成功完成！")
            return final_proposal, negotiation_data
            
        except Exception as e:
            print(f"\n 协商过程出现错误: {str(e)}")
            # 回退到简单分配
            fallback_proposal = self._create_fallback_proposal()
            negotiation_data = self._create_negotiation_data(False, "error_fallback")
            
            # 会话收尾日志（失败）
            if self.logger:
                try:
                    self.logger.end_session(
                        final_allocation=fallback_proposal,
                        success=False,
                        failure_reason=str(e),
                        average_satisfaction=0.0
                    )
                except Exception:
                    pass
            return fallback_proposal, negotiation_data
    
    def _establish_principles(self) -> Dict[str, Any]:
        """阶段1：确定分配原则"""
        self.current_stage = "principles"
        
        # 开始日志记录
        if self.logger:
            self.logger.start_stage("establish_principles", [agent["id"] for agent in self.agents])
        
        # 1.1 收集各家庭的原则偏好
        print("\n   收集各家庭的分配原则偏好...")
        principle_preferences = {}
        
        for agent in self.agents:
            preference = self._get_principle_preference(agent)
            principle_preferences[agent["id"]] = preference
            print(f"    {agent['family_name']}家：{preference['summary']}")
            
            # 记录原则偏好
            if self.logger:
                self.logger.log_discussion_turn(
                    speaker_id=agent["id"],
                    speaker_name=agent["family_name"],
                    speaker_value_type=agent["value_type"],
                    content=preference["raw_response"],
                    speech_type="principle_preference",
                    target_topic="分配原则偏好"
                )
        
        # 1.2 识别共同原则
        print("\n   寻找共同原则...")
        common_principles = self._find_common_principles(principle_preferences)
        
        # 记录共同原则决策
        if self.logger and common_principles:
            self.logger.log_decision(
                decision_type="common_principles_identified",
                decision_content=common_principles,
                supporters=list(range(1, len(self.agents) + 1)),  # 所有人支持的原则
                opponents=[]
            )
        
        # 1.3 讨论有争议的原则
        print("\n   讨论有争议的原则...")
        discussed_principles = self._discuss_disputed_principles(principle_preferences, common_principles)
        
        # 1.4 确定最终原则
        final_principles = {**common_principles, **discussed_principles}
        
        print(f"\n   确定的分配原则：")
        for key, value in final_principles.items():
            print(f"    - {key}: {value}")
        
        # 结束阶段记录
        if self.logger:
            consensus_level = len(final_principles) / max(len(principle_preferences), 1)
            self.logger.end_stage(
                stage_outcome=f"确定了{len(final_principles)}个分配原则",
                consensus_level=consensus_level
            )
        
        return final_principles
    
    def _get_principle_preference(self, agent: Dict[str, Any]) -> Dict[str, Any]:
        """获取代理的原则偏好"""
        prompt = f"""你是{agent['family_name']}家庭的代表，价值观为{agent['value_type']}。

家庭情况：
- 成员数：{agent['members']}人
- 劳动力：{agent['labor_force']}人
- 核心信念：{agent['core_beliefs'][0]}

社区情况：
- 总资源：{self.total_grain:.1f}单位农作物
- 总人口：{self.total_members}人
- 总劳动力：{self.total_labor}人

现在社区需要确定资源分配的基本原则。请表达你认为最重要的3个分配原则，并简要解释原因。

可考虑的原则包括但不限于：
- 按需分配（优先满足基本生存需求）
- 按劳分配（根据劳动力贡献分配）
- 平等分配（每人或每家获得相同份额）
- 照顾弱势（对困难家庭给予更多支持）
- 效率优先（确保资源得到最有效利用）
- 可持续发展（为长期发展保留资源）

请用以下格式回答：
原则1：[原则名称] - [简要理由]
原则2：[原则名称] - [简要理由] 
原则3：[原则名称] - [简要理由]
"""
        
        model_name = "deepseek-v3"
        temperature = 0.7
        
        try:
            start_time = time.time()
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "你是一个参与社区协商的家庭代表，请根据你的价值观和家庭情况，真诚地表达你的分配原则偏好。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=400
            )
            duration = time.time() - start_time
            
            content = response.choices[0].message.content
            principles = self._parse_principles(content)
            
            # 记录LLM交互
            llm_logger = get_logger()
            if llm_logger:
                llm_logger.log_negotiation_call(
                    round_number=self.round_number,
                    stage="principles",
                    agent=agent,
                    input_prompt=prompt,
                    raw_output=content,
                    model=model_name,
                    temperature=temperature,
                    duration=duration,
                    success=True,
                    processed_data={
                        "principles": principles,
                        "summary": f"强调{principles[0] if principles else '平衡发展'}"
                    }
                )
            
            return {
                "raw_response": content,
                "principles": principles,
                "summary": f"强调{principles[0] if principles else '平衡发展'}"
            }
            
        except Exception as e:
            print(f"获取{agent['family_name']}家原则偏好失败: {str(e)}")
            
            # 记录失败的LLM调用
            llm_logger = get_logger()
            if llm_logger:
                llm_logger.log_negotiation_call(
                    round_number=self.round_number,
                    stage="principles",
                    agent=agent,
                    input_prompt=prompt,
                    raw_output=f"获取失败: {str(e)}",
                    model=model_name,
                    temperature=temperature,
                    duration=0.0,
                    success=False
                )
            
            return {
                "raw_response": "获取失败",
                "principles": ["按需分配", "公平合理", "可持续发展"],
                "summary": "平衡发展"
            }
    
    def _parse_principles(self, content: str) -> List[str]:
        """解析原则回复"""
        principles = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if re.match(r'原则[123][:：]', line):
                # 提取原则名称（冒号前到第一个"-"或"—"之间的部分）
                match = re.search(r'原则[123][:：]\s*([^-—]+)', line)
                if match:
                    principle = match.group(1).strip()
                    principles.append(principle)
        
        # 如果解析失败，返回默认原则
        if not principles:
            principles = ["公平分配", "满足基本需求", "考虑贡献"]
        
        return principles[:3]  # 最多3个原则
    
    def _find_common_principles(self, principle_preferences: Dict[int, Dict[str, Any]]) -> Dict[str, str]:
        """寻找共同原则"""
        # 统计所有提到的原则
        principle_counts = {}
        
        for agent_id, pref in principle_preferences.items():
            for principle in pref["principles"]:
                # 归一化原则名称
                normalized = self._normalize_principle_name(principle)
                principle_counts[normalized] = principle_counts.get(normalized, 0) + 1
        
        # 找出大多数人支持的原则（超过一半）
        threshold = len(self.agents) // 2 + 1
        common_principles = {}
        
        for principle, count in principle_counts.items():
            if count >= threshold:
                common_principles[principle] = f"获得{count}/{len(self.agents)}家庭支持"
        
        return common_principles
    
    def _normalize_principle_name(self, principle: str) -> str:
        """归一化原则名称"""
        # 简单的关键词匹配归一化
        principle_lower = principle.lower()
        
        if any(word in principle_lower for word in ["按需", "需求", "基本需要"]):
            return "按需分配"
        elif any(word in principle_lower for word in ["按劳", "贡献", "劳动"]):
            return "按劳分配"
        elif any(word in principle_lower for word in ["平等", "均等", "相同"]):
            return "平等分配"
        elif any(word in principle_lower for word in ["弱势", "困难", "照顾"]):
            return "照顾弱势"
        elif any(word in principle_lower for word in ["效率", "有效"]):
            return "效率优先"
        elif any(word in principle_lower for word in ["可持续", "长期", "发展"]):
            return "可持续发展"
        else:
            return principle  # 保持原名
    
    def _discuss_disputed_principles(self, principle_preferences: Dict[int, Dict[str, Any]], 
                                   common_principles: Dict[str, str]) -> Dict[str, str]:
        """讨论有争议的原则"""
        
        # 找出未达成共识但有支持的原则
        all_mentioned = {}
        for pref in principle_preferences.values():
            for principle in pref["principles"]:
                normalized = self._normalize_principle_name(principle)
                if normalized not in common_principles:
                    all_mentioned[normalized] = all_mentioned.get(normalized, 0) + 1
        
        # 选择最有争议的2个原则进行讨论
        disputed = sorted(all_mentioned.items(), key=lambda x: x[1], reverse=True)[:2]
        
        discussed_results = {}
        
        for principle_name, support_count in disputed:
            print(f"\n     讨论原则：{principle_name} (当前支持度：{support_count}/{len(self.agents)})")
            
            # 让支持者和反对者各自表达观点
            discussion_result = self._moderate_principle_discussion(principle_name, principle_preferences)
            discussed_results[principle_name] = discussion_result
        
        return discussed_results
    
    def _moderate_principle_discussion(self, principle_name: str, 
                                     principle_preferences: Dict[int, Dict[str, Any]]) -> str:
        """主持原则讨论"""
        
        # 找出支持者和反对者
        supporters = []
        others = []
        
        for agent in self.agents:
            agent_principles = [self._normalize_principle_name(p) for p in 
                             principle_preferences[agent["id"]]["principles"]]
            if principle_name in agent_principles:
                supporters.append(agent)
            else:
                others.append(agent)
        
        # 记录争议
        if self.logger and len(supporters) > 1 and len(others) > 0:
            self.logger.log_conflict(
                conflict_topic=f"原则：{principle_name}",
                conflicting_parties=[agent["id"] for agent in others],
                conflict_description=f"{len(supporters)}家支持，{len(others)}家反对或中立"
            )
        
        # 如果支持者过少，直接放弃
        if len(supporters) <= 1:
            return f"支持度不足，不采纳"
        
        # 让一个支持者进行说服
        if supporters:
            advocate = supporters[0]  # 选择第一个支持者作为倡导者
            persuasion = self._generate_principle_persuasion(advocate, principle_name)
            
            # 记录说服发言
            if self.logger:
                self.logger.log_discussion_turn(
                    speaker_id=advocate["id"],
                    speaker_name=advocate["family_name"],
                    speaker_value_type=advocate["value_type"],
                    content=persuasion,
                    speech_type="persuasion",
                    target_topic=f"为原则'{principle_name}'说服"
                )
            
            # 评估说服效果
            convinced_count = self._evaluate_persuasion_effect(persuasion, others, principle_name)
            
            total_support = len(supporters) + convinced_count
            result_msg = ""
            if total_support >= len(self.agents) // 2 + 1:
                result_msg = f"经讨论后获得{total_support}/{len(self.agents)}家庭支持，采纳"
                # 记录决策
                if self.logger:
                    self.logger.log_decision(
                        decision_type="principle_adopted",
                        decision_content={principle_name: "采纳"},
                        supporters=[agent["id"] for agent in supporters] + [others[i]["id"] for i in range(convinced_count)],
                        opponents=[agent["id"] for agent in others[convinced_count:]]
                    )
            else:
                result_msg = f"讨论后仍只有{total_support}/{len(self.agents)}家庭支持，不采纳"
                
            return result_msg
        
        return "讨论无结果"
    
    def _generate_principle_persuasion(self, advocate: Dict[str, Any], principle_name: str) -> str:
        """生成原则说服论述"""
        prompt = f"""你是{advocate['family_name']}家庭的代表，你支持"{principle_name}"这个分配原则。

现在需要你向其他家庭解释为什么这个原则对整个社区有益，尝试说服他们支持这个原则。

你的家庭背景：{advocate['background']}
你的核心信念：{advocate['core_beliefs'][0]}

社区情况：
- 总资源：{self.total_grain:.1f}单位农作物
- 总人口：{self.total_members}人
- 总劳动力：{self.total_labor}人

请用简洁有力的语言（不超过100字）解释：
1. 为什么这个原则符合社区整体利益
2. 这个原则如何帮助社区长期发展
3. 呼吁其他家庭支持

要求：语言真诚、论据合理、考虑其他家庭的利益。
"""
        
        model_name = "deepseek-v3"
        temperature = 0.6
        
        try:
            start_time = time.time()
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "你是一个善于沟通和说服的社区代表，请用真诚和理性的方式进行论述。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=200
            )
            duration = time.time() - start_time
            
            content = response.choices[0].message.content
            
            # 记录LLM交互
            llm_logger = get_logger()
            if llm_logger:
                llm_logger.log_negotiation_call(
                    round_number=self.round_number,
                    stage="principles-persuasion",
                    agent=advocate,
                    input_prompt=prompt,
                    raw_output=content,
                    model=model_name,
                    temperature=temperature,
                    duration=duration,
                    success=True,
                    processed_data={
                        "principle_name": principle_name,
                        "persuasion_type": "说服其他家庭支持原则"
                    }
                )
            
            return content
            
        except Exception as e:
            fallback = f"我认为{principle_name}对我们社区的长期发展很重要，希望大家能够支持。"
            
            # 记录失败的LLM调用
            llm_logger = get_logger()
            if llm_logger:
                llm_logger.log_negotiation_call(
                    round_number=self.round_number,
                    stage="principles-persuasion",
                    agent=advocate,
                    input_prompt=prompt,
                    raw_output=f"获取失败: {str(e)}",
                    model=model_name,
                    temperature=temperature,
                    duration=0.0,
                    success=False
                )
            
            return fallback
    
    def _evaluate_persuasion_effect(self, persuasion: str, others: List[Dict[str, Any]], 
                                   principle_name: str) -> int:
        """评估说服效果"""
        convinced_count = 0
        
        for agent in others:
            # 简化的说服效果评估
            agent_value = agent["value_type"]
            
            # 根据价值观匹配度判断是否被说服
            if principle_name == "按需分配" and agent_value in ["needs_based", "altruistic"]:
                convinced_count += 1
            elif principle_name == "按劳分配" and agent_value in ["merit_based", "pragmatic"]:
                convinced_count += 1
            elif principle_name == "平等分配" and agent_value in ["egalitarian", "altruistic"]:
                convinced_count += 1
            elif principle_name == "照顾弱势" and agent_value in ["altruistic", "needs_based"]:
                convinced_count += 1
            elif principle_name == "效率优先" and agent_value in ["merit_based", "pragmatic"]:
                convinced_count += 1
            elif principle_name == "可持续发展" and agent_value == "pragmatic":
                convinced_count += 1
        
        return convinced_count
    
    def _negotiate_framework(self, principles: Dict[str, str]) -> Dict[str, Any]:
        """阶段2：协商分配框架"""
        self.current_stage = "framework"
        
        # 开始框架协商阶段
        if self.logger:
            self.logger.start_stage("negotiate_framework", [agent["id"] for agent in self.agents])
        
        print("\n   基于确定的原则，构建分配框架...")
        
        # 2.1 根据原则确定分配策略
        allocation_strategy = self._determine_allocation_strategy(principles)
        
        # 记录策略决定
        if self.logger:
            self.logger.log_decision(
                decision_type="allocation_strategy_determined",
                decision_content=allocation_strategy,
                supporters=[agent["id"] for agent in self.agents],
                opponents=[]
            )
        
        # 2.2 协商具体的分配比例
        print("\n   协商具体分配比例...")
        allocation_ratios = self._negotiate_allocation_ratios(principles, allocation_strategy)
        
        # 2.3 确定优先级顺序
        print("\n   确定分配优先级...")
        priority_order = self._establish_priority_order(principles)
        
        framework = {
            "strategy": allocation_strategy,
            "ratios": allocation_ratios,
            "priority_order": priority_order,
            "based_on_principles": list(principles.keys())
        }
        
        print(f"\n   框架确定：{allocation_strategy['name']}")
        
        # 结束框架阶段
        if self.logger:
            self.logger.end_stage(
                stage_outcome=f"确定了{allocation_strategy['name']}分配框架",
                consensus_level=0.9  # 假设框架阶段通常能达成较高共识
            )
        
        return framework
    
    def _determine_allocation_strategy(self, principles: Dict[str, str]) -> Dict[str, Any]:
        """根据原则确定分配策略"""
        
        principle_names = list(principles.keys())
        
        # 根据主导原则确定策略
        if "按需分配" in principle_names and "照顾弱势" in principle_names:
            return {
                "name": "需求优先策略",
                "description": "优先满足基本需求，特别照顾困难家庭",
                "base_method": "needs_first"
            }
        elif "按劳分配" in principle_names and "效率优先" in principle_names:
            return {
                "name": "贡献导向策略", 
                "description": "根据劳动贡献分配，激励高效生产",
                "base_method": "contribution_based"
            }
        elif "平等分配" in principle_names:
            return {
                "name": "平等基础策略",
                "description": "在保证基本需求前提下尽量平等分配",
                "base_method": "equality_based"
            }
        else:
            return {
                "name": "混合平衡策略",
                "description": "综合考虑多种因素的平衡分配",
                "base_method": "balanced_hybrid"
            }
    
    def _negotiate_allocation_ratios(self, principles: Dict[str, str], 
                                   strategy: Dict[str, Any]) -> Dict[str, float]:
        """协商分配比例"""
        
        # 基于策略和原则确定初始比例
        base_ratios = self._get_base_ratios(strategy)
        
        # 让代理讨论和调整比例
        adjusted_ratios = self._discuss_ratio_adjustments(base_ratios, principles)
        
        return adjusted_ratios
    
    def _get_base_ratios(self, strategy: Dict[str, Any]) -> Dict[str, float]:
        """获取基础分配比例"""
        
        if strategy["base_method"] == "needs_first":
            return {
                "survival_guarantee": 0.6,  # 60%用于保证生存需求
                "additional_support": 0.25,  # 25%用于额外支持
                "community_reserve": 0.15   # 15%作为社区储备
            }
        elif strategy["base_method"] == "contribution_based":
            return {
                "survival_guarantee": 0.4,  # 40%保证基本生存
                "contribution_reward": 0.5,  # 50%按贡献分配
                "community_reserve": 0.1    # 10%社区储备
            }
        elif strategy["base_method"] == "equality_based":
            return {
                "survival_guarantee": 0.5,  # 50%保证生存
                "equal_distribution": 0.4,  # 40%平等分配
                "community_reserve": 0.1    # 10%储备
            }
        else:  # balanced_hybrid
            return {
                "survival_guarantee": 0.45,  # 45%保证生存
                "merit_portion": 0.25,      # 25%按贡献
                "equal_portion": 0.2,       # 20%平等分配
                "community_reserve": 0.1    # 10%储备
            }
    
    def _discuss_ratio_adjustments(self, base_ratios: Dict[str, float], 
                                 principles: Dict[str, str]) -> Dict[str, float]:
        """讨论比例调整"""
        
        print(f"    初始比例方案：{base_ratios}")
        
        # 征求各家庭对比例的意见
        adjustment_suggestions = {}
        
        for agent in self.agents:
            suggestion = self._get_ratio_adjustment_suggestion(agent, base_ratios, principles)
            adjustment_suggestions[agent["id"]] = suggestion
            
            if suggestion["has_adjustment"]:
                print(f"    {agent['family_name']}家建议：{suggestion['suggestion']}")
                
                # 记录比例调整建议
                if self.logger:
                    self.logger.log_discussion_turn(
                        speaker_id=agent["id"],
                        speaker_name=agent["family_name"],
                        speaker_value_type=agent["value_type"],
                        content=suggestion["suggestion"],
                        speech_type="ratio_adjustment_suggestion",
                        target_topic="分配比例调整"
                    )
        
        # 找出有共识的调整
        final_ratios = self._apply_consensus_adjustments(base_ratios, adjustment_suggestions)
        
        print(f"    最终比例方案：{final_ratios}")
        return final_ratios
    
    def _get_ratio_adjustment_suggestion(self, agent: Dict[str, Any], base_ratios: Dict[str, float],
                                       principles: Dict[str, str]) -> Dict[str, Any]:
        """获取比例调整建议"""
        
        # 根据代理价值观判断是否需要调整
        value_type = agent["value_type"]
        has_adjustment = False
        suggestion = ""
        
        if value_type == "altruistic" and base_ratios.get("survival_guarantee", 0) < 0.5:
            has_adjustment = True
            suggestion = "建议提高生存保障比例到50%以上"
        elif value_type == "merit_based" and base_ratios.get("contribution_reward", 0) < 0.4:
            has_adjustment = True
            suggestion = "建议提高按贡献分配的比例"
        elif value_type == "egalitarian" and base_ratios.get("equal_distribution", 0) < 0.3:
            has_adjustment = True
            suggestion = "建议增加平等分配的比例"
        
        return {
            "has_adjustment": has_adjustment,
            "suggestion": suggestion,
            "agent_id": agent["id"]
        }
    
    def _apply_consensus_adjustments(self, base_ratios: Dict[str, float], 
                                   suggestions: Dict[int, Dict[str, Any]]) -> Dict[str, float]:
        """应用有共识的调整"""
        
        # 简化处理：如果超过一半代理建议同样的调整，则应用
        adjusted_ratios = base_ratios.copy()
        
        # 统计调整建议
        adjustment_counts = {}
        for suggestion in suggestions.values():
            if suggestion["has_adjustment"]:
                key = suggestion["suggestion"]
                adjustment_counts[key] = adjustment_counts.get(key, 0) + 1
        
        # 应用有共识的调整（超过一半支持）
        threshold = len(self.agents) // 2 + 1
        
        for adjustment, count in adjustment_counts.items():
            if count >= threshold:
                # 简化的调整逻辑
                if "生存保障" in adjustment and "50%" in adjustment:
                    if "survival_guarantee" in adjusted_ratios:
                        old_value = adjusted_ratios["survival_guarantee"]
                        adjusted_ratios["survival_guarantee"] = max(0.5, old_value)
                        # 相应调整其他比例
                        self._rebalance_ratios(adjusted_ratios)
        
        return adjusted_ratios
    
    def _rebalance_ratios(self, ratios: Dict[str, float]) -> None:
        """重新平衡比例，确保总和为1"""
        total = sum(ratios.values())
        if total != 1.0:
            # 按比例调整所有项目
            for key in ratios:
                ratios[key] = ratios[key] / total
    
    def _establish_priority_order(self, principles: Dict[str, str]) -> List[str]:
        """确定分配优先级顺序"""
        
        priority_order = []
        
        # 基于原则确定优先级
        if "按需分配" in principles or "照顾弱势" in principles:
            priority_order.append("满足基本生存需求")
        
        if "按劳分配" in principles:
            priority_order.append("按劳动贡献分配")
        
        if "平等分配" in principles:
            priority_order.append("保证分配公平性")
        
        if "可持续发展" in principles:
            priority_order.append("预留发展资源")
        
        # 确保至少有基本优先级
        if not priority_order:
            priority_order = ["满足基本生存需求", "公平合理分配"]
        
        return priority_order
    
    def _build_detailed_proposal(self, framework: Dict[str, Any]) -> Dict[int, Dict[str, float]]:
        """阶段3：构建详细分配方案（包含LLM驱动的协商）"""
        self.current_stage = "details"
        
        # 开始阶段日志
        if self.logger:
            try:
                self.logger.start_stage("details", [agent["id"] for agent in self.agents])
            except Exception:
                pass
        
        print("\n   根据框架计算初步分配方案...")
        
        # 3.1 计算初步基础分配
        initial_allocation = self._calculate_base_allocation(framework)
        initial_allocation = self._handle_special_cases(initial_allocation, framework)
        initial_allocation = self._validate_and_optimize(initial_allocation)
        
        print("\n   初步分配方案：")
        for agent in self.agents:
            agent_id = agent["id"]
            allocation = initial_allocation.get(agent_id, {})
            total = sum(allocation.values())
            print(f"    {agent['family_name']}家：{total:.2f}单位")
        
        # 记录初步分配
        if self.logger:
            try:
                per_agent_totals = {aid: sum(res.values()) for aid, res in initial_allocation.items()}
                self.logger.log_decision(
                    decision_type="initial_allocation_proposed",
                    decision_content={
                        "strategy": framework.get("strategy", {}),
                        "ratios": framework.get("ratios", {}),
                        "per_agent_total": per_agent_totals
                    },
                    supporters=[agent["id"] for agent in self.agents],
                    opponents=[]
                )
            except Exception:
                pass
        
        # 🎯 3.2 让各家庭对初步方案发表意见和提出调整请求
        print("\n   征求各家庭对初步方案的意见...")
        allocation_opinions = self._collect_allocation_opinions(initial_allocation, framework)
        
        # 🎯 3.3 识别有争议的分配并进行讨论
        print("\n   处理分配异议...")
        disputed_agents = [aid for aid, op in allocation_opinions.items() 
                          if op.get("has_objection", False)]
        
        if disputed_agents:
            print(f"    发现 {len(disputed_agents)} 家提出异议，开始协商...")
            negotiated_allocation = self._negotiate_disputed_allocations(
                initial_allocation, allocation_opinions, framework
            )
        else:
            print("    各家庭无重大异议")
            negotiated_allocation = initial_allocation
        
        # 3.4 最终验证
        print("\n   最终分配方案：")
        final_allocation = self._validate_and_optimize(negotiated_allocation)
        for agent in self.agents:
            agent_id = agent["id"]
            allocation = final_allocation.get(agent_id, {})
            total = sum(allocation.values())
            print(f"    {agent['family_name']}家：{total:.2f}单位")
        
        # 结束阶段日志
        if self.logger:
            try:
                satisfied = 0
                for agent in self.agents:
                    aid = agent["id"]
                    got = sum(final_allocation.get(aid, {}).values())
                    need = sum(self.survival_needs.get(aid, {}).values())
                    if need <= 0 or got >= need:
                        satisfied += 1
                consensus_level = satisfied / len(self.agents) if self.agents else 0.0
                self.logger.end_stage(
                    stage_outcome="详细方案协商完成",
                    consensus_level=consensus_level
                )
            except Exception:
                pass
        
        return final_allocation
    
    def _calculate_base_allocation(self, framework: Dict[str, Any]) -> Dict[int, Dict[str, float]]:
        """计算基础分配"""
        
        strategy = framework["strategy"]["base_method"]
        ratios = framework["ratios"]
        
        if strategy == "needs_first":
            return self._calculate_needs_first_allocation(ratios)
        elif strategy == "contribution_based":
            return self._calculate_contribution_allocation(ratios)
        elif strategy == "equality_based":
            return self._calculate_equality_allocation(ratios)
        else:  # balanced_hybrid
            return self._calculate_hybrid_allocation(ratios)
    
    def _calculate_needs_first_allocation(self, ratios: Dict[str, float]) -> Dict[int, Dict[str, float]]:
        """需求优先分配计算"""
        allocation = self._initialize_empty_proposal()
        
        # 第一步：保证生存需求
        survival_budget = self.total_grain * ratios["survival_guarantee"]
        remaining_budget = self.total_grain - survival_budget
        
        # 满足所有家庭的基本生存需求
        total_survival_needs = sum(
            sum(needs.values()) for needs in self.survival_needs.values()
        )
        
        for agent in self.agents:
            agent_id = agent["id"]
            agent_needs = sum(self.survival_needs.get(agent_id, {}).values())
            
            if total_survival_needs > 0:
                survival_share = (agent_needs / total_survival_needs) * survival_budget
                allocation[agent_id]["grain"] = survival_share
        
        # 第二步：剩余资源按需求程度分配
        if remaining_budget > 0:
            # 计算各家庭的需求强度（考虑家庭规模和依赖比）
            need_weights = {}
            total_weight = 0
            
            for agent in self.agents:
                agent_id = agent["id"]
                members = agent["members"]
                labor_force = agent["labor_force"]
                dependency_ratio = members / labor_force if labor_force > 0 else 2.0
                
                # 需求权重 = 成员数 * 依赖比
                weight = members * dependency_ratio
                need_weights[agent_id] = weight
                total_weight += weight
            
            # 按权重分配剩余资源
            for agent in self.agents:
                agent_id = agent["id"]
                if total_weight > 0:
                    additional_share = (need_weights[agent_id] / total_weight) * remaining_budget
                    allocation[agent_id]["grain"] += additional_share
        
        return allocation
    
    def _calculate_contribution_allocation(self, ratios: Dict[str, float]) -> Dict[int, Dict[str, float]]:
        """贡献导向分配计算"""
        allocation = self._initialize_empty_proposal()
        
        # 第一步：保证基本生存
        survival_budget = self.total_grain * ratios["survival_guarantee"]
        contribution_budget = self.total_grain * ratios["contribution_reward"]
        
        # 按最低需求分配生存资源
        for agent in self.agents:
            agent_id = agent["id"]
            min_survival = sum(self.survival_needs.get(agent_id, {}).values())
            allocation[agent_id]["grain"] = min_survival
        
        # 第二步：按劳动力贡献分配剩余资源
        if self.total_labor > 0:
            for agent in self.agents:
                agent_id = agent["id"]
                labor_force = agent["labor_force"]
                contribution_share = (labor_force / self.total_labor) * contribution_budget
                allocation[agent_id]["grain"] += contribution_share
        
        return allocation
    
    def _calculate_equality_allocation(self, ratios: Dict[str, float]) -> Dict[int, Dict[str, float]]:
        """平等分配计算"""
        allocation = self._initialize_empty_proposal()
        
        # 简单的平等分配
        per_family_share = self.total_grain / len(self.agents)
        
        for agent in self.agents:
            agent_id = agent["id"]
            allocation[agent_id]["grain"] = per_family_share
        
        return allocation
    
    def _calculate_hybrid_allocation(self, ratios: Dict[str, float]) -> Dict[int, Dict[str, float]]:
        """混合分配计算"""
        allocation = self._initialize_empty_proposal()
        
        # 多层分配
        survival_budget = self.total_grain * ratios["survival_guarantee"]
        merit_budget = self.total_grain * ratios["merit_portion"]
        equal_budget = self.total_grain * ratios["equal_portion"]
        
        # 层1：生存保障
        for agent in self.agents:
            agent_id = agent["id"]
            min_survival = sum(self.survival_needs.get(agent_id, {}).values())
            allocation[agent_id]["grain"] = min(min_survival, survival_budget / len(self.agents))
        
        # 层2：按劳分配
        if self.total_labor > 0:
            for agent in self.agents:
                agent_id = agent["id"]
                labor_share = (agent["labor_force"] / self.total_labor) * merit_budget
                allocation[agent_id]["grain"] += labor_share
        
        # 层3：平等分配
        equal_share = equal_budget / len(self.agents)
        for agent in self.agents:
            agent_id = agent["id"]
            allocation[agent_id]["grain"] += equal_share
        
        return allocation
    
    def _handle_special_cases(self, base_allocation: Dict[int, Dict[str, float]], 
                            framework: Dict[str, Any]) -> Dict[int, Dict[str, float]]:
        """处理特殊情况"""
        adjusted_allocation = copy.deepcopy(base_allocation)
        
        # 检查是否有家庭分配过少
        for agent in self.agents:
            agent_id = agent["id"]
            min_survival = sum(self.survival_needs.get(agent_id, {}).values())
            current_allocation = adjusted_allocation[agent_id]["grain"]
            
            if current_allocation < min_survival:
                # 需要从其他家庭调配资源
                deficit = min_survival - current_allocation
                # 记录冲突：生存未满足
                if self.logger:
                    try:
                        self.logger.log_conflict(
                            conflict_topic="生存未满足",
                            conflicting_parties=[agent_id],
                            conflict_description=f"缺口={deficit:.2f}"
                        )
                    except Exception:
                        pass
                self._redistribute_for_survival(adjusted_allocation, agent_id, deficit)
        
        return adjusted_allocation
    
    def _redistribute_for_survival(self, allocation: Dict[int, Dict[str, float]], 
                                 needy_agent_id: int, deficit: float) -> None:
        """为保证生存需求重新分配资源"""
        
        # 找出有剩余的家庭
        surplus_agents = []
        
        for agent in self.agents:
            agent_id = agent["id"]
            if agent_id == needy_agent_id:
                continue
                
            current = allocation[agent_id]["grain"]
            min_needed = sum(self.survival_needs.get(agent_id, {}).values())
            
            if current > min_needed:
                surplus = current - min_needed
                surplus_agents.append((agent_id, surplus))
        
        # 按剩余量排序，从剩余最多的开始调配
        surplus_agents.sort(key=lambda x: x[1], reverse=True)
        
        remaining_deficit = deficit
        
        for agent_id, surplus in surplus_agents:
            if remaining_deficit <= 0:
                break
            
            transfer_amount = min(surplus * 0.5, remaining_deficit)  # 最多转移一半剩余
            
            allocation[agent_id]["grain"] -= transfer_amount
            allocation[needy_agent_id]["grain"] += transfer_amount
            remaining_deficit -= transfer_amount
            
            # 记录每笔再分配
            if self.logger and transfer_amount > 0:
                try:
                    self.logger.log_decision(
                        decision_type="survival_redistribution",
                        decision_content={
                            "from": agent_id,
                            "to": needy_agent_id,
                            "amount": transfer_amount
                        },
                        supporters=[agent_id],
                        opponents=[]
                    )
                except Exception:
                    pass
    
    def _collect_allocation_opinions(self, allocation: Dict[int, Dict[str, float]], 
                                   framework: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
        """收集各家庭对初步分配方案的意见"""
        opinions = {}
        
        for agent in self.agents:
            agent_id = agent["id"]
            allocated_amount = sum(allocation.get(agent_id, {}).values())
            survival_need = sum(self.survival_needs.get(agent_id, {}).values())
            
            opinion = self._get_allocation_opinion(
                agent, allocated_amount, survival_need, allocation, framework
            )
            opinions[agent_id] = opinion
            
            # 记录意见
            if self.logger and opinion.get("has_objection"):
                self.logger.log_discussion_turn(
                    speaker_id=agent_id,
                    speaker_name=agent["family_name"],
                    speaker_value_type=agent["value_type"],
                    content=opinion.get("objection_reason", ""),
                    speech_type="allocation_objection",
                    target_topic="初步分配方案"
                )
        
        return opinions
    
    def _get_allocation_opinion(self, agent: Dict[str, Any], allocated_amount: float,
                              survival_need: float, all_allocations: Dict[int, Dict[str, float]],
                              framework: Dict[str, Any]) -> Dict[str, Any]:
        """获取单个家庭对分配方案的意见（LLM驱动）"""
        
        # 构建其他家庭分配情况的描述
        other_allocations_str = ""
        for other_agent in self.agents:
            if other_agent["id"] != agent["id"]:
                other_amount = sum(all_allocations.get(other_agent["id"], {}).values())
                other_need = sum(self.survival_needs.get(other_agent["id"], {}).values())
                other_allocations_str += f"- {other_agent['family_name']}家（{other_agent['members']}人，{other_agent['labor_force']}劳力）：分配{other_amount:.1f}单位，生存需求{other_need:.1f}\n"
        
        prompt = f"""你是{agent['family_name']}家庭的代表，价值观为{agent['value_type']}。

当前协商进展：社区已确定分配框架（{framework['strategy']['name']}），现在需要对初步计算出的具体分配数字进行讨论。

你家情况：
- 成员数：{agent['members']}人
- 劳动力：{agent['labor_force']}人
- 生存需求：{survival_need:.1f}单位粮食
- 初步分配：{allocated_amount:.1f}单位粮食
- 盈余/缺口：{allocated_amount - survival_need:+.1f}单位

其他家庭的初步分配：
{other_allocations_str}

社区资源总量：{self.total_grain:.1f}单位

请根据你的价值观评估这个初步分配方案：
1. 你是否接受这个分配数量？（直接回答"接受"或"有异议"）
2. 如果有异议，简要说明原因（不超过50字）
3. 如果有异议，你希望调整到多少单位？（给出具体数字）

请按以下格式回答：
态度：[接受/有异议]
理由：[你的理由]
期望数量：[数字]（如果接受则填当前数量）
"""
        
        model_name = "deepseek-v3"
        temperature = 0.8
        
        try:
            start_time = time.time()
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "你是一个参与社区资源协商的家庭代表。请根据你的价值观和家庭实际情况，真实地表达你对分配方案的看法。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=300
            )
            duration = time.time() - start_time
            
            content = response.choices[0].message.content
            
            # 解析回复
            has_objection = "有异议" in content
            
            # 提取期望数量
            expected_amount = allocated_amount  # 默认值
            amount_match = re.search(r'期望数量[:：]\s*([\d.]+)', content)
            if amount_match:
                try:
                    expected_amount = float(amount_match.group(1))
                except:
                    pass
            
            # 提取理由
            reason_match = re.search(r'理由[:：]\s*(.+?)(?=\n|期望数量|$)', content, re.DOTALL)
            reason = reason_match.group(1).strip() if reason_match else "未说明"
            
            # 记录LLM交互
            llm_logger = get_logger()
            if llm_logger:
                llm_logger.log_negotiation_call(
                    round_number=self.round_number,
                    stage="details-opinion",
                    agent=agent,
                    input_prompt=prompt,
                    raw_output=content,
                    model=model_name,
                    temperature=temperature,
                    duration=duration,
                    success=True,
                    processed_data={
                        "has_objection": has_objection,
                        "expected_amount": expected_amount,
                        "allocated_amount": allocated_amount
                    }
                )
            
            return {
                "has_objection": has_objection,
                "objection_reason": reason if has_objection else "",
                "expected_amount": expected_amount,
                "allocated_amount": allocated_amount,
                "raw_response": content
            }
            
        except Exception as e:
            print(f"  获取{agent['family_name']}家意见失败: {str(e)}")
            return {
                "has_objection": False,
                "objection_reason": "",
                "expected_amount": allocated_amount,
                "allocated_amount": allocated_amount,
                "raw_response": "获取失败"
            }
    
    def _negotiate_disputed_allocations(self, allocation: Dict[int, Dict[str, float]],
                                      opinions: Dict[int, Dict[str, Any]],
                                      framework: Dict[str, Any]) -> Dict[int, Dict[str, float]]:
        """协商有争议的分配"""
        
        # 识别异议者和他们的诉求
        disputed_agents = [(aid, op) for aid, op in opinions.items() if op.get("has_objection")]
        
        if not disputed_agents:
            return allocation
        
        # 计算总的调整需求
        total_adjustment_need = sum(
            op["expected_amount"] - op["allocated_amount"] 
            for _, op in disputed_agents
        )
        
        print(f"    总调整需求：{total_adjustment_need:+.1f}单位")
        
        # 如果总需求为正（要求增加），需要从其他家庭调剂
        if abs(total_adjustment_need) < 0.5:
            print("    调整幅度很小，接受现有方案")
            return allocation
        
        # 进行一轮调整协商
        adjusted_allocation = self._mediate_allocation_adjustment(
            allocation, disputed_agents, total_adjustment_need, framework
        )
        
        return adjusted_allocation
    
    def _mediate_allocation_adjustment(self, allocation: Dict[int, Dict[str, float]],
                                     disputed_agents: List[Tuple[int, Dict[str, Any]]],
                                     total_need: float,
                                     framework: Dict[str, Any]) -> Dict[int, Dict[str, float]]:
        """调解分配调整"""
        
        adjusted = copy.deepcopy(allocation)
        
        # 限制调整幅度：最多调整10%的总资源
        max_adjustment = self.total_grain * 0.1
        actual_adjustment = min(abs(total_need), max_adjustment)
        
        if total_need > 0:  # 有人要求增加
            # 方案1：从满意者中匀出一部分
            satisfied_agents = [agent for agent in self.agents 
                              if agent["id"] not in [aid for aid, _ in disputed_agents]]
            
            if satisfied_agents:
                # 按比例从满意者处调出
                donors = []
                for agent in satisfied_agents:
                    aid = agent["id"]
                    current = sum(adjusted[aid].values())
                    survival = sum(self.survival_needs.get(aid, {}).values())
                    surplus = current - survival
                    if surplus > 1.0:  # 有余量才能调出
                        donors.append((aid, surplus))
                
                if donors:
                    total_available = sum(s for _, s in donors)
                    actual_transfer = min(actual_adjustment, total_available * 0.3)  # 最多转30%的余量
                    
                    # 从donor调出
                    for aid, surplus in donors:
                        transfer_amount = (surplus / total_available) * actual_transfer
                        adjusted[aid]["grain"] -= transfer_amount
                    
                    # 分给异议者
                    for aid, opinion in disputed_agents:
                        requested_increase = opinion["expected_amount"] - opinion["allocated_amount"]
                        if requested_increase > 0:
                            share = (requested_increase / total_need) * actual_transfer
                            adjusted[aid]["grain"] += share
                    
                    print(f"    调解方案：从{len(donors)}个余量家庭调出{actual_transfer:.1f}单位")
                    
                    # 记录调解决策
                    if self.logger:
                        self.logger.log_decision(
                            decision_type="allocation_mediation",
                            decision_content={
                                "transferred_amount": actual_transfer,
                                "donors": [aid for aid, _ in donors],
                                "recipients": [aid for aid, _ in disputed_agents]
                            },
                            supporters=[aid for aid, _ in donors],
                            opponents=[]
                        )
        
        return adjusted
    
    def _validate_and_optimize(self, allocation: Dict[int, Dict[str, float]]) -> Dict[int, Dict[str, float]]:
        """验证和优化分配方案"""
        
        # 验证总量
        total_allocated = sum(sum(agent_alloc.values()) for agent_alloc in allocation.values())
        
        if abs(total_allocated - self.total_grain) > 0.01:
            # 需要调整
            adjustment_factor = self.total_grain / total_allocated
            # 记录归一化
            if self.logger:
                try:
                    self.logger.log_decision(
                        decision_type="normalization_applied",
                        decision_content={
                            "factor": adjustment_factor,
                            "before_total": total_allocated,
                            "after_total": self.total_grain
                        },
                        supporters=[agent["id"] for agent in self.agents],
                        opponents=[]
                    )
                except Exception:
                    pass
            for agent_id in allocation:
                for resource in allocation[agent_id]:
                    allocation[agent_id][resource] *= adjustment_factor
        
        return allocation

    def _integerize_allocation(self, allocation: Dict[int, Dict[str, float]], enforce_min_survival: bool = True) -> Dict[int, Dict[str, float]]:
        """将最终分配整数化（最大余数法 + 生存保底）
        
        步骤：
        1) 以每户floor为基准；
        2) 若启用保底，则将每户基准提升到ceil(生存需求)；
        3) 计算目标总量=四舍五入当前总量；
        4) 若基准和<目标，按小数部分由大到小+1；若基准和>目标，按小数部分由小到大-1，但不低于保底。
        """
        # 只处理 grain 这一个资源
        agent_ids = [agent["id"] for agent in self.agents]
        real_values: Dict[int, float] = {aid: float(allocation.get(aid, {}).get("grain", 0.0)) for aid in agent_ids}
        fractional: Dict[int, float] = {}
        base: Dict[int, int] = {}
        min_need: Dict[int, int] = {}
        
        for aid in agent_ids:
            val = real_values.get(aid, 0.0)
            base[aid] = math.floor(val)
            fractional[aid] = val - base[aid]
            if enforce_min_survival:
                need = sum(self.survival_needs.get(aid, {}).values())
                min_need[aid] = int(math.ceil(need)) if need > 0 else 0
            else:
                min_need[aid] = 0
        
        # 应用保底
        for aid in agent_ids:
            if base[aid] < min_need[aid]:
                base[aid] = min_need[aid]
                fractional[aid] = 0.0
        
        current_sum = sum(real_values.values())
        target_total = int(round(current_sum))
        base_sum = sum(base.values())
        
        # 如果基准和小于目标，按小数部分从大到小加1
        if base_sum < target_total:
            need = target_total - base_sum
            order = sorted(agent_ids, key=lambda a: fractional[a], reverse=True)
            i = 0
            while need > 0 and i < len(order):
                aid = order[i]
                base[aid] += 1
                need -= 1
                i += 1
        # 如果基准和大于目标，按小数部分从小到大减1（不低于保底）
        elif base_sum > target_total:
            excess = base_sum - target_total
            order = sorted(agent_ids, key=lambda a: fractional[a])
            i = 0
            while excess > 0 and i < len(order):
                aid = order[i]
                if base[aid] > min_need[aid]:
                    base[aid] -= 1
                    excess -= 1
                i += 1
        
        # 组装新allocation
        new_alloc: Dict[int, Dict[str, float]] = {aid: {"grain": float(base.get(aid, 0))} for aid in agent_ids}
        
        # 日志记录
        if self.logger:
            try:
                diff = {aid: base[aid] - int(round(real_values.get(aid, 0.0))) for aid in agent_ids}
                self.logger.log_decision(
                    decision_type="integerization_applied",
                    decision_content={
                        "method": "largest_remainder_with_min",
                        "before_total": current_sum,
                        "after_total": sum(base.values()),
                        "changes": diff
                    },
                    supporters=[aid for aid in agent_ids],
                    opponents=[]
                )
            except Exception:
                pass
        
        return new_alloc
    
    def _finalize_proposal(self, detailed_proposal: Dict[int, Dict[str, float]]) -> Dict[int, Dict[str, float]]:
        """阶段4：最终确认和微调（包含LLM驱动的多轮确认）"""
        self.current_stage = "finalization"
        
        # 开始阶段日志
        if self.logger:
            try:
                self.logger.start_stage("finalization", [agent["id"] for agent in self.agents])
            except Exception:
                pass
        
        print("\n   【第1轮确认】征求各家庭最终意见...")
        
        # 第一轮反馈
        first_feedback = self._collect_final_confirmation(detailed_proposal, round_num=1)
        
        # 记录第一轮反馈
        self._log_feedback(first_feedback, "第1轮确认")
        
        current_proposal = detailed_proposal
        
        # 🎯 如果有不满意者，进行第2轮微调协商
        unsatisfied = [aid for aid, fb in first_feedback.items() 
                      if fb.get("satisfaction_level", 3) < 3]
        
        if unsatisfied and len(unsatisfied) <= len(self.agents) // 2:  # 少数人不满意
            print(f"\n   发现{len(unsatisfied)}家不满意，进行第2轮微调协商...")
            
            # 🎯 让不满意者提出具体调整方案
            adjustment_proposals = self._collect_adjustment_proposals(
                current_proposal, first_feedback, unsatisfied
            )
            
            # 🎯 让其他家庭对调整方案投票
            if adjustment_proposals:
                print("\n   其他家庭对微调方案进行投票...")
                adjusted_proposal = self._vote_on_adjustments(
                    current_proposal, adjustment_proposals
                )
                
                # 第2轮确认
                print("\n   【第2轮确认】再次征求意见...")
                second_feedback = self._collect_final_confirmation(adjusted_proposal, round_num=2)
                self._log_feedback(second_feedback, "第2轮确认")
                
                current_proposal = adjusted_proposal
            else:
                print("   未能形成有效调整方案，维持原方案")
        elif len(unsatisfied) > len(self.agents) // 2:  # 多数人不满意
            print(f"\n   ⚠️ 多数家庭（{len(unsatisfied)}家）不满意，但已达协商轮次上限")
            print("   维持当前方案并记录分歧")
            if self.logger:
                self.logger.log_conflict(
                    conflict_topic="最终方案分歧严重",
                    conflicting_parties=unsatisfied,
                    conflict_description=f"多数家庭不满意，但协商未达成更好方案"
                )
        else:
            print("   ✓ 各家庭基本满意，无需微调")
        
        # 整数化（最大余数法 + 生存保底）
        try:
            integerized = self._integerize_allocation(current_proposal, enforce_min_survival=True)
            current_proposal = integerized
        except Exception:
            pass
        
        print("\n   ✓ 分配方案最终确定！")
        print("\n   最终分配结果：")
        for agent in self.agents:
            aid = agent["id"]
            amount = sum(current_proposal.get(aid, {}).values())
            print(f"    {agent['family_name']}家：{amount:.0f}单位")
        
        # 结束阶段日志
        try:
            # 使用最后一轮的反馈计算共识度
            final_feedback = first_feedback if not unsatisfied or len(unsatisfied) > len(self.agents) // 2 else second_feedback
            levels = [fb.get("satisfaction_level", 0.0) for fb in final_feedback.values()]
            avg_level = sum(levels) / len(levels) if levels else 0.0
            self.final_average_satisfaction = avg_level
            ok_ratio = sum(1 for l in levels if l >= 3.0) / len(levels) if levels else 0.0
            if self.logger:
                self.logger.end_stage(
                    stage_outcome="最终确认完成",
                    consensus_level=ok_ratio
                )
        except Exception:
            pass
        
        return current_proposal
    
    def _collect_final_confirmation(self, proposal: Dict[int, Dict[str, float]], 
                                   round_num: int = 1) -> Dict[int, Dict[str, Any]]:
        """收集最终确认反馈（LLM驱动）"""
        feedback = {}
        
        for agent in self.agents:
            agent_id = agent["id"]
            agent_allocation = proposal.get(agent_id, {})
            total_allocation = sum(agent_allocation.values())
            survival_need = sum(self.survival_needs.get(agent_id, {}).values())
            
            # 使用LLM获取最终确认意见
            confirmation = self._get_final_confirmation_llm(
                agent, total_allocation, survival_need, proposal, round_num
            )
            
            feedback[agent_id] = confirmation
        
        return feedback
    
    def _get_final_confirmation_llm(self, agent: Dict[str, Any], allocated_amount: float,
                                   survival_need: float, all_allocations: Dict[int, Dict[str, float]],
                                   round_num: int) -> Dict[str, Any]:
        """使用LLM获取最终确认意见"""
        
        # 构建其他家庭分配情况
        other_info = ""
        for other_agent in self.agents:
            if other_agent["id"] != agent["id"]:
                other_amount = sum(all_allocations.get(other_agent["id"], {}).values())
                other_info += f"- {other_agent['family_name']}家：{other_amount:.0f}单位\n"
        
        prompt = f"""你是{agent['family_name']}家庭的代表，价值观为{agent['value_type']}。

经过多轮协商，现在需要对最终分配方案进行第{round_num}轮确认。

你家的最终分配：
- 获得资源：{allocated_amount:.0f}单位粮食
- 生存需求：{survival_need:.0f}单位
- 盈余/缺口：{allocated_amount - survival_need:+.0f}单位

其他家庭的分配：
{other_info}

请根据你的价值观评价这个最终方案：
1. 你的满意程度（1-5分，1=非常不满意，3=可以接受，5=非常满意）
2. 如果满意度低于3分，请说明你的主要顾虑（不超过30字）
3. 如果有顾虑，你希望如何调整？（简要说明）

请按以下格式回答：
满意度：[1-5的数字]
顾虑：[你的顾虑或"无"]
调整建议：[你的建议或"无"]
"""
        
        model_name = "deepseek-v3"
        temperature = 0.8
        
        try:
            start_time = time.time()
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "你是一个参与社区资源协商的家庭代表。现在是最终确认阶段，请真实表达你对最终方案的看法。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=250
            )
            duration = time.time() - start_time
            
            content = response.choices[0].message.content
            
            # 解析满意度
            satisfaction_level = 3.0  # 默认值
            satisfaction_match = re.search(r'满意度[：:]\s*([1-5])', content)
            if satisfaction_match:
                try:
                    satisfaction_level = float(satisfaction_match.group(1))
                except:
                    pass
            
            # 提取顾虑
            concern_match = re.search(r'顾虑[：:]\s*(.+?)(?=\n|调整建议|$)', content, re.DOTALL)
            concern = concern_match.group(1).strip() if concern_match else ""
            has_concern = concern and concern != "无" and satisfaction_level < 3
            
            # 提取调整建议
            adjustment_match = re.search(r'调整建议[：:]\s*(.+?)$', content, re.DOTALL)
            adjustment_suggestion = adjustment_match.group(1).strip() if adjustment_match else ""
            
            # 记录LLM交互
            llm_logger = get_logger()
            if llm_logger:
                llm_logger.log_negotiation_call(
                    round_number=self.round_number,
                    stage=f"finalization-round{round_num}",
                    agent=agent,
                    input_prompt=prompt,
                    raw_output=content,
                    model=model_name,
                    temperature=temperature,
                    duration=duration,
                    success=True,
                    processed_data={
                        "satisfaction_level": satisfaction_level,
                        "has_concern": has_concern,
                        "concern": concern
                    }
                )
            
            return {
                "satisfaction_level": satisfaction_level,
                "has_concerns": has_concern,
                "concern": concern if has_concern else "",
                "adjustment_suggestion": adjustment_suggestion if has_concern else "",
                "raw_response": content
            }
            
        except Exception as e:
            print(f"  获取{agent['family_name']}家确认意见失败: {str(e)}")
            # 使用基于规则的fallback
            satisfaction = 3.0
            if allocated_amount >= survival_need * 1.1:
                satisfaction = 4.0
            elif allocated_amount < survival_need:
                satisfaction = 2.0
            
            return {
                "satisfaction_level": satisfaction,
                "has_concerns": satisfaction < 3,
                "concern": "分配不足" if satisfaction < 3 else "",
                "adjustment_suggestion": "",
                "raw_response": "获取失败"
            }
    
    def _log_feedback(self, feedback: Dict[int, Dict[str, Any]], stage_name: str):
        """记录反馈到日志"""
        if not self.logger:
            return
        
        for agent in self.agents:
            aid = agent["id"]
            fb = feedback.get(aid, {})
            self.logger.log_discussion_turn(
                speaker_id=aid,
                speaker_name=agent["family_name"],
                speaker_value_type=agent["value_type"],
                content=f"满意度：{fb.get('satisfaction_level', 0)}, {fb.get('concern', '无顾虑')}",
                speech_type="final_confirmation",
                target_topic=stage_name
            )
    
    def _collect_adjustment_proposals(self, current_allocation: Dict[int, Dict[str, float]],
                                    feedback: Dict[int, Dict[str, Any]],
                                    unsatisfied_agents: List[int]) -> List[Dict[str, Any]]:
        """收集不满意家庭的调整提案（LLM驱动）"""
        
        proposals = []
        
        for agent_id in unsatisfied_agents:
            agent = next((a for a in self.agents if a["id"] == agent_id), None)
            if not agent:
                continue
            
            fb = feedback.get(agent_id, {})
            current_amount = sum(current_allocation.get(agent_id, {}).values())
            
            # 简化处理：直接从反馈中提取调整建议
            adjustment_text = fb.get("adjustment_suggestion", "")
            
            if adjustment_text and adjustment_text != "无":
                # 尝试从建议中提取期望的调整量
                # 例如："希望增加5单位" 或 "调整到30单位"
                amount_match = re.search(r'(\d+)', adjustment_text)
                if amount_match:
                    requested_change = float(amount_match.group(1))
                    
                    # 判断是增量还是目标值
                    if "增加" in adjustment_text or "多" in adjustment_text:
                        target_amount = current_amount + requested_change
                    else:
                        target_amount = requested_change
                    
                    # 限制调整幅度（最多±20%）
                    max_change = current_amount * 0.2
                    target_amount = max(current_amount - max_change, 
                                      min(target_amount, current_amount + max_change))
                    
                    proposals.append({
                        "agent_id": agent_id,
                        "agent_name": agent["family_name"],
                        "current_amount": current_amount,
                        "target_amount": target_amount,
                        "reason": fb.get("concern", ""),
                        "adjustment_text": adjustment_text
                    })
                    
                    print(f"    {agent['family_name']}家提案：{current_amount:.0f} → {target_amount:.0f}单位")
        
        return proposals
    
    def _vote_on_adjustments(self, current_allocation: Dict[int, Dict[str, float]],
                           proposals: List[Dict[str, Any]]) -> Dict[int, Dict[str, float]]:
        """让其他家庭对调整提案投票（简化处理）"""
        
        if not proposals:
            return current_allocation
        
        adjusted = copy.deepcopy(current_allocation)
        
        # 简化投票：如果提案总需求合理，则按比例满足
        total_increase_needed = sum(
            max(0, p["target_amount"] - p["current_amount"]) 
            for p in proposals
        )
        
        # 找出可以贡献的家庭（高于平均水平的）
        avg_allocation = self.total_grain / len(self.agents)
        potential_donors = [
            (agent["id"], sum(adjusted[agent["id"]].values()) - avg_allocation)
            for agent in self.agents
            if agent["id"] not in [p["agent_id"] for p in proposals]
            and sum(adjusted[agent["id"]].values()) > avg_allocation * 1.1
        ]
        
        if not potential_donors:
            print("    无可调配资源，维持原方案")
            return current_allocation
        
        total_available = sum(surplus for _, surplus in potential_donors)
        actual_transfer = min(total_increase_needed, total_available * 0.5)  # 最多转50%的余量
        
        if actual_transfer > 0.5:
            # 从donor调出
            for donor_id, surplus in potential_donors:
                transfer_out = (surplus / total_available) * actual_transfer
                adjusted[donor_id]["grain"] -= transfer_out
            
            # 分给提案者
            for proposal in proposals:
                increase_needed = max(0, proposal["target_amount"] - proposal["current_amount"])
                if increase_needed > 0:
                    share = (increase_needed / total_increase_needed) * actual_transfer
                    adjusted[proposal["agent_id"]]["grain"] += share
            
            print(f"    ✓ 调整通过：转移{actual_transfer:.1f}单位资源")
            
            # 记录决策
            if self.logger:
                self.logger.log_decision(
                    decision_type="adjustment_voted_approved",
                    decision_content={
                        "transferred_amount": actual_transfer,
                        "proposals": proposals,
                        "donors": [did for did, _ in potential_donors]
                    },
                    supporters=[did for did, _ in potential_donors],
                    opponents=[]
                )
        else:
            print("    调整幅度过小，维持原方案")
        
        return adjusted
    
    def _create_fallback_proposal(self) -> Dict[int, Dict[str, float]]:
        """创建回退分配方案（简单平均分配）"""
        per_family = self.total_grain / len(self.agents)
        
        return {
            agent["id"]: {"grain": per_family}
            for agent in self.agents
        }
    
    def _create_negotiation_data(self, success: bool, method: str) -> Dict[str, Any]:
        """创建协商过程数据"""
        return {
            "success": success,
            "method": method,
            "stages_completed": list(self.stage_results.keys()),
            "conversation_rounds": len(self.conversation_history),
            "consensus_items": len(self.consensus_items),
            "final_stage": self.current_stage,
            "stage_results": self.stage_results
        }


def collaborative_negotiation_distribution(
    total_resources: Dict[str, float],
    agents: List[Dict[str, Any]],
    survival_needs: Dict[int, Dict[str, float]],
    round_number: int = 1,
    previous_distribution: Dict[int, Dict[str, float]] = None,
    max_negotiation_rounds: int = 4,
    experiment_id: str = None
) -> Dict[int, Dict[str, float]]:
    """协作式协商分配的主入口函数
    
    参数:
        total_resources: 总资源字典
        agents: 代理列表
        survival_needs: 生存需求字典
        round_number: 当前轮数
        previous_distribution: 上一轮分配结果（暂未使用）
        max_negotiation_rounds: 最大协商轮数（暂未使用）
        experiment_id: 实验ID，用于统一所有轮次的日志
        
    返回:
        最终分配结果字典
    """
    
    try:
        # 创建协商机制实例
        negotiation = CollaborativeNegotiation(
            agents=agents,
            total_resources=total_resources,
            survival_needs=survival_needs,
            round_number=round_number,
            experiment_id=experiment_id
        )
        
        # 运行协商流程
        final_allocation, negotiation_data = negotiation.run_collaborative_negotiation()
        
        # 打印结果摘要
        print(f"\n 协商结果摘要：")
        print(f"   成功完成：{negotiation_data['success']}")
        print(f"   方法：{negotiation_data['method']}")
        print(f"   完成阶段：{negotiation_data['stages_completed']}")
        
        return final_allocation
        
    except Exception as e:
        print(f"\n 协商分配失败，使用平均分配作为回退方案: {str(e)}")
        
        # 回退到平均分配
        num_families = len(agents)
        if num_families == 0:
            return {}
        
        per_family_amount = total_resources.get("grain", 0) / num_families
        
        return {
            agent["id"]: {"grain": per_family_amount}
            for agent in agents
        }
