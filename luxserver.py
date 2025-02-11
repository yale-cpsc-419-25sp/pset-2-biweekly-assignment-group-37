#!/usr/bin/env python3
import socket
import sys
import json
import sqlite3
import argparse

DATABASE = "lux.sqlite"

def connect_database():
    """Returns a connection to the SQLite database."""
    try:
        return sqlite3.connect(DATABASE)
    except sqlite3.Error as e:
        sys.stderr.write(f"Database error: {e}\n")
        sys.exit(1)


def build_timespan_str(bdate, edate):
    """
    Builds a timespan string (e.g., "-0580 – -0550" or "1976–") from the agent’s dates.
    """
    def y(s):
        return s[:4] if s and len(s) >= 4 else None
    by = y(bdate)
    ey = y(edate)
    if by:
        if by[0] == "0":
            by_val = "-" + by
        else:
            by_val = by
    else:
        by_val = ""
    if ey:
        if ey[0] == "0":
            ey_val = "-" + ey
        else:
            ey_val = ey
    else:
        ey_val = ""
    if by_val and ey_val:
        return f"{by_val} – {ey_val}"
    if by_val and not ey_val:
        return f"{by_val}–"
    return ey_val



def fetch_nationalities(cursor, agt_id):
    """
    Retrieves a sorted list (case-insensitive) of nationality descriptors for the given agent.
    Queries the agents_nationalities table joined with nationalities.
    """
    q = """
        SELECT nationalities.descriptor
        FROM agents_nationalities
        JOIN nationalities ON nationalities.id = agents_nationalities.nat_id
        WHERE agents_nationalities.agt_id = ?
    """
    cursor.execute(q, (agt_id,))
    rows = cursor.fetchall()
    descs = [r[0] for r in rows if r[0]]
    return sorted(descs, key=str.lower)


def get_producers(cursor, obj_id):
    """
    Retrieves producers for the given object.
    Returns a list of tuples: (Part, Name, Nationalities, Timespan).
    Sorted in ascending order by agent name, then part, and then by the nationality string.
    """
    query = """
        SELECT agents.name, productions.part, agents.begin_date, agents.end_date, agents.id
        FROM productions
        JOIN agents ON productions.agt_id = agents.id
        WHERE productions.obj_id = ?
        ORDER BY agents.name ASC, productions.part ASC
    """
    cursor.execute(query, (obj_id,))
    rows = cursor.fetchall()
    data = []
    for name, part, bdate, edate, agt_id in rows:
        timespan = build_timespan_str(bdate, edate)
        # Join nationalities with newline characters
        nat_list = fetch_nationalities(cursor, agt_id)
        nat_str = "\n".join(nat_list)
        data.append((part or "", name, nat_str, timespan))
    # Sort again to ensure correct order
    data.sort(key=lambda x: (x[1].lower(), x[0].lower(), x[2].lower()))
    return data


def get_classifications(cursor, obj_id):
    """
    Retrieves a sorted (alphabetically, case-insensitive) list of classifier names for the object.
    Returns a newline-separated string where each classifier appears on its own line.
    """
    query = """
        SELECT classifiers.name
        FROM objects_classifiers
        JOIN classifiers ON objects_classifiers.cls_id = classifiers.id
        WHERE objects_classifiers.obj_id = ?
    """
    cursor.execute(query, (obj_id,))
    rows = cursor.fetchall()
    classifiers = [r[0] for r in rows if r[0]]
    classifiers_sorted = sorted(classifiers, key=lambda s: s.lower())
    return "\n".join(classifiers_sorted)


def fetch_filtered_objects(filters):
    """
    Performs a filtered query on the objects table.
    """
    conn = connect_database()
    cursor = conn.cursor()
    query = """
        SELECT objects.id, objects.label, objects.date
        FROM objects
        WHERE 1=1
    """
    params = []
    if filters.get("date"):
        query += " AND objects.date LIKE ?"
        params.append(f"%{filters['date']}%")
    if filters.get("agent"):
        query += """
            AND objects.id IN (
                SELECT obj_id FROM productions
                JOIN agents ON productions.agt_id = agents.id
                WHERE agents.name LIKE ?
            )
        """
        params.append(f"%{filters['agent']}%")
    if filters.get("classifier"):
        query += """
            AND objects.id IN (
                SELECT obj_id FROM objects_classifiers
                JOIN classifiers ON objects_classifiers.cls_id = classifiers.id
                WHERE classifiers.name LIKE ?
            )
        """
        params.append(f"%{filters['classifier']}%")
    if filters.get("label"):
        query += " AND objects.label LIKE ?"
        params.append(f"%{filters['label']}%")
    query += " ORDER BY objects.label ASC, objects.date ASC LIMIT 1000"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    results = []
    for obj_id, label, date in rows:
        produced_by = get_producers(cursor, obj_id)
        classified_as = get_classifications(cursor, obj_id)
        results.append({
            "id": obj_id,
            "label": label,
            "date": date,
            "produced_by": produced_by,
            "classified_as": classified_as
        })
    conn.close()
    return results

def handle_client(conn):
    """
    Handles a single client connection.
    Reads the complete request, performs the query, sends back a JSON response.
    """
    data = b""
    while True:
        chunk = conn.recv(4096)
        if not chunk:
            break
        data += chunk
    try:
        request = json.loads(data.decode("utf-8"))
    except Exception as e:
        response = {"error": f"Invalid JSON: {e}"}
        conn.sendall(json.dumps(response).encode("utf-8"))
        return
    results = fetch_filtered_objects(request)
    response = {"results": results}
    conn.sendall(json.dumps(response).encode("utf-8"))

def main():
    parser = argparse.ArgumentParser(
        description="Server for the YUAG application.",
        allow_abbrev=False
    )
    parser.add_argument("port", type=int, help="the port at which the server should listen")
    args = parser.parse_args()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("", args.port))
    except Exception as e:
        sys.stderr.write(f"Error binding to port {args.port}: {e}\n")
        sys.exit(1)
    sock.listen(5)
    print(f"Server listening on port {args.port}...")
    while True:
        try:
            conn, addr = sock.accept()
            with conn:
                handle_client(conn)
        except KeyboardInterrupt:
            print("Server shutting down...")
            break
        except Exception as e:
            sys.stderr.write(f"Error handling request: {e}\n")
    sock.close()

if __name__ == "__main__":
    main()
