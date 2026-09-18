<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2 style="margin-bottom: 4px">喷涂质检智能体</h2>
      <p style="color: #9ca3af; font-size: 13px; margin-bottom: 18px">喷涂作业后工件质量检测与评估系统 V1.0</p>
      <el-form @submit.prevent="doLogin">
        <el-form-item>
          <el-input v-model="username" placeholder="用户名" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="password" type="password" placeholder="密码" size="large" show-password />
        </el-form-item>
        <el-button type="primary" size="large" style="width: 100%" :loading="loading" native-type="submit">
          登 录
        </el-button>
      </el-form>
      <p style="font-size: 12px; color: #9ca3af; margin-top: 14px">
        演示账号：operator / Operator@123，engineer / Engineer@123，admin / Admin@123
      </p>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const router = useRouter();
const username = ref("engineer");
const password = ref("Engineer@123");
const loading = ref(false);

async function doLogin() {
  loading.value = true;
  try {
    await auth.login(username.value, password.value);
    router.push("/");
  } catch {
    ElMessage.error("登录失败");
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-wrap { height: 100%; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #e8f1fd 0%, #f5f6f8 100%); }
.login-card { width: 380px; padding: 10px 6px; }
</style>
