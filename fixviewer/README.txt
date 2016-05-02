FixTranslate is just a pretty-printer script for FIX messages, in the form of an HTML page.

Message field names and enumerated values are defined by the ***DataDictionary.xml files (hence the need for a web server -- these files cannot be loaded by HTTP::GET without a web server due to cross-domain scripting safeguards).

Uses python to serve web files -- run start-server.bat. The python web server is not meant for production -- use something else on at-risk machines.

The DataDictionary files are from various places.:
 - FIX standard ones from http://www.quickfixengine.org/xml.html
 - some were written by hand from specifications