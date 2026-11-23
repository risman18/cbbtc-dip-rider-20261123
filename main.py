"""cbBTC dip-rider for make.fun btc-race-24h-20261123-0511.

One cycle, long only, $1,000 paper money, 1-minute cbBTC bars:

- Sit in cash while the close stays near the window's first scored close.
- Buy with all cash when a close prints at least DIP_BPS below that first
  close (a small dip early in the window), or, if no dip has shown up by
  scored bar FALLBACK_BAR, buy there anyway so the bot always trades.
- Once in, track the highest close seen since entry. Sell everything when
  a close falls PEAK_EXIT_BPS below that peak (trailing exit that lets a
  trend run but banks the move), or STOP_BPS below the entry close (stop).
- After the sell the cycle is over: stay in cash for the rest of the window.

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
DIP_BPS = 30          # buy when close <= first close * (1 - 0.30%)
PEAK_EXIT_BPS = 200   # sell when close <= post-entry peak * (1 - 2.00%)
STOP_BPS = 150        # sell when close <= entry close * (1 - 1.50%)
FALLBACK_BAR = 1200   # scored-bar index (0-based) that forces a buy if flat
MAX_SLIPPAGE_BPS = 200

BPS = 10_000


class DipRider:
    """One-cycle dip rider. All state is plain ints / bools."""

    def __init__(self):
        self.anchor_close = None   # close of the first scored bar
        self.scored_bars = 0       # tradeable batches seen so far
        self.buy_sent = False      # a buy order is out, fill not yet seen
        self.entry_close = None    # close of the bar the buy was decided on
        self.peak_close = None     # highest close seen since entry
        self.exited = False        # the one sell has been sent

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
            self.exited = True
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
