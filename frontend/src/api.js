
import axios from "axios";

export const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_BASE_URL}/api`,
});

export function errorMessage(error, fallback) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (error?.message) {
    return error.message;
  }
  return fallback;
}
