"""
Banking & Financial Transaction Domain Workloads for Multithreaded Engine.

OS Concepts Illustrated via Core Banking Systems:
- Critical Section & Race Conditions: Concurrent ATM withdrawals & double-spend attacks.
- Mutual Exclusion (Mutex): Account-level locking for atomic debit/credit.
- Deadlock (Circular Wait): Cross-account transfers (Alice -> Bob vs Bob -> Alice).
- Deadlock Avoidance: Account ID Ordering Protocol (Lock min(ID_A, ID_B) then max(ID_A, ID_B)).
- Counting Semaphore: Bounded SWIFT / Payment Gateway connection lines (Capacity: 3).
- CPU Scheduling & Priority Aging: Real-time fraud detection & VIP wires vs batch statements.
- Cooperative Round-Robin: Large corporate payroll disbursements sliced into fair quanta.
"""

import time
import random
import threading
from typing import Any, Dict, List, Optional, Tuple
from engine.task import Task
from engine.resources import SharedResourcePool


class BankAccount:
    """Thread-safe bank account model with internal Mutex."""
    def __init__(self, account_id: str, holder_name: str, initial_balance: float):
        self.account_id = account_id
        self.holder_name = holder_name
        self.balance = initial_balance
        self.lock = threading.Lock()
        self.transaction_count = 0

    def to_dict(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "account_id": self.account_id,
                "holder_name": self.holder_name,
                "balance": round(self.balance, 2),
                "transaction_count": self.transaction_count,
            }


class BankLedger:
    """Central ledger managing accounts and concurrency synchronization."""
    def __init__(self):
        self.accounts: Dict[str, BankAccount] = {
            "ACC_101": BankAccount("ACC_101", "Alice Smith", 5000.0),
            "ACC_102": BankAccount("ACC_102", "Bob Jones", 4200.0),
            "ACC_103": BankAccount("ACC_103", "Charlie Brown", 3500.0),
            "ACC_104": BankAccount("ACC_104", "Diana Prince", 8900.0),
            "ACC_105": BankAccount("ACC_105", "Enterprise Corp", 50000.0),
            "ACC_106": BankAccount("ACC_106", "FinTech Global", 75000.0),
        }
        self.swift_gateway_pool = SharedResourcePool(name="SWIFT_Settlement_Lines", capacity=3)
        self.global_ledger_lock = threading.Lock()
        self.audit_log: List[str] = []

    def reset_balances(self) -> None:
        """Reset accounts to initial baseline."""
        with self.global_ledger_lock:
            self.accounts["ACC_101"].balance = 5000.0
            self.accounts["ACC_102"].balance = 4200.0
            self.accounts["ACC_103"].balance = 3500.0
            self.accounts["ACC_104"].balance = 8900.0
            self.accounts["ACC_105"].balance = 50000.0
            self.accounts["ACC_106"].balance = 75000.0
            for acc in self.accounts.values():
                acc.transaction_count = 0
            self.audit_log.clear()

    def get_accounts_summary(self) -> List[Dict[str, Any]]:
        return [acc.to_dict() for acc in self.accounts.values()]


# Global singleton instance for the app
bank_ledger = BankLedger()


# ---------------- BANKING TRANSACTION TASKS ----------------

