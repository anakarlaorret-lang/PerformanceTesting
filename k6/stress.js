import { runJourney } from "./lib/eventflow.js";

const maxVus = Number(__ENV.STRESS_MAX_VUS || 30);
const rampDuration = __ENV.STRESS_RAMP_DURATION || "30s";
const stepDuration = __ENV.STRESS_STEP_DURATION || "1m";
const rampDownDuration = __ENV.STRESS_RAMP_DOWN_DURATION || "30s";
if (!Number.isInteger(maxVus) || maxVus < 1) {
  throw new Error("STRESS_MAX_VUS must be a positive integer");
}

export const options = {
  scenarios: {
    stress: {
      executor: "ramping-vus",
      startVUs: 1,
      stages: [
        { duration: rampDuration, target: Math.min(5, maxVus) },
        { duration: stepDuration, target: Math.min(10, maxVus) },
        { duration: stepDuration, target: Math.min(20, maxVus) },
        { duration: stepDuration, target: maxVus },
        { duration: rampDownDuration, target: 0 },
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
  runJourney({ hotEvent: true });
}
