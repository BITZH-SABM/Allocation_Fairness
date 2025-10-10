"""
协商讨论记录系统
用于保存和分析协商过程中的所有讨论内容、决策过程和结果
"""
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class DiscussionTurn:
    """单次发言记录"""
    turn_id: str                    # 发言ID
    speaker_id: int                 # 发言者ID  
    speaker_name: str               # 发言者家庭名
    speaker_value_type: str         # 发言者价值观
    stage: str                      # 协商阶段
    round_number: int               # 轮次
    timestamp: str                  # 时间戳
    content: str                    # 发言内容
    speech_type: str                # 发言类型：proposal/response/objection/agreement/compromise
    target_topic: str               # 讨论主题
    references: List[str]           # 引用的其他发言ID
    proposal_changes: Optional[Dict] # 提案变化（如果有）
    sentiment: str                  # 情感倾向：positive/neutral/negative
    keywords: List[str]             # 关键词提取

@dataclass 
class StageRecord:
    """阶段记录"""
    stage_name: str                 # 阶段名称
    start_time: str                 # 开始时间
    end_time: str                   # 结束时间
    duration: float                 # 持续时间（秒）
    participants: List[int]         # 参与者ID列表
    discussion_turns: List[DiscussionTurn]  # 讨论轮次
    decisions_made: List[Dict]      # 达成的决定
    consensus_level: float          # 共识程度（0-1）
    conflicts: List[Dict]           # 冲突记录
    stage_outcome: str              # 阶段结果

@dataclass
class NegotiationSession:
    """完整协商会话记录"""
    session_id: str                 # 会话ID
    round_number: int               # 轮数
    start_time: str                 # 开始时间
    end_time: str                   # 结束时间
    total_duration: float           # 总持续时间
    participants: List[Dict]        # 参与者信息
    total_resources: Dict[str, float]  # 总资源
    survival_needs: Dict[int, Dict[str, float]]  # 生存需求
    
    # 协商过程
    stages: List[StageRecord]       # 各阶段记录
    final_allocation: Dict[int, Dict[str, float]]  # 最终分配
    success: bool                   # 是否成功
    failure_reason: Optional[str]   # 失败原因
    
    # 统计数据
    total_turns: int                # 总发言次数
    consensus_reached: bool         # 是否达成共识
    average_satisfaction: float     # 平均满意度
    
    # 元数据
    metadata: Dict[str, Any]        # 其他元数据


