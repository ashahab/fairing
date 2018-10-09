import subprocess
import os
import stat
import json
from pkg_resources import resource_filename
import platform
import requests
import tempfile
import zipfile
import tarfile
import shutil
import logging

logger = logging.getLogger(__name__)

def get_mp_bin_path():
    plat = platform.system()
    if plat == "Linux":
        return resource_filename(__name__, "/usr/local/bin/mp-compiler")
    elif plat == "Windows":
        return resource_filename(__name__, "bin/metaparticle/windows/mp-compiler.exe")
    elif plat == "Darwin":
        return resource_filename(__name__, "bin/metaparticle/darwin/mp-compiler")
    else:
        raise Exception("Your platform is not supported.")


def ensure_metaparticle_present():
    install_path = get_mp_bin_path()
    if os.path.exists(install_path):
        return
    # update_metaparticle()


ensure_metaparticle_present()


class MetaparticleClient(object):

    def run(self, svc):
        if not os.path.exists('.metaparticle'):
            os.makedirs('.metaparticle')

        with open('.metaparticle/spec.json', 'w') as out:
            json.dump(svc, out)
        logger.info("Launching metaparticle")
        subprocess.check_call(["/usr/local/bin/mp-compiler", '-f', '.metaparticle/spec.json'])

    def cancel(self, name):
        subprocess.check_call(
            ["/usr/local/bin/mp-compiler", '-f', '.metaparticle/spec.json', '--delete'])

    def logs(self, name):
        subprocess.check_call(
            ["/usr/local/bin/mp-compiler", '-f', '.metaparticle/spec.json', '--deploy=false', '--attach=true'])
