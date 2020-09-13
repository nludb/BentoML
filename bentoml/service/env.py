# Copyright 2019 Atalaya Tech, Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import logging
import stat
from sys import version_info
from pathlib import Path
from typing import List

from bentoml.exceptions import BentoMLException
from bentoml.utils.ruamel_yaml import YAML
from bentoml import config
from bentoml.configuration import get_bentoml_deploy_version
from bentoml.saved_bundle.pip_pkg import (
    EPP_PKG_NOT_EXIST,
    EPP_PKG_VERSION_MISMATCH,
    parse_requirement_string,
    verify_pkg,
    seek_pip_dependencies,
)


logger = logging.getLogger(__name__)

PYTHON_VERSION = "{major}.{minor}.{micro}".format(
    major=version_info.major, minor=version_info.minor, micro=version_info.micro
)

# Including 'conda-forge' channel in the default channels to ensure newest Python
# versions can be installed properly via conda when building API server docker image
DEFAULT_CONDA_ENV_BASE_YAML = """
name: bentoml-default-conda-env
channels:
  - conda-forge
  - defaults
dependencies:
  - pip
"""


class CondaEnv(object):
    """A wrapper around conda environment settings file, allows adding/removing
    conda or pip dependencies to env configuration, and supports load/export those
    settings from/to yaml files. The generated file is the same format as yaml file
    generated from `conda env export` command.
    """

    def __init__(
        self,
        name: str = None,
        channels: List[str] = None,
        dependencies: List[str] = None,
        default_env_yaml_file: str = None,
    ):
        self._yaml = YAML()
        self._yaml.default_flow_style = False

        if default_env_yaml_file:
            env_yml_file = Path(default_env_yaml_file)
            if not env_yml_file.is_file():
                raise BentoMLException(
                    f"Can not find conda environment config yaml file at: "
                    f"`{default_env_yaml_file}`"
                )
            self._conda_env = self._yaml.load(env_yml_file)
        else:
            self._conda_env = self._yaml.load(DEFAULT_CONDA_ENV_BASE_YAML)

        if name:
            self.set_name(name)

        if channels:
            self.add_channels(channels)

        if dependencies:
            self.add_conda_dependencies(dependencies)

    def set_name(self, name):
        self._conda_env["name"] = name

    def add_conda_dependencies(self, conda_dependencies: List[str]):
        # BentoML uses conda's channel_priority=strict option by default
        # Adding `dependencies` to beginning of the list to take priority over the
        # existing conda channels
        self._conda_env["dependencies"] = (
            conda_dependencies + self._conda_env["dependencies"]
        )

    def add_channels(self, channels: List[str]):
        for channel_name in channels:
            if channel_name not in self._conda_env["channels"]:
                self._conda_env["channels"] += channels
            else:
                logger.debug(f"Conda channel {channel_name} already added")

    def write_to_yaml_file(self, filepath):
        with open(filepath, 'wb') as output_yaml:
            self._yaml.dump(self._conda_env, output_yaml)


