# test_telegram.py
from dotenv import load_dotenv
load_dotenv()
from core.notifier import TelegramNotifier
n = TelegramNotifier()
print(n.send_test())