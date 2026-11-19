import axios from "axios";

const rawBase = import.meta.env.VITE_API_BASE_URL;
export const API_BASE = rawBase ? `${rawBase.replace(/\/+$/, "")}/api` : "/api";

export const api = axios.create({
  baseURL: API_BASE,
});

export function apiUrl(path = "") {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${cleanPath}`;
}

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
