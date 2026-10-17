"""管理用小工具。

產生後台登入密碼的雜湊值：
    python manage.py hash-password
"""
import getpass
import sys

import security


def hash_password_command():
    password = getpass.getpass("請輸入後台密碼（輸入時不會顯示）：")
    if len(password) < 10:
        print("密碼至少要 10 個字元。")
        return 1
    if password != getpass.getpass("再輸入一次："):
        print("兩次輸入不一樣。")
        return 1
    print("\n把下面這一行放進 .env 檔（或主機的環境變數），整行包含單引號都要保留：\n")
    print(f"ADMIN_PASSWORD_HASH='{security.hash_password(password)}'")
    return 0


if __name__ == "__main__":
    commands = {"hash-password": hash_password_command}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        print(__doc__)
        sys.exit(1)
    sys.exit(commands[sys.argv[1]]())
