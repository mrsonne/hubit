# Paths are relative to the root directory where the tests are executed from
# This model collects wall data in a list on the end node
model = """
    -   
        # move a number
        func_name: move_number
        path: ./components/comp0.py 
        provides: 
            - name: number
              path: first_coor[IDX1].second_coor[IDX2].value 
        consumes:
            input: 
                - name: number
                  path: list[IDX1].some_attr.inner_list[IDX2].xval

    -
        func_name: multiply_by_2
        # Path relative to base_path
        path: ./components/comp1.py 
        provides: 
            - name: comp1_results
              path: list[IDX1].some_attr.two_x_numbers
        consumes:
            input: 
                - name: numbers_consumed_by_comp1
                  path: list[IDX1].some_attr.numbers
    -
        func_name: multiply_by_factors
        path: ./components/comp2.py
        provides:
            - name: temperatures
              path: list[IDX1].some_attr.two_x_numbers_x_factor
        consumes:
            input: 
                - name: factors
                  path: list[IDX1].some_attr.factors
            results: 
                - name: numbers_provided_by_comp1
                  path: list[IDX1].some_attr.two_x_numbers
    -
        func_name: slicing
        path: ./components/comp3.py # consumes factors for all list items and stores them in nested list
        provides:
            - name: mylist
              path: factors
        consumes:
            input: 
                - name: factors
                  path: list[:@IDX1].some_attr.factors
    -
        func_name: fun4
        path: ./components/comp4.py
        provides:
            - name: yvals
              path: list[IDX1].some_attr.inner_list[:@IDX2].yval
        consumes:
            input:
                - name: fact
                  path: list[IDX1].some_attr.x_to_y_fact
                - name: xvals
                  path: list[IDX1].some_attr.inner_list[:@IDX2].xval

    -   # Does nothing exceppt test that it's OK not to have the cosumes section
        func_name: fun5
        path: ./components/comp5.py
        provides:
            - name: yval
              path: number5

    -   # Does nothing except test that it's OK not to have the input section
        func_name: fun6
        path: ./components/comp6.py
        provides:
            - name: yval
              path: number6
        consumes:
            results:
                - name: yval2
                  path: list[IDX1].some_attr.two_x_numbers

    """

yml_input = """
    list:
        - some_attr:
            numbers: [0.2, 0.3]
            factors: [2., 3.]
            x_to_y_fact: 2.
            inner_list:
                - 
                    xval: 1.
                - 
                    xval: 2.
        - some_attr:
            numbers: [0.4, 0.5]
            factors: [4., 5.]
            x_to_y_fact: 3.
            inner_list:
                - 
                    xval: 3.
                - 
                    xval: 4.
    """
