#!/usr/bin/env python3
import os
import time
import json
from datetime import datetime

import requests
import urllib3
from prometheus_client import start_http_server, Gauge, Info

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class bcolors:
    OK = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    RESET = "\033[0m"


def env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip().lower()
    if v == "":
        return False
    if v in ("1", "true", "yes", "y", "on"):
        return True
    if v in ("0", "false", "no", "n", "off"):
        return False
    return default


def env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if not v:
        return default
    try:
        return int(v)
    except Exception:
        return default


def log_info(msg: str):
    print(f"{bcolors.OK}{datetime.now():%Y-%m-%d %H:%M:%S} [INFO] {msg}{bcolors.RESET}")


def log_warn(msg: str):
    print(f"{bcolors.WARNING}{datetime.now():%Y-%m-%d %H:%M:%S} [WARNING] {msg}{bcolors.RESET}")


def log_err(msg: str):
    print(f"{bcolors.FAIL}{datetime.now():%Y-%m-%d %H:%M:%S} [ERROR] {msg}{bcolors.RESET}")


def request_json(method, url, auth_user, auth_pass, secure, payload=None, timeout=30, retries=3):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    last_err = None
    for _ in range(retries):
        try:
            if method == "GET":
                r = requests.get(url, auth=(auth_user, auth_pass), headers=headers, verify=secure, timeout=timeout)
            else:
                r = requests.post(url, auth=(auth_user, auth_pass), headers=headers, json=payload, verify=secure, timeout=timeout)

            if r.ok:
                return r.json()

            if r.status_code in (401, 403):
                raise RuntimeError(f"Auth failed {r.status_code} for {url}")

            last_err = RuntimeError(f"HTTP {r.status_code} {r.text}")
            time.sleep(2)
        except Exception as e:
            last_err = e
            time.sleep(2)

    raise last_err


# -----------------------
# Prism Central v3 (PC)
# -----------------------
def pc_list_clusters(pc_ip, pc_port, user, pwd, secure):
    """
    POST /api/nutanix/v3/clusters/list (PC v3 list endpoint uses POST)
    Supports pagination with length/offset.
    """
    entities = []
    length = 50
    offset = 0
    while True:
        url = f"https://{pc_ip}:{pc_port}/api/nutanix/v3/clusters/list"
        payload = {"kind": "cluster", "length": length, "offset": offset}
        data = request_json("POST", url, user, pwd, secure, payload=payload, timeout=30, retries=3)
        batch = data.get("entities", [])
        entities.extend(batch)
        if len(batch) < length:
            break
        offset += length
    return entities


# -----------------------
# Prism Element v1/v2 (PE)
# -----------------------
def pe_get_clusters(pe_ip, pe_port, user, pwd, secure):
    url = f"https://{pe_ip}:{pe_port}/PrismGateway/services/rest/v2.0/clusters/"
    return request_json("GET", url, user, pwd, secure, timeout=30, retries=3)

def pe_get_hosts(pe_ip, pe_port, user, pwd, secure):
    url = f"https://{pe_ip}:{pe_port}/PrismGateway/services/rest/v2.0/hosts"
    return request_json("GET", url, user, pwd, secure, timeout=30, retries=3)

def pe_get_storage_containers(pe_ip, pe_port, user, pwd, secure):
    url = f"https://{pe_ip}:{pe_port}/PrismGateway/services/rest/v2.0/storage_containers/"
    return request_json("GET", url, user, pwd, secure, timeout=30, retries=3)

def pe_get_vms(pe_ip, pe_port, user, pwd, secure):
    url = f"https://{pe_ip}:{pe_port}/PrismGateway/services/rest/v1/vms"
    return request_json("GET", url, user, pwd, secure, timeout=30, retries=3)

def pe_get_vdisks(pe_ip, pe_port, user, pwd, secure):
    url = f"https://{pe_ip}:{pe_port}/PrismGateway/services/rest/v1/virtual_disks"
    return request_json("GET", url, user, pwd, secure, timeout=30, retries=3)


class MetricFactory:
    def __init__(self):
        self.gauges = {}

    def gauge(self, name, desc, labelnames):
        key = (name, tuple(labelnames))
        g = self.gauges.get(key)
        if g is None:
            g = Gauge(name, desc, labelnames)
            self.gauges[key] = g
        return g


