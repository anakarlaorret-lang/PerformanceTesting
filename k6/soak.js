import { runJourney } from "./lib/eventflow.js";

const vus = Number(__ENV.SOAK_VUS || 5);
if (!Number.isInteger(vus) || vus < 1) {
  throw new Error("SOAK_VUS must be a positive integer");
}

export const options = {
  scenarios: {
    soak: {
      executor: "constant-vus",
      vus,
      duration: __ENV.SOAK_DURATION || "30m",
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
