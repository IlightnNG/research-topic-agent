export interface AppError extends Error {
  code: string;
  status: number;
}

const BASE = "";

export function describeError(error: unknown): string {
  if (!error) return "";
  if (typeof error === "string") return error;
  if (error instanceof Error) return error.message;
  return String(error);
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const code = (payload && payload.code) || `HTTP_${response.status}`;
    const message = (payload && payload.message) || response.statusText;
    const error = new Error(`${code}: ${message}`) as AppError;
    error.code = code;
    error.status = response.status;
    throw error;
  }
  return payload as T;
}

export const httpErrorCode = (error: unknown): string =>
  (error as AppError | undefined)?.code ?? "";
