import requests

url = "http://toxiproxy:8474"

def add_toxic(proxy_name):
    requests.post(url+"/proxies/"+proxy_name+"/toxics",json = {
        "name":"toxic_timeout",
        "type":"timeout",
        "stream": "downstream",
        "attributes":{
            "timeout":1000
        }
    })

def remove_toxic(proxy_name):
    requests.delete(url+"/proxies/"+proxy_name+"/toxics/toxic_timeout")



    