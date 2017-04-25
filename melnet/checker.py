import os

for args, dirname, files in os.walk('gtfs'):
    if 'routes.txt' in files:
        with open(os.path.join(args, 'routes.txt'), 'r', encoding='utf-8') as f:
            lines = f.readlines()
            print(args, len(lines))
            print("".join(lines[:4]))
            print()
