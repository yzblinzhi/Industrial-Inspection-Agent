<template>
  <div class="chat-header"><b>检测数据库</b></div>
  <div class="page-body">
    <el-form inline>
      <el-form-item label="工件号">
        <el-input v-model="q.workpiece_no" placeholder="如 FL-PN18-A" clearable style="width: 170px" />
      </el-form-item>
      <el-form-item label="最新结论">
        <el-select v-model="q.status" clearable style="width: 140px">
          <el-option v-for="s in ['pass', 'fail', 'special']" :key="s"
            :value="s" :label="SYSTEM_STATUS_CN[s]" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="load">查询</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="rows" border size="small">
      <el-table-column prop="workpiece_no" label="工件号" min-width="130" />
      <el-table-column prop="workpiece_name" label="工件名" width="110" />
      <el-table-column label="批次号" width="130">
        <template #default="{ row }">{{ row.batch_no || "未分批" }}</template>
      </el-table-column>
      <el-table-column label="检测次数" width="90" align="center">
        <template #default="{ row }">{{ row.check_count }} 次</template>
      </el-table-column>
      <el-table-column label="最新结论" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="row.status === 'pass' ? 'success' : row.status === 'fail' ? 'danger' : 'info'">
            {{ SYSTEM_STATUS_CN[row.status] || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最新检测时间" width="180">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="90" align="center">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!rows.length" description="暂无数据" :image-size="80" />

    <el-dialog v-model="dlgVisible" :title="`检测数据库 · ${dlg.workpiece_no}（${dlg.batch_no || '未分批'}）`"
      width="780px" top="3vh">
      <!-- 最新一次检测详情（操作工为简版） -->
      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="工件号">{{ dlg.workpiece_no }}</el-descriptions-item>
        <el-descriptions-item label="批次号">{{ dlg.batch_no || "未分批" }}</el-descriptions-item>
        <el-descriptions-item label="检测次数">{{ dlg.check_count }} 次</el-descriptions-item>
      </el-descriptions>

      <template v-if="detail.cv_result">
        <h5 class="sec-title">工件图片与缺陷标注（YOLO，最新一次）</h5>
        <DefectCanvas v-if="detail.image_key" :image-key="detail.image_key" :result="detail.cv_result" />
        <div class="defect-list">
          <div v-for="d in detail.cv_result?.detections || []" :key="d.id" class="defect-item">
            <span>{{ DEFECT_CN[d.defect_type] || d.defect_type }}</span>
            <span style="color: #9ca3af">conf {{ d.confidence }}</span>
            <span v-if="d.measure.area_cm2 != null" style="color: #9ca3af">{{ d.measure.area_cm2 }} cm²</span>
            <span v-if="d.measure.delta_e != null" style="color: #9ca3af">ΔE {{ d.measure.delta_e }}</span>
          </div>
        </div>
        <h5 class="sec-title">AI 分析（最新一次）</h5>
        <div class="msg assistant" style="max-width: 100%">{{ detail.analysis_report?.summary_text || "-" }}</div>
        <el-button size="small" type="primary" plain style="margin-top: 8px" @click="openReport">
          📄 查看完整报告
        </el-button>
      </template>
      <el-alert v-else type="info" :closable="false" style="margin-top: 10px"
        title="当前角色仅可查看结论摘要（量化数据与 AI 分析仅工艺员/管理员可见）" />

      <!-- 该键全部检测时间线 -->
      <h5 class="sec-title">该工件+批次的全部检测（{{ history.length }} 次）</h5>
      <el-table :data="history" size="small" border>
        <el-table-column prop="id" label="#" width="70" />
        <el-table-column label="检测时间" width="180">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="结论" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'pass' ? 'success' : row.status === 'fail' ? 'danger' : 'info'">
              {{ SYSTEM_STATUS_CN[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="center">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="viewHistory(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <ReportDialog v-model="reportVisible" :content="reportContent" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { http } from "../api/http";
import DefectCanvas from "../components/canvas/DefectCanvas.vue";
import ReportDialog from "../components/report/ReportDialog.vue";
import { fmtTime } from "../utils/format";
import { SYSTEM_STATUS_CN } from "../utils/review";
import { DEFECT_CN } from "../stores/chat";

const q = reactive({ workpiece_no: "", status: "" });
const rows = ref<any[]>([]);
const dlg = ref<any>({});
const detail = ref<any>({});
const history = ref<any[]>([]);
const dlgVisible = ref(false);
const reportVisible = ref(false);
const reportContent = ref("");
let currentInspectionId: number | null = null;

async function load() {
  const { data } = await http.get("/inspections/database", { params: { ...q } });
  rows.value = data.items;
}

async function openDetail(row: any) {
  dlg.value = row;
  detail.value = row; // 列表行已含最新一次详情数据（操作工已被后端裁剪）
  currentInspectionId = row.inspection_id;
  dlgVisible.value = true;
  // 该键全部检测（走既有列表接口）
  const { data } = await http.get("/inspections", {
    params: { workpiece_no: row.workpiece_no, batch_no: row.batch_no || undefined, size: 50 },
  });
  history.value = data.items;
}

/** 点击历史条目：切换弹窗数据源为该次检测详情 */
async function viewHistory(row: any) {
  currentInspectionId = row.id;
  const { data } = await http.get(`/inspections/${row.id}`);
  detail.value = {
    inspection_id: data.id,
    cv_result: data.cv_result,
    analysis_report: data.analysis_report,
    image_key: data.image_key,
  };
}

async function openReport() {
  if (!currentInspectionId) return;
  const resp = await http.get(`/inspections/${currentInspectionId}/report/download`, {
    responseType: "blob",
  });
  reportContent.value = await (resp.data as Blob).text();
  reportVisible.value = true;
}

onMounted(load);
</script>

<style scoped>
.sec-title { margin: 14px 0 8px; font-size: 14px; font-weight: 700; color: #1f2329; }
</style>
