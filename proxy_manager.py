"""
proxy_manager.py — Multi-ISP Proxy Manager
Handles: parsing, health-check, ISP detection, ISP deduplication
"""
import requests
import os
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


# ─── Parse ────────────────────────────────────────────────────────────────────

def parse_proxy(proxy_str):
    """Parse 'IP:PORT:USER:PASS' or 'IP:PORT' into a dict."""
    proxy_str = proxy_str.strip()
    if not proxy_str:
        return None
    parts = proxy_str.split(':', 3)
    if len(parts) < 2:
        return None
    return {
        'raw': proxy_str,
        'ip': parts[0],
        'port': parts[1],
        'user': parts[2] if len(parts) > 2 else '',
        'pass': parts[3] if len(parts) > 3 else '',
    }


def build_proxy_url(p):
    """Build requests-compatible proxy URL from parsed proxy dict."""
    if p['user']:
        return f"http://{p['user']}:{p['pass']}@{p['ip']}:{p['port']}"
    return f"http://{p['ip']}:{p['port']}"


# ─── Health Check ──────────────────────────────────────────────────────────────

def check_proxy_alive(proxy_str, timeout=10):
    """
    Test if a proxy is alive by making a request through it.
    Returns True if alive, False if dead.
    """
    p = parse_proxy(proxy_str)
    if not p:
        return False
    proxy_url = build_proxy_url(p)
    proxies = {'http': proxy_url, 'https': proxy_url}
    try:
        r = requests.get(
            'http://ip-api.com/json',
            proxies=proxies,
            timeout=timeout,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        return r.status_code == 200
    except Exception:
        return False


def check_proxies_batch(proxy_list, timeout=10, max_workers=5):
    """
    Check a list of proxy strings in parallel.
    Returns list of dicts: {raw, alive, isp, org, country}
    """
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(check_and_detect, p, timeout): p for p in proxy_list}
        for future in as_completed(futures):
            results.append(future.result())
    return results


# ─── ISP Detection ─────────────────────────────────────────────────────────────

def detect_isp(ip, proxy_str=None, timeout=10):
    """
    Query ip-api.com through the proxy itself to detect outgoing ISP.
    If proxy_str is None, queries directly.
    Returns dict: {isp, org, country, query_ip}
    """
    url = f'http://ip-api.com/json/{ip}'
    try:
        if proxy_str:
            p = parse_proxy(proxy_str)
            proxy_url = build_proxy_url(p)
            proxies = {'http': proxy_url, 'https': proxy_url}
            # Query with no IP to get the proxy's outgoing IP/ISP
            r = requests.get(
                'http://ip-api.com/json',
                proxies=proxies,
                timeout=timeout,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
        else:
            r = requests.get(url, timeout=timeout)
        data = r.json()
        return {
            'isp': data.get('isp', 'Unknown'),
            'org': data.get('org', ''),
            'country': data.get('country', ''),
            'query_ip': data.get('query', ip),
            'region': data.get('regionName', ''),
        }
    except Exception as e:
        return {'isp': 'Unknown', 'org': '', 'country': '', 'query_ip': ip, 'region': ''}


def check_and_detect(proxy_str, timeout=10):
    """
    Combined: check alive + detect ISP via the proxy.
    Returns full info dict.
    """
    p = parse_proxy(proxy_str)
    if not p:
        return {'raw': proxy_str, 'alive': False, 'isp': 'Invalid', 'org': '', 'country': '', 'query_ip': ''}

    proxy_url = build_proxy_url(p)
    proxies = {'http': proxy_url, 'https': proxy_url}

    # Try multiple test URLs in case one is blocked by the proxy provider
    TEST_URLS = [
        'https://ipinfo.io/json',
        'http://ip-api.com/json',
        'https://httpbin.org/ip',
    ]
    last_exc = None
    for test_url in TEST_URLS:
        try:
            r = requests.get(
                test_url,
                proxies=proxies,
                timeout=timeout,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            if r.status_code == 200:
                try:
                    data = r.json()
                except Exception:
                    data = {}
                return {
                    'raw': proxy_str,
                    'ip': p['ip'],
                    'port': p['port'],
                    'alive': True,
                'isp': data.get('isp', data.get('org', 'Unknown')),
                'org': data.get('org', ''),
                'country': data.get('country', data.get('countryCode', 'VN')),
                'query_ip': data.get('query', data.get('ip', p['ip'])),
                'region': data.get('regionName', data.get('region', '')),
                }
        except Exception as e:
            last_exc = e
            continue

    # Alive check failed — try direct ISP detect from proxy IP
    isp_info = detect_isp(p['ip'], proxy_str=None, timeout=5)
    return {
        'raw': proxy_str,
        'ip': p['ip'],
        'port': p['port'],
        'alive': False,
        'isp': isp_info.get('isp', 'Unknown'),
        'org': isp_info.get('org', ''),
        'country': isp_info.get('country', ''),
        'query_ip': p['ip'],
        'region': isp_info.get('region', ''),
    }


# ─── ISP Deduplication ─────────────────────────────────────────────────────────

def get_unique_isp_proxies(proxy_results):
    """
    From a list of check_and_detect results, keep one live proxy per ISP.
    Prioritises alive proxies. Returns list of dicts.
    """
    seen_isps = {}
    for r in proxy_results:
        isp = r.get('isp', 'Unknown')
        if isp == 'Unknown' or not isp:
            continue
        if isp not in seen_isps:
            seen_isps[isp] = r
        else:
            # Prefer alive over dead
            if r.get('alive') and not seen_isps[isp].get('alive'):
                seen_isps[isp] = r
    return list(seen_isps.values())


# ─── CLI Test ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    test_proxies = [
        '171.236.112.121:14617:ifqre_hackm:SRomhUsZ',
        '160.25.76.230:8589:X6geihackm:xc57GFSM',
        '160.25.77.92:8894:Fxqh2hackm:FoTjMU0s',
        '103.171.1.4:8003:K4Fhihackm:BfHzWnnR',
        '103.232.53.8:8590:CvtVLs4.1:NQ45lOvb',
        '113.190.132.40:40012:xhuwi_s4.1:VWq9vOyf',
        '160.191.17.98:44823:2511scoyj0:2511scoyj0',
        '160.191.16.26:44823:2511scoyj0:2511scoyj0',
        '160.191.17.26:44823:2511scoyj0:2511scoyj0',
    ]

    print('Checking proxies...')
    results = check_proxies_batch(test_proxies, timeout=12)

    print('\n=== ALL PROXIES ===')
    for r in results:
        status = '✅' if r['alive'] else '❌'
        print(f"{status} {r['ip']:20s} | ISP: {r['isp']:30s} | {r['country']}")

    print('\n=== UNIQUE ISP (alive first) ===')
    unique = get_unique_isp_proxies(results)
    for r in unique:
        status = '✅' if r['alive'] else '❌'
        print(f"{status} {r['raw'][:30]:32s} | ISP: {r['isp']}")
