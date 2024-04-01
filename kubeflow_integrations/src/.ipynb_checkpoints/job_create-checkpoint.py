
from kubernetes import client, config, utils
import yaml
import requests

def get_namespace():
    # Path to the namespace file inside a pod
    namespace_path = '/var/run/secrets/kubernetes.io/serviceaccount/namespace'
    with open(namespace_path, 'r') as file:
        return file.read().strip()

def get_yaml_from_git(repo_url,pvc_name):
    response = requests.get(repo_url)
    if response.status_code == 200:
        yaml_content = yaml.safe_load(response.text)
        
        # Assuming the structure of the YAML is consistent with your example,
        # update PVC names for both Master and Worker
        for role in ['Master', 'Worker']:
            if role in yaml_content['spec']['xgbReplicaSpecs']:
                for volume in yaml_content['spec']['xgbReplicaSpecs'][role]['template']['spec']['volumes']:
                    if volume['name'] == 'task-pv-storage':
                        volume['persistentVolumeClaim']['claimName'] = pvc_name
        
        return yaml_content
    else:
        raise Exception(f"Failed to get YAML file from {repo_url}. Status code: {response.status_code}")
        sys.exit(1)

# Load in-cluster Kubernetes configuration
config.load_incluster_config()

# Determine the namespace dynamically
namespace = get_namespace()

# URL to the raw YAML file in a Git repository
yaml_file_url = 'https://raw.githubusercontent.com/chasecadet/kubeflow_course/main/kubeflow_integrations/volcano_iris_train.yml'

# Get the XGBoostJob definition from the YAML file in the Git repository
crd_manifest = get_yaml_from_git(yaml_file_url)

# Define the details of the custom resource
group = 'kubeflow.org'  # API group of the XGBoostJob
version = 'v1'  # API version
plural = 'xgboostjobs'  # Plural form of the XGBoostJob custom resource definition (CRD)

# Get the API instance for custom objects
api_instance = client.CustomObjectsApi()

# Create the XGBoostJob
try:
    api_response = api_instance.create_namespaced_custom_object(
        group=group,
        version=version,
        namespace=namespace,
        plural=plural,
        body=crd_manifest,
    )
    print("Custom resource created. Status: %s" % api_response)
except client.ApiException as e:
    print("An exception occurred: %s" % e)