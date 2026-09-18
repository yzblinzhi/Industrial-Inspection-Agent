import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: () => import("../views/LoginView.vue") },
    {
      path: "/",
      component: () => import("../components/layout/AppLayout.vue"),
      children: [
        { path: "", name: "chat", component: () => import("../views/ChatView.vue") },
        {
          path: "history",
          name: "history",
          component: () => import("../views/HistoryView.vue"),
        },
        {
          path: "database",
          name: "database",
          component: () => import("../views/DatabaseView.vue"),
        },
        {
          path: "my-reviews",
          name: "myreviews",
          component: () => import("../views/MyReviewsView.vue"),
        },
        {
          path: "review",
          name: "review",
          component: () => import("../views/ReviewView.vue"),
          meta: { roles: ["process_engineer", "admin"] },
        },
        {
          path: "admin",
          name: "admin",
          component: () => import("../views/AdminView.vue"),
          meta: { roles: ["admin"] },
        },
      ],
    },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (to.path !== "/login" && !auth.isLoggedIn) return "/login";
  const roles = to.meta.roles as string[] | undefined;
  if (roles && auth.user && !roles.includes(auth.user.role)) return "/";
  if (to.path === "/login" && auth.isLoggedIn) return "/";
  return true;
});

export default router;
