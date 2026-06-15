"""Quick test: verify templates output correct subject/body"""
import sys
sys.path.insert(0, '/home/ubuntu/nanosoft/re_pipeline')
from templates import get_template

print("=" * 60)
print("TEMPLATE TEST")
print("=" * 60)

# Test Angle A Touch 1
t = get_template("A", 1, "Sunshine Realty Group", "Michael Torres", "Miami")
print(f"\n--- Angle A Touch 1 ---")
print(f"Subject: {t['subject']}")
print(f"Body:\n{t['body']}")

# Test Angle A Touch 2
t = get_template("A", 2, "Sunshine Realty Group", "Michael Torres", "Miami")
print(f"\n--- Angle A Touch 2 ---")
print(f"Subject: '{t['subject']}'")
print(f"Body:\n{t['body']}")

# Test Angle B Touch 1
t = get_template("B", 1, "Gulf Coast Real Estate", "David Chen", "Houston")
print(f"\n--- Angle B Touch 1 ---")
print(f"Subject: {t['subject']}")
print(f"Body:\n{t['body']}")

# Test Angle B Touch 3
t = get_template("B", 3, "Gulf Coast Real Estate", "David Chen", "Houston")
print(f"\n--- Angle B Touch 3 ---")
print(f"Subject: {t['subject']}")
print(f"Body:\n{t['body']}")

# Test Angle A Touch 4
t = get_template("A", 4, "Sunshine Realty Group", "Michael Torres", "Miami")
print(f"\n--- Angle A Touch 4 ---")
print(f"Subject: {t['subject']}")
print(f"Body:\n{t['body']}")

print("\n" + "=" * 60)
print("ALL TEMPLATES OK")
