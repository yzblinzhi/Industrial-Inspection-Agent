import axios from "axios";
import { ElMessage } from "element-plus";
import { useAuthStore } from "../stores/auth";

export const http = axios.create({ baseURL: "/api/v1", timeout: 60000 });

http.interceptors.request.use((config) => {
  const auth = useAuthStore();
  if (auth.token) config.headers.Authorization = `Bearer ${auth.token}`;
  return config;
});

http.interceptors.response.use(
  (resp) => resp,
  (err) => {
    if (err.response?.status === 401) {
      useAuthStore().logout();
    } else {
      ElMessage.error(err.response?.data?.detail || "请求失败");
    }
    return Promise.reject(err);
  }
);

export interface UploadResult {
  image_key: string;
  preview_url: string;
}

export async function uploadImage(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await http.post<UploadResult>("/upload/image", form);
  return data;
}
