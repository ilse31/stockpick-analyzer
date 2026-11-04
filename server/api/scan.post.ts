import { idxRequest } from "../utils/idx-request";

export default defineEventHandler(async (event) => {
  const origin = getHeader(event, "origin");
  if (origin && origin !== getRequestURL(event).origin) {
    throw createError({ statusCode: 403, statusMessage: "Forbidden" });
  }

  return idxRequest(event, "/scan", "POST");
});
