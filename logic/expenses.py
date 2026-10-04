from dataclasses import dataclass

from logic.validation import (
    parse_money, validate_category, validate_description,
)

CATEGORIES = [
    "Food",
    "Transportation",
    "School Supplies",
    "Tuition & Fees",
    "Boarding / Rent",
    "Load & Internet",
    "Utilities",
    "Health",
    "Entertainment",
    "Shopping",
    "Savings",
    "Others",
]


@dataclass(frozen=True)
class ExpenseItem:
    category: str
    description: str
    amount: float


class ExpenseLog:
    """The list of expenses in one tracker."""

    def __init__(self, items=None):
        self._items = [
            ExpenseItem(category, description or "", float(amount))
            for category, description, amount in (items or [])
        ]

    def add(self, category, description, amount_text):
        """Validate the raw input and add it. Raises ValidationError."""
        item = ExpenseItem(
            validate_category(category, CATEGORIES),
            validate_description(description),
            parse_money(amount_text, "amount"),
        )
        self._items.append(item)
        return item

    def remove(self, indexes):
        for index in sorted(set(indexes), reverse=True):
            if 0 <= index < len(self._items):
                del self._items[index]

    def clear(self):
        self._items.clear()

    def total(self):
        return round(sum(item.amount for item in self._items), 2)

    def as_tuples(self):
        """(category, description, amount) rows, ready for the database."""
        return [(i.category, i.description, i.amount) for i in self._items]

    @property
    def items(self):
        return list(self._items)

    def __len__(self):
        return len(self._items)