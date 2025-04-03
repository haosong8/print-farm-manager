# Filament Length Calculator
import math
spool_id = 30
spool_current = 130
filament_diameter = 1.75
filament_density = 1.07
spool_width = 137
asa_ratio = 1000/388.75

num_of_donut = math.floor(((spool_current - spool_id) / filament_diameter) / 2)
print(num_of_donut)

total_length = 0

for i in range(num_of_donut):
    # circumference * width gives number of revolutions at each spool
    donut_length = spool_id + i*2 * math.pi * (spool_width / filament_diameter)
    total_length += donut_length

print(total_length * 0.001)
total_weight = (total_length * 0.001) * asa_ratio
print(total_weight)

# kg to filament length conversion
filament_radius = filament_diameter / 2
kg = 5
# calculate volume
filament_length = kg * 1000 / (math.pi * filament_radius**2 * filament_density)
print(filament_length)