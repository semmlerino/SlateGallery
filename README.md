# Encoded Releases

This branch contains base64-encoded bundles of SlateGallery for deployment.

## Decoding

```bash
python decode_app.py slategallery_latest.txt -o /path/to/deploy
```

## Contents

- `slategallery_latest.txt` - Latest encoded bundle
- `slategallery_latest_metadata.json` - Bundle metadata (commit info, timestamp)
