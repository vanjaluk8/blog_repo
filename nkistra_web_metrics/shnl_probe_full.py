#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests

CLUBS = [
    ('Dinamo', 'https://gnkdinamo.hr/'),
    ('Hajduk', 'https://hajduk.hr/'),
    ('Rijeka', 'https://nk-rijeka.hr/'),
    ('Varaždin', 'https://nk-varazdin.hr/'),
    ('Slaven Belupo', 'https://nk-slaven-belupo.hr/'),
    ('Lokomotiva', 'https://nklokomotiva.hr/'),
    ('Osijek', 'http://nk-osijek.hr/'),
    ('Istra 1961', 'https://nkistra.com/'),
    ('Vukovar', 'https://hnk-vukovar1991.hr/'),
    ('Gorica', 'https://hnk-gorica.hr/'),
]

CURL_FORMAT_JSON = '%{json}'
PSI_ENDPOINT = 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed'


def to_float(value):
    try:
        return float(value)
    except Exception:
        return ''


def pick_numeric(d, *keys):
    for key in keys:
        val = d.get(key)
        if isinstance(val, (int, float)):
            return val
    return ''


def get_host_ip(host):
    try:
        return socket.gethostbyname(host)
    except Exception:
        return ''


def ip_enrichment(ip, session):
    if not ip:
        return {'provider': '', 'country': '', 'asn': '', 'whois_excerpt': ''}

    provider = country = asn = whois_excerpt = ''
    for endpoint in [f'https://ipwho.is/{ip}', f'https://ipapi.co/{ip}/json/']:
        try:
            r = session.get(endpoint, timeout=20)
            data = r.json()
            if endpoint.startswith('https://ipwho.is') and data.get('success') is False:
                continue
            provider = data.get('connection', {}).get('isp') or data.get('org') or data.get('asn_description') or data.get('isp') or ''
            country = data.get('country_code') or data.get('country') or data.get('asn_country_code') or ''
            asn = str(data.get('connection', {}).get('asn') or data.get('asn') or '')
            whois_excerpt = json.dumps(data, ensure_ascii=False)[:500]
            if provider or country or asn:
                return {'provider': provider, 'country': country, 'asn': asn, 'whois_excerpt': whois_excerpt}
        except Exception:
            pass

    try:
        p = subprocess.run(['whois', ip], capture_output=True, text=True, timeout=25)
        txt = p.stdout
        whois_excerpt = txt[:500]
        pm = re.search(r'(?im)^(?:OrgName|org-name|organisation|Organization|owner|descr):\s*(.+)$', txt)
        cm = re.search(r'(?im)^country:\s*([A-Z]{2}|[A-Za-z ]+)$', txt)
        am = re.search(r'(?im)^(?:origin|originas):\s*(AS\d+)$', txt)
        if pm:
            provider = pm.group(1).strip()
        if cm:
            country = cm.group(1).strip()
        if am:
            asn = am.group(1).strip()
    except Exception:
        pass

    return {'provider': provider, 'country': country, 'asn': asn, 'whois_excerpt': whois_excerpt}


