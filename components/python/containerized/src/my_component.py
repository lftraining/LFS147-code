#import KFP DSL and our utility function 
from kfp import dsl
from math_utils import calculate_area

# Declare our base_image that our code will be packaged on top of and our target_image, which will be what we name our new container image when pushed to our registry
 
@dsl.component(target_image='chasechristensen/material_cost_component:v1')
#Declare our calculate_material_costs function 
def calculate_material_cost(radius: float, cost_per_square_unit: float) -> float:
    """Calculates the cost of materials needed to cover a circle's area."""
    area = calculate_area(radius)
    total_cost = area * cost_per_square_unit
    print(f"The total cost to cover the area of a circle with radius {radius} is: ${total_cost:.2f}")
    return total_cost
