"""Input_Parser 节点：意图识别 + 工件解析（精确匹配 → 名称匹配 → 笔误纠错）。
检测前置校验：必须有图 + 工件号可解析到已登记工件，否则返回指引且**不进入检测工作流、不落单据**。"""
import difflib
import logging
import re

from langchain_core.messages import AIMessage

from app.prompts.parser import build_parser_messages
from app.providers.factory import get_llm_provider
from app.providers.llm_qwen import LLMAuthError
from app.schemas.intent import IntentParse
from app.services.standards import get_workpiece, list_all_workpieces

logger = logging.getLogger(__name__)

WORKPIECE_NO_RE = re.compile(r"\b([A-Z]{2,4}-[A-Z0-9]{2,8}-[A-Z0-9])\b")
BATCH_RE = re.compile(r"批次[:：\s]*([A-Za-z0-9\-]+)")
INSPECT_KW = ("检测", "检查", "质检", "评估", "看一下这个")
HISTORY_KW = ("历史", "之前", "上次", "记录", "查询", "查一下")
REVIEW_KW = ("请求复核", "申请复核", "复核该工件", "提交复核", "申请复检", "不认可", "复核一下")

SIMILARITY_THRESHOLD = 0.8  # 工件号编辑相似度阈值（笔误纠正）


def _base_name(name: str) -> str:
    """『法兰盘A』→『法兰盘』：去掉尾部型号代号，便于口语名称匹配。"""
    return re.sub(r"[A-Za-z0-9]+$", "", name or "").strip()


async def resolve_workpiece(text: str, raw_no: str | None) -> tuple[str | None, str | None]:
    """把用户输入解析为已登记工件号。返回 (工件号, 说明)；工件号为 None 表示无法解析。"""
    candidates = await list_all_workpieces()
    if not candidates:
        return None, "系统中尚未登记任何工件，请联系管理员在「系统管理」中添加。"

    if raw_no:
        wp = await get_workpiece(raw_no)
        if wp:
            return raw_no, None  # 精确命中
        # 工件号未登记 → 先按名称匹配纠错，再按编号相似度纠错
        name_hits = [
            w for w in candidates
            if (w["name"] and w["name"] in text) or (_base_name(w["name"]) and _base_name(w["name"]) in text)
        ]
        if len(name_hits) == 1:
            w = name_hits[0]
            return w["workpiece_no"], (
                f"您填写的工件号 `{raw_no}` 未登记，已按名称「{w['name']}」匹配为 `{w['workpiece_no']}`。"
            )
        sim = sorted(
            ((w, difflib.SequenceMatcher(None, raw_no.upper(), w["workpiece_no"].upper()).ratio())
             for w in candidates),
            key=lambda x: x[1], reverse=True,
        )
        if sim and sim[0][1] >= SIMILARITY_THRESHOLD:
            w = sim[0][0]
            return w["workpiece_no"], (
                f"工件号 `{raw_no}` 未登记，与已登记的 `{w['workpiece_no']}`（{w['name']}）高度相似，"
                f"已按笔误纠正。"
            )
        return None, (
            f"工件号 `{raw_no}` 未登记，无法发起检测。已登记工件号："
            + "、".join(f"{w['workpiece_no']}（{w['name']}）" for w in candidates)
            + "。请核对后重新提交。"
        )

    # 未提供工件号 → 尝试按名称匹配
    name_hits = [
        w for w in candidates
        if (w["name"] and w["name"] in text) or (_base_name(w["name"]) and _base_name(w["name"]) in text)
    ]
    if len(name_hits) == 1:
        w = name_hits[0]
        return w["workpiece_no"], f"已按名称「{w['name']}」匹配到工件号 `{w['workpiece_no']}`。"
    if len(name_hits) > 1:
        return None, (
            "您提到的名称对应多个工件（" + "、".join(w["workpiece_no"] for w in name_hits)
            + "），请明确工件号后重新提交。"
        )
    return None, None  # 交由调用方给通用指引


def rule_parse(text: str, has_image: bool) -> dict:
    if not has_image and any(k in text for k in REVIEW_KW):
        intent = "request_review"
    elif has_image:
        intent = "new_inspection"
    elif any(k in text for k in HISTORY_KW):
        intent = "history_query"
    elif any(k in text for k in INSPECT_KW) and WORKPIECE_NO_RE.search(text):
        intent = "new_inspection"
    else:
        intent = "followup_qa"
    wp = WORKPIECE_NO_RE.search(text)
    batch = BATCH_RE.search(text)
    return {
        "intent": intent,
        "workpiece_no": wp.group(1) if wp else None,
        "batch_no": batch.group(1) if batch else None,
    }


async def node(state: dict) -> dict:
    text = state.get("user_input") or ""
    has_image = bool(state.get("image_key"))

    parsed: IntentParse | None = None
    try:
        result = await get_llm_provider().chat(
            build_parser_messages(text, has_image), IntentParse
        )
        if isinstance(result, IntentParse):
            parsed = result
    except LLMAuthError:
        raise  # 鉴权失败直接暴露给用户，不能静默降级
    except Exception as exc:  # noqa: BLE001
        logger.warning("意图解析 LLM 失败，降级规则解析: %s", exc)

    data = parsed.model_dump() if parsed else rule_parse(text, has_image)

    # 语义修正
    if has_image and data["intent"] != "request_review":
        data["intent"] = "new_inspection"
    elif data["intent"] == "new_inspection" and not has_image:
        data["intent"] = "followup_qa"

    workpiece_info = dict(state.get("workpiece_info") or {})
    if data.get("workpiece_no"):
        workpiece_info["workpiece_no"] = data["workpiece_no"]
    if data.get("batch_no"):
        workpiece_info["batch_no"] = data["batch_no"]

    # ---- 工件解析与前置校验（不合规直接结束，绝不落库） ----
    if data["intent"] == "new_inspection":
        if not has_image:
            data["intent"] = "followup_qa"
        else:
            resolved, notice = await resolve_workpiece(text, workpiece_info.get("workpiece_no"))
            if resolved:
                workpiece_info["workpiece_no"] = resolved
                messages_out = [AIMessage(content=notice)] if notice else []
                logger.info("工件解析: %s%s", resolved, f"（{notice}）" if notice else "")
                return {
                    "intent": "new_inspection",
                    "workpiece_info": workpiece_info,
                    "messages": messages_out,
                    "status": "pending",
                }
            # 无法解析：给指引，直接结束（不建单据、不检测）
            guidance = notice or (
                "📝 发起检测请按以下规则：**上传工件照片，并在消息中写明工件号（建议同时注明批次号）**。\n\n"
                "示例：`检测立柱 CL-ZH02-B，批次 B2026-09-01`"
            )
            logger.info("检测前置校验未通过: %s", notice)
            return {
                "intent": "need_guidance",
                "workpiece_info": workpiece_info,
                "messages": [AIMessage(content=guidance)],
                "status": "pending",
            }

    return {
        "intent": data["intent"],
        "workpiece_info": workpiece_info,
        "status": "pending",
    }
