import math

MAX_DESCRIPTION_LENGTH = 40
MAX_AMOUNT = 10_000_000


class ValidationError(ValueError):

    def __init__(self, message, field=None):
        super().__init__(message)
        self.field = field


def parse_money(text, field="amount"):
  
    cleaned = str(text).strip().replace(",", "").replace(" ", "")
    label = field.capitalize()

    if not cleaned:
        raise ValidationError(f"Please enter the {field}.", field)

    try:
        value = float(cleaned)
    except ValueError:
        raise ValidationError(f"{label} must be a number.", field) from None

    if math.isnan(value) or math.isinf(value):
        raise ValidationError(f"{label} must be a real number.", field)
    if value <= 0:
        raise ValidationError(f"{label} must be greater than zero.", field)
    if value > MAX_AMOUNT:
        raise ValidationError(f"{label} is too large (max {MAX_AMOUNT:,}).", field)

    return round(value, 2)


def validate_category(category, allowed):
    category = str(category).strip()
    if category not in allowed:
        raise ValidationError("Please choose a category from the list.", "category")
    return category


def validate_description(text):
    text = " ".join(str(text).split())
    if len(text) > MAX_DESCRIPTION_LENGTH:
        raise ValidationError(
            f"Description is too long (max {MAX_DESCRIPTION_LENGTH} characters).",
            "description",
        )
    return text