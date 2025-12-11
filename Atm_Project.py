"""
ATM MACHINE SIMULATION SYSTEM (SQLite, PIN hashed)
- Create accounts with PIN/password
- Deposit updates balance in SQLite immediately
- Encapsulation (private pin & balance) + Inheritance
- Session transaction history (in-memory)
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import hashlib
import os

DB_FILE = "atm_accounts.db"


def hash_pin(pin: str) -> str:
    """Return SHA-256 hex digest of the PIN (simple hashing)."""
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


# ---------------- Transaction ----------------
class Transaction:
    def __init__(self, txn_type: str, amount: float, balance_after: float):
        self.txn_type = txn_type
        self.amount = amount
        self.balance_after = balance_after
        self.timestamp = datetime.now()

    def __str__(self) -> str:
        return (
            f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] "
            f"{self.txn_type:<10} | Amount: ₹{self.amount:.2f} | Balance: ₹{self.balance_after:.2f}"
        )


# ---------------- Account (encapsulation) ----------------
class Account:
    """
    Account object linked to SQLite row.
    __pin_hash and __balance are private; changes persist via DB connection.
    """

    def __init__(self, account_number: str, pin_hash: str, balance: float, conn: sqlite3.Connection):
        self.account_number = account_number
        self.__pin_hash = pin_hash         # private (hashed)
        self.__balance = float(balance)    # private
        self._transactions: List[Transaction] = []
        self._conn = conn                  # DB connection for persistence

    # Encapsulated PIN check (compare hashed)
    def _check_pin(self, pin: str) -> bool:
        return self.__pin_hash == hash_pin(pin)

    # Persist balance to DB after change
    def _persist_balance(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE accounts SET balance = ? WHERE account_number = ?",
            (self.__balance, self.account_number),
        )
        self._conn.commit()

    # Persist pin hash to DB (if changed)
    def _persist_pin(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE accounts SET pin = ? WHERE account_number = ?",
            (self.__pin_hash, self.account_number),
        )
        self._conn.commit()

    # Public operations
    def get_balance(self) -> float:
        self._transactions.append(Transaction("INQUIRY", 0.0, self.__balance))
        return self.__balance

    def deposit(self, amount: float) -> bool:
        if amount <= 0:
            return False
        self.__balance += amount
        self._persist_balance()                    # **update DB**
        self._transactions.append(Transaction("DEPOSIT", amount, self.__balance))
        return True

    def withdraw(self, amount: float) -> bool:
        if amount <= 0 or amount > self.__balance:
            return False
        self.__balance -= amount
        self._persist_balance()                    # **update DB**
        self._transactions.append(Transaction("WITHDRAW", amount, self.__balance))
        return True

    def change_pin(self, old_pin: str, new_pin: str) -> bool:
        if not self._check_pin(old_pin):
            return False
        if len(new_pin) < 4:
            return False
        self.__pin_hash = hash_pin(new_pin)
        self._persist_pin()
        return True

    def get_transactions(self) -> List[Transaction]:
        return self._transactions.copy()


class SavingsAccount(Account):
    """Inheritance placeholder - same behavior for now."""
    pass


# ---------------- DB helpers ----------------
def init_db(conn: sqlite3.Connection) -> None:
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
    # Insert sample accounts (pin stored hashed)
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
    cur = conn.cursor()
    cur.execute("SELECT account_number, pin, balance FROM accounts")
    rows = cur.fetchall()
    accounts: Dict[str, Account] = {}
    for acc_no, pin_hash, balance in rows:
        accounts[acc_no] = SavingsAccount(acc_no, pin_hash, balance, conn)
    return accounts


def insert_account_to_db(conn: sqlite3.Connection, account_number: str, pin: str) -> bool:
    """Insert new account with hashed pin and 0 balance. Return False if account exists."""
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


# ---------------- ATM class ----------------
class ATM:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        init_db(self._conn)
        self.accounts = load_all_accounts(self._conn)
        self.current_account: Optional[Account] = None

    def create_account(self):
        print("\n===== CREATE NEW ACCOUNT =====")
        acc_no = input("Enter NEW Account Number: ").strip()
        if not acc_no:
            print("Account number cannot be empty.\n")
            return

        if acc_no in self.accounts:
            print("Account number already exists. Try a different number.\n")
            return

        pin = input("Set a 4-digit PIN/password: ").strip()
        if len(pin) < 4:
            print("PIN must be at least 4 digits.\n")
            return

        if insert_account_to_db(self._conn, acc_no, pin):
            # add to in-memory map
            self.accounts[acc_no] = SavingsAccount(acc_no, hash_pin(pin), 0.0, self._conn)
            print("\nAccount created successfully! Initial balance: ₹0\n")
        else:
            print("\nFailed to create account (maybe it already exists).\n")

    def authenticate_user(self) -> bool:
        print("\n===== LOGIN TO ATM =====")
        acc_no = input("Enter Account Number: ").strip()
        pin = input("Enter PIN/password: ").strip()

        account = self.accounts.get(acc_no)
        if account and account._check_pin(pin):
            self.current_account = account
            print("\nLogin successful!\n")
            return True

        print("\nInvalid account number or PIN.\n")
        return False

    def show_menu(self):
        print("========= ATM MENU =========")
        print("1. Balance Inquiry")
        print("2. Cash Withdrawal")
        print("3. Cash Deposit")
        print("4. Transaction History (session)")
        print("5. Change PIN")
        print("6. Logout")
        print("============================")

    def handle_choice(self, choice: str) -> bool:
        if choice == "1":
            bal = self.current_account.get_balance()
            print(f"\nYour balance: ₹{bal:.2f}\n")
        elif choice == "2":
            try:
                amt = float(input("Enter withdrawal amount: ₹"))
            except ValueError:
                print("\nInvalid amount.\n")
                return True
            if self.current_account.withdraw(amt):
                print("\nWithdrawal successful — DB updated.\n")
            else:
                print("\nFailed. Insufficient balance or invalid amount.\n")
        elif choice == "3":
            try:
                amt = float(input("Enter deposit amount: ₹"))
            except ValueError:
                print("\nInvalid amount.\n")
                return True
            if self.current_account.deposit(amt):
                print("\nDeposit successful — DB updated.\n")
            else:
                print("\nFailed. Enter amount > 0.\n")
        elif choice == "4":
            txns = self.current_account.get_transactions()
            print("\n------ TRANSACTION HISTORY (this session) ------")
            if not txns:
                print("No transactions in this session.")
            else:
                for t in txns:
                    print(t)
            print("------------------------------------------------\n")
        elif choice == "5":
            old_pin = input("Enter current PIN/password: ").strip()
            new_pin = input("Enter new PIN/password (min 4 digits): ").strip()
            if self.current_account.change_pin(old_pin, new_pin):
                print("\nPIN changed successfully — DB updated.\n")
            else:
                print("\nFailed to change PIN. Check current PIN and new PIN validity.\n")
        elif choice == "6":
            print("\nLogging out...\n")
            self.current_account = None
            return False
        else:
            print("\nInvalid choice. Try again.\n")
        return True

    def run(self):
        while True:
            print("\n===== PYTHON ATM (SQLite) =====")
            print("1. Login")
            print("2. Create New Account")
            print("3. Exit")
            print("================================")
            opt = input("Choose (1-3): ").strip()
            if opt == "1":
                if self.authenticate_user():
                    session = True
                    while session:
                        self.show_menu()
                        session = self.handle_choice(input("Enter choice: ").strip())
            elif opt == "2":
                self.create_account()
            elif opt == "3":
                print("\nThank you for using ATM. Goodbye!\n")
                break
            else:
                print("\nInvalid option. Try again.\n")


# ----------------- Main -----------------
def main():
    conn = sqlite3.connect(DB_FILE)
    try:
        atm = ATM(conn)
        atm.run()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
