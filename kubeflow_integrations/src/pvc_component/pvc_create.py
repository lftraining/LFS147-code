from kubernetes import client, config
import yaml
import requests
import uuid
from datetime import datetime
import time
from kfp import dsl

def generate_unique_volume_name(base_name):
    # Example of using a UUID
    unique_id = uuid.uuid4().hex[:3]
    # Example of using a timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    # Combine the base name with a unique identifier
    unique_job_name = f"{base_name}-{unique_id}-{timestamp}"
    return unique_job_name
      

def get_namespace():
    # Path to the namespace file inside a pod
    namespace_path = '/var/run/secrets/kubernetes.io/serviceaccount/namespace'
    with open(namespace_path, 'r') as file:
        return file.read().strip()

def monitor_pvc_status(api_instance, namespace, pvc_name, timeout_period, max_timeout):
    timeout_total = 0
    while True:
        if timeout_total > max_timeout:
            print("Reached max timeout waiting for PVC to become Bound.")
            sys.exit(1)

        try:
            # Get the current status of the PVC
            pvc_status = api_instance.read_namespaced_persistent_volume_claim(namespace=namespace, name=pvc_name).status.phase
            
            if pvc_status == "Bound":
                print("PVC is successfully Bound!")
                break  # PVC is Bound, exit the loop
            else:
                print(f"Waiting for PVC to bind. Current status: {pvc_status}")
                
        except client.exceptions.ApiException as e:
            print(f"Error querying PVC status: {e}")
            sys.exit(1)  # Exit script with an error due to API exception
        
        # Increment the timeout counter and wait before the next check
        timeout_total += 1
        time.sleep(timeout_period)
@dsl.component(target_image='chasechristensen/volume_component:v2')
def create_volume(pvc_name: str,timeout_period: float,max_timeout: float,storage_size: float)-> str:
    # Define the PVC specifications
    config.load_incluster_config()
    v1 = client.CoreV1Api()
    pvc_name=generate_unique_volume_name(pvc_name)
    pvc_spec = client.V1PersistentVolumeClaim(
        metadata=client.V1ObjectMeta(name=pvc_name),
        spec=client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],  # Adjust access modes as needed
            resources=client.V1ResourceRequirements(
                requests={"storage": str(storage_size)+"Gi"}
            ),
            storage_class_name="standard",
        ),
    )
    print(pvc_spec)
    namespace=get_namespace()
    created_pvc = v1.create_namespaced_persistent_volume_claim(namespace=namespace, body=pvc_spec)
    print(f"PVC {created_pvc.metadata.name} created in namespace {namespace}")
    monitor_pvc_status(api_instance=v1, namespace=namespace, pvc_name=pvc_name, timeout_period=timeout_period, max_timeout=max_timeout)
    return pvc_name

