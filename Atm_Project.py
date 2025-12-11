"""
Atm_Project.py

ATM MACHINE SIMULATION SYSTEM (SQLite)
- Account creation (account_number + PIN)
- Login using account_number + PIN
- Deposit and withdrawal update SQLite database immediately
- PIN stored as SHA-256 hash
- Session transaction history maintained in-memory
- Encapsulation: private balance and PIN hash inside Account class
- Inheritance: SavingsAccount extends Account
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import hashlib

DB_FILE = "atm_accounts.db"


def hash_pin(pin: str) -> str:
    """Return SHA-256 hex digest of the input PIN."""
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


class Transaction:
    """Represents a single in-session transaction record."""

    def __init__(self, txn_type: str, amount: float, balance_after: float) -> None:
        self.txn_type = txn_type
        self.amount = amount
        self.balance_after = balance_after
        self.timestamp = datetime.now()

    def __str__(self) -> str:
        return (
            f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] "
            f"{self.txn_type:<10} | Amount: ₹{self.amount:.2f} | Balance: ₹{self.balance_after:.2f}"
        )


class Account:
    """
    Account model linked to a SQLite row.

    Private attributes:
      - __pin_hash: stored hashed PIN
      - __balance: numeric balance

    Public methods:
      - _check_pin(pin): bool
      - get_balance(): float
      - deposit(amount): bool
      - withdraw(amount): bool
      - change_pin(old_pin, new_pin): bool
      - get_transactions(): List[Transaction]
    """

    def __init__(self, account_number: str, pin_hash: str, balance: float, conn: sqlite3.Connection) -> None:
        self.account_number = account_number
        self.__pin_hash = pin_hash
        self.__balance = float(balance)
        self._transactions: List[Transaction] = []
        self._conn = conn

    def _check_pin(self, pin: str) -> bool:
        """Validate plain-text PIN against stored hash."""
        return self.__pin_hash == hash_pin(pin)

    def _persist_balance(self) -> None:
        """Write current balance to the accounts table for this account."""
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE accounts SET balance = ? WHERE account_number = ?",
            (self.__balance, self.account_number),
        )
        self._conn.commit()

    def _persist_pin(self) -> None:
        """Write current PIN hash to the accounts table for this account."""
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE accounts SET pin = ? WHERE account_number = ?",
            (self.__pin_hash, self.account_number),
        )
        self._conn.commit()

    def get_balance(self) -> float:
        """Record an INQUIRY transaction and return current balance."""
        self._transactions.append(Transaction("INQUIRY", 0.0, self.__balance))
        return self.__balance

    def deposit(self, amount: float) -> bool:
        """Add amount to balance, persist to DB, record transaction. Return True on success."""
        if amount <= 0:
            return False
        self.__balance += amount
        self._persist_balance()
        self._transactions.append(Transaction("DEPOSIT", amount, self.__balance))
        return True

    def withdraw(self, amount: float) -> bool:
        """Subtract amount from balance if sufficient, persist to DB, record transaction."""
        if amount <= 0 or amount > self.__balance:
            return False
        self.__balance -= amount
        self._persist_balance()
        self._transactions.append(Transaction("WITHDRAW", amount, self.__balance))
        return True

    def change_pin(self, old_pin: str, new_pin: str) -> bool:
        """Change PIN if old_pin matches and new_pin meets length requirement."""
        if not self._check_pin(old_pin):
            return False
        if len(new_pin) < 4:
            return False
        self.__pin_hash = hash_pin(new_pin)
        self._persist_pin()
        return True

    def get_transactions(self) -> List[Transaction]:
        """Return a copy of session transactions."""
        return self._transactions.copy()


class SavingsAccount(Account):
    """Subclass of Account for potential future specialization."""
    pass


# Database helper functions
def init_db(conn: sqlite3.Connection) -> None:
    """Create accounts table if missing and insert sample accounts if absent."""
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            account_number TEXT PRIMARY KEY,
            pin TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 0
        )
        """
    )
    samples = [
        ("1001", hash_pin("1234"), 0.0),
        ("1002", hash_pin("5678"), 0.0),
        ("1003", hash_pin("0000"), 0.0),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO accounts (account_number, pin, balance) VALUES (?, ?, ?)",
        samples,
    )
    conn.commit()


