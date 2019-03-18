
import json
import os
import re
from utils.commit import check_if_revision_in_range


def get_patch_name(path):
    return os.path.basename(path).split('.')[0]


class Patch:
    def __init__(self, revision_first, revision_last):
        self.path = None
        self.revision_first = revision_first
        self.revision_last = revision_last
        self.name = None

    @staticmethod
    def create(path, revision_first, revision_last):
        patch = Patch(revision_first, revision_last)
        patch.path = path
        patch.name = get_patch_name(path)
        return patch


class PatchConfig:
    def __init__(self):
        self._patches = []

    def parse_patch(self, json_patch, config_file_dir):
        rev_range = json_patch['range'].split('..')

        patch_path = os.path.join(config_file_dir, json_patch['path'])

        patch = Patch.create(patch_path, rev_range[0], rev_range[1])

        self._patches.append(patch)

    def parse(self, config_file):
        if not os.path.exists(config_file):
            raise Exception("config path does not exist " + config_file)
        self.path = config_file

        with open(config_file, 'r') as in_f:
            json_data = json.load(in_f)

        config_file_dir = os.path.abspath(os.path.dirname(config_file))

        for json_patch in json_data:
            self.parse_patch(json_patch, config_file_dir)

    def get_patches(self):
        return self._patches[:]


def get_patches_to_apply(cwd, base_revision, patches):
    return [patch for patch in patches
            if check_if_revision_in_range(cwd, base_revision,
                                          patch.revision_first,
                                          patch.revision_last)]


def get_commit_msg_for_patch(patch):
    return '[reu] Apply patch "{0}"'.format(patch.name)


def parse_patch_name_from_commit_desc(desc):
    m = re.match(r'\[reu\] Apply patch "(.*)"', desc)
    if m is None:
        return None
    return m.group(1)


def get_applied_patches_from_commits(commits):
    ret = []
    for c in commits:
        name = parse_patch_name_from_commit_desc(c.desc)
        if name is not None:
            ret.append(name)
    return ret
