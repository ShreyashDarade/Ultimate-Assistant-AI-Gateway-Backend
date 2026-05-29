"""Generate a Fernet master encryption key for BYOK key encryption."""

from cryptography.fernet import Fernet


def main():
    key = Fernet.generate_key()
    print(f"\nGenerated MASTER_ENCRYPTION_KEY:\n")
    print(f"  {key.decode()}\n")
    print("Add this to your .env file as MASTER_ENCRYPTION_KEY=<key>")
    print("WARNING: Losing this key means all encrypted provider keys are unrecoverable.\n")


if __name__ == "__main__":
    main()
