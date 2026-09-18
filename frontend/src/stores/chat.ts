import { defineStore } from "pinia";
import { http } from "../api/http";
import { consumeSse } from "../api/sse";
import { uploadImage } from "../api/http";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  image?: string; // 用户消息随附的上传图（签名 URL）
  inspectionId?: number; // 关联的检测记录（点击气泡查看详情/申请复核）
}

export interface DefectItem {
  id: number;
  defect_type: string;
  confidence: number;
  bbox_xyxy: number[];
  measure: Record<string, number | null>;
}

export interface CvResult {
  image_key: string;
  image_size: { width: number; height: number };
  detections: DefectItem[];
  meta?: Record<string, any>;
}

export const DEFECT_CN: Record<string, string> = {
  sagging: "流挂",
  orange_peel: "橘皮",
  color_deviation: "色差",
  particle: "颗粒",
  pinhole: "针孔",
  scratch: "划伤",
};

export const useChatStore = defineStore("chat", {
  state: () => ({
    sessionId: "" as string,
    messages: [] as ChatMessage[],
    streaming: false,
    stage: "" as string,
    cvResult: null as CvResult | null,
    status: "" as string,
    lastInspectionId: null as number | null, // 本会话最近一次检测（查看报告/申请复核用）
    previewImage: "" as string, // 本次上传图的签名 URL（消息气泡显示用）
    previewImageUrl: "" as string, // 操作工视角的结果图（无量化数据）
  }),
  actions: {
    async loadSession(sid: string) {
      this.$reset();
      this.sessionId = sid;
      try {
        const { data } = await http.get(`/conversations/${sid}/messages`);
        // 回放：恢复消息文本、上传图（签名 URL）、检测记录关联，以及最近一次检测 id；
        // 连续的 assistant 消息（名称纠正提示 + 检测报告）合并为一条，与在线流式展示保持一致
        const merged: ChatMessage[] = [];
        for (const m of data.messages || []) {
          const item: ChatMessage = {
            role: m.role,
            content: m.content,
            image: m.image || undefined,
            inspectionId: m.inspection_id || undefined,
          };
          const last = merged[merged.length - 1];
          if (item.role === "assistant" && last && last.role === "assistant") {
            last.content += "\n\n" + item.content;
            if (item.inspectionId) last.inspectionId = item.inspectionId;
          } else {
            merged.push(item);
          }
        }
        this.messages = merged;
        if (data.last_inspection_id) this.lastInspectionId = data.last_inspection_id;
      } catch {
        this.messages = [];
      }
    },
    async send(text: string, file?: File | null) {
      if (this.streaming) return;
      let imageKey: string | null = null;
      let imageUrl = "";
      if (file) {
        const up = await uploadImage(file);
        imageKey = up.image_key;
        imageUrl = up.preview_url; // MinIO 签名 URL
        this.previewImage = imageUrl;
      }
      this.messages.push({ role: "user", content: text, image: imageUrl || undefined });
      this.streaming = true;
      this.stage = "正在解析意图…";
      this.cvResult = null;
      this.status = "";

      await consumeSse(
        "/api/v1/chat/stream",
        { session_id: this.sessionId || undefined, message: text, image_key: imageKey },
        {
          onEvent: (event, data) => this.handleEvent(event, data),
          onError: (msg) => {
            this.messages.push({ role: "assistant", content: `⚠️ ${msg}` });
          },
        }
      );
      this.streaming = false;
    },
    handleEvent(event: string, data: any) {
      if (event === "stage") {
        const nodeNames: Record<string, string> = {
          input_parser: "意图解析",
          cv_engine: "视觉检测",
          standard_validator: "标准比对",
          rag_retrieval: "工艺知识检索",
          reasoning: "根因分析",
          self_reflection: "结果自检",
          report_generator: "报告生成",
          human_review: "人工复核",
          qa_answer: "问题解答",
        };
        this.stage = `${nodeNames[data.node] || data.node} ✓`;
      } else if (event === "cv_result") {
        this.cvResult = data;
      } else if (event === "token") {
        const last = this.messages[this.messages.length - 1];
        if (last && last.role === "assistant" && (last as any).__streaming) {
          last.content += data.delta;
        } else {
          const m = { role: "assistant" as const, content: data.delta, __streaming: true } as any;
          this.messages.push(m);
        }
      } else if (event === "status") {
        this.status = data.status;
      } else if (event === "report") {
        // 结构化报告已随 token 输出，占位以便扩展结论卡片
      } else if (event === "interrupt") {
        // 检测工作流不再产生 interrupt（结论二态化）；保留兜底展示
        this.messages.push({
          role: "assistant",
          content: `⚠️ ${data.prompt || "检测结论待人工复核"}（记录 #${data.inspection_id}），请在复核工作台处理。`,
        });
      } else if (event === "done") {
        if (data.session_id) this.sessionId = data.session_id;
        if (data.inspection_id) {
          this.lastInspectionId = data.inspection_id;
          // 关联到本轮（最后一条）用户消息：每个"图片+文字"各自可点开对应详情
          for (let i = this.messages.length - 1; i >= 0; i--) {
            if (this.messages[i].role === "user") {
              this.messages[i].inspectionId = data.inspection_id;
              break;
            }
          }
        }
        const last = this.messages[this.messages.length - 1] as any;
        if (last?.__streaming) delete last.__streaming;
        this.stage = "";
        // 新会话落入左栏历史列表
        import("./sessions").then(({ useSessionsStore }) => useSessionsStore().refresh());
      } else if (event === "error") {
        this.messages.push({ role: "assistant", content: `⚠️ ${data.message || data}` });
      }
    },
  },
});
