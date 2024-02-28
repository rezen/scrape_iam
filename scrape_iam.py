#!/usr/bin/env python3
""" It is nice having a list of all the IAM actions in a text file """
import os
import re
import json
from concurrent import futures
import requests
from bs4 import BeautifulSoup
import os.path
import botocore
from glob import glob
from collections import defaultdict
from inflector import Inflector

BOTO_DATA_DIR = os.path.dirname(botocore.__file__) + "/data/"


def camelize(s):
    return "".join(e.title() for e in s.split("_"))


def entity_name(x):
    splitters = ["Without", "By", "From", "With"]
    words = re.findall('[A-Z][^A-Z]*', x)
    for w in splitters:
        if w in words:
            x = x.split(w).pop(0)
            break
    if x.endswith("tatus"):
        return x

    return Inflector().singularize(x)


def aws_service_versions():
    global BOTO_DATA_DIR
    by_service = defaultdict(list)
    for name in glob(BOTO_DATA_DIR + "*/*/service-2.json"):
        parts = name.split("/")[-3:]
        by_service[parts[0]].append(parts[1])
        by_service[parts[0]] = sorted(by_service[parts[0]])
    return by_service


def ensure_dir(file):
    dir = os.path.dirname(os.path.expanduser(file))
    os.makedirs(dir, exist_ok=True)


def parse_services(response):
    soup = BeautifulSoup(response.text, "html.parser")
    return [
        a["href"]
        for el in soup.find_all("ul")
        for a in el.find_all("a")
        if "list" in a["href"]
    ]


def parse_actions(ref_url):
    ref_url = ref_url.replace("//./", "/")
    response = requests.get(ref_url, timeout=7)
    soup = BeautifulSoup(response.text, "html.parser")
    codes = soup.find_all("code", {"class": "code"})
    try:
        prefix = codes.pop(0).text
    except:
        print(ref_url)
        exit()

    records = []
    for table in soup.find_all("div", {"class": "table-contents"}):
        rows = table.find_all("tr")
        _ = rows.pop(0)
        for _, row in enumerate(rows):
            data = {"svc": prefix, "action": None, "access_level": "", "obj": None}
            cols = row.find_all("td")
            if len(cols) != 6:
                continue
            data["action"] = cols[0].text.strip()
            joined_action = prefix + ":" + data["action"]
            if "[" in joined_action:
                continue
            data["access_level"] = cols[2].text.strip()
            if data["access_level"] == "Permissions management":
                data["access_level"] = "perm-mgmt"

            data["resource_types"] = [x for x in cols[3].text.strip().split("\n") if x]
            data["resource_types"] = (
                data["resource_types"] if data["resource_types"] else ["?"]
            )
            data["resource_types"] = [r.replace("_", "").replace("-", "").lower() for r in data["resource_types"]]
            data["condition_keys"] = [x for x in cols[4].text.strip().split("\n") if x]

            tmp_action = data["action"]
            if tmp_action.startswith("Batch"):
                tmp_action = tmp_action.replace("Batch", "")

            if tmp_action.startswith("With"):
                tmp_action = tmp_action.split("With")[0]

            for action_key in action_types:
                if tmp_action.startswith(action_key):
                    data["obj"] = entity_name(tmp_action.replace(action_key, "", 1))

            if "?" in data["resource_types"]:
                data["resource_types"] = []

            records.append(data)
    return prefix, ref_url, records


def download_boto_docs(data_dir):
    response = requests.get(
        "https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/index.html"
    )
    soup = BeautifulSoup(response.text, "html.parser")
    anchors = soup.find_all("li", {"class": "toctree-l1"})
    boto_services = []
    for el in anchors:
        a = el.find("a")
        if "/" in a["href"] or a["href"] == "":
            continue

        boto_services.append(a["href"].replace(".html", ""))

    with open(f"{data_dir}/aws/boto_services.json", "w+") as fh:
        fh.write(json.dumps(sorted(boto_services), indent=True))

    with open(f"{data_dir}/aws/service_versions.json", "w+") as fh:
        fh.write(json.dumps(aws_service_versions(), indent=True))


def download_terraform_resources(validate_services=[]):
    response = requests.get(
        "https://registry.terraform.io/v2/provider-versions/34748?include=provider-docs"
    )
    data = response.json()
    resources = set()
    for resource in data["included"]:
        attrs = resource["attributes"]
        if not attrs.get("subcategory"):
            continue
        slug = attrs["slug"]
        subcategory = attrs["subcategory"].split("(").pop(0).strip()
        sub_slug = subcategory.replace(" ", "-").lower()
        tmp = slug.split("_")
        obj_label = None
        svc = None
        original_service = None
        if sub_slug == "vpc":
            svc = "ec2"
        elif sub_slug == "opensearch":
            svc = "es"
        elif slug.startswith("cloudwatch_log"):
            svc = "logs"
            original_service = "cloudwatch"
        elif sub_slug == "api-gateway-v2":
            svc = "apigateway"
        elif sub_slug == "elb":
            svc = "elasticloadbalancing"
        elif tmp[0] in validate_services:
            svc = tmp[0]
        elif sub_slug in validate_services:
            svc = sub_slug
        elif sub_slug.replace("-", "") in validate_services:
            svc = sub_slug.replace("-", "")
        else:
            pass

        if svc:
            wo_prefix = slug.lstrip(original_service if original_service else svc).lstrip("_")
            obj_label = entity_name(''.join(x for x in wo_prefix.title() if not x.isspace()).replace("_", ""))
        resources.add((slug, subcategory, svc, obj_label))

    return sorted(list(resources))


root = "https://docs.aws.amazon.com/service-authorization/latest/reference/"
data_dir = os.path.expanduser("~/vcs/scrape_iam/docs")

with open(data_dir + "/aws/action_type.json", "r") as fh:
    action_types = json.loads(fh.read())

ensure_dir(f"{data_dir}/aws/by_svc/")

response = requests.get(
    f"{root}/reference_policies_actions-resources-contextkeys.html", timeout=5
)
urls = parse_services(response)

with futures.ThreadPoolExecutor(max_workers=20) as executor:
    promises = [executor.submit(parse_actions, f"{root}/{url}") for url in urls]

all_records = []
service_docs = {}
for idx, promise in enumerate(promises):
    prefix, ref_url, records = promise.result()
    service_docs[prefix] = ref_url
    all_records.extend(records)


with open(f"{data_dir}/aws/iam_all_records.json", "w+") as fh:
    fh.write(json.dumps(all_records))


tf_resources = download_terraform_resources(list(service_docs.keys()))
download_boto_docs(data_dir)

with open(f"{data_dir}/aws/terraform_resources.json", "w+") as fh:
    fh.write(json.dumps(tf_resources))

with open(f"{data_dir}/aws/service_urls.json", "w+") as fh:
    json.dump(service_docs, fh, indent=2)
