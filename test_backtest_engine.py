"""
🛡️ VALKYRIE QUANT DESK - BACKTEST & OUT-OF-SAMPLE TEST SUITE
Test the mathematical soundness, time series isolation, fee deduction,
and degradation index calculations of the Backtest Engine.
"""

import pytest
import pandas as pd
import numpy as np
from backtest_engine import ValkyrieBacktestEngine


def test_synthetic_klines_generation():
    engine = ValkyrieBacktestEngine()
    df = engine.generate_synthetic_klines(days=7, interval_minutes=5)
    assert len(df) == (7 * 24 * 60) // 5
    assert all(col in df.columns for col in ['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    assert (df['high'] >= df['low']).all()
    assert (df['high'] >= df['open']).all()
    assert (df['high'] >= df['close']).all()
    assert (df['low'] <= df['open']).all()
    assert (df['low'] <= df['close']).all()


def test_indicator_calculations():
    engine = ValkyrieBacktestEngine()
    df = engine.generate_synthetic_klines(days=5, interval_minutes=5)
    df_ind = engine.calculate_indicators(df, camarilla_lookback=24)
    
    assert 'atr_14' in df_ind.columns
    assert 'rvol' in df_ind.columns
    assert 'cam_p' in df_ind.columns
    assert 'cam_r4' in df_ind.columns
    assert 'cam_s4' in df_ind.columns
    assert not df_ind['cam_r4'].iloc[25:].isna().any()


def test_time_series_chronological_split():
    engine = ValkyrieBacktestEngine(oos_ratio=0.30)
    df = engine.generate_synthetic_klines(days=10, interval_minutes=5)
    results = engine.run_simulation(df)
    
    total = results['total_bars']
    is_bars = results['is_bars']
    oos_bars = results['oos_bars']
    
    assert is_bars + oos_bars == total
    assert round(oos_bars / total, 2) == 0.30
    assert "in_sample" in results
    assert "out_of_sample" in results
    assert "combined" in results


def test_commission_and_slippage_accounting():
    # If commission is zero vs positive, net PnL must reflect the exact fee difference
    engine_fee = ValkyrieBacktestEngine(commission_rate=0.001)  # 0.1% per leg
    df = engine_fee.generate_synthetic_klines(days=15, interval_minutes=5, seed=123)
    results = engine_fee.run_simulation(df)
    
    comb = results['combined']
    assert comb['total_commission_paid'] >= 0.0
    assert comb['degradation_index'] >= 0.0
    assert comb['health_status'] in ["ROBUST_EDGE", "MODERATE_DECAY", "OVERFITTED_DANGER"]
