<template>
  <div class="chat-header">
    <b>质检对话</b>
    <span class="sid">{{ chat.sessionId || "新会话" }}</span>
  </div>
  <div class="chat-body">
    <div class="chat-left">
      <MessageList @open-inspection="openInspectionDetail" />
      <ChatInput />
    </div>
    <aside class="preview-col">
      <h4 style="margin-bottom: 10px">检测结果预览</h4>
      <template v-if="chat.cvResult">
        <DefectCanvas :image-key="chat.cvResult.image_key" :result="chat.cvResult" />
        <div class="defect-list">
          <div v-for="d in chat.cvResult.detections" :key="d.id" class="defect-item">
            <span class="defect-dot" :style="{ background: colorOf(d.id) }"></span>
            <span>{{ DEFECT_CN[d.defect_type] || d.defect_type }}</span>
            <span style="color: #9ca3af">conf {{ d.confidence.toFixed(2) }}</span>
            <span v-if="d.measure.area_cm2 != null" style="color: #9ca3af">
              {{ d.measure.area_cm2 }} cm²
            </span>
            <span v-if="d.measure.delta_e != null" style="color: #9ca3af">ΔE {{ d.measure.delta_e }}</span>
          </div>
        </div>
        <el-alert
          v-if="mockScene"
          :title="`视觉引擎为 Mock 预置场景 ${mockScene}（与图片实际内容无关）`"
          type="info" :closable="false" style="margin-top: 10px" />
      </template>
      <template v-else-if="chat.previewImageUrl">
        <!-- 操作工视角：仅结果图与结论，无量化数据 -->
        <img :src="chat.previewImageUrl" style="width: 100%; border-radius: 8px" />
      </template>
      <el-empty v-else description="暂无检测结果（点击带图的消息气泡可查看该次检测）" :image-size="70" />
      <div style="margin-top: 12px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap">
        <el-button size="small" type="primary" plain :disabled="!chat.lastInspectionId" :loading="reportLoading"
          @click="openReport">📄 查看完整报告</el-button>
        <el-button v-if="canRequestReview" size="small" type="warning" plain :disabled="reviewRequested"
          :loading="reviewLoading" @click="reviewDlg = true">🔁 申请复核</el-button>
        <span v-if="chat.status" style="color: #9ca3af; font-size: 12px">状态: {{ chat.status }}</span>
      </div>

      <el-dialog v-model="reviewDlg" title="申请人工复核" width="440px">
        <p style="font-size: 13px; color: #6b7280; margin-bottom: 10px">
          将对检测记录 <b>#{{ chat.lastInspectionId }}</b>（{{ chat.status }}）发起复核申请，由工艺员在复核工作台处置。
        </p>
        <el-input v-model="reviewComment" type="textarea" :rows="3" placeholder="说明不认可的原因（会转给工艺员并记入审计日志）" />
        <template #footer>
          <el-button @click="reviewDlg = false">取消</el-button>
          <el-button type="primary" :loading="reviewLoading" @click="submitReviewRequest">提交申请</el-button>
        </template>
      </el-dialog>
      <ReportDialog v-model="reportVisible" :content="reportContent" />
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";
import MessageList from "../components/chat/MessageList.vue";
import ChatInput from "../components/chat/ChatInput.vue";
import DefectCanvas from "../components/canvas/DefectCanvas.vue";
import ReportDialog from "../components/report/ReportDialog.vue";
import { http } from "../api/http";
import { useChatStore, DEFECT_CN } from "../stores/chat";

const chat = useChatStore();
const mockScene = computed(() => chat.cvResult?.meta?.scene as string | undefined);
const reportLoading = ref(false);
const reportVisible = ref(false);
const reportContent = ref("");
const reviewDlg = ref(false);
const reviewLoading = ref(false);
const reviewComment = ref("");
const reviewRequested = ref(false);
const COLORS = ["#f56c6c", "#e6a23c", "#409eff", "#67c23a", "#b37feb", "#f8985d"];
const colorOf = (id: number) => COLORS[(id - 1) % COLORS.length];

// 仅对"不合格"结论提供申诉入口（合格无复核意义）
const canRequestReview = computed(() => chat.status === "fail" && !!chat.lastInspectionId);

/** 点击历史消息气泡：加载该次检测详情到右侧预览区（回放会话同样可用）。
 *  操作工详情被裁剪无 cv_result → 展示结果图 + 状态即可。 */
async function openInspectionDetail(id: number) {
  try {
    const { data } = await http.get(`/inspections/${id}`);
    chat.status = data.status;
    chat.lastInspectionId = data.id;
    if (data.cv_result) {
      chat.cvResult = data.cv_result;
      chat.previewImageUrl = "";
      chat.messages.forEach((m) => {
        if (m.role === "user" && m.inspectionId === id && !m.image && data.image_key) {
          http
            .get(`/files/${data.image_key}`, { responseType: "blob" })
            .then((r) => (m.image = URL.createObjectURL(r.data as Blob)));
        }
      });
    } else if (data.annotated_image_url || data.image_url) {
      chat.cvResult = null;
      chat.previewImageUrl = data.annotated_image_url || data.image_url;
    } else {
      ElMessage.info("该记录暂无可展示的检测数据");
    }
  } catch {
    ElMessage.error("加载检测详情失败");
  }
}

/** 报告带 JWT 经 axios 取回并强制 UTF-8 解码，站内弹窗展示（避免新窗口编码乱码） */
async function openReport() {
  if (!chat.lastInspectionId) return;
  reportLoading.value = true;
  try {
    const resp = await http.get(`/inspections/${chat.lastInspectionId}/report/download`, {
      responseType: "blob",
    });
    reportContent.value = await (resp.data as Blob).text();
    reportVisible.value = true;
  } finally {
    reportLoading.value = false;
  }
}

async function submitReviewRequest() {
  if (!chat.lastInspectionId) return;
  reviewLoading.value = true;
  try {
    const { data } = await http.post(`/inspections/${chat.lastInspectionId}/request-review`, {
      comment: reviewComment.value,
    });
    reviewRequested.value = true;
    reviewDlg.value = false;
    chat.messages.push({
      role: "assistant",
      content: `✅ ${data.message || "复核申请已提交"}（记录 #${data.id}），工艺员将在复核工作台处置。`,
    });
    reviewComment.value = "";
  } catch {
    ElMessage.error("复核申请提交失败");
  } finally {
    reviewLoading.value = false;
  }
}
</script>
