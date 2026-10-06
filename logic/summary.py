from dataclasses import dataclass, field

from logic.budget import format_money  


@dataclass
class Summary:
    budget: float
    spent: float
    remaining: float
    percent_used: float
    status: str
    message: str
    count: int
    average: float
    highest: object           
    top_category: str        
    by_category: list = field(default_factory=list)  


def build_summary(budget, log):
    spent = log.total()
    items = log.items

    totals = {}
    for item in items:
        totals[item.category] = totals.get(item.category, 0.0) + item.amount

    by_category = sorted(
        (
            (category, round(total, 2), (total / spent * 100) if spent else 0.0)
            for category, total in totals.items()
        ),
        key=lambda row: (-row[1], row[0]),
    )

    return Summary(
        budget=budget.total,
        spent=spent,
        remaining=budget.remaining(spent),
        percent_used=budget.percent_used(spent),
        status=budget.status(spent),
        message=budget.message(spent),
        count=len(items),
        average=round(spent / len(items), 2) if items else 0.0,
        highest=max(items, key=lambda i: i.amount) if items else None,
        top_category=by_category[0][0] if by_category else None,
        by_category=by_category,
    )