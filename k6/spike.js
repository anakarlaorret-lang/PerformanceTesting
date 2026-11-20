import { runJourney } from "./lib/eventflow.js";

const baseVus = Number(__ENV.SPIKE_BASE_VUS || 5);
const spikeVus = Number(__ENV.SPIKE_VUS || 30);
const baseDuration = __ENV.SPIKE_BASE_DURATION || "30s";
const spikeDuration = __ENV.SPIKE_DURATION || "15s";
const recoveryDuration = __ENV.SPIKE_RECOVERY_DURATION || "30s";
const rampDownDuration = __ENV.SPIKE_RAMP_DOWN_DURATION || "15s";
if (
  !Number.isInteger(baseVus) ||
  baseVus < 1 ||
  !Number.isInteger(spikeVus) ||
  spikeVus < baseVus
) {
  throw new Error("SPIKE_VUS must be an integer greater than or equal to SPIKE_BASE_VUS");
}

export const options = {
  scenarios: {
    spike: {
      executor: "ramping-vus",
      startVUs: baseVus,
      stages: [
        { duration: baseDuration, target: baseVus },
        { duration: spikeDuration, target: spikeVus },
        { duration: recoveryDuration, target: baseVus },
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
