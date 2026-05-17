import { friendlyErrorMessage } from "./lib/apiErrors.js";

/**
 * If `VITE_API_BASE_URL` is missing at build time (common when Vercel env UI misbehaves),
 * production builds still point at Render. Override via env or change this URL if yours differs.
 */
const PRODUCTION_API_FALLBACK = "https://arxiv-research-hub-1.onrender.com";

function resolveApiBase() {
  const fromEnv = import.meta.env.VITE_API_BASE_URL?.trim();
  if (fromEnv) return fromEnv;
  if (import.meta.env.PROD) return PRODUCTION_API_FALLBACK;
  return "http://127.0.0.1:8000";
}

const API_BASE = resolveApiBase().replace(/\/$/, "");

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

/** Abort hung requests so KPIs don't sit on "—" forever. */
async function fetchApi(path, options = {}, timeoutMs = 25_000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    return await fetch(apiUrl(path), { ...options, signal: ctrl.signal });
  } catch (e) {
    if (e?.name === "AbortError") {
      throw new Error("Request timed out — is the API responding?");
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export async function getStats() {
  const res = await fetchApi("/stats");
  return parseResponse(res);
}

export async function getPapersOverTime(days = 90) {
  const params = new URLSearchParams({ days: String(days) });
  const res = await fetch(apiUrl(`/analytics/papers-over-time?${params.toString()}`));
  return parseResponse(res);
}

export async function getPipelineRuns({ page = 1, pageSize = 10 } = {}) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  const res = await fetch(apiUrl(`/pipeline-runs?${params.toString()}`));
  return parseResponse(res);
}

export async function getPipelineBusy() {
  const res = await fetch(apiUrl("/pipeline-status"));
  return parseResponse(res);
}

export async function searchCorpus({ q, mode = "hybrid", bucket, limit = 15, rerank = false }) {
  const params = new URLSearchParams({ q, mode, limit: String(limit) });
  if (bucket) params.set("bucket", bucket);
  if (rerank) params.set("rerank", "true");
  const res = await fetch(apiUrl(`/search?${params.toString()}`));
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
  if (res.status === 409) {
    const text = await res.text();
    throw new Error(friendlyErrorMessage(text || res.statusText));
  }
  return parseResponse(res);
}

export async function cancelPipeline() {
  const res = await fetch(apiUrl("/cancel-pipeline"), { method: "POST" });
  if (res.status === 409) {
    const text = await res.text();
    throw new Error(friendlyErrorMessage(text || res.statusText));
  }
  return parseResponse(res);
}
