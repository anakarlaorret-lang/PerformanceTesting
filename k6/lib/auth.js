if (!/^[0-9a-f]{64}$/.test(__ENV.EVENTFLOW_TOKEN || "")) {
  throw new Error("EVENTFLOW_TOKEN must be a valid API token");
}

export const authHeaders = { Authorization: `Bearer ${__ENV.EVENTFLOW_TOKEN}` };
