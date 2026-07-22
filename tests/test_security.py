import pytest
import os
from security import MemoryVault

os.environ["ENCRYPTION_KEY"] = "MTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTI="

def test_encryption_alters_text():
    vault = MemoryVault(os.environ["ENCRYPTION_KEY"])
    original_text = "This is a highly classified memory."
    encrypted = vault.lock(original_text)

    assert encrypted!=original_text
    assert len(encrypted)>0

def test_decryption_restores_text():
    vault = MemoryVault(os.environ["ENCRYPTION_KEY"])
    original_text = "This is another classified memory."
    encrypted = vault.lock(original_text)
    decrypted = vault.unlock(encrypted)

    assert decrypted==original_text

