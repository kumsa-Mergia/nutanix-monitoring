#!/usr/bin/env python3
import requests
from requests.auth import HTTPBasicAuth
from flask import Flask, Response, request
import json, os

requests.packages.urllib3.disable_warnings()
app = Flask(__name__)

PRISM_IPS = os.getenv("PRISM_IPS", "").split(",")
USERNAME = os.getenv("PRISM_USER")
PASSWORD = os.getenv("PRISM_PASS")

METRICS = [
    "hypervisor_cpu_usage_ppm",
    "hypervisor_memory_usage_ppm",
    "controller_num_ops",
    "controller_avg_io_latency_usecs",
    "controller_read_io_bandwidth_kBps",
    "controller_write_io_bandwidth_kBps",
    "hypervisor_network_io_bandwidth_kBps"
]

def get_vms(prism_ip):
    url = f"https://{prism_ip}:9440/api/nutanix/v3/vms/list"
    try:
        resp = requests.post(
            url,
            auth=HTTPBasicAuth(USERNAME, PASSWORD),
            verify=False,
            headers={"Content-Type": "application/json"},
            data=json.dumps({"kind": "vm", "offset": 0, "length": 500})
        )
        return resp.json().get("entities", [])
    except Exception as e:
        print(f"[ERROR] {prism_ip} VM fetch failed: {e}")
        return []

def get_vm_stats(prism_ip, vm_uuid):
    url = f"https://{prism_ip}:9440/PrismGateway/services/rest/v2.0/vms/{vm_uuid}/stats/?metrics={','.join(METRICS)}"
    try:
        resp = requests.get(url, auth=HTTPBasicAuth(USERNAME, PASSWORD), verify=False)
        return resp.json().get("statsSpecificResponses", [])
    except Exception as e:
        print(f"[ERROR] {prism_ip} stats failed: {e}")
        return []

@app.route("/metrics")
def metrics():
    vm_filter_name = request.args.get("vm")
    vm_filter_ip = request.args.get("ip")
    output = []

    for prism_ip in PRISM_IPS:
        vms = get_vms(prism_ip)
        for vm in vms:
            vm_name = vm["spec"]["name"]
            vm_uuid = vm["metadata"]["uuid"]

            # Filter by name
            if vm_filter_name and vm_filter_name != vm_name:
                continue

            # Filter by IP
            vm_nics = vm["status"]["resources"].get("nic_list", [])
            vm_ips = [ep.get("ip") for nic in vm_nics for ep in nic.get("ip_endpoint_list", [])]
            if vm_filter_ip and vm_filter_ip not in vm_ips:
                continue

            stats = get_vm_stats(prism_ip, vm_uuid)
            for stat in stats:
                metric_name = stat["metric"]
                try:
                    value = float(stat["values"][-1])
                except (ValueError, IndexError):
                    value = 0
                if "ppm" in metric_name:
                    value = value / 10000.0

                output.append(
                    f'nutanix_vm_{metric_name}{{vm="{vm_name}",prism="{prism_ip}"}} {value}'
                )

    return Response("\n".join(output), mimetype="text/plain")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9100)
