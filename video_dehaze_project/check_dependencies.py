#!/usr/bin/env python
"""Quick script to verify all dependencies are installed correctly."""

import sys

print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print()

missing = []
required = [
    "fastapi",
    "uvicorn", 
    "cv2",  # opencv-python
    "numpy",
    "dotenv",  # python-dotenv
    "jwt",  # PyJWT
    "passlib",
    "sqlalchemy",
    "pymysql",
    "cryptography",
]

print("Checking dependencies...")
for module in required:
    try:
        if module == "cv2":
            import cv2
            print(f"[OK] opencv-python (cv2)")
        elif module == "dotenv":
            from dotenv import load_dotenv
            print(f"[OK] python-dotenv (dotenv)")
        elif module == "jwt":
            import jwt
            print(f"[OK] PyJWT (jwt)")
        else:
            __import__(module)
            print(f"[OK] {module}")
    except ImportError:
        print(f"[FAIL] {module} - MISSING")
        missing.append(module)

print()
if missing:
    print(f"ERROR: Missing {len(missing)} package(s): {', '.join(missing)}")
    print("\nInstall missing packages with:")
    print(f"  python -m pip install {' '.join(missing)}")
    sys.exit(1)
else:
    print("[OK] All dependencies are installed!")
    print("\nYou can now run the backend with:")
    print("  python backend.py")
    sys.exit(0)

