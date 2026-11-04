import { idxRequest } from "../utils/idx-request";

export default defineEventHandler((event) =>
  idxRequest(event, "/stocks", "GET"),
);
