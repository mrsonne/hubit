# Calculate heat transfer number and the energy class

energy_classes = {'A': (0, 0.5),
                  'B': (0.5, 0.75),
                  'C': (0.75, 1.),
                  'D': (1., 100000.),
                 }

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
    results_provided['energy_class'] = [ecls 
                                        for ecls, limits 
                                        in energy_classes.items() 
                                        if htn >= limits[0] and htn < limits[1]][0]
    return results_provided