class NegotiationLogger:
    """协商过程记录器"""
    
    def __init__(self, session_id: str, output_dir: str = "negotiation_logs"):
        """初始化记录器
        
        参数:
            session_id: 会话ID
            output_dir: 输出目录
        """
        self.session_id = session_id
        # 根目录
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # 本次会话独立子目录
        self.session_dir = self.output_dir / f"session_{session_id}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        # 当前会话记录
        self.current_session: Optional[NegotiationSession] = None
        self.current_stage: Optional[StageRecord] = None
        self.turn_counter = 0
        
        # 实时记录文件（置于会话目录下）
        self.log_file = self.session_dir / "live.jsonl"
        
    def start_session(self, round_number: int, participants: List[Dict], 
                     total_resources: Dict[str, float], 
                     survival_needs: Dict[int, Dict[str, float]]):
        """开始新的协商会话"""
        self.current_session = NegotiationSession(
            session_id=self.session_id,
            round_number=round_number,
            start_time=datetime.now().isoformat(),
            end_time="",
            total_duration=0.0,
            participants=participants,
            total_resources=total_resources,
            survival_needs=survival_needs,
            stages=[],
            final_allocation={},
            success=False,
            failure_reason=None,
            total_turns=0,
            consensus_reached=False,
            average_satisfaction=0.0,
            metadata={}
        )
        
        # 记录会话开始
        self._write_live_log("session_start", {
            "session_id": self.session_id,
            "timestamp": self.current_session.start_time,
            "participants": participants,
            "total_resources": total_resources
        })
        
        print(f"📝 开始记录协商会话: {self.session_id}")
    
    def start_stage(self, stage_name: str, participants: List[int]):
        """开始新的协商阶段"""
        if self.current_stage:
            self.end_stage()
        
        self.current_stage = StageRecord(
            stage_name=stage_name,
            start_time=datetime.now().isoformat(),
            end_time="",
            duration=0.0,
            participants=participants,
            discussion_turns=[],
            decisions_made=[],
            consensus_level=0.0,
            conflicts=[],
            stage_outcome=""
        )
        
        # 记录阶段开始
        self._write_live_log("stage_start", {
            "stage_name": stage_name,
            "timestamp": self.current_stage.start_time,
            "participants": participants
        })
        
        print(f"  📋 开始阶段: {stage_name}")
    
    def log_discussion_turn(self, speaker_id: int, speaker_name: str, 
                           speaker_value_type: str, content: str,
                           speech_type: str = "statement",
                           target_topic: str = "",
                           references: List[str] = None,
                           proposal_changes: Dict = None):
        """记录一次讨论发言"""
        if not self.current_stage:
            raise ValueError("必须先开始一个阶段才能记录发言")
        
        self.turn_counter += 1
        turn_id = f"turn_{self.session_id}_{self.turn_counter:04d}"
        
        turn = DiscussionTurn(
            turn_id=turn_id,
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            speaker_value_type=speaker_value_type,
            stage=self.current_stage.stage_name,
            round_number=self.current_session.round_number,
            timestamp=datetime.now().isoformat(),
            content=content,
            speech_type=speech_type,
            target_topic=target_topic,
            references=references or [],
            proposal_changes=proposal_changes,
            sentiment=self._analyze_sentiment(content),
            keywords=self._extract_keywords(content)
        )
        
        self.current_stage.discussion_turns.append(turn)
        
        # 实时记录
        self._write_live_log("discussion_turn", asdict(turn))
        
        print(f"    💬 记录发言: {speaker_name}家 ({speech_type})")
        return turn_id
    
    def log_decision(self, decision_type: str, decision_content: Dict, 
                    supporters: List[int], opponents: List[int]):
        """记录决策结果"""
        if not self.current_stage:
            return
        
        decision = {
            "timestamp": datetime.now().isoformat(),
            "type": decision_type,
            "content": decision_content,
            "supporters": supporters,
            "opponents": opponents,
            "consensus_level": len(supporters) / (len(supporters) + len(opponents)) if (len(supporters) + len(opponents)) > 0 else 0
        }
        
        self.current_stage.decisions_made.append(decision)
        
        # 实时记录
        self._write_live_log("decision", decision)
        
        print(f"    ⚖️ 记录决策: {decision_type}")
    
    def log_conflict(self, conflict_topic: str, conflicting_parties: List[int], 
                    conflict_description: str, resolution_status: str = "unresolved"):
        """记录冲突"""
        if not self.current_stage:
            return
        
        conflict = {
            "timestamp": datetime.now().isoformat(),
            "topic": conflict_topic,
            "parties": conflicting_parties,
            "description": conflict_description,
            "status": resolution_status
        }
        
        self.current_stage.conflicts.append(conflict)
        
        # 实时记录
        self._write_live_log("conflict", conflict)
        
        print(f"    ⚠️ 记录冲突: {conflict_topic}")
    
    def end_stage(self, stage_outcome: str = "", consensus_level: float = 0.0):
        """结束当前阶段"""
        if not self.current_stage:
            return
        
        self.current_stage.end_time = datetime.now().isoformat()
        self.current_stage.duration = self._calculate_duration(
            self.current_stage.start_time, 
            self.current_stage.end_time
        )
        self.current_stage.stage_outcome = stage_outcome
        self.current_stage.consensus_level = consensus_level
        
        # 添加到会话记录
        self.current_session.stages.append(self.current_stage)
        
        # 实时记录
        self._write_live_log("stage_end", {
            "stage_name": self.current_stage.stage_name,
            "duration": self.current_stage.duration,
            "outcome": stage_outcome,
            "consensus_level": consensus_level,
            "turns_count": len(self.current_stage.discussion_turns),
            "decisions_count": len(self.current_stage.decisions_made),
            "conflicts_count": len(self.current_stage.conflicts)
        })
        
        print(f"  ✅ 阶段结束: {self.current_stage.stage_name} (用时: {self.current_stage.duration:.1f}秒)")
        self.current_stage = None
    
    def end_session(self, final_allocation: Dict[int, Dict[str, float]], 
                   success: bool, failure_reason: str = None,
                   average_satisfaction: float = 0.0):
        """结束协商会话"""
        if not self.current_session:
            return
        
        # 结束当前阶段（如果有）
        if self.current_stage:
            self.end_stage()
        
        self.current_session.end_time = datetime.now().isoformat()
        self.current_session.total_duration = self._calculate_duration(
            self.current_session.start_time,
            self.current_session.end_time
        )
        self.current_session.final_allocation = final_allocation
        self.current_session.success = success
        self.current_session.failure_reason = failure_reason
        self.current_session.total_turns = self.turn_counter
        self.current_session.average_satisfaction = average_satisfaction
        
        # 计算整体统计
        self.current_session.consensus_reached = any(
            stage.consensus_level > 0.8 for stage in self.current_session.stages
        )
        
        # 保存完整记录
        self._save_complete_session()
        
        # 实时记录会话结束
        self._write_live_log("session_end", {
            "success": success,
            "total_duration": self.current_session.total_duration,
            "total_turns": self.turn_counter,
            "consensus_reached": self.current_session.consensus_reached
        })
        
        print(f"📝 协商会话记录完成: {self.session_id}")
        print(f"   总用时: {self.current_session.total_duration:.1f}秒")
        print(f"   总发言: {self.turn_counter}次")
        print(f"   成功: {success}")
    
    def _write_live_log(self, event_type: str, data: Dict):
        """写入实时日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "session_id": self.session_id,
            "data": data
        }
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    def _save_complete_session(self):
        """保存完整的会话记录"""
        # JSON格式（置于会话目录下）
        json_file = self.session_dir / "complete.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(self.current_session), f, ensure_ascii=False, indent=2)
        
        # 生成可读的文本摘要（置于会话目录下）
        summary_file = self.session_dir / "summary.txt"
        self._generate_text_summary(summary_file)
        
        print(f"   📄 完整记录已保存: {json_file}")
        print(f"   📄 摘要已保存: {summary_file}")
    
    def _generate_text_summary(self, summary_file: Path):
        """生成可读的文本摘要"""
        with open(summary_file, 'w', encoding='utf-8') as f:
            session = self.current_session
            
            f.write(f"协商会话摘要报告\n")
            f.write(f"{'='*50}\n\n")
            
            f.write(f"会话ID: {session.session_id}\n")
            f.write(f"轮数: {session.round_number}\n")
            f.write(f"开始时间: {session.start_time}\n")
            f.write(f"结束时间: {session.end_time}\n")
            f.write(f"总用时: {session.total_duration:.1f}秒\n")
            f.write(f"成功: {session.success}\n")
            f.write(f"达成共识: {session.consensus_reached}\n\n")
            
            f.write(f"参与者:\n")
            for participant in session.participants:
                f.write(f"  - {participant['family_name']}家 ({participant['value_type']})\n")
            f.write(f"\n")
            
            f.write(f"资源总量: {session.total_resources}\n\n")
            
            # 各阶段摘要
            f.write(f"协商阶段摘要:\n")
            f.write(f"-" * 30 + "\n")
            
            for i, stage in enumerate(session.stages, 1):
                f.write(f"\n阶段{i}: {stage.stage_name}\n")
                f.write(f"  用时: {stage.duration:.1f}秒\n")
                f.write(f"  发言次数: {len(stage.discussion_turns)}\n")
                f.write(f"  决策数: {len(stage.decisions_made)}\n")
                f.write(f"  冲突数: {len(stage.conflicts)}\n")
                f.write(f"  共识程度: {stage.consensus_level:.2f}\n")
                f.write(f"  结果: {stage.stage_outcome}\n")
                
                # 主要发言摘要
                if stage.discussion_turns:
                    f.write(f"  主要讨论:\n")
                    for turn in stage.discussion_turns[:3]:  # 只显示前3个发言
                        f.write(f"    {turn.speaker_name}: {turn.content[:100]}...\n")
            
            # 最终分配
            f.write(f"\n最终分配结果:\n")
            f.write(f"-" * 30 + "\n")
            for agent_id, allocation in session.final_allocation.items():
                agent_name = next(p['family_name'] for p in session.participants if p['id'] == agent_id)
                total = sum(allocation.values())
                f.write(f"  {agent_name}家: {total:.2f}\n")
    
    def _analyze_sentiment(self, content: str) -> str:
        """简单的情感分析"""
        positive_words = ["同意", "支持", "赞成", "好", "满意", "公平", "合理"]
        negative_words = ["反对", "不同意", "不满", "不公平", "不合理", "问题", "担心"]
        
        positive_count = sum(1 for word in positive_words if word in content)
        negative_count = sum(1 for word in negative_words if word in content)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _extract_keywords(self, content: str) -> List[str]:
        """提取关键词"""
        keywords = []
        
        # 简单的关键词提取
        key_terms = [
            "分配", "资源", "公平", "需求", "贡献", "劳动力", "家庭", "成员",
            "生存", "基本", "平等", "按需", "按劳", "协商", "妥协", "同意"
        ]
        
        for term in key_terms:
            if term in content:
                keywords.append(term)
        
        return keywords
    
    def _calculate_duration(self, start_time: str, end_time: str) -> float:
        """计算持续时间（秒）"""
        start = datetime.fromisoformat(start_time)
        end = datetime.fromisoformat(end_time)
        return (end - start).total_seconds()


class NegotiationAnalyzer:
    """协商记录分析器"""
    
    def __init__(self, log_directory: str = "negotiation_logs"):
        self.log_dir = Path(log_directory)
    
    def analyze_session(self, session_id: str) -> Dict[str, Any]:
        """分析单个会话"""
        # 兼容新版目录结构：session_{id}/complete.json
        json_file = self.log_dir / f"session_{session_id}" / "complete.json"
        
        if not json_file.exists():
            # 兼容旧版扁平命名
            legacy = self.log_dir / f"session_{session_id}_complete.json"
            if legacy.exists():
                json_file = legacy
            else:
                raise FileNotFoundError(f"会话记录文件不存在: {json_file}")
        
        with open(json_file, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
        
        return self._generate_analysis(session_data)
    
    def _generate_analysis(self, session_data: Dict) -> Dict[str, Any]:
        """生成分析报告"""
        analysis = {
            "basic_stats": self._analyze_basic_stats(session_data),
            "communication_patterns": self._analyze_communication(session_data),
            "consensus_evolution": self._analyze_consensus(session_data),
            "value_conflicts": self._analyze_value_conflicts(session_data),
            "efficiency_metrics": self._analyze_efficiency(session_data)
        }
        
        return analysis
    
    def _analyze_basic_stats(self, session_data: Dict) -> Dict:
        """基础统计分析"""
        return {
            "total_duration": session_data["total_duration"],
            "total_turns": session_data["total_turns"],
            "stages_count": len(session_data["stages"]),
            "success_rate": 1 if session_data["success"] else 0,
            "consensus_reached": session_data["consensus_reached"]
        }
    
    def _analyze_communication(self, session_data: Dict) -> Dict:
        """沟通模式分析"""
        all_turns = []
        for stage in session_data["stages"]:
            all_turns.extend(stage["discussion_turns"])
        
        # 按价值观分组发言次数
        value_type_counts = {}
        for turn in all_turns:
            vt = turn["speaker_value_type"]
            value_type_counts[vt] = value_type_counts.get(vt, 0) + 1
        
        # 发言类型分布
        speech_type_counts = {}
        for turn in all_turns:
            st = turn["speech_type"]
            speech_type_counts[st] = speech_type_counts.get(st, 0) + 1
        
        return {
            "turns_by_value_type": value_type_counts,
            "speech_type_distribution": speech_type_counts,
            "average_turn_length": sum(len(turn["content"]) for turn in all_turns) / len(all_turns) if all_turns else 0
        }
    
    def _analyze_consensus(self, session_data: Dict) -> Dict:
        """共识演化分析"""
        consensus_evolution = []
        
        for stage in session_data["stages"]:
            consensus_evolution.append({
                "stage": stage["stage_name"],
                "consensus_level": stage["consensus_level"],
                "decisions_made": len(stage["decisions_made"]),
                "conflicts": len(stage["conflicts"])
            })
        
        return {
            "evolution": consensus_evolution,
            "final_consensus": session_data["consensus_reached"],
            "peak_consensus": max((stage["consensus_level"] for stage in session_data["stages"]), default=0)
        }
    
    def _analyze_value_conflicts(self, session_data: Dict) -> Dict:
        """价值观冲突分析"""
        conflicts_by_stage = {}
        
        for stage in session_data["stages"]:
            stage_conflicts = []
            for conflict in stage["conflicts"]:
                # 分析冲突涉及的价值观
                participants = session_data["participants"]
                conflict_values = []
                for party_id in conflict["parties"]:
                    participant = next(p for p in participants if p["id"] == party_id)
                    conflict_values.append(participant["value_type"])
                
                stage_conflicts.append({
                    "topic": conflict["topic"],
                    "involved_values": conflict_values,
                    "status": conflict["status"]
                })
            
            conflicts_by_stage[stage["stage_name"]] = stage_conflicts
        
        return conflicts_by_stage
    
    def _analyze_efficiency(self, session_data: Dict) -> Dict:
        """效率指标分析"""
        total_time = session_data["total_duration"]
        total_turns = session_data["total_turns"]
        
        return {
            "time_per_turn": total_time / total_turns if total_turns > 0 else 0,
            "time_per_stage": total_time / len(session_data["stages"]) if session_data["stages"] else 0,
            "decisions_per_minute": len([d for stage in session_data["stages"] for d in stage["decisions_made"]]) / (total_time / 60) if total_time > 0 else 0,
            "success_rate": 1 if session_data["success"] else 0
        }
