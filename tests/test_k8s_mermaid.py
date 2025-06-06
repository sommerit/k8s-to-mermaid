import os
import tempfile
import importlib.util
import pytest

MODULE_PATH = os.path.join(os.path.dirname(__file__), os.pardir, 'k8s-mermaid.py')
spec = importlib.util.spec_from_file_location('k8s_mermaid', MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

parse_kubernetes_resources = module.parse_kubernetes_resources
generate_mermaid_classdiagram_from_yaml = module.generate_mermaid_classdiagram_from_yaml

SIMPLE_YAML = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-dep
  labels:
    app: myapp
spec:
  template:
    spec:
      containers:
        - name: c
          image: myimage
  selector:
    matchLabels:
      app: myapp
---
apiVersion: v1
kind: Service
metadata:
  name: my-svc
spec:
  selector:
    app: myapp
  ports:
    - port: 80
"""

def write_temp_yaml(content):
    fd, path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w") as tmp:
        tmp.write(content)
    return path

def test_parse_kubernetes_resources_labels_and_relationships():
    path = write_temp_yaml(SIMPLE_YAML)
    try:
        resources, relationships = parse_kubernetes_resources(path)
        # Deployment resource should have labels stored
        dep_key = "Deployment_default_my-dep"
        assert dep_key in resources
        assert resources[dep_key]["labels"] == {"app": "myapp"}
        # Service should create a targets relationship to deployment
        assert any(
            r["relation"] == "targets" and r["source_kind"] == "Service" and r["target_selector"] == {"app": "myapp"}
            for r in relationships
        )
    finally:
        os.remove(path)

def test_generate_mermaid_classdiagram_from_yaml_contains_relationship():
    path = write_temp_yaml(SIMPLE_YAML)
    try:
        diagram = generate_mermaid_classdiagram_from_yaml(path)
        assert "Service_default_my_svc" in diagram
        assert "Deployment_default_my_dep" in diagram
        # Relationship arrow from service to deployment
        assert "Service_default_my_svc --> Deployment_default_my_dep : targets" in diagram
    finally:
        os.remove(path)
