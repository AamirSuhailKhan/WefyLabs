import os

path = 'docs/audits/PHASE14_PRODUCT_STRATEGY_AND_BUSINESS_MODEL.md'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Replace any old occurrences
text = text.replace('?11,080', '₹11,120')
text = text.replace('?11,120', '₹11,120')
text = text.replace('$11,080', '₹11,120')
text = text.replace('?39,999', '₹39,999')
text = text.replace('?4,999', '₹4,999')
text = text.replace('?1,780', '₹1,780')
text = text.replace('?6,93,000', '₹6,93,103')
text = text.replace('?45,000', '₹45,000')

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
print("Updated product strategy business model encoding and figures.")

