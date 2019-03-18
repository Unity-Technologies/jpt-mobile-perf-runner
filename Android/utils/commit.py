
import json
import os
import time
from utils.command import call_program
from utils.command import ProgramError


def format_date_timestamp(timestamp):
    return time.strftime("%Y-%m-%d_%H%M%S", time.gmtime(timestamp))


class Commit:
    def __init__(self):
        self.desc = None
        self.revision = None
        self.branch = None
        self.date_str = None

    @staticmethod
    def from_hg_log(json_commit):
        commit = Commit()
        commit.desc = json_commit['desc']
        commit.revision = json_commit['node']
        commit.branch = json_commit['branch']
        commit.date_str = format_date_timestamp(json_commit['date'][0])
        return commit

    def __eq__(self, other):
        if not isinstance(other, Commit):
            return NotImplemented

        return self.__dict__ == other.__dict__

    def __repr__(self):
        return 'Commit(desc={0}, revision={1}, ' \
               'branch={2}, date_str={3})'.format(self.desc, self.revision,
                                                  self.branch, self.date_str)


def hg_log(cwd, revset):
    if not os.path.isdir(cwd):
        raise Exception('Mercurial dir {0} does not exist'.format(cwd))

    try:
        annotation = call_program(
            ['hg', 'log', '-Tjson', '-r', revset], cwd=cwd)
    except ProgramError:
        return []

    json_data = json.loads(annotation.decode('utf-8'))
    return [Commit.from_hg_log(json_commit) for json_commit in json_data]


def check_if_revision_in_range(cwd, revision, revision_first, revision_last):
    any_first = revision_first == 'first'
    any_last = revision_last == 'last'

    if any_first and any_last:
        return True
    if any_first:
        revs = hg_log(cwd, '{0} and ancestors({1})'.format(
            revision, revision_last))
    elif any_last:
        revs = hg_log(cwd, '{0} and descendants({1})'.format(
            revision, revision_first))
    else:
        revs = hg_log(cwd, '{0} and descendants({1}) and ancestors({2}) and \
                not descendants({2})'.format(revision, revision_first,
                                             revision_last))
    if len(revs) > 0:
        return True
    return False


def short_revision(rev):
    return rev[:12]


def get_tool_branch_name(base_commit):
    return 'reu/{0}-{1}-{2}'.format(base_commit.branch, base_commit.date_str,
                                    short_revision(base_commit.revision))
