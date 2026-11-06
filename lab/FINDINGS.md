# Findings — Part 4 debug lab

---

## Defect 1

**Symptom** (what you observed — paste the real command output):
```text
==> installing the broken chart
level=WARN msg="upgrade failed" name=debug-lab error="server-side apply failed for object debug-lab/migrate batch/v1, Kind=Job: Job.batch \"migrate\" is invalid: spec.template: Invalid value: {\"labels\":{\"app\":\"migrate\"... \"restartPolicy\":\"Always\"}: Unsupported value: \"Always\": supported values: \"OnFailure\", \"Never\""
```

**Cause** (the actual root cause, not the symptom restated):
The `migrate-job.yaml` template configured the Job's pod template with `restartPolicy: Always`. Kubernetes `Job` resources run tasks to completion, so they strictly require `restartPolicy` to be either `Never` or `OnFailure`.

**Fix** (what you changed, and why this over alternatives):
I modified `broken-chart/templates/migrate-job.yaml` to set `restartPolicy: Never`. This is the correct Kubernetes API specification for a one-shot migration job.

**How I found it** (the sequence of commands/reasoning that led you here):
I ran `./scenario.sh up` which immediately failed and printed the Kubernetes API validation error explicitly pointing to the unsupported `restartPolicy` value in the Job object.

---

## Defect 2

**Symptom:**
```text
  FAIL  deployment reporter: 0/1 ready
```
And running `kubectl logs deployment/reporter -n debug-lab` showed:
```text
pod list failed: pods is forbidden: User "system:serviceaccount:debug-lab:reporter" cannot list resource "pods" in API group "" in the namespace "debug-lab"
```

**Cause:**
The RBAC configuration in `rbac.yaml` had two issues:
1. The ServiceAccount `reporter` was entirely missing from the templates.
2. The `RoleBinding` subjects array bound the Role to a ServiceAccount named `default`, not `reporter`.

**Fix:**
I appended a `ServiceAccount` manifest named `reporter` to `rbac.yaml`. I also updated the `RoleBinding` subjects block to correctly reference `name: reporter`.

**How I found it:**
The `./scenario.sh verify` output showed the reporter wasn't ready. Checking the reporter container logs revealed a Kubernetes API 403 Forbidden error. Inspecting `rbac.yaml` quickly showed the mismatched ServiceAccount name in the RoleBinding and the absence of the ServiceAccount object itself.

---

## Defect 3

**Symptom:**
```text
  FAIL  gateway /status reports backend=ok
```
Curling the gateway directly (`kubectl exec -n debug-lab deploy/gateway -- curl -s http://localhost:8080/status`) returned:
```json
{"self":"ok","backend":"error (Get \"http://backend.default.svc:8080/healthz\": dial tcp: lookup backend.default.svc on 10.96.0.10:53: no such host)"}
```

**Cause:**
The `gateway` pod is configured via `BACKEND_URL` in `values.yaml` to connect to `http://backend.default.svc:8080`. However, the entire lab is deployed into the `debug-lab` namespace, not `default`. 

**Fix:**
I updated `BACKEND_URL` in `values.yaml` to point to the correct namespace and port: `http://backend.debug-lab.svc:8081`.

**How I found it:**
I checked the `./scenario.sh verify` output. I then checked the gateway logs and executed a curl against the gateway's status endpoint, which explicitly printed the DNS resolution error for `backend.default.svc`.

---

## Defect 4

**Symptom:**
```text
  FAIL  deployment metrics: 0/1 ready
```
Running `kubectl describe replicaset -n debug-lab -l app=metrics` showed:
```text
Warning  FailedCreate  Error creating: pods "metrics-5d7f87bf59-4v2vw" is forbidden: maximum cpu usage per Container is 500m, but limit is 4
```

**Cause:**
The metrics deployment templates and `values.yaml` specify CPU requests of `2` (2 cores) and limits of `4` (4 cores). However, the namespace has a `LimitRange` named `debug-lab-guardrails` that restricts maximum CPU usage per container to `500m`. 

**Fix:**
I updated the resources block in `values.yaml` to request `50m` CPU and limit it to `200m` CPU. This satisfies the namespace `LimitRange` while providing adequate resources.

**How I found it:**
The metrics pod wasn't even being created. `kubectl get pods` showed no metrics pod. I checked the ReplicaSet events (`kubectl describe rs -l app=metrics`), which surfaced the LimitRange admission controller rejection.

---

## Defect 5

**Symptom:**
```text
  FAIL  deployment worker: 0/1 ready
```
Running `kubectl logs deployment/worker -n debug-lab` showed:
```text
panic: open /var/cache/app/worker.state: read-only file system
```

**Cause:**
The `worker` deployment is configured with a strict security context (`readOnlyRootFilesystem: true`). However, the application code requires write access to `/var/cache/app` to maintain its state.

**Fix:**
I modified `worker.yaml` to include an `emptyDir` volume named `cache-volume`, and mounted it to the container at `/var/cache/app`. This allows the application to write to the cache directory while keeping the rest of the root filesystem read-only.

**How I found it:**
Checking `kubectl get pods` showed the worker pod repeatedly in `CrashLoopBackOff`. Pulling the pod logs immediately exposed the Go panic indicating a write attempt to a read-only filesystem.

---

## Defect 6

**Symptom:**
The readiness probes were failing for multiple services (e.g. `backend`, `gateway`, `reporter`) even when the pods were running.
```text
Warning  Unhealthy  Readiness probe failed: Get "http://10.244.0.12:8080/healthz": dial tcp 10.244.0.12:8080: connect: connection refused
```

**Cause:**
The `values.yaml` file defined `common.port: 8080`. The Readiness Probes and Services were dynamically using this value. However, the prebuilt Docker image `eb-debug-app` internally listens on port `8081` by default.

**Fix:**
I changed `common.port: 8080` to `common.port: 8081` in `values.yaml`. This ensures all Kubernetes networking resources target the correct application port.

**How I found it:**
Checking the pod logs showed the application starting and printing: `listening on :8081`. However, running `kubectl describe pod` showed the Readiness probes were attempting to hit port `8080`, leading to connection refused errors.

