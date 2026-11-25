# FX Forward Margin Monitor
# Marks a book of open FX forwards to market, applies a margin policy, shows how far each
# trade is from a margin call, stress tests the book against moves in spot and charts it.
# The trades in sample_book.csv are made up.

import pandas as pd
import matplotlib.pyplot as plt

# Display settings so the full report prints on one line.
pd.set_option("display.width", 300)
pd.set_option("display.max_columns", None)
# Spot rates: units of each currency per one pound. Updated by hand.
rates = {"EUR": 1.1930, "USD": 1.3054, "GBP": 1.000, "JPY": 207.83, "CHF": 1.0844, "CAD": 1.8578, "AUD": 1.9830}
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
# Also works out how far spot must move before each trade reaches a margin call.
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

    # Distance to a margin call.
    #   position %   = side x (contract / forward - 1) x 100
    #   A margin call happens when position % = -call level, which gives:
    #   call forward = contract / (1 - side x call level / 100)
    #   call spot    = call forward x spot / forward
    #   move %       = (call spot - spot) / spot x 100
    #   room %       = move % x side
    # The level each client is called at: 3% for new, 4% for established.
    df["call_level"] = df["client_type"].map({"new": 3, "established": 4})
    # The forward rate at which the trade sits exactly at its call level.
    df["call_factor"] = 1 - df["sign"] * df["call_level"] / 100
    df["call_forward"] = df["contract_rate"] / df["call_factor"]
    # The spot rate that gives that forward, holding today's ratio of spot to forward.
    df["call_spot"] = df["market_rate"] / df["forward_rate"] * df["call_forward"]
    # How far spot has to move to reach it. Positive is up, negative is down.
    df["move_pct"] = (df["call_spot"] - df["market_rate"]) / df["market_rate"] * 100
    # Room left in the direction that hurts the client. Negative means already past the call level.
    df["room_pct"] = df["move_pct"] * df["sign"]
    return df


df = mark_book(0.0)
total_notional = df["notional_gbp"].sum()
total_pnl = df["pnl_gbp"].sum()
total_position = total_pnl / total_notional * 100

# Report: closest to a margin call first. Printed and saved to CSV.
report = df[["row", "pair", "side", "value_date", "days", "notional_gbp", "mtm_pct", "pnl_gbp", "decision", "check",
             "market_rate", "call_spot", "room_pct"]].round(
    {"call_spot": 4, "market_rate": 4, "notional_gbp": 2, "mtm_pct": 2, "pnl_gbp": 2, "room_pct": 2}).sort_values(
    "room_pct")
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
