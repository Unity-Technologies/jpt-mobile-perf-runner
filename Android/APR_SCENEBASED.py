#!/usr/bin/env python3

import argparse
import os
import time
import glob
import datetime
from utils.command import call_program
from utils.command import retry_call_program
import traceback
import json
import requests
import datetime
import six
import base64

def get_logcat(adb_cmd, filters=[]):
    if len(filters) > 0:
        # ignore others
        filters = ['-s'] + filters

    ret = call_program(adb_cmd + ['logcat', '-d'] + filters)
    return ret.decode('utf-8', errors='ignore')


def get_results_from_logcat(adb_cmd):
    filters = ['Unity', 'ActivityManager', 'PackageManager',
               'dalvikvm', 'DEBUG']
    out = get_logcat(adb_cmd, filters)
    lines = out.splitlines()
    results = []
    ident = 'ZZRES>>'
    for l in lines:
        idx = l.find(ident)
        if idx == -1:
            continue
        results.append(l[idx + len(ident):])
    if len(results) == 0:
        return None
    return results[0]

def get_attributes_from_logcat(adb_cmd):
    filters = ['Unity', 'ActivityManager', 'PackageManager',
                'dalvikvm', 'DEBUG']
    out = get_logcat(adb_cmd, filters)
    lines = out.splitlines()
    identArch = 'CPU ='
    identScript = 'Scripting Backend'
    identInfo = 'Built from'
    identUnity = 'Version'
    identBuildType = 'Build type'
    identVulkan = 'Vulkan API version'
    identGLES = 'OpenGL ES'
    identGraphics = 'Graphics API = '
    identStop = 'APP_STARTED'
    
    architecture = 'UNKNOWN'
    scriptingBackend = 'UNKNOWN'
    buildType = 'UNKNOWN'
    version = 'UNKNOWN'
    changeset = 'UNKNOWN'
    graphics_API = 'UNKNOWN'
    stop = False
    
    for l in lines:
        idxA = l.find(identArch)
        idxI = l.find(identInfo)
        idxV = l.find(identVulkan)
        idxG = l.find(identGLES)
        idxGfx = l.find(identGraphics)
        idxBt = l.find(identBuildType)
        
        if idxA > -1:
            architecture =  l[idxA:].split(identArch)[1].split(' ')[1]
        if idxI > -1:
            idxS = l.find(identScript)
            idxU = l.find(identUnity)

            if idxS > -1:
                scriptingBackend = l[idxS:].split('\'')[1]
            if idxU > -1:
                combined = l[idxU + len(identUnity):].split('\'')[1]
                version = combined.split('(')[0]
                changeset = combined.split('(')[1].split(')')[0]
        if idxV > -1:
            graphics_API = 'Vulkan'
        if idxG > -1:
            idxContext = l.find('Context level')
            if (idxContext > -1):
                graphics_API = l[idxContext + len('Context level'):].split('<')[1].split('>')[0]
        if idxBt > -1:
            buildType = l[idxBt + len(identBuildType):].split('\'')[1].split('\'')[0]
        if idxGfx > -1:
            graphics_API = l[idxGfx + len(identGraphics):]
        if l.find(identStop) > -1:
            stop = True
    return architecture, scriptingBackend, buildType, version, changeset, graphics_API.strip(), stop
    
def find_attributes(adb_cmd, timeout):
    ret = None
    stop = False
    start = time.time()
    ticker = start
    end = start + timeout
    while ticker < end and not stop:
        ticker = time.time()
        ret = get_attributes_from_logcat(adb_cmd)
        stop = ret[len(ret)-1]
    return ret
    
def measure_startup(adb_cmd, sleep):
    ret = None
    launchTime = None
    start = time.time()
    ticker = start
    end = start + sleep
    while ticker < end and ret is None:
        ticker = time.time()
        ret = get_results_from_logcat(adb_cmd)
    if ret is not None:
        launchTime = ticker - start
    time.sleep(max(start + sleep - ticker, 0))
    print(launchTime)
    return launchTime
    
def write_to_file(path,content):
    try:
        if (os.path.isfile(path)):
            file = open(path,'a')
        else:
            file = open(path, 'w')
        file.write(content)
        file.close()
    except EnvironmentError: 
        print ('Error writing to file', EnvironmentError) 

