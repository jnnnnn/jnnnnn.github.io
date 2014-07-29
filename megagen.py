# Generate a huge number of move sequences from a given state transition diagram TSV file.

import os, sys, random, time, pprint, csv
from collections import defaultdict

sleeptime = 1
outfile = sys.stdout
outfile = open(r'bachata.txt', 'w', encoding='utf-8')
sleeptime = 0

# build moves list
moves = defaultdict(list)
positions = set()
csvfile = os.path.join(os.path.dirname(__file__),'bachata_moves.txt')
with open(csvfile, 'r') as infile:
    reader = csv.reader(infile, delimiter='\t')
    reader.__next__() # skip header
    for start_position, move, end_position, *_ in reader:
        start_position = start_position.strip()
        move = move.strip()
        end_position = end_position.strip()
        moves[start_position].append((move, end_position))
        positions.add(start_position)
        positions.add(end_position)
    
# check moves list for dead ends
for position in positions:    
    if not moves[position]:
        print("Warning! '{}' is a dead end!".format(end_position), file=sys.stderr)
sys.stderr.flush()

pprint.pprint(positions)        
pprint.pprint(moves)

# start randomly choosing moves..
position = "Open hold"
while True:    
    old_position = position
    move, position = random.choice(moves[position])
    if old_position == position:
        print("{} ({})".format(move, position), file=outfile)
    else:
        print(move + " → " + position, file=outfile)
    #outfile.flush()
    if sleeptime:
        time.sleep(sleeptime)
        for i in range(3):                    
            print('.', end="", file=outfile)
            sys.stdout.flush()
            time.sleep(sleeptime)            
        print(file=outfile)
        outfile.flush()
