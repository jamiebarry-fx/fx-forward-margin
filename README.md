# FX Forward Margin Monitor

A small Python tool that marks a book of open FX forwards to market, flags
positions that are close to, or past, a margin trigger, and stress tests the
book against moves in spot.

I built it to monitor a live forward book at an FX and payments firm. The trades
in this repository are made up.

## What it does

For each open forward it:

1. Works out the time left to settlement
2. Builds a forward rate for the settlement date from spot and the two
   currencies' interest rates
3. Marks the trade against that forward rate, not spot
4. Converts the profit or loss into pounds
5. Applies a margin policy and gives a decision: No Action, Warning or Margin Call
6. Flags any trade within 0.10% of a trigger, so it can be checked against a
   live forward quote

It then reports the whole book, sorted from most offside to most onside, with
total notional, total mark-to-market and the book's overall position, and saves
a chart of every trade against the margin triggers.

Finally, it runs a stress test: it moves spot rates up and down by 1%, 2% and 3%,
re-marks the book each time and shows which trades would change decision.

## How the marking works

    forward = spot x (1 + quote rate x t) / (1 + base rate x t)

    P&L in quote currency = base amount x (contract rate - forward) x side
    P&L in base currency  = P&L in quote currency / forward
    position %            = P&L in base currency / base amount

`side` is +1 if the client buys the quote currency and -1 if they sell it.

The tool handles any pair, not only pairs against the pound. Each trade names
its base currency, cross rates are derived from the pound rates, and all
results are converted into pounds for the book totals.

## Margin policy

Set in `decide()`:

- New clients: margin call at 3% offside
- Established clients: warning at 3% offside, margin call at 4%

## Running it

    pip install -r requirements.txt
    python margin_monitor.py

The book is read from `sample_book.csv`. Spot rates and interest rates are set
at the top of `margin_monitor.py`.

## Example output

     row    pair side  notional_gbp   pnl_gbp  mtm_pct    decision check
       8 GBP/EUR  buy     569176.88 -23461.34    -4.12 Margin Call
       5 EUR/USD sell     346080.89 -13050.70    -3.77     Warning
      11 GBP/AUD  buy     393184.80 -13156.46    -3.35     Warning
       7 GBP/USD sell     735294.12 -24192.94    -3.29 Margin Call
       1 GBP/EUR  buy     325379.61 -10141.90    -3.12     Warning
       6 GBP/EUR  buy      72340.43  -1063.37    -1.47   No Action
      10 GBP/JPY  buy     121359.22  -1723.80    -1.42   No Action
       2 GBP/USD sell     375234.52  -4299.48    -1.15   No Action
       3 GBP/EUR sell     210084.03    944.64     0.45   No Action
       9 GBP/CAD  buy     149732.62   2140.99     1.43   No Action
       4 GBP/USD  buy    2425373.13  42975.73     1.77   No Action
      12 GBP/CHF  buy      89285.71   2448.26     2.74   No Action

    Total Notional: GBP 5,812,525.97
    Total MTM: GBP -42,580.36
    Total Position as a percentage: -0.73%

## Chart

The tool also saves a chart of the book as `book_chart.png`.

![Chart of the book by position](book_chart.png)

One bar per trade, most offside at the top. Green is No Action, orange is Warning
and red is Margin Call. The dashed lines mark the 3% and 4% triggers. A new client
can be red before the 4% line, because their margin call level is 3%.

## Stress test

The marking is wrapped in a function, `mark_book(shock)`, so the same code can
price the book at today's rates or with spot moved. The stress test calls it for
seven shocks from -3% to +3%, applies the margin policy each time and compares
the result with today's decisions.

A positive shock means the base currency strengthens against the quote currency.
For each shock the tool lists only the trades whose decision changes:

    Shock: -3%
     row    pair side  mtm_pct real_decision    decision
       1 GBP/EUR  buy    -0.12       Warning   No Action
       2 GBP/USD sell    -4.27     No Action Margin Call
       5 EUR/USD sell    -6.98       Warning Margin Call
       8 GBP/EUR  buy    -1.16   Margin Call   No Action
      11 GBP/AUD  buy    -0.36       Warning   No Action

It then prints a summary of how many trades sit in each decision at each shock:

     Shock  No Action  Warning  Margin Call
     -0.03          9        0            3
     -0.02          9        1            2
     -0.01          9        1            2
      0.00          7        3            2
      0.01          9        0            3
      0.02          7        2            3
      0.03          7        0            5

This shows how close the book is to its triggers. In the sample book, a 3% rise
in the base currencies takes margin calls from 2 to 5, while a 3% fall moves two
trades to a margin call and clears three others.

## Notes and limits

- Interest rates are central bank policy rates, used as a stand-in for market
  term rates. Checked against live forward quotes, the tool's forward rates
  were within 1 to 5 pips, which is why trades near a trigger are flagged for
  a manual check.
- Spot rates are entered by hand.
- The stress test applies the same percentage move to every pair at once. This
  is a simple sensitivity check, not a single consistent market scenario, since
  linked pairs such as GBP/EUR, EUR/USD and GBP/USD cannot all move by the same
  amount together.

## Next steps

- Distance to trigger: how far spot must move before each trade changes decision
- Exposure by currency pair
- Margin call amounts
- Load the dealing platform's export directly