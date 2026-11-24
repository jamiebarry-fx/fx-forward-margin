import pandas as pd
import matplotlib.pyplot as plt

# Display settings so the full report prints on one line.
pd.set_option("display.width", 300)
pd.set_option("display.max_columns", None)
# Spot rates: units of each currency per one pound. Updated by hand.
rates = {"EUR": 1.1987, "USD": 1.3179, "GBP": 1.000, "JPY": 209.55, "CHF": 1.1054, "CAD": 1.8755, "AUD": 1.9638}
# Central bank policy rates as decimals (4% = 0.04). Used to build forward rates.
base_rates = {"GBP": 0.04, "EUR": 0.025, "USD": 0.03875, "JPY": 0.0125, "CHF": 0.00, "CAD": 0.025, "AUD": 0.0485}


# Margin policy. New clients: margin call at 3% offside. Established: warning at 3%, margin call at 4%.
def decide(row):
    if row["client_type"] == "new" and row["mtm_pct"] <= -3:
        decision = "Margin Call"
    elif row["client_type"] == "established" and -4 < row["mtm_pct"] <= -3:
        decision = "Warning"
    elif row["client_type"] == "established" and row["mtm_pct"] <= -4:
        decision = "Margin Call"
    else:
        decision = "No Action"
    return decision


# Flag trades within 0.10% of a trigger. The forward uses policy rates, so these are checked against a live rate.
def near_trigger(row):
    decision = ""
    if row["client_type"] == "established" and -4.10 < row["mtm_pct"] <= -3.90:
        decision = "Live Rate"
    elif -3.10 < row["mtm_pct"] <= -2.90:
        decision = "Live Rate"
    return decision


# Mark the whole book with spot moved by a given percentage (0.01 = +1%). A shock of 0 is today's market.
def mark_book(shock):
    # Load the book: one row per open forward.
    df = pd.read_csv("sample_book.csv")
    df["value_date"] = pd.to_datetime(df["value_date"])
    today = pd.Timestamp.today().normalize()
    # Time to settlement.
    df["days"] = (df["value_date"] - today).dt.days
    df["years"] = df["days"] / 365
    # Base amount of each trade, and the spot rate for its pair. Crosses are derived from the pound rates.
    df["notional_base"] = df["notional"] / df["contract_rate"]
    df["base_spot"] = df["base"].map(rates)
    df["market_rate"] = df["currency"].map(rates) / df["base_spot"]
    df["market_rate"] = df["market_rate"] * (1 + shock)
    # Interest rate for each side of the pair.
    df["quote_rate"] = df["currency"].map(base_rates)
    df["base_ccy_rate"] = df["base"].map(base_rates)
    # Forward rate to the settlement date: spot x (1 + quote rate x t) / (1 + base rate x t).
    df["forward_rate"] = df["market_rate"] * (1 + df["quote_rate"] * df["years"]) / (
            1 + df["base_ccy_rate"] * df["years"])
    # +1 if the client buys the quote currency, -1 if they sell it.
    df["sign"] = df["side"].map({"buy": 1, "sell": -1})
    # Mark against the forward: P&L in the quote currency, then in the trade's base currency.
    df["pnl_ccy"] = df["notional_base"] * (df["contract_rate"] - df["forward_rate"]) * df["sign"]
    df["pnl_base"] = df["pnl_ccy"] / df["forward_rate"]
    # Convert to pounds for the book totals.
    df["notional_gbp"] = df["notional_base"] / df["base_spot"]
    df["pnl_gbp"] = df["pnl_base"] / df["base_spot"]
    # Position as a percentage of the trade, then apply the policy.
    df["mtm_pct"] = df["pnl_base"] / df["notional_base"] * 100
    df["decision"] = df.apply(decide, axis=1)
    df["check"] = df.apply(near_trigger, axis=1)
    df["pair"] = df["base"] + "/" + df["currency"]
    return df


df = mark_book(0.0)
total_notional = df["notional_gbp"].sum()
total_pnl = df["pnl_gbp"].sum()
total_position = total_pnl / total_notional * 100
# Report: most offside first. Printed and saved to CSV.
report = df[["row", "pair", "side", "notional_gbp", "pnl_gbp", "mtm_pct", "decision", "check"]].round(2).sort_values(
    "mtm_pct")
print(report.to_string(index=False))
report.to_csv("book_report.csv", index=False)
print()
print(f"Total Notional: GBP {total_notional:,.2f}")
print(f"Total MTM: GBP {total_pnl:,.2f}")
print(f"Total Position as a percentage: {total_position:,.2f}%")
print()
print(df["decision"].value_counts().to_string())
print()
# Stress test: move every pair's spot rate up and down, then re-mark the book and re-apply the margin policy.
# A positive shock means the base currency strengthens against the quote currency.
shocks = [-0.03, -0.02, -0.01, 0.00, 0.01, 0.02, 0.03]
results = []
for s in shocks:
    stressed = mark_book(s)
    result = {"Shock": s, "No Action": (stressed["decision"] == "No Action").sum(),
              "Warning": (stressed["decision"] == "Warning").sum(),
              "Margin Call": (stressed["decision"] == "Margin Call").sum()}
    results.append(result)
    # List the trades whose decision differs from today's.
    stressed["real_decision"] = df["decision"]
    changed = stressed[stressed["decision"] != stressed["real_decision"]]
    report_shock = changed[["row", "pair", "side", "mtm_pct", "real_decision", "decision"]].round(2)
    print(f"Shock: {s:.0%}")
    if len(changed) == 0:
        print("No Changes")
    else:
        print(report_shock.to_string(index=False))
    print()
# Summary: number of trades in each decision at each shock.
stress_table = pd.DataFrame(results)
print(stress_table.to_string(index=False))
# Chart: one bar per trade, most offside at the top.
# Green = No Action, orange = Warning, red = Margin Call.
# Dashed lines mark the 3% and 4% triggers.
df["label"] = df["row"].astype(str) + ": " + df["pair"]
df["color"] = df["decision"].map({"No Action": "green", "Warning": "orange", "Margin Call": "red"})
chart = df.sort_values("mtm_pct", ascending=False)
plt.figure(figsize=(10, 5.2))
plt.barh(chart["label"], chart["mtm_pct"], color=chart["color"])
plt.axvline(-3, color="orange", linestyle="--")
plt.axvline(-4, color="red", linestyle="--")
plt.title("Forward book: position by trade")
plt.xlabel("MTM %")
plt.tight_layout()
plt.savefig("book_chart.png", dpi=150)
plt.show()
