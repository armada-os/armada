# AYN Odin 3 asset notes

## Runtime artwork

- `controller.png`: 704 × 326 full-controller outline
- `controller-left.png`: 643 × 464 controller-settings left side
- `controller-right.png`: 643 × 464 controller-settings right side
- `a.png`, `b.png`, `x.png`, `y.png`: monochrome face-button glyphs
- `a-color.png`, `b-color.png`, `x-color.png`, `y-color.png`: rainbow
  face-button glyphs
- `select.png`, `start.png`, `home.png`, `back.png`: system glyphs
- `m1.png`, `m2.png`: back-button glyphs
- `dpad*.png`, `lstick*.png`, `rstick*.png`: directional glyphs
- `l1.png`, `r1.png`, `l2.png`, `r2.png`: shoulder and trigger glyphs
- `l2-soft.png`, `r2-soft.png`: half-pull trigger glyphs

All runtime files are transparent PNGs. The controller-settings halves are
crops of the same corrected controller master rather than independent
redraws.

## Face-button mapping

Armada preserves physical cardinal positions while Steam names the positions
using Xbox labels. Odin 3 uses Nintendo-layout legends:

| Steam slot | Odin position | Glyph |
|---|---|---|
| A / South | B | `b.png` |
| B / East | A | `a.png` |
| X / West | Y | `y.png` |
| Y / North | X | `x.png` |

The Rainbow option replaces only those four monochrome files with their
`-color` variants. All other controller artwork remains unchanged.

## Provenance and license

The CSS and controller-glyph theme derive from
[Handheld Controller Glyphs](https://github.com/victor-borges/handheld-controller-glyphs).
The upstream copyright and MIT license are preserved in `LICENSE`.
