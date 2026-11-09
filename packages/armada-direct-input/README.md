# Armada Direct Input

`armada-direct-input` runs in the direct controller mode, where InputPlumber is
masked and games and Steam read the raw rsinput gamepad node. It writes into
that node, so everything still sees one controller:

| Input | Written as |
|---|---|
| Left back paddle (`BTN_Z` on `gpio-keys-paddles`) | `BTN_SOUTH` (A) |
| Right back paddle (`BTN_C` on `gpio-keys-paddles`) | `BTN_EAST` (B) |
| Bottom right button (`BTN_BACK` on the gamepad) | Guide, then A 80 ms later, while held |

SDL maps no gamepad button to `BTN_BACK`, so Steam ignores that button on the
raw node. Guide plus A is Steam's Quick Access Menu chord; the order and the
80 ms steps are the ones InputPlumber's xpad target uses. With Steam Input off,
a game also sees that A press.

The gamepad is found by its phys path, `rsinput-gamepad/input0`. The paddles
are optional, so a board without `gpio-keys-paddles` gets only the Quick
Access chord. The kernel accepts only codes the gamepad node already
advertises, so this can duplicate existing buttons but cannot add new ones.

`armada-direct-input.service` starts it only while
`/etc/armada/direct-input` exists, which `controller-type set direct` creates.
