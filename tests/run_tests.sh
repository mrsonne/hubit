cd ..
coverage run --source=hubit -m unittest discover -s ./tests -p "*_test.py"
coverage report -m  
coverage html -d htmlcov 
black --check .
cd tests
read -n 1 -s -r -p "Press any key to continue"