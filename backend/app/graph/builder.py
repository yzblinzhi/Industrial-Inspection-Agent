"""StateGraph 组装与编译（文档 5.3）。
检测工作流只产出 pass / fail 两态结论；复核走"操作工申请（review_request）→
复核工作台人工处置（REST 直改单据）"，不再有图内 interrupt。"""
import logging

from langgraph.graph import END, START, StateGraph

from app.graph import edges
from app.graph.nodes import (
    cv_engine,
    input_parser,
    qa_answer,
    rag_retrieval,
    reasoning,
    report_generator,
    review_request,
    self_reflection,
    standard_validator,
)
from app.graph.state import AgentState

logger = logging.getLogger(__name__)


def build_graph(checkpointer) -> "StateGraph":  # noqa: F821
    g = StateGraph(AgentState)
    g.add_node("input_parser", input_parser.node)
    g.add_node("cv_engine", cv_engine.node)
    g.add_node("standard_validator", standard_validator.node)
    g.add_node("rag_retrieval", rag_retrieval.node)
    g.add_node("reasoning", reasoning.node)
    g.add_node("self_reflection", self_reflection.node)
    g.add_node("report_generator", report_generator.node)
    g.add_node("review_request", review_request.node)
    g.add_node("qa_answer", qa_answer.node)

    g.add_edge(START, "input_parser")
    g.add_conditional_edges(
        "input_parser",
        edges.route_after_parse,
        {"inspect": "cv_engine", "qa": "qa_answer", "review": "review_request", "finish": END},
    )
    g.add_edge("cv_engine", "standard_validator")
    g.add_conditional_edges(
        "standard_validator",
        edges.route_after_validate,
        {"retrieval": "rag_retrieval", "report": "report_generator", "reason": "reasoning"},
    )
    g.add_edge("rag_retrieval", "reasoning")
    g.add_edge("reasoning", "self_reflection")
    g.add_conditional_edges(
        "self_reflection",
        edges.route_after_reflection,
        {"regen": "reasoning", "report": "report_generator"},
    )
    g.add_edge("report_generator", END)
    g.add_edge("review_request", END)
    g.add_edge("qa_answer", END)

    graph = g.compile(checkpointer=checkpointer)
    logger.info("LangGraph 质检图编译完成（9 节点 / 1 条循环边 / 结论二态 pass|fail）")
    return graph
