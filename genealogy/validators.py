# apps/genealogy/validators.py
import re
from django.core.exceptions import ValidationError


def validate_individual_name(first_name: str, middle_name: str, last_name: str):
    """
    Validates individual name constraints per SRS 4.2:
      1. At least one of First, Middle, or Last Name is mandatory.
      2. Combined alphabetic count across First, Middle, Last must be >= 4.
      3. Permitted characters: English letters (A-Za-z) and apostrophe (').
      4. First and Last Name: strictly no spaces.
      5. Middle Name: single spaces allowed between words; no leading/trailing/consecutive spaces.
    """
    fn = (first_name or '').strip()
    mn = middle_name or ''  # Do not strip yet to verify leading/trailing whitespace
    ln = (last_name or '').strip()

    if not fn and not mn.strip() and not ln:
        raise ValidationError("At least one of First Name, Middle Name, or Last Name is mandatory.")

    # Combined alphabetic count
    combined = f"{fn}{mn}{ln}"
    alpha_count = sum(1 for c in combined if c.isalpha())
    if alpha_count < 4:
        raise ValidationError(
            f"The combined name must contain at least 4 alphabetic characters (currently has {alpha_count})."
        )

    # First Name validation
    if fn:
        if not re.fullmatch(r"^[A-Za-z']+$", fn):
            raise ValidationError("First Name can only contain letters and apostrophes, and cannot contain spaces.")

    # Last Name validation
    if ln:
        if not re.fullmatch(r"^[A-Za-z']+$", ln):
            raise ValidationError("Last Name can only contain letters and apostrophes, and cannot contain spaces.")

    # Middle Name validation: single spaces between words only; no leading/trailing/multiple spaces
    if mn:
        if mn.startswith(' ') or mn.endswith(' '):
            raise ValidationError("Middle Name cannot contain leading or trailing spaces.")
        if '  ' in mn:
            raise ValidationError("Middle Name can only contain single spaces between words.")
        if not re.fullmatch(r"^[A-Za-z']+(?: [A-Za-z']+)*$", mn):
            raise ValidationError(
                "Middle Name can only contain letters and apostrophes, with single spaces between words."
            )