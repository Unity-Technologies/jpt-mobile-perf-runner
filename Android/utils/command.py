
import os
import tempfile
import time
import signal
import subprocess
import traceback


def wait_for_process_exit(pr, timeout):
    i = 0.0
    while i < timeout:
        if pr.returncode is not None:
            return True
        time.sleep(0.1)
        i += 0.1
    return False


def kill_process(pr):
    os.kill(pr.pid, signal.SIGINT)
    if wait_for_process_exit(pr, 1.0):
        return
    pr.terminate()
    if wait_for_process_exit(pr, 1.0):
        return
    pr.kill()


def call_program_with_code(args, stdin=None, cwd=None):
    if stdin is None:
        pr = subprocess.Popen(args, cwd=cwd,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            out, err = pr.communicate()
        except KeyboardInterrupt:
            kill_process(pr)
            raise
    else:
        # subprocess.Popen opens pipes of fixed size which deadlock if we want
        # to both pass input and retrieve output
        with tempfile.TemporaryFile() as file_out:
            with tempfile.TemporaryFile() as file_err:
                with tempfile.TemporaryFile() as file_in:
                    file_in.write(stdin)
                    file_in.seek(0)
                    pr = subprocess.Popen(args, cwd=cwd,
                                          stdin=file_in,
                                          stdout=file_out, stderr=file_err)
                    try:
                        pr.communicate()
                    except KeyboardInterrupt:
                        kill_process(pr)
                        raise
                    file_out.seek(0)
                    file_err.seek(0)
                    out = file_out.read()
                    err = file_err.read()
    return out, err, pr.returncode

def retry_call_program(args, retry_count, **kwargs):
    success = False
    exc = None
    for retry in range(retry_count):
        try:
            return call_program(args, **kwargs)
        except ProgramError as e:
            exc = e
            traceback.print_exc()
            print('Got exception while running command, retrying...')
    raise exc

class ProgramError(Exception):
    def __init__(self, args, returncode):
        msg = "Program '{0}' returned exit code {1}".format(' '.join(args),
                                                            returncode)
        super().__init__(msg)
        self.args = args
        self.returncode = returncode


def call_program(args, stdin=None, cwd=None, check_returncode=True):
    out, _, code = call_program_with_code(args, stdin=stdin, cwd=cwd)
    #print(out)
    if check_returncode and code != 0:
        raise ProgramError(args, code)
    return out