class BentoServiceEnv(object):
    """Defines all aspect of the system environment requirements for a custom
    BentoService to be used. This includes:


    Args:
        pip_dependencies: list of pip_dependencies required, specified by package name
            or with specified version `{package_name}=={package_version}`
        pip_index_url: passing down to pip install --index-url option
        pip_trusted_host: passing down to pip install --trusted-host option
        pip_extra_index_url: passing down to pip install --extra-index-url option
        auto_pip_dependencies: Turn on to automatically find all the required
            pip dependencies and pin their version
        requirements_txt_file: pip dependencies in the form of a requirements.txt file,
            this can be a relative path to the requirements.txt file or the content
            of the file
        conda_channels: list of extra conda channels to be used
        conda_dependencies: list of conda dependencies required
        conda_env_yml_file: use a pre-defined conda environment yml filej
        setup_sh: user defined setup bash script, it is executed in docker build time
        docker_base_image: used when generating Dockerfile in saved bundle
    """

    def __init__(
        self,
        pip_dependencies: List[str] = None,
        pip_index_url: str = None,
        pip_trusted_host: str = None,
        pip_extra_index_url: str = None,
        auto_pip_dependencies: bool = False,
        requirements_txt_file: str = None,
        conda_channels: List[str] = None,
        conda_dependencies: List[str] = None,
        conda_env_yml_file: str = None,
        setup_sh: str = None,
        docker_base_image: str = None,
    ):
        self._python_version = PYTHON_VERSION
        self._pip_index_url = pip_index_url
        self._pip_trusted_host = pip_trusted_host
        self._pip_extra_index_url = pip_extra_index_url

        self._conda_env = CondaEnv(
            channels=conda_channels,
            dependencies=conda_dependencies,
            default_env_yaml_file=conda_env_yml_file,
        )

        bentoml_deploy_version = get_bentoml_deploy_version()
        self._pip_dependencies = ["bentoml=={}".format(bentoml_deploy_version)]
        if pip_dependencies:
            if auto_pip_dependencies:
                logger.warning(
                    "auto_pip_dependencies enabled, it may override package versions "
                    "specified in `pip_dependencies=%s`",
                    pip_dependencies,
                )
            self.add_python_packages(pip_dependencies)

        if requirements_txt_file:
            if auto_pip_dependencies:
                logger.warning(
                    "auto_pip_dependencies enabled, it may override package versions "
                    "specified in `requirements_txt_file=%s`",
                    requirements_txt_file,
                )
            self.add_packages_from_requirements_txt_file(requirements_txt_file)

        self._auto_pip_dependencies = auto_pip_dependencies

        self.set_setup_sh(setup_sh)

        if docker_base_image:
            self._docker_base_image = docker_base_image
        else:
            self._docker_base_image = config('core').get('default_docker_base_image')

    @staticmethod
    def check_dependency(dependency):
        name, version = parse_requirement_string(dependency)
        code = verify_pkg(name, version)
        if code == EPP_PKG_NOT_EXIST:
            logger.warning(
                '%s package does not exist in the current python ' 'session', name
            )
        elif code == EPP_PKG_VERSION_MISMATCH:
            logger.warning(
                '%s package version is different from the version '
                'being used in the current python session',
                name,
            )

    def add_conda_channels(self, channels: List[str]):
        self._conda_env.add_channels(channels)

    def add_conda_dependencies(self, conda_dependencies: List[str]):
        self._conda_env.add_conda_dependencies(conda_dependencies)

    def add_python_packages(self, pip_dependencies: List[str]):
        # Insert dependencies to the beginning of self.dependencies, so that user
        # specified dependency version could overwrite this. This is used by BentoML
        # to inject ModelArtifact or Adapter's optional pip dependencies
        self._pip_dependencies = pip_dependencies + self._pip_dependencies

    def set_setup_sh(self, setup_sh_path_or_content):
        self._setup_sh = None

        if setup_sh_path_or_content:
            setup_sh_file = Path(setup_sh_path_or_content)
        else:
            return

        if setup_sh_file.is_file():
            with setup_sh_file.open("rb") as f:
                self._setup_sh = f.read()
        else:
            self._setup_sh = setup_sh_path_or_content.encode("utf-8")

    def add_packages_from_requirements_txt_file(self, requirements_txt_path):
        requirements_txt_file = Path(requirements_txt_path)

        with requirements_txt_file.open("rb") as f:
            content = f.read()
            module_list = content.decode("utf-8").split("\n")
            self.add_python_packages(module_list)

    def save(self, path, bento_service):
        conda_yml_file = os.path.join(path, "environment.yml")
        self._conda_env.write_to_yaml_file(conda_yml_file)

        with open(os.path.join(path, "python_version"), "wb") as f:
            f.write(self._python_version.encode("utf-8"))

        requirements_txt_file = os.path.join(path, "requirements.txt")
        with open(requirements_txt_file, "wb") as f:
            if self._pip_index_url:
                f.write(f"--index-url={self._pip_index_url}\n".encode("utf-8"))
            if self._pip_trusted_host:
                f.write(f"--trusted-host={self._pip_trusted_host}\n".encode("utf-8"))
            if self._pip_extra_index_url:
                f.write(
                    f"--extra-index-url={self._pip_extra_index_url}\n".encode("utf-8")
                )

            dependencies_map = {}
            for dep in self._pip_dependencies:
                name, version = parse_requirement_string(dep)
                dependencies_map[name] = version

            if self._auto_pip_dependencies:
                bento_service_module = sys.modules[bento_service.__class__.__module__]
                if hasattr(bento_service_module, "__file__"):
                    bento_service_py_file_path = bento_service_module.__file__
                    reqs, unknown_modules = seek_pip_dependencies(
                        bento_service_py_file_path
                    )
                    dependencies_map.update(reqs)
                    for module_name in unknown_modules:
                        logger.warning(
                            "unknown package dependency for module: %s", module_name
                        )

                # Reset bentoml to configured deploy version - this is for users using
                # customized BentoML branch for development but use a different stable
                # version for deployment
                #
                # For example, a BentoService created with local dirty branch will fail
                # to deploy with docker due to the version can't be found on PyPI, but
                # get_bentoml_deploy_version gives the user the latest released PyPI
                # version that's closest to the `dirty` branch
                dependencies_map['bentoml'] = get_bentoml_deploy_version()

            # Set self._pip_dependencies so it get writes to BentoService config file
            self._pip_dependencies = []
            for pkg_name, pkg_version in dependencies_map.items():
                self._pip_dependencies.append(
                    "{}{}".format(
                        pkg_name, "=={}".format(pkg_version) if pkg_version else ""
                    )
                )

            pip_content = "\n".join(self._pip_dependencies).encode("utf-8")
            f.write(pip_content)

        if self._setup_sh:
            setup_sh_file = os.path.join(path, "setup.sh")
            with open(setup_sh_file, "wb") as f:
                f.write(self._setup_sh)

            # chmod +x setup.sh
            st = os.stat(setup_sh_file)
            os.chmod(setup_sh_file, st.st_mode | stat.S_IEXEC)

    def to_dict(self):
        env_dict = dict()

        if self._setup_sh:
            env_dict["setup_sh"] = self._setup_sh

        if self._pip_dependencies:
            env_dict["pip_dependencies"] = self._pip_dependencies

        env_dict["conda_env"] = self._conda_env._conda_env

        env_dict["python_version"] = self._python_version

        env_dict["docker_base_image"] = self._docker_base_image
        return env_dict