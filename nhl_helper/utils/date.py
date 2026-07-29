from datetime import datetime, date, timedelta


def get_date_of_interest()->datetime.date:
    """
    The date of interest by default is the current date minus after 12PM or yesterday before 12PM.
    """

    if datetime.now().hour < 12:
        return date.today() - timedelta(days=1)
    else:
        return date.today()