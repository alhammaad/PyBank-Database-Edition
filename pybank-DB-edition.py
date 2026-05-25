import sqlite3
from typing import Optional

# ── Custom Exception ───────────────────────────────────────────────────────────

class InsufficientFundsError(Exception):
    def __init__(self, balance: float, amount: float):
        self.balance = balance
        self.amount = amount
        super().__init__(f"Cannot withdraw ₹{amount:.2f}. Current balance: ₹{balance:.2f}")


# ── Database Manager Class ─────────────────────────────────────────────────────

class BankDatabase:
    """Handles all direct SQL database interactions."""
    def __init__(self, db_name: str = "pybank.db"):
        self.db_name = db_name
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_name)

    def _init_db(self):
        """Creates tables if they don't already exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Enable Foreign Key support in SQLite
            cursor.execute("PRAGMA foreign_keys = ON;")
            
            # Accounts Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    owner TEXT PRIMARY KEY,
                    balance REAL NOT NULL DEFAULT 0.0
                );
            """)
            
            # Transactions Table (Linked to accounts)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner TEXT NOT NULL,
                    type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    balance_after REAL NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (owner) REFERENCES accounts(owner) ON DELETE CASCADE
                );
            """)
            conn.commit()


# ── BankAccount Class ─────────────────────────────────────────────────────────

class BankAccount:
    def __init__(self, owner: str, db_manager: BankDatabase):
        self.owner = owner
        self.db = db_manager
        
        # Ensure account exists in DB or load existing one
        self._load_or_create()

    def _load_or_create(self):
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM accounts WHERE owner = ?", (self.owner,))
            row = cursor.fetchone()
            
            if row is None:
                # Create default account with initial ₹1000 balance if new
                cursor.execute("INSERT INTO accounts (owner, balance) VALUES (?, ?)", (self.owner, 1000.0))
                conn.commit()
                print(f"  ✔ New database record created for {self.owner} with ₹1000.00")
            else:
                print(f"  ✔ Loaded existing record for {self.owner} from database.")

    @property
    def balance(self) -> float:
        """Always pull the live balance directly from the database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM accounts WHERE owner = ?", (self.owner,))
            return cursor.fetchone()[0]

    # ── Core Operations ────────────────────────────────────────────────────────

    def deposit(self, amount: float):
        if amount <= 0:
            raise ValueError("Deposit amount must be positive.")
        
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Update the balance
            cursor.execute("UPDATE accounts SET balance = balance + ? WHERE owner = ?", (amount, self.owner))
            # 2. Log the transaction
            new_balance = self.balance
            cursor.execute("""
                INSERT INTO transactions (owner, type, amount, balance_after) 
                VALUES (?, 'deposit', ?, ?)
            """, (self.owner, amount, new_balance))
            conn.commit()
            print(f"  ✔ Deposited ₹{amount:.2f}. Live balance: ₹{new_balance:.2f}")

    def withdraw(self, amount: float):
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive.")
        
        current_balance = self.balance
        if amount > current_balance:
            raise InsufficientFundsError(current_balance, amount)
            
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Update the balance
            cursor.execute("UPDATE accounts SET balance = balance - ? WHERE owner = ?", (amount, self.owner))
            # 2. Log the transaction
            new_balance = current_balance - amount
            cursor.execute("""
                INSERT INTO transactions (owner, type, amount, balance_after) 
                VALUES (?, 'withdrawal', ?, ?)
            """, (self.owner, amount, new_balance))
            conn.commit()
            print(f"  ✔ Withdrew ₹{amount:.2f}. Live balance: ₹{new_balance:.2f}")

    # ── True Database Transaction Transfer ───────────────────────────────────

    def transfer(self, amount: float, target_owner: str):
        """Executes a database transaction. Automatically rolls back on error."""
        if amount <= 0:
            raise ValueError("Transfer amount must be positive.")
            
        conn = self.db._get_connection()
        try:
            cursor = conn.cursor()
            # Turn off auto-commit to manage transaction block manually
            conn.execute("BEGIN TRANSACTION;")
            
            # 1. Check sender balance
            cursor.execute("SELECT balance FROM accounts WHERE owner = ?", (self.owner,))
            sender_balance = cursor.fetchone()[0]
            if amount > sender_balance:
                raise InsufficientFundsError(sender_balance, amount)
                
            # 2. Verify target exists
            cursor.execute("SELECT balance FROM accounts WHERE owner = ?", (target_owner,))
            target_row = cursor.fetchone()
            if target_row is None:
                raise ValueError(f"Target account '{target_owner}' does not exist.")
            
            target_balance = target_row[0]

            # 3. Apply updates
            cursor.execute("UPDATE accounts SET balance = balance - ? WHERE owner = ?", (amount, self.owner))
            cursor.execute("UPDATE accounts SET balance = balance + ? WHERE owner = ?", (amount, target_owner))
            
            # 4. Log transaction entries
            cursor.execute("INSERT INTO transactions (owner, type, amount, balance_after) VALUES (?, 'transfer_out', ?, ?)", 
                           (self.owner, amount, sender_balance - amount))
            cursor.execute("INSERT INTO transactions (owner, type, amount, balance_after) VALUES (?, 'transfer_in', ?, ?)", 
                           (target_owner, amount, target_balance + amount))
            
            # If everything succeeded, save changes to disk permanently
            conn.commit()
            print(f"  ✔ Transferred ₹{amount:.2f} safely to {target_owner}.")
            
        except Exception as e:
            # Crucial: If ANYTHING fails inside the try block, reverse all operations!
            conn.rollback()
            print(f"  ✘ Transaction failed! All changes safely rolled back. Reason: {e}")
            raise
        finally:
            conn.close()

    # ── History Queries ───────────────────────────────────────────────────────

    def print_history(self):
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT type, amount, balance_after, timestamp 
                FROM transactions 
                WHERE owner = ? 
                ORDER BY timestamp ASC
            """, (self.owner,))
            rows = cursor.fetchall()
            
            if not rows:
                print("  No transactions found in database.")
                return
                
            print(f"\n  {'Type':<14} {'Amount':>10} {'Balance After':>15} {'Timestamp':>22}")
            print("  " + "-" * 65)
            for row in rows:
                print(f"  {row[0]:<14} ₹{row[1]:>8.2f} ₹{row[2]:>13.2f}  {row[3]}")
            print()


# ── Interactive App ────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("      Welcome to PyBank (Database Edition)")
    print("=" * 50)

    db_manager = BankDatabase("pybank.db")
    name = input("Enter account owner name: ").strip() or "User"
    account = BankAccount(name, db_manager)

    while True:
        print(f"\n  [{account.owner}'s Session] Options: deposit | withdraw | transfer | history | switch | quit")
        choice = input("  > ").strip().lower()

        try:
            match choice:
                case "deposit":
                    amt = float(input("  Amount to deposit: ₹"))
                    account.deposit(amt)
                case "withdraw":
                    amt = float(input("  Amount to withdraw: ₹"))
                    account.withdraw(amt)
                case "transfer":
                    target = input("  Enter recipient's name: ").strip()
                    amt = float(input(f"  Amount to transfer to {target}: ₹"))
                    account.transfer(amt, target)
                case "history":
                    account.print_history()
                case "switch":
                    name = input("  Enter account name to switch to: ").strip() or "User"
                    account = BankAccount(name, db_manager)
                case "quit" | "exit" | "q":
                    print(f"\n  Goodbye! Final balance: ₹{account.balance:.2f}")
                    break
                case _:
                    print("  ✘ Unknown command.")
        except ValueError as e:
            print(f"  ✘ Input Error: {e}")
        except InsufficientFundsError as e:
            print(f"  ✘ Balance Error: {e}")
        except Exception as e:
            print(f"  ✘ System Error: {e}")

if __name__ == "__main__":
    main()