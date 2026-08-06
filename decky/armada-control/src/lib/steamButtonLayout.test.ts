import assert from "node:assert/strict";
import test from "node:test";
import { selectBuiltInController, type ControllerInfo } from "./steamButtonLayout.ts";

function controller(
  nControllerIndex: number,
  eControllerType: number,
  unUniqueID: number,
): ControllerInfo {
  return {
    nControllerIndex,
    eControllerType,
    unUniqueID,
    unVendorID: 0,
    unProductID: 0,
    strSerialNumber: "",
  };
}

test("selects the built-in target type instead of the lowest external controller", () => {
  const externalXbox = controller(0, 31, 10);
  const builtInDeck = controller(2, 4, 20);
  assert.equal(
    selectBuiltInController([externalXbox, builtInDeck], [], "deck-uhid", null, false),
    2,
  );
});

test("waits when the built-in controller disappears during recreation", () => {
  const builtInDeck = controller(0, 4, 20);
  const externalXbox = controller(1, 31, 10);
  assert.equal(
    selectBuiltInController(
      [externalXbox],
      [builtInDeck, externalXbox],
      "xb360",
      null,
      true,
    ),
    null,
  );
});

test("selects the newly recreated controller instead of an existing external match", () => {
  const builtInDeck = controller(0, 4, 20);
  const externalXbox = controller(1, 31, 10);
  const recreatedXbox = controller(3, 31, 30);
  assert.equal(
    selectBuiltInController(
      [externalXbox, recreatedXbox],
      [builtInDeck, externalXbox],
      "xb360",
      null,
      true,
    ),
    3,
  );
});

test("recognizes recreation when Steam reuses the controller index", () => {
  const builtInDeck = controller(0, 4, 20);
  const recreatedXbox = controller(0, 31, 30);
  assert.equal(
    selectBuiltInController(
      [recreatedXbox],
      [builtInDeck],
      "xb360",
      null,
      true,
    ),
    0,
  );
});