def curl_metrics(url):
    try:
        p = subprocess.run(['curl', '-L', '-w', CURL_FORMAT_JSON, '-o', '/dev/null', '-s', url], capture_output=True, text=True, timeout=60)
        if p.returncode != 0:
            return {'curl_status': 'error', 'curl_error': (p.stderr or p.stdout).strip()}
        data = json.loads(p.stdout)
    except Exception as e:
        return {'curl_status': 'error', 'curl_error': str(e)}

    t_namelookup = to_float(data.get('time_namelookup'))
    t_connect = to_float(data.get('time_connect'))
    t_appconnect = to_float(data.get('time_appconnect'))
    t_pretransfer = to_float(data.get('time_pretransfer'))
    t_starttransfer = to_float(data.get('time_starttransfer'))
    t_total = to_float(data.get('time_total'))

    def delta(a, b):
        if a == '' or b == '':
            return ''
        return round(a - b, 6)

    return {
        'curl_status': 'ok',
        'curl_error': '',
        'curl_effective_url': data.get('url_effective', ''),
        'curl_response_code': data.get('response_code', data.get('http_code', '')),
        'curl_http_version': data.get('http_version', ''),
        'curl_scheme': data.get('scheme', ''),
        'curl_content_type': data.get('content_type', ''),
        'curl_remote_ip': data.get('remote_ip', ''),
        'curl_remote_port': data.get('remote_port', ''),
        'curl_local_ip': data.get('local_ip', ''),
        'curl_local_port': data.get('local_port', ''),
        'curl_num_redirects': data.get('num_redirects', ''),
        'curl_num_connects': data.get('num_connects', ''),
        'curl_size_download_bytes': data.get('size_download', ''),
        'curl_size_header_bytes': data.get('size_header', ''),
        'curl_size_request_bytes': data.get('size_request', ''),
        'curl_speed_download_bytes_s': data.get('speed_download', ''),
        'curl_ssl_verify_result': data.get('ssl_verify_result', ''),
        'curl_time_namelookup_s': t_namelookup,
        'curl_time_connect_s': t_connect,
        'curl_time_appconnect_s': t_appconnect,
        'curl_time_pretransfer_s': t_pretransfer,
        'curl_time_starttransfer_s': t_starttransfer,
        'curl_time_total_s': t_total,
        'curl_dns_s': t_namelookup,
        'curl_tcp_handshake_s': delta(t_connect, t_namelookup),
        'curl_tls_handshake_s': delta(t_appconnect, t_connect),
        'curl_pretransfer_after_tls_s': delta(t_pretransfer, t_appconnect),
        'curl_ttfb_after_connect_s': delta(t_starttransfer, t_pretransfer),
        'curl_download_time_s': delta(t_total, t_starttransfer),
        'curl_raw_json': json.dumps(data, ensure_ascii=False)[:800],
    }


def run_lighthouse(url, preset='desktop'):
    lighthouse_bin = shutil.which('lighthouse')
    if not lighthouse_bin:
        return {'lighthouse_status': 'missing', 'lighthouse_error': 'Lighthouse CLI nije instaliran'}

    chrome_flags = '--headless --no-sandbox --disable-dev-shm-usage'
    try:
        with tempfile.TemporaryDirectory() as td:
            out_json = Path(td) / 'report.json'
            cmd = [
                lighthouse_bin,
                url,
                '--quiet',
                '--no-update-notifier',
                '--no-enable-error-reporting',
                '--output=json',
                f'--output-path={out_json}',
                f'--preset={preset}',
                f'--chrome-flags={chrome_flags}',
            ]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if p.returncode != 0 or not out_json.exists():
                return {'lighthouse_status': 'error', 'lighthouse_error': (p.stderr or p.stdout).strip()}
            report = json.loads(out_json.read_text(encoding='utf-8'))
    except Exception as e:
        return {'lighthouse_status': 'error', 'lighthouse_error': str(e)}

    audits = report.get('audits', {})
    categories = report.get('categories', {})
    score = categories.get('performance', {}).get('score')
    if score is not None:
        score = round(score * 100, 2)

    return {
        'lighthouse_status': 'ok',
        'lighthouse_error': '',
        'lighthouse_final_url': report.get('finalUrl', ''),
        'lighthouse_fetch_time': report.get('fetchTime', ''),
        'lighthouse_version': report.get('lighthouseVersion', ''),
        'lighthouse_performance_score': score,
        'lh_fcp_ms': pick_numeric(audits.get('first-contentful-paint', {}), 'numericValue'),
        'lh_lcp_ms': pick_numeric(audits.get('largest-contentful-paint', {}), 'numericValue'),
        'lh_speed_index_ms': pick_numeric(audits.get('speed-index', {}), 'numericValue'),
        'lh_tbt_ms': pick_numeric(audits.get('total-blocking-time', {}), 'numericValue'),
        'lh_cls': pick_numeric(audits.get('cumulative-layout-shift', {}), 'numericValue'),
        'lh_tti_ms': pick_numeric(audits.get('interactive', {}), 'numericValue'),
        'lh_server_response_time_ms': pick_numeric(audits.get('server-response-time', {}), 'numericValue'),
        'lh_network_requests': len(audits.get('network-requests', {}).get('details', {}).get('items', [])) or '',
        'lh_total_byte_weight_bytes': pick_numeric(audits.get('total-byte-weight', {}), 'numericValue'),
        'lh_dom_size_elements': pick_numeric(audits.get('dom-size', {}), 'numericValue'),
        'lh_render_blocking_resources_ms': pick_numeric(audits.get('render-blocking-resources', {}), 'numericValue'),
        'lh_unused_javascript_bytes': audits.get('unused-javascript', {}).get('details', {}).get('overallSavingsBytes', ''),
        'lh_unused_css_bytes': audits.get('unused-css-rules', {}).get('details', {}).get('overallSavingsBytes', ''),
        'lh_mainthread_work_breakdown_ms': pick_numeric(audits.get('mainthread-work-breakdown', {}), 'numericValue'),
        'lh_bootup_time_ms': pick_numeric(audits.get('bootup-time', {}), 'numericValue'),
        'lh_max_potential_fid_ms': pick_numeric(audits.get('max-potential-fid', {}), 'numericValue'),
        'lh_lcp_element': audits.get('largest-contentful-paint-element', {}).get('displayValue', ''),
    }


