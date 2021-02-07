# Calculate heat flow from width, height and heat flux

def heat_transfer_number(_input_consumed, _results_consumed, results_provided):
    areas = [width*height 
             for width, height in 
             zip(_input_consumed['widths'], _input_consumed['heights'])]
    total_area = sum(areas)
    
    # Mean heat transfer number
    htn = sum([htn*area/total_area 
               for htn, area in 
               zip(_results_consumed["heat_transfer_numbers"], areas)])
    results_provided['heat_transfer_number'] = htn  
    return results_provided