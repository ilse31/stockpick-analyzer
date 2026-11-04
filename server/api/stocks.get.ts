import { defineEventHandler } from "h3";
import { idxRequest } from "../utils/idx-request";

export default defineEventHandler((event) =>
  idxRequest(event, "/stocks", "GET"),
);
