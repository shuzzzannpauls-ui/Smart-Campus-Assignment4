import sqlite3

DB = "q6_demo.db"

# Example campus policies (planning assumptions)
POLICIES = {
    "Campus-A": {"max_duration": 180, "threshold": 28.0},
    "Campus-B": {"max_duration": 120, "threshold": 26.0}
}

conn = sqlite3.connect(DB)

# Original database structure
conn.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campus TEXT,
    start_min INTEGER,
    end_min INTEGER,
    status TEXT
)
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    status TEXT
)
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS audit_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT
)
""")

# Add sample old records only when the tables are empty
if conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0] == 0:
    conn.execute(
        "INSERT INTO bookings VALUES (1, 'Campus-A', 100, 160, 'Approved')"
    )

if conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 0:
    conn.execute(
        "INSERT INTO tickets VALUES (1, 'Old projector fault', 'Resolved')"
    )

if conn.execute("SELECT COUNT(*) FROM audit_history").fetchone()[0] == 0:
    conn.execute(
        "INSERT INTO audit_history VALUES (1, 'Original booking created')"
    )

conn.commit()

# Database migration
columns = [
    row[1] for row in conn.execute("PRAGMA table_info(bookings)")
]

if "campus_code" not in columns:
    conn.execute("ALTER TABLE bookings ADD COLUMN campus_code TEXT")

if "policy_version" not in columns:
    conn.execute("""
    ALTER TABLE bookings
    ADD COLUMN policy_version TEXT DEFAULT 'legacy-v1'
    """)

conn.execute("""
UPDATE bookings
SET campus_code = campus
WHERE campus_code IS NULL
""")

conn.commit()
print("PASS: Database migration completed")

# Check preservation of old records
assert conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0] >= 1
assert conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] >= 1
assert conn.execute("SELECT COUNT(*) FROM audit_history").fetchone()[0] >= 1

print("PASS: Old bookings, tickets and audit history preserved")


# Revised booking API version 2
def create_booking_v2(campus, start, end):
    if campus not in POLICIES:
        raise ValueError("Unknown campus")

    duration = end - start

    if duration <= 0:
        raise ValueError("Invalid booking duration")

    maximum = POLICIES[campus]["max_duration"]

    if duration > maximum:
        raise ValueError("Booking exceeds campus policy")

    cursor = conn.execute("""
    INSERT INTO bookings
    (campus, start_min, end_min, status, campus_code, policy_version)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (campus, start, end, "Pending", campus, "campus-policy-v2"))

    conn.commit()
    return cursor.lastrowid


# Compatibility adapter for an older API client
def create_booking_v1(start, end):
    return create_booking_v2("Campus-A", start, end)


# Campus-specific booking boundary checks
create_booking_v2("Campus-A", 200, 380)
print("PASS: Campus-A 180-minute booking accepted")

try:
    create_booking_v2("Campus-A", 400, 581)
    raise AssertionError("Over-limit booking was accepted")
except ValueError:
    print("PASS: Campus-A 181-minute booking rejected")

create_booking_v2("Campus-B", 600, 720)
print("PASS: Campus-B 120-minute booking accepted")

try:
    create_booking_v2("Campus-B", 800, 921)
    raise AssertionError("Over-limit booking was accepted")
except ValueError:
    print("PASS: Campus-B 121-minute booking rejected")


# Campus-specific sensor threshold checks
def sensor_alert(campus, temperature):
    return temperature > POLICIES[campus]["threshold"]


assert sensor_alert("Campus-A", 28.0) is False
assert sensor_alert("Campus-A", 28.1) is True
assert sensor_alert("Campus-B", 26.0) is False
assert sensor_alert("Campus-B", 26.1) is True

print("PASS: Campus-specific sensor thresholds verified")


# Old API compatibility check
old_api_booking = create_booking_v1(900, 960)
assert old_api_booking is not None

print("PASS: Older API request remains supported")


# Durable synchronization queue
conn.execute("""
CREATE TABLE IF NOT EXISTS sync_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_key TEXT UNIQUE,
    payload TEXT,
    status TEXT DEFAULT 'Pending'
)
""")

conn.execute("""
INSERT OR IGNORE INTO sync_outbox
(event_key, payload, status)
VALUES ('EVENT-Q6-001', 'Calendar booking update', 'Pending')
""")

conn.commit()


def synchronize(event_key, service_available):
    status = "Synced" if service_available else "Pending"

    conn.execute("""
    UPDATE sync_outbox
    SET status = ?
    WHERE event_key = ?
    """, (status, event_key))

    conn.commit()
    return status


# External service unavailable
result = synchronize("EVENT-Q6-001", False)
assert result == "Pending"

print("PASS: Unavailable external service keeps request Pending")

# Retry after service becomes available
result = synchronize("EVENT-Q6-001", True)
assert result == "Synced"

print("PASS: Synchronization retry completed")

# Duplicate request protection
conn.execute("""
INSERT OR IGNORE INTO sync_outbox
(event_key, payload)
VALUES ('EVENT-Q6-001', 'Calendar booking update')
""")

conn.commit()

count = conn.execute("""
SELECT COUNT(*) FROM sync_outbox
WHERE event_key = 'EVENT-Q6-001'
""").fetchone()[0]

assert count == 1
print("PASS: Duplicate synchronization request prevented")

conn.close()

print("Q6 DEMONSTRATION COMPLETED")