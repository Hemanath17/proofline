"use client";

import { getStoredActorId } from "@/lib/session";

/** Every API error surfaces through this one shape: a status code, the
 * `detail` string the API always sends (CLAUDE.md: "a 403 names the
 * rule"), and the raw body for callers that need more (e.g. a 409's
 * `current_state`). */
export class ApiError extends Error {
  status: number;
  detail: string;
  body: unknown;

  constructor(status: number, detail: string, body: unknown) {
    super(detail);
    this.status = status;
    this.detail = detail;
    this.body = body;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "X-Proofline-Actor": getStoredActorId(),
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  const text = await response.text();
  const body = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : response.statusText;
    throw new ApiError(response.status, detail, body);
  }
  return body as T;
}

export function apiFetch<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function apiPost<T>(path: string, payload?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}
