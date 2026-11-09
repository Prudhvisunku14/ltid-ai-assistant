# Scenario 02 — Synthetic weather forecasting CLI

**Important:** The included data are synthetic and designed for software development, not real weather predictions. The current model is a trivial recent-average baseline and does not contain a scientific forecast model.

## Run
`python -m weather_app --city Tokyo --days 3`

## Test
`python -m unittest discover -s tests -v`

The canonical specification is in `02_Weather_Requirements.docx` in Google Drive. The development agent should explain the limitations of the data, propose appropriate tools, build and test the requested capabilities, and document forecasts and limitations.