def run_pagespeed_field_data(url, strategy, api_key, session):
    if not api_key:
        return {
            f'psi_{strategy}_status': 'skipped',
            f'psi_{strategy}_error': 'Nema PSI_API_KEY',
        }
    try:
        r = session.get(PSI_ENDPOINT, params={
            'url': url,
            'key': api_key,
            'strategy': strategy,
            'category': 'performance'
        }, timeout=180)
        if not r.ok:
            return {
                f'psi_{strategy}_status': 'error',
                f'psi_{strategy}_error': f'HTTP {r.status_code}: {r.text[:200]}'
            }
        data = r.json()
    except Exception as e:
        return {
            f'psi_{strategy}_status': 'error',
            f'psi_{strategy}_error': str(e)
        }

    field = data.get('loadingExperience', {}).get('metrics', {})
    origin = data.get('originLoadingExperience', {}).get('metrics', {})
    lighthouse = data.get('lighthouseResult', {}).get('audits', {})

    def field_metric(source, name):
        metric = source.get(name, {})
        return metric.get('percentile', '')

    def field_category(source, name):
        metric = source.get(name, {})
        return metric.get('category', '')

    return {
        f'psi_{strategy}_status': 'ok',
        f'psi_{strategy}_error': '',
        f'psi_{strategy}_lab_fcp_ms': pick_numeric(lighthouse.get('first-contentful-paint', {}), 'numericValue'),
        f'psi_{strategy}_lab_lcp_ms': pick_numeric(lighthouse.get('largest-contentful-paint', {}), 'numericValue'),
        f'psi_{strategy}_lab_cls': pick_numeric(lighthouse.get('cumulative-layout-shift', {}), 'numericValue'),
        f'psi_{strategy}_lab_tbt_ms': pick_numeric(lighthouse.get('total-blocking-time', {}), 'numericValue'),
        f'psi_{strategy}_field_lcp_p75_ms': field_metric(field, 'LARGEST_CONTENTFUL_PAINT_MS'),
        f'psi_{strategy}_field_cls_p75': field_metric(field, 'CUMULATIVE_LAYOUT_SHIFT_SCORE'),
        f'psi_{strategy}_field_inp_p75_ms': field_metric(field, 'INTERACTION_TO_NEXT_PAINT'),
        f'psi_{strategy}_field_fcp_p75_ms': field_metric(field, 'FIRST_CONTENTFUL_PAINT_MS'),
        f'psi_{strategy}_field_ttfb_p75_ms': field_metric(field, 'EXPERIMENTAL_TIME_TO_FIRST_BYTE'),
        f'psi_{strategy}_field_lcp_category': field_category(field, 'LARGEST_CONTENTFUL_PAINT_MS'),
        f'psi_{strategy}_field_cls_category': field_category(field, 'CUMULATIVE_LAYOUT_SHIFT_SCORE'),
        f'psi_{strategy}_field_inp_category': field_category(field, 'INTERACTION_TO_NEXT_PAINT'),
        f'psi_{strategy}_origin_lcp_p75_ms': field_metric(origin, 'LARGEST_CONTENTFUL_PAINT_MS'),
        f'psi_{strategy}_origin_cls_p75': field_metric(origin, 'CUMULATIVE_LAYOUT_SHIFT_SCORE'),
        f'psi_{strategy}_origin_inp_p75_ms': field_metric(origin, 'INTERACTION_TO_NEXT_PAINT'),
    }


