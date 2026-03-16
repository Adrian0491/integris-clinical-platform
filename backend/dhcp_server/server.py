import socket
import struct
import threading
import time
from typing import Optional

from attr import dataclass

from backend.logging import Logging
from flask import Flask, Response, request, jsonify
from types import Dict, TypedDict


@dataclass
class Lease:
    ip: str
    expires: float


class BasicDHCPServer:
    def __init__(
        self,
        server_ip: str = "192.168.1.1",
        subnet_mask: str = "255.255.255.0",
        router: str = "192.168.1.1",
        dns: str = "8.8.8.8",
        lease_time: int = 3600,
        ip_base: str = "192.168.1.",
        pool_start: int = 100,
        pool_end: int = 150,
        flask_host: str = "0.0.0.0",
        flask_port: int = 5000,
        logger: Optional[Logging] = None,
    ) -> None:
        self.server_ip: str = server_ip
        self.subnet_mask: str = subnet_mask
        self.router: str = router
        self.dns: str = dns
        self.lease_time: int = lease_time
        self.ip_base: str = ip_base
        self.pool_start: int = pool_start
        self.pool_end: int = pool_end
        self.flask_host: str = flask_host
        self.flask_port: int = flask_port

        self.leases: dict[str, Lease] = {}
        self.offered: dict[str, str] = {}
        self.lock: threading.Lock = threading.Lock()

        self.logger: Logging = logger if logger is not None else Logging(
            log_dir="../logs",
            log_file="dhcp_server.log",
        )

        self.app: Flask = Flask(__name__)
        self._setup_routes()

        self.logger.info("BasicDHCPServer initialized.")

    # -----------------------------
    # Flask routes
    # -----------------------------
    def _setup_routes(self) -> None:
        @self.app.route("/")
        def index() -> Response:
            self.logger.info("GET / called")
            return jsonify({"message": "Basic DHCP server + Flask API is running"})

        @self.app.route("/leases", methods=["GET"])
        def get_leases() -> Response:
            self.logger.info("GET /leases called")
            with self.lock:
                return jsonify({
                    mac: {
                        "ip": lease.ip,
                        "expires": lease.expires,
                    }
                    for mac, lease in self.leases.items()
                })

        @self.app.route("/leases/<mac>", methods=["DELETE"])
        def delete_lease(mac: str) -> Response | tuple[Response, int]:
            self.logger.warning(f"DELETE /leases/{mac} called")
            with self.lock:
                if mac in self.leases:
                    deleted: Lease = self.leases.pop(mac)
                    self.logger.info(f"Lease deleted for MAC {mac}, IP {deleted.ip}")
                    return jsonify({
                        "status": "deleted",
                        "lease": {
                            "ip": deleted.ip,
                            "expires": deleted.expires,
                        },
                    })
                self.logger.warning(f"Lease delete requested but not found for MAC {mac}")
                return jsonify({"error": "not found"}), 404

        @self.app.route("/config", methods=["GET"])
        def get_config() -> Response:
            self.logger.info("GET /config called")
            return jsonify({
                "server_ip": self.server_ip,
                "subnet_mask": self.subnet_mask,
                "router": self.router,
                "dns": self.dns,
                "lease_time": self.lease_time,
                "pool": [
                    f"{self.ip_base}{self.pool_start}",
                    f"{self.ip_base}{self.pool_end}",
                ],
            })

    # -----------------------------
    # Helpers
    # -----------------------------
    @staticmethod
    def ip_to_bytes(ip: str) -> bytes:
        return socket.inet_aton(ip)

    @staticmethod
    def bytes_to_ip(data: bytes) -> str:
        return socket.inet_ntoa(data)

    @staticmethod
    def mac_to_str(mac: bytes) -> str:
        return ":".join(f"{b:02x}" for b in mac[:6])

    def get_free_ip(self) -> Optional[str]:
        used_ips: set[str] = {lease.ip for lease in self.leases.values()}
        used_ips.update(self.offered.values())

        for i in range(self.pool_start, self.pool_end + 1):
            candidate: str = f"{self.ip_base}{i}"
            if candidate not in used_ips:
                return candidate
        return None

    @staticmethod
    def parse_dhcp_options(options: bytes) -> dict[int, bytes]:
        result: dict[int, bytes] = {}
        i: int = 0

        while i < len(options):
            option_type: int = options[i]

            if option_type == 255:
                break
            if option_type == 0:
                i += 1
                continue
            if i + 1 >= len(options):
                break

            length: int = options[i + 1]
            value: bytes = options[i + 2:i + 2 + length]
            result[option_type] = value
            i += 2 + length

        return result

    def build_dhcp_packet(
        self,
        xid: bytes,
        yiaddr: str,
        chaddr: bytes,
        msg_type: int,
        requested_ip: Optional[str] = None,
    ) -> bytes:
        op: int = 2
        htype: int = 1
        hlen: int = 6
        hops: int = 0
        secs: int = 0
        flags: int = 0x0000

        ciaddr: bytes = b"\x00\x00\x00\x00"
        yiaddr_b: bytes = self.ip_to_bytes(yiaddr)
        siaddr: bytes = self.ip_to_bytes(self.server_ip)
        giaddr: bytes = b"\x00\x00\x00\x00"

        chaddr_padded: bytes = chaddr[:6] + b"\x00" * 10
        sname: bytes = b"\x00" * 64
        boot_file: bytes = b"\x00" * 128
        magic_cookie: bytes = b"\x63\x82\x53\x63"

        bootp: bytes = struct.pack(
            "!BBBB4sHH4s4s4s4s16s64s128s",
            op,
            htype,
            hlen,
            hops,
            xid,
            secs,
            flags,
            ciaddr,
            yiaddr_b,
            siaddr,
            giaddr,
            chaddr_padded,
            sname,
            boot_file,
        )

        options = bytearray()
        options += magic_cookie
        options += bytes([53, 1, msg_type])
        options += bytes([54, 4]) + self.ip_to_bytes(self.server_ip)
        options += bytes([51, 4]) + struct.pack("!I", self.lease_time)
        options += bytes([1, 4]) + self.ip_to_bytes(self.subnet_mask)
        options += bytes([3, 4]) + self.ip_to_bytes(self.router)
        options += bytes([6, 4]) + self.ip_to_bytes(self.dns)

        if requested_ip is not None:
            options += bytes([50, 4]) + self.ip_to_bytes(requested_ip)

        options += bytes([255])

        return bootp + bytes(options)

    # -----------------------------
    # Background tasks
    # -----------------------------
    def cleanup_expired_leases(self) -> None:
        while True:
            now: float = time.time()
            with self.lock:
                expired: list[str] = [
                    mac for mac, lease in self.leases.items()
                    if lease.expires < now
                ]
                for mac in expired:
                    expired_ip: str = self.leases[mac].ip
                    del self.leases[mac]
                    self.logger.warning(f"Expired lease removed: MAC={mac}, IP={expired_ip}")
            time.sleep(30)

    def dhcp_server(self) -> None:
        sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        sock.bind(("", 67))
        self.logger.info("DHCP server listening on UDP 67...")

        while True:
            data: bytes
            addr: tuple[str, int]
            data, addr = sock.recvfrom(1024)

            if len(data) < 240:
                self.logger.warning(f"Ignored short packet from {addr}")
                continue

            try:
                xid: bytes = data[4:8]
                chaddr: bytes = data[28:34]
                client_mac: str = self.mac_to_str(chaddr)

                options: dict[int, bytes] = self.parse_dhcp_options(data[240:])
                msg_type_opt: Optional[bytes] = options.get(53)

                if msg_type_opt is None:
                    self.logger.warning(f"No DHCP message type found for packet from {client_mac}")
                    continue

                msg_type: int = msg_type_opt[0]

                if msg_type == 1:  # DHCPDISCOVER
                    with self.lock:
                        existing_lease: Optional[Lease] = self.leases.get(client_mac)
                        ip: Optional[str] = existing_lease.ip if existing_lease else None

                        if ip is None:
                            ip = self.get_free_ip()

                        if ip is None:
                            self.logger.error(f"No free IPs available for {client_mac}")
                            continue

                        self.offered[client_mac] = ip

                    offer: bytes = self.build_dhcp_packet(
                        xid=xid,
                        yiaddr=ip,
                        chaddr=chaddr,
                        msg_type=2,
                    )

                    sock.sendto(offer, ("<broadcast>", 68))
                    self.logger.info(f"Offered {ip} to {client_mac}")

                elif msg_type == 3:  # DHCPREQUEST
                    requested_ip: Optional[str] = None
                    if 50 in options:
                        requested_ip = self.bytes_to_ip(options[50])

                    with self.lock:
                        existing_lease: Optional[Lease] = self.leases.get(client_mac)
                        ip: Optional[str] = (
                            requested_ip
                            or self.offered.get(client_mac)
                            or (existing_lease.ip if existing_lease else None)
                        )

                        if ip is None:
                            ip = self.get_free_ip()

                        if ip is None:
                            self.logger.error(f"No free IPs available for ACK to {client_mac}")
                            continue

                        self.leases[client_mac] = Lease(
                            ip=ip,
                            expires=time.time() + self.lease_time,
                        )
                        self.offered.pop(client_mac, None)

                    ack: bytes = self.build_dhcp_packet(
                        xid=xid,
                        yiaddr=ip,
                        chaddr=chaddr,
                        msg_type=5,
                    )

                    sock.sendto(ack, ("<broadcast>", 68))
                    self.logger.info(f"Leased {ip} to {client_mac}")

                elif msg_type == 7:  # DHCPRELEASE
                    with self.lock:
                        if client_mac in self.leases:
                            released_ip: str = self.leases[client_mac].ip
                            del self.leases[client_mac]
                            self.logger.info(f"Released {released_ip} from {client_mac}")
                        else:
                            self.logger.warning(f"Release received for unknown MAC {client_mac}")

                else:
                    self.logger.warning(f"Unhandled DHCP message type {msg_type} from {client_mac}")

            except Exception as e:
                self.logger.error(f"Error handling packet from {addr}: {e}")

    # -----------------------------
    # Runner
    # -----------------------------
    def start(self) -> None:
        self.logger.info("Starting DHCP server threads...")
        threading.Thread(target=self.dhcp_server, daemon=True).start()
        threading.Thread(target=self.cleanup_expired_leases, daemon=True).start()

        self.logger.info(
            f"Starting Flask API on {self.flask_host}:{self.flask_port}"
        )
        self.app.run(host=self.flask_host, port=self.flask_port, debug=True)


if __name__ == "__main__":
    log = Logging(log_dir="../logs", log_file="dhcp_server.log")
    server = BasicDHCPServer(logger=log)
    server.start()