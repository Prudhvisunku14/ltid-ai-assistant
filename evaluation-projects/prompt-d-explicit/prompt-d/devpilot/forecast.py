"""D3 - Forecasting with time-ordered validation and MAE. ALL DATA AND FORECASTS ARE SYNTHETIC."""
import csv, math, random, datetime as dt
from pathlib import Path

LABEL = "SYNTHETIC DATA - not a real weather forecast"


class DataError(ValueError):
    pass


def mae(actual, predicted):
    if len(actual) == 0 or len(predicted) == 0:
        raise DataError("MAE needs at least one observation")
    if len(actual) != len(predicted):
        raise DataError(f"length mismatch: {len(actual)} actual vs {len(predicted)} predicted")
    for v in list(actual) + list(predicted):
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
            raise DataError(f"non-finite or non-numeric value: {v!r}")
    return sum(abs(a - p) for a, p in zip(actual, predicted)) / len(actual)


def make_synthetic(path, n=400, seed=7):
    rng, start = random.Random(seed), dt.date(2024, 1, 1)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "temp_c", "synthetic"])
        for i in range(n):
            t = 15 + 10 * math.sin(2 * math.pi * (i - 80) / 365) + rng.gauss(0, 1.5)
            w.writerow([(start + dt.timedelta(days=i)).isoformat(), round(t, 2), "true"])


def load_series(path):
    p = Path(path)
    if not p.exists():
        raise DataError(f"file not found: {path}")
    with open(p, newline="") as f:
        rd = csv.DictReader(f)
        need = {"date", "temp_c"}
        if not rd.fieldnames or not need <= set(rd.fieldnames):
            raise DataError(f"missing required columns {sorted(need)}; got {rd.fieldnames}")
        dates, vals, prev = [], [], None
        for ln, row in enumerate(rd, start=2):
            try:
                d = dt.date.fromisoformat(row["date"])
            except ValueError:
                raise DataError(f"line {ln}: bad date {row['date']!r}")
            if row["temp_c"] in ("", None):
                raise DataError(f"line {ln}: missing temp_c")
            try:
                v = float(row["temp_c"])
            except ValueError:
                raise DataError(f"line {ln}: non-numeric temp_c {row['temp_c']!r}")
            if not math.isfinite(v):
                raise DataError(f"line {ln}: non-finite temp_c")
            if prev and d <= prev:
                raise DataError(f"line {ln}: dates must be strictly increasing (time order)")
            prev = d
            dates.append(d); vals.append(v)
    if len(vals) < 30:
        raise DataError(f"need >= 30 rows, got {len(vals)}")
    return dates, vals


# ---- methods: each takes `history` (only past values) and returns the next value ----
def naive(h): return h[-1]
def moving_avg(k):
    return lambda h: sum(h[-k:]) / len(h[-k:])
def drift(h):
    return h[-1] if len(h) < 2 else h[-1] + (h[-1] - h[0]) / (len(h) - 1)
def ses(alpha):
    def f(h):
        lvl = h[0]
        for y in h[1:]:
            lvl = alpha * y + (1 - alpha) * lvl
        return lvl
    return f


def one_step(method, series, start, end):
    """Forecast series[t] from series[:t] only (no leakage), for t in [start, end)."""
    return [method(series[:t]) for t in range(start, end)]


def fit_ses(train):
    best = min((a / 10 for a in range(1, 10)),
               key=lambda a: mae(train[10:], one_step(ses(a), train, 10, len(train))))
    return ses(best), best


def evaluate(series):
    n = len(series)
    i1, i2 = int(n * .6), int(n * .8)  # train | validation | test, strictly chronological
    res = {"n": n, "splits": {"train": i1, "val": i2 - i1, "test": n - i2}, "label": LABEL, "models": {}}
    cands = {"naive": naive, "moving_avg_7": moving_avg(7), "drift": drift}
    ses_val, a_val = fit_ses(series[:i1])
    cands[f"ses(alpha={a_val})"] = ses_val
    for name, m in cands.items():
        res["models"][name] = {"val_mae": mae(series[i1:i2], one_step(m, series, i1, i2))}
    best = min(res["models"], key=lambda k: res["models"][k]["val_mae"])  # chosen on validation ONLY
    if best.startswith("ses"):
        best_m, a_t = fit_ses(series[:i2])  # refit on train+val
        best = f"ses(alpha={a_t})"; res["models"].setdefault(best, {"val_mae": None})
    else:
        best_m = cands[best]
    res["selected"] = best
    res["test_mae_selected"] = mae(series[i2:], one_step(best_m, series, i2, n))
    res["test_mae_naive_baseline"] = mae(series[i2:], one_step(naive, series, i2, n))
    res["_method"] = best_m
    return res


def forecast_next(series, method, days=7):
    h, out = list(series), []
    for _ in range(days):
        v = method(h); out.append(round(v, 2)); h.append(v)
    return out


def demo_errors(tmp_dir):
    """Deliberately feed bad inputs; each must raise DataError with a clear message."""
    tmp = Path(tmp_dir); tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "bad_header.csv").write_text("day,temperature\n2024-01-01,1\n")
    (tmp / "bad_value.csv").write_text("date,temp_c,synthetic\n" + "".join(f"2024-01-{i:02d},{i},true\n" for i in range(1, 29)) + "2024-01-29,abc,true\n2024-01-30,1,true\n")
    (tmp / "unordered.csv").write_text("date,temp_c,synthetic\n2024-01-02,1,true\n2024-01-01,2,true\n")
    cases = {
        "empty MAE": lambda: mae([], []),
        "length mismatch": lambda: mae([1, 2], [1]),
        "NaN input": lambda: mae([1.0, float("nan")], [1.0, 2.0]),
        "missing file": lambda: load_series(tmp / "nope.csv"),
        "wrong header": lambda: load_series(tmp / "bad_header.csv"),
        "non-numeric value": lambda: load_series(tmp / "bad_value.csv"),
        "dates out of order": lambda: load_series(tmp / "unordered.csv"),
    }
    out = {}
    for name, fn in cases.items():
        try:
            fn(); out[name] = "NOT REJECTED (bug)"
        except DataError as e:
            out[name] = f"rejected: {e}"
    return out


def render(res, fc, errors):
    L = [f"# D3 Forecast validation  [{LABEL}]", "",
         f"Rows: {res['n']}; chronological split train/val/test = {res['splits']}. One-step-ahead (1 day) rolling origin; "
         "model chosen on validation only; test MAE computed once on the untouched final block.", "",
         "| Model | Validation MAE (degC) |", "|---|---|"]
    for k, v in res["models"].items():
        if v["val_mae"] is not None:
            L.append(f"| {k} | {v['val_mae']:.3f} |")
    L += ["", f"Selected: **{res['selected']}**",
          f"Test MAE selected: **{res['test_mae_selected']:.3f}** degC vs naive baseline {res['test_mae_naive_baseline']:.3f}",
          "", f"Next 7 synthetic days (recursive, {LABEL}): {fc}", "", "## Error handling demonstration"]
    L += [f"- {k}: {v}" for k, v in errors.items()]
    return "\n".join(L)
