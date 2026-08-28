import http.server
import socketserver
import os
import urllib.parse
import urllib.request
import mimetypes

import http.client

PORT = 8888
DIRECTORY = "/opt/cpps/wand/vanilla-media"
DASH_HOST = "127.0.0.1"
DASH_PORT = 3000

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
        conn = None
        try:
            conn = http.client.HTTPConnection(DASH_HOST, DASH_PORT, timeout=10)
            headers = {}

            # Forward relevant request headers
            content_type = self.headers.get('Content-Type')
            if content_type:
                headers['Content-Type'] = content_type
            elif body is not None:
                headers['Content-Type'] = 'application/x-www-form-urlencoded'

            cookie = self.headers.get('Cookie')
            if cookie:
                headers['Cookie'] = cookie

            for h in ['X-Drupal-Ajax-Token', 'X-Requested-With', 'Accept', 'User-Agent', 'Referer']:
                v = self.headers.get(h)
                if v:
                    headers[h] = v

            conn.request(method, path, body=body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()

            print(f"[proxy_to_dash] {method} {path} -> Dash status {resp.status}")
            if resp.status >= 400 and len(data) < 300:
                print(f"[proxy_to_dash] Dash response: {data.decode('utf-8', errors='ignore')}")

            is_ajax = (self.headers.get('X-Requested-With') == 'XMLHttpRequest' or 
                       'X-Drupal-Ajax-Token' in self.headers or 
                       'application/json' in self.headers.get('Accept', ''))

            # If Dash returns a 302 redirect for an AJAX request, Drupal AJAX needs JSON commands to redirect
            if resp.status in (301, 302, 303, 307) and is_ajax:
                redirect_url = '/play/ruffle.html'
                for header, val in resp.getheaders():
                    if header.lower() == 'location':
                        parsed_loc = urllib.parse.urlparse(val)
                        if 'play' in parsed_loc.netloc or 'play' in parsed_loc.path or 'ruffle' in parsed_loc.path:
                            redirect_url = '/play/ruffle.html'
                        elif parsed_loc.path:
                            redirect_url = parsed_loc.path
                            if parsed_loc.query:
                                redirect_url += '?' + parsed_loc.query

                if body:
                    try:
                        form_data = urllib.parse.parse_qs(body.decode('utf-8', errors='ignore'))
                        if 'name' in form_data and form_data['name']:
                            user_param = f"created=1&user={urllib.parse.quote(form_data['name'][0])}"
                            redirect_url += ('&' if '?' in redirect_url else '?') + user_param
                    except Exception:
                        pass

                ajax_json = (
                    f'[{{"command":"redirect","url":"{redirect_url}"}},'
                    f'{{"command":"invoke","selector":"body","method":"javascript_goto","arguments":["{redirect_url}"]}}]'
                ).encode('utf-8')

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('X-Drupal-Ajax-Token', '1')
                for header, val in resp.getheaders():
                    if header.lower() == 'set-cookie':
                        self.send_header(header, val)
                self.send_header('Content-Length', str(len(ajax_json)))
                self.end_headers()
                self.wfile.write(ajax_json)
                print(f"[proxy_to_dash] Sent Drupal AJAX redirect command to: {redirect_url}")
                return True

            self.send_response(resp.status)
            for header, val in resp.getheaders():
                if header.lower() == 'location':
                    parsed_loc = urllib.parse.urlparse(val)
                    if 'play' in parsed_loc.netloc or 'play' in parsed_loc.path or 'ruffle' in parsed_loc.path:
                        val = '/play/ruffle.html'
                    elif parsed_loc.path:
                        val = parsed_loc.path
                        if parsed_loc.query:
                            val += '?' + parsed_loc.query

                    if body:
                        try:
                            form_data = urllib.parse.parse_qs(body.decode('utf-8', errors='ignore'))
                            if 'name' in form_data and form_data['name']:
                                user_param = f"created=1&user={urllib.parse.quote(form_data['name'][0])}"
                                val += ('&' if '?' in val else '?') + user_param
                        except Exception:
                            pass
                    print(f"[proxy_to_dash] Redirecting client to: {val}")

            # Inject helper script into create page HTML so the submit button never gets stuck
            if method == "GET" and ("create" in path or "penguin" in path) and b'</body>' in data and b'edit-submit' in data:
                fix_script = b'''<script>
(function() {
    function checkFormReady() {
        if (typeof jQuery === 'undefined') return;
        var name = (jQuery('#edit-name').val() || '').trim();
        var pass = (jQuery('#edit-pass').val() || '').trim();
        var email = (jQuery('#edit-email').val() || '').trim();
        var terms = jQuery('#edit-terms').is(':checked');
        var captcha = jQuery('#edit-captcha input:checked').length > 0;
        
        if (name.length >= 3 && pass.length >= 6 && email.length >= 5 && terms && captcha) {
            jQuery('#edit-submit').removeClass('disabled').removeAttr('disabled');
            jQuery('#submit-wrapper .preventer').hide();
        }
    }

    jQuery(document).ready(function($) {
        $(document).on('input keyup change click', '#edit-name, #edit-pass, #edit-email, #edit-terms, #edit-captcha input', function() {
            setTimeout(checkFormReady, 100);
        });
        $(document).on('click', '#submit-wrapper', function(e) {
            $('#edit-name, #edit-pass, #edit-email').trigger('blur');
            setTimeout(function() {
                checkFormReady();
                var btn = $('#edit-submit');
                if (!btn.hasClass('disabled') && !(typeof Drupal !== 'undefined' && Drupal.penguin && Drupal.penguin.ajaxInProgress)) {
                    $('#penguin-create-form').submit();
                }
            }, 300);
        });
    });
})();
</script></body>'''
                data = data.replace(b'</body>', fix_script)

            for header, val in resp.getheaders():
                if header.lower() not in ['transfer-encoding', 'content-length']:
                    self.send_header(header, val)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return True
        except Exception as e:
            print(f"[proxy_to_dash] error proxying {method} {path}: {e}")
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

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
        clean_path = raw_path.rstrip('/')
        dash_target = PENGUIN_POST_MAP.get(clean_path, PENGUIN_POST_MAP.get(raw_path))
        if dash_target:
            if parsed.query:
                dash_target += '?' + parsed.query
            if self.proxy_to_dash(dash_target, body, method='POST'):
                return

        # Forward POST requests coming to Dash services
        if any(raw_path.startswith(p) for p in ["/create", "/activate", "/autocomplete", "/penguin"]):
            if self.proxy_to_dash(self.path, body, method="POST"):
                return

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def _lookup_penguin_db(self, name):
        """Look up penguin ID and username/nickname from the PostgreSQL database."""
        if not name:
            return None

        # Method 1: psycopg2 if installed
        try:
            import psycopg2
            conn = psycopg2.connect(host="127.0.0.1", port=5432, user="postgres", password="postgres", dbname="postgres")
            cur = conn.cursor()
            cur.execute("SELECT id, username, nickname FROM penguin WHERE LOWER(username)=LOWER(%s) OR LOWER(nickname)=LOWER(%s) LIMIT 1", (name, name))
            row = cur.fetchone()
            conn.close()
            if row:
                return {"id": row[0], "username": row[1], "nickname": row[2]}
        except Exception:
            pass

        # Method 2: docker exec wand-db-1 psql
        try:
            import subprocess
            clean_name = ''.join(c for c in name if c.isalnum() or c in ' _-')
            cmd = ["docker", "exec", "wand-db-1", "psql", "-U", "postgres", "-t", "-A", "-c",
                   f"SELECT id, username, nickname FROM penguin WHERE LOWER(username)=LOWER('{clean_name}') OR LOWER(nickname)=LOWER('{clean_name}') LIMIT 1;"]
            out = subprocess.check_output(cmd, timeout=3).decode('utf-8').strip()
            if out:
                parts = out.split('|')
                return {"id": int(parts[0]), "username": parts[1], "nickname": parts[2]}
        except Exception as e:
            print(f"[_lookup_penguin_db] docker exec error: {e}")

        # Method 3: sudo docker exec wand-db-1 psql
        try:
            import subprocess
            clean_name = ''.join(c for c in name if c.isalnum() or c in ' _-')
            cmd = ["sudo", "docker", "exec", "wand-db-1", "psql", "-U", "postgres", "-t", "-A", "-c",
                   f"SELECT id, username, nickname FROM penguin WHERE LOWER(username)=LOWER('{clean_name}') OR LOWER(nickname)=LOWER('{clean_name}') LIMIT 1;"]
            out = subprocess.check_output(cmd, timeout=3).decode('utf-8').strip()
            if out:
                parts = out.split('|')
                return {"id": int(parts[0]), "username": parts[1], "nickname": parts[2]}
        except Exception as e:
            print(f"[_lookup_penguin_db] sudo docker exec error: {e}")

        return None

    def _handle_datatech_get(self, raw_path, qs):
        """Responses for the Disney Friends /datatech API used by the CP SWF & Friends UI.

        The Show Friends button (and the friends list overlay) calls several endpoints:
          - /datatech/cp/getPublicPlayerDataByDisplayName  -> look up a player by name
          - /datatech/cp/GetPublicProfileData              -> get a player's profile
          - /datatech/cp/GetPlayerFriendsList              -> friends list
          - /datatech/cp/GetFriendshipStatus               -> friendship status
          All other /datatech calls receive a generic empty-success response.
        """
        import json

        path_lower = raw_path.lower()

        # Look up player by display name (used by "Find a Friend" search in Disney Friends panel)
        if 'getpublicplayerdatabydisplayname' in path_lower:
            display_name = (qs.get('displayName') or qs.get('displayname') or [''])[0]
            player = self._lookup_penguin_db(display_name)
            if player:
                print(f"[datatech] Found player for '{display_name}': id={player['id']}, name={player['nickname']}")
                payload = {
                    "status": 200,
                    "payload": {
                        "data": {
                            "displayName": player["nickname"] or player["username"],
                            "swid": str(player["id"]),
                            "id": player["id"],
                            "age": 0,
                            "country": "US"
                        }
                    }
                }
            else:
                print(f"[datatech] Player not found for '{display_name}'")
                payload = {
                    "status": 404,
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
        elif target.endswith('.json') or os.path.basename(target) == 'services':
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

    def list_directory(self, path):
        self.send_error(404, "File not found")
        return None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        raw_path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        # Redirect root to /play/
        if raw_path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header('Location', '/play/')
            self.end_headers()
            return

        if raw_path in ("/play", "/play/", "/play/index.html"):
            target = "/opt/cpps/wand/vanilla-media/play/index.html"
            if not os.path.isfile(target):
                target = "/opt/cpps/wand/templates/vanilla-media/play/index.html.template"
            if os.path.isfile(target):
                with open(target, 'rb') as f:
                    content = f.read()
                # Ensure Login button links directly to /play/ruffle.html and other links to /play/
                content = content.replace(b'href="/#/login"', b'href="/play/ruffle.html"')
                content = content.replace(b'href="http://www.clubpenguin.com/?home=return"', b'href="/play/"')
                content = content.replace(b'href="https://secured.clubpenguin.com/membership"', b'href="/play/"')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        if raw_path == "/play/ruffle.html":
            target = "/opt/cpps/wand/ruffle.html"
            if os.path.isfile(target):
                self.send_file(target)
                return

        # CP SWF navigates to these URLs via navigateToURL().
        # Proxy them to the correct Dash routes so the page stays on port 8888.
        PENGUIN_ROUTES = {
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
        clean_path = raw_path.rstrip('/')
        dash_target = PENGUIN_ROUTES.get(clean_path, PENGUIN_ROUTES.get(raw_path))
        if dash_target:
            if parsed.query:
                dash_target += '?' + parsed.query
            if self.proxy_to_dash(dash_target, method="GET"):
                return

        # 1. Dash (Port 3000) Avatar, Create, Activate, Penguin and Web Service Redirects
        if (raw_path.startswith("/avatar") or raw_path.startswith("/social") or 
            raw_path.startswith("/create") or raw_path.startswith("/activate") or
            raw_path.startswith("/penguin") or "autocomplete" in raw_path):
            dash_path = self.path
            if raw_path.startswith("/avatar/"):
                dash_path = re.sub(r'^/avatar/(\d+)/[a-zA-Z]+', r'/avatar/\1', self.path)
            if self.proxy_to_dash(dash_path, method="GET"):
                return

        # 2. Disney Friends / datatech API stubs
        # The CP SWF calls these to power the Show Friends button and friends list overlay.
        if raw_path.startswith("/datatech/"):
            self._handle_datatech_get(raw_path, qs)
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

class ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

with ThreadingServer(("", PORT), CPPSHandler) as httpd:
    print(f"[✓] CPPS Multi-threaded Web Server running on port {PORT}.")
    httpd.serve_forever()
