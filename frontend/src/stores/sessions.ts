import { defineStore } from "pinia";
import { http } from "../api/http";

/** 左栏会话列表：新对话产生后由 chat store 触发 refresh() */
export const useSessionsStore = defineStore("sessions", {
  state: () => ({ list: [] as any[] }),
  actions: {
    async refresh() {
      try {
        const { data } = await http.get("/conversations");
        this.list = data;
      } catch {
        /* 静默失败：未登录等场景 */
      }
    },
  },
});
