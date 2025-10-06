import os
import time
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from prometheus_client import start_http_server, Gauge

# =====================
# Load environment variables
# =====================
load_dotenv()

NUTANIX_CLUSTER = os.getenv("NUTANIX_CLUSTER")
NUTANIX_USER = os.getenv("NUTANIX_USER")
NUTANIX_PASS = os.getenv("NUTANIX_PASS")
EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", 9100))

# Disable warnings for self-signed certs
requests.packages.urllib3.disable_warnings()

# =====================
# Prometheus Gauges
# =====================

# Exporter health
EXPORTER_UP = Gauge("nutanix_thq_exporter_up", "Exporter scrape status (1=success, 0=fail)")

# VM metrics
vm_power_state = Gauge("nutanix_thq_vm_power_state", "VM power state (1=on, 0=off)", ["vm_name"])
vm_vcpu = Gauge("nutanix_thq_vm_vcpu", "Number of vCPUs per VM", ["vm_name"])
vm_memory_mb = Gauge("nutanix_thq_vm_memory_mb", "Memory assigned to VM in MB", ["vm_name"])
vm_cpu_usage_pct = Gauge("nutanix_thq_vm_cpu_usage_percent", "VM CPU usage (%)", ["vm_name"])
vm_memory_usage_pct = Gauge("nutanix_thq_vm_memory_usage_percent", "VM memory usage (%)", ["vm_name"])
vm_disk_usage_bytes = Gauge("nutanix_thq_vm_disk_usage_bytes", "VM disk usage in bytes", ["vm_name", "disk_name"])
vm_net_rx_bytes = Gauge("nutanix_thq_vm_network_receive_bytes", "VM network receive bytes", ["vm_name", "nic_name"])
vm_net_tx_bytes = Gauge("nutanix_thq_vm_network_transmit_bytes", "VM network transmit bytes", ["vm_name", "nic_name"])

# Cluster metrics
CLUSTER_CPU = Gauge("nutanix_thq_cluster_cpu_usage_ppm", "Cluster CPU usage in PPM")
CLUSTER_MEMORY = Gauge("nutanix_thq_cluster_memory_usage_ppm", "Cluster Memory usage in PPM")
CLUSTER_IO = Gauge("nutanix_thq_cluster_io_bandwidth_kbps", "Cluster IO Bandwidth in Kbps")
CLUSTER_IOPS = Gauge("nutanix_thq_cluster_iops", "Cluster IOPS")

# Cluster additional metrics
CLUSTER_VM_COUNT = Gauge("nutanix_thq_cluster_vm_count", "Number of VMs in the cluster", ["cluster_name"])
CLUSTER_HOST_COUNT = Gauge("nutanix_thq_cluster_host_count", "Number of hosts in the cluster", ["cluster_name"])
TOTAL_VM_COUNT = Gauge("nutanix_thq_total_vm_count", "Total number of VMs across all clusters")

# Cluster storage metrics
CLUSTER_STORAGE_TOTAL_BYTES = Gauge("nutanix_thq_cluster_storage_total_bytes", "Total cluster storage capacity in bytes")
CLUSTER_STORAGE_USED_BYTES = Gauge("nutanix_thq_cluster_storage_used_bytes", "Used cluster storage capacity in bytes")
CLUSTER_STORAGE_FREE_BYTES = Gauge("nutanix_thq_cluster_storage_free_bytes", "Free cluster storage capacity in bytes")

# Host metrics
HOST_CPU = Gauge("nutanix_thq_host_cpu_usage_ppm", "Host CPU usage in PPM", ["host"])
HOST_MEMORY = Gauge("nutanix_thq_host_memory_usage_ppm", "Host Memory usage in PPM", ["host"])
HOST_IO = Gauge("nutanix_thq_host_io_bandwidth_kbps", "Host IO Bandwidth in Kbps", ["host"])
HOST_IOPS = Gauge("nutanix_thq_host_iops", "Host IOPS", ["host"])

# =====================
# API Functions
# =====================
def get_vms():
    """Fetch list of VMs from Nutanix Prism Central v3"""
    url = f"{NUTANIX_CLUSTER}/api/nutanix/v3/vms/list"
    payload = {"kind": "vm", "length": 100, "offset": 0}
    all_vms = []

    while True:
        response = requests.post(url, json=payload,
                                 auth=HTTPBasicAuth(NUTANIX_USER, NUTANIX_PASS),
                                 verify=False, timeout=30)
        response.raise_for_status()
        data = response.json()
        entities = data.get("entities", [])
        if not entities:
            break

        all_vms.extend(entities)
        payload["offset"] += payload["length"]

    return all_vms


