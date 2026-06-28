import json
import pandas as pd

# Load the three translation files
with open("gloss_translation-qwen-maxT1.0.json", "r", encoding="utf-8") as f:
    t10 = json.load(f)

with open("gloss_translation-qwen-maxT1.1.json", "r", encoding="utf-8") as f:
    t11 = json.load(f)

with open("gloss_translation-qwen-maxT1.2.json", "r", encoding="utf-8") as f:
    t12 = json.load(f)

# Get all unique keys (characters)
all_keys = set(t10.keys()) | set(t11.keys()) | set(t12.keys())

# Build the data
data = []
for char in all_keys:
    en_gloss = t10.get(char, {}).get("gloss_en", "") or t11.get(char, {}).get("gloss_en", "") or t12.get(char, {}).get("gloss_en", "")
    fr_10 = t10.get(char, {}).get("gloss_fr", "")
    fr_11 = t11.get(char, {}).get("gloss_fr", "")
    fr_12 = t12.get(char, {}).get("gloss_fr", "")
    data.append([char, en_gloss, fr_10, fr_11, fr_12])

# Create DataFrame
df = pd.DataFrame(data, columns=["Char", "en_gloss", "1.0", "1.1", "1.2"])

# Sort by character to maintain consistent order
df = df.sort_values(by="Char").reset_index(drop=True)

# Write to Excel
df.to_excel("gloss_translations_comparison.xlsx", index=False)

print(f"Excel file created with {len(df)} entries: gloss_translations_comparison.xlsx")
