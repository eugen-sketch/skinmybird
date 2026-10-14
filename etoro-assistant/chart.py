"""Grafic simplu pentru Telegram: lumanari de 1 ora, medii EMA50/EMA200, nivelurile de intrare/tinta/plasa, suport/rezistenta si RSI."""
from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

import ta  # noqa: E402

BG, FG, GRID, UP, DOWN = "#0f1420", "#d7dce6", "#232b3d", "#26a269", "#e5484d"


def render(df: pd.DataFrame, title: str, side: int | None = None, entry: float | None = None, tp: float | None = None,
           sl: float | None = None, support: float | None = None, resistance: float | None = None, bars: int = 72,
           digits: int = 5) -> bytes:
    """PNG cu ultimele `bars` lumanari. side: +1 cumparare / -1 vanzare (pentru etichete); entry/tp/sl/suport/rezistenta = linii orizontale."""
    close = df["close"]
    e50, e200, rsi = ta.ema(close, 50), ta.ema(close, 200), ta.rsi(close, 14)
    d = df.iloc[-bars:]
    x = list(range(len(d)))
    fig, (ax, ar) = plt.subplots(2, 1, figsize=(9, 6), gridspec_kw={"height_ratios": [4, 1]}, sharex=True, facecolor=BG)
    for a_ in (ax, ar):
        a_.set_facecolor(BG)
        a_.tick_params(colors=FG, labelsize=8)
        a_.grid(color=GRID, linewidth=0.6)
        for s in a_.spines.values():
            s.set_color(GRID)
    for i, (_, r) in zip(x, d.iterrows()):
        col = UP if r["close"] >= r["open"] else DOWN
        ax.plot([i, i], [r["low"], r["high"]], color=col, linewidth=1)
        lo, hi = sorted((r["open"], r["close"]))
        ax.add_patch(plt.Rectangle((i - 0.3, lo), 0.6, max(hi - lo, (r["high"] - r["low"]) * 0.02), color=col))
    ax.plot(x, e50.iloc[-bars:].values, color="#f5a623", linewidth=1.2, label="EMA50")
    ax.plot(x, e200.iloc[-bars:].values, color="#4da3ff", linewidth=1.2, label="EMA200")

    lo_p, hi_p = float(d["low"].min()), float(d["high"].max())
    extra = [v for v in (tp, sl, entry) if v]
    if extra:
        lo_p, hi_p = min(lo_p, *extra), max(hi_p, *extra)
    pad = (hi_p - lo_p) * 0.08 or hi_p * 0.001
    ax.set_ylim(lo_p - pad, hi_p + pad)
    ax.set_xlim(-1, len(d) + 14)

    def line(y, color, label, style="-"):
        if y and lo_p - pad <= y <= hi_p + pad:                      # liniile din afara graficului nu se deseneaza
            ax.axhline(y, color=color, linestyle=style, linewidth=1.2)
            ax.text(len(d) + 13.5, y, f"{label} {y:.{digits}f}", color=color, fontsize=8, va="center", ha="right",
                    bbox={"facecolor": BG, "edgecolor": "none", "pad": 1.5})
    line(entry, FG, "intrare", "--")
    line(tp, UP, "țintă")
    line(sl, DOWN, "plasă")
    line(resistance, "#b57bff", "rezistență", ":")
    line(support, "#7bd3ff", "suport", ":")
    arrow = {1: "▲ CUMPĂRARE", -1: "▼ VÂNZARE"}.get(side, "")
    ax.set_title(f"{title}  {arrow}  (lumânări de 1 oră, ora României)", color=FG, fontsize=11, loc="left")
    ax.legend(loc="upper left", facecolor=BG, edgecolor=GRID, labelcolor=FG, fontsize=8)
    ar.plot(x, rsi.iloc[-bars:].values, color="#c9d1e0", linewidth=1.2)
    for lv, c in ((70, DOWN), (30, UP)):
        ar.axhline(lv, color=c, linewidth=0.8, linestyle="--")
    ar.set_ylim(0, 100)
    ar.set_ylabel("RSI", color=FG, fontsize=8)
    ticks = list(range(0, len(d), max(1, len(d) // 6)))
    ar.set_xticks(ticks)
    ar.set_xticklabels([d.index[t].tz_convert("Europe/Bucharest").strftime("%d.%m %H:%M") if d.index.tz is not None else f"{d.index[t]:%d.%m %H:%M}" for t in ticks], fontsize=7)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, facecolor=BG)
    plt.close(fig)
    return buf.getvalue()