def bank_safe_transfer(from_id: str, to_id: str, amount: float, task_ref: Optional[Task] = None) -> Dict[str, Any]:
    """
    OS Concept: Deadlock Avoidance via Resource Hierarchy (Global Lock Ordering).
    To avoid circular wait when Alice transfers to Bob while Bob transfers to Alice:
    Both threads acquire the lock of the account with the smaller ID first!
    """
    if from_id == to_id:
        return {"status": "error", "message": "Source and destination accounts must differ"}

    acc_from = bank_ledger.accounts.get(from_id)
    acc_to = bank_ledger.accounts.get(to_id)
    if not acc_from or not acc_to:
        raise ValueError("Invalid account identifier")

    # Global Lock Ordering Protocol: min ID first, then max ID
    first_lock = acc_from.lock if from_id < to_id else acc_to.lock
    second_lock = acc_to.lock if from_id < to_id else acc_from.lock

    with first_lock:
        time.sleep(0.04)  # Simulate network / ledger query
        with second_lock:
            if acc_from.balance < amount:
                return {
                    "status": "rejected",
                    "reason": "Insufficient balance",
                    "from_account": from_id,
                    "attempted": amount,
                    "available": acc_from.balance,
                }
            acc_from.balance -= amount
            acc_to.balance += amount
            acc_from.transaction_count += 1
            acc_to.transaction_count += 1
            
            if task_ref:
                task_ref.progress = 1.0

            return {
                "status": "transferred",
                "from_account": from_id,
                "to_account": to_id,
                "amount": amount,
                "from_balance": round(acc_from.balance, 2),
                "to_balance": round(acc_to.balance, 2),
            }


def bank_atm_withdrawal(account_id: str, amount: float, task_ref: Optional[Task] = None) -> Dict[str, Any]:
    """
    ATM cash withdrawal protected by Mutex to prevent double-spending.
    """
    acc = bank_ledger.accounts.get(account_id)
    if not acc:
        raise ValueError(f"Account {account_id} not found")

    with acc.lock:
        time.sleep(0.06)  # Dispenser mechanical simulation
        if acc.balance < amount:
            return {"status": "declined", "reason": "Insufficient funds", "balance": acc.balance}
        acc.balance -= amount
        acc.transaction_count += 1
        if task_ref:
            task_ref.progress = 1.0
        return {"status": "dispensed", "account": account_id, "amount": amount, "new_balance": acc.balance}


def bank_swift_wire_transfer(amount: float, task_ref: Optional[Task] = None) -> Dict[str, Any]:
    """
    OS Concept: Counting Semaphore.
    International SWIFT wire transfers require one of only 3 secure encryption pipeline channels.
    """
    pool = bank_ledger.swift_gateway_pool
    if task_ref:
        task_ref.state = task_ref.state.__class__.BLOCKED

    permit = pool.acquire(requester_id=task_ref.task_id if task_ref else "WireTx", timeout=4.0)
    if not permit:
        raise TimeoutError("SWIFT settlement gateway timeout (All 3 channels saturated)")

    try:
        if task_ref:
            task_ref.resource_held = permit
            task_ref.state = task_ref.state.__class__.RUNNING

        # Simulate secure cryptographic signature & interbank settlement
        time.sleep(0.35)
        if task_ref:
            task_ref.progress = 1.0
        return {"status": "settled", "wire_channel": permit, "amount": amount}
    finally:
        pool.release(permit)
        if task_ref:
            task_ref.resource_held = None


def bank_fraud_ai_analysis(account_id: str, task_ref: Optional[Task] = None) -> Dict[str, Any]:
    """
    OS Concept: CPU-Bound Transaction Risk Scoring (Matrix / Hash / Anomaly Scoring).
    High priority task evaluating high-value transfers.
    """
    score = 0
    for i in range(12000):
        if task_ref and task_ref.cancellation_token.is_set():
            return {"status": "cancelled"}
        score = (score + i * 37) % 10000
        if task_ref and i % 2000 == 0:
            task_ref.progress = min(0.99, i / 12000)

    risk_level = "LOW_RISK" if score < 7000 else "FLAGGED_FOR_REVIEW"
    if task_ref:
        task_ref.progress = 1.0
    return {"account": account_id, "risk_score": score, "classification": risk_level}


def bank_corporate_payroll_quantum(company_id: str = "ACC_105", total_employees: int = 120, task_ref: Optional[Task] = None) -> Dict[str, Any]:
    """
    OS Concept: Cooperative Round-Robin Time-Slicing.
    Corporate payroll takes multiple quanta to disburse across thousands of employees.
    Yields CPU between slices so retail banking users aren't starved!
    """
    if task_ref and not hasattr(task_ref, "employees_paid"):
        task_ref.employees_paid = 0
        task_ref.total_employees = total_employees

    # Process batch of 30 employees per quantum
    time.sleep(0.12)
    if task_ref:
        task_ref.employees_paid += 30
        task_ref.progress = min(1.0, task_ref.employees_paid / task_ref.total_employees)
        is_done = task_ref.employees_paid >= task_ref.total_employees
        return {
            "finished": is_done,
            "company": company_id,
            "disbursed_so_far": task_ref.employees_paid,
            "total_employees": task_ref.total_employees,
        }
    return {"finished": True}


