#!bin/bash

echo "Buscando IP no Google Cloud..."
PROJECT_ID="ces-igniteprogram"
export GATEWAY_IP=$(gcloud compute addresses describe gke-ip-lb --global --format='value(address)' --project $PROJECT_ID)
K8S_DIR="k8s"

envsubst < $K8S_DIR/microsservices/ngo-service/ngo-http-route.yaml.template > $K8S_DIR/microsservices/ngo-service/ngo-http-route.yaml
envsubst < $K8S_DIR/microsservices/donation-service/donation-http-route.yaml.template > $K8S_DIR/microsservices/donation-service/donation-http-route.yaml
envsubst < $K8S_DIR/microsservices/volunteer-service/volunteer-http-route.yaml.template > $K8S_DIR/microsservices/volunteer-service/volunteer-http-route.yaml
envsubst < $K8S_DIR/monitoring/monitoring-http-route.yaml.template > $K8S_DIR/monitoring/monitoring-http-route.yaml
envsubst < $K8S_DIR/argocd/argocd-http-route.yaml.template > $K8S_DIR/argocd/argocd-http-route.yaml

ansible-playbook -i /etc/ansible/hosts iac/ansible/playbooks/namespaces.yaml -e "env=$K8S_DIR"
ansible-playbook -i /etc/ansible/hosts iac/ansible/playbooks/keda.yaml -e "env=$K8S_DIR"
ansible-playbook -i /etc/ansible/hosts iac/ansible/playbooks/monitoring.yaml -e "env=$K8S_DIR"
ansible-playbook -i /etc/ansible/hosts iac/ansible/playbooks/argocd.yaml -e "env=$K8S_DIR"
ansible-playbook -i /etc/ansible/hosts iac/ansible/playbooks/applications.yaml -e "env=$K8S_DIR"
