# Where each rule comes from

Connected Google Drive folder searched on 2026-11-10. Relevant documents found:

| File | Status | Used? |
|---|---|---|
| `Policy_Expense_v2_Current.txt` — Northstar Services Expense Policy v2, effective 2026-10-01 | Current | **Yes — the only source of company rules** (copy in `docs/source_policy/`) |
| `Policy_Expense_v1_Superseded.txt` — v1 (30-day window, JPY 12,000 hotel cap) | Superseded; says it "must not override the current version" | **No** (a test proves the v1 values are not applied) |
| `Policy_Leave_Current.txt`, `Engineering_Deployment_Guide.txt`, `Project_Helpdesk_ServiceSpec.txt` | Unrelated to expenses | No |

No separate specification for an expense/approval system was found, so the functional requirements come from the task text.

## Rules taken from the policy (cite: Policy_Expense_v2_Current.txt, effective 2026-10-01)
| ID | Rule | Where enforced |
|---|---|---|
| R1 | Claims within 10 calendar days after the expense occurs | `service.submit_expense` |
| R2 | Receipt required for any individual expense >= JPY 2,000 | `service.submit_expense` |
| R3 | Domestic travel needs manager approval before the trip | `service.submit_expense` (records trip start + pre-approval date) |
| R4 | International travel needs finance and manager approval | `service.decide` (two required approvals) |
| R5 | Domestic hotel cap JPY 15,000 per night, excluding applicable taxes | `service.hotel_figures` |

## Not in the documents -> not enforced as policy
Approval amount limits / who approves managers; the category list; caps other than domestic hotels; late-claim exceptions;
the time zone of the 10-day window; whether v2 covers expenses before 2026-10-01; whether a hotel night counts as "domestic travel";
pre-trip approval for international trips; order of manager/finance approval; payment timing, per-diems, foreign currency.

## Design choices that are NOT company policy (confirm with the policy owner)
* Category names are a system default; Hotel - Domestic is only subject to the cap, not to pre-trip approval.
* "Pre-trip approval" is documented by recording a date that must be earlier than the trip start (date granularity).
* Hotel `amount` = total paid including tax; reimbursable = amount minus any room charge above 15,000 x nights. Taxes are not counted toward the cap.
* Japan time is used for "today" in the 10-day test; late claims are hard-rejected (policy says "must"; it defines no override).
* S1-S3 (no future dates, no self-approval / only the employee's own manager decides, whole yen) are engineering controls.
* Fictional org chart: managers decide for direct reports; finance decides only where finance approval is required.
