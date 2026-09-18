<template>
  <div class="chat-header"><b>复核工作台</b></div>
  <div class="page-body">
    <el-tabs v-model="tab" @tab-change="load">
      <el-tab-pane label="待处理" name="pending" />
      <el-tab-pane label="已复核" name="done" />
      <el-tab-pane label="全部复核" name="all" />
    </el-tabs>

    <el-table :data="rows" border size="small">
      <el-table-column prop="id" label="工单#" width="70" />
      <el-table-column prop="applicant" label="申请人" width="150" />
      <el-table-column prop="workpiece_no" label="工件号" min-width="120" />
      <el-table-column label="批次号" width="110">
        <template #default="{ row }">{{ row.batch_no || "-" }}</template>
      </el-table-column>
      <el-table-column label="系统状态" width="95">
        <template #default="{ row }">
          <el-tag size="small" :type="row.system_status === 'pass' ? 'success' : row.system_status === 'fail' ? 'danger' : 'info'">
            {{ SYSTEM_STATUS_CN[row.system_status] || row.system_status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="复核状态" width="95">
        <template #default="{ row }">
          <el-tag size="small" :type="REVIEW_TAG_TYPE[row.review_status]">
            {{ REVIEW_STATUS_CN[row.review_status] || row.review_status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="reviewer" label="处理人" width="140" />
      <el-table-column prop="reviewer_role" label="处理人身份" width="105" />
      <el-table-column label="检测时间" width="165">
        <template #default="{ row }">{{ fmtTime(row.inspection_created_at) }}</template>
      </el-table-column>
      <el-table-column label="复核时间" width="165">
        <template #default="{ row }">{{ fmtTime(row.reviewed_at) }}</template>
      </el-table-column>
      <el-table-column label="驳回时间" width="165">
        <template #default="{ row }">{{ fmtTime(row.reject_at) }}</template>
      </el-table-column>
      <el-table-column label="重申时间" width="165">
        <template #default="{ row }">{{ fmtTime(row.reapply_at) }}</template>
      </el-table-column>
      <el-table-column label="复核结果" width="100">
        <template #default="{ row }">{{ DECISION_CN[row.decision] || "-" }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.review_status === 'pending' || row.review_status === 'reapply'"
            size="small" type="warning" @click="open(row)">复核</el-button>
          <el-button v-else size="small" type="primary" plain @click="open(row)">查看</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!rows.length" :description="tab === 'pending' ? '暂无待处理复核 🎉' : '暂无记录'" :image-size="80" />

    <el-dialog v-model="dlgVisible" :title="`复核工单 · #${currentId}`" width="820px" top="3vh">
      <template v-if="detail">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="工件号">{{ detail.workpiece_no }}</el-descriptions-item>
          <el-descriptions-item label="批次号">{{ detail.batch_no || "-" }}</el-descriptions-item>
          <el-descriptions-item label="系统状态">{{ SYSTEM_STATUS_CN[detail.system_status] || detail.system_status }}</el-descriptions-item>
          <el-descriptions-item label="申请人">{{ detail.applicant }}</el-descriptions-item>
          <el-descriptions-item label="处理人">{{ detail.reviewer }}</el-descriptions-item>
          <el-descriptions-item label="复核状态">{{ REVIEW_STATUS_CN[detail.review_status] || detail.review_status }}</el-descriptions-item>
        </el-descriptions>

        <h5 class="sec-title">工件图片与缺陷标注（YOLO）</h5>
        <DefectCanvas v-if="detail.cv_result && detail.image_key" :image-key="detail.image_key" :result="detail.cv_result" />
        <div class="defect-list">
          <div v-for="d in detail.cv_result?.detections || []" :key="d.id" class="defect-item">
            <span>{{ DEFECT_CN[d.defect_type] || d.defect_type }}</span>
            <span style="color: #9ca3af">conf {{ d.confidence }}</span>
            <span v-if="d.measure.area_cm2 != null" style="color: #9ca3af">{{ d.measure.area_cm2 }} cm²</span>
            <span v-if="d.measure.max_length_mm != null" style="color: #9ca3af">{{ d.measure.max_length_mm }} mm</span>
            <span v-if="d.measure.delta_e != null" style="color: #9ca3af">ΔE {{ d.measure.delta_e }}</span>
          </div>
        </div>

        <h5 class="sec-title">标准比对（超标项）</h5>
        <div v-if="(detail.standard_gaps || []).length" style="font-size: 13px">
          <div v-for="(g, i) in detail.standard_gaps" :key="i">
            · {{ DEFECT_CN[g.defect_type] || g.defect_type }}：实测 {{ JSON.stringify(g.actual) }}，
            限值 {{ JSON.stringify(g.limit) }}，超标 {{ g.exceed_ratio }} 倍
          </div>
        </div>
        <p v-else style="color: #9ca3af; font-size: 13px">无超标项</p>

        <h5 class="sec-title">AI 分析结论</h5>
        <div class="msg assistant" style="max-width: 100%">{{ detail.analysis_report?.summary_text || "-" }}</div>
        <p v-if="detail.applicant_note" style="font-size: 13px; margin-top: 8px">申请备注：{{ detail.applicant_note }}</p>
        <p v-if="detail.comment" style="font-size: 13px; margin-top: 4px">处理意见：{{ detail.comment }}</p>

        <!-- 处置表单：仅待处理可操作 -->
        <template v-if="detail.review_status === 'pending' || detail.review_status === 'reapply'">
          <el-divider>复核处置</el-divider>
          <el-alert v-if="detail.review_status === 'reapply'" type="warning" :closable="false"
            title="该工单为驳回重审，此次不得再次驳回，必须给出最终结论（合格 / 不合格 / 特殊标注）。"
            style="margin-bottom: 10px" />
          <el-form label-width="90px">
            <el-form-item label="复核结论">
              <el-radio-group v-model="decision">
                <el-radio value="confirm_fail">确认不合格</el-radio>
                <el-radio value="confirm_pass">确认合格</el-radio>
                <el-radio v-if="detail.review_status === 'pending'" value="reject">驳回重检</el-radio>
                <el-radio value="special">特殊标注</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item v-if="decision === 'reject'">
              <el-checkbox v-model="forceReject">强制驳回重审（对方必须填写备注申请重审，由我方给出最终结论）</el-checkbox>
            </el-form-item>
            <el-form-item label="复核意见">
              <el-input v-model="comment" type="textarea" :rows="2" placeholder="复核意见（选填，记入审计日志）" />
            </el-form-item>
          </el-form>
        </template>

        <!-- 特殊标注改写：special 工单 -->
        <template v-if="detail.review_status === 'special'">
          <el-divider>特殊标注改写（线下核实后改回正常结论）</el-divider>
          <el-form label-width="90px">
            <el-form-item label="改写为">
              <el-radio-group v-model="rewriteFinal">
                <el-radio value="pass">合格</el-radio>
                <el-radio value="fail">不合格</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="改写意见">
              <el-input v-model="rewriteComment" type="textarea" :rows="2" placeholder="填写线下核实结论（选填）" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="acting" @click="submitRewrite">提交改写</el-button>
            </el-form-item>
          </el-form>
        </template>
      </template>
      <template #footer>
        <el-button @click="dlgVisible = false">关闭</el-button>
        <el-button v-if="detail && (detail.review_status === 'pending' || detail.review_status === 'reapply')"
          type="primary" :loading="acting" @click="submit">提交复核</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { http } from "../api/http";
import DefectCanvas from "../components/canvas/DefectCanvas.vue";
import { fmtTime } from "../utils/format";
import { DECISION_CN, REVIEW_STATUS_CN, REVIEW_TAG_TYPE, SYSTEM_STATUS_CN } from "../utils/review";
import { DEFECT_CN } from "../stores/chat";

const tab = ref<"pending" | "done" | "all">("pending");
const rows = ref<any[]>([]);
const dlgVisible = ref(false);
const acting = ref(false);
const currentId = ref<number | null>(null);
const detail = ref<any>(null);
const decision = ref("confirm_fail");
const comment = ref("");
const forceReject = ref(false);
const rewriteFinal = ref("pass");
const rewriteComment = ref("");

async function load() {
  const { data } = await http.get("/reviews/workbench", { params: { box: tab.value } });
  rows.value = data;
}

function open(row: any) {
  currentId.value = row.id;
  detail.value = row;
  decision.value = "confirm_fail";
  comment.value = "";
  forceReject.value = false;
  rewriteFinal.value = "pass";
  rewriteComment.value = "";
  dlgVisible.value = true;
}

async function submit() {
  if (!currentId.value) return;
  acting.value = true;
  try {
    const { data } = await http.post(`/reviews/${currentId.value}/decide`, {
      decision: decision.value,
      comment: comment.value,
      force: decision.value === "reject" ? forceReject.value : false,
    });
    ElMessage.success(`处置完成，系统状态已置为 ${data.inspection_status}`);
    dlgVisible.value = false;
    await load();
  } finally {
    acting.value = false;
  }
}

async function submitRewrite() {
  if (!currentId.value) return;
  acting.value = true;
  try {
    const { data } = await http.post(`/reviews/${currentId.value}/special-rewrite`, {
      final: rewriteFinal.value,
      comment: rewriteComment.value,
    });
    ElMessage.success(`改写完成，系统状态已置为 ${data.inspection_status}`);
    dlgVisible.value = false;
    await load();
  } finally {
    acting.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.sec-title { margin: 14px 0 8px; font-size: 14px; font-weight: 700; color: #1f2329; }
</style>
