# k8s-secrets-to-vault

Kubernetes Admission Webhook to sync K8s secrets to HashiCorp Vault

## Contents

* app - Python code for Admission Webhook
* k8s-manifests - Kubernetes manifests to deploy Admission Webhook
* Test - Vault Helm chart values file to deploy Vault for tests

## Deploy

### Build Docker image
```
docker build -t andreyasoskovwork/secrets-to-vault:0.1.0 -f Dockerfile .
docker push andreyasoskovwork/secrets-to-vault:0.1.0
```

### Create test environment

```
# Start Minikube
minikube start

# Deploy Vault
helm repo add hashicorp https://helm.releases.hashicorp.com
helm repo update
helm install --create-namespace  --namespace vault vault hashicorp/vault -f ./Test/Vault_Helm_chart/values.yaml
```

### Configure Vault
```
kubectl -n vault exec vault-0 -- vault status
kubectl -n vault exec vault-0 -- vault auth enable kubernetes

# Replace URL with correct URL to Kubernetes API Server
kubectl -n vault exec vault-0 -- vault write auth/kubernetes/config kubernetes_host=https://192.168.64.11:8443

# Create vault policy for prefix that would be used to store secrets
kubectl -n vault exec -it vault-0 -- vault policy write k8s-secrets - <<EOF
path "secret/data/k8s-secrets/*" {
  capabilities = ["create", "read", "update", "delete", "list", "patch" ]
}

path "secret/metadata/k8s-secrets/*" {
  capabilities = ["create", "read", "update", "delete", "list", "patch" ]
}
EOF

# Set SA
kubectl -n vault exec vault-0 -- vault write auth/kubernetes/role/k8s-secrets \
    bound_service_account_names=secrets-to-vault \
    bound_service_account_namespaces=secrets-to-vault \
    policies=k8s-secrets \
    ttl=24h
```

### Create TLS cert and key

Use the following names (service_name.namespace_name) for Cert:
* "secrets-to-vault"
* "secrets-to-vault.secrets-to-vault.svc"
* "secrets-to-vault.secrets-to-vault.svc.cluster.local"
* "127.0.0.1"

### Deploy Kubernetes manifests

```
kubectl apply -f ./k8s-manifests/0.Namespace.yaml
kubectl apply -f ./k8s-manifests/1.ConfigMap_envs.yaml  # Configure Vault connection params, secret prefix for Vault secrets storage and label selector for K8s secrets
kubectl apply -f ./k8s-manifests/2.1.SA.yaml
kubectl apply -f ./k8s-manifests/2.2.SA_secret.yaml
kubectl apply -f ./k8s-manifests/3.Secret_certs.yaml  # Configure TLS cert and key
kubectl apply -f ./k8s-manifests/4.Deployment.yaml  # Replace image with your image
kubectl apply -f ./k8s-manifests/5.PDB.yaml
kubectl apply -f ./k8s-manifests/6.Service.yaml
kubectl apply -f ./k8s-manifests/7.ValidatingWebhook.yaml
```

## Test
```
kubectl apply -f ./Test/Secret_to_test.yaml
```
