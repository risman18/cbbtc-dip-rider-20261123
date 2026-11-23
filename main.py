"""cbBTC dip-rider for make.fun btc-race-24h-20261123-0511.

Long only, $1,000 paper money, 1-minute cbBTC bars:

- Sit in cash while the close stays near the anchor close (the first
  scored close, then the close of the bar a cycle sold on).
- Buy with all cash when a close prints at least DIP_BPS below the
  anchor (a small dip early in the window), or, if no dip has shown up
  by scored bar FALLBACK_BAR, buy there anyway so the bot always trades.
- Once in, track the highest close seen since entry. Sell everything when
  a close falls PEAK_EXIT_BPS below that peak (trailing exit that lets a
  trend run but banks the move), or STOP_BPS below the entry close (stop).
- After a sell the bot may ride ONE more cycle (MAX_CYCLES = 2 in total):
  the sell bar's close becomes the new anchor, so a fresh DIP_BPS dip
  below the price it just sold at buys back in for the next leg instead
  of sitting in cash while the market recovers. After the second sell
  the bot stays in cash for the rest of the window.

All comparisons are integer arithmetic on the protocol's raw price units
(price_scale 5), so the bot is deterministic: the same bars always give
the same orders. No network, no clock, no files, no randomness.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"

# Strategy parameters, in basis points (1 bp = 0.01%).
# Measured on the kit's frozen dev window (1,440 bars) with a local
# protocol replica (fee 4 bps, slippage 2 bps, pool impact at each
# fill bar's open depth, flatten at the last close):
#   DIP 30 / PEAK 200 / STOP 150 -> +$36.29, 1 trade, max DD 1.98%
#   DIP 45 / PEAK 200 / STOP 150 -> +$37.01, 1 trade, max DD 1.98%
#   (DIP 45-48 all buy the same 48.8 bp dip at bar 34; 45 is the least
#   demanding of that plateau, so the most likely to trigger live.
#   DIP 49+ never sees its dip and falls back to a top buy, +$0.09.)
#   PEAK 150 exits at bar 434 -> +$27.88; PEAK 190 -> +$23.09, so the
#   200 bp trail stays. STOP 100 vs 150: never fires either way.
# The re-entry (MAX_CYCLES = 2) is dev-neutral here: with PEAK 200 the
# first exit never fires on the dev window, so dev stays +$37.01; it
# only matters live, where an early exit no longer strands the bot in
# cash for the rest of the window.
DIP_BPS = 45          # buy when close <= anchor close * (1 - 0.45%)
PEAK_EXIT_BPS = 200   # sell when close <= post-entry peak * (1 - 2.00%)
STOP_BPS = 150        # sell when close <= entry close * (1 - 1.50%)
FALLBACK_BAR = 1200   # scored-bar index (0-based) that forces a buy if flat
MAX_CYCLES = 2        # at most two buy/sell cycles per window (one re-entry)
MAX_SLIPPAGE_BPS = 200

BPS = 10_000


class DipRider:
    """Dip rider: up to MAX_CYCLES buy/sell cycles. All state is plain ints / bools."""

    def __init__(self):
        self.anchor_close = None   # close of the first scored bar
        self.scored_bars = 0       # tradeable batches seen so far
        self.buy_sent = False      # a buy order is out, fill not yet seen
        self.entry_close = None    # close of the bar the buy was decided on
        self.peak_close = None     # highest close seen since entry
        self.cycles = 0            # completed sell cycles (re-entry if < MAX)
        self.exited = False        # all cycles used up: stay in cash

    def on_batch(self, state, batch):
        if state.warming_up:
            return []
        close = state.close(SYMBOL)
        if close is None:
            return []

        if self.anchor_close is None:
            self.anchor_close = close
        bar_index = self.scored_bars
        self.scored_bars += 1

        holding = state.positions.get(SYMBOL)

        if holding is None:
            if self.exited:
                return []
            if self.buy_sent:
                # The buy was rejected at the last open (e.g. slippage):
                # send it again at the same size.
                return self._buy(state)
            dip = close * BPS <= self.anchor_close * (BPS - DIP_BPS)
            if dip or bar_index >= FALLBACK_BAR:
                self.entry_close = close
                self.peak_close = close
                return self._buy(state)
            return []

        # Holding a position: update the peak, then check the exits.
        self.buy_sent = False
        if self.peak_close is None or close > self.peak_close:
            self.peak_close = close
        trail = close * BPS <= self.peak_close * (BPS - PEAK_EXIT_BPS)
        stop = close * BPS <= self.entry_close * (BPS - STOP_BPS)
        if trail or stop:
            self.cycles += 1
            self.entry_close = None
            self.peak_close = None
            # Re-anchor on the sell bar's close: a later dip below the
            # price just sold at re-enters for the next leg (cycle 2).
            self.anchor_close = close
            self.exited = self.cycles >= MAX_CYCLES
            return [
                {
                    "side": "sell",
                    "symbol": SYMBOL,
                    "qty": holding.qty,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                }
            ]
        return []

    def _buy(self, state):
        self.buy_sent = True
        amount = state.cash
        if amount <= 0:
            return []
        return [
            {
                "side": "buy",
                "symbol": SYMBOL,
                "notional_quote_units": amount,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }
        ]


def main():
    rider = DipRider()
    makefun_bars.run(rider.on_batch)


if __name__ == "__main__":
    main()
