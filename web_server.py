import http.server
import socketserver
import os
import urllib.parse
import urllib.request
import mimetypes

PORT = 8888
DIRECTORY = "/opt/cpps/wand/vanilla-media"
DASH_URL = "http://127.0.0.1:3000"

class CPPSHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, HEAD')
        self.send_header('Access-Control-Allow-Headers', '*')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def proxy_to_dash(self, path, body=None, method="GET"):
        try:
            target_url = f"{DASH_URL}{path}"
            req = urllib.request.Request(target_url, data=body, method=method)
            req.add_header('Content-Type', self.headers.get('Content-Type', 'application/json'))

            # Forward cookies so session-based Dash pages (e.g. registration) work.
            cookie = self.headers.get('Cookie')
            if cookie:
                req.add_header('Cookie', cookie)

            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
                self.send_response(resp.status)
                for header, val in resp.getheaders():
                    if header.lower() not in ['transfer-encoding', 'content-length']:
                        self.send_header(header, val)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return True
        except Exception as e:
            return False

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        raw_path = parsed.path
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length > 0 else None

        # Stub Disney Friends /datatech API (Dash has no /datatech route)
        if raw_path.startswith("/datatech/"):
            self.send_json(b'{"status":200,"payload":{},"data":{}}')
            return

        # Map /en|fr|es|pt/penguin/create|activate POST to Dash routes.
        PENGUIN_POST_MAP = {
            '/en/penguin/create':   '/create/vanilla/en',
            '/fr/penguin/create':   '/create/vanilla/fr',
            '/es/penguin/create':   '/create/vanilla/es',
            '/pt/penguin/create':   '/create/vanilla/pt',
            '/en/penguin/activate': '/activate/vanilla/en',
            '/fr/penguin/activate': '/activate/vanilla/fr',
            '/es/penguin/activate': '/activate/vanilla/es',
            '/pt/penguin/activate': '/activate/vanilla/pt',
            '/penguin/create':      '/create/vanilla/en',
            '/penguin/activate':    '/activate/vanilla/en',
        }
        if raw_path in PENGUIN_POST_MAP:
            dash_path = PENGUIN_POST_MAP[raw_path]
            if parsed.query:
                dash_path += '?' + parsed.query
            if self.proxy_to_dash(dash_path, body, method='POST'):
                return

        # Forward POST requests coming to Dash services
        if any(raw_path.startswith(p) for p in ["/create", "/activate", "/autocomplete"]):
            if self.proxy_to_dash(self.path, body, method="POST"):
                return

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def _handle_datatech_get(self, raw_path, qs):
        """Stub responses for the Disney Friends /datatech API used by the CP SWF.

        The Show Friends button (and the friends list overlay) calls several endpoints:
          - /datatech/cp/getPublicPlayerDataByDisplayName  -> look up a player by name
          - /datatech/cp/GetPublicProfileData              -> get a player's profile
          - /datatech/cp/GetPlayerFriendsList              -> friends list
          - /datatech/cp/GetFriendshipStatus               -> friendship status
          All other /datatech calls receive a generic empty-success response.
        """
        import json

        path_lower = raw_path.lower()

        # Look up player by display name (used by "Find a Friend" search)
        if 'getpublicplayerdatabydisplayname' in path_lower:
            display_name = (qs.get('displayName') or qs.get('displayname') or [''])[0]
            payload = {
                "status": 200,
                "payload": {
                    "data": {
                        "displayName": display_name,
                        "swid": "",
                        "id": 0,
                        "age": 0,
                        "country": "US"
                    }
                }
            }
            self.send_json(json.dumps(payload).encode())
            return

        # Get a player's public profile
        if 'getpublicprofiledata' in path_lower or 'getprofiledata' in path_lower:
            payload = {
                "status": 200,
                "payload": {
                    "data": {
                        "displayName": "",
                        "swid": "",
                        "membershipType": 1
                    }
                }
            }
            self.send_json(json.dumps(payload).encode())
            return

        # Friends list
        if 'getplayerfriendslist' in path_lower or 'friendslist' in path_lower:
            payload = {
                "status": 200,
                "payload": {
                    "data": {
                        "friends": []
                    }
                }
            }
            self.send_json(json.dumps(payload).encode())
            return

        # Friendship status check
        if 'getfriendshipstatus' in path_lower or 'friendshipstatus' in path_lower:
            payload = {
                "status": 200,
                "payload": {
                    "data": {
                        "status": "NOT_FRIEND"
                    }
                }
            }
            self.send_json(json.dumps(payload).encode())
            return

        # Generic fallback for any other /datatech endpoint
        self.send_json(b'{"status":200,"payload":{"data":{}}}')

    def send_file(self, target):
        mime_type, _ = mimetypes.guess_type(target)
        if target.endswith('.swf'):
            mime_type = 'application/x-shockwave-flash'
        elif target.endswith('.xml'):
            mime_type = 'text/xml'
        elif target.endswith('.json'):
            mime_type = 'application/json'
        elif target.endswith('.jsonp'):
            mime_type = 'application/javascript'

        self.send_response(200)
        self.send_header('Content-Type', mime_type or 'application/octet-stream')
        self.send_header('Content-Length', str(os.path.getsize(target)))
        self.end_headers()
        with open(target, 'rb') as f:
            self.wfile.write(f.read())

    def send_json(self, data: bytes):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        raw_path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if raw_path == "/play/ruffle.html":
            target = "/opt/cpps/wand/ruffle.html"
            if os.path.isfile(target):
                self.send_file(target)
                return

        # CP SWF navigates to these URLs via navigateToURL().
        # Proxy them to the correct Dash routes so the page stays on port 8888.
        PENGUIN_REDIRECTS = {
            '/en/penguin/create':        '/create/vanilla/en',
            '/en/penguin/create/game':   '/create/vanilla/en',
            '/en/penguin/create/redeem': '/create/vanilla/en',
            '/fr/penguin/create':        '/create/vanilla/fr',
            '/fr/penguin/create/game':   '/create/vanilla/fr',
            '/es/penguin/create':        '/create/vanilla/es',
            '/es/penguin/create/game':   '/create/vanilla/es',
            '/pt/penguin/create':        '/create/vanilla/pt',
            '/pt/penguin/create/game':   '/create/vanilla/pt',
            '/en/penguin/activate':      '/activate/vanilla/en',
            '/fr/penguin/activate':      '/activate/vanilla/fr',
            '/es/penguin/activate':      '/activate/vanilla/es',
            '/pt/penguin/activate':      '/activate/vanilla/pt',
            '/penguin/create':           '/create/vanilla/en',
            '/penguin/activate':         '/activate/vanilla/en',
        }
        if raw_path in PENGUIN_REDIRECTS:
            dest = 'http://127.0.0.1:3000' + PENGUIN_REDIRECTS[raw_path]
            if parsed.query:
                dest += '?' + parsed.query
            self.send_response(302)
            self.send_header('Location', dest)
            self.end_headers()
            return

        # 1. Dash (Port 3000) Avatar and Web Service Redirects
        if raw_path.startswith("/avatar") or raw_path.startswith("/social") or "autocomplete" in raw_path:
            if self.proxy_to_dash(self.path, method="GET"):
                return

        # 2. Disney Friends / datatech API stubs
        # The CP SWF calls these to power the Show Friends button and friends list overlay.
        if raw_path.startswith("/datatech/"):
            self._handle_datatech_get(raw_path, qs)
            return

        if "services" in raw_path:
            services_xml = b'''<?xml version="1.0" encoding="UTF-8"?>
            <services>
                <service name="like" status="enabled"/>
                <service name="igloo" status="enabled"/>
            </services>'''
            self.send_response(200)
            self.send_header('Content-Type', 'text/xml')
            self.send_header('Content-Length', str(len(services_xml)))
            self.end_headers()
            self.wfile.write(services_xml)
            return

        # 2. Direct file path matching
        direct_path = self.translate_path(self.path)
        if os.path.exists(direct_path) and not os.path.isdir(direct_path):
            self.send_file(direct_path)
            return

        # 3. Smart Scored File Search
        filename = os.path.basename(raw_path)
        if filename and not filename.startswith("start-module"):
            parts = [p.lower() for p in raw_path.strip('/').split('/') if p]
            best_match = None
            best_score = -1

            for root, _, files in os.walk(DIRECTORY):
                for f in files:
                    if f.lower() == filename.lower():
                        full_path = os.path.join(root, f)
                        full_lower = full_path.lower()

                        score = sum(1 for part in parts if part in full_lower)
                        if len(parts) >= 2 and f"{parts[-2]}/{parts[-1]}" in full_lower:
                            score += 5
                        if len(parts) >= 3 and f"{parts[-3]}/{parts[-2]}/{parts[-1]}" in full_lower:
                            score += 10

                        if score > best_score:
                            best_score = score
                            best_match = full_path

            if best_match:
                self.send_file(best_match)
                return

        return super().do_GET()

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), CPPSHandler) as httpd:
    print(f"[✓] CPPS Web Server running on port {PORT}.")
    httpd.serve_forever()
