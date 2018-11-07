from kubernetes import client as kube_client
from kubernetes import watch
from kubernetes import config
from kubernetes.client.rest import ApiException
import os
import json
import time
from fairing.utils import is_running_in_k8s, get_current_k8s_namespace
import logging
logger = logging.getLogger(__name__)
MAX_RETRIES = 100
MAX_REQUEST_TIMEOUT = 30
MAX_SLEEP_SECONDS = 3
MAX_STREAM_BYTES = 1024


class KubeClient(object):

    def __init__(self, kubeconfig="/var/run/kubernetes/config"):
        self.kubeconfig = kubeconfig
        self.load_config()

    def load_config(self):
        """Create kubernetes config from provided kubeconfig or in_cluster
        :return: an api_client
        """
        if not self.kubeconfig or not os.path.isfile(self.kubeconfig):
            config.load_incluster_config()

        else:
            config.load_kube_config(config_file=self.kubeconfig)

    def run(self, svc):
        if is_running_in_k8s():
            svc['namespace'] = get_current_k8s_namespace()
        else:
            svc['namespace'] = svc.get('namespace') or 'default'
        v1 = kube_client.CoreV1Api()
        v1.create_namespaced_config_map(namespace=svc['namespace'], body=svc['configMap'])
        api_response = v1.read_namespaced_config_map(name=svc['configMap']['metadata']['name'],
                                                     namespace=svc['namespace'],
                                                     pretty='true')
        logger.debug("Created configmap '%s'", api_response)
        api_instance = kube_client.CustomObjectsApi()
        group = 'kubeflow.org'  # str | The custom resource's group name
        version = 'v1alpha2'  # str | The custom resource's version
        plural = 'tfjobs'  # str | The custom resource's plural name.
        namespace = svc['namespace']
        body = svc['tfJob']
        api_response = api_instance.create_namespaced_custom_object(group, version, namespace, plural, body)
        logger.debug("Created tfjob '%s'", api_response)

    def load_configmap(self, name):
        v1 = kube_client.CoreV1Api()
        if is_running_in_k8s():
            namespace = get_current_k8s_namespace()
        else:
            namespace = 'default'
        config_map = v1.read_namespaced_config_map(name=name, namespace=namespace)
        return config_map.data

    def cancel(self, name):
        pass

    def logs(self, name, namespace):
        tail = None
        v1 = kube_client.CoreV1Api()
        ev = kube_client.EventsV1beta1Api()
        # Retry to allow starting of pod
        # TODO Use urllib3's retry
        retries = MAX_RETRIES
        while retries > 0:
            try:
                w = watch.Watch()
                for event in w.stream(ev.list_namespaced_event, namespace=namespace):
                    logger.info("Event: %s %s", event['type'], event['reason'])
                    if event['type'] == 'Normal' and event['reason'] == 'Started' and event['involvedObject']['name'] == name:
                        tail = v1.read_namespaced_pod_log(name, namespace, follow=True, _preload_content=False)
                break
            except ApiException as e:
                logger.error("error getting status for {} {}".format(name, str(e)))
                retries -= 1
                time.sleep(MAX_SLEEP_SECONDS)
        if tail:
            try:
                for chunk in tail.stream(MAX_STREAM_BYTES):
                    print(chunk)
            finally:
                tail.release_conn()

    def cleanup(self, name, namespace):
        # "Watch" till the job is finished
        api_instance = kube_client.CustomObjectsApi()
        job_name = name
        group = 'kubeflow.org'  # str | The custom resource's group name
        version = 'v1alpha2'  # str | The custom resource's version
        plural = 'tfjobs'  # str | The custom resource's plural name.
        retries = MAX_RETRIES
        while retries > 0:
            try:
                api_response = api_instance.get_namespaced_custom_object(group, version, namespace, plural, job_name)
                if bool(api_response['status']['conditions'][-1]['status']):
                    break
                retries -= 1
                time.sleep(MAX_SLEEP_SECONDS)
            except ApiException as e:
                logger.error("error getting status for {} {}".format(job_name, str(e)))
                break

        v1 = kube_client.CoreV1Api()
        body = kube_client.V1DeleteOptions()
        v1.delete_namespaced_config_map(name, namespace, body)
