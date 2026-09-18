<template>
  <el-dialog :model-value="modelValue" title="质检报告" width="720px" @update:model-value="emit('update:modelValue', $event)">
    <div class="report-body">{{ content || "（报告内容为空）" }}</div>
  </el-dialog>
</template>

<script setup lang="ts">
defineProps<{ modelValue: boolean; content: string }>();
const emit = defineEmits<{ (e: "update:modelValue", v: boolean): void }>();
</script>

<style scoped>
.report-body {
  max-height: 62vh;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.75;
  background: #f9fafb;
  border-radius: 8px;
  padding: 14px;
}
</style>
