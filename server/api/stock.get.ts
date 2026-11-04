import { idxRequest } from "../utils/idx-request";

export default defineEventHandler((event) => {
  const { symbol } = getQuery(event);
  if (typeof symbol !== "string" || !/^[A-Z0-9]{1,12}$/i.test(symbol)) {
    throw createError({
      statusCode: 400,
      message: "Masukkan kode saham yang valid.",
    });
  }
  return idxRequest(event, "/stock", "GET", { symbol });
});
