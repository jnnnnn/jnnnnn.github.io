import csv

def select_typed():
    with open(r"D:\drop\jnnnnn.github.io\bachata_moves.txt", newline='') as infile:
        inrows = csv.reader(infile, delimiter='\t')
        with open(r"D:\drop\jnnnnn.github.io\bachata_moves_typed.tsv", 'w', newline='') as outfile:
            outrows = csv.writer(outfile, delimiter='\t')
            outrows.writerow(inrows.__next__()) # copy header
            for row in inrows:        	  	
                if 'basic' in row[3]:
                	row[4] = "basic"
                if 'turn' in row[3]:
                	row[4] = "turn"
                outrows.writerow(row)

def check_tags():
    moves = {} # key -> tags
    with open(r"D:\drop\jnnnnn.github.io\bachata_moves.txt", newline='') as infile:
        for row in csv.reader(infile, delimiter='\t'):
            key = row[0] + " -> " + row[1] + " -> " + row[2]
            tags = sorted(tag.strip() for tag in row[3].split(","))
            if key in moves:
                if moves[key] != tags:
                    print("{} has tags {} and {}".format(key, moves[key], tags))
            else:
                moves[key] = tags

def select_fun():
    with open(r"D:\drop\jnnnnn.github.io\bachata_moves.txt", newline='') as infile:
        inrows = csv.reader(infile, delimiter='\t')
        with open(r"D:\drop\jnnnnn.github.io\bachata_moves_fun.txt", 'w', newline='') as outfile:
            outrows = csv.writer(outfile, delimiter='\t')
            outrows.writerow(inrows.__next__()) # copy header
            for row in inrows:              
                if 'fun' in row[3] or 'body' in row[3]:                    
                    outrows.writerow(row)

def select_unique():
    with open(r"D:\drop\jnnnnn.github.io\bachata_moves.txt", newline='') as infile:
        inrows = csv.reader(infile, delimiter='\t')
        with open(r"D:\drop\jnnnnn.github.io\bachata_moves_unique.txt", 'w', newline='') as outfile:
            outrows = csv.writer(outfile, delimiter='\t')
            outrows.writerow(inrows.__next__()) # copy header
            seen_keys = set()
            for row in inrows:  
                key = row[0] + " -> " + row[1] + " -> " + row[2]            
                if key not in seen_keys:
                    outrows.writerow(row)
                    seen_keys.add(key)

select_unique()
