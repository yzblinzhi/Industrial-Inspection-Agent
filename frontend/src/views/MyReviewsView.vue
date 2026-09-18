<template>
  <div class="chat-header"><b>复核申请处理</b></div>
  <div class="page-body">
    <el-tabs v-model="tab" @tab-change="load">
      <el-tab-pane label="全部复核" name="all" />
      <el-tab-pane label="待复核" name="pending" />
      <el-tab-pane label="被驳回" name="rejected" />
      <el-tab-pane label="驳回重申" name="reapply" />
      <el-tab-pane v-if="auth.canReview" label="特殊标注" name="special" />
    </el-tabs>

    <el-table :data="rows" border size="small">
      <el-table-column prop="id" label="工单#" width="70" />
      <el-table-column prop="workpiece_no" label="工件号" min-width="120" />
      <el-table-column label="批次号" width="120">
        <template #default="{ row }">{{ row.batch_no || "-" }}</template>
      </el-table-column>
      <el-table-column label="系统状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="row.system_status === 'pass' ? 'success' : row.system_status === 'fail' ? 'danger' : 'info'">
            {{ SYSTEM_STATUS_CN[row.system_status] || row.system_status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="复核状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="REVIEW_TAG_TYPE[row.review_status]">
            {{ REVIEW_STATUS_CN[row.review_status] || row.review_status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="reviewer" label="处理人" width="150" />
      <el-table-column prop="reviewer_role" label="处理人身份" width="110" />
      <el-table-column label="检测时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.inspection_created_at) }}</template>
      </el-table-column>
      <el-table-column label="复核时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.reviewed_at) }}</template>
      </el-table-column>
      <el-table-column label="驳回时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.reject_at) }}</template>
      </el-table-column>
      <el-table-column label="驳回重申时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.reapply_at) }}</template>
      </el-table-column>
      <el-table-column label="复核结果" min-width="110">
        <template #default="{ row }">{{ DECISION_CN[row.decision] || "-" }}</template>
      </el-table-column>
      <el-table-column v-if="tab === 'rejected'" label="操作" width="190" fixed="right" align="center" header-align="center">
        <template #default="{ row }">
          <div class="op-btns">
            <el-button v-if="!row.force_reject" size="small" type="success" @click="ack(row)">确认处理</el-button>
            <el-button size="small" type="warning" @click="reapplyDlg = row">申请驳回重审</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!rows.length" description="暂无记录" :image-size="80" />

    <!-- 申请驳回重申（备注必填） -->
    <el-dialog v-model="reapplyVisible" title="申请驳回重审" width="460px">
      <p style="font-size: 13px; color: #6b7280; margin-bottom: 10px">
        提交后工单将重新进入复核队列，由处理人再次复核（此次处理人不得再驳回，必须给出最终结论）。
      </p>
      <el-input v-model="reapplyNote" type="textarea" :rows="4" placeholder="复核备注（必填）：说明不认可驳回的理由" />
      <template #footer>
        <el-button @click="reapplyVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="doReapply">提交重申</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { http } from "../api/http";
import { fmtTime } from "../utils/format";
import { DECISION_CN, REVIEW_STATUS_CN, REVIEW_TAG_TYPE, SYSTEM_STATUS_CN } from "../utils/review";
import { useAuthStore } from "../stores/auth";
import { useReviewBadge } from "../stores/reviewBadge";

const auth = useAuthStore();
const badge = useReviewBadge();
const tab = ref("all");
const rows = ref<any[]>([]);
const reapplyDlg = ref<any>(null);
const reapplyNote = ref("");
const acting = ref(false);
const reapplyVisible = computed({
  get: () => !!reapplyDlg.value,
  set: (v) => { if (!v) reapplyDlg.value = null; },
});

async function load() {
  const { data } = await http.get("/reviews/my", { params: { box: tab.value } });
  rows.value = data;
  badge.refresh();
}

async function ack(row: any) {
  acting.value = true;
  try {
    await http.post(`/reviews/${row.id}/ack-rejection`);
    ElMessage.success("已确认处理（接受驳回结果）");
    await load();
  } finally {
    acting.value = false;
  }
}

async function doReapply() {
  if (!reapplyNote.value.trim()) {
    ElMessage.warning("复核备注必填");
    return;
  }
  acting.value = true;
  try {
    await http.post(`/reviews/${reapplyDlg.value.id}/reapply`, { comment: reapplyNote.value });
    ElMessage.success("已提交驳回重审，等待处理人再次复核");
    reapplyDlg.value = null;
    reapplyNote.value = "";
    await load();
  } finally {
    acting.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.op-btns {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
</style>
