#!/bin/bash
set -e

WAND_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VANILLA_MEDIA="$WAND_DIR/vanilla-media"

mkdir -p "$VANILLA_MEDIA/media/play/v2/client/web_service"
mkdir -p "$VANILLA_MEDIA/play/web_service"

cat > "$VANILLA_MEDIA/media/play/v2/client/web_service/environment_data.xml" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<environment>
    <servers>http://localhost:8888/media/play/servers.xml</servers>
</environment>
XML

cp "$VANILLA_MEDIA/media/play/v2/client/web_service/environment_data.xml" \
   "$VANILLA_MEDIA/play/web_service/environment_data.xml"

echo "environment_data.xml applied."
