def check_booking(start1, end1, start2, end2):
    return start1 < end2 and start2 < end1


def check_temperature(temperature):
    return temperature > 28.00


def create_ticket(issue):
    return {
        "issue": issue,
        "status": "New"
    }
