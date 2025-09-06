# 🖥️ Nutanix VM Monitoring Solution

Centralized monitoring VM for Nutanix environments, designed per datacenter or central site.

---

## 🚀 Overview

This monitoring VM collects, visualizes, and alerts on Nutanix cluster metrics using a containerized stack:

- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization and alerting
- **Custom Nutanix Exporter**: Python Flask app to fetch VM stats from Prism APIs
- **Docker + Docker Compose**: Simplified container orchestration

---

## ⚙️ VM Specifications

| Component | Recommended Specs                      |
|-----------|-------------------------------------|
| vCPU      | 4 – 8 cores                         |
| Memory    | 8 – 16 GB                          |
| Disk      | 100 GB (for ~30 days Prometheus data retention; adjust as needed) |
| OS        | Ubuntu 22.04 LTS / RHEL 8+          |
| Network   | Must reach all Prism Centrals on TCP port 9440 |

---

## 🧰 Software Stack

- **Prometheus**: Collects and stores metrics from Nutanix clusters
- **Grafana**: Dashboarding and alerting platform
- **Custom Nutanix Exporter**: Python Flask application that interfaces with Prism APIs to export VM stats
- **Docker & Docker Compose**: Manage containerized applications for easy deployment

---

## 🔐 Security & Best Practices

- **Nutanix User**: Create a dedicated read-only Nutanix user with API access only for monitoring purposes.
- **Credential Management**: Store all sensitive credentials in a `.env` file; avoid hardcoding secrets in source code.
- **Network Security**: Restrict access to the exporter and Prometheus instances via firewalls or network policies.
- **Transport Security**: Use TLS/HTTPS for all external connections. A reverse proxy (e.g., Nginx or Traefik) is recommended to manage certificates and encryption.

---

## 📁 File Structure (Final Best Practice)

```plaintext
nutanix-monitoring/
├── .env                        # stores sensitive values
├── docker-compose.yml
├── exporters/
│   ├── Dockerfile
│   └── nutanix_exporter.py
├── prometheus/
│   ├── prometheus.yml
│   └── alerts.yml              # alert rules (e.g., high CPU)
├── grafana/
│   ├── dashboards/
│   │   └── nutanix-vm-dashboard.json
│   └── provisioning/
│       ├── datasources/
│       │   └── prometheus.yml
│       └── dashboards/
│           └── dashboards.yml

````

---

## ⚡ Getting Started

1. Clone the repository:

   ```bash
   git clone <repo-url>
   cd <repo-name>
   ```

2. Create a `.env` file with your Nutanix API credentials:

   ```
   NUTANIX_USERNAME=your_readonly_user
   NUTANIX_PASSWORD=your_api_password
   PRISM_CENTRAL_URL=https://prism-central-address:9440
   ```

3. Customize Prometheus and Grafana configurations as needed.

4. Start the stack:

   ```bash
   docker-compose up -d
   ```

5. Access Grafana at `http://<vm-ip>:3000` and configure your dashboards.

---

## 📞 Support

For issues or feature requests, please open an issue on this repository.

---


---

*Built with ❤️ for Nutanix environments.*
