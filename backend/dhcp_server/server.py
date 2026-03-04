import requests
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS

class DHCP_SERVER:
    def __init__(self,port,ip,subnet_mask, dns_ip):
        self.port = port
        self.ip = ip
        self.subnet_mask = subnet_mask
        self.dns_ip = dns_ip
        
app = Flask(__name__)
CORS(app)