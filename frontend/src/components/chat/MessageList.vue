<template>
  <div class="message-col" ref="containerRef">
    <div v-if="!chat.messages.length" class="stage-tip">
      上传喷涂后的工件照片并描述检测要求，例如："检测这个法兰盘 FL-PN18-A，批次 B2026-09-01"
    </div>
    <template v-for="(m, i) in chat.messages" :key="i">
      <div
        class="msg"
        :class="[m.role, { clickable: m.role === 'user' && m.inspectionId }]"
        :title="m.role === 'user' && m.inspectionId ? '点击查看该次检测详情' : ''"
        @click="m.role === 'user' && m.inspectionId && emit('openInspection', m.inspectionId)"
      >
        <img v-if="m.image" :src="m.image"
          style="max-width: 260px; max-height: 200px; border-radius: 8px; display: block; margin-bottom: 6px" />
        {{ m.content }}
      </div>
    </template>
    <div v-if="chat.streaming && chat.stage" class="stage-tip">{{ chat.stage }}</div>
    <div v-if="chat.status" class="stage-tip">
      状态：<el-tag :type="statusTagType" size="small">{{ chat.status }}</el-tag>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from "vue";
import { useChatStore } from "../../stores/chat";

const emit = defineEmits<{ (e: "openInspection", id: number): void }>();
const chat = useChatStore();
const containerRef = ref<HTMLElement>();
const statusTagType = computed(() => {
  const map: Record<string, string> = {
    pass: "success", fail: "danger", need_review: "warning",
    rechecking: "info", pending: "info", detecting: "info",
  };
  return (map[chat.status] || "info") as any;
});

watch(
  () => chat.messages.length,
  async () => {
    await nextTick();
    containerRef.value?.scrollTo({ top: containerRef.value.scrollHeight });
  }
);
watch(
  () => chat.messages.map((m) => m.content.length).join(","),
  async () => {
    await nextTick();
    containerRef.value?.scrollTo({ top: containerRef.value.scrollHeight });
  }
);
</script>
