<template>
  <div class="chat-header"><b>历史检测记录</b></div>
  <div class="page-body">
    <el-form inline>
      <el-form-item label="工件号">
        <el-input v-model="q.workpiece_no" placeholder="如 FL-PN18-A" clearable style="width: 160px" />
      </el-form-item>
      <el-form-item label="批次号">
        <el-input v-model="q.batch_no" clearable style="width: 140px" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="q.status" clearable style="width: 140px">
          <el-option v-for="s in ['pass', 'fail', 'need_review', 'pending', 'rechecking']" :key="s" :value="s" :label="s" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="load">查询</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="rows" border>
      <el-table-column prop="id" label="#" width="60" />
      <el-table-column prop="workpiece_no" label="工件号" />
      <el-table-column prop="batch_no" label="批次号" />
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="row.status === 'pass' ? 'success' : row.status === 'fail' ? 'danger' : 'warning'" size="small">
            {{ row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="检测时间" width="180">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="showDetail(row.id)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>

  <el-dialog v-model="detailVisible" title="检测详情" width="720px" top="4vh">
    <template v-if="detail">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="工件号">{{ detail.workpiece_no }}</el-descriptions-item>
        <el-descriptions-item label="批次号">{{ detail.batch_no || "-" }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ detail.status }}</el-descriptions-item>
        <el-descriptions-item label="复核意见">{{ detail.review_comment || "-" }}</el-descriptions-item>
      </el-descriptions>

      <template v-if="detail.cv_result">
        <DefectCanvas :image-key="detail.image_key" :result="detail.cv_result" style="margin-top: 10px" />
        <h5 style="margin: 12px 0 6px">AI 分析</h5>
        <div class="msg assistant" style="max-width: 100%">{{ detail.analysis_report?.summary_text || "-" }}</div>
      </template>
      <template v-else>
        <img v-if="detail.annotated_image_url" :src="detail.annotated_image_url"
          style="width: 100%; border-radius: 8px; margin-top: 10px" />
        <p v-if="detail.conclusion_text" style="margin-top: 10px">{{ detail.conclusion_text }}</p>
      </template>

      <el-button size="small" type="primary" plain style="margin-top: 10px" @click="openReportById(detail.id)">
        📄 查看完整报告
      </el-button>
    </template>
  </el-dialog>

  <ReportDialog v-model="reportVisible" :content="reportContent" />
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { http } from "../api/http";
import DefectCanvas from "../components/canvas/DefectCanvas.vue";
import ReportDialog from "../components/report/ReportDialog.vue";
import { fmtTime } from "../utils/format";

const q = reactive({ workpiece_no: "", batch_no: "", status: "" });
const rows = ref<any[]>([]);
const detail = ref<any>(null);
const detailVisible = ref(false);
const reportVisible = ref(false);
const reportContent = ref("");

async function load() {
  const { data } = await http.get("/inspections", { params: { ...q } });
  rows.value = data.items;
}

async function showDetail(id: number) {
  const { data } = await http.get(`/inspections/${id}`);
  detail.value = data;
  detailVisible.value = true;
}

async function openReportById(id: number) {
  const resp = await http.get(`/inspections/${id}/report/download`, { responseType: "blob" });
  reportContent.value = await (resp.data as Blob).text(); // 强制 UTF-8 解码，杜绝乱码
  reportVisible.value = true;
}

onMounted(load);
</script>
