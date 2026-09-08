import sys
import os

sys.path.append(r'C:\Users\aucar\Desktop\trade-bot')
from paper_trader import PaperTrader

print("Connecting to GitHub to reset database...")
pt = PaperTrader() # This loads from GitHub
pt.balance = 10000.0
pt.open_positions = {}
pt.history = []

print("Overwriting GitHub state...")
pt._push_to_github({
    "balance": pt.balance,
    "open_positions": pt.open_positions,
    "history": pt.history
})
print("Reset complete! You can restart the bot now.")
