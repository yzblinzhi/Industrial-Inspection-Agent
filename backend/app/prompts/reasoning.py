"""推理节点 Prompt：核心约束是"结论锚定量化数据"（文档 5.2 / 原则 3）。"""
import json

from langchain_core.messages import HumanMessage, SystemMessage

REASONING_SYSTEM = """你是工业喷涂质检领域的根因分析专家。基于给定的检测事实（facts）输出严格的 JSON 结构。

【铁律——违反任何一条即视为无效输出】
1. 只能使用 facts 中出现的数据，禁止编造任何缺陷、数值、参数；
2. conclusion 必须与 facts 一致：standard_gaps 或 suspects 非空→"fail"，
   两者均为空→"pass"；facts.conclusion_hint 有值时以其为准；
3. suggestions 中每条建议的 defect_type 必须在 facts.standard_gaps 的缺陷类型集合内；
4. param_value 中的数值必须落在对应 rag 文档 params 标注的参数范围内；
5. summary_text 中出现的所有数值必须能在 facts（CV测量值/标准限值/工艺参数）中找到来源；
6. root_cause 禁止使用"可能/大概/应该是/或许"等模糊限定词，必须给出确定性表述；
7. summary_text 面向现场人员：使用中文业务语言，禁止出现 JSON 字段名与内部术语
   （如 standard_gaps、facts、rag_docs、bbox 等英文标识符）；
8. facts.rag_docs 为空数组时：说明知识库中暂无该缺陷的工艺资料——
   严禁编造任何工艺参数与整改数值，suggestions 输出空数组，
   root_cause 只做基于检测结果事实的定性描述（如涂层异常的表现与可能环节），
   并在 summary_text 末尾追加一行："（本次分析未参考工艺知识库，建议由工艺员线下核实。）"；
9. 只输出 JSON，不要输出 markdown 代码块标记或任何解释文字。
"""


def build_reasoning_messages(facts: dict, history: list = []) -> list:
    """history 仅作上下文参考，事实以 <facts> 块为准。"""
    msgs = [SystemMessage(content=REASONING_SYSTEM)]
    msgs.extend(history)
    facts_json = json.dumps(facts, ensure_ascii=False, default=str)
    msgs.append(
        HumanMessage(
            content=(
                "请根据以下检测事实生成根因分析与整改建议。\n"
                f"<facts>\n{facts_json}\n</facts>\n"
                "输出 JSON 字段：conclusion(pass|fail|need_review) / root_cause / "
                "suggestions[{defect_type,param_name,param_value,action,source}] / summary_text"
            )
        )
    )
    return msgs
