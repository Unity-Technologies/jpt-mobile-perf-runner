import subprocess
import argparse
import sys
import time
import os

def run_on_ios(ios_device, path,sleep):
    try:
        p = subprocess.check_output(["ios-deploy",
        "-b",  path,
        "-i", ios_device,
        "-v",
        "-u",
        "-I"])
        out = str(p,'utf-8')
        lines= out.splitlines()
    except subprocess.CalledProcessError as e:
       raise RuntimeError("command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
    time.sleep(sleep)
    results = []
    ident = 'ZZRES>>'
    for line in lines:
        idx = line.find(ident)
        if idx == -1:
            continue
        results.append(line[idx + len(ident):])
    if len(results) == 0:
        return None
    return results[0]

def check_connected(ios_device):
    p = subprocess.check_output(["ios-deploy", "-c"])
    out = str(p, 'utf-8')
    lines = out.splitlines()
    for line in lines:
        if ios_device in line:
            return True
        else:
            continue
        return False

def check_directory_and_build (path):
    FNULL = open(os.devnull, 'w')
    os.chdir(path)
    for file in os.listdir(path):
        if file.endswith(".app"):
            return path+'/' + file
    print("Haven't found .app file in directory specified. Building it...")
    p = subprocess.check_output(["xcodebuild",
    "-project", path+'/Unity-iPhone.xcodeproj',
    "-scheme", "Unity-iPhone",
    "CONFIGURATION_BUILD_DIR="+ path,
    "-allowProvisioningUpdates"], stderr=FNULL)
    out = str(p,'utf-8')
    out = out.splitlines()

    for x in out:
        if "MkDir" in x:
            pathToApp = x.split()
            rez = pathToApp[1]
            print(rez)
    print("Finished building .app file")
    return rez

def main():
    parser = argparse.ArgumentParser(prog='ios-runner')
    parser.add_argument(
        'path', type=str, nargs = '*', default = None,
        help="Path to built Xcode project. Can be more than 1.")
    parser.add_argument(
        '--run', type=int, default=1,
        help='Number of times to run app')
    parser.add_argument(
        '--device', type=str, default=None,
        help='Device identifier (use `instruments -s devices` to find that)')
    parser.add_argument(
        '--sleep', type=int, default=60*5,
        help='Time to sleep before fetching results')

    args = parser.parse_args()

    if not check_connected(args.device):
        print("Device ID you've specified is not connected to your computer.")
        sys.exit()

    paths_to_app =[]

    for i in args.path:
        paths_to_app.append(check_directory_and_build(i))


    result_sets = []
    dir_names = []

    for i in range(len(args.path)):
            result_sets.append([])

    for x in args.path:
        rez = x.split('/')
        result = rez[-1]
        dir_names.append(result)
    
    for i in range(args.run):
        for i_proj, proj in enumerate(args.path):
            result = run_on_ios(args.device, paths_to_app[i_proj], args.sleep)
            print('Result set {0}: {1}'.format(i_proj, result))
            result_sets[i_proj].append(result)

    print('--------------------------------')

    for i, result_set in enumerate(result_sets):
        print('Result set {0}'.format(i))
        print('Project name: ', dir_names[i])

        for r in result_set:
            print(r)

if __name__ == '__main__':
    main()
