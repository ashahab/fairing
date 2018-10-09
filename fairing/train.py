import signal
import sys
import types
import logging
import shutil

# from fairing.backend import get_backend, Native
from fairing.builders import get_container_builder
from fairing.utils import is_runtime_phase, get_image_full
from fairing.options import TensorboardOptions
from fairing.architectures.native.basic import BasicArchitecture
from fairing.strategies.basic import BasicTrainingStrategy
from fairing.metaparticle import MetaparticleClient
from fairing.utils import get_unique_tag

logger = logging.getLogger(__name__)

class Trainer(object):
    def __init__(self,
                 repository,
                 image_name='fairing-job',
                 image_tag=None,
                 publish=True,
                 dockerfile=None,
                 base_image=None,
                 tensorboard=None,
                 architecture=BasicArchitecture(),
                 strategy=BasicTrainingStrategy(),
                 builder=None):

        self.repository = repository
        self.image_name = image_name
        self.image_tag = image_tag
        
        self.publish = publish
        self.base_image = base_image
        self.dockerfile = dockerfile

        self.strategy = strategy
        self.architecture = architecture
        self.tensorboard_options = TensorboardOptions(**tensorboard) if tensorboard else None
        self.backend = self.architecture.get_associated_backend()
        self.strategy.set_architecture(self.architecture)

        self.builder = get_container_builder(builder)

        self.full_image_name = None

    def get_base_ast(self):
        return {
            "name": "{name}-{tag}".format(name=self.image_name, tag=self.image_tag),
            # Metaparticle does not generate a default GUID,
            # and we don't care about it's actual value
            "guid": 123456
        }
    
    def compile_ast(self):
        ast = self.get_base_ast()
        volumes = None
        volume_mounts = None
        if self.tensorboard_options:
            ast, volumes, volume_mounts = self.backend.add_tensorboard(
                ast, self.image_name, self.tensorboard_options)
        
        ast, env = self.strategy.add_training(
            ast, self.repository, self.image_name, self.image_tag, volumes, volume_mounts)
        logger.warn("Compiled ast '%s'.", ast)
        return ast, env

    def get_metaparticle_client(self):
        return MetaparticleClient()

    def fill_image_name_and_tag(self):
        if self.image_tag is None:
            self.image_tag = get_unique_tag()
        
        self.full_image_name = get_image_full(
            self.repository, self.image_name, self.image_tag)

    def deploy_training(self, stream_logs=True):
        logger.info("Deploying")
        self.fill_image_name_and_tag()
        ast, env = self.compile_ast()
        # image build
        self.builder.execute(self.repository,
                             self.image_name,
                             self.image_tag,
                             self.base_image,
                             self.dockerfile,
                             self.publish,
                             env)

        mp = self.get_metaparticle_client()

        def signal_handler(signal, frame):
            mp.cancel(self.image_name)
            sys.exit(0)
        signal.signal(signal.SIGINT, signal_handler)
        mp.run(ast)

        logger.warn("Training(s) launched.")

        if stream_logs:
            self.backend.stream_logs(self.image_name, self.image_tag)

    def start_training(self, user_class, *args, **kwargs):
        logger.warn("Starting user code!!!")
        self.strategy.exec_user_code(user_class, *args, **kwargs)


class Train(object):
    def __init__(self,
                 repository,
                 image_name='fairing-job',
                 image_tag=None,
                 publish=True,
                 dockerfile=None,
                 base_image=None,
                 tensorboard=None,
                 architecture=BasicArchitecture(),
                 strategy=BasicTrainingStrategy(),
                 builder=None):

        logger.setLevel(logging.DEBUG)
        self.trainer = Trainer(repository=repository,
                               image_name=image_name,
                               image_tag=image_tag,
                               publish=publish,
                               dockerfile=dockerfile,
                               base_image=base_image,
                               tensorboard=tensorboard,
                               architecture=architecture,
                               strategy=strategy,
                               builder=builder)

    def __call__(self, cls):
        # deploy training
        class UserClass(cls):
            # self refers to the Train instance
            # user_class is equivalentto self in the UserClass instance
            def __init__(user_class):
                user_class.is_training_initialized = False

            def __getattribute__(user_class, attribute_name, *args, **kwargs):
                # Overriding train in order to minimize the changes necessary in the user
                # code to go from local to remote execution.
                # That way, by simply commenting or uncommenting the Train decorator
                # Model.train() will execute either on the local setup or in kubernetes
                logger.info("Inside user class")
                if attribute_name != 'train' or user_class.is_training_initialized:
                    return super(UserClass, user_class).__getattribute__(attribute_name, *args, **kwargs)

                if attribute_name == 'train' and not is_runtime_phase():
                    return super(UserClass, user_class).__getattribute__('_deploy_training')

                user_class.is_training_initialized = True
                self.trainer.start_training(user_class, *args, **kwargs)
                return super(UserClass, user_class).__getattribute__('_noop_attribute')

            def _noop_attribute(user_class):
                pass

            def _deploy_training(user_class):
                self.trainer.deploy_training()

        return UserClass
