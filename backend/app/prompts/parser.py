"""意图解析 Prompt。"""
from langchain_core.messages import HumanMessage, SystemMessage

PARSER_SYSTEM = """你是喷涂质检助手的意图解析器。识别用户意图并抽取参数，只输出 JSON：
{"intent": "new_inspection|history_query|followup_qa|request_review",
 "workpiece_no": "工件型号编号，形如 FL-PN18-A，未提及则 null",
 "batch_no": "批次号，未提及则 null"}

判定规则：
- 用户提供了图片或明确要求检测某个工件 → new_inspection
- 用户表达"请求复核/申请复核/复核该工件/不认可结果"等复核诉求 → request_review
- 用户在查询历史记录/之前的检测结果 → history_query
- 其余追问、闲聊、工艺咨询 → followup_qa
"""


def build_parser_messages(text: str, has_image: bool) -> list:
    prefix = "（用户随消息附带了图片）" if has_image else ""
    return [
        SystemMessage(content=PARSER_SYSTEM),
        HumanMessage(content=f"{prefix}用户消息：{text}"),
    ]
