export type User = { id: string; email: string; full_name: string; role: "USER" | "ADMIN"; permissions: string[] };
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }
let queue: Promise<unknown> = Promise.resolve();
function locked<T>(work: () => Promise<T>): Promise<T> {
  const execute = async (): Promise<T> => navigator.locks ? await navigator.locks.request("creditiq-session", work) : await work();
  const result = queue.then(execute, execute); queue = result.catch(() => undefined); return result;
}
async function raw(path: string, options: RequestInit = {}) {
  return fetch(`/api/v1${path}`, { ...options, credentials: "include", cache: "no-store" });
}
async function mutation(path: string, options: RequestInit) {
  const csrf = await raw("/auth/csrf");
  if (!csrf.ok) throw new ApiError(csrf.status, "Unable to establish a secure session.");
  const { csrf_token } = await csrf.json();
  return raw(path, { ...options, headers: { ...options.headers, "Content-Type": "application/json", "X-CSRF-Token": csrf_token } });
}
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const changing = options.method && options.method !== "GET";
  const run = () => changing ? mutation(path, options) : raw(path, options);
  let response = changing ? await locked(run) : await run();
  if (response.status === 401 && !path.startsWith("/auth/")) {
    const recovered = await locked(async () => {
      // Another tab/request may already have rotated cookies while this one waited.
      if ((await raw("/me")).ok) return true;
      return (await mutation("/auth/refresh", { method: "POST" })).ok;
    });
    if (recovered) response = changing ? await locked(run) : await run();
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const detail = typeof error.detail === "string" ? error.detail : Array.isArray(error.detail)
      ? error.detail.map((e: { loc: string[]; msg: string }) => `${e.loc.slice(1).join(".")}: ${e.msg}`).join("; ") : "Request failed. Please try again.";
    throw new ApiError(response.status, detail);
  }
  return response.status === 204 ? undefined as T : response.json();
}
