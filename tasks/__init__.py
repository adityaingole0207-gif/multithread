"""Task package with Standard and Banking Workloads."""

from tasks.task_types import (
    cpu_matrix_multiplication,
    cpu_prime_calculation,
    cpu_file_hashing,
    io_simulated_network,
    io_simulated_disk,
    mixed_word_count,
    mixed_image_processing,
    cooperative_quanta_task,
    database_query_task,
    faulty_task,
)

from tasks.banking_tasks import (
    bank_ledger,
    bank_safe_transfer,
    bank_atm_withdrawal,
    bank_swift_wire_transfer,
    bank_fraud_ai_analysis,
    bank_corporate_payroll_quantum,
    run_banking_double_spend_race,
    run_banking_cross_transfer_deadlock,
)

__all__ = [
    "cpu_matrix_multiplication",
    "cpu_prime_calculation",
    "cpu_file_hashing",
    "io_simulated_network",
    "io_simulated_disk",
    "mixed_word_count",
    "mixed_image_processing",
    "cooperative_quanta_task",
    "database_query_task",
    "faulty_task",
    "bank_ledger",
    "bank_safe_transfer",
    "bank_atm_withdrawal",
    "bank_swift_wire_transfer",
    "bank_fraud_ai_analysis",
    "bank_corporate_payroll_quantum",
    "run_banking_double_spend_race",
    "run_banking_cross_transfer_deadlock",
]
