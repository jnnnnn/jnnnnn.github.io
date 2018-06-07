"""Short script to detect uncommon words in a string (for sanitization purposes)"""
import urllib3, os, zipfile, io, tempfile

# go get a wordlist if we haven't already
wordsfile = os.path.join(tempfile.gettempdir(), 'words_dictionary.json')
if not os.path.exists(wordsfile):
    req = urllib3.PoolManager().request('GET', 'https://github.com/dwyl/english-words/raw/master/words_dictionary.zip')
    zipfile.ZipFile(io.BytesIO(req.data)).extractall(path=tempfile.gettempdir())
    print("Extracted", wordsfile)

# load the wordlist
import json, string
with open(wordsfile, 'r') as f:
    words_common = set(json.load(f).keys())

inputstring = """
test string with
lots asdfasdnfoinseflk of common words and
a couuuuple of unusual ones 
her insults were on point
"""

# remove junk characters to make isolating words with str.split() easy
allowed_chars = set("abcdefghijklmnopqrstuvwxyz \t\n-'")
filtered_string = ''.join(c for c in inputstring.lower() if c in allowed_chars)

print("Unusual words:")
print(set([word for word in filtered_string.split() if word not in words_common]))

words_gendered = 'he she him her his hers himself herself'
print("Gendered words:")
print(set([word for word in filtered_string.split() if word in words_gendered]))