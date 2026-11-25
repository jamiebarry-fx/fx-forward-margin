# FX Forward Margin Monitor

A small Python tool that marks a book of open FX forwards to market, flags
positions that are close to, or past, a margin trigger, shows how far each trade
is from a margin call, totals exposure by currency pair, and stress tests the
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
7. Works out the spot rate at which the trade would reach a margin call, and
   how much room is left before it gets there

It then reports the whole book, sorted from the trade closest to a margin call
to the one furthest from it, with total notional, total mark-to-market and the
book's overall position, and saves a chart of every trade against the margin
triggers.

It also totals the book by currency pair and side, to show where exposure is
concentrated.

Finally it runs a stress test: it moves spot rates up and down by 1%, 2% and 3%,
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

## Distance to a margin call

The position formula can be written in one line and then turned round to find
the rate at which a trade is called:

    position %   = side x (contract / forward - 1) x 100

    A margin call happens when position % = -call level, which gives:

    call forward = contract / (1 - side x call level / 100)
    call spot    = call forward x spot / forward
    move %       = (call spot - spot) / spot x 100
    room %       = move % x side

Two checks that can be done on a calculator:

- A buy at 1.2000 with a 4% call level is called at a forward of
  1.2000 / 0.96 = 1.2500. A buyer is called when the rate rises.
- A sell at 1.2000 with a 4% call level is called at a forward of
  1.2000 / 1.04 = 1.1538. A seller is called when the rate falls.

`call_spot` is the spot rate that produces the call forward, holding today's
ratio of spot to forward. `room_pct` is how far spot can move against the client
before a margin call. A negative number means the trade is already past its
call level.

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

     row    pair side value_date  days  notional_gbp  mtm_pct   pnl_gbp    decision check  market_rate  call_spot  room_pct
       7 GBP/USD sell 2027-08-30   278     735294.12    -4.28 -31463.02 Margin Call             1.3054     1.3216     -1.24
      11 GBP/AUD  buy 2027-06-30   217     393184.80    -4.28 -16827.69 Margin Call             1.9830     1.9772     -0.29
       5 EUR/USD sell 2027-02-28    95     347734.42    -4.27 -14849.51 Margin Call             1.0942     1.0971     -0.26
       8 GBP/EUR  buy 2027-04-30   156     569176.88    -3.67 -20875.90     Warning             1.1930     1.1971      0.35
       1 GBP/EUR  buy 2027-06-01   188     325379.61    -2.66  -8648.32   No Action             1.1930     1.2097      1.40
       2 GBP/USD sell 2027-03-15   110     375234.52    -2.11  -7932.46   No Action             1.3054     1.2817      1.81
       3 GBP/EUR sell 2027-01-31    67     210084.03    -0.02    -46.07   No Action             1.1930     1.1585      2.89
       6 GBP/EUR  buy 2027-03-31   126      72340.43    -1.00   -725.70   No Action             1.1930     1.2302      3.12
      10 GBP/JPY  buy 2026-12-31    36     121359.22    -0.61   -742.74   No Action           207.8300   215.1646      3.53
       9 GBP/CAD  buy 2028-01-31   432     149732.62     2.39   3582.11   No Action             1.8578     1.9611      5.56
       4 GBP/USD  buy 2027-09-01   280    2425373.13     2.75  66603.63   No Action             1.3054     1.3827      5.92
      12 GBP/CHF  buy 2027-04-01   127      89285.71     4.72   4214.64   No Action             1.0844     1.1707      7.96

    Total Notional: GBP 5,814,179.50
    Total MTM: GBP -27,711.02
    Total Position as a percentage: -0.48%

Reading two rows: trade 8 is on a Warning with 0.35% of room, so a move in
GBP/EUR from 1.1930 to 1.1971 would make it a margin call. Trade 7 is already
1.24% past its call level, and GBP/USD would need to recover to 1.3216 to bring
it back.

## Exposure by pair

The book is then grouped by currency pair and side, most offside first:

    Exposure by pair
       pair side  notional_gbp   pnl_gbp  mtm_pct
    GBP/AUD  buy     393184.80 -16827.69    -4.28
    EUR/USD sell     347734.42 -14849.51    -4.27
    GBP/USD sell    1110528.64 -39395.48    -3.55
    GBP/EUR  buy     966896.92 -30249.92    -3.13
    GBP/JPY  buy     121359.22   -742.74    -0.61
    GBP/EUR sell     210084.03    -46.07    -0.02
    GBP/CAD  buy     149732.62   3582.11     2.39
    GBP/USD  buy    2425373.13  66603.63     2.75
    GBP/CHF  buy      89285.71   4214.64     4.72

The percentage for each group is worked out from its totals, not averaged
across trades, so a large trade carries more weight than a small one.

This shows what the trade-by-trade report cannot. Three separate GBP/EUR buys
add up to GBP 967,000 and are 3.13% offside as a group, and the same rise in
GBP/EUR hurts all three at once. Buys and sells are kept apart because they
move in opposite directions.

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
       2 GBP/USD sell    -5.27     No Action Margin Call
       3 GBP/EUR sell    -3.12     No Action Margin Call
       8 GBP/EUR  buy    -0.69       Warning   No Action
      11 GBP/AUD  buy    -1.32   Margin Call   No Action

It then prints a summary of how many trades sit in each decision at each shock:

     Shock  No Action  Warning  Margin Call
     -0.03          8        0            4
     -0.02          9        0            3
     -0.01          8        2            2
      0.00          8        1            3
      0.01          7        2            3
      0.02          9        0            3
      0.03          7        2            3

In the sample book, a 3% fall in the base currencies takes margin calls from 3
to 4. A 3% rise leaves the count at 3, but two different trades are called and
two are cleared, which the trade-level lists show and the totals alone would
hide.

The stress test and the room column agree with each other. Trade 2 has 1.81% of
room and moves to a margin call between the 1% and 2% shocks. Trade 3 has 2.89%
and is called at 3%.

## Notes and limits

- Interest rates are central bank policy rates, used as a stand-in for market
  term rates. Checked against live forward quotes, the tool's forward rates
  were within 1 to 5 pips, which is why trades near a trigger are flagged for
  a manual check.
- Spot rates are entered by hand.
- Distance is measured to the margin call, not the warning. For an established
  client that is the 4% level.
- The call spot assumes the gap between spot and forward stays as it is today,
  so it does not allow for a change in interest rates.
- Exposure is shown gross, with buys and sells in a pair listed separately.
  They are not netted against each other.
- The stress test applies the same percentage move to every pair at once. This
  is a simple sensitivity check, not a single consistent market scenario, since
  linked pairs such as GBP/EUR, EUR/USD and GBP/USD cannot all move by the same
  amount together.

## Next steps

- Net exposure by pair
- Margin call amounts
- Tests against hand-worked answers
- Load the dealing platform's export directly