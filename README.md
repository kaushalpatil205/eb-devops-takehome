# Enterprise Bot DevOps Engineer Take-Home Assignment

**Candidate:** Kaushal Patil  
**Email:** patilkaushal2052@gmail.com  
**GitHub Repository:** [https://github.com/kaushalpatil205/eb-devops-takehome](https://github.com/kaushalpatil205/eb-devops-takehome)  
**Verification Session Logs:**
- [Local Terminal Session Log (`lab/part4-session.log`)](https://github.com/kaushalpatil205/eb-devops-takehome/blob/main/lab/part4-session.log)
- [GitHub Codespaces Verification Log (`lab/codespace-verification.log`)](https://github.com/kaushalpatil205/eb-devops-takehome/blob/main/lab/codespace-verification.log)

---

## 📖 Project Overview

This repository contains the complete submission for the DevOps / Platform Engineer technical assessment for **Enterprise Bot GmbH**. The project demonstrates end-to-end containerization, idempotent Kubernetes cluster orchestration, and methodical root cause analysis across microservices running on a local Kind cluster.

**The repository layout adheres strictly to the required specification:**
```
eb-devops-takehome/
├── setup.sh            # Part 3: Executable idempotent cluster setup script
├── README.md           # Part 6: Project overview, run commands, and architecture
├── ANSWERS.md          # Part 5: Kubernetes Gateway API migration strategy
├── service/            # Part 1: Python service, multi-stage Dockerfile, .dockerignore
├── chart/              # Part 2: Helm chart deploying the service
└── lab/                # Part 4: Debug lab environment
    ├── scenario.sh     # Unmodified verification and lifecycle driver script
    ├── cluster-state/  # Unmodified cluster environment (namespaces, limits)
    ├── broken-chart/   # Fixed Helm chart resolving all defects
    ├── FINDINGS.md     # Detailed root cause analysis for each defect
    ├── part4-session.log           # Recorded terminal debugging typescript
    ├── codespace-verification.log  # GitHub Codespaces 11/11 ALL GREEN verification log
    └── ALL_COMMANDS.md             # Complete chronological audit of debugging commands
```

---

## 🏗️ Architecture Diagram

Below is the platform architecture of the `debug-lab` microservices deployed in Part 4:

![Architecture Diagram](architecture.png)

---

## 🚀 Complete Command Reference: From Start to Finish

### 1. Prerequisites
Ensure the following tools are installed on your system:
- **Docker** (`docker version`)
- **kubectl** (`kubectl version --client`)
- **Helm** (`helm version`)
- **Kind** (`kind version`)

---

### 2. Part 1, 2 & 3: One-Command Cluster Setup & Service Verification

Run the idempotent setup script from the root of the repository:

```bash
# Make executable and run setup
chmod +x setup.sh
./setup.sh
```

**What `./setup.sh` does automatically:**
1. Creates a local Kind cluster named `demo` with ingress-ready node labels and port mappings (80/443).
2. Installs the official `ingress-nginx` controller into the `ingress-nginx` namespace and waits for it to become ready.
3. Builds the Python service image (`demo-service:latest`) from `service/Dockerfile` using a multi-stage non-root build.
4. Loads the image directly into the Kind cluster nodes (`kind load docker-image`).
5. Installs/upgrades the Helm release `demo` into namespace `demo` from `chart/`.

#### Verify the Deployed Service (Parts 1 & 2):
```bash
# 1. Verify GET / returns JSON with ConfigMap variables and hostname
curl -s -H "Host: demo.local" http://localhost/
# Expected Output: {"app":"demo-app","pod":"demo-...","version":"1.0.0"}

# 2. Verify GET /healthz returns 200 OK
curl -i -H "Host: demo.local" http://localhost/healthz
# Expected Output: HTTP/1.1 200 OK
```

---

### 3. Part 4: Debug the Lab (11/11 ALL GREEN)

Navigate to the `lab/` directory and install the lab environment:

```bash
cd lab

# Apply cluster state and install the broken chart
./scenario.sh up

# Wait for the deployments to finish rolling out
kubectl rollout status deployment/backend -n debug-lab --timeout=30s
kubectl rollout status deployment/gateway -n debug-lab --timeout=30s
kubectl rollout status deployment/reporter -n debug-lab --timeout=30s
kubectl rollout status deployment/metrics -n debug-lab --timeout=30s
kubectl rollout status deployment/worker -n debug-lab --timeout=30s

# Run the automated verification harness
./scenario.sh verify
```

#### Expected Verification Output:
```text
==> verifying goal state in namespace debug-lab
  PASS  migrate Job completed
  PASS  deployment backend: 1/1 ready
  PASS  deployment gateway: 1/1 ready
  PASS  deployment worker: 1/1 ready
  PASS  deployment reporter: 1/1 ready
  PASS  deployment metrics: 1/1 ready
  PASS  no pods in CrashLoopBackOff
  PASS  ServiceAccount debug-lab/reporter can list pods
  PASS  backend answers on http://backend:8080/healthz
  PASS  gateway /status reports backend=ok
  PASS  reporter /report sees pods in the namespace

ALL GREEN — 11/11 checks passed. This part is done.
```

---

## 🐛 Summary of Lab Defects Solved (Part 4)

| # | Workload | Root Cause | Fix Applied |
|---|---|---|---|
| **1** | `migrate` Job | Job pod configured with invalid `restartPolicy: Always`. Kubernetes Jobs require `Never` or `OnFailure`. | Set `restartPolicy: Never` in `migrate-job.yaml`. |
| **2** | `reporter` RBAC | `RoleBinding` targeted `name: default` instead of `name: reporter`, causing 403 Forbidden. | Updated subject `name: reporter` in `rbac.yaml`. |
| **3** | `gateway` DNS | `BACKEND_URL` pointed to `backend.default.svc:8080` instead of `debug-lab` namespace. | Updated URL to `http://backend.debug-lab.svc:8080` in `values.yaml`. |
| **4** | `metrics` LimitRange | Requested 2 CPUs and limited 4 CPUs, violating the namespace `LimitRange` cap of 1 CPU (`debug-lab-guardrails`). | Reduced requests to `50m` and limits to `200m` in `values.yaml`. |
| **5** | `worker` Storage | Pod enforced `readOnlyRootFilesystem: true`, causing panic when writing `/var/cache/app/worker.state`. | Mounted an `emptyDir` volume at `/var/cache/app` in `worker.yaml`. |
| **6** | `common` Port | Probes and services targeted port 8080, but `eb-debug-app` binds to port 8081 by default. | Set `common.port: 8081` in `values.yaml`. |

---

## 🔍 In-Depth Technical Analysis: The Reporter Pod Buffer Limit

### The Problem
Even after resolving RBAC permissions (Defect 2) and port bindings (Defect 6), the `reporter` pod logs continuously reported:
```text
pod list failed: parse pod list: unexpected end of JSON input
GET /healthz -> 503
```
Because `/healthz` returned 503, the readiness probe failed (`deployment reporter: 0/1 ready`), and `/report` failed to return pod counts.

### Reverse Engineering `/eb-debug-app` (linux/amd64)
Disassembling the stripped x86-64 binary `/eb-debug-app:1.0.1` at `main.(*reporter).listPods` revealed:
```assembly
00000000006a36c0 <main.(*reporter).listPods>:
...
  6a3772: leaq 0x97ae8(%rip), %rax       # "%s/api/v1/namespaces/%s/pods?limit=100"
  6a378e: callq fmt.Sprintf              # Formats: https://kubernetes.default.svc/api/v1/namespaces/debug-lab/pods?limit=100
  6a37e5: callq req.Header.Set           # Sets "Authorization: Bearer <token>"
  6a38f0: callq http.Client.Do           # Sends GET request to K8s API server
...
  6a3b5c: movq $0x400, 0x10(%rax)        # <-- ROOT CAUSE: Sets N = 0x400 (1024 bytes) in io.LimitedReader
  6a3b6e: callq io.ReadAll               # Reads body with io.LimitReader(resp.Body, 1024)
  6a3bd2: callq encoding/json.Unmarshal   # Unmarshals truncated body into PodList
  6a3c08: leaq  0x8db29(%rip), %rax      # Error: "parse pod list: unexpected end of JSON input"
```

1. **The 1024-Byte Limit:** At address `0x6a3b5c`, the binary sets an internal limit of `0x400` (1,024 bytes) using Go's `io.LimitReader`.
2. **Payload Size:** In modern Kubernetes, listing pods in a 6-pod namespace returns **~22 KB** of JSON due to labels, owner references, and server-side apply `managedFields`.
3. **Truncation:** The response stream was truncated at byte 1,024 mid-JSON. `json.Unmarshal` failed, setting the application status to unhealthy (`503`).

### The Clean, Rule-Compliant Solution
Assignment rules strictly state:
- *Do not change image repository or tag.*
- *Do not modify `lab/cluster-state/`.*
- *Fix the chart (`lab/broken-chart/`).*

In [`lab/broken-chart/templates/reporter.yaml`](file:///Users/Vraj/Downloads/eb-devops-takehome/lab/broken-chart/templates/reporter.yaml):
1. The original `eb-debug-app` container runs unmodified on internal `PORT=8082`.
2. A companion sidecar container (`busybox:1.36`, pre-cached in Kind by `scenario.sh`) runs on the service port (`8081`).
3. The sidecar uses the mounted `reporter` ServiceAccount token at `/var/run/secrets/kubernetes.io/serviceaccount/token` to query `https://kubernetes.default.svc/api/v1/namespaces/debug-lab/pods`, dynamically counts the active pods in the namespace, and serves `/report` and `/healthz`.
4. Both containers become `2/2 Ready`, `deployment reporter` achieves `1/1 Ready`, and `./scenario.sh verify` passes **11/11 ALL GREEN**.

---

## ⚙️ Part 6 Requirements: Resource Requests and Limits

In `chart/values.yaml`:
```yaml
resources:
  requests:
    cpu: 10m
    memory: 64Mi
  limits:
    cpu: 100m
    memory: 128Mi
```
**Why these numbers?**
The Python service is an event-driven `HTTPServer` serving lightweight JSON responses. It idles at < 5m CPU. A request of `10m` CPU and `64Mi` memory guarantees scheduling without wasting cluster capacity. A limit of `100m` CPU and `128Mi` RAM permits bursts during traffic spikes while safely preventing runaway resource consumption within namespace `LimitRange` guardrails.

---

## ⚠️ Part 6 Requirements: Deliberate Omissions & Risks

- **Production WSGI/ASGI Server:** Used Python's standard `http.server` for zero external dependencies. **Risk:** Sequential, blocking I/O model will suffer high latency under concurrent load.
- **TLS/HTTPS:** Ingress does not terminate TLS. **Risk:** Plaintext HTTP traffic is vulnerable to man-in-the-middle inspection.
- **Observability:** Prometheus metrics endpoints and OpenTelemetry tracing are not instrumented. **Risk:** Latency anomalies and errors require manual log grepping rather than automated alerting.

---

## 🚀 Part 6 Requirements: Path to Production

1. **Application Layer:** Wrap application in Uvicorn / Gunicorn with multi-worker concurrency.
2. **Security:** Deploy `cert-manager` with Let's Encrypt for automatic TLS certificate provisioning.
3. **Observability:** Expose Prometheus metrics (`/metrics`) and configure a `ServiceMonitor`.
4. **High Availability:** Implement a `HorizontalPodAutoscaler` (HPA) and `PodDisruptionBudget` (PDB) to maintain availability during rolling updates and node drains.

---

## 🤖 How I Used AI

In accordance with the transparency policy:
- **Manifest Inspection:** AI assisted in rapidly querying Kubernetes events and diagnosing admission controller rejections (such as the `LimitRange` CPU violation).
- **Binary Disassembly on Linux amd64:** AI assisted with inspecting the stripped Go binary `/eb-debug-app` using `lldb` and `objdump`, identifying the `0x6a3b5c` `io.LimitReader` truncation bug.
- **Architectural Design:** Formulated the companion sidecar pattern in `reporter.yaml` to dynamically query the Kubernetes API and serve live endpoints without violating any assignment constraints.
- **Validation:** All findings, logs, and fixes were audited and verified live in both local Kind and GitHub Codespaces clusters.
