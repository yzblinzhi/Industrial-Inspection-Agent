<template>
  <div class="input-wrap">
    <div v-if="filePreviewUrl" class="attach-row">
      <div class="attach-thumb">
        <img :src="filePreviewUrl" />
        <button class="attach-remove" title="移除图片" @click="clearFile">×</button>
      </div>
    </div>
    <div class="input-bar">
    <el-upload :show-file-list="false" :auto-upload="false" accept="image/*" :on-change="onFile">
      <el-button :icon="Picture" circle :disabled="chat.streaming" title="上传工件照片" />
    </el-upload>
    <el-button v-if="speechSupported" :icon="Microphone" circle :disabled="chat.streaming" @click="toggleAsr"
      :type="asrOn ? 'danger' : 'default'" title="语音输入（浏览器 Web Speech API）" />
    <el-input
      v-model="text"
      type="textarea"
      :rows="1"
      autosize
      :placeholder="file ? '请输入检测要求…' : '输入检测要求或追问…'"
      @keydown.enter.exact.prevent="send"
      :disabled="chat.streaming"
    />
    <el-button type="primary" :loading="chat.streaming" @click="send">发送</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from "vue";
import { Picture, Microphone } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { useChatStore } from "../../stores/chat";

const chat = useChatStore();
const text = ref("");
const file = ref<File | null>(null);
const filePreviewUrl = ref("");
const asrOn = ref(false);
const speechSupported = "webkitSpeechRecognition" in window || "SpeechRecognition" in window;

function onFile(uploadFile: any) {
  const raw = uploadFile.raw;
  if (!raw) return;
  clearFile();
  file.value = raw;
  filePreviewUrl.value = URL.createObjectURL(raw);
}

function clearFile() {
  if (filePreviewUrl.value) URL.revokeObjectURL(filePreviewUrl.value);
  file.value = null;
  filePreviewUrl.value = "";
}

function send() {
  const t = text.value.trim();
  if (!t && !file.value) return;
  const f = file.value;
  const content = t || `检测这个工件（${f?.name}）`;
  text.value = "";
  clearFile();
  chat.send(content, f);
}

function toggleAsr() {
  const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  if (!SR) {
    ElMessage.warning("当前浏览器不支持 Web Speech API");
    return;
  }
  if (asrOn.value) {
    asrOn.value = false;
    return;
  }
  const rec = new SR();
  rec.lang = "zh-CN";
  rec.onresult = (e: any) => {
    text.value += e.results[0][0].transcript;
  };
  rec.onend = () => (asrOn.value = false);
  rec.start();
  asrOn.value = true;
}

onBeforeUnmount(clearFile);
</script>

<style scoped>
.attach-row { padding: 0 0 8px; }
.attach-thumb {
  position: relative;
  width: 64px;
  height: 64px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  background: #f3f4f6;
}
.attach-thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
.attach-remove {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}
.attach-remove:hover { background: rgba(0, 0, 0, 0.75); }
</style>
