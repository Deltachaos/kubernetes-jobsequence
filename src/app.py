import os
import yaml
import random
import string
import time
import logging
from kubernetes import client, config

def generate_random_suffix(length=6):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def create_configmap(namespace, name, data):
    v1 = client.CoreV1Api()
    metadata = client.V1ObjectMeta(name=name)
    configmap = client.V1ConfigMap(metadata=metadata, data=data)
    return v1.create_namespaced_config_map(namespace=namespace, body=configmap)

def delete_configmap(namespace, name):
    v1 = client.CoreV1Api()
    return v1.delete_namespaced_config_map(name=name, namespace=namespace)

def create_job(namespace, job_definition):
    batch_v1 = client.BatchV1Api()
    return batch_v1.create_namespaced_job(namespace=namespace, body=job_definition)

def wait_for_job_completion(namespace, job_name):
    batch_v1 = client.BatchV1Api()
    while True:
        job = batch_v1.read_namespaced_job(name=job_name, namespace=namespace)
        job_status = job.status
        if job_status.succeeded:
            logging.info(f"Job {job_name} succeeded.")
            return True
        if job_status.failed:
            logging.error(f"Job {job_name} failed.")
            return False
        logging.info(f"Job {job_name} status: {job_status.active} active pods.")
        time.sleep(5)

def read_configmap(namespace, name):
    v1 = client.CoreV1Api()
    return v1.read_namespaced_config_map(name=name, namespace=namespace).data

def read_job_files_from_directory(directory):
    job_files = []
    for filename in os.listdir(directory):
        if filename.endswith('.yaml') or filename.endswith('.yml'):
            with open(os.path.join(directory, filename), 'r') as file:
                job_files.append(file.read())
    return job_files

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("Starting the job sequence script.")

    config.load_incluster_config()
    namespace = os.getenv('NAMESPACE', 'default')
    configmap_name = os.getenv('JOB_CONFIGMAP')
    job_name_env = "job"

    if os.getenv('JOB_NAME'):
      job_name_env = os.getenv('JOB_NAME')

    v1 = client.CoreV1Api()

    if configmap_name:
        logging.info(f"Reading initial configmap: {configmap_name}")
        configmap = v1.read_namespaced_config_map(name=configmap_name, namespace=namespace)
        queue = list(configmap.data.values())
    else:
        logging.info("JOB_CONFIGMAP environment variable is not set. Reading job files from /jobs directory.")
        queue = read_job_files_from_directory('/jobs')

    while queue:
        yaml_definition = queue.pop(0)
        job_definition = yaml.safe_load(yaml_definition)

        result_configmap_name = f"{job_name_env}-{generate_random_suffix()}"

        if 'metadata' not in job_definition:
            job_definition['metadata'] = {}

        job_definition['metadata']['name'] = result_configmap_name
        
        # Create a configmap for job results
        logging.info(f"Creating result configmap: {result_configmap_name}")
        create_configmap(namespace, result_configmap_name, data={})

        if 'env' not in job_definition['spec']['template']['spec']['containers'][0]:
            job_definition['spec']['template']['spec']['containers'][0]['env'] = []
        
        # Modify job definition to include the result configmap
        job_definition['spec']['template']['spec']['containers'][0]['env'].append(
            client.V1EnvVar(name='JOBSEQUENCE_RESULT_CONFIGMAP', value=result_configmap_name)
        )

        # Create the job
        logging.info(f"Creating job: {job_definition['metadata']['name']}")
        job = create_job(namespace, job_definition)
        job_name = job.metadata.name

        # Wait for the job to complete
        logging.info(f"Waiting for job {job_name} to complete.")
        job_succeeded = wait_for_job_completion(namespace, job_name)

        # Read the result configmap
        logging.info(f"Reading result configmap: {result_configmap_name}")
        result_configmap_data = read_configmap(namespace, result_configmap_name)

        # Delete the result configmap
        logging.info(f"Deleting result configmap: {result_configmap_name}")
        delete_configmap(namespace, result_configmap_name)

        if not job_succeeded:
            logging.error("Exiting due to job failure.")
            exit(1)

        # Add items to the queue
        queue.extend(result_configmap_data.values())

    logging.info("Job sequence script completed.")

if __name__ == '__main__':
    main()
