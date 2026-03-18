import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    snippet_reads: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "10s", target: 20 },
        { duration: "30s", target: 20 },
        { duration: "10s", target: 0 },
      ],
      gracefulRampDown: "5s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<500"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const SHORT_ID = __ENV.SHORT_ID;
const VERSION = __ENV.VERSION;

function buildPath() {
  const basePath = `/v1/api/snippet/${SHORT_ID}`;
  if (!VERSION) {
    return basePath;
  }

  return `${basePath}?version=${VERSION}`;
}

export function setup() {
  if (!SHORT_ID) {
    throw new Error("Set SHORT_ID to a public snippet short_id before running k6");
  }

  const path = buildPath();
  const warmup = http.get(`${BASE_URL}${path}`);
  check(warmup, {
    "warmup status is 200": (r) => r.status === 200,
  });

  return { path };
}

export default function (data) {
  const response = http.get(`${BASE_URL}${data.path}`);
  check(response, {
    "status is 200": (r) => r.status === 200,
    "response includes id": (r) => !!r.json("id"),
  });

  sleep(0.2);
}