# Nutanix Monitoring with Prometheus & Grafana

Monitor **Nutanix** infrastructure using **Prometheus**, **Grafana**, and **nutanix-exporter** running in Docker.

This project provides a simple and scalable way to monitor:

* Nutanix Clusters
* AHV Hosts
* Virtual Machines
* Storage Containers
* Cluster Capacity
* Performance Metrics

Supports multi-datacenter deployment ( DC1 / DC2).

---

# Architecture

```text
Nutanix Prism Central / Prism Element
                ↓
        nutanix-exporter
                ↓
           Prometheus
                ↓
             Grafana
                ↓
          Alertmanager
```

---

# Features

* Multi-datacenter monitoring
* Docker-based deployment
* Prometheus metrics export
* Grafana dashboard integration
* Alertmanager support
* Read-only monitoring accounts
* Separate environment files per datacenter

---

# Project Structure

```text
nutanix-monitoring/
├── docker-compose.yml
├── prometheus.yml
├── alerts.yml
├── DC1-nutanix-exporter.env
├── DC2-nutanix-exporter.env
└── README.md
```

---

# Requirements

* Docker
* Docker Compose
* Nutanix Prism Central or Prism Element
* Prometheus
* Grafana


---

# Environment File Example

## DC1-nutanix-exporter.env

```bash
# Prism Central
PC_IP=10.190.126.200  #Prism Central IP
PC_PORT=9440       #Nutamix PORT
PC_USERNAME=monitoring_user@domain.local #Your Prism Central Username
PC_PASSWORD=strong_password     #Your Prism Central Password
PC_SECURE=false

# Prism Element
PE_USERNAME=monitoring_user   #Your Prism Element Username
PE_PASSWORD=strong_password   #Your Prism Element Password
PE_PORT=9440      #Nutanix PORT
PE_SECURE=false

# Exporter
EXPORTER_PORT=8000
POLLING_INTERVAL_SECONDS=60

# Metrics
CLUSTER_METRICS=true
HOST_METRICS=true
VM_METRICS=true
VDISK_METRICS=false
STORAGE_CONTAINERS_METRICS=true
```

---

# Start Exporters

```bash
docker compose up -d
```

---

# Verify Metrics

```bash
curl http://localhost:9409/metrics
curl http://localhost:9410/metrics
```

---

# Prometheus Configuration

## prometheus.yml

```yaml
global:
  scrape_interval: 60s

scrape_configs:

  - job_name: 'nutanix_DC1'
    static_configs:
      - targets: ['nutanix_exporter_dc1:8000']
        labels:
          datacenter: DC1
          platform: nutanix

  - job_name: 'nutanix_DC2'
    static_configs:
      - targets: ['nutanix_exporter_dc2:8000']
        labels:
          datacenter: DC2
          platform: nutanix
```

---

# Recommended Alerts

## Exporter Down

```yaml
- alert: NutanixExporterDown
  expr: up{job=~"nutanix.*"} == 0
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Nutanix exporter is down"
```

---

## Storage Usage High

```yaml
- alert: NutanixStorageHigh
  expr: (
    nutanix_cluster_storage_usage_bytes
    /
    nutanix_cluster_storage_capacity_bytes
  ) * 100 > 85
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "Nutanix storage usage above 85%"
```

---

# Recommended Grafana Dashboards

Suggested dashboards:

* Cluster Overview
* AHV Host Performance
* VM Resource Usage
* Storage Capacity
* CVM Health

---

# Security Recommendations

* Use read-only monitoring accounts
* Do not use Prism admin accounts
* Protect `.env` files
* Use Docker secrets in production
* Restrict exporter access with firewall rules

---

# Useful Metrics

Examples:

```text
nutanix_cluster_storage_usage_bytes
nutanix_cluster_storage_capacity_bytes
nutanix_host_cpu_usage_ppm
nutanix_vm_memory_usage_ppm
```

---

# Troubleshooting

## Check exporter logs

```bash
docker logs nutanix_exporter_hq
```

## Verify connectivity

```bash
curl -k https://<PRISM_IP>:9440
```

## Verify Prometheus targets

Open:

```text
http://<prometheus-server>:9090/targets
```

---

# Future Improvements

* VMware monitoring integration
* Linux node_exporter integration
* Windows exporter integration
* Blackbox exporter
* Telegram alerting
* Slack / Teams notifications
* Kubernetes monitoring

---

# License

MIT License

---

# Author

Kumsa Mega
System Engineer | DevOps Enthusiast
# Nutanix Monitoring with Prometheus & Grafana

