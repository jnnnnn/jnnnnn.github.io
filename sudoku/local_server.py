"""Firefox's security protections get more difficult every day. You not only
have to not use file:// to get around CORS, you also have to return the correct
content type."""

import webbrowser
import http.server
import socketserver

PORT = 8080

Handler = http.server.SimpleHTTPRequestHandler

Handler.extensions_map = {
    '.manifest': 'text/cache-manifest',
    '.html': 'text/html',
    '.png': 'image/png',
    '.jpg': 'image/jpg',
    '.svg':	'image/svg+xml',
    '.css':	'text/css',
    '.js':	'application/x-javascript',
    '': 'application/octet-stream',  # Default
}

httpd = socketserver.TCPServer(("", PORT), Handler)

webbrowser.open(f"http://localhost:{PORT}", new=2)
httpd.serve_forever()
