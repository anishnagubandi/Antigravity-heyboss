import os
import sys
import json
import base64
import re
import urllib.request

def collect_files(frontend_dir):
    files = []
    for root, _, filenames in os.walk(frontend_dir):
        for name in filenames:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, os.path.dirname(frontend_dir))
            # We want paths that include the `frontend/` prefix
            rel_path = os.path.join('frontend', os.path.relpath(full, frontend_dir)).replace('\\', '/')
            with open(full, 'rb') as f:
                data = f.read()
            files.append({
                'file': rel_path,
                'data': base64.b64encode(data).decode('ascii')
            })
    return files

def include_root_file(repo_root, files, filename):
    path = os.path.join(repo_root, filename)
    if os.path.isfile(path):
        with open(path, 'rb') as f:
            data = f.read()
        files.append({
            'file': filename.replace('\\', '/'),
            'data': base64.b64encode(data).decode('ascii')
        })
        print(f'Included root file: {filename}')
    else:
        print(f'Root file not found: {filename}')

def deploy(token, project_name):
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    frontend_dir = os.path.join(repo_root, 'frontend')
    if not os.path.isdir(frontend_dir):
        print('Error: frontend directory not found at', frontend_dir)
        sys.exit(1)

    files = collect_files(frontend_dir)
    # Ensure vercel.json (and other root config) is included so routing/builds are applied
    include_root_file(repo_root, files, 'vercel.json')
    print(f'Preparing deployment: project={project_name}, files={len(files)}')
    payload = {
        'name': project_name,
        'files': files,
        'target': 'production'
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        'https://api.vercel.com/v13/deployments?skipAutoDetectionConfirmation=1',
        data=data,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    )

    try:
        print('Sending request to https://api.vercel.com/v13/deployments?skipAutoDetectionConfirmation=1')
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode('utf-8')
            print('Response length:', len(body))
            print('Response snippet:', body[:1000])
            j = json.loads(body)
            if 'url' in j:
                print('Deployment URL: https://' + j['url'])
            elif 'previewUrl' in j:
                print('Preview URL:', j['previewUrl'])
            else:
                print('Deployment created, check Vercel dashboard for details.')
    except urllib.error.HTTPError as e:
        print('HTTPError:', e.code, e.reason)
        try:
            print(e.read().decode())
        except Exception:
            pass
        sys.exit(1)
    except Exception as e:
        print('Unexpected error:', type(e).__name__, str(e))
        sys.exit(1)

if __name__ == '__main__':
    token = os.environ.get('VERCEL_TOKEN')
    if not token:
        if len(sys.argv) > 1:
            token = sys.argv[1]
        else:
            print('Usage: set VERCEL_TOKEN env var or pass token as first arg')
            sys.exit(1)

    raw_name = os.path.basename(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    # Sanitize project name: lowercase, allow only letters, digits, '.', '_', '-' and collapse runs of '-' 
    name = raw_name.lower()
    name = re.sub(r'[^a-z0-9._-]', '-', name)
    name = re.sub(r'-{2,}', '-', name)
    if len(name) > 100:
        name = name[:100]
    deploy(token, name)
