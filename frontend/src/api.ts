/** Server calls. Every call has a short timeout so the app never hangs when the server is unreachable. */
export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

export const OFFLINE = 0;

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown; timeout?: number } = {}): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), init.timeout ?? 8000);
  const headers: Record<string, string> = { Accept: "application/json" };
  let body = init.body;
  if (init.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.json);
  }
  let response: Response;
  try {
    response = await fetch(path, { ...init, body, headers: { ...headers, ...(init.headers as object) }, credentials: "same-origin", signal: controller.signal });
  } catch {
    throw new ApiError("Can't reach the server. Is Tailscale on and the server running?", OFFLINE);
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) {
    let detail = `Server error ${response.status}`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") detail = data.detail;
      else if (Array.isArray(data.detail)) detail = data.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      /* not JSON */
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

export async function apiBlob(path: string, timeout = 15000): Promise<Blob | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(path, { credentials: "same-origin", signal: controller.signal });
    return response.ok ? await response.blob() : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export function upload<T>(path: string, file: Blob, fields: Record<string, string> = {}): Promise<T> {
  const form = new FormData();
  form.append("photo", file, "photo.jpg");
  for (const [k, v] of Object.entries(fields)) form.append(k, v);
  return api<T>(path, { method: "POST", body: form, timeout: 60000 });
}

/** Shrink camera photos before upload (phones produce 4–12 MB images). */
export async function shrinkPhoto(file: File, maxSide = 1600): Promise<Blob> {
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    return await new Promise<Blob>((resolve) => canvas.toBlob((b) => resolve(b ?? file), "image/jpeg", 0.88));
  } catch {
    return file;
  }
}
