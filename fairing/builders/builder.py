from enum import Enum

from fairing.builders.cmbuilder import CmBuilder
from fairing.builders.knative import KnativeBuilder
from fairing.utils import is_running_in_k8s

class Builders(Enum):
    DOCKER = 1
    KNATIVE = 2
    CM = 3

def get_container_builder(builder_str=None):
    if builder_str == None:
        return get_default_container_builder()
    
    try:
        builder = Builders[builder_str.upper()]
    except KeyError:
        raise ValueError("Unsupported builder type: ", builder_str)

    return get_builder(builder)

def get_default_container_builder():
    if is_running_in_k8s():
        return get_builder(Builders.CM)
    return get_builder(Builders.CM)


def get_builder(builder):
    if builder == Builders.CM:
        return CmBuilder()
    elif builder == Builders.KNATIVE:
        return KnativeBuilder()
