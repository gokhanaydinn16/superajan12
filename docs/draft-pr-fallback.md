# Draft PR fallback procedure

When the tools we depend on cannot move a draft pull request to *ready for review*, this document is the playbook we follow so the next person can finish without guesswork.

## When to use this
- The GitHub GraphQL mutation or connector call to `markPullRequestReadyForReview` fails with a schema/`htmlUrl` error.
- The PR is still marked as `draft`, CI is green, and there are no active review threads locking the branch.
- The failure happened after you finished development and you want to keep the same head commit and title/body.

## Verification checklist
1. Confirm the failure is a GitHub-side schema issue (the tool reports `htmlUrl`/`undefinedField` or `Pull Request is still a draft` with HTTP 405). Do not retry in a loop; note the error message for later.
2. Confirm the head SHA you want to merge is clean and `git status` is empty on your local branch.
3. Record the old draft PR number for traceability.
4. Ensure the branch has no outstanding review requests that must be ported to a new PR.

## Safe fall back steps
1. Close the existing draft PR without deleting the branch. Copy its title, body, and any important labels or milestone information into a temporary note.
2. Re-open a fresh PR from the same branch to the same base (`main`). Use the same title/body, and note the closed PR number in the new description for traceability.
3. If needed, re-request reviews or link the contributors who reviewed the draft version manually.
4. Allow GitHub Actions (`CI` matrix) to re-run. The run that matters is the one triggered on the new PR head commit.
5. Once checks pass, merge the new PR and cite the closed draft PR in the merge description for auditing.

## Communication tip
- After merging, comment on the closed draft PR (if you can still edit it) with a short note: `Draft-to-ready fallback completed via PR #<new-number> due to connector schema bug.`
- Mention the fallback case in the new PR’s description, e.g., `Replaces draft PR #3 because the connector could not mark it ready.`

## Why this matters
We keep the workflow predictable for future contributors when the external toolchain misbehaves, preserve CI history, and make provenance between draft and ready states explicit.