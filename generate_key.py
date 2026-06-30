import os
import base64

raw_key = os.urandom(32)

safe_key = base64.urlsafe_b64encode(raw_key).decode('utf-8');

print("\nYOUR AES-256 MASTER KEY:")
print("========================")
print(safe_key)
print("========================")
print("WARNING: If you lose this, your data is permanently gone.\n")