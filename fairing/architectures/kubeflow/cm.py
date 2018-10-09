from fairing.architectures.kubeflow.basic import BasicArchitecture
from fairing.backend.kubeflow import KubeflowBackend
from fairing.notebook_helper import get_notebook_name
import subprocess
import os
import logging
logger = logging.getLogger(__name__)

class CMTraining(BasicArchitecture):
    def __init__(self, ps_count, worker_count):
        self.ps_count = ps_count
        self.worker_count = worker_count

    def add_jobs(self, svc, count, repository, img, name, volumes, volume_mounts):
        nb_name = get_notebook_name()
        cmd = "jupyter nbconvert --to script {} --output /tmp/code.py".format(nb_name).split()
        p = subprocess.Popen(cmd, env=os.environ)
        stdout, stderr = p.communicate()
        logger.info('Stdout: {}, stderr: {}, return_code'.format(stdout, stderr, p.returncode))
        if p.returncode:
            raise Exception("Could not convert '%s' stdout: '%s', stderr: '%s'",
                            cmd,
                            stdout, stderr)
        tfjobs = []
        # append configmap to volume and volumeMounts
        with open('/tmp/code.py') as f:
            code = f.read()
        configMaps = [{
            "name": name,
            "data": {
                "code.py": code
            }
        }]
        svc["configMaps"] = configMaps
        volume_mounts = volume_mounts or []
        volume_mounts.append({
            "name": "code",
            "mountPath": "/code"
        })
        volumes = volumes or []
        volumes.append({
            "name": code,
            "configMap": {
                "name": name
            }
        })
        for ix in range(count):
            tfjobs.append({
                "name": "{}-{}".format(name, ix),
                "replicaSpecs": [{
                    "replicaType": "MASTER",
                    "replicas": 1,
                    "containers": [
                        {
                            "image": img,
                            "volumeMounts": volume_mounts
                        }
                    ],
                    "volumes": volumes
                },
                    {
                    "replicaType": "WORKER",
                    "replicas": self.worker_count,
                    "containers": [
                        {
                            "image": img
                        }
                    ]
                },
                    {
                    "replicaType": "PS",
                    "replicas": self.ps_count,
                    "containers": [
                        {
                            "image": img
                        }]
                }]
            })

        svc["tfJobs"] = tfjobs
        logger.info("Svc '%s'".format(svc))
        return svc

    def get_associated_backend(self):
        return KubeflowBackend()
