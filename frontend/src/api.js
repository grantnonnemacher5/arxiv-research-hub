import { friendlyErrorMessage } from "./lib/apiErrors.js";

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

export function apiUrl(path) {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${p}`;
}

async function parseResponse(res) {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(friendlyErrorMessage(text || res.statusText));
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return res.text();
}

export async function getStats() {
  const res = await fetch(apiUrl("/stats"));
  return parseResponse(res);
}

export async function getPapers({ page = 1, pageSize = 20, bucket, q } = {}) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (bucket) params.set("bucket", bucket);
  if (q) params.set("q", q);
  const res = await fetch(apiUrl(`/papers?${params.toString()}`));
  return parseResponse(res);
}

export async function generateReport(period) {
  const res = await fetch(apiUrl(`/generate-report/${period}`), {
    method: "POST",
  });
  return parseResponse(res);
}

export async function listReports() {
  const res = await fetch(apiUrl("/reports"));
  return parseResponse(res);
}

export async function runPipeline() {
  const res = await fetch(apiUrl("/run-pipeline"), { method: "POST" });
  return parseResponse(res);
}
