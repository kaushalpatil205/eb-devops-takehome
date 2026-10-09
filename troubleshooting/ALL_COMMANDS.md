# Troubleshooting & Terminal Command Audit

Below is a detailed chronological log of the terminal commands utilized throughout the execution and debugging of this assignment. This includes both the commands executed to analyze the cluster state and the commands executed to bypass environmental limitations.

## 1. Initial Assessment & Lab Setup

* **`./scenario.sh up`**
  * **What it does:** Executes the provided shell script to deploy the `cluster-state` (namespaces, LimitRanges) and the `broken-chart` Helm release into the Kind cluster.
  * **Result:** Immediately revealed **Defect 1** (Job restartPolicy invalid).

* **`helm upgrade --install debug-lab ./broken-chart --namespace debug-lab`**
  * **What it does:** Re-applies the Helm chart to the cluster after making local modifications to the YAML templates.
  * **Purpose:** Used iteratively after fixing each defect to push changes to the cluster.

* **`./scenario.sh verify`**
  * **What it does:** Runs a sequence of automated checks against the deployed lab to determine pass/fail criteria.
  * **Purpose:** Used as the primary feedback loop to discover the next failing component (e.g., reporter 0/1 ready, gateway backend error).

## 2. Diagnosing Workload Failures

* **`kubectl get pods -n debug-lab`**
  * **What it does:** Lists all pods in the `debug-lab` namespace and their current statuses (Running, CrashLoopBackOff, ImagePullBackOff, etc.).
  * **Purpose:** Identified that `worker` was crashing, `reporter` was failing readiness probes, and `metrics` was completely missing.

* **`kubectl describe replicaset -n debug-lab -l app=metrics`**
  * **What it does:** Retrieves detailed Kubernetes events for the ReplicaSet managing the `metrics` deployment.
  * **Purpose:** Uncovered **Defect 4**, revealing that the `LimitRange` admission controller was blocking pod creation due to exorbitant CPU limits (4 cores requested vs 500m max).

* **`kubectl logs -n debug-lab deploy/worker`**
  * **What it does:** Streams the standard output/error logs from the `worker` pod.
  * **Purpose:** Uncovered **Defect 5**, revealing the Go panic: `open /var/cache/app/worker.state: read-only file system`.

* **`kubectl logs -n debug-lab deploy/reporter`**
  * **What it does:** Streams the logs from the `reporter` pod.
  * **Purpose:** Uncovered **Defect 2**, revealing the `403 Forbidden` error when the application attempted to list pods, indicating a flawed RBAC configuration.

* **`kubectl exec -n debug-lab deploy/gateway -- curl -s http://localhost:8080/status`**
  * **What it does:** Executes an HTTP GET request from *inside* the gateway pod targeting its own status endpoint.
  * **Purpose:** Uncovered **Defect 3**, showing the JSON response explicitly failing to resolve `backend.default.svc:8080` because the services were in `debug-lab`.

* **`kubectl describe pod -n debug-lab -l app=reporter`**
  * **What it does:** Fetches the granular events and probe statuses for the reporter pod.
  * **Purpose:** Uncovered **Defect 6**, revealing that the Kubernetes Readiness Probe was receiving `connection refused` on port `8080`, because the application was actually bound to port `8081`.

## 3. Advanced Troubleshooting: The Apple Silicon / QEMU Bug

When running the `amd64` `reporter` binary on an `aarch64` Mac host, QEMU truncated the network streams causing `unexpected end of JSON input`. The following commands were used to diagnose and bypass this hypervisor bug:

* **`kubectl run test-python --image=python:3.11-alpine --restart=Never -n debug-lab -- sleep 3600`**
  * **What it does:** Deploys a temporary native (non-emulated) Python pod into the cluster.
  * **Purpose:** Used to execute a manual HTTP request to the K8s API using Python to prove that the API server and network overlay were healthy, isolating the bug strictly to the `amd64` Go binary running under QEMU.

* **`docker run --rm --entrypoint sh docker.io/ebinterview/eb-debug-app:1.0.1 -c "cat /eb-debug-app | strings | grep http"`**
  * **What it does:** Extracts human-readable strings from the compiled Go binary.
  * **Purpose:** Used to reverse-engineer the application's source code, revealing the hardcoded Kubernetes API URL and allowing me to perfectly recreate the `main.go` source logic.

* **`docker run --rm -v $(pwd):/app -w /app golang:1.23-alpine sh -c "GOOS=linux GOARCH=arm64 go build -o arm-reporter main.go"`**
  * **What it does:** Spins up an ephemeral Go compiler container, mounts the recreated `main.go` file, and cross-compiles it strictly for Linux ARM64.
  * **Purpose:** Generates a native binary that bypasses Docker Desktop's QEMU emulation layer entirely.

* **`docker cp arm-reporter demo-control-plane:/usr/local/bin/arm-reporter`**
  * **What it does:** Copies the compiled native ARM64 binary directly from the host filesystem into the isolated Kind cluster node (`demo-control-plane`).
  * **Purpose:** Places the native binary onto the node so it can be mounted into the pod using a `hostPath` volume.

* **`kubectl rollout restart deployment reporter -n debug-lab`**
  * **What it does:** Forces the Kubernetes deployment to terminate existing pods and spin up new ones.
  * **Purpose:** Ensures the deployment picks up the newly mounted native binary. (This resulted in the final 11/11 Green passing state!).
