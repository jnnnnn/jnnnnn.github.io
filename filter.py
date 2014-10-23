import csv
with open(r"D:\drop\jnnnnn.github.io\bachata_moves.txt", newline='') as infile:
    inrows = csv.reader(infile, delimiter='\t')
    with open(r"D:\drop\jnnnnn.github.io\bachata_moves_fun.txt", 'w', newline='') as outfile:
        outrows = csv.writer(outfile, delimiter='\t')
        outrows.writerow(inrows.__next__()) # copy header
        for row in inrows:
            if 'fun' in row[3] or 'body' in row[3]:
                outrows.writerow(row)