class Tracker:
    def __init__(self, name, month, budget):
        self.name = name
        self.month = month
        self.budget = float(budget)
        self.expenses = []

    def add_expense(self, expense):
        self.expenses.append(expense)

    def get_total_spent(self):
        total = 0

        for expense in self.expenses:
            total += expense.amount

        return total

    def get_remaining(self):
        return self.budget - self.get_total_spent()

    def is_over_budget(self):
        return self.get_total_spent() > self.budget