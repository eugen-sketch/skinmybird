"""AGGRESSIVE_MODE: aceleasi reguli de siguranta, mai multe semnale si expunere mai mare. Implicit OPRIT.
Se activeaza cu config.json "aggressive_mode": true sau variabila AGGRESSIVE_MODE=1, pe demo si pe real (decizia utilizatorului)."""
from __future__ import annotations

import copy
import os


def on(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "da", "on")


def apply(cfg: dict, real: bool) -> dict:
    """Intoarce configul efectiv. Seteaza cfg['_aggressive'] (bool) si, la nevoie, cfg['_mode_note'] (text pentru Telegram)."""
    out = copy.deepcopy(cfg)
    out["_aggressive"], out["_mode_note"] = False, ""
    asked = on(os.getenv("AGGRESSIVE_MODE", "")) or on(cfg.get("aggressive_mode", False))
    if not asked:
        return out
    a = cfg["aggressive"]
    for inst in out["instruments"]:
        sigs = []
        for n in inst["signals"]:
            if n.startswith("rsi_rev"):
                n = f"rsi_rev{a['rsi_oil'] if inst['name'] == 'OIL' else a['rsi_forex']}"
            elif n.startswith("pullback"):
                n = f"pullback{a['pullback']}"
            sigs.append(n)
        inst["signals"] = sigs
    for k in ("wave_atr", "max_positions", "max_positions_small", "tp_atr", "max_tp_usd", "sl_atr", "max_sl_usd", "autotrade_daily_loss_usd"):
        if k in a:
            out[k] = a[k]
    out["wave_opts"] = {"cooldown_min": a["wave_cooldown_min"], "rsi_buy_max": a["wave_rsi_buy_max"], "rsi_sell_min": a["wave_rsi_sell_min"],
                        "allow_neutral": a["wave_allow_neutral"]}
    out["wave_max_proposals"] = a["wave_max_proposals"]
    out["signal_cooldown_min"] = a["signal_cooldown_min"]
    out["boost_alloc"] = a["boost_alloc"]
    out["_aggressive"] = True
    return out
