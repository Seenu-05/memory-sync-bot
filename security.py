import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class MemoryVault:

    def __init__(self, base64_key: str):
        self.key = base64.urlsafe_b64decode(base64_key)
        self.aesgcm = AESGCM(self.key)

    def lock(self, plain_text: str) -> str:
        iv = os.urandom(12)
        ciphertext = self.aesgcm.encrypt(iv, plain_text.encode('utf-8'), None)
        glued_payload = iv + ciphertext
        return base64.urlsafe_b64encode(glued_payload).decode('utf-8')
    
    def unlock(self, locked_string: str) ->str:
        glued_payload = base64.urlsafe_b64decode(locked_string)
        iv = glued_payload[:12]
        ciphertext = glued_payload[12:]
        decrypted_bytes = self.aesgcm.decrypt(iv, ciphertext, None)
        return decrypted_bytes.decode('utf-8')