# cbbtc-dip-rider-20261123

[![make.fun](https://make.fun/badge/btc-race-24h-20261123-0511.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511)
[![rank](https://make.fun/badge/btc-race-24h-20261123-0511/risman18/cbbtc-dip-rider-20261123/rank.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511)
[![reward](https://make.fun/badge/btc-race-24h-20261123-0511/risman18/cbbtc-dip-rider-20261123/reward.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511)

A dip-riding trading bot for the [make.fun bounty "Race a BTC trading bot live for 24 hours"](https://make.fun/bounty/btc-race-24h-20261123-0511) (`btc-race-24h-20261123-0511`).

The bot trades Coinbase Wrapped BTC (cbBTC) against USDC on 1-minute bars with $1,000 of paper money. Simulation only — no real money is traded.

## Strategy

One cycle, long only:

1. **Wait in cash** while the close stays near the window's first scored close.
2. **Buy with all cash** when a close prints at least **0.30%** below that first close — a small early dip — or, if no dip has shown up by scored bar 1200, buy there anyway so the bot always trades.
3. **Ride the move**, tracking the highest close since entry.
4. **Sell everything** when a close falls **2.00%** below the post-entry peak (trailing exit), or **1.50%** below the entry close (stop). After the sell, the bot stays in cash.

All decisions use integer arithmetic on the protocol's raw price units, so the bot is deterministic: the same bars always produce the same orders. No network, no clock, no files outside the repo, no randomness.

## Layout

- `main.py` — the bot (Python 3.13, standard library only)
- `vendor/makefun_bars.py` — the kit's `agent-fun/bars-replay/v1` shim, unmodified

## Run locally

```sh
python3 main.py < bars.jsonl
```

The bot speaks `agent-fun/bars-replay/v1` on stdin/stdout: one JSON line per minute, one reply per batch.
