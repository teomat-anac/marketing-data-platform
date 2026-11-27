# Domain docs

How the engineering skills read and update this repo's domain documentation. Single-context repo: one glossary, one decision log.

## Before exploring, read these

- **`docs/glossary.md`**: the project's terms, metrics and tools.
- **`docs/architecture.md` §6 Decisions**: the decision log (D1, D2, …). Read the rows that touch the area you're about to work in.
- **`docs/requirements.md`**: the source of truth for *what* to build.

## Where new terms and decisions go

These two files are the only homes for terms and decisions:

- A skill's `GLOSSARY.md` maps to `docs/glossary.md`. Add a new term to the section that fits it.
- A skill's `docs/adr/` maps to the §6 table. "Write an ADR" means adding the next D-number row: the decision, its status, a one-line why. "ADR-NNNN" means row D-NNN.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `docs/glossary.md`. Use the glossary's own term rather than a synonym.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag decision conflicts

If your output contradicts a decision in §6, surface it explicitly rather than silently overriding:

> _Contradicts D17 (revenue is counted before refunds), but worth reopening because…_
