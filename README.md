# jpt-mobile-perf-runner
Repository for the scripts used in testing performance on Android and iOS

### **Usage**

Before use, Open the script and change line 176 to match your own Android SDK path

*Android:* 
1. In Unity, use a script to test something, like an average frame time and output that result after x time to console (f.e. Debug.Log) with an identifier of "ZZRES>>" So an example of a result would look like this "ZZRES>>16.510" or "ZZRES>> Scene name: Test_01 | Frame time: 21.52ms"
2. Then run the python script following this structure: python adb_perf_runner.py {package_identifier} ({path to apk1} {path to apk2} ... ) 

OR

--folder {path to folder with all apks to test}

--run 10  (How many times the test will be repeated per apk)

--sleep 340 (This is the time for which the script sleeps before getting the result, it should be made up of - Test duration + amount of time to wait between tests)

--retry 5 (The amount of times to retry if a result was not reached after the sleep time. (Some devices break during the test or the results get lost, the default is 3, so you can just skip writing it if you want)

--device QWEFDJ3564S (Device serial key, to which the tests should be deployed. Doesn't need defining if you have only one device)

--startup (Write this keyword only if you are outputting a debug log at the very start of the app instead of after a test and want to measure the time it takes for the app to load)

--kibana (This is for kibana development right now, only write this if you have an elastic search server running. This is pretty much for development right now) 

An example of this sort of command could look like this
```
python adb_perf_runner.py com.speed.weed --folder C:\Unity_Projects\Project\APKS_TO_TEST\Vulkan --run 5 --sleep 400 --device M9643AQ9222Z8
```

### ** Snipe it **

To have Snipe it usability create a file "config.json" in your Android folder and add this info to it
```
{
    "snipeItKey" : "{Bearer snipeItKey}"
}
```
