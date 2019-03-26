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

def get_logcat(adb_cmd, filters=[]):
    if len(filters) > 0:
        # ignore others
        filters = ['-s'] + filters

    ret = call_program(adb_cmd + ['logcat', '-d'] + filters)
    #call_program(adb_cmd + ['logcat', '-c'])
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
    
def run_single_app(adb_cmd, app_name, apk_path, sleep_s, retry_amount, measure_start = False):
    counter = retry_amount + 1
    while True and counter > 0:
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
        #call_program(adb_cmd + ['shell' , 'input', 'keyevent' , '26'])
        if measure_start is not False:
            ret = measure_startup(adb_cmd, sleep_s)
        else: 
            print('waiting the remainder')
            time.sleep(sleep_s)
            ret = get_results_from_logcat(adb_cmd)
        if ret is not None:
            return ret
        counter -= 1
        print('Did not get result, retrying',counter,'more times')
    ret = 'Skipped after ' + str(retry_amount + 1) + ' attempts'
    return ret
    
def send_to_Kibana(url, device_id, sleep, result, headers):
    test_url = url + '/_update'
    print(test_url)
    #result_string = ""
    #for key,value in enumerate(results):
    #    result_string += key + " : " + value + "\n"
    #print(result_string)
    string = {
      "script" : {
        "source" : """
        int check = 0;
        for (int i = 0; i < ctx._source.results.length; i++) {
          if(ctx._source.results[i].containsValue(params.result_existing.serial)){
            ctx._source.results[i].data.add(params.result_existing.data);
            check = 1;
            break;
           }
          }
        if (check == 0 )ctx._source.results.add(params.result_new);
        """,
        "params" : 
        {
          "result_new" : {
            "serial" : device_id,
            "sleep" : str(sleep),
            "data" : [
                {
                "frame_time" : str(result)
              }
            ]
          },
          "result_existing" : {
            "serial" : device_id,
            "sleep" : str(sleep),
            "data" : {
                "frame_time" : str(result)
            }
          }
        }
      }
}
    print (string)
    r = requests.post(test_url, data = json.dumps(string), headers = headers, timeout = 5)
    print (r.text)
    
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
        '--retry', type=int, default=3,
        help='Amount of times to retry before skipping a test. Test will be run (1 + retry) amount of times')
    parser.add_argument(
        '--startup', action='store_true',
        help='Add this keyword to measure startup time. It will not collect the data, just measure time until data was output')
    parser.add_argument(
        '--kibana', action='store_true',
        help='Add this keyword to send data to local Kibana server (in development)')
    args = parser.parse_args()

    sdk_root = 'C:/Android_stuff/SDK'
    adb_path = os.path.join(sdk_root, 'platform-tools/adb')

    adb_cmd = [adb_path]
    result_sets = []
    if (args.kibana):
        kibana_url = "http://localhost:9200/performance/tests/"
        headers = {"Content-Type" : "application/json"}
        start_time = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        #print(start_time)
        test = {
        'test_started_date' : start_time,
        'test_finished_date' : start_time,
        'results' : []
        }
        r = requests.post(kibana_url , data = json.dumps(test, default=str), headers=headers, timeout=5)
        resp_json = r.json()
        #print(resp_json)
        test_id = resp_json["_id"]
        kibana_send_url = kibana_url + str(test_id)
        #print(kibana_send_url)
        
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
        return
    if args.startup is True:
        measure = True
    else:
        measure = False
        
    for i in range(len(apks)):
            result_sets.append([])
    call_program(adb_cmd + ['logcat', '-G', '10M'])
    level1 =  call_program(adb_cmd + ['shell', 'dumpsys', 'battery', '|', 'grep', 'level']).strip()
    
    
    for i in range(args.run):
        print('Cycle ', i , '\n')
        write_to_file(result_file_path, 'Cycle ' + str(i) + '\n')
        for i_apk, apk in enumerate(apks):
            tempBatLevel = call_program(adb_cmd + ['shell', 'dumpsys', 'battery', '|', 'grep', 'level']).strip()
            print('Battery level before test # ' + str(i_apk) + ' is ' + str(tempBatLevel.decode('utf-8')) + '\n')
            write_to_file(result_file_path, 'Battery level before test # ' + str(i_apk) + ' is ' + str(tempBatLevel.decode('utf-8')) + '\n')
            result = run_single_app(adb_cmd, args.app_name, apk, args.sleep, args.retry, measure)
            if(args.kibana):
                send_to_Kibana(kibana_send_url, device_id, args.sleep, result, headers)
            print('Result set {0}: {1}'.format(i_apk, result))
            write_to_file(result_file_path, 'Result set {0}: {1}'.format(i_apk, result) + '\n') 
            result_sets[i_apk].append(result)
    level2 = call_program(adb_cmd + ['shell', 'dumpsys', 'battery', '|', 'grep', 'level']).strip()
    print(result_sets)
    if(args.kibana):
        finish_time = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        body = {
            'doc' : {
                'test_finished_date' : finish_time
            }
        }
        r = requests.post(kibana_send_url + '/_update', data = json.dumps(body), headers = headers, timeout = 5)
    
    for set in result_sets:
            for string in set:
                write_to_file(result_file_path, string + '\n')
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
            write_payload += r + '\n'
        write_to_file(result_file_path, write_payload)


if __name__ == '__main__':
    main()
