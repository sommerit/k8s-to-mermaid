import yaml

def parse_kubernetes_resources(yaml_file):
    resources, relationships = {}, []

    with open(yaml_file, 'r') as stream:
        try:
            for doc in yaml.safe_load_all(stream):
                if not doc or 'kind' not in doc:
                    continue
                kind = doc['kind']
                metadata = doc.get('metadata', {})
                spec = doc.get('spec', {})
                name = metadata.get('name', 'Unnamed')
                namespace = metadata.get('namespace', 'default')
                labels = metadata.get('labels', {})
                api_version = doc.get('apiVersion', 'Unknown')

                resource = {
                    'kind': kind,
                    'api_version': api_version,
                    'name': name,
                    'namespace': namespace,
                    'service_account_name': None,
                    'image': None,
                    'ports': [],
                }

                key = f"{kind}_{namespace}_{name}"
                resources[key] = resource

                if kind in ["Deployment", "StatefulSet", "DaemonSet", "ReplicaSet", "Job", "CronJob"]:
                    pod_spec = spec.get('template', {}).get('spec', {})
                    resource['service_account_name'] = pod_spec.get('serviceAccountName')
                    containers = pod_spec.get('containers', [])
                    if containers:
                        container = containers[0]
                        resource['image'] = container.get('image')
                        for c in containers:
                            for env in c.get('env', []):
                                value_from = env.get('valueFrom', {})
                                for ref_type in ['secretKeyRef', 'configMapKeyRef']:
                                    ref = value_from.get(ref_type)
                                    if ref:
                                        relationships.append({
                                            'source_kind': kind,
                                            'source_name': name,
                                            'relation': f"uses_{ref_type.replace('KeyRef', '').lower()}",
                                            'target_kind': ref_type.replace('KeyRef', '').replace('Ref', ''),
                                            'target_name': ref['name'],
                                            'namespace': namespace
                                        })
                            for env_from in c.get('envFrom', []):
                                for ref_type in ['secretRef', 'configMapRef']:
                                    ref = env_from.get(ref_type)
                                    if ref:
                                        relationships.append({
                                            'source_kind': kind,
                                            'source_name': name,
                                            'relation': f"uses_{ref_type.replace('Ref', '').lower()}",
                                            'target_kind': ref_type.replace('Ref', ''),
                                            'target_name': ref['name'],
                                            'namespace': namespace
                                        })
                    for volume in pod_spec.get('volumes', []):
                        for vol_type in ['configMap', 'secret', 'persistentVolumeClaim']:
                            vol = volume.get(vol_type)
                            if vol:
                                relationships.append({
                                    'source_kind': kind,
                                    'source_name': name,
                                    'relation': f"mounts_{vol_type.lower()}",
                                    'target_kind': vol_type.capitalize(),
                                    'target_name': vol.get('name') or vol.get('claimName') or vol.get('secretName'),
                                    'namespace': namespace
                                })
                    if resource['service_account_name']:
                        relationships.append({
                            'source_kind': kind,
                            'source_name': name,
                            'relation': 'uses_serviceaccount',
                            'target_kind': 'ServiceAccount',
                            'target_name': resource['service_account_name'],
                            'namespace': namespace
                        })

                elif kind == "Service":
                    resource['ports'] = [(p.get('port'), p.get('protocol', 'TCP')) for p in spec.get('ports', [])]
                    selector = spec.get('selector', {})
                    if selector:
                        relationships.append({
                            'source_kind': 'Service',
                            'source_name': name,
                            'relation': 'targets',
                            'target_selector': selector,
                            'namespace': namespace
                        })

                elif kind == "Ingress":
                    for rule in spec.get('rules', []):
                        for path in rule.get('http', {}).get('paths', []):
                            service = path.get('backend', {}).get('service', {})
                            if service:
                                relationships.append({
                                    'source_kind': 'Ingress',
                                    'source_name': name,
                                    'relation': 'routes_to',
                                    'target_kind': 'Service',
                                    'target_name': service.get('name'),
                                    'namespace': namespace
                                })

                elif kind == "NetworkPolicy":
                    relationships.append({
                        'source_kind': 'NetworkPolicy',
                        'source_name': name,
                        'relation': 'applies_to',
                        'target_selector': spec.get('podSelector', {}).get('matchLabels', {}),
                        'namespace': namespace
                    })

                elif kind == "HorizontalPodAutoscaler":
                    scale_target = spec.get('scaleTargetRef', {})
                    relationships.append({
                        'source_kind': 'HorizontalPodAutoscaler',
                        'source_name': name,
                        'relation': 'controls',
                        'target_kind': scale_target.get('kind'),
                        'target_name': scale_target.get('name'),
                        'namespace': namespace
                    })

        except yaml.YAMLError as exc:
            print(f"Error parsing {yaml_file}: {exc}")

    return resources, relationships

def generate_mermaid_classdiagram_from_yaml(yaml_file):
    resources, relationships = parse_kubernetes_resources(yaml_file)
    mermaid_output = "classDiagram\n"

    entity_mapping = {k: k.replace('-', '_').replace('.', '_') for k in resources}

    for key, res in resources.items():
        entity_name = entity_mapping[key]
        attributes = [f"+{k}: {v}" for k, v in res.items() if v and k not in ['labels', 'annotations']]
        mermaid_output += f"class {entity_name} {{\n  " + "\n  ".join(attributes) + "\n}}\n"

    for rel in relationships:
        source_key = f"{rel['source_kind']}_{rel['namespace']}_{rel['source_name']}"
        source_entity = entity_mapping.get(source_key)
        if not source_entity:
            continue
        if 'target_name' in rel and 'target_kind' in rel:
            target_key = f"{rel['target_kind']}_{rel['namespace']}_{rel['target_name']}"
            target_entity = entity_mapping.get(target_key)
            if not target_entity:
                continue
            mermaid_output += f"{source_entity} --> {target_entity} : {rel['relation']}\n"
        elif 'target_selector' in rel:
            for key, res in resources.items():
                if res['namespace'] == rel['namespace'] and all(item in res['labels'].items() for item in rel['target_selector'].items()):
                    target_entity = entity_mapping[key]
                    mermaid_output += f"{source_entity} --> {target_entity} : {rel['relation']}\n"

    return mermaid_output

# Beispielaufruf
yaml_file = './extended_k8s.yaml'
mermaid_diagram = generate_mermaid_classdiagram_from_yaml(yaml_file)
if mermaid_diagram:
    print(mermaid_diagram)
    with open('output_class.mmd', 'w') as f:
        f.write(mermaid_diagram)
else:
    print("No output generated.")
