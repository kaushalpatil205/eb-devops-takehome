#!/usr/bin/env bash
set -eo pipefail

echo "[INFO] Bootstrapping kind cluster 'demo'..."
cat << 'KIND' | kind create cluster --name demo --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
  - containerPort: 443
    hostPort: 443
    protocol: TCP
KIND

echo "[INFO] Installing ingress-nginx..."
helm upgrade --install ingress-nginx ingress-nginx \
  --repo https://kubernetes.github.io/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --set controller.hostPort.enabled=true \
  --set controller.service.type=NodePort \
  --set-string controller.nodeSelector."ingress-ready"=true \
  --wait

echo "[INFO] Building docker image for demo service..."
docker build -t demo-service:latest ./service

echo "[INFO] Loading image into kind cluster..."
kind load docker-image demo-service:latest --name demo

echo "[INFO] Installing Helm release 'demo' in namespace 'demo'..."
helm upgrade --install demo ./chart --namespace demo --create-namespace --wait

echo "--------------------------------------------------------"
echo "Setup complete! The service is running."
echo "Test it via: curl -H 'Host: demo.local' http://localhost/"
echo "--------------------------------------------------------"
