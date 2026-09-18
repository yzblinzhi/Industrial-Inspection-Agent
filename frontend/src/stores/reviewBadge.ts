import { defineStore } from "pinia";
import { http } from "../api/http";

/** 侧栏"复核申请处理"的被驳回感叹号（存在未处理被驳回工单时常显）。 */
export const useReviewBadge = defineStore("reviewBadge", {
  state: () => ({ rejected: 0 }),
  getters: {
    showAlert: (s) => s.rejected > 0,
  },
  actions: {
    async refresh() {
      try {
        const { data } = await http.get("/reviews/rejected-count");
        this.rejected = data.count || 0;
      } catch {
        this.rejected = 0;
      }
    },
  },
});
