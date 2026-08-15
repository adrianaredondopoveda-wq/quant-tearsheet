"""
Quantitative Tearsheet
-----------------------
Builds a one-page performance and risk report ("tearsheet") for any
ticker, computing standard risk-adjusted return metrics from scratch
(no quantstats / pyfolio dependency) and visualizing them.

Author: Adriana
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.style.use('seaborn-v0_8-darkgrid')

TRADING_DAYS_PER_YEAR = 252


# ---------------------------------------------------------------------
# 1. Data
# ---------------------------------------------------------------------
def download_prices(ticker: str, start: str, end: str) -> pd.Series:
    """Download daily close prices for a given ticker."""
    data = yf.download(ticker, start=start, end=end)
    prices = data['Close'].squeeze()  # ensures a 1D Series, not a DataFrame
    return prices


# ---------------------------------------------------------------------
# 2. Returns
# ---------------------------------------------------------------------
def compute_log_returns(prices: pd.Series) -> pd.Series:
    """Daily log returns. Log returns are additive over time, which is
    why we can sum (not multiply) them when aggregating over periods."""
    return np.log(prices / prices.shift(1)).dropna()


def compute_cumulative_returns(log_returns: pd.Series) -> pd.Series:
    """Growth of $1 invested at the start of the period."""
    return np.exp(log_returns.cumsum())


# ---------------------------------------------------------------------
# 3. Risk / return metrics
# ---------------------------------------------------------------------
def compute_metrics(log_returns: pd.Series, cumulative_returns: pd.Series) -> dict:
    total_return = cumulative_returns.iloc[-1]
    n_years = len(log_returns) / TRADING_DAYS_PER_YEAR

    cagr = total_return ** (1 / n_years) - 1
    volatility = log_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    sharpe = (log_returns.mean() * TRADING_DAYS_PER_YEAR) / volatility

    downside_returns = log_returns[log_returns < 0]
    downside_vol = downside_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    sortino = (log_returns.mean() * TRADING_DAYS_PER_YEAR) / downside_vol

    running_max = cumulative_returns.cummax()
    drawdown = (cumulative_returns - running_max) / running_max
    max_drawdown = drawdown.min()

    calmar = cagr / abs(max_drawdown)

    return {
        "CAGR": cagr,
        "Annualized Volatility": volatility,
        "Sharpe Ratio": sharpe,
        "Sortino Ratio": sortino,
        "Max Drawdown": max_drawdown,
        "Calmar Ratio": calmar,
        "_drawdown_series": drawdown,  # kept for plotting
    }


# ---------------------------------------------------------------------
# 4. Monthly returns table (for the heatmap)
# ---------------------------------------------------------------------
def compute_monthly_returns_pivot(log_returns: pd.Series) -> pd.DataFrame:
    monthly = log_returns.resample('ME').apply(lambda x: np.exp(x.sum()) - 1)
    table = monthly.to_frame('return')
    table['year'] = table.index.year
    table['month'] = table.index.month
    return table.pivot(index='year', columns='month', values='return')


# ---------------------------------------------------------------------
# 5. Plotting: full one-page dashboard
# ---------------------------------------------------------------------
def plot_tearsheet(ticker: str, cumulative_returns: pd.Series, log_returns: pd.Series,
                    metrics: dict, monthly_pivot: pd.DataFrame, output_path: str = "tearsheet.png"):

    drawdown = metrics["_drawdown_series"]

    fig = plt.figure(figsize=(14, 12))
    gs = fig.add_gridspec(4, 2, hspace=0.5, wspace=0.3)

    # Equity curve
    ax1 = fig.add_subplot(gs[0, :])
    ax1.plot(cumulative_returns.index, cumulative_returns.values, color='navy')
    ax1.set_title('Cumulative Return', fontweight='bold')
    ax1.xaxis.set_major_locator(mdates.YearLocator())

    # Drawdown (underwater plot)
    ax2 = fig.add_subplot(gs[1, :])
    ax2.fill_between(drawdown.index, drawdown.values * 100, 0, color='red', alpha=0.4)
    ax2.set_title('Drawdown (%)', fontweight='bold')

    # Return distribution
    ax3 = fig.add_subplot(gs[2, 0])
    ax3.hist(log_returns, bins=60, color='steelblue', alpha=0.7)
    ax3.axvline(log_returns.mean(), color='red', linestyle='--', label='Mean')
    ax3.set_title('Daily Return Distribution', fontweight='bold')
    ax3.legend()

    # Key metrics table
    ax4 = fig.add_subplot(gs[2, 1])
    ax4.axis('off')
    metrics_text = (
        f"CAGR: {metrics['CAGR']:.2%}\n"
        f"Volatility: {metrics['Annualized Volatility']:.2%}\n"
        f"Sharpe: {metrics['Sharpe Ratio']:.2f}\n"
        f"Sortino: {metrics['Sortino Ratio']:.2f}\n"
        f"Max Drawdown: {metrics['Max Drawdown']:.2%}\n"
        f"Calmar: {metrics['Calmar Ratio']:.2f}"
    )
    ax4.text(0.1, 0.5, metrics_text, fontsize=13, va='center', family='monospace')
    ax4.set_title('Key Metrics', fontweight='bold')

    # Monthly returns heatmap
    ax5 = fig.add_subplot(gs[3, :])
    im = ax5.imshow(monthly_pivot.values * 100, cmap='RdYlGn', aspect='auto')
    ax5.set_xticks(range(12))
    ax5.set_xticklabels(['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'])
    ax5.set_yticks(range(len(monthly_pivot.index)))
    ax5.set_yticklabels(monthly_pivot.index)
    ax5.set_title('Monthly Returns (%)', fontweight='bold')
    plt.colorbar(im, ax=ax5, label='% return')

    fig.suptitle(f'Quantitative Tearsheet — {ticker}', fontsize=18, fontweight='bold')
    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    plt.show()


# ---------------------------------------------------------------------
# 6. Main
# ---------------------------------------------------------------------
if __name__ == "__main__":
    TICKER = "^GSPC"
    START = "2015-01-01"
    END = "2026-08-15"

    prices = download_prices(TICKER, START, END)
    log_returns = compute_log_returns(prices)
    cumulative_returns = compute_cumulative_returns(log_returns)
    metrics = compute_metrics(log_returns, cumulative_returns)
    monthly_pivot = compute_monthly_returns_pivot(log_returns)

    print(f"--- {TICKER} Tearsheet Metrics ---")
    for key, value in metrics.items():
        if key.startswith("_"):
            continue
        if "Ratio" in key:
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value:.2%}")

    plot_tearsheet(TICKER, cumulative_returns, log_returns, metrics, monthly_pivot)
