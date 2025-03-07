import sys
import os
import logging
import random
import asyncio
import aioboto3
from aiohttp import web

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(open('/dev/stdout', 'a'))])

def get_env_list(var_name):
    return [val.strip() for val in os.getenv(var_name, "").split(",") if val.strip()]

def get_env_int(var_name, default):
    try:
        return int(os.getenv(var_name, default))
    except ValueError:
        return default

EXCLUDED_SUBSTRINGS = get_env_list("EXCLUDED_SUBSTRINGS")
EXCLUDED_PREFIXES = get_env_list("EXCLUDED_PREFIXES")
EXCLUDED_SUFFIXES = get_env_list("EXCLUDED_SUFFIXES")
EXCLUDED_RECORD_SUBSTRINGS = get_env_list("EXCLUDED_RECORD_SUBSTRINGS")
EXCLUDED_IP_PREFIXES = get_env_list("EXCLUDED_IP_PREFIXES")

HOSTED_ZONE_IDS = get_env_list("ROUTE53_HOSTED_ZONES")

MAX_CONCURRENT_REQUESTS = get_env_int("MAX_CONCURRENT_REQUESTS", 2)
DNS_CACHE_REFRESH_INTERVAL = get_env_int("DNS_CACHE_REFRESH_INTERVAL", 900)
MAX_BACKOFF_WAIT = get_env_int("MAX_BACKOFF_WAIT", 60)

# AWS Route 53 Client Session
session = aioboto3.Session()

# Cache
dns_cache = []
cache_lock = asyncio.Lock()

# Semaphore to limit concurrent AWS API requests
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

async def fetch_dns_records():
    global dns_cache
    all_records = []

    async def fetch_from_zone(zone_id):
        async with semaphore:
            async with session.client('route53') as client:
                paginator = client.get_paginator('list_resource_record_sets')
                retries = 5

                for attempt in range(retries):
                    try:
                        logging.debug(f"Fetching records for zone {zone_id} (Attempt {attempt + 1})")
                        async for page in paginator.paginate(HostedZoneId=zone_id):
                            for record in page['ResourceRecordSets']:
                                if record['Type'] in ['A', 'CNAME']:
                                    domain_name = record['Name'].rstrip('.')
                                    record_type = record['Type']
                                    resource_record = record.get('ResourceRecords', [{}])[0].get('Value', '')
                                    hosted_zone = zone_id

                                    # Apply exclusions
                                    if any(substr in domain_name for substr in EXCLUDED_SUBSTRINGS):
                                        logging.debug(f"Excluded by EXCLUDED_SUBSTRINGS: {domain_name} - {resource_record}")
                                        continue
                                    if any(domain_name.startswith(pref) for pref in EXCLUDED_PREFIXES):
                                        logging.debug(f"Excluded by EXCLUDED_PREFIXES: {domain_name} - {resource_record}")
                                        continue
                                    if any(domain_name.endswith(suffix) for suffix in EXCLUDED_SUFFIXES):
                                        logging.debug(f"Excluded by EXCLUDED_SUFFIXES: {domain_name} - {resource_record}")
                                        continue
                                    if any(substr in resource_record for substr in EXCLUDED_RECORD_SUBSTRINGS):
                                        logging.debug(f"Excluded by EXCLUDED_RECORD_SUBSTRINGS: {domain_name} - {resource_record}")
                                        continue
                                    if any(resource_record.endswith(suffix) for suffix in EXCLUDED_SUFFIXES):
                                        logging.debug(f"Excluded by EXCLUDED_SUFFIXES (Resource Record): {domain_name} - {resource_record}")
                                        continue
                                    if any(resource_record.startswith(ip) for ip in EXCLUDED_IP_PREFIXES):
                                        logging.debug(f"Excluded by EXCLUDED_IP_PREFIXES: {domain_name} - {resource_record}")
                                        continue

                                    # Format the record to match the desired output
                                    all_records.append({
                                        "targets": [f"https://{domain_name}"],
                                        "labels": {
                                            "hosted_zone": hosted_zone,
                                            "record": resource_record,
                                            "type": record_type
                                        }
                                    })

                        break

                    except Exception as e:
                        wait_time = min(MAX_BACKOFF_WAIT, 2 ** attempt + random.uniform(0, 2))
                        logging.warning(f"Error: {e}. Retrying in {wait_time:.2f} seconds...")
                        await asyncio.sleep(wait_time)

    tasks = [fetch_from_zone(zone_id) for zone_id in HOSTED_ZONE_IDS]
    await asyncio.gather(*tasks)

    async with cache_lock:
        dns_cache.clear()
        dns_cache.extend(all_records)
        logging.info(f"DNS cache updated with {len(dns_cache)} entries")

async def update_dns_cache():
    while True:
        try:
            await fetch_dns_records()
        except Exception as e:
            logging.error(f"Error updating DNS cache: {e}")
        logging.info(f"Waiting {DNS_CACHE_REFRESH_INTERVAL} seconds before next update...")
        await asyncio.sleep(DNS_CACHE_REFRESH_INTERVAL)

async def dns_targets(request):
    async with cache_lock:
        return web.json_response(dns_cache)

async def home(request):
    return web.Response(text="Welcome to DNS Exporter", content_type="text/plain")

async def metrics(request):
    metrics_data = "# HELP dns_exporter_total_records Total number of DNS records fetched\n"
    async with cache_lock:
        metrics_data += f"# TYPE dns_exporter_total_records gauge\ndns_exporter_total_records {len(dns_cache)}\n"
    return web.Response(text=metrics_data, content_type="text/plain")

app = web.Application()
app.router.add_get('/', home)
app.router.add_get('/metrics', metrics)
app.router.add_get('/dns_targets', dns_targets)

async def start_background_tasks(app):
    app['update_task'] = asyncio.create_task(update_dns_cache())

app.on_startup.append(start_background_tasks)

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=80)

