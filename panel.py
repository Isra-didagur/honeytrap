from flask import Flask, render_template_string
import os
import glob
import csv

app = Flask(__name__)

def fetch_latest_logs():
    """Reads all rows from the most recent honeypot CSV log file."""
    log_files = glob.glob("logs/honeypot_audit_*.csv")
    if not log_files:
        return []
    
    # Get the latest log file by modification time
    latest_file = max(log_files, key=os.path.getmtime)
    
    entries = []
    try:
        with open(latest_file, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                entries.append(row)
    except Exception as e:
        print(f"Error reading logs: {e}")
        
    # Return entries in reverse chronological order (newest first)
    return list(reversed(entries))

@app.route('/')
def dashboard():
    logs = fetch_latest_logs()
    total_attacks = len(logs)
    flagged_attacks = sum(1 for log in logs if log.get("Flagged_Status") == "Yes")
    
    # HTML template with modern styling
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>HoneyTrapTR - Security Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <meta http-equiv="refresh" content="5"> <!-- Auto refresh every 5 seconds -->
    </head>
    <body class="bg-dark text-light">
        <div class="container my-5">
            <h1 class="mb-4">🕷️ HoneyTrapTR - Intrusion Dashboard</h1>
            
            <div class="row mb-4">
                <div class="col-md-6">
                    <div class="card bg-secondary text-white p-3">
                        <h3>Total Attempts</h3>
                        <p class="fs-2 fw-bold">{{ total }}</p>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card bg-danger text-white p-3">
                        <h3>Blocked / Flagged Threats</h3>
                        <p class="fs-2 fw-bold">{{ flagged }}</p>
                    </div>
                </div>
            </div>

            <div class="card bg-secondary text-white p-4">
                <h3>Live Attack Telemetry</h3>
                <div class="table-responsive mt-3">
                    <table class="table table-dark table-striped table-hover">
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Source IP</th>
                                <th>Country</th>
                                <th>Port</th>
                                <th>Username</th>
                                <th>Password</th>
                                <th>Flagged</th>
                                <th>Threat Score</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for log in logs %}
                            <tr>
                                <td>{{ log.Timestamp }}</td>
                                <td><code>{{ log.Source_IP }}</code></td>
                                <td>{{ log.Geolocation }}</td>
                                <td>{{ log.Target_Port }}</td>
                                <td><code>{{ log.Provided_User }}</code></td>
                                <td><code>{{ log.Provided_Pass }}</code></td>
                                <td>
                                    {% if log.Flagged_Status == 'Yes' %}
                                        <span class="badge bg-danger">Yes</span>
                                    {% else %}
                                        <span class="badge bg-success">No</span>
                                    {% endif %}
                                </td>
                                <td>{{ log.Threat_Index }}</td>
                            </tr>
                            {% else %}
                            <tr>
                                <td colspan="8" class="text-center">No intrusion data recorded yet. Try testing a connection!</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html_template, logs=logs, total=total_attacks, flagged=flagged_attacks)

if __name__ == '__main__':
    print("[+] Launching Web Dashboard Panel on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
    