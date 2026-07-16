export function forwardedHeaders(request: Request, includeJson = false): Record<string, string> {
  const headers: Record<string, string> = {};
  const authorization = request.headers.get("authorization");
  if (authorization) headers.Authorization = authorization;
  if (includeJson) headers["Content-Type"] = "application/json";
  return headers;
}
