import socket
import threading
import datetime
import os
import csv
import subprocess
import requests
import time
import json
from collections import defaultdict, deque

class HoneyTrapServer:
    """
    An advanced, object-oriented socket deception framework engineered 
    for intrusion detection, connection logging, and active threat mitigation.
    """
    def __init__(self, config_path="honeytrap_config.json"):
        self.log_directory = "logs"
        self.ban_record = os.path.join(self.log_directory, "banlist.txt")
        self.config_filepath = config_path
        
        # Default runtime parameters
        self.target_ports = [22, 2222, 22222]
        self.discord_endpoint = "YOUR_DISCORD_WEBHOOK_HERE"
        self.abuse_api_token = "YOUR_ABUSEIPDB_KEY_HERE"
        self.vt_api_token = "YOUR_VIRUSTOTAL_KEY_HERE"
        
        self.stealth_active = False
        self.firewall_enforcement = True
        self.max_conn_threshold = 5
        self.session_timeout = 30
        
        # Thread-safe tracking structures
        self.connection_tracker = defaultdict(int)
        self.temporal_deque = defaultdict(deque)
        self.blacklisted_ips = set()
        
        os.makedirs(self.log_directory, exist_ok=True)
        self._load_environment_config()
        self._hydrate_ban_list()

    def _load_environment_config(self):
        """Loads configuration from disk if available, updating runtime state."""
        if os.path.exists(self.config_filepath):
            try:
                with open(self.config_filepath, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    self.target_ports = cfg.get('ports', self.target_ports)
                    self.stealth_active = cfg.get('silent_mode', self.stealth_active)
                    self.firewall_enforcement = cfg.get('firewall_block', self.firewall_enforcement)
                    self.max_conn_threshold = cfg.get('max_connections', self.max_conn_threshold)
                    self.session_timeout = cfg.get('timeout', self.session_timeout)
                    self.discord_endpoint = cfg.get('discord_webhook', self.discord_endpoint)
                    self.abuse_api_token = cfg.get('abuseipdb_key', self.abuse_api_token)
                    self.vt_api_token = cfg.get('virustotal_key', self.vt_api_token)
            except Exception as err:
                print(f"[Configuration Error] Failed to parse configuration file: {err}")

    def persist_configuration(self):
        """Saves current runtime settings back to the configuration file."""
        cfg = {
            'ports': self.target_ports,
            'silent_mode': self.stealth_active,
            'firewall_block': self.firewall_enforcement,
            'max_connections': self.max_conn_threshold,
            'timeout': self.session_timeout,
            'discord_webhook': self.discord_endpoint,
            'abuseipdb_key': self.abuse_api_token,
            'virustotal_key': self.vt_api_token
        }
        try:
            with open(self.config_filepath, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=4)
        except Exception as err:
            print(f"[Configuration Error] Failed to write configuration: {err}")

    def _hydrate_ban_list(self):
        """Loads previously restricted IP addresses into memory."""
        if os.path.exists(self.ban_record):
            with open(self.ban_record, 'r', encoding='utf-8') as f:
                for entry in f:
                    clean_ip = entry.strip()
                    if clean_ip:
                        self.blacklisted_ips.add(clean_ip)

    def _resolve_target_csv(self):
        """Generates a daily rotating CSV log filepath."""
        date_stamp = datetime.datetime.now().strftime('%Y-%m-%d')
        return os.path.join(self.log_directory, f"honeypot_audit_{date_stamp}.csv")

    def _initialize_ledger(self):
        """Ensures the daily CSV audit ledger has proper headers."""
        ledger_path = self._resolve_target_csv()
        if not os.path.exists(ledger_path):
            with open(ledger_path, mode="w", newline="", encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "Source_IP", "Geolocation", "Organization", 
                    "Target_Port", "Provided_User", "Provided_Pass", 
                    "Flagged_Status", "Payload_URL", "Threat_Index"
                ])
        return ledger_path

    @staticmethod
    def query_ip_metadata(target_ip):
        """Fetches geographic and network owner information for a given IP."""
        try:
            resp = requests.get(f"http://ip-api.com/json/{target_ip}", timeout=5)
            if resp.status_code == 200:
                payload = resp.json()
                return payload.get("country", "Unknown"), payload.get("org", "Unknown"), payload.get("as", "Unknown")
        except Exception:
            pass
        return "Unknown", "Unknown", "Unknown"

    def evaluate_virustotal_threat(self, target_ip):
        """Queries VirusTotal telemetry for historical indicator analysis."""
        if not self.vt_api_token:
            return 0
        try:
            endpoint = f"https://www.virustotal.com/api/v3/ip_addresses/{target_ip}"
            headers = {"x-apikey": self.vt_api_token}
            response = requests.get(endpoint, headers=headers, timeout=10)
            if response.status_code == 200:
                attributes = response.json().get('data', {}).get('attributes', {})
                stats = attributes.get('last_analysis_stats', {})
                return stats.get('malicious', 0)
        except Exception:
            pass
        return 0

    def broadcast_abuseipdb_signal(self, target_ip):
        """Reports malicious client IPs to the AbuseIPDB intelligence registry."""
        if not self.abuse_api_token:
            return
        try:
            requests.post(
                "https://api.abuseipdb.com/api/v2/report",
                headers={"Key": self.abuse_api_token, "Accept": "application/json"},
                data={"ip": target_ip, "categories": 18, "comment": "Automated Honeypot Intrusion Detection."},
                timeout=10
            )
            print(f"[Threat Intelligence] Successfully reported IP {target_ip} to AbuseIPDB.")
        except Exception as err:
            print(f"[Threat Intelligence] Reporting failed: {err}")

    def dispatch_discord_notification(self, ip, country, org, port, user, password, flagged, score, payload_url):
        """Dispatches an interactive webhook notification to configured Discord channels."""
        if not self.discord_endpoint:
            return
        try:
            color_code = 0xff0000 if flagged else 0xffff00
            embed_obj = {
                "title": "🛡️ HoneyTrap Security Event Log",
                "color": color_code,
                "fields": [
                    {"name": "Client IP", "value": ip, "inline": True},
                    {"name": "Country", "value": country, "inline": True},
                    {"name": "Organization", "value": org[:90] if len(org) > 90 else org, "inline": True},
                    {"name": "Port", "value": str(port), "inline": True},
                    {"name": "Username", "value": f"`{user}`", "inline": True},
                    {"name": "Password", "value": f"`{password}`", "inline": True},
                    {"name": "Threat Score", "value": str(score), "inline": True}
                ],
                "timestamp": datetime.datetime.now().isoformat()
            }
            if payload_url:
                embed_obj["fields"].append({"name": "Captured URL", "value": f"`{payload_url}`", "inline": False})
            if flagged:
                embed_obj["fields"].append({"name": "Action Taken", "value": "🚨 HOST BLACKLISTED & FIREWALL ENFORCED", "inline": False})
            
            requests.post(self.discord_endpoint, json={"embeds": [embed_obj]}, timeout=5)
        except Exception:
            pass

    def commit_audit_log(self, ip, port, user, password, flagged=False, payload_url="", score=0):
        """Records telemetry data to CSV and triggers external alert hooks."""
        ledger = self._initialize_ledger()
        timestamp_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        country, org, _ = self.query_ip_metadata(ip)
        
        with open(ledger, mode="a", newline="", encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                timestamp_str, ip, country, org, port, user, password, 
                "Yes" if flagged else "No", payload_url, score
            ])
        
        badge = "⚠️" if flagged else "🔍"
        print(f"[{timestamp_str}] {badge} Source: {ip} | Geo: {country} [{org}] | Creds: {user}:{password} | Score: {score}" +
              (f" | Payload: {payload_url}" if payload_url else ""))
        
        self.dispatch_discord_notification(ip, country, org, port, user, password, flagged, score, payload_url)
        if flagged:
            self.broadcast_abuseipdb_signal(ip)

    def enforce_network_ban(self, target_ip):
        """Adds an offending IP to local storage blocks and applies system firewall rules."""
        if target_ip in self.blacklisted_ips:
            return
        
        self.blacklisted_ips.add(target_ip)
        with open(self.ban_record, "a", encoding='utf-8') as banfile:
            banfile.write(target_ip + "\n")
        
        print(f"[Security Enforcer] IP Added to Blacklist Database: {target_ip}")
        
        if self.firewall_enforcement:
            try:
                subprocess.run(["iptables", "-A", "INPUT", "-s", target_ip, "-j", "DROP"], check=True, timeout=10)
                print(f"[Firewall Engine] Successfully applied iptables DROP rule for {target_ip}")
            except Exception as err:
                print(f"[Firewall Engine] Rule application skipped or failed: {err}")

    def analyze_connection_frequency(self, ip_address):
        """Evaluates connection frequency to identify brute-force or scanning spikes."""
        now = time.time()
        self.temporal_deque[ip_address].append(now)
        
        while self.temporal_deque[ip_address] and now - self.temporal_deque[ip_address][0] > 3600:
            self.temporal_deque[ip_address].popleft()
            
        return len(self.temporal_deque[ip_address]) > self.max_conn_threshold

    def simulate_interaction_shell(self, socket_conn, ip, port, user, password, is_flagged):
        """Emulates a live, interactive Linux shell environment for captured sessions."""
        if self.stealth_active:
            socket_conn.close()
            return

        emulated_responses = {
            "ls": "bin  boot  dev  etc  home  lib  media  mnt  opt  proc  root  run  sbin  srv  sys  tmp  usr  var",
            "ls -la": "total 96\ndrwxr-xr-x  23 root root  4096 Oct 26 10:00 .\ndrwxr-xr-x  23 root root  4096 Oct 26 10:00 ..\n-rw-------   1 root root  1024 Oct 26 09:58 .bash_history",
            "whoami": "root",
            "id": "uid=0(root) gid=0(root) groups=0(root)",
            "pwd": "/root",
            "uname -a": "Linux production-core-01 5.4.0-91-generic #102-Ubuntu SMP x86_64 GNU/Linux",
            "cat /etc/passwd": "root:x:0:0:root:/root:/bin/bash\ndaemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin",
            "ps aux": "USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\nroot         1  0.0  0.1 169484 11240 ?        Ss   Oct26   0:02 /sbin/init",
        }

        try:
            socket_conn.settimeout(self.session_timeout)
            socket_conn.sendall(b"Ubuntu 20.04.6 LTS (GNU/Linux 5.4.0-91-generic x86_64)\n\n")
            socket_conn.sendall(b"Last login: Mon Oct 26 10:00:00 2026 from 10.0.0.14\n")
            socket_conn.sendall(b"root@production-core-01:~# ")

            while True:
                incoming_data = socket_conn.recv(1024)
                if not incoming_data:
                    break
                
                cmd_string = incoming_data.decode('utf-8', errors='ignore').strip()
                
                if cmd_string.lower() in ['exit', 'logout', 'quit']:
                    socket_conn.sendall(b"logout\n")
                    break
                elif cmd_string.lower().startswith(("wget ", "curl ")):
                    extracted_url = cmd_string.split(" ", 1)[1] if " " in cmd_string else "UNKNOWN_URL"
                    self.commit_audit_log(ip, port, user, password, is_flagged, extracted_url)
                    socket_conn.sendall(b"bash: " + cmd_string.split()[0].encode() + b": command not found\n")
                elif cmd_string.lower() in emulated_responses:
                    output_text = emulated_responses[cmd_string.lower()] + "\n"
                    socket_conn.sendall(output_text.encode())
                elif cmd_string == "":
                    pass
                else:
                    socket_conn.sendall(b"bash: " + cmd_string.encode() + b": command not found\n")
                
                socket_conn.sendall(b"root@production-core-01:~# ")
                
        except Exception:
            pass
        finally:
            socket_conn.close()

    def process_incoming_client(self, client_socket, remote_address, active_port):
        """Manages incoming connections, handshake telemetry, and credential collection."""
        client_ip = remote_address[0]
        
        if client_ip in self.blacklisted_ips:
            client_socket.close()
            return

        username, password = "silent_mode_user", "silent_mode_pass"
        try:
            client_socket.settimeout(10)
            if not self.stealth_active:
                client_socket.sendall(b"Ubuntu 20.04.6 LTS\nserver login: ")
                username = client_socket.recv(1024).decode('utf-8', errors='ignore').strip()
                
                client_socket.sendall(b"password: ")
                password = client_socket.recv(1024).decode('utf-8', errors='ignore').strip()
        except Exception:
            client_socket.close()
            return

        threat_index = self.evaluate_virustotal_threat(client_ip)
        flagged_state = self.analyze_connection_frequency(client_ip) or (threat_index > 2)
        
        self.commit_audit_log(client_ip, active_port, username, password, flagged_state, "", threat_index)

        if flagged_state:
            self.enforce_network_ban(client_ip)
            try:
                client_socket.sendall(b"Permission denied, please try again.\n")
            except Exception:
                pass
            client_socket.close()
            return

        if not self.stealth_active:
            try:
                client_socket.sendall(b"Access granted. Initializing secure shell environment...\n")
            except Exception:
                pass
        
        self.simulate_interaction_shell(client_socket, client_ip, active_port, username, password, flagged_state)

    def bind_and_listen(self, port_num):
        """Binds a socket listener to the specified port and spawns thread handlers."""
        listener_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            listener_sock.bind(("0.0.0.0", port_num))
            listener_sock.listen(15)
            print(f"[Listener Active] Port {port_num} listening [Stealth: {self.stealth_active}, Firewall: {self.firewall_enforcement}]")
            
            while True:
                sock_conn, client_addr = listener_sock.accept()
                worker_thread = threading.Thread(
                    target=self.process_incoming_client, 
                    args=(sock_conn, client_addr, port_num), 
                    daemon=True
                )
                worker_thread.start()
        except Exception as err:
            print(f"[Listener Error] Port {port_num} binding failed: {err}")
        finally:
            listener_sock.close()

    def launch(self):
        """Initializes the multi-port server threads and begins execution."""
        print(f"""
        🕷️ HoneyTrapTR Framework - Customized Secure Edition
        📍 Active Ports: {self.target_ports}
        🔒 Firewall Shield: {self.firewall_enforcement}
        👻 Stealth Mode: {self.stealth_active}
        """)
        
        for p in self.target_ports:
            t = threading.Thread(target=self.bind_and_listen, args=(p,), daemon=True)
            t.start()
            
        print("[*] HoneyTrapTR operational. Press Ctrl+C to safely terminate.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[*] Shutting down honeypot services and saving configurations...")
            self.persist_configuration()

if __name__ == "__main__":
    trap_server = HoneyTrapServer()
    trap_server.launch()