import json
from pathlib import Path

POSITIONS_FILE = Path("../positions.json")
CAPITAL        = 100_000
MAX_POSITIONS  = 5
RISK_PCT       = 0.02
REWARD_RATIO   = 2.0

def verify():
    if not POSITIONS_FILE.exists():
        print("positions.json not found")
        return

    with open(POSITIONS_FILE) as f:
        positions = json.load(f)

    if not positions:
        print("No open positions in positions.json")
        return

    print(f"\n{'=' * 65}")
    print(f"TRADE ACCURACY CHECK  —  {len(positions)} open position(s)")
    print(f"{'=' * 65}")

    total_allocated = 0
    total_risk = 0
    all_ok = True

    for symbol, position in positions.items():
        entry = position["entry_price"]
        stop = position["stop_price"]
        target = position["target_price"]
        qty = position["qty"]
        side = position["side"]

        risk_per_share = abs(entry - stop)
        slot_capital = CAPITAL / MAX_POSITIONS

        # Recalculate what quantity SHOULD be
        expected_from_risk = int((CAPITAL * RISK_PCT) / risk_per_share)
        expected_from_slot = int(slot_capital / entry)
        expected_qty = max(1, min(expected_from_risk, expected_from_slot))

        # Recalculate what target SHOULD be
        expected_target = round(
            entry + REWARD_RATIO * risk_per_share if side == "BUY"
            else entry - REWARD_RATIO * risk_per_share, 2
        )

        allocated = qty * entry
        risk_amt = qty * risk_per_share
        reward_amt = qty * abs(target - entry)
        rr_ratio = abs(target - entry) / risk_per_share if risk_per_share > 0 else 0

        qty_ok = (qty == expected_qty)
        target_ok = (abs(target - expected_target) < 0.5)

        total_allocated += allocated
        total_risk += risk_amt

        print(f"\n{symbol}  ({side})")
        print(f"{'─' * 60}")
        print(f"Entry price    : ₹{entry:>10.2f}")
        print(f"Stop price     : ₹{stop:>10.2f}  "
              f"(risk/share = ₹{risk_per_share:.2f})")
        print(f"Target price   : ₹{target:>10.2f}  "
              f"{'✓' if target_ok else '✗ expected ₹' + str(expected_target)}")
        print(f"Quantity       : {qty:>10}  "
              f"{'✓' if qty_ok else '✗ expected ' + str(expected_qty)}")
        print(f"Allocated      : ₹{allocated:>10,.0f}  "
              f"({allocated / CAPITAL * 100:.1f}% of capital)")
        print(f"Max loss       : ₹{risk_amt:>10,.0f}  "
              f"({risk_amt / CAPITAL * 100:.2f}% of capital)")
        print(f"Max profit     : ₹{reward_amt:>10,.0f}  "
              f"({reward_amt / CAPITAL * 100:.2f}% of capital)")
        print(f"Risk : Reward  :   1 : {rr_ratio:.1f}  "
              f"{'✓' if abs(rr_ratio - REWARD_RATIO) < 0.1 else '✗ expected 1:' + str(REWARD_RATIO)}")

        if not qty_ok or not target_ok:
            all_ok = False

    total_risk_pct = total_risk / CAPITAL * 100

    print(f"\n{'=' * 65}")
    print(f"PORTFOLIO TOTALS")
    print(f"{'=' * 65}")
    print(f"Positions open    : {len(positions)} / {MAX_POSITIONS}")
    print(f"Capital allocated : ₹{total_allocated:>12,.0f}  "
          f"({total_allocated / CAPITAL * 100:.1f}%)")
    print(f"Capital free      : ₹{CAPITAL - total_allocated:>12,.0f}  "
          f"({(CAPITAL - total_allocated) / CAPITAL * 100:.1f}%)")
    print(f"Total max risk    : ₹{total_risk:>12,.0f}  "
          f"({total_risk_pct:.1f}% of capital)")

    per_slot = CAPITAL / MAX_POSITIONS
    over_slot = [(s, p["qty"] * p["entry_price"])
                 for s, p in positions.items()
                 if p["qty"] * p["entry_price"] > per_slot * 1.05]
    if over_slot:
        print(f"\nThese positions exceed slot size (₹{per_slot:,.0f}):")
        for sym, val in over_slot:
            print(f"{sym}: ₹{val:,.0f}")

    print(f"\nOverall: {'✓ All checks passed' if all_ok else '⚠️  Some values differ — review above'}")
    print(f"{'=' * 65}\n")


if __name__ == "__main__":
    verify()