import http from "k6/http";
import { check, sleep } from "k6";
import { Trend } from "k6/metrics";
import { authHeaders } from "./lib/auth.js";

const BASE_URL = (__ENV.BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const VUS = Number(__ENV.VUS || 5);
const DURATION = __ENV.DURATION || "2m";
const THINK_TIME_SECONDS = Number(__ENV.THINK_TIME_SECONDS || 1);

if (!Number.isInteger(VUS) || VUS < 1) {
  throw new Error("VUS must be a positive integer");
}
if (!Number.isFinite(THINK_TIME_SECONDS) || THINK_TIME_SECONDS < 0) {
  throw new Error("THINK_TIME_SECONDS must be a non-negative number");
}

const eventsListDuration = new Trend("events_list_duration");
const eventDetailDuration = new Trend("event_detail_duration");
const availabilityDuration = new Trend("availability_duration");
const reservationCreateDuration = new Trend("reservation_create_duration");
const reservationConfirmDuration = new Trend("reservation_confirm_duration");
const reservationCancelDuration = new Trend("reservation_cancel_duration");

export const options = {
  scenarios: {
    mixed_baseline: {
      executor: "constant-vus",
      vus: VUS,
      duration: DURATION,
    },
  },
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
  thresholds: {
    checks: ["rate==1"],
    http_req_failed: ["rate<0.01"],
  },
};

function expectStatus(response, expectedStatus, description, durationMetric) {
  durationMetric.add(response.timings.duration);
  return check(response, {
    [description]: (result) => result.status === expectedStatus,
  });
}

export default function () {
  const eventsResponse = http.get(`${BASE_URL}/api/events?limit=100`, {
    tags: { name: "GET /api/events" },
  });
  if (!expectStatus(eventsResponse, 200, "list events returns 200", eventsListDuration)) {
    return;
  }

  const events = eventsResponse.json();
  if (
    !check(events, {
      "event list contains seeded events": (body) =>
        Array.isArray(body) && body.length > 0,
    })
  ) {
    return;
  }
  const event = events[(__VU + __ITER) % events.length];

  const detailResponse = http.get(`${BASE_URL}/api/events/${event.id}`, {
    tags: { name: "GET /api/events/{id}" },
  });
  if (!expectStatus(detailResponse, 200, "event detail returns 200", eventDetailDuration)) {
    return;
  }

  const availabilityResponse = http.get(
    `${BASE_URL}/api/events/${event.id}/availability`,
    { tags: { name: "GET /api/events/{id}/availability" } },
  );
  if (
    !expectStatus(
      availabilityResponse,
      200,
      "availability returns 200",
      availabilityDuration,
    )
  ) {
    return;
  }

  const createResponse = http.post(
    `${BASE_URL}/api/reservations`,
    JSON.stringify({
      event_id: event.id,
      quantity: 1,
      idempotency_key: `k6-${Date.now()}-${__VU}-${__ITER}`,
    }),
    {
      headers: { ...authHeaders, "Content-Type": "application/json" },
      tags: { name: "POST /api/reservations" },
    },
  );
  if (
    !expectStatus(
      createResponse,
      201,
      "reservation creation returns 201",
      reservationCreateDuration,
    )
  ) {
    return;
  }

  const reservation = createResponse.json();
  if (
    !check(reservation, {
      "reservation response contains an integer id": (body) =>
        body && Number.isInteger(body.id),
    })
  ) {
    return;
  }

  const confirmResponse = http.post(
    `${BASE_URL}/api/reservations/${reservation.id}/confirm`,
    null,
    { headers: authHeaders, tags: { name: "POST /api/reservations/{id}/confirm" } },
  );
  if (
    !expectStatus(
      confirmResponse,
      200,
      "reservation confirmation returns 200",
      reservationConfirmDuration,
    )
  ) {
    return;
  }

  const cancelResponse = http.del(
    `${BASE_URL}/api/reservations/${reservation.id}`,
    null,
    { headers: authHeaders, tags: { name: "DELETE /api/reservations/{id}" } },
  );
  expectStatus(
    cancelResponse,
    204,
    "reservation cancellation returns 204",
    reservationCancelDuration,
  );

  sleep(THINK_TIME_SECONDS);
}