def run_all(out_csv, preset='desktop', psi_api_key=None, include_psi_mobile=False, include_psi_desktop=False):
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    rows = []

    total = len(CLUBS)
    print(f"Starting probe for {total} clubs (preset={preset}, psi_mobile={include_psi_mobile}, psi_desktop={include_psi_desktop})")

    for i, (club, url) in enumerate(CLUBS, 1):
        print(f"\n[{i}/{total}] {club} — {url}")

        host = urlparse(url).hostname or ''
        ip = get_host_ip(host)
        print(f"  DNS resolved: {host} -> {ip or 'FAILED'}")

        row = {
            'club': club,
            'website': url,
            'host': host,
            'resolved_ip': ip,
        }

        print(f"  IP enrichment...")
        row.update(ip_enrichment(ip, session))
        print(f"    provider={row.get('provider') or '-'}, country={row.get('country') or '-'}, asn={row.get('asn') or '-'}")

        print(f"  curl metrics...")
        curl = curl_metrics(url)
        row.update(curl)
        if curl.get('curl_status') == 'ok':
            print(f"    status={curl.get('curl_response_code')}, total={curl.get('curl_time_total_s')}s, ttfb={curl.get('curl_ttfb_after_connect_s')}s")
        else:
            print(f"    ERROR: {curl.get('curl_error')}")

        print(f"  Lighthouse ({preset})...")
        lh = run_lighthouse(url, preset=preset)
        row.update(lh)
        if lh.get('lighthouse_status') == 'ok':
            print(f"    performance={lh.get('lighthouse_performance_score')}, FCP={lh.get('lh_fcp_ms')}ms, LCP={lh.get('lh_lcp_ms')}ms")
        else:
            print(f"    {lh.get('lighthouse_status')}: {lh.get('lighthouse_error')}")

        if include_psi_mobile:
            print(f"  PSI mobile...")
            psi = run_pagespeed_field_data(url, 'mobile', psi_api_key, session)
            row.update(psi)
            status = psi.get('psi_mobile_status')
            if status == 'ok':
                print(f"    LCP={psi.get('psi_mobile_field_lcp_p75_ms')}ms, CLS={psi.get('psi_mobile_field_cls_p75')}, INP={psi.get('psi_mobile_field_inp_p75_ms')}ms")
            else:
                print(f"    {status}: {psi.get('psi_mobile_error')}")

        if include_psi_desktop:
            print(f"  PSI desktop...")
            psi = run_pagespeed_field_data(url, 'desktop', psi_api_key, session)
            row.update(psi)
            status = psi.get('psi_desktop_status')
            if status == 'ok':
                print(f"    LCP={psi.get('psi_desktop_field_lcp_p75_ms')}ms, CLS={psi.get('psi_desktop_field_cls_p75')}, INP={psi.get('psi_desktop_field_inp_p75_ms')}ms")
            else:
                print(f"    {status}: {psi.get('psi_desktop_error')}")

        rows.append(row)

    fieldnames = []
    for row in rows:
        for k in row.keys():
            if k not in fieldnames:
                fieldnames.append(k)

    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Results saved to: {out_csv}")
    return out_csv


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Konačna SHNL skripta: DNS/IP/WHOIS + curl mrežne metrike + Lighthouse browser metrike + opcionalno PageSpeed field data.')
    parser.add_argument('--out', default='output/shnl_full_metrics.csv')
    parser.add_argument('--preset', default='desktop', choices=['desktop', 'perf'])
    parser.add_argument('--psi-api-key', default=os.getenv('PSI_API_KEY', ''))
    parser.add_argument('--psi-mobile', action='store_true')
    parser.add_argument('--psi-desktop', action='store_true')
    args = parser.parse_args()

    out = run_all(
        out_csv=args.out,
        preset=args.preset,
        psi_api_key=args.psi_api_key,
        include_psi_mobile=args.psi_mobile,
        include_psi_desktop=args.psi_desktop,
    )
    print(out)
