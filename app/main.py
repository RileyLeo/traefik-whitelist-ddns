import os
import socket

from urllib.request import urlopen

from sync_objects import(
    patch_traefik_middleware,
    patch_porkbun_A_records_dns,
    cluster_config_map,
)

patch_resource = {
    "traefik_middleware" : patch_traefik_middleware,
    "porkbun_dns" : patch_porkbun_A_records_dns,
    "cluster_config_map" : cluster_config_map,
}

def parse_env_bool(env_var: str, default: bool = False) -> bool:
    val = os.environ.get(env_var, '').strip().lower()
    return val in ('true') if val else default

def main():  
    domain = os.environ.get('DOMAIN')
    current_public_ip = urlopen('https://api.ipify.org').read().decode('utf8')
    skip_dns_check = parse_env_bool('SKIP_DNS_CHECK')
    
    if domain and not skip_dns_check:
        dns_ip_list = socket.gethostbyname_ex(domain)[2]
        if current_public_ip in dns_ip_list:
            print(f"Current public IP {current_public_ip} is already in DNS records for domain {domain}. No patching needed.")
            return

    resource_to_patch = os.environ['RESOURCES_TO_PATCH']
    print("==========================================================")
    for resource in resource_to_patch.split(','):
        if resource in patch_resource:
            print(f"Patching {resource} with new public IP: {current_public_ip}")
            patch_resource[resource](current_public_ip)
        else:
            print(f"Resource {resource} not found in patch resources.")
    
    print("Patching completed.")

if __name__ == '__main__':
    main()
