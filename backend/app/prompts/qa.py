"""问答节点 Prompt：多轮追问 / 历史查询，回答按角色裁剪。"""
import json

from langchain_core.messages import HumanMessage, SystemMessage

QA_SYSTEM = """你是喷涂质检助手，负责回答关于检测结果的追问与工艺咨询。

【规则】
1. 回答必须基于 <facts> 中的检测快照与工艺知识，禁止编造数值与参数；
2. facts.user_role 为 operator（操作工）时：不得透露具体工艺参数数值、不得给出整改参数，只做定性说明并建议联系工艺员；
3. 工艺参数类问题必须引用工艺知识文档中的取值范围；
4. 回答使用简体中文，简洁、面向现场操作。
"""


def build_qa_messages(facts: dict, history: list = []) -> list:
    msgs = [SystemMessage(content=QA_SYSTEM)]
    msgs.extend(history[-10:])
    facts_json = json.dumps(facts, ensure_ascii=False, default=str)
    msgs.append(
        HumanMessage(content=f"请回答用户问题。\n<facts>\n{facts_json}\n</facts>\n"
                             "输出 JSON 字段：answer")
    )
    return msgs