def run_single_app(adb_cmd, app_name, apk_path, measure_start, sleep_s):
    #counter = retry_amount + 1
    #while True and counter > 0:
    ret = ''
    #call_program(adb_cmd + ['shell' , 'input', 'keyevent' , '26']) #Unlock phone before test run
    #call_program(adb_cmd + ['shell' , 'input', 'keyevent' , '82'])
    #call_program(adb_cmd + ['shell' , 'input', 'keyevent' , '82'])
    #retry_call_program(adb_cmd + ['uninstall', app_name], retry_count = 3,
                 #check_returncode=False)  # check if app is installed at all
    retry_call_program(adb_cmd + ['shell', 'pm', 'clear', app_name], retry_count = 3,
                 check_returncode=False)  # app might have never existed
    time.sleep(5)
    retry_call_program(adb_cmd + ['install', '-r', '-d', apk_path], retry_count = 3)
    retry_call_program(adb_cmd + ['shell', 'sync'], retry_count = 3)
    retry_call_program(adb_cmd + ['logcat', '-c'], retry_count = 3)
    time.sleep(5)
    activity_name = '{}/com.unity3d.player.UnityPlayerActivity'.format(
        app_name)
    retry_call_program(adb_cmd + ['shell', 'am', 'start', '-n', activity_name], retry_count = 3)
    if measure_start is not False:
            print('Measuring startup time')
            ret = measure_startup(adb_cmd, sleep_s)
            time.sleep(5)
    return ret
    #call_program(adb_cmd + ['shell' , 'input', 'keyevent' , '26'])

    
def get_results(adb_cmd, sleep_s, retry_amount):
    print('waiting the remainder')
    time.sleep(sleep_s)
    ret = get_results_from_logcat(adb_cmd)
    if ret is not None:
        return ret
    return None
    
def send_to_Kibana(url, device_id, payload, headers, id):
    kibana_send_url = url + '/_update/' + str(id)
    try:
        float(payload)
        build_json = {
            'script' : {
            'source' : 'ctx._source.data.add(' + payload + ');'  
            }
        }
    except ValueError:
        build_json = {
            'script' : {
            'source' : 'ctx._source.error_log.add(\"' + payload + '\");'  
            }
        }
        
    if build_json:
        print("Sending to Kibana with id(" + id + ") -> "  , build_json)
        r = requests.post(kibana_send_url, data = json.dumps(build_json), headers = headers, timeout = 5)
        #print (r.text)
    
def get_device_Snipeit(adb_cmd, device_id):
    snipeItKey = ""
    name, tag = 'Unknown' , 'Unknown'
    with open('config.json') as json_file:
        config_data = json.load(json_file)
        snipeItKey = config_data['snipeItKey']
    headers = {'Accept-Language':'en,en-US;q=0.9','Accept-Encoding':'gzip,deflate,br','accept':'application/json', 'content-type':'application/json' , 'Authorization': snipeItKey}
    url = 'https://snipe-it.hq.unity3d.com/api/v1/hardware?search=' + device_id
    try:
        r = requests.get(url, headers = headers, timeout = 5)
    except:
        print('Failed to connect to Snipe-it')
        name, tag = 'Unknown', 'Unknown'
    else:
        data = json.loads(r.text)
        try:
            name = data['rows'][0]['name']
            tag = data['rows'][0]['asset_tag']
        except:
            return name,tag
    return name,tag

def output_parse(result, device_id, info, headers, start_time_kibana, kibana_url, test_template, apk_name, encoded_image):
    lines = result.split('----')
    lines = filter(None, lines)
    scene_name = 'UNKNOWN'
    try:
        idx = result.index('Skipped')
        print('Skipped sending to Kibana, because Error')
        return None
    except:
        if lines is None:
            print('Unable to parse separate entries by delimiter(----)')
            return None
        for i_line, line in enumerate(lines):
            elements = line.split('|')
            if elements is None or len(elements) < 2:
                print('Unable to parse separate entries by delimiter(|)')
                return None
            try:
                scene_name = elements[0].split(':')[1]
                data = elements[1].split(':')[1]
            except:
                print('Unable to parse separate entries by delimiter(:)')
                return None
            check_id = {
                "query" : {
                    "bool" : {
                        "must":[
                            {"match_phrase": {"scene_name" : scene_name}},
                            {"match_phrase": {"date_of_test" : start_time_kibana}},
                            {"match_phrase": {"apk_name" : apk_name}}
                        ]
                    }
                }
            }
            headers = {"Content-Type" : "application/json"}
            r = requests.get(kibana_url + '/_search', data = json.dumps(check_id), headers=headers, timeout = 5)
            if (not r.ok):
                print('Failed to check for existing data')
                return None
            json_r = json.loads(r.text)
            if (len(json_r['hits']['hits']) == 0):
                test = test_template
                test['target_architecture'] = info[0] 
                test['scripting_backend'] = info[1] 
                test['build_Type'] = info[2]
                test['unity_version'] = info[3] 
                test['changeset'] = info[4] 
                test['graphics_API'] = info[5] 
                test['scene_name'] = scene_name
                test['apk_name'] = apk_name
                #test['image'] = encoded_image.decode("utf-8")
                r = requests.post(kibana_url + '/_doc', data = json.dumps(test), headers = headers, timeout = 5)
                json_r = json.loads(r.text)
                id = json_r['_id']
                if (r.ok):
                    print('Created new test entry in kibana with id = ' + str(id))
                    send_to_Kibana(kibana_url, device_id, data, headers, id)
                else:
                    print('Unable to create new test entry')
                    return None
                #Send Request and get ID
            elif (len(json_r['hits']['hits']) == 1):
                id = json_r['hits']['hits'][0]['_id']
                send_to_Kibana(kibana_url, device_id, data, headers, id)
                #Get ID of existing entry and add to it
            else:
                print('Too many entries match the query')

