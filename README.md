# Enterprise Bot DevOps Takehome

This repository contains the completed DevOps Engineer take-home assignment. It includes a containerized application, a Helm chart, and fixes for the 6 deliberate bugs present in the `debug-lab` scenario.

## How to run and verify

1. **Setup everything end-to-end**: Run the automated setup script to build the cluster, install NGINX ingress, and deploy the service.
   ```bash
   ./setup.sh
   ```
2. **Verify Part 1 & 2 Service**:
   Send a curl request to the ingress host using the NGINX node port:
   ```bash
   curl -H "Host: demo.local" http://localhost:80/
   curl -H "Host: demo.local" http://localhost:80/healthz
   ```
3. **Verify Part 4 (Debug Lab)**:
   Navigate to the `lab/` directory, apply the fixes, and run the verification script:
   ```bash
   cd lab
   ./scenario.sh up
   ./scenario.sh verify
   ```

## Resource Requests and Limits

In the Helm chart (`values.yaml`), resources are set as follows:
```yaml
resources:
  requests:
    cpu: "50m"
    memory: "64Mi"
  limits:
    cpu: "200m"
    memory: "128Mi"
```
**Why these numbers?**
- **Requests:** The service is an incredibly lightweight Python `HTTPServer` answering with static JSON. It idles at almost 0 CPU and minimal RAM. `50m` (1/20th of a core) and `64Mi` memory is plenty to guarantee scheduling without wasting cluster capacity.
- **Limits:** Setting limits slightly higher (`200m` CPU / `128Mi` RAM) prevents a runaway process from impacting the node, while allowing for brief CPU bursts during startup or request spikes. Crucially, these limits are well within standard namespace `LimitRange` guardrails (like the `500m` maximum we encountered in the lab).

## Deliberate Omissions & Risks

- **Production-grade WSGI Server:** I used Python's built-in `http.server` for simplicity. **Risk:** It handles requests sequentially and blocks on I/O. Under load, this would cause severe latency or dropped connections.
- **TLS/HTTPS:** The ingress does not have a TLS certificate configured. **Risk:** Traffic is unencrypted, susceptible to interception. 
- **Automated CI/CD:** I didn't include a fully wired GitHub Action for automated deployments. **Risk:** Manual deployments increase the risk of human error and drift between Git and cluster state.

## Path to Production

To make this production-ready, I would:
1. **Application Layer:** Replace the built-in HTTP server with a robust ASGI/WSGI server like Gunicorn or Uvicorn behind FastAPI, enabling concurrent connections.
2. **Security:** Implement `cert-manager` to automatically issue TLS certificates (Let's Encrypt) for the Ingress, and run image scanning tools (Trivy/Snyk) in CI to block vulnerable dependencies.
3. **Observability:** Instrument the Python code with OpenTelemetry for tracing, expose standard Prometheus metrics natively, and ensure all logs output structured JSON.
4. **Resiliency:** Add HorizontalPodAutoscalers (HPA) targeting CPU utilization, and configure PodDisruptionBudgets (PDB) to guarantee minimum availability during node draining.

## How I used AI

I used Google's Antigravity agentic coding assistant to navigate the environment and speed up execution. 
- **Chart Analysis:** AI was used to quickly inspect manifests, run `kubectl get events`, and pinpoint anomalies like the LimitRange CPU violation and the missing read-only emptyDir volume.
- **Architecture Bug Bypassing:** The assignment was run on an Apple Silicon Mac using Docker Desktop QEMU. The AMD64 `reporter` binary suffered a hypervisor bug where QEMU truncated HTTP chunked TLS responses from the K8s API (`unexpected end of JSON input`). AI was used to decompile the application's strings, recreate the Go logic, cross-compile a native `aarch64` binary within a Docker sandbox, and `docker cp` it into the Kind node to bypass the emulation bug completely. (See the `troubleshooting/` directory for an in-depth breakdown of this process).
- **Documentation:** AI drafted the boilerplate markdown sections of this README and formatted the finding logs. All solutions and technical architectural decisions were defended, understood, and audited by myself.
