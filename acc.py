import json


# ── Custom Exception ───────────────────────────────────────────────────────────

class InsufficientFundsError(Exception):
    def __init__(self, balance, amount):
        self.balance = balance
        self.amount = amount
        super().__init__(
            f"Cannot withdraw ₹{amount:.2f}. Current balance: ₹{balance:.2f}"
        )


# ── BankAccount Class ─────────────────────────────────────────────────────────

class BankAccount:
    def __init__(self, owner: str, initial_balance: float = 0.0):
        if initial_balance < 0:
            raise ValueError("Initial balance cannot be negative.")
        self.owner = owner
        self.balance = initial_balance
        self.transactions = []

    # ── Core Methods ────────────────────────────────────────────────────────

    def deposit(self, amount: float):
        if amount <= 0:
            raise ValueError("Deposit amount must be positive.")
        self.balance += amount
        self.transactions.append({
            "type": "deposit",
            "amount": amount,
            "balance_after": self.balance
        })
        print(f"  ✔ Deposited ₹{amount:.2f}. New balance: ₹{self.balance:.2f}")

    def withdraw(self, amount: float):
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive.")
        if amount > self.balance:
            raise InsufficientFundsError(self.balance, amount)
        self.balance -= amount
        self.transactions.append({
            "type": "withdrawal",
            "amount": amount,
            "balance_after": self.balance
        })
        print(f"  ✔ Withdrew ₹{amount:.2f}. New balance: ₹{self.balance:.2f}")

    # ── Bonus: Transfer with Rollback ────────────────────────────────────────

    def transfer(self, amount: float, target: "BankAccount"):
        """Transfer amount to target account. Rolls back if deposit fails."""
        self.withdraw(amount)           # may raise InsufficientFundsError
        try:
            target.deposit(amount)
        except Exception as e:
            # Rollback: undo the withdrawal
            self.balance += amount
            self.transactions.pop()
            print(f"  ✘ Transfer failed, withdrawal rolled back. Reason: {e}")
            raise
        print(f"  ✔ Transferred ₹{amount:.2f} to {target.owner}.")

    # ── Transaction History ──────────────────────────────────────────────────

    def print_history(self):
        if not self.transactions:
            print("  No transactions yet.")
            return
        print(f"\n  {'Type':<12} {'Amount':>10} {'Balance After':>15}")
        print("  " + "-" * 40)
        for t in self.transactions:
            print(f"  {t['type']:<12} ₹{t['amount']:>8.2f} ₹{t['balance_after']:>13.2f}")
        print()

    # ── File I/O ─────────────────────────────────────────────────────────────

    def save_to_file(self, filename: str):
        f = None
        try:
            f = open(filename, "w")
            data = {
                "owner": self.owner,
                "balance": self.balance,
                "transactions": self.transactions
            }
            json.dump(data, f, indent=2)
            print(f"  ✔ Account saved to '{filename}'.")
        except OSError as e:
            print(f"  ✘ Could not save file: {e}")
        finally:
            if f:
                f.close()

    @classmethod
    def load_from_file(cls, filename: str) -> "BankAccount":
        f = None
        try:
            f = open(filename, "r")
            data = json.load(f)
            acc = cls(data["owner"], data["balance"])
            acc.transactions = data["transactions"]
            print(f"  ✔ Loaded account for '{acc.owner}'.")
            return acc
        except FileNotFoundError:
            print(f"  ✘ File '{filename}' not found.")
            raise
        except (KeyError, json.JSONDecodeError) as e:
            print(f"  ✘ Invalid file format: {e}")
            raise
        finally:
            if f:
                f.close()

    def __repr__(self):
        return f"BankAccount(owner='{self.owner}', balance=₹{self.balance:.2f})"


# ── Main Interactive Loop ──────────────────────────────────────────────────────

def get_amount(prompt: str) -> float:
    """Helper to safely read a float from the user."""
    try:
        return float(input(prompt))
    except ValueError:
        print("  ✘ Please enter a valid number.")
        return None


def main():
    print("=" * 45)
    print("      Welcome to PyBank")
    print("=" * 45)

    name = input("Enter account owner name: ").strip() or "User"
    account = BankAccount(name, initial_balance=1000.0)
    print(f"  ✔ Account created for {name} with ₹1000.00\n")

    while True:
        print("\n  Options: deposit | withdraw | history | save | load | quit")
        choice = input("  > ").strip().lower()

        match choice:
            case "deposit":
                amt = get_amount("  Amount to deposit: ₹")
                if amt is not None:
                    try:
                        account.deposit(amt)
                    except ValueError as e:
                        print(f"  ✘ {e}")

            case "withdraw":
                amt = get_amount("  Amount to withdraw: ₹")
                if amt is not None:
                    try:
                        account.withdraw(amt)
                    except (ValueError, InsufficientFundsError) as e:
                        print(f"  ✘ {e}")

            case "history":
                account.print_history()

            case "save":
                fname = input("  Filename (e.g. account.json): ").strip()
                account.save_to_file(fname or "account.json")

            case "load":
                fname = input("  Filename to load: ").strip()
                try:
                    account = BankAccount.load_from_file(fname)
                except Exception:
                    print("  Keeping current account.")

            case "quit" | "exit" | "q":
                print(f"\n  Goodbye, {account.owner}! Final balance: ₹{account.balance:.2f}")
                break

            case _:
                print("  ✘ Unknown command. Try: deposit, withdraw, history, save, load, quit")


# ── Quick Demo (runs without interactive input) ────────────────────────────────

def demo():
    print("=" * 45)
    print("           DEMO RUN")
    print("=" * 45)

    acc1 = BankAccount("ali", 1000)
    acc2 = BankAccount("sohel", 500)

    print("\n--- deposits & withdrawals ---")
    acc1.deposit(500)
    acc1.withdraw(200)

    print("\n--- invalid operations ---")
    try:
        acc1.withdraw(9999)
    except InsufficientFundsError as e:
        print(f"  Caught: {e}")

    try:
        acc1.deposit(-50)
    except ValueError as e:
        print(f"  Caught: {e}")

    print("\n--- transaction history ---")
    acc1.print_history()

    print("--- save & reload ---")
    acc1.save_to_file("ali_demo.json")
    acc_loaded = BankAccount.load_from_file("ali_demo.json")
    print(f"  Loaded: {acc_loaded}")

    print("\n--- bonus: transfer ---")
    acc1.transfer(300, acc2)
    print(f"  acc1 balance: ₹{acc1.balance:.2f}")
    print(f"  acc2 balance: ₹{acc2.balance:.2f}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        demo()
    else:
        main()