# ---------------- BANKING SYNCHRONIZATION DEMOS ----------------

def run_banking_double_spend_race(account_id: str = "ACC_101", concurrent_withdrawals: int = 10, amount_per_tx: float = 600.0, use_mutex: bool = False) -> Dict[str, Any]:
    """
    Demonstrates Race Condition:
    Account has $5,000. 10 ATMs simultaneously try to withdraw $600 (Total $6,000 requested).
    With Mutex: Exactly 8 withdrawals succeed ($4,800 total), 2 fail (insufficient funds), balance = $200.
    Without Mutex (Race Condition): Interleaved reads allow ALL 10 to withdraw! The balance goes negative or becomes corrupt!
    """
    initial_balance = 5000.0
    shared_balance = {"val": initial_balance}
    acc_lock = threading.Lock()
    successful_withdrawals = 0
    declined_withdrawals = 0
    results_lock = threading.Lock()

    def atm_worker(worker_id: int):
        nonlocal successful_withdrawals, declined_withdrawals
        if use_mutex:
            with acc_lock:
                current = shared_balance["val"]
                time.sleep(0.002)  # Context switch window
                if current >= amount_per_tx:
                    shared_balance["val"] = current - amount_per_tx
                    with results_lock:
                        successful_withdrawals += 1
                else:
                    with results_lock:
                        declined_withdrawals += 1
        else:
            # Unsynchronized critical section: classic banking double-spend race condition
            current = shared_balance["val"]
            time.sleep(0.002)  # Preemptive context switch happens right here!
            if current >= amount_per_tx:
                shared_balance["val"] = current - amount_per_tx
                with results_lock:
                    successful_withdrawals += 1
            else:
                with results_lock:
                    declined_withdrawals += 1

    threads = []
    for i in range(concurrent_withdrawals):
        t = threading.Thread(target=atm_worker, args=(i+1,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    total_withdrawn = successful_withdrawals * amount_per_tx
    final_balance = shared_balance["val"]
    overdraft_occurred = (total_withdrawn > initial_balance) or (final_balance < 0) or (final_balance != (initial_balance - total_withdrawn))

    return {
        "mode": "Mutex Protected (Atomic Debit)" if use_mutex else "Unsynchronized (Double-Spend Vulnerability)",
        "initial_balance": initial_balance,
        "concurrent_atms": concurrent_withdrawals,
        "withdrawal_amount": amount_per_tx,
        "successful_withdrawals": successful_withdrawals,
        "declined_withdrawals": declined_withdrawals,
        "final_balance": round(final_balance, 2),
        "total_cash_dispensed": total_withdrawn,
        "bank_loss_anomaly": overdraft_occurred,
        "explanation": (
            "With Mutex enabled, withdrawals are serialized: once balance reaches $200, subsequent withdrawals "
            "are properly declined. Without locks, concurrent ATMs read the old balance before debits commit, "
            "allowing double-spending and resulting in bank cash loss!"
        ),
    }


def run_banking_cross_transfer_deadlock(avoid_deadlock: bool = False) -> Dict[str, Any]:
    """
    Demonstrates Transfer Deadlock:
    Transfer 1: Alice (ACC_101) transfers $500 to Bob (ACC_102) -> needs Lock(Alice) then Lock(Bob).
    Transfer 2: Bob (ACC_102) transfers $300 to Alice (ACC_101) -> needs Lock(Bob) then Lock(Alice).
    
    If avoid_deadlock is False: Circular Wait causes permanent deadlock (timed out after 1.5s).
    If avoid_deadlock is True: Both acquire Lock(min(ID_1, ID_2)) then Lock(max(ID_1, ID_2)).
    """
    lock_alice = threading.Lock()
    lock_bob = threading.Lock()
    logs = []
    log_lock = threading.Lock()

    def log(msg: str):
        with log_lock:
            logs.append(f"[{time.strftime('%H:%M:%S')}] {msg}")

    state = {"tx1_done": False, "tx2_done": False, "deadlocked": False}

    if not avoid_deadlock:
        # Transfer 1: Alice -> Bob
        def tx_alice_to_bob():
            log("Tx 1 (Alice->Bob): Locking Alice's Account...")
            lock_alice.acquire()
            log("Tx 1 (Alice->Bob): Locked Alice. Preparing ledger...")
            time.sleep(0.2)
            log("Tx 1 (Alice->Bob): Attempting to lock Bob's Account (Wait for Tx 2)...")
            acquired = lock_bob.acquire(timeout=1.5)
            if acquired:
                log("Tx 1: Acquired Bob! Transfer committed.")
                lock_bob.release()
                state["tx1_done"] = True
            else:
                log("Tx 1: DEADLOCK DETECTED! Timed out waiting for Bob's lock.")
            lock_alice.release()

        # Transfer 2: Bob -> Alice
        def tx_bob_to_alice():
            log("Tx 2 (Bob->Alice): Locking Bob's Account...")
            lock_bob.acquire()
            log("Tx 2 (Bob->Alice): Locked Bob. Preparing ledger...")
            time.sleep(0.2)
            log("Tx 2 (Bob->Alice): Attempting to lock Alice's Account (Wait for Tx 1)...")
            acquired = lock_alice.acquire(timeout=1.5)
            if acquired:
                log("Tx 2: Acquired Alice! Transfer committed.")
                lock_alice.release()
                state["tx2_done"] = True
            else:
                log("Tx 2: DEADLOCK DETECTED! Timed out waiting for Alice's lock.")
            lock_bob.release()

        t1 = threading.Thread(target=tx_alice_to_bob)
        t2 = threading.Thread(target=tx_bob_to_alice)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        state["deadlocked"] = not (state["tx1_done"] and state["tx2_done"])
        return {
            "mode": "Deadlock Incurred (Circular Wait in Cross-Transfer)",
            "deadlocked": state["deadlocked"],
            "logs": logs,
            "explanation": (
                "Deadlock occurred because Tx 1 holds Lock(Alice) waiting for Lock(Bob), "
                "while Tx 2 holds Lock(Bob) waiting for Lock(Alice). Circular dependency forms."
            ),
        }

    else:
        # Lock Ordering: Always lock Account with smaller ID first (Alice < Bob)
        def tx_ordered(tx_id: int, from_name: str, to_name: str):
            log(f"Tx {tx_id} ({from_name}->{to_name}): Enforcing Account ID Order (Lock Alice FIRST)...")
            with lock_alice:
                log(f"Tx {tx_id}: Acquired Alice's lock. Next locking Bob...")
                with lock_bob:
                    log(f"Tx {tx_id}: Acquired Bob's lock. Both accounts locked safely. Committing transfer...")
                    time.sleep(0.1)
                log(f"Tx {tx_id}: Released Bob's lock.")
            log(f"Tx {tx_id}: Released Alice's lock. Transfer {tx_id} completed successfully!")
            state[f"tx{tx_id}_done"] = True

        t1 = threading.Thread(target=tx_ordered, args=(1, "Alice", "Bob"))
        t2 = threading.Thread(target=tx_ordered, args=(2, "Bob", "Alice"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        return {
            "mode": "Deadlock Avoided via Global Account ID Ordering",
            "deadlocked": False,
            "success": state["tx1_done"] and state["tx2_done"],
            "logs": logs,
            "explanation": (
                "Deadlock avoided by ordering account locks: both transactions request Lock(Alice) "
                "before Lock(Bob). Circular wait is broken, and transfers proceed deterministically."
            ),
        }
