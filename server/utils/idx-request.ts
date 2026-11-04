import type { H3Event } from "h3";

export async function idxRequest(event: H3Event, path: string, method: "GET" | "POST", query?: { symbol: string }) {
  const { idxBackend } = useRuntimeConfig(event);
  const response = await $fetch
    .raw(path, {
      baseURL: idxBackend,
      method,
      query,
      ignoreResponseError: true,
      retry: 0,
    })
    .catch(() => {
      throw createError({
        statusCode: 502,
        message: "Backend IDX tidak dapat dijangkau.",
      });
    });

  setResponseStatus(event, response.status);
  setResponseHeader(event, "Cache-Control", "no-store");
  return response._data;
}