Monitor **Nutanix** infrastructure using **Prometheus**, **Grafana**, and **nutanix-exporter** running in Docker.

This project provides a simple and scalable way to monitor:

* Nutanix Clusters
* AHV Hosts
* Virtual Machines
* Storage Containers
* Cluster Capacity
* Performance Metrics

Supports multi-datacenter deployment (HQ / THQ / DC1 / DC2).

---

# Architecture

```text
Nutanix Prism Central / Prism Element
                ↓
        nutanix-exporter
                ↓
           Prometheus
                ↓
             Grafana
                ↓
          Alertmanager
```

---

# Features

* Multi-datacenter monitoring
* Docker-based deployment
* Prometheus metrics export
* Grafana dashboard integration
* Alertmanager support
* Read-only monitoring accounts
* Separate environment files per datacenter

---

# Project Structure

```text
nutanix-monitoring/
├── docker-compose.yml
├── prometheus.yml
├── alerts.yml
├── HQ-nutanix-exporter.env
├── THQ-nutanix-exporter.env
└── README.md
```

---

# Requirements

* Docker
* Docker Compose
* Nutanix Prism Central or Prism Element
* Prometheus
* Grafana

---

# Docker Compose

```yaml
version: '3.8'

services:

  nutanix_exporter_hq:
    image: johnnyxiao/nutanix-exporter:latest
    container_name: nutanix_exporter_hq
    env_file:
      - ./HQ-nutanix-exporter.env
    ports:
      - "9409:8000"
    restart: unless-stopped

  nutanix_exporter_thq:
    image: johnnyxiao/nutanix-exporter:latest
    container_name: nutanix_exporter_thq
    env_file:
      - ./THQ-nutanix-exporter.env
    ports:
      - "9410:8000"
    restart: unless-stopped
```

---

# Environment File Example

## HQ-nutanix-exporter.env

```bash
# Prism Central
PC_IP=10.190.126.200
PC_PORT=9440
PC_USERNAME=monitoring_user
PC_PASSWORD=strong_password
PC_SECURE=false

# Prism Element
PE_USERNAME=monitoring_user
PE_PASSWORD=strong_password
PE_PORT=9440
PE_SECURE=false

# Exporter
EXPORTER_PORT=8000
POLLING_INTERVAL_SECONDS=60

# Metrics
CLUSTER_METRICS=true
HOST_METRICS=true
VM_METRICS=true
VDISK_METRICS=false
STORAGE_CONTAINERS_METRICS=true
```

---

# Start Exporters

```bash
docker compose up -d
```

---

# Verify Metrics

```bash
curl http://localhost:9409/metrics
curl http://localhost:9410/metrics
```

---

# Prometheus Configuration

## prometheus.yml

```yaml
global:
  scrape_interval: 60s

scrape_configs:

  - job_name: 'nutanix_hq'
    static_configs:
      - targets: ['nutanix_exporter_hq:8000']
        labels:
          datacenter: HQ
          platform: nutanix

  - job_name: 'nutanix_thq'
    static_configs:
      - targets: ['nutanix_exporter_thq:8000']
        labels:
          datacenter: THQ
          platform: nutanix
```

---

# Recommended Alerts

## Exporter Down

```yaml
- alert: NutanixExporterDown
  expr: up{job=~"nutanix.*"} == 0
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Nutanix exporter is down"
```

---

## Storage Usage High

```yaml
- alert: NutanixStorageHigh
  expr: (
    nutanix_cluster_storage_usage_bytes
    /
    nutanix_cluster_storage_capacity_bytes
  ) * 100 > 85
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "Nutanix storage usage above 85%"
```

---

# Recommended Grafana Dashboards

Suggested dashboards:

* Cluster Overview
* AHV Host Performance
* VM Resource Usage
* Storage Capacity
* CVM Health

---

# Security Recommendations

* Use read-only monitoring accounts
* Do not use Prism admin accounts
* Protect `.env` files
* Use Docker secrets in production
* Restrict exporter access with firewall rules

---

---

# Troubleshooting

## Check exporter logs

```bash
docker logs nutanix_exporter_hq
```

## Verify connectivity

```bash
curl -k https://<PRISM_IP>:9440
```

## Verify Prometheus targets

Open:

```text
http://<prometheus-server>:9090/targets
```

---

# Future Improvements

* VMware monitoring integration
* Linux node_exporter integration
* Windows exporter integration
* Blackbox exporter
* Telegram alerting
* Slack / Teams notifications
* Kubernetes monitoring

---

---

# Author

Kumsa Mega
System Engineer | DevOps Enthusiast
