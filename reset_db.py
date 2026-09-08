import json
import os

db_path = r'C:\Users\aucar\Desktop\trade-bot\trade_history.json'

data = {
    "balance": 10000.0,
    "open_positions": {},
    "history": []
}

with open(db_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4)

print("Demo database reset to $10,000. Open and closed positions cleared.")
