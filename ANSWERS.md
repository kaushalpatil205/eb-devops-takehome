# Part 5 — Written Question

**Q1. Migration from ingress-nginx to Gateway API**

**Approach & Order of Operations:**
1. **Provision the Gateway Controller & CRDs:** Install the Gateway API CRDs and deploy a Gateway controller (e.g., Envoy Gateway, or the ingress-nginx Gateway API provider) alongside the existing `ingress-nginx` installation.
2. **Provision a new Gateway & IP:** Create the `Gateway` resource, which will provision a new LoadBalancer and allocate a new external IP address.
3. **Mechanical Translation:** Use a tool like `ingress2gateway` to automatically convert the 40 existing `Ingress` resources into `HTTPRoute` resources. 
4. **Deploy HTTPRoutes:** Apply the `HTTPRoute` manifests. At this stage, both `ingress-nginx` (via the old IP) and the new Gateway API controller (via the new IP) will route traffic to the same backend Services concurrently.
5. **Testing & Verification:** Test the new Gateway IP thoroughly using a local `/etc/hosts` override, ensuring TLS termination, headers, and routing work identically.
6. **DNS Cutover (Zero Downtime):** Update the DNS records (A/CNAME) for all hostnames to point to the new Gateway IP. Because both controllers are active and healthy, the propagation delay causes no downtime.
7. **Cleanup:** Once DNS propagation is fully complete and traffic to the old IP drops to zero, decommission the `ingress-nginx` controller and old `Ingress` objects.

**What I expect to break / Risks:**
- **Custom Annotations:** The hardest part of the migration will be complex `ingress-nginx` annotations (e.g., rate-limiting, custom Lua snippets, regex rewrites). These do not map 1:1 to standard `HTTPRoute` resources and will require manual translation using `ExtensionRef` or vendor-specific filters.
- **Certificate Management:** `cert-manager` integrations might clash if both controllers try to solve HTTP-01 challenges for the same hostnames concurrently. We must carefully scope the solver or rely on DNS-01 challenges during the transition.
- **External DNS:** If `external-dns` is actively managing records based on Ingress objects, deploying `HTTPRoutes` with the same hostnames might cause a split-brain DNS battle. We must freeze or reconfigure `external-dns` before the transition.
