import sqlite3
import os
import time

DB = "q5_demo.db"
BACKUP = "q5_demo_backup.db"

# Start with a clean demonstration database
for file in [DB, BACKUP]:
    if os.path.exists(file):
        os.remove(file)

conn = sqlite3.connect(DB)

conn.execute("""
CREATE TABLE bookings (
    id INTEGER PRIMARY KEY,
    facility TEXT,
    restricted INTEGER,
    status TEXT
)
""")

conn.execute("""
CREATE TABLE tickets (
    id INTEGER PRIMARY KEY,
    issue TEXT,
    event_id TEXT UNIQUE,
    sync_status TEXT DEFAULT 'Pending'
)
""")

conn.commit()


def create_booking(facility, restricted):
    cursor = conn.execute(
        "INSERT INTO bookings (facility, restricted, status) VALUES (?, ?, ?)",
        (facility, restricted, "Pending")
    )
    conn.commit()
    return cursor.lastrowid


def view_booking(booking_id, role):
    booking = conn.execute(
        "SELECT * FROM bookings WHERE id = ?", (booking_id,)
    ).fetchone()

    if booking[2] and role not in ["admin", "facility_manager", "approver"]:
        raise PermissionError("Access denied")

    return booking


def approve_booking(booking_id, authenticated_role, claimed_role):
    if authenticated_role != claimed_role:
        raise PermissionError("Role impersonation rejected")

    if authenticated_role not in ["admin", "approver"]:
        raise PermissionError("Approval not permitted")

    conn.execute(
        "UPDATE bookings SET status = 'Approved' WHERE id = ?",
        (booking_id,)
    )
    conn.commit()


def create_ticket(issue, event_id):
    existing = conn.execute(
        "SELECT id FROM tickets WHERE event_id = ?", (event_id,)
    ).fetchone()

    if existing:
        return existing[0]

    cursor = conn.execute(
        "INSERT INTO tickets (issue, event_id) VALUES (?, ?)",
        (issue, event_id)
    )
    conn.commit()
    return cursor.lastrowid


def synchronize_ticket(ticket_id, available):
    status = "Synced" if available else "Pending"

    conn.execute(
        "UPDATE tickets SET sync_status = ? WHERE id = ?",
        (status, ticket_id)
    )
    conn.commit()
    return status


# 1. Restricted booking access test
booking_id = create_booking("Restricted Laboratory", 1)

try:
    view_booking(booking_id, "student")
    raise AssertionError("Student access was not blocked")
except PermissionError:
    print("PASS: Student restricted access rejected")

# 2. Role impersonation test
try:
    approve_booking(booking_id, "student", "approver")
    raise AssertionError("Role impersonation was not blocked")
except PermissionError:
    print("PASS: Role impersonation rejected")

# 3. Duplicate submission test
ticket_id = create_ticket("Sensor alert", "EVENT001")
duplicate_id = create_ticket("Sensor alert", "EVENT001")

assert ticket_id == duplicate_id
count = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
assert count == 1

print("PASS: Duplicate submission created only one ticket")

# 4. External dependency failure test
status = synchronize_ticket(ticket_id, False)
assert status == "Pending"

print("PASS: Unavailable dependency keeps ticket Pending")

# 5. Retry after dependency becomes available
status = synchronize_ticket(ticket_id, True)
assert status == "Synced"

print("PASS: Ticket synchronization retry succeeded")

# 6. Persistence test
conn.close()
conn = sqlite3.connect(DB)

saved = conn.execute(
    "SELECT issue FROM tickets WHERE id = ?", (ticket_id,)
).fetchone()

assert saved is not None
print("PASS: Ticket data remains after database reopening")

# 7. Bounded local database experiment (100 sequential requests)
times = []

for i in range(100):
    start = time.perf_counter()
    create_ticket("Load test ticket", f"LOAD{i}")
    times.append((time.perf_counter() - start) * 1000)

ordered = sorted(times)
p50 = ordered[49]
p95 = ordered[94]

print("LOAD EXPERIMENT")
print("Requests:", len(times))
print("Errors: 0")
print("Average time:", round(sum(times) / len(times), 3), "ms")
print("P50:", round(p50, 3), "ms")
print("P95:", round(p95, 3), "ms")

# 8. Backup and recovery test
backup_conn = sqlite3.connect(BACKUP)
conn.backup(backup_conn)
backup_conn.close()

# Simulate data loss during a failed release
conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
conn.commit()
conn.close()

# Restore the previous database
os.replace(BACKUP, DB)

conn = sqlite3.connect(DB)

restored = conn.execute(
    "SELECT issue FROM tickets WHERE id = ?", (ticket_id,)
).fetchone()

assert restored is not None

print("PASS: Backup recovery preserved ticket data")

conn.close()

print("Q5 DEMONSTRATION COMPLETED")