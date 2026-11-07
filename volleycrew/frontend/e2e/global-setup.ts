import { execFileSync } from "node:child_process";

export default function setup() {
  const url = process.env.VOLLEYCREW_E2E_DATABASE_URL;
  if (!url || !new URL(url).pathname.endsWith("_test")) {
    throw new Error(
      "Set VOLLEYCREW_E2E_DATABASE_URL to a disposable *_test database",
    );
  }
  const result = execFileSync("python3", ["../../scripts/dev.py", "e2e-seed"], {
    encoding: "utf8",
    env: { ...process.env, VOLLEYCREW_DATABASE_URL: url },
  });
  const seed = JSON.parse(result.trim());
  process.env.E2E_ROOM_MEETINGS = JSON.stringify(seed.room_meetings);
  process.env.E2E_ADMIN_ID = seed.admin_id;
  process.env.E2E_INVITE = seed.invite;
  process.env.E2E_CALENDAR_MONTH = seed.calendar_month;
  process.env.E2E_CANCELLED_ID = seed.cancelled_id;
  process.env.E2E_ENROLLMENT_MEETINGS = JSON.stringify(
    seed.enrollment_meetings,
  );
}
