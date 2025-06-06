import os
import requests
from pprint import pprint
import json
from datetime import datetime, timezone

from kubernetes import client, config

def patch_traefik_middleware (new_public_ip: str):
    print("==========================================================")
    print("Updating Traefik middleware with new public IP...")
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
    print("==========================================================")
    
def patch_porkbun_A_records_dns(new_public_ip: str):
    print("==========================================================")
    print("Updating Porkbun A records with new public IP...")
    
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
            
    print("==========================================================")
    
def cluster_config_map(new_public_ip: str):
    print("==========================================================")
    print("Updating ConfigMap with new public IP...")
    config.load_incluster_config()
    v1 = client.CoreV1Api()
    
    config_maps_to_update = json.loads(os.environ.get('CONFIG_MAPS_TO_UPDATE', '[]'))
    if not isinstance(config_maps_to_update, list):
        print("CONFIG_MAPS_TO_UPDATE must be a valid JSON list.")
        return
    deployments_to_restart = json.loads(os.environ.get('DEPLOYMENTS_TO_RESTART', '[]'))
    # validate json format
    if not isinstance(deployments_to_restart, list):
        print("DEPLOYMENTS_TO_RESTART must be a valid JSON list.")
        return

    if not config_maps_to_update:
        print("No ConfigMaps specified for update.")
        return
    
    for config_map in config_maps_to_update:
        config_map_name = config_map['name']
        config_map_namespace = config_map.get('namespace', 'default')  # Default to 'default' namespace if not specified
        config_map_key_to_update = config_map['key'] 
        print(f"Updating ConfigMap {config_map_name} in namespace {config_map_namespace} with key {config_map_key_to_update} to new public IP: {new_public_ip}")
        
        try:
            cm = v1.read_namespaced_config_map(name=config_map_name, namespace=config_map_namespace)
            
            cm.data[config_map_key_to_update] = new_public_ip
            
            v1.patch_namespaced_config_map(
                name=config_map_name,
                namespace=config_map_namespace,
                body=cm
            )
            print(f"Updated ConfigMap {config_map_name} in namespace {config_map_namespace}.")
        except client.ApiException as e:
            print(f"Failed to update ConfigMap {config_map_name} in namespace {config_map_namespace}: {e}")
            continue
        
    
    print("Updated ConfigMap")
    
    apps_v1 = client.AppsV1Api()
    
    if deployments_to_restart != []:
        print(f"Deployments to restart: {deployments_to_restart}")
        for deployment in deployments_to_restart:
            deployment_name = deployment["name"]
            deployment_namespace = deployment.get("namespace", "default")  # Default to 'default' namespace if not specified
            # Patch to trigger restart
            patch = {
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {
                                "kubectl.kubernetes.io/restartedAt": datetime.now(timezone.utc).isoformat()
                            }
                        }
                    }
                }
            }
            try:
                apps_v1.patch_namespaced_deployment(
                    name=deployment_name,
                    namespace=deployment_namespace,
                    body=patch
                )
                print(f"Successfully restarted deployment {deployment_name} in namespace {deployment_namespace}.")
            except client.ApiException as e:
                print(f"Failed to restart deployment {deployment.strip()}: {e}")
    else:
        print("No deployments specified for restart.")
    
    print("==========================================================")