def load_all_accounts(conn: sqlite3.Connection) -> Dict[str, Account]:
    """Load account rows into in-memory Account objects."""
    cur = conn.cursor()
    cur.execute("SELECT account_number, pin, balance FROM accounts")
    rows = cur.fetchall()
    accounts: Dict[str, Account] = {}
    for acc_no, pin_hash, balance in rows:
        accounts[acc_no] = SavingsAccount(acc_no, pin_hash, balance, conn)
    return accounts


def insert_account_to_db(conn: sqlite3.Connection, account_number: str, pin: str) -> bool:
    """Insert a new account row with hashed PIN and zero balance. Return False on IntegrityError."""
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO accounts (account_number, pin, balance) VALUES (?, ?, 0)",
            (account_number, hash_pin(pin)),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


class ATM:
    """Console ATM interface using in-memory Account objects backed by SQLite persistence."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        init_db(self._conn)
        self.accounts = load_all_accounts(self._conn)
        self.current_account: Optional[Account] = None

    def create_account(self) -> None:
        acc_no = input("Enter NEW Account Number: ").strip()
        if not acc_no:
            print("Account number required.")
            return
        if acc_no in self.accounts:
            print("Account number exists.")
            return
        pin = input("Set a 4-digit PIN: ").strip()
        if len(pin) < 4:
            print("PIN must be at least 4 digits.")
            return
        if insert_account_to_db(self._conn, acc_no, pin):
            self.accounts[acc_no] = SavingsAccount(acc_no, hash_pin(pin), 0.0, self._conn)
            print("Account created. Initial balance: ₹0.")
        else:
            print("Failed to create account.")

    def authenticate_user(self) -> bool:
        acc_no = input("Enter Account Number: ").strip()
        pin = input("Enter PIN: ").strip()
        account = self.accounts.get(acc_no)
        if account and account._check_pin(pin):
            self.current_account = account
            print("Login successful.")
            return True
        print("Invalid account number or PIN.")
        return False

    def show_menu(self) -> None:
        print("1. Balance Inquiry")
        print("2. Cash Withdrawal")
        print("3. Cash Deposit")
        print("4. Transaction History (session)")
        print("5. Change PIN")
        print("6. Logout")

    def handle_choice(self, choice: str) -> bool:
        if choice == "1":
            bal = self.current_account.get_balance()
            print(f"Balance: ₹{bal:.2f}")
        elif choice == "2":
            try:
                amt = float(input("Enter withdrawal amount: ₹"))
            except ValueError:
                print("Invalid amount.")
                return True
            if self.current_account.withdraw(amt):
                print("Withdrawal successful.")
            else:
                print("Insufficient balance or invalid amount.")
        elif choice == "3":
            try:
                amt = float(input("Enter deposit amount: ₹"))
            except ValueError:
                print("Invalid amount.")
                return True
            if self.current_account.deposit(amt):
                print("Deposit successful.")
            else:
                print("Amount must be > 0.")
        elif choice == "4":
            txns = self.current_account.get_transactions()
            if not txns:
                print("No transactions this session.")
            else:
                for t in txns:
                    print(t)
        elif choice == "5":
            old_pin = input("Enter current PIN: ").strip()
            new_pin = input("Enter new PIN (min 4 digits): ").strip()
            if self.current_account.change_pin(old_pin, new_pin):
                print("PIN changed successfully.")
            else:
                print("PIN change failed.")
        elif choice == "6":
            self.current_account = None
            return False
        else:
            print("Invalid choice.")
        return True

    def run(self) -> None:
        while True:
            print("\nMain Menu")
            print("1. Login")
            print("2. Create New Account")
            print("3. Exit")
            opt = input("Choose (1-3): ").strip()
            if opt == "1":
                if self.authenticate_user():
                    session_active = True
                    while session_active:
                        self.show_menu()
                        session_active = self.handle_choice(input("Enter choice: ").strip())
            elif opt == "2":
                self.create_account()
            elif opt == "3":
                break
            else:
                print("Invalid option.")


def main() -> None:
    conn = sqlite3.connect(DB_FILE)
    try:
        atm = ATM(conn)
        atm.run()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
