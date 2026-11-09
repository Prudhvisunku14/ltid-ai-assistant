# Scenario 02 — Weather Forecasting Demo

Fictional client: Eastbay City Lab | Data: synthetic observations | MOCK REVISION (test data, not in Drive)

# Scope and honesty

Build an educational temperature forecasting demo; do NOT advertise the supplied synthetic observations as real historical measurements.

Forecasts may use a simple transparent statistical baseline. A live weather API is required for the final demo; describe limitations honestly.

# Functional requirements

Inputs — Accept a city in the dataset and a forecast horizon of 1–5 days. Invalid cities and horizons must show clear errors.

Forecast — Provide forecast daily temperature in Celsius and Fahrenheit, the method used, and a note that the dataset is synthetic.

Evaluation — The time-ordered train/evaluation split should be used and MAE should be computed on held-out observations.

Output — Allow a human-readable report or JSON output. Explain why the chosen implementation tools are appropriate.

# Acceptance evidence

Demonstrate three cities and three forecast horizons; show MAE calculations on the reserved portion of data.

Provide unit tests for at least invalid city, invalid horizon, and one evaluation calculation.