class NutanixHybridExporter:
    def __init__(self):
        self.pc_ip = os.getenv("PC_IP")
        self.pc_port = env_int("PC_PORT", 9440)
        self.pc_user = os.getenv("PC_USERNAME")
        self.pc_pwd = os.getenv("PC_PASSWORD")
        self.pc_secure = env_bool("PC_SECURE", False)

        self.pe_user = os.getenv("PE_USERNAME") or self.pc_user
        self.pe_pwd = os.getenv("PE_PASSWORD") or self.pc_pwd
        self.pe_port = env_int("PE_PORT", 9440)
        self.pe_secure = env_bool("PE_SECURE", False)

        if not self.pc_ip or not self.pc_user or not self.pc_pwd:
            raise SystemExit("PC_IP, PC_USERNAME, PC_PASSWORD must be set")

        if not self.pe_user or not self.pe_pwd:
            raise SystemExit("PE credentials missing (PE_USERNAME/PE_PASSWORD) and PC credentials not set")

        self.interval = env_int("POLLING_INTERVAL_SECONDS", 60)

        self.enable_cluster = env_bool("CLUSTER_METRICS", True)
        self.enable_hosts = env_bool("HOST_METRICS", True)
        self.enable_vms = env_bool("VM_METRICS", True)
        self.enable_vdisks = env_bool("VDISK_METRICS", True)
        self.enable_containers = env_bool("STORAGE_CONTAINERS_METRICS", True)

        self.mf = MetricFactory()

        self.pc_cluster_info = Info(
            "nutanix_pc_cluster_info",
            "Cluster information from Prism Central v3",
            ["cluster_name", "cluster_uuid"]
        )
        self.pc_cluster_state = self.mf.gauge(
            "nutanix_pc_cluster_state",
            "Cluster state from Prism Central (1=COMPLETE, 0=other)",
            ["cluster_name", "cluster_uuid"]
        )

    def run(self):
        log_info("Starting Nutanix HYBRID exporter (PC v3 discovery + PE full metrics)")
        while True:
            try:
                self.collect_once()
            except Exception as e:
                log_err(f"Collector loop error: {e}")
            time.sleep(self.interval)

    def collect_once(self):
        clusters = pc_list_clusters(self.pc_ip, self.pc_port, self.pc_user, self.pc_pwd, self.pc_secure)

        for c in clusters:
            cluster_uuid = c.get("metadata", {}).get("uuid", "unknown")
            cluster_name = c.get("spec", {}).get("name", "unknown")
            state = c.get("status", {}).get("state", "UNKNOWN")

            if cluster_name == "Unnamed":
                continue

            self.pc_cluster_info.labels(cluster_name=cluster_name, cluster_uuid=cluster_uuid).info({"state": state})
            self.pc_cluster_state.labels(cluster_name=cluster_name, cluster_uuid=cluster_uuid).set(1 if state == "COMPLETE" else 0)

            pe_ip = (
                c.get("status", {}).get("resources", {}).get("network", {}).get("external_ip")
                or c.get("spec", {}).get("resources", {}).get("network", {}).get("external_ip")
            )

            if not pe_ip:
                log_warn(f"{cluster_name}: no external_ip found in PC response; skipping PE metrics")
                continue

            self.collect_pe_for_cluster(cluster_name, cluster_uuid, pe_ip)

    def collect_pe_for_cluster(self, cluster_name, cluster_uuid, pe_ip):
        labels_cluster = {"cluster_name": cluster_name, "cluster_uuid": cluster_uuid}

        if self.enable_cluster:
            data = pe_get_clusters(pe_ip, self.pe_port, self.pe_user, self.pe_pwd, self.pe_secure)
            entities = data.get("entities", []) or []
            if entities:
                cd = entities[0]
                for k, v in (cd.get("stats", {}) or {}).items():
                    mn = f"NutanixClusters_stats_{str(k).replace('.','_').replace('-','_')}"
                    g = self.mf.gauge(mn, mn, ["cluster_name", "cluster_uuid"])
                    g.labels(**labels_cluster).set(float(v) if self._is_number(v) else 0)
                for k, v in (cd.get("usage_stats", {}) or {}).items():
                    mn = f"NutanixClusters_usage_stats_{str(k).replace('.','_').replace('-','_')}"
                    g = self.mf.gauge(mn, mn, ["cluster_name", "cluster_uuid"])
                    g.labels(**labels_cluster).set(float(v) if self._is_number(v) else 0)

        if self.enable_hosts:
            data = pe_get_hosts(pe_ip, self.pe_port, self.pe_user, self.pe_pwd, self.pe_secure)
            for h in data.get("entities", []) or []:
                host = h.get("name", "unknown")
                lbl = {"cluster_name": cluster_name, "cluster_uuid": cluster_uuid, "host": host}
                for k, v in (h.get("stats", {}) or {}).items():
                    mn = f"NutanixHosts_stats_{str(k).replace('.','_').replace('-','_')}"
                    g = self.mf.gauge(mn, mn, ["cluster_name", "cluster_uuid", "host"])
                    g.labels(**lbl).set(float(v) if self._is_number(v) else 0)
                for k, v in (h.get("usage_stats", {}) or {}).items():
                    mn = f"NutanixHosts_usage_stats_{str(k).replace('.','_').replace('-','_')}"
                    g = self.mf.gauge(mn, mn, ["cluster_name", "cluster_uuid", "host"])
                    g.labels(**lbl).set(float(v) if self._is_number(v) else 0)

        if self.enable_vms:
            data = pe_get_vms(pe_ip, self.pe_port, self.pe_user, self.pe_pwd, self.pe_secure)
            for vm in data.get("entities", []) or []:
                vmn = vm.get("vmName", "unknown")
                lbl = {"cluster_name": cluster_name, "cluster_uuid": cluster_uuid, "vm": vmn}
                for k, v in (vm.get("stats", {}) or {}).items():
                    mn = f"NutanixVms_stats_{str(k).replace('.','_').replace('-','_')}"
                    g = self.mf.gauge(mn, mn, ["cluster_name", "cluster_uuid", "vm"])
                    g.labels(**lbl).set(float(v) if self._is_number(v) else 0)
                for k, v in (vm.get("usageStats", {}) or {}).items():
                    mn = f"NutanixVms_usage_stats_{str(k).replace('.','_').replace('-','_')}"
                    g = self.mf.gauge(mn, mn, ["cluster_name", "cluster_uuid", "vm"])
                    g.labels(**lbl).set(float(v) if self._is_number(v) else 0)

        if self.enable_vdisks:
            data = pe_get_vdisks(pe_ip, self.pe_port, self.pe_user, self.pe_pwd, self.pe_secure)
            for d in data.get("entities", []) or []:
                vmn = d.get("attachedVMName") or "UNATTACHED"
                addr = str(d.get("diskAddress") or "unknown")
                lbl = {"cluster_name": cluster_name, "cluster_uuid": cluster_uuid, "vm": vmn, "addr": addr}
                for k, v in (d.get("stats", {}) or {}).items():
                    mn = f"NutanixVdisks_stats_{str(k).replace('.','_').replace('-','_')}"
                    g = self.mf.gauge(mn, mn, ["cluster_name", "cluster_uuid", "vm", "addr"])
                    g.labels(**lbl).set(float(v) if self._is_number(v) else 0)
                cap = d.get("diskCapacityInBytes", 0)
                gcap = self.mf.gauge("NutanixVdisks_disk_capacity_bytes", "NutanixVdisks_disk_capacity_bytes",
                                     ["cluster_name", "cluster_uuid", "vm", "addr"])
                gcap.labels(**lbl).set(float(cap) if self._is_number(cap) else 0)

        if self.enable_containers:
            data = pe_get_storage_containers(pe_ip, self.pe_port, self.pe_user, self.pe_pwd, self.pe_secure)
            for sc in data.get("entities", []) or []:
                name = sc.get("name", "unknown")
                lbl = {"cluster_name": cluster_name, "cluster_uuid": cluster_uuid, "storage_container": name}
                for k, v in (sc.get("stats", {}) or {}).items():
                    mn = f"NutanixStorageContainers_stats_{str(k).replace('.','_').replace('-','_')}"
                    g = self.mf.gauge(mn, mn, ["cluster_name", "cluster_uuid", "storage_container"])
                    g.labels(**lbl).set(float(v) if self._is_number(v) else 0)
                for k, v in (sc.get("usage_stats", {}) or {}).items():
                    mn = f"NutanixStorageContainers_usage_stats_{str(k).replace('.','_').replace('-','_')}"
                    g = self.mf.gauge(mn, mn, ["cluster_name", "cluster_uuid", "storage_container"])
                    g.labels(**lbl).set(float(v) if self._is_number(v) else 0)

    @staticmethod
    def _is_number(v):
        try:
            float(v)
            return True
        except Exception:
            return False


def main():
    exporter_port = env_int("EXPORTER_PORT", 8000)
    log_info(f"Starting HTTP server on port {exporter_port}")
    start_http_server(exporter_port)
    exporter = NutanixHybridExporter()
    exporter.run()


if __name__ == "__main__":
    main()