CURRENCY = "PHP "

def format_money(amount):
    sign = "-" if amount < 0 else ""
    return f"{sign}{CURRENCY}{abs(amount):,.2f}"

class BudgetStatus:
    SAFE = "safe"        # green
    WARNING = "warning"  # orange
    OVER = "over"        # red

class Budget:

    WARNING_THRESHOLD = 0.75  

    def __init__(self, total):
        self.total = float(total)

    def remaining(self, spent):
        return round(self.total - spent, 2)

    def overspent_by(self, spent):
        return max(0.0, round(spent - self.total, 2))

    def percent_used(self, spent):
        if self.total <= 0:
            return 100.0 if spent > 0 else 0.0
        return spent / self.total * 100

    def bar_fraction(self, spent):
        return max(0.0, min(1.0, self.percent_used(spent) / 100))

    def status(self, spent):
        if spent > self.total:
            return BudgetStatus.OVER
        if spent >= self.total * self.WARNING_THRESHOLD:
            return BudgetStatus.WARNING
        return BudgetStatus.SAFE

    def message(self, spent):
        status = self.status(spent)
        if status == BudgetStatus.OVER:
            return f"Over budget by {format_money(self.overspent_by(spent))}! Time to cut back."
        if status == BudgetStatus.WARNING:
            return (f"Careful! {self.percent_used(spent):.0f}% used. "
                    f"Only {format_money(self.remaining(spent))} left.")
        return f"On track. {format_money(self.remaining(spent))} still available."