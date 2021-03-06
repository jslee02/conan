from conans.model import Generator
import platform
import os
import copy
from conans.errors import ConanException


def get_setenv_variables_commands(deps_env_info, command_set=None):
    if command_set is None:
        command_set = "SET" if platform.system() == "Windows" else "export"

    multiple_to_set, simple_to_set = get_dict_values(deps_env_info)
    ret = []
    for name, value in multiple_to_set.items():
        if platform.system() == "Windows":
            ret.append(command_set + ' "' + name + '=' + value + ';%' + name + '%"')
        else:
            ret.append(command_set + ' ' + name + '=' + value + ':$' + name)
    for name, value in simple_to_set.items():
        if platform.system() == "Windows":
            ret.append(command_set + ' "' + name + '=' + value + '"')
        else:
            ret.append(command_set + ' ' + name + '=' + value)
    return ret


def get_dict_values(deps_env_info):
    def adjust_var_name(name):
        return "PATH" if name.lower() == "path" else name
    multiple_to_set = {}
    simple_to_set = {}
    for name, value in deps_env_info.vars.items():
        name = adjust_var_name(name)
        if isinstance(value, list):
            # Allow path with spaces in non-windows platforms
            if platform.system() != "Windows" and name in ["PATH", "PYTHONPATH"]:
                value = ['"%s"' % v for v in value]
            multiple_to_set[name] = os.pathsep.join(value)
        else:
            simple_to_set[name] = value

    return multiple_to_set, simple_to_set


class VirtualEnvGenerator(Generator):

    @property
    def filename(self):
        return

    @property
    def content(self):
        old_venv = os.environ.get("_CONAN_VENV", None)
        if old_venv:
            raise ConanException("Deactivate the current virtual environment (or close the "
                                 "console) and then execute conan install again: %s" % old_venv)
        multiple_to_set, simple_to_set = get_dict_values(self.deps_env_info)
        all_vars = copy.copy(multiple_to_set)
        all_vars.update(simple_to_set)
        venv_name = os.path.basename(self.conanfile.conanfile_directory)
        venv_dir = self.conanfile.conanfile_directory
        deactivate_lines = ["@echo off"] if platform.system() == "Windows" else []
        for name in all_vars.keys():
            old_value = os.environ.get(name, "")
            if platform.system() == "Windows":
                deactivate_lines.append('SET "%s=%s"' % (name, old_value))
            else:
                deactivate_lines.append('export %s=%s' % (name, old_value))
        if platform.system() == "Windows":
            deactivate_lines.append("SET PROMPT=%s" % os.environ.get("PROMPT", ""))
            deactivate_lines.append("SET _CONAN_VENV=")
        else:
            deactivate_lines.append('export PS1="$OLD_PS1"')
            deactivate_lines.append("export _CONAN_VENV=")

        activate_lines = ["@echo off"] if platform.system() == "Windows" else []
        if platform.system() == "Windows":
            activate_lines.append('if defined _CONAN_VENV (echo Deactivate current venv first with %_CONAN_VENV%\deactivate.bat)')
            activate_lines.append('if defined _CONAN_VENV (EXIT /B)')
            activate_lines.append("SET PROMPT=(%s) " % venv_name + "%PROMPT%")
            activate_lines.append("SET _CONAN_VENV=%s" % venv_dir)
        else:
            activate_lines.append('if [ -n "$_CONAN_VENV" ]; then echo "Deactivate current venv first with \'source $_CONAN_VENV\deactivate"; fi')
            activate_lines.append('if [ -n "$_CONAN_VENV" ]; then exit; fi')
            activate_lines.append("export OLD_PS1=\"$PS1\"")
            activate_lines.append("export PS1=\"(%s) " % venv_name + "$PS1\"")
            activate_lines.append("export _CONAN_VENV=%s" % venv_dir)

        activate_lines.extend(get_setenv_variables_commands(self.deps_env_info))
        ext = "bat" if platform.system() == "Windows" else "sh"
        return {"activate.%s" % ext: os.linesep.join(activate_lines),
                "deactivate.%s" % ext: os.linesep.join(deactivate_lines)}
