#!/usr/bin/env python3
"""
publish_only.py — Minimal tester for your existing publish_upload() logic.

Usage:
  export NOMAD_API=http://localhost/nomad-oasis/api      # or .../api/v1
  export NOMAD_TOKEN='<paste_UI_token_here>'
  python3 publish_only.py --id <upload_id>

It will POST {API}/v1/uploads/<id>/action/publish and print status + a short body preview.
Exit codes: 0 = 200/202; 3 = non-2xx HTTP; 4 = other error.
"""
import argparse
import os
import sys
import requests

def join_api(api_base: str, path: str) -> str:
    api_base = api_base.rstrip('/')
    path = path.lstrip('/')
    return f"{api_base}/{path}"

def publish_upload(nomad_url: str, token: str, upload_id: str, timeout: int = 60) -> requests.Response:
    """
    Your original publish function, with a tiny guard to ensure /v1/ is present.
    Accepts nomad_url as .../api OR .../api/v1 and normalizes to /api/v1/...
    """
    base = nomad_url.rstrip('/')
    if not base.endswith('/v1'):
        base = base + '/v1'
    url = join_api(base, f'uploads/{upload_id}/action/publish')
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
    resp = requests.post(url, headers=headers, timeout=timeout)
    return resp

def main():
    p = argparse.ArgumentParser(description="POST /v1/uploads/<id>/action/publish and show the result.")
    p.add_argument('--api', default=os.getenv('NOMAD_API', 'http://localhost/nomad-oasis/api'),
                   help='API base (…/api or …/api/v1). Default: env NOMAD_API or http://localhost/nomad-oasis/api')
    p.add_argument('--token', default=os.getenv('NOMAD_TOKEN', ''),
                   help='Bearer token. Default: env NOMAD_TOKEN')
    p.add_argument('--id', required=True, help='upload_id to publish')
    p.add_argument('--timeout', type=int, default=60, help='Request timeout seconds (default 60)')
    args = p.parse_args()

    if not args.token:
        print("[error] No token provided. Set NOMAD_TOKEN or use --token.", file=sys.stderr)
        sys.exit(4)

    try:
        resp = publish_upload(args.api, args.token, args.id, timeout=args.timeout)
        ct = resp.headers.get('content-type', '')
        body_preview = (resp.text or '')[:300].replace('\n', ' ').replace('\r', ' ')
        print(f"[publish] URL: {resp.request.url}")
        print(f"[publish] HTTP {resp.status_code}  CT={ct}")
        print(f"[publish] Body (first 300 chars): {body_preview}")
        if resp.status_code in (200, 202):
            sys.exit(0)
        else:
            sys.exit(3)
    except Exception as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(4)

if __name__ == '__main__':
    main()