def get_picture(adb_cmd, device_id, device_name, start_time_file, time_to_sleep, output_dir, apk_name, cycle):
    time.sleep(time_to_sleep)
    picture_name =  str(apk_name) + '_Cycle-' + str(cycle) + '_' + str(device_name.replace(' ','_')) + '_' + str(device_id) + '_' + str(start_time_file) + '.png'
    call_program(adb_cmd + ['shell', 'screencap', '/sdcard/' + picture_name])
    picture_dir = os.path.join(output_dir, 'pictures')
    if (os.path.isdir(picture_dir)) is False:
        os.makedirs(picture_dir)
    ret = call_program(adb_cmd + ['pull', '/sdcard/' + picture_name, picture_dir])
    call_program(adb_cmd + ['shell', 'rm', '-f', '/sdcard/' + picture_name])
    try:
        with open(os.path.join(picture_dir, picture_name), "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read())
    except FileNotFoundError:
        return 'Image unavailable'
    #print(encoded_string)
    return encoded_string
                
def main():
    parser = argparse.ArgumentParser(prog='adb_perf_runner')
    parser.add_argument(
        'app_name', type=str,
        help="App name")
    parser.add_argument(
        'apks', type=str, nargs='*', default=None,
        help="Paths to the apk files")
    parser.add_argument(
        '--folder', type=str, default=None,
        help='Folder with all the apks to run. Will override given individual apks')
    parser.add_argument(
        '--run', type=int, default=1,
        help='Number of times to run app')
    parser.add_argument(
        '--device', type=str, default=None,
        help='Device identifier (use `adb devices` to find that)')
    parser.add_argument(
        '--sleep', type=int, default=60*5,
        help='Time to sleep before fetching results')
    parser.add_argument(
        '--retry', type=int, default=2,
        help='Amount of times to retry before skipping a test. Test will be run (1 + retry) amount of times')
    parser.add_argument(
        '--startup', action='store_true',
        help='Add this keyword to measure startup time. It will not collect the data, just measure time until data was output')
    parser.add_argument(
        '--kibana', type=str,
        help='Define the project name that will be the index for sending info to Kibana')
    args = parser.parse_args()

    sdk_root = 'C:/Android_stuff/SDK'
    adb_path = os.path.join(sdk_root, 'platform-tools/adb')
    
    adb_cmd = [adb_path]
    device_name, device_tag = get_device_Snipeit(adb_cmd, args.device)
    result_sets = []
    
    start_time_kibana = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    start_time_file = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    dir_path = os.path.dirname(os.path.realpath(__file__))
    results_path = os.path.join(dir_path,'results')
    if (os.path.isdir(results_path)) is False:
        os.makedirs(results_path)
    if args.device is not None:
        adb_cmd += ['-s', args.device]
        device_id = args.device
    else:
        device_id = call_program(adb_cmd + ['shell','getprop','ro.boot.serialno']).strip()
        device_id = device_id.decode('ascii')
    output_dir = os.path.join(results_path, device_id)    
    if (os.path.isdir(output_dir)) is False:
        os.makedirs(output_dir)
    results_in_folder = glob.glob(os.path.join(output_dir,'*.txt'))
    result_file_name = str((len(results_in_folder) + 1)) + '_Test_run_' + str(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")) + '.txt'
    result_file_path = os.path.join(output_dir, result_file_name)
    write_to_file(result_file_path, 'BEGIN\n')
    if args.folder is not None:
        fullpath = os.path.join(args.folder, '*.apk')
        apks = glob.glob(fullpath)
        print('Using Folder to gather apks')
    elif len(args.apks) is not 0:
        apks = args.apks
        print('Using given list of apks \n')
    else:
        print('Input one of the following: A list of APKs, a folder with APKs to run \n')
        return None
    if args.startup is True:
        measure = True
    else:
        measure = False
        
    for i in range(len(apks)):
            result_sets.append([])
    call_program(adb_cmd + ['logcat', '-G', '10M'])
    level1 =  call_program(adb_cmd + ['shell', 'dumpsys', 'battery', '|', 'grep', 'level']).strip()
    if (args.kibana is not None):
        kibana_url = "http://10.37.34.49:9200/" + args.kibana.lower()
        r = requests.put(kibana_url, timeout=5)
        if r.ok:
            print('Index pattern created')
        else:
            json_r = json.loads(r.text)
            print('Unable to create index. REASON =  ',json_r['error']['type'])
        print(kibana_url)        
        headers = {"Content-Type" : "application/json"}
        test_template = {
            'device_serial' : args.device,
            'device_name' : device_name,
            'date_of_test' : start_time_kibana,
            'apk_name' : 'UNKNOWN',
            'scene_name' : 'UNKNOWN',
            'target_architecture' : 'UNKNOWN',
            'scripting_backend' : 'UNKNOWN',
            'build_Type' : 'UNKNOWN',
            'unity_version' : 'UNKNOWN',
            'changeset' : 'UNKNOWN',
            'graphics_API' : 'UNKNOWN',
            'image' : 'Image unavailable',
            'data' : [],
            'error_log' : []
            }
    
    for i in range(args.run):
        print('Cycle ', i , '\n')
        write_to_file(result_file_path, 'Cycle ' + str(i) + '\n')
        for i_apk, apk in enumerate(apks):
            tempBatLevel = call_program(adb_cmd + ['shell', 'dumpsys', 'battery', '|', 'grep', 'level']).strip()
            print('Battery level before test # ' + str(i_apk) + ' is ' + str(tempBatLevel.decode('utf-8')) + '\n')
            write_to_file(result_file_path, 'Battery level before test # ' + str(i_apk) + ' is ' + str(tempBatLevel.decode('utf-8')) + '\n')
            apk_name = os.path.basename(apk) 
            print('Running APK:' + str(apk_name)) 
            counter = args.retry + 1
            result = None
            info = None
            while (result is None and counter > 0):
                result = run_single_app(adb_cmd, args.app_name, apk, measure, args.sleep)
                info = find_attributes(adb_cmd, 5)
                #encoded_image = get_picture(adb_cmd, device_id, device_name, start_time_file, 1, output_dir, apk_name, i)
                encoded_image = ''
                if (not measure):
                    result = get_results(adb_cmd, args.sleep,  args.retry)
                counter -= 1
                if (result is None):
                    print('Did not get result, retrying',counter,'more times')
            if result is None and counter == 0:
                result = 'Test #' + str(i + 1) + ' Skipped after ' + str(args.retry + 1) + ' attempts'
            if(args.kibana is not None):
                output_parse(result, device_id, info, headers, start_time_kibana, kibana_url, test_template, apk_name, encoded_image)
            print('Result set {0}: {1}'.format(i_apk, result))
            write_to_file(result_file_path, 'Result set {0}: {1}'.format(i_apk, result) + '\n') 
            result_sets[i_apk].append(result)
    level2 = call_program(adb_cmd + ['shell', 'dumpsys', 'battery', '|', 'grep', 'level']).strip()
    print(result_sets)
    for set in result_sets:
            for string in set:
                write_to_file(result_file_path, str(string) + '\n')
    print('--------------------------------')
    write_payload = '--------------------------------' + '\n' + 'Battery on start ' + level1.decode('utf-8') + '\n' + 'Battery on finish ' + level2.decode('utf-8') + '\n'
    write_to_file(result_file_path, write_payload)
    print('Battery on start ' + level1.decode('utf-8'))
    print('Battery on finish ' + level2.decode('utf-8'))
    for i, result_set in enumerate(result_sets):
        print('Result set {0}'.format(i))
        write_to_file(result_file_path,'Result set {0}'.format(i) + '\n')	
        print('APK Name:',os.path.basename(apks[i]))
        write_to_file(result_file_path, 'APK Name:' + os.path.basename(apks[i]) + '\n')
        write_payload = ""
        for r in result_set:
            print(r)
            write_payload += str(r) + '\n'
        write_to_file(result_file_path, write_payload)


if __name__ == '__main__':
    main()
