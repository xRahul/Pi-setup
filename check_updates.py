import urllib.request
import json
import re
import sys

def get_token_and_tags_url(registry, image):
    if registry == 'docker.io':
        # Docker Hub API is different
        if '/' not in image:
            image = 'library/' + image
        return None, f"https://hub.docker.com/v2/repositories/{image}/tags?page_size=100&ordering=last_updated"
    
    # Generic OCI / Docker V2 Registry logic (GHCR, etc.)
    base_url = f"https://{registry}/v2"
    auth_url = base_url
    
    try:
        req = urllib.request.Request(base_url)
        with urllib.request.urlopen(req) as response:
            pass # Should verify connection
    except urllib.error.HTTPError as e:
        if e.code == 401:
            auth_header = e.headers.get('Www-Authenticate')
            if auth_header:
                # Parse Bearer realm="..." service="..."
                # Example: Bearer realm="https://ghcr.io/token",service="ghcr.io",scope="repository:user/image:pull"
                realm_match = re.search(r'realm="([^"]+)"', auth_header)
                service_match = re.search(r'service="([^"]+)"', auth_header)
                
                if realm_match:
                    realm = realm_match.group(1)
                    service = service_match.group(1) if service_match else registry
                    scope = f"repository:{image}:pull"
                    
                    token_url = f"{realm}?service={service}&scope={scope}"
                    # print(f"Getting token from {token_url} for {registry}/{image}...", file=sys.stderr)
                    
                    try:
                        with urllib.request.urlopen(token_url) as token_resp:
                            token_data = json.load(token_resp)
                            token = token_data.get('token') or token_data.get('access_token')
                            tags_url = f"https://{registry}/v2/{image}/tags/list"
                            return token, tags_url
                    except Exception as token_err:
                        print(f"Error getting token for {image}: {token_err}", file=sys.stderr)
                        return None, None
    except Exception as e:
        print(f"Error connecting to {registry}: {e}", file=sys.stderr)
        
    return None, None

def fetch_tags(full_image_name):
    parts = full_image_name.split('/')
    if '.' in parts[0] and 'docker.io' not in parts[0] and parts[0] != 'docker.io':
        registry = parts[0]
        image = '/'.join(parts[1:])
    else:
        registry = 'docker.io'
        image = full_image_name
        if registry == 'docker.io' and full_image_name.startswith('docker.io/'):
             image = full_image_name[len('docker.io/'):]

    token, url = get_token_and_tags_url(registry, image)
    
    if not url:
        return []

    req = urllib.request.Request(url)
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.load(response)
            if registry == 'docker.io':
                # Docker Hub returns a list of objects in 'results'
                return [t['name'] for t in data.get('results', [])]
            else:
                # OCI returns 'tags' list
                return data.get('tags', [])
    except Exception as e:
        print(f"Failed to fetch tags for {full_image_name}: {e}", file=sys.stderr)
        return []

def is_stable(tag):
    # Filter out alpha, beta, rc, nightly, etc.
    # Allow dates like 2025.08.0
    if re.search(r'(alpha|beta|rc|nightly|dev|test|preview|snapshot|master|latest|sha256)', tag, re.IGNORECASE):
        return False
    return True

def sort_tags(tags):
    # Try to parse semantic versions or date versions
    # We want to sort descending
    
    parsed_tags = []
    for tag in tags:
        if not is_stable(tag):
            continue
            
        # Clean tag for parsing
        clean_tag = tag.lstrip('v')
        
        # Try to match semver-ish (num.num.num) or date-ish (num.num.num)
        # We replace delimiters with dots to standardize
        parts = re.split(r'[.-]', clean_tag)
        
        try:
            # Convert parts to integers where possible
            int_parts = [int(p) for p in parts if p.isdigit()]
            if int_parts:
                parsed_tags.append((int_parts, tag))
        except ValueError:
            pass
            
    # Sort by the integer parts, descending
    parsed_tags.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in parsed_tags]

def get_compose_images():
    try:
        import yaml
    except ImportError:
        print("PyYAML required to parse docker-compose.yml", file=sys.stderr)
        return []

    try:
        with open("docker-compose.yml") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"Error reading docker-compose.yml: {e}", file=sys.stderr)
        return []

    services = data.get("services", {})
    images = []
    seen = set()
    for sname, sdata in services.items():
        img = sdata.get("image")
        if not img or ":" not in img:
            continue
        if "@sha256" in img:
            img = img.split("@sha256")[0]
        full_img, tag = img.rsplit(":", 1)
        if full_img in ("homelab-caddy", "rahul/antigravity-web"):
            continue
        key = (full_img, tag)
        if key not in seen:
            seen.add(key)
            images.append({"service": sname, "image": full_img, "current": tag})
    return images

def main():
    images_to_check = get_compose_images()
    print(f"Checking for updates across {len(images_to_check)} compose images...")
    for item in images_to_check:
        full_image = item["image"]
        current_tag = item["current"]
        
        print(f"Checking {full_image} (current: {current_tag})...")
        tags = fetch_tags(full_image)
        sorted_stable_tags = sort_tags(tags)
        
        if sorted_stable_tags:
            latest_tag = sorted_stable_tags[0]
            if current_tag == 'latest':
                print(f"UPDATE_FOUND: {item['service']} | {full_image} | {current_tag} -> {latest_tag}")
            elif current_tag != latest_tag:
                def parse(t):
                    return [int(p) for p in re.split(r'[.-]', t.lstrip('v')) if p.isdigit()]
                
                curr_ver = parse(current_tag)
                new_ver = parse(latest_tag)
                
                if new_ver > curr_ver:
                    print(f"UPDATE_FOUND: {item['service']} | {full_image} | {current_tag} -> {latest_tag}")
                else:
                    print(f"UP_TO_DATE: {item['service']} | {full_image} | {current_tag}")
            else:
                print(f"UP_TO_DATE: {item['service']} | {full_image} | {current_tag}")
        else:
            print(f"ERROR: Could not fetch tags for {full_image}")

if __name__ == '__main__':
    main()
