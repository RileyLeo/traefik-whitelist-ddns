import os
import requests
from pprint import pprint

from kubernetes import client, config

def patch_traefik_middleware (new_public_ip: str):
    config.load_incluster_config()
    api = client.CustomObjectsApi()
    
    patch_body = {
        "spec": {
            "ipAllowList": {
                "sourceRange": [new_public_ip]
            }
        }
    }
    
    name = os.environ.get('WHITELIST_MIDDLEWARE_NAME', 'ip-whitelist')
    namespace = os.environ.get('WHITELIST_TRAEFIK_NAMESPACE', 'traefik-system')

    patch_resource = api.patch_namespaced_custom_object(
        group="traefik.io",
        version="v1alpha1",
        name=name,
        namespace=namespace,
        plural="middlewares",
        body=patch_body,
    )

    print("Current state of the middleware: ")
    pprint(patch_resource)
    
def patch_porkbun_A_records_dns(new_public_ip: str):
    API_KEY = os.environ.get('PORKBUN_API_KEY')
    SECRET_KEY = os.environ.get('PORKBUN_SECRET_KEY')
    domain = os.environ.get('DOMAIN')
    ttl = os.environ.get('TTL', 300) 
    subdomain_list = os.environ.get('SUBDOMAIN')
    
    if not API_KEY or not SECRET_KEY or not domain:
        print("Porkbun API key, secret key, and domain must be set in environment variables.")
        return
    
    if subdomain_list:
        subdomain_list = subdomain_list.split(',')
    else:
        subdomain_list = [['@', "*"]]  # Default to root domain if no subdomains specified 
    
    # Step 1: Retrieve all records
    retrieve_url = f"https://api.porkbun.com/api/json/v3/dns/retrieve/{domain}"
    retrieve_payload = {
        "apikey": API_KEY,
        "secretapikey": SECRET_KEY
    }
    headers = {"Content-Type": "application/json"}

    response = requests.post(retrieve_url, json=retrieve_payload, headers=headers)
    if response.status_code != 200:
        print(f"Failed to retrieve records: {response.status_code} - {response.text}")
        return
    
    records = response.json().get("records", [])
    
    for subdomain in subdomain_list:
        record_found = False
        print(f"Checking for A records for subdomain: {subdomain} in domain: {domain}")
        for record in records:
            if subdomain == '@':
                complete_domain = domain
            else:
                complete_domain = f'{subdomain}.{domain}'
            if record["type"] == "A" and record["name"] == complete_domain:
                pprint(f"Found A record for {subdomain}.{domain}")
                record_id = record["id"]
                edit_url = f"https://api.porkbun.com/api/json/v3/dns/edit/{domain}/{record_id}"
                edit_payload = {
                    "apikey": API_KEY,
                    "secretapikey": SECRET_KEY,
                    "name": subdomain,
                    "type": "A",
                    "content": new_public_ip,
                    "ttl": ttl
                }
                edit_response = requests.post(edit_url, json=edit_payload, headers=headers)

                if edit_response.status_code == 200 and edit_response.json().get("status") == "SUCCESS":
                    print(f"Successfully updated A record for {subdomain}.{domain} to 202.186.95.111.")
                else:
                    print(f"Failed to update A record for {subdomain}.{domain}: {edit_response.json().get('message')}")
                record_found = True
                break

        if not record_found:
            print(f"No A record found for {subdomain}.{domain} to update.")
    
def cluster_config_map(new_public_ip: str):
    config.load_incluster_config()
    v1 = client.CoreV1Api()
    
    config_map_name = os.environ.get('CONFIG_MAP_NAME', 'ip-config')
    namespace = os.environ.get('CONFIG_MAP_NAMESPACE', 'default')
    deployments_to_restart = os.environ.get('DEPLOYMENTS_TO_RESTART')

    config_map = v1.read_namespaced_config_map(config_map_name, namespace)
    
    config_map.data['current_public_ip'] = new_public_ip
    
    updated_config_map = v1.patch_namespaced_config_map(
        name=config_map_name,
        namespace=namespace,
        body=config_map
    )
    
    print("Updated ConfigMap:")
    pprint(updated_config_map)
    
    if deployments_to_restart is not None:
        for deployment in deployments_to_restart.split(','):
            try:
                v1.patch_namespaced_deployment(
                    name=deployment.strip(),
                    namespace=namespace,
                    body={"spec": {"template": {"metadata": {"annotations": {"kubectl.kubernetes.io/restartedAt": new_public_ip}}}}}
                )
                print(f"Restarted deployment: {deployment.strip()}")
            except client.ApiException as e:
                print(f"Failed to restart deployment {deployment.strip()}: {e}")