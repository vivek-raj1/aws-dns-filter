# AWS DNS FILTER

AWS DNS FILTER is a lightweight exporter that fetches DNS records from AWS Route 53 and exposes them as a Prometheus-compatible endpoint.

## Features

- Fetches A and CNAME records from specified Route 53 hosted zones.
- Filters records based on configurable exclusion criteria.
- Caches DNS records to reduce API calls.
- Exposes metrics for Prometheus monitoring.

## Installation

### Prerequisites

- Python 3.8+
- AWS credentials configured for accessing Route 53
- Required Python packages: `aioboto3`, `aiohttp`

### Setup

1. Clone the repository:

   ```sh
   git clone git@github.com:vivek-raj1/aws-dns-filter.git
   cd aws-dns-filter
   ```

2. Install dependencies:

   ```sh
   pip install -r requirements.txt
   ```

3. Set environment variables:

   ```sh
   export ROUTE53_HOSTED_ZONES="hosted_zone_id1,hosted_zone_id2"
   export EXCLUDED_SUBSTRINGS="example1,example2"
   export EXCLUDED_PREFIXES="prefix1,prefix2"
   export EXCLUDED_SUFFIXES="suffix1,suffix2"
   export EXCLUDED_IP_PREFIXES="10.50.,172.16."
   ```

4. Run the exporter:

   ```sh
   python dns_exporter.py
   ```

## Endpoints

- `/` - Health check endpoint
- `/metrics` - Prometheus metrics endpoint
- `/dns_targets` - JSON API returning DNS records

## Configuration

You can configure exclusions using environment variables:

- `EXCLUDED_SUBSTRINGS` - List of substrings to exclude.
- `EXCLUDED_PREFIXES` - List of prefixes to exclude.
- `EXCLUDED_SUFFIXES` - List of suffixes to exclude.
- `EXCLUDED_IP_PREFIXES` - List of IP prefixes to exclude.

## Deployment

You can run the exporter as a Docker container:

```sh
docker build -t dns-exporter .
docker run -p 80:80 -e ROUTE53_HOSTED_ZONES="hosted_zone_id" dns-exporter
```
