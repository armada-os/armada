import assert from "node:assert/strict";
import test from "node:test";

import { updateNotice } from "../src/lib/updateStatus.ts";

test("only blocking results produce a notice", () => {
  for (const result of ["available", "up_to_date", "staged", "toString", "unknown"]) {
    assert.equal(updateNotice({ result }), null);
  }
  assert.equal(updateNotice(null), null);
});

test("no_space reports the missing amount including the reserve, rounded up", () => {
  // Values from a real RP6 journal: 6354919334 needed + 2 GiB reserve, 2716225536 free.
  const notice = updateNotice({
    result: "no_space", needed_bytes: 6354919334, reserve_bytes: 2147483648, available_bytes: 2716225536,
  });
  assert.deepEqual(notice, { key: "update.noSpace", size: "5.8 GB", toast: true });
});

test("network failures stay out of toasts", () => {
  assert.equal(updateNotice({ result: "remote_unreachable" })?.toast, false);
  assert.equal(updateNotice({ result: "apply_failed" })?.toast, true);
});
