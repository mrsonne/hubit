cd ..
coverage run --source=. -m unittest discover -s ./tests -p "*_test.py"
coverage report -m --omit='./tests/*','./examples/*','./docs/*','setup.py' 
coverage html --omit='./tests/*','./examples/*','./docs/*','setup.py' -d htmlcov 
cd tests
read -n 1 -s -r -p "Press any key to continue"