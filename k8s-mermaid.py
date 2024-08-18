import os
import yaml

def parse_kubernetes_resources(yaml_file):
    resources = {}
    service_account_links = []
    configmap_links = []
    service_links = []

    with open(yaml_file, 'r') as stream:
        try:
            docs = yaml.safe_load_all(stream)
            for doc in docs:
                if doc and isinstance(doc, dict) and 'kind' in doc:
                    kind = doc['kind']
                    api_version = doc.get('apiVersion', 'Unknown')
                    name = doc.get('metadata', {}).get('name', 'Unnamed')
                    namespace = doc.get('metadata', {}).get('namespace', 'default')
                    labels = doc.get('metadata', {}).get('labels', {})
                    image = None
                    ports = []
                    service_account_name = None
                    spec = doc.get('spec', {})

                    if kind == "Service":
                        ports = spec.get('ports', [])
                        selector = spec.get('selector', {})
                        if ports:
                            ports = [(p.get('port'), p.get('protocol', 'TCP')) for p in ports]
                        if selector:
                            service_links.append((name, selector, namespace, kind))

                    if kind == "Pod":
                        service_account_name = spec.get('serviceAccountName')

                    if kind == "Deployment":
                        pod_spec = spec.get('template', {}).get('spec', {})
                        service_account_name = pod_spec.get('serviceAccountName')
                        containers = pod_spec.get('containers', [])
                        volumes = pod_spec.get('volumes', [])
                        if containers:
                            image = containers[0].get('image', None)

                        # Sicherstellen, dass volumes existiert und iterierbar ist
                        if volumes is not None:
                            for volume in volumes:
                                if 'configMap' in volume:
                                    configmap_name = volume['configMap'].get('name')
                                    if configmap_name:
                                        configmap_links.append((name, configmap_name, namespace, kind))

                    add_resource(resources, kind, api_version, name, namespace, labels, image, ports, service_account_name)

                    if service_account_name:
                        service_account_links.append((name, service_account_name, namespace, kind))

        except yaml.YAMLError as exc:
            print(f"Error parsing {yaml_file}: {exc}")

    return resources, service_account_links, configmap_links, service_links

def add_resource(resources, kind, api_version, name, namespace, labels, image, ports, service_account_name):
    key = f"{kind}_{api_version}"
    if key not in resources:
        resources[key] = []
    resources[key].append((name, api_version, namespace, labels, image, ports, service_account_name))

def find_entity_name(resources, kind, name, namespace):
    entities = []
    for key, elements in resources.items():
        k, _ = key.split("_")
        if k == kind:
            for i, (n, _, ns, _, _, _, _) in enumerate(elements, start=1):
                if n == name and ns == namespace:
                    entities.append(f"{k}_{i}")
    return entities

def match_selector_labels(selector, labels):
    # Überprüfen, ob alle Schlüssel-Wert-Paare im selector in labels enthalten sind
    return all(item in labels.items() for item in selector.items())

def generate_mermaid_erdiagram_from_yaml(yaml_file):
    mermaid_output = "%%{init: {'theme':'forest'}}%%\nerDiagram\n"
    resources, service_account_links, configmap_links, service_links = parse_kubernetes_resources(yaml_file)

    # Standardfall, wenn keine Ressourcen gefunden wurden
    if not resources:
        mermaid_output += "NoResourcesFound {{\n  string message \"No Kubernetes resources found in the provided YAML.\"\n}}\n"

    for key, elements in resources.items():
        kind, api_version = key.split("_")
        for i, (name, api_version, namespace, labels, image, ports, service_account_name) in enumerate(elements, start=1):
            entity_name = f"{kind}_{i}"
            mermaid_output += f"{entity_name} {{\n"
            mermaid_output += f"  string kind \"{kind}\"\n"
            mermaid_output += f"  string name \"{name}\"\n"
            mermaid_output += f"  string api_version \"{api_version}\"\n"
            mermaid_output += f"  string namespace \"{namespace}\"\n"
            if service_account_name:
                mermaid_output += f"  string serviceAccountName \"{service_account_name}\"\n"
            if image:
                mermaid_output += f"  string image \"{image}\"\n"
            if ports:
                networking_info = ", ".join([f"Port: {port}, Protocol: {protocol}" for port, protocol in ports])
                mermaid_output += f"  string networking \"{networking_info}\"\n"
            mermaid_output += f"}}\n"

    # Links zwischen Deployments/Pods und ServiceAccounts basierend auf serviceAccountName
    for deployment_name, service_account_name, namespace, kind in service_account_links:
        deployment_entities = find_entity_name(resources, kind, deployment_name, namespace)
        service_account_entities = find_entity_name(resources, "ServiceAccount", service_account_name, namespace)
        for deployment_entity in deployment_entities:
            for service_account_entity in service_account_entities:
                if service_account_name:  # Überprüfen, ob serviceAccountName tatsächlich existiert
                    mermaid_output += f"{deployment_entity} ||--o| {service_account_entity} : I\n"

    # Links zwischen Deployments und ConfigMaps basierend auf Volumes
    for deployment_name, configmap_name, namespace, kind in configmap_links:
        deployment_entities = find_entity_name(resources, kind, deployment_name, namespace)
        configmap_entities = find_entity_name(resources, "ConfigMap", configmap_name, namespace)
        for deployment_entity in deployment_entities:
            for configmap_entity in configmap_entities:
                if configmap_name:  # Überprüfen, ob ConfigMap-Name tatsächlich existiert
                    mermaid_output += f"{deployment_entity} ||--o| {configmap_entity} : I\n"

    # Links zwischen Services und Deployments basierend auf Labels
    for service_name, selector, namespace, kind in service_links:
        service_entities = find_entity_name(resources, "Service", service_name, namespace)
        for key, elements in resources.items():
            resource_kind, _ = key.split("_")
            if resource_kind == "Deployment":
                for i, (name, _, ns, labels, _, _, _) in enumerate(elements, start=1):
                    if ns == namespace and match_selector_labels(selector, labels):
                        deployment_entity = f"{resource_kind}_{i}"
                        for service_entity in service_entities:
                            mermaid_output += f"{service_entity} ||--o| {deployment_entity} : I\n"

    return mermaid_output

# Beispielaufruf
yaml_file = './grafana.yaml'  # Hier den Pfad zu Ihrer YAML-Datei angeben
mermaid_diagram = generate_mermaid_erdiagram_from_yaml(yaml_file)
if mermaid_diagram:
    print(mermaid_diagram)
else:
    print("No output generated.")

# Mermaid-Diagramm in eine Datei schreiben
with open('output_er.mmd', 'w') as f:
    f.write(mermaid_diagram)
