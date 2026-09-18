import { defineStore } from "pinia";
import { http } from "../api/http";

export interface UserInfo {
  user_id: number;
  username: string;
  role: "operator" | "process_engineer" | "admin";
  display_name: string | null;
}

const ROLE_CN: Record<string, string> = {
  operator: "操作工",
  process_engineer: "工艺员",
  admin: "管理员",
};

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem("qc_token") || "",
    user: JSON.parse(localStorage.getItem("qc_user") || "null") as UserInfo | null,
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    roleCn: (s) => (s.user ? ROLE_CN[s.user.role] || s.user.role : ""),
    canReview: (s) => s.user?.role === "process_engineer" || s.user?.role === "admin",
    isAdmin: (s) => s.user?.role === "admin",
  },
  actions: {
    async login(username: string, password: string) {
      const { data } = await http.post("/auth/login", { username, password });
      this.token = data.access_token;
      this.user = {
        user_id: data.user_id,
        username: data.username,
        role: data.role,
        display_name: data.display_name,
      };
      localStorage.setItem("qc_token", this.token);
      localStorage.setItem("qc_user", JSON.stringify(this.user));
    },
    logout() {
      this.token = "";
      this.user = null;
      localStorage.removeItem("qc_token");
      localStorage.removeItem("qc_user");
      location.href = "/login";
    },
  },
});
