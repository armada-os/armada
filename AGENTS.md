# AGENTS.md

Rules for AI coding agents working in this repository. Human contributors
should follow the code and patch conventions too.

## GitHub and Git

- By default, do not commit. Leave changes in the working tree (staged with
  `git add` is fine) for a human to review, then stop. Commit only when the
  human explicitly asks for it. Commits get no `Co-Authored-By:` or
  generated-tool trailers.
- Do not push, open PRs, merge, or rewrite published history. The human
  pushes.
- Do not post anything to GitHub as the user: no PR or issue comments,
  reviews, approvals, labels, or issue creation. `gh` is authenticated as a
  real person and everything it posts appears publicly under their name.
  Draft the text in the conversation and let the human post it.
- An ambiguous follow-up ("ok", "continue", "what next") is not approval to
  publish anything. Only an explicit yes for that specific content is.

## Comments

Default: no comment. Add one only when the reason is not recoverable from the
code or a quick `git log -p`.

Keep:

- Hidden constraints the code does not show.
- Workarounds for specific upstream bugs. Name the bug and say when the
  workaround can be removed:

      # <component> <does the wrong thing> (<link or short cause>).
      # Remove once <fixed upstream / version X ships>.

- Surprising ordering or invariants ("must run before X because Y locks it").
- Magic numbers and GUIDs that have no name.

Cut:

- Comments that restate what the code does.
- History and pivot narratives ("was X, switched to Y"), dates, and anything
  referring to a conversation, debug session, or review. That belongs in the
  commit message.
- References to private docs, tracker IDs, or callers ("used by X"). Code in
  this repo must stand on its own.
- Multi-paragraph rationale. One short line, leading with the constraint.
- Long comments in declarative config (systemd, udev, dracut, sysctl, tuned,
  sysusers, binfmt.d, bootc). At most one short line when a setting is easy to
  misread.

Style:

- No first person ("we", "our"). Name Armada or use passive voice.
- Plain ASCII punctuation. No em or en dashes in comments, docs, or
  user-facing strings.

Before handing back, recheck every comment, patch body, and `PATCHES.md` line
you wrote against these rules.

## Patches (`packages/*/patches/`)

- New patches use `git format-patch` output. The body explains why the change
  is needed, like an upstream commit message. `From:` is the human author's
  own identity, never an agent or tool name or the old
  `Armada <noreply@armada.local>` placeholder.
- Leave imported patches' filenames, authors, and trailers as they are.
- A fix to code that an imported patch introduced goes into that patch, with
  a `notes:` line. Fixes to upstream code get their own patch.
- Record every patch in the package's `PATCHES.md`, following the fields
  already used there:
  - `source:` a permanent URL pinned to a commit, or `armada` for original
    work.
  - `upstream:` (where used) submission status only: a URL, `local`, or
    `unknown`.
  - `notes:` only when the patch deviates from its source. One sentence
    stating the deviation. Verbatim imports get none.
