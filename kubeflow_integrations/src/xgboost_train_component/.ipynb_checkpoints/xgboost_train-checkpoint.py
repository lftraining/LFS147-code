import sys
from kubernetes import client, config
import yaml
import requests
import uuid
from datetime import datetime
import time
from kfp import dsl


def generate_unique_job_name(base_name):
    # Example of using a UUID
    unique_id = uuid.uuid4().hex[:3]
    # Example of using a timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    # Combine the base name with a unique identifier
    unique_job_name = f"{base_name}-{unique_id}-{timestamp}"
    return unique_job_name


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

def get_namespace():
    # Path to the namespace file inside a pod
    namespace_path = '/var/run/secrets/kubernetes.io/serviceaccount/namespace'
    with open(namespace_path, 'r') as file:
        return file.read().strip()

def apply_custom_resource_conditionally(api_instance, group, version, namespace, plural, body,timeout_period,max_timeout,worker_replicas,master_replicas):
    body['metadata']['name'] = generate_unique_job_name( body['metadata']['name']) 
    print( body['metadata']['name'])
    body['spec']['xgbReplicaSpecs']['Master']['replicas']=master_replicas
    body['spec']['xgbReplicaSpecs']['Worker']['replicas']=worker_replicas
    try:
        api_response = api_instance.create_namespaced_custom_object(group=group, version=version, namespace=namespace, plural=plural, body=body)
        print("Custom resource applied. Status: %s" % api_response) 
        print(f"Monitoring status...")
        monitor_job_status(api_instance, group, version, namespace, plural, body['metadata']['name'],timeout_period,max_timeout)
        
    except client.exceptions.ApiException as e:
        print(f"Failed to apply {name}: {e}")
        sys.exit(1)

def monitor_job_status(api_instance, group, version, namespace, plural, job_name, timeout_period, max_timeout):
    timeout_total = 0
    while True:
        if timeout_total > max_timeout:
            print("Reached max timeout total waiting for job to complete.")
            sys.exit(1)

        try:
            response = api_instance.get_namespaced_custom_object(
                group=group,
                version=version,
                namespace=namespace,
                plural=plural,
                name=job_name
            )
            conditions = response.get('status', {}).get('conditions', [])
            
            # Initialize flags for succeeded and failed conditions
            succeeded = False
            failed = False
            
            for condition in conditions:
                if condition.get('type') == 'Succeeded' and condition.get('status') == 'True':
                    succeeded = True
                elif condition.get('type') == 'Failed' and condition.get('status') == 'True':
                    failed = True
            
            # Check flags to determine next steps
            if succeeded:
                print("XGBOOST TRAIN Job succeeded!!")
                break  # Exit the while loop
            elif failed:
                print("XGBOOST TRAIN Job failed. Check")
                sys.exit(1)  # Exit script with an error
            
            # For debugging or monitoring, you might want to print the current condition type being checked
            print(f"Current condition checked: {conditions[-1].get('type') if conditions else 'None'}")

        except client.exceptions.ApiException as e:
            print(f"Error querying job status: {e}")
            sys.exit(1)  # Exit script with an error due to API exception
        
        # Increment the timeout counter and wait for the specified period before the next check
        timeout_total += 1
        time.sleep(timeout_period)


@dsl.component(target_image='chasechristensen/xgboost_train_component:v1')
def xgboost_train(yaml_file_url,claim_name,master_replica,worker_replica,pvc_name,raw_manifest_url,check_period,max_timeout,worker_replicas,master_replicas):
    config.load_incluster_config()
    api_instance = client.CustomObjectsApi()
    crd_manifest = get_yaml_from_git(yaml_file_url,claim_name)
    group = 'kubeflow.org'
    version = 'v1'
    plural = 'xgboostjobs'
    # Get namespace
    namespace = get_namespace()
    apply_custom_resource_conditionally(api_instance, group, version, namespace, plural, crd_manifest, timeout_period,max_timeout,worker_replicas,master_replicas)




