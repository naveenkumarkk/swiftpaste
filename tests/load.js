import http from "k6/http";
import { check } from "k6";

export const options = {
  vus: 100,
  duration: "30s",
};

export default function () {
  const res = http.get("http://host.docker.internal:8000/v1/api/snippet/view/FuKtIeXQ");
  check(res, { "status 200": (r) => r.status === 200 });
}