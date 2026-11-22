from app import check_booking, check_temperature, create_ticket


def test_booking_overlap():
    assert check_booking(9, 11, 10, 12) == True


def test_booking_no_overlap():
    assert check_booking(9, 10, 10, 12) == False


def test_temperature_alert():
    assert check_temperature(29) == True


def test_temperature_no_alert():
    assert check_temperature(28) == False


def test_create_ticket():
    ticket = create_ticket("Broken projector")
    assert ticket["status"] == "New"