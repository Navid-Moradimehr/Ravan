export class HttpError extends Error {
  status: number;
  details: unknown;

  constructor(message: string, status: number, details: unknown = null) {
    super(message);
    this.name = "HttpError";
    this.status = status;
    this.details = details;
  }
}

function stringifyDetail(detail: unknown): string | null {
  if (typeof detail === "string") {
    return detail.trim() || null;
  }

  if (Array.isArray(detail)) {
    const values = detail
      .map((item) => stringifyDetail(item))
      .filter((item): item is string => Boolean(item));
    return values.length ? values.join(", ") : null;
  }

  if (detail && typeof detail === "object") {
    for (const key of ["error", "detail", "message", "title", "reason"] as const) {
      const value = (detail as Record<string, unknown>)[key];
      const message = stringifyDetail(value);
      if (message) {
        return message;
      }
    }
  }

  return null;
}

export function formatErrorMessage(error: unknown, fallback = "Something went wrong"): string {
  if (error instanceof HttpError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message || fallback;
  }

  const message = stringifyDetail(error);
  return message ?? fallback;
}

export async function readResponseError(response: Response): Promise<HttpError> {
  const contentType = response.headers.get("content-type") ?? "";
  let details: unknown = null;

  try {
    details = contentType.includes("application/json") ? await response.json() : await response.text();
  } catch {
    details = null;
  }

  const message =
    stringifyDetail(details) ??
    response.statusText?.trim() ??
    `Request failed with status ${response.status}`;

  return new HttpError(message, response.status, details);
}

export async function requestJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    cache: "no-store",
    ...init,
  });

  if (!response.ok) {
    throw await readResponseError(response);
  }

  return response.json() as Promise<T>;
}
