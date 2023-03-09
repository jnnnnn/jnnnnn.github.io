# after pasting a summary card from the spreadsheet, run this script to clean it up

import bs4
import glob

def clean_summary(soup):
    # remove styles and IDs from all tags
    for tag in soup.find_all(True):
        del tag['style']
        del tag['id']
    
for filename in glob.glob('*.html'):
    with open(filename, 'r') as f:
        soup = bs4.BeautifulSoup(f, 'html.parser')
    clean_summary(soup)
    with open(filename, 'w') as f:
        f.write(str(soup))