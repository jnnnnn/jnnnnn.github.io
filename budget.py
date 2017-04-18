import csv, collections

categories = collections.defaultdict(list)
with open(r"d:/drop/jnnnnn.github.io/translog.txt") as f:
  for row in csv.DictReader(f, delimiter="\t"):
    categories[row["Category"]].append((float(row["Debit"]), row["Description"]))
for c in categories:
    categories[c].sort()

import pprint
pprint.pprint(categories)