# Agent instructions

## Language
Everything in this project is in English: code, comments, docs, commit messages.

## Docs
- One document per topic, updated in place; git keeps the history.
- `docs/requirements.md` is the source of truth for *what* to build. Technical plans trace back to it.
- `docs/architecture.md` covers how it's built. Record each new design decision as the next D-number row in its §6, with its status and a one-line why.
- `docs/data-sources.md` covers the data: the GA4 sample, the synthetic ad-cost rules, how they join, and the exploration findings.
- `docs/costs.md` holds the Free Tier limits per service and the cost guardrails.
- `docs/glossary.md` holds the metrics and terms used in this project. Add new terms there.
- Docs describe the system as it is now, for a reader new to the project; git keeps the history.

## Public repo
The repo is public. Write `<project-id>` in place of the real GCP project and of any value derived from it (bucket names, service account emails); the real values live in gitignored files (D56).

## Working rules
- Ask before `terraform apply`/`destroy`, deploys, billable resources or IAM changes.
- Read provider attribute names from `terraform providers schema -json`.
- Pin all versions.
- Run the same checks as CI before a commit (`api/README.md`, `pipeline/README.md`, `terraform/README.md`).

## Guardrails
- `.claude/settings.json` allows read-only and validation commands, and always asks for anything that applies, deploys, deletes or changes IAM. Work within it.
- BigQuery queries always carry `--maximum_bytes_billed`; capped queries are pre-approved.

## Costs: stay in the Free Tier
- The project stays within the GCP Free Tier wherever possible (D14). Check every step that adds a GCP resource, a billable API call or more usage (Terraform, deploys, image pushes, LLM calls, large queries) against `docs/costs.md` §2.
- If it could go beyond the Free Tier or spend money, show this block at the **top** of the reply, **before** acting, and wait for the user's explicit OK:
  ```
  ⚠️ COST WARNING — <service>: <what could cost money>
  Free limit: <limit>  ·  Expected use: <estimate>  ·  Worst case: <estimate>
  Mitigation: <how we stay free, or why we can't>
  → Waiting for your OK before <action>.
  ```

## Agent skills

### Issue tracker

GitHub Issues on this repo, via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context, using `docs/glossary.md` and the decision log in `docs/architecture.md` §6. See `docs/agents/domain.md`.
