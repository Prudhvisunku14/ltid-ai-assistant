# Scenario 02 — Weather Forecasting Demo (requirements)

Fictional client: Eastbay City Lab | Data: synthetic observations

NOTE: Text below was read **directly from the Google Drive file** `02_Weather_Requirements.docx`
(Drive file id `1P71uar5JkwFeitePiqHMxVbhcJLMddgH`, 38 KB, last modified 2026-11-03) through the Google Drive
connector on 2026-11-10. It is a plain-text rendering of the document, not a copy of the .docx itself.

## Scope and honesty
Build an educational temperature forecasting demo; do NOT advertise the supplied synthetic observations as real historical measurements.
Forecasts may use a simple transparent statistical baseline. A live weather API is optional, not required; describe limitations honestly.

## Functional requirements
* **Inputs** — Accept a city in the dataset and a forecast horizon of 1–3 days. Invalid cities and horizons must show clear errors.
* **Forecast** — Provide forecast daily temperature in Celsius, the method used, and a note that the dataset is synthetic.
* **Evaluation** — Implement a time-ordered train/evaluation split and compute mean absolute error (MAE) on held-out observations.
* **Robustness** — Handle missing or malformed observations without an unhandled crash; document the selected policy.
* **Output** — Allow a human-readable report or JSON output. Explain why the chosen implementation tools are appropriate.

## Acceptance evidence
* Demonstrate two cities and three forecast horizons; show MAE calculations on the reserved portion of data.
* Provide unit tests for at least invalid city, invalid horizon, and one evaluation calculation.

LTID AI Development Competition | Fictional training materials | November 2026
