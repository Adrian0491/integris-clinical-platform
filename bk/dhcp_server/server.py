from __future__ import annotations

import os
import socket
import struct
import threading
import time
from dataclasses import dataclass
from typing import Optional

from flask import Flask, Response, jsonify

from bk.logging.log_indexing import Logger


@dataclass
class Lease:
    ip: str
    expires: float


class DHCPServer:
    def __init__(
        self,
        server_ip:   str = "192.168.1.1",
        subnet_mask: str = "255.255.255.0",
        router:      str = "192.168.1.1",
        dns:         str = "8.8.8.8",
        lease_time:  int = 3600,
        ip_base:     str = "192.168.1.",
        pool_start:  int = 100,
        pool_end:    int = 150,
        flask_host:  str = "0.0.0.0",
        flask_port:  int = 5000,
        logger: Optional[Logger] = None,
    ) -> None:
        self.server_ip   = server_ip
        self.subnet_mask = subnet_mask
        self.router      = router
        self.dns         = dns
        self.lease_time  = lease_time
        self.ip_base     = ip_base
        self.pool_start  = pool_start
        self.pool_end    = pool_end
        self.flask_host  = flask_host
        self.flask_port  = flask_port

        self.leases:  dict[str, Lease] = {}
        self.offered: dict[str, str]   = {}
        self.lock = threading.Lock()

        self.log = logger or Logger(log_file="dhcp_server.log")
        self.app = Flask(__name__)
        self._setup_routes()
        self.log.info("DHCPServer initialised.")

    def _setup_routes(self) -> None:
        @self.app.route("/")
        def index() -> Response:
            return jsonify({"status": "CDCT DHCP server running"})

        @self.app.route("/leases", methods=["GET"])
        def get_leases() -> Response:
            with self.lock:
                return jsonify({
                    mac: {"ip": l.ip, "expires": l.expires}
                    for mac, l in self.leases.items()
                })

        @self.app.route("/leases/<mac>", methods=["DELETE"])
        def delete_lease(mac: str):
            with self.lock:
                if mac not in self.leases:
                    return jsonify({"error": "not found"}), 404
                deleted = self.leases.pop(mac)
                self.log.info(f"Lease deleted: MAC={mac} IP={deleted.ip}")
                return jsonify({"status": "deleted", "ip": deleted.ip})

        @self.app.route("/config", methods=["GET"])
        def get_config() -> Response:
            return jsonify({
                "server_ip":   self.server_ip,
                "subnet_mask": self.subnet_mask,
                "router":      self.router,
                "dns":         self.dns,
                "lease_time":  self.lease_time,
                "pool":        [f"{self.ip_base}{self.pool_start}",
                                f"{self.ip_base}{self.pool_end}"],
            })

    @staticmethod
    def _ip_to_bytes(ip: str) -> bytes: return socket.inet_aton(ip)
    @staticmethod
    def _bytes_to_ip(b: bytes) -> str:  return socket.inet_ntoa(b)
    @staticmethod
    def _mac_str(mac: bytes) -> str:    return ":".join(f"{b:02x}" for b in mac[:6])

    def _free_ip(self) -> Optional[str]:
        used = {l.ip for l in self.leases.values()} | set(self.offered.values())
        for i in range(self.pool_start, self.pool_end + 1):
            ip = f"{self.ip_base}{i}"
            if ip not in used:
                return ip
        return None

    @staticmethod
    def _parse_options(opts: bytes) -> dict[int, bytes]:
        result, i = {}, 0
        while i < len(opts):
            t = opts[i]
            if t == 255: break
            if t == 0:   i += 1; continue
            if i + 1 >= len(opts): break
            n = opts[i + 1]
            result[t] = opts[i + 2: i + 2 + n]
            i += 2 + n
        return result

    def _build_packet(self, xid: bytes, yiaddr: str, chaddr: bytes, msg_type: int,
                      requested_ip: Optional[str] = None) -> bytes:
        bootp = struct.pack(
            "!BBBB4sHH4s4s4s4s16s64s128s",
            2, 1, 6, 0, xid, 0, 0,
            b"\x00\x00\x00\x00",
            self._ip_to_bytes(yiaddr),
            self._ip_to_bytes(self.server_ip),
            b"\x00\x00\x00\x00",
            chaddr[:6] + b"\x00" * 10,
            b"\x00" * 64, b"\x00" * 128,
        )
        opts = bytearray(b"\x63\x82\x53\x63")
        opts += bytes([53, 1, msg_type])
        opts += bytes([54, 4]) + self._ip_to_bytes(self.server_ip)
        opts += bytes([51, 4]) + struct.pack("!I", self.lease_time)
        opts += bytes([1, 4])  + self._ip_to_bytes(self.subnet_mask)
        opts += bytes([3, 4])  + self._ip_to_bytes(self.router)
        opts += bytes([6, 4])  + self._ip_to_bytes(self.dns)
        if requested_ip:
            opts += bytes([50, 4]) + self._ip_to_bytes(requested_ip)
        opts += bytes([255])
        return bootp + bytes(opts)

    def _cleanup_loop(self) -> None:
        while True:
            now = time.time()
            with self.lock:
                expired = [m for m, l in self.leases.items() if l.expires < now]
                for m in expired:
                    ip = self.leases.pop(m).ip
                    self.log.warning(f"Expired: MAC={m} IP={ip}")
            time.sleep(30)

    def _dhcp_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("", 67))
        self.log.info("DHCP listening on UDP port 67...")

        while True:
            try:
                data, addr = sock.recvfrom(1024)
                if len(data) < 240:
                    continue
                xid, chaddr  = data[4:8], data[28:34]
                mac          = self._mac_str(chaddr)
                opts         = self._parse_options(data[240:])
                msg_opt      = opts.get(53)
                if not msg_opt:
                    continue
                msg_type = msg_opt[0]

                if msg_type == 1:   # DISCOVER
                    with self.lock:
                        ip = self.leases[mac].ip if mac in self.leases else self._free_ip()
                        if not ip: self.log.error(f"No free IPs for {mac}"); continue
                        self.offered[mac] = ip
                    sock.sendto(self._build_packet(xid, ip, chaddr, 2), ("<broadcast>", 68))
                    self.log.info(f"OFFER {ip} → {mac}")

                elif msg_type == 3:  # REQUEST
                    req = self._bytes_to_ip(opts[50]) if 50 in opts else None
                    with self.lock:
                        ip = req or self.offered.get(mac) or \
                             (self.leases[mac].ip if mac in self.leases else self._free_ip())
                        if not ip: self.log.error(f"No free IPs for ACK to {mac}"); continue
                        self.leases[mac] = Lease(ip=ip, expires=time.time() + self.lease_time)
                        self.offered.pop(mac, None)
                    sock.sendto(self._build_packet(xid, ip, chaddr, 5), ("<broadcast>", 68))
                    self.log.info(f"ACK {ip} → {mac}")

                elif msg_type == 7:  # RELEASE
                    with self.lock:
                        if mac in self.leases:
                            self.log.info(f"RELEASE {self.leases.pop(mac).ip} from {mac}")

            except Exception as e:
                self.log.error(f"Packet error from {addr}: {e}")

    def start(self) -> None:
        threading.Thread(target=self._dhcp_loop,    daemon=True, name="dhcp").start()
        threading.Thread(target=self._cleanup_loop,  daemon=True, name="cleanup").start()
        debug = os.getenv("ENV") == "dev"
        self.log.info(f"Flask API on {self.flask_host}:{self.flask_port} (debug={debug})")
        self.app.run(host=self.flask_host, port=self.flask_port, debug=debug)


if __name__ == "__main__":
    DHCPServer().start()
