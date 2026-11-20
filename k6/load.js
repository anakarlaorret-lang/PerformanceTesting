import { runJourney } from "./lib/eventflow.js";

const vus = Number(__ENV.LOAD_VUS || 10);
if (!Number.isInteger(vus) || vus < 1) {
  throw new Error("LOAD_VUS must be a positive integer");
}

export const options = {
  scenarios: {
    load: {
      executor: "ramping-vus",
      startVUs: 1,
      stages: [
        { duration: "30s", target: vus },
        { duration: __ENV.LOAD_HOLD || "3m", target: vus },
        { duration: "30s", target: 0 },
      ],
    },
  },
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
  thresholds: {
    checks: ["rate==1"],
    http_req_failed: ["rate<0.01"],
  },
};

export default function () {
  runJourney();
}
