#!/usr/bin/env python3
""" It is nice having a list of all the IAM actions in a text file """
import os
import json
from concurrent import futures
import requests
from bs4 import BeautifulSoup
import os.path


def ensure_dir(file):
    dir = os.path.dirname(os.path.expanduser(file))
    os.makedirs(dir, exist_ok=True)

def parse_services(response):
    soup = BeautifulSoup(response.text, 'html.parser')
    return [a['href'] for el in soup.find_all('ul') for a in el.find_all('a') if 'list' in a['href']]

def parse_actions(ref_url):
    ref_url = ref_url.replace("//./", "/")
    response = requests.get(ref_url, timeout=7)
    soup = BeautifulSoup(response.text, 'html.parser')
    codes = soup.find_all('code', {"class": 'code'})
    try:
        prefix = codes.pop(0).text
    except:
        print(ref_url)
        exit()

    actions = []
    by_resource = {}
    for table in soup.find_all("div", {"class": 'table-contents'}):
        rows = table.find_all('tr')
        _ = rows.pop(0)
        for _, row in enumerate(rows):
            cols = row.find_all('td')
            if len(cols) != 6:
                continue
            action = prefix + ":" + cols[0].text.strip()
            if '[' in action:
                continue
            resource = str(cols[3].text.strip())
            resource = resource if resource else '?'
            if resource not in by_resource:
                by_resource[resource] = []
            by_resource[resource].append(action)
            actions.append(action)

    return prefix, actions, by_resource, ref_url


def download_terraform_resources(data_dir):
    response = requests.get("https://registry.terraform.io/v2/provider-versions/34748?include=provider-docs")
    data = response.json()
    tf_resources = set()
    for resource in data['included']:
        tf_resources.add(resource['attributes']['slug'])

    with open(f'{data_dir}/aws/terraform_resources.json', 'w+') as fh:
        fh.write(json.dumps(sorted(list(tf_resources)), indent=True))

data_dir = os.path.expanduser('~/vcs/scrape_iam/docs')
ensure_dir(f'{data_dir}/aws/by_svc/')
download_terraform_resources(data_dir)
root = "https://docs.aws.amazon.com/service-authorization/latest/reference/"

response = requests.get(f"{root}/reference_policies_actions-resources-contextkeys.html", timeout=5)
urls = parse_services(response)

with futures.ThreadPoolExecutor(max_workers=20) as executor:
    promises = [
        executor.submit(parse_actions, f"{root}/{url}")
        for url in urls
    ]

actions = []
services = []
tree = {}
service_docs = {}
for idx, promise in enumerate(promises):
    prefix, subset, by_resource, ref_url = promise.result()
    tree[prefix] = by_resource
    actions = actions + subset
    services.append(prefix)
    with open(f'{data_dir}/aws/by_svc/{prefix}.json', 'w+') as fh:
        fh.write(json.dumps(subset, indent=True))

    with open(f'{data_dir}/aws/by_svc/{prefix}_resources.json', 'w+') as fh:
        by_resource['_url'] = ref_url
        service_docs[prefix] = ref_url
        fh.write(json.dumps(by_resource, indent=True))

with open(f'{data_dir}/aws/services.json', 'w+') as fh:
    fh.write(json.dumps(sorted(services), indent=True))

with open(f'{data_dir}/aws/actions.json', 'w+') as fh:
    fh.write(json.dumps(sorted(actions), indent=True))

with open(f'{data_dir}/aws/actions_by_resource.json', 'w+') as fh:
    json.dump(tree, fh, indent=2)

with open(f'{data_dir}/aws/service_urls.json', 'w+') as fh:
    json.dump(service_docs, fh, indent=2)