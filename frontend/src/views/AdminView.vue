<template>
  <div class="chat-header"><b>系统管理（管理员）</b></div>
  <div class="page-body">
    <el-tabs>
      <el-tab-pane label="工件与标准">
        <el-button type="primary" size="small" style="margin-bottom: 10px" @click="wpDialog = true">
          新建工件
        </el-button>
        <el-table :data="workpieces" border>
          <el-table-column prop="workpiece_no" label="工件号" width="140" />
          <el-table-column prop="name" label="名称" width="120" />
          <el-table-column prop="material" label="材料" width="100" />
          <el-table-column prop="coating_spec" label="涂层规范" />
          <el-table-column label="标准条数" width="90">
            <template #default="{ row }">{{ row.standards.length }}</template>
          </el-table-column>
          <el-table-column label="操作" width="90">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="editStandards(row)">编辑标准</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="审计日志">
        <el-table :data="audits" border size="small">
          <el-table-column prop="id" label="#" width="60" />
          <el-table-column prop="user" label="用户" width="110" />
          <el-table-column prop="action" label="动作" width="150" />
          <el-table-column prop="target_type" label="对象类型" width="110" />
          <el-table-column prop="target_id" label="对象ID" />
          <el-table-column prop="created_at" label="时间" width="180" />
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>

  <el-dialog v-model="wpDialog" title="新建工件" width="480px">
    <el-form label-width="90px">
      <el-form-item label="工件号"><el-input v-model="wp.workpiece_no" /></el-form-item>
      <el-form-item label="名称"><el-input v-model="wp.name" /></el-form-item>
      <el-form-item label="材料"><el-input v-model="wp.material" /></el-form-item>
      <el-form-item label="涂层规范"><el-input v-model="wp.coating_spec" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="wpDialog = false">取消</el-button>
      <el-button type="primary" @click="createWp">创建</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="stdDialog" title="编辑质检标准（JSON）" width="640px">
    <el-input v-model="stdJson" type="textarea" :rows="12" />
    <template #footer>
      <el-button @click="stdDialog = false">取消</el-button>
      <el-button type="primary" @click="saveStandards">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { http } from "../api/http";

const workpieces = ref<any[]>([]);
const audits = ref<any[]>([]);
const wpDialog = ref(false);
const stdDialog = ref(false);
const wp = ref({ workpiece_no: "", name: "", material: "", coating_spec: "" });
const stdJson = ref("[]");
let editingId: number | null = null;

async function load() {
  const [w, a] = await Promise.all([http.get("/workpieces"), http.get("/admin/audit-logs")]);
  workpieces.value = w.data;
  audits.value = a.data;
}

async function createWp() {
  await http.post("/workpieces", { ...wp.value, standards: [] });
  ElMessage.success("已创建");
  wpDialog.value = false;
  load();
}

function editStandards(row: any) {
  editingId = row.id;
  stdJson.value = JSON.stringify(row.standards, null, 2);
  stdDialog.value = true;
}

async function saveStandards() {
  try {
    const standards = JSON.parse(stdJson.value);
    await http.put(`/workpieces/${editingId}/standards`, { standards });
    ElMessage.success("标准已更新");
    stdDialog.value = false;
    load();
  } catch {
    ElMessage.error("JSON 解析失败");
  }
}

onMounted(load);
</script>
