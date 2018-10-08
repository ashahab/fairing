import subprocess
import os
import logging

from fairing.builders.dockerfile import DockerFile
from fairing.builders.container_image_builder import ContainerImageBuilder
from fairing.notebook_helper import get_notebook_name

logger = logging.getLogger('fairing')


class CmBuilder(ContainerImageBuilder):
    def __init__(self):
        self.docker_client = None
        self.dockerfile = DockerFile()

    def execute(self, repository, image_name, image_tag, base_image, dockerfile, publish, env):
        """Takes the source, nbconverts it to code, and creates a configmap out of it
        :param repository:
        :param image_name:
        :param image_tag:
        :param base_image:
        :param dockerfile:
        :param publish:
        :param env:
        :return:
        """
        nb_name = get_notebook_name()
        cmd = "jupyter nbconvert --to script /app/{} --output /tmp/code.py".format(nb_name)
        p = subprocess.Popen(cmd, env=os.environ)
        stdout, stderr = p.communicate()
        logger.info('Stdout: {}, stderr: {}, return_code'.format(stdout, stderr, p.returncode))
        if p.returncode:
            raise Exception("Could not assing podCIDR '%s' stdout: '%s', stderr: '%s'",
                            cmd,
                            stdout, stderr)
