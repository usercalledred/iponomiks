class Expense:
    def __init__(self, category, description, amount):
        self.category = category
        self.description = description
        self.amount = float(amount)

    def get_details(self):
        return {
            "category": self.category,
            "description": self.description,
            "amount": self.amount
        }