<template>
  <div class="canvas-wrap">
    <img v-show="url" ref="imgRef" :src="url" class="base-img" @load="redraw" />
    <canvas v-show="url" ref="canvasRef" class="overlay"></canvas>
  </div>
  <div v-if="!url" class="empty-tip">图片加载中…</div>
  <div v-else-if="!result || !result.detections.length" class="empty-tip">无缺陷检出</div>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { http } from "../../api/http";
import type { CvResult } from "../../stores/chat";

/**
 * 缺陷框叠加画布。
 * 图片经同源代理 /api/v1/files（带 JWT）取回 blob 后展示——
 * <img> 直接用签名 URL 在部分场景会静默失败，blob 方式保证可加载。
 */
const props = defineProps<{ imageKey: string; result: CvResult | null }>();
const url = ref("");
const imgRef = ref<HTMLImageElement>();
const canvasRef = ref<HTMLCanvasElement>();

const COLORS = ["#f56c6c", "#e6a23c", "#409eff", "#67c23a", "#b37feb", "#f8985d"];

let currentKey = "";
watch(
  () => props.imageKey,
  async (key) => {
    if (!key) {
      url.value = "";
      return;
    }
    currentKey = key;
    try {
      const resp = await http.get(`/files/${key}`, { responseType: "blob" });
      if (currentKey !== key) return; // 已切换图片，丢弃过期响应
      const newUrl = URL.createObjectURL(resp.data as Blob);
      if (url.value) URL.revokeObjectURL(url.value);
      url.value = newUrl;
    } catch {
      url.value = "";
    }
  },
  { immediate: true }
);

function redraw() {
  const img = imgRef.value;
  const canvas = canvasRef.value;
  if (!img || !canvas || !img.naturalWidth) return;
  const wrap = canvas.parentElement!;
  const scale = Math.min(wrap.clientWidth / img.naturalWidth, 1);
  const w = img.naturalWidth * scale;
  const h = img.naturalHeight * scale;
  canvas.width = w;
  canvas.height = h;
  canvas.style.width = `${w}px`;
  canvas.style.height = `${h}px`;
  const ctx = canvas.getContext("2d")!;
  ctx.clearRect(0, 0, w, h);
  const size = props.result?.image_size || {
    width: img.naturalWidth,
    height: img.naturalHeight,
  };
  (props.result?.detections || []).forEach((d, i) => {
    const [x1, y1, x2, y2] = d.bbox_xyxy;
    const color = COLORS[i % COLORS.length];
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.strokeRect((x1 / size.width) * w, (y1 / size.height) * h, ((x2 - x1) / size.width) * w, ((y2 - y1) / size.height) * h);
    const label = `${d.defect_type} ${d.confidence.toFixed(2)}`;
    ctx.font = "12px sans-serif";
    const tw = ctx.measureText(label).width + 8;
    const bx = (x1 / size.width) * w;
    const by = Math.max(0, (y1 / size.height) * h - 16);
    ctx.fillStyle = color;
    ctx.fillRect(bx, by, tw, 16);
    ctx.fillStyle = "#fff";
    ctx.fillText(label, bx + 4, by + 12);
  });
}

watch(
  () => props.result,
  () => redraw(),
  { deep: true }
);
</script>

<style scoped>
.canvas-wrap { position: relative; width: 100%; min-height: 40px; }
.base-img { width: 100%; display: block; border-radius: 8px; }
.overlay { position: absolute; inset: 0; }
.empty-tip { text-align: center; color: #9ca3af; font-size: 13px; margin: 8px 0; }
</style>
