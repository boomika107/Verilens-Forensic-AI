import axios from "axios";
export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000" });
api.interceptors.request.use((c) => { const t = localStorage.getItem("vl_token"); if (t) c.headers.Authorization = `Bearer ${t}`; return c; });
api.interceptors.response.use((r) => r, (e) => { if (e.response?.status === 401 && !location.pathname.startsWith("/login")) { localStorage.removeItem("vl_token"); location.href = "/login"; } return Promise.reject(e); });
export const errMsg = (e: any) => { const d = e?.response?.data?.detail; return typeof d === "string" ? d : d ? JSON.stringify(d) : e?.message || "Error"; };
export const DISCLAIMER = "AI-assisted analysis of supplied information. Not a determination of guilt, deception, identity or legal admissibility. All findings require independent human verification.";
