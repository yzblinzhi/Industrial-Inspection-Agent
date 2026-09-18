<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">喷涂质检智能体</div>
      <div class="new-btn-wrap">
        <button class="new-btn" @click="newSession">＋ 新检测会话</button>
      </div>
      <nav class="nav">
        <button class="nav-item" :class="{ active: route.name === 'chat' }" @click="router.push('/')">
          💬 质检对话
        </button>
        <button class="nav-item" :class="{ active: route.name === 'history' }" @click="router.push('/history')">
          📋 历史检测记录
        </button>
        <button class="nav-item" :class="{ active: route.name === 'database' }" @click="router.push('/database')">
          📦 检测数据库
        </button>
        <button class="nav-item" :class="{ active: route.name === 'myreviews' }" @click="router.push('/my-reviews')">
          <el-badge :value="badge.showAlert ? '!' : ''" :hidden="!badge.showAlert" type="danger">
            📨 复核申请处理
          </el-badge>
        </button>
        <button v-if="auth.canReview" class="nav-item" :class="{ active: route.name === 'review' }" @click="router.push('/review')">
          🔍 复核工作台
        </button>
        <button v-if="auth.isAdmin" class="nav-item" :class="{ active: route.name === 'admin' }" @click="router.push('/admin')">
          ⚙️ 系统管理
        </button>
      </nav>
      <el-divider style="margin: 10px 0" />
      <div class="list-label">会话记录</div>
      <div class="session-list">
        <div
          v-for="s in sessionsStore.list"
          :key="s.session_id"
          class="session-item"
          :class="{ active: s.session_id === chat.sessionId }"
          @click="openSession(s)"
        >
          {{ s.title || "未命名会话" }}
        </div>
      </div>
      <div class="user-bar">
        <div>
          <div class="u-name">{{ auth.user?.display_name || auth.user?.username }}</div>
          <div class="u-role">{{ auth.roleCn }}</div>
        </div>
        <div>
          <el-button v-if="auth.isAdmin" text size="small" @click="$router.push('/admin')">管理</el-button>
          <el-button text size="small" type="danger" @click="auth.logout()">退出</el-button>
        </div>
      </div>
    </aside>
    <main class="chat-area">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../../stores/auth";
import { useChatStore } from "../../stores/chat";
import { useSessionsStore } from "../../stores/sessions";
import { useReviewBadge } from "../../stores/reviewBadge";

const auth = useAuthStore();
const chat = useChatStore();
const sessionsStore = useSessionsStore();
const badge = useReviewBadge();
const router = useRouter();
const route = useRoute();

function newSession() {
  chat.$reset();
  router.push("/");
}

function openSession(s: any) {
  router.push("/");
  chat.loadSession(s.session_id);
}

onMounted(() => {
  sessionsStore.refresh();
  badge.refresh();
  // 轻量轮询：工艺员驳回后，操作工侧栏感叹号实时亮起/消失
  setInterval(() => badge.refresh(), 30_000);
});
</script>
