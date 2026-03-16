import time
import unittest
from unittest.mock import MagicMock, patch

from server import BasicDHCPServer, Lease


class TestBasicDHCPServer(unittest.TestCase):
    def setUp(self) -> None:
        self.server = BasicDHCPServer(
            server_ip="192.168.1.1",
            subnet_mask="255.255.255.0",
            router="192.168.1.1",
            dns="8.8.8.8",
            lease_time=3600,
            ip_base="192.168.1.",
            pool_start=100,
            pool_end=102,
            flask_host="127.0.0.1",
            flask_port=5001,
        )
        self.client = self.server.app.test_client()

    # -----------------------------
    # Helper tests
    # -----------------------------
    def test_ip_to_bytes_and_back(self) -> None:
        ip = "192.168.1.123"
        packed = self.server.ip_to_bytes(ip)
        unpacked = self.server.bytes_to_ip(packed)

        self.assertEqual(unpacked, ip)

    def test_mac_to_str(self) -> None:
        mac = b"\x08\x00\x27\xaa\xbb\xcc"
        result = self.server.mac_to_str(mac)

        self.assertEqual(result, "08:00:27:aa:bb:cc")

    def test_parse_dhcp_options(self) -> None:
        # option 53 -> DHCP message type discover (1)
        # option 50 -> requested IP 192.168.1.101
        options = bytes([
            53, 1, 1,
            50, 4, 192, 168, 1, 101,
            255
        ])

        parsed = self.server.parse_dhcp_options(options)

        self.assertIn(53, parsed)
        self.assertIn(50, parsed)
        self.assertEqual(parsed[53], b"\x01")
        self.assertEqual(self.server.bytes_to_ip(parsed[50]), "192.168.1.101")

# -----------------------------
    # Lease / pool tests
    # -----------------------------
    def test_get_free_ip_returns_first_available(self) -> None:
        ip = self.server.get_free_ip()
        self.assertEqual(ip, "192.168.1.100")

    def test_get_free_ip_skips_used_ips(self) -> None:
        self.server.leases["aa:bb:cc:dd:ee:01"] = Lease(
            ip="192.168.1.100",
            expires=time.time() + 3600,
        )
        self.server.offered["aa:bb:cc:dd:ee:02"] = "192.168.1.101"

        ip = self.server.get_free_ip()
        self.assertEqual(ip, "192.168.1.102")

    def test_get_free_ip_returns_none_when_pool_exhausted(self) -> None:
        self.server.leases["aa:bb:cc:dd:ee:01"] = Lease(
            ip="192.168.1.100",
            expires=time.time() + 3600,
        )
        self.server.leases["aa:bb:cc:dd:ee:02"] = Lease(
            ip="192.168.1.101",
            expires=time.time() + 3600,
        )
        self.server.offered["aa:bb:cc:dd:ee:03"] = "192.168.1.102"

        ip = self.server.get_free_ip()
        self.assertIsNone(ip)

    def test_build_dhcp_packet_returns_bytes(self) -> None:
        packet = self.server.build_dhcp_packet(
            xid=b"\x39\x03\xf3\x26",
            yiaddr="192.168.1.100",
            chaddr=b"\x08\x00\x27\xaa\xbb\xcc",
            msg_type=2,
        )

        self.assertIsInstance(packet, bytes)
        self.assertGreater(len(packet), 240)

    # -----------------------------
    # Flask route tests
    # -----------------------------
    def test_index_route(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"message": "Basic DHCP server + Flask API is running"}
        )
        self.mock_logger.info.assert_any_call("GET / called")

    def test_get_config_route(self) -> None:
        response = self.client.get("/config")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertEqual(data["server_ip"], "192.168.1.1")
        self.assertEqual(data["subnet_mask"], "255.255.255.0")
        self.assertEqual(data["router"], "192.168.1.1")
        self.assertEqual(data["dns"], "8.8.8.8")
        self.assertEqual(data["lease_time"], 3600)
        self.assertEqual(data["pool"], ["192.168.1.100", "192.168.1.102"])

        self.mock_logger.info.assert_any_call("GET /config called")

    def test_get_leases_route(self) -> None:
        self.server.leases["08:00:27:aa:bb:cc"] = Lease(
            ip="192.168.1.100",
            expires=9999999999.0,
        )

        response = self.client.get("/leases")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertIn("08:00:27:aa:bb:cc", data)
        self.assertEqual(data["08:00:27:aa:bb:cc"]["ip"], "192.168.1.100")

        self.mock_logger.info.assert_any_call("GET /leases called")

    def test_delete_existing_lease_route(self) -> None:
        self.server.leases["08:00:27:aa:bb:cc"] = Lease(
            ip="192.168.1.100",
            expires=9999999999.0,
        )

        response = self.client.delete("/leases/08:00:27:aa:bb:cc")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertEqual(data["status"], "deleted")
        self.assertEqual(data["lease"]["ip"], "192.168.1.100")
        self.assertNotIn("08:00:27:aa:bb:cc", self.server.leases)

        self.mock_logger.warning.assert_any_call(
            "DELETE /leases/08:00:27:aa:bb:cc called"
        )
        self.mock_logger.info.assert_any_call(
            "Lease deleted for MAC 08:00:27:aa:bb:cc, IP 192.168.1.100"
        )

    def test_delete_missing_lease_route(self) -> None:
        response = self.client.delete("/leases/08:00:27:ff:ee:dd")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {"error": "not found"})

        self.mock_logger.warning.assert_any_call(
            "DELETE /leases/08:00:27:ff:ee:dd called"
        )
        self.mock_logger.warning.assert_any_call(
            "Lease delete requested but not found for MAC 08:00:27:ff:ee:dd"
        )

    # -----------------------------
    # Logging-focused tests
    # -----------------------------
    def test_logger_called_on_init(self) -> None:
        mock_logger = MagicMock()

        BasicDHCPServer(
            logger=mock_logger,
            flask_host="127.0.0.1",
            flask_port=5002,
        )

        mock_logger.info.assert_any_call("BasicDHCPServer initialized.")

    def test_cleanup_expired_leases_logs_warning(self) -> None:
        expired_mac = "08:00:27:aa:bb:cc"
        self.server.leases[expired_mac] = Lease(
            ip="192.168.1.100",
            expires=time.time() - 10,
        )

        original_sleep = time.sleep

        def stop_after_first_loop(_: float) -> None:
            raise KeyboardInterrupt()

        try:
            time.sleep = stop_after_first_loop
            with self.assertRaises(KeyboardInterrupt):
                self.server.cleanup_expired_leases()
        finally:
            time.sleep = original_sleep

        self.assertNotIn(expired_mac, self.server.leases)
        self.mock_logger.warning.assert_any_call(
            "Expired lease removed: MAC=08:00:27:aa:bb:cc, IP=192.168.1.100"
        )


if __name__ == "__main__":
    unittest.main()