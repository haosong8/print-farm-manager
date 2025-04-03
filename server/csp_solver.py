#!/usr/bin/env python3
from datetime import datetime, timedelta
from constraint import Problem

# --- Mock Data Setup ---

# Define two printers (using datetime for available windows).
# Note: supported_materials are given as a comma-separated string.
printers = {
    "printer1": {
        "available_start": datetime(2025, 5, 12, 10, 0),
        "available_end": datetime(2025, 5, 12, 22, 0),
        "supported_materials": "PLA,ABS"  # printer1 supports PLA and ABS
    },
    "printer2": {
        "available_start": datetime(2025, 5, 12, 10, 0),
        "available_end": datetime(2025, 5, 12, 22, 0),
        "supported_materials": "PLA,PETG"  # printer2 supports PLA and PETG
    }
}

# Define gcodes.
# Each gcode is associated with a printer, has an estimated_print_time (as timedelta),
# and a material.
gcodes = {
    "gcode1": {  # on printer1, for PLA parts
        "printer_id": "printer1",
        "estimated_print_time": timedelta(minutes=60),
        "material": "PLA"
    },
    "gcode2": {  # on printer1, for ABS parts
        "printer_id": "printer1",
        "estimated_print_time": timedelta(minutes=45),
        "material": "ABS"
    },
    "gcode3": {  # on printer2, for PLA parts
        "printer_id": "printer2",
        "estimated_print_time": timedelta(minutes=75),
        "material": "PLA"
    },
    "gcode4": {  # on printer2, for PETG parts
        "printer_id": "printer2",
        "estimated_print_time": timedelta(minutes=90),
        "material": "PETG"
    }
}

# Define a single product with a due_date.
product = {
    "product_id": 1,
    "product_name": "Widget",
    "due_date": datetime(2025, 5, 12, 20, 0)  # Product must be completed by 8:00 pm
}

# Define product components (parts to be printed).
# Each component requires a specific material.
product_components = {
    "comp1": {  # requires PLA
        "required_material": "PLA"
    },
    "comp2": {  # requires PETG
        "required_material": "PETG"
    },
    "comp3": {  # requires ABS
        "required_material": "ABS"
    }
}

# Define time resolution for scheduling (5-minute increments)
TIME_STEP = timedelta(minutes=5)

# --- Build Candidate Domains for Each Product Component ---
# For each component, first compute the candidate list of (printer, gcode) pairs
# that are able to print the required material.
# Then, for each candidate, generate all possible start times (in increments)
# that allow the job (using the candidate’s gcode estimated print time) to finish
# before both the printer's available_end and the product’s due_date.
domains = {}

for comp_id, comp in product_components.items():
    req_material = comp["required_material"]
    candidate_assignments = []
    # First, get candidate (printer, gcode) pairs.
    for pid, p in printers.items():
        supported = [m.strip() for m in p["supported_materials"].split(",")]
        if req_material not in supported:
            continue
        for gid, g in gcodes.items():
            if g["printer_id"] != pid:
                continue
            if g["material"] != req_material:
                continue
            candidate_assignments.append((pid, gid))
    
    # For each candidate, generate feasible start times.
    options = []
    for (pid, gid) in candidate_assignments:
        p = printers[pid]
        g = gcodes[gid]
        est_time = g["estimated_print_time"]
        # Latest start is the minimum of (printer.available_end - est_time) and (product.due_date - est_time)
        latest_start = min(p["available_end"], product["due_date"]) - est_time
        current_start = p["available_start"]
        while current_start <= latest_start:
            options.append((pid, gid, current_start))
            current_start += TIME_STEP
    domains[comp_id] = options
    if not options:
        print(f"No feasible assignments for component {comp_id} (requires {req_material}).")

# --- Set Up the Constraint Problem ---
problem = Problem()

# Each product component is a variable; its domain is the list of (printer, gcode, start_time) tuples.
for comp_id, domain in domains.items():
    problem.addVariable(comp_id, domain)

# --- Add Constraints ---

# 1. Each component's printing must finish before the product's due_date.
def finish_before_due(assignment, product_due):
    # assignment is (printer_id, gcode_id, start_time)
    _, gid, start_time = assignment
    finish_time = start_time + gcodes[gid]["estimated_print_time"]
    return finish_time <= product_due

for comp_id in product_components.keys():
    problem.addConstraint(lambda a, due=product["due_date"]: finish_before_due(a, due), [comp_id])

# 2. No overlapping prints on the same printer.
def non_overlap(a1, a2):
    pid1, gid1, start1 = a1
    pid2, gid2, start2 = a2
    # If different printers, no conflict.
    if pid1 != pid2:
        return True
    finish1 = start1 + gcodes[gid1]["estimated_print_time"]
    finish2 = start2 + gcodes[gid2]["estimated_print_time"]
    return finish1 <= start2 or finish2 <= start1

comp_ids = list(product_components.keys())
for i in range(len(comp_ids)):
    for j in range(i+1, len(comp_ids)):
        problem.addConstraint(non_overlap, (comp_ids[i], comp_ids[j]))

# --- Solve the CSP ---
solutions = problem.getSolutions()

if solutions:
    solution = solutions[0]
    print("A feasible product schedule:")
    for comp_id in sorted(solution):
        printer_id, gcode_id, start_time = solution[comp_id]
        est_time = gcodes[gcode_id]["estimated_print_time"]
        finish_time = start_time + est_time
        print(f"{comp_id}: Assigned Printer = {printer_id}, Gcode = {gcode_id}, "
              f"Start = {start_time.strftime('%Y-%m-%d %H:%M')}, "
              f"Finish = {finish_time.strftime('%Y-%m-%d %H:%M')}")
else:
    print("No feasible product schedule found.")
