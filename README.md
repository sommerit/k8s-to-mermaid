# Kubernetes to Mermaid Diagram Generator

This script parses Kubernetes YAML files and generates a Mermaid class diagram that visualizes the resources and their relationships within a Kubernetes cluster.

## Features

- **Supports multiple resource types**:
  - Processes various Kubernetes resources such as Deployments, StatefulSets, DaemonSets, Services, Ingresses, ConfigMaps, Secrets, PersistentVolumeClaims, NetworkPolicies, and HorizontalPodAutoscalers.

- **Relationship Mapping**:
  - Identifies and represents relationships between resources, including:
    - **Uses**: Indicates when a resource uses another resource (e.g., a Deployment uses a ConfigMap).
    - **Mounts**: Shows when a resource mounts a volume (e.g., a StatefulSet mounts a PersistentVolumeClaim).
    - **Targets**: Represents Services targeting workloads based on selectors.
    - **Controls**: Shows HorizontalPodAutoscalers controlling Deployments or StatefulSets.
    - **Applies To**: Displays NetworkPolicies applied to specific workloads.

- **Optimized and Compact**:
  - The script is optimized to be concise without losing functionality.

- **Customizable Output**:
  - Generates Mermaid class diagrams that can be easily visualized with tools like the [Mermaid Live Editor](https://mermaid.live/).

## Prerequisites

- **Python 3.x**
- **PyYAML Library**

  Install PyYAML using:

  pip install pyyaml


```mermaid
classDiagram
class Namespace_production_production {
  +kind: Namespace
  +api_version: v1
  +name: production
  +namespace: production
}
class ServiceAccount_production_app_serviceaccount {
  +kind: ServiceAccount
  +api_version: v1
  +name: app-serviceaccount
  +namespace: production
}
class ConfigMap_production_app_config {
  +kind: ConfigMap
  +api_version: v1
  +name: app-config
  +namespace: production
}
class Secret_production_db_secret {
  +kind: Secret
  +api_version: v1
  +name: db-secret
  +namespace: production
}
class PersistentVolumeClaim_production_db_pvc {
  +kind: PersistentVolumeClaim
  +api_version: v1
  +name: db-pvc
  +namespace: production
}
class Deployment_production_web_deployment {
  +kind: Deployment
  +api_version: apps/v1
  +name: web-deployment
  +namespace: production
  +service_account_name: app-serviceaccount
  +image: nginx:1.19
}
class StatefulSet_production_db_statefulset {
  +kind: StatefulSet
  +api_version: apps/v1
  +name: db-statefulset
  +namespace: production
  +service_account_name: app-serviceaccount
  +image: postgres:12
}
class DaemonSet_production_log_daemonset {
  +kind: DaemonSet
  +api_version: apps/v1
  +name: log-daemonset
  +namespace: production
  +service_account_name: app-serviceaccount
  +image: fluentd:latest
}
class Service_production_web_service {
  +kind: Service
  +api_version: v1
  +name: web-service
  +namespace: production
  +ports: [(80, 'TCP')]
}
class Service_production_db_service {
  +kind: Service
  +api_version: v1
  +name: db-service
  +namespace: production
  +ports: [(5432, 'TCP')]
}
class Ingress_production_web_ingress {
  +kind: Ingress
  +api_version: networking.k8s.io/v1
  +name: web-ingress
  +namespace: production
}
class IngressClass_default_nginx {
  +kind: IngressClass
  +api_version: networking.k8s.io/v1
  +name: nginx
  +namespace: default
}
class NetworkPolicy_production_allow_web {
  +kind: NetworkPolicy
  +api_version: networking.k8s.io/v1
  +name: allow-web
  +namespace: production
}
class HorizontalPodAutoscaler_production_web_hpa {
  +kind: HorizontalPodAutoscaler
  +api_version: autoscaling/v2
  +name: web-hpa
  +namespace: production
}
Deployment_production_web_deployment --> ServiceAccount_production_app_serviceaccount : uses_serviceaccount
Deployment_production_web_deployment --> ConfigMap_production_app_config : uses_configmap
Deployment_production_web_deployment --> ConfigMap_production_app_config : mounts_configmap
StatefulSet_production_db_statefulset --> ServiceAccount_production_app_serviceaccount : uses_serviceaccount
StatefulSet_production_db_statefulset --> Secret_production_db_secret : uses_secret
StatefulSet_production_db_statefulset --> PersistentVolumeClaim_production_db_pvc : mounts_persistentvolumeclaim
DaemonSet_production_log_daemonset --> ServiceAccount_production_app_serviceaccount : uses_serviceaccount
Service_production_web_service --> Deployment_production_web_deployment : targets
Service_production_db_service --> StatefulSet_production_db_statefulset : targets
Ingress_production_web_ingress --> Service_production_web_service : routes_to
NetworkPolicy_production_allow_web --> Deployment_production_web_deployment : applies_to
HorizontalPodAutoscaler_production_web_hpa --> Deployment_production_web_deployment : controls
```

## Gitlab Call

```bash
curl --request POST --header "PRIVATE-TOKEN: <your_access_token>" \
  --form "file=@output_er.mmd" \
  "https://gitlab.com/api/v4/projects/<your_project_id>/uploads"
```
