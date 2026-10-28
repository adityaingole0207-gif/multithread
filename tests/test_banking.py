"""
Unit tests for Core Banking Concurrency and Transaction Synchronization.
Tests:
- Atomic Fund Transfers (Mutex & Global Lock Ordering)
- Concurrent ATM Double-Spend Prevention vs Race Condition Vulnerability
- Cross-Account Transfer Deadlock Detection & Avoidance
- SWIFT International Settlement via Counting Semaphore
"""

import pytest
from tasks.banking_tasks import (
    bank_ledger,
    bank_safe_transfer,
    bank_atm_withdrawal,
    bank_swift_wire_transfer,
    run_banking_double_spend_race,
    run_banking_cross_transfer_deadlock,
)


@pytest.fixture(autouse=True)
def reset_ledger_state():
    bank_ledger.reset_balances()
    yield
    bank_ledger.reset_balances()


def test_bank_safe_transfer():
    """Verify that safe transfer atomically moves funds between accounts."""
    res = bank_safe_transfer("ACC_101", "ACC_102", 500.0)
    assert res["status"] == "transferred"
    assert res["from_balance"] == 4500.0
    assert res["to_balance"] == 4700.0


def test_bank_atm_insufficient_funds():
    """Verify overdraft protection prevents withdrawal when balance is insufficient."""
    res = bank_atm_withdrawal("ACC_101", 6000.0)
    assert res["status"] == "declined"
    assert res["balance"] == 5000.0


def test_bank_double_spend_with_mutex():
    """Verify Mutex prevents double spending across 10 concurrent ATMs."""
    res = run_banking_double_spend_race(account_id="ACC_101", concurrent_withdrawals=10, amount_per_tx=600.0, use_mutex=True)
    # $5,000 balance / $600 = 8 successful ($4,800), 2 declined, $200 remainder
    assert res["successful_withdrawals"] == 8
    assert res["declined_withdrawals"] == 2
    assert res["final_balance"] == 200.0
    assert res["bank_loss_anomaly"] is False


def test_bank_cross_transfer_deadlock_detected():
    """Verify circular wait in reciprocal fund transfers triggers deadlock."""
    res = run_banking_cross_transfer_deadlock(avoid_deadlock=False)
    assert res["deadlocked"] is True


def test_bank_cross_transfer_deadlock_avoided():
    """Verify Account ID lock ordering avoids deadlock completely."""
    res = run_banking_cross_transfer_deadlock(avoid_deadlock=True)
    assert res["deadlocked"] is False
    assert res["success"] is True


def test_bank_swift_semaphore_bound():
    """Verify SWIFT wire transfer acquires and releases semaphore permits."""
    res = bank_swift_wire_transfer(5000.0)
    assert res["status"] == "settled"
    assert "SWIFT_Settlement_Lines_Slot" in res["wire_channel"]
    status = bank_ledger.swift_gateway_pool.get_status()
    assert status["available_count"] == 3
    assert status["allocated_count"] == 0
