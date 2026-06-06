def convert_time_unit(seconds: int) -> str:
    """Convert seconds to a human-readable time format."""
    if seconds < 60:
        return f"{seconds} seconds"
    elif seconds < 60**2:  # 3600
        minutes = seconds / 60
        return f"{round(minutes, 3)} minutes"
    elif seconds < 60**2 * 24:  # 86400
        hours = seconds / (60**2)
        return f"{round(hours, 3)} hours"
    elif seconds < 60**2 * 24 * 30:  # 2,592,000 (30 days)
        days = seconds / (60**2 * 24)
        return f"{round(days, 3)} days"
    elif seconds < 60**2 * 24 * 365:  # 31,536,000 (365 days)
        months = seconds / (60**2 * 24 * 30)
        return f"{round(months, 3)} months"
    elif seconds < 60**2 * 24 * 365 * 10:  # 315,360,000 (10 years)
        years = seconds / (60**2 * 24 * 365)
        return f"{round(years, 3)} years"
    elif seconds < 60**2 * 24 * 365 * 100:  # 3,153,600,000 (100 years)
        decades = seconds / (60**2 * 24 * 365 * 10)
        return f"{round(decades, 3)} decades"
    else:
        centuries = seconds / (60**2 * 24 * 365 * 100)  # 100 years
        return f"{round(centuries, 3)} centuries"
