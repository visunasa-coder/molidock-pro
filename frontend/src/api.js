export const API_BASE =
  import.meta.env.VITE_API_URL || "https://molidock-pro-backend.onrender.com";
  
  const TOKEN_KEY = "molidock_access_token";

  export function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  export function setToken(token) {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  }

  async function parseResponse(response) {
    const contentType = response.headers.get("content-type") || "";
    if (!response.ok) {
      let message = response.statusText;
      if (contentType.includes("application/json")) {
        const payload = await response.json();
        message = payload.detail || JSON.stringify(payload);
      } else {
        message = await response.text();
      }
      throw new Error(message);
    }
    if (response.status === 204) return null;
    return response.json();
  }

  export async function request(path, options = {}) {
    const token = getToken();
    const headers = new Headers(options.headers || {});
    if (token) headers.set("Authorization", `Bearer ${token}`);
    if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    return parseResponse(response);
  }

  export async function register(payload) {
    return request("/auth/register", { method: "POST", body: JSON.stringify(payload) });
  }

  export async function login(email, password) {
    const body = new URLSearchParams();
    body.set("username", email);
    body.set("password", password);
    const data = await request("/auth/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    setToken(data.access_token);
    return data;
  }

  export function me() {
    return request("/auth/me");
  }

  export function health() {
    return request("/health");
  }

  export function createDockingJob(formData) {
    return request("/dock", { method: "POST", body: formData });
  }

  export function listJobs() {
    return request("/dock");
  }

  export function getJob(id) {
    return request(`/dock/${id}`);
  }

  export function runAdmet(smiles) {
    const body = new FormData();
    body.set("smiles", smiles);
    return request("/admet", { method: "POST", body });
  }

  export function createCheckout(plan) {
    return request(`/billing/checkout/${plan}`, { method: "POST" });
  }

  export async function getFileText(path) {
    const token = getToken();
    const response = await fetch(`${API_BASE}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) throw new Error(await response.text());
    return response.text();
  }

  export async function downloadFile(path, filename) {
    const token = getToken();
    const response = await fetch(`${API_BASE}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) throw new Error(await response.text());
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }

