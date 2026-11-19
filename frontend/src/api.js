import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
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
