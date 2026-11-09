"""Company rules. Every constant below is traceable to a source document.

SOURCE (the only expense-policy document in the connected Drive folder that is current):
    Policy_Expense_v2_Current.txt  -- Northstar Services Expense Policy v2, effective 2026-10-01
    https://drive.google.com/file/d/1xCJWu-5BKSGN_-Qil5dQZBq8_a827IbI/view
Policy_Expense_v1_Superseded.txt (30-day window, JPY 12,000 hotel cap) is deliberately NOT used:
the document itself says it must not override the current version.

Anything NOT in those documents is listed in NOT_SPECIFIED and is not enforced as policy.
Items tagged "system" in RULES are engineering/data-integrity checks, not company policy.
"""

POLICY_FILE = "Policy_Expense_v2_Current.txt"
POLICY_EFFECTIVE = "2026-10-01"
POLICY_URL = "https://drive.google.com/file/d/1xCJWu-5BKSGN_-Qil5dQZBq8_a827IbI/view"
CITE = f"{POLICY_FILE} (effective {POLICY_EFFECTIVE})"

SUBMISSION_WINDOW_DAYS = 10          # v2: "within 10 calendar days after an expense occurs"
RECEIPT_THRESHOLD_JPY = 2000         # v2: "JPY 2,000 or more"
HOTEL_CAP_PER_NIGHT_JPY = 15000      # v2: "one domestic hotel night ... excluding applicable taxes"

# Category names are NOT defined by the policy (see NOT_SPECIFIED). They are a system
# default list; only the three behaviours the policy mentions are attached to categories.
DOMESTIC_TRAVEL = "Travel - Domestic"
INTERNATIONAL_TRAVEL = "Travel - International"
DOMESTIC_HOTEL = "Hotel - Domestic"
CATEGORIES = [DOMESTIC_TRAVEL, INTERNATIONAL_TRAVEL, DOMESTIC_HOTEL,
              "Meals", "Office Supplies", "Software & Subscriptions", "Other"]

RULES = [
    {"id": "R1", "kind": "policy", "text": "Claims must be submitted within 10 calendar days after the expense occurs.",
     "source": POLICY_FILE, "effective": POLICY_EFFECTIVE,
     "how": "Submission is rejected if (submission date - expense date) > 10 days. No override: the policy defines none."},
    {"id": "R2", "kind": "policy", "text": "A receipt is required for any individual expense of JPY 2,000 or more.",
     "source": POLICY_FILE, "effective": POLICY_EFFECTIVE,
     "how": "Amounts >= 2,000 need a receipt reference (e.g. a file name or number); one claim = one expense."},
    {"id": "R3", "kind": "policy", "text": "Domestic travel expenses require manager approval before the trip.",
     "source": POLICY_FILE, "effective": POLICY_EFFECTIVE,
     "how": "Domestic-travel claims must record the trip start date and the date of the manager's pre-trip approval, which must be earlier than the trip start. (How pre-approval is documented is not specified; recording the date is a design choice.)"},
    {"id": "R4", "kind": "policy", "text": "International travel requires finance and manager approval.",
     "source": POLICY_FILE, "effective": POLICY_EFFECTIVE,
     "how": "International-travel claims need an approval from the employee's manager AND from finance (either order). Any rejection is final."},
    {"id": "R5", "kind": "policy", "text": "Reimbursement cap: JPY 15,000 per domestic hotel night, excluding applicable taxes.",
     "source": POLICY_FILE, "effective": POLICY_EFFECTIVE,
     "how": "Hotel claims record nights and the tax portion. Room charge = amount - tax; any room charge above 15,000 x nights is shown as 'cap excess' and excluded from the reimbursable amount. Taxes are not counted toward the cap (our reading of 'excluding applicable taxes')."},
    {"id": "S1", "kind": "system", "text": "Expense date cannot be in the future.", "source": "system validation", "effective": "-", "how": "Data integrity."},
    {"id": "S2", "kind": "system", "text": "Employees cannot decide their own expenses; a manager decides only for their direct reports; finance decides only where finance approval is required.",
     "source": "system access control", "effective": "-", "how": "Segregation of duties as an engineering control; not stated in the policy documents."},
    {"id": "S3", "kind": "system", "text": "Amounts are whole Japanese yen (JPY).", "source": "system validation (the policy states amounts in JPY)", "effective": "-", "how": "No foreign-currency handling."},
]

NOT_SPECIFIED = [
    "Approval limits or thresholds by amount, and who approves expenses of managers/finance staff.",
    "The list of expense categories (the app's categories are a system default, not company policy).",
    "Whether a domestic hotel night is itself 'domestic travel' needing pre-trip approval (the app does NOT require it; one-line change in service.py if the policy owner says otherwise).",
    "Reimbursement caps for anything other than domestic hotel nights (meals, international hotels, etc.): no caps applied.",
    "Exceptions or overrides for late claims, and how a missing receipt may be remedied.",
    "Time zone for the 10-day window (app uses Japan time) and whether v2 applies to expenses that occurred before 2026-10-01.",
    "Whether an international trip also needs pre-trip approval, and the order of manager/finance approval.",
    "Payment/reimbursement timing, per-diem rates, and foreign-currency conversion.",
]
