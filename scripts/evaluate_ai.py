import os
import sys
from collections import defaultdict
import json

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from adapters.ai import BedrockAI

TEST_DATA = [
    ("NETFLIX SUBSCRIPTION", -250000, "Subscriptions"),
    ("SALARY MAY 2026", 20000000, "Income"),
    ("CGV CINEMA", -150000, "Entertainment"),
    ("HIGHLANDS COFFEE", -55000, "Food"),
    ("SHELL PETROL", -80000, "Transport"),
    ("EVN HANOI", -450000, "Utilities"),
    ("VIETTEL POST", -25000, "Shopping"),
    ("LAZADA ECOMMERCE", -350000, "Shopping"),
    ("TRANSFER TO MOM", -5000000, "Transfer"),
    ("PHARMACITY STORE", -120000, "Health"),
    ("SPOTIFY PREMIUM", -59000, "Subscriptions"),
    ("UBER TRIP", -120000, "Transport"),
    ("MEDLATEC BLOOD TEST", -800000, "Health"),
    ("VNPT INTERNET", -220000, "Utilities"),
    ("DIVIDEND STOCK", 1500000, "Income"),
    
    ("VINMART HCM 04", -120000, "Food"),
    ("T1908 GRAB CITY", -50000, "Transport"),
    ("MACBOOK PRO 14 SHOPEE", -35000000, "Shopping"),
    ("GRAB FOOD DELIVERY", -60000, "Food"),
    ("BE BIKE HANOI", -25000, "Transport"),
    ("SHOPEE PAY TOPUP", -500000, "Transfer"),
    
    ("FT0024112501 ID:0001", -250000, "Other"),
    ("REF:839201948", -50000, "Other"),
    ("POS 192837482", -12000, "Other"),
    ("TRANS 009281X", -5000, "Other"),
    ("UNKNOWN DEBIT", -100000, "Other"),
    ("SYSTEM FEE 999", -11000, "Other"),
    ("MAINTENANCE CHARGE", -55000, "Other"),
    ("AUTO DEBIT 11X9", -20000, "Other"),
    ("ACH DEP 900", 500000, "Income"),
    ("XFER 00991", -50000, "Transfer"),
]

def main():
    model_id = os.environ.get("AI_MODEL_ID", "us.amazon.nova-2-lite-v1:0")
    region = os.environ.get("AWS_REGION", "us-west-2")
    ai = BedrockAI(region=region, model_id=model_id)

    print(f"Starting evaluation using model: {model_id}")
    
    y_true = []
    y_pred = []
    
    correct = 0
    total = len(TEST_DATA)
    
    for desc, amount, true_cat in TEST_DATA:
        print(f"Processing: {desc}...")
        try:
            result = ai.categorize(description=desc, amount=amount, date="2026-05-15")
            pred_cat = result["category"]
            y_true.append(true_cat)
            y_pred.append(pred_cat)
            
            if pred_cat == true_cat:
                correct += 1
            else:
                print(f"  [MISMATCH] Desc: '{desc}' | Expected: {true_cat} | Got: {pred_cat} (Conf: {result['confidence']})")
        except Exception as e:
            print(f"  [ERROR] {e}")
            y_true.append(true_cat)
            y_pred.append("ERROR")

    print("\n--- RESULTS ---")
    accuracy = correct / total * 100
    print(f"Accuracy: {accuracy:.1f}% ({correct}/{total})")
    
    print("\n--- CONFUSION MATRIX ---")
    categories = sorted(list(set(y_true + y_pred)))
    
    header = f"{'True \ Pred':<15} | " + " | ".join([f"{c:<12}" for c in categories])
    print(header)
    print("-" * len(header))
    
    matrix = defaultdict(lambda: defaultdict(int))
    for t, p in zip(y_true, y_pred):
        matrix[t][p] += 1
        
    for t_cat in categories:
        row = f"{t_cat:<15} | "
        for p_cat in categories:
            row += f"{matrix[t_cat][p_cat]:<12} | "
        print(row)
        
    print("\n[Done] Copy these results to Evidence Pack §6.5")

if __name__ == "__main__":
    main()
