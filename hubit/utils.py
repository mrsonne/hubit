def is_digit(s: str) -> bool:
    """Alternative to s.isdigit() that handles negative integers

    Args:
        s (str): A string

    Returns:
        bool: Flag indicating if the input string is a signed int
    """
    try:
        int(s)
        return True
    except ValueError:
        return False