def fetch_vm_metrics():
    """Fetch VM-level metrics"""
    try:
        vms = get_vms()
        for vm in vms:
            vm_name = vm["spec"]["name"]
            vm_uuid = vm["metadata"]["uuid"]
            resources = vm["spec"]["resources"]

            # Config metrics
            power_state = vm.get("status", {}).get("resources", {}).get("power_state") or resources.get("power_state")
            vm_power_state.labels(vm_name).set(1 if str(power_state).lower() == "on" else 0)
            vm_vcpu.labels(vm_name).set(resources.get("num_vcpus_per_socket", 0) * resources.get("num_sockets", 0))
            vm_memory_mb.labels(vm_name).set(resources.get("memory_size_mib", 0))

            # Runtime stats
            summary_url = f"{NUTANIX_CLUSTER}/api/nutanix/v3/vms/{vm_uuid}/stats/summary"
            resp = requests.get(summary_url, auth=HTTPBasicAuth(NUTANIX_USER, NUTANIX_PASS),
                                verify=False, timeout=30)
            if resp.status_code != 200:
                print(f"[WARN] VM summary fetch failed for {vm_name}: {resp.status_code}")
                continue

            summary = resp.json()
            vm_cpu_usage_pct.labels(vm_name).set(summary.get("cpu", {}).get("usage_percent", 0))
            vm_memory_usage_pct.labels(vm_name).set(summary.get("memory", {}).get("usage_percent", 0))

            # Disks
            for disk in summary.get("disk", []):
                name = disk.get("name", "disk_unknown")
                used_bytes = disk.get("used_bytes", 0)
                vm_disk_usage_bytes.labels(vm_name, name).set(used_bytes)

            # NICs
            for nic in summary.get("nic", []):
                nic_name = nic.get("name", "nic_unknown")
                rx = nic.get("rx_bytes", 0)
                tx = nic.get("tx_bytes", 0)
                vm_net_rx_bytes.labels(vm_name, nic_name).set(rx)
                vm_net_tx_bytes.labels(vm_name, nic_name).set(tx)

    except Exception as e:
        print(f"[ERROR] fetch_vm_metrics failed: {e}")


def fetch_cluster_metrics():
    """Fetch cluster and host metrics (Prism Element v2 endpoints)"""
    try:
        total_vm_count = 0
        cluster_vm_counts = {}
        cluster_host_counts = {}

        # Fetch Cluster Stats
        cluster_stats_url = f"{NUTANIX_CLUSTER}/clusters/"
        resp = requests.get(cluster_stats_url, auth=HTTPBasicAuth(NUTANIX_USER, NUTANIX_PASS), verify=False)
        if resp.status_code == 200:
            data = resp.json()
            for cluster in data.get("entities", []):
                cluster_name = cluster.get("name", "unknown_cluster")
                stats = cluster.get("stats", {})

                # Set cluster-level metrics for CPU usage
                cluster_cpu_usage_ppm = float(stats.get("hypervisor_cpu_usage_ppm", 0))
                CLUSTER_CPU.set(cluster_cpu_usage_ppm)

                # Set cluster-level metrics for Memory usage
                cluster_memory_usage_ppm = float(stats.get("hypervisor_memory_usage_ppm", 0))
                CLUSTER_MEMORY.set(cluster_memory_usage_ppm)

                # Set cluster-level metrics for I/O Bandwidth and IOPS
                CLUSTER_IO.set(float(stats.get("controller_io_bandwidth_kBps", 0)))
                CLUSTER_IOPS.set(float(stats.get("controller_num_iops", 0)))

                # Count VMs in the cluster
                cluster_vm_counts[cluster_name] = cluster_vm_counts.get(cluster_name, 0) + len(cluster.get("vm", []))

                # Count Hosts in the cluster
                cluster_host_counts[cluster_name] = cluster_host_counts.get(cluster_name, 0) + len(cluster.get("hosts", []))

                # Fetch storage metrics (Capacity, Used, Free)
                storage_stats = cluster.get("storage", {})
                total_storage = storage_stats.get("total_capacity_bytes", 0)
                used_storage = storage_stats.get("used_capacity_bytes", 0)
                free_storage = total_storage - used_storage

                # Expose storage metrics
                CLUSTER_STORAGE_TOTAL_BYTES.set(total_storage)
                CLUSTER_STORAGE_USED_BYTES.set(used_storage)
                CLUSTER_STORAGE_FREE_BYTES.set(free_storage)

        else:
            print(f"[WARN] Cluster stats request failed: {resp.status_code}")

        # Set cluster-level counts for VMs and Hosts
        for cluster_name, vm_count in cluster_vm_counts.items():
            CLUSTER_VM_COUNT.labels(cluster_name).set(vm_count)

        for cluster_name, host_count in cluster_host_counts.items():
            CLUSTER_HOST_COUNT.labels(cluster_name).set(host_count)

        # Set total VM count across clusters
        TOTAL_VM_COUNT.set(sum(cluster_vm_counts.values()))

        # Fetch Hosts
        host_stats_url = f"{NUTANIX_CLUSTER}/hosts/"
        resp = requests.get(host_stats_url, auth=HTTPBasicAuth(NUTANIX_USER, NUTANIX_PASS), verify=False)
        if resp.status_code == 200:
            data = resp.json()
            for host in data.get("entities", []):
                name = host.get("name", "unknown_host")
                stats = host.get("stats", {})
                HOST_CPU.labels(host=name).set(float(stats.get("hypervisor_cpu_usage_ppm", 0)))
                HOST_MEMORY.labels(host=name).set(float(stats.get("hypervisor_memory_usage_ppm", 0)))
                HOST_IO.labels(host=name).set(float(stats.get("controller_io_bandwidth_kBps", 0)))
                HOST_IOPS.labels(host=name).set(float(stats.get("controller_num_iops", 0)))
        else:
            print(f"[WARN] Host stats request failed: {resp.status_code}")

    except Exception as e:
        print(f"[ERROR] fetch_cluster_metrics failed: {e}")


# =====================
# Main Loop
# =====================
if __name__ == "__main__":
    print(f"🚀 Starting Nutanix Full Exporter on port {EXPORTER_PORT}...")
    start_http_server(EXPORTER_PORT)

    while True:
        try:
            fetch_vm_metrics()
            fetch_cluster_metrics()
            EXPORTER_UP.set(1)
        except Exception as e:
            print(f"[FATAL] Exporter scrape failed: {e}")
            EXPORTER_UP.set(0)
        time.sleep(30)
