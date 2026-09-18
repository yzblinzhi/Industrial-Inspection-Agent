/** 复核工单状态与结论的中文映射（前端统一使用）。 */
export const REVIEW_STATUS_CN: Record<string, string> = {
  pending: "待复核",
  done: "已复核",
  rejected: "被驳回",
  reapply: "驳回重审",
  special: "特殊标注",
};

export const DECISION_CN: Record<string, string> = {
  confirm_fail: "确认不合格",
  confirm_pass: "确认合格",
  reject: "驳回重检",
  special: "特殊标注",
};

export const SYSTEM_STATUS_CN: Record<string, string> = {
  pass: "合格",
  fail: "不合格",
  special: "特殊标注",
  need_review: "复核中",
  rechecking: "重检中",
  pending: "检测中",
  detecting: "检测中",
};

export const REVIEW_TAG_TYPE: Record<string, string> = {
  pending: "warning",
  done: "success",
  rejected: "danger",
  reapply: "warning",
  special: "info",
};
