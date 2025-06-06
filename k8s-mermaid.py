import yaml
import argparse
import sys
import os
from typing import Dict, List, Tuple, Any

def parse_kubernetes_resources(yaml_file: str) -> Tuple[Dict[str, Dict], List[Dict]]:
    """Parse Kubernetes YAML file and extract resources and relationships."""
    resources, relationships = {}, []
    
    if not os.path.exists(yaml_file):
        raise FileNotFoundError(f"YAML file not found: {yaml_file}")

    with open(yaml_file, 'r') as stream:
        try:
            documents = list(yaml.safe_load_all(stream))
            if not documents:
                raise ValueError("No documents found in YAML file")
                
            for doc in documents:
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
                    'labels': labels,
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
                            # Enhanced environment variable detection from ConfigMaps and Secrets
                            for env in c.get('env', []):
                                value_from = env.get('valueFrom', {})
                                env_name = env.get('name', 'unknown')
                                
                                for ref_type in ['secretKeyRef', 'configMapKeyRef']:
                                    ref = value_from.get(ref_type)
                                    if ref:
                                        if ref_type == 'secretKeyRef':
                                            target_kind = 'Secret'
                                            relation = 'reads_secret_key'
                                        else:
                                            target_kind = 'ConfigMap'
                                            relation = 'reads_configmap_key'
                                        
                                        relationships.append({
                                            'source_kind': kind,
                                            'source_name': name,
                                            'relation': relation,
                                            'target_kind': target_kind,
                                            'target_name': ref['name'],
                                            'namespace': namespace,
                                            'env_name': env_name,
                                            'key_name': ref.get('key')
                                        })
                            
                            # envFrom references (entire ConfigMap/Secret)
                            for env_from in c.get('envFrom', []):
                                for ref_type in ['secretRef', 'configMapRef']:
                                    ref = env_from.get(ref_type)
                                    if ref:
                                        if ref_type == 'secretRef':
                                            target_kind = 'Secret'
                                            relation = 'imports_all_secret'
                                        else:
                                            target_kind = 'ConfigMap'
                                            relation = 'imports_all_configmap'
                                        
                                        relationships.append({
                                            'source_kind': kind,
                                            'source_name': name,
                                            'relation': relation,
                                            'target_kind': target_kind,
                                            'target_name': ref['name'],
                                            'namespace': namespace
                                        })
                    # Enhanced volume mount detection
                    for volume in pod_spec.get('volumes', []):
                        volume_name = volume.get('name', 'unnamed')
                        for vol_type in ['configMap', 'secret', 'persistentVolumeClaim']:
                            vol = volume.get(vol_type)
                            if vol:
                                target_name = vol.get('name') or vol.get('claimName') or vol.get('secretName')
                                if target_name:
                                    relationships.append({
                                        'source_kind': kind,
                                        'source_name': name,
                                        'relation': f"mounts_{vol_type.lower()}",
                                        'target_kind': vol_type.replace('persistentVolumeClaim', 'PersistentVolumeClaim').capitalize(),
                                        'target_name': target_name,
                                        'namespace': namespace,
                                        'volume_name': volume_name
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
                    ports = spec.get('ports', [])
                    resource['ports'] = [(p.get('port'), p.get('protocol', 'TCP'), p.get('targetPort')) for p in ports]
                    resource['service_type'] = spec.get('type', 'ClusterIP')
                    resource['cluster_ip'] = spec.get('clusterIP')
                    resource['is_headless'] = spec.get('clusterIP') == 'None'
                    
                    selector = spec.get('selector', {})
                    if selector:
                        # Enhanced service targeting with port mapping
                        for port_info in ports:
                            port = port_info.get('port')
                            target_port = port_info.get('targetPort', port)
                            protocol = port_info.get('protocol', 'TCP')
                            
                            relationships.append({
                                'source_kind': 'Service',
                                'source_name': name,
                                'relation': f"exposes_{protocol.lower()}_{port}",
                                'target_selector': selector,
                                'namespace': namespace,
                                'port_mapping': f"{port}→{target_port}"
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
                    resource['min_replicas'] = spec.get('minReplicas')
                    resource['max_replicas'] = spec.get('maxReplicas')
                    relationships.append({
                        'source_kind': 'HorizontalPodAutoscaler',
                        'source_name': name,
                        'relation': 'controls',
                        'target_kind': scale_target.get('kind'),
                        'target_name': scale_target.get('name'),
                        'namespace': namespace
                    })
                    
                elif kind in ["ConfigMap", "Secret"]:
                    data_keys = list(doc.get('data', {}).keys()) if doc.get('data') else []
                    string_data_keys = list(doc.get('stringData', {}).keys()) if doc.get('stringData') else []
                    resource['data_keys'] = data_keys + string_data_keys
                    resource['secret_type'] = doc.get('type') if kind == 'Secret' else None
                    
                elif kind == "PersistentVolumeClaim":
                    resource['access_modes'] = spec.get('accessModes', [])
                    resource['storage_class'] = spec.get('storageClassName')
                    storage_requests = spec.get('resources', {}).get('requests', {})
                    resource['storage_size'] = storage_requests.get('storage')
                    
                elif kind == "Pod":
                    pod_spec = spec
                    resource['service_account_name'] = pod_spec.get('serviceAccountName')
                    containers = pod_spec.get('containers', [])
                    if containers:
                        resource['image'] = containers[0].get('image')
                        resource['container_count'] = len(containers)

        except yaml.YAMLError as exc:
            raise ValueError(f"Error parsing YAML file {yaml_file}: {exc}")

    # Post-process relationships to add PVC connections
    _add_pvc_relationships(resources, relationships)
    
    return resources, relationships

def _add_pvc_relationships(resources: Dict[str, Dict], relationships: List[Dict]):
    """Add relationships between StatefulSets and their PVCs."""
    for key, resource in resources.items():
        if resource['kind'] == 'StatefulSet':
            # Look for volume claim templates in the original resource
            # This is a simplified approach - in a real implementation you'd want to 
            # parse the volumeClaimTemplates from the StatefulSet spec
            pvc_name_pattern = f"{resource['name']}-data"  # Common pattern
            for pvc_key, pvc_resource in resources.items():
                if (pvc_resource['kind'] == 'PersistentVolumeClaim' and 
                    pvc_resource['namespace'] == resource['namespace'] and
                    pvc_name_pattern in pvc_resource['name']):
                    relationships.append({
                        'source_kind': 'StatefulSet',
                        'source_name': resource['name'],
                        'relation': 'claims_storage',
                        'target_kind': 'PersistentVolumeClaim',
                        'target_name': pvc_resource['name'],
                        'namespace': resource['namespace']
                    })

def sanitize_mermaid_name(name: str) -> str:
    """Sanitize names for Mermaid compatibility."""
    return name.replace('-', '_').replace('.', '_').replace(':', '_')

def get_resource_role(resource: Dict[str, Any]) -> str:
    """Determine the architectural role of a Kubernetes resource."""
    kind = resource['kind']
    
    if kind in ['Deployment', 'StatefulSet', 'DaemonSet', 'Job', 'CronJob', 'Pod']:
        # Analyze image to determine role
        image = resource.get('image', '')
        if any(db in image.lower() for db in ['postgres', 'mysql', 'mongodb', 'redis']):
            return 'database'
        elif any(web in image.lower() for web in ['nginx', 'apache', 'web', 'app']):
            return 'application'
        else:
            return 'workload'
    elif kind == 'Service':
        if resource.get('is_headless'):
            return 'database_service'
        elif resource.get('service_type') == 'LoadBalancer':
            return 'external_service' 
        else:
            return 'internal_service'
    elif kind in ['ConfigMap', 'Secret']:
        return 'configuration'
    elif kind == 'PersistentVolumeClaim':
        return 'storage'
    elif kind == 'Ingress':
        return 'gateway'
    else:
        return 'resource'

def format_attribute_value(value: Any) -> str:
    """Format attribute values for better readability."""
    if isinstance(value, list):
        if len(value) > 3:
            return f"[{len(value)} items]"
        elif len(value) == 0:
            return "[]"
        return str(value)
    elif isinstance(value, bool):
        return "✓" if value else "✗"
    return str(value)

def generate_mermaid_classdiagram_from_yaml(yaml_file: str, include_labels: bool = False) -> str:
    """Generate Mermaid class diagram from Kubernetes YAML file."""
    try:
        resources, relationships = parse_kubernetes_resources(yaml_file)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return ""
        
    if not resources:
        print("Warning: No resources found in YAML file", file=sys.stderr)
        return "classDiagram\n"
        
    mermaid_output = "classDiagram\n"
    entity_mapping = {k: sanitize_mermaid_name(k) for k in resources}

    # Group resources by namespace for better organization
    namespaces = {}
    for key, res in resources.items():
        ns = res['namespace']
        if ns not in namespaces:
            namespaces[ns] = []
        namespaces[ns].append((key, res))

    # Generate classes grouped by namespace
    for namespace, ns_resources in namespaces.items():
        if len(namespaces) > 1:
            mermaid_output += f"\n  %% Namespace: {namespace}\n"
            
        for key, res in ns_resources:
            entity_name = entity_mapping[key]
            excluded_attrs = ['labels', 'annotations'] if not include_labels else ['annotations']
            attributes = []
            
            for k, v in res.items():
                if v is not None and k not in excluded_attrs:
                    formatted_value = format_attribute_value(v)
                    if len(formatted_value) > 50:
                        formatted_value = formatted_value[:47] + "..."
                    attributes.append(f"+{k}: {formatted_value}")
            
            mermaid_output += f"class {entity_name} {{\n"
            if attributes:
                mermaid_output += "  " + "\n  ".join(attributes) + "\n"
            mermaid_output += "}\n"

    # Add relationships
    mermaid_output += "\n  %% Relationships\n"
    relationship_count = 0
    
    for rel in relationships:
        source_key = f"{rel['source_kind']}_{rel['namespace']}_{rel['source_name']}"
        source_entity = entity_mapping.get(source_key)
        if not source_entity:
            continue
            
        if 'target_name' in rel and 'target_kind' in rel and rel['target_name']:
            target_key = f"{rel['target_kind']}_{rel['namespace']}_{rel['target_name']}"
            target_entity = entity_mapping.get(target_key)
            if target_entity:
                mermaid_output += f"{source_entity} --> {target_entity} : {rel['relation']}\n"
                relationship_count += 1
        elif 'target_selector' in rel and rel['target_selector']:
            for key, res in resources.items():
                if (res['namespace'] == rel['namespace'] and 
                    res.get('labels') and 
                    all(item in res['labels'].items() for item in rel['target_selector'].items())):
                    target_entity = entity_mapping[key]
                    mermaid_output += f"{source_entity} --> {target_entity} : {rel['relation']}\n"
                    relationship_count += 1
    
    if relationship_count == 0:
        mermaid_output += "  %% No relationships found\n"

    return mermaid_output

def main():
    """Main function with command line argument support."""
    parser = argparse.ArgumentParser(
        description='Convert Kubernetes YAML files to Mermaid class diagrams',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python k8s-mermaid.py input.yaml
  python k8s-mermaid.py input.yaml -o diagram.mmd
  python k8s-mermaid.py input.yaml --include-labels"""
    )
    
    parser.add_argument('yaml_file', help='Input Kubernetes YAML file')
    parser.add_argument('-o', '--output', 
                       help='Output file (default: output_class.mmd)',
                       default='output_class.mmd')
    parser.add_argument('--include-labels', 
                       action='store_true',
                       help='Include labels in the class diagram')
    parser.add_argument('--quiet', '-q',
                       action='store_true', 
                       help='Suppress non-error output')
    
    args = parser.parse_args()
    
    try:
        mermaid_diagram = generate_mermaid_classdiagram_from_yaml(
            args.yaml_file, 
            include_labels=args.include_labels
        )
        
        if mermaid_diagram.strip() == "classDiagram":
            print("Error: No valid Kubernetes resources found", file=sys.stderr)
            sys.exit(1)
            
        if not args.quiet:
            print(mermaid_diagram)
            
        with open(args.output, 'w') as f:
            f.write(mermaid_diagram)
            
        if not args.quiet:
            print(f"\nDiagram saved to: {args.output}", file=sys.stderr)
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
