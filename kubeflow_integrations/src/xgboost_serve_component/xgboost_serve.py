import sys
from kubernetes import client, config
import yaml
import requests
import uuid
from datetime import datetime
import time
from kfp import dsl
def monitor_server_status(api_instance, group, version, namespace, plural, service_name, timeout_period, max_timeout):
    timeout_total = 0
    while True:
        if timeout_total > max_timeout:
            print("Reached max timeout total waiting for service to become ready.")
            sys.exit(1)

        try:
            response = api_instance.get_namespaced_custom_object(
                group=group,
                version=version,
                namespace=namespace,
                plural=plural,
                name=service_name
            )
            conditions = response.get('status', {}).get('conditions', [])
            
            # Specifically check for the 'Ready' condition
            ready_condition = next((condition for condition in conditions if condition.get('type') == 'Ready'), None)
            if ready_condition and ready_condition.get('status') == 'True':
                print(f"Service {service_name} is ready!")
                break  # Exit the loop, service is ready
            else:
                # Provide more detailed output for debugging
                if ready_condition:
                    print(f"Waiting for service {service_name} to become ready. Current status: {ready_condition.get('status')}. Checking again in {timeout_period} seconds.")
                else:
                    print(f"Ready condition not found for service {service_name}. Checking again in {timeout_period} seconds.")
        except client.exceptions.ApiException as e:
            print(f"Error querying service status: {e}")
            sys.exit(1)  # Exit script with an error due to API exception
        
        # Increment the timeout counter and wait for the specified period before the next check
        timeout_total += 1
        time.sleep(timeout_period)

def get_yaml_from_git(repo_url):
    response = requests.get(repo_url)
    if response.status_code == 200:
        yaml_content = yaml.safe_load(response.text)          
        return yaml_content
    else:
        raise Exception(f"Failed to get YAML file from {repo_url}. Status code: {response.status_code}")
        sys.exit(1)     
def get_namespace():
    # Path to the namespace file inside a pod
    namespace_path = '/var/run/secrets/kubernetes.io/serviceaccount/namespace'
    with open(namespace_path, 'r') as file:
        return file.read().strip()

@dsl.component(target_image='chasechristensen/xgboost_serve_component:v3')
def create_inference_service(timeout_period: float,max_timeout: float,name: str,storageUri: str,raw_manifest_url: str)-> None:
    config.load_incluster_config()
    api_instance = client.CustomObjectsApi()
    body = get_yaml_from_git(raw_manifest_url)
    group = 'serving.kserve.io'
    version = 'v1beta1'
    plural = 'inferenceservices'
    body['metadata']['name'] = name
    print( body['metadata']['name'])
    body['spec']['predictor']['xgboost']['storageUri']="pvc://"+storageUri
    namespace=get_namespace()
    try:
        api_response = api_instance.create_namespaced_custom_object(group=group, version=version, namespace=namespace, plural=plural, body=body)
        print("Custom resource applied. Status: %s" % api_response) 
        print(f"Monitoring status...")
        monitor_server_status(api_instance, group, version, namespace, plural, body['metadata']['name'],timeout_period,max_timeout)      
    except client.exceptions.ApiException as e:
        print(f"Failed to apply {name}: {e}")
        sys.exit